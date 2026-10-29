"""Linear frequency-domain wave response about the solved still-water equilibrium, for one rigid body (6 DOF) or
several bodies coupled by hydrodynamic interaction and linear mooring-line springs (6 DOF per body).

Equation (exp(-i w t), unit wave amplitude, DOF of each body about its own COM along the world axes):
    [ -w^2 (M + A(w)) - i w (B(w) + B_visc) + K ] X = F(w, heading)
M: block-diagonal rigid-body mass/inertia (inertia rotated to the equilibrium attitude); A, B: Capytaine added mass
and radiation damping (full matrices: cross-body coupling included); K: hydrostatic restoring of each body (heave,
roll, pitch; surge/sway/yaw have no restoring) + the line-spring stiffness coupling the bodies; F: Froude-Krylov +
diffraction. Wave height H is crest-to-trough; amplitude A = H/2; heading = direction of travel, CCW from +X.
Reconstructed time histories are LINEAR reconstructions, x_i(t) = Re(X_i A exp(-i w t)).
"""
from __future__ import annotations

import numpy as np

from .units import G_STD, deg

DOF = ["surge", "sway", "heave", "roll", "pitch", "yaw"]


def wavenumber(omega, depth, g=G_STD):
    if depth is None or np.isinf(depth):
        return omega ** 2 / g
    k = omega ** 2 / g
    for _ in range(100):
        f = g * k * np.tanh(k * depth) - omega ** 2
        df = g * np.tanh(k * depth) + g * k * depth / np.cosh(k * depth) ** 2
        dk = f / df
        k -= dk
        if abs(dk) < 1e-14:
            break
    return k


def mass_matrix_6(mass, inertia_body, R):
    M = np.zeros((6, 6))
    M[:3, :3] = np.eye(3) * mass
    M[3:, 3:] = R @ np.asarray(inertia_body) @ R.T
    return M


def stiffness_6(C3, extra=None):
    K = np.zeros((6, 6))
    idx = [2, 3, 4]
    for a, i in enumerate(idx):
        for b, j in enumerate(idx):
            K[i, j] = C3[a][b]
    if extra is not None:
        K += np.diag(extra)
    return K


def skew(r):
    return np.array([[0, -r[2], r[1]], [r[2], 0, -r[0]], [-r[1], r[0], 0]])


def line_stiffness(lines, com_world):
    """Linear stiffness of pretensioned line springs between bodies, generalised to the (6 x n_bodies) DOF.

    Each line: attachment points a (on body i) and b (on body j) in world coordinates, pretension T0, axial stiffness
    k. Relative displacement of the attachments d = (xi_j + Omega_j x r_j) - (xi_i + Omega_i x r_i); force on body j
    = -(k u u^T + (T0/L)(I - u u^T)) d  (axial + geometric 'string' stiffness), u = (b - a)/L; equal and opposite
    on body i. Returns the symmetric positive-semidefinite matrix K_lines and the list of B matrices (d = B q)."""
    nb = len(com_world)
    K = np.zeros((6 * nb, 6 * nb))
    Bs = []
    for ln in lines:
        i, j = ln["body_i"], ln["body_j"]
        a, b = np.asarray(ln["a_world"], float), np.asarray(ln["b_world"], float)
        L = np.linalg.norm(b - a)
        if L <= 1e-9:
            continue
        u = (b - a) / L
        kl = ln["stiffness_N_per_m"] * np.outer(u, u) + (ln["pretension_N"] / L) * (np.eye(3) - np.outer(u, u))
        ra = a - np.asarray(com_world[i])
        rb = b - np.asarray(com_world[j])
        Bm = np.zeros((3, 6 * nb))
        Bm[:, 6 * i:6 * i + 3] -= np.eye(3)
        Bm[:, 6 * i + 3:6 * i + 6] += skew(ra)          # -(Omega x r) = r x Omega = [r]x Omega
        Bm[:, 6 * j:6 * j + 3] += np.eye(3)
        Bm[:, 6 * j + 3:6 * j + 6] -= skew(rb)
        K += Bm.T @ kl @ Bm
        Bs.append((ln, u, Bm))
    return K, Bs


class ResponseModel:
    """bodies: list of dict(name, pose{R_world, com_world, G_body}, floats{id: {centre_body, top_above_waterline_m,
    bottom_below_waterline_m}} (optional), lower_deck_freeboard_min_m (optional), deck_points{name: p_body})."""

    def __init__(self, hydro, M, K, rho, g, depth, bodies, lines=None, line_B=None):
        self.hydro, self.M, self.K, self.rho, self.g, self.depth = hydro, M, K, rho, g, depth
        self.bodies = bodies
        self.nb = len(bodies)
        self.n = 6 * self.nb
        self.lines = lines or []
        self.line_B = line_B or []
        assert hydro.A.shape[1] == self.n, "hydro DOF count does not match the bodies"

    # ----------------------------------------------------------- damping
    def _damp_for(self, damping, name):
        """Per-body damping: damping may be {"zeta":..,"absolute":..} (all bodies) or {body_name: {...}}."""
        d = damping or {}
        if name in d:
            return d[name]
        return d

    def viscous_matrix(self, damping):
        """Diagonal viscous damping, zeta applied as B = 2 zeta sqrt(K_ii (M_ii + A_ii(w_n))) per body and DOF."""
        Bv = np.zeros((self.n, self.n))
        nat = self.natural_frequencies()
        for bi, body in enumerate(self.bodies):
            d = self._damp_for(damping, body["name"])
            z = d.get("zeta", {})
            ab = d.get("absolute", {})
            for nm in ("heave", "roll", "pitch"):
                zeta = z.get(nm, 0.0)
                if zeta:
                    i = 6 * bi + DOF.index(nm)
                    roots = nat["bodies"][body["name"]]["uncoupled_roots"][nm]
                    w_n = roots[0] if roots else self.hydro.omegas[0]
                    A, _ = self.hydro.coeffs(w_n)
                    ma = max(self.M[i, i] + A[i, i], 0.05 * self.M[i, i])
                    Bv[i, i] = 2 * zeta * np.sqrt(max(self.K[i, i], 0.0) * ma)
            for nm in ("surge", "sway", "yaw"):
                if ab.get(nm):
                    Bv[6 * bi + DOF.index(nm), 6 * bi + DOF.index(nm)] = ab[nm]
        return Bv

    # ----------------------------------------------------------- natural frequencies
    def natural_frequencies(self):
        if hasattr(self, "_nat"):
            return self._nat
        from scipy.optimize import brentq
        wl, wh = float(self.hydro.omegas[0]), float(self.hydro.omegas[-1])
        ws = np.linspace(wl, wh, 1200)

        def roots_of(f):
            v = np.array([f(w) for w in ws])
            out = []
            for k in range(len(ws) - 1):
                if np.isfinite(v[k]) and np.isfinite(v[k + 1]) and v[k] * v[k + 1] < 0:
                    try:
                        out.append(float(brentq(f, ws[k], ws[k + 1], xtol=1e-10)))
                    except ValueError:
                        pass
            return out
        per = {}
        for bi, body in enumerate(self.bodies):
            unc = {}
            for nm in ("heave", "roll", "pitch"):
                i = 6 * bi + DOF.index(nm)
                unc[nm] = roots_of(lambda w, i=i: self.K[i, i] - w * w * (self.M[i, i] + self.hydro.coeffs(w)[0][i, i]))
            per[body["name"]] = dict(uncoupled_roots=unc, T_uncoupled_s={k: [2 * np.pi / w for w in v] for k, v in unc.items()})
        # coupled: restrained DOFs of all bodies (heave/roll/pitch, plus surge/sway/yaw when lines restrain them)
        idx = [i for i in range(self.n) if self.K[i, i] > 1e-6]

        def detk(w):
            A = self.hydro.coeffs(w)[0]
            Mt = (self.K - w * w * (self.M + A))[np.ix_(idx, idx)]
            s, ld = np.linalg.slogdet(Mt)
            return float(s * np.exp(ld / len(idx)))      # scaled determinant (sign preserved)
        croots = roots_of(detk)
        labels = []
        for w in croots:
            A = self.hydro.coeffs(w)[0]
            Mt = (self.K - w * w * (self.M + A))[np.ix_(idx, idx)]
            _, _, vt = np.linalg.svd(Mt)
            v = np.abs(vt[-1])
            k = idx[int(np.argmax(v))]
            labels.append(f"{self.bodies[k // 6]['name']} {DOF[k % 6]}")
        self._nat = dict(bodies=per, coupled_roots=croots, coupled_labels=labels, T_coupled_s=[2 * np.pi / w for w in croots],
                         band=[wl, wh], gap_resonance_bands_rad_s=self.hydro.gap_bands(),
                         # legacy single-body fields
                         labels=["heave", "roll", "pitch"],
                         uncoupled_roots=per[self.bodies[0]["name"]]["uncoupled_roots"],
                         omega_diag=[(per[self.bodies[0]["name"]]["uncoupled_roots"][k] or [None])[0] for k in ("heave", "roll", "pitch")],
                         T_diag_s=[None if w is None else 2 * np.pi / w for w in [(per[self.bodies[0]["name"]]["uncoupled_roots"][k] or [None])[0] for k in ("heave", "roll", "pitch")]],
                         note="Undamped roots on the computed band (added mass evaluated at the root). Several roots per DOF can occur "
                              "because potential-flow added mass varies sharply near the resonances of the water trapped between the "
                              "float rows (and between the boat hull and the floats); those bands are listed. Real viscous damping, "
                              "absent from the BEM, limits them.")
        return self._nat

    # ----------------------------------------------------------- RAO
    def encounter_omega(self, omega, heading, speed):
        """Encounter frequency for a body advancing at `speed` along +X: w_e = w - k U cos(heading)
        (heading = direction the waves travel toward; following seas at heading 0 lower it, head seas raise it)."""
        if not speed:
            return omega
        k = wavenumber(omega, self.depth, self.g)
        return omega - k * speed * np.cos(heading)

    def rao(self, omega, heading, damping=None, speed=0.0):
        """Zero-speed potential-flow coefficients; with forward speed the equations of motion are solved at the encounter
        frequency with A, B taken at w_e and the excitation at the wave frequency (low-Froude approximation, labelled)."""
        we = self.encounter_omega(omega, heading, speed)
        wl, wh = self.hydro.omegas[[0, -1]]
        we_c = min(max(we, wl), wh)
        A, B = self.hydro.coeffs(we_c)
        F = self.hydro.excitation(omega, heading)
        Bv = self.viscous_matrix(damping)
        Z = -we ** 2 * (self.M + A) - 1j * we * (B + Bv) + self.K
        return np.linalg.solve(Z, F)

    def rao_curve(self, omegas, heading, damping=None, speed=0.0):
        return np.array([self.rao(w, heading, damping, speed) for w in omegas])

    # ----------------------------------------------------------- geometry helpers
    def point_world_offset(self, p_body, body_index=0):
        pose = self.bodies[body_index]["pose"]
        return np.asarray(pose["R_world"]) @ (np.asarray(p_body, float) - np.asarray(pose["G_body"]))

    def body_block(self, X, bi):
        return X[6 * bi:6 * bi + 6]

    # ----------------------------------------------------------- regular wave
    def regular_wave(self, H, T, heading, damping=None, deck_points=None, speed=0.0):
        """deck_points: {name: p_body} for body 0 (legacy) - each body may also carry its own 'deck_points'.
        speed: forward speed along +X (m/s) -> encounter frequency (see `rao`)."""
        omega = 2 * np.pi / T
        wl, wh = self.hydro.omegas[[0, -1]]
        out = dict(H_m=H, amplitude_m=H / 2, period_s=T, omega=omega, heading_rad=heading, heading_deg=deg(heading),
                   heading_convention="direction the waves travel TOWARD, CCW from +X (0 deg: travelling toward +X)",
                   n_bodies=self.nb, body_names=[b["name"] for b in self.bodies])
        if not (wl <= omega <= wh):
            out["in_range"] = False
            out["error"] = f"omega {omega:.3f} outside computed band [{wl:.2f}, {wh:.2f}] rad/s (T {2*np.pi/wh:.2f}-{2*np.pi/wl:.2f} s)"
            return out
        k = wavenumber(omega, self.depth, self.g)
        lam = 2 * np.pi / k
        Aw = H / 2
        speed = float(speed or 0.0)
        we = self.encounter_omega(omega, heading, speed)
        if speed:
            out["encounter"] = dict(speed_m_s=speed, omega_e=float(we), period_e_s=(float(2 * np.pi / we) if we > 1e-9 else None),
                                    in_band=bool(wl <= we <= wh),
                                    note="forward speed: equations of motion solved at the encounter frequency with ZERO-SPEED added mass/damping "
                                         "taken at w_e (clamped to the computed band) and the excitation at the wave frequency; low-Froude "
                                         "approximation, no speed-dependent hydrodynamics")
            if we <= 1e-9:
                out["in_range"] = False
                out["error"] = f"encounter frequency {we:.3f} rad/s <= 0 (following sea overtaken at {speed:.2f} m/s): no oscillatory encounter"
                return out
        X = self.rao(omega, heading, damping, speed)
        Xa = X * Aw
        out.update(in_range=True, wavenumber=k, wavelength_m=lam, omega_motion=float(we),
                   X_complex=[[float(z.real), float(z.imag)] for z in Xa],
                   rao_complex=[[float(z.real), float(z.imag)] for z in X])
        bodies_out = {}
        for bi, body in enumerate(self.bodies):
            xb, Xb = self.body_block(Xa, bi), self.body_block(X, bi)
            amp = np.abs(xb)
            bo = dict(amplitude={n: float(amp[i]) for i, n in enumerate(DOF)},
                      amplitude_deg={n: float(deg(amp[i])) for i, n in enumerate(DOF) if i >= 3},
                      phase_lag_deg={n: float(deg(np.angle(xb[i]))) for i, n in enumerate(DOF)},
                      rao_amplitude={n: float(abs(Xb[i])) for i, n in enumerate(DOF)},
                      X_complex=[[float(z.real), float(z.imag)] for z in xb], points={})
            pts = body.get("deck_points") or (deck_points if bi == 0 else None) or {}
            for name, p in pts.items():
                r = self.point_world_offset(p, bi)
                u = xb[:3] + np.cross(xb[3:], r)
                a = -we ** 2 * u
                bo["points"][name] = dict(disp_amp_m=[float(abs(c)) for c in u], accel_amp_ms2=[float(abs(c)) for c in a],
                                          accel_vertical_amp_ms2=float(abs(a[2])), accel_vertical_amp_g=float(abs(a[2]) / self.g),
                                          accel_horizontal_amp_ms2=float(np.hypot(abs(a[0]), abs(a[1]))))
            if bo["points"]:
                bo["deck_accel_vertical_max_amp_ms2"] = max(p["accel_vertical_amp_ms2"] for p in bo["points"].values())
                bo["deck_accel_horizontal_max_amp_ms2"] = max(p["accel_horizontal_amp_ms2"] for p in bo["points"].values())
            bo["tilt_amplitude_deg"] = dict(roll=bo["amplitude_deg"]["roll"], pitch=bo["amplitude_deg"]["pitch"])
            bodies_out[body["name"]] = bo
        out["bodies"] = bodies_out
        first = bodies_out[self.bodies[0]["name"]]            # legacy top-level = body 0 (EXO)
        for key in ("amplitude", "amplitude_deg", "phase_lag_deg", "rao_amplitude", "points", "tilt_amplitude_deg",
                    "deck_accel_vertical_max_amp_ms2", "deck_accel_horizontal_max_amp_ms2"):
            if key in first:
                out[key] = first[key]
        # line tensions (linear): dynamic tension amplitude per line = |k u.d + geometric terms|; slack if > pretension
        if self.line_B:
            lt = []
            for ln, u, Bm in self.line_B:
                d = Bm @ Xa
                T_dyn = ln["stiffness_N_per_m"] * (u @ d)
                T0 = float(ln["pretension_N"])
                lt.append(dict(id=ln["id"], pretension_N=T0, dynamic_tension_amp_N=float(abs(T_dyn)),
                               tension_mean_N=T0, tension_amp_N=float(abs(T_dyn)), min_N=float(max(0.0, T0 - abs(T_dyn))),
                               max_N=float(T0 + abs(T_dyn)), slack_in_cycle=bool(abs(T_dyn) > T0),
                               slack_at_rest=bool(ln.get("slack", False)),
                               relative_stretch_amp_m=float(abs(u @ d)), transverse_rel_motion_amp_m=float(np.linalg.norm(d - (u @ d) * u)),
                               goes_slack=bool(abs(T_dyn) > T0)))
            out["lines"] = lt
            self._last_linear_lines = lt
        # relative motion between the two bodies at the clearance points (linear amplitude vs the still clearance)
        if self.nb > 1 and self.bodies[0].get("relative_points"):
            rel = {}
            for rp in self.bodies[0]["relative_points"]:
                i, j = rp["body_i"], rp["body_j"]
                ui = self.body_block(Xa, i); uj = self.body_block(Xa, j)
                ri = self.point_world_offset(rp["p_i"], i); rj = self.point_world_offset(rp["p_j"], j)
                di = ui[:3] + np.cross(ui[3:], ri); dj = uj[:3] + np.cross(uj[3:], rj)
                ax = {"x": 0, "y": 1, "z": 2}[rp["axis"]]
                amp = float(abs(di[ax] - dj[ax]))
                rel[rp["name"]] = dict(still_clearance_m=rp["still_clearance_m"], relative_motion_amp_m=amp,
                                       min_clearance_m=(None if rp["still_clearance_m"] is None else float(rp["still_clearance_m"] - amp)),
                                       axis=rp["axis"])
            out["relative_motion"] = rel
            worst = [(k, v["min_clearance_m"]) for k, v in rel.items() if v["min_clearance_m"] is not None]
            if worst:
                kmin = min(worst, key=lambda kv: kv[1])
                out["min_relative_clearance"] = dict(name=kmin[0], min_clearance_m=kmin[1])
        out["flags"] = self.range_flags(out, Xa, omega, k, lam, H, damping)
        return out

    # ----------------------------------------------------------- applicability flags
    def range_flags(self, out, Xa, omega, k, lam, H, damping):
        flags = []
        s = H / lam
        if s > 1 / 7:
            flags.append(("error", f"wave steepness H/L = {s:.3f} exceeds the breaking limit ~1/7: outside linear theory"))
        elif s > 1 / 10:
            flags.append(("warn", f"wave steepness H/L = {s:.3f} > 1/10: nonlinear effects expected"))
        if self.depth is not None and not np.isinf(self.depth) and H / self.depth > 0.78:
            flags.append(("error", f"H/depth = {H/self.depth:.2f} > 0.78: shallow-water breaking limit"))
        nat = self.natural_frequencies()
        for bi, body in enumerate(self.bodies):
            bo = out["bodies"][body["name"]]
            tag = f"[{body['name']}] " if self.nb > 1 else ""
            for n in ("roll", "pitch"):
                if bo["amplitude_deg"][n] > 10:
                    flags.append(("warn", f"{tag}{n} amplitude {bo['amplitude_deg'][n]:.1f} deg > 10 deg: small-angle linearisation questionable"))
            z = self._damp_for(damping, body["name"]).get("zeta", {})
            for nm in ("heave", "roll", "pitch"):
                for wn in nat["bodies"][body["name"]]["uncoupled_roots"][nm][:1]:
                    if abs(omega - wn) / wn < 0.15 and z.get(nm, 0.0) < 0.1:
                        flags.append(("warn", f"{tag}wave frequency within 15% of the {nm} natural frequency ({2*np.pi/wn:.2f} s): response limited "
                                              f"only by radiation + the viscous damping you set ({z.get(nm, 0.0):.2f} of critical); real damping is unknown"))
            xb = self.body_block(Xa, bi)
            worst = None
            for fid, fl in (body.get("floats") or {}).items():
                r = self.point_world_offset(fl["centre_body"], bi)
                c = np.asarray(body["pose"]["com_world"])
                uz = xb[2] + (np.cross(xb[3:], r))[2]
                xw, yw = c[0] + r[0], c[1] + r[1]
                eta = (H / 2) * np.exp(1j * k * (xw * np.cos(out["heading_rad"]) + yw * np.sin(out["heading_rad"])))
                rel = abs(uz - eta)
                lim = min(fl["bottom_below_waterline_m"], fl["top_above_waterline_m"])
                if worst is None or rel / max(lim, 1e-9) > worst[1]:
                    worst = (fid, rel / max(lim, 1e-9), rel, lim)
            if worst and worst[1] >= 1:
                flags.append(("error", f"{tag}relative float motion {worst[2]:.2f} m at {worst[0]} reaches its draft/freeboard ({worst[3]:.2f} m): "
                                       "float emerges or is fully submerged; linear theory invalid"))
            elif worst and worst[1] > 0.5:
                flags.append(("warn", f"{tag}relative float motion at {worst[0]} is {100*worst[1]:.0f}% of its local draft/freeboard"))
            # deck wetting: relative vertical motion of each deck corner w.r.t. the local wave surface, phase included
            worst_c = None
            c = np.asarray(body["pose"]["com_world"])
            for cname, (p, fb0) in (body.get("deck_corners") or {}).items():
                r = self.point_world_offset(p, bi)
                uz = xb[2] + (np.cross(xb[3:], r))[2]
                xw, yw = c[0] + r[0], c[1] + r[1]
                eta = (H / 2) * np.exp(1j * k * (xw * np.cos(out["heading_rad"]) + yw * np.sin(out["heading_rad"])))
                rel = abs(uz - eta)
                bo.setdefault("deck_corner_relative_motion", {})[cname] = dict(still_freeboard_m=float(fb0), relative_motion_amp_m=float(rel),
                                                                               min_clearance_m=float(fb0 - rel))
                if worst_c is None or fb0 - rel < worst_c[1]:
                    worst_c = (cname, fb0 - rel, rel, fb0)
            if worst_c is not None:
                if worst_c[1] <= 0:
                    flags.append(("error", f"{tag}deck corner {worst_c[0]} reaches the wave surface (relative motion {worst_c[2]:.2f} m vs still "
                                           f"freeboard {worst_c[3]:.2f} m): deck wetting / slamming, NOT modelled; linear result not valid"))
                elif worst_c[1] < 0.5 * worst_c[3]:
                    flags.append(("warn", f"{tag}deck corner {worst_c[0]}: minimum clearance to the wave surface {worst_c[1]:.2f} m "
                                          f"(relative motion {worst_c[2]:.2f} m of a {worst_c[3]:.2f} m freeboard)"))
        for lo, hi in nat["gap_resonance_bands_rad_s"]:
            if lo - 0.1 <= omega <= hi + 0.1:
                flags.append(("warn", f"wave frequency lies in a potential-flow gap-resonance band ({2*np.pi/hi:.2f}-{2*np.pi/lo:.2f} s): "
                                      "coefficients vary sharply and are over-predicted without viscous damping"))
        rpm = max((b.get("panel_size_m", 0.12) for b in self.hydro.meta.get("bodies", [])), default=self.hydro.meta.get("panel_size_m", 0.12)) * 0.55
        if lam / 8 < rpm:
            flags.append(("warn", f"wavelength {lam:.1f} m is short for the panel size: BEM resolution may be insufficient"))
        for lt in out.get("lines", []):
            if lt["goes_slack"]:
                flags.append(("warn", f"line {lt['id']}: dynamic tension amplitude {lt['dynamic_tension_amp_N']:.0f} N exceeds the pretension "
                                      f"{lt['pretension_N']:.0f} N -> the line would go slack and snatch (nonlinear, not modelled)"))
        worst_rel = {}
        for k_, v in (out.get("relative_motion") or {}).items():     # worst station per side / per pair only
            grp = k_.split("_x")[0]
            if v["min_clearance_m"] is not None and (grp not in worst_rel or v["min_clearance_m"] < worst_rel[grp][1]["min_clearance_m"]):
                worst_rel[grp] = (k_, v)
        for k_, v in worst_rel.values():
            if v["min_clearance_m"] is not None and v["min_clearance_m"] <= 0:
                flags.append(("error", f"relative motion at {k_}: amplitude {v['relative_motion_amp_m']:.2f} m exceeds the still clearance "
                                       f"{v['still_clearance_m']:.2f} m -> the hull would hit the EXO (contact not modelled, linear result invalid)"))
            elif v["min_clearance_m"] is not None and v["min_clearance_m"] < 0.5 * max(v["still_clearance_m"], 1e-9):
                flags.append(("warn", f"relative motion at {k_}: {v['relative_motion_amp_m']:.2f} m of a {v['still_clearance_m']:.2f} m clearance"))
        if self.nb > 1:
            flags.append(("info", "two-body result: the 0.19 m gap between the boat hull and the floats is under-resolved by the BEM panels and "
                                  "its viscous dissipation is not modelled; treat gap-resonance periods as indicative only"))
        return flags

    # ----------------------------------------------------------- time reconstruction
    def time_series(self, rw, t):
        """LINEAR reconstruction x(t) = Re(X e^{-i w t}) for all DOF (n = 6 x bodies) and the wave at the phase origin."""
        X = np.array([complex(a, b) for a, b in rw["X_complex"]])
        w = rw["omega"]
        x = np.real(X[None, :] * np.exp(-1j * w * np.asarray(t))[:, None])
        eta = (rw["H_m"] / 2) * np.cos(w * np.asarray(t))
        return x, eta

    # ----------------------------------------------------------- irregular waves
    def irregular(self, Hs, Tp, heading, gamma=3.3, damping=None, deck_points=None, n=400):
        """JONSWAP linear spectral statistics (ONLY a linear statistic; no nonlinear extremes)."""
        wl, wh = self.hydro.omegas[[0, -1]]
        w = np.linspace(wl, wh, n)
        wp = 2 * np.pi / Tp
        sig = np.where(w <= wp, 0.07, 0.09)
        S = (w ** -5) * np.exp(-1.25 * (wp / w) ** 4) * gamma ** np.exp(-((w - wp) ** 2) / (2 * sig ** 2 * wp ** 2))
        m0w = np.trapezoid(S, w)
        S = S * (Hs / 4) ** 2 / m0w
        wf = np.linspace(0.05, 12.0, 4000)
        sigf = np.where(wf <= wp, 0.07, 0.09)
        Sf = (wf ** -5) * np.exp(-1.25 * (wp / wf) ** 4) * gamma ** np.exp(-((wf - wp) ** 2) / (2 * sigf ** 2 * wp ** 2))
        frac_in = np.trapezoid(np.where((wf >= wl) & (wf <= wh), Sf, 0), wf) / np.trapezoid(Sf, wf)
        Xs = np.array([self.rao(wi, heading, damping) for wi in w])
        bodies_out = {}
        for bi, body in enumerate(self.bodies):
            res = {}
            for i, nme in enumerate(DOF):
                Sx = np.abs(Xs[:, 6 * bi + i]) ** 2 * S
                m0 = np.trapezoid(Sx, w)
                m2 = np.trapezoid(Sx * w ** 2, w)
                res[nme] = dict(sigma=float(np.sqrt(m0)), sig_amplitude=float(2 * np.sqrt(m0)),
                                Tz_s=float(2 * np.pi * np.sqrt(m0 / m2)) if m2 > 0 else None)
                if i >= 3:
                    res[nme]["sigma_deg"] = float(deg(np.sqrt(m0)))
            pts = {}
            for name, p in (body.get("deck_points") or (deck_points if bi == 0 else None) or {}).items():
                r = self.point_world_offset(p, bi)
                az = np.array([-wi ** 2 * (Xs[j, 6 * bi + 2] + np.cross(Xs[j, 6 * bi + 3:6 * bi + 6], r)[2]) for j, wi in enumerate(w)])
                m0 = np.trapezoid(np.abs(az) ** 2 * S, w)
                pts[name] = dict(sigma_vertical_accel_ms2=float(np.sqrt(m0)), sigma_vertical_accel_g=float(np.sqrt(m0) / self.g))
            bodies_out[body["name"]] = dict(response=res, points=pts)
        first = bodies_out[self.bodies[0]["name"]]
        return dict(Hs_m=Hs, Tp_s=Tp, gamma=gamma, heading_deg=deg(heading), energy_fraction_inside_band=float(frac_in),
                    response=first["response"], points=first["points"], bodies=bodies_out,
                    note="Linear spectral statistics (JONSWAP, long-crested). Sigma = RMS; significant single amplitude = 2 sigma. "
                         "Not an extreme-value, breaking-wave or capsize prediction.")


# ---------------------------------------------------------------- time-domain cross-check of the algebra
def time_domain_check(model, omega, heading, H, damping, steps_per_period=(16, 32, 64, 128), n_periods=None):
    """Integrate (M+A)x'' + (B+Bv)x' + Kx = Re(F A exp(-i w t)) with RK4 at FIXED coefficients A(w), B(w)
    and compare the steady oscillation amplitude with |X| from the frequency-domain solve.

    Verifies the frequency-domain algebra and the time-step convergence of the integrator (not the physics).
    Amplitude = least-squares sinusoid fit (with free offset for unrestrained DOFs) over the last period.
    """
    n = model.n
    A, B = model.hydro.coeffs(omega)
    F = model.hydro.excitation(omega, heading) * (H / 2)
    Bv = model.viscous_matrix(damping)
    Mt = model.M + A
    Bt = B + Bv
    K = model.K
    Minv = np.linalg.inv(Mt)
    X = np.linalg.solve(-omega ** 2 * Mt - 1j * omega * Bt + K, F)
    T = 2 * np.pi / omega
    ev = np.linalg.eigvals(np.block([[np.zeros((n, n)), np.eye(n)], [-Minv @ K, -Minv @ Bt]]))
    ev = ev[np.abs(ev) > 1e-8]
    nat_decay = float(np.min(-ev.real))
    if nat_decay <= 0:
        raise ValueError("system has non-decaying modes: add viscous damping for the time-domain check")
    if n_periods is None:
        n_periods = int(np.ceil(25.0 / nat_decay / T)) + 2
    out = []
    ref = np.abs(X)
    names = [f"{b['name']}_{d}" for b in model.bodies for d in DOF] if model.nb > 1 else DOF
    for N in steps_per_period:
        dt = T / N
        nsteps = int(n_periods * N)
        y = np.zeros(2 * n)

        def f(t, y):
            x, v = y[:n], y[n:]
            force = np.real(F * np.exp(-1j * omega * t))
            return np.concatenate([v, Minv @ (force - Bt @ v - K @ x)])
        hist = np.zeros((N + 1, n))
        t = 0.0
        k_last = nsteps - N
        for step in range(nsteps):
            if step == k_last:
                hist[0] = y[:n]
            k1 = f(t, y); k2 = f(t + dt / 2, y + dt / 2 * k1); k3 = f(t + dt / 2, y + dt / 2 * k2); k4 = f(t + dt, y + dt * k3)
            y = y + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
            t += dt
            if step >= k_last:
                hist[step - k_last + 1] = y[:n]
        tt = np.arange(N + 1) * dt
        basis = np.stack([np.cos(omega * tt), np.sin(omega * tt), np.ones_like(tt)], 1)
        coef = np.linalg.lstsq(basis, hist, rcond=None)[0]
        amp = np.hypot(coef[0], coef[1])
        rel = np.abs(amp - ref) / np.maximum(ref, 1e-6 * ref.max())
        out.append(dict(steps_per_period=N, dt_s=dt, n_periods=n_periods, max_rel_amp_error=float(rel.max()),
                        rel_error_by_dof={names[i]: float(rel[i]) for i in range(n)}))
    return dict(omega=omega, period_s=T, results=out, reference_amplitudes={names[i]: float(ref[i]) for i in range(n)})


def line_snatch_check(model, omega, heading, H, damping, speed=0.0, n_periods=14, steps_per_period=96):
    """Time-domain check of the UNILATERAL lines: the linear line stiffness is removed from K and replaced by the
    tension-only law T = max(0, k (L - L0)) evaluated on the instantaneous attachment positions (small rotations), with
    the hydrodynamic coefficients frozen at the (encounter) frequency - the same assumption as the frequency-domain
    model. Reports, per line, the peak and minimum tension, the fraction of the cycle spent slack and the snatch ratio
    (peak dynamic tension / linear-model amplitude), and the motion amplitudes compared with the linear solution.
    Nothing here is validated against measurements; it bounds the linear-line assumption, not reality."""
    n = model.n
    we = model.encounter_omega(omega, heading, speed)
    wl, wh = model.hydro.omegas[[0, -1]]
    A, B = model.hydro.coeffs(min(max(we, wl), wh))
    F = model.hydro.excitation(omega, heading) * (H / 2)
    Bv = model.viscous_matrix(damping)
    Mt = model.M + A
    Bt = B + Bv
    Minv = np.linalg.inv(Mt)
    # linear reference (same K including the linearised lines)
    X = np.linalg.solve(-we ** 2 * Mt - 1j * we * Bt + model.K, F)
    # hydrostatic/boat stiffness without the lines
    K_lines, _ = line_stiffness(model.lines, [b["pose"]["com_world"] for b in model.bodies]) if model.lines else (np.zeros((n, n)), [])
    K0 = model.K - K_lines
    coms = [np.asarray(b["pose"]["com_world"], float) for b in model.bodies]
    lines = []
    for ln in model.lines:
        a, b = np.asarray(ln["a_world"], float), np.asarray(ln["b_world"], float)
        L = float(np.linalg.norm(b - a))
        k = float(ln["stiffness_N_per_m"])
        T0 = float(ln["pretension_N"])
        if ln.get("slack") and k <= 0:
            k = float(ln.get("stiffness_N_per_m_nominal", 0.0) or 0.0)
        # unstretched length consistent with the static solution (slack lines: the recorded unstretched length)
        L0 = float(ln.get("unstretched_length_m", L - (T0 / k if k > 0 else 0.0)))
        lines.append(dict(id=ln["id"], i=ln["body_i"], j=ln["body_j"], ra=a - coms[ln["body_i"]], rb=b - coms[ln["body_j"]], k=k, L0=L0, T0=T0))

    def line_forces(x):
        f = np.zeros(n)
        Ts = []
        for ln in lines:
            i, j = ln["i"], ln["j"]
            ui, ti = x[6 * i:6 * i + 3], x[6 * i + 3:6 * i + 6]
            uj, tj = x[6 * j:6 * j + 3], x[6 * j + 3:6 * j + 6]
            pa = coms[i] + ln["ra"] + ui + np.cross(ti, ln["ra"])
            pb = coms[j] + ln["rb"] + uj + np.cross(tj, ln["rb"])
            d = pb - pa
            L = np.linalg.norm(d)
            u = d / L if L > 1e-12 else np.zeros(3)
            T = max(0.0, ln["k"] * (L - ln["L0"])) if ln["k"] > 0 else 0.0
            Ts.append(T)
            Fa = T * u                     # on body i, toward body j
            f[6 * i:6 * i + 3] += Fa; f[6 * i + 3:6 * i + 6] += np.cross(ln["ra"] + ui * 0, Fa)
            f[6 * j:6 * j + 3] -= Fa; f[6 * j + 3:6 * j + 6] += np.cross(ln["rb"], -Fa)
        return f, Ts

    # the static line forces are already balanced by the hydrostatics in the equilibrium: subtract them so that x = 0
    # is the rest state (only the DYNAMIC part of the line force drives the motion)
    f_static, T_static = line_forces(np.zeros(n))
    T_e = 2 * np.pi / we
    dt = T_e / steps_per_period
    nsteps = int(n_periods * steps_per_period)
    y = np.zeros(2 * n)

    def rhs(t, y):
        x, v = y[:n], y[n:]
        fl, _ = line_forces(x)
        force = np.real(F * np.exp(-1j * we * t)) + (fl - f_static)
        return np.concatenate([v, Minv @ (force - Bt @ v - K0 @ x)])
    hist_x = np.zeros((steps_per_period * 2 + 1, n))
    hist_T = np.zeros((steps_per_period * 2 + 1, len(lines)))
    t = 0.0
    keep_from = nsteps - 2 * steps_per_period
    for s in range(nsteps + 1):
        if s >= keep_from:
            hist_x[s - keep_from] = y[:n]
            hist_T[s - keep_from] = line_forces(y[:n])[1]
        if s == nsteps:
            break
        k1 = rhs(t, y); k2 = rhs(t + dt / 2, y + dt / 2 * k1); k3 = rhs(t + dt / 2, y + dt / 2 * k2); k4 = rhs(t + dt, y + dt * k3)
        y = y + dt / 6 * (k1 + 2 * k2 + 2 * k3 + k4)
        t += dt
    amp_nl = (hist_x.max(0) - hist_x.min(0)) / 2
    amp_lin = np.abs(X)
    names = [f"{b['name']}_{d}" for b in model.bodies for d in DOF] if model.nb > 1 else list(DOF)
    out_lines = []
    for q, ln in enumerate(lines):
        Tq = hist_T[:, q]
        lin_amp = None
        for lt in (getattr(model, "_last_linear_lines", None) or []):
            if lt["id"] == ln["id"]:
                lin_amp = lt["tension_amp_N"]
        out_lines.append(dict(id=ln["id"], static_N=float(T_static[q]), peak_N=float(Tq.max()), min_N=float(Tq.min()),
                              slack_fraction_of_cycle=float((Tq <= 1e-6).mean()), dynamic_peak_N=float(Tq.max() - T_static[q]),
                              linear_amp_N=lin_amp,
                              snatch_ratio=(float((Tq.max() - T_static[q]) / lin_amp) if lin_amp else None)))
    return dict(omega_e=float(we), period_e_s=float(T_e), n_periods=n_periods, steps_per_period=steps_per_period,
                amplitude_nonlinear={nm: float(a) for nm, a in zip(names, amp_nl)}, amplitude_linear={nm: float(a) for nm, a in zip(names, amp_lin)},
                max_amplitude_ratio=float(np.max(amp_nl / np.maximum(amp_lin, 1e-9))) if n else None,
                lines=out_lines,
                note="RK4 with hydrodynamic coefficients frozen at the encounter frequency; tension-only lines on the instantaneous geometry "
                     "(small rotations); the static line forces are balanced by the equilibrium. Bounds the linearised-line assumption only.")
