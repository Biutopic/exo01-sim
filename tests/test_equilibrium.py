import numpy as np
import pytest

from exo01.analysis import evaluate
from exo01.buoyancy import BuoyantAssembly, CapsuleX
from exo01 import equilibrium as eqm
from exo01.config import resolve

G = 9.80665


def test_residuals_within_tolerance(ill_result):
    e = ill_result["equilibrium"]
    Mg = e["residuals"]["weight_N"]
    assert abs(e["residuals"]["Fz_N"]) < 1e-9 * Mg
    assert abs(e["residuals"]["Mx_Nm"]) < 1e-9 * Mg
    assert abs(e["residuals"]["My_Nm"]) < 1e-9 * Mg
    assert e["displaced_mass_kg"] == pytest.approx(856.0, rel=1e-10)      # 840 kg register + 2 x 8 kg pods (assumed)


def test_simple_test_body_draft_matches_analytic():
    """Single horizontal capsule with COM at its centre: draft from V = M/rho (hand formula)."""
    cap = CapsuleX("c", (0, 0, 0), 1.6, 0.29, n_circ=96, n_axial=12, n_cap=24)
    asm = BuoyantAssembly([cap])
    rho, M = 1025.0, 150.0
    eq = eqm.equilibrium(asm, M, np.zeros(3), rho)
    from test_buoyancy import v_analytic
    from scipy.optimize import brentq
    d = brentq(lambda d: v_analytic(d) - M / rho, -0.29, 0.29)            # waterline height above axis
    assert eq["zG"] == pytest.approx(-d, abs=1e-3)          # axis (= COM) sits at height -d above the still water
    assert abs(eq["phi"]) < 1e-9 and abs(eq["theta"]) < 1e-9


def test_symmetric_case_has_no_heel(sym_result):
    e = sym_result["equilibrium"]
    assert abs(e["heel_rad"]) < 1e-10
    v = e["per_float_volume_m3"]
    for k in (1, 2, 3):
        assert v[f"FLOAT_NEG_Y_{k}"] == pytest.approx(v[f"FLOAT_POS_Y_{k}"], rel=1e-9)
    assert sym_result["mass"]["com_m"][1] == pytest.approx(0.0, abs=1e-12)
    assert abs(e["centre_of_buoyancy_world_m"][1]) < 1e-10


def test_trim_direction_follows_cog_aft_of_cob(ill_result):
    e = ill_result["equilibrium"]
    pf = e["per_float_volume_m3"]
    # COM is slightly aft (-X) of the float centroid -> rear floats more immersed, trim < 0 (-X end down)
    assert e["trim_rad"] < 0
    assert pf["FLOAT_NEG_Y_1"] > pf["FLOAT_NEG_Y_3"]


def test_added_mass_changes_displacement_exactly(illustrative, ill_result):
    cfg = resolve(illustrative, {"components": {"BATTERY_1": {"mass_kg": 200.0}}, "host_boat": {"included": False}})
    r = evaluate(cfg)
    assert r["equilibrium"]["displaced_mass_kg"] == pytest.approx(936.0, rel=1e-10)


def test_asymmetric_people_heel_toward_loaded_side():
    from exo01.config import load_config, load_scenario, resolve_scenario
    cfg = resolve_scenario(load_scenario("occupants_asymmetric"))
    r = evaluate(cfg)
    assert r["status"]["equilibrium"] == "solved"
    # people on +Y: +Y side goes down. Heel is right-handed about +X (+Y up), so heel must be negative
    assert r["equilibrium"]["heel_rad"] < -1e-4
    base = evaluate(load_config("illustrative"))
    assert r["equilibrium"]["heel_rad"] < base["equilibrium"]["heel_rad"]


def test_no_equilibrium_is_reported_not_forced(illustrative):
    cfg = resolve(illustrative, {"components": {"BATTERY_1": {"mass_kg": 2200.0}}})
    r = evaluate(cfg)
    assert r["status"]["equilibrium"] == "no_feasible_equilibrium"
    assert "No equilibrium" in r["equilibrium"]["reason"]
    assert r["buoyant_volume_total_m3"] == pytest.approx(6 * np.pi * 0.3 ** 2 * 1.45, rel=2e-4)   # buoyancy was NOT increased


def test_baseline_not_computed(baseline):
    r = evaluate(baseline)
    assert r["mass"]["total_listed_mass_kg"] == 840.0
    assert r["mass"]["com_m"] is None and r["status"]["equilibrium"] == "not_computed"
    assert "equilibrium" not in r or r.get("equilibrium") is None


def test_stiffness_matches_waterplane_formulas(ill_result):
    eq, I = ill_result["_eq"], ill_result["_eq"]["integrals"]
    C = np.array(ill_result["stability_static"]["C_hydrostatic_NmPerUnit"])
    rg = eq["rho"] * eq["g"]
    zrel = I["B"][2] - eq["zG"]
    assert C[0, 0] == pytest.approx(rg * I["Awp"], rel=1e-7)
    assert C[1, 1] == pytest.approx(rg * (I["Ixx"] + I["V"] * zrel), rel=1e-6)
    assert C[2, 2] == pytest.approx(rg * (I["Iyy"] + I["V"] * zrel), rel=1e-6)
    assert C[0, 2] == pytest.approx(-rg * I["Sx"], rel=1e-6)
    assert np.allclose(C, C.T, rtol=1e-6, atol=1e-3 * np.abs(C).max() * 1e-3)
    assert ill_result["stability_static"]["statically_stable_here"]


def test_equilibrium_converges_with_tessellation(illustrative):
    out = []
    for res in (dict(n_circ=24, n_axial=4, n_cap=6), dict(n_circ=48, n_axial=8, n_cap=12), dict(n_circ=96, n_axial=16, n_cap=24)):
        e = evaluate(illustrative, resolution=res)["equilibrium"]
        out.append((e["trim_deg"], e["freeboard"]["draft_max_m"], e["freeboard"]["lower_deck_freeboard_min_m"]))
    out = np.array(out)
    assert np.all(np.abs(out[2] - out[1]) <= np.abs(out[1] - out[0]) + 1e-9)
    assert abs(out[2, 1] - out[1, 1]) < 5e-4


def test_analytic_restoring_matrix_equals_finite_differences(ill_result):
    """restoring_matrix (waterplane integrals) vs central differences of the exact wrench, at the solved attitude
    and at a deliberately heeled/trimmed, non-equilibrium attitude."""
    eq, asm = ill_result["_eq"], ill_result["_assembly"]
    C_fd = eqm.hydrostatic_stiffness(asm, eq)
    C_an = eqm.restoring_matrix(eq["integrals"], eq["rho"], eq["g"], eq["zG"])
    assert np.allclose(C_an, C_fd, rtol=1e-5, atol=1e-6 * np.abs(C_fd).max())
    from exo01.buoyancy import attitude
    eq2 = dict(eq, R=attitude(0.12, -0.08), zG=eq["zG"] + 0.05)
    eq2["integrals"] = asm.integrals(eq2["R"], eq["G_body"], eq2["zG"])
    C_fd2 = eqm.hydrostatic_stiffness(asm, eq2)
    C_an2 = eqm.restoring_matrix(eq2["integrals"], eq["rho"], eq["g"], eq2["zG"])
    assert np.allclose(C_an2, C_fd2, rtol=1e-5, atol=1e-6 * np.abs(C_fd2).max())


def test_warm_start_reduces_evaluations(illustrative):
    exo = resolve(illustrative, {"host_boat": {"included": False}})
    r1 = evaluate(exo, warm_key="t")
    n_cold = r1["equilibrium"]["solver"]["n_evaluations"]
    cfg = resolve(exo, {"components": {"BATTERY_1": {"com_m": [0.9, -1.05, 0.25]}}})
    r2 = evaluate(cfg, warm_key="t")
    assert r2["equilibrium"]["solver"]["newton_converged"]
    assert r2["equilibrium"]["solver"]["n_evaluations"] < n_cold
    assert r2["equilibrium"]["solver"]["residual_relative"] < 1e-11
