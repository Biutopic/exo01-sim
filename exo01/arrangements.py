"""Coupling arrangements: the one place that says where every rope, pad and wheel goes.

Before this module the same geometry was written out in `scripts/run_final_coupling.py`,
`scripts/run_arrangement_search.py`, `scripts/run_wind_load_cases.py`, `scripts/run_connection_loads.py` and
`scripts/build_explorer.py`, which is five chances for the numbers to drift apart. Everything now builds from here,
and `tests/test_arrangements.py` asserts the constants still match the study script they came from.

Frames and datums
-----------------
* ``exo_point_m``  is in the EXO frame; ``boat_point_m`` is in the boat frame (x from the transom towards the bow).
* The two vertical datums are levelled: EXO z 0.25 sits at boat z 0.40, so ``boat_z = exo_z + 0.15``.
* The boat is berthed at ``X_BERTH`` in the EXO frame.

Element kinds are the ones ``exo01.twobody`` understands: ``line`` (tension only), ``fender`` (compression only,
along a declared ``axis_m``), ``strut`` (bilateral) and ``bridle`` (one rope, two EXO points, one boat point - which
is also how an under-hull sling is modelled, a frictionless strap being exactly a bridle over a turning point).

Known limits carried from the studies, so nothing here reads as more settled than it is:

* A fender with a declared ``axis_m`` applies a spurious couple (COUPLING.md section 16). Surge-only load cases are
  unaffected; the two differential-thrust cases carry up to 7.6 % error, in the non-conservative direction.
* The straight bow-leg path is not riggable: it passes inside the hull envelope and the real rope must be led along
  the ~160 mm side deck, which changes the half-angle (section 15.3). The legs here are the straight idealisation.
* Every arrangement whose boat end is a cleat conflicts with the cahier des charges rules on host-boat modification
  and 80 % boat compatibility (section 17). ``needs_boat_fittings`` records which ones.
"""
from __future__ import annotations

import numpy as np

# ───────────────────────────────────────────────────────────── geometry (EXO frame unless stated)
X_BERTH = 2.265         # boat origin in the EXO frame
Z_EXO, Z_BOAT = 0.25, 0.40   # levelled contact heights: EXO rear-deck datum / boat catalogue waterline
Z_DATUM_OFFSET = Z_EXO - Z_BOAT   # add to a boat z to get the EXO z: boat 0.40 is level with EXO 0.25

BUMP_PROJ = 0.165       # bumper contact face ahead of the rear crossmember
X_CROSS = 2.10          # EXO rear crossmember
Y_BUMP = 0.90           # bumper half-spacing
X_WHEEL_BOAT = 1.20     # dockwheel station, boat frame
Y_HULL = 1.49           # hull half-beam at the wheels
Y_FLOAT_FACE = 1.67     # EXO float inner face
WHEEL_GAP = 0.030       # free travel before a wheel touches
X_VEE, Y_VEE, Z_VEE = 5.20, 2.25, 0.30      # bow-rope anchors on the EXO frame
X_BOW_BOAT, Z_BOW_BOAT = 8.00, 0.78         # stemhead, boat frame

AFT_POST = (0.05, 2.25, 0.30)
MID_POST = (2.10, 2.25, 0.30)
FWD_POST = (4.95, 2.25, 0.30)
VEE_ANCHOR = (X_VEE, Y_VEE, Z_VEE)

STERN_CLEAT = (0.30, 1.30, 0.80)            # boat frame; existing fittings, ratings UNKNOWN
MID_CLEAT = (4.30, 1.35, 0.80)
BOW_STEM = (X_BOW_BOAT, 0.0, Z_BOW_BOAT)    # hull bearing surface, not a fitting
TRANSOM_QTR = (0.25, 0.90, 0.40)            # a tube here needs a bracket: NOT an existing fitting

DRAFT_PROXY = 0.381     # boat frame; the proxy hull EXCLUDES the keel
Y_THREAD = Y_FLOAT_FACE  # a sling threads the float-to-hull gap
Z_SLING_TOP = 0.30
SLING_STATIONS = (0.80, 2.50)               # boat frame; both are AFT of the boat COM at 3.60 m

K_ROPE = {"soft": 7000.0, "mid": 13500.0, "stiff": 27000.0}
K_BUMP = {"soft": 20000.0, "mid": 50000.0, "stiff": 120000.0}
K_WHEEL = {"soft": 50000.0, "mid": 200000.0, "stiff": 500000.0}
K_SLING = 40_100.0      # EA 150 kN over the 3.74 m sling path
K_TUBE = 1.0e5          # elastomer cartridge in series with a pinned tube
T_SNUG = 150.0          # a secondary rope rigged snug by hand, not winched. ASSUMED.

STIFFNESS_NOTE = ("All three contact stiffnesses are UNMEASURED. They spread the quasi-static answer by a factor of "
                  "3, although rope tension pins the rear compression exactly (COUPLING.md section 7).")


# ───────────────────────────────────────────────────────────── element builders
def pair(id_, exo, boat, kind="line", k=None, t0=0.0, **kw):
    """Port/starboard pair, mirrored in y."""
    k = K_ROPE["mid"] if k is None else k
    return [dict(id=f"{id_}_{nm}", kind=kind,
                 exo_point_m=[exo[0], s * exo[1], exo[2]],
                 boat_point_m=[boat[0], s * boat[1], boat[2]],
                 stiffness_N_per_m=k, pretension_N=t0, **kw)
            for s, nm in ((+1, "PORT"), (-1, "STBD"))]


def crossed(id_, exo, boat, k=None, t0=0.0):
    """Pair crossing the centreline. Lies across the aft deck by geometry - chafe protection, not a blocker."""
    k = K_ROPE["mid"] if k is None else k
    return [dict(id=f"{id_}_P2S", kind="line", exo_point_m=list(exo),
                 boat_point_m=[boat[0], -boat[1], boat[2]], stiffness_N_per_m=k, pretension_N=t0),
            dict(id=f"{id_}_S2P", kind="line", exo_point_m=[exo[0], -exo[1], exo[2]],
                 boat_point_m=list(boat), stiffness_N_per_m=k, pretension_N=t0)]


def yoke(id_, exo, boat, k=None, t0=0.0):
    """ONE rope making a mirrored pair, equalised by turning blocks at the posts and a winch on the rail between
    them. Mechanically the pair of `pair()`, minus their differential stiffness: a single tension in both legs.
    Path length is the sum of the two legs; the rail run between the blocks is fixed and folds into L0."""
    k = K_ROPE["mid"] if k is None else k
    return [dict(id=id_, kind="yoke",
                 exo_point_m=[exo[0], +exo[1], exo[2]], boat_point_m=[boat[0], +boat[1], boat[2]],
                 exo_point_b_m=[exo[0], -exo[1], exo[2]], boat_point_b_m=[boat[0], -boat[1], boat[2]],
                 stiffness_N_per_m=k, pretension_N=t0)]


def vee_pulley(t0, k=None):
    """One continuous rope from both EXO anchors over a pulley at the stem: the pulley equalises the tension."""
    k = K_ROPE["mid"] if k is None else k
    return [dict(id="VEE_ROPE", kind="bridle", exo_point_m=[X_VEE, Y_VEE, Z_VEE],
                 exo_point_b_m=[X_VEE, -Y_VEE, Z_VEE], boat_point_m=list(BOW_STEM),
                 stiffness_N_per_m=k, pretension_N=t0)]


def vee_legs(t0, k=None):
    """Two independent legs to the stem. A leg is half the path, hence twice the path stiffness. Restrains yaw six
    times better than the free pulley at the same peak tension (section 13.2)."""
    k = K_ROPE["mid"] if k is None else k
    return pair("LEG", VEE_ANCHOR, BOW_STEM, k=2 * k, t0=t0)


def sling(id_, x_boat, t0, k=K_SLING):
    """One strap under the hull: down the float-to-hull gap, under the boat, up the other side.

    Carries 0.89 x T vertically and EXACTLY ZERO in surge - a transverse wrap has a surge direction cosine of zero,
    and a frictionless strap over a smooth hull can only transmit force normal to the surface. It therefore always
    needs a separate surge element. Needs no boat fittings at all, which is its whole attraction (section 17).
    """
    return [dict(id=id_, kind="bridle",
                 exo_point_m=[x_boat + X_BERTH, Y_THREAD, Z_SLING_TOP],
                 exo_point_b_m=[x_boat + X_BERTH, -Y_THREAD, Z_SLING_TOP],
                 boat_point_m=[x_boat, 0.0, -DRAFT_PROXY],
                 stiffness_N_per_m=k, pretension_N=t0)]


def slings(t0, stations=SLING_STATIONS):
    return [e for i, x in enumerate(stations) for e in sling(f"SLING_{i + 1}", x, t0)]


def bumpers(kb="mid"):
    """Two rear foam bumpers, acting fore-and-aft. The forward-thrust load path."""
    return [dict(id=f"BUMPER_{nm}", kind="fender",
                 exo_point_m=[X_CROSS, s * Y_BUMP, Z_EXO], boat_point_m=[0.0, s * Y_BUMP, Z_BOAT],
                 axis_m=[1.0, 0.0, 0.0], stiffness_N_per_m=K_BUMP[kb], pretension_N=0.0)
            for s, nm in ((+1, "PORT"), (-1, "STBD"))]


def wheels(kw="mid", gap=WHEEL_GAP):
    """Two lateral dockwheels. They carry 0 N in every static case of the recommended arrangement: a physical stop
    and insurance, not a load path, and the gap is not a dimension needing precision (section 15.4)."""
    return [dict(id=f"WHEEL_{nm}", kind="fender",
                 exo_point_m=[X_WHEEL_BOAT + X_BERTH, s * (Y_HULL + gap), Z_EXO],
                 boat_point_m=[X_WHEEL_BOAT, s * Y_HULL, Z_BOAT],
                 axis_m=[0.0, -s, 0.0], gap_m=gap,
                 stiffness_N_per_m=K_WHEEL[kw], pretension_N=0.0)
            for s, nm in ((+1, "PORT"), (-1, "STBD"))]


def tubes(k=K_TUBE):
    """Pinned tubes, EXO rear crossmember quarters to the transom quarters. Needs brackets on the boat."""
    return pair("TUBE", (X_CROSS, Y_BUMP, Z_EXO), TRANSOM_QTR, kind="strut", k=k, t0=0.0)


# ───────────────────────────────────────────────────────────── the registry
def _A(build, title, *, preload, ops, primary=(), fittings=None, note=""):
    return dict(build=build, title=title, design_preload_N=preload, ops_actions=ops,
                primary=tuple(primary), needs_boat_fittings=fittings, note=note)


ARRANGEMENTS = {
    "A_vee_pulley": _A(
        lambda t, g: vee_pulley(t) + bumpers() + wheels(),
        "The brief's configuration: bow-pulley V + 2 rear bumpers + 2 dockwheels",
        preload=2217.5, ops=1, primary=("VEE_ROPE",), fittings=None,
        note="Second-to-last of seventeen (section 15.2). One rope path, so the loss of any single element leaves no "
             "equilibrium in reverse. Sway is near-unrestrained: it fails 4 of 16 wind cases on demands of a few "
             "tens of newtons."),
    "C_vee_legs_crossed": _A(
        lambda t, g: vee_legs(t) + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g) + bumpers() + wheels(),
        "Smallest correction to the brief: fixed bow legs + 2 crossed stern ropes",
        preload=600.0, ops=4, primary=("LEG",), fittings="stern cleats",
        note="Two ropes and no new fittings take the brief's layout from 2218 N / 1586 N / no redundancy to "
             "600 N / 708 N / full redundancy."),
    "I_fwd_midship_crossed": _A(
        lambda t, g: (pair("SPRING", FWD_POST, MID_CLEAT, t0=t)
                      + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g) + bumpers() + wheels()),
        "Recommended on mechanics (section 15): 2 midship springs + 2 crossed stern ropes",
        preload=600.0, ops=4, primary=("SPRING",), fittings="midship and stern cleats",
        note="Best of seventeen: 600 N preload, 647 N peak, full redundancy, holds all 16 wind cases. Conflicts with "
             "the cahier des charges under a broad reading of 'the boat carries nothing' (section 17)."),
    "X_yoke_midship_crossed": _A(
        lambda t, g: (yoke("YOKE", FWD_POST, MID_CLEAT, t0=t)
                      + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g) + bumpers() + wheels()),
        "MEASURED NEGATIVE RESULT (section 19): arrangement I with the midship springs equalised into one rope",
        preload=2150.0, ops=1, primary=("YOKE",), fittings="midship and stern cleats",
        note="Kept as evidence, not as an option. One winch and one tensioning action instead of four, at 3,5x the "
             "preload (2120 N) and 6,3x the peak load (4080 N), with a single point of failure and contact lost in "
             "a 0,3 m beam wave. A symmetric equalised pair has provably ZERO yaw capacity, and the binding case "
             "diff_opp is pure yaw: the springs' job is to be unequal. Also needs a powered winch, which arrangement "
             "I does not. Section 19 has the mechanism."),
    "U_sling_midship": _A(
        lambda t, g: (slings(g) + pair("SPRING", FWD_POST, MID_CLEAT, t0=t) + bumpers() + wheels()),
        "Under-hull slings (snug) + 2 midship springs carrying the preload",
        preload=2000.0, ops=4, primary=("SPRING",), fittings="midship cleats",
        note="The slings halve the roll transmitted to the boat but cost a factor of 6 in peak rope load. Preloading "
             "them is a bad trade: +63 % peak load to buy 0.8 deg of roll (sling_preload.json)."),
    "V_spec_zero_fittings": _A(
        lambda t, g: vee_legs(t) + slings(g) + bumpers() + wheels(),
        "Zero boat fittings: 2 under-hull slings + 2 bow legs on a stem saddle + bumpers + wheels",
        preload=2000.0, ops=3, primary=("LEG",), fittings=None,
        note="The only arrangement tested that satisfies the cahier des charges in full: everything bears on the "
             "hull, nothing attaches to it, so it can target 80 % of boats. Costs a factor of 6 in peak rope load "
             "and half the redundancy against arrangement I, and buys a factor of 3 in roll."),
    "W_spec_sling_only": _A(
        lambda t, g: slings(t) + bumpers() + wheels(),
        "Slings + bumpers + wheels only, no surge element",
        preload=2000.0, ops=2, primary=("SLING",), fittings=None,
        note="FAILS the static gate, as the geometry predicts: a transverse sling has a surge direction cosine of "
             "exactly zero, so nothing restrains reverse. Kept as the negative control."),
    "O_aft_breasts": _A(
        lambda t, g: pair("BREAST", AFT_POST, STERN_CLEAT, t0=t) + bumpers() + wheels(),
        "2 aft breast ropes to the stern cleats + bumpers + wheels",
        preload=600.0, ops=2, primary=("BREAST",), fittings="stern cleats",
        note="Excellent in surge (0.92 direction cosine in half the bow leg's length, clean geometry) and useless "
             "in yaw: unrestrained under diff_opp. Half an arrangement."),
    "G_six_rope_wheels": _A(
        lambda t, g: (pair("AFT2MID", AFT_POST, MID_CLEAT, t0=t)
                      + pair("FWD2STERN", FWD_POST, STERN_CLEAT, t0=g)
                      + crossed("CROSS", MID_POST, STERN_CLEAT, t0=g) + bumpers() + wheels()),
        "The 30 Oct six-rope arrangement, with the dockwheels added",
        preload=981.0, ops=6, primary=("AFT2MID",), fittings="midship and stern cleats",
        note="Full redundancy over six elements, but six tensioning actions to couple."),
    "K_tubes_aft_vee": _A(
        lambda t, g: vee_pulley(t) + tubes() + wheels(),
        "2 aft tubes with elastomer cartridges + bow-pulley V + wheels",
        preload=400.0, ops=1, primary=("VEE_ROPE",), fittings="transom-quarter tube brackets",
        note="Lowest loads of any arrangement, but the brackets are a permanent modification."),
}


DEFAULT = "I_fwd_midship_crossed"
"""The selected arrangement (decision of 9 Nov 2026, docs/COUPLING.md section 18).

Chosen on mechanics for a FIXED ROUTE with a KNOWN HOST BOAT. It is the best of seventeen on every mechanical
measure, and it knowingly departs from the cahier des charges rule against loading the host boat's fittings. That
departure is scoped, not waived: the moment a second host boat or the 80 % compatibility target becomes binding,
V_spec_zero_fittings is the arrangement to return to, at a factor of 6 in peak rope load.
"""


def build(arrangement_id=None, preload_N=None, snug_N=T_SNUG):
    """Element list for a named arrangement."""
    a = ARRANGEMENTS[arrangement_id or DEFAULT]
    t = a["design_preload_N"] if preload_N is None else float(preload_N)
    return a["build"](t, float(snug_N))


def catalogue():
    """Everything the interface needs to offer a choice, without the callables."""
    return {k: {kk: vv for kk, vv in v.items() if kk != "build"} | {"n_elements": len(build(k))}
            for k, v in ARRANGEMENTS.items()}


def element_geometry(arrangement_id=None, preload_N=None, snug_N=T_SNUG):
    """Element endpoints in a single frame (the EXO frame), ready for drawing."""
    out = []
    arrangement_id = arrangement_id or DEFAULT
    for e in build(arrangement_id, preload_N, snug_N):
        b = np.asarray(e["boat_point_m"], float) + np.array([X_BERTH, 0.0, Z_DATUM_OFFSET])
        rec = dict(id=e["id"], kind=e.get("kind", "line"),
                   a=list(np.asarray(e["exo_point_m"], float)), b=b.tolist(),
                   stiffness_N_per_m=e.get("stiffness_N_per_m"), pretension_N=e.get("pretension_N"))
        if e.get("exo_point_b_m") is not None:
            rec["a2"] = list(np.asarray(e["exo_point_b_m"], float))
        if e.get("boat_point_b_m") is not None:
            rec["b2"] = (np.asarray(e["boat_point_b_m"], float)
                         + np.array([X_BERTH, 0.0, Z_DATUM_OFFSET])).tolist()
        rec["length_m"] = float(np.linalg.norm(b - np.asarray(rec["a"], float)))
        out.append(rec)
    return out
