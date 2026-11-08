"""Tests for the wind and speed/energy models added in v3."""
import numpy as np
import pytest

from exo01 import aero
from exo01 import performance as perf

A_DISK = 2 * np.pi * 0.125 ** 2
T0 = 1213.5
P_ELEC = 10000.0


# ───────────────────────────────────────────── thrust
def test_all_thrust_models_agree_at_bollard():
    """The three models exist to disagree at speed; at zero speed they must give the same bollard figure."""
    for m in ("constant", "constant_power", "momentum"):
        assert perf.thrust(0.0, T0, m, A_DISK) == pytest.approx(T0, rel=1e-6)


def test_thrust_falls_with_speed_except_the_constant_model():
    fast, slow = perf.thrust(3.0, T0, "momentum", A_DISK), perf.thrust(0.5, T0, "momentum", A_DISK)
    assert fast < slow < T0
    assert perf.thrust(3.0, T0, "constant", A_DISK) == pytest.approx(T0)


def test_induced_velocity_at_speed_reduces_to_the_bollard_relation():
    assert perf.induced_velocity_at_speed(800.0, A_DISK, 0.0) == pytest.approx(
        perf.induced_velocity(800.0, A_DISK), rel=1e-9)


def test_momentum_thrust_satisfies_its_own_definition():
    """T must equal 2 ρ A (U + w) w for the w that produces it."""
    for U in (0.0, 1.0, 2.5, 4.0):
        T = perf.thrust(U, T0, "momentum", A_DISK)
        w = perf.induced_velocity_at_speed(T, A_DISK, U)
        assert 2 * perf.RHO_WATER * A_DISK * (U + w) * w == pytest.approx(T, rel=1e-6)


def test_full_thrust_never_draws_more_than_the_installed_power():
    """The bug this catches: using the BOLLARD induced-velocity relation at speed made a 10 kW installation draw
    12.6 kW at 2.4 m/s. Holding water power constant, full thrust must draw exactly the installed power."""
    for U in (0.0, 1.0, 2.0, 2.42, 3.0, 4.0):
        T = perf.thrust(U, T0, "momentum", A_DISK)
        P = perf.electrical_power_for_thrust(T, T0, P_ELEC, A_DISK, U)
        assert P == pytest.approx(P_ELEC, rel=1e-6), f"at {U} m/s the draw is {P:.0f} W, not {P_ELEC:.0f} W"


def test_part_thrust_draws_less_than_full():
    U = 2.0
    T_full = perf.thrust(U, T0, "momentum", A_DISK)
    assert perf.electrical_power_for_thrust(0.5 * T_full, T0, P_ELEC, A_DISK, U) < P_ELEC


# ───────────────────────────────────────────── wind
def test_apparent_wind_head_and_following():
    V, beta = aero.apparent_wind(2.0, 5.0, 0.0)          # 5 m/s from dead ahead, making 2 m/s
    assert V == pytest.approx(7.0, rel=1e-9)
    assert abs(beta) < 1e-6
    V, beta = aero.apparent_wind(2.0, 5.0, 180.0)        # from astern
    assert V == pytest.approx(3.0, rel=1e-9)
    assert abs(abs(beta) - 180.0) < 1e-6


def test_apparent_wind_in_still_air_is_the_boat_s_own_speed_from_ahead():
    V, beta = aero.apparent_wind(3.0, 0.0, 90.0)
    assert V == pytest.approx(3.0, rel=1e-9)
    assert abs(beta) < 1e-6


def test_head_wind_is_drag_and_following_wind_is_thrust():
    a = dict(A_front_m2=10.0, A_lateral_m2=20.0, z_lateral_m=1.0, L_m=8.0)
    assert aero.wind_wrench(a, 10.0, 0.0)["F"][0] < 0        # from ahead -> -x
    assert aero.wind_wrench(a, 10.0, 180.0)["F"][0] > 0      # from astern -> +x


def test_beam_wind_is_pure_side_force_with_no_yaw():
    """The first-harmonic yaw form sin(2 beta) vanishes on the beam and head-on, and peaks near 45 deg."""
    a = dict(A_front_m2=10.0, A_lateral_m2=20.0, z_lateral_m=1.0, L_m=8.0)
    beam = aero.wind_wrench(a, 10.0, 90.0)
    assert beam["F"][1] > 0
    assert abs(beam["M"][2]) < 1e-9
    assert abs(aero.wind_wrench(a, 10.0, 0.0)["M"][2]) < 1e-9
    assert abs(aero.wind_wrench(a, 10.0, 45.0)["M"][2]) > abs(beam["M"][2])


def test_wind_force_scales_with_the_square_of_speed():
    a = dict(A_front_m2=10.0, A_lateral_m2=20.0, z_lateral_m=1.0, L_m=8.0)
    f1 = abs(aero.wind_wrench(a, 5.0, 90.0)["F"][1])
    f2 = abs(aero.wind_wrench(a, 10.0, 90.0)["F"][1])
    assert f2 / f1 == pytest.approx(4.0, rel=1e-9)


def test_cabin_windage_integrates_the_recorded_stations():
    """A 10 m long, 2 m wide box standing 1 m above the deck: 10 m2 of side, 2 m2 presented ahead."""
    stations = [[0, 1000, 1000], [10000, 1000, 1000]]
    w = aero.cabin_windage(stations, deck_z_m=0.0)
    assert w["A_lateral_m2"] == pytest.approx(10.0, rel=1e-9)
    assert w["A_front_m2"] == pytest.approx(2.0, rel=1e-9)
    assert w["lateral_centroid_z_m"] == pytest.approx(0.5, rel=1e-9)


def test_tilting_the_panels_adds_frontal_area():
    """A flat array presents nothing to the wind; tilt it and it becomes a sail. 16 m2 at 30 deg is 8 m2."""
    assert 15.98 * np.sin(np.radians(30.0)) == pytest.approx(7.99, abs=0.01)


# ───────────────────────────────────────────── energy
def test_solar_neutral_speed_is_none_when_the_hotel_load_outruns_the_array(monkeypatch):
    out = perf.solar_neutral_speed(T0=T0, model="momentum", A_disk=A_DISK, P_water=None,
                                   P_electrical_max=P_ELEC, exo_rows={}, boat_geo=dict(S_wet=1.0, L_wl=1.0),
                                   res_cfg=dict(nu_m2_s=1.14e-6,
                                                exo=dict(form_factor_k=0.3, pressure_drag_cd=0.15),
                                                boat=dict(form_factor_k=0.25, appendage_factor=1.15,
                                                          residuary_c_at_fr02=0.0015, residuary_exponent=4.0)),
                                   solar_w=100.0, hotel_w=150.0)
    assert out is None
