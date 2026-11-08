"""Speed, thrust, wind and energy for the EXO + host boat.

What this adds over `propulsion.py`, whose docstring records its own gaps ("thrust taken constant with speed
(optimistic at speed)" and "No wave-added resistance, wind or current"):

  * **Thrust that falls with speed.** Three models, deliberately kept as a band rather than one guessed curve:
      `constant`        T = T0                       - what the project assumed; a hard upper bound
      `constant_power`  T = min(T0, P_water / U)     - fixed power to the water; the usual engineering lower bound
      `momentum`        actuator disk, T = 2ρA(U+w)w with w from P_water = T(U+w)   - the physical one, in between
    All three are pinned to the same bollard thrust, so they agree at U = 0 and diverge with speed. The spread IS
    the answer until the pod's real thrust curve is available.

  * **Wind**, through `aero.py`: the apparent wind at speed, its drag added to the hydrodynamic resistance, and its
    side force and yaw moment available as a coupling load case.

  * **Current**, by separating speed through the water from speed over ground. Resistance is a function of speed
    through the water; the wind sees speed over ground.

  * **Energy**: endurance and range from the recorded battery, and the solar-neutral speed - the speed the array can
    sustain indefinitely, which for a solar boat is a more useful number than maximum speed.

A note on the pod data. The recorded pair (62 kgf bollard, 5 kW electrical per pod) implies, under ideal momentum
theory for a rim drive of plausible disk area, only 20-30 % overall electrical-to-water efficiency. A rim drive
should do better than that, so either the 62 kgf is conservative or the 5 kW is a peak rather than a continuous
rating. `implied_efficiency()` reports it so the inconsistency is visible rather than buried in a max-speed number.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from . import aero
from .propulsion import boat_resistance_from_geometry, exo_resistance_from_geometry, itt57  # noqa: F401

KNOT = 0.514444
RHO_WATER = 1000.0


# ───────────────────────────────────────────────────────────────── thrust curves
def induced_velocity(T0, A_disk, rho=RHO_WATER):
    """Induced velocity at the disk at bollard, from T0 = 2 ρ A w²."""
    A = max(float(A_disk), 1e-6)
    return float(np.sqrt(max(float(T0), 0.0) / (2.0 * rho * A)))


def induced_velocity_at_speed(T, A_disk, U, rho=RHO_WATER):
    """Induced velocity that produces thrust T at forward speed U, from T = 2 ρ A (U + w) w.

    At U = 0 this reduces to the bollard relation. Using the bollard relation AT SPEED overstates the water power
    by about 25 % at 2.4 m/s, which is how a 10 kW installation came out drawing 12.6 kW.
    """
    A = max(float(A_disk), 1e-6)
    U = max(float(U), 0.0)
    return float(0.5 * (-U + np.sqrt(U * U + 2.0 * max(float(T), 0.0) / (rho * A))))


def water_power_at_bollard(T0, A_disk, rho=RHO_WATER):
    """Power delivered to the water at bollard pull, P0 = T0 · w0. Ideal; a real propulsor needs more."""
    return float(T0) * induced_velocity(T0, A_disk, rho)


def thrust_momentum(U, T0, A_disk, rho=RHO_WATER, P_water=None):
    """Actuator-disk thrust at speed U, holding the power delivered to the water constant.

    Solves 2 ρ A w (U + w)² = P_water for the induced velocity w, then T = 2 ρ A (U + w) w.
    """
    A = max(float(A_disk), 1e-6)
    P = water_power_at_bollard(T0, A, rho) if P_water is None else float(P_water)
    if P <= 0.0:
        return 0.0
    U = max(float(U), 0.0)
    if U < 1e-9:
        w = (P / (2.0 * rho * A)) ** (1.0 / 3.0)
        return float(2.0 * rho * A * w * w)

    def f(w):
        return 2.0 * rho * A * w * (U + w) ** 2 - P

    hi = max((P / (2.0 * rho * A)) ** (1.0 / 3.0), 1e-6)
    while f(hi) < 0.0 and hi < 1e4:
        hi *= 2.0
    w = brentq(f, 1e-12, hi, xtol=1e-10)
    return float(2.0 * rho * A * (U + w) * w)


def thrust(U, T0, model="momentum", A_disk=0.0982, P_water=None, rho=RHO_WATER):
    """Thrust available at speed U through the water, by the chosen model."""
    T0 = float(T0)
    if model == "constant":
        return T0
    if model == "constant_power":
        P = water_power_at_bollard(T0, A_disk, rho) if P_water is None else float(P_water)
        U = max(float(U), 1e-6)
        return float(min(T0, P / U))
    if model == "momentum":
        return thrust_momentum(U, T0, A_disk, rho, P_water)
    raise ValueError(f"unknown thrust model {model!r}")


def implied_efficiency(T0, A_disk, P_electrical, rho=RHO_WATER):
    """Overall electrical-to-water efficiency implied by a stated bollard thrust and electrical power."""
    P0 = water_power_at_bollard(T0, A_disk, rho)
    return dict(P_water_W=P0, P_electrical_W=float(P_electrical),
                efficiency=(P0 / float(P_electrical)) if P_electrical else None,
                induced_velocity_m_s=induced_velocity(T0, A_disk, rho),
                note="Ideal momentum theory: a real propulsor needs MORE water power for the same thrust, so this is "
                     "an upper bound on the efficiency consistent with the two stated numbers. A low value means the "
                     "bollard figure is conservative or the power rating is a peak.")


# ───────────────────────────────────────────────────────────────── resistance, with wind
def hydro_resistance(U_water, exo_rows, boat_geo, res_cfg, g=9.80665, rho=RHO_WATER):
    """Hydrodynamic resistance of the pair at speed through the water. Thin wrapper over propulsion.py so the two
    models cannot drift apart."""
    U = abs(float(U_water))
    if U < 1e-9:
        return dict(total_N=0.0, exo_N=0.0, boat_N=0.0, exo_detail={}, boat_detail={})
    nu = float(res_cfg["nu_m2_s"])
    Re, Rd = exo_resistance_from_geometry(exo_rows, rho, nu, res_cfg["exo"], U)
    Rb, Bd = boat_resistance_from_geometry(boat_geo, rho, g, nu, res_cfg["boat"], U)
    return dict(total_N=Re + Rb, exo_N=Re, boat_N=Rb, exo_detail=Rd, boat_detail=Bd)


def wind_resistance(U_ground, V_true, wind_from_deg, areas, coeffs=None, rho_air=aero.RHO_AIR):
    """Longitudinal wind force on the pair, plus the side force and yaw moment per body."""
    V_app, beta = aero.apparent_wind(U_ground, V_true, wind_from_deg)
    out, Fx = {}, 0.0
    for body in ("EXO", "BOAT"):
        if body not in areas:
            continue
        w = aero.wind_wrench(areas[body], V_app, beta, coeffs, rho_air)
        out[body] = w
        Fx += float(w["F"][0])
    return dict(V_app_m_s=V_app, beta_deg=beta, Fx_total_N=Fx, bodies=out,
                note="Each body's areas are computed independently, so the pair's total is an over-estimate wherever "
                     "one body shelters the other. Steady wind only - no gusts.")


def net_thrust_minus_resistance(U_ground, *, T0, model, A_disk, P_water, exo_rows, boat_geo, res_cfg,
                                V_true=0.0, wind_from_deg=0.0, areas=None, coeffs=None, current_m_s=0.0,
                                g=9.80665, rho=RHO_WATER, rho_air=aero.RHO_AIR):
    """T(U) - R_hydro(U_water) - R_wind(U_ground). Zero at the steady speed."""
    U_water = float(U_ground) - float(current_m_s)       # a following current reduces speed through the water
    T = thrust(max(U_water, 0.0), T0, model, A_disk, P_water, rho)
    R = hydro_resistance(U_water, exo_rows, boat_geo, res_cfg, g, rho)["total_N"]
    R = R * np.sign(U_water) if U_water < 0 else R
    Fw = 0.0
    if areas and V_true:
        Fw = wind_resistance(U_ground, V_true, wind_from_deg, areas, coeffs, rho_air)["Fx_total_N"]
    return float(T - R + Fw)                              # Fw is already signed (-x for a head wind)


def max_speed(*, T0, model, A_disk, P_water, exo_rows, boat_geo, res_cfg, V_true=0.0, wind_from_deg=0.0,
              areas=None, coeffs=None, current_m_s=0.0, g=9.80665, rho=RHO_WATER, rho_air=aero.RHO_AIR,
              hi=12.0):
    """Steady speed over ground at full thrust: the root of T - R. None when thrust cannot overcome the wind at rest."""
    kw = dict(T0=T0, model=model, A_disk=A_disk, P_water=P_water, exo_rows=exo_rows, boat_geo=boat_geo,
              res_cfg=res_cfg, V_true=V_true, wind_from_deg=wind_from_deg, areas=areas, coeffs=coeffs,
              current_m_s=current_m_s, g=g, rho=rho, rho_air=rho_air)
    f0 = net_thrust_minus_resistance(0.0, **kw)
    if f0 <= 0.0:
        return None                                      # cannot even start against this wind
    fh = net_thrust_minus_resistance(hi, **kw)
    if fh > 0.0:
        return float(hi)                                  # faster than the bracket; report the bracket edge
    return float(brentq(lambda U: net_thrust_minus_resistance(U, **kw), 1e-6, hi, xtol=1e-4))


# ───────────────────────────────────────────────────────────────── energy
def electrical_power_for_thrust(T_required, T0, P_electrical_max, A_disk, U_water, rho=RHO_WATER):
    """Electrical power to hold a given thrust, scaled from the full-power point.

    ASSUMPTION, and a crude one: electrical power is taken proportional to the ideal water power at that thrust and
    speed, with the same overall efficiency as at bollard. Real pod efficiency varies with loading; without a pod
    efficiency map this is the most that can be said. The consistency check is that at full thrust this must return
    the installed electrical power, no more.
    """
    T_required = max(float(T_required), 0.0)
    if T_required <= 0.0:
        return 0.0
    eff = water_power_at_bollard(T0, A_disk, rho) / float(P_electrical_max) if P_electrical_max else None
    if not eff or eff <= 0:
        return float("nan")
    w = induced_velocity_at_speed(T_required, A_disk, U_water, rho)
    P_water = T_required * (max(float(U_water), 0.0) + w)
    return float(P_water / eff)


def endurance(U_ground, *, T0, model, A_disk, P_water, P_electrical_max, exo_rows, boat_geo, res_cfg,
              battery_kwh, usable_fraction=0.80, hotel_w=150.0, solar_w=0.0,
              V_true=0.0, wind_from_deg=0.0, areas=None, coeffs=None, current_m_s=0.0,
              g=9.80665, rho=RHO_WATER, rho_air=aero.RHO_AIR):
    """Hours and distance at a held speed, given the battery and any solar input."""
    U_water = float(U_ground) - float(current_m_s)
    R = hydro_resistance(U_water, exo_rows, boat_geo, res_cfg, g, rho)["total_N"]
    Fw = 0.0
    if areas and V_true:
        Fw = wind_resistance(U_ground, V_true, wind_from_deg, areas, coeffs, rho_air)["Fx_total_N"]
    T_req = max(R - Fw, 0.0)                              # a following wind reduces the thrust needed
    T_avail = thrust(max(U_water, 0.0), T0, model, A_disk, P_water, rho)
    P_prop = electrical_power_for_thrust(T_req, T0, P_electrical_max, A_disk, U_water, rho)
    P_net = P_prop + float(hotel_w) - float(solar_w)
    kwh = float(battery_kwh) * float(usable_fraction)
    hours = (kwh * 1000.0 / P_net) if P_net > 1e-9 else float("inf")
    return dict(U_ground_m_s=float(U_ground), U_water_m_s=U_water, thrust_required_N=T_req,
                thrust_available_N=T_avail, achievable=bool(T_avail >= T_req - 1e-6),
                P_propulsion_W=P_prop, P_hotel_W=float(hotel_w), P_solar_W=float(solar_w), P_net_W=P_net,
                usable_kwh=kwh, hours=hours,
                range_km=(float("inf") if not np.isfinite(hours) else hours * float(U_ground) * 3.6))


def solar_neutral_speed(*, T0, model, A_disk, P_water, P_electrical_max, exo_rows, boat_geo, res_cfg,
                        solar_w, hotel_w=150.0, current_m_s=0.0, g=9.80665, rho=RHO_WATER, hi=6.0):
    """The speed whose propulsion draw exactly consumes the available solar power after the hotel load.

    For a solar boat this is the speed that can be held indefinitely in that light, which matters more than the
    maximum. Returns None when the hotel load alone already exceeds the solar input.
    """
    budget = float(solar_w) - float(hotel_w)
    if budget <= 0.0:
        return None

    def f(U):
        U_water = U - float(current_m_s)
        R = hydro_resistance(U_water, exo_rows, boat_geo, res_cfg, g, rho)["total_N"]
        return electrical_power_for_thrust(R, T0, P_electrical_max, A_disk, U_water, rho) - budget

    if f(1e-3) > 0.0:
        return 0.0
    if f(hi) < 0.0:
        return float(hi)
    return float(brentq(f, 1e-3, hi, xtol=1e-4))
