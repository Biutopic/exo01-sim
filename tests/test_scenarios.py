import json

import pytest

from exo01.analysis import evaluate
from exo01.config import load_config, load_scenario, resolve, resolve_scenario, list_scenarios, validate
from exo01.mass import validate_people
from exo01 import scenarios as sc


def test_builtin_scenarios_present():
    assert {"baseline_illustrative", "battery_relocated", "occupants_symmetric", "occupants_asymmetric"} <= set(list_scenarios())


def test_recompute_after_change(ill_result):
    r = evaluate(resolve_scenario(load_scenario("occupants_symmetric")))
    assert r["mass"]["total_mass_kg"] == pytest.approx(856 + 160)
    assert r["equilibrium"]["displaced_mass_kg"] == pytest.approx(1016.0, rel=1e-10)
    assert r["mass"]["com_m"][2] > ill_result["mass"]["com_m"][2]


def test_save_load_roundtrip(tmp_path):
    s = load_scenario("battery_relocated")
    p = tmp_path / "x.json"
    sc.save_scenario(s, p)
    s2 = load_scenario(p)
    assert s == s2
    assert resolve_scenario(s) == resolve_scenario(s2)


def test_people_validation(illustrative):
    bad = resolve(illustrative, {"people": [
        {"id": "P1", "mass_kg": 80, "surface": "observation_deck", "posture": "standing", "x_m": 0.5, "y_m": 0.0},   # off the deck
        {"id": "P2", "mass_kg": 80, "surface": "lower_deck", "posture": "standing", "x_m": 1.0, "y_m": 0.0, "com_height_m": -0.1},
        {"id": "P3", "mass_kg": -5, "surface": "lower_deck", "posture": "seated_on_deck", "x_m": 1.0, "y_m": 0.0}]})
    errs = [m for l, m in validate_people(bad)]
    assert len(errs) == 3
    assert evaluate(bad)["status"].get("all") == "invalid_input"


def test_person_com_above_surface_standing_vs_seated(illustrative):
    from exo01.mass import items_from_config
    cfg = resolve(illustrative, {"people": [
        {"id": "S", "mass_kg": 80, "surface": "observation_deck", "posture": "standing", "x_m": 2.8, "y_m": 0.0},
        {"id": "Q", "mass_kg": 80, "surface": "observation_deck", "posture": "seated_on_deck", "x_m": 2.8, "y_m": 0.5}]})
    its = {i.id: i for i in items_from_config(cfg)}
    assert its["S"].com[2] == pytest.approx(2.2 + 1.0) and its["Q"].com[2] == pytest.approx(2.2 + 0.4)


def test_duplicate_component_detected(illustrative):
    import copy
    cfg = copy.deepcopy(illustrative)
    cfg["components"].append(copy.deepcopy(cfg["components"][0]))
    assert any(l == "error" for l, _ in validate(cfg))


def test_compare_table_uses_only_computed_values():
    rows = sc.compare_table([evaluate(load_config("baseline"))])
    assert rows[0]["total_listed_mass_kg"] == 840.0 and rows[0]["trim_deg"] is None
