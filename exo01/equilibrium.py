"""Still-water equilibrium (draft, heel, trim), freeboards and initial stability.

Frame: world X,Y horizontal, Z up, waterline at Z = 0. The body (CAD axes) is placed with
    w = R(phi, theta) (p - G) + (0, 0, zG),     G = assembly COM in body axes,
so the COM sits at horizontal origin and at height zG above the waterline. Unknowns: zG, phi, theta.
phi = heel about +X (right-handed), theta = trim about +Y (right-handed; positive lowers the +X end).

Balance (buoyancy force rho g V acts vertically at the centre of buoyancy B):
    Fz = rho g V - M g = 0,    Mx = rho g V yB = 0,    My = -rho g V xB = 0   (about the COM)
Floats are the ONLY buoyant surfaces; nothing is added to make the structure float.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq, root

from .buoyancy import BuoyantAssembly, attitude, wet_integrals, signed_volume
from .units import G_STD


class NoEquilibrium(Exception):
    """Raised when no statically stable equilibrium exists; `best` (optional) describes the best balance point found:
    dict(heel_deg, trim_deg, z_origin_m, residual_relative, full_floats, dry_floats) for the interface to show."""

    def __init__(self, msg, best=None):
        super().__init__(msg)
        self.best = best


def _vol_at(assembly, R, G, zG):
    return assembly.integrals(R, G, zG)


def solve_heave(assembly, R, G, target_volume, zG0=None):
    """zG such that displaced volume == target (V(zG) is monotone decreasing). Safeguarded Newton with
    dV/dzG = -A_wp, bracketed by the fully-submerged / fully-emerged positions; brentq fallback."""
    rel = (assembly._flat - np.asarray(G, float)) @ R.T
    zmin, zmax = rel[:, 2].min(), rel[:, 2].max()
    lo = -zmax - 1e-9        # fully submerged -> V = Vmax
    hi = -zmin + 1e-9        # fully emerged  -> V = 0
    if target_volume >= assembly.max_volume or target_volume <= 0:
        raise NoEquilibrium("target volume outside (0, max buoyant volume)")
    zG = 0.5 * (lo + hi) if zG0 is None else float(np.clip(zG0, lo, hi))
    I = assembly.integrals(R, G, zG)
    for _ in range(60):
        f = I["V"] - target_volume
        if abs(f) < 1e-13 * target_volume:
            return zG, I
        if f > 0:            # too much volume -> the body must rise: zG is a new lower bound
            lo = zG
        else:
            hi = zG
        step = f / I["Awp"] if I["Awp"] > 0 else None
        zn = zG + step if step is not None else 0.5 * (lo + hi)
        if not (lo < zn < hi):
            zn = 0.5 * (lo + hi)
        zG = zn
        I = assembly.integrals(R, G, zG)
    f = lambda z: assembly.integrals(R, G, z)["V"] - target_volume
    zG = brentq(f, lo, hi, xtol=1e-14, rtol=1e-14, maxiter=200)
    return zG, assembly.integrals(R, G, zG)


def _no_equilibrium_reason(assembly, mass, G, rho, g, best):
    r, zG, R, I = best
    phi, theta, _ = _euler_from_R(R)
    vols = assembly.per_surface_volume(R, G, zG)
    full = [s.id for i, s in enumerate(assembly.surfaces)
            if vols[s.id] > 0.995 * signed_volume(assembly.tris[i])]
    dry = [s.id for s in assembly.surfaces if vols[s.id] < 1e-6]
    C = restoring_matrix(I, rho, g, zG)
    ev = np.linalg.eigvalsh(0.5 * (C + C.T))
    msg = (f"no statically stable equilibrium found within the modelled float volume. Best balance point: residual "
           f"{r:.2e} of Mg at heel {np.degrees(phi):.1f} deg, trim {np.degrees(theta):.1f} deg; ")
    if full:
        msg += f"fully submerged float(s): {', '.join(full)}; "
    if dry:
        msg += f"float(s) out of the water: {', '.join(dry)}; "
    if np.any(ev <= 0):
        msg += (f"restoring matrix indefinite (eigenvalues {np.round(ev, 0).tolist()} N/m, N m/rad): the body keeps "
                "sinking by the submerged end - the floats alone cannot hold this load distribution.")
    else:
        msg += "solver stalled; check the load case."
    return msg


def _best_point(assembly, G, best):
    r, zG, R, I = best
    phi, theta, _ = _euler_from_R(R)
    vols = assembly.per_surface_volume(R, G, zG)
    full = [s.id for i, s in enumerate(assembly.surfaces) if vols[s.id] > 0.995 * signed_volume(assembly.tris[i])]
    dry = [s.id for s in assembly.surfaces if vols[s.id] < 1e-6]
    return dict(heel_deg=float(np.degrees(phi)), trim_deg=float(np.degrees(theta)), z_origin_m=float(zG - (R @ np.asarray(G, float))[2]),
                zG_m=float(zG), R_world=np.asarray(R).tolist(), residual_relative=float(r), full_floats=full, dry_floats=dry,
                note="best balance point found by the solver: NOT an equilibrium; shown so the tendency (which end sinks) is visible")


def _euler_from_R(R):
    """Decompose R = Rz(psi) Ry(theta) Rx(phi); returns (phi, theta, psi)."""
    theta = -np.arcsin(np.clip(R[2, 0], -1.0, 1.0))
    phi = np.arctan2(R[2, 1], R[2, 2])
    psi = np.arctan2(R[1, 0], R[0, 0])
    return phi, theta, psi


def _wrench(assembly, mass, G, rho, g, q):
    R = attitude(q[1], q[2])
    I = assembly.integrals(R, G, q[0])
    Fb = rho * g * I["V"]
    return np.array([Fb - mass * g, Fb * I["B"][1], -Fb * I["B"][0]]), I


def restoring_matrix(I, rho, g, zG):
    """Exact hydrostatic restoring matrix C = -dW/dq for q = (heave, roll about world X, pitch about world Y) of the
    buoyancy+gravity wrench about the COM, from the waterplane integrals of the clipped surface:
        C33 = rho g A,  C34 = rho g S_y,  C35 = -rho g S_x,
        C44 = rho g (I_xx + V z_rel),  C55 = rho g (I_yy + V z_rel),  C45 = -rho g I_xy,   z_rel = z_B - z_G.
    Valid at any attitude (not only at equilibrium); verified against central differences in tests."""
    zrel = I["B"][2] - zG
    rg = rho * g
    return rg * np.array([[I["Awp"], I["Sy"], -I["Sx"]],
                          [I["Sy"], I["Ixx"] + I["V"] * zrel, -I["Ixy"]],
                          [-I["Sx"], -I["Ixy"], I["Iyy"] + I["V"] * zrel]])


def _wrench_R(assembly, mass, G, rho, g, zG, R):
    I = assembly.integrals(R, G, zG)
    Fb = rho * g * I["V"]
    return np.array([Fb - mass * g, Fb * I["B"][1], -Fb * I["B"][0]]), I


def equilibrium(assembly: BuoyantAssembly, mass, G_body, rho, g=G_STD, start=(0.0, 0.0), tol=1e-11, max_iter=60,
                warm_start=None, external=None):
    """Solve for zero net force and moment: unknowns zG (COM height above the waterline) and the attitude R.

    Newton on the exact wrench W = (Fz, Mx, My) about the COM with the analytic Jacobian J = -C (restoring matrix
    from the waterplane integrals). Increments are rotations about the WORLD X and Y axes through the COM,
    R <- Ry(d_theta) Rx(d_phi) R, which is exactly what C describes, so convergence is quadratic. Backtracking line
    search; warm start (zG, phi, theta) from a previous solve; brentq+hybr fallback if Newton stalls.
    The final R is re-expressed as Ry(theta) Rx(phi) (any accumulated yaw is removed: the problem is yaw-invariant).
    Raises NoEquilibrium with a reason if no equilibrium exists within the modelled buoyant volume.
    external: optional constant world-frame wrench (Fz, Mx, My) about the COM added to the hydrostatic + gravity wrench
    (e.g. thrust/drag couples); the hybr fallback is not used with it.
    """
    G = np.asarray(G_body, float)
    ext = np.zeros(3) if external is None else np.asarray(external, float)

    def wrench(zG_, R_):
        W_, I_ = _wrench_R(assembly, mass, G, rho, g, zG_, R_)
        return W_ + ext, I_
    Vt = mass / rho
    if Vt >= assembly.max_volume:
        raise NoEquilibrium(
            f"required displaced volume {Vt:.4f} m3 (mass {mass:.1f} kg at rho {rho:.0f}) is not below the total volume of the "
            f"modelled buoyant surfaces ({assembly.max_volume:.4f} m3 = {assembly.max_volume * rho:.0f} kg when fully submerged). "
            "No equilibrium with the floats alone; buoyancy was not increased artificially.")
    scale = mass * g
    n_eval = 0
    if warm_start is not None:
        # warm start = previous body pose (R, z of the CAD origin above the waterline): independent of the COM, so a
        # moved mass changes only the wrench, not the starting geometry
        R = attitude(float(warm_start[1]), float(warm_start[2]))
        zG = float(warm_start[0]) + float((R @ G)[2])
    else:
        R = attitude(*start)
        zG, _ = solve_heave(assembly, R, G, Vt)
        n_eval += 8
    W, I = wrench(zG, R)
    n_eval += 1
    r = np.linalg.norm(W) / scale
    converged = r < tol
    stalled = False
    best = (r, zG, R, I)
    for _ in range(max_iter):
        if converged:
            break
        if I["V"] <= 0 or I["Awp"] <= 0:
            stalled = True
            break
        J = -restoring_matrix(I, rho, g, zG)
        try:
            dq = np.linalg.solve(J, -W)
        except np.linalg.LinAlgError:
            stalled = True
            break
        big = max(abs(dq[0]) / 0.25, abs(dq[1]) / 0.15, abs(dq[2]) / 0.15, 1.0)   # step limiter: 0.25 m, 0.15 rad
        a = 1.0 / big
        improved = False
        while a > 1e-4 / big:
            zn = zG + a * dq[0]
            Rn = _Ry(a * dq[2]) @ _Rx(a * dq[1]) @ R
            Wn, In = wrench(zn, Rn)
            n_eval += 1
            rn = np.linalg.norm(Wn) / scale
            if rn < r:
                zG, R, W, I, r = zn, Rn, Wn, In, rn
                improved = True
                if r < best[0]:
                    best = (r, zG, R, I)
                break
            a *= 0.5
        if not improved:
            stalled = True
            break
        converged = r < tol
    best_newton = best
    if not converged and r >= 1e-9 and external is not None:
        raise NoEquilibrium(f"no static equilibrium with the external wrench {ext.round(1).tolist()} (Newton stalled at a relative "
                            f"residual of {r:.1e})", _best_point(assembly, G, best_newton))
    if not converged and r >= 1e-9:                      # robust fallback (bracketing heave + hybr attitude)
        def resid(x):
            z, Ii = solve_heave(assembly, attitude(x[0], x[1]), G, Vt)
            return np.array([Ii["B"][0], Ii["B"][1]])
        phi0, theta0, _ = _euler_from_R(R)
        best = None
        for s0 in ((phi0, theta0), (0.0, 0.0)):
            try:
                sol = root(resid, np.array(s0, float), method="hybr", tol=1e-14)
            except NoEquilibrium:
                continue
            rr = np.linalg.norm(sol.fun)
            if best is None or rr < best[0]:
                best = (rr, sol.x)
            if rr < 1e-10:
                break
        if best is None or best[0] > 1e-8:
            raise NoEquilibrium(_no_equilibrium_reason(assembly, mass, G, rho, g, best_newton), _best_point(assembly, G, best_newton))
        R = attitude(*best[1])
        zG, I = solve_heave(assembly, R, G, Vt)
        W, I = wrench(zG, R)
        r = np.linalg.norm(W) / scale
        converged = r < 1e-9
    phi, theta, psi = _euler_from_R(R)
    R = attitude(phi, theta)                               # yaw-free convention R = Ry(theta) Rx(phi)
    W, I = wrench(zG, R)
    C = restoring_matrix(I, rho, g, zG)
    stable = bool(np.all(np.linalg.eigvalsh(0.5 * (C + C.T)) > 0))
    if warm_start is not None and not stable:
        # a warm start can land on an unstable second root: redo from the level-keel cold start
        return equilibrium(assembly, mass, G_body, rho, g, start=start, tol=tol, max_iter=max_iter, warm_start=None, external=external)
    return dict(phi=float(phi), theta=float(theta), zG=float(zG), R=R, integrals=I, G_body=G,
                mass=float(mass), rho=float(rho), g=float(g), residual_relative=float(np.linalg.norm(W) / scale),
                n_evaluations=n_eval, newton_converged=bool(converged and not stalled), yaw_removed_rad=float(psi),
                z_origin=float(zG - (R @ G)[2]), statically_stable=stable,
                external_wrench=None if external is None else ext.tolist())


# ---------------------------------------------------------------- derived outputs
def residuals(assembly, eq):
    I = assembly.integrals(eq["R"], eq["G_body"], eq["zG"])
    rho, g, M = eq["rho"], eq["g"], eq["mass"]
    Fb = rho * g * I["V"]
    out = dict(Fz_N=float(Fb - M * g), Mx_Nm=float(Fb * I["B"][1]), My_Nm=float(-Fb * I["B"][0]),
               weight_N=float(M * g), buoyancy_N=float(Fb))
    if eq.get("external_wrench") is not None:          # hydrostatic + gravity imbalance = -(external wrench) at equilibrium
        out["external_wrench_Fz_Mx_My"] = list(eq["external_wrench"])
        out["Fz_N_incl_external"] = out["Fz_N"] + eq["external_wrench"][0]
        out["Mx_Nm_incl_external"] = out["Mx_Nm"] + eq["external_wrench"][1]
        out["My_Nm_incl_external"] = out["My_Nm"] + eq["external_wrench"][2]
    return out


def hydrostatic_stiffness(assembly, eq, dq=1e-6, dh=1e-6):
    """3x3 restoring matrix [heave, roll(about world X), pitch(about world Y)] about the COM, from the exact
    wrench of the (gravity + buoyancy) system by central differences. C = -dW/dq with W = (Fz, Mx, My)."""
    G, rho, g = eq["G_body"], eq["rho"], eq["g"]
    R0, zG0 = eq["R"], eq["zG"]

    def wrench(h, a, b):
        Rinc = _Ry(b) @ _Rx(a)
        Rn = Rinc @ R0
        I = assembly.integrals(Rn, G, zG0 + h)
        Fb = rho * g * I["V"]
        return np.array([Fb - eq["mass"] * g, Fb * I["B"][1], -Fb * I["B"][0]])
    C = np.zeros((3, 3))
    steps = (dh, dq, dq)
    for j in range(3):
        e = np.zeros(3)
        e[j] = steps[j]
        Wp = wrench(*e)
        Wm = wrench(*(-e))
        C[:, j] = -(Wp - Wm) / (2 * steps[j])
    return C


def _Rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _Ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def initial_stability(assembly, eq):
    """Static initial-stability measures (NOT dynamic wave behaviour)."""
    rho, g, V = eq["rho"], eq["g"], eq["integrals"]["V"]
    C = restoring_matrix(eq["integrals"], rho, g, eq["zG"])
    GMT = C[1, 1] / (rho * g * V)
    GML = C[2, 2] / (rho * g * V)
    I = eq["integrals"]
    ev = np.linalg.eigvalsh(0.5 * (C + C.T))
    return dict(C_hydrostatic_NmPerUnit=C.tolist(), GM_transverse_m=float(GMT), GM_longitudinal_m=float(GML),
                waterplane_area_m2=float(I["Awp"]), eigenvalues_C=ev.tolist(),
                statically_stable_here=bool(np.all(ev > 0)),
                note="GM from the analytic restoring matrix (waterplane integrals) about the COM at the solved attitude "
                     "(about world X / Y axes).")


def freeboards(assembly, eq, cfg):
    """Clearly defined freeboards: height above the still waterline (m). Negative = submerged."""
    R, G, zG = eq["R"], eq["G_body"], eq["zG"]

    def zw(p):
        return float((R @ (np.asarray(p, float) - G))[2] + zG)

    float_tops = {}
    for i, s in enumerate(assembly.surfaces):
        w = assembly.world_tris(R, G, zG, which=i)
        float_tops[s.id] = dict(top_above_waterline_m=float(w[:, :, 2].max()),
                                bottom_below_waterline_m=float(-w[:, :, 2].min()))
    fb = cfg["freeboard_points"]
    out = dict(
        float_top_freeboard_min_m=min(v["top_above_waterline_m"] for v in float_tops.values()),
        draft_max_m=max(v["bottom_below_waterline_m"] for v in float_tops.values()),
        per_float=float_tops,
        lower_deck_freeboard_min_m=min(zw(p) for p in fb["lower_deck_corners"]),
        frame_footprint_deck_datum_freeboard_min_m=min(zw(p) for p in fb["frame_footprint_corners_deck_datum"]),
        observation_deck_centre_height_m=zw(fb["observation_deck_centre"]),
        definitions={
            "float_top_freeboard_min_m": "lowest, over the six floats, of (highest point of the float above the still waterline); <0 means a float is fully submerged",
            "draft_max_m": "depth of the lowest point of any float below the still waterline",
            "lower_deck_freeboard_min_m": "lowest height above the waterline of the 4 corners of the 2.1 m rear deck plate (top surface, Z=0 datum)",
            "frame_footprint_deck_datum_freeboard_min_m": "lowest height above the waterline of the 4 corners of the full 4.95 m x 4.547 m footprint at the deck datum Z=0",
            "observation_deck_centre_height_m": "height of the observation-deck surface centre above the waterline",
        })
    return out


def level_keel_screening(assembly, mass, rho):
    """Baseline-safe scalar: draft of the floats at ZERO heel/trim for the listed subtotal only.
    NOT an equilibrium (COM unknown => attitude unknown) and not the full operating displacement."""
    Vt = mass / rho
    R = np.eye(3)
    G = np.zeros(3)
    if Vt >= assembly.max_volume:
        return dict(feasible=False, reason="listed mass exceeds total modelled float volume",
                    max_buoyant_mass_kg=assembly.max_volume * rho)
    zG, I = solve_heave(assembly, R, G, Vt)
    zbot = assembly.all_tris[:, :, 2].min()
    return dict(feasible=True, level_draft_m=float(-(zbot + zG)),
                displaced_volume_m3=float(I["V"]), waterplane_area_m2=float(I["Awp"]),
                max_buoyant_mass_kg=float(assembly.max_volume * rho),
                reserve_buoyancy_mass_kg=float(assembly.max_volume * rho - mass),
                reserve_fraction=float(1 - Vt / assembly.max_volume))
