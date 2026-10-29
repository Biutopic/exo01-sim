import numpy as np
import pytest

from exo01.buoyancy import CapsuleX, BuoyantAssembly, signed_volume, wet_integrals, attitude

R, LC = 0.29, 1.6 - 0.58


def v_analytic(d, r=R, lc=LC):
    A = r * r * np.arccos(-d / r) + d * np.sqrt(r * r - d * d)
    h = d + r
    return A * lc + np.pi * h * h * (3 * r - h) / 3


def awp_analytic(d, r=R, lc=LC):
    w = np.sqrt(r * r - d * d)
    return lc * 2 * w + np.pi * w * w


CAP = CapsuleX("f", (0, 0, 0), 1.6, R, n_circ=96, n_axial=12, n_cap=24)


def test_full_volume_matches_analytic():
    assert signed_volume(CAP.triangles()) == pytest.approx(CAP.analytic_volume(), rel=1e-3)


@pytest.mark.parametrize("d", [-0.2, -0.1, 0.0, 0.1, 0.25])
def test_partial_volume_and_waterplane_vs_analytic(d):
    I = wet_integrals(CAP.triangles() - np.array([0, 0, d]))
    assert I["V"] == pytest.approx(v_analytic(d), rel=1e-3)
    assert I["Awp"] == pytest.approx(awp_analytic(d), rel=1e-3)


def test_sphere_test_body_volume_and_centroid():
    sph = CapsuleX("s", (0, 0, 0), 2 * R, R, n_circ=96, n_axial=1, n_cap=48)
    h = 0.2                                      # submerged cap height
    I = wet_integrals(sph.triangles() + np.array([0, 0, R - h]))      # waterline at body z = -R + h
    assert I["V"] == pytest.approx(np.pi * h * h * (3 * R - h) / 3, rel=1e-3)
    # centroid of a spherical cap (below the plane) is 3 (2R-h)^2 / (4 (3R-h)) below the sphere centre
    zc = -3 * (2 * R - h) ** 2 / (4 * (3 * R - h)) + (R - h)
    assert I["B"][2] == pytest.approx(zc, abs=5e-4)


def test_volume_converges_with_tessellation():
    errs = []
    for n in (16, 32, 64, 128):
        c = CapsuleX("f", (0, 0, 0), 1.6, R, n_circ=n, n_axial=8, n_cap=max(8, n // 4))
        I = wet_integrals(c.triangles() - np.array([0, 0, 0.1]))
        errs.append(abs(I["V"] / v_analytic(0.1) - 1))
    assert errs[-1] < 5e-4 and errs[-1] <= errs[0]


def test_rotation_invariance_of_total_volume():
    asm = BuoyantAssembly([CAP])
    for phi, th in [(0.3, 0.1), (-0.5, 0.4)]:
        T = asm.world_tris(attitude(phi, th), np.zeros(3), 5.0)     # fully emerged -> 0
        assert wet_integrals(T)["V"] == 0.0
        T = asm.world_tris(attitude(phi, th), np.zeros(3), -5.0)    # fully submerged -> total
        assert wet_integrals(T)["V"] == pytest.approx(asm.max_volume, rel=1e-12)


def test_float_proxies_total_volume(ill_result, ref, illustrative):
    """Six Flofiz floats: tessellated volume within 2e-4 of the analytic pi r^2 (L_body + L_nose/2); and the revision-3
    GLB capsule scenario stays within 1.5 % of the GLB's own (visual) tessellation."""
    from exo01.buoyancy import FlofizX
    from exo01.config import resolve, load_scenario
    from exo01.analysis import evaluate
    ana = sum(FlofizX(s["id"], s["flat_end_x_m"], s["nose_dir"], (s["y_m"], s["z_axis_m"]), s["diameter_m"], s["body_length_m"],
                      s["nose_length_m"]).analytic_volume() for s in illustrative["buoyant_surfaces"])
    assert ill_result["buoyant_volume_total_m3"] == pytest.approx(ana, rel=2e-4)
    assert ana == pytest.approx(6 * np.pi * 0.3 ** 2 * (1.30 + 0.15), rel=1e-12)
    glb = sum(v["tessellated_volume_m3"] for v in ref.float_surface_params().values())
    r_glb = evaluate(resolve(illustrative, load_scenario("floats_glb_capsules")["overrides"]))
    assert r_glb["buoyant_volume_total_m3"] == pytest.approx(glb, rel=0.015)
