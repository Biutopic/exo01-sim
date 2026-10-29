"""Units, coordinate transforms, mass accounting and package audit."""
import json

import numpy as np
import pytest

from exo01.reference import step_units_and_extent
from exo01.units import mm_to_m, m_to_mm
from conftest import ROOT


def test_unit_helpers():
    assert mm_to_m(4950) == pytest.approx(4.95)
    assert m_to_mm(2.2) == pytest.approx(2200.0)


def test_step_is_millimetres_and_agrees_with_glb_extent(ref):
    unit, scale, (lo, hi) = step_units_and_extent(ROOT / "data/reference_v3/EXO01_reference.step")
    assert unit == "mm" and scale == 1e-3
    glo, ghi = ref.model_bounds_cad()
    # maxima of the STEP points coincide with the GLB geometry (GLB is metres): within 3 mm
    assert np.max(np.abs(hi - ghi)) < 3e-3
    assert abs(lo[0] - glo[0]) < 3e-3


def test_root_transform_is_the_only_axis_conversion(ref):
    R = ref.R_cad_to_gltf
    assert np.allclose(R @ R.T, np.eye(3), atol=1e-12) and np.linalg.det(R) == pytest.approx(1.0)
    p = np.array([1.3, -1.97, -0.29])
    assert np.allclose(ref.cad_to_gltf(p), [1.3, -0.29, 1.97])            # (x,y,z)->(x,z,-y)
    assert np.allclose(ref.gltf_to_cad(ref.cad_to_gltf(p)), p)
    assert ref.child_has_own_transform == []                              # no child carries a transform


def test_child_vertices_are_already_cad_not_converted_twice(ref):
    lo, hi = ref.model_bounds_cad()
    expect = ref.artifact_validation["model_bounds_cad_m"]
    assert np.allclose(lo, expect["minimum"], atol=1e-6) and np.allclose(hi, expect["maximum"], atol=1e-6)
    # applying the conversion a second time would move the 5.585 m x 4.553 m footprint into Z: detect that
    wrong_lo, wrong_hi = ref.cad_to_gltf(lo), ref.cad_to_gltf(hi)
    assert not np.allclose(np.sort([wrong_lo[1], wrong_hi[1]]), np.sort([lo[1], hi[1]]), atol=1e-3)


def test_mass_each_parent_counted_once(ref):
    reg = ref.glb_mass_register()
    assert len(reg) == 16
    assert ref.total_listed_mass() == pytest.approx(840.0, abs=1e-12)
    assert ref.stray_mass_keys() == []                                   # no child carries mass_kg
    ids = list(reg)
    assert len(ids) == len(set(ids))
    cats = {}
    for v in reg.values():
        cats[v["category"]] = cats.get(v["category"], 0) + v["mass_kg"]
    assert cats == {"structure": 290, "float": 180, "solar": 80, "battery": 240, "electronics": 50}
    # children refer to existing parents
    unresolved = []
    for n in ref.nodes:
        e = n.get("extras") or {}
        if "mass_owner" in e:
            assert e["mass_owner"] in reg
            if e["mass_is_in_parent"] is not True:
                unresolved.append((n["name"], e))
    # exactly one child is documented as unresolved: the observation-deck surface (mass inclusion unconfirmed)
    assert [u[0] for u in unresolved] == ["upper_observation_deck_proxy"]
    e = unresolved[0][1]
    assert e["mass_is_in_parent"] is None and e["surface_mass_kg"] is None and e["occupants_mass_kg"] is None


def test_json_register_matches_glb_and_config(ref, baseline):
    jm = {c["component_id"]: c["mass_kg"] for c in ref.meta["components"]}
    gm = {k: v["mass_kg"] for k, v in ref.glb_mass_register().items()}
    cm = {c["id"]: c["mass_kg"] for c in baseline["components"] if c.get("register", True)}
    assert jm == gm == cm
    assert sum(cm.values()) == 840
    extra = [c for c in baseline["components"] if not c.get("register", True)]
    assert [c["id"] for c in extra] == ["POD_STBD", "POD_PORT"] and all(c["mass_kg"] is None for c in extra)


def test_dimensions_and_unresolved_discrepancy_preserved(baseline, ref):
    d = baseline["drawing_dimensions"]
    assert d["frame_length_m"] == 4.95 and d["drawing_overall_length_m"] == 4.98
    assert d["unresolved_length_difference_m"] == pytest.approx(0.03)
    assert d["frame_width_m"] == 4.547 and d["top_frame_z_m"] == 2.7
    assert d["observation_surface_z_m"] == pytest.approx(d["top_frame_z_m"] - 0.5)
    assert sum(d["section_lengths_m"]) == pytest.approx(4.95)
    # observation deck surface from the GLB
    lo, hi = ref.subpart_bounds_cad("EXO_MIDDLE_70", "upper_observation")
    assert hi[2] == pytest.approx(2.2, abs=1e-6)
    # solar: one transverse row, no lateral overhang, front (+X) overhang only
    for k in (1, 2, 3, 4):
        lo, hi = ref.component_bounds_cad(f"SOLAR_{k}")
        assert hi[1] <= 4.547 / 2 + 1e-6 and lo[1] >= -4.547 / 2 - 1e-6
        assert lo[0] >= 3.525 - 1e-6 and hi[0] == pytest.approx(5.585, abs=1e-6)


def test_baseline_unknowns_remain_null(baseline):
    assert all(c["com_m"] is None and c["inertia"] is None for c in baseline["components"])
    assert baseline["environment"]["rho_kg_m3"] is None and baseline["environment"]["water_depth_m"] is None
    hb = baseline["host_boat"]
    assert hb["com_m"] is None and hb["inertia"] is None and hb["people"] == []          # boat: archival mass, COM null
    assert not hb["placement_in_exo_frame"]["confirmed"] and not hb["buoyant_surface"]["verified"]
    assert baseline["people"] == []
    assert baseline["pending_loads"]["observation_deck_surface_mass_kg"] is None
    assert baseline["pending_loads"]["included_in_middle_section"] == "unconfirmed"


def test_float_proxy_matches_glb_bounds_and_volume(ref, baseline):
    """Flofiz floats keep the GLB rows (y) and stay within 0.25 m of the GLB float spans (which overlap by 9 cm)."""
    fl = ref.float_surface_params()
    for s in baseline["buoyant_surfaces"]:
        p = fl[s["id"]]
        assert s["type"] == "flofiz_x"
        assert s["y_m"] == pytest.approx(p["centre"][1], abs=1e-6)
        lo, hi = s["x_span_m"]
        assert abs(lo - (p["centre"][0] - p["length"] / 2)) < 0.25 and abs(hi - (p["centre"][0] + p["length"] / 2)) < 0.25
        assert s["diameter_m"] == 0.60 and s["z_axis_m"] == pytest.approx(-0.30)
        assert s["length_m"] == pytest.approx(1.60)                       # GLB proxies: 1.6 / 1.425 / 1.575 m end to end
