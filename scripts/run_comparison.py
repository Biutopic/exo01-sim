"""Batch comparison of the built-in scenarios: still water for all, wave response where the BEM is available
(or computed here with --bem). Writes results/comparison/{comparison.csv, comparison.md, *.png, comparison.json}.

    python scripts/run_comparison.py            # still water only (fast)
    python scripts/run_comparison.py --bem      # + BEM per scenario (default grid; several minutes each)
"""
import csv
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from exo01.analysis import build_response, evaluate, strip_private, hydro_for  # noqa: E402
from exo01.config import load_scenario, resolve_scenario  # noqa: E402
from exo01.scenarios import compare_table  # noqa: E402

OUT = ROOT / "results" / "comparison"
OUT.mkdir(parents=True, exist_ok=True)
SCEN = ["baseline_illustrative", "floats_glb_capsules", "battery_relocated", "battery_float_frame", "occupants_symmetric", "occupants_asymmetric", "with_hydronaute"]
WAVE = dict(H_m=0.3, T_s=2.5, heading_deg=90)          # illustrative beam-sea case
DAMP = {"zeta": {"heave": 0.05, "roll": 0.05, "pitch": 0.05}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}}
LABEL = "Exploratory — assumed geometry and mass distribution."


def main(do_bem):
    results, waves, raos, nats = [], {}, {}, {}
    from exo01.analysis import HYDRO_DEFAULTS
    s_ = HYDRO_DEFAULTS
    om = np.round(np.arange(s_["omega_min"], s_["omega_max"] + 1e-9, s_["omega_step"]), 10)      # the interface's grid: shares its cache
    hd_ = np.array([np.radians(WAVE['heading_deg'])])          # exact heading
    for name in SCEN:
        cfg = resolve_scenario(load_scenario(name))
        t = time.time()
        r = evaluate(cfg)
        results.append(r)
        print(f"{name}: still water {r['status'].get('equilibrium')} ({time.time()-t:.1f}s)")
        if do_bem and r["status"].get("equilibrium") == "solved":
            t = time.time()
            hd = hydro_for(r, cfg, om, hd_)
            m = build_response(r, hd, cfg)
            beta = np.radians(WAVE["heading_deg"])
            waves[name] = m.regular_wave(WAVE["H_m"], WAVE["T_s"], beta, DAMP, cfg["deck_acceleration_points"])
            omf = np.linspace(om[0], om[-1], 200)
            raos[name] = (omf, m.rao_curve(omf, beta, DAMP))
            nats[name] = m.natural_frequencies()
            print(f"   BEM {hd.meta['cache']} ({time.time()-t:.0f}s), roll amp {waves[name]['amplitude_deg']['roll']:.2f} deg")
    rows = compare_table(results, waves)
    with (OUT / "comparison.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        for row in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (list, dict)) else v) for k, v in row.items()})
    cols = [("name", "scenario"), ("total_listed_mass_kg", "mass kg"), ("com_x_m", "COM x"), ("com_y_m", "COM y"), ("com_z_m", "COM z"),
            ("heel_deg", "heel °"), ("trim_deg", "trim °"), ("draft_max_m", "draft m"), ("lower_deck_freeboard_min_m", "deck fb m"),
            ("GM_transverse_m", "GM_T m"), ("GM_longitudinal_m", "GM_L m"), ("heave_amp_m", "heave amp m"), ("roll_amp_deg", "roll amp °"),
            ("pitch_amp_deg", "pitch amp °"), ("deck_accel_vertical_max_amp_ms2", "deck a_z m/s²")]
    f = lambda v: "not computed" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))
    md = [f"# Scenario comparison — {LABEL}", "", f"Regular wave for the wave columns: H={WAVE['H_m']} m, T={WAVE['T_s']} s, β={WAVE['heading_deg']}°, ζ=0.05 (heave/roll/pitch).", "",
          "| " + " | ".join(c[1] for c in cols) + " |", "|" + "---|" * len(cols)]
    for row in rows:
        md.append("| " + " | ".join(f(row[c[0]]) for c in cols) + " |")
    md += ["", "All rows share the same float proxies and assumed COMs (EXO-only). Compare rows with each other; do not read them as absolute predictions."]
    (OUT / "comparison.md").write_text("\n".join(md))
    # plots
    fig, axs = plt.subplots(2, 4, figsize=(16, 7))
    keys = [("heel_deg", "heel [°]"), ("trim_deg", "trim [°]"), ("draft_max_m", "max draft [m]"), ("lower_deck_freeboard_min_m", "min deck freeboard [m]"),
            ("com_z_m", "COM z [m]"), ("GM_transverse_m", "GM_T [m]"), ("roll_amp_deg", f"roll amp [°] (H={WAVE['H_m']}, T={WAVE['T_s']})"), ("deck_accel_vertical_max_amp_ms2", "deck a_z amp [m/s²]")]
    names = [r["name"].replace("_", "\n") for r in rows]
    for ax, (k, lab) in zip(axs.ravel(), keys):
        vals = [np.nan if r[k] is None else r[k] for r in rows]
        ax.bar(names, vals, color=["#4fc3f7", "#ffb74d", "#81c784", "#ef5350", "#ce93d8"][:len(names)])
        ax.set_title(lab, fontsize=10)
        ax.tick_params(axis="x", labelsize=7)
        if all(np.isnan(vals)):
            ax.text(0.5, 0.5, "not computed\n(run with --bem)", ha="center", va="center", transform=ax.transAxes, color="#b26a00")
    fig.suptitle(LABEL, color="#b26a00")
    fig.tight_layout()
    fig.savefig(OUT / "comparison_bars.png", dpi=130)
    if raos:
        fig, axs = plt.subplots(1, 3, figsize=(15, 4))
        for name, (omf, X) in raos.items():
            T = 2 * np.pi / omf
            axs[0].plot(T, np.abs(X[:, 2]), label=name + (" (EXO)" if X.shape[1] > 6 else ""))
            axs[1].plot(T, np.degrees(np.abs(X[:, 3])), label=name + (" (EXO)" if X.shape[1] > 6 else ""))
            axs[2].plot(T, np.degrees(np.abs(X[:, 4])), label=name + (" (EXO)" if X.shape[1] > 6 else ""))
            if X.shape[1] > 6:
                axs[0].plot(T, np.abs(X[:, 8]), "--", label=name + " (boat)")
                axs[1].plot(T, np.degrees(np.abs(X[:, 9])), "--", label=name + " (boat)")
                axs[2].plot(T, np.degrees(np.abs(X[:, 10])), "--", label=name + " (boat)")
        for ax, t in zip(axs, ["heave RAO [m/m]", "roll RAO [°/m]", "pitch RAO [°/m]"]):
            ax.set_title(t + f" — β={WAVE['heading_deg']}°, ζ=0.05")
            ax.set_xlabel("wave period T [s]")
            ax.set_xlim(1, 8)
            ax.grid(alpha=0.3)
        bands = next(iter(nats.values()))["gap_resonance_bands_rad_s"]
        for ax in axs:
            for lo, hi in bands:
                ax.axvspan(2 * np.pi / hi, 2 * np.pi / lo, color="orange", alpha=0.15)
        axs[0].legend(fontsize=7)
        fig.suptitle(LABEL + "  (orange: potential-flow gap-resonance bands)", color="#b26a00")
        fig.tight_layout()
        fig.savefig(OUT / "rao_comparison.png", dpi=130)
    json.dump(dict(label=LABEL, wave=WAVE, damping=DAMP, rows=rows, natural_frequencies=nats,
                   still_water={r["name"] + "/" + str(r.get("scenario")): strip_private(r) for r in results}),
              (OUT / "comparison.json").open("w"), indent=1, default=str)
    print("\n".join(md))


if __name__ == "__main__":
    main("--bem" in sys.argv)
