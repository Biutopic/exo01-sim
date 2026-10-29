"""Pre-compute the BEM cache shipped with the package: the default UI grid for the built-in scenarios and several headings,
so the interface animates immediately (and reuses these for nearby poses / moved masses)."""
import sys, time, warnings
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
warnings.simplefilter("ignore")
import numpy as np
from exo01.config import load_scenario, resolve_scenario
from exo01.analysis import evaluate, hydro_for, HYDRO_DEFAULTS, has_boat

SCEN = sys.argv[1:] or ["baseline_illustrative", "with_hydronaute", "battery_relocated", "battery_float_frame", "occupants_symmetric", "occupants_asymmetric", "floats_glb_capsules"]
HEAD = np.radians([0.0, 45.0, 90.0, 135.0, 180.0])
s = dict(HYDRO_DEFAULTS)
om = np.round(np.arange(s["omega_min"], s["omega_max"] + 1e-9, s["omega_step"]), 10)
for name in SCEN:
    cfg = resolve_scenario(load_scenario(name))
    r = evaluate(cfg)
    if r["status"].get("equilibrium") != "solved":
        print(name, "no equilibrium"); continue
    t = time.time()
    hd = hydro_for(r, cfg, om, HEAD, s)
    print(f"{name}: {'two-body' if has_boat(r) else 'EXO'} BEM {hd.meta['cache']} in {time.time() - t:.0f} s; {hd.meta.get('n_omega')} omegas, headings {np.degrees(hd.headings).round(0).tolist()}", flush=True)
print("done")
