"""EXO-01 exploratory simulation server.

    python app.py            ->  http://127.0.0.1:8050

Physics lives in exo01/ (no rendering). This file only exposes it over HTTP and serves the static viewer.
"""
from __future__ import annotations

import copy
import csv
import io
import json
import threading
import time
import uuid
from pathlib import Path

import numpy as np
from flask import Flask, jsonify, request, send_from_directory, Response

from exo01 import __version__
from exo01 import aero, arrangements as AR, performance as perf
from exo01.analysis import build_response, evaluate, strip_private, has_boat, hydro_for, HYDRO_DEFAULTS
from exo01.config import (CONFIG_DIR, SCENARIO_DIR, ROOT, list_scenarios, load_config, load_scenario, resolve,
                          resolve_scenario)
from exo01.hydro import HydroNotComputed, POSE_TOL
from exo01.response import DOF, time_domain_check
from exo01.scenarios import compare_table, save_scenario
from exo01.units import G_STD

WEB = ROOT / "web"
EXPORT_DIR = ROOT / "results" / "exports"
EXPORT_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__, static_folder=str(WEB), static_url_path="/static")

# ------------------------------------------------------------------ hydrodynamic settings (editable from the UI)
DEFAULT_HYDRO = dict(HYDRO_DEFAULTS)
JOBS = {}
EVAL_CACHE = {}


def _np(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    if isinstance(o, dict):
        return {k: _np(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_np(v) for v in o]
    return o


def _state_from_request(body):
    base = body.get("base", "illustrative")
    cfg = load_config(base)
    cfg = resolve(cfg, body.get("overrides") or {})
    cfg["scenario_name"] = body.get("scenario_name") or base
    cfg["scenario_title"] = body.get("scenario_title") or cfg["title"]
    return cfg


def _eval_key(cfg):
    return json.dumps({k: cfg.get(k) for k in ("components", "people", "buoyant_surfaces", "environment", "host_boat", "propulsion")}, sort_keys=True)


def _evaluate_cached(cfg):
    """Results are cached on the physical content only; name/title fields are re-stamped from the request."""
    k = _eval_key(cfg)
    if k not in EVAL_CACHE:
        if len(EVAL_CACHE) > 64:
            EVAL_CACHE.clear()
        EVAL_CACHE[k] = evaluate(cfg, warm_key=cfg.get("name"))      # warm start per base configuration
    res = dict(EVAL_CACHE[k])
    res["scenario"] = cfg.get("scenario_name")
    res["title"] = cfg.get("scenario_title") or cfg["title"]
    return res


def _hydro_grid(settings, wave):
    s = dict(DEFAULT_HYDRO, **(settings or {}))
    om = np.round(np.arange(s["omega_min"], s["omega_max"] + 1e-9, s["omega_step"]), 10)
    hd = np.array([np.radians(float((wave or {}).get("heading_deg", 90.0)))])      # exact heading, no interpolation
    return s, om, hd


def _hydro(res, cfg, s, om, hd, cache_only, allow_pose_reuse=False):
    return hydro_for(res, cfg, om, hd, s, cache_only=cache_only, allow_pose_reuse=allow_pose_reuse)


@app.errorhandler(Exception)
def _any_error(e):
    """Never leave the interface without an answer: every unexpected failure becomes a JSON error (HTTP 500)."""
    import traceback
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    app.logger.error("unhandled: %s", traceback.format_exc())
    return jsonify(dict(error=f"{type(e).__name__}: {e}", status="error")), 500


# ------------------------------------------------------------------ errors as JSON (never an HTML 500 page in the interface)
@app.errorhandler(Exception)
def _json_error(e):
    from werkzeug.exceptions import HTTPException
    if isinstance(e, HTTPException):
        return e
    import traceback
    from exo01.mass import MissingInput
    bad = isinstance(e, (KeyError, ValueError, TypeError, MissingInput))
    app.logger.error("%s: %s\n%s", type(e).__name__, e, traceback.format_exc()[-1500:])
    return jsonify(dict(error=f"{type(e).__name__}: {e}", status="error", kind="input" if bad else "server")), (400 if bad else 500)


# ------------------------------------------------------------------ static
@app.get("/")
def index():
    return send_from_directory(WEB, "index.html")


@app.get("/reference.glb")
def glb():
    return send_from_directory(ROOT / "data" / "reference_v3", "EXO01_reference.glb", mimetype="model/gltf-binary")


@app.get("/boat.glb")
def boat_glb():
    return send_from_directory(ROOT / "data" / "renaud8000_v1", "Renaud8000_reference.glb", mimetype="model/gltf-binary")


# ------------------------------------------------------------------ configs / scenarios
@app.get("/api/health")
def health():
    from exo01.hydro import POSE_INDEX
    n_cache = 0
    try:
        n_cache = len(json.loads(POSE_INDEX.read_text())) if POSE_INDEX.exists() else 0
    except (OSError, ValueError):
        pass
    return jsonify(dict(ok=True, version=__version__, cached_poses=n_cache, jobs_active=sum(1 for j in JOBS.values() if j["status"] in ("queued", "running"))))


@app.get("/api/meta")
def meta():
    ill = load_config("illustrative")
    return jsonify(dict(version=__version__, configs=sorted(p.stem for p in CONFIG_DIR.glob("*.json") if p.stem in ("baseline", "illustrative")),
                        scenarios=list_scenarios(), default_hydro=DEFAULT_HYDRO,
                        five_missing=json.loads((CONFIG_DIR / "five_missing_measurements.json").read_text()),
                        dof=DOF, line_presets=(ill.get("host_boat") or {}).get("line_presets", []),
                        propulsion_defaults=ill.get("propulsion"), pose_tolerance=POSE_TOL))


@app.get("/api/config/<name>")
def get_config(name):
    return jsonify(load_config(name))


@app.get("/api/scenario/<name>")
def get_scenario(name):
    return jsonify(load_scenario(name))


@app.post("/api/scenario/save")
def post_scenario():
    body = request.get_json(force=True)
    name = "".join(ch for ch in body.get("name", "scenario") if ch.isalnum() or ch in "-_") or "scenario"
    sc = dict(schema="exo01_scenario_v1", name=name, title=body.get("title", name), base=body.get("base", "illustrative"),
              overrides=body.get("overrides") or {}, notes=body.get("notes", "user-saved scenario"),
              hydro_settings=body.get("hydro_settings"), wave=body.get("wave"), damping=body.get("damping"),
              saved=time.strftime("%Y-%m-%d %H:%M:%S"))
    path = SCENARIO_DIR / f"{name}.json"
    save_scenario(sc, path)
    return jsonify(dict(saved=str(path.relative_to(ROOT)), scenarios=list_scenarios()))


# ------------------------------------------------------------------ still water
@app.post("/api/evaluate")
def post_evaluate():
    body = request.get_json(force=True)
    cfg = _state_from_request(body)
    res = _evaluate_cached(cfg)
    out = strip_private(copy.deepcopy(res))
    out["resolved_config"] = cfg
    if "_eq" in res:
        eq = res["_eq"]
        out["pose"] = dict(R=eq["R"].tolist(), G_body=eq["G_body"].tolist(), zG=eq["zG"])
    for b in (out.get("bodies") or {}).values():
        b.pop("_eq", None)
    return jsonify(_np(out))


# ------------------------------------------------------------------ background jobs: one worker PROCESS at a time
# Heavy jobs (BEM, design sweeps) run in their own process so the interpreter serving the interface is never blocked;
# the worker writes the BEM cache + a result JSON, the server re-reads the cache (cache_only) when the job is done.
# Jobs are serialised (one process at a time, FIFO), report progress through a small JSON file, and can be cancelled
# (the process is terminated; the cache stays consistent because files are written atomically).
JOB_DIR = ROOT / "results" / "jobs"
JOB_DIR.mkdir(parents=True, exist_ok=True)
JOB_LOCK = threading.Lock()
_SCHED = {"thread": None, "proc": None, "current": None}


def _job_public(j):
    keep = ("id", "kind", "status", "created", "started", "finished", "progress", "message", "eta_s", "elapsed_s", "error", "trace",
            "meta", "result", "target", "wave", "two_body", "n_problems", "queue_position", "note", "seconds", "cancelled")
    out = {k: j[k] for k in keep if k in j}
    if j.get("status") == "running" and j.get("started"):
        out["elapsed_s"] = time.time() - j["started"]
    out["queue_position"] = _queue_position(j)
    return out


def _queue_position(j):
    if j["status"] != "queued":
        return 0
    return 1 + sum(1 for o in JOBS.values() if o["status"] == "queued" and o["created"] < j["created"]) + (1 if _SCHED["current"] else 0)


def _scheduler():
    import multiprocessing as mp
    from exo01.jobs import run_job
    ctx = mp.get_context("spawn")
    while True:
        job = None
        with JOB_LOCK:
            queued = sorted((j for j in JOBS.values() if j["status"] == "queued"), key=lambda j: j["created"])
            if queued:
                job = queued[0]
                job["status"] = "running"
                job["started"] = time.time()
                job["message"] = "starting the worker process (loading Capytaine, meshing)…"
                _SCHED["current"] = job["id"]
        if job is None:
            time.sleep(0.3)
            continue
        rpath, ppath = JOB_DIR / f"{job['id']}.result.json", JOB_DIR / f"{job['id']}.progress.json"
        for p in (rpath, ppath):
            if p.exists():
                p.unlink()
        proc = ctx.Process(target=run_job, args=(job["kind"], job["_payload"], str(rpath), str(ppath)), daemon=True)
        proc.start()
        _SCHED["proc"] = proc
        while proc.is_alive():
            if ppath.exists():
                try:
                    job.update(json.loads(ppath.read_text()))
                except (OSError, ValueError):
                    pass
            if job.get("cancel_requested"):
                proc.terminate()
                proc.join(5)
                job["status"] = "cancelled"
                job["cancelled"] = True
                break
            proc.join(0.4)
        if job["status"] == "running":
            try:
                out = json.loads(rpath.read_text()) if rpath.exists() else dict(status="error", error=f"worker exited (code {proc.exitcode}) without a result")
            except (OSError, ValueError) as e:
                out = dict(status="error", error=f"unreadable result: {e}")
            if "result" in out:
                out["result"] = _np(out["result"])
            job.update(out)
            job["progress"] = 1.0 if out.get("status") == "done" else job.get("progress")
        job["finished"] = time.time()
        for p in (rpath, ppath):
            try:
                p.unlink()
            except OSError:
                pass
        _SCHED["current"] = None
        _SCHED["proc"] = None


def _ensure_scheduler():
    if _SCHED["thread"] is None:
        _SCHED["thread"] = threading.Thread(target=_scheduler, daemon=True)
        _SCHED["thread"].start()


def _enqueue(kind, payload, **fields):
    _ensure_scheduler()
    jid = uuid.uuid4().hex[:10]
    job = dict(id=jid, kind=kind, status="queued", created=time.time(), progress=0.0, _payload=payload, **fields)
    with JOB_LOCK:
        JOBS[jid] = job
    return job


@app.post("/api/hydro")
def post_hydro():
    body = request.get_json(force=True)
    cfg = _state_from_request(body)
    settings = body.get("hydro_settings") or {}
    res = _evaluate_cached(cfg)
    if res["status"].get("equilibrium") != "solved":
        return jsonify(dict(job_id=None, status="error", error="no solved still-water equilibrium")), 200
    if res["mass"]["inertia_com_kgm2"] is None:
        return jsonify(dict(job_id=None, status="error", error="inertia tensor not available (missing inertia models)")), 200
    s, om, hd = _hydro_grid(settings, body.get("wave"))
    try:
        hdd = _hydro(res, cfg, s, om, hd, cache_only=True, allow_pose_reuse=bool(body.get("allow_pose_reuse")))
        return jsonify(_np(dict(job_id=None, status="done", meta=hdd.meta)))
    except HydroNotComputed:
        pass
    two = has_boat(res)
    om_run = om[om <= s["two_body_omega_max"] + 1e-9] if two else om
    key = json.dumps([_eval_key(cfg), s, om_run.tolist(), hd.tolist()], sort_keys=True)
    for j in JOBS.values():                                  # one job per (state, grid, heading)
        if j.get("kind") == "hydro" and j.get("key") == key and j["status"] in ("queued", "running"):
            return jsonify(dict(job_id=j["id"], status=j["status"], note="already queued", queue_position=_queue_position(j)))
    job = _enqueue("hydro", dict(cfg=cfg, settings=s, omegas=om_run.tolist(), headings=hd.tolist()), key=key, wave=body.get("wave"),
                   two_body=two, n_problems=int(len(om_run) * ((12 if two else 6) + len(hd))),
                   message=f"queued: {'EXO + boat' if two else 'EXO'} BEM, {len(om_run)} frequencies, heading {np.degrees(hd[0]):.0f} deg")
    return jsonify(dict(job_id=job["id"], status="queued", queue_position=_queue_position(job)))


@app.get("/api/jobs")
def list_jobs():
    with JOB_LOCK:
        js = sorted(JOBS.values(), key=lambda j: j["created"], reverse=True)[:20]
    return jsonify(_np([_job_public(j) for j in js]))


@app.post("/api/job/<jid>/cancel")
def cancel_job(jid):
    job = JOBS.get(jid)
    if job is None:
        return jsonify(dict(status="unknown")), 404
    if job["status"] == "queued":
        job["status"] = "cancelled"
        job["cancelled"] = True
        job["finished"] = time.time()
    elif job["status"] == "running":
        job["cancel_requested"] = True
    return jsonify(_np(_job_public(job)))


@app.get("/api/job/<jid>")
def get_job(jid):
    job = JOBS.get(jid)
    if job is None:
        return jsonify(dict(status="unknown")), 404
    return jsonify(_np(_job_public(job)))


def _model_for(body):
    cfg = _state_from_request(body)
    res = _evaluate_cached(cfg)
    if res["status"].get("equilibrium") != "solved":
        return None, None, None, "no solved still-water equilibrium"
    s, om, hd = _hydro_grid(body.get("hydro_settings") or {}, body.get("wave"))
    try:
        hdd = _hydro(res, cfg, s, om, hd, cache_only=True, allow_pose_reuse=bool(body.get("allow_pose_reuse")))
    except HydroNotComputed as e:
        return None, None, None, f"hydrodynamic coefficients not computed for this configuration/heading ({e}): run the BEM first"
    model = build_response(res, hdd, cfg, body.get("extra_stiffness"))
    return cfg, res, model, None


def _speed(body, res):
    """Forward speed for the encounter frequency: explicit `speed_m_s`, else the quasi-static propulsion speed of the state."""
    if body.get("speed_m_s") is not None:
        return float(body["speed_m_s"])
    pr = res.get("propulsion") if res else None
    return float(pr["speed_m_s"]) if pr and pr.get("speed_m_s") else 0.0


# ------------------------------------------------------------------ wave response
@app.post("/api/wave")
def post_wave():
    body = request.get_json(force=True)
    cfg, res, model, err = _model_for(body)
    if err:
        if body.get("allow_pose_reuse"):
            return jsonify(dict(error=err, status="no_hydro")), 200
        return jsonify(dict(error=err, status="not_computed")), 400
    w = body.get("wave") or {}
    H, T, beta = float(w.get("H_m", 0.3)), float(w.get("T_s", 3.0)), np.radians(float(w.get("heading_deg", 90)))
    damping = body.get("damping") or {}
    speed = _speed(body, res)
    rw = model.regular_wave(H, T, beta, damping, cfg["deck_acceleration_points"], speed=speed)
    nat = model.natural_frequencies()
    if not rw.get("in_range"):
        return jsonify(_np(dict(label=cfg["result_label"], regular_wave=rw, natural_frequencies=nat, hydro_meta=model.hydro.meta,
                                status="out_of_range", error=rw["error"]))), 200
    out = dict(label=cfg["result_label"], regular_wave=rw, natural_frequencies=nat, hydro_meta=model.hydro.meta,
               damping_used=damping, viscous_matrix_diag=np.diag(model.viscous_matrix(damping)).tolist(),
               encounter=rw.get("encounter"), speed_m_s=speed, propulsion=res.get("propulsion"),
               bodies=[dict(name=b["name"], pose=b["pose"]) for b in model.bodies],
               phase_origin_world=[0.0, 0.0] if model.nb > 1 else list(model.bodies[0]["pose"]["com_world"][:2]),
               motion_note="Reconstructed LINEAR motion about the still-water equilibrium: x_i(t) = Re(X_i exp(-i w t)), "
                           "unit-amplitude wave crest at the COM at t = 0.")
    if rw.get("in_range"):
        t = np.linspace(0, 3 * T, 181)
        x, eta = model.time_series(rw, t)
        out["time_series"] = dict(t=t.tolist(), x=x.tolist(), eta_com=eta.tolist(), dof=DOF)
    # RAO curves on the computed band for plots
    om = model.hydro.omegas
    omf = np.linspace(om[0], om[-1], 120)
    X = model.rao_curve(omf, beta, damping, speed)
    out["rao_curve"] = dict(omega=omf.tolist(), period_s=(2 * np.pi / omf).tolist(), heading_deg=float(w.get("heading_deg", 90)),
                            amplitude={d: np.abs(X[:, i]).tolist() for i, d in enumerate(DOF)},
                            bodies={b["name"]: {d: np.abs(X[:, 6 * bi + i]).tolist() for i, d in enumerate(DOF)} for bi, b in enumerate(model.bodies)})
    # damping sensitivity (roll) at the requested wave
    sens = []
    for z in (0.0, 0.02, 0.05, 0.1, 0.2):
        d2 = copy.deepcopy(damping)
        d2.setdefault("zeta", {})["roll"] = z
        r2 = model.regular_wave(H, T, beta, d2, cfg["deck_acceleration_points"], speed=speed)
        sens.append(dict(zeta_roll=z, roll_amp_deg=r2["amplitude_deg"]["roll"], heave_amp_m=r2["amplitude"]["heave"],
                         deck_accel_vertical_max_amp_ms2=r2.get("deck_accel_vertical_max_amp_ms2")))
    out["roll_damping_sensitivity"] = sens
    # roll RAO vs omega for several damping ratios (beam seas) for the plot
    Xz = {}
    for z in (0.0, 0.05, 0.1, 0.2):
        d2 = copy.deepcopy(damping)
        d2.setdefault("zeta", {})["roll"] = z
        Xz[str(z)] = np.degrees(np.abs(model.rao_curve(omf, beta, d2, speed)[:, 3])).tolist()      # EXO roll
    out["roll_rao_vs_damping_deg_per_m"] = Xz
    return jsonify(_np(out))


@app.post("/api/snatch")
def post_snatch():
    """Unilateral-line time-domain check (lines can go slack and snatch); same payload as /api/wave."""
    body = request.get_json(force=True)
    cfg, res, model, err = _model_for(body)
    if err:
        return jsonify(dict(error=err, status="not_computed")), 400
    if not model.lines:
        return jsonify(dict(error="no mooring lines in this state", status="not_computed")), 400
    w = body.get("wave") or {}
    H, T, beta = float(w.get("H_m", 0.3)), float(w.get("T_s", 3.0)), np.radians(float(w.get("heading_deg", 90)))
    damping = body.get("damping") or {}
    from exo01.response import line_snatch_check
    model.regular_wave(H, T, beta, damping, cfg["deck_acceleration_points"], speed=_speed(body, res))      # linear reference for the ratios
    out = line_snatch_check(model, 2 * np.pi / T, beta, H, damping, speed=_speed(body, res))
    out["label"] = cfg["result_label"]
    return jsonify(_np(out))


@app.post("/api/irregular")
def post_irregular():
    body = request.get_json(force=True)
    cfg, res, model, err = _model_for(body)
    if err:
        return jsonify(dict(error=err, status="not_computed")), 400
    w = body.get("sea") or {}
    out = model.irregular(float(w.get("Hs_m", 0.5)), float(w.get("Tp_s", 4.0)), np.radians(float(w.get("heading_deg", 90))),
                          float(w.get("gamma", 3.3)), body.get("damping") or {}, cfg["deck_acceleration_points"])
    out["label"] = cfg["result_label"]
    return jsonify(_np(out))


@app.post("/api/timestep_check")
def post_timestep():
    body = request.get_json(force=True)
    cfg, res, model, err = _model_for(body)
    if err:
        return jsonify(dict(error=err)), 400
    w = body.get("wave") or {}
    d = body.get("damping") or {}
    if not d.get("zeta") or not d.get("absolute"):
        return jsonify(dict(error="time-domain check needs damping on every DOF (zeta heave/roll/pitch and absolute surge/sway/yaw)")), 400
    r = time_domain_check(model, 2 * np.pi / float(w.get("T_s", 3.0)), np.radians(float(w.get("heading_deg", 90))), float(w.get("H_m", 0.3)), d)
    return jsonify(_np(r))


# ------------------------------------------------------------------ comparison
@app.post("/api/compare")
def post_compare():
    body = request.get_json(force=True)
    items = body.get("scenarios") or [dict(scenario=n) for n in ("baseline_illustrative", "battery_relocated", "occupants_symmetric", "occupants_asymmetric")]
    results, waves, hydro_status = [], {}, {}
    wave = body.get("wave")
    damping = body.get("damping") or {}
    settings = body.get("hydro_settings") or {}
    for it in items:
        if "scenario" in it:
            cfg = resolve_scenario(load_scenario(it["scenario"]))
        else:
            cfg = _state_from_request(it)
        res = _evaluate_cached(cfg)
        results.append(res)
        name = res.get("scenario") or res.get("name")
        if wave and res["status"].get("equilibrium") == "solved" and res["mass"]["inertia_com_kgm2"] is not None:
            s, om, hd = _hydro_grid(settings, wave)
            try:
                hdd = _hydro(res, cfg, s, om, hd, cache_only=True)
            except HydroNotComputed:
                hydro_status[name] = "BEM not computed for this scenario/heading"
                continue
            model = build_response(res, hdd, cfg)
            waves[name] = model.regular_wave(float(wave["H_m"]), float(wave["T_s"]), np.radians(float(wave["heading_deg"])), damping,
                                             cfg["deck_acceleration_points"])
            hydro_status[name] = "computed"
    rows = compare_table(results, waves)
    return jsonify(_np(dict(rows=rows, hydro_status=hydro_status, label="Exploratory — assumed geometry and mass distribution.")))


# ------------------------------------------------------------------ export
@app.post("/api/export")
def post_export():
    body = request.get_json(force=True)
    cfg = _state_from_request(body)
    res = _evaluate_cached(cfg)
    out = dict(exported=time.strftime("%Y-%m-%d %H:%M:%S"), software=dict(exo01=__version__), label=cfg["result_label"],
               resolved_config=cfg, still_water=strip_private(copy.deepcopy(res)), assumptions_document="ASSUMPTIONS.md",
               hydro_settings=dict(DEFAULT_HYDRO, **(body.get("hydro_settings") or {})), damping=body.get("damping"),
               wave=body.get("wave"), wave_response=None, warnings=[])
    try:
        import capytaine
        out["software"]["capytaine"] = capytaine.__version__
    except Exception:  # noqa: BLE001
        pass
    out["software"]["numpy"] = np.__version__
    cfg2, res2, model, err = _model_for(body)
    if err:
        out["warnings"].append("wave response not computed: " + err)
    elif body.get("wave"):
        w = body["wave"]
        rw = model.regular_wave(float(w["H_m"]), float(w["T_s"]), np.radians(float(w["heading_deg"])), body.get("damping") or {},
                                cfg["deck_acceleration_points"], speed=_speed(body, res2))
        out["wave_response"] = rw
        out["natural_frequencies"] = model.natural_frequencies()
        out["hydro_meta"] = model.hydro.meta
        om = model.hydro.omegas
        out["hydro_coefficients"] = dict(omega=om.tolist(), headings_rad=model.hydro.headings.tolist(), headings_exact=True,
                                         added_mass=model.hydro.A.tolist(), radiation_damping=model.hydro.B.tolist(),
                                         excitation_re=model.hydro.F.real.tolist(), excitation_im=model.hydro.F.imag.tolist(),
                                         mass_matrix=model.M.tolist(), stiffness_matrix=model.K.tolist(), dof=DOF)
    name = "".join(ch for ch in (body.get("name") or cfg["scenario_name"]) if ch.isalnum() or ch in "-_")
    stamp = time.strftime("%Y%m%d-%H%M%S")
    jpath = EXPORT_DIR / f"{name}_{stamp}.json"
    jpath.write_text(json.dumps(_np(out), indent=1, default=str))
    # flat CSV
    row = compare_table([res], {res.get("scenario") or res.get("name"): out["wave_response"]} if out["wave_response"] else None)[0]
    cpath = EXPORT_DIR / f"{name}_{stamp}.csv"
    with cpath.open("w", newline="") as f:
        wri = csv.writer(f)
        wri.writerow(["label", cfg["result_label"]])
        for k, v in row.items():
            wri.writerow([k, json.dumps(v) if isinstance(v, (list, dict)) else v])
    # human-readable summary (markdown) for sharing: what was assumed, what came out, what it does not mean
    mpath = EXPORT_DIR / f"{name}_{stamp}.md"
    mpath.write_text(_summary_md(cfg, res, out))
    return jsonify(dict(json=str(jpath.relative_to(ROOT)), csv=str(cpath.relative_to(ROOT)), md=str(mpath.relative_to(ROOT)),
                        download=f"/api/download/{jpath.name}", download_md=f"/api/download/{mpath.name}"))


def _summary_md(cfg, res, out):
    e = res.get("equilibrium") or {}
    L = [f"# EXO-01 — {cfg.get('scenario_title') or cfg['title']}", "", f"**{cfg['result_label']}**  ", f"exported {out['exported']}, exo01 v{__version__}, "
         f"Capytaine {out['software'].get('capytaine', '?')}; density {cfg['environment'].get('rho_kg_m3')} kg/m³, depth {cfg['environment'].get('water_depth_m') or 'infinite'} m", ""]
    m = res.get("mass") or {}
    L += ["## Mass", f"* total {m.get('total_mass_kg', '?')} kg (listed subtotal {m.get('total_listed_mass_kg', '?')} kg); COM {np.round(m.get('com_m') or [], 3).tolist() if m.get('com_m') else 'not computed'} m (CAD frame)", ""]
    if e.get("feasible"):
        fb = e["freeboard"]
        st = res.get("stability_static") or {}
        L += ["## Still water (EXO)", f"* heel {e['heel_deg']:.2f}°, trim {e['trim_deg']:.2f}° (+ = +X end down), max draught {fb['draft_max_m']:.3f} m",
              f"* freeboards: deck-plate corners min {fb['lower_deck_freeboard_min_m']:.3f} m, float tops min {fb['float_top_freeboard_min_m']:.3f} m",
              f"* GM transverse {st.get('GM_transverse_m', float('nan')):.2f} m, longitudinal {st.get('GM_longitudinal_m', float('nan')):.2f} m (initial static stability only)", ""]
    else:
        L += ["## Still water (EXO)", f"* **no feasible equilibrium**: {e.get('reason', '')}", ""]
    bb = (res.get("bodies") or {}).get("boat")
    if bb and bb.get("equilibrium", {}).get("feasible"):
        be = bb["equilibrium"]
        L += ["## Hydronaute (second body)", f"* heel {be['heel_deg']:.2f}°, trim {be['trim_deg']:.2f}°, proxy-hull draught {be.get('draft_hull_proxy_m', float('nan')):.2f} m", ""]
    if res.get("lines"):
        ce = res.get("coupled_equilibrium") or {}
        L += ["## Mooring lines (coupled static equilibrium)", f"* {'converged' if ce.get('converged') else 'NOT converged'}" + ("; CONTACT: boat displaced into the EXO structure" if ce.get("interference") else "")]
        L += [f"* {l['id']}: {l['tension_N']:.0f} N{' (slack)' if l['slack'] else ''}" for l in res["lines"]]
        L += [""]
    pr = res.get("propulsion")
    if pr:
        L += ["## Propulsion (quasi-static)", f"* {pr['unit_title']} at {100 * pr['thrust_fraction']:.0f} %: thrust {pr['thrust_total_N']:.0f} N, steady speed {pr['speed_m_s']:.2f} m/s "
              f"({pr['speed_kn']:.1f} kn); resistance EXO {pr['resistance']['exo_N']:.0f} N, boat {pr['resistance']['boat_N']:.0f} N; line load {pr['line_load_N']:.0f} N", ""]
    rw = out.get("wave_response")
    if rw and rw.get("in_range"):
        L += ["## Regular wave", f"* H {rw['H_m']} m, T {rw['period_s']} s, heading {rw['heading_deg']:.0f}° (direction the waves travel toward)"]
        for bname, bo in rw["bodies"].items():
            L += [f"* {bname}: heave {bo['amplitude']['heave']:.3f} m, roll {bo['amplitude_deg']['roll']:.2f}°, pitch {bo['amplitude_deg']['pitch']:.2f}°"
                  + (f", deck vertical acceleration up to {bo['deck_accel_vertical_max_amp_ms2']:.2f} m/s²" if bo.get("deck_accel_vertical_max_amp_ms2") is not None else "")]
        for lvl, msg in rw.get("flags", []):
            L += [f"* [{lvl}] {msg}"]
        L += [""]
    if res.get("flags"):
        L += ["## Flags", *[f"* {f}" for f in res["flags"]], ""]
    L += ["## What this does not mean", "Exploratory model with assumed geometry and mass distribution (see ASSUMPTIONS.md): no occupancy limit, operating sea state or approval "
          "follows from these numbers. The five measurements that would change them most are listed in configs/five_missing_measurements.json.", ""]
    return "\n".join(L)


# ------------------------------------------------------------------ optimisation (battery position / line arrangement) as a job
@app.post("/api/optimise")
def post_optimise():
    body = request.get_json(force=True)
    cfg = _state_from_request(body)
    target = body.get("target", "battery")
    job = _enqueue("optimise", dict(cfg=cfg, target=target, wave=body.get("wave") or {}, damping=body.get("damping") or {},
                                    settings=dict(DEFAULT_HYDRO, **(body.get("hydro_settings") or {})), options=body.get("options") or {}),
                   target=target, message=f"queued: {target} sweep")
    return jsonify(dict(job_id=job["id"], status="queued", queue_position=_queue_position(job)))


@app.get("/api/download/<fname>")
def download(fname):
    return send_from_directory(EXPORT_DIR, fname, as_attachment=True)


# ------------------------------------------------------------------ coupling arrangements
# One source of geometry (exo01/arrangements.py) for the studies, the explorer and this server.
@app.get("/api/arrangements")
def get_arrangements():
    """The catalogue, with each arrangement's published verdict and whether it needs fittings on the host boat."""
    return jsonify(_np(dict(arrangements=AR.catalogue(), default=AR.DEFAULT, snug_preload_N=AR.T_SNUG,
                            stiffness_note=AR.STIFFNESS_NOTE)))


@app.post("/api/arrangement")
def post_arrangement():
    """Solve one arrangement under an optional surge / sway / yaw demand.

    Body: {base, overrides, arrangement, preload_N, snug_N, surge_N, sway_N, yaw_Nm}
    Returns the element geometry in the EXO frame plus the tension in each element, for drawing in the viewer.
    """
    body = request.get_json(force=True)
    aid = body.get("arrangement") or AR.DEFAULT
    if aid not in AR.ARRANGEMENTS:
        return jsonify(error=f"unknown arrangement {aid!r}", available=sorted(AR.ARRANGEMENTS)), 400
    preload = body.get("preload_N")
    snug = float(body.get("snug_N") or AR.T_SNUG)
    els = AR.build(aid, preload, snug)

    cfg = _state_from_request(body)
    hb = dict(cfg.get("host_boat") or {})
    hb["lines"] = els
    hb["placement_in_exo_frame"] = dict(hb.get("placement_in_exo_frame") or {}, x_m=AR.X_BERTH)
    cfg = resolve(cfg, {"host_boat": hb})

    surge = float(body.get("surge_N") or 0.0)
    sway = float(body.get("sway_N") or 0.0)
    yaw = float(body.get("yaw_Nm") or 0.0)

    if surge or sway or yaw:
        from exo01.twobody import coupled_equilibrium

        def external(pe, pb):
            # globally balanced: whatever is applied to one body is reacted on the other, with the moment
            # transported between the two centres of mass. An unbalanced wrench makes a divergent solve look
            # converged (COUPLING.md, the external-wrench fix).
            Fb = np.array([-surge, -sway, 0.0])
            Mb = np.array([0.0, 0.0, -yaw])
            Fe = -Fb
            Me = -Mb - np.cross(np.asarray(pb["com_world"]) - np.asarray(pe["com_world"]), Fb)
            return Fe, Me, Fb, Mb

        base = _evaluate_cached(cfg)
        rho = float((cfg.get("environment") or {}).get("water_density_kg_m3") or 1000.0)
        bmass = (base.get("bodies") or {}).get("boat", {}).get("mass") or {}
        eq, beq, pe, pb, lines, info, q = coupled_equilibrium(
            cfg, base["_assembly"], base["mass"]["total_mass_kg"], base["mass"]["com_m"],
            base["_boat_assembly"], bmass["total_mass_kg"], bmass["com_m"], rho, G_STD, external=external)
        tensions = {l["id"]: float(l["tension_N"]) for l in lines}
        state = dict(converged=bool(info.get("converged")), dx_mm=1000 * float(q[3]), dy_mm=1000 * float(q[4]),
                     dyaw_deg=float(np.degrees(q[5])), residual_relative=info.get("residual_relative"))
    else:
        res = _evaluate_cached(cfg)
        ce = res.get("coupled_equilibrium") or {}
        tensions = {l["id"]: float(l["tension_N"]) for l in (res.get("lines") or [])}
        sh = ce.get("boat_shift_from_nominal") or {}
        state = dict(converged=bool(ce.get("converged")),
                     dx_mm=(sh.get("dx_m") * 1000.0) if sh.get("dx_m") is not None else None,
                     dy_mm=(sh.get("dy_m") * 1000.0) if sh.get("dy_m") is not None else None,
                     dyaw_deg=sh.get("dyaw_deg"), residual_relative=ce.get("residual_relative"))

    geom = AR.element_geometry(aid, preload, snug)
    for g in geom:
        g["tension_N"] = tensions.get(g["id"])
    meta = {k: v for k, v in AR.ARRANGEMENTS[aid].items() if k != "build"}
    # config_lines is the element list exactly as host_boat.lines wants it, so the viewer can drop an arrangement
    # straight into the configuration and let the existing solve, 3D rendering and export paths handle it.
    return jsonify(_np(dict(arrangement=aid, meta=meta, elements=geom, state=state, config_lines=els,
                            demand=dict(surge_N=surge, sway_N=sway, yaw_Nm=yaw),
                            berth_x_m=AR.X_BERTH, z_datum_offset_m=AR.Z_DATUM_OFFSET)))


# ------------------------------------------------------------------ speed, wind and energy
_POSE_GATE_DEG = 5.0


def _attitude(beq):
    R = np.asarray(beq["R"], float)
    return (float(np.degrees(np.arctan2(R[2, 1], R[2, 2]))),
            float(np.degrees(np.arcsin(-np.clip(R[2, 0], -1.0, 1.0)))))


@app.post("/api/performance")
def post_performance():
    """Speed, wind and energy at the current configuration.

    Body adds: {thrust_fraction, thrust_model, disk_diameter_m, wind_kn, wind_from_deg, current_m_s,
                panel_tilt_deg, sun_fraction}

    POSE GATE: resistance is evaluated at the thrust-off pose. The coupled solve WITH thrust applied converges to a
    capsized branch for some arrangements - 88.6 deg of heel, reported as physical - and resistance there understates
    the boat's wetted area by 44 % (docs/PERFORMANCE.md section 1).
    """
    from exo01.propulsion import boat_geometry, exo_geometry

    body = request.get_json(force=True)
    cfg = _state_from_request(body)
    cfg = resolve(cfg, {"propulsion": {"thrust_fraction": 0.0}})
    res = _evaluate_cached(cfg)
    if not has_boat(res):
        return jsonify(error="performance needs a host boat in the configuration"), 400

    heel, trim = _attitude(res["_boat_eq"])
    if abs(heel) > _POSE_GATE_DEG:
        return jsonify(error="pose gate", detail=f"boat heel {heel:.1f} deg at the reference pose; refusing to "
                                                 f"evaluate resistance there", heel_deg=heel, trim_deg=trim), 409

    exo_rows = exo_geometry(res["_assembly"], res["_eq"])
    boat_geo = boat_geometry(res["_boat_assembly"], res["_boat_eq"])
    res_cfg = cfg["propulsion"]["resistance"]

    tilt = float(body.get("panel_tilt_deg") or 0.0)
    acfg = dict(cfg.get("aero") or {})
    acfg["exo_structure"] = dict(acfg.get("exo_structure") or {}, panel_tilt_deg=tilt)
    cfg_a = dict(cfg, aero=acfg)
    ft = res["_assembly"].world_tris(res["_eq"]["R"], res["_eq"]["G_body"], res["_eq"]["zG"])
    ht = res["_boat_assembly"].world_tris(res["_boat_eq"]["R"], res["_boat_eq"]["G_body"], res["_boat_eq"]["zG"])
    areas = aero.body_areas(cfg_a, float_tris_world=ft, hull_tris_world=ht)
    coeffs, rho_air = areas["_coefficients"], areas["_rho_air_kg_m3"]

    en = cfg.get("energy") or {}
    prop = en.get("propulsion") or {}
    T0_full = float(prop.get("total_bollard_N") or 1216.0)
    P_elec = float(prop.get("total_electrical_kw") or 10.0) * 1000.0
    frac = float(body.get("thrust_fraction", 1.0))
    model = body.get("thrust_model") or "momentum"
    D = float(body.get("disk_diameter_m") or 0.25)
    A_disk = 2 * np.pi * (D / 2) ** 2

    d = np.asarray(res["_eq"]["R"], float) @ np.asarray(
        cfg["propulsion"]["units"]["EXO_PODS"]["direction_body"], float)
    h_factor = float(np.hypot(d[0], d[1]))
    T0 = T0_full * h_factor * frac

    V = float(body.get("wind_kn") or 0.0) * perf.KNOT
    ang = float(body.get("wind_from_deg") or 0.0)
    cur = float(body.get("current_m_s") or 0.0)
    base = dict(T0=T0, A_disk=A_disk, P_water=None, exo_rows=exo_rows, boat_geo=boat_geo, res_cfg=res_cfg)

    U = perf.max_speed(model=model, V_true=V, wind_from_deg=ang, areas=areas, coeffs=coeffs,
                       rho_air=rho_air, current_m_s=cur, **base)
    bat = en.get("battery") or {}
    sol = en.get("solar") or {}
    solar_full = min(float(sol.get("array_kwp") or 0.0) * 1000.0 * float(sol.get("derate_to_dc_fraction") or 0.8),
                     float(sol.get("mppt_max_charge_w") or 1e9))
    solar = solar_full * float(body.get("sun_fraction", 1.0))
    hotel = float(en.get("hotel_load_w") or 150.0)

    end = None if U is None else perf.endurance(
        U, model=model, P_electrical_max=P_elec, battery_kwh=float(bat.get("total_kwh") or 0.0),
        usable_fraction=float(bat.get("usable_fraction") or 0.8), hotel_w=hotel, solar_w=solar,
        V_true=V, wind_from_deg=ang, areas=areas, coeffs=coeffs, rho_air=rho_air, current_m_s=cur, **base)
    sn = perf.solar_neutral_speed(model=model, P_electrical_max=P_elec, solar_w=solar, hotel_w=hotel,
                                  current_m_s=cur, **base)
    wind = perf.wind_resistance(U or 0.0, V, ang, areas, coeffs, rho_air) if V else None
    hyd = perf.hydro_resistance(max((U or 0.0) - cur, 0.0), exo_rows, boat_geo, res_cfg)

    models = {m: perf.max_speed(model=m, V_true=V, wind_from_deg=ang, areas=areas, coeffs=coeffs,
                                rho_air=rho_air, current_m_s=cur, **base)
              for m in ("constant", "constant_power", "momentum")}

    return jsonify(_np(dict(
        pose=dict(heel_deg=heel, trim_deg=trim, gate_deg=_POSE_GATE_DEG),
        thrust=dict(bollard_N=T0_full, horizontal_factor=h_factor, setting_fraction=frac, applied_N=T0,
                    model=model, disk_diameter_m=D,
                    implied=perf.implied_efficiency(T0_full * h_factor, A_disk, P_elec)),
        speed=dict(U_m_s=U, U_kn=None if U is None else U / perf.KNOT, by_model=models,
                   current_m_s=cur, U_through_water_m_s=None if U is None else U - cur),
        resistance=hyd, wind=wind,
        windage={b: {k: v for k, v in areas[b].items()
                     if k in ("A_front_m2", "A_lateral_m2", "z_lateral_m", "L_m")} for b in ("EXO", "BOAT")},
        energy=dict(endurance=end, solar_neutral_m_s=sn, solar_w=solar, solar_full_w=solar_full, hotel_w=hotel,
                    battery_kwh=bat.get("total_kwh"), usable_fraction=bat.get("usable_fraction")),
        caveats=[
            "Wind coefficients and the two structural solidity ratios are ASSUMED; they dominate every wind figure.",
            "The pod disk diameter is not recorded; it is worth about 0.2 m/s across its plausible range.",
            "Resistance is evaluated at the thrust-off pose (see the pose gate).",
            "Sinkage and trim at speed, wave-added resistance and gusts are not modelled.",
        ])))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8050)
    ap.add_argument("--host", default="127.0.0.1")
    a = ap.parse_args()
    from exo01.hydro import POSE_INDEX
    try:
        n_cache = len(json.loads(POSE_INDEX.read_text())) if POSE_INDEX.exists() else 0
    except (OSError, ValueError):
        n_cache = 0
    print(f"EXO-01 exploratory simulation v{__version__}  ->  http://{a.host}:{a.port}   (BEM cache: {n_cache} poses; long jobs run in a worker process; Ctrl+C to stop)")
    try:
        app.run(host=a.host, port=a.port, debug=False, threaded=True)
    except OSError as e:
        print(f"\nCannot listen on {a.host}:{a.port} ({e}).\nAnother server (an earlier app.py?) is probably using the port: close it, or start this one "
              f"with  python app.py --port {a.port + 1}")
        raise SystemExit(1)
