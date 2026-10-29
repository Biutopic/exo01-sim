"""Still-water evaluation of one resolved configuration: mass -> equilibrium -> stability -> freeboards.

Never invents inputs: anything that needs a null value is reported as `not_computed` with the reasons.
"""
from __future__ import annotations

import copy

import numpy as np

from . import equilibrium as eqm
from .buoyancy import BuoyantAssembly, surfaces_from_config
from .config import validate
from .mass import MissingInput, items_from_config, mass_properties, aggregate_by_category
from .units import deg
from .twobody import evaluate_boat, pose_exo, pose_boat, line_geometry, clearances

STILL_WATER_RES = dict(n_circ=96, n_axial=12, n_cap=24)   # verified: capsule volume/waterplane within 6e-4 of analytic


_ASSEMBLIES = {}


def build_assembly(cfg, resolution=None):
    """BuoyantAssembly for the config's buoyant surfaces (cached: tessellation is the costly part)."""
    import json
    key = json.dumps([cfg["buoyant_surfaces"], resolution or STILL_WATER_RES], sort_keys=True)
    if key not in _ASSEMBLIES:
        if len(_ASSEMBLIES) > 16:
            _ASSEMBLIES.clear()
        _ASSEMBLIES[key] = BuoyantAssembly(surfaces_from_config(cfg, resolution or STILL_WATER_RES))
    return _ASSEMBLIES[key]


_WARM = {}
_LEVEL_KEEL = {}


def _level_keel_cached(asm, mass, rho):
    key = (id(asm), round(float(mass), 9), round(float(rho), 9))
    if key not in _LEVEL_KEEL:
        if len(_LEVEL_KEEL) > 64:
            _LEVEL_KEEL.clear()
        _LEVEL_KEEL[key] = eqm.level_keel_screening(asm, mass, rho)
    return copy.deepcopy(_LEVEL_KEEL[key])


def _exo_equilibrium_fields(asm, eq, cfg, rho, g):
    I = eq["integrals"]
    G = eq["G_body"]
    M = eq["mass"]
    res = eqm.residuals(asm, eq)
    fb = eqm.freeboards(asm, eq, cfg)
    B_body = eq["R"].T @ (I["B"] - np.array([0.0, 0.0, eq["zG"]])) + G      # world -> body: w = R (p - G) + (0, 0, zG)
    return dict(
        feasible=True, heel_deg=deg(eq["phi"]), trim_deg=deg(eq["theta"]),
        heel_rad=eq["phi"], trim_rad=eq["theta"],
        sign_convention="heel: right-handed about +X (+Y side up); trim: right-handed about +Y (positive = +X end down)",
        com_height_above_waterline_m=eq["zG"],
        displaced_volume_m3=I["V"], displaced_mass_kg=I["V"] * rho,
        centre_of_buoyancy_world_m=I["B"].tolist(),
        centre_of_buoyancy_body_m=B_body.tolist(), centre_of_mass_body_m=np.asarray(G).tolist(),
        per_float_volume_m3=asm.per_surface_volume(eq["R"], G, eq["zG"]),
        residuals=res, residuals_note="hydrostatic + gravity only; with the boat moored the difference is carried by the line forces (see lines_note)",
        waterplane_area_m2=I["Awp"],
        freeboard=fb, R_body_to_world=eq["R"].tolist(),
        rho=rho, g=g, mass_kg=M, tolerance_note="residual targets: |Fz| < 1e-9 Mg, |Mx|,|My| < 1e-9 Mg*1m",
        solver=dict(n_evaluations=eq["n_evaluations"], newton_converged=eq["newton_converged"], residual_relative=eq["residual_relative"]))


def _boat_equilibrium_fields(cfg, asm, eq, rho, g):
    from .twobody import boat_equilibrium_fields
    return boat_equilibrium_fields(cfg, asm, eq, rho, g)


def evaluate(cfg, resolution=None, assembly=None, warm_key=None):
    """warm_key: optional hashable key; the previous equilibrium for that key seeds the Newton solve."""
    issues = validate(cfg)
    out = dict(name=cfg.get("name"), scenario=cfg.get("scenario_name"), title=cfg.get("scenario_title") or cfg["title"],
               mode=cfg["mode"], label=cfg["result_label"], issues=issues,
               host_boat_included=cfg.get("host_boat") is not None,
               status={}, not_computed={})
    if any(l == "error" for l, _ in issues):
        out["status"]["all"] = "invalid_input"
        return out
    items = items_from_config(cfg)
    mp = mass_properties(items, strict=False)
    out["mass"] = mp
    out["mass"]["by_category_kg"] = aggregate_by_category(items)
    out["mass"]["scope_note"] = ("Sum of listed items only: NOT the full operating displacement "
                                 "(host boat, deck-surface mass if separate, propulsion, payload unknown).")
    env = cfg["environment"]
    rho, g = env.get("rho_kg_m3"), env.get("g_m_s2", 9.80665)
    asm = assembly or build_assembly(cfg, resolution)
    out["buoyant_volume_total_m3"] = asm.max_volume
    out["buoyant_volume_note"] = "Volume of the six float PROXY surfaces (unverified); not a verified displacement surface."

    if rho is None:
        out["not_computed"]["equilibrium"] = ["water density (environment.rho_kg_m3) is null"]
    # level-keel screening for the listed subtotal (valid even when COM is unknown)
    if rho is not None and mp["total_listed_mass_kg"] > 0:
        out["level_keel_screening"] = _level_keel_cached(asm, mp["total_listed_mass_kg"], rho)
        out["level_keel_screening"]["note"] = (
            "Heave-only screening for the LISTED SUBTOTAL at zero heel/trim. Not an equilibrium (COM unknown or "
            "attitude not solved) and not the true displacement.")
    hb = cfg.get("host_boat")
    _boat = None
    if hb and hb.get("included", False):
        _boat = evaluate_boat(cfg, rho, g, warm=_WARM.get((warm_key, "boat")) if warm_key is not None else None)
        out["bodies"] = {"boat": _boat[0]}
    if mp["com_m"] is None:
        out["not_computed"]["centre_of_mass"] = [f"COM of {x}" for x in mp["missing_com"]] + [f"mass of {x}" for x in mp["missing_mass"]]
        out["status"]["equilibrium"] = "not_computed"
        out["status"]["stability"] = "not_computed"
        return out
    if mp["inertia_com_kgm2"] is None:
        out["not_computed"]["inertia_tensor"] = [f"inertia model of {x}" for x in mp["missing_inertia"]]
    if rho is None:
        out["status"]["equilibrium"] = "not_computed"
        return out
    M, G = mp["total_mass_kg"], np.array(mp["com_m"])
    try:
        eq = eqm.equilibrium(asm, M, G, rho, g, warm_start=_WARM.get(warm_key) if warm_key is not None else None)
        if warm_key is not None:
            _WARM[warm_key] = (eq["z_origin"], eq["phi"], eq["theta"])
    except eqm.NoEquilibrium as e:
        out["status"]["equilibrium"] = "no_feasible_equilibrium"
        out["equilibrium"] = dict(feasible=False, reason=str(e), best_point=getattr(e, "best", None), mass_kg=M,
                                  centre_of_mass_body_m=np.asarray(G).tolist())
        if getattr(e, "best", None):
            bp = e.best
            out["bodies"] = {"exo": dict(pose=dict(R_world=bp["R_world"], com_world=[float(G[0]), float(G[1]), bp["zG_m"]], G_body=np.asarray(G).tolist()),
                                         best_point_only=True)}
        return out
    # --- propulsion / tow (quasi-static): thrust fraction > 0 adds thrust and drag wrenches to the equilibria
    prop = None
    from .propulsion import propulsion_setting, PropulsionModel
    pfrac, punit = propulsion_setting(cfg)
    boat_on = bool(hb and hb.get("included", False))
    if pfrac > 0 and cfg.get("propulsion"):
        unit = cfg["propulsion"]["units"].get(punit)
        if unit is None:
            out["flags"] = [f"unknown propulsion unit {punit}"]
        elif unit.get("bollard_thrust_N") is None:
            out["not_computed"]["propulsion"] = [f"bollard thrust of {punit} is null"]
        elif unit["body"] == "BOAT" and not boat_on:
            out["not_computed"]["propulsion"] = ["boat engine selected but the host boat is not included"]
        else:
            prop = PropulsionModel(cfg, asm, None, rho, g)
    exo_only_prop = prop is not None and (not boat_on or not hb.get("lines"))
    if exo_only_prop and prop.unit["body"] == "EXO":
        # EXO alone (or boat present but unconnected): thrust and the EXO's own drag; two passes (speed <-> pose)
        for _ in range(2):
            prop.solve_speed(eq, None)
            ext = prop.external_exo_only(pose_exo(eq))
            eq = eqm.equilibrium(asm, M, G, rho, g, warm_start=(eq["z_origin"], eq["phi"], eq["theta"]), external=ext)
        prop.solve_speed(eq, None)
    st = eqm.initial_stability(asm, eq)
    fb = eqm.freeboards(asm, eq, cfg)
    out["status"]["equilibrium"] = "solved"
    out["equilibrium"] = _exo_equilibrium_fields(asm, eq, cfg, rho, g)
    out["stability_static"] = st
    out["stability_static"]["scope"] = ("STATIC initial stability of the floats-only buoyancy model. It is not wave behaviour, "
                                        "not a capsize limit, and ignores frame/deck buoyancy and flooding.")
    flags = []
    if fb["float_top_freeboard_min_m"] < 0:
        flags.append("at least one float is fully submerged: buoyancy outside the modelled proxy surfaces would matter")
    if abs(deg(eq["phi"])) > 10 or abs(deg(eq["theta"])) > 10:
        flags.append("static heel or trim exceeds 10 deg: linear wave response about this attitude is out of range")
    if not st["statically_stable_here"]:
        flags.append("restoring matrix not positive definite at this attitude: equilibrium is not statically stable")
    out["flags"] = flags
    out["_eq"] = eq
    out["_assembly"] = asm
    out["bodies"] = {"exo": dict(pose=pose_exo(eq))}
    if hb and hb.get("included", False):
        bres, basm, beq = _boat                      # solved once above (independent flotation of the boat)
        out["bodies"]["boat"] = bres
        if beq is not None:
            coupled = None
            if hb.get("lines"):
                from .twobody import coupled_equilibrium, boat_assembly
                try:
                    external = None
                    if prop is not None:
                        prop.basm = basm
                        prop.solve_speed(eq, beq)
                        external = prop.external
                    warm_c = _WARM.get((warm_key, "coupled")) if warm_key is not None else None
                    for _pass in range(4):
                        eq_c, beq_c, pe_c, pb_c, lines_c, info_c, qc = coupled_equilibrium(
                            cfg, asm, M, G, basm, beq["mass"], beq["G_body"], rho, g, warm=warm_c, external=external,
                            eq_e0=(eq if prop is None else None), eq_b0=beq)
                        if prop is None or not info_c["converged"]:
                            break
                        used = prop.state()                         # speed / resistances the equilibrium was solved with
                        prop.solve_speed(eq_c, beq_c)              # wetted areas at the coupled poses
                        if max(abs(prop.R_e - used["R_e"]), abs(prop.R_b - used["R_b"])) < 1e-3 * prop.T:
                            prop.restore(used)                      # report exactly what the converged equilibrium used
                            break
                        warm_c = qc
                    if prop is not None:
                        info_c["speed_m_s"] = prop.U
                    coupled = info_c
                    if info_c["converged"]:
                        if warm_key is not None:
                            _WARM[(warm_key, "coupled")] = qc
                        # replace both bodies' equilibria by the coupled ones (line forces included)
                        eq = eq_c
                        out["_eq"] = eq
                        out["equilibrium"].update(_exo_equilibrium_fields(asm, eq, cfg, rho, g))
                        out["stability_static"] = eqm.initial_stability(asm, eq)
                        out["stability_static"]["scope"] = ("STATIC initial stability of the floats-only buoyancy model (hydrostatic restoring only; "
                                                            "line springs are added in the wave model). Not wave behaviour, not a capsize limit.")
                        bres.update(_boat_equilibrium_fields(cfg, basm, beq_c, rho, g))
                        beq = beq_c
                        out["bodies"]["exo"]["pose"] = dict(R_world=pe_c["R_world"].tolist(), com_world=pe_c["com_world"].tolist(), G_body=pe_c["G_body"].tolist())
                        pb = dict(R_world=pb_c["R_world"].tolist(), com_world=pb_c["com_world"].tolist(), G_body=pb_c["G_body"].tolist(), yaw_rad=pb_c["yaw_rad"])
                        out["lines"] = lines_c
                        slack = [l["id"] for l in lines_c if l["slack"]]
                        out["lines_note"] = (f"coupled static equilibrium (buoyancy + weight + tension-only lines): boat shifted "
                                             f"{info_c['boat_shift_from_nominal']['dx_m']*1000:.0f} mm x, {info_c['boat_shift_from_nominal']['dy_m']*1000:.0f} mm y, "
                                             f"{info_c['boat_shift_from_nominal']['dyaw_deg']:.2f} deg yaw from the nominal berth; line tensions "
                                             + ", ".join(f"{l['id']} {l['tension_N']:.0f} N" for l in lines_c)
                                             + (f"; SLACK at rest: {', '.join(slack)}" if slack else "") + f"; residual {info_c['residual_relative']:.1e} of Mg")
                        if slack:
                            out["flags"].append(f"lines slack at the static equilibrium: {', '.join(slack)} (no stiffness in the wave model; check the arrangement)")
                        if info_c["all_lines_slack"]:
                            out["flags"].append("all lines slack: the boat's static position is undetermined (held at the nominal berth by a numerical centering spring)")
                    else:
                        out["flags"].append(f"coupled equilibrium did not converge (residual {info_c['residual_relative']:.1e}); showing independent flotations")
                except Exception as e:  # noqa: BLE001
                    out["flags"].append(f"coupled equilibrium failed ({type(e).__name__}: {e}); showing independent flotations")
            if prop is not None and (coupled is None or not coupled["converged"]):
                out["flags"].append("propulsion: the line arrangement cannot carry the thrust/drag forces (no static equilibrium): the "
                                    "bodies would move relative to each other until they touch; showing the no-thrust flotations")
            if coupled is None or not coupled["converged"]:
                pb = pose_boat(beq, hb["placement_in_exo_frame"])
                out["lines"] = line_geometry(hb, out["bodies"]["exo"]["pose"], pb)
                T0 = sum(l["vertical_component_N"] for l in out["lines"])
                out["lines_note"] = (f"independent flotations (lines NOT in the equilibria): nominal pretension vertical components sum to {T0:.0f} N "
                                     f"({100 * T0 / (M * g):.1f}% of the EXO weight)")
            bres["pose"] = pb
            out["coupled_equilibrium"] = coupled
            out["clearances"] = clearances(cfg, out["bodies"]["exo"]["pose"], pb, asm)
            out["flags"] += out["clearances"]["flags"]
            if coupled is not None:
                inter = [f for f in out["clearances"]["flags"] if f.startswith("INTERFERENCE")]
                coupled["interference"] = bool(inter)
                coupled["physical"] = bool(coupled.get("converged")) and not inter
                shift = coupled.get("boat_shift_from_nominal") or {}
                if inter and coupled.get("converged"):
                    out["flags"].append(f"coupled equilibrium exists only with the boat displaced {np.hypot(shift.get('dx_m', 0), shift.get('dy_m', 0)):.2f} m "
                                        "from the berth INTO the EXO structure (no contact model): not a usable arrangement for this load")
            out["_boat_eq"] = beq
            out["_boat_assembly"] = basm
            if warm_key is not None:
                _WARM[(warm_key, "boat")] = (beq["z_origin"], beq["phi"], beq["theta"])
        out["combined_note"] = ("Combined system = two bodies with assumed mass distributions, a proxy boat hull and an assumed berth "
                                "position. No combined-vessel capacity, limit or approval follows from it.")
    if prop is not None:
        out["propulsion"] = prop.summary(out.get("lines"), out.get("coupled_equilibrium"))
        if exo_only_prop and boat_on:
            out["propulsion"]["notes"].insert(0, "host boat included but no lines: thrust acts on the EXO alone, the boat is not pushed")
        if prop.unit["body"] == "BOAT" and exo_only_prop:
            out["not_computed"]["propulsion"] = ["boat engine with no lines: the EXO is not towed"]
        out["flags"].append(f"PROPULSION ON ({prop.unit_id} {100 * prop.frac:.0f} %): quasi-static thrust {prop.T:.0f} N, steady speed "
                            f"{prop.U:.2f} m/s ({prop.U / 0.514444:.1f} kn) from ASSUMED resistance coefficients; trim/heel/line tensions include it")
    return out


def strip_private(res):
    return {k: v for k, v in res.items() if not k.startswith("_")}


# ---------------------------------------------------------------- wave response set-up
def has_boat(res):
    return "boat" in (res.get("bodies") or {}) and res.get("_boat_eq") is not None


def hydro_specs(res, cfg, boat_resolution=None):
    """Body specs for exo01.hydro.compute_hydro_bodies (common world frame W)."""
    from .boat import surface_from_config
    eq = res["_eq"]
    specs = [dict(name="EXO", surfaces=res["_assembly"].surfaces, pose=res["bodies"]["exo"]["pose"], mass=eq["mass"])]
    if has_boat(res):
        hb = cfg["host_boat"]
        hull = surface_from_config(hb["buoyant_surface"], boat_resolution or dict(dx_max=0.25, ds_max=0.25))
        specs.append(dict(name="BOAT", vertices=hull.vertices, faces=hull.faces, pose=res["bodies"]["boat"]["pose"],
                          mass=res["_boat_eq"]["mass"]))
    return specs


def build_response(res, hydro, cfg, extra_stiffness=None):
    """Assemble the ResponseModel (6 DOF, or 12 DOF with the host boat) from an evaluated configuration and the BEM."""
    from .equilibrium import restoring_matrix
    from .response import ResponseModel, mass_matrix_6, stiffness_6, line_stiffness
    eq, asm = res["_eq"], res["_assembly"]
    if res["mass"]["inertia_com_kgm2"] is None:
        raise MissingInput("wave response", ["inertia tensor"])
    two = has_boat(res) and hydro.A.shape[1] == 12
    fb = res["equilibrium"]["freeboard"]
    floats = {s.id: dict(centre_body=list(s.centre), **fb["per_float"][s.id]) for s in asm.surfaces}
    if two:
        pose_e = res["bodies"]["exo"]["pose"]
    else:  # legacy single-body hydro: COM at the horizontal origin
        pose_e = dict(R_world=eq["R"].tolist(), com_world=[0.0, 0.0, eq["zG"]], G_body=eq["G_body"].tolist())
    corners = {}
    for i, p in enumerate(cfg["freeboard_points"]["lower_deck_corners"]):
        w = eq["R"] @ (np.asarray(p, float) - eq["G_body"])
        corners[f"lower_deck_corner_{i}"] = (list(p), float(w[2] + eq["zG"]))
    bodies = [dict(name="EXO", pose=pose_e, floats=floats, lower_deck_freeboard_min_m=fb["lower_deck_freeboard_min_m"],
                   deck_points=cfg["deck_acceleration_points"], deck_corners=corners)]
    M = mass_matrix_6(eq["mass"], res["mass"]["inertia_com_kgm2"], eq["R"])
    K = stiffness_6(restoring_matrix(eq["integrals"], eq["rho"], eq["g"], eq["zG"]), extra_stiffness)
    lines, line_B = [], []
    if two:
        beq = res["_boat_eq"]
        bm = res["bodies"]["boat"]["mass"]
        if bm["inertia_com_kgm2"] is None:
            raise MissingInput("wave response", ["boat inertia tensor"])
        pose_b = res["bodies"]["boat"]["pose"]
        Rb = np.asarray(pose_b["R_world"])
        Mb = mass_matrix_6(beq["mass"], bm["inertia_com_kgm2"], Rb)
        Kb = stiffness_6(restoring_matrix(beq["integrals"], beq["rho"], beq["g"], beq["zG"]))
        # boat restoring matrix is about its own (yawed) world axes: rotate by the placement yaw
        Rz_ = np.asarray(Rb) @ np.linalg.inv(beq["R"])     # = Rz(yaw)
        T6 = np.zeros((6, 6)); T6[:3, :3] = Rz_; T6[3:, 3:] = Rz_
        Kb = T6 @ Kb @ T6.T
        hbcfg = cfg["host_boat"]
        bpts = {"boat_aft_deck_centre": [0.3, 0.0, 0.78], "boat_roof_centre": [4.8, 0.0, 2.28], "boat_forward_terrace": [7.0, 0.0, 0.49]}
        bcorners = {f"boat_deck_edge_{i}": (list(p), float(fbv)) for i, (p, fbv) in
                    enumerate(zip(res["bodies"]["boat"]["equilibrium"]["deck_edge_points_m"], res["bodies"]["boat"]["equilibrium"]["deck_edge_freeboards_m"]))}
        bodies.append(dict(name="BOAT", pose=pose_b, deck_points=bpts, deck_corners=bcorners))
        bodies[0]["relative_points"] = _relative_points(cfg, res, pose_e, pose_b)
        M = np.block([[M, np.zeros((6, 6))], [np.zeros((6, 6)), Mb]])
        K = np.block([[K, np.zeros((6, 6))], [np.zeros((6, 6)), Kb]])
        # equilibrium tensions feed the line stiffness; a line slack at rest has no linear stiffness
        lines = [dict(l, body_i=0, body_j=1, stiffness_N_per_m=(0.0 if l.get("slack") else l["stiffness_N_per_m"]),
                      stiffness_N_per_m_nominal=l["stiffness_N_per_m"]) for l in res.get("lines", [])]
        Kl, line_B = line_stiffness(lines, [pose_e["com_world"], pose_b["com_world"]])
        K = K + Kl
    return ResponseModel(hydro, M, K, eq["rho"], eq["g"], cfg["environment"].get("water_depth_m"), bodies, lines, line_B)


def _relative_points(cfg, res, pose_e, pose_b):
    """Point pairs (EXO body point, boat body point) whose relative motion is compared with the still-water clearance:
    hull topsides vs float inner face (lateral, three stations in the overlap) and cabin roof vs header underside (vertical)."""
    from .twobody import to_world
    hb = cfg["host_boat"]
    cr = hb["clearance_reference"]
    cl = res.get("clearances") or {}
    ce, Ge = np.asarray(pose_e["com_world"], float), np.asarray(pose_e["G_body"], float)
    pts = []
    lat = cl.get("lateral_clearance_to_float_inner_face_m") or {}
    for x_mm, b_mm, _ in hb["buoyant_surface"]["stations_mm"]:
        for sgn, key in ((1, "port"), (-1, "starboard")):
            pb = [x_mm / 1000.0, sgn * b_mm / 1000.0, 0.3]
            w = to_world(pose_b, pb)
            if 1.0 <= w[0] <= 5.0 and lat.get(key) is not None:
                pe = [float(w[0] - ce[0] + Ge[0]), sgn * cr["exo_float_inner_face_y_m"], -0.30]
                pts.append(dict(name=f"hull_vs_float_{key}_x{w[0]:.1f}", body_i=0, body_j=1, p_i=pe, p_j=pb, axis="y",
                                still_clearance_m=float(lat[key])))
    vert = (cl.get("vertical_clearance_m") or {}).get("exo_header_underside")
    if vert is not None:
        best = None
        for x_mm, _, h_mm in cr["boat_cabin_stations_mm"]:
            pb = [x_mm / 1000.0, 0.0, h_mm / 1000.0]
            w = to_world(pose_b, pb)
            if 2.05 <= w[0] <= 5.0 and (best is None or h_mm > best[0]):
                best = (h_mm, pb, w)
        if best:
            pe = [float(best[2][0] - ce[0] + Ge[0]), 0.0, cr["exo_header_underside_z_m"]]
            pts.append(dict(name="roof_vs_header", body_i=0, body_j=1, p_i=pe, p_j=best[1], axis="z", still_clearance_m=float(vert)))
    return pts


HYDRO_DEFAULTS = dict(omega_min=0.5, omega_max=6.0, omega_step=0.15, panel_size_m=0.12, lid=True, refine_bands=True,
                      two_body_panel_exo_m=0.20, two_body_panel_boat_m=0.30, two_body_omega_max=5.0)


def hydro_for(res, cfg, omegas, headings, settings=None, cache_only=False, allow_pose_reuse=False):
    """BEM coefficients for an evaluated configuration: single body (EXO) or EXO + boat, per `settings`.

    The BEM is cached per POSE (attitude + draught of each body), not per mass distribution: moving a mass that leaves
    the pose unchanged is an exact cache hit (reference-point transform). With allow_pose_reuse, a cached BEM of a
    nearby pose (within hydro.POSE_TOL) is used when the exact pose has none, flagged in meta["pose_reuse"]."""
    from .hydro import (compute_hydro, compute_hydro_bodies, HydroNotComputed, single_signature, multi_signature, canonical_eq,
                        canonical_specs, multi_pose, find_reusable_pose_tiered, _angles)
    s = dict(HYDRO_DEFAULTS, **(settings or {}))
    env = cfg["environment"]
    omegas = np.asarray(omegas, float)
    depth = env.get("water_depth_m")
    depth = None if depth in (None, np.inf) else float(depth)
    refine = s["refine_bands"] and 0.05
    if has_boat(res):
        om2 = omegas[omegas <= s["two_body_omega_max"] + 1e-9]
        specs = hydro_specs(res, cfg, dict(dx_max=s["two_body_panel_boat_m"], ds_max=s["two_body_panel_boat_m"]))
        kw = dict(panel_sizes=[s["two_body_panel_exo_m"], s["two_body_panel_boat_m"]], use_lid=s["lid"], refine_bands=s["refine_bands"])
        try:
            return compute_hydro_bodies(specs, om2, headings, env["rho_kg_m3"], env["g_m_s2"], depth, cache_only=cache_only, **kw)
        except HydroNotComputed:
            if not allow_pose_reuse:
                raise
            sig = multi_signature(canonical_specs(specs), om2, env["rho_kg_m3"], env["g_m_s2"], depth, kw["panel_sizes"], s["lid"], refine)
            hit, tier = find_reusable_pose_tiered("multi", sig, multi_pose(canonical_specs(specs)), headings)
            if hit is None:
                raise
            return compute_hydro_bodies(specs, om2, headings, env["rho_kg_m3"], env["g_m_s2"], depth, cache_only=True,
                                        pose_from=dict(pose=hit[1]["pose"], key=hit[1].get("key"), tier=tier), **kw)
    surfaces, eq = res["_assembly"].surfaces, res["_eq"]
    kw = dict(use_lid=s["lid"], refine_bands=s["refine_bands"])
    try:
        return compute_hydro(surfaces, eq, omegas, headings, env["rho_kg_m3"], env["g_m_s2"], depth, s["panel_size_m"], cache_only=cache_only, **kw)
    except HydroNotComputed:
        if not allow_pose_reuse:
            raise
        sig = single_signature(surfaces, omegas, env["rho_kg_m3"], env["g_m_s2"], depth, s["panel_size_m"], s["lid"], refine)
        ce = canonical_eq(eq)
        phi, theta = _angles(ce["R"])
        hit, tier = find_reusable_pose_tiered("single", sig, {"EXO": dict(phi=phi, theta=theta, z=float(ce["zG"]))}, headings)
        if hit is None:
            raise
        return compute_hydro(surfaces, eq, omegas, headings, env["rho_kg_m3"], env["g_m_s2"], depth, s["panel_size_m"], cache_only=True,
                             pose_from=dict(hit[1]["pose"]["EXO"], key=hit[1].get("key"), exc_keys=hit[1].get("exc_keys"), tier=tier), **kw)
