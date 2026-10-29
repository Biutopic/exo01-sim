import numpy as np
import pytest

from exo01.mass import (Item, MissingInput, inertia_shell_box, inertia_solid_box, inertia_cylinder_shell_x,
                        items_from_config, mass_properties)


def test_cube_shell_inertia():
    assert np.allclose(np.diag(inertia_shell_box(1.0, (1, 1, 1))), 5 / 18)


def test_solid_box_and_cylinder():
    assert np.allclose(np.diag(inertia_solid_box(12.0, (1, 2, 3))), [13, 10, 5])
    assert np.allclose(np.diag(inertia_cylinder_shell_x(2.0, (3.0, 0.5))), [0.5, 0.25 + 1.5, 0.25 + 1.5])


def test_parallel_axis_two_point_masses():
    it = [Item("a", "a", "x", 1.0, np.array([1, 0, 0.]), "point", ()),
          Item("b", "b", "x", 1.0, np.array([-1, 0, 0.]), "point", ())]
    mp = mass_properties(it)
    assert mp["com_m"] == [0, 0, 0]
    assert np.allclose(mp["inertia_com_kgm2"], np.diag([0, 2, 2]))


def test_parallel_axis_offset_box():
    """Box of 12 kg 1x2x3 at (5,0,0) combined with a point mass at (-5,0,0): hand calculation."""
    it = [Item("a", "a", "x", 12.0, np.array([5., 0, 0]), "solid_box", (1, 2, 3)),
          Item("b", "b", "x", 12.0, np.array([-5., 0, 0]), "point", ())]
    mp = mass_properties(it)
    I = np.array(mp["inertia_com_kgm2"])
    # about the COM (origin): box own diag(13,10,5) + 2 point-like contributions m*d^2 = 12*25 each on y,z
    assert np.allclose(np.diag(I), [13, 10 + 600, 5 + 600])


def test_inertia_symmetric_positive_definite(ill_result):
    I = np.array(ill_result["mass"]["inertia_com_kgm2"])
    assert np.allclose(I, I.T)
    assert np.all(np.linalg.eigvalsh(I) > 0)
    # triangle inequality of principal moments for a physical rigid body
    a, b, c = np.linalg.eigvalsh(I)
    assert a + b >= c - 1e-9


def test_baseline_com_is_not_computed(baseline):
    items = items_from_config(baseline)
    with pytest.raises(MissingInput):
        mass_properties(items, strict=True)
    mp = mass_properties(items, strict=False)
    assert mp["com_m"] is None and mp["inertia_com_kgm2"] is None
    assert mp["total_listed_mass_kg"] == 840.0


def test_illustrative_com_hand_check(illustrative, ill_result):
    mp = ill_result["mass"]
    xs = {c["id"]: c["com_m"] for c in illustrative["components"]}
    M = sum(c["mass_kg"] for c in illustrative["components"])
    com = sum(c["mass_kg"] * np.array(c["com_m"]) for c in illustrative["components"]) / M
    assert M == 856.0 and np.allclose(mp["com_m"], com, atol=1e-12)        # 840 register + 2 x 8 kg pods (assumed)
    assert mp["total_mass_kg"] == 856.0
