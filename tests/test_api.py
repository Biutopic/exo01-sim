"""HTTP API: JSON everywhere (errors included), no-equilibrium reporting, cached wave response, job listing."""
import json

import pytest

import app as server


@pytest.fixture(scope="module")
def client():
    server.app.config["TESTING"] = True
    return server.app.test_client()


def _scenario(client, name):
    sc = client.get(f"/api/scenario/{name}").get_json()
    return dict(base=sc["base"], overrides=sc["overrides"])


def test_meta_and_presets(client):
    m = client.get("/api/meta").get_json()
    assert m["version"] and "with_hydronaute" in m["scenarios"]
    assert {p["id"] for p in m["line_presets"]} >= {"simulator_default", "figure_all_forward", "push_springs_long"}
    assert m["propulsion_defaults"]["units"]["EXO_PODS"]["bollard_thrust_N"] > 1000


def test_evaluate_default_is_coupled(client):
    r = client.post("/api/evaluate", json=_scenario(client, "with_hydronaute")).get_json()
    assert r["status"]["equilibrium"] == "solved" and r["coupled_equilibrium"]["converged"]
    assert len(r["lines"]) == 4 and all(l["tension_N"] > 0 for l in r["lines"])


def test_bad_input_is_a_json_400(client):
    st = _scenario(client, "with_hydronaute")
    st["overrides"] = dict(st["overrides"], components={"NOT_A_COMPONENT": {"mass_kg": 1}})
    resp = client.post("/api/evaluate", json=st)
    assert resp.status_code == 400
    j = resp.get_json()
    assert j["status"] == "error" and "NOT_A_COMPONENT" in j["error"]


def test_no_equilibrium_reports_best_point(client):
    st = _scenario(client, "baseline_illustrative")
    st["overrides"] = dict(st["overrides"], people=[dict(id="P1", mass_kg=800, surface="lower_deck", posture="standing", x_m=0.5, y_m=-1.8)])
    r = client.post("/api/evaluate", json=st).get_json()
    assert r["status"]["equilibrium"] == "no_feasible_equilibrium"
    bp = r["equilibrium"]["best_point"]
    assert bp and bp["trim_deg"] < -5 and bp["full_floats"]              # stern sinks, rear float(s) fully submerged
    assert r["bodies"]["exo"]["best_point_only"] and len(r["bodies"]["exo"]["pose"]["R_world"]) == 3


def test_wave_from_cache_or_no_hydro(client):
    """With the shipped cache the default two-body pose answers at once; without it the status is 'no_hydro' (never a 500)."""
    st = _scenario(client, "with_hydronaute")
    resp = client.post("/api/wave", json=dict(st, wave=dict(H_m=0.3, T_s=2.5, heading_deg=90), allow_pose_reuse=True,
                                                damping={"EXO": {"zeta": {"heave": .05, "roll": .05, "pitch": .05}}, "BOAT": {"zeta": {"roll": .1}}}))
    assert resp.status_code == 200
    j = resp.get_json()
    if j.get("status") == "no_hydro":
        pytest.skip("no cached BEM in this checkout")
    rw = j["regular_wave"]
    assert rw["in_range"] and set(rw["bodies"]) == {"EXO", "BOAT"}
    assert 0 < rw["bodies"]["EXO"]["amplitude_deg"]["roll"] < 30 and rw["bodies"]["BOAT"]["amplitude"]["heave"] > 0
    assert "lines" in rw and all("tension_mean_N" in l for l in rw["lines"])
    assert "relative_motion" in rw


def test_jobs_listing_and_unknown_job(client):
    assert isinstance(client.get("/api/jobs").get_json(), list)
    assert client.get("/api/job/nope").status_code == 404
