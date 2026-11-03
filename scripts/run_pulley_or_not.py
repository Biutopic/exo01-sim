"""Is the bow pulley worth having, and what does the front fender actually carry?

Compares three front arrangements at the same rear preload:
  A  bridle  - one rope over a pulley: the tension equalises (what the brief specifies)
  B  two fixed legs - the rope is made off at the bow (or simply bears on the fender): each leg is independent
  C  the same, with the anchors raised to 1.00 m

Reports the yaw stiffness each one actually provides, the load each leg carries, and the bearing pressure on the bow
for plausible contact widths.      ->  results/coupling/pulley_or_not.json
"""
import json, sys, warnings
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); warnings.simplefilter("ignore")
import numpy as np  # noqa: E402
src = (ROOT / "scripts" / "run_final_coupling.py").read_text()
head = src.split("# ──────────────────────────────────────────────────────────────── A ·")[0]
ns = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "p"}
exec(compile(head, "head", "exec"), ns)
solve, elements, BASE, K_ROPE = ns["solve"], ns["elements"], ns["BASE"], ns["K_ROPE"]
XV, YV, XBOW = 5.20, 2.25, 8.00

def front(mode, T0, zv=0.30, k=None):
    """mode 'bridle' = one rope over a pulley; 'legs' = two independent legs of twice the stiffness each
    (a rope of half the length has twice the axial stiffness, so this is the same rope made off at the bow)."""
    k = k or K_ROPE["mid"]
    if mode == "bridle":
        return [dict(id="VEE_ROPE", kind="bridle", exo_point_m=[XV, YV, zv], exo_point_b_m=[XV, -YV, zv],
                     boat_point_m=[XBOW, 0.0, 0.78], stiffness_N_per_m=k, pretension_N=T0)]
    return [dict(id=f"LEG_{nm}", kind="line", exo_point_m=[XV, s * YV, zv], boat_point_m=[XBOW, 0.0, 0.78],
                 stiffness_N_per_m=2 * k, pretension_N=T0 / 2.0) for s, nm in ((+1, "PORT"), (-1, "STBD"))]

def run(mode, T0, zv=0.30):
    els = front(mode, T0, zv) + [e for e in elements(0.0, **BASE) if e["id"] != "VEE_ROPE"]
    out = {}
    for cid in ("moored", "diff_one", "diff_opp"):
        c = ns["cases"] if False else None
        pass
    return els

CASES = {"moored": (0.0, 0.0), "diff_one": (+422.0, 1198.0), "diff_opp": (0.0, 2396.0)}
res = {}
for label, (mode, zv) in {"A bridle (pulley), anchors 0.30 m": ("bridle", 0.30),
                          "B two fixed legs, anchors 0.30 m": ("legs", 0.30),
                          "C two fixed legs, anchors 1.00 m": ("legs", 1.00)}.items():
    # match the rear preload to 1972 N so the three are compared at equal clamping
    lo, hi = 1.0, 30000.0
    for _ in range(36):
        mid = 0.5 * (lo + hi)
        els = front(mode, mid, zv) + [e for e in elements(0.0, **BASE) if e["id"] != "VEE_ROPE"]
        f = solve(els)["bumper_total_N"]
        lo, hi = (mid, hi) if f < 1972.0 else (lo, mid)
    T0 = 0.5 * (lo + hi)
    rows = {}
    for cid, (su, yw) in CASES.items():
        els = front(mode, T0, zv) + [e for e in elements(0.0, **BASE) if e["id"] != "VEE_ROPE"]
        r = solve(els, surge_N=su, yaw_Nm=yw)
        legs = {k: v["T_N"] for k, v in r["elements"].items() if k.startswith("LEG") or k == "VEE_ROPE"}
        rows[cid] = dict(dyaw_deg=r["dyaw_deg"], dy_mm=r["dy_mm"], bumper_min_N=r["bumper_min_N"],
                         wheel_max_N=r["wheel_max_N"], legs={k: round(v) for k, v in legs.items()},
                         front_resultant_N=r["pulley_N"] if mode == "bridle" else None)
    res[label] = dict(mode=mode, anchor_z_m=zv, commanded_T0_N=T0, cases=rows)
    y = rows["diff_opp"]
    print(f"{label:34s} T0 {T0:6.0f} N | yaw under opposed pods {y['dyaw_deg']:+6.2f}°, "
          f"wheel {y['wheel_max_N']:5.0f} N, legs {y['legs']}", flush=True)

# bearing pressure on the bow if the rope bears on a fender instead of running over a pulley
F = 1972.0
press = {}
for w_mm, L_mm in ((10, 200), (30, 250), (50, 300), (120, 400)):
    a = (w_mm / 1000) * (L_mm / 1000)
    press[f"{w_mm} x {L_mm} mm"] = dict(area_m2=round(a, 4), kPa=round(F / a / 1000, 1), bar=round(F / a / 1e5, 2))
    print(f"  bearing {w_mm:3d} x {L_mm:3d} mm -> {F/a/1000:7.1f} kPa ({F/a/1e5:.2f} bar) for {F:.0f} N")
(ROOT / "results" / "coupling" / "pulley_or_not.json").write_text(json.dumps(
    dict(label="Exploratory. Rear preload matched to 1972 N in all three arrangements.",
         arrangements=res, bow_bearing_pressure=press, resultant_N=F), indent=1, default=str))
print("\nwritten results/coupling/pulley_or_not.json")
