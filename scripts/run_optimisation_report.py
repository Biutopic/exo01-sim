"""Battery-position and line-arrangement sweeps on the illustrative configuration -> results/optimisation/ (md, csv, png).

Uses the shipped/cached BEM of the base poses for the wave columns (exact COM transform, nearby-pose reuse); run
scripts/precompute_cache.py first if the wave columns come out empty.
"""
import csv
import json
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.simplefilter("ignore")
import numpy as np  # noqa: E402

from exo01.analysis import HYDRO_DEFAULTS  # noqa: E402
from exo01.config import load_config, load_scenario, resolve_scenario  # noqa: E402
from exo01.optimise import run_optimisation  # noqa: E402

OUT = ROOT / "results" / "optimisation"
OUT.mkdir(parents=True, exist_ok=True)
WAVE = dict(H_m=0.3, T_s=2.5, heading_deg=90)
DAMP = {"EXO": {"zeta": {"heave": 0.05, "roll": 0.05, "pitch": 0.05}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}},
        "BOAT": {"zeta": {"heave": 0.05, "roll": 0.10, "pitch": 0.10}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}}}


def fmt(v, d=2):
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.{d}f}"
    if isinstance(v, list):
        return ", ".join(map(str, v)) or "none"
    return str(v)


def write(name, out, cols):
    rows = sorted([r for r in out["rows"] if r["feasible"]], key=lambda r: r["rank"])
    with (OUT / f"{name}.csv").open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow([c[0] for c in cols])
        for r in rows:
            w.writerow([fmt(c[1](r), c[2] if len(c) > 2 else 2) for c in cols])
    md = [f"# {name} sweep — {out['label']}", "", f"Reference wave H {WAVE['H_m']} m, T {WAVE['T_s']} s, heading {WAVE['heading_deg']}°; "
          f"{out['n_candidates']} candidates in {out['seconds']:.0f} s. {out['hydro_note']}", ""]
    md.append("| " + " | ".join(c[0] for c in cols) + " |")
    md.append("|" + "---|" * len(cols))
    for r in rows:
        md.append("| " + " | ".join(fmt(c[1](r), c[2] if len(c) > 2 else 2) for c in cols) + " |")
    md += ["", *[f"* {n}" for n in out["notes"]]]
    (OUT / f"{name}.md").write_text("\n".join(md))
    (OUT / f"{name}.json").write_text(json.dumps(out, indent=1, default=str))
    return rows


def main():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = time.time()
    # ---- batteries: EXO alone and with the boat
    for tag, scen in (("battery_exo_only", "baseline_illustrative"), ("battery_with_boat", "with_hydronaute")):
        cfg = resolve_scenario(load_scenario(scen))
        out = run_optimisation(cfg, "battery", WAVE, DAMP, dict(HYDRO_DEFAULTS), progress=lambda f, m: print(f"  {m}", end="\r"))
        cols = [("rank", lambda r: r["rank"]), ("zone", lambda r: r["candidate"]["zone"]), ("x [m]", lambda r: r["candidate"]["x_m"]),
                ("y stbd [m]", lambda r: r["candidate"]["y_stbd_m"]),
                ("y port [m]", lambda r: r["candidate"]["y_port_m"]), ("trim [°]", lambda r: r["trim_deg"]), ("heel [°]", lambda r: r["heel_deg"]),
                ("deck fb min [m]", lambda r: r["deck_freeboard_min_m"], 3), ("GM_T [m]", lambda r: r["GM_T_m"], 1), ("COM z [m]", lambda r: r["com_z_m"], 3),
                ("roll amp [°]", lambda r: r.get("roll_amp_deg")), ("pitch amp [°]", lambda r: r.get("pitch_amp_deg")),
                ("heave amp [m]", lambda r: r.get("heave_amp_m"), 3), ("deck a_z [m/s²]", lambda r: r.get("deck_accel_max_ms2")),
                ("line min [N]", lambda r: r.get("line_min_N"), 0), ("slack", lambda r: r.get("slack_lines")), ("score", lambda r: r["score"])]
        rows = write(tag, out, cols)
        print(f"\n{tag}: best {rows[0]['candidate']['zone']} x={rows[0]['candidate']['x_m']} y=({rows[0]['candidate']['y_stbd_m']}, "
              f"{rows[0]['candidate']['y_port_m']}) trim {rows[0]['trim_deg']:.2f} heel {rows[0]['heel_deg']:.2f}; zero trim x={fmt(out.get('x_zero_trim_m'))}")
        # plot trim and roll amplitude vs x for the symmetric rail row
        sym = [r for r in rows if r["candidate"]["symmetric"] and r["candidate"]["y_stbd_m"] == 2.05]
        sym.sort(key=lambda r: r["candidate"]["x_m"])
        if sym:
            fig, ax = plt.subplots(1, 2, figsize=(10, 3.6))
            ax[0].plot([r["candidate"]["x_m"] for r in sym], [r["trim_deg"] for r in sym], "o-")
            ax[0].axhline(0, color="k", lw=0.6); ax[0].axvline(2.1, color="grey", ls="--", lw=0.8)
            ax[0].text(1.0, ax[0].get_ylim()[1] * 0.9, "rear deck", ha="center", fontsize=8, color="grey")
            ax[0].text(3.5, ax[0].get_ylim()[1] * 0.9, "float-top frames", ha="center", fontsize=8, color="grey")
            ax[0].set_xlabel("battery x [m] (both at |y| 2.05 m, above the floats)"); ax[0].set_ylabel("trim [°]  (− = rear deck down)"); ax[0].grid(alpha=.3)
            if sym[0].get("roll_amp_deg") is not None:
                ax[1].plot([r["candidate"]["x_m"] for r in sym], [r["roll_amp_deg"] for r in sym], "o-", label="roll")
                ax[1].plot([r["candidate"]["x_m"] for r in sym], [r["pitch_amp_deg"] for r in sym], "s-", label="pitch")
                ax[1].set_ylabel("amplitude [°] at H 0.3 m, T 2.5 s, beam"); ax[1].legend(); ax[1].grid(alpha=.3)
            ax[1].set_xlabel("battery x [m]")
            fig.suptitle(f"{tag} — {out['label']}", color="#b5651d", fontsize=9)
            fig.tight_layout(); fig.savefig(OUT / f"{tag}.png", dpi=130); plt.close(fig)
    # ---- lines
    if "--battery-only" in sys.argv:
        print(f"done (battery only) in {time.time() - t:.0f} s -> {OUT}")
        return
    cfg = resolve_scenario(load_scenario("with_hydronaute"))
    out = run_optimisation(cfg, "lines", WAVE, DAMP, dict(HYDRO_DEFAULTS), progress=lambda f, m: print(f"  {m}", end="\r"))
    cols = [("rank", lambda r: r["rank"]), ("arrangement", lambda r: r["candidate"]["id"]), ("can push", lambda r: r.get("can_push")),
            ("can tow", lambda r: r.get("can_tow")), ("rest min/max [N]", lambda r: f"{r.get('line_min_N', 0):.0f}/{r.get('line_max_N', 0):.0f}"),
            ("slack at rest", lambda r: r.get("slack_lines")), ("push max [N]", lambda r: r.get("push_line_max_N"), 0),
            ("push slack", lambda r: r.get("push_slack")), ("tow max [N]", lambda r: r.get("tow_line_max_N"), 0), ("tow slack", lambda r: r.get("tow_slack")),
            ("wave slack", lambda r: r.get("lines_slack_in_cycle")), ("min rel. clearance [m]", lambda r: r.get("min_relative_clearance_m"), 3),
            ("EXO roll amp [°]", lambda r: r.get("roll_amp_deg")), ("boat roll amp [°]", lambda r: r.get("boat_roll_amp_deg")),
            ("snatch peak [N]", lambda r: r.get("snatch_peak_N"), 0), ("slack max (cycle)", lambda r: r.get("snatch_slack_fraction_max")),
            ("snatch ratio", lambda r: r.get("snatch_ratio_max")), ("score", lambda r: r["score"])]
    rows = write("lines", out, cols)
    print(f"\nlines: best {rows[0]['candidate']['id']} score {rows[0]['score']:.2f}")
    print(f"done in {time.time() - t:.0f} s -> {OUT}")


if __name__ == "__main__":
    main()
