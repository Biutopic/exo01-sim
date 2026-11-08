"""The coupling elements added for the final configuration (3 Nov 2026): the pulley bridle, a contact with a declared
normal (axis_m) and a contact that starts open (gap_m)."""
import numpy as np
import pytest

from exo01.analysis import evaluate
from exo01.config import load_config, resolve, validate
from exo01.twobody import ELEMENT_KINDS, element_sign

X_BERTH, X_CROSS = 2.265, 2.10


def _cfg(elements, ill):
    return resolve(ill, {"host_boat": {"lines": elements,
                                       "placement_in_exo_frame": dict(ill["host_boat"]["placement_in_exo_frame"], x_m=X_BERTH)},
                         "propulsion": {"thrust_fraction": 0.0}})


def _bridle(T0=1600.0, k=13500.0):
    return dict(id="VEE", kind="bridle", exo_point_m=[5.20, 2.25, 0.30], exo_point_b_m=[5.20, -2.25, 0.30],
                boat_point_m=[8.00, 0.0, 0.78], stiffness_N_per_m=k, pretension_N=T0)


def _bumper(sgn, k=50000.0, gap=0.0):
    return dict(id=f"B{'P' if sgn > 0 else 'S'}", kind="fender", axis_m=[1.0, 0.0, 0.0],
                exo_point_m=[X_CROSS, sgn * 0.90, 0.25], boat_point_m=[0.0, sgn * 0.90, 0.40],
                stiffness_N_per_m=k, pretension_N=0.0, gap_m=gap)


def test_bridle_is_a_known_kind():
    assert ELEMENT_KINDS["bridle"] == +1
    assert element_sign({"id": "x", "kind": "bridle"}) == +1


def test_bridle_needs_its_second_leg(illustrative):
    bad = dict(_bridle()); bad.pop("exo_point_b_m")
    errs = [m for lvl, m in validate(_cfg([bad], illustrative)) if lvl == "error"]
    assert any("exo_point_b_m" in m for m in errs)


def test_axis_and_gap_are_fender_only(illustrative):
    errs = [m for lvl, m in validate(_cfg([dict(_bridle(), gap_m=0.03)], illustrative)) if lvl == "error"]
    assert any("gap_m" in m for m in errs)
    line = dict(id="L", kind="line", exo_point_m=[2.1, 2.25, 0.0], boat_point_m=[0.3, 1.3, 0.8], axis_m=[1, 0, 0])
    errs = [m for lvl, m in validate(_cfg([line], illustrative)) if lvl == "error"]
    assert any("axis_m" in m for m in errs)


def test_pulley_equalises_and_the_resultant_follows_the_half_angle(illustrative):
    """One rope over a pulley: the aft resultant on the boat must be 2 cos(alpha) times the rope tension, and the
    rear bumpers must carry exactly that resultant."""
    els = [_bridle(), _bumper(+1), _bumper(-1)]
    r = evaluate(_cfg(els, illustrative))
    ce = r["coupled_equilibrium"]
    assert ce["converged"]
    lines = {l["id"]: l for l in r["lines"]}
    vee = lines["VEE"]
    alpha = np.radians(vee["half_angle_deg"])
    assert 20.0 < vee["half_angle_deg"] < 28.0                      # geometry of this berth
    amp = 2 * np.cos(alpha)
    assert vee["pulley_reaction_N"] == pytest.approx(amp * vee["tension_N"], rel=1e-6)
    bump = sum(lines[k]["compression_N"] for k in ("BP", "BS"))
    assert bump == pytest.approx(vee["pulley_reaction_N"], rel=2e-3)  # the whole aft pull lands on the bumpers
    # the two legs are very nearly equal; they differ by under a millimetre because the EXO's own COM sits 63 mm
    # off the centreline, so the berth is not perfectly symmetric
    assert vee["leg_length_m"][0] == pytest.approx(vee["leg_length_m"][1], abs=2e-3)


def test_a_contact_with_a_gap_carries_nothing_until_it_closes(illustrative):
    """A dockwheel-style contact that starts 30 mm open must be free at the nominal berth."""
    wheel = dict(id="W", kind="fender", axis_m=[0.0, -1.0, 0.0],
                 exo_point_m=[X_BERTH + 1.20, 1.49 + 0.030, 0.25], boat_point_m=[1.20, 1.49, 0.40],
                 stiffness_N_per_m=200000.0, pretension_N=0.0, gap_m=0.030)
    r = evaluate(_cfg([_bridle(), _bumper(+1), _bumper(-1), wheel], illustrative))
    assert r["coupled_equilibrium"]["converged"]
    w = next(l for l in r["lines"] if l["id"] == "W")
    assert w["compression_N"] == pytest.approx(0.0, abs=1.0)
    same_without_gap = dict(wheel, gap_m=0.0, exo_point_m=[X_BERTH + 1.20, 1.49, 0.25])
    r2 = evaluate(_cfg([_bridle(), _bumper(+1), _bumper(-1), same_without_gap], illustrative))
    w2 = next(l for l in r2["lines"] if l["id"] == "W")
    assert abs(w2["compression_N"]) >= abs(w["compression_N"])       # closing the gap can only add load


@pytest.mark.xfail(reason="KNOWN DEFECT, 8 Nov 2026: a fender with a declared axis_m carries its force along that "
                          "axis while its two endpoints separate geometrically, and the EXO moment is taken at `a` "
                          "while the boat moment is taken at `b`. The element therefore applies a couple of "
                          "cross(a-b, f), which no pad can transmit: measured at 178 Nm from one bumper at 2652 N, "
                          "7.4 % of the diff_opp yaw demand, acting as a spurious RESTORING couple - so modelled yaw "
                          "angles are too small wherever a fender is heavily loaded. Surge-only load cases are "
                          "unaffected (residuals 0.0-1.8 Nm); the two differential-thrust cases are not. "
                          "Applying the force at a single point was tried and DESTABILISES the yaw equilibrium (a "
                          "symmetric arrangement with no external load solves asymmetric: one bumper 7131 N, the "
                          "other 0). A correct fix needs a contact-point definition on the pad surface, not a choice "
                          "between the two reference points. See docs/COUPLING.md section 16.", strict=True)
def test_no_element_applies_a_spurious_couple():
    """Every coupling element must apply a force system with ZERO net moment: a rope, strap or pad carries no couple.

    A fender with a declared axis_m is the case that broke this. Its force lies along the declared axis while its
    two endpoints separate geometrically once the bodies displace, so taking the EXO moment at `a` and the boat
    moment at `b` invented a couple of cross(a - b, f) - measured at 178 Nm from one bumper at 2652 N, a spurious
    RESTORING couple that made reported yaw angles too small. A contact acts at one point on both bodies.
    """
    import numpy as np
    from exo01.twobody import _line_forces

    hb = dict(placement_in_exo_frame=dict(x_m=2.265, y_m=0.0, z_m=0.0))
    pe = dict(R_world=np.eye(3).tolist(), com_world=[2.3, 0.06, 0.64], G_body=[2.297, 0.063, 0.642],
              yaw_rad=0.0)
    # a displaced, yawed boat: exactly the state in which the old code invented a couple
    psi = np.radians(1.7)
    Rb = np.array([[np.cos(psi), -np.sin(psi), 0.0], [np.sin(psi), np.cos(psi), 0.0], [0.0, 0.0, 1.0]])
    pb = dict(R_world=Rb.tolist(), com_world=[5.86, 0.0, 0.35], G_body=[3.6, 0.0, 0.35],
              yaw_rad=float(psi))

    # NOTE: _u0 is the internal field the solver reads for a declared contact axis; axis_m alone is injected by the
    # config layer, so a raw dict without _u0 silently takes the geometric fallback and cannot exercise the defect.
    cfg = [
        dict(id="ROPE", kind="line", exo_point_m=[4.95, 2.25, 0.30], boat_point_m=[4.30, 1.35, 0.80],
             stiffness_N_per_m=13500.0, pretension_N=600.0),
        # a pad whose EXO point and hull point are laterally offset - the real dockwheels had a 30 mm lateral and
        # 80 mm vertical mismatch, which is why axis_m was introduced in the first place
        dict(id="BUMPER", kind="fender", exo_point_m=[2.10, 0.90, 0.25], boat_point_m=[0.0, 0.70, 0.40],
             axis_m=[-1.0, 0.0, 0.0], _u0=[-1.0, 0.0, 0.0],
             stiffness_N_per_m=50000.0, pretension_N=0.0),
        dict(id="WHEEL", kind="fender", exo_point_m=[1.20, 1.52, 0.30], boat_point_m=[1.20, 1.49, 0.40],
             axis_m=[0.0, -1.0, 0.0], _u0=[0.0, -1.0, 0.0], gap_m=0.030,
             stiffness_N_per_m=200000.0, pretension_N=0.0),
        dict(id="SLING", kind="bridle", exo_point_m=[3.07, 1.67, 0.30], exo_point_b_m=[3.07, -1.67, 0.30],
             boat_point_m=[0.80, 0.0, -0.381], stiffness_N_per_m=40100.0, pretension_N=2000.0),
    ]
    L0 = np.array([1.0, 2.0, 0.05, 3.6])
    k = np.array([c["stiffness_N_per_m"] for c in cfg], float)
    lf = _line_forces(hb, cfg, pe, pb, L0, k, None)

    for l in lf:
        M = np.zeros(3)
        F = np.zeros(3)
        T = float(l["T"])
        u = np.asarray(l["u"], float)
        if l.get("legs"):
            for p_, f_ in l["legs"]:
                M = M + np.cross(p_, f_); F = F + f_
            M = M + np.cross(np.asarray(l["b"], float), -T * u); F = F - T * u
        else:
            M = M + np.cross(np.asarray(l["a"], float), T * u); F = F + T * u
            M = M + np.cross(np.asarray(l["b"], float), -T * u); F = F - T * u
        scale = max(abs(T), 1.0)
        assert np.linalg.norm(F) < 1e-6 * scale, f"{l['id']} applies a net FORCE to the pair: {F}"
        assert np.linalg.norm(M) < 1e-6 * scale, f"{l['id']} applies a net COUPLE to the pair: {M} Nm (T={l['T']} N)"
