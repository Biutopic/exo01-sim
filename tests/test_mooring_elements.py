"""Mooring elements (v1.2): compression-only fenders, bilateral struts, and the force loops they close."""
import copy

import numpy as np
import pytest

from exo01.analysis import evaluate
from exo01.config import load_config, resolve


@pytest.fixture(scope="module")
def ill():
    return load_config("illustrative")


def _preset(ill, pid):
    return copy.deepcopy(next(p for p in ill["host_boat"]["line_presets"] if p["id"] == pid)["lines"])


def _ev(ill, lines, thr=0.0, unit="EXO_PODS"):
    return evaluate(resolve(ill, {"host_boat": {"lines": lines}, "propulsion": {"thrust_fraction": thr, "unit": unit}}))


def test_fenders_carry_the_push_and_release_in_tow(ill):
    lines = _preset(ill, "fenders_crossed_lines")
    r = _ev(ill, lines, 1.0, "EXO_PODS")
    ce = r["coupled_equilibrium"]
    assert ce["converged"] and ce["physical"]
    fenders = [l for l in r["lines"] if l["kind"] == "fender"]
    assert len(fenders) == 2 and all(l["tension_N"] < -300 for l in fenders)                 # both in compression
    # the fenders + line longitudinal components balance the boat's resistance
    Fx = sum(-l["tension_N"] * l["unit"][0] for l in r["lines"])
    assert Fx == pytest.approx(r["propulsion"]["resistance"]["boat_N"], rel=1e-3)
    assert abs(ce["boat_shift_from_nominal"]["dx_m"]) < 0.02 and abs(ce["boat_shift_from_nominal"]["dy_m"]) < 0.01
    rt = _ev(ill, lines, 1.0, "BOAT_ENGINE")
    assert rt["coupled_equilibrium"]["physical"]
    assert all(l["slack"] and l["tension_N"] == 0.0 for l in rt["lines"] if l["kind"] == "fender")   # free when towed away
    assert all(l["tension_N"] >= 0.0 for l in rt["lines"] if l["kind"] == "line")


def test_fender_never_pulls_and_line_never_pushes(ill):
    for pid in ("fenders_tow_lines", "fenders_diagonals", "simulator_default"):
        for thr, unit in ((0.0, "EXO_PODS"), (1.0, "EXO_PODS"), (1.0, "BOAT_ENGINE")):
            r = _ev(ill, _preset(ill, pid), thr, unit)
            for l in r["lines"]:
                if l["kind"] == "fender":
                    assert l["tension_N"] <= 1e-9
                elif l["kind"] == "line":
                    assert l["tension_N"] >= -1e-9


def test_rigid_struts_are_bilateral_and_carry_both_signs(ill):
    lines = _preset(ill, "rigid_struts")
    r = _ev(ill, lines, 1.0, "EXO_PODS")
    T = {l["id"]: l["tension_N"] for l in r["lines"]}
    assert r["coupled_equilibrium"]["physical"]
    assert T["STRUT_FWD_PORT"] < -300 and T["STRUT_AFT_PORT"] > 50            # forward struts in compression, aft in tension
    assert abs(r["coupled_equilibrium"]["boat_shift_from_nominal"]["dx_m"]) < 0.01    # ~rigid: millimetres
    assert not any(l["slack"] for l in r["lines"])


def test_soft_lines_alone_cannot_push_without_interference(ill):
    lines = _preset(ill, "simulator_default")
    for l in lines:
        l["stiffness_N_per_m"] = 2000.0
    r = _ev(ill, lines, 1.0, "EXO_PODS")
    ce = r["coupled_equilibrium"]
    assert not ce.get("physical", True)                        # the boat slides into the rear deck plate
    assert ce["boat_shift_from_nominal"]["dx_m"] < -0.1


def test_snatch_check_handles_fenders(ill):
    from exo01.analysis import hydro_for, build_response, HYDRO_DEFAULTS
    from exo01.response import line_snatch_check
    lines = _preset(ill, "fenders_crossed_lines")
    cfg = resolve(ill, {"host_boat": {"lines": lines}, "propulsion": {"thrust_fraction": 0.0}})
    r = evaluate(cfg)
    s = dict(HYDRO_DEFAULTS)
    om = np.round(np.arange(s["omega_min"], s["omega_max"] + 1e-9, s["omega_step"]), 10)
    hd = np.array([np.radians(90.0)])
    try:
        hdd = hydro_for(r, cfg, om, hd, s, cache_only=True, allow_pose_reuse=True)
    except Exception:  # noqa: BLE001  (no cache in a fresh checkout)
        pytest.skip("no cached BEM for the moored pose")
    model = build_response(r, hdd, cfg)
    D = {"EXO": {"zeta": {"heave": 0.05, "roll": 0.05, "pitch": 0.05}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}},
         "BOAT": {"zeta": {"heave": 0.05, "roll": 0.10, "pitch": 0.10}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}}}
    rw = model.regular_wave(0.3, 2.5, hd[0], D, cfg["deck_acceleration_points"])
    assert any(l["kind"] == "fender" for l in rw["lines"])
    sn = line_snatch_check(model, 2 * np.pi / 2.5, hd[0], 0.3, D, n_periods=6, steps_per_period=48)
    for l in sn["lines"]:
        if l["kind"] == "fender":
            assert l["max_N"] <= 1e-6 and l["peak_N"] <= 0.0           # compression only, whole cycle
        elif l["kind"] == "line":
            assert l["min_N"] >= -1e-6                                 # never pushes
    assert np.isfinite(sn["max_amplitude_ratio"])
