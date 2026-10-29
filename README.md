# EXO-01 — exploratory flotation, static stability and linear wave response

Python calculation backend (`exo01/`, no rendering) + Flask API (`app.py`) + browser 3D interface (`web/`, three.js,
vendored). Built from the EXO-01 revision-3 reference package (`data/reference_v3/`) and the Renaud 8000 reference
package v1 (`data/renaud8000_v1/`, the Hydronaute as a second floating body moored with line springs). Read
**AUDIT.md** (what was found in the packages) and **ASSUMPTIONS.md** (conventions, assumptions, limits, validation
plan) before using any number.

Every result on the illustrative configuration is labelled **"Exploratory — assumed geometry and mass distribution."**
The baseline configuration keeps all unknowns `null` and reports *not computed* instead of guessing.

## Launch

**Windows**: double-click `start_windows.bat` — it uses an environment that already has the dependencies
(`%USERPROFILE%\.venv` or a local `.venv`), otherwise creates `.venv` and installs them (first run only), then starts the
server and opens the browser at http://127.0.0.1:8050 (close the window to stop). **macOS / Linux**: `./start_unix.sh`.

**Updates**: the project is a git repository (`Biutopic/exo01-sim`). Clone it once (`git clone https://github.com/Biutopic/exo01-sim.git`
or GitHub Desktop), then double-click `update_windows.bat` (`git pull`) to get a new version — the Python environment and the
BEM cache are kept, nothing is reinstalled. `results/cache` (precomputed BEM), `results/comparison`, `results/optimisation` and
`results/verification` are committed; `results/exports`, `results/jobs` and `results/ui` are local outputs.

By hand:

```bash
python -m venv .venv && source .venv/bin/activate          # Linux/macOS   (Windows cmd: python -m venv .venv && .venv\Scripts\activate)
pip install -r requirements.txt                              # Python 3.11-3.13; Capytaine 3.0.0 pinned (API differs from 2.x)
python app.py                                                # -> http://127.0.0.1:8050   (python app.py --port 8051 if the port is taken)
```

The header shows the pipeline state (① still water, ② BEM, ③ waves) and a progress strip for whatever is running
(still-water solve, wave update, BEM or sweep job with percentage, elapsed time and time left); long jobs run in a
separate process, so the interface stays live while a BEM computes, and they can be cancelled from the job panel in
the 3D view.

`requirements-lock-py313.txt` holds the exact versions used for the verification run; `requirements-dev.txt` adds
Playwright for the headless UI test.

Workflow in the interface: **1 · Still water** (automatic on every edit; coupled EXO + boat equilibrium with
tension-only lines, and with the motor's thrust/drag when a setting is on) → **2 · Compute BEM** (Capytaine radiation,
cached per **pose** — moving a mass that leaves the pose unchanged is an exact hit, a nearby pose is reused and
flagged; the package ships the cache for the built-in scenarios at headings 0/45/90/135/180°, so the default scenes
animate at once. Timing on 2 cores when a new pose is needed: EXO alone ≈ 3 min at the default 3 m depth (≈ 1 min
with blank = infinite depth), EXO + boat ≈ 10–25 min; a new heading ≈ 1/4 of that) →
**3 · Wave response** (RAO tables/plots, deck accelerations, damping sensitivity, animated linear motion of both
bodies, line tensions and relative-motion clearances; refreshed automatically after every still-water solve when a
usable BEM exists) → **Motor** (Off / 20 / 50 / 100 %: quasi-static thrust, speed, resistance split, line loads,
encounter frequency) → **Lines** (edit attachment points in the table or by dragging the yellow end spheres; presets)
→ **Optimise** (battery positions, line arrangements: full tables with scores) → **Compare scenarios** →
**Export results**. Batteries and electronics can be
dragged in 3D (click a battery, drag the gizmo) or edited numerically; people are added with mass, surface, posture,
position. People can be dragged on the EXO decks and on the boat; a first-order preview follows the drag and the exact solve
runs on release (~0.2 s). The boat (mass, COM, berth x/y/yaw, line pretension and stiffness) is edited in its own
section; untick *include boat* for the EXO-only case. Scenarios are saved to `scenarios/*.json`; exports go to
`results/exports/` (JSON with the resolved configuration, assumptions label, solver settings and all coefficients,
plus a flat CSV).

Command line:

```bash
python -m pytest tests -q                 # 84 unit/integration tests (~1.5 min; small BEM grids)
python scripts/run_verification.py        # numerical verification with actual errors -> results/verification/verification_report.json
python scripts/run_comparison.py --bem    # built-in scenario comparison -> results/comparison/ (csv, md, png)
python scripts/make_configs.py            # regenerate configs/ and scenarios/ from the reference package
python scripts/ui_v1_check.py             # headless-Chromium end-to-end check of the running interface (needs playwright)
python scripts/precompute_cache.py        # (re)build the shipped BEM cache for the built-in scenarios (~40 min)
python scripts/run_optimisation_report.py # battery / line sweeps -> results/optimisation/
```

## Layout

```
exo01/reference.py    GLB/STEP/JSON reader; single CAD<->glTF conversion; mass register audit
exo01/mass.py         items, COM, inertia tensor (parallel axis), people, inertia models
exo01/buoyancy.py     closed float surfaces (capsule proxies / measured meshes), exact clipped integrals
exo01/equilibrium.py  draft/heel/trim solve, residuals, freeboards, restoring matrix, GM
exo01/hydro.py        Capytaine 3.0 wrapper: immersed mesh at the solved pose, A(w), B(w), F(w,beta), gap-band refinement, cache
exo01/response.py     6-DOF frequency-domain response, viscous damping, natural frequencies, flags, irregular sea, RK4 check
exo01/analysis.py     evaluate(config) -> still-water results (EXO + boat); build_response(); hydro_for()
exo01/boat.py         Renaud 8000 hull envelope proxy (ruled loft from the package station table)
exo01/twobody.py      boat equilibrium, common-world poses, mooring-line geometry, berth clearances
exo01/config.py, scenarios.py   configs, overrides, validation, comparison table
configs/baseline.json           user-reported values only, unknowns null
configs/illustrative.json       assumed geometry and mass distribution (labelled)
configs/five_missing_measurements.json
scenarios/*.json                baseline_illustrative, battery_relocated, battery_float_frame, occupants_symmetric, occupants_asymmetric (EXO-only), with_hydronaute
tests/                          pytest suite
scripts/                        verification, comparison, config generation, UI smoke test
results/                        verification report, comparison tables/plots, exports, BEM cache, UI screenshots
web/                            index.html, app.js, app.css, vendor/three (r169, MIT)
```

## What was actually run here

* `pytest`: 84 passed (see `results/verification/pytest.xml`) — physics, two-body, propulsion, jobs and HTTP API.
* `scripts/run_verification.py`: `results/verification/verification_report.md|json` — units/transforms, mass accounting,
  analytic buoyancy (capsule and Flofiz), equilibrium residuals (~1e-13 relative), symmetric case, stiffness vs analytic
  formulas and vs Capytaine, BEM panel/frequency/heading convergence, RK4 time-step convergence, two-body symmetry and
  panel convergence, coupled-equilibrium force balance, propulsion force balance, BEM reference-point transform.
* `scripts/run_comparison.py --bem`: `results/comparison/` (6 scenarios, fresh water, 3 m depth).
* `scripts/run_optimisation_report.py`: `results/optimisation/` (battery positions EXO-only and with the boat; line
  arrangements under push, tow and the reference wave).
* Interface: `scripts/ui_v1_check.py` in headless Chromium (software WebGL) — boot, progress strip, no-equilibrium
  display, live head-sea motion of both bodies from the shipped cache, motor, line presets, optimisation job;
  screenshots in `results/ui/`. No real-GPU browser was available in the build environment.

## Replacing the float proxies with measured geometry

Provide a closed triangulated surface per float (outward normals, CAD metres) and build
`exo01.buoyancy.MeshSurface(id, vertices, faces)` in place of `CapsuleX` in `surfaces_from_config` (a `mesh_file`
type is reserved in the config schema). The equilibrium, stiffness and BEM code need no change; re-run
`scripts/run_verification.py` to re-check mesh convergence with the new tessellation.

## Unreal (later)

The API is the contract: `POST /api/evaluate` returns the pose (`R`, `G_body`, `zG`), `POST /api/wave` returns the
complex 6-DOF amplitudes `X_complex` and the wave parameters; an Unreal client only needs to reproduce
`x(t) = Re(X e^{-i w t})` and `eta(x,y,t) = A cos(k(x cos b + y sin b) - w t)` as `web/app.js` does.
