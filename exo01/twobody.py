"""Host boat as a second floating body: its own still-water equilibrium, common-world poses, mooring-line
geometry and clearance checks against the EXO frame. Dynamics (12 DOF) are in response.py / hydro.py.

Common world frame W: Z up, still waterline at Z = 0, horizontal axes = EXO CAD axes with the EXO CAD origin at
(0, 0) horizontally (the EXO COM sits at its CAD (x, y)). Each body: w = R_w (p - G) + c_w, with p in the body's
own CAD frame, G its COM (body frame) and c_w the world position of its COM.
"""
from __future__ import annotations

import json

import numpy as np

from . import equilibrium as eqm
from .boat import surface_from_config
from .buoyancy import BuoyantAssembly
from .mass import boat_items_from_config, mass_properties, aggregate_by_category
from .units import deg

_BOAT_ASM = {}


def boat_assembly(hb, resolution=None):
    key = json.dumps([hb["buoyant_surface"], resolution], sort_keys=True)
    if key not in _BOAT_ASM:
        if len(_BOAT_ASM) > 8:
            _BOAT_ASM.clear()
        _BOAT_ASM[key] = BuoyantAssembly([surface_from_config(hb["buoyant_surface"], resolution)])
    return _BOAT_ASM[key]


def Rz(psi):
    c, s = np.cos(psi), np.sin(psi)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def pose_exo(eq):
    """EXO body -> world W."""
    G = eq["G_body"]
    return dict(R_world=eq["R"].tolist(), com_world=[float(G[0]), float(G[1]), float(eq["zG"])], G_body=G.tolist())


def pose_boat(eq_b, placement):
    """Boat body -> world W: horizontal placement (x, y, yaw) of the boat CAD frame in the EXO CAD frame, vertical
    position and attitude from the boat's own flotation."""
    psi = np.radians(placement.get("yaw_deg", 0.0))
    G = eq_b["G_body"]
    Rw = Rz(psi) @ eq_b["R"]
    c = Rz(psi) @ np.array([G[0], G[1], 0.0]) + np.array([placement["x_m"], placement["y_m"], 0.0])
    c[2] = eq_b["zG"]
    return dict(R_world=Rw.tolist(), com_world=c.tolist(), G_body=G.tolist(), yaw_rad=float(psi))


def to_world(pose, p):
    R = np.asarray(pose["R_world"])
    return R @ (np.asarray(p, float) - np.asarray(pose["G_body"])) + np.asarray(pose["com_world"])


def evaluate_boat(cfg, rho, g, resolution=None, warm=None):
    hb = cfg["host_boat"]
    items = boat_items_from_config(cfg)
    mp = mass_properties(items, strict=False)
    mp["by_category_kg"] = aggregate_by_category(items)
    out = dict(id=hb["id"], name=hb["name"], mass=mp, status={}, not_computed={},
               mass_note=f"{hb['mass_source']}; alternatives {hb.get('mass_alternatives_kg')} kg. Not the measured current boat.",
               hull_note=hb["buoyant_surface"]["source"], placement=hb["placement_in_exo_frame"])
    asm = boat_assembly(hb, resolution)
    out["buoyant_volume_total_m3"] = asm.max_volume
    if rho is not None and mp["total_listed_mass_kg"] > 0:
        out["level_keel_screening"] = eqm.level_keel_screening(asm, mp["total_listed_mass_kg"], rho)
        # draft of the proxy hull at the package's drawn waterline (z=0, level): what mass would float there
        I0 = asm.integrals(np.eye(3), np.zeros(3), 0.0)
        out["proxy_hull_at_drawn_waterline"] = dict(displaced_volume_m3=I0["V"], equivalent_mass_kg=I0["V"] * rho,
                                                    note="mass the proxy hull would need to float at the package's z=0 waterline; "
                                                         "compare with the 2.1-3.0 t references -> hull form/datum consistency check")
    if mp["com_m"] is None:
        out["not_computed"]["centre_of_mass"] = [f"COM of {x}" for x in mp["missing_com"]]
        out["status"]["equilibrium"] = "not_computed"
        return out, asm, None
    if rho is None:
        out["not_computed"]["equilibrium"] = ["water density is null"]
        out["status"]["equilibrium"] = "not_computed"
        return out, asm, None
    M, G = mp["total_mass_kg"], np.array(mp["com_m"])
    try:
        eq = eqm.equilibrium(asm, M, G, rho, g, warm_start=warm)
    except eqm.NoEquilibrium as e:
        out["status"]["equilibrium"] = "no_feasible_equilibrium"
        out["equilibrium"] = dict(feasible=False, reason=str(e), best_point=getattr(e, "best", None))
        return out, asm, None
    out.update(boat_equilibrium_fields(cfg, asm, eq, rho, g))
    return out, asm, eq


def boat_equilibrium_fields(cfg, asm, eq, rho, g):
    hb = cfg["host_boat"]
    out = {}
    G = np.asarray(eq["G_body"])
    I = eq["integrals"]
    st = eqm.initial_stability(asm, eq)
    R, zG = eq["R"], eq["zG"]
    V = asm.all_tris.reshape(-1, 3)
    w = (V - G) @ R.T + np.array([0, 0, zG])
    draft = float(-w[:, 2].min())
    deck_z = hb["standing_surfaces"]["boat_aft_deck"]["z_m"]
    # deck-edge freeboard at the four "corners" of the deck outline (stern and midship, port/starboard)
    corners = [[0.3, 1.34, deck_z], [0.3, -1.34, deck_z], [4.8, 1.49, deck_z], [4.8, -1.49, deck_z], [7.4, 1.3, deck_z], [7.4, -1.3, deck_z]]
    fb = [float((R @ (np.array(p) - G))[2] + zG) for p in corners]
    out["status"] = {"equilibrium": "solved"}
    out["equilibrium"] = dict(
        feasible=True, heel_deg=deg(eq["phi"]), trim_deg=deg(eq["theta"]), heel_rad=eq["phi"], trim_rad=eq["theta"],
        sign_convention="boat frame: heel right-handed about +X (stern->bow), + = port side up; trim right-handed about +Y (port), + = bow down",
        com_height_above_waterline_m=zG, displaced_volume_m3=I["V"], displaced_mass_kg=I["V"] * rho,
        centre_of_buoyancy_body_m=(R.T @ (I["B"] - np.array([0.0, 0.0, zG])) + G).tolist(), centre_of_mass_body_m=G.tolist(),
        residuals=eqm.residuals(asm, eq), waterplane_area_m2=I["Awp"],
        draft_hull_proxy_m=draft, draft_note="hull proxy only (keel excluded, +~0.22 m); catalogue draft 0.75 m incl. keel",
        deck_edge_freeboard_min_m=min(fb), deck_edge_freeboards_m=fb, deck_edge_points_m=corners,
        waterline_z_in_boat_frame_m=float(-(zG - (R @ G)[2])) if abs(eq["phi"]) + abs(eq["theta"]) < 1e-9 else None,
        solver=dict(n_evaluations=eq["n_evaluations"], newton_converged=eq["newton_converged"], residual_relative=eq["residual_relative"]))
    out["stability_static"] = st
    out["flags"] = []
    if min(fb) < 0:
        out["flags"].append("boat deck edge below the waterline at this loading: proxy hull/COM assumptions not credible")
    return out


# ---------------------------------------------------------------- lines and clearances
def line_geometry(hb, pose_e, pose_b):
    lines = []
    d = hb.get("line_defaults", {})
    for ln in hb.get("lines", []):
        a = to_world(pose_e, ln["exo_point_m"])
        b = to_world(pose_b, ln["boat_point_m"])
        L = float(np.linalg.norm(b - a))
        u = (b - a) / L if L > 0 else np.zeros(3)
        T0 = float(ln.get("pretension_N", d.get("pretension_N", 0.0)))
        k = float(ln.get("stiffness_N_per_m", d.get("stiffness_N_per_m", 0.0)))
        s = element_sign(ln)
        lines.append(dict(id=ln["id"], kind=ln.get("kind", "line"), a_world=a.tolist(), b_world=b.tolist(), length_m=L, unit=u.tolist(),
                          pretension_N=-T0 if s < 0 else T0, tension_N=-T0 if s < 0 else T0, slack=False, nominal_pretension_N=T0,
                          stiffness_N_per_m=k, vertical_component_N=float(T0 * abs(u[2]))))
    return lines


def clearances(cfg, pose_e, pose_b, exo_assembly):
    """Geometric clearances between the boat proxy and the EXO frame at the still-water poses (negative = interference)."""
    hb = cfg["host_boat"]
    cr = hb["clearance_reference"]
    out = {}
    # --- vertical: boat roof line vs EXO header / observation deck / panel undersides, by x overlap in world
    roof = [(x / 1000.0, h / 1000.0) for x, b, h in cr["boat_cabin_stations_mm"]]
    roof_world = [to_world(pose_b, [x, 0.0, h]) for x, h in roof]
    def exo_z(x_world, z_body):   # world z of an EXO point at CAD (x_world-ish, 0, z_body): use the inverse of the EXO pose horizontally ~ small angles
        return float(to_world(pose_e, [x_world, 0.0, z_body])[2])
    checks = {"exo_header_underside": (cr["exo_header_underside_z_m"], [2.1, 3.525, 4.95]),
              "exo_observation_deck_underside": (cr["exo_observation_deck_underside_z_m"], [2.1, 3.525]),
              "exo_panel_underside": (cr["exo_panel_underside_z_m"], [3.525, 5.585])}
    vert = {}
    for name, (zb, xr) in checks.items():
        xs = sorted(xr)
        worst = None
        for rw in roof_world:
            if xs[0] - 0.05 <= rw[0] <= xs[-1] + 0.05:
                c = exo_z(rw[0], zb) - rw[2]
                if worst is None or c < worst:
                    worst = c
        vert[name] = None if worst is None else float(worst)
    out["vertical_clearance_m"] = vert
    # --- lateral: boat hull half-beam vs float inner faces, over the x-overlap with the floats (0.5..5.1 in EXO CAD)
    stations = hb["buoyant_surface"]["stations_mm"]
    port = stbd = None
    for x, b, rise in stations:
        for sgn in (+1, -1):
            w = to_world(pose_b, [x / 1000.0, sgn * b / 1000.0, 0.3])          # hull side near the waterline/topsides
            if 0.5 <= w[0] <= 5.1:
                fl = to_world(pose_e, [w[0], sgn * cr["exo_float_inner_face_y_m"], -0.30])
                c = (fl[1] - w[1]) * sgn
                if sgn > 0:
                    port = c if port is None else min(port, c)
                else:
                    stbd = c if stbd is None else min(stbd, c)
    out["lateral_clearance_to_float_inner_face_m"] = dict(port=port, starboard=stbd,
                                                          note="boat topsides at the station half-beam vs the float proxy inner face, over the overlapping x-range")
    # --- longitudinal: boat transom vs the EXO rear deck plate forward edge (x = 2.1)
    transom = to_world(pose_b, [0.0, 0.0, cr["boat_deck_z_m"]])
    deck_edge = to_world(pose_e, [cr["exo_rear_deck_plate_x_range_m"][1], 0.0, 0.0])
    out["transom_to_rear_deck_plate_m"] = float(transom[0] - deck_edge[0])
    # --- waterline levels
    out["relative_levels_m"] = dict(exo_deck_datum_above_wl=float(to_world(pose_e, [2.1, 0.0, 0.0])[2]),
                                    boat_deck_above_wl=float(to_world(pose_b, [0.3, 0.0, cr["boat_deck_z_m"]])[2]))
    flags = []
    for k, v in vert.items():
        if v is not None and v < 0:
            flags.append(f"INTERFERENCE: boat roof above the {k.replace('_', ' ')} by {-v:.2f} m at the assumed placement")
        elif v is not None and v < 0.1:
            flags.append(f"tight: {v:.2f} m under the {k.replace('_', ' ')}")
    for side, v in (("port", port), ("starboard", stbd)):
        if v is not None and v < 0:
            flags.append(f"INTERFERENCE: boat hull overlaps the {side} float by {-v:.2f} m")
        elif v is not None and v < 0.1:
            flags.append(f"tight: {v:.2f} m between the boat hull and the {side} float")
    if out["transom_to_rear_deck_plate_m"] < 0:
        flags.append(f"INTERFERENCE: boat transom {-out['transom_to_rear_deck_plate_m']:.2f} m over the EXO rear deck plate")
    out["flags"] = flags
    return out


# ---------------------------------------------------------------- coupled static equilibrium with tension-only lines
ELEMENT_KINDS = {"line": +1, "fender": -1, "strut": 0}
# sign of the admissible force: line = tension only (T >= 0), fender = compression only (T <= 0, e.g. a push bar or a
# fender between the EXO rear deck edge and the boat's transom), strut = bilateral (a rigid or bolted link)


def element_sign(ln):
    kind = str(ln.get("kind", "line")).lower()
    if kind not in ELEMENT_KINDS:
        raise ValueError(f"line {ln.get('id')}: unknown kind {kind!r} (line, fender, strut)")
    return ELEMENT_KINDS[kind]


def _line_forces(hb, lines_cfg, pose_e, pose_b, L0, k, active=None):
    """World attachment points, lengths, unit vectors and element forces (T > 0 tension pulling the bodies together,
    T < 0 compression pushing them apart).
    line: T = max(0, k (L - L0)); fender: T = min(0, k (L - L0)); strut: T = k (L - L0). With an `active` mask
    (active-set solve) the active unilateral elements are treated as bilateral springs (the sign is checked by the
    outer loop) and the inactive ones carry nothing."""
    out = []
    for i, (ln, l0, kk) in enumerate(zip(lines_cfg, L0, k)):
        a = to_world(pose_e, ln["exo_point_m"])
        b = to_world(pose_b, ln["boat_point_m"])
        s = element_sign(ln)
        if s < 0 and ln.get("_u0") is not None:
            # fender: signed penetration along its nominal axis, so that a transom pushed past the contact point keeps
            # compressing instead of 'reappearing' as a free gap on the other side
            u = np.asarray(ln["_u0"], float)
            L = float((b - a) @ u)
        else:
            L = float(np.linalg.norm(b - a))
            u = (b - a) / L if L > 1e-12 else np.zeros(3)
        ext = kk * (L - l0)
        if active is None:
            T = ext if s == 0 else (max(0.0, ext) if s > 0 else min(0.0, ext))
        else:
            T = ext if (active[i] or s == 0) else 0.0
        slack = (T == 0.0) if s != 0 else False
        out.append(dict(id=ln["id"], a=a, b=b, L=L, u=u, T=T, slack=slack, L0=l0, k=kk, extension_N=ext, sign=s, kind=ln.get("kind", "line")))
    return out


def coupled_equilibrium(cfg, exo_asm, M_e, G_e, boat_asm, M_b, G_b, rho, g, warm=None, tol=1e-9, max_iter=40, external=None,
                        eq_e0=None, eq_b0=None):
    """Static equilibrium of EXO + boat with tension-only line springs.

    Unknowns q = [zG_e, phi_e, theta_e, dx_b, dy_b, dpsi_b, zG_b, phi_b, theta_b]: the EXO keeps its horizontal
    position and heading (it defines the world frame); the boat may shift/yaw from the nominal berth placement.
    Equations: EXO force/moment balance in all 6 components (buoyancy + weight + line forces), boat vertical force
    and heel/pitch moments (its horizontal balance is the EXO's with opposite sign: internal forces).
    Elements (kind): "line" = tension-only spring (T = max(0, k (L - L0)), L0 = L_nominal - T0/k so it carries the
    nominal pretension T0 at the nominal berth); "fender" = compression-only (push bar / fender between the two bodies,
    T = min(0, k (L - L0)), L0 = L_nominal + T0/k: preload T0 in compression, T0 = 0 just touching); "strut" = bilateral
    spring (rigid link in the limit k -> large).
    Newton with analytic hydrostatic Jacobian blocks and finite-difference line terms; backtracking line search.
    If every line is slack the boat's horizontal position is undetermined: a weak numerical centering spring
    (1 N/m, 1 N m/rad) holds it at the nominal placement and the result is flagged.
    external: optional callable (pose_e, pose_b) -> (F_e, M_e, F_b, M_b): world-frame external forces and moments about
    each COM (thrust, drag). Their in-plane resultant on the whole system must vanish (steady state) or no static
    equilibrium exists; the solver reports the net in-plane external force so the caller can check.
    """
    hb = cfg["host_boat"]
    pl = hb["placement_in_exo_frame"]
    d = hb.get("line_defaults", {})
    lines_cfg = hb.get("lines", [])
    k = np.array([float(l.get("stiffness_N_per_m", d.get("stiffness_N_per_m", 0.0))) for l in lines_cfg])
    T0 = np.array([float(l.get("pretension_N", d.get("pretension_N", 0.0))) for l in lines_cfg])
    # independent flotations (start point) and nominal line lengths -> L0
    if eq_e0 is None:
        eq_e0 = eqm.equilibrium(exo_asm, M_e, G_e, rho, g)
    if eq_b0 is None:
        eq_b0 = eqm.equilibrium(boat_asm, M_b, G_b, rho, g)
    pose_e0, pose_b0 = pose_exo(eq_e0), pose_boat(eq_b0, pl)
    Lnom = np.array([np.linalg.norm(to_world(pose_b0, l["boat_point_m"]) - to_world(pose_e0, l["exo_point_m"])) for l in lines_cfg])
    # fenders keep their nominal axis (unit vector at the independent flotations) as the direction of contact
    lines_cfg = [dict(l, _u0=((to_world(pose_b0, l["boat_point_m"]) - to_world(pose_e0, l["exo_point_m"])) / max(ln_, 1e-12)).tolist())
                 if element_sign(l) < 0 else l for l, ln_ in zip(lines_cfg, Lnom)]
    signs = np.array([element_sign(l) for l in lines_cfg], float) if lines_cfg else np.zeros(0)
    # lines and struts: unstretched length L0 = L_nominal - T0/k (pretension T0 at the nominal berth);
    # fenders: contact length L0 = L_nominal + T0/k (preload T0 in compression at the nominal berth; T0 = 0 -> just touching)
    L0 = Lnom - np.where(k > 0, np.where(signs < 0, -1.0, 1.0) * T0 / np.maximum(k, 1e-12), 0.0)
    yaw0 = np.radians(pl.get("yaw_deg", 0.0))
    x0, y0 = pl["x_m"], pl["y_m"]
    scale = np.array([M_e * g] * 6 + [M_b * g] * 3)
    centering = 1.0        # N/m and N m/rad: numerical only, see docstring

    def poses(q):
        Re = eqm.attitude(q[1], q[2])
        pe = dict(R_world=Re, com_world=np.array([G_e[0], G_e[1], q[0]]), G_body=np.asarray(G_e))
        psi = yaw0 + q[5]
        Rbl = eqm.attitude(q[7], q[8])
        Rb = Rz(psi) @ Rbl
        cb = Rz(psi) @ np.array([G_b[0], G_b[1], 0.0]) + np.array([x0 + q[3], y0 + q[4], 0.0])
        cb[2] = q[6]
        pb = dict(R_world=Rb, com_world=cb, G_body=np.asarray(G_b), yaw_rad=psi)
        return pe, pb, Re, Rbl, psi

    ACTIVE = {"mask": None}          # active-set mask (None = tension-only kink model)

    def coupling_part(q, pe, pb, psi):
        """Line, external and centering contributions (no hydrostatic integrals: cheap, used for the FD Jacobian block)."""
        lf = _line_forces(hb, lines_cfg, pe, pb, L0, k, ACTIVE["mask"])
        Fe = np.zeros(3); Me = np.zeros(3); Fb = np.zeros(3); Mb = np.zeros(3)
        for l in lf:
            f = l["T"] * l["u"]
            Fe += f; Me += np.cross(l["a"] - pe["com_world"], f)
            Fb -= f; Mb += np.cross(l["b"] - pb["com_world"], -f)
        if external is not None:
            Fxe, Mxe, Fxb, Mxb = external(pe, pb)
            Fe = Fe + np.asarray(Fxe, float); Me = Me + np.asarray(Mxe, float)
            Fb = Fb + np.asarray(Fxb, float); Mb = Mb + np.asarray(Mxb, float)
        all_slack = all(l["slack"] for l in lf) or not lf
        # numerical centering (1 N/m, 1 N m/rad): always on, so that an in-plane mode no element restrains (sway with
        # fenders only, everything when all lines are slack) stays determined; negligible against any real line force
        Fb[:2] += -centering * q[3:5]; Fe[:2] -= -centering * q[3:5]
        Mb[2] += -centering * q[5]
        return np.array([Fe[0], Fe[1], Fe[2], Me[0], Me[1], Me[2], Fb[2], Mb[0], Mb[1]]), lf, all_slack

    def coupling_only(q):
        pe, pb, Re, Rbl, psi = poses(q)
        return coupling_part(q, pe, pb, psi)[0]

    def hydro_jacobian(q, Ie, Ib, psi, Wb):
        """Analytic block-diagonal Jacobian of the hydrostatic + gravity wrenches w.r.t. q (restoring matrices)."""
        J = np.zeros((9, 9))
        Ce = eqm.restoring_matrix(Ie, rho, g, q[0])                     # d(Fz,Mx,My)/d(z, world-x rot, world-y rot) = -C
        Cb = eqm.restoring_matrix(Ib, rho, g, q[6])
        # phi is a rotation about the body-tilted x axis (cos(theta) x_world - sin(theta) z_world); theta is about world y
        J[2:5, 0] = -Ce[:, 0]; J[2:5, 1] = -Ce[:, 1] * np.cos(q[2]); J[2:5, 2] = -Ce[:, 2]
        Jb = np.zeros((3, 3))
        Jb[:, 0] = -Cb[:, 0]; Jb[:, 1] = -Cb[:, 1] * np.cos(q[8]); Jb[:, 2] = -Cb[:, 2]
        Rzp = Rz(psi)[:2, :2]
        J[6, 6:9] = Jb[0, :]
        J[7:9, 6:9] = Rzp @ Jb[1:3, :]
        dR = np.array([[-np.sin(psi), -np.cos(psi)], [np.cos(psi), -np.sin(psi)]])
        J[7:9, 5] = dR @ np.array([Wb[1], Wb[2]])
        return J

    def residual(q, want_lines=False):
        pe, pb, Re, Rbl, psi = poses(q)
        We, Ie = eqm._wrench_R(exo_asm, M_e, np.asarray(G_e), rho, g, q[0], Re)          # (Fz, Mx, My) hydro+gravity
        Wb, Ib = eqm._wrench_R(boat_asm, M_b, np.asarray(G_b), rho, g, q[6], Rbl)        # in the boat's yawed frame
        Mb_xy = Rz(psi)[:2, :2] @ np.array([Wb[1], Wb[2]])
        Lc, lf, all_slack = coupling_part(q, pe, pb, psi)
        R = Lc + np.array([0.0, 0.0, We[0], We[1], We[2], 0.0, Wb[0], Mb_xy[0], Mb_xy[1]])
        if want_lines:
            return R, lf, (Ie, Ib, Re, Rbl, psi, pe, pb, all_slack, Wb)
        return R

    def _residual_legacy(q, want_lines=False):
        pe, pb, Re, Rbl, psi = poses(q)
        We, Ie = eqm._wrench_R(exo_asm, M_e, np.asarray(G_e), rho, g, q[0], Re)          # (Fz, Mx, My) hydro+gravity
        Wb, Ib = eqm._wrench_R(boat_asm, M_b, np.asarray(G_b), rho, g, q[6], Rbl)        # in the boat's yawed frame
        Mb_xy = Rz(psi)[:2, :2] @ np.array([Wb[1], Wb[2]])
        lf = _line_forces(hb, lines_cfg, pe, pb, L0, k, ACTIVE["mask"])
        Fe = np.zeros(3); Me = np.zeros(3); Fb = np.zeros(3); Mb = np.zeros(3)
        for l in lf:
            f = l["T"] * l["u"]                        # on the EXO (toward the boat)
            Fe += f; Me += np.cross(l["a"] - pe["com_world"], f)
            Fb -= f; Mb += np.cross(l["b"] - pb["com_world"], -f)
        if external is not None:
            Fxe, Mxe, Fxb, Mxb = external(pe, pb)
            Fe = Fe + np.asarray(Fxe, float); Me = Me + np.asarray(Mxe, float)
            Fb = Fb + np.asarray(Fxb, float); Mb = Mb + np.asarray(Mxb, float)
        all_slack = all(l["slack"] for l in lf) or not lf
        Fb[:2] += -centering * q[3:5]; Fe[:2] -= -centering * q[3:5]          # numerical centering, see coupling_part
        Mb[2] += -centering * q[5]
        R = np.array([Fe[0], Fe[1], We[0] + Fe[2], We[1] + Me[0], We[2] + Me[1], Me[2],
                      Wb[0] + Fb[2], Mb_xy[0] + Mb[0], Mb_xy[1] + Mb[1]])
        if want_lines:
            return R, lf, (Ie, Ib, Re, Rbl, psi, pe, pb, all_slack, Wb)
        return R

    q_cold = np.zeros(9)
    q_cold[0], q_cold[1], q_cold[2] = eq_e0["zG"], eq_e0["phi"], eq_e0["theta"]
    q_cold[6], q_cold[7], q_cold[8] = eq_b0["zG"], eq_b0["phi"], eq_b0["theta"]
    n_eval = 0

    def newton(q, R, r, lf, aux, jac="split"):
        """Damped Newton; returns (q, R, r, lf, aux, converged).
        jac="split": analytic hydrostatic Jacobian (restoring matrices from the integrals already computed) + central
        differences of the cheap coupling part only (lines, external, centering) -> 2 hydrostatic integrals per iteration
        instead of 38. jac="fd": central differences of the full residual (fallback)."""
        nonlocal n_eval
        converged = r < tol
        h = np.array([1e-4, 1e-4, 1e-4, 1e-3, 1e-3, 1e-3, 1e-4, 1e-4, 1e-4])

        def jacobian(mode):
            nonlocal n_eval
            J = np.zeros((9, 9))
            if mode == "split":
                Ie, Ib, Re, Rbl, psi, pe, pb, all_slack, Wb = aux
                J = hydro_jacobian(q, Ie, Ib, psi, Wb)
                for j in range(9):
                    e = np.zeros(9); e[j] = h[j]
                    J[:, j] += (coupling_only(q + e) - coupling_only(q - e)) / (2 * h[j])
            else:
                for j in range(9):
                    e = np.zeros(9); e[j] = h[j]
                    Rp = residual(q + e); Rm = residual(q - e)
                    n_eval += 2
                    J[:, j] = (Rp - Rm) / (2 * h[j])
            return J

        def step(J):
            nonlocal q, R, r, lf, aux, n_eval
            try:
                dq = np.linalg.solve(J, -R)
            except np.linalg.LinAlgError:
                return False
            big = max(abs(dq[0]) / 0.2, abs(dq[6]) / 0.2, np.abs(dq[[1, 2, 7, 8]]).max() / 0.1, np.abs(dq[3:5]).max() / 0.3, abs(dq[5]) / 0.1, 1.0)
            a = 1.0 / big
            while a > 1e-4 / big:
                qn = q + a * dq
                Rn, lfn, auxn = residual(qn, True)
                n_eval += 1
                rn = np.linalg.norm(Rn / scale)
                if rn < r:
                    q, R, r, lf, aux = qn, Rn, rn, lfn, auxn
                    return True
                a *= 0.5
            return False

        mode = jac
        for _ in range(max_iter):
            if converged:
                break
            improved = step(jacobian(mode))
            if not improved and mode == "split":
                improved = step(jacobian("fd"))        # the approximate phi columns can stall near the solution: one exact step
            if not improved:
                break
            converged = r < tol
        return q, R, r, lf, aux, converged

    def start_point():
        q = q_cold.copy()
        R, lf, aux = residual(q, True)
        r = np.linalg.norm(R / scale)
        if warm is not None and len(warm) == 9:
            # a warm start from a previous solve of a DIFFERENT state (other masses, berth, lines) can be far off: use it
            # only when it is closer to equilibrium than the cold start (independent flotations)
            qw = np.array(warm, float)
            Rw, lfw, auxw = residual(qw, True)
            rw = np.linalg.norm(Rw / scale)
            if np.isfinite(rw) and rw < r:
                q, R, lf, aux, r = qw, Rw, lfw, auxw, rw
        return q, R, r, lf, aux

    # ---- 1. active-set solve: lines in the set are bilateral springs (smooth problem, quadratic convergence); a line
    #         whose tension comes out negative leaves the set, a line out of the set whose extension turns positive
    #         joins it; the kink of the tension-only law is never inside a Newton solve
    q, R, r, lf, aux = start_point()
    n_eval += 1
    active = np.array([(l["sign"] == 0) or (l["sign"] * l["extension_N"] > 0) for l in lf]) if lf else np.zeros(0, bool)
    converged = False
    history = []
    for sweep in range(2 * max(len(lf), 1) + 2):
        ACTIVE["mask"] = active
        R, lf, aux = residual(q, True)
        r = np.linalg.norm(R / scale)
        q, R, r, lf, aux, conv = newton(q, R, r, lf, aux)
        tol_f = 1e-9 * max(1.0, M_e * g)
        drop = np.array([bool(active[i]) and l["sign"] != 0 and l["sign"] * l["T"] < -tol_f for i, l in enumerate(lf)])
        add = np.array([(not active[i]) and l["sign"] != 0 and l["sign"] * l["extension_N"] > tol_f for i, l in enumerate(lf)])
        history.append(dict(sweep=sweep, active=active.tolist(), converged=bool(conv), residual=float(r)))
        if conv and not drop.any() and not add.any():
            converged = True
            break
        new_active = (active & ~drop) | add
        if (new_active == active).all() and not conv:
            break                                  # Newton failed with a consistent set: fall back below
        active = new_active
    ACTIVE["mask"] = None
    # ---- 2. verification with the tension-only law (and fallback: damped Newton on the kink model as before)
    R, lf, aux = residual(q, True)
    r = np.linalg.norm(R / scale)
    if not (converged and r < 1e-7):
        q2, R2, r2, lf2, aux2 = start_point()
        if r2 < r:
            q, R, r, lf, aux = q2, R2, r2, lf2, aux2
        q, R, r, lf, aux, converged = newton(q, R, r, lf, aux, jac="fd")
    fallback = None
    if not converged and r >= 1e-7:
        # Newton stalled (stiff lines, several slack/taut kinks): finish with a trust-region least-squares solve on the
        # same residual from the best point reached; accepted only if it actually reaches the tolerance
        from scipy.optimize import least_squares
        try:
            # bounds keep the solution physical: the boat may shift at most 1 m / yaw 0.3 rad from the nominal berth (the
            # numerical centering spring could otherwise "balance" any force with a kilometre of drift), attitudes < 0.5 rad
            lo = np.array([q_cold[0] - 1.0, -0.5, -0.5, -1.0, -1.0, -0.3, q_cold[6] - 1.0, -0.5, -0.5])
            hi = np.array([q_cold[0] + 1.0, 0.5, 0.5, 1.0, 1.0, 0.3, q_cold[6] + 1.0, 0.5, 0.5])
            q0 = np.clip(q, lo + 1e-9, hi - 1e-9)
            sol = least_squares(lambda x: residual(x) / scale, q0, method="trf", bounds=(lo, hi), xtol=1e-13, ftol=1e-13, gtol=1e-13,
                                max_nfev=600, x_scale=np.array([0.1, 0.05, 0.05, 0.1, 0.1, 0.05, 0.1, 0.05, 0.05]))
            n_eval += int(sol.nfev) * 10
            rn = float(np.linalg.norm(sol.fun))
            fallback = dict(used=True, residual_relative=rn, nfev=int(sol.nfev), message=str(sol.message))
            if rn < r:
                q = sol.x
                R, lf, aux = residual(q, True)
                r = float(np.linalg.norm(R / scale))
                converged = r < max(tol, 1e-8)
        except Exception as e:  # noqa: BLE001
            fallback = dict(used=True, error=f"{type(e).__name__}: {e}")
    at_boundary = False
    if not converged and r < 1e-5:
        # Newton chatters on the kink of a line at the slack/taut boundary (T = 0): a 1e-5 Mg residual (a few mN) is accepted
        converged, at_boundary = True, True
    Ie, Ib, Re, Rbl, psi, pe, pb, all_slack = aux[:8]
    eq_e = dict(phi=float(q[1]), theta=float(q[2]), zG=float(q[0]), R=Re, integrals=Ie, G_body=np.asarray(G_e), mass=float(M_e), rho=rho, g=g,
                residual_relative=float(r), n_evaluations=n_eval, newton_converged=bool(converged), z_origin=float(q[0] - (Re @ np.asarray(G_e))[2]),
                statically_stable=True, yaw_removed_rad=0.0)
    eq_b = dict(phi=float(q[7]), theta=float(q[8]), zG=float(q[6]), R=Rbl, integrals=Ib, G_body=np.asarray(G_b), mass=float(M_b), rho=rho, g=g,
                residual_relative=float(r), n_evaluations=n_eval, newton_converged=bool(converged), z_origin=float(q[6] - (Rbl @ np.asarray(G_b))[2]),
                statically_stable=True, yaw_removed_rad=0.0)
    lines_out = [dict(id=l["id"], kind=l["kind"], a_world=l["a"].tolist(), b_world=l["b"].tolist(), length_m=l["L"], unstretched_length_m=l["L0"],
                      nominal_length_m=float(ln), unit=l["u"].tolist(), tension_N=l["T"], slack=bool(l["slack"]),
                      pretension_N=l["T"], stiffness_N_per_m=l["k"], vertical_component_N=float(l["T"] * abs(l["u"][2])),
                      nominal_pretension_N=float(t0), compression_N=float(max(0.0, -l["T"]))) for l, ln, t0 in zip(lf, Lnom, T0)]
    ext_net = None
    if external is not None:
        Fxe, Mxe, Fxb, Mxb = external(pe, pb)
        ext_net = dict(Fx_N=float(Fxe[0] + Fxb[0]), Fy_N=float(Fxe[1] + Fxb[1]),
                       note="net in-plane external force on the two-body system (must be ~0 for a steady state)")
    info = dict(converged=bool(converged), residual_relative=float(r), n_evaluations=n_eval, converged_at_slack_boundary=at_boundary,
                external_net_force=ext_net, least_squares_fallback=fallback, active_set_sweeps=history,
                boat_shift_from_nominal=dict(dx_m=float(q[3]), dy_m=float(q[4]), dyaw_deg=float(np.degrees(q[5]))),
                all_lines_slack=bool(all_slack),
                independent_flotations=dict(exo=dict(zG=eq_e0["zG"], heel_deg=deg(eq_e0["phi"]), trim_deg=deg(eq_e0["theta"])),
                                            boat=dict(zG=eq_b0["zG"], heel_deg=deg(eq_b0["phi"]), trim_deg=deg(eq_b0["theta"]))),
                note="Coupled static equilibrium: buoyancy + weight + tension-only line springs on both bodies; the EXO fixes the "
                     "horizontal frame, the boat shifts/yaws until the line forces balance. L0 = L_nominal - T0/k.")
    return eq_e, eq_b, pe, pb, lines_out, info, q
