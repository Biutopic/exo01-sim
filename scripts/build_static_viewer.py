"""Build a server-free 3D viewer for GitHub Pages -> docs/simulator/

    python scripts/build_static_viewer.py

app.py + web/ is the real simulator: it solves on demand. This is a static build of the same scene and the same
physics, for a browser with no Python behind it. Two things are therefore different, and the page says so:

  * the coupling solves are PRECOMPUTED, one per arrangement per load case, rather than solved on demand;
  * the speed, wind and energy model runs live in the browser, from the same geometry-derived card the Python
    module uses, so those numbers are computed rather than looked up.

Everything is copied into docs/simulator/ so GitHub Pages can serve it from the /docs folder on main.
"""
import json
import shutil
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.simplefilter("ignore")
import numpy as np  # noqa: E402

from exo01 import arrangements as AR  # noqa: E402
from exo01.analysis import evaluate  # noqa: E402
from exo01.config import load_config, resolve  # noqa: E402
from exo01.twobody import coupled_equilibrium  # noqa: E402

OUT = ROOT / "docs" / "simulator"
(OUT / "vendor").mkdir(parents=True, exist_ok=True)
(OUT / "assets").mkdir(parents=True, exist_ok=True)

ill = load_config("illustrative")

LOAD_CASES = [
    dict(id="still", label="still water, moored", surge=0.0, sway=0.0, yaw=0.0),
    dict(id="fwd100", label="forward 100 %", surge=554.0, sway=0.0, yaw=0.0),
    dict(id="rev100", label="reverse 100 %", surge=-818.0, sway=0.0, yaw=0.0),
    dict(id="diff_opp", label="one pod ahead, one astern", surge=0.0, sway=0.0, yaw=2395.5),
    dict(id="wind20_beam", label="20 kn beam wind, moored", surge=0.0, sway=33.0, yaw=0.0),
]


def cfg_for(els):
    return resolve(ill, {"host_boat": {"lines": els,
                                       "placement_in_exo_frame": dict(ill["host_boat"]["placement_in_exo_frame"],
                                                                      x_m=AR.X_BERTH)},
                         "propulsion": {"thrust_fraction": 0.0}})


_base = evaluate(cfg_for(AR.build("I_fwd_midship_crossed")))
ASM, BASM = _base["_assembly"], _base["_boat_assembly"]
M_E, G_E = _base["mass"]["total_mass_kg"], _base["mass"]["com_m"]
_BB = _base["bodies"]["boat"]["mass"]
M_B, G_B = _BB["total_mass_kg"], _BB["com_m"]
RHO = float((ill.get("environment") or {}).get("water_density_kg_m3") or 1000.0)
G = 9.80665


def pose_of(eq):
    return dict(R=np.asarray(eq["R"], float).tolist(), G_body=np.asarray(eq["G_body"], float).tolist(),
                zG=float(eq["zG"]), com_world=np.asarray(eq["com_world"], float).tolist()
                if eq.get("com_world") is not None else None)


def solve_case(els, surge, sway, yaw):
    cfg = cfg_for(els)

    def external(pe, pb):
        Fb = np.array([-surge, -sway, 0.0])
        Mb = np.array([0.0, 0.0, -yaw])
        return -Fb, -Mb - np.cross(np.asarray(pb["com_world"]) - np.asarray(pe["com_world"]), Fb), Fb, Mb

    eq, beq, pe, pb, lines, info, q = coupled_equilibrium(cfg, ASM, M_E, G_E, BASM, M_B, G_B, RHO, G,
                                                          external=external)
    bump = [-float(l["tension_N"]) for l in lines if l["id"].startswith("BUMPER")]
    return dict(
        ok=bool(info.get("converged")) and abs(q[3]) < 0.3 and abs(q[4]) < 0.3 and abs(np.degrees(q[5])) < 15,
        converged=bool(info.get("converged")),
        dx_mm=round(1000 * float(q[3]), 2), dy_mm=round(1000 * float(q[4]), 2),
        dyaw_deg=round(float(np.degrees(q[5])), 3),
        bumper_min_N=round(min(bump), 1) if bump else None,
        tensions={l["id"]: round(float(l["tension_N"]), 1) for l in lines},
        exo_pose=pose_of(dict(eq, com_world=pe["com_world"])),
        boat_pose=pose_of(dict(beq, com_world=pb["com_world"])))


data = {"arrangements": {}, "load_cases": LOAD_CASES, "default": AR.DEFAULT,
        "catalogue": AR.catalogue(), "snug_N": AR.T_SNUG, "stiffness_note": AR.STIFFNESS_NOTE,
        "berth_x_m": AR.X_BERTH, "z_datum_offset_m": AR.Z_DATUM_OFFSET}

t0 = time.time()
for aid in AR.ARRANGEMENTS:
    els = AR.build(aid)
    rec = dict(geometry=AR.element_geometry(aid), cases={})
    for c in LOAD_CASES:
        try:
            rec["cases"][c["id"]] = solve_case(els, c["surge"], c["sway"], c["yaw"])
        except Exception as e:  # noqa: BLE001
            rec["cases"][c["id"]] = dict(ok=False, error=f"{type(e).__name__}: {e}")
    data["arrangements"][aid] = rec
    n_ok = sum(1 for v in rec["cases"].values() if v.get("ok"))
    print(f"  {aid:24s} {len(rec['geometry'])} elements, {n_ok}/{len(LOAD_CASES)} cases hold "
          f"({time.time() - t0:.0f} s)", flush=True)

# the live speed/wind/energy card
perf = json.loads((ROOT / "results" / "performance" / "performance.json").read_text())
data["card"] = perf["card"]
data["card"]["exo_frame"] = {k: perf["windage"]["EXO"]["structure"].get(k)
                             for k in ("frame_A_front_m2", "frame_A_lateral_m2", "panel_A_plan_m2",
                                       "solidity_frontal", "solidity_lateral", "envelope_height_m",
                                       "envelope_width_m")}
data["card"]["boat_windage"] = {k: perf["windage"]["BOAT"][k]
                                for k in ("A_front_m2", "A_lateral_m2", "z_lateral_m", "L_m")}
data["card"]["pose"] = perf["pose"]
data["generated"] = perf["generated"]

(OUT / "data.json").write_text(json.dumps(data, separators=(",", ":"), default=str))
print(f"\ndata.json {(OUT / 'data.json').stat().st_size / 1024:.0f} kB")

# assets: the two reference models and the three.js pieces the page imports
for src, dst in ((ROOT / "data" / "reference_v3" / "EXO01_reference.glb", "exo.glb"),
                 (ROOT / "data" / "renaud8000_v1" / "Renaud8000_reference.glb", "boat.glb")):
    shutil.copyfile(src, OUT / "assets" / dst)
# the whole three.js tree: GLTFLoader imports ../utils/BufferGeometryUtils.js by relative path, so flattening breaks it
V = ROOT / "web" / "vendor" / "three"
dst = OUT / "vendor" / "three"
if dst.exists():
    shutil.rmtree(dst)
shutil.copytree(V, dst)
print(f"assets and vendor copied ({sum(f.stat().st_size for f in dst.rglob('*') if f.is_file()) / 1024:.0f} kB of three.js)")

shutil.copyfile(ROOT / "scripts" / "templates" / "simulator_page.html", OUT / "index.html")
print(f"written {OUT/'index.html'}")
