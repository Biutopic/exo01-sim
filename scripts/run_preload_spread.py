"""Does arrangement I survive UNEQUAL spring preloads? -> results/coupling/preload_spread.json

    python scripts/run_preload_spread.py

Reeving the whole coupling as one rope through blocks and jamming each leg afterwards (COUPLING.md section 20) is
attractive operationally: one pull instead of four tensioning actions. But the legs do not come up equal. Each
sheave takes its cut, so tension grades from the hauling tail down to the dead end, by eta^n.

This asks the question that scheme depends on: at what spread does arrangement I stop closing? The port spring is
held at the design 600 N and the starboard one is walked down, which is the worst case - it is the asymmetry that
matters, not the average.

Everything else is the selected arrangement untouched. Statics only: the spread is a preload question, and the
binding case for arrangement I is static (diff_opp), not a wave.
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
NS = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "spread"}
exec(compile(head, "head", "exec"), NS)
solve, CASES = NS["solve"], NS["CASES"]
OUT = ROOT / "results" / "coupling"
# the gauntlet's own gate (scripts/run_arrangement_search.py): below this a rear bumper is
# open and rattling, not loaded. Must match, or these scripts grade on a laxer curve.
BUMP_MIN_N = 50.0

T_HIGH = 600.0
# sheave efficiency eta over n turns: the far leg sits at eta**n of the near one
ETAS = {"ball bearing, 4 turns": 0.97 ** 4, "ball bearing, 8 turns": 0.97 ** 8,
        "plain bush, 4 turns": 0.90 ** 4, "plain bush, 8 turns": 0.90 ** 8}


def build(t_port, t_stbd):
    els = AR.build("I_fwd_midship_crossed", preload_N=T_HIGH)
    for e in els:
        if e["id"] == "SPRING_PORT":
            e["pretension_N"] = t_port
        elif e["id"] == "SPRING_STBD":
            e["pretension_N"] = t_stbd
    return els


def check(t_port, t_stbd):
    worst_T, worst, bmin = 0.0, None, None
    for c in CASES:
        r = solve(build(t_port, t_stbd), surge_N=c["surge"], yaw_Nm=c["yaw"])
        if not (r["converged"] and r["physical"]) or r["unrestrained"]:
            return dict(ok=False, failed_case=c["id"], reason="no restrained equilibrium")
        if r.get("bumper_min_N") is not None and r["bumper_min_N"] < BUMP_MIN_N:
            return dict(ok=False, failed_case=c["id"], reason="a bumper opened")
        T = max((v["T_N"] for v in r["elements"].values()
                 if v["kind"] in ("line", "bridle", "yoke")), default=0.0)
        if T > worst_T:
            worst_T, worst = T, c["id"]
        bmin = r["bumper_min_N"] if bmin is None else min(bmin, r["bumper_min_N"])
    return dict(ok=True, peak_T_N=round(worst_T, 1), peak_case=worst, bumper_min_N=round(bmin, 1))


rows = []
for frac in (1.00, 0.95, 0.90, 0.85, 0.80, 0.75, 0.70, 0.60, 0.50, 0.40, 0.30):
    t_s = T_HIGH * frac
    r = check(T_HIGH, t_s)
    rows.append(dict(ratio=frac, port_N=T_HIGH, stbd_N=round(t_s, 1), **r))
    tag = f"peak {r['peak_T_N']:.0f} N ({r['peak_case']})" if r["ok"] else f"FAILS: {r['reason']} @ {r['failed_case']}"
    print(f"  stbd/port {frac:4.0%}  ({t_s:5.0f} N vs 600 N)  {tag}", flush=True)

worst_ok = min((r["ratio"] for r in rows if r["ok"]), default=None)
print(f"\nholds down to a {worst_ok:.0%} spread" if worst_ok else "\nno spread holds")
print("\nwhat the rove actually delivers:")
hw = []
for lab, eta in ETAS.items():
    ok = next((r["ok"] for r in rows if abs(r["ratio"] - round(eta, 2)) < 0.051), None)
    hw.append(dict(hardware=lab, far_leg_fraction=round(eta, 3)))
    print(f"  {lab:24s} far leg at {eta:5.1%} of the tail")

(OUT / "preload_spread.json").write_text(json.dumps(
    dict(arrangement="I_fwd_midship_crossed", held_leg_N=T_HIGH, cases=[c["id"] for c in CASES],
         rows=rows, tolerated_down_to=worst_ok, hardware=hw,
         caveat="Statics only. The crossed ropes are wave-governed and are NOT varied here; they stay snug."),
    indent=1, default=str))
print(f"\nwritten {OUT/'preload_spread.json'}")
