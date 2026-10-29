"""Long computations (BEM, design sweeps) run in a separate PROCESS so the HTTP server stays responsive.

The worker only writes the BEM cache and small JSON files (progress, result); the server re-reads the cache
(cache_only=True) when the job is done. Windows-safe: a top-level entry point, spawn start method, no server state
crosses the boundary, and the process can be terminated (cancel) at any time without corrupting the cache (npz files
are written atomically by numpy at the end of each solve; the pose index is written through a temp file).
"""
from __future__ import annotations

import json
import time
import traceback
import warnings


def _write(path, obj):
    if not path:
        return
    tmp = str(path) + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, default=str)
    import os
    os.replace(tmp, path)


def hydro_job(cfg, settings, omegas, headings, progress_path=None):
    """Compute (or complete) the BEM for the configuration; returns the HydroData meta."""
    import numpy as np
    from .analysis import evaluate, hydro_for, has_boat
    from . import hydro as H
    t0 = time.time()
    res = evaluate(cfg)
    if res["status"].get("equilibrium") != "solved":
        return dict(status="error", error="no solved still-water equilibrium: " + json.dumps(res.get("not_computed") or res.get("equilibrium"), default=str))
    if res["mass"]["inertia_com_kgm2"] is None:
        return dict(status="error", error="inertia tensor not available (missing inertia models)")
    om = np.asarray(omegas, float)
    hd = np.asarray(headings, float)
    # progress units: one per radiation omega (+ ~25 % for in-band refinement) + 0.35 per omega per heading
    units = len(om) * 1.25 + 0.35 * len(om) * len(hd)

    def cb(frac, msg, eta):
        _write(progress_path, dict(progress=frac, message=msg, eta_s=eta, elapsed_s=time.time() - t0))
    H.set_progress(cb, units)
    hdd = hydro_for(res, cfg, om, hd, settings)
    H.set_progress(None)
    _write(progress_path, dict(progress=1.0, message=f"done ({hdd.meta.get('cache', '?')})", eta_s=0.0, elapsed_s=time.time() - t0))
    return dict(status="done", meta=hdd.meta, seconds=time.time() - t0, two_body=has_boat(res))


def optimise_job(cfg, target, wave, damping, settings, options, progress_path=None):
    from .optimise import run_optimisation
    t0 = time.time()

    def progress(frac, msg):
        _write(progress_path, dict(progress=frac, message=msg, elapsed_s=time.time() - t0,
                                   eta_s=((time.time() - t0) * (1 - frac) / frac if frac > 0.02 else None)))
    out = run_optimisation(cfg, target, wave, damping, settings, progress=progress, options=options)
    return dict(status="done", result=out, seconds=time.time() - t0)


def run_job(kind, payload, result_path, progress_path):
    """Process entry point: run one job and write its result JSON (status done/error) to result_path."""
    warnings.simplefilter("ignore")
    try:
        if kind == "hydro":
            out = hydro_job(payload["cfg"], payload["settings"], payload["omegas"], payload["headings"], progress_path)
        elif kind == "optimise":
            out = optimise_job(payload["cfg"], payload["target"], payload["wave"], payload["damping"], payload["settings"],
                               payload["options"], progress_path)
        else:
            out = dict(status="error", error=f"unknown job kind {kind}")
    except Exception as e:  # noqa: BLE001
        out = dict(status="error", error=f"{type(e).__name__}: {e}", trace=traceback.format_exc()[-3000:])
    _write(result_path, out)
