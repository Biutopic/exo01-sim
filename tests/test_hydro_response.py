"""Hydrodynamics / response checks. Use a coarse mesh and a small grid (fast); convergence is in scripts/run_verification.py."""
import numpy as np
import pytest

from exo01.analysis import build_response
from exo01.buoyancy import wet_integrals
from exo01.hydro import compute_hydro, build_world_mesh, world_triangles
from exo01.response import time_domain_check, wavenumber

OMEGAS = np.array([0.6, 1.0, 1.6, 2.4, 3.2, 4.4, 6.0])
HEADINGS = np.arange(0, 360, 30) * np.pi / 180
H_COARSE = 0.2
RHO, G = 1025.0, 9.80665


@pytest.fixture(scope="module")
def sym_hydro(sym_result):
    return compute_hydro(sym_result["_assembly"].surfaces, sym_result["_eq"], OMEGAS, HEADINGS, RHO, G, None, H_COARSE)


@pytest.fixture(scope="module")
def sym_model(sym_result, symmetric_cfg, sym_hydro):
    return build_response(sym_result, sym_hydro, symmetric_cfg)


def test_dispersion_relation():
    w = 2.0
    k = wavenumber(w, None)
    assert k == pytest.approx(w ** 2 / G)
    kd = wavenumber(w, 3.0)
    assert G * kd * np.tanh(kd * 3.0) == pytest.approx(w ** 2, rel=1e-12)


def test_long_wave_heave_excitation_limit_and_phase_convention(sym_result, sym_hydro):
    """kL -> 0 (small body in a long wave): F3 -> (C33 - w^2 A33) eta, with C33 = rho g A_wp of the SAME BEM mesh,
    and the phase lag equals k * x_centroid(waterplane) for waves travelling toward +X (heading 0).
    Also confirms the sign convention exp(-i w t) / eta = exp(i k x)."""
    eq = sym_result["_eq"]
    mesh = build_world_mesh(sym_result["_assembly"].surfaces, eq, H_COARSE)
    C33 = RHO * G * float(mesh.waterplane_area)
    w = OMEGAS[0]                                          # 0.6 rad/s: wavelength 171 m >> 5 m body
    F3 = sym_hydro.F[0, 0, 2]
    A33 = sym_hydro.A[0, 2, 2]
    assert abs(F3) == pytest.approx(C33 - w * w * A33, rel=0.012)
    xf = float(mesh.waterplane_center[0])
    assert np.angle(F3) == pytest.approx(w * w / G * xf, rel=0.2)      # lag = k x_f (k = w^2/g)


def test_my_hydrostatics_match_capytaine_on_identical_mesh(sym_result):
    import capytaine as cpt
    eq = sym_result["_eq"]
    mesh = build_world_mesh(sym_result["_assembly"].surfaces, eq, H_COARSE)
    com = np.array([0.0, 0.0, eq["zG"]])
    body = cpt.FloatingBody(mesh=mesh, dofs=cpt.rigid_body_dofs(rotation_center=com), center_of_mass=com, mass=eq["mass"])
    K = np.asarray(body.compute_hydrostatic_stiffness(rho=RHO, g=G).values)
    I = wet_integrals(world_triangles(sym_result["_assembly"].surfaces, eq, H_COARSE))
    assert I["V"] == pytest.approx(float(mesh.disp_volume), rel=1e-9)
    assert K[2, 2] == pytest.approx(RHO * G * I["Awp"], rel=1e-6)
    zrel = I["B"][2] - eq["zG"]
    assert K[3, 3] == pytest.approx(RHO * G * (I["Ixx"] + I["V"] * zrel), rel=5e-3)   # Capytaine gravity term uses mass vs rho*V of the mesh
    assert K[4, 4] == pytest.approx(RHO * G * (I["Iyy"] + I["V"] * zrel), rel=5e-3)


def test_symmetric_loading_gives_symmetric_response(sym_model):
    for beta in (0.0, np.pi):
        X = sym_model.rao(2.0, beta)
        scale = max(abs(X[0]), abs(X[2]), abs(X[4]))
        assert max(abs(X[1]), abs(X[3]), abs(X[5])) < 1e-4 * scale     # residual ~2e-5: lid/clip triangulation is not mirror-exact


def test_reference_point_transform_matches_direct_bem(sym_result):
    """The BEM is computed about the CAD origin and moved to the COM exactly: compare with a direct solve about the COM,
    for the actual COM and for a COM moved by (0.4, -0.15, 0.2) m at the same pose (cache hit + transform)."""
    from exo01.hydro import _body, _solve_radiation, _solve_diffraction, compute_hydro
    eq = sym_result["_eq"]
    surf = sym_result["_assembly"].surfaces
    om, hd = np.array([1.0, 1.6]), np.radians([30.0])
    for dG in (np.zeros(3), np.array([0.4, -0.15, 0.2])):
        eq2 = dict(eq, G_body=eq["G_body"] + dG, zG=eq["zG"] + float((eq["R"] @ dG)[2]))
        body, _, _ = _body(surf, eq2, om, G, H_COARSE, True)
        A0, B0 = _solve_radiation(body, om, RHO, G, None)
        F0 = _solve_diffraction(body, om, hd, RHO, G, None)
        h = compute_hydro(surf, eq2, om, hd, RHO, G, None, H_COARSE)
        assert np.abs(h.A - A0).max() < 1e-9 * np.abs(A0).max()
        assert np.abs(h.B - B0).max() < 1e-9 * np.abs(B0).max()
        assert np.abs(h.F - F0).max() < 1e-9 * np.abs(F0).max()


def test_mesh_mirror_symmetry(sym_result):
    """The BEM mesh of a symmetric loading is exactly mirror-symmetric about the x-z plane (vertex sets match)."""
    mesh = build_world_mesh(sym_result["_assembly"].surfaces, sym_result["_eq"], H_COARSE)
    key = {tuple(v) for v in np.round(mesh.vertices, 7)}
    assert all(tuple(v) in key for v in np.round(mesh.vertices, 7) * np.array([1, -1, 1]))


def test_heading_antisymmetry(sym_model):
    """Mirror-image headings give mirror-image responses. The mesh is exactly symmetric (previous test); the residual
    is the solver's own asymmetry (Green-function evaluation), 6e-4 at h = 0.2 m on the Flofiz mesh."""
    for b in (np.pi / 6, np.pi / 3, np.pi / 2):
        Xp, Xm = sym_model.rao(2.0, b), sym_model.rao(2.0, -b)
        assert abs(Xp[2] - Xm[2]) < 1e-3 * abs(Xp[2])           # heave even
        assert abs(Xp[1] + Xm[1]) < 1e-3 * abs(Xp[1])           # sway odd
        assert abs(Xp[3] + Xm[3]) < 1e-3 * abs(Xp[3])           # roll odd


def test_quasi_static_limits(sym_model):
    """Long waves: a free-floating body follows the surface (heave RAO -> 1) and the wave slope in roll."""
    X = sym_model.rao(0.6, np.pi / 2)
    k = 0.6 ** 2 / G
    assert abs(X[2]) == pytest.approx(1.0, abs=0.03)
    assert abs(X[3]) == pytest.approx(k, rel=0.05)                       # roll follows the wave slope


def test_time_domain_convergence_matches_frequency_domain(sym_model):
    damp = {"zeta": {"heave": 0.3, "roll": 0.3, "pitch": 0.3}, "absolute": {"surge": 2000, "sway": 2000, "yaw": 4000}}
    res = time_domain_check(sym_model, 2 * np.pi / 4.0, np.pi / 3, 0.3, damp, steps_per_period=(16, 32, 64))
    e = [r["max_rel_amp_error"] for r in res["results"]]
    assert e[0] > e[1] > e[2]
    assert e[2] < 1e-4


def test_flags_outside_linear_range(sym_model):
    rw = sym_model.regular_wave(1.2, 2.0, np.pi / 2)            # steep: H/L = 1.2/6.2 ~ 0.19
    assert any(l == "error" for l, _ in rw["flags"])
    rw = sym_model.regular_wave(0.1, 60.0, 0.0)                 # outside computed band
    assert rw["in_range"] is False


def test_line_snatch_check_reduces_to_linear_for_tiny_waves(ill_boat_result, illustrative):
    """With a 1 mm wave no line goes slack, so the tension-only time-domain model must reproduce the linear amplitudes
    (checks the integrator, the line kinematics and the static-force subtraction); a 0.3 m beam wave makes the
    'slightly tense' default lines snatch (peak well above the linear amplitude) - reported, not hidden."""
    from exo01.analysis import hydro_for, build_response, HYDRO_DEFAULTS
    from exo01.response import line_snatch_check
    from exo01.config import resolve
    cfg = resolve(illustrative, {})
    r = ill_boat_result
    om = np.round(np.arange(HYDRO_DEFAULTS["omega_min"], HYDRO_DEFAULTS["omega_max"] + 1e-9, HYDRO_DEFAULTS["omega_step"]), 10)
    try:
        hd = hydro_for(r, cfg, om, np.radians([90.0]), dict(HYDRO_DEFAULTS), cache_only=True, allow_pose_reuse=True)
    except Exception:  # noqa: BLE001
        pytest.skip("two-body BEM cache not available in this checkout")
    m = build_response(r, hd, cfg)
    damp = {"EXO": {"zeta": {"heave": .05, "roll": .05, "pitch": .05}, "absolute": {"surge": 200, "sway": 200, "yaw": 200}},
            "BOAT": {"zeta": {"heave": .05, "roll": .1, "pitch": .1}, "absolute": {"surge": 500, "sway": 500, "yaw": 500}}}
    w, b = 2 * np.pi / 2.5, np.radians(90)
    m.regular_wave(0.002, 2.5, b, damp, cfg["deck_acceleration_points"])
    sn = line_snatch_check(m, w, b, 0.002, damp, n_periods=16, steps_per_period=96)
    assert all(l["slack_fraction_of_cycle"] == 0 for l in sn["lines"])
    for nm in ("EXO_heave", "EXO_roll", "BOAT_heave", "BOAT_roll"):
        assert sn["amplitude_nonlinear"][nm] == pytest.approx(sn["amplitude_linear"][nm], rel=0.03)
    m.regular_wave(0.3, 2.5, b, damp, cfg["deck_acceleration_points"])
    sn = line_snatch_check(m, w, b, 0.3, damp, n_periods=10, steps_per_period=64)
    assert any(l["slack_fraction_of_cycle"] > 0.1 for l in sn["lines"]) and max(l["snatch_ratio"] for l in sn["lines"]) > 1.3
