"""Host boat as a second body: hull proxy integrity, boat equilibrium, line stiffness, clearances."""
import json

import numpy as np
import pytest

from exo01.analysis import evaluate
from exo01.boat import hull_envelope, check_closed
from exo01.buoyancy import signed_volume, wet_integrals
from exo01.config import load_config, resolve
from exo01.response import line_stiffness
from conftest import ROOT

P = json.loads((ROOT / "data/renaud8000_v1/parameters.json").read_text())


def test_hull_proxy_closed_consistently_oriented_and_converged():
    h = hull_envelope(P["hull_stations_mm"], P["topside_top_z_mm"])
    assert check_closed(h.faces)
    V, F = h.vertices, h.faces
    de = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    key = de[:, 0] * len(V) + de[:, 1]
    assert len(np.unique(key)) == len(key)                                # every directed edge once
    assert np.isin(key, de[:, 1] * len(V) + de[:, 0]).all()               # ... and its reverse exists
    v0 = signed_volume(V[F])
    assert v0 > 0
    hf = hull_envelope(P["hull_stations_mm"], P["topside_top_z_mm"], dx_max=0.05, ds_max=0.05)
    assert signed_volume(hf.vertices[hf.faces]) == pytest.approx(v0, rel=1e-9)   # ruled surface: subdivision is exact
    lo, hi = V.min(0), V.max(0)
    assert np.allclose(lo, [0.0, -1.49, -0.53], atol=1e-6) and np.allclose(hi, [8.0, 1.49, 0.78], atol=1e-6)


def test_hull_proxy_waterline_consistency_check():
    """At the package's drawn waterline the proxy displaces ~4.9 m3: documented inconsistency with 2.1-3.0 t."""
    h = hull_envelope(P["hull_stations_mm"], P["topside_top_z_mm"])
    I = wet_integrals(h.vertices[h.faces])
    assert 4.5 < I["V"] < 5.2


def test_boat_equilibrium_illustrative(ill_boat_result):
    b = ill_boat_result["bodies"]["boat"]
    e = b["equilibrium"]
    assert e["feasible"]
    assert e["displaced_mass_kg"] == pytest.approx(2100.0, rel=0.02)         # lines carry a little vertical force
    assert abs(e["heel_deg"]) < 0.01                                      # symmetric boat, centreline COM
    assert 0.3 < e["draft_hull_proxy_m"] < 0.5
    assert e["deck_edge_freeboard_min_m"] > 0.5
    assert b["stability_static"]["statically_stable_here"]
    assert ill_boat_result["coupled_equilibrium"]["converged"]


def test_boat_person_heels_boat_not_exo(illustrative, ill_boat_result):
    cfg = resolve(illustrative, {"host_boat": {"people": [{"id": "BP", "mass_kg": 80, "surface": "boat_roof", "posture": "standing", "x_m": 4.0, "y_m": 1.0}]}})
    r = evaluate(cfg)
    assert r["bodies"]["boat"]["equilibrium"]["heel_deg"] < -0.3            # +Y (port) loaded -> port down -> negative
    assert r["equilibrium"]["heel_deg"] == pytest.approx(ill_boat_result["equilibrium"]["heel_deg"], abs=0.05)   # lines couple them weakly
    assert r["bodies"]["boat"]["mass"]["total_mass_kg"] == pytest.approx(2180.0)


def test_exo_only_when_boat_excluded(illustrative):
    r = evaluate(resolve(illustrative, {"host_boat": {"included": False}}))
    assert "boat" not in r["bodies"] and "lines" not in r


def test_baseline_boat_not_computed(baseline):
    r = evaluate(baseline)
    assert r["bodies"]["boat"]["status"]["equilibrium"] == "not_computed"
    assert "COM of RENAUD8000" in r["bodies"]["boat"]["not_computed"]["centre_of_mass"]


def test_clearances_and_lines_reported(ill_boat_result):
    c = ill_boat_result["clearances"]
    assert all(v is None or v > 0 for v in c["vertical_clearance_m"].values())
    assert 0.1 < c["lateral_clearance_to_float_inner_face_m"]["port"] < 0.3
    assert c["transom_to_rear_deck_plate_m"] > 0
    assert len(ill_boat_result["lines"]) == 4 and all(l["length_m"] > 0.5 for l in ill_boat_result["lines"])


def test_line_stiffness_properties(ill_boat_result):
    ce = np.array(ill_boat_result["bodies"]["exo"]["pose"]["com_world"])
    cb = np.array(ill_boat_result["bodies"]["boat"]["pose"]["com_world"])
    lines = [dict(l, body_i=0, body_j=1, pretension_N=0.0) for l in ill_boat_result["lines"]]
    K, _ = line_stiffness(lines, [ce, cb])
    assert np.allclose(K, K.T) and np.linalg.eigvalsh(K).min() > -1e-6 * np.abs(K).max()
    # rigid translation and rigid rotation of BOTH bodies produce no line force (T0 = 0)
    q = np.zeros(12); q[0] = q[6] = 1.0
    assert np.abs(K @ q).max() < 1e-9 * np.abs(K).max()
    Om = np.array([0.1, 0.2, 0.3])
    q = np.concatenate([np.zeros(3), Om, np.cross(Om, cb - ce), Om])
    assert np.abs(K @ q).max() < 1e-9 * np.abs(K).max()
    # with pretension the geometric ('string') stiffness adds T0/L-level terms only
    lines2 = [dict(l, body_i=0, body_j=1) for l in ill_boat_result["lines"]]
    K2, _ = line_stiffness(lines2, [ce, cb])
    assert np.abs(K2 @ q).max() < 2 * sum(l["pretension_N"] / l["length_m"] for l in lines2) * np.linalg.norm(q) * 3


def test_measured_mesh_import_round_trip(illustrative, ill_result, tmp_path):
    """Export the six capsule proxies as OBJ, reload them as `mesh_file` surfaces: same equilibrium, same BEM mesh path."""
    from exo01.buoyancy import save_mesh_obj, load_mesh_file, MeshSurface
    from exo01.hydro import surface_tris_for_bem, weld
    import copy
    asm = ill_result["_assembly"]
    cfg = copy.deepcopy(illustrative)
    cfg["host_boat"]["included"] = False
    new = []
    for s in asm.surfaces:
        V, F = weld(s.triangles())
        path = tmp_path / f"{s.id}.obj"
        save_mesh_obj(path, V, F)
        new.append({"id": s.id, "component_id": s.id, "type": "mesh_file", "path": str(path), "scale": 1.0, "verified": False, "source": "test export"})
    cfg["buoyant_surfaces"] = new
    r = evaluate(cfg)
    base = evaluate(resolve(illustrative, {"host_boat": {"included": False}}))
    assert r["equilibrium"]["trim_deg"] == pytest.approx(base["equilibrium"]["trim_deg"], abs=1e-6)
    assert r["equilibrium"]["freeboard"]["draft_max_m"] == pytest.approx(base["equilibrium"]["freeboard"]["draft_max_m"], abs=1e-6)
    ms = r["_assembly"].surfaces[0]
    assert isinstance(ms, MeshSurface) and ms.check()["closed"]
    V, F = surface_tris_for_bem(ms, 0.12)                       # used as-is by the BEM path
    assert len(F) == len(ms.faces)
    # inverted file orientation is corrected on load
    V2, F2 = load_mesh_file(tmp_path / f"{asm.surfaces[0].id}.obj")
    save_mesh_obj(tmp_path / "inv.obj", V2, F2[:, [0, 2, 1]])
    cfg2 = copy.deepcopy(cfg); cfg2["buoyant_surfaces"][0]["path"] = str(tmp_path / "inv.obj")
    assert evaluate(cfg2)["equilibrium"]["freeboard"]["draft_max_m"] == pytest.approx(base["equilibrium"]["freeboard"]["draft_max_m"], abs=1e-6)


def test_cob_body_position_consistent(ill_boat_result):
    """The exported body-frame COB maps back to the world COB used by the solver (previously off by zG)."""
    eq = ill_boat_result["_eq"]
    Bb = np.array(ill_boat_result["equilibrium"]["centre_of_buoyancy_body_m"])
    w = eq["R"] @ (Bb - eq["G_body"]) + np.array([0, 0, eq["zG"]])
    assert np.allclose(w, eq["integrals"]["B"], atol=1e-9)
    assert -0.6 < Bb[2] < 0.0                                         # inside the floats (z -0.58..0)
    bb = ill_boat_result["bodies"]["boat"]
    beq = ill_boat_result["_boat_eq"]
    Bb2 = np.array(bb["equilibrium"]["centre_of_buoyancy_body_m"])
    w2 = beq["R"] @ (Bb2 - beq["G_body"]) + np.array([0, 0, beq["zG"]])
    assert np.allclose(w2, beq["integrals"]["B"], atol=1e-9)


def test_coupled_equilibrium_balances_line_forces(ill_boat_result):
    """Static balance includes the tension-only lines: net line force on the EXO equals its hydrostatic imbalance."""
    c = ill_boat_result["coupled_equilibrium"]
    assert c["converged"] and c["residual_relative"] < 1e-9
    lines = ill_boat_result["lines"]
    assert all(l["tension_N"] >= 0 for l in lines)
    Fz_lines = sum(l["tension_N"] * l["unit"][2] for l in lines)             # vertical line force on the EXO (toward the boat)
    res = ill_boat_result["equilibrium"]["residuals"]
    assert res["Fz_N"] + Fz_lines == pytest.approx(0.0, abs=1e-6 * res["weight_N"])
    # horizontal line forces on the EXO cancel (nothing else holds it)
    Fx = sum(l["tension_N"] * l["unit"][0] for l in lines)
    Fy = sum(l["tension_N"] * l["unit"][1] for l in lines)
    assert abs(Fx) < 1e-6 * res["weight_N"] and abs(Fy) < 1e-6 * res["weight_N"]
    assert abs(c["boat_shift_from_nominal"]["dx_m"]) < 0.1


def test_unbalanced_line_arrangement_goes_slack(illustrative):
    """Springs attached FORWARD of the EXO posts pull the boat aft like the breast lines: no taut balance exists,
    the solver must report slack lines rather than a fake balanced pretension."""
    cfg = resolve(illustrative, {"host_boat": {"lines": [
        {"id": "A1", "exo_point_m": [2.1, 2.25, 0.0], "boat_point_m": [0.3, 1.3, 0.8]},
        {"id": "A2", "exo_point_m": [2.1, -2.25, 0.0], "boat_point_m": [0.3, -1.3, 0.8]},
        {"id": "F1", "exo_point_m": [4.95, 2.25, 0.0], "boat_point_m": [4.3, 1.35, 0.8]},
        {"id": "F2", "exo_point_m": [4.95, -2.25, 0.0], "boat_point_m": [4.3, -1.35, 0.8]}]}})
    r = evaluate(cfg)
    c = r["coupled_equilibrium"]
    assert c["converged"]
    assert any(l["slack"] for l in r["lines"]) or c["all_lines_slack"]
    assert any("slack" in f for f in r["flags"])


def test_active_set_converges_with_stiff_lines_and_yawed_berth(illustrative):
    """The tension-only kink used to stall the damped Newton on this state (residual 1e-3); the active-set outer loop
    solves it to the tolerance."""
    from exo01.config import resolve
    from exo01.analysis import evaluate
    cfg = resolve(illustrative, {"host_boat": {"mass_kg": 3000, "placement_in_exo_frame": {"x_m": 2.6, "y_m": 0.2, "yaw_deg": 3.0},
                                               "line_defaults": {"pretension_N": 400, "stiffness_N_per_m": 50000}}})
    r = evaluate(cfg)
    ce = r["coupled_equilibrium"]
    assert ce["converged"] and ce["residual_relative"] < 1e-9
    assert all(l["tension_N"] >= 0 for l in r["lines"])
    # tension-only law satisfied: slack lines have non-positive extension, taut lines positive
    for l in r["lines"]:
        ext = l["stiffness_N_per_m"] * (l["length_m"] - l["unstretched_length_m"])
        assert (l["slack"] and ext <= 1e-6) or (not l["slack"] and abs(ext - l["tension_N"]) < 1e-6)


def test_invalid_inputs_are_reported_not_crashed(illustrative):
    from exo01.config import resolve
    from exo01.analysis import evaluate
    cfg = resolve(illustrative, {"components": {"BATTERY_1": {"mass_kg": float("nan")}}, "environment": {"rho_kg_m3": 5.0}})
    r = evaluate(cfg)
    assert r["status"]["all"] == "invalid_input"
    msgs = " ".join(m for _, m in r["issues"])
    assert "BATTERY_1" in msgs and "density" in msgs
