"""The `yoke` element: one rope, two legs, ONE tension.

A yoke is the mirror of a bridle. A bridle equalises tension between two EXO legs over a turning point on the boat;
a yoke equalises it between two legs that end on the BOAT, over turning points on the EXO (blocks at the posts and a
winch on the rail between them). What must hold:

  * both legs carry the same tension, by construction - that is the whole point of the element;
  * the path length is the sum of the two leg lengths, so slack in one leg is slack in both;
  * a symmetric yoke applies NO net couple to either body, and is in equilibrium with itself;
  * it is tension-only: shorten the path and it goes slack rather than pushing.

Equalising the pair costs their differential stiffness. That is measured rather than asserted here - COUPLING.md
section 19 - because the question is how much, not whether.
"""
import numpy as np
import pytest

from exo01 import arrangements as AR
from exo01.config import load_config, resolve, validate
from exo01.twobody import _line_forces, element_sign

HB = dict(placement_in_exo_frame=dict(x_m=AR.X_BERTH, y_m=0.0, z_m=0.0))


def _poses(dx=0.0, yaw_deg=0.0):
    psi = np.radians(yaw_deg)
    Rb = np.array([[np.cos(psi), -np.sin(psi), 0.0], [np.sin(psi), np.cos(psi), 0.0], [0.0, 0.0, 1.0]])
    pe = dict(R_world=np.eye(3).tolist(), com_world=[2.30, 0.0, 0.64], G_body=[2.30, 0.0, 0.64], yaw_rad=0.0)
    pb = dict(R_world=Rb.tolist(), com_world=[AR.X_BERTH + 3.60 + dx, 0.0, 0.35],
              G_body=[3.60, 0.0, 0.35], yaw_rad=float(psi))
    return pe, pb


def _run(cfg, pe, pb, L0=None):
    """Solve the elements at this pose, deriving L0 the way the solver does: L_nominal -/+ T0/k."""
    k = np.array([c["stiffness_N_per_m"] for c in cfg], float)
    if L0 is None:
        probe = _line_forces(HB, cfg, pe, pb, np.zeros(len(cfg)), k, None)
        Lnom = np.array([p["L"] for p in probe])
        T0 = np.array([c.get("pretension_N", 0.0) for c in cfg], float)
        sg = np.array([element_sign(c) for c in cfg], float)
        L0 = Lnom - np.where(sg < 0, -1.0, 1.0) * T0 / k
    return _line_forces(HB, cfg, pe, pb, np.asarray(L0, float), k, None), L0


YK = AR.yoke("Y", AR.FWD_POST, AR.MID_CLEAT, t0=600.0)


def test_yoke_legs_share_one_tension_and_sum_their_lengths():
    pe, pb = _poses()
    (r,), _ = _run(list(YK), pe, pb)
    assert r["kind"] == "yoke"
    l1, l2 = r["leg_len_m"]
    assert r["L"] == pytest.approx(l1 + l2, rel=1e-12)
    T1 = float(np.linalg.norm(r["legs_b"][0][1]))
    T2 = float(np.linalg.norm(r["legs_b"][1][1]))
    assert T1 == pytest.approx(T2, rel=1e-12), "a yoke that does not equalise is not a yoke"
    assert T1 == pytest.approx(abs(r["T"]), rel=1e-12)
    assert r["T"] == pytest.approx(600.0, rel=1e-9), "preload must come out as asked"


def test_the_tension_stays_equal_when_the_boat_is_displaced_and_yawed():
    """The pair it replaces would split 76/524 N here. The yoke must not: that asymmetry is what it trades away."""
    pe, pb = _poses(dx=-0.015, yaw_deg=1.7)
    (ry,), _ = _run(list(YK), pe, pb, L0=_run(list(YK), *_poses())[1])
    T1 = float(np.linalg.norm(ry["legs_b"][0][1]))
    T2 = float(np.linalg.norm(ry["legs_b"][1][1]))
    assert T1 == pytest.approx(T2, rel=1e-12)

    springs = AR.pair("S", AR.FWD_POST, AR.MID_CLEAT, t0=600.0)
    _, L0s = _run(springs, *_poses())
    rp, _ = _run(springs, pe, pb, L0=L0s)
    assert abs(rp[0]["T"] - rp[1]["T"]) > 50.0, "the spring pair should split under yaw - that is the comparison"


def test_symmetric_yoke_applies_no_couple_to_either_body():
    pe, pb = _poses()
    (r,), _ = _run(list(YK), pe, pb)
    f = r["T"] * np.asarray(r["u"], float)
    Me = sum((np.cross(np.asarray(p) - np.asarray(pe["com_world"]), fp) for p, fp in r["legs"]), np.zeros(3))
    Mb = sum((np.cross(np.asarray(p) - np.asarray(pb["com_world"]), fp) for p, fp in r["legs_b"]), np.zeros(3))
    assert abs(f[1]) < 1e-9, "mirrored legs cannot make a net sway force"
    assert abs(Me[0]) < 1e-9 and abs(Me[2]) < 1e-9, "no roll or yaw on the EXO"
    assert abs(Mb[0]) < 1e-9 and abs(Mb[2]) < 1e-9, "no roll or yaw on the boat"
    assert np.allclose(f + sum((fp for _, fp in r["legs_b"]), np.zeros(3)), 0.0, atol=1e-9)


def test_leg_forces_sum_to_the_reported_resultant_on_both_sides():
    """The resultant the assembly uses for force must agree with the legs it uses for moment."""
    pe, pb = _poses(dx=-0.02, yaw_deg=1.1)
    (r,), _ = _run(list(YK), pe, pb)
    assert np.allclose(sum((fp for _, fp in r["legs"]), np.zeros(3)),
                       r["T"] * np.asarray(r["u"], float), atol=1e-9)
    assert np.allclose(sum((fp for _, fp in r["legs_b"]), np.zeros(3)),
                       -r["T"] * np.asarray(r["u"], float), atol=1e-9)


def test_a_yoke_is_tension_only():
    pe, pb = _poses()
    _, L0 = _run(list(YK), pe, pb)
    pe2, pb2 = _poses(dx=-0.5)            # boat 0.5 m closer: both legs shorten well past slack
    (r,), _ = _run(list(YK), pe2, pb2, L0=L0)
    assert r["L"] < r["L0"]
    assert r["T"] == 0.0 and r["slack"]


def test_yoke_matches_the_spring_pair_it_replaces_leg_for_leg():
    """Same points, same preload, undisplaced: the yoke's legs ARE the spring pair's legs."""
    pe, pb = _poses()
    (ry,), _ = _run(list(YK), pe, pb)
    rp, _ = _run(AR.pair("S", AR.FWD_POST, AR.MID_CLEAT, t0=600.0), pe, pb)
    assert sorted(ry["leg_len_m"]) == pytest.approx(sorted(r["L"] for r in rp), rel=1e-12)
    assert np.allclose(ry["T"] * np.asarray(ry["u"], float),
                       sum((r["T"] * np.asarray(r["u"], float) for r in rp), np.zeros(3)), atol=1e-9)


def test_config_rejects_a_malformed_yoke():
    ill = load_config("illustrative")
    bad = resolve(ill, {"host_boat": {"lines": [dict(id="Y", kind="yoke", exo_point_m=[1, 1, 0],
                                                     boat_point_m=[1, 1, 0], stiffness_N_per_m=1e4)]}})
    msgs = [m for lv, m in validate(bad) if lv == "error"]
    assert any("boat_point_b_m" in m for m in msgs)


def test_the_combo_arrangement_is_registered_and_mirrors_arrangement_I():
    a = AR.build("X_yoke_midship_crossed")
    i = AR.build("I_fwd_midship_crossed")
    ids = {e["id"] for e in a}
    assert "YOKE" in ids and not {"SPRING_PORT", "SPRING_STBD"} & ids
    assert len(a) == len(i) - 1, "one rope replaces two"
    rest_a = {e["id"]: e for e in a if e["id"] != "YOKE"}
    rest_i = {e["id"]: e for e in i if not e["id"].startswith("SPRING")}
    assert rest_a == rest_i, "the combo must change nothing else about arrangement I"
    assert AR.ARRANGEMENTS["X_yoke_midship_crossed"]["ops_actions"] == 1, "one winch, one action"


def test_the_combo_geometry_carries_both_boat_points_for_drawing():
    (g,) = [e for e in AR.element_geometry("X_yoke_midship_crossed") if e["id"] == "YOKE"]
    assert g.get("a2") is not None and g.get("b2") is not None
    assert g["a"][1] == pytest.approx(-g["a2"][1]) and g["b"][1] == pytest.approx(-g["b2"][1])
