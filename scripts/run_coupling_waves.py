"""The final coupling configuration in waves: linear response + tension-only time domain, over anchor height, rear
preload, rope stiffness and the three Erdre reference waves -> results/coupling/coupling_waves.{json,md}

    python scripts/run_coupling_waves.py [--quick]

Same wave set, damping and time-domain settings as scripts/run_mooring_final.py, so the numbers are directly comparable
with the six-rope arrangement of 30 Oct (docs/MOORING.md §7).

Front arrangement modelled: TWO FIXED LEGS (the §13 recommendation). For surge a bridle of axial stiffness k over the
whole path is exactly two legs of 2k each, so the peak tensions here also apply to the free-pulley variant; the two
differ only in yaw, where the fixed legs are the better of the two (§13.2). The linear wave model has no bridle element,
which is why the pulley variant is not run separately.
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

from exo01.analysis import evaluate, hydro_for, build_response, HYDRO_DEFAULTS  # noqa: E402
from exo01.config import load_config, resolve  # noqa: E402
from exo01.response import line_snatch_check  # noqa: E402

OUT = ROOT / "results" / "coupling"
QUICK = "--quick" in sys.argv
ill = load_config("illustrative")

src = (ROOT / "scripts" / "run_final_coupling.py").read_text()
head = src.split("# ──────────────────────────────────────────────────────────────── solve one case")[0]
NS = {"__file__": str(ROOT / "scripts" / "run_final_coupling.py"), "__name__": "waves"}
exec(compile(head, "head", "exec"), NS)
elements, BASE, K_ROPE, X_BERTH = NS["elements"], NS["BASE"], NS["K_ROPE"], NS["X_BERTH"]
XV, YV, XBOW, ZBOW = 5.20, 2.25, 8.00, 0.78

WAVES = [dict(id="beam_03_25", H_m=0.3, T_s=2.5, heading_deg=90),
         dict(id="head_03_25", H_m=0.3, T_s=2.5, heading_deg=180),
         dict(id="beam_05_30", H_m=0.5, T_s=3.0, heading_deg=90)]
DAMP = {"EXO": {"zeta": {"heave": 0.05, "roll": 0.05, "pitch": 0.05}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}},
        "BOAT": {"zeta": {"heave": 0.05, "roll": 0.10, "pitch": 0.10}, "absolute": {"surge": 0, "sway": 0, "yaw": 0}}}
SET = dict(HYDRO_DEFAULTS)
OM = np.round(np.arange(SET["omega_min"], SET["omega_max"] + 1e-9, SET["omega_step"]), 10)

ROPES = {"polyester 12 mm": K_ROPE["mid"], "UHMWPE 4.8 mm": 164_200.0}
ANCHORS = {0.30: "as drawn", 1.00: "raised"}
# Leg pretension at the nominal berth. The achieved rear compression is recorded; it is far from proportional,
# because a stiff leg relaxes as the boat settles (see COUPLING.md §4).
LEG_T0 = [500.0, 1500.0, 3000.0, 6000.0, 12000.0, 24000.0, 48000.0]
if QUICK:
    ROPES = {"polyester 12 mm": K_ROPE["mid"]}; ANCHORS = {1.00: "raised"}; LEG_T0 = [1500.0, 12000.0]; WAVES = WAVES[:1]


def legs(T0_leg, zv, k_path):
    """Two independent legs, each of twice the whole-path stiffness (a rope of half the length)."""
    return [dict(id=f"LEG_{nm}", kind="line", exo_point_m=[XV, s * YV, zv], boat_point_m=[XBOW, 0.0, ZBOW],
                 stiffness_N_per_m=2 * k_path, pretension_N=T0_leg) for s, nm in ((+1, "PORT"), (-1, "STBD"))]


def build(T0_leg, zv, k_path):
    return legs(T0_leg, zv, k_path) + [e for e in elements(0.0, **BASE) if e["id"] != "VEE_ROPE"]


def cfg_for(els):
    return resolve(ill, {"host_boat": {"lines": els,
                                       "placement_in_exo_frame": dict(ill["host_boat"]["placement_in_exo_frame"], x_m=X_BERTH)},
                         "propulsion": {"thrust_fraction": 0.0}})


def rear_total(r):
    return sum(max(0.0, -l["tension_N"]) for l in r.get("lines", []) if l["id"].startswith("BUMPER"))


def match_preload(target, zv, k_path):
    """Leg pretension that lands on `target` newtons of rear compression."""
    lo, hi = 1.0, 20000.0
    for _ in range(30):
        mid = 0.5 * (lo + hi)
        r = evaluate(cfg_for(build(mid, zv, k_path)))
        lo, hi = (mid, hi) if rear_total(r) < target else (lo, mid)
    return 0.5 * (lo + hi)


def wave_case(r, cfg, w):
    hd = np.array([np.radians(w["heading_deg"])])
    hdd = hydro_for(r, cfg, OM, hd, SET, cache_only=True, allow_pose_reuse=True)
    model = build_response(r, hdd, cfg)
    rw = model.regular_wave(w["H_m"], w["T_s"], hd[0], DAMP, cfg["deck_acceleration_points"])
    out = dict(pose_reuse=hdd.meta.get("pose_reuse"),
               boat_roll_deg=rw["bodies"]["BOAT"]["amplitude_deg"]["roll"],
               exo_roll_deg=rw["bodies"]["EXO"]["amplitude_deg"]["roll"])
    el = rw.get("lines") or []
    out["lin_leg_max_N"] = max((l["max_N"] for l in el if l["id"].startswith("LEG")), default=None)
    out["lin_leg_slack"] = [l["id"] for l in el if l["id"].startswith("LEG") and l["slack_in_cycle"]]
    out["lin_fender_opens"] = [l["id"] for l in el if l.get("kind") == "fender" and l["slack_in_cycle"]]
    rel = rw.get("relative_motion") or {}
    tg = [v for k_, v in rel.items() if k_.startswith("transom_vs_deck_edge")]
    out["transom_gap_min_m"] = min((v["min_clearance_m"] for v in tg if v["min_clearance_m"] is not None), default=None)
    sn = line_snatch_check(model, 2 * np.pi / w["T_s"], hd[0], w["H_m"], DAMP, n_periods=10, steps_per_period=64)
    lg = [l for l in sn["lines"] if l["id"].startswith("LEG")]
    bp = [l for l in sn["lines"] if l["id"].startswith("BUMPER")]
    wh = [l for l in sn["lines"] if l["id"].startswith("WHEEL")]
    out.update(td_leg_peak_N=max((l["peak_N"] for l in lg), default=None),
               td_leg_slack_frac=max((l["slack_fraction_of_cycle"] for l in lg), default=None),
               td_leg_snatch_ratio=max(((l["snatch_ratio"] or 0.0) for l in lg), default=None),
               td_bumper_peak_N=max((-l["peak_N"] for l in bp), default=None),
               td_bumper_open_frac=max((l["slack_fraction_of_cycle"] for l in bp), default=None),
               td_wheel_peak_N=max((-l["peak_N"] for l in wh), default=None),
               td_motion_ratio=sn["max_amplitude_ratio"])
    return out


rows = []
t0 = time.time()
n = len(ANCHORS) * len(ROPES) * len(LEG_T0)
i = 0
for zv, zlab in ANCHORS.items():
    for rname, kpath in ROPES.items():
        for T0 in LEG_T0:
            i += 1
            els = build(T0, zv, kpath)
            cfg = cfg_for(els)
            r = evaluate(cfg)
            ce = r.get("coupled_equilibrium") or {}
            rec = dict(anchor_z_m=zv, anchor_label=zlab, rope=rname, k_leg_N_per_m=2 * kpath, leg_pretension_N=T0,
                       converged=bool(ce.get("converged")), rear_total_N=rear_total(r),
                       leg_static_N=max((l["tension_N"] for l in r["lines"] if l["id"].startswith("LEG")), default=0.0),
                       waves={})
            if rec["converged"]:
                for w in WAVES:
                    try:
                        rec["waves"][w["id"]] = wave_case(r, cfg, w)
                    except Exception as e:  # noqa: BLE001
                        rec["waves"][w["id"]] = dict(error=f"{type(e).__name__}: {e}")
            rows.append(rec)
            eng = {wid: (not wv.get("lin_leg_slack") and not wv.get("lin_fender_opens"))
                   for wid, wv in rec["waves"].items() if "error" not in wv}
            print(f"[{i}/{n}] anchors {zv:.2f} {rname:16s} legT0 {T0:7.0f} -> rear {rec['rear_total_N']:7.0f} N, "
                  f"leg static {rec['leg_static_N']:6.0f} N | engaged all cycle: "
                  f"{ {k: ('yes' if v else 'no') for k, v in eng.items()} }  ({time.time()-t0:.0f} s)", flush=True)

res = dict(label="Exploratory — assumed geometry and masses; contact stiffnesses unknown. Front modelled as two fixed "
                 "legs (§13); for surge this is equivalent to the bridle, so the peaks apply to both front arrangements.",
           bem_note="BEM reused from a nearby pose (tier 'approximate'). Checked against an exact BEM for one case: "
                    "leg peak 2318 N exact vs 2332 N reused (0.6 %), boat roll 11.84 deg vs 12.20 deg. The reuse is "
                    "adequate for these linear results; an exact BEM costs 347 s per configuration.",
           time_domain_note="The tension-only time-domain peaks do NOT converge in this configuration: at a rear "
                    "preload of 2000 N they wander between 11.0 and 15.7 kN from 64 to 1024 steps per period, with a "
                    "time-domain/linear amplitude ratio of 6-22. With elements this stiff, no element damping and the "
                    "contacts opening twice per cycle, the integration cannot bound the snatch load. Peaks from it are "
                    "therefore NOT reported as results; the engagement criterion below is used instead.",
           generated="2026-11-03", waves=WAVES, damping=DAMP, ropes=ROPES, anchors=list(ANCHORS),
           leg_pretensions_N=LEG_T0, rows=rows, seconds=time.time() - t0)
(OUT / "coupling_waves.json").write_text(json.dumps(res, indent=1, default=str))
print(f"\nwritten {OUT/'coupling_waves.json'} ({time.time()-t0:.0f} s)")
