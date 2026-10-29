"""Mooring — final comparison of the candidate arrangements at the settings the study converged on
(line k 10 kN/m or 2 kN/m snubber, T0 400 N, eyes at cleat height z 0.3), plus the hybrid "two tubes aft + two ropes
forward" with an elastomer cartridge in series on the tubes -> results/mooring/final_comparison.{json,md}

    python scripts/run_mooring_final.py

Same static cases (moored / push / tow) and waves (linear + tension-only time domain) as run_mooring_study.py.
Shock absorbers enter the model as stiffness only — no damping element exists in the model (ASSUMPTIONS 5e).
"""
import copy
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
from exo01.response import line_snatch_check  # noqa: E402

OUT = ROOT / "results" / "mooring"
LABEL = "Exploratory — assumed geometry and mass distribution; line/fender/tube properties are assumptions; no damping in elements."
ill = load_config("illustrative")
PRESETS = {p["id"]: p for p in ill["host_boat"]["line_presets"]}
WAVES = [dict(id="beam_03_25", H_m=0.3, T_s=2.5, heading_deg=90), dict(id="head_03_25", H_m=0.3, T_s=2.5, heading_deg=180),
         dict(id="beam_05_30", H_m=0.5, T_s=3.0, heading_deg=90)]
DAMP = {"EXO": {"zeta": {"heave": 0.05, "roll": 0.05, "pitch": 0.05}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}},
        "BOAT": {"zeta": {"heave": 0.05, "roll": 0.10, "pitch": 0.10}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}}}
SET = dict(HYDRO_DEFAULTS)
OM = np.round(np.arange(SET["omega_min"], SET["omega_max"] + 1e-9, SET["omega_step"]), 10)

ZE = 0.3   # EXO eye height at cleat level (decided 29/10: near-horizontal lines)


def sym(id_, exo, boat, **kw):
    return [dict(id=f"{id_}_PORT", exo_point_m=[exo[0], exo[1], exo[2]], boat_point_m=[boat[0], boat[1], boat[2]], **kw),
            dict(id=f"{id_}_STBD", exo_point_m=[exo[0], -exo[1], exo[2]], boat_point_m=[boat[0], -boat[1], boat[2]], **kw)]


def rope(id_, exo, boat, k=10000.0, t0=400.0):
    return sym(id_, exo, boat, kind="line", stiffness_N_per_m=k, pretension_N=t0)


def fender(id_, k=50000.0):
    return sym(id_, (2.1, 0.9, 0.25), (0.0, 0.9, 0.40), kind="fender", stiffness_N_per_m=k, pretension_N=0.0)


def tube(id_, k):
    """Pinned tube between the EXO rear-deck edge at the quarters and the transom quarters; k = elastomer cartridge in series
    (1e6 = no cartridge, rigid)."""
    return sym(id_, (2.1, 0.9, 0.25), (0.25, 0.9, 0.40), kind="strut", stiffness_N_per_m=k, pretension_N=0.0)


def crossed(k=10000.0, t0=400.0):
    return [dict(id="CROSS_P2S", exo_point_m=[2.1, 2.25, ZE], boat_point_m=[0.3, -1.3, 0.8], kind="line", stiffness_N_per_m=k, pretension_N=t0),
            dict(id="CROSS_S2P", exo_point_m=[2.1, -2.25, ZE], boat_point_m=[0.3, 1.3, 0.8], kind="line", stiffness_N_per_m=k, pretension_N=t0)]


AFT2MID = lambda k=10000.0, t0=400.0, z=ZE: rope("AFT2MID", (0.05, 2.25, z), (4.30, 1.35, 0.80), k, t0)      # noqa: E731
FWD2STERN = lambda k=10000.0, t0=400.0, z=ZE: rope("FWD2STERN", (4.95, 2.25, z), (0.30, 1.30, 0.80), k, t0)  # noqa: E731
TOW = lambda k=10000.0, t0=400.0, z=ZE: rope("TOW", (4.95, 2.25, z), (4.30, 1.35, 0.80), k, t0)              # noqa: E731

CANDS = {}
CANDS["A_fenders_diagonals_deck"] = dict(title="Study best: 2 stern fenders + diagonals, eyes at deck level (reference)",
                                         lines=fender("FENDER") + AFT2MID(z=0.0) + FWD2STERN(z=0.0))
CANDS["A2_fenders_diagonals_cleat"] = dict(title="Same, eyes raised to cleat level (+0.3 m)", lines=fender("FENDER") + AFT2MID() + FWD2STERN())
CANDS["B_six_lines_knees"] = dict(title="Elven's six-line sketch + stern knees/fenders, eyes at cleat level",
                                  lines=fender("FENDER") + rope("L12_AF", (2.1, 2.25, ZE), (4.30, 1.35, 0.80)) + rope("L34_MI", (4.95, 2.25, ZE), (0.30, 1.30, 0.80)) + crossed())
CANDS["C_four_tubes_rigid"] = dict(title="Four rigid tubes (study limit case, k 1 MN/m)", lines=PRESETS["rigid_struts"]["lines"])
CANDS["D_four_tubes_cartridge"] = dict(title="Four tubes with elastomer cartridges (k 100 kN/m)",
                                       lines=[dict(l, stiffness_N_per_m=1.0e5) for l in PRESETS["rigid_struts"]["lines"]])
for kt, kn in [(1.0e6, "rigid"), (2.0e5, "200k"), (1.0e5, "100k"), (5.0e4, "50k")]:
    CANDS[f"E_hybrid_tubes_{kn}_ropes10k"] = dict(title=f"Hybrid: 2 tubes aft ({kn}) + 2 ropes fwd posts->midship (k 10k, T0 400)", lines=tube("TUBE", kt) + TOW())
CANDS["E_hybrid_tubes_100k_snubber2k"] = dict(title="Hybrid: 2 tubes aft (100k) + 2 ropes with snubber (k 2k, T0 400)", lines=tube("TUBE", 1.0e5) + TOW(k=2000.0))
CANDS["F_hybrid_tubes_100k_crossed"] = dict(title="Hybrid: 2 tubes aft (100k) + crossed stern ropes + tow ropes (k 10k, T0 400)",
                                            lines=tube("TUBE", 1.0e5) + crossed() + TOW())
CANDS["G_hybrid_tubes_100k_diagonals"] = dict(title="Hybrid: 2 tubes aft (100k) + diagonals (aft->mid, fwd->stern), k 10k T0 400",
                                              lines=tube("TUBE", 1.0e5) + AFT2MID() + FWD2STERN())


def static_case(lines, thr, unit):
    r = evaluate(resolve(ill, {"host_boat": {"lines": lines}, "propulsion": {"thrust_fraction": thr, "unit": unit}}))
    ce = r.get("coupled_equilibrium") or {}
    els = r.get("lines", [])
    kind = lambda l: l.get("kind", "line")  # noqa: E731
    tens = [l["tension_N"] for l in els if kind(l) == "line"]
    comp = [-l["tension_N"] for l in els if kind(l) == "fender"]
    st = [abs(l["tension_N"]) for l in els if kind(l) == "strut"]
    return dict(converged=bool(ce.get("converged")), physical=bool(ce.get("physical", ce.get("converged"))),
                dx_mm=1000 * ce.get("boat_shift_from_nominal", {}).get("dx_m", np.nan), yaw_deg=ce.get("boat_shift_from_nominal", {}).get("dyaw_deg", np.nan),
                line_max_N=max(tens) if tens else None, slack=[l["id"] for l in els if l.get("slack")],
                fender_max_N=max(comp) if comp else None, strut_max_N=max(st) if st else None,
                transom_gap_m=(r.get("clearances") or {}).get("transom_to_rear_deck_plate_m")), r


def wave_case(r, cfg, wave):
    hd = np.array([np.radians(wave["heading_deg"])])
    hdd = hydro_for(r, cfg, OM, hd, SET, cache_only=True, allow_pose_reuse=True)
    model = build_response(r, hdd, cfg)
    rw = model.regular_wave(wave["H_m"], wave["T_s"], hd[0], DAMP, cfg["deck_acceleration_points"])
    out = dict(exo_roll_deg=rw["bodies"]["EXO"]["amplitude_deg"]["roll"], boat_roll_deg=rw["bodies"]["BOAT"]["amplitude_deg"]["roll"],
               boat_pitch_deg=rw["bodies"]["BOAT"]["amplitude_deg"]["pitch"])
    rel = rw.get("relative_motion") or {}
    tg = [v for k_, v in rel.items() if k_.startswith("transom_vs_deck_edge")]
    out["transom_gap_min_m"] = min((v["min_clearance_m"] for v in tg if v["min_clearance_m"] is not None), default=None)
    sn = line_snatch_check(model, 2 * np.pi / wave["T_s"], hd[0], wave["H_m"], DAMP, n_periods=10, steps_per_period=64)
    ln = [l for l in sn["lines"] if l["kind"] == "line"]; fd = [l for l in sn["lines"] if l["kind"] == "fender"]; st = [l for l in sn["lines"] if l["kind"] == "strut"]
    out.update(line_peak_N=max((l["peak_N"] for l in ln), default=None), slack_frac=max((l["slack_fraction_of_cycle"] for l in ln), default=None),
               fender_peak_N=max((-l["peak_N"] for l in fd), default=None), fender_free_frac=max((l["slack_fraction_of_cycle"] for l in fd), default=None),
               strut_peak_N=max((max(abs(l["min_N"]), abs(l["max_N"])) for l in st), default=None))
    return out


rows = []
t0 = time.time()
for i, (cid, c) in enumerate(CANDS.items(), 1):
    row = dict(id=cid, title=c["title"], n_elements=len(c["lines"]))
    moored, r0 = static_case(c["lines"], 0.0, "EXO_PODS"); row["moored"] = moored
    row["push"], _ = static_case(c["lines"], 1.0, "EXO_PODS")
    row["tow"], _ = static_case(c["lines"], 1.0, "BOAT_ENGINE")
    cfg0 = resolve(ill, {"host_boat": {"lines": c["lines"]}, "propulsion": {"thrust_fraction": 0.0}})
    row["waves"] = {}
    for w in WAVES:
        try:
            row["waves"][w["id"]] = wave_case(r0, cfg0, w)
        except Exception as e:  # noqa: BLE001
            row["waves"][w["id"]] = dict(error=f"{type(e).__name__}: {e}")
    rows.append(row)
    b = row["waves"].get("beam_03_25", {})
    print(f"[{i}/{len(CANDS)}] {cid}: push {'ok' if row['push']['physical'] else 'NO'} dx {row['push']['dx_mm']:.0f} mm, tow {'ok' if row['tow']['physical'] else 'NO'} "
          f"dx {row['tow']['dx_mm']:.0f}; beam0.3: line pk {b.get('line_peak_N')} slack {b.get('slack_frac')} fender {b.get('fender_peak_N')} strut {b.get('strut_peak_N')} "
          f"gap {b.get('transom_gap_min_m')} roll {b.get('boat_roll_deg')} ({time.time() - t0:.0f} s)", flush=True)


# ---------------------------------------------------------------- scoring (explicit, editable)
def score(row):
    """Lower is better. Hard gates: push and tow must close. Then: worst element load across the 3 waves (any kind), slack fraction,
    transom contact, boat roll. Weights are a choice — stated in the md."""
    if not (row["push"]["physical"] and row["tow"]["physical"]):
        return None
    ws = [w for w in row["waves"].values() if "error" not in w]
    peak = max(max(filter(None, [w.get("line_peak_N"), w.get("fender_peak_N"), w.get("strut_peak_N")]), default=0) for w in ws)
    slack = max((w.get("slack_frac") or 0.0) for w in ws)
    gap = min((w["transom_gap_min_m"] if w.get("transom_gap_min_m") is not None else 0.0) for w in ws)
    roll = max(w["boat_roll_deg"] for w in ws)
    dx = max(abs(row["push"]["dx_mm"]), abs(row["tow"]["dx_mm"]))
    s = peak / 1000.0 + 2.0 * slack + (5.0 * -gap if gap < 0 else 0.0) + roll / 10.0 + dx / 100.0
    return dict(score=round(s, 3), peak_N=round(peak), slack=round(slack, 2), gap_min_m=round(gap, 3), boat_roll_deg=round(roll, 1), dx_mm=round(dx))


for row in rows:
    row["score"] = score(row)
ranked = sorted([r for r in rows if r["score"]], key=lambda r: r["score"]["score"])
(OUT / "final_comparison.json").write_text(json.dumps(dict(label=LABEL, waves=WAVES, damping=DAMP, rows=rows, ranking=[r["id"] for r in ranked],
                                                        seconds=time.time() - t0), indent=1, default=str))


def f(v, d=0):
    return "—" if v is None else (f"{v:.{d}f}" if isinstance(v, (int, float)) else str(v))


md = [f"# Mooring — final comparison of the candidate arrangements\n\n> {LABEL}\n",
      "All ropes k 10 kN/m, T0 400 N, EXO eyes at z 0.3 (cleat level) unless stated; fenders k 50 kN/m; tubes pinned at (2.1, ±0.9) → transom quarters, "
      "k = elastomer cartridge in series (1 MN/m = rigid). Waves: beam 0.3 m / 2.5 s, head 0.3 / 2.5, beam 0.5 / 3.0 (Erdre test case). Damping: radiation + assumed 5 % (boat roll/pitch 10 %).\n",
      "Score (lower is better, a choice): worst element peak [kN] + 2 × slack fraction + 5 × transom overlap [m] + boat roll [°]/10 + |dx| [mm]/100; hard gate: push and tow must close.\n",
      "| rank | id | elements | push dx [mm] | tow dx [mm] | worst peak [N] | slack frac | gap min [m] | boat roll [°] | score |", "|---|---|---|---|---|---|---|---|---|---|"]
for n, r in enumerate(ranked, 1):
    s = r["score"]
    md.append(f"| {n} | {r['id']} | {r['n_elements']} | {f(r['push']['dx_mm'])} | {f(r['tow']['dx_mm'])} | {s['peak_N']} | {s['slack']} | {s['gap_min_m']} | {s['boat_roll_deg']} | {s['score']} |")
for r in rows:
    if not r["score"]:
        md.append(f"| — | {r['id']} | {r['n_elements']} | {'ok' if r['push']['physical'] else 'FAIL'} {f(r['push']['dx_mm'])} | {'ok' if r['tow']['physical'] else 'FAIL'} {f(r['tow']['dx_mm'])} | | | | | gate |")
md.append("\n## Per wave\n\n| id | wave | line peak [N] | slack | fender peak [N] | fender free | tube peak [N] | gap min [m] | boat roll [°] |\n|---|---|---|---|---|---|---|---|---|")
for r in rows:
    for wid, w in r["waves"].items():
        if "error" in w:
            md.append(f"| {r['id']} | {wid} | error: {w['error']} | | | | | | |"); continue
        md.append(f"| {r['id']} | {wid} | {f(w.get('line_peak_N'))} | {f(w.get('slack_frac'), 2)} | {f(w.get('fender_peak_N'))} | {f(w.get('fender_free_frac'), 2)} | "
                  f"{f(w.get('strut_peak_N'))} | {f(w.get('transom_gap_min_m'), 3)} | {f(w['boat_roll_deg'], 1)} |")
md.append("\n## Static\n\n| id | case | ok | dx [mm] | yaw [°] | line max [N] | fender max [N] | tube max [N] | slack |\n|---|---|---|---|---|---|---|---|---|")
for r in rows:
    for cs in ("moored", "push", "tow"):
        c = r[cs]
        md.append(f"| {r['id']} | {cs} | {c['physical']} | {f(c['dx_mm'])} | {f(c['yaw_deg'], 2)} | {f(c['line_max_N'])} | {f(c['fender_max_N'])} | {f(c['strut_max_N'])} | {', '.join(c['slack']) or '—'} |")
md.append("\n## Titles\n")
md += [f"- `{r['id']}` — {r['title']}" for r in rows]
(OUT / "final_comparison.md").write_text("\n".join(md) + "\n")
print("\n".join(md[:6 + len(ranked) + 3]))
