"""Scenario save/load and comparison tables. Values that were not computed stay None (never filled in)."""
from __future__ import annotations

import json
from pathlib import Path


def save_scenario(scenario, path):
    scenario = dict(scenario)
    scenario.setdefault("schema", "exo01_scenario_v1")
    Path(path).write_text(json.dumps(scenario, indent=1, sort_keys=False))
    return path


def compare_table(results, waves=None):
    """One row per evaluated scenario. `waves` = optional {scenario_name: regular_wave_result}."""
    rows = []
    for r in results:
        mp = r.get("mass", {})
        eq = r.get("equilibrium") or {}
        st = r.get("stability_static") or {}
        fb = eq.get("freeboard") or {}
        com = mp.get("com_m")
        row = dict(
            name=r.get("scenario") or r.get("name"), title=r.get("title"), label=r.get("label"),
            status=r["status"].get("equilibrium", r["status"].get("all")),
            total_listed_mass_kg=mp.get("total_listed_mass_kg"),
            com_x_m=None if com is None else com[0], com_y_m=None if com is None else com[1],
            com_z_m=None if com is None else com[2],
            heel_deg=eq.get("heel_deg"), trim_deg=eq.get("trim_deg"),
            draft_max_m=fb.get("draft_max_m"), float_top_freeboard_min_m=fb.get("float_top_freeboard_min_m"),
            lower_deck_freeboard_min_m=fb.get("lower_deck_freeboard_min_m"),
            displaced_volume_m3=eq.get("displaced_volume_m3"),
            GM_transverse_m=st.get("GM_transverse_m"), GM_longitudinal_m=st.get("GM_longitudinal_m"))
        w = (waves or {}).get(row["name"])
        if w and w.get("in_range"):
            row.update(heave_amp_m=w["amplitude"]["heave"], roll_amp_deg=w["amplitude_deg"]["roll"],
                       pitch_amp_deg=w["amplitude_deg"]["pitch"],
                       deck_accel_vertical_max_amp_ms2=w.get("deck_accel_vertical_max_amp_ms2"),
                       wave_flags=[f[1] for f in w["flags"]])
        else:
            row.update(heave_amp_m=None, roll_amp_deg=None, pitch_amp_deg=None,
                       deck_accel_vertical_max_amp_ms2=None, wave_flags=None)
        rows.append(row)
    return rows
