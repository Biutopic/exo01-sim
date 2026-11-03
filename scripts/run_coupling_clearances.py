"""Supplementary pass: hull-to-float and transom clearances at the design preload for the governing load cases,
folded into results/coupling/final_coupling.json (the main sweep's extractor missed the nested clearance dict).

    python scripts/run_coupling_clearances.py
"""
import json, sys, warnings
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT)); warnings.simplefilter("ignore")
src = (ROOT / "scripts" / "run_final_coupling.py").read_text()
head = src.split("# ──────────────────────────────────────────────────────────────── A ·")[0]
ns = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "clr"}
exec(compile(head, "head", "exec"), ns)

J = ROOT / "results" / "coupling" / "final_coupling.json"
R = json.loads(J.read_text())
T_DES = R["design_preload_N"]
out = {}
for cid, c in R["cases"].items():
    r = ns["solve"](ns["elements"](T_DES, **ns["BASE"]), surge_N=c["surge_N"], yaw_Nm=c["yaw_Nm"])
    out[cid] = dict(preload_N=T_DES, hull_to_float_min_m=r["hull_to_float_min_m"],
                    transom_to_deck_m=r["transom_to_deck_m"], flags=r["clearance_flags"],
                    dx_mm=r["dx_mm"], dy_mm=r["dy_mm"], dyaw_deg=r["dyaw_deg"],
                    rope_N=r["rope_N"], pulley_N=r["pulley_N"], bumper_min_N=r["bumper_min_N"],
                    bumper_max_N=r["bumper_max_N"], wheel_max_N=r["wheel_max_N"])
    print(f"  {cid:9s} clearance {r['hull_to_float_min_m']:.3f} m, transom {r['transom_to_deck_m']:.3f} m, "
          f"wheel {r['wheel_max_N']:6.0f} N, yaw {r['dyaw_deg']:+.2f}°", flush=True)
R["clearances_at_design_preload"] = out
J.write_text(json.dumps(R, indent=1, default=str))
print("folded into", J)
