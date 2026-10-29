"""Mooring study: arrangement x line stiffness x pretension, static (moored / push / tow) and in waves (linear + tension-only
time domain), with stern fenders (compression-only) and a rigid-strut limit case -> results/mooring/.

    python scripts/run_mooring_study.py [--quick]

Questions it answers (ASSUMPTIONS 5e): which arrangement closes the push and tow force loops; what pretension keeps the
lines from going slack in the reference waves; how the peak (snatch) loads scale with line stiffness (soft snubber vs
stiff rope); what a rigid coupling would have to carry; whether stern fenders change the picture; how much the transom
gap breathes (fender travel).
"""
import copy
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

from exo01.analysis import evaluate, hydro_for, build_response, HYDRO_DEFAULTS  # noqa: E402
from exo01.config import load_config, resolve  # noqa: E402
from exo01.optimise import _pair, EXO_POINTS, BOAT_CLEATS  # noqa: E402
from exo01.response import line_snatch_check  # noqa: E402

OUT = ROOT / "results" / "mooring"
OUT.mkdir(parents=True, exist_ok=True)
QUICK = "--quick" in sys.argv
LABEL = "Exploratory — assumed geometry and mass distribution; line/fender properties are assumptions."

ill = load_config("illustrative")
PRESETS = {p["id"]: p for p in ill["host_boat"]["line_presets"]}
ARR = {
    "best_diagonals": dict(title="aft posts -> midship cleats + fwd posts -> stern cleats (line-sweep best)",
                           lines=_pair("AFT2MID", EXO_POINTS["aft_post"], BOAT_CLEATS["midship"]) + _pair("FWD2STERN", EXO_POINTS["fwd_post"], BOAT_CLEATS["stern"])),
    "simulator_default": dict(title=PRESETS["simulator_default"]["title"], lines=PRESETS["simulator_default"]["lines"]),
    "figure_all_forward": dict(title=PRESETS["figure_all_forward"]["title"], lines=PRESETS["figure_all_forward"]["lines"]),
    "six_lines": dict(title=PRESETS["six_lines"]["title"], lines=PRESETS["six_lines"]["lines"]),
    "fenders_crossed_lines": dict(title=PRESETS["fenders_crossed_lines"]["title"], lines=PRESETS["fenders_crossed_lines"]["lines"]),
    "fenders_diagonals": dict(title=PRESETS["fenders_diagonals"]["title"], lines=PRESETS["fenders_diagonals"]["lines"]),
    "rigid_struts": dict(title=PRESETS["rigid_struts"]["title"], lines=PRESETS["rigid_struts"]["lines"]),
}
K_LINES = [2000.0, 10000.0, 50000.0, 200000.0]          # N/m: elastic snubber / default / short polyester / Dyneema-like
T0S = [50.0, 100.0, 200.0, 400.0, 800.0]                 # N
if QUICK:
    K_LINES, T0S = [2000.0, 50000.0], [100.0, 400.0]
WAVES = [dict(id="beam_03_25", H_m=0.3, T_s=2.5, heading_deg=90), dict(id="head_03_25", H_m=0.3, T_s=2.5, heading_deg=180),
         dict(id="beam_05_30", H_m=0.5, T_s=3.0, heading_deg=90)]
DAMP = {"EXO": {"zeta": {"heave": 0.05, "roll": 0.05, "pitch": 0.05}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}},
        "BOAT": {"zeta": {"heave": 0.05, "roll": 0.10, "pitch": 0.10}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}}}
SET = dict(HYDRO_DEFAULTS)
OM = np.round(np.arange(SET["omega_min"], SET["omega_max"] + 1e-9, SET["omega_step"]), 10)


def with_props(lines, k, t0):
    out = copy.deepcopy(lines)
    for l in out:
        if l.get("kind", "line") == "line":
            l["stiffness_N_per_m"] = k; l["pretension_N"] = t0
    return out


def static_case(lines, thr, unit):
    r = evaluate(resolve(ill, {"host_boat": {"lines": lines}, "propulsion": {"thrust_fraction": thr, "unit": unit}}))
    ce = r.get("coupled_equilibrium") or {}
    els = r.get("lines", [])
    tens = [l["tension_N"] for l in els if l.get("kind", "line") != "fender"]
    comp = [-l["tension_N"] for l in els if l.get("kind", "line") == "fender"]
    return dict(converged=bool(ce.get("converged")), physical=bool(ce.get("physical", ce.get("converged"))),
                dx_mm=1000 * ce.get("boat_shift_from_nominal", {}).get("dx_m", np.nan), dy_mm=1000 * ce.get("boat_shift_from_nominal", {}).get("dy_m", np.nan),
                yaw_deg=ce.get("boat_shift_from_nominal", {}).get("dyaw_deg", np.nan),
                line_max_N=max(tens) if tens else None, line_min_N=min(tens) if tens else None,
                slack=[l["id"] for l in els if l.get("slack")], fender_max_N=max(comp) if comp else None,
                transom_gap_m=(r.get("clearances") or {}).get("transom_to_rear_deck_plate_m"),
                speed_m_s=(r.get("propulsion") or {}).get("speed_m_s")), r


def wave_case(r, cfg, wave):
    hd = np.array([np.radians(wave["heading_deg"])])
    hdd = hydro_for(r, cfg, OM, hd, SET, cache_only=True, allow_pose_reuse=True)
    model = build_response(r, hdd, cfg)
    rw = model.regular_wave(wave["H_m"], wave["T_s"], hd[0], DAMP, cfg["deck_acceleration_points"])
    out = dict(pose_reuse=hdd.meta.get("pose_reuse"), exo_roll_deg=rw["bodies"]["EXO"]["amplitude_deg"]["roll"], exo_pitch_deg=rw["bodies"]["EXO"]["amplitude_deg"]["pitch"],
               boat_roll_deg=rw["bodies"]["BOAT"]["amplitude_deg"]["roll"], boat_pitch_deg=rw["bodies"]["BOAT"]["amplitude_deg"]["pitch"])
    lines = rw.get("lines") or []
    out["lin_line_max_N"] = max((l["max_N"] for l in lines if l.get("kind", "line") == "line"), default=None)
    out["lin_slack"] = [l["id"] for l in lines if l.get("kind", "line") == "line" and l["slack_in_cycle"]]
    out["lin_fender_loses_contact"] = [l["id"] for l in lines if l.get("kind") == "fender" and l["slack_in_cycle"]]
    out["lin_strut_amp_N"] = max((l["tension_amp_N"] for l in lines if l.get("kind") == "strut"), default=None)
    rel = rw.get("relative_motion") or {}
    tg = [v for k_, v in rel.items() if k_.startswith("transom_vs_deck_edge")]
    out["transom_gap_motion_amp_m"] = max((v["relative_motion_amp_m"] for v in tg), default=None)
    out["transom_gap_min_m"] = min((v["min_clearance_m"] for v in tg if v["min_clearance_m"] is not None), default=None)
    out["min_rel_clearance_m"] = (rw.get("min_relative_clearance") or {}).get("min_clearance_m")
    out["min_rel_clearance_at"] = (rw.get("min_relative_clearance") or {}).get("name")
    try:
        sn = line_snatch_check(model, 2 * np.pi / wave["T_s"], hd[0], wave["H_m"], DAMP, n_periods=10, steps_per_period=64)
        ln = [l for l in sn["lines"] if l["kind"] == "line"]
        fd = [l for l in sn["lines"] if l["kind"] == "fender"]
        st = [l for l in sn["lines"] if l["kind"] == "strut"]
        out.update(td_line_peak_N=max((l["peak_N"] for l in ln), default=None), td_slack_fraction_max=max((l["slack_fraction_of_cycle"] for l in ln), default=None),
                   td_snatch_ratio_max=max(((l["snatch_ratio"] or 0.0) for l in ln), default=None),
                   td_fender_peak_N=max((-l["peak_N"] for l in fd), default=None), td_fender_free_fraction_max=max((l["slack_fraction_of_cycle"] for l in fd), default=None),
                   td_strut_peak_abs_N=max((max(abs(l["min_N"]), abs(l["max_N"])) for l in st), default=None),
                   td_motion_ratio=sn["max_amplitude_ratio"])
    except Exception as e:  # noqa: BLE001
        out["td_error"] = f"{type(e).__name__}: {e}"
    return out


rows = []
t0 = time.time()
n_total = sum(1 if a == "rigid_struts" else len(K_LINES) * len(T0S) for a in ARR)
i = 0
for aid, a in ARR.items():
    grid = [(1.0e6, 0.0)] if aid == "rigid_struts" else [(k, t) for k in K_LINES for t in T0S]
    for k, t in grid:
        i += 1
        lines = with_props(a["lines"], k, t)
        row = dict(arrangement=aid, title=a["title"], k_line_N_per_m=k, pretension_N=t)
        moored, r0 = static_case(lines, 0.0, "EXO_PODS")
        row["moored"] = moored
        row["push"], _ = static_case(lines, 1.0, "EXO_PODS")
        row["tow"], _ = static_case(lines, 1.0, "BOAT_ENGINE")
        cfg0 = resolve(ill, {"host_boat": {"lines": lines}, "propulsion": {"thrust_fraction": 0.0}})
        row["waves"] = {}
        if moored["converged"]:
            for w in WAVES:
                try:
                    row["waves"][w["id"]] = wave_case(r0, cfg0, w)
                except Exception as e:  # noqa: BLE001
                    row["waves"][w["id"]] = dict(error=f"{type(e).__name__}: {e}")
        rows.append(row)
        print(f"[{i}/{n_total}] {aid} k={k:.0f} T0={t:.0f}: moored max {moored['line_max_N']} N, push {'ok' if row['push']['physical'] else 'NO'} "
              f"(max {row['push']['line_max_N']}), tow {'ok' if row['tow']['physical'] else 'NO'}, "
              f"beam td peak {row['waves'].get('beam_03_25', {}).get('td_line_peak_N')} N, slack {row['waves'].get('beam_03_25', {}).get('td_slack_fraction_max')} "
              f"({time.time() - t0:.0f} s)", flush=True)

(OUT / "mooring_study.json").write_text(json.dumps(dict(label=LABEL, waves=WAVES, damping=DAMP, k_lines=K_LINES, pretensions=T0S, rows=rows, seconds=time.time() - t0), indent=1, default=str))


# ------------------------------------------------------------------ tables, decisions and plots
def f(v, d=0):
    if v is None or (isinstance(v, float) and np.isnan(v)):
        return "—"
    return f"{v:.{d}f}" if isinstance(v, (int, float)) else str(v)


cols = ["arrangement", "k_line_N_per_m", "pretension_N", "moored_line_max_N", "moored_slack", "moored_gap_m", "push_ok", "push_dx_mm", "push_line_max_N", "push_fender_max_N",
        "tow_ok", "tow_dx_mm", "tow_line_max_N"]
for w in WAVES:
    cols += [f"{w['id']}_td_peak_N", f"{w['id']}_slack_frac", f"{w['id']}_fender_peak_N", f"{w['id']}_strut_peak_N", f"{w['id']}_gap_min_m", f"{w['id']}_boat_roll_deg"]
with (OUT / "mooring_study.csv").open("w", newline="") as fh:
    wr = csv.writer(fh); wr.writerow(cols)
    for r in rows:
        line = [r["arrangement"], r["k_line_N_per_m"], r["pretension_N"], f(r["moored"]["line_max_N"]), ",".join(r["moored"]["slack"]) or "none", f(r["moored"]["transom_gap_m"], 3),
                r["push"]["physical"], f(r["push"]["dx_mm"]), f(r["push"]["line_max_N"]), f(r["push"]["fender_max_N"]), r["tow"]["physical"], f(r["tow"]["dx_mm"]), f(r["tow"]["line_max_N"])]
        for w in WAVES:
            wv = r["waves"].get(w["id"], {})
            line += [f(wv.get("td_line_peak_N")), f(wv.get("td_slack_fraction_max"), 2), f(wv.get("td_fender_peak_N")), f(wv.get("td_strut_peak_abs_N")), f(wv.get("transom_gap_min_m"), 3), f(wv.get("boat_roll_deg"), 2)]
        wr.writerow(line)

# decisions
dec = {}
for aid in ARR:
    rs = [r for r in rows if r["arrangement"] == aid]
    d = dict(title=ARR[aid]["title"], push_ok_all=all(r["push"]["physical"] for r in rs), tow_ok_all=all(r["tow"]["physical"] for r in rs),
             push_ok_any=any(r["push"]["physical"] for r in rs), tow_ok_any=any(r["tow"]["physical"] for r in rs))
    # minimum pretension with no slack in the beam 0.3 m wave (time domain), per stiffness
    mins = {}
    for k in sorted({r["k_line_N_per_m"] for r in rs}):
        ok = [r["pretension_N"] for r in rs if r["k_line_N_per_m"] == k and (r["waves"].get("beam_03_25", {}).get("td_slack_fraction_max") or 1.0) < 0.02 and not r["moored"]["slack"]]
        mins[f"{k:.0f}"] = min(ok) if ok else None
    d["min_pretension_no_slack_beam03_by_k"] = mins
    # peak loads at that pretension, per stiffness
    peaks = {}
    for k in sorted({r["k_line_N_per_m"] for r in rs}):
        t = mins[f"{k:.0f}"]
        rr = [r for r in rs if r["k_line_N_per_m"] == k and r["pretension_N"] == t]
        if rr:
            peaks[f"{k:.0f}"] = dict(pretension_N=t, **{w["id"]: rr[0]["waves"].get(w["id"], {}).get("td_line_peak_N") for w in WAVES},
                                      push_line_max_N=rr[0]["push"]["line_max_N"], tow_line_max_N=rr[0]["tow"]["line_max_N"], push_fender_max_N=rr[0]["push"]["fender_max_N"])
    d["loads_at_min_pretension_by_k"] = peaks
    d["transom_gap_min_m_worst"] = min((v.get("transom_gap_min_m") for r in rs for v in r["waves"].values() if v.get("transom_gap_min_m") is not None), default=None)
    d["transom_gap_motion_amp_m_worst"] = max((v.get("transom_gap_motion_amp_m") for r in rs for v in r["waves"].values() if v.get("transom_gap_motion_amp_m") is not None), default=None)
    if aid == "rigid_struts":
        d["strut_peak_abs_N_by_wave"] = {w["id"]: rs[0]["waves"].get(w["id"], {}).get("td_strut_peak_abs_N") for w in WAVES}
        d["strut_static_push_N"] = rs[0]["push"]["line_max_N"]; d["strut_static_tow_N"] = rs[0]["tow"]["line_max_N"]
    dec[aid] = d
(OUT / "decisions.json").write_text(json.dumps(dec, indent=1, default=str))

md = [f"# Mooring study — {LABEL}", "", f"{len(rows)} configurations in {time.time() - t0:.0f} s. Waves: " + "; ".join(f"{w['id']} (H {w['H_m']} m, T {w['T_s']} s, {w['heading_deg']}°)" for w in WAVES)
      + ". Line stiffness k and pretension T0 apply to the tension-only lines; fenders k = 50 kN/m, preload 0 (just touching at the nominal berth); struts k = 1 MN/m bilateral.", "",
      "## Arrangements: can they close the force loop?", "", "| arrangement | push (pods 100 %) | tow (boat engine 100 %) | worst transom gap in waves [m] | gap breathing amp [m] |", "|---|---|---|---|---|"]
for aid, d in dec.items():
    md.append(f"| {aid} | {'yes' if d['push_ok_all'] else ('some' if d['push_ok_any'] else 'NO')} | {'yes' if d['tow_ok_all'] else ('some' if d['tow_ok_any'] else 'NO')} | {f(d['transom_gap_min_m_worst'], 3)} | {f(d['transom_gap_motion_amp_m_worst'], 3)} |")
md += ["", "## Minimum pretension with no slack line in beam waves H 0.3 m T 2.5 s (time-domain), and the loads there", "",
       "| arrangement | k [N/m] | min T0 [N] | peak beam 0.3 [N] | peak head 0.3 [N] | peak beam 0.5 [N] | push line max [N] | push fender max [N] | tow line max [N] |", "|---|---|---|---|---|---|---|---|---|"]
for aid, d in dec.items():
    for k, p in d["loads_at_min_pretension_by_k"].items():
        md.append(f"| {aid} | {k} | {f(p['pretension_N'])} | {f(p.get('beam_03_25'))} | {f(p.get('head_03_25'))} | {f(p.get('beam_05_30'))} | {f(p['push_line_max_N'])} | {f(p['push_fender_max_N'])} | {f(p['tow_line_max_N'])} |")
    if aid == "rigid_struts":
        md.append(f"| rigid_struts | 1e6 (bilateral) | — | strut peak {f(d['strut_peak_abs_N_by_wave'].get('beam_03_25'))} | {f(d['strut_peak_abs_N_by_wave'].get('head_03_25'))} | {f(d['strut_peak_abs_N_by_wave'].get('beam_05_30'))} | {f(d['strut_static_push_N'])} | — | {f(d['strut_static_tow_N'])} |")
md += ["", "## Full grid", "", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
with (OUT / "mooring_study.csv").open() as fh:
    for j, line in enumerate(csv.reader(fh)):
        if j:
            md.append("| " + " | ".join(line) + " |")
(OUT / "mooring_study.md").write_text("\n".join(md))

# plots
import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
arrs = [a for a in ARR if a != "rigid_struts"]
fig, axs = plt.subplots(2, len(arrs), figsize=(3.2 * len(arrs), 6.4), sharex=True)
for c, aid in enumerate(arrs):
    rs = [r for r in rows if r["arrangement"] == aid]
    for k in K_LINES:
        rk = sorted([r for r in rs if r["k_line_N_per_m"] == k], key=lambda r: r["pretension_N"])
        xs = [r["pretension_N"] for r in rk]
        axs[0, c].plot(xs, [r["waves"].get("beam_03_25", {}).get("td_line_peak_N") or np.nan for r in rk], "o-", label=f"k {k/1000:.0f} kN/m")
        axs[1, c].plot(xs, [100 * (r["waves"].get("beam_03_25", {}).get("td_slack_fraction_max") if r["waves"].get("beam_03_25", {}).get("td_slack_fraction_max") is not None else np.nan) for r in rk], "o-")
    axs[0, c].set_title(aid, fontsize=9); axs[0, c].grid(alpha=.3); axs[1, c].grid(alpha=.3); axs[1, c].set_xlabel("pretension T0 [N]"); axs[1, c].set_xscale("log")
axs[0, 0].set_ylabel("peak line load, beam 0.3 m [N] (time domain)"); axs[1, 0].set_ylabel("worst line: % of cycle slack"); axs[0, 0].legend(fontsize=7)
fig.suptitle(LABEL, color="#b5651d", fontsize=9); fig.tight_layout(); fig.savefig(OUT / "mooring_peaks_vs_pretension.png", dpi=130); plt.close(fig)
print(f"done in {time.time() - t0:.0f} s -> {OUT}")
