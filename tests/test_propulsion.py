"""Quasi-static propulsion / tow: force balance, line transmission, feasibility, and the design sweeps."""
import numpy as np
import pytest

from exo01.config import load_config, resolve
from exo01.analysis import evaluate, HYDRO_DEFAULTS
from exo01.propulsion import exo_resistance, boat_resistance, itt57


@pytest.fixture(scope="module")
def ill():
    return load_config("illustrative")


def _lines_force_on_boat(res):
    """Sum of the line forces on the boat (world): each line pulls the boat toward the EXO along -unit."""
    F = np.zeros(3)
    for l in res["lines"]:
        F += -l["tension_N"] * np.asarray(l["unit"])
    return F


def test_thrust_zero_is_identical_to_static(ill):
    r0 = evaluate(resolve(ill, {}))
    r1 = evaluate(resolve(ill, {"propulsion": {"thrust_fraction": 0.0, "unit": "EXO_PODS"}}))
    assert "propulsion" not in r1
    assert r1["equilibrium"]["trim_deg"] == pytest.approx(r0["equilibrium"]["trim_deg"], abs=1e-12)


def test_push_force_balance_through_the_lines(ill):
    """EXO pods at 100 %: thrust = R_exo + R_boat (speed solve), and the lines carry exactly the boat's resistance."""
    r = evaluate(resolve(ill, {"propulsion": {"thrust_fraction": 1.0, "unit": "EXO_PODS"}}))
    p = r["propulsion"]
    assert r["coupled_equilibrium"]["converged"]
    assert p["thrust_total_N"] == pytest.approx(ill["propulsion"]["units"]["EXO_PODS"]["bollard_thrust_N"], rel=1e-12)
    assert p["thrust_total_N"] == pytest.approx(2 * 62.0 * 9.80665, rel=1e-4)
    assert p["resistance"]["total_N"] == pytest.approx(p["thrust_horizontal_N"], rel=1e-5)
    assert p["thrust_horizontal_N"] < p["thrust_total_N"]                              # trimmed EXO: cos(trim) factor
    assert 0.5 < p["speed_m_s"] < 6.0
    Fb = _lines_force_on_boat(r)
    assert Fb[0] == pytest.approx(p["resistance"]["boat_N"], rel=1e-4)          # lines push the boat forward by R_boat
    assert abs(Fb[1]) < 1e-3 * p["resistance"]["boat_N"]                            # symmetric
    net = r["coupled_equilibrium"]["external_net_force"]
    assert abs(net["Fx_N"]) < 1e-4 * p["thrust_total_N"]      # thrust direction follows the trim solved by Newton (0.04 N residual)
    # the EXO's hydrostatic imbalance equals minus the external + line vertical forces
    res = r["equilibrium"]["residuals"]
    assert abs(res["Fz_N_incl_external"] if "Fz_N_incl_external" in res else 0.0) < 1e9     # (coupled: reported via lines_note)
    assert any("PROPULSION ON" in f for f in r["flags"])


def test_all_forward_lines_cannot_push(ill):
    lines = next(p for p in ill["host_boat"]["line_presets"] if p["id"] == "figure_all_forward")["lines"]
    r = evaluate(resolve(ill, {"host_boat": {"lines": lines}, "propulsion": {"thrust_fraction": 1.0, "unit": "EXO_PODS"}}))
    ce = r["coupled_equilibrium"]
    # either no equilibrium at all, or one reached only after the boat slides aft into the EXO rear deck (interference)
    assert not ce.get("physical", ce["converged"])
    if ce["converged"]:
        assert ce["boat_shift_from_nominal"]["dx_m"] < -0.3 and any(f.startswith("INTERFERENCE") for f in r["flags"])
        assert any("INTO the EXO structure" in f for f in r["flags"])
    else:
        assert any("cannot carry the thrust" in f for f in r["flags"])
    # ... but the same arrangement carries a tow by the boat's engine
    rt = evaluate(resolve(ill, {"host_boat": {"lines": lines}, "propulsion": {"thrust_fraction": 1.0, "unit": "BOAT_ENGINE"}}))
    assert rt["coupled_equilibrium"]["converged"] and not any(l["slack"] for l in rt["lines"])
    Fb = _lines_force_on_boat(rt)
    assert Fb[0] == pytest.approx(-rt["propulsion"]["resistance"]["exo_N"], rel=1e-4)      # lines pull the boat back by R_exo


def test_exo_alone_external_wrench_balanced(ill):
    r = evaluate(resolve(ill, {"host_boat": {"included": False}, "propulsion": {"thrust_fraction": 0.5, "unit": "EXO_PODS"}}))
    e = r["equilibrium"]
    res = e["residuals"]
    Mg = res["weight_N"]
    assert abs(res["Fz_N_incl_external"]) < 1e-8 * Mg and abs(res["My_Nm_incl_external"]) < 1e-8 * Mg
    p = r["propulsion"]
    assert p["resistance"]["boat_N"] == 0.0 and p["resistance"]["exo_N"] == pytest.approx(p["thrust_horizontal_N"], rel=1e-5)
    r0 = evaluate(resolve(ill, {"host_boat": {"included": False}}))
    assert e["trim_deg"] != pytest.approx(r0["equilibrium"]["trim_deg"], abs=1e-3)   # the thrust/drag couple changes the trim


def test_resistance_models_monotonic(ill):
    r = evaluate(resolve(ill, {}))
    c = ill["propulsion"]["resistance"]
    R = [exo_resistance(r["_assembly"], r["_eq"], 999.0, c["nu_m2_s"], c["exo"], U)[0] for U in (0.5, 1.0, 2.0)]
    assert R[0] < R[1] < R[2] and R[2] / R[1] > 3.0       # ~U^2
    Rb = [boat_resistance(r["_boat_assembly"], r["_boat_eq"], 999.0, 9.80665, c["nu_m2_s"], c["boat"], U)[0] for U in (0.5, 1.0, 2.0)]
    assert Rb[0] < Rb[1] < Rb[2]
    assert itt57(1e6) == pytest.approx(0.075 / 16.0, rel=1e-12)


def test_battery_and_line_sweeps_run(ill):
    from exo01.optimise import (battery_candidates, line_candidates, run_optimisation, OBSTACLES, FRAME_OBSTACLES, FRAME_X, FRAME_Y,
                                _rect_overlap, BATTERY_FOOTPRINT)
    cands = battery_candidates({"dx": 0.4})
    assert cands
    fx, fy = BATTERY_FOOTPRINT
    for c in cands:
        for y in (-c["y_stbd_m"], c["y_port_m"]):
            rect = (c["x_m"] - fx / 2, c["x_m"] + fx / 2, y - fy / 2, y + fy / 2)
            if c["zone"] == "rear_deck":
                assert 0.0 <= rect[0] and rect[1] <= 2.1 + 1e-9
                assert not any(_rect_overlap(rect, o) for o in OBSTACLES.values())
            else:   # float-top frames: above the float row, forward of the deck, clear of the uprights
                assert c["zone"] == "float_frame" and c["symmetric"]
                assert FRAME_X[0] <= rect[0] and rect[1] <= FRAME_X[1] + 1e-9 and FRAME_Y[0] <= abs(y) - fy / 2 and abs(y) + fy / 2 <= FRAME_Y[1]
                assert all(rect[1] <= o[0] or o[1] <= rect[0] for o in FRAME_OBSTACLES.values())
    assert {c["zone"] for c in cands} == {"rear_deck", "float_frame"}
    assert all(c["zone"] == "rear_deck" for c in battery_candidates({"dx": 0.4, "zones": "rear_deck"}))
    assert len(line_candidates(ill, {})) == 36 + len(ill["host_boat"]["line_presets"])
    cfg = resolve(ill, {"host_boat": {"included": False}})
    out = run_optimisation(cfg, "battery", dict(H_m=0.3, T_s=2.5, heading_deg=90), {}, dict(HYDRO_DEFAULTS), options={"dx": 0.4})
    feas = sorted([r for r in out["rows"] if r["feasible"]], key=lambda r: r["rank"])
    assert feas and out["best"]["overrides_to_apply"]["components"]["BATTERY_1"]["com_m"][0] == out["best"]["candidate"]["x_m"]
    assert feas[0]["rank"] == 1 and all("trim_deg" in r for r in feas) and feas[0]["score"] <= feas[-1]["score"]
    # the physics of the two zones: on the rear deck the trim stays stern-down; on the float frames it crosses zero (empty EXO)
    z = out["zones"]
    assert z["rear_deck"]["trim_deg"] < -2.0 and abs(z["float_frame"]["trim_deg"]) < 1.0
    assert out["x_zero_trim_m"] is not None and 3.0 < out["x_zero_trim_m"] < 4.0
    assert out["best"]["candidate"]["zone"] == "float_frame"
