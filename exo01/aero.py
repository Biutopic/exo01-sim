"""Wind loads on the EXO + host boat: projected areas above the waterline, then a first-harmonic force model.

The projected areas of the FLOATS and the HULL are computed from the same meshes the buoyancy model uses, clipped
above z = 0 at the current pose - so they follow trim and heel and are not typed in. Everything that is not in a
mesh (the EXO frame, its solar panels, the boat's cabin) is an explicit input: the frame and panels come from the
configuration's `aero` block, and the cabin is integrated from `host_boat.clearance_reference.boat_cabin_stations_mm`,
which is real recorded geometry.

The force model is the standard first-harmonic form used for ships, with the apparent wind angle beta measured from
the bow (0 = head wind, 90 deg = wind on the port beam):

    q   = ½ ρ_air V_app²
    F_x = -q · Cx0 · cos(beta) · A_front          along +x (so a head wind gives -x, a drag)
    F_y =  q · Cy0 · sin(beta) · A_lat
    M_z =  q · Cn0 · sin(2·beta) · A_lat · L      yaw, the weather-vaning couple
    M_x =  F_y · z_lat                            heel, the lateral force acting at the lateral area centroid

The three coefficients are ASSUMED (see `aero.coefficients`): a bluff small-craft superstructure is of order
Cx0 ≈ 0.8, Cy0 ≈ 1.0, Cn0 ≈ 0.1. The sin(2·beta) yaw form means the couple vanishes head-on and on the beam and
peaks near 45 deg, which is the behaviour that matters for a coupling that has to hold yaw.

What this does NOT model: gusts (a steady wind only), the interference between the EXO's frame and the boat's cabin
(each body's areas are computed independently, so the pair's total is an over-estimate when one shelters the other),
vertical wind force or the lift of a tilted panel array, and any Reynolds dependence of the coefficients.
"""
from __future__ import annotations

import numpy as np

from .buoyancy import clip_below

RHO_AIR = 1.225          # kg/m3 at 15 C, sea level
KNOT = 0.514444


def _clip_above(tris):
    """The part of a triangle set ABOVE z = 0, by mirroring z and reusing the buoyancy clipper."""
    t = np.asarray(tris, float).copy()
    t[:, :, 2] *= -1.0
    up, _ = clip_below(t)
    if len(up) == 0:
        return np.zeros((0, 3, 3))
    up = np.asarray(up, float).copy()
    up[:, :, 2] *= -1.0
    return up


def _projected(tris, axis):
    """Projected area along `axis` (0=x frontal, 1=y lateral, 2=z plan) counting only faces whose outward normal has a
    positive component on that axis - the front half of a closed body, which is exact for a convex shape and an
    over-estimate for a train of floats (the same convention propulsion.py uses for the submerged frontal area).

    Returns (area, centroid of that projected area).
    """
    if len(tris) == 0:
        return 0.0, np.zeros(3)
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    n = np.cross(b - a, c - a)
    w = np.maximum(n[:, axis], 0.0) / 2.0
    tot = float(w.sum())
    if tot <= 1e-12:
        return 0.0, np.zeros(3)
    cen = (a + b + c) / 3.0
    return tot, (w[:, None] * cen).sum(0) / tot


def mesh_windage(tris_world):
    """Above-water frontal, lateral and plan areas of a mesh at its current pose, with the area centroids."""
    up = _clip_above(tris_world)
    Af, cf = _projected(up, 0)
    Al, cl = _projected(up, 1)
    Ap, cp = _projected(up, 2)
    zmax = float(up[:, :, 2].max()) if len(up) else 0.0
    xext = (float(up[:, :, 0].min()), float(up[:, :, 0].max())) if len(up) else (0.0, 0.0)
    return dict(A_front_m2=Af, A_lateral_m2=Al, A_plan_m2=Ap,
                front_centroid=cf.tolist(), lateral_centroid=cl.tolist(), plan_centroid=cp.tolist(),
                z_max_m=zmax, x_extent_m=xext)


def cabin_windage(stations_mm, deck_z_m):
    """Frontal and lateral area of a superstructure given as (x, half_width, top_z) stations, in the boat frame.

    Real recorded geometry (clearance_reference.boat_cabin_stations_mm), integrated rather than assumed:
      lateral area  = integral of (top - deck) dx          (one side's silhouette)
      frontal area  = max over x of 2·half_width·(top-deck) (the widest, tallest section presented to a head wind)
    """
    st = np.asarray(stations_mm, float) / 1000.0
    if st.size == 0:
        return dict(A_front_m2=0.0, A_lateral_m2=0.0, lateral_centroid_x_m=0.0, lateral_centroid_z_m=0.0, z_max_m=0.0)
    x, hw, top = st[:, 0], st[:, 1], st[:, 2]
    h = np.maximum(top - deck_z_m, 0.0)
    # trapezoidal integration of the side silhouette, with its centroid
    dx = np.diff(x)
    hm = 0.5 * (h[:-1] + h[1:])
    seg = dx * hm
    A_lat = float(seg.sum())
    xm = 0.5 * (x[:-1] + x[1:])
    zm = deck_z_m + 0.5 * hm
    cx = float((seg * xm).sum() / A_lat) if A_lat > 1e-9 else 0.0
    cz = float((seg * zm).sum() / A_lat) if A_lat > 1e-9 else deck_z_m
    A_front = float(np.max(2.0 * hw * h)) if len(h) else 0.0
    return dict(A_front_m2=A_front, A_lateral_m2=A_lat, lateral_centroid_x_m=cx, lateral_centroid_z_m=cz,
                z_max_m=float(top.max()))


def aero_config(cfg):
    """The `aero` block, with documented defaults so an older configuration still works."""
    a = dict((cfg.get("aero") or {}))
    c = dict(Cx0=0.80, Cy0=1.00, Cn0=0.10,
             note="ASSUMED first-harmonic wind coefficients for a bluff small-craft superstructure. Cx0 and Cy0 are "
                  "referred to the frontal and lateral projected areas respectively; Cn0 to A_lateral x L. No "
                  "measurement, no wind-tunnel or CFD basis.")
    c.update(a.get("coefficients") or {})
    f = dict(frame_A_front_m2=None, frame_A_lateral_m2=None, frame_centroid_z_m=None,
             panel_A_plan_m2=None, panel_tilt_deg=0.0, panel_centroid_z_m=None,
             note="EXO frame and solar array windage. These are NOT in any mesh, so they are explicit inputs. When "
                  "left null they are derived from the frame envelope in clearance_reference and flagged DERIVED.")
    f.update(a.get("exo_structure") or {})
    return dict(coefficients=c, exo_structure=f, rho_air_kg_m3=float(a.get("rho_air_kg_m3", RHO_AIR)))


def derive_exo_structure(cfg, float_windage):
    """Frame, module and panel windage from the dimensional envelope in the cahier des charges.

    Grounded in recorded spec rather than guessed: the envelope (height 3,00 m, width 4,50 m, length 9,00 m, air
    draft 3,80 m on the Erdre) and the panel count and size are real. The two SOLIDITY ratios - what fraction of
    that silhouette is actually structure, given an open tube frame, a trampoline, two 4,20 x 1,60 m modules and a
    panel roof - are assumed, and they are the dominant uncertainty in any wind number here.

    Flat panels present no frontal area; a tilted array does, and the tilt is an input because it matters: at 20 deg
    the array adds over 5 m2 of frontal area, which is comparable to the whole frame silhouette.
    """
    env = cfg.get("envelope") or {}
    ae = (cfg.get("aero") or {}).get("exo_structure") or {}
    H = float(env.get("height_max_m") or 3.00)                 # above the waterline, consistent with the air draft
    W = float(env.get("width_max_m") or 4.50)
    sf = float(ae.get("solidity_frontal", 0.45))
    sl = float(ae.get("solidity_lateral", 0.40))
    L_exo = 5.20                                                # EXO frame fore-and-aft extent (not the 9 m envelope,
                                                                # which includes the host boat's overhang)
    z_float_top = max(float(float_windage.get("z_max_m") or 0.0), 0.0)
    h = max(H - z_float_top, 0.0)
    n = int(ae.get("panel_count", 0) or 0)
    a_each = float(ae.get("panel_area_each_m2", 0.0) or 0.0)
    panel_plan = float(ae.get("panel_area_total_m2") or (n * a_each))
    return dict(frame_A_front_m2=round(W * h * sf, 3),
                frame_A_lateral_m2=round(L_exo * h * sl, 3),
                frame_centroid_z_m=round(z_float_top + 0.5 * h, 3),
                panel_A_plan_m2=round(panel_plan, 3),
                panel_tilt_deg=float(ae.get("panel_tilt_deg", 0.0) or 0.0),
                panel_centroid_z_m=round(H, 3),
                envelope_height_m=H, envelope_width_m=W, exo_length_m=L_exo,
                solidity_frontal=sf, solidity_lateral=sl, derived=True,
                note="DERIVED from the recorded envelope (height, width) x an ASSUMED solidity. The envelope and the "
                     "panel geometry are real; the two solidity ratios are not measured and dominate the uncertainty. "
                     "Vertical wind force and the lift of a tilted array are not modelled.")


def body_areas(cfg, float_tris_world=None, hull_tris_world=None, include_exo_structure=True):
    """Collect the windage areas of each body at the current pose."""
    ac = aero_config(cfg)
    out = {}
    if float_tris_world is not None:
        fw = mesh_windage(float_tris_world)
        ex = dict(ac["exo_structure"])
        if ex.get("frame_A_front_m2") is None:
            ex = {**ex, **derive_exo_structure(cfg, fw)}
        tilt = np.radians(float(ex.get("panel_tilt_deg") or 0.0))
        panel_front = float(ex.get("panel_A_plan_m2") or 0.0) * abs(np.sin(tilt))
        A_front = fw["A_front_m2"] + (float(ex.get("frame_A_front_m2") or 0.0) + panel_front
                                      if include_exo_structure else 0.0)
        A_lat = fw["A_lateral_m2"] + (float(ex.get("frame_A_lateral_m2") or 0.0) + panel_front
                                      if include_exo_structure else 0.0)
        zc = ex.get("frame_centroid_z_m")
        z_lat = (float(zc) if zc is not None else fw["lateral_centroid"][2]) if include_exo_structure \
            else fw["lateral_centroid"][2]
        L = max(fw["x_extent_m"][1] - fw["x_extent_m"][0], 1.0)
        out["EXO"] = dict(A_front_m2=A_front, A_lateral_m2=A_lat, z_lateral_m=z_lat, L_m=L,
                          floats=fw, structure=ex)
    if hull_tris_world is not None:
        hw = mesh_windage(hull_tris_world)
        cr = (cfg.get("host_boat") or {}).get("clearance_reference") or {}
        deck = float(((cfg.get("host_boat") or {}).get("buoyant_surface") or {}).get("topside_top_mm") or 780) / 1000.0
        cab = cabin_windage(cr.get("boat_cabin_stations_mm") or [], deck)
        A_front = hw["A_front_m2"] + cab["A_front_m2"]
        A_lat = hw["A_lateral_m2"] + cab["A_lateral_m2"]
        # lateral centroid height, area-weighted between the freeboard strip and the cabin side
        num = hw["A_lateral_m2"] * hw["lateral_centroid"][2] + cab["A_lateral_m2"] * cab["lateral_centroid_z_m"]
        z_lat = num / A_lat if A_lat > 1e-9 else deck
        L = max(hw["x_extent_m"][1] - hw["x_extent_m"][0], 1.0)
        out["BOAT"] = dict(A_front_m2=A_front, A_lateral_m2=A_lat, z_lateral_m=z_lat, L_m=L,
                           hull=hw, cabin=cab)
    out["_coefficients"] = ac["coefficients"]
    out["_rho_air_kg_m3"] = ac["rho_air_kg_m3"]
    return out


def apparent_wind(U_ground, V_true, wind_from_deg):
    """Apparent wind seen by a body making way at U_ground along +x, with the true wind blowing FROM wind_from_deg
    (0 = from dead ahead, 90 = from the port beam). Returns (V_app, beta_deg)."""
    th = np.radians(float(wind_from_deg))
    # true wind velocity vector (what the air is doing), blowing from the given bearing
    wx, wy = -float(V_true) * np.cos(th), -float(V_true) * np.sin(th)
    # air velocity relative to the boat
    ax, ay = wx - float(U_ground), wy
    V = float(np.hypot(ax, ay))
    beta = float(np.degrees(np.arctan2(-ay, -ax)))      # direction the apparent wind comes FROM, 0 = ahead
    return V, beta


def wind_wrench(areas_body, V_app, beta_deg, coeffs=None, rho_air=RHO_AIR):
    """Force and moment on one body from a steady apparent wind. Returns a dict with F (3,) and M (3,) about the
    body's own reference point, in body axes."""
    c = dict(Cx0=0.80, Cy0=1.00, Cn0=0.10)
    c.update(coeffs or {})
    q = 0.5 * float(rho_air) * float(V_app) ** 2
    b = np.radians(float(beta_deg))
    Af = float(areas_body["A_front_m2"])
    Al = float(areas_body["A_lateral_m2"])
    L = float(areas_body["L_m"])
    z = float(areas_body["z_lateral_m"])
    Fx = -q * c["Cx0"] * np.cos(b) * Af
    Fy = q * c["Cy0"] * np.sin(b) * Al
    Mz = q * c["Cn0"] * np.sin(2.0 * b) * Al * L
    Mx = Fy * z                                          # heeling moment about the waterline
    return dict(F=np.array([Fx, Fy, 0.0]), M=np.array([Mx, 0.0, Mz]),
                q_Pa=q, beta_deg=float(beta_deg), V_app_m_s=float(V_app),
                A_front_m2=Af, A_lateral_m2=Al, coefficients=c)
