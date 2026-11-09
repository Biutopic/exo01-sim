"""Which coupling arrangement is actually best? A search over arrangements, not a comparison of two.

    python scripts/run_arrangement_search.py [--quick] [--cands A_vee_pulley,F_six_rope]

Every candidate goes through the same gauntlet, with the same solver, load cases and waves as the final-coupling study
(scripts/run_final_coupling.py) and the mooring study, so the numbers are comparable with both:

  1. the nine static load cases, built from the configuration's own thrust data - hard gate, all must close
  2. the smallest per-element preload at which they all close
  3. the three Erdre reference waves, linear: engagement (nothing goes slack or opens), peak load, boat roll, transom gap
  4. the smallest preload at which all three waves stay engaged
  5. redundancy: lose any ONE tension element, re-run the worst static case, count the losses that leave no equilibrium
  6. geometry: closest approach of every rope to the hull envelope (negative = it lies on the gunwale)
  7. operations: how many tensioning actions to couple, and whether it needs boat fittings that do not exist

Time-domain peaks are deliberately absent: scripts/run_coupling_waves.py showed they do not converge in these
configurations (11.0-15.7 kN over 64-1024 steps per period). Engagement is the criterion that is well posed.
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

from exo01 import arrangements as AR  # noqa: E402
from exo01.analysis import evaluate, hydro_for, build_response, HYDRO_DEFAULTS  # noqa: E402

OUT = ROOT / "results" / "coupling"
QUICK = "--quick" in sys.argv
ONLY = None
OUTNAME = "arrangement_search.json"
for a in sys.argv:
    if a.startswith("--cands"):
        ONLY = set(a.split("=", 1)[1].split(",")) if "=" in a else None
    if a.startswith("--out="):
        OUTNAME = a.split("=", 1)[1]

# reuse the final-coupling study's geometry, element builder, solver, thrust-derived load cases
src = (ROOT / "scripts" / "run_final_coupling.py").read_text()
head = src.split("# ──────────────────────────────────────────────────────────────── A · preload sweep")[0]
NS = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "search"}
exec(compile(head, "head", "exec"), NS)
elements, cfg_for, solve, CASES, D = NS["elements"], NS["cfg_for"], NS["solve"], NS["CASES"], NS["D"]
K_ROPE, K_BUMP, K_WHEEL, BASE = NS["K_ROPE"], NS["K_BUMP"], NS["K_WHEEL"], NS["BASE"]
X_BERTH, X_VEE, Y_VEE, Z_VEE = NS["X_BERTH"], NS["X_VEE"], NS["Y_VEE"], NS["Z_VEE"]
X_BOW_BOAT, Z_BOW_BOAT = NS["X_BOW_BOAT"], NS["Z_BOW_BOAT"]
ill = NS["ill"]

KR = K_ROPE["mid"]
WAVES = [dict(id="beam_03_25", H_m=0.3, T_s=2.5, heading_deg=90),
         dict(id="head_03_25", H_m=0.3, T_s=2.5, heading_deg=180),
         dict(id="beam_05_30", H_m=0.5, T_s=3.0, heading_deg=90)]
DAMP = {"EXO": {"zeta": {"heave": 0.05, "roll": 0.05, "pitch": 0.05}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}},
        "BOAT": {"zeta": {"heave": 0.05, "roll": 0.10, "pitch": 0.10}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}}}
SET = dict(HYDRO_DEFAULTS)
OM = np.round(np.arange(SET["omega_min"], SET["omega_max"] + 1e-9, SET["omega_step"]), 10)

# ──────────────────────────────────────────────────── attachment points that already exist on the boat
# boat frame: x from the transom towards the bow, y to port, z on the catalogue waterline
STERN_CLEAT = (0.30, 1.30, 0.80)
MID_CLEAT = (4.30, 1.35, 0.80)
BOW_STEM = (X_BOW_BOAT, 0.0, Z_BOW_BOAT)
TRANSOM_QTR = (0.25, 0.90, 0.40)          # a tube here needs a bracket: NOT an existing fitting
# EXO frame
AFT_POST = (0.05, 2.25, 0.30)
MID_POST = (2.10, 2.25, 0.30)
FWD_POST = (4.95, 2.25, 0.30)
VEE_ANCHOR = (X_VEE, Y_VEE, Z_VEE)


T_SNUG = 150.0   # N: a secondary rope "rigged snug" by hand, not winched. ASSUMED.


def pair(id_, exo, boat, kind="line", k=KR, t0=0.0, **kw):
    """Symmetric pair, port and starboard."""
    return [dict(id=f"{id_}_{nm}", kind=kind, exo_point_m=[exo[0], s * exo[1], exo[2]],
                 boat_point_m=[boat[0], s * boat[1], boat[2]], stiffness_N_per_m=k, pretension_N=t0, **kw)
            for s, nm in ((+1, "PORT"), (-1, "STBD"))]


def crossed(id_, exo, boat, k=KR, t0=0.0):
    """Symmetric pair that crosses the centreline: port EXO point to starboard boat point and back."""
    return [dict(id=f"{id_}_P2S", kind="line", exo_point_m=[exo[0], exo[1], exo[2]],
                 boat_point_m=[boat[0], -boat[1], boat[2]], stiffness_N_per_m=k, pretension_N=t0),
            dict(id=f"{id_}_S2P", kind="line", exo_point_m=[exo[0], -exo[1], exo[2]],
                 boat_point_m=[boat[0], boat[1], boat[2]], stiffness_N_per_m=k, pretension_N=t0)]


def vee_pulley(t0):
    return [dict(id="VEE_ROPE", kind="bridle", exo_point_m=[X_VEE, Y_VEE, Z_VEE], exo_point_b_m=[X_VEE, -Y_VEE, Z_VEE],
                 boat_point_m=list(BOW_STEM), stiffness_N_per_m=KR, pretension_N=t0)]


def vee_legs(t0):
    """Two independent legs to the stem. A leg is half the path, so twice the path stiffness."""
    return pair("LEG", VEE_ANCHOR, BOW_STEM, k=2 * KR, t0=t0)


def rear(kb="mid"):
    return [e for e in elements(0.0, kb=kb) if e["id"].startswith("BUMPER")]


def wheels(kw="mid"):
    return [e for e in elements(0.0, kw=kw) if e["id"].startswith("WHEEL")]


def tubes(k):
    """Pinned tube, EXO rear crossmember quarters to the transom quarters, elastomer cartridge in series."""
    return pair("TUBE", (2.10, 0.90, 0.25), TRANSOM_QTR, kind="strut", k=k, t0=0.0)


# ── the sandwich sling ─────────────────────────────────────────────────────────────────────────────────────────
# Datums: elements() levels EXO z 0.25 with boat z 0.40, so boat_z = exo_z + 0.15.
Z_DATUM_OFF = 0.15
DRAFT_PROXY = 0.381        # m, boat frame, from the coupled equilibrium. The proxy EXCLUDES the keel, so the real
                           # strap would bear on the keel, not the flat bottom - which is also the only fore-and-aft
                           # feature it could locate against. Unknown geometry; not modelled.
Y_THREAD = 1.67            # EXO float inner face: the strap threads the 180 mm float-to-hull gap
Z_SLING_TOP = 0.30         # EXO frame attachment
K_SLING = 40_100.0         # N/m: EA 150 kN (same webbing modulus as the 12 mm rope) over the 3.74 m sling path


def sling(id_, x_boat, t0):
    """One strap under the hull at boat station x_boat. Vertical force on the boat = 0.89 x T upward; surge = 0."""
    return [dict(id=id_, kind="bridle",
                 exo_point_m=[x_boat + X_BERTH, Y_THREAD, Z_SLING_TOP],
                 exo_point_b_m=[x_boat + X_BERTH, -Y_THREAD, Z_SLING_TOP],
                 boat_point_m=[x_boat, 0.0, -DRAFT_PROXY],
                 stiffness_N_per_m=K_SLING, pretension_N=t0)]


def ANS_vee_legs_saddle(t0):
    """Two fixed legs to a broad saddle on the stem. The saddle BEARS on the hull - it is not a fitting - so this
    satisfies 'zero modification'. Section 12 measured 0.41 bar under a 120 x 400 mm saddle against 9.9 bar for a
    bare rope. Section 15.3 showed the straight-line path is not riggable and the real legs must be led along the
    ~160 mm side deck, which changes the half-angle; that penalty is NOT modelled here."""
    return vee_legs(t0)


def slings(t0, stations=(0.80, 2.50)):
    return [e for i, x in enumerate(stations) for e in sling(f"SLING_{i+1}", x, t0)]


# ──────────────────────────────────────────────────── the candidates
# ops  = tensioning actions to couple (a winch on a pulley bridle equalises both legs in one pull)
# fits = boat fittings the arrangement needs that are NOT already there
CANDS = {}


def C(id_, title, f, ops, fits="", primary=()):
    """f(t_primary, t_snug) -> element list. `primary` names the ids carrying the swept preload, for the record."""
    CANDS[id_] = dict(title=title, build=f, ops=ops, fits=fits, primary=list(primary))

C("A_vee_pulley", "The brief's configuration: bow-pulley V + 2 rear bumpers + 2 dockwheels",
  lambda t, g: vee_pulley(t) + rear() + wheels(), 1, primary=("VEE_ROPE",))
C("B_vee_legs", "Same, two fixed legs to the stem instead of the pulley (§13)",
  lambda t, g: vee_legs(t) + rear() + wheels(), 2, primary=("LEG",))
C("C_vee_legs_crossed", "Fixed legs + 2 crossed stern ropes (the hybrid)",
  lambda t, g: vee_legs(t) + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g) + rear() + wheels(), 4,
  primary=("LEG",))
C("D_vee_pulley_crossed", "Bow-pulley V + 2 crossed stern ropes",
  lambda t, g: vee_pulley(t) + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g) + rear() + wheels(), 3,
  primary=("VEE_ROPE",))
C("E_vee_pulley_breasts", "Bow-pulley V + 2 straight stern breast ropes",
  lambda t, g: vee_pulley(t) + pair("BREAST", AFT_POST, STERN_CLEAT, t0=g) + rear() + wheels(), 3,
  primary=("VEE_ROPE",))
C("F_six_rope", "The 30 Oct winner: 2 bumpers + aft->midship + fwd->stern + crossed (no wheels, as run then)",
  lambda t, g: pair("AFT2MID", AFT_POST, MID_CLEAT, t0=t) + pair("FWD2STERN", FWD_POST, STERN_CLEAT, t0=g)
  + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g) + rear(), 6, primary=("AFT2MID",))
C("G_six_rope_wheels", "The same six ropes, with the dockwheels added",
  lambda t, g: pair("AFT2MID", AFT_POST, MID_CLEAT, t0=t) + pair("FWD2STERN", FWD_POST, STERN_CLEAT, t0=g)
  + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g) + rear() + wheels(), 6, primary=("AFT2MID",))
C("H_fwd_midship", "No bow rope at all: forward springs to the midship cleats + bumpers + wheels",
  lambda t, g: pair("SPRING", FWD_POST, MID_CLEAT, t0=t) + rear() + wheels(), 2, primary=("SPRING",))
C("I_fwd_midship_crossed", "Forward springs to midship + 2 crossed stern ropes",
  lambda t, g: pair("SPRING", FWD_POST, MID_CLEAT, t0=t) + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g)
  + rear() + wheels(), 4, primary=("SPRING",))
C("J_vee_pulley_midship", "Bow-pulley V + 2 springs to the midship cleats (belt and braces forward)",
  lambda t, g: vee_pulley(t) + pair("SPRING", FWD_POST, MID_CLEAT, t0=g) + rear() + wheels(), 3,
  primary=("VEE_ROPE",))
C("K_tubes_aft_vee", "2 aft tubes with elastomer cartridges + bow-pulley V + wheels",
  lambda t, g: vee_pulley(t) + tubes(1.0e5) + wheels(), 1, "transom-quarter tube brackets",
  primary=("VEE_ROPE",))
C("L_tubes_four", "Four bilateral tubes, cartridges (the old rank 1, re-scored)",
  lambda t, g: tubes(1.0e5) + pair("TUBE_F", FWD_POST, MID_CLEAT, kind="strut", k=1.0e5), 0,
  "transom-quarter + midship tube brackets")
C("M_vee_pulley_no_wheels", "The brief's configuration without the dockwheels (what do they buy?)",
  lambda t, g: vee_pulley(t) + rear(), 1, primary=("VEE_ROPE",))
C("N_diagonals", "2 bumpers + the two best diagonals only (4 elements) + wheels",
  lambda t, g: pair("AFT2MID", AFT_POST, MID_CLEAT, t0=t) + pair("FWD2STERN", FWD_POST, STERN_CLEAT, t0=g)
  + rear() + wheels(), 4, primary=("AFT2MID",))

C("O_aft_breasts", "No bow rope at all: 2 aft breast ropes (EXO aft posts -> stern cleats) + bumpers + wheels",
  lambda t, g: pair("BREAST", AFT_POST, STERN_CLEAT, t0=t) + rear() + wheels(), 2, primary=("BREAST",))
C("P_aft_breasts_crossed", "Aft breasts + 2 crossed stern ropes (yaw)",
  lambda t, g: pair("BREAST", AFT_POST, STERN_CLEAT, t0=t) + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g)
  + rear() + wheels(), 4, primary=("BREAST",))
C("Q_aft_breasts_midship", "Aft breasts + 2 midship springs - every element short enough for a 3 m strap",
  lambda t, g: pair("BREAST", AFT_POST, STERN_CLEAT, t0=t) + pair("SPRING", FWD_POST, MID_CLEAT, t0=g)
  + rear() + wheels(), 4, primary=("BREAST",))

C("R_sling_bumpers", "Sandwich: 2 under-hull slings + bumpers + wheels, no forward tension element",
  lambda t, g: slings(t) + rear() + wheels(), 2, primary=("SLING",))
C("S_sling_midship", "Sandwich slings + 2 midship springs (the section 15 forward element) + bumpers + wheels",
  lambda t, g: slings(t) + pair("SPRING", FWD_POST, MID_CLEAT, t0=g) + rear() + wheels(), 4,
  primary=("SLING",))
C("T_sling_crossed", "Sandwich slings + 2 crossed stern ropes + bumpers + wheels",
  lambda t, g: slings(t) + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g) + rear() + wheels(), 4,
  primary=("SLING",))
C("U_sling_midship_primary", "Sandwich slings snug + 2 midship springs carrying the preload",
  lambda t, g: slings(g) + pair("SPRING", FWD_POST, MID_CLEAT, t0=t) + rear() + wheels(), 4,
  primary=("SPRING",))

C("V_spec_zero_fittings", "Zero boat fittings: 2 under-hull slings + 2 fixed bow legs on a stem saddle + bumpers "
                          "+ wheels. Everything bears on the hull; nothing attaches to it.",
  lambda t, g: ANS_vee_legs_saddle(t) + slings(g) + rear() + wheels(), 3,
  primary=("LEG",))
C("W_spec_sling_only", "Zero boat fittings, no bow rope: slings + bumpers + wheels only",
  lambda t, g: slings(t) + rear() + wheels(), 2, primary=("SLING",))

C("X_yoke_midship_crossed", "Arrangement I with the two midship springs replaced by ONE equalised rope: a winch "
                              "on the frame rail, turning blocks at the forward posts, one tension in both legs",
  lambda t, g: (AR.yoke("YOKE", FWD_POST, MID_CLEAT, t0=t)
                + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g) + rear() + wheels()), 1, primary=("YOKE",))

# Arrangement I with a shock absorber in series with the CROSSED STERN ROPES. Section 19 measured an absorber on
# the primary pair and it cost preload, because that pair carries the yaw case by being unequal. The crossed ropes
# carry no differential job and ARE wave-governed (amplification 4,2-4,5 against <=1,1 for everything else), so
# this is the place the idea should pay if it pays anywhere. k_eff = 1/(1/k_rope + 1/k_shock).
for _ks in (27000.0, 13500.0, 5000.0, 2000.0, 800.0):
    _ke = 1.0 / (1.0 / KR + 1.0 / _ks)
    C(f"I_shock_cross_{int(_ks)}",
      f"Arrangement I with a {_ks:.0f} N/m shock absorber in series with the crossed stern ropes "
      f"(k_eff {_ke:.0f} N/m)",
      lambda t, g, _k=_ke: (pair("SPRING", FWD_POST, MID_CLEAT, t0=t)
                            + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g, k=_k) + rear() + wheels()),
      4, primary=("SPRING",))

C("Y_full_rove", "ONE continuous rope through blocks: all four of arrangement I's legs on a single tension",
  lambda t, g: AR.build("Y_full_rove", preload_N=t, snug_N=g), 1, primary=("ROVE",))

if ONLY:
    CANDS = {k: v for k, v in CANDS.items() if k in ONLY}

# ──────────────────────────────────────────────────── hull envelope, for the rope-vs-gunwale check
_ST = np.array(ill["host_boat"]["buoyant_surface"]["stations_mm"], float) / 1000.0
HULL_X, HULL_Y = _ST[:, 0], _ST[:, 1]
TOPSIDE = float(ill["host_boat"]["buoyant_surface"]["topside_top_mm"]) / 1000.0


def half_beam(xb):
    """Hull half-beam at boat station xb; 0 outside the hull."""
    if xb < HULL_X[0] or xb > HULL_X[-1]:
        return 0.0
    return float(np.interp(xb, HULL_X, HULL_Y))


_CAB = np.array(ill["host_boat"]["clearance_reference"]["boat_cabin_stations_mm"], float) / 1000.0
CAB_X, CAB_Y, CAB_Z = _CAB[:, 0], _CAB[:, 1], _CAB[:, 2]


def cabin_at(xb):
    """(half-width, top) of the superstructure at boat station xb; (0, 0) where there is none."""
    if xb < CAB_X[0] or xb > CAB_X[-1]:
        return 0.0, 0.0
    return float(np.interp(xb, CAB_X, CAB_Y)), float(np.interp(xb, CAB_X, CAB_Z))


def rope_hull_clearance(els):
    """Closest approach of every rope to the boat at the NOMINAL berth (rigging geometry, not the solved pose).
    Checks the hull side below the deck edge AND the superstructure above it. Negative = the rope cannot be rigged as
    drawn: its straight path passes through the boat, so it needs a fairlead, a roller or a gallows to lead it."""
    worst, where = None, None
    for e in els:
        if e.get("kind") in ("fender", "strut"):
            continue
        a = np.array(e["exo_point_m"], float)
        bb = np.array(e["boat_point_m"], float)
        b = np.array([bb[0] + X_BERTH, bb[1], bb[2]])        # boat -> EXO frame
        ends = [(a, b)]
        if e.get("exo_point_b_m") is not None:
            ends.append((np.array(e["exo_point_b_m"], float), b))
        for p0, p1 in ends:
            for t in np.linspace(0.0, 1.0, 401):
                p = p0 + t * (p1 - p0)
                xb = p[0] - X_BERTH
                cw, ct = cabin_at(xb)
                if p[2] < TOPSIDE:                            # below the deck edge: the hull side is the obstruction
                    hb = half_beam(xb)
                    obst, what = (hb, "hull") if hb > 0.0 else (None, None)
                elif cw > 0.0 and p[2] < ct:                  # above the deck edge, alongside the superstructure
                    obst, what = cw, "cabin"
                else:
                    obst, what = None, None                   # over the open deck or clear above everything
                if obst is None:
                    continue
                c = abs(p[1]) - obst
                if worst is None or c < worst:
                    lies_on = ("deck edge (chafe, leadable)" if what == "hull" and p[2] < TOPSIDE
                               else "superstructure (not leadable)")
                    side_deck = round(float(half_beam(xb) - cabin_at(xb)[0]), 3) if cabin_at(xb)[0] > 0 else None
                    worst, where = float(c), dict(element=e["id"], obstruction=what,
                                                  boat_station_m=round(float(xb), 3),
                                                  z_m=round(float(p[2]), 3), half_width_m=round(obst, 3),
                                                  would_lie_on=lies_on, side_deck_width_m=side_deck)
    return worst, where


# ──────────────────────────────────────────────────── the gauntlet
BUMP_MIN_N = 50.0   # N per rear bumper: the compression below which the contact is "open" and rattling


def statics(els_fn, t0):
    """All nine load cases. Gate: converged, physical, restrained, AND both rear bumpers still loaded - the bumpers
    are the forward-thrust load path, so an arrangement that lets one open has not passed (COUPLING.md section 5)."""
    els = els_fn(t0, T_SNUG)
    has_bump = any(e["id"].startswith("BUMPER") for e in els)
    out, ok = {}, True
    for c in CASES:
        r = solve(els, surge_N=c["surge"], yaw_Nm=c["yaw"])
        bump_ok = (not has_bump) or (r["bumper_min_N"] is not None and r["bumper_min_N"] >= BUMP_MIN_N)
        good = bool(r["converged"] and r["physical"] and not r["unrestrained"] and bump_ok)
        tens = [v["T_N"] for v in r["elements"].values() if v["kind"] in ("line", "bridle", "yoke")]
        out[c["id"]] = dict(ok=good, bumpers_loaded=bool(bump_ok),
                            bumper_min_N=None if r["bumper_min_N"] is None else round(r["bumper_min_N"], 1),
                            dx_mm=round(r["dx_mm"], 1), dyaw_deg=round(r["dyaw_deg"], 3),
                            max_tension_N=round(max(tens), 1) if tens else None,
                            bumper_total_N=round(r["bumper_total_N"], 1), wheel_max_N=round(r["wheel_max_N"], 1),
                            transom_to_deck_m=r["transom_to_deck_m"], unrestrained=r["unrestrained"])
        ok = ok and good
    return ok, out


def min_preload_static(els_fn, hi=8000.0):
    """Smallest per-element preload at which all nine static cases close."""
    if statics(els_fn, 1.0)[0]:
        return 1.0
    if not statics(els_fn, hi)[0]:
        return None
    lo = 1.0
    for _ in range(14):
        mid = 0.5 * (lo + hi)
        lo, hi = (lo, mid) if statics(els_fn, mid)[0] else (mid, hi)
    return round(hi, 1)


def wave_metrics(els, t0, primary=()):
    """Linear response in the three reference waves. engaged = the PRIMARY load path stays in tension and no contact
    opens. A snug secondary rope going slack in a wave is normal for a backup and is recorded, not failed."""
    cfg = cfg_for(els)
    r = evaluate(cfg)
    ce = r.get("coupled_equilibrium") or {}
    if not ce.get("converged"):
        return dict(error="still-water equilibrium did not converge")
    res = {}
    for w in WAVES:
        try:
            hd = np.array([np.radians(w["heading_deg"])])
            hdd = hydro_for(r, cfg, OM, hd, SET, cache_only=True, allow_pose_reuse=True)
            model = build_response(r, hdd, cfg)
            rw = model.regular_wave(w["H_m"], w["T_s"], hd[0], DAMP, cfg["deck_acceleration_points"])
            el = rw.get("lines") or []
            slack = [l["id"] for l in el if l.get("kind") in ("line", "bridle", "yoke") and l["slack_in_cycle"]]
            prim_slack = [i for i in slack if any(i.startswith(p_) for p_ in primary)] if primary else slack
            opens = [l["id"] for l in el if l.get("kind") == "fender" and l["slack_in_cycle"]]
            rel = rw.get("relative_motion") or {}
            tg = [v for k_, v in rel.items() if k_.startswith("transom_vs_deck_edge")]
            res[w["id"]] = dict(engaged=not prim_slack and not opens, primary_slack=prim_slack,
                                secondary_slack=[i for i in slack if i not in prim_slack], opens=opens,
                                peak_N=max((l["max_N"] for l in el if l.get("kind") in ("line", "bridle", "yoke")), default=None),
                                boat_roll_deg=round(rw["bodies"]["BOAT"]["amplitude_deg"]["roll"], 2),
                                transom_gap_min_m=min((v["min_clearance_m"] for v in tg
                                                       if v["min_clearance_m"] is not None), default=None),
                                pose_reuse=hdd.meta.get("pose_reuse"))
        except Exception as e:  # noqa: BLE001
            res[w["id"]] = dict(error=f"{type(e).__name__}: {e}")
    return res


LADDER = [1.0, 200.0, 400.0, 600.0, 800.0, 1000.0, 1300.0, 1600.0, 2000.0, 2500.0,
          3000.0, 4000.0, 5000.0, 6500.0, 8000.0, 10000.0, 12000.0]


def min_preload_waves(els_fn, primary=()):
    """Lowest preload on the ladder at which all three waves engage. A ladder, not a bisection: engagement is NOT
    monotone in preload (section 14 found engaged at 900 N, slack at 1100 N, engaged at 1300 N), so a bisection
    both misses the true threshold and reports None for an arrangement that simply fails at the top of the bracket."""
    for t in LADDER:
        m = wave_metrics(els_fn(t, T_SNUG), t, primary)
        if "error" in m or any("error" in v for v in m.values()):
            continue
        if all(v.get("engaged") for v in m.values()):
            return round(t, 1)
    return None


def redundancy(els_fn, t0):
    """Lose any ONE tension element: how many single losses leave no static equilibrium in the worst case?"""
    els = els_fn(t0, T_SNUG)
    ids = [e["id"] for e in els if e.get("kind") in ("line", "bridle", "yoke", "yoke", "strut")]
    worst = [c for c in CASES if c["id"] in ("rev100", "diff_opp", "estop")]
    fatal = []
    for drop in ids:
        kept = [e for e in els if e["id"] != drop]
        for c in worst:
            r = solve(kept, surge_N=c["surge"], yaw_Nm=c["yaw"])
            if not (r["converged"] and r["physical"] and not r["unrestrained"]):
                fatal.append(dict(lost=drop, case=c["id"]))
                break
    return dict(n_tension_elements=len(ids), n_single_losses_fatal=len(fatal), fatal=fatal)


rows = []
t0 = time.time()
for i, (cid, c) in enumerate(CANDS.items(), 1):
    row = dict(id=cid, title=c["title"], ops_actions=c["ops"], new_boat_fittings=c["fits"],
               primary_elements=c["primary"])
    f = c["build"]
    row["n_elements"] = len(f(400.0, T_SNUG))
    row["min_preload_static_N"] = min_preload_static(f)
    row["min_preload_waves_N"] = (min_preload_waves(f, tuple(c["primary"]))
                                  if row["min_preload_static_N"] is not None else None)
    # design preload: whichever of the two gates is binding, with a floor so a gateless arrangement still gets a number
    cands_t = [v for v in (row["min_preload_static_N"], row["min_preload_waves_N"]) if v is not None]
    T = max(cands_t) if cands_t else None
    row["design_preload_N"] = T
    if T is not None:
        row["statics_ok"], row["statics"] = statics(f, T)
        bm = [(k, v["bumper_min_N"]) for k, v in row["statics"].items() if v.get("bumper_min_N") is not None]
        row["binding_static_case"] = min(bm, key=lambda kv: kv[1])[0] if bm else None
        row["waves"] = wave_metrics(f(T, T_SNUG), T, tuple(c["primary"]))
        row["redundancy"] = redundancy(f, T)
    cl, where = rope_hull_clearance(f(400.0, T_SNUG))
    row["rope_hull_clearance_m"] = None if cl is None else round(cl, 4)
    row["rope_hull_clearance_at"] = where
    rows.append(row)
    w = row.get("waves") or {}
    pk = max((v["peak_N"] for v in w.values() if isinstance(v, dict) and v.get("peak_N")), default=None)
    rl = max((v["boat_roll_deg"] for v in w.values() if isinstance(v, dict) and v.get("boat_roll_deg")), default=None)
    print(f"[{i}/{len(CANDS)}] {cid:24s} T* {str(T):>8s} N | statics {row.get('statics_ok')} | "
          f"peak {pk} N roll {rl}° | fatal single losses {(row.get('redundancy') or {}).get('n_single_losses_fatal')}"
          f"/{(row.get('redundancy') or {}).get('n_tension_elements')} | hull clr {row['rope_hull_clearance_m']} m "
          f"({time.time()-t0:.0f} s)", flush=True)

res = dict(label="Exploratory - assumed geometry and masses; contact stiffnesses unknown; boat attachment points assumed.",
           method="Nine thrust-derived static load cases, gated on both rear bumpers staying loaded (hard gate) + three Erdre reference waves, linear, engagement "
                  "criterion. Time-domain peaks are omitted on purpose: they do not converge in these configurations "
                  "(see results/coupling/coupling_waves.json).",
           generated="2026-11-03", waves=WAVES, damping=DAMP, k_rope_N_per_m=KR, k_sling_N_per_m=K_SLING, draft_proxy_m=DRAFT_PROXY, snug_preload_N=T_SNUG, bumper_min_N=BUMP_MIN_N, preload_ladder_N=LADDER,
           boat_points=dict(stern_cleat=STERN_CLEAT, midship_cleat=MID_CLEAT, bow_stem=BOW_STEM,
                            transom_quarter=TRANSOM_QTR),
           rows=rows, seconds=time.time() - t0)
(OUT / OUTNAME).write_text(json.dumps(res, indent=1, default=str))
print(f"\nwritten {OUT/OUTNAME} ({time.time()-t0:.0f} s)")
