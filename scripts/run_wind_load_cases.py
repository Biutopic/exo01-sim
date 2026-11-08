"""Wind as a coupling load case, and the thrust cases recomputed at an upright pose.

    python scripts/run_wind_load_cases.py

Two things the coupling study (docs/COUPLING.md sections 1-16) never had:

1. **Wind.** A platform carrying 16 m2 of solar panels inside a 4,50 x 3,00 m envelope, coupled to a boat with a
   28 m2 lateral silhouette, is a sail. A beam wind pushes the pair sideways and yaws it, and the coupling carries
   whatever the two bodies do not each absorb hydrodynamically. The whole arrangement comparison omitted this.

2. **Corrected thrust demands.** `demands()` built every load case from resistance evaluated at a pose where the
   boat sits at 88,6 deg of heel (see docs/PERFORMANCE.md). At an upright pose the boat's resistance is 37 % higher
   and its share of the total rises from 69 % to 76 %, so every surge value and every reverse case changes.

Both are injected as GLOBALLY BALANCED external wrenches, the same discipline the thrust cases use: whatever is
applied to one body is reacted on the other, with the moment transported between the two centres of mass. An
unbalanced wrench makes the solver report a divergent answer as converged.

The sway reaction is split between the bodies by their SUBMERGED LATERAL AREA, which is computed from the meshes.
That is a crude proxy for the sway drag share - it ignores the very different aspect ratios of a slender float row
and a hull - and it is the main assumption in the wind cases.
"""
import json
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
warnings.simplefilter("ignore")
import numpy as np  # noqa: E402

from exo01 import aero, performance as perf  # noqa: E402
from exo01.analysis import evaluate  # noqa: E402
from exo01.config import load_config, resolve  # noqa: E402
from exo01.propulsion import boat_geometry, exo_geometry  # noqa: E402
from exo01.twobody import coupled_equilibrium  # noqa: E402
from exo01.buoyancy import clip_below  # noqa: E402

OUT = ROOT / "results" / "performance"
OUT.mkdir(parents=True, exist_ok=True)
KNOT = perf.KNOT

# element builders and the model handles
_asrc = (ROOT / "scripts" / "run_arrangement_search.py").read_text()
ANS = {"__file__": str(ROOT / "scripts" / "run_arrangement_search.py"), "__name__": "wind"}
_argv, sys.argv = sys.argv, ["x"]
exec(compile(_asrc.split("rows = []\nt0 = time.time()")[0], "a", "exec"), ANS)
_fsrc = (ROOT / "scripts" / "run_final_coupling.py").read_text()
FNS = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "wind_model"}
exec(compile(_fsrc.split("# ─────────────────────────────────────────────────────────────── A · preload sweep")[0]
             if "─────────────────────────────────────────────────────────────── A · preload sweep" in _fsrc
             else _fsrc.split("# ──────────────────────────────────────────────────────────────── A · preload sweep")[0],
             "f", "exec"), FNS)
sys.argv = _argv

ill = FNS["ill"]
cfg_for, X_BERTH, T_SNUG = ANS["cfg_for"], ANS["X_BERTH"], ANS["T_SNUG"]
ASM, M_E, G_E = FNS["ASM"], FNS["M_E"], FNS["G_E"]
BASM, M_B, G_B = FNS["BASM"], FNS["M_B"], FNS["G_B"]
RHO, G = FNS["RHO"], FNS["G"]
elements = FNS["elements"]


def submerged_lateral_area(tris_world):
    """Lateral (x-z) projected area of the part BELOW the waterline - the proxy for sway drag share."""
    wet, _ = clip_below(np.asarray(tris_world, float))
    if len(wet) == 0:
        return 0.0
    a, b, c = wet[:, 0], wet[:, 1], wet[:, 2]
    n = np.cross(b - a, c - a)
    return float(np.maximum(n[:, 1], 0.0).sum() / 2.0)


# ── upright pose, geometry, windage
base_cfg = resolve(ill, {"host_boat": {"lines": elements(800.0),
                                       "placement_in_exo_frame": dict(ill["host_boat"]["placement_in_exo_frame"],
                                                                      x_m=X_BERTH)},
                         "propulsion": {"thrust_fraction": 0.0, "unit": "EXO_PODS"}})
r0 = evaluate(base_cfg)
Rb_ = np.asarray(r0["_boat_eq"]["R"], float)
heel = float(np.degrees(np.arctan2(Rb_[2, 1], Rb_[2, 2])))
if abs(heel) > 5.0:
    raise SystemExit(f"POSE GATE: boat heel {heel:.1f} deg at the reference pose")
print(f"[pose] upright reference pose, boat heel {heel:+.2f} deg")

float_tris = ASM.world_tris(r0["_eq"]["R"], r0["_eq"]["G_body"], r0["_eq"]["zG"])
hull_tris = BASM.world_tris(r0["_boat_eq"]["R"], r0["_boat_eq"]["G_body"], r0["_boat_eq"]["zG"])
areas = aero.body_areas(base_cfg, float_tris_world=float_tris, hull_tris_world=hull_tris)
coeffs, rho_air = areas["_coefficients"], areas["_rho_air_kg_m3"]
exo_rows, boat_geo = exo_geometry(ASM, r0["_eq"]), boat_geometry(BASM, r0["_boat_eq"])
res_cfg = base_cfg["propulsion"]["resistance"]

A_sub_e = submerged_lateral_area(float_tris)
A_sub_b = submerged_lateral_area(hull_tris)
share_b = A_sub_b / (A_sub_e + A_sub_b)
print(f"[sway share] submerged lateral area: EXO {A_sub_e:.2f} m2, boat {A_sub_b:.2f} m2 "
      f"-> boat takes {100*share_b:.0f} % of the sway reaction (ASSUMED proxy for drag share)")

# ── corrected thrust demands at this pose
U_corr = perf.max_speed(model="momentum", T0=float(base_cfg["energy"]["propulsion"]["total_bollard_N"]),
                        A_disk=2 * np.pi * 0.125 ** 2, P_water=None,
                        exo_rows=exo_rows, boat_geo=boat_geo, res_cfg=res_cfg)
hr = perf.hydro_resistance(U_corr, exo_rows, boat_geo, res_cfg)
print(f"[thrust cases] corrected: at the realistic max speed {U_corr:.2f} m/s, R_boat {hr['boat_N']:.0f} N, "
      f"R_exo {hr['exo_N']:.0f} N, boat share {100*hr['boat_N']/hr['total_N']:.0f} % "
      f"(the project used R_boat 841 N and 69 %)")

# ── load cases
CASES = []
for V_kn in (10, 15, 20, 25, 30):
    V = V_kn * KNOT
    for ang in (45, 90, 135):
        V_app, beta = aero.apparent_wind(0.0, V, ang)         # moored / station-keeping: no way on
        we = aero.wind_wrench(areas["EXO"], V_app, beta, coeffs, rho_air)
        wb = aero.wind_wrench(areas["BOAT"], V_app, beta, coeffs, rho_air)
        Fy_tot = float(we["F"][1] + wb["F"][1])
        Mz_tot = float(we["M"][2] + wb["M"][2])
        # the boat's net demand on the coupling: its own aero load minus its share of the pair's reaction
        sway = float(wb["F"][1]) - share_b * Fy_tot
        yaw = float(wb["M"][2]) - share_b * Mz_tot
        CASES.append(dict(id=f"wind{V_kn}_{ang}", family="wind", V_kn=V_kn, wind_from_deg=ang,
                          surge=0.0, sway=sway, yaw=yaw,
                          aero_Fy_total_N=Fy_tot, aero_Mz_total_Nm=Mz_tot,
                          label=f"Moored, {V_kn} kn wind from {ang} deg"))
CASES.append(dict(id="fwd100_corr", family="thrust", surge=hr["boat_N"], sway=0.0, yaw=0.0,
                  label=f"Forward 100 %, resistance at the UPRIGHT pose ({hr['boat_N']:.0f} N, not 841 N)"))


def solve_sway(els, surge_N=0.0, sway_N=0.0, yaw_Nm=0.0):
    """Static equilibrium under a globally balanced surge/sway/yaw demand."""
    cfg = cfg_for(els)

    def external(pe, pb):
        Fb = np.array([-surge_N, -sway_N, 0.0])
        Mb = np.array([0.0, 0.0, -yaw_Nm])
        Fe = -Fb
        Me = -Mb - np.cross(np.asarray(pb["com_world"]) - np.asarray(pe["com_world"]), Fb)
        return Fe, Me, Fb, Mb

    eq, beq, pe, pb, lines, info, q = coupled_equilibrium(cfg, ASM, M_E, G_E, BASM, M_B, G_B, RHO, G,
                                                          external=external)
    tens = {l["id"]: float(l["tension_N"]) for l in lines}
    bump = [v for k, v in tens.items() if k.startswith("BUMPER")]
    return dict(converged=bool(info.get("converged")), dx_mm=1000 * q[3], dy_mm=1000 * q[4],
                dyaw_deg=float(np.degrees(q[5])), tensions=tens,
                max_tension_N=max([v for k, v in tens.items() if v > 0] or [0.0]),
                bumper_min_N=min([-v for v in bump] or [0.0]),
                unrestrained=bool(abs(q[3]) > 0.3 or abs(q[4]) > 0.3 or abs(np.degrees(q[5])) > 15))


ARR = {
    "I_fwd_midship_crossed": lambda t, g: (ANS["pair"]("SPRING", ANS["FWD_POST"], ANS["MID_CLEAT"], t0=t)
                                           + ANS["crossed"]("CROSS", ANS["MID_POST"], ANS["STERN_CLEAT"], t0=g)
                                           + ANS["rear"]() + ANS["wheels"]()),
    "A_vee_pulley": lambda t, g: ANS["vee_pulley"](t) + ANS["rear"]() + ANS["wheels"](),
}
PRELOAD = {"I_fwd_midship_crossed": 600.0, "A_vee_pulley": 2217.5}

rows = {}
t0 = time.time()
for aid, build in ARR.items():
    els = build(PRELOAD[aid], T_SNUG)
    out = {}
    for c in CASES:
        s = solve_sway(els, surge_N=c["surge"], sway_N=c["sway"], yaw_Nm=c["yaw"])
        out[c["id"]] = dict(**{k: s[k] for k in ("converged", "dx_mm", "dy_mm", "dyaw_deg", "max_tension_N",
                                                 "bumper_min_N", "unrestrained")},
                            demand=dict(surge_N=c["surge"], sway_N=c["sway"], yaw_Nm=c["yaw"]))
        ok = s["converged"] and not s["unrestrained"] and s["bumper_min_N"] >= 50.0
        print(f"  {aid:24s} {c['id']:14s} sway {c['sway']:+8.0f} N yaw {c['yaw']:+8.0f} Nm -> "
              f"{'ok  ' if ok else 'FAIL'} dy {s['dy_mm']:+8.1f} mm dyaw {s['dyaw_deg']:+7.2f} deg "
              f"maxT {s['max_tension_N']:7.0f} N bump_min {s['bumper_min_N']:7.0f} N", flush=True)
    rows[aid] = dict(preload_N=PRELOAD[aid], cases=out)

doc = dict(label="Exploratory. Wind coefficients and structural solidity assumed; the sway reaction share is a "
                 "submerged-lateral-area proxy. The thrust case is recomputed at an upright pose.",
           generated="2026-11-08",
           pose=dict(boat_heel_deg=heel),
           windage={b: {k: v for k, v in areas[b].items() if k in ("A_front_m2", "A_lateral_m2", "z_lateral_m", "L_m")}
                    for b in ("EXO", "BOAT")},
           sway_share=dict(A_submerged_lateral_exo_m2=A_sub_e, A_submerged_lateral_boat_m2=A_sub_b,
                           boat_share=share_b),
           corrected_thrust=dict(U_max_momentum_m_s=U_corr, R_boat_N=hr["boat_N"], R_exo_N=hr["exo_N"],
                                 boat_share=hr["boat_N"] / hr["total_N"],
                                 project_R_boat_N=841.06, project_boat_share=0.6935),
           cases=CASES, arrangements=rows, seconds=round(time.time() - t0, 1))
(OUT / "wind_load_cases.json").write_text(json.dumps(doc, indent=1, default=str))
print(f"\nwritten {OUT/'wind_load_cases.json'} ({time.time()-t0:.0f} s)")
