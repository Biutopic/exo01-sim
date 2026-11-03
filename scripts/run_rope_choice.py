"""Does the winch's own 4.8 mm synthetic rope work for the front V, instead of 12-14 mm polyester?

Compares rope stiffness over the real V geometry: the tension needed for a target rear preload, the winch travel to
reach it, and - the question that decides it - how much preload survives a few millimetres of bumper creep or surge.

    python scripts/run_rope_choice.py   ->  results/coupling/rope_choice.json
"""
import json, sys, warnings
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); warnings.simplefilter("ignore")
import numpy as np  # noqa: E402
src = (ROOT / "scripts" / "run_final_coupling.py").read_text()
head = src.split("# ──────────────────────────────────────────────────────────────── A ·")[0]
ns = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "rope"}
exec(compile(head, "head", "exec"), ns)
solve, elements, BASE, K_BUMP = ns["solve"], ns["elements"], ns["BASE"], ns["K_BUMP"]

# Rope axial stiffness over the whole V path (2 legs, 11.0 m total). EA is the unknown; these are the published
# material ranges, not measured values for the actual products.
L_PATH = 11.02
ROPES = {
    "polyester 12 mm (soft, bedded in)": dict(EA_kN=80,   d_mm=12),
    "polyester 12 mm (typical)":         dict(EA_kN=150,  d_mm=12),
    "polyester 14 mm (stiff)":           dict(EA_kN=300,  d_mm=14),
    "UHMWPE 4.8 mm (winch rope)":        dict(EA_kN=1810, d_mm=4.8),   # E ~100 GPa x 18.1 mm2
}
for r in ROPES.values():
    r["k_N_per_m"] = 1000 * r["EA_kN"] / L_PATH

TARGET = 2000.0          # N of rear bumper compression we want to hold
CREEP_MM = [0, 1, 2, 5, 10]
out = {}
for name, r in ROPES.items():
    k = r["k_N_per_m"]
    # commanded preload that lands on the target
    lo, hi = 1.0, 60000.0
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        els = [dict(e, stiffness_N_per_m=k) if e["id"] == "VEE_ROPE" else e for e in elements(mid, **BASE)]
        f = solve(els)["bumper_total_N"]
        lo, hi = (mid, hi) if f < TARGET else (lo, mid)
    T0 = 0.5 * (lo + hi)
    base = solve([dict(e, stiffness_N_per_m=k) if e["id"] == "VEE_ROPE" else e for e in elements(T0, **BASE)])
    # creep: the foam bumpers take a permanent set of c mm -> modelled as a contact gap
    rows = []
    for c in CREEP_MM:
        els = []
        for e in elements(T0, **BASE):
            e = dict(e)
            if e["id"] == "VEE_ROPE":
                e["stiffness_N_per_m"] = k
            elif e["id"].startswith("BUMPER"):
                e["gap_m"] = c / 1000.0
            els.append(e)
        s = solve(els)
        rows.append(dict(creep_mm=c, bumper_total_N=s["bumper_total_N"], rope_N=s["rope_N"],
                         kept_pct=100 * s["bumper_total_N"] / max(base["bumper_total_N"], 1e-9)))
    out[name] = dict(**r, commanded_T0_N=T0, rope_tension_N=base["rope_N"], pulley_N=base["pulley_N"],
                     bumper_N=base["bumper_total_N"], boat_dx_mm=base["dx_mm"],
                     dT_per_mm_N=2 * k * np.cos(np.radians(base["vee_half_angle_deg"])) / 1000.0,
                     creep=rows)
    print(f"{name:34s} k {k/1000:7.1f} kN/m | tension {base['rope_N']:6.0f} N | "
          f"dT/dmm {out[name]['dT_per_mm_N']:6.1f} N/mm | preload left after 2 mm creep: "
          f"{rows[2]['kept_pct']:5.1f} %  after 5 mm: {rows[3]['kept_pct']:5.1f} %", flush=True)

(ROOT / "results" / "coupling" / "rope_choice.json").write_text(json.dumps(
    dict(label="Exploratory - rope EA from published material ranges, not measured on the actual product.",
         path_length_m=L_PATH, target_bumper_N=TARGET, ropes=out), indent=1, default=str))
print("\nwritten results/coupling/rope_choice.json")
