"""Speed, wind and energy for the EXO + host boat -> results/performance/performance.json

    python scripts/run_performance.py

Produces, at the solved floating poses:

  1. a regression anchor: the existing model's own answer (constant thrust, no wind) must come back as 2,96 m/s
  2. maximum speed under the three thrust models, so the spread is visible rather than hidden
  3. the windage areas, derived from the real meshes plus the recorded dimensional envelope
  4. maximum speed against wind speed and wind direction
  5. endurance and range against held speed, from the recorded 28,8 kWh battery
  6. the solar-neutral speed - the speed the array sustains indefinitely
  7. a compact "card" of geometry-derived constants, so a browser can evaluate the same physics live

Everything is computed; nothing is typed in. Assumptions are carried in the output next to the numbers they affect.
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

OUT = ROOT / "results" / "performance"
OUT.mkdir(parents=True, exist_ok=True)
KNOT = perf.KNOT

ill = load_config("illustrative")

# Match the configuration the project's own forward-100 % figure was computed from: the coupling elements fitted and
# the boat at its berth. The poses - and therefore the wetted geometry and the resistance - depend on both, so a bare
# config gives a different answer and the regression anchor below would fail for the wrong reason.
_fsrc = (ROOT / "scripts" / "run_final_coupling.py").read_text()
_fhead = _fsrc.split("# ──────────────────────────────────────────────────────────────── A · preload sweep")[0]
FNS = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "perf_model"}
_argv, sys.argv = sys.argv, ["x"]
exec(compile(_fhead, "fhead", "exec"), FNS)
sys.argv = _argv
elements, X_BERTH = FNS["elements"], FNS["X_BERTH"]

def _pose_cfg(frac):
    return resolve(ill, {"host_boat": {"lines": elements(800.0),
                                       "placement_in_exo_frame": dict(ill["host_boat"]["placement_in_exo_frame"],
                                                                      x_m=X_BERTH)},
                         "propulsion": {"thrust_fraction": frac, "unit": "EXO_PODS"}})


def _attitude(beq):
    R = np.asarray(beq["R"], float)
    return (float(np.degrees(np.arctan2(R[2, 1], R[2, 2]))),      # heel
            float(np.degrees(np.arcsin(-np.clip(R[2, 0], -1, 1)))))  # trim


# POSE VALIDITY GATE. The coupled solve WITH thrust applied converges to a capsized branch for this arrangement:
# heel 88.6 deg, residual 1.5e-10, reported as physical and "solved". Resistance evaluated there understates the
# boat's wetted area by 44 % (11.30 m2 against 16.25 m2) and its resistance by 37 %. Every figure below is therefore
# taken at the thrust-OFF pose, which is upright and converged; sinkage and trim at speed are not modelled either
# way. See docs/PERFORMANCE.md.
cfg = _pose_cfg(0.0)
r = evaluate(cfg)
_heel, _trim = _attitude(r["_boat_eq"])
print(f"[pose] thrust-off pose: heel {_heel:+.2f} deg, trim {_trim:+.2f} deg")
if abs(_heel) > 5.0 or abs(_trim) > 10.0:
    raise SystemExit(f"POSE GATE: refusing to compute resistance at heel {_heel:.1f} deg / trim {_trim:.1f} deg")
_rt = evaluate(_pose_cfg(1.0))
_h2, _t2 = _attitude(_rt["_boat_eq"])
print(f"[pose] thrust-on pose:  heel {_h2:+.2f} deg, trim {_t2:+.2f} deg"
      f"{'   <-- REJECTED, capsized branch' if abs(_h2) > 5.0 else ''}")
POSE_WARNING = None if abs(_h2) <= 5.0 else (
    f"The coupled solve with thrust applied converges to a capsized branch (heel {_h2:.1f} deg) and reports itself "
    f"physical. All figures here use the thrust-off pose (heel {_heel:.2f} deg). The project's forward-100 % "
    f"resistance of 841 N was computed at the capsized pose and is understated by 37 %.")

# ── geometry at the solved poses (the expensive, pose-dependent part, done once)
asm, basm = r["_assembly"], r["_boat_assembly"]
eq_e, eq_b = r["_eq"], r["_boat_eq"]
exo_rows = exo_geometry(asm, eq_e)
boat_geo = boat_geometry(basm, eq_b)
res_cfg = cfg["propulsion"]["resistance"]

# ── windage areas from the same meshes, clipped above the waterline, + the recorded envelope
float_tris = asm.world_tris(eq_e["R"], eq_e["G_body"], eq_e["zG"])
hull_tris = basm.world_tris(eq_b["R"], eq_b["G_body"], eq_b["zG"])
areas = aero.body_areas(cfg, float_tris_world=float_tris, hull_tris_world=hull_tris)
coeffs = areas["_coefficients"]
rho_air = areas["_rho_air_kg_m3"]

en = cfg["energy"]
T0 = float(en["propulsion"]["total_bollard_N"])
P_ELEC = float(en["propulsion"]["total_electrical_kw"]) * 1000.0
D_DISK = 0.25                      # m, per pod. ASSUMED - the POD 5.0 duct diameter is not recorded. Swept below.
A_DISK = 2 * np.pi * (D_DISK / 2) ** 2

# propulsion.py balances the horizontal component of thrust at the trimmed pose, not the full bollard figure
_d = np.asarray(eq_e["R"], float) @ np.asarray(cfg["propulsion"]["units"]["EXO_PODS"]["direction_body"], float)
H_FACTOR = float(np.hypot(_d[0], _d[1]))
T0_H = T0 * H_FACTOR
print(f"[thrust] bollard {T0:.0f} N, horizontal factor {H_FACTOR:.4f} at the trimmed pose -> {T0_H:.0f} N driving")

base = dict(T0=T0_H, A_disk=A_DISK, P_water=None, exo_rows=exo_rows, boat_geo=boat_geo, res_cfg=res_cfg)

# ── 1. two anchors. A validates this module against propulsion.py by reproducing its answer AT THE SAME (capsized)
#       pose it used. B is the corrected answer at the upright pose. A proves the code; B is the engineering.
_ge_bad = exo_geometry(_rt["_assembly"], _rt["_eq"])
_gb_bad = boat_geometry(_rt["_boat_assembly"], _rt["_boat_eq"])
U_anchor_A = perf.max_speed(model="constant", T0=T0_H, A_disk=A_DISK, P_water=None,
                            exo_rows=_ge_bad, boat_geo=_gb_bad, res_cfg=res_cfg)
anchor_ok = abs(U_anchor_A - 2.9596) < 0.02
print(f"[anchor A] same (capsized) pose, constant thrust -> {U_anchor_A:.3f} m/s "
      f"({'MATCHES' if anchor_ok else 'DOES NOT MATCH'} propulsion.py's 2.960 m/s)")
if not anchor_ok:
    print("  this module disagrees with propulsion.py on identical inputs; results below are not trustworthy")
U_anchor = perf.max_speed(model="constant", **base)
print(f"[anchor B] upright pose, constant thrust  -> {U_anchor:.3f} m/s "
      f"({100*(U_anchor/2.9596-1):+.1f} % against the figure the project has been using)")

# ── 2. max speed, three thrust models
models = {}
for m in ("constant", "constant_power", "momentum"):
    U = perf.max_speed(model=m, **base)
    models[m] = dict(U_m_s=U, U_kn=None if U is None else U / KNOT,
                     thrust_at_speed_N=None if U is None else perf.thrust(U, T0_H, m, A_DISK))
    print(f"[max speed] {m:15s} {U:.3f} m/s = {U/KNOT:.2f} kn   (thrust there {models[m]['thrust_at_speed_N']:.0f} N)")

eff = perf.implied_efficiency(T0_H, A_DISK, P_ELEC)
print(f"[pods] implied water power {eff['P_water_W']:.0f} W of {P_ELEC:.0f} W electrical "
      f"-> {100*eff['efficiency']:.0f} % overall (ideal theory, so an UPPER bound)")

# ── 3. disk-diameter sensitivity (the one unrecorded propulsion input)
disk_sweep = []
for D in (0.15, 0.20, 0.25, 0.30, 0.35):
    A = 2 * np.pi * (D / 2) ** 2
    e = perf.implied_efficiency(T0_H, A, P_ELEC)
    U = perf.max_speed(model="momentum", **{**base, "A_disk": A})
    disk_sweep.append(dict(D_m=D, A_total_m2=A, implied_efficiency=e["efficiency"],
                           P_water_W=e["P_water_W"], U_max_m_s=U, U_max_kn=U / KNOT))
    print(f"[disk] D {D:.2f} m -> implied eff {100*e['efficiency']:4.0f} %, momentum U_max {U:.2f} m/s")

# ── 4. wind
print(f"[windage] EXO front {areas['EXO']['A_front_m2']:.2f} m2 lateral {areas['EXO']['A_lateral_m2']:.2f} m2 | "
      f"BOAT front {areas['BOAT']['A_front_m2']:.2f} m2 lateral {areas['BOAT']['A_lateral_m2']:.2f} m2")
wind_grid = []
for V_kn in (0, 5, 10, 15, 20, 25, 30):
    V = V_kn * KNOT
    row = dict(V_true_kn=V_kn, V_true_m_s=V, by_direction=[])
    for ang in (0, 45, 90, 135, 180):
        U = perf.max_speed(model="momentum", V_true=V, wind_from_deg=ang, areas=areas, coeffs=coeffs,
                           rho_air=rho_air, **base)
        wr = perf.wind_resistance(U or 0.0, V, ang, areas, coeffs, rho_air)
        row["by_direction"].append(dict(wind_from_deg=ang, U_max_m_s=U,
                                        U_max_kn=None if U is None else U / KNOT,
                                        Fx_N=wr["Fx_total_N"],
                                        Fy_N=sum(float(b["F"][1]) for b in wr["bodies"].values()),
                                        Mz_Nm=sum(float(b["M"][2]) for b in wr["bodies"].values()),
                                        V_app_m_s=wr["V_app_m_s"], beta_deg=wr["beta_deg"]))
    wind_grid.append(row)
    hd = row["by_direction"][0]["U_max_m_s"]
    bm = row["by_direction"][2]
    print(f"[wind] {V_kn:2d} kn: head-on U_max {('--' if hd is None else f'{hd:.2f}')} m/s | "
          f"beam: side force {bm['Fy_N']:7.0f} N, yaw {bm['Mz_Nm']:8.0f} Nm")

# ── 5. energy
bat = en["battery"]
sol = en["solar"]
P_SOLAR_FULL = float(sol["array_kwp"]) * 1000.0 * float(sol["derate_to_dc_fraction"])
P_SOLAR_FULL = min(P_SOLAR_FULL, float(sol["mppt_max_charge_w"]))
HOTEL = float(en["hotel_load_w"])
curve = []
for U in np.arange(0.5, 4.01, 0.25):
    e0 = perf.endurance(float(U), model="momentum", P_electrical_max=P_ELEC,
                        battery_kwh=float(bat["total_kwh"]), usable_fraction=float(bat["usable_fraction"]),
                        hotel_w=HOTEL, solar_w=0.0, **base)
    es = perf.endurance(float(U), model="momentum", P_electrical_max=P_ELEC,
                        battery_kwh=float(bat["total_kwh"]), usable_fraction=float(bat["usable_fraction"]),
                        hotel_w=HOTEL, solar_w=P_SOLAR_FULL, **base)
    curve.append(dict(U_m_s=float(U), U_kn=float(U) / KNOT, thrust_required_N=e0["thrust_required_N"],
                      achievable=e0["achievable"], P_propulsion_W=e0["P_propulsion_W"],
                      hours_battery_only=e0["hours"], range_km_battery_only=e0["range_km"],
                      hours_with_full_sun=es["hours"], range_km_with_full_sun=es["range_km"]))

sn = {}
for frac, label in ((1.0, "full sun"), (0.5, "half sun"), (0.25, "overcast")):
    Ps = P_SOLAR_FULL * frac
    U = perf.solar_neutral_speed(model="momentum", P_electrical_max=P_ELEC, solar_w=Ps, hotel_w=HOTEL, **base)
    sn[label] = dict(solar_w=Ps, U_m_s=U, U_kn=None if U is None else U / KNOT)
    print(f"[solar-neutral] {label:9s} {Ps:5.0f} W -> "
          f"{'hotel load exceeds solar' if U is None else f'{U:.2f} m/s = {U/KNOT:.2f} kn indefinitely'}")

# ── 6. the card: geometry-derived constants a browser can evaluate the same physics from
card = dict(
    exo_rows={k: {kk: (float(vv) if isinstance(vv, (int, float, np.floating)) else vv)
                  for kk, vv in v.items()} for k, v in exo_rows.items()},
    boat_geo={k: (float(v) if isinstance(v, (int, float, np.floating)) else
                  (np.asarray(v).tolist() if isinstance(v, np.ndarray) else v)) for k, v in boat_geo.items()},
    resistance_cfg=res_cfg, rho_water=perf.RHO_WATER, rho_air=rho_air, g=9.80665,
    areas={b: {k: v for k, v in areas[b].items() if k in ("A_front_m2", "A_lateral_m2", "z_lateral_m", "L_m")}
           for b in ("EXO", "BOAT")},
    coefficients=coeffs, T0_N=T0, T0_horizontal_N=T0_H, thrust_horizontal_factor=H_FACTOR, P_electrical_W=P_ELEC, A_disk_m2=A_DISK, disk_diameter_m=D_DISK,
    battery_kwh=float(bat["total_kwh"]), usable_fraction=float(bat["usable_fraction"]),
    solar_full_w=P_SOLAR_FULL, hotel_w=HOTEL,
)

doc = dict(
    label="Exploratory. Hull and float geometry are proxies, the wind coefficients and the two structural solidity "
          "ratios are assumed, and the pod disk diameter is not recorded. Energy and envelope figures come from the "
          "Notion cahier des charges and component list, with their conflicts carried.",
    generated="2026-11-08",
    pose=dict(heel_deg=_heel, trim_deg=_trim, thrust_on_heel_deg=_h2, thrust_on_trim_deg=_t2,
              thrust_on_rejected=bool(abs(_h2) > 5.0), warning=POSE_WARNING),
    regression_anchor=dict(U_capsized_pose_m_s=U_anchor_A, project_value_m_s=2.9596, module_validated=bool(anchor_ok),
                           U_upright_pose_m_s=U_anchor,
                           note="The project's 2.96 m/s was computed at the capsized pose. At the upright pose the "
                                "same thrust gives a lower speed, so the anchor is EXPECTED to differ now; it is "
                                "retained to show by how much."),
    max_speed=models, pods=eff, disk_sensitivity=disk_sweep,
    windage=dict(EXO=areas["EXO"], BOAT=areas["BOAT"], coefficients=coeffs, rho_air_kg_m3=rho_air),
    wind_grid=wind_grid, energy_curve=curve, solar_neutral=sn,
    spec_sources=dict(envelope=cfg["envelope"], design_rules=cfg["design_rules"], energy=en),
    card=card,
)
(OUT / "performance.json").write_text(json.dumps(doc, indent=1, default=str))
print(f"\nwritten {OUT/'performance.json'}")
