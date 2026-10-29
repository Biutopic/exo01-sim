"""Quasi-static propulsion / towing of the EXO + host boat: thrust setting -> steady speed -> forces on each body.

Every coefficient is an explicit, editable assumption from the configuration's `propulsion` block. The model is
deliberately simple and transparent:

  thrust      T = fraction x bollard thrust, taken constant with speed (optimistic at speed)
  EXO         R_e(U) = sum over the two float rows of  ½ ρ U² [ (1+k) C_f(Re) S_wet + C_d A_front ]
  boat        R_b(U) = ½ ρ U² S_wet [ (1+k) C_f(Re) a_app + c_R (Fr/0.2)^n ]
  speed       T = R_e(U) + R_b(U)   (brentq)

with C_f the ITTC-57 line, Re = U L / ν on each body's immersed length, Fr = U / sqrt(g L_wl) for the boat, S_wet and
A_front from the clipped buoyant surfaces at the current poses. The drag of a body acts at the depth of its submerged
centroid (centre of buoyancy) and along the thrust axis (steering holds the assembly straight: yaw moments from any
lateral offset of the drag centroids are reported, not solved). The thrust acts at the configured points, along the
body +x axis. The resulting world-frame forces and moments about each COM feed the (coupled) static equilibrium, so the
trim, heel and the line tensions/slack reflect the push or tow. No wave-added resistance, wind or current.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from .buoyancy import clip_below
from .twobody import to_world

KNOT = 0.514444


def itt57(Re):
    Re = max(float(Re), 1e3)
    return 0.075 / (np.log10(Re) - 2.0) ** 2


def wetted_geometry(tris_world):
    """Wetted area, immersed length (x-extent), submerged centroid and frontal (y-z projected) area of the part below z=0."""
    wet, _ = clip_below(np.asarray(tris_world, float))
    if len(wet) == 0:
        return dict(S_wet=0.0, L_wl=0.0, centroid=np.zeros(3), A_front=0.0)
    a, b, c = wet[:, 0], wet[:, 1], wet[:, 2]
    n = np.cross(b - a, c - a)
    area = 0.5 * np.linalg.norm(n, axis=1)
    # volume centroid via divergence theorem (F = (x²/2, y²/2, z²/2) over the closed clipped surface + waterplane cap,
    # cap contributes nothing to x,y and to V): same integrals as wet_integrals but kept local here for the frontal area
    V = float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)
    cen = (a + b + c) / 3.0
    nz = n  # (unnormalised)
    Mx = float((nz[:, 0] * (a[:, 0] ** 2 + b[:, 0] ** 2 + c[:, 0] ** 2 + a[:, 0] * b[:, 0] + b[:, 0] * c[:, 0] + c[:, 0] * a[:, 0]) / 24.0).sum())
    My = float((nz[:, 1] * (a[:, 1] ** 2 + b[:, 1] ** 2 + c[:, 1] ** 2 + a[:, 1] * b[:, 1] + b[:, 1] * c[:, 1] + c[:, 1] * a[:, 1]) / 24.0).sum())
    Mz = float((nz[:, 2] * (a[:, 2] ** 2 + b[:, 2] ** 2 + c[:, 2] ** 2 + a[:, 2] * b[:, 2] + b[:, 2] * c[:, 2] + c[:, 2] * a[:, 2]) / 24.0).sum())
    centroid = np.array([Mx, My, Mz]) / V if V > 1e-12 else cen.mean(0)
    # frontal area: projection of the wetted surface on the y-z plane, counting only faces whose normal has a +x component
    # (the "front" half of a closed body) - exact for convex bodies, an over-estimate for a train of floats
    A_front = float(np.maximum(n[:, 0], 0.0).sum() / 2.0)
    return dict(S_wet=float(area.sum()), L_wl=float(wet[:, :, 0].max() - wet[:, :, 0].min()), centroid=centroid, A_front=A_front)


def exo_geometry(asm, eq):
    """Per-row wetted area, immersed length and max frontal area at a pose (the expensive part, pose-dependent only)."""
    rows = {}
    for i, s in enumerate(asm.surfaces):
        key = "port" if float(s.centre[1]) > 0 else "starboard"
        wt = asm.world_tris(eq["R"], eq["G_body"], eq["zG"], which=i)
        g = wetted_geometry(wt)
        r = rows.setdefault(key, dict(S_wet=0.0, xmin=1e9, xmax=-1e9, A_front_max=0.0))
        r["S_wet"] += g["S_wet"]
        r["A_front_max"] = max(r["A_front_max"], g["A_front"])
        wet, _ = clip_below(wt)
        if len(wet):
            r["xmin"] = min(r["xmin"], float(wet[:, :, 0].min())); r["xmax"] = max(r["xmax"], float(wet[:, :, 0].max()))
    return rows


def exo_resistance_from_geometry(rows, rho, nu, c, U):
    total, detail = 0.0, {}
    for key, r in rows.items():
        L = max(r["xmax"] - r["xmin"], 0.1)
        Re = U * L / nu
        Cf = itt57(Re)
        q = 0.5 * rho * U * U
        Rf = q * (1.0 + c["form_factor_k"]) * Cf * r["S_wet"]
        Rp = q * c["pressure_drag_cd"] * r["A_front_max"]
        detail[key] = dict(S_wet_m2=r["S_wet"], immersed_length_m=L, Re=Re, Cf=Cf, friction_N=Rf, pressure_N=Rp, A_front_m2=r["A_front_max"])
        total += Rf + Rp
    return total, detail


def exo_resistance(asm, eq, rho, nu, c, U):
    """Resistance of the EXO floats (both rows) at speed U: friction (ITTC-57, form factor) + pressure drag on the frontal
    area of ONE float per row (nose/flat-end junctions); S_wet and A_front from the clipped float surfaces."""
    return exo_resistance_from_geometry(exo_geometry(asm, eq), rho, nu, c, U)


def boat_geometry(basm, beq):
    return wetted_geometry(basm.world_tris(beq["R"], beq["G_body"], beq["zG"]))


def boat_resistance_from_geometry(geo, rho, g, nu, c, U):
    L = max(geo["L_wl"], 0.5)
    Re = U * L / nu
    Cf = itt57(Re)
    Fr = U / np.sqrt(g * L)
    q = 0.5 * rho * U * U
    Rf = q * geo["S_wet"] * (1.0 + c["form_factor_k"]) * Cf * c["appendage_factor"]
    Rr = q * geo["S_wet"] * c["residuary_c_at_fr02"] * (Fr / 0.2) ** c["residuary_exponent"]
    return Rf + Rr, dict(S_wet_m2=geo["S_wet"], L_wl_m=L, Re=Re, Cf=Cf, Fr=Fr, friction_N=Rf, residuary_N=Rr)


def boat_resistance(basm, beq, rho, g, nu, c, U):
    return boat_resistance_from_geometry(boat_geometry(basm, beq), rho, g, nu, c, U)


def propulsion_setting(cfg):
    """(fraction, unit id) from the resolved config; fraction 0 / missing = off."""
    p = cfg.get("propulsion") or {}
    f = float(p.get("thrust_fraction") or 0.0)
    unit = p.get("unit") or "EXO_PODS"
    return max(0.0, min(f, 1.0)), unit


class PropulsionModel:
    """Holds the geometry needed to evaluate thrust/drag at any pose; `external(pe, pb)` is the callable for the coupled
    solver, `external_exo_only(pe)` the (Fz, Mx, My) wrench for the single-body solver."""

    def __init__(self, cfg, asm, basm, rho, g):
        self.cfg, self.asm, self.basm, self.rho, self.g = cfg, asm, basm, rho, g
        p = cfg["propulsion"]
        self.frac, self.unit_id = propulsion_setting(cfg)
        self.unit = p["units"][self.unit_id]
        self.res = p["resistance"]
        self.nu = float(self.res["nu_m2_s"])
        self.bollard = self.unit.get("bollard_thrust_N")
        self.T = None if self.bollard is None else self.frac * float(self.bollard)
        self.U = 0.0
        self.R_e = self.R_b = 0.0
        self.detail = {}

    # ---- speed from the balance thrust = resistance (poses enter through S_wet / A_front)
    def solve_speed(self, eq_e, eq_b):
        c_e, c_b = self.res["exo"], self.res["boat"]
        geo_e = exo_geometry(self.asm, eq_e)                                         # pose-dependent geometry once
        geo_b = boat_geometry(self.basm, eq_b) if (self.basm is not None and eq_b is not None) else None

        def total(U):
            Re_, _ = exo_resistance_from_geometry(geo_e, self.rho, self.nu, c_e, U)
            Rb_ = boat_resistance_from_geometry(geo_b, self.rho, self.g, self.nu, c_b, U)[0] if geo_b is not None else 0.0
            return Re_ + Rb_

        # the horizontal component of the thrust balances the (horizontal) resistance; the vertical component T sin(trim)
        # goes into the vertical/pitch balance of the thrusting body
        eq_unit = eq_b if (self.unit["body"] == "BOAT" and eq_b is not None) else eq_e
        d = np.asarray(eq_unit["R"], float) @ np.asarray(self.unit["direction_body"], float)
        self.thrust_horizontal_factor = float(np.hypot(d[0], d[1]))
        T_h = (self.T or 0.0) * self.thrust_horizontal_factor
        if not self.T or self.T <= 0:
            self.U = 0.0
        else:
            f = lambda U: total(U) - T_h   # noqa: E731
            hi = 1.0
            while f(hi) < 0 and hi < 30:
                hi *= 2
            self.U = brentq(f, 0.0, hi, xtol=1e-6) if f(hi) >= 0 else hi
        self.R_e, de = exo_resistance_from_geometry(geo_e, self.rho, self.nu, c_e, self.U)
        self.R_b, db = (boat_resistance_from_geometry(geo_b, self.rho, self.g, self.nu, c_b, self.U) if geo_b is not None else (0.0, {}))
        self.detail = dict(exo=de, boat=db)
        # drag application points, frozen in each BODY frame at this pose (submerged centroid x,z; y on the centreline):
        # keeps the Newton iterations of the equilibrium cheap; refreshed by the caller's outer pass
        ge = wetted_geometry(self.asm.world_tris(eq_e["R"], eq_e["G_body"], eq_e["zG"]))
        G_e = np.asarray(eq_e["G_body"], float)
        pe_body = np.asarray(eq_e["R"]).T @ (ge["centroid"] - np.array([0.0, 0.0, eq_e["zG"]])) + G_e     # world_tris: COM at (0,0,zG)
        self.drag_body_e = np.array([pe_body[0], 0.0, pe_body[2]])
        self.drag_centroid_y_e = float(ge["centroid"][1])
        self.drag_body_b = None
        if self.basm is not None and eq_b is not None:
            gb = wetted_geometry(self.basm.world_tris(eq_b["R"], eq_b["G_body"], eq_b["zG"]))
            G_b = np.asarray(eq_b["G_body"], float)
            pb_body = np.asarray(eq_b["R"]).T @ (gb["centroid"] - np.array([0.0, 0.0, eq_b["zG"]])) + G_b
            self.drag_body_b = np.array([pb_body[0], 0.0, pb_body[2]])
            self.drag_centroid_y_b = float(gb["centroid"][1])
        return self.U

    def state(self):
        return dict(U=self.U, R_e=self.R_e, R_b=self.R_b, detail=self.detail, drag_body_e=self.drag_body_e, drag_body_b=self.drag_body_b,
                    thf=getattr(self, "thrust_horizontal_factor", 1.0))

    def restore(self, st):
        self.U, self.R_e, self.R_b, self.detail = st["U"], st["R_e"], st["R_b"], st["detail"]
        self.drag_body_e, self.drag_body_b, self.thrust_horizontal_factor = st["drag_body_e"], st["drag_body_b"], st["thf"]

    # ---- forces at a pose (world frame, moments about each COM)
    def _thrust_world(self, pose):
        pts = [to_world(pose, p) for p in self.unit["thrust_points_m"]]
        d = np.asarray(pose["R_world"]) @ np.asarray(self.unit["direction_body"], float)
        return pts, d

    def wrenches(self, pe, pb):
        """(F_e, M_e, F_b, M_b): thrust on the unit's body, drag on each body along the thrust axis. World frame; moments
        about each COM. `world_tris` places a body's COM at the horizontal origin, so all levers are COM-relative."""
        Fe = np.zeros(3); Me = np.zeros(3); Fb = np.zeros(3); Mb = np.zeros(3)
        if not self.T:
            return Fe, Me, Fb, Mb
        on_boat = self.unit["body"] == "BOAT"
        pose_t = pb if on_boat else pe
        pts, d = self._thrust_world(pose_t)
        ct = np.asarray(pose_t["com_world"], float)
        Ft = self.T / len(pts) * d
        for p in pts:
            r = np.asarray(p, float) - ct
            if on_boat:
                Fb += Ft; Mb += np.cross(r, Ft)
            else:
                Fe += Ft; Me += np.cross(r, Ft)
        # drag: -R along the horizontal projection of the thrust axis, at the body-frame drag points frozen by solve_speed
        # (submerged centroid x,z on the body centreline): the pilot steers; lateral centroid offsets are reported only
        dh = np.array([d[0], d[1], 0.0]); dh /= max(np.linalg.norm(dh), 1e-9)
        ce = np.asarray(pe["com_world"], float)
        pe_drag = to_world(pe, self.drag_body_e)
        Fd = -self.R_e * dh
        Fe += Fd; Me += np.cross(pe_drag - ce, Fd)
        pb_drag = None
        if pb is not None and self.drag_body_b is not None:
            cb = np.asarray(pb["com_world"], float)
            pb_drag = to_world(pb, self.drag_body_b)
            Fd = -self.R_b * dh
            Fb += Fd; Mb += np.cross(pb_drag - cb, Fd)
            pb_drag = pb_drag.tolist()
        self.last_points = dict(thrust=[list(map(float, p)) for p in pts], drag_exo=pe_drag.tolist(), drag_boat=pb_drag,
                                drag_centroid_y_offset_exo_m=self.drag_centroid_y_e,
                                drag_centroid_y_offset_boat_m=getattr(self, "drag_centroid_y_b", None),
                                note="drag applied on each body's centreline at its submerged-centroid x,z; the y offsets show the "
                                     "lateral eccentricity of the true drag centroid that the steering must hold")
        return Fe, Me, Fb, Mb

    def external(self, pe, pb):
        return self.wrenches(pe, pb)

    def external_exo_only(self, pe):
        Fe, Me, _, _ = self.wrenches(pe, None)
        return np.array([Fe[2], Me[0], Me[1]])

    def summary(self, lines=None, info=None):
        T = self.T or 0.0
        out = dict(unit=self.unit_id, unit_title=self.unit["title"], thrust_fraction=self.frac, bollard_thrust_N=self.bollard,
                   thrust_total_N=T, thrust_horizontal_N=T * getattr(self, "thrust_horizontal_factor", 1.0),
                   thrust_points_world=getattr(self, "last_points", {}).get("thrust"),
                   speed_m_s=self.U, speed_kn=self.U / KNOT,
                   resistance=dict(exo_N=self.R_e, boat_N=self.R_b, total_N=self.R_e + self.R_b, breakdown=self.detail),
                   drag_points_world=getattr(self, "last_points", None),
                   line_load_N=(self.R_b if self.unit["body"] == "EXO" else self.R_e),
                   line_load_note=("force the lines must transmit: the boat's resistance when the EXO pushes, the EXO's resistance when the boat tows"),
                   label=self.cfg["propulsion"]["label"], notes=[self.cfg["propulsion"]["thrust_model"]["note"],
                                                                    self.res["exo"]["note"], self.res["boat"]["note"]])
        if self.bollard is None:
            out["notes"].insert(0, f"bollard thrust of {self.unit_id} is null in this configuration: nothing computed")
        if info is not None:
            out["coupled"] = dict(converged=info.get("converged"), external_net_force=info.get("external_net_force"),
                                  all_lines_slack=info.get("all_lines_slack"))
        if lines is not None:
            out["lines"] = [dict(id=l["id"], tension_N=l["tension_N"], slack=l["slack"]) for l in lines]
        return out
