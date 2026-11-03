"""EXO-01 final coupling configuration (3 Nov 2026): front V-rope on a bow pulley + winch, two rear compression
bumpers, two lateral dockwheels. Statics, preload requirement, thrust cases, sensitivity to the unknown stiffnesses,
and failure modes -> results/coupling/.

    python scripts/run_final_coupling.py [--quick]

What it answers (the brief of 3 Nov):
  * does the front V-rope geometry actually produce the intended rear bumper compression, and how much;
  * what winch preload keeps the bumpers in contact under forward, reverse, differential thrust and an emergency stop;
  * the pulley reaction and the load the bow fitting must take;
  * dockwheel contact forces, lateral clearance take-up and yaw behaviour;
  * what happens when an element fails.

Every component stiffness here is UNKNOWN (no manufacturer force-deflection data was published for any of the three
contact products) and is therefore swept, never assumed to one value. Thrust comes from the existing configuration.
"""
import copy
import json
import sys
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.simplefilter("ignore")
import numpy as np  # noqa: E402

from exo01.analysis import evaluate  # noqa: E402
from exo01.config import load_config, resolve  # noqa: E402
from exo01.twobody import coupled_equilibrium, clearances  # noqa: E402

OUT = ROOT / "results" / "coupling"
OUT.mkdir(parents=True, exist_ok=True)
QUICK = "--quick" in sys.argv
ill = load_config("illustrative")

# ──────────────────────────────────────────────────────────────── geometry (EXO frame, metres)
# Set by the hardware, not chosen: the rear bumper's 3/4 profile projects ~0.165 m from the crossmember face at
# x = 2.10, so the transom rests at x = 2.265 when the bumpers just touch. The berth moves 65 mm forward of the
# previously modelled 2.20 m for this reason.
BUMP_PROJ = 0.165                 # m, 3/4 of the Ø220 fender -> contact face ahead of the crossmember
X_CROSS = 2.10                    # EXO rear crossmember
X_BERTH = X_CROSS + BUMP_PROJ     # transom at the nominal berth (bumpers touching, zero preload)
Y_BUMP = 0.90                     # bumpers inboard of the transom corners (transom half-beam 1.34 m)
Z_EXO, Z_BOAT = 0.25, 0.40        # levelled contact heights (EXO rear-deck datum / boat catalogue WL)

X_WHEEL_BOAT = 1.20               # boat station of maximum half-beam (1.49 m) -> where a wheel should bear
Y_HULL = 1.49                     # boat half-beam there
Y_FLOAT_FACE = 1.67               # EXO float inner face
WHEEL_GAP = 0.030                 # m per side: nominal clearance hull -> wheel face. ASSUMED (wheel Ø not published)

X_VEE = 5.20                      # EXO forward frame, where the V-rope legs anchor
Y_VEE = 2.25
Z_VEE = 0.30
X_BOW_BOAT = 8.00                 # boat station of the bow pulley (LOA)
Z_BOW_BOAT = 0.78                 # boat deck level at the stemhead

# ──────────────────────────────────────────────────────────────── unknown stiffnesses: swept, never assumed
K_ROPE = dict(soft=7_000.0, mid=13_500.0, stiff=27_000.0)    # N/m for the WHOLE rope path (EA 80 / 150 / 300 kN / 11.1 m)
K_BUMP = dict(soft=20_000.0, mid=50_000.0, stiff=120_000.0)  # N/m per rear bumper
K_WHEEL = dict(soft=50_000.0, mid=200_000.0, stiff=500_000.0)
BASE = dict(kr="mid", kb="mid", kw="mid", gap=WHEEL_GAP)


def elements(T0_rope, kr="mid", kb="mid", kw="mid", gap=WHEEL_GAP,
             rope=True, bumpers=(True, True), wheels=(True, True)):
    """The coupling element set. T0_rope = rope tension held by the winch at the nominal berth (N)."""
    e = []
    if rope:
        e.append(dict(id="VEE_ROPE", kind="bridle",
                      exo_point_m=[X_VEE, Y_VEE, Z_VEE], exo_point_b_m=[X_VEE, -Y_VEE, Z_VEE],
                      boat_point_m=[X_BOW_BOAT, 0.0, Z_BOW_BOAT],
                      stiffness_N_per_m=K_ROPE[kr], pretension_N=T0_rope))
    for on, sgn, nm in zip(bumpers, (+1, -1), ("PORT", "STBD")):
        if on:
            e.append(dict(id=f"BUMPER_{nm}", kind="fender", axis_m=[1.0, 0.0, 0.0],
                          exo_point_m=[X_CROSS, sgn * Y_BUMP, Z_EXO], boat_point_m=[0.0, sgn * Y_BUMP, Z_BOAT],
                          stiffness_N_per_m=K_BUMP[kb], pretension_N=0.0))
    for on, sgn, nm in zip(wheels, (+1, -1), ("PORT", "STBD")):
        if on:
            e.append(dict(id=f"WHEEL_{nm}", kind="fender", axis_m=[0.0, -float(sgn), 0.0],
                          exo_point_m=[X_BERTH + X_WHEEL_BOAT, sgn * (Y_HULL + gap), Z_EXO],
                          boat_point_m=[X_WHEEL_BOAT, sgn * Y_HULL, Z_BOAT],
                          stiffness_N_per_m=K_WHEEL[kw], pretension_N=0.0, gap_m=gap))
    return e


def cfg_for(els):
    return resolve(ill, {"host_boat": {"lines": els, "placement_in_exo_frame": dict(ill["host_boat"]["placement_in_exo_frame"], x_m=X_BERTH)},
                         "propulsion": {"thrust_fraction": 0.0}})


# ──────────────────────────────────────────────────────────────── solve one case at a prescribed demand
_BASE = evaluate(cfg_for(elements(0.0)))
ASM, BASM = _BASE["_assembly"], _BASE["_boat_assembly"]
M_E, G_E = _BASE["mass"]["total_mass_kg"], _BASE["mass"]["com_m"]
_BB = _BASE["bodies"]["boat"]["mass"]
M_B, G_B = _BB["total_mass_kg"], _BB["com_m"]
RHO = float((ill.get("environment") or {}).get("water_density_kg_m3") or 1000.0)
G = 9.80665
print(f"EXO {M_E:.0f} kg  G {np.round(G_E,3)} | boat {M_B:.0f} kg  G {np.round(G_B,3)} | berth x {X_BERTH:.3f} m")


def solve(els, surge_N=0.0, yaw_Nm=0.0):
    """Coupled static equilibrium with a prescribed in-plane demand on the boat (and its reaction on the EXO).
    surge_N > 0 = the coupling must push the boat forward (+x); < 0 = pull it aft. yaw_Nm about the boat COM."""
    cfg = cfg_for(els)

    def external(pe, pb):
        # What the rest of the world does to the boat; the coupling has to make it up. The reaction on the EXO cancels
        # the force AND the moment about a common point, so the pair is in global equilibrium and a static solution exists.
        Fb = np.array([-surge_N, 0.0, 0.0])
        Mb = np.array([0.0, 0.0, -yaw_Nm])
        Fe = -Fb
        Me = -Mb - np.cross(np.asarray(pb["com_world"]) - np.asarray(pe["com_world"]), Fb)
        return Fe, Me, Fb, Mb

    eq, beq, pe, pb, lines, info, q = coupled_equilibrium(
        cfg, ASM, M_E, G_E, BASM, M_B, G_B, RHO, G, external=external)
    cl = clearances(cfg, pe, pb, ASM)
    out = dict(converged=bool(info.get("converged")), physical=bool(info.get("physical", info.get("converged"))),
               dx_mm=1000 * q[3], dy_mm=1000 * q[4], dyaw_deg=float(np.degrees(q[5])), elements={})
    for l in lines:
        d = dict(T_N=float(l["tension_N"]), slack=bool(l.get("slack")), kind=l.get("kind", "line"))
        if l.get("kind") == "bridle":
            d.update(rope_tension_N=float(l["tension_N"]),
                     pulley_reaction_N=float(l.get("pulley_reaction_N", 0.0)),
                     half_angle_deg=float(l.get("half_angle_deg", 0.0)))
        if l.get("kind") == "fender":
            d["compression_N"] = -float(l["tension_N"])
        out["elements"][l["id"]] = d
    b = [v["compression_N"] for k, v in out["elements"].items() if k.startswith("BUMPER")]
    w = [v["compression_N"] for k, v in out["elements"].items() if k.startswith("WHEEL")]
    r = out["elements"].get("VEE_ROPE", {})
    lat = cl.get("lateral_clearance_to_float_inner_face_m") or {}
    hull_float = [float(v) for k_, v in lat.items() if isinstance(v, (int, float))]
    out["hull_to_float_min_m"] = float(min(hull_float)) if hull_float else None
    out["transom_to_deck_m"] = cl.get("transom_to_rear_deck_plate_m")
    out["clearance_flags"] = cl.get("flags", [])
    # a static solve that walks far past any modelled stop means the model has no restraint in that direction,
    # not that the boat really moves that far: report it as unrestrained rather than quoting the number
    out["unrestrained"] = bool(abs(out["dx_mm"]) > 300 or abs(out["dy_mm"]) > 300 or abs(out["dyaw_deg"]) > 15)
    out.update(bumper_total_N=float(sum(b)), bumper_min_N=float(min(b)) if b else None,
               bumper_max_N=float(max(b)) if b else None,
               wheel_max_N=float(max(w)) if w else 0.0,
               rope_N=float(r.get("rope_tension_N", 0.0)), pulley_N=float(r.get("pulley_reaction_N", 0.0)),
               vee_half_angle_deg=float(r.get("half_angle_deg", 0.0)),
               one_bumper_open=bool(b and min(b) <= 1.0),
               both_bumpers_open=bool(b and max(b) <= 1.0))
    return out


# ──────────────────────────────────────────────────────────────── demands from the existing thrust data
def demands():
    """Surge and yaw the coupling must carry, built from the configuration's own thrust and resistance model."""
    fwd = evaluate(resolve(ill, {"host_boat": {"lines": elements(800.0), "placement_in_exo_frame": dict(ill["host_boat"]["placement_in_exo_frame"], x_m=X_BERTH)},
                                 "propulsion": {"thrust_fraction": 1.0, "unit": "EXO_PODS"}}))
    pr = fwd["propulsion"]
    U = float(pr["speed_m_s"])
    R_b = float(pr["resistance"]["boat_N"])
    R_e = float(pr["resistance"]["exo_N"])
    T_bollard = float(ill["propulsion"]["units"]["EXO_PODS"]["bollard_thrust_N"])
    pods = ill["propulsion"]["units"]["EXO_PODS"]["thrust_points_m"]
    y_pod = float(max(abs(p[1]) for p in pods))
    share_b = R_b / (R_e + R_b)
    return dict(U_fwd=U, R_boat=R_b, R_exo=R_e, bollard_N=T_bollard, y_pod_m=y_pod, boat_share=share_b)


D = demands()
print(f"forward 100%: U {D['U_fwd']:.2f} m/s, R_boat {D['R_boat']:.0f} N, R_exo {D['R_exo']:.0f} N "
      f"(boat = {100*D['boat_share']:.0f} % of total), pods at y ±{D['y_pod_m']:.2f} m")

REV_FRAC = [0.5, 0.7, 1.0]        # reverse thrust as a fraction of forward bollard: UNKNOWN for a rim-drive pod
M_ADDED = 0.15                    # added-mass fraction for the surge transient: ASSUMED
CASES = []
CASES.append(dict(id="moored", label="Moored, no thrust", surge=0.0, yaw=0.0))
CASES.append(dict(id="fwd100", label="Forward, EXO pods 100 %", surge=+D["R_boat"], yaw=0.0))
for f in REV_FRAC:
    CASES.append(dict(id=f"rev{int(f*100)}", label=f"Reverse, pods {int(f*100)} % of forward bollard",
                      surge=-f * D["bollard_N"] * D["boat_share"], yaw=0.0))
# emergency stop: full reverse applied at the forward steady speed, before the pair has slowed
for f in (0.7,):
    F_net = f * D["bollard_N"] + (D["R_boat"] + D["R_exo"])          # thrust + drag both decelerate the pair
    a = F_net / ((M_E + M_B) * (1 + M_ADDED))
    surge = -(M_B * (1 + M_ADDED) * a - D["R_boat"])                 # what the coupling must take off the boat
    CASES.append(dict(id="estop", label=f"Emergency stop (full reverse {int(f*100)} % at {D['U_fwd']:.1f} m/s)",
                      surge=surge, yaw=0.0, note=f"decel {a:.2f} m/s²"))
CASES.append(dict(id="diff_one", label="Differential: one pod 100 %, other off",
                  surge=+0.5 * D["bollard_N"] * D["boat_share"], yaw=0.5 * D["bollard_N"] * D["y_pod_m"]))
CASES.append(dict(id="diff_opp", label="Differential: one pod full ahead, one full astern",
                  surge=0.0, yaw=D["bollard_N"] * D["y_pod_m"]))

# T0 = 0 exactly is a degenerate point of the active-set solve (both fenders sit exactly on their kink), so the
# sweep starts at 1 N: "rope rigged, no tension". The difference is numerical, not physical.
PRELOADS = [1, 200, 400, 600, 800, 1200, 1600, 2000, 2500, 3000, 3500] if not QUICK else [1, 800, 2000]


# ──────────────────────────────────────────────────────────────── A · preload sweep: does the rope compress the bumpers?
print("\n[A] preload sweep")
sweep = []
for T0 in PRELOADS:
    r = solve(elements(T0, **BASE))
    sweep.append(dict(preload_N=T0, **{k: r[k] for k in
                 ("converged", "physical", "dx_mm", "dy_mm", "dyaw_deg", "rope_N", "pulley_N",
                  "vee_half_angle_deg", "bumper_total_N", "bumper_min_N", "wheel_max_N", "one_bumper_open", "unrestrained", "hull_to_float_min_m")}))
    print(f"  T0 {T0:5.0f} N -> rope {r['rope_N']:6.0f} N, pulley {r['pulley_N']:6.0f} N, "
          f"bumpers {r['bumper_total_N']:6.0f} N, dx {r['dx_mm']:+6.1f} mm, alpha {r['vee_half_angle_deg']:.1f}°", flush=True)

# ──────────────────────────────────────────────────────────────── B · thrust and transient cases vs preload
print("\n[B] load cases vs preload")
cases = {}
for c in CASES:
    rows = []
    for T0 in PRELOADS:
        r = solve(elements(T0, **BASE),
                  surge_N=c["surge"], yaw_Nm=c["yaw"])
        rows.append(dict(preload_N=T0, **{k: r[k] for k in
                    ("converged", "physical", "dx_mm", "dy_mm", "dyaw_deg", "rope_N", "pulley_N",
                     "bumper_total_N", "bumper_min_N", "bumper_max_N", "wheel_max_N", "one_bumper_open",
                     "both_bumpers_open", "unrestrained", "hull_to_float_min_m")}))
    ok = [x["preload_N"] for x in rows if x["converged"] and not x["one_bumper_open"] and not x["unrestrained"]]
    held = [x["preload_N"] for x in rows if x["converged"] and not x["unrestrained"]
            and not x["both_bumpers_open"] and (x["hull_to_float_min_m"] or 1) > 0]
    cases[c["id"]] = dict(label=c["label"], surge_N=c["surge"], yaw_Nm=c["yaw"], note=c.get("note"),
                          rows=rows, min_preload_both_bumpers_N=(min(ok) if ok else None),
                          min_preload_restrained_N=(min(held) if held else None))
    mp, mh = cases[c["id"]]["min_preload_both_bumpers_N"], cases[c["id"]]["min_preload_restrained_N"]
    f_ = lambda v: "above the sweep" if v is None else f"{v:.0f} N"  # noqa: E731
    print(f"  {c['id']:9s} surge {c['surge']:+8.0f} N  yaw {c['yaw']:7.0f} N·m  -> both bumpers loaded from "
          f"{f_(mp)}; restrained from {f_(mh)}", flush=True)

# ──────────────────────────────────────────────────────────────── C · sensitivity to the unknown stiffnesses
print("\n[C] sensitivity (unknown stiffnesses), at the design preload")
T_DES = 1600.0
sens = []
for kr in K_ROPE:
    for kb in K_BUMP:
        for kw in (["mid"] if QUICK else K_WHEEL):
            r = solve(elements(T_DES, kr=kr, kb=kb, kw=kw, gap=BASE["gap"]), surge_N=0.0)
            r2 = solve(elements(T_DES, kr=kr, kb=kb, kw=kw, gap=BASE["gap"]),
                       surge_N=cases["rev70"]["surge_N"])
            sens.append(dict(rope=kr, bumper=kb, wheel=kw,
                             moored_bumper_N=r["bumper_total_N"], moored_pulley_N=r["pulley_N"], moored_dx_mm=r["dx_mm"],
                             rev70_bumper_min_N=r2["bumper_min_N"], rev70_rope_N=r2["rope_N"],
                             rev70_pulley_N=r2["pulley_N"], rev70_dx_mm=r2["dx_mm"], rev70_one_bumper_open=r2["one_bumper_open"]))
print(f"  {len(sens)} combinations; moored bumper total "
      f"{min(x['moored_bumper_N'] for x in sens):.0f}–{max(x['moored_bumper_N'] for x in sens):.0f} N")

# ──────────────────────────────────────────────────────────────── D · wheel clearance / yaw take-up
print("\n[D] lateral clearance and yaw")
gapscan = []
for gp in ([0.0, 0.030, 0.060] if not QUICK else [0.030]):
    for c in ("diff_one", "diff_opp"):
        r = solve(elements(T_DES, **{k: v for k, v in BASE.items() if k != "gap"}, gap=gp),
                  surge_N=cases[c]["surge_N"], yaw_Nm=cases[c]["yaw_Nm"])
        gapscan.append(dict(gap_mm=1000 * gp, case=c, wheel_max_N=r["wheel_max_N"], dyaw_deg=r["dyaw_deg"],
                            dy_mm=r["dy_mm"], bumper_min_N=r["bumper_min_N"], bumper_max_N=r["bumper_max_N"],
                            hull_to_float_min_m=r["hull_to_float_min_m"], converged=r["converged"]))
        print(f"  gap {1000*gp:4.0f} mm  {c:9s} -> wheel {r['wheel_max_N']:6.0f} N, yaw {r['dyaw_deg']:+.2f}°, "
              f"sway {r['dy_mm']:+.1f} mm", flush=True)

# ──────────────────────────────────────────────────────────────── E · failure modes
print("\n[E] failure modes")
FAIL = [
    ("baseline", dict()),
    ("rope_parted", dict(rope=False)),
    ("winch_released", dict()),                       # preload -> 0, rope still rigged
    ("one_bumper_lost", dict(bumpers=(True, False))),
    ("one_wheel_lost", dict(wheels=(True, False))),
]
fails = []
for name, kw in FAIL:
    T0 = 0.0 if name == "winch_released" else T_DES
    for c in ("moored", "fwd100", "rev70"):
        els = elements(T0, **{k: v for k, v in BASE.items() if k not in kw}, **kw)
        r = solve(els, surge_N=cases[c]["surge_N"], yaw_Nm=cases[c]["yaw_Nm"])
        fails.append(dict(mode=name, case=c, converged=r["converged"], physical=r["physical"],
                          dx_mm=r["dx_mm"], dy_mm=r["dy_mm"], dyaw_deg=r["dyaw_deg"],
                          rope_N=r["rope_N"], pulley_N=r["pulley_N"], bumper_total_N=r["bumper_total_N"],
                          bumper_max_N=r["bumper_max_N"], wheel_max_N=r["wheel_max_N"],
                          one_bumper_open=r["one_bumper_open"], both_bumpers_open=r["both_bumpers_open"],
                          unrestrained=r["unrestrained"], hull_to_float_min_m=r["hull_to_float_min_m"]))
    f = [x for x in fails if x["mode"] == name]
    unr = [x["case"] for x in f if x["unrestrained"] or not x["converged"]]
    ok_ = [x for x in f if not x["unrestrained"] and x["converged"]]
    print(f"  {name:16s} restrained cases: worst dx {max((abs(x['dx_mm']) for x in ok_), default=0):6.1f} mm, "
          f"worst yaw {max((abs(x['dyaw_deg']) for x in ok_), default=0):5.2f}°"
          + (f"  |  UNRESTRAINED in: {', '.join(unr)}" if unr else ""), flush=True)

# ──────────────────────────────────────────────────────────────── write
res = dict(
    label="Exploratory — assumed geometry and mass distribution; every coupling-component stiffness is UNKNOWN and swept.",
    generated="2026-11-03", version="exo01-sim v1.3-dev",
    geometry=dict(berth_x_m=X_BERTH, bumper_projection_m=BUMP_PROJ, crossmember_x_m=X_CROSS, y_bumper_m=Y_BUMP,
                  wheel_boat_station_m=X_WHEEL_BOAT, hull_half_beam_m=Y_HULL, float_inner_face_y_m=Y_FLOAT_FACE,
                  wheel_gap_m=WHEEL_GAP, vee_anchor=[X_VEE, Y_VEE, Z_VEE], bow_pulley_boat=[X_BOW_BOAT, 0.0, Z_BOW_BOAT]),
    stiffness_sets=dict(rope_N_per_m=K_ROPE, bumper_N_per_m=K_BUMP, wheel_N_per_m=K_WHEEL, base=BASE),
    demands=D, reverse_fractions=REV_FRAC, added_mass_fraction=M_ADDED,
    preload_sweep=sweep, cases=cases, sensitivity=sens, gap_scan=gapscan, failures=fails,
    design_preload_N=T_DES,
)
(OUT / "final_coupling.json").write_text(json.dumps(res, indent=1, default=str))
print(f"\nwritten {OUT/'final_coupling.json'}")
