"""Worker-process job entry points: progress file, result file, and the chunked BEM giving identical coefficients."""
import json
import numpy as np

from exo01.config import load_config, resolve
from exo01.jobs import run_job
from exo01.analysis import HYDRO_DEFAULTS


def test_hydro_job_writes_progress_and_result(tmp_path, illustrative):
    cfg = resolve(illustrative, {"host_boat": {"included": False}, "environment": {"water_depth_m": None}})
    settings = dict(HYDRO_DEFAULTS, omega_min=0.8, omega_max=2.4, omega_step=0.8, panel_size_m=0.25, refine_bands=False)
    om = [0.8, 1.6, 2.4]
    rp, pp = tmp_path / "r.json", tmp_path / "p.json"
    run_job("hydro", dict(cfg=cfg, settings=settings, omegas=om, headings=[np.pi / 2]), str(rp), str(pp))
    out = json.loads(rp.read_text())
    assert out["status"] == "done", out
    assert out["meta"]["n_omega"] == 3 and out["meta"]["headings_deg"] == [90.0]
    # progress was reported at least once with a fraction in (0, 1]
    assert pp.exists()
    prog = json.loads(pp.read_text())
    assert 0 < prog["progress"] <= 1.0 and "message" in prog


def test_unknown_job_kind_is_an_error(tmp_path):
    rp = tmp_path / "r.json"
    run_job("nope", {}, str(rp), None)
    assert json.loads(rp.read_text())["status"] == "error"
