"""Design sweeps with the actual solvers: battery position and mooring-line arrangement.

Nothing here is a black-box optimiser: every candidate is evaluated with the same still-water (coupled) equilibrium,
propulsion and wave-response code as the interface, and the full table is returned so the trade-offs are visible.
Wave columns use the BEM of the base pose (exact reference-point transform to each candidate's COM; the pose
difference is within hydro.POSE_TOL or the wave columns are left empty) - the hydro_note says which.
"""
from __future__ import annotations

import copy
import itertools
import time

import numpy as np

from .analysis import evaluate, hydro_for, build_response, has_boat
from .config import resolve
from .hydro import HydroNotComputed

LABEL = "Exploratory — assumed geometry and mass distribution."


# ------------------------------------------------------------------ helpers
def _wave_metrics(res, cfg, wave, damping, settings):
    """Regular-wave response of an evaluated candidate with the (nearby-pose) cached BEM; None if none is usable."""
    om = np.round(np.arange(settings["omega_min"], settings["omega_max"] + 1e-9, settings["omega_step"]), 10)
    hd = np.array([np.radians(float(wave.get("heading_deg", 90.0)))])
    try:
        hdd = hydro_for(res, cfg, om, hd, settings, cache_only=True, allow_pose_reuse=True)
    except HydroNotComputed as e:
        return None, f"{e}"
    model = build_response(res, hdd, cfg)
    speed = (res.get("propulsion") or {}).get("speed_m_s", 0.0) or 0.0
    rw = model.regular_wave(float(wave.get("H_m", 0.3)), float(wave.get("T_s", 2.5)), hd[0], damping, cfg["deck_acceleration_points"], speed=speed)
    if not rw.get("in_range"):
        return None, rw.get("error")
    exo = rw["bodies"]["EXO"]
    m = dict(roll_amp_deg=exo["amplitude_deg"]["roll"], pitch_amp_deg=exo["amplitude_deg"]["pitch"], heave_amp_m=exo["amplitude"]["heave"],
             deck_accel_max_ms2=exo.get("deck_accel_vertical_max_amp_ms2"),
             deck_corner_min_clearance_m=min((v["min_clearance_m"] for v in (exo.get("deck_corner_relative_motion") or {}).values()), default=None),
             pose_reuse=hdd.meta.get("pose_reuse"), hydro_cache=hdd.meta.get("cache"))
    if "BOAT" in rw["bodies"]:
        b = rw["bodies"]["BOAT"]
        m.update(boat_roll_amp_deg=b["amplitude_deg"]["roll"], boat_pitch_amp_deg=b["amplitude_deg"]["pitch"])
    if rw.get("lines"):
        m.update(line_min_dyn_N=min(l["min_N"] for l in rw["lines"]), line_max_dyn_N=max(l["max_N"] for l in rw["lines"]),
                 lines_slack_in_cycle=[l["id"] for l in rw["lines"] if l["slack_in_cycle"]])
    if rw.get("min_relative_clearance"):
        m["min_relative_clearance_m"] = rw["min_relative_clearance"]["min_clearance_m"]
        m["min_relative_clearance_at"] = rw["min_relative_clearance"]["name"]
    return m, None


def _still_metrics(res):
    e = res.get("equilibrium") or {}
    if not e.get("feasible"):
        return dict(feasible=False, reason=e.get("reason") or res["status"].get("equilibrium"))
    fb = e["freeboard"]
    st = res.get("stability_static") or {}
    m = dict(feasible=True, heel_deg=e["heel_deg"], trim_deg=e["trim_deg"], draft_m=fb["draft_max_m"],
             deck_freeboard_min_m=fb["lower_deck_freeboard_min_m"], float_top_freeboard_min_m=fb["float_top_freeboard_min_m"],
             GM_T_m=st.get("GM_transverse_m"), GM_L_m=st.get("GM_longitudinal_m"), com_z_m=res["mass"]["com_m"][2],
             com_x_m=res["mass"]["com_m"][0], flags=[f for f in res.get("flags", []) if "PROPULSION" not in f])
    if res.get("lines"):
        m.update(line_min_N=min(l["tension_N"] for l in res["lines"]), line_max_N=max(l["tension_N"] for l in res["lines"]),
                 slack_lines=[l["id"] for l in res["lines"] if l["slack"]])
    if res.get("coupled_equilibrium"):
        m["coupled_converged"] = res["coupled_equilibrium"]["converged"]
    return m


def _rect_overlap(a, b):
    return not (a[1] <= b[0] or b[1] <= a[0] or a[3] <= b[2] or b[3] <= a[2])


# ------------------------------------------------------------------ battery position
BATTERY_FOOTPRINT = (0.55, 0.30)        # x, y (upright PowerBrick, drawn size)
DECK_X = (0.0, 2.1)
DECK_HALF_Y = 2.2735
# obstacles on the rear deck (x0, x1, y0, y1), from the user's layout (28/10): cabinet port side, ladder starboard side,
# pod brackets at the aft corners
OBSTACLES = {"cabinet": (1.50, 1.96, 0.62, 1.54), "ladder": (1.10, 2.10, -1.45, -0.75), "pod_bracket_stbd": (0.0, 0.45, -2.2735, -1.75),
             "pod_bracket_port": (0.0, 0.45, 1.75, 2.2735)}
# second zone (user, 29/10): the float-top side frames forward of the rear deck, alongside the boat. The batteries sit above
# the float row (|y| = 2.05: float spans 1.67-2.27, boat half-beam 1.49 -> no conflict with the hull); the frame runs from
# the deck edge to the float noses, with the mid and end uprights (x 2.81 / 4.24) as obstacles. Whether the float cradle
# can carry 120 kg per battery is a structural question outside this model.
FRAME_X = (2.1, 4.9)
FRAME_Y = (1.67, 2.2735)
FRAME_OBSTACLES = {"upright_mid": (2.76, 2.86), "upright_end": (4.19, 4.29)}
BATTERY_ZONES = {"rear_deck": "rear deck plate (x 0-2.1 m)", "float_frame": "float-top side frames forward of the deck (x 2.1-4.9 m)"}


def battery_candidates(options):
    """Mirrored positions (x, |y|) on the rear deck, plus asymmetric variants (the port battery moved inboard by 0.3-0.9 m
    to counter the port-side cabinet) at every x, plus mirrored positions on the float-top side frames forward of the
    deck; footprints must stay inside their zone and clear of the obstacles. Each candidate carries its zone."""
    dx = float(options.get("dx", 0.20))
    xs = np.round(np.arange(0.30, 1.90, dx), 3)
    ys = [2.05, 1.70, 1.30, 0.90, 0.50, 0.20]
    fx, fy = BATTERY_FOOTPRINT
    out = []

    def ok(x, y_stbd, y_port):
        rects = [(x - fx / 2, x + fx / 2, -y_stbd - fy / 2, -y_stbd + fy / 2), (x - fx / 2, x + fx / 2, y_port - fy / 2, y_port + fy / 2)]
        if any(r[0] < DECK_X[0] - 1e-9 or r[1] > DECK_X[1] + 1e-9 or r[2] < -DECK_HALF_Y or r[3] > DECK_HALF_Y for r in rects):
            return False
        if any(_rect_overlap(r, o) for r in rects for o in OBSTACLES.values()):
            return False
        return y_stbd + y_port >= fy                      # the two batteries must not overlap each other
    for x in xs:
        for y in ys:
            if ok(x, y, y):
                out.append(dict(x_m=float(x), y_stbd_m=float(y), y_port_m=float(y), symmetric=True, zone="rear_deck"))
        for d in (0.3, 0.6, 0.9):
            if ok(x, 2.05, 2.05 - d):
                out.append(dict(x_m=float(x), y_stbd_m=2.05, y_port_m=float(round(2.05 - d, 3)), symmetric=False, zone="rear_deck"))
    # float-top frames: one lateral position (above the float), x from the deck edge to the float noses
    if options.get("zones", "all") in ("all", "float_frame"):
        y = 2.05
        for x in np.round(np.arange(FRAME_X[0] + fx / 2 + 0.05, FRAME_X[1] - fx / 2 + 1e-9, dx), 3):
            x0, x1 = x - fx / 2, x + fx / 2
            if y - fy / 2 < FRAME_Y[0] or y + fy / 2 > FRAME_Y[1]:
                continue
            if any(not (x1 <= o[0] or o[1] <= x0) for o in FRAME_OBSTACLES.values()):
                continue
            out.append(dict(x_m=float(x), y_stbd_m=y, y_port_m=y, symmetric=True, zone="float_frame"))
    if options.get("zones") == "rear_deck":
        out = [c for c in out if c["zone"] == "rear_deck"]
    return out


def optimise_battery(cfg, wave, damping, settings, progress=None, options=None):
    options = options or {}
    cands = battery_candidates(options)
    rows, notes = [], []
    hydro_note = None
    t0 = time.time()
    for i, c in enumerate(cands):
        ov = {"components": {"BATTERY_1": {"com_m": [c["x_m"], -c["y_stbd_m"], 0.50]}, "BATTERY_2": {"com_m": [c["x_m"], c["y_port_m"], 0.50]}}}
        cfg_c = resolve(cfg, dict(ov, propulsion={"thrust_fraction": 0.0}))      # static berth (motor off)
        res = evaluate(cfg_c)
        row = dict(candidate=c, overrides=ov, **_still_metrics(res))
        if row["feasible"]:
            wm, err = _wave_metrics(res, cfg_c, wave, damping, settings)
            if wm:
                row.update(wm)
            elif hydro_note is None:
                hydro_note = f"wave columns not computed: {err}"
        rows.append(row)
        if progress:
            progress((i + 1) / len(cands), f"battery candidate {i + 1}/{len(cands)} ({time.time() - t0:.0f} s)")
    feas = [r for r in rows if r["feasible"]]
    # scores: (1) level attitude, (2) wave motion; the combined ranking is transparent and editable
    for r in feas:
        r["score_level"] = abs(r["trim_deg"]) + 2.0 * abs(r["heel_deg"]) + 10.0 * max(0.0, 0.15 - r["deck_freeboard_min_m"])
        if r.get("roll_amp_deg") is not None:
            r["score_motion"] = r["roll_amp_deg"] + r["pitch_amp_deg"] + (r.get("deck_accel_max_ms2") or 0.0)
        else:
            r["score_motion"] = None
        r["score"] = r["score_level"] + (0.5 * r["score_motion"] if r["score_motion"] is not None else 0.0)
    feas.sort(key=lambda r: r["score"])
    for k, r in enumerate(feas):
        r["rank"] = k + 1
    best = feas[0] if feas else None
    # physical context: how far the COM is from the float centroid and what it would take to level the EXO
    zones, x_zero = {}, None
    if feas:
        notes.append("Score = |trim| + 2|heel| (deg) + freeboard penalty below 0.15 m + 0.5 x (roll + pitch amplitude (deg) + deck accel (m/s2)) "
                     "at the reference wave; edit the weights in exo01/optimise.py if your priorities differ.")
        for z in BATTERY_ZONES:
            fz = [r for r in feas if r["candidate"]["zone"] == z]
            if fz:
                bz = min(fz, key=lambda r: abs(r["trim_deg"]))
                zones[z] = dict(best_rank=min(r["rank"] for r in fz), n=len(fz), x_min_trim_m=bz["candidate"]["x_m"], trim_deg=bz["trim_deg"],
                                heel_deg=bz["heel_deg"], deck_freeboard_min_m=bz["deck_freeboard_min_m"], label=BATTERY_ZONES[z])
        # zero-trim position along the symmetric |y| = 2.05 column (linear interpolation between neighbouring x)
        col = sorted([r for r in feas if r["candidate"]["symmetric"] and abs(r["candidate"]["y_stbd_m"] - 2.05) < 1e-6], key=lambda r: r["candidate"]["x_m"])
        x_zero = None
        for a, b in zip(col, col[1:]):
            ta, tb = a["trim_deg"], b["trim_deg"]
            if ta * tb <= 0 and ta != tb:
                xa, xb = a["candidate"]["x_m"], b["candidate"]["x_m"]
                x_zero = xa + (xb - xa) * ta / (ta - tb)
                break
        rd, ff = zones.get("rear_deck"), zones.get("float_frame")
        if rd:
            notes.append(f"Rear deck (x 0-2.1 m): the most forward row is the best for trim, but the COM stays aft of the float centroid - "
                         f"least trim {rd['trim_deg']:+.2f} deg at x = {rd['x_min_trim_m']:.2f} m. Asymmetric rows (port battery moved inboard) "
                         f"counter the heel from the port-side cabinet.")
        if ff:
            notes.append(f"Float-top side frames (x 2.1-4.9 m, |y| 2.05 m, above the floats, outboard of the hull): least trim "
                         f"{ff['trim_deg']:+.2f} deg at x = {ff['x_min_trim_m']:.2f} m with rear-deck freeboard {ff['deck_freeboard_min_m']:.2f} m"
                         + (f"; the trim crosses zero at x = {x_zero:.2f} m for the loads of this scenario" if x_zero is not None else
                            "; the trim does not cross zero within the frame for the loads of this scenario (people/payload aft dominate)")
                         + ". Whether the float cradle can carry 120 kg per battery is a structural question outside this model.")
        notes.append("Trim sign: negative = rear deck down. Mass on the rear deck (people at the table) adds stern trim that the batteries "
                     "can only partly compensate - re-run with the occupants you expect.")
    return dict(target="battery", label=LABEL, rows=rows, best=None if best is None else dict(candidate=best["candidate"], overrides_to_apply=best["overrides"],
                                                                                           score=best["score"]),
                zones=zones, x_zero_trim_m=x_zero,
                notes=notes, hydro_note=hydro_note or "wave columns from the cached BEM of the base pose (exact COM transform; pose within tolerance)",
                n_candidates=len(cands), seconds=time.time() - t0)


# ------------------------------------------------------------------ line arrangement
EXO_POINTS = {"aft_post": (0.05, 2.25, 0.0), "mid_post": (2.1, 2.25, 0.0), "fwd_post": (4.95, 2.25, 0.0)}
BOAT_CLEATS = {"stern": (0.3, 1.30, 0.8), "aft_quarter": (2.0, 1.35, 0.8), "midship": (4.3, 1.35, 0.8)}


def _pair(name, e, b):
    return [dict(id=f"{name}_PORT", exo_point_m=[e[0], e[1], e[2]], boat_point_m=[b[0], b[1], b[2]]),
            dict(id=f"{name}_STBD", exo_point_m=[e[0], -e[1], e[2]], boat_point_m=[b[0], -b[1], b[2]])]


def line_candidates(cfg, options):
    pairs = {f"{ek}>{bk}": (ev, bv) for ek, ev in EXO_POINTS.items() for bk, bv in BOAT_CLEATS.items()}
    n_pairs = int(options.get("pairs", 2))
    out = []
    for combo in itertools.combinations(sorted(pairs), n_pairs):
        lines = []
        for name in combo:
            e, b = pairs[name]
            lines += _pair(name.replace(">", "_TO_").upper(), e, b)
        out.append(dict(id="+".join(combo), lines=lines, source="candidate"))
    for p in (cfg.get("host_boat") or {}).get("line_presets", []):
        out.append(dict(id=p["id"], lines=p["lines"], source="preset", title=p.get("title")))
    return out


def optimise_lines(cfg, wave, damping, settings, progress=None, options=None):
    options = options or {}
    if not (cfg.get("host_boat") or {}).get("included"):
        raise ValueError("line optimisation needs the host boat included")
    cands = line_candidates(cfg, options)
    push = float(options.get("push_fraction", 1.0))
    tow = float(options.get("tow_fraction", 1.0))
    rows = []
    hydro_note = None
    t0 = time.time()
    for i, c in enumerate(cands):
        ov = {"host_boat": {"lines": c["lines"]}}
        cfg0 = resolve(cfg, dict(ov, propulsion={"thrust_fraction": 0.0}))
        r0 = evaluate(cfg0)
        row = dict(candidate=dict(id=c["id"], source=c["source"], title=c.get("title"), n_lines=len(c["lines"])), overrides=ov, **_still_metrics(r0))
        if row["feasible"]:
            rp = evaluate(resolve(cfg, dict(ov, propulsion={"thrust_fraction": push, "unit": "EXO_PODS"})))
            ce = rp.get("coupled_equilibrium") or {}
            row.update(push_converged=bool(ce.get("physical", ce.get("converged"))), push_speed_m_s=(rp.get("propulsion") or {}).get("speed_m_s"),
                       push_boat_shift_m=float(np.hypot((ce.get("boat_shift_from_nominal") or {}).get("dx_m", 0), (ce.get("boat_shift_from_nominal") or {}).get("dy_m", 0))),
                       push_line_max_N=(max(l["tension_N"] for l in rp["lines"]) if rp.get("lines") and ce.get("converged") else None),
                       push_slack=[l["id"] for l in rp.get("lines", []) if l["slack"]] if ce.get("converged") else None,
                       push_trim_deg=rp["equilibrium"]["trim_deg"] if ce.get("converged") else None)
            rt = evaluate(resolve(cfg, dict(ov, propulsion={"thrust_fraction": tow, "unit": "BOAT_ENGINE"})))
            ct = rt.get("coupled_equilibrium") or {}
            row.update(tow_converged=bool(ct.get("physical", ct.get("converged"))),
                       tow_boat_shift_m=float(np.hypot((ct.get("boat_shift_from_nominal") or {}).get("dx_m", 0), (ct.get("boat_shift_from_nominal") or {}).get("dy_m", 0))),
                       tow_line_max_N=(max(l["tension_N"] for l in rt["lines"]) if rt.get("lines") and ct.get("converged") else None),
                       tow_slack=[l["id"] for l in rt.get("lines", []) if l["slack"]] if ct.get("converged") else None)
            wm, err = _wave_metrics(r0, cfg0, wave, damping, settings)
            if wm:
                row.update(wm)
            elif hydro_note is None:
                hydro_note = f"wave columns not computed: {err}"
        rows.append(row)
        if progress:
            progress((i + 1) / len(cands), f"line arrangement {i + 1}/{len(cands)} ({time.time() - t0:.0f} s)")
    feas = [r for r in rows if r["feasible"]]
    for r in feas:
        ok_push, ok_tow = bool(r.get("push_converged")), bool(r.get("tow_converged"))
        s = 0.0
        if not ok_push:
            s += 1000.0
        if not ok_tow:
            s += 1000.0
        s += 0.001 * (r.get("push_line_max_N") or 0.0) + 0.001 * (r.get("tow_line_max_N") or 0.0)     # 1 point per kN
        s += 3.0 * len(r.get("slack_lines") or [])                 # slack at rest: the boat is not held by that line at all
        if r.get("lines_slack_in_cycle") is not None:
            s += 1.0 * len(r["lines_slack_in_cycle"])              # goes slack in the reference wave (snatch loads)
        mrc = r.get("min_relative_clearance_m")
        if mrc is not None:
            s += 100.0 if mrc <= 0 else 5.0 * max(0.0, 0.10 - mrc) / 0.1     # hull would hit a float in the reference wave
        if (r.get("push_boat_shift_m") or 0.0) > 0.08 or (r.get("tow_boat_shift_m") or 0.0) > 0.08:
            s += 2.0                                                # the berth slack is nearly used up under thrust
        r["score"] = s
        r["can_push"], r["can_tow"] = ok_push, ok_tow
    feas.sort(key=lambda r: r["score"])
    for k, r in enumerate(feas):
        r["rank"] = k + 1
    # nonlinear (tension-only) check of the best candidates in the reference wave: peak tension and slack fraction
    for r in feas[:10]:
        if r.get("roll_amp_deg") is None:
            continue
        try:
            from .response import line_snatch_check
            cfg0 = resolve(cfg, dict(r["overrides"], propulsion={"thrust_fraction": 0.0}))
            r0 = evaluate(cfg0)
            om = np.round(np.arange(settings["omega_min"], settings["omega_max"] + 1e-9, settings["omega_step"]), 10)
            hd = np.array([np.radians(float(wave.get("heading_deg", 90.0)))])
            hdd = hydro_for(r0, cfg0, om, hd, settings, cache_only=True, allow_pose_reuse=True)
            model = build_response(r0, hdd, cfg0)
            model.regular_wave(float(wave.get("H_m", 0.3)), float(wave.get("T_s", 2.5)), hd[0], damping, cfg0["deck_acceleration_points"])
            sn = line_snatch_check(model, 2 * np.pi / float(wave.get("T_s", 2.5)), hd[0], float(wave.get("H_m", 0.3)), damping, n_periods=10, steps_per_period=64)
            r["snatch_peak_N"] = max(l["peak_N"] for l in sn["lines"])
            r["snatch_slack_fraction_max"] = max(l["slack_fraction_of_cycle"] for l in sn["lines"])
            r["snatch_ratio_max"] = max((l["snatch_ratio"] or 0.0) for l in sn["lines"])
        except Exception as e:  # noqa: BLE001
            r["snatch_error"] = f"{type(e).__name__}: {e}"
        if progress:
            progress(1.0, f"snatch check of the top candidates ({r['rank']}/10)")
    best = feas[0] if feas else None
    notes = ["Score: +1000 if the arrangement cannot carry the pods' push (EXO_PODS 100 %) or a tow by the boat's engine (BOAT_ENGINE 100 %) "
             "without the boat sliding into the EXO structure (an equilibrium reached only with INTERFERENCE counts as 'cannot'), "
             "+1 per kN of the highest line tension under push and under tow, +3 per line slack at rest, +1 per line that goes slack in the "
             "reference wave, +100 if the hull would touch a float in the reference wave (else +5 per 0.1 m of clearance below 0.1 m), "
             "+2 if the boat slides more than 80 mm under push or tow. Attachment points are ASSUMED post and cleat positions.",
             "A line can only pull: to push the boat forward a line must run from an EXO point to a boat point AFT of it; to tow (or brake) "
             "the boat it must run to a boat point FORWARD of it. Both are needed for a thrust-capable berth; long lines carry force with less "
             "lateral squeeze than short cross lines."]
    return dict(target="lines", label=LABEL, rows=rows, best=None if best is None else dict(candidate=best["candidate"], overrides_to_apply=best["overrides"], score=best["score"]),
                notes=notes, hydro_note=hydro_note or "wave columns from the cached BEM of the base pose (exact COM transform; pose within tolerance)",
                n_candidates=len(cands), seconds=time.time() - t0)


def run_optimisation(cfg, target, wave, damping, settings, progress=None, options=None):
    if target == "lines":
        return optimise_lines(cfg, wave, damping, settings, progress, options)
    return optimise_battery(cfg, wave, damping, settings, progress, options)
