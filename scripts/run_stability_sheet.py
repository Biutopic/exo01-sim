"""EXO-01 alone: flotation and stability sheet (light ship, passenger load cases, crowding heel, deck-wetting wave height)
-> results/stability/. Input for a registration file (DDTM / service instructeur), NOT a certificate: every number comes from
the exploratory model (assumed masses, proxy floats) and must be replaced by the weighing and the inclining test.

    python scripts/run_stability_sheet.py

Passenger mass 75 kg (the usual value of inland passenger-vessel rules); criteria quoted as orders of magnitude the
applicable text must confirm: heel <= 12 deg under crowding, residual freeboard >= 0.20 m at the rear deck edge (ES-TRIN art. 19.03 values: 75 kg per person, 4 persons per m2, heel <= 12 deg, residual freeboard >= 0.20 m), and
the deck edge not reached by the wave (linear relative motion) for the stated wave height.
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

from exo01.analysis import evaluate, hydro_for, build_response, HYDRO_DEFAULTS  # noqa: E402
from exo01.config import load_config, resolve  # noqa: E402

OUT = ROOT / "results" / "stability"
OUT.mkdir(parents=True, exist_ok=True)
LABEL = "Exploratory — assumed geometry and mass distribution; not a measured stability test."
ill = load_config("illustrative")
MP = 75.0
HEEL_MAX = 12.0
FB_MIN = 0.20
BATT = {"figure_x1.43": 1.425, "float_frame_x3.60": 3.60, "end_frame_x4.24": 4.24}
t0 = time.time()


def person(i, x, y, surf):
    return dict(id=f"P{i}", name=f"passenger {i}", mass_kg=MP, mass_source="rule value 75 kg (assumption)", surface=surf, posture="standing", x_m=x, y_m=y)


def run(bx, people, thrust=0.0):
    ov = {"host_boat": {"included": False}, "components": {"BATTERY_1": {"com_m": [bx, -2.05, 0.5]}, "BATTERY_2": {"com_m": [bx, 2.05, 0.5]}},
          "people": people, "propulsion": {"thrust_fraction": thrust}}
    cfg = resolve(ill, ov)
    r = evaluate(cfg)
    e = r["equilibrium"]
    if not e.get("feasible"):
        return dict(feasible=False, reason=e.get("reason") or r["status"].get("equilibrium"), people=len(people)), r, cfg
    fb = e["freeboard"]; st = r.get("stability_static") or {}
    return dict(feasible=True, people=len(people), mass_kg=r["mass"]["total_mass_kg"], heel_deg=e["heel_deg"], trim_deg=e["trim_deg"], draught_m=fb["draft_max_m"],
                deck_freeboard_min_m=fb["lower_deck_freeboard_min_m"], float_top_freeboard_min_m=fb["float_top_freeboard_min_m"],
                GM_T_m=st.get("GM_transverse_m"), GM_L_m=st.get("GM_longitudinal_m"), KG_m=r["mass"]["com_m"][2], com_x_m=r["mass"]["com_m"][0]), r, cfg


# ---- placements: n persons on a surface, spread or crowded to one side
def spread(n, surf, x0, x1, half_y):
    cols = 2 if n > 1 else 1
    rows = int(np.ceil(n / cols))
    pts = []
    for i in range(n):
        rr, cc = divmod(i, cols)
        x = x0 + (x1 - x0) * (rr + 0.5) / rows
        y = (-half_y if cc == 0 else half_y) if cols == 2 else 0.0
        pts.append(person(i + 1, x, y, surf))
    return pts


def crowd(n, surf, x0, x1, y):
    return [person(i + 1, x0 + (x1 - x0) * (i + 0.5) / n, y, surf) for i in range(n)]


CASES = {
    "rear_deck_spread": lambda n: spread(n, "lower_deck", 0.5, 1.9, 1.3),
    "upper_deck_spread": lambda n: spread(n, "observation_deck", 2.3, 3.4, 1.2),
    "both_decks_spread": lambda n: spread(n - n // 2, "lower_deck", 0.5, 1.9, 1.3) + [dict(p, id=f"U{i}") for i, p in enumerate(spread(n // 2, "observation_deck", 2.3, 3.4, 1.2))],
    "rear_deck_one_side": lambda n: crowd(n, "lower_deck", 0.4, 2.0, 1.9),
    "upper_deck_one_side": lambda n: crowd(n, "observation_deck", 2.2, 3.4, 1.9),
    "rear_deck_stern_corner": lambda n: crowd(n, "lower_deck", 0.2, 0.9, 1.9),
}

sheet = {"label": LABEL, "passenger_mass_kg": MP, "criteria": dict(heel_max_deg=HEEL_MAX, residual_deck_freeboard_min_m=FB_MIN,
         note="orders of magnitude used by inland passenger-craft rules; the applicable text (ES-TRIN / arrêté) must be confirmed with the service instructeur"),
         "batteries": {}, "seconds": None}
rows = []
for bname, bx in BATT.items():
    light, r_light, cfg_light = run(bx, [])
    b = dict(light_ship=light, cases={})
    # capacity per case: largest n (1..10) that keeps heel <= HEEL_MAX and deck freeboard >= FB_MIN
    for cname, fn in CASES.items():
        res = []
        for n in range(1, 11):
            m, _, _ = run(bx, fn(n))
            m.update(batteries=bname, case=cname)
            res.append(m); rows.append(m)
            if not m["feasible"]:
                break
        ok = [m["people"] for m in res if m["feasible"] and abs(m["heel_deg"]) <= HEEL_MAX and m["deck_freeboard_min_m"] >= FB_MIN]
        b["cases"][cname] = dict(max_people=max(ok) if ok else 0, limiting=None)
        if ok:
            nmax = max(ok)
            nxt = [m for m in res if m["people"] == nmax + 1]
            if nxt:
                m = nxt[0]
                b["cases"][cname]["limiting"] = ("no equilibrium" if not m["feasible"] else ("heel" if abs(m["heel_deg"]) > HEEL_MAX else "deck freeboard"))
    b["max_people_all_cases"] = min(v["max_people"] for v in b["cases"].values())
    # deck-wetting wave height (linear): H_max = H_ref * still_fb / relative_motion_amp at the worst deck corner, by period/heading
    S = dict(HYDRO_DEFAULTS)
    om = np.round(np.arange(S["omega_min"], S["omega_max"] + 1e-9, S["omega_step"]), 10)
    hd = np.radians([0.0, 45.0, 90.0, 135.0, 180.0])
    D = {"zeta": {"heave": 0.05, "roll": 0.05, "pitch": 0.05}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}}
    hmax = {}
    for lbl, people in (("light", []), (f"{b['max_people_all_cases']}_passengers_both_decks", CASES["both_decks_spread"](max(b["max_people_all_cases"], 1)))):
        m, r, cfg = run(bx, people)
        try:
            hdd = hydro_for(r, cfg, om, hd, S, cache_only=True, allow_pose_reuse=True)
            model = build_response(r, hdd, cfg)
            table = {}
            for T in (1.5, 2.0, 2.5, 3.0, 4.0):
                for j, hdg in enumerate((0, 45, 90, 135, 180)):
                    rw = model.regular_wave(0.3, T, hd[j], D, cfg["deck_acceleration_points"])
                    if not rw.get("in_range"):
                        continue
                    dc = rw["bodies"]["EXO"]["deck_corner_relative_motion"]
                    worst = min(dc.values(), key=lambda v: v["still_freeboard_m"] / max(v["relative_motion_amp_m"], 1e-9))
                    table[f"T{T}_b{hdg}"] = dict(T_s=T, heading_deg=hdg, H_deck_edge_awash_m=0.3 * worst["still_freeboard_m"] / max(worst["relative_motion_amp_m"], 1e-9),
                                                 roll_amp_deg_per_m=rw["bodies"]["EXO"]["amplitude_deg"]["roll"] / 0.3, pitch_amp_deg_per_m=rw["bodies"]["EXO"]["amplitude_deg"]["pitch"] / 0.3,
                                                 pose_reuse=hdd.meta.get("pose_reuse"))
            hmax[lbl] = dict(table=table, H_min_over_table_m=min(v["H_deck_edge_awash_m"] for v in table.values()) if table else None, pose_reuse=hdd.meta.get("pose_reuse"))
        except Exception as e:  # noqa: BLE001
            hmax[lbl] = dict(error=f"{type(e).__name__}: {e}")
    b["deck_wetting_wave_height"] = hmax
    sheet["batteries"][bname] = b
    print(bname, "light trim %.2f fb %.2f GM_T %.1f" % (light["trim_deg"], light["deck_freeboard_min_m"], light["GM_T_m"]), "max people", b["max_people_all_cases"],
          {k: (v["max_people"], v["limiting"]) for k, v in b["cases"].items()}, "H_awash light", hmax.get("light", {}).get("H_min_over_table_m"), f"({time.time() - t0:.0f} s)", flush=True)

sheet["seconds"] = time.time() - t0
(OUT / "stability_sheet.json").write_text(json.dumps(sheet, indent=1, default=str))
with (OUT / "load_cases.csv").open("w", newline="") as fh:
    w = csv.writer(fh); w.writerow(["batteries", "case", "people", "feasible", "mass_kg", "heel_deg", "trim_deg", "draught_m", "deck_freeboard_min_m", "float_top_freeboard_min_m", "GM_T_m", "GM_L_m", "KG_m"])
    for m in rows:
        w.writerow([m["batteries"], m["case"], m["people"], m["feasible"]] + [f"{m[k]:.3f}" if m.get(k) is not None and m["feasible"] else "" for k in ("mass_kg", "heel_deg", "trim_deg", "draught_m", "deck_freeboard_min_m", "float_top_freeboard_min_m", "GM_T_m", "GM_L_m", "KG_m")])


def f(v, d=2):
    return "—" if v is None else (f"{v:.{d}f}" if isinstance(v, (int, float)) else str(v))


md = [f"# EXO-01 alone — flotation and stability sheet ({LABEL})", "",
      f"Passenger mass {MP:.0f} kg. Criteria used to read the tables (orders of magnitude, to be confirmed with the service instructeur): heel ≤ {HEEL_MAX:.0f}° under crowding, "
      f"residual freeboard ≥ {FB_MIN:.2f} m at the rear deck edge. Nothing here replaces the weighing and the inclining test.", ""]
for bname, b in sheet["batteries"].items():
    L = b["light_ship"]
    md += [f"## Batteries: {bname}", "", f"Light ship: {L['mass_kg']:.0f} kg listed, draught {L['draught_m']:.2f} m, trim {L['trim_deg']:+.2f}°, heel {L['heel_deg']:+.2f}°, rear-deck freeboard {L['deck_freeboard_min_m']:.2f} m, "
           f"float-top freeboard {L['float_top_freeboard_min_m']:.2f} m, GM_T {L['GM_T_m']:.1f} m, GM_L {L['GM_L_m']:.1f} m, KG {L['KG_m']:.2f} m.", "",
           "| load case | max passengers | limited by |", "|---|---|---|"]
    for cname, v in b["cases"].items():
        md.append(f"| {cname} | {v['max_people']} | {v['limiting'] or '—'} |")
    md += [f"", f"**Capacity over all placements: {b['max_people_all_cases']} passengers** (the worst placement governs).", "",
           "| load case | n | heel [°] | trim [°] | deck freeboard [m] | float-top freeboard [m] |", "|---|---|---|---|---|---|"]
    for m in rows:
        if m["batteries"] == bname and m["feasible"] and (m["people"] in (1, 2, 4, 6, 8) or m["people"] == b["cases"][m["case"]]["max_people"]):
            md.append(f"| {m['case']} | {m['people']} | {m['heel_deg']:+.1f} | {m['trim_deg']:+.1f} | {m['deck_freeboard_min_m']:.2f} | {m['float_top_freeboard_min_m']:.2f} |")
    md += ["", "Deck-edge-awash regular wave height (linear relative motion at the worst rear-deck corner, scaled from H 0.3 m; linear theory, read values above ~0.6 m as 'outside the model'):", "",
           "| loading | T 1.5 s | T 2.0 s | T 2.5 s | T 3.0 s | T 4.0 s |", "|---|---|---|---|---|---|"]
    for lbl, hx in b["deck_wetting_wave_height"].items():
        if "table" not in hx:
            md.append(f"| {lbl} | error: {hx.get('error')} |"); continue
        cells = []
        for T in (1.5, 2.0, 2.5, 3.0, 4.0):
            vals = [v for v in hx["table"].values() if v["T_s"] == T]
            cells.append(f"{min(v['H_deck_edge_awash_m'] for v in vals):.2f} (β {min(vals, key=lambda v: v['H_deck_edge_awash_m'])['heading_deg']}°)" if vals else "—")
        md.append(f"| {lbl} | " + " | ".join(cells) + " |")
    md.append("")
(OUT / "stability_sheet.md").write_text("\n".join(md))
print(f"done in {time.time() - t0:.0f} s -> {OUT}")
