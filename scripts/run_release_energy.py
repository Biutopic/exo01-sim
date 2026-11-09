"""What happens when the coupling is released? -> results/coupling/release_energy.json

    python scripts/run_release_energy.py

Emergency release is a requirement the cahier des charges does not state and the study never tested: if something
goes wrong, how fast can the boat be freed, and is letting go violent?

Every element is a spring holding stored energy, 1/2 k x^2. Release them all at once and that energy goes into
separating the two bodies. This reports it per element and in total, for the selected arrangement and for the
single-rope alternative, at rest and at the worst static case.

What this does NOT model: the separation transient itself (two free bodies in water), or what the pods are doing
at the moment of release. Both are noted as requirements rather than computed.
"""
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.simplefilter("ignore")

from exo01 import arrangements as AR  # noqa: E402

src = (ROOT / "scripts" / "run_final_coupling.py").read_text()
head = src.split("# ──────────────────────────────────────────────────────────────── A · preload sweep")[0]
NS = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "rel"}
exec(compile(head, "head", "exec"), NS)
solve, CASES = NS["solve"], NS["CASES"]
OUT = ROOT / "results" / "coupling"

RIGS = [("I_fwd_midship_crossed", 600.0), ("Y_full_rove", 2500.0)]
CASE = {c["id"]: c for c in CASES}


def energy(rig, t0, case_id):
    c = CASE[case_id]
    els = AR.build(rig, preload_N=t0)
    k = {e["id"]: float(e["stiffness_N_per_m"]) for e in els}
    r = solve(els, surge_N=c["surge"], yaw_Nm=c["yaw"])
    per, tot = {}, 0.0
    for eid, v in r["elements"].items():
        T = abs(float(v["T_N"]))
        kk = k.get(eid, 0.0)
        if kk <= 0 or T <= 0:
            continue
        E = 0.5 * T * T / kk                       # 1/2 k x^2 with x = T/k
        per[eid] = dict(T_N=round(T, 1), k_N_per_m=kk, extension_mm=round(1000.0 * T / kk, 1), energy_J=round(E, 2))
        tot += E
    return dict(case=case_id, total_J=round(tot, 1), per_element=per,
                equivalent_drop_kg_1m=round(tot / 9.80665, 2))


res = {}
for rig, t0 in RIGS:
    res[rig] = dict(preload_N=t0, states={cid: energy(rig, t0, cid) for cid in ("moored", "diff_opp")})
    for cid, v in res[rig]["states"].items():
        print(f"  {rig:24s} {cid:9s} preload {t0:5.0f} N | stored {v['total_J']:6.1f} J "
              f"(= dropping {v['equivalent_drop_kg_1m']:.1f} kg from 1 m)")
    worst = max(res[rig]["states"]["diff_opp"]["per_element"].items(), key=lambda kv: kv[1]["energy_J"])
    print(f"      most energetic single element: {worst[0]} at {worst[1]['energy_J']:.1f} J, "
          f"{worst[1]['extension_mm']:.0f} mm of stretch", flush=True)

res["requirements_not_modelled"] = [
    "The separation transient: two free bodies in water, not solved here.",
    "Pod state at release. Freeing the EXO with its pods driving produces a loose powered platform; any release "
    "arrangement has to kill propulsion in the same action or before it.",
    "Release force at the fitting. A rope clutch under load can be hard to open by hand; a quick-release shackle "
    "is designed to let go under load. Which fitting is used decides whether release is actually seconds.",
]
(OUT / "release_energy.json").write_text(json.dumps(res, indent=1, default=str))
print(f"\nwritten {OUT/'release_energy.json'}")
