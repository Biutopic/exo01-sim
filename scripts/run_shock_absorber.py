"""How soft should the shock absorber be? -> results/coupling/shock_absorber.json

    python scripts/run_shock_absorber.py [--quick]

The user's rig puts a shock absorber (a "ressort") IN SERIES with the coupling rope. A series spring cannot change
what the coupling has to hold - statics are statics - but it changes three things that matter:

  * the stiffness the boat feels, k_eff = 1/(1/k_rope + 1/k_shock), which the SOFTER element dominates;
  * how far the boat moves before the rope takes up, which is what the stroke budget has to cover;
  * the peak in a wave, because a softer path turns a displacement excursion into less force.

So the question is not "is a shock absorber good" - it is "how soft before the travel becomes unacceptable". This
sweeps k_shock against arrangement I's primary pair, with everything else held exactly as the selected arrangement.

Against the model's limits: the absorber is treated as a LINEAR spring with unlimited stroke. A real shock absorber
is neither - it is progressive, hysteretic, and bottoms out. Both are recorded with the result.
"""
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.simplefilter("ignore")
import numpy as np  # noqa: E402

from exo01 import arrangements as AR  # noqa: E402

src = (ROOT / "scripts" / "run_final_coupling.py").read_text()
head = src.split("# ──────────────────────────────────────────────────────────────── A · preload sweep")[0]
NS = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "shock"}
exec(compile(head, "head", "exec"), NS)
solve, CASES, K_ROPE = NS["solve"], NS["CASES"], NS["K_ROPE"]

OUT = ROOT / "results" / "coupling"
OUT.mkdir(parents=True, exist_ok=True)
QUICK = "--quick" in sys.argv
K_R = K_ROPE["mid"]
# k_shock in N/m. 1e9 = no absorber at all (the selected arrangement). The low end is a bungee; the middle is a
# commercial mooring compensator; the high end is a short length of nylon rather than a fitting.
K_SHOCK = [1e9, 27000.0, 13500.0, 8000.0, 5000.0, 3000.0, 2000.0, 1200.0, 800.0, 500.0]
if QUICK:
    K_SHOCK = [1e9, 5000.0, 1200.0]
PRELOADS = [200, 400, 600, 800, 1200, 1600, 2200, 3000]


def series(k_shock):
    return 1.0 / (1.0 / K_R + 1.0 / k_shock)


def build(k_eff, t0, snug=AR.T_SNUG):
    """Arrangement I, with the primary pair's path stiffness replaced by the series value."""
    els = AR.build("I_fwd_midship_crossed", preload_N=t0, snug_N=snug)
    for e in els:
        if e["id"].startswith("SPRING"):
            e["stiffness_N_per_m"] = k_eff
    return els


def statics(k_eff, t0):
    """Every static case, with the arrangement-search gate: converged, physical, restrained, bumpers still loaded."""
    worst_T, worst_case, dx, dyaw, bmin = 0.0, None, 0.0, 0.0, None
    for c in CASES:
        r = solve(build(k_eff, t0), surge_N=c["surge"], yaw_Nm=c["yaw"])
        if not (r["converged"] and r["physical"]) or r["unrestrained"]:
            return dict(ok=False, failed_case=c["id"])
        if r.get("bumper_min_N") is not None and r["bumper_min_N"] <= 1.0:
            return dict(ok=False, failed_case=c["id"], reason="a bumper opened")
        T = max((v["T_N"] for v in r["elements"].values()
                 if v["kind"] in ("line", "bridle", "yoke")), default=0.0)
        if T > worst_T:
            worst_T, worst_case = T, c["id"]
        dx = max(dx, abs(r["dx_mm"]))
        dyaw = max(dyaw, abs(r["dyaw_deg"]))
        bmin = r["bumper_min_N"] if bmin is None else min(bmin, r["bumper_min_N"])
    return dict(ok=True, peak_T_N=worst_T, peak_case=worst_case, max_dx_mm=dx, max_dyaw_deg=dyaw,
                bumper_min_N=bmin)


rows = []
for ks in K_SHOCK:
    keff = series(ks)
    Tmin = None
    for t0 in PRELOADS:
        if statics(keff, t0)["ok"]:
            Tmin = t0
            break
    at600 = statics(keff, 600.0)
    row = dict(k_shock_N_per_m=(None if ks > 1e8 else ks), k_eff_N_per_m=round(keff, 1),
               min_preload_N=Tmin, at_600N=at600)
    if at600["ok"] and ks < 1e8:
        # what the absorber itself has to travel: its own extension under preload and under the peak
        row["stroke_at_preload_mm"] = round(1000.0 * 600.0 / ks, 1)
        row["stroke_at_peak_mm"] = round(1000.0 * at600["peak_T_N"] / ks, 1)
        row["extra_travel_vs_rope_mm"] = round(1000.0 * at600["peak_T_N"] * (1.0 / ks), 1)
    rows.append(row)
    lab = "none (rope only)" if ks > 1e8 else f"{ks:.0f} N/m"
    pk = f"{at600['peak_T_N']:.0f} N" if at600["ok"] else f"FAILS ({at600.get('failed_case')})"
    st = f", stroke {row.get('stroke_at_peak_mm', 0):.0f} mm" if "stroke_at_peak_mm" in row else ""
    print(f"  absorber {lab:>16s} | k_eff {keff:8.0f} N/m | min preload {str(Tmin):>5s} N | peak @600 N {pk}{st}",
          flush=True)

res = dict(arrangement="I_fwd_midship_crossed", k_rope_N_per_m=K_R, cases=[c["id"] for c in CASES], rows=rows,
           caveats=["The absorber is modelled as a LINEAR spring of unlimited stroke. Real mooring compensators are "
                    "progressive and hysteretic, and they bottom out: past that point the rope stiffness returns in "
                    "full and the peak is the rope-only peak, not the soft one.",
                    "Stroke is the ABSORBER's own extension. The boat's displacement is reported separately as "
                    "max_dx_mm and includes it.",
                    "Statics cannot be improved by a series spring - the same load must be carried. What changes is "
                    "displacement, and in a wave, the peak."])
(OUT / "shock_absorber.json").write_text(json.dumps(res, indent=1, default=str))
print(f"\nwritten {OUT/'shock_absorber.json'}")
