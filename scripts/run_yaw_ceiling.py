"""How much differential thrust can each rig hold? -> results/coupling/yaw_ceiling.json

    python scripts/run_yaw_ceiling.py

Section 19 and 20 both bind on `diff_opp` - one pod full ahead, one full astern - and both conclusions were "the
single rope cannot do it". That is true, and it is also answering a question nobody asked. `diff_opp` is a load
case WE chose: it assumes the pods will be driven in full opposition. If they are not, the yaw demand falls and
the simple rig may be sufficient.

So this reframes the choice as a control limit rather than a rigging limit: for each rig and preload, what is the
largest differential thrust that still leaves a restrained equilibrium with the bumpers loaded?

The differential fraction f puts one pod at +f and the other at -f of bollard thrust: yaw = f * T_bollard * y_pod,
net surge zero. f = 1,0 is `diff_opp`. f = 0,5 is roughly "one pod on, one off" in yaw terms. All the pure-surge
cases (forward, reverse, emergency stop) are checked at every point too - a rig that fails those fails outright.
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
NS = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "yawceil"}
exec(compile(head, "head", "exec"), NS)
solve, CASES, D = NS["solve"], NS["CASES"], NS["D"]
OUT = ROOT / "results" / "coupling"
# the gauntlet's own gate (scripts/run_arrangement_search.py): below this a rear bumper is
# open and rattling, not loaded. Must match, or these scripts grade on a laxer curve.
BUMP_MIN_N = 50.0

YAW_FULL = D["bollard_N"] * D["y_pod_m"]          # diff_opp, N*m
SURGE_ONLY = [c for c in CASES if abs(c["yaw"]) < 1e-9]
RIGS = ["I_fwd_midship_crossed", "X_yoke_midship_crossed", "Y_full_rove"]
PRELOADS = [600.0, 1000.0, 1500.0, 2000.0]
FRACS = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def ok(rig, t0, surge, yaw):
    r = solve(AR.build(rig, preload_N=t0), surge_N=surge, yaw_Nm=yaw)
    if not (r["converged"] and r["physical"]) or r["unrestrained"]:
        return False, "no restrained equilibrium"
    if r.get("bumper_min_N") is not None and r["bumper_min_N"] < BUMP_MIN_N:
        return False, "a bumper opened"
    return True, round(max((v["T_N"] for v in r["elements"].values()
                            if v["kind"] in ("line", "bridle", "yoke")), default=0.0), 1)


rows = []
for rig in RIGS:
    for t0 in PRELOADS:
        surge_fail = next((c["id"] for c in SURGE_ONLY if not ok(rig, t0, c["surge"], 0.0)[0]), None)
        best, peak = None, None
        if surge_fail is None:
            for f in FRACS:
                good, info = ok(rig, t0, 0.0, f * YAW_FULL)
                if not good:
                    break
                best, peak = f, info
        rows.append(dict(rig=rig, preload_N=t0, surge_cases_ok=(surge_fail is None), surge_failed=surge_fail,
                         max_diff_fraction=best, peak_T_N=peak))
        tag = ("surge FAILS at " + surge_fail) if surge_fail else (
            f"differential ceiling {best:.0%}" + (f", peak {peak:.0f} N" if peak else ""))
        print(f"  {rig:24s} preload {t0:6.0f} N | {tag}", flush=True)
    print(flush=True)

res = dict(yaw_full_Nm=round(YAW_FULL, 1), bollard_N=D["bollard_N"], y_pod_m=D["y_pod_m"],
           surge_cases=[c["id"] for c in SURGE_ONLY], fractions=FRACS, rows=rows,
           note="The differential fraction f drives one pod to +f and the other to -f of bollard thrust. "
                "f = 1,0 is the diff_opp design case. Statics only; the wave cases are separate.")
(OUT / "yaw_ceiling.json").write_text(json.dumps(res, indent=1, default=str))
print(f"written {OUT/'yaw_ceiling.json'}  (full differential = {YAW_FULL:.0f} N*m)")
