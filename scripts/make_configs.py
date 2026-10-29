"""Generate configs/baseline.json and configs/illustrative.json (+ scenario files) from the revision-3 package.

Every number is traceable to: the reference JSON/GLB (user_reported, drawing_dimension) or is declared
as a modelling_assumption / missing_input. Baseline keeps all unknowns as null.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from exo01.reference import Reference  # noqa: E402

ref = Reference(ROOT / "data" / "reference_v3")
meta = ref.meta
BOAT = json.loads((ROOT / "data" / "renaud8000_v1" / "parameters.json").read_text())
BOAT_META = json.loads((ROOT / "data" / "renaud8000_v1" / "Renaud8000_mass_metadata.json").read_text())
glb = ref.glb_mass_register()
fl = ref.float_surface_params()

PROV = {
    "user_reported": "value supplied by the user (2026-10-28 mass list / annotation)",
    "drawing_dimension": "dimension transcribed from La Mutine sheet 1/3 (raster)",
    "modelling_assumption": "assumed to run a calculation; NOT measured",
    "missing_input": "unknown - kept null in the baseline configuration",
    "illustrative": "example value for demonstration only",
}

MISSING_INPUTS = [
    "float displacement geometry (cross-section, length, end shape, installed position, buoyant volume)",
    "installed centre of mass of every component (esp. vertical) and installed battery/electronics positions",
    "confirmation of mass accounting (do 150/70 kg section masses exclude floats and equipment?)",
    "observation-deck surface mass (included in the 70 kg middle section or not)",
    "complete operating displacement: host boat, people, payload, propulsion and other unlisted loads",
    "host boat mass, buoyancy, COM and connection to the EXO structure",
    "occupant count, masses, postures and positions on the lower/observation deck",
    "component inertia data; structural mass distribution",
    "float-to-frame connection stiffness (rigid-connection is assumed)",
    "viscous damping (roll/heave/pitch); water depth and wave climate at the site",
    "resolution of the 4.980 m (drawing) vs 4.950 m (section chain) overall-length discrepancy",
    "Hydronaute (host boat) berth: clear width/length required inside the frame, docking position, connection stiffness",
]

FIVE_MOST_CONSEQUENTIAL = [
    {"rank": 1, "item": "Float installed positions and section (Flofiz 1.60 x D0.60 m per the component list: x of each float on "
     "the frame, height of the float axis under the deck datum, lateral spacing, moulded channel, fill)",
     "why": "Buoyancy, draft, waterplane inertia and hydrodynamics all come from this one surface. Roll stiffness scales with "
            "the square of the lateral spacing, and the drawing gives 3200 mm (end view) and 3353 mm (top view) clearances "
            "that do not both match the proxy spacing."},
    {"rank": 2, "item": "Installed centre of mass of every component, especially vertical (structure sections, batteries, "
     "electronics, panels), and inertia distribution",
     "why": "Heel/trim at rest come from the horizontal offset COM-COB; KG enters every restoring term; inertia sets natural periods."},
    {"rank": 3, "item": "Mass accounting and total operating displacement (do section masses exclude floats/equipment? "
     "deck-surface mass? propulsion, payload, cabling, fluids)",
     "why": "The 840 kg is a listed subtotal. Draft scales directly with displacement; double counting or omissions "
            "shift every result."},
    {"rank": 4, "item": "Host boat (if attached): mass, buoyancy geometry, COM, cleat positions and the connection to the EXO frame "
     "(line material/length/pretension); the pods' thrust-vs-speed curve for the push/tow cases",
     "why": "The combined vessel is a different floating body; the EXO-only results here say nothing about it."},
    {"rank": 5, "item": "Operational loads and environment: occupants (number, mass, posture, positions), water depth, "
     "wave climate, and measured roll/heave/pitch damping (decay test)",
     "why": "People on the observation deck at ~2.2 m move the COM and load the structure; response near resonance is "
            "governed by damping that linear potential theory does not provide."},
]

COMPONENT_ORDER = ["EXO_REAR_150", "EXO_MIDDLE_70", "EXO_END_70",
                   "FLOAT_NEG_Y_1", "FLOAT_NEG_Y_2", "FLOAT_NEG_Y_3",
                   "FLOAT_POS_Y_1", "FLOAT_POS_Y_2", "FLOAT_POS_Y_3",
                   "SOLAR_1", "SOLAR_2", "SOLAR_3", "SOLAR_4", "BATTERY_1", "BATTERY_2", "ELECTRONICS_50"]
metac = {c["component_id"]: c for c in meta["components"]}


# ---- Flofiz floats (EXO-01 component list 2026-09-12 via the user's anatomy figure, 28/10/2026; flofiz.com plan,
# "mesures approximatives"): 1.60 m x D 0.60 m, body 1.30 m flat at one end, 0.30 m sled nose; rear float nose aft,
# middle and end floats nose forward (La Mutine renders). The GLB proxies of revision 3 are drawn end to end but with
# unequal lengths (1.6 / 1.425 / 1.575 m: 0.5-2.1, 2.1-3.525, 3.525-5.1), so three 1.60 m floats are placed end to end
# (2 cm gaps) from the rear float's drawn position, reaching x = 5.34 m (GLB row ends at 5.1 m, frame at 4.95 m, panels
# overhang to 5.585 m); the installed positions are measurement #1 of the five.
FLOAT_Y = 1.97
FLOAT_D, FLOAT_BODY, FLOAT_NOSE = 0.60, 1.30, 0.30
FLOAT_Z_AXIS = -FLOAT_D / 2            # top of the float at the deck datum Z = 0 (as drawn: beam sits in the top channel)
FLOFIZ_ROW = {1: (2.10, -1), 2: (2.12, +1), 3: (3.74, +1)}      # index -> (flat end x, nose direction)


def flofiz_surface(cid, y):
    idx = int(cid[-1])
    x_flat, nd = FLOFIZ_ROW[idx]
    return {
        "id": cid, "component_id": cid, "type": "flofiz_x",
        "flat_end_x_m": x_flat, "nose_dir": nd, "y_m": round(float(y), 6), "z_axis_m": FLOAT_Z_AXIS,
        "diameter_m": FLOAT_D, "body_length_m": FLOAT_BODY, "nose_length_m": FLOAT_NOSE,
        "x_span_m": [min(x_flat, x_flat + nd * 1.6), max(x_flat, x_flat + nd * 1.6)],
        "centre_m": [round(x_flat + nd * FLOAT_BODY / 2, 6), round(float(y), 6), FLOAT_Z_AXIS],
        "length_m": FLOAT_BODY + FLOAT_NOSE, "radius_m": FLOAT_D / 2,
        "source": "Flofiz 1.60 m x D0.60 m float (component list 2026-09-12; dimensions 'approximate' per flofiz.com); "
                  "y from the GLB proxies (+-1.97 m); x placed end to end from the rear float's drawn position (GLB proxies are "
                  "1.6/1.425/1.575 m long, the real floats 1.60 m each); top at Z=0 "
                  "as drawn. NOT a measured displacement surface: installed positions, fill and the top channel are unverified.",
        "verified": False,
    }


POD_POINTS = {"POD_STBD": [0.34, -FLOAT_Y, -0.44], "POD_PORT": [0.34, FLOAT_Y, -0.44]}


def pod_component(cid, y):
    return {
        "id": cid, "name": f"RDT POD 5.0 rim drive ({'port' if y > 0 else 'starboard'})", "category": "propulsion",
        "mass_kg": None, "mass_source": "missing_input",
        "mass_note": "NOT in the 840 kg register (16 parents). Datasheet: 5 kg in air (geo-matching.com, POD 5.0); bracket, "
                     "cable and controller unknown.",
        "com_m": None, "com_source": "missing_input", "inertia": None,
        "preview_anchor_m": POD_POINTS[cid], "geometry_status": "user_statement", "location_status": "user_statement",
        "register": False,
        "location_note": "Elven 28/10/2026: two POD 5.0 at the back, behind each float row; hub 0.44 m below the deck datum ASSUMED",
    }


def base_component(cid):
    m = metac[cid]
    return {
        "id": cid, "name": m["name"], "category": m["category"],
        "mass_kg": m["mass_kg"],
        "mass_source": m["mass_status"],            # user_reported / user_estimate
        "mass_note": m["mass_counting_rule"],
        "com_m": None, "com_source": "missing_input",
        "inertia": None,
        "preview_anchor_m": m["preview_anchor_m"],   # visual anchor, NOT a measured COM
        "geometry_status": m["geometry_status"],
        "location_status": m["location_status"],
    }


def _sym(id_, exo, boat):
    return [{"id": f"{id_}_PORT", "exo_point_m": [exo[0], exo[1], exo[2]], "boat_point_m": [boat[0], boat[1], boat[2]]},
            {"id": f"{id_}_STBD", "exo_point_m": [exo[0], -exo[1], exo[2]], "boat_point_m": [boat[0], -boat[1], boat[2]]}]


LINE_PRESETS = [
    {"id": "simulator_default", "title": "Aft breasts + backward springs (v0.3 default)",
     "note": "EXO aft posts -> stern cleats, EXO forward posts -> midship cleats aft of them: balanced at rest, the springs can carry a forward push",
     "lines": _sym("LINE_AFT", (2.1, 2.25, 0.0), (0.3, 1.3, 0.8)) + _sym("SPRING", (4.95, 2.25, 0.0), (2.0, 1.35, 0.8))},
    {"id": "figure_all_forward", "title": "Four lines all running forward (anatomy figure, 28/10)",
     "note": "EXO x 2.18 and 4.87 -> boat cleats forward of each (stern x 0.30, midship x 4.30): holds the boat against a tow or braking only; "
             "cannot transmit a forward push from the pods (all lines go slack)",
     "lines": _sym("AFT", (2.18, 2.19, 0.11), (0.30, 1.30, 0.83)) + _sym("FWD", (4.87, 2.19, 0.11), (4.30, 1.35, 0.80))},
    {"id": "push_springs_long", "title": "Long push springs + forward breasts",
     "note": "EXO forward posts -> stern cleats (long, mostly longitudinal: carry the pods' push efficiently) and EXO aft posts -> midship cleats "
             "forward (carry a tow/brake and restrain yaw)",
     "lines": _sym("PUSH", (4.95, 2.25, 0.0), (0.30, 1.30, 0.80)) + _sym("TOW", (2.1, 2.25, 0.0), (4.30, 1.35, 0.80))},
    {"id": "six_lines", "title": "Six lines: breasts + push springs + tow springs",
     "note": "breasts at the stern cleats from the aft posts, long push springs from the forward posts to the stern cleats, tow springs from the "
             "aft posts to the midship cleats",
     "lines": _sym("BREAST", (2.1, 2.25, 0.0), (0.3, 1.3, 0.8)) + _sym("PUSH", (4.95, 2.25, 0.0), (0.30, 1.30, 0.80)) + _sym("TOW", (2.1, 2.25, 0.0), (4.30, 1.35, 0.80))},
]


def build_propulsion(baseline):
    """Quasi-static propulsion/tow model: thrust units, thrust-vs-speed assumption and the resistance coefficients.
    Every coefficient is an explicit, editable ASSUMPTION; see exo01/propulsion.py for the formulas."""
    return {
        "units": {
            "EXO_PODS": {
                "title": "2 x Rim Drive Technology POD 5.0 (EXO, aft of each float row)", "body": "EXO",
                "bollard_thrust_N": None if baseline else round(2 * 62.0 * 9.80665, 1),
                "thrust_source": "component list 2026-09-12: 62 kgf each (5 kW, 48 V, 106 A); 5 kg in air (geo-matching.com)",
                "thrust_points_m": [POD_POINTS["POD_STBD"], POD_POINTS["POD_PORT"]], "direction_body": [1.0, 0.0, 0.0],
                "position_source": "Elven 28/10/2026 (anatomy figure): just aft of the rear floats, in line with each row; hub depth 0.44 m ASSUMED",
            },
            "BOAT_ENGINE": {
                "title": "Hydronaute inboard (Volvo 19 CV, archival)", "body": "BOAT",
                "bollard_thrust_N": None if baseline else 1500.0,
                "thrust_source": "19 CV from the archival sheet; bollard thrust UNKNOWN - 1500 N is an ORDER-OF-MAGNITUDE assumption for a ~14 kW inboard, not a datasheet value",
                "thrust_points_m": [[0.5, 0.0, -0.45]], "direction_body": [1.0, 0.0, 0.0],
                "position_source": "ASSUMED propeller 0.5 m forward of the transom, 0.45 m below the package datum",
            },
        },
        "thrust_model": {"type": "constant_bollard",
                         "note": "thrust = fraction x bollard thrust, independent of speed (optimistic at speed: a rim drive's thrust falls with advance speed)"},
        "resistance": {
            "nu_m2_s": 1.14e-6, "rho_note": "water density from environment",
            "exo": {"form_factor_k": 0.30, "pressure_drag_cd": 0.15,
                    "note": "per float row: ITTC-57 friction on the wetted area x (1+k) + Cd x submerged frontal area of one float for the "
                            "nose/flat-end junctions and gaps (ASSUMED coefficients; the flat-to-flat junction of the rear and middle floats "
                            "and the nose-to-flat junction of the middle and end floats are not resolved)"},
            "boat": {"form_factor_k": 0.25, "appendage_factor": 1.15, "residuary_c_at_fr02": 0.0015, "residuary_exponent": 4.0,
                     "note": "ITTC-57 friction on the proxy hull's wetted area x (1+k) x appendages (keel, rudder, propeller) + residuary "
                             "C_R = c (Fr/0.2)^n on the wetted area (ASSUMED; the proxy hull is not the real hull)"},
            "drag_points": "EXO: resultant at the centroid of the submerged float volume (world); boat: at its centre of buoyancy",
        },
        "label": "QUASI-STATIC: steady state, thrust = total resistance, no wave-added resistance, wind or current; "
                 "line loads are what the arrangement must carry to push/tow the other body",
    }


def build_boat(baseline):
    """Hydronaute (Renaud 8000) as a second floating body. Baseline: archival mass, COM/inertia null."""
    b = {
        "included": True,
        "id": "RENAUD8000", "name": "Hydronaute (Renaud 8000) - reference reconstruction v1",
        "reference_package": "data/renaud8000_v1",
        "frame": "boat CAD: X stern -> bow, Y to port, Z up; Z = 0 is the package's illustrative catalogue waterline (not an equilibrium)",
        "mass_kg": BOAT["archival_light_mass_kg"],
        "mass_source": "archival_light_weight_unverified (2.1 t on the archived sheet; Fluvial page says 3.0 t; current restored boat not weighed)",
        "mass_alternatives_kg": [BOAT["archival_light_mass_kg"], BOAT["published_alternative_mass_kg"]],
        "com_m": None, "com_source": "missing_input",
        "inertia": None,
        "buoyant_surface": {
            "id": "RENAUD8000_HULL_PROXY", "type": "renaud8000_hull_proxy",
            "stations_mm": BOAT["hull_stations_mm"], "topside_top_mm": BOAT["topside_top_z_mm"],
            "keel_excluded": True, "verified": False,
            "source": "closed gull-wing envelope rebuilt from the package station table (same loft as its build_model.py); "
                      "NOT a measured hull - no offsets exist. At the package's drawn waterline (z=0) it displaces ~4.9 m3, "
                      "far more than the 2.1-3.0 t references: the proxy hull form and/or its waterline datum are not consistent.",
        },
        "placement_in_exo_frame": {
            "x_m": 2.2, "y_m": 0.0, "yaw_deg": 0.0, "confirmed": False,
            "source": "modelling_assumption: boat stern 0.1 m forward of the EXO rear deck plate edge (x = 2.2 m), centred "
                      "between the float rows; stern/aft cabin under the frame bays, bow 5.15 m beyond the end frame. "
                      "Vertical position and attitude come from the boat's own flotation, never from this transform.",
        },
        "standing_surfaces": {
            "boat_aft_deck": {"z_m": 0.78, "x_range_m": [0.05, 0.45], "y_range_m": [-1.3, 1.3], "source": "package deck level 0.78 m; aft deck strip"},
            "boat_forward_terrace": {"z_m": 0.49, "x_range_m": [6.3, 7.7], "y_range_m": [-1.2, 1.2], "source": "package front well floor 0.49 m"},
            "boat_roof": {"z_m": 2.28, "x_range_m": [3.4, 6.2], "y_range_m": [-1.1, 1.1], "source": "package roof level (stepped roof); walking on it is an assumption"},
        },
        "people": [],
        "lines": [
            {"id": "LINE_AFT_PORT", "exo_point_m": [2.1, 2.25, 0.0], "boat_point_m": [0.3, 1.3, 0.8]},
            {"id": "LINE_AFT_STBD", "exo_point_m": [2.1, -2.25, 0.0], "boat_point_m": [0.3, -1.3, 0.8]},
            {"id": "SPRING_PORT", "exo_point_m": [4.95, 2.25, 0.0], "boat_point_m": [2.0, 1.35, 0.8]},
            {"id": "SPRING_STBD", "exo_point_m": [4.95, -2.25, 0.0], "boat_point_m": [2.0, -1.35, 0.8]},
        ],
        "line_presets": LINE_PRESETS,
        "lines_note": "assumed arrangement: two aft breast lines (EXO aft posts -> stern cleats, pulling the boat slightly aft) and "
                      "two springs (EXO forward posts -> midship cleats aft of them, pulling the boat forward) so that the horizontal "
                      "line forces can balance; attachment points are not measured",
        "line_defaults": {
            "pretension_N": 100.0, "stiffness_N_per_m": 10000.0,
            "source": "modelling_assumption: 'slightly tense' lines = linear springs about a small pretension. A bare taut "
                      "10-12 mm polyester line of 1-2 m is ~5-10x stiffer and goes slack in compression (nonlinear, not modelled); "
                      "the response flags when the dynamic tension amplitude exceeds the pretension.",
        },
        "clearance_reference": {
            "exo_header_underside_z_m": 2.1, "exo_observation_deck_underside_z_m": 2.176, "exo_panel_underside_z_m": 2.72,
            "exo_float_inner_face_y_m": round(FLOAT_Y - FLOAT_D / 2, 4), "exo_rear_deck_plate_x_range_m": [0.0, 2.1],
            "boat_cabin_stations_mm": BOAT["cabin_stations_mm"], "boat_half_beam_m": 1.49, "boat_deck_z_m": 0.78,
        },
        "notes": [
            "The boat and the EXO are two separate floating bodies; each has its own still-water equilibrium.",
            "Still water: coupled equilibrium of both bodies with tension-only line springs (L0 = L_nominal - T0/k): the boat shifts/yaws from the nominal berth until the line forces balance; equilibrium tensions (possibly slack) feed the wave model.",
            "Wave response: both bodies in one Capytaine problem (hydrodynamic interaction included), 12 DOF, lines as linear springs.",
        ],
    }
    if not baseline:
        b["com_m"] = [3.6, 0.0, 0.35]
        b["com_source"] = "assumption"
        b["com_note"] = ("ASSUMED: 45% of the length from the stern (engine aft), on the centreline, 0.35 m above the package datum "
                         "(~0.9 m above the hull bottom; cabin raises the light-ship COM)")
        b["inertia"] = {"model": "shell_box", "dims_m": [8.0, 2.98, 2.3], "source": "assumption"}
    return b


def build_baseline():
    comps = [base_component(c) for c in COMPONENT_ORDER]
    surfaces = []
    for cid in COMPONENT_ORDER:
        if cid.startswith("FLOAT"):
            p = fl[cid]
            surfaces.append(flofiz_surface(cid, float(p["centre"][1])))
    comps += [pod_component("POD_STBD", -FLOAT_Y), pod_component("POD_PORT", FLOAT_Y)]
    cfg = {
        "schema": "exo01_config_v1",
        "name": "baseline",
        "title": "EXO-01 baseline (revision 3) - user-reported values only; unknowns are null",
        "mode": "baseline",
        "result_label": "Baseline - missing inputs are not replaced by assumptions",
        "reference_revision": meta["revision"],
        "provenance_key": PROV,
        "drawing_dimensions": {
            "frame_length_m": 4.95, "drawing_overall_length_m": 4.98, "unresolved_length_difference_m": 0.03,
            "frame_width_m": 4.547, "frame_height_above_deck_m": 2.7,
            "top_frame_z_m": 2.7, "observation_surface_z_m": 2.2, "observation_drop_below_top_frame_m": 0.5,
            "lower_deck_top_z_m": 0.0, "section_lengths_m": [2.1, 1.425, 1.425],
            "clearances_m": {"clear_height_end_view": 2.1, "ladder_width": 0.6,
                             "end_view_dimension_3200": 3.2, "top_view_dimension_3353": 3.353},
            "source": "drawing_dimension (30 mm and 3200/3353 inconsistencies preserved, not resolved)",
        },
        "environment": {"rho_kg_m3": None, "g_m_s2": 9.80665, "water_depth_m": None,
                        "note": "water density and depth are site inputs: null in the baseline"},
        "components": comps,
        "buoyant_surfaces": surfaces,
        "people": [],
        "standing_surfaces": {
            "lower_deck": {"z_m": 0.0, "x_range_m": [0.0, 2.1], "y_range_m": [-2.2735, 2.2735],
                           "source": "GLB deck_plate_proxy bounds (rear deck plate, top at Z=0)"},
            "observation_deck": {"z_m": 2.2, "x_range_m": [2.1, 3.525], "y_range_m": [-2.2485, 2.2485],
                                 "source": "GLB upper_observation_deck_proxy bounds; Z=2.200 m (user: ~0.5 m below top frame)"},
        },
        "freeboard_points": {
            "lower_deck_corners": [[0.0, -2.2735, 0.0], [0.0, 2.2735, 0.0], [2.1, -2.2735, 0.0], [2.1, 2.2735, 0.0]],
            "frame_footprint_corners_deck_datum": [[0.0, -2.2735, 0.0], [0.0, 2.2735, 0.0],
                                                   [4.95, -2.2735, 0.0], [4.95, 2.2735, 0.0]],
            "observation_deck_centre": [2.8125, 0.0, 2.2],
        },
        "deck_acceleration_points": {
            "observation_deck_centre": [2.8125, 0.0, 2.2],
            "observation_deck_corner_aft_port": [2.1, -2.2485, 2.2],
            "observation_deck_corner_aft_stbd": [2.1, 2.2485, 2.2],
            "observation_deck_corner_fwd_port": [3.525, -2.2485, 2.2],
            "observation_deck_corner_fwd_stbd": [3.525, 2.2485, 2.2],
        },
        "host_boat": build_boat(baseline=True),
        "propulsion": build_propulsion(baseline=True),
        "visual_overrides": {
            "hidden_subparts": ["walkway_-1", "walkway_1", "base_crossmember_end", "EXO_END_70/longeron_-1_2675", "EXO_END_70/longeron_1_2675"],
            "reason": "User corrections 2026-10-28: (1) the two longitudinal walkway plates drawn in the middle and end bays do not exist; "
                      "(2) the two transverse base members crossing the gap between the float rows at deck level (x = 3.5 m and 4.95 m) do "
                      "not exist either - they are the only members that intersect the berthed Hydronaute; (3) 18:21: the top side rails of the "
                      "end (panel) bay do not exist. Names may be qualified by section (SECTION/name) when the same name occurs in several "
                      "sections. The space between the float rows is open so the boat can be berthed inside the frame.",
            "mass_effect": "none - section masses are user-reported totals, never derived from the visual envelopes",
            "buoyancy_effect": "none - only the six floats are buoyant surfaces",
        },
        "host_boat_berth": {
            "clear_width_between_float_proxies_m": round(2 * (FLOAT_Y - FLOAT_D / 2), 4),
            "note": "2 x 1.67 m (inner faces of the D 0.60 m Flofiz floats at y = +-1.97 m; 3.3616 m with the D 0.58 m GLB proxies). "
                    "Close to the 3353 mm top-view dimension of the drawing: "
                    "HYPOTHESIS that this dimension is the clear berth width - not confirmed.",
            "status": "hypothesis",
        },
        "pending_loads": {"observation_deck_surface_mass_kg": None, "included_in_middle_section": "unconfirmed",
                          "people": None, "host_boat": None, "propulsion_payload_other": None},
        "missing_inputs": MISSING_INPUTS,
        "rigid_connection_assumption": "the six floats and the frame move as ONE rigid body (no joint compliance)",
    }
    return cfg


def build_illustrative(base):
    cfg = copy.deepcopy(base)
    cfg["name"] = "illustrative"
    cfg["title"] = "EXO-01 illustrative (EXO-only) - assumed geometry and mass distribution"
    cfg["mode"] = "exploratory"
    cfg["result_label"] = "Exploratory — assumed geometry and mass distribution."
    cfg["environment"] = {"rho_kg_m3": 999.0, "g_m_s2": 9.80665, "water_depth_m": 3.0,
                          "note": "ILLUSTRATIVE: fresh water (river Erdre, ~999 kg/m3 at 15 degC) and an ASSUMED 3.0 m depth (typical "
                                  "Erdre channel near Nantes is 2-4 m; measure at the berth - finite depth changes added mass and wavelength "
                                  "for T > ~2 s). Blank depth = infinite."}
    cfg["host_boat"] = build_boat(baseline=False)
    cfg["propulsion"] = build_propulsion(baseline=False)
    cfg["host_boat_note"] = ("Host boat included as a SECOND BODY with assumed mass distribution and a proxy hull; set host_boat.included=false "
                             "for the EXO-only case (the built-in scenarios cover both).")

    box = {"rear": [2.1, 4.547, 0.76], "bay": [1.425, 4.547, 2.7]}
    spec = {
        "EXO_REAR_150": ([1.05, 0.0, 0.38], {"model": "shell_box", "dims_m": box["rear"]},
                         "ASSUMED COM at centre of the deck/rail envelope (deck plate Z=0, rails to ~0.76 m); inertia: thin-walled box"),
        "EXO_MIDDLE_70": ([2.8125, 0.0, 1.35], {"model": "shell_box", "dims_m": box["bay"]},
                          "ASSUMED COM at mid-height of the 2.7 m bay envelope; inertia: thin-walled box"),
        "EXO_END_70": ([4.2375, 0.0, 1.35], {"model": "shell_box", "dims_m": box["bay"]},
                       "ASSUMED COM at mid-height of the 2.7 m bay envelope; inertia: thin-walled box"),
    }
    for c in cfg["components"]:
        cid = c["id"]
        anchor = c["preview_anchor_m"]
        if cid in spec:
            com, inertia, note = spec[cid]
            c["com_m"], c["com_source"], c["com_note"] = com, "assumption", note
            c["inertia"] = dict(inertia, source="assumption")
        elif cid.startswith("FLOAT"):
            s = next(s for s in cfg["buoyant_surfaces"] if s["id"] == cid)
            c["com_m"] = list(s["centre_m"])
            c["com_source"] = "assumption"
            c["com_note"] = "ASSUMED at the centre of the float's cylindrical body (uniform shell)"
            c["inertia"] = {"model": "cylinder_shell_x", "dims_m": [s["length_m"], s["radius_m"]], "source": "assumption"}
        elif cid.startswith("POD"):
            c["mass_kg"], c["mass_source"] = 8.0, "assumption"
            c["mass_note"] = "ASSUMED 8 kg: 5 kg motor (datasheet, in air) + 3 kg bracket/shaft/cable; NOT in the 840 kg register"
            c["com_m"], c["com_source"] = list(POD_POINTS[cid]), "assumption"
            c["com_note"] = "at the pod hub (Elven 28/10: aft of each float row; depth ASSUMED)"
            c["inertia"] = {"model": "point", "dims_m": [], "source": "assumption"}
        elif cid.startswith("SOLAR"):
            c["com_m"], c["com_source"] = list(anchor), "assumption"
            c["com_note"] = "ASSUMED at the preview anchor (panel centre); horizontal, tilt not confirmed"
            c["inertia"] = {"model": "solid_box", "dims_m": [2.06, 1.10675, 0.04], "source": "assumption"}
        elif cid.startswith("BATTERY"):
            sgn = -1.0 if cid.endswith("1") else 1.0
            c["com_m"], c["com_source"] = [1.425, sgn * 2.05, 0.50], "user_statement+assumption"
            c["com_note"] = ("Elven 28/10/2026: two Dyness PowerBrick Plus standing upright, one strapped to each side rail, mirrored; "
                             "footprint x 1.15-1.70 m, |y| 1.90-2.20 m, 1.0 m tall (drawn size, not a datasheet); COM ASSUMED at mid-height")
            c["inertia"] = {"model": "solid_box", "dims_m": [0.55, 0.30, 1.00], "source": "assumption"}
        elif cid.startswith("ELECTRONICS"):
            c["com_m"], c["com_source"] = [1.73, 1.08, 0.50], "user_statement+assumption"
            c["com_note"] = ("Elven 28/10/2026: electrical cabinet on the port side of the rear deck, back against the frame, opening aft; "
                             "footprint x 1.50-1.96 m, y 0.62-1.54 m, 1.0 m tall; COM ASSUMED at mid-height")
            c["inertia"] = {"model": "solid_box", "dims_m": [0.46, 0.92, 1.00], "source": "assumption"}
    return cfg


GLB_CAPSULE = {}
for _cid in COMPONENT_ORDER:
    if _cid.startswith("FLOAT"):
        _p = fl[_cid]
        _r = meta["dimension_register"]["float_diameter_proxy_m"] / 2.0
        GLB_CAPSULE[_cid] = {"type": "capsule_x", "centre_m": [round(float(_p["centre"][0]), 6), round(float(_p["centre"][1]), 6), -_r],
                             "length_m": round(float(_p["length"]), 6), "radius_m": _r,
                             "source": "revision-3 GLB float proxy as a capsule (v0.1-v0.3 model)", "verified": False}

SCEN_NOTES = "ILLUSTRATIVE scenario on the exploratory configuration; masses/positions are examples, not data."


def scenarios():
    person = lambda i, m, x, y, surf, posture="standing": {
        "id": f"PERSON_{i}", "name": f"Person {i} (illustrative)", "mass_kg": m, "mass_source": "illustrative",
        "surface": surf, "posture": posture, "x_m": x, "y_m": y}
    exo_only = {"host_boat": {"included": False}}
    return {
        "baseline_illustrative": {
            "title": "Illustrative baseline (EXO-only, no occupants)", "base": "illustrative", "overrides": dict(exo_only),
            "notes": SCEN_NOTES},
        "with_hydronaute": {
            "title": "EXO + Hydronaute (Renaud 8000, 2.1 t archival, proxy hull) moored with 4 soft lines", "base": "illustrative",
            "overrides": {},
            "notes": SCEN_NOTES + " Boat placement, mass, COM and hull are assumptions; two-body response with line springs."},
        "battery_relocated": {
            "title": "Batteries moved aft on the rear deck (x 1.425 -> 0.60 m), still at the side rails", "base": "illustrative",
            "overrides": {"components": {"BATTERY_1": {"com_m": [0.60, -2.05, 0.50]},
                                         "BATTERY_2": {"com_m": [0.60, 2.05, 0.50]}}, **exo_only},
            "notes": SCEN_NOTES + " Footprint x 0.325-0.875 m stays on the 2.1 m deck; cleat/pod bracket clearance not checked."},
        "battery_float_frame": {
            "title": "Batteries moved forward onto the float-top side frames (x 1.425 -> 3.60 m, above the floats, between the mid and end uprights)",
            "base": "illustrative",
            "overrides": {"components": {"BATTERY_1": {"com_m": [3.60, -2.05, 0.50]},
                                         "BATTERY_2": {"com_m": [3.60, 2.05, 0.50]}}, **exo_only},
            "notes": SCEN_NOTES + " User proposal (29/10): both batteries forward, beside the boat. The sweep (exo01/optimise.py, float_frame zone) "
                                  "puts the zero-trim position of the empty EXO at x ~3.5 m; whether the float cradle carries 120 kg per battery is "
                                  "a structural question outside this model."},
        "floats_glb_capsules": {
            "title": "Float proxies of revision 3 (capsules D 0.58 m fitted to the GLB) instead of the Flofiz shape", "base": "illustrative",
            "overrides": {"buoyant_surfaces": {cid: GLB_CAPSULE[cid] for cid in GLB_CAPSULE}, **exo_only},
            "notes": SCEN_NOTES + " Sensitivity of draft/trim/stability to the float geometry assumption."},
        "occupants_symmetric": {
            "title": "Two illustrative 80 kg occupants standing symmetrically on the observation deck",
            "base": "illustrative",
            "overrides": {"people": [person(1, 80.0, 2.8125, -1.0, "observation_deck"),
                                     person(2, 80.0, 2.8125, 1.0, "observation_deck")], **exo_only},
            "notes": SCEN_NOTES + " 80 kg is an ILLUSTRATIVE person mass."},
        "occupants_asymmetric": {
            "title": "Two illustrative 80 kg occupants standing on the same (+Y) side of the observation deck",
            "base": "illustrative",
            "overrides": {"people": [person(1, 80.0, 2.5, 1.8, "observation_deck"),
                                     person(2, 80.0, 3.1, 1.8, "observation_deck")], **exo_only},
            "notes": SCEN_NOTES + " 80 kg is an ILLUSTRATIVE person mass."},
    }


if __name__ == "__main__":
    base = build_baseline()
    ill = build_illustrative(base)
    (ROOT / "configs").mkdir(exist_ok=True)
    (ROOT / "scenarios").mkdir(exist_ok=True)
    (ROOT / "configs" / "baseline.json").write_text(json.dumps(base, indent=1))
    (ROOT / "configs" / "illustrative.json").write_text(json.dumps(ill, indent=1))
    (ROOT / "configs" / "five_missing_measurements.json").write_text(json.dumps(FIVE_MOST_CONSEQUENTIAL, indent=1))
    for k, v in scenarios().items():
        sc = {"schema": "exo01_scenario_v1", "name": k, **v}
        (ROOT / "scenarios" / f"{k}.json").write_text(json.dumps(sc, indent=1))
    print("written", [p.name for p in (ROOT / "configs").iterdir()], [p.name for p in (ROOT / "scenarios").iterdir()])
