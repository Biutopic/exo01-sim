"""Descente de charges: every coupling connection resolved into a force vector, per load case, per attachment point.

    python scripts/run_connection_loads.py

This is the load input a structural check needs, not the check itself: the project holds no frame sections, no
material and no laminate schedule (config `missing_inputs` already says so), so nothing here verifies a member.
What it produces, for each arrangement, is:

  * the force VECTOR each element applies at its EXO end and at its boat end, in every one of the nine
    thrust-derived static load cases;
  * those vectors summed per attachment point, since several elements can share a lug;
  * the governing case and direction for each point, which is what orients a padeye;
  * the linear wave peak alongside, so the dynamic amplification per element is explicit.

Self-check: the extracted vectors are summed and compared against the applied external wrench. If the force and
moment residuals are not ~0, the extraction is wrong and the run says so rather than reporting numbers.

Output: results/coupling/connection_loads.json
"""
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
from exo01.twobody import coupled_equilibrium  # noqa: E402

OUT = ROOT / "results" / "coupling"

# reuse the search's geometry, element builders, load cases and model handles
_src = (ROOT / "scripts" / "run_arrangement_search.py").read_text()
_head = _src.split("rows = []\nt0 = time.time()")[0]
NS = {"__file__": str(ROOT / "scripts" / "run_arrangement_search.py"), "__name__": "loads"}
_argv, sys.argv = sys.argv, ["x"]
exec(compile(_head, "head", "exec"), NS)
sys.argv = _argv

# the search script execs run_final_coupling's head into a namespace of its own, so the model handles are not
# re-exported; exec that head here too rather than reaching into someone else's scope
_fsrc = (ROOT / "scripts" / "run_final_coupling.py").read_text()
_fhead = _fsrc.split("# ──────────────────────────────────────────────────────────────── A · preload sweep")[0]
FNS = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "loads_model"}
_argv, sys.argv = sys.argv, ["x"]
exec(compile(_fhead, "fhead", "exec"), FNS)
sys.argv = _argv

_need = ["ASM", "M_E", "G_E", "BASM", "M_B", "G_B", "RHO", "G", "cfg_for", "CASES"]
_missing = [n for n in _need if n not in FNS]
if _missing:
    raise SystemExit(f"run_final_coupling.py no longer exports {_missing}; the extractor needs them")
ASM, M_E, G_E = FNS["ASM"], FNS["M_E"], FNS["G_E"]
BASM, M_B, G_B = FNS["BASM"], FNS["M_B"], FNS["G_B"]
RHO, G = FNS["RHO"], FNS["G"]
cfg_for, CASES = NS["cfg_for"], FNS["CASES"]
T_SNUG = NS["T_SNUG"]
WAVES, DAMP, OM, SET = NS["WAVES"], NS["DAMP"], NS["OM"], NS["SET"]
X_BERTH = NS["X_BERTH"]

# ───────────────────────────────────────────────── the arrangements the study covers
ARRANGEMENTS = {
    "I_fwd_midship_crossed": dict(
        title="Recommended (section 15): 2 midship springs + 2 crossed stern ropes + 2 rear bumpers + 2 dockwheels",
        preload=600.0,
        build=lambda t, g: (NS["pair"]("SPRING", NS["FWD_POST"], NS["MID_CLEAT"], t0=t)
                            + NS["crossed"]("CROSS", NS["MID_POST"], NS["STERN_CLEAT"], t0=g)
                            + NS["rear"]() + NS["wheels"]())),
    "C_vee_legs_crossed": dict(
        title="Smallest correction to the brief: 2 fixed bow legs + 2 crossed stern ropes + bumpers + wheels",
        preload=600.0,
        build=lambda t, g: (NS["vee_legs"](t) + NS["crossed"]("CROSS", NS["MID_POST"], NS["STERN_CLEAT"], t0=g)
                            + NS["rear"]() + NS["wheels"]())),
    "A_vee_pulley": dict(
        title="The brief's own configuration: bow-pulley V + bumpers + wheels",
        preload=2217.5,
        build=lambda t, g: NS["vee_pulley"](t) + NS["rear"]() + NS["wheels"]()),
    "U_sling_midship": dict(
        title="Sandwich option: 2 under-hull slings + 2 midship springs + bumpers + wheels",
        preload=2000.0,
        build=lambda t, g: (NS["slings"](g) + NS["pair"]("SPRING", NS["FWD_POST"], NS["MID_CLEAT"], t0=t)
                            + NS["rear"]() + NS["wheels"]())),
}
SLING_PRELOAD = 2000.0   # for the sandwich option; see results/coupling/sling_preload.json


def solve_vectors(els, surge_N=0.0, yaw_Nm=0.0):
    """Static equilibrium, returning the force VECTOR each element applies at each end."""
    cfg = cfg_for(els)

    def external(pe, pb):
        Fb = np.array([-surge_N, 0.0, 0.0])
        Mb = np.array([0.0, 0.0, -yaw_Nm])
        Fe = -Fb
        Me = -Mb - np.cross(np.asarray(pb["com_world"]) - np.asarray(pe["com_world"]), Fb)
        return Fe, Me, Fb, Mb

    eq, beq, pe, pb, lines, info, q = coupled_equilibrium(
        cfg, ASM, M_E, G_E, BASM, M_B, G_B, RHO, G, external=external)

    rec, Fb_sum, Mb_sum = {}, np.zeros(3), np.zeros(3)
    com_b = np.asarray(pb["com_world"])
    for l in lines:
        # coupled_equilibrium returns the reporting dicts: a_world/b_world/unit/tension_N (+ a2_world for a bridle).
        # For a bridle `unit` is u1 + u2, so -T * unit is the boat-side resultant for every kind.
        T = float(l["tension_N"])
        a = np.asarray(l["a_world"], float)
        b = np.asarray(l["b_world"], float)
        u = np.asarray(l["unit"], float)
        f_boat = -T * u
        if l.get("a2_world") is not None:                  # bridle / sling: one tension, two EXO legs
            a2 = np.asarray(l["a2_world"], float)
            d1, d2 = b - a, b - a2
            u1 = d1 / max(np.linalg.norm(d1), 1e-12)
            u2 = d2 / max(np.linalg.norm(d2), 1e-12)
            ends = [dict(side="EXO", point=a.tolist(), force_N=(T * u1).tolist()),
                    dict(side="EXO", point=a2.tolist(), force_N=(T * u2).tolist())]
        else:
            ends = [dict(side="EXO", point=a.tolist(), force_N=(T * u).tolist())]
        ends.append(dict(side="BOAT", point=b.tolist(), force_N=f_boat.tolist()))
        Fb_sum += f_boat
        Mb_sum += np.cross(b - com_b, f_boat)
        rec[l["id"]] = dict(kind=l.get("kind", "line"), T_N=T, slack=bool(l.get("slack")),
                            length_m=float(l["length_m"]), ends=ends,
                            magnitude_N=float(np.linalg.norm(f_boat)))
    # self-check: the boat FLOATS, so hydrostatics supply Fz, Mx and My. Only the in-plane wrench the external
    # demand describes has to be closed by the coupling: Fx, Fy and Mz (a floating body has no hydrostatic yaw
    # stiffness). Checking all six would be checking the wrong thing.
    resF = float(np.linalg.norm([Fb_sum[0] - surge_N, Fb_sum[1]]))
    resM = float(abs(Mb_sum[2] - yaw_Nm))
    return dict(converged=bool(info.get("converged")), physical=bool(info.get("physical", info.get("converged"))),
                dx_mm=1000 * q[3], dy_mm=1000 * q[4], dyaw_deg=float(np.degrees(q[5])),
                elements=rec,
                check_force_residual_N=resF, check_moment_residual_Nm=resM,
                resultant_on_boat_N=Fb_sum.tolist())


def wave_peaks(els, primary=()):
    """Linear wave peak per element, for the dynamic amplification column."""
    cfg = cfg_for(els)
    r = evaluate(cfg)
    peaks = {}
    for w in WAVES:
        try:
            hd = np.array([np.radians(w["heading_deg"])])
            hdd = hydro_for(r, cfg, OM, hd, SET, cache_only=True, allow_pose_reuse=True)
            rw = build_response(r, hdd, cfg).regular_wave(w["H_m"], w["T_s"], hd[0], DAMP,
                                                          cfg["deck_acceleration_points"])
            for l in (rw.get("lines") or []):
                v = l.get("max_N")
                if v is not None:
                    peaks[l["id"]] = max(peaks.get(l["id"], 0.0), abs(float(v)))
        except Exception as e:  # noqa: BLE001
            peaks.setdefault("_error", str(e))
    return peaks


def body_points(els):
    """element id -> its attachment coordinates in each body's OWN frame, which is what a drawing needs."""
    out = {}
    for e in els:
        out[e["id"]] = dict(exo=e.get("exo_point_m"), exo_b=e.get("exo_point_b_m"), boat=e.get("boat_point_m"))
    return out


def point_key(side, p, tol=0.02):
    """Group ends that sit on the same lug (within 20 mm), in body-frame coordinates."""
    return (side,) + tuple(round(float(c) / tol) * tol for c in p)


results = {}
t_start = time.time()
for aid, a in ARRANGEMENTS.items():
    T = a["preload"]
    els = a["build"](T, SLING_PRELOAD if aid == "U_sling_midship" else T_SNUG)
    BP = body_points(els)
    rows, bad = {}, []
    for c in CASES:
        r = solve_vectors(els, surge_N=c["surge"], yaw_Nm=c["yaw"])
        rows[c["id"]] = r
        if r["check_force_residual_N"] > 1.0 or r["check_moment_residual_Nm"] > 5.0:
            bad.append(dict(case=c["id"], F=r["check_force_residual_N"], M=r["check_moment_residual_Nm"]))

    # per-element envelope over the static cases
    env = {}
    for cid, r in rows.items():
        for eid, e in r["elements"].items():
            cur = env.setdefault(eid, dict(kind=e["kind"], length_m=round(e["length_m"], 3),
                                           max_abs_T_N=0.0, governing_case=None))
            if abs(e["T_N"]) > abs(cur["max_abs_T_N"]):
                cur.update(max_abs_T_N=e["T_N"], governing_case=cid)

    # per-attachment-point resultant envelope
    pts = {}
    for cid, r in rows.items():
        acc = {}
        for eid, e in r["elements"].items():
            bp = BP.get(eid, {})
            # ends are ordered: EXO (exo_point_m), [EXO_b (exo_point_b_m) for a bridle], BOAT (boat_point_m)
            keys = ([bp.get("exo"), bp.get("exo_b"), bp.get("boat")] if bp.get("exo_b") is not None
                    else [bp.get("exo"), bp.get("boat")])
            for nd, bpt in zip(e["ends"], keys):
                if bpt is None:
                    continue
                k = point_key(nd["side"], bpt)
                a_ = acc.setdefault(k, dict(side=nd["side"], point=list(bpt), force=np.zeros(3), elements=set()))
                a_["force"] = a_["force"] + np.asarray(nd["force_N"], float)
                a_["elements"].add(eid)
        for k, a_ in acc.items():
            mag = float(np.linalg.norm(a_["force"]))
            cur = pts.setdefault(k, dict(side=a_["side"], point=[round(c, 3) for c in a_["point"]],
                                         elements=sorted(a_["elements"]), max_resultant_N=0.0,
                                         governing_case=None, direction=None))
            cur["elements"] = sorted(set(cur["elements"]) | a_["elements"])
            if mag > cur["max_resultant_N"]:
                u = (a_["force"] / mag) if mag > 1e-9 else np.zeros(3)
                cur.update(max_resultant_N=round(mag, 1), governing_case=cid,
                           direction=[round(float(c), 3) for c in u],
                           force_N=[round(float(c), 1) for c in a_["force"]])

    pk = wave_peaks(els, ())
    for eid, e in env.items():
        p = pk.get(eid)
        e["wave_peak_N"] = None if p is None else round(p, 1)
        e["dynamic_amplification"] = (None if (p is None or abs(e["max_abs_T_N"]) < 1.0)
                                      else round(p / abs(e["max_abs_T_N"]), 2))

    results[aid] = dict(title=a["title"], primary_preload_N=T,
                        sling_preload_N=SLING_PRELOAD if aid == "U_sling_midship" else None,
                        snug_preload_N=T_SNUG, equilibrium_check_failures=bad,
                        elements=env, attachment_points=sorted(pts.values(),
                                                               key=lambda d: -d["max_resultant_N"]),
                        cases={k: dict(dx_mm=round(v["dx_mm"], 1), dyaw_deg=round(v["dyaw_deg"], 3),
                                       resultant_on_boat_N=[round(c, 1) for c in v["resultant_on_boat_N"]],
                                       force_residual_N=round(v["check_force_residual_N"], 4),
                                       moment_residual_Nm=round(v["check_moment_residual_Nm"], 3))
                               for k, v in rows.items()})
    worstF = max((r["check_force_residual_N"] for r in rows.values()), default=0)
    worstM = max((r["check_moment_residual_Nm"] for r in rows.values()), default=0)
    print(f"{aid:24s} {len(env)} elements, {len(pts)} attachment points | "
          f"equilibrium residuals: force {worstF:.3g} N, moment {worstM:.3g} Nm "
          f"{'OK' if not bad else 'FAILED - do not use these numbers'} ({time.time()-t_start:.0f} s)", flush=True)

doc = dict(label="Exploratory. Loads only - the project holds no frame sections, material or laminate schedule, so "
                 "nothing here verifies a member. Geometry, masses, contact stiffnesses and boat attachment points "
                 "are assumed; see ASSUMPTIONS.md and config missing_inputs.",
           generated="2026-11-08", load_cases=CASES, waves=WAVES, arrangements=results,
           seconds=round(time.time() - t_start, 1))
(OUT / "connection_loads.json").write_text(json.dumps(doc, indent=1, default=str))
print(f"\nwritten {OUT/'connection_loads.json'}")
