"""exo01.arrangements must stay identical to the study scripts it was consolidated from.

The point of the module is that five files no longer each carry their own copy of the geometry. That is only worth
anything if the one remaining copy still matches what the published results were computed with, so this test
re-derives the study script's constants and compares.
"""
import sys
import warnings
from pathlib import Path

import numpy as np
import pytest

from exo01 import arrangements as AR
from exo01.twobody import ELEMENT_KINDS

ROOT = Path(__file__).resolve().parents[1]
MARKER = "# ──────────────────────────────────────────────────────────────── A · preload sweep"


@pytest.fixture(scope="module")
def study():
    """The geometry as run_final_coupling.py defines it, which is what the published results used."""
    warnings.simplefilter("ignore")
    src = (ROOT / "scripts" / "run_final_coupling.py").read_text()
    ns = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "study"}
    argv, sys.argv = sys.argv, ["x"]
    try:
        exec(compile(src.split(MARKER)[0], "head", "exec"), ns)
    finally:
        sys.argv = argv
    return ns


@pytest.mark.parametrize("name", ["BUMP_PROJ", "X_CROSS", "X_BERTH", "Y_BUMP", "X_WHEEL_BOAT", "Y_HULL",
                                  "Y_FLOAT_FACE", "WHEEL_GAP", "X_VEE", "Y_VEE", "Z_VEE", "X_BOW_BOAT",
                                  "Z_BOW_BOAT", "Z_EXO", "Z_BOAT"])
def test_geometry_constants_match_the_study_script(study, name):
    assert getattr(AR, name) == pytest.approx(study[name]), f"{name} has drifted from run_final_coupling.py"


@pytest.mark.parametrize("name", ["K_ROPE", "K_BUMP", "K_WHEEL"])
def test_stiffness_sets_match(study, name):
    assert getattr(AR, name) == study[name]


def test_bumpers_and_wheels_match_the_study_elements(study):
    """elements() in the study builds the rear bumpers and dockwheels; ours must be the same objects."""
    ref = {e["id"]: e for e in study["elements"](0.0)}
    for e in AR.bumpers() + AR.wheels():
        r = ref[e["id"]]
        for k in ("kind", "stiffness_N_per_m", "pretension_N"):
            assert e[k] == r[k], f"{e['id']}.{k}"
        for k in ("exo_point_m", "boat_point_m", "axis_m"):
            assert np.allclose(e[k], r[k]), f"{e['id']}.{k}"
        if "gap_m" in r:
            assert e["gap_m"] == pytest.approx(r["gap_m"])


def test_vee_pulley_matches_the_study_rope(study):
    ref = {e["id"]: e for e in study["elements"](800.0)}["VEE_ROPE"]
    ours = AR.vee_pulley(800.0)[0]
    assert ours["kind"] == ref["kind"] == "bridle"
    for k in ("exo_point_m", "exo_point_b_m", "boat_point_m"):
        assert np.allclose(ours[k], ref[k]), k
    assert ours["stiffness_N_per_m"] == pytest.approx(ref["stiffness_N_per_m"])


# ───────────────────────────────────────────── properties the registry must keep
def test_every_arrangement_builds_and_is_well_formed():
    for aid in AR.ARRANGEMENTS:
        els = AR.build(aid)
        assert els, aid
        ids = [e["id"] for e in els]
        assert len(ids) == len(set(ids)), f"{aid} has duplicate element ids"
        for e in els:
            assert e["kind"] in ELEMENT_KINDS, f"{aid}: {e['id']} declares an unmodelled kind"
            assert e["stiffness_N_per_m"] > 0
            if e["kind"] == "bridle":
                assert e.get("exo_point_b_m") is not None, f"{e['id']} is a bridle with one leg"


def test_a_transverse_sling_has_exactly_no_surge_component():
    """The geometric fact that makes a sling need a separate surge element, and that W_spec_sling_only fails on."""
    s = AR.sling("S", 1.5, 0.0)[0]
    a, a2 = np.asarray(s["exo_point_m"]), np.asarray(s["exo_point_b_m"])
    b = np.asarray(s["boat_point_m"]) + np.array([AR.X_BERTH, 0.0, AR.Z_DATUM_OFFSET])
    for leg in (b - a, b - a2):
        assert abs(leg[0] / np.linalg.norm(leg)) < 1e-12, "a sling has gained a surge component"


def test_slings_sit_aft_of_the_boat_centre_of_mass():
    """Why the sandwich cannot lift the boat: the EXO frame does not reach forward of the COM at 3.60 m."""
    for x in AR.SLING_STATIONS:
        assert x < 3.60


def test_arrangements_declare_whether_they_need_boat_fittings():
    """Section 17 turns on this distinction, so it must be recorded rather than inferred."""
    zero = [k for k, v in AR.ARRANGEMENTS.items() if v["needs_boat_fittings"] is None]
    assert "V_spec_zero_fittings" in zero
    assert AR.ARRANGEMENTS["I_fwd_midship_crossed"]["needs_boat_fittings"]


def test_element_geometry_puts_both_ends_in_one_frame():
    g = {e["id"]: e for e in AR.element_geometry("I_fwd_midship_crossed")}
    sp = g["SPRING_PORT"]
    assert sp["length_m"] == pytest.approx(np.linalg.norm(np.asarray(sp["b"]) - np.asarray(sp["a"])))
    # nominal geometry; connection_loads.json reports 1.83 m at the SOLVED pose, which includes trim and sinkage
    assert sp["length_m"] == pytest.approx(1.88, abs=0.03)


def test_catalogue_is_serialisable():
    import json
    json.dumps(AR.catalogue())
