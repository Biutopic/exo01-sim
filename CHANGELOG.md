# Changelog

## v1.2.1 (30 Oct 2026)

* Methodology package for the website: `scripts/draw_methodology.py` -> five figures x FR/EN (calculation chain,
  claim discipline, mooring element laws, model boundary, verification evidence), `docs/website/methodologie.fr.md`,
  `methodology.en.md`, `methodology_figures.json`, `METHODOLOGY_PACKAGE.md`. Every number in the verification figure is
  read from `results/verification/verification_report.json` at run time.
* Two code maps of the project itself: `docs/codemap/` (static, technical) and `docs/floorplan-source/` (plain-language,
  rebuildable with the Floorplan plugin).

* `scripts/run_mooring_final.py`: final comparison of 12 arrangements (ropes + knees, four tubes rigid / with
  cartridges, two-tube hybrids) at the converged settings → `results/mooring/final_comparison.{md,json}`, read in
  `docs/MOORING.md` §7. Sketches `results/mooring/sketch_six_lines*.png`, `sketch_hybrid_tubes_ropes.png`.

## v1.2 (29 Oct 2026)

Mooring elements and the mooring study
* Elements between the EXO and the boat now have a kind: line (tension only), fender (compression only: push bar / stern
  fender) and strut (bilateral, rigid link in the stiff limit) — in the coupled static solver (active set, signed fender
  penetration), the linear wave model and the time-domain snatch check. Presets `fenders_tow_lines`,
  `fenders_crossed_lines`, `fenders_diagonals`, `rigid_struts`; the line editor has a kind selector; fenders are drawn
  cyan, struts grey. The transom-to-deck-edge gap is tracked as a relative-motion point in waves.
* `scripts/run_mooring_study.py`: arrangement × stiffness × pretension study (static moored/push/tow + three waves, linear
  and time domain) → `results/mooring/` and the reading in `docs/MOORING.md`.
* `scripts/run_stability_sheet.py`: EXO-01 alone flotation/stability sheet (light ship, passenger load cases with the
  ES-TRIN art. 19.03 values 75 kg/person, heel ≤ 12°, residual freeboard ≥ 0.20 m, crowding, deck-edge-awash wave height)
  → `results/stability/`, as input for a registration file — not a certificate.
* Battery sweep: the end-frame position (x 4.24 m) added to the discussion (docs/MOORING.md §batteries).

## v1.1 (29 Oct 2026)

Battery position — second zone (user proposal: both batteries further forward)
* The battery sweep (`exo01/optimise.py`, interface "Optimise → battery") now also covers the float-top side frames
  forward of the rear deck (x 2.1–4.9 m, |y| 2.05 m, clear of the mid and end uprights); each candidate carries its
  zone, the table shows it, and the result reports per zone the position of least trim plus the interpolated zero-trim
  position. Options: `zones: "rear_deck" | "float_frame" | "all"` (default all).
* Result for the illustrative configuration with the boat moored, no occupants: rear deck at best −3.30° (x 1.70 m);
  float frames 0° at x ≈ 3.54 m, +0.15° at x 3.62 m with 0.36 m rear-deck freeboard (vs 0.17 m at the figure's
  position). With two 80 kg people at the rear table the trim is −6.9° at the figure's position (deck edge awash) and
  −2.2° with the batteries at x 3.70 m; four people on the rear deck have no static equilibrium at the figure's
  position and −4.3° / 0.09 m freeboard at x 3.70 m. The batteries forward are necessary, not sufficient.
* New scenario `battery_float_frame` (x 3.60 m, EXO-only) in the comparison grid and the shipped BEM cache.
* Nothing checks whether the float cradle frame carries 120 kg per battery: structural question, outside the model.

## v1.0 (29 Oct 2026)

Interface
* Global progress strip under the header: still-water solve, wave update, 3D model loading, and the background jobs
  with percentage, elapsed time, estimated time left, queue length and the current solver step; the wave response is
  fetched automatically when a BEM job finishes.
* No static equilibrium (e.g. 800 kg on one deck corner): the solver's best balance point is shown in 3D with the
  water and a red "NO STATIC EQUILIBRIUM" label (which floats are fully submerged, how much weight is unbalanced),
  instead of the model falling back to the CAD datum.
* Coupled equilibria that exist only with the boat displaced into the EXO structure (no contact model) are flagged
  as CONTACT in the pipeline chip and counted as "cannot" in the line sweep.
* Background jobs (BEM, design sweeps) run in a separate worker process: the interface never blocks while a BEM runs;
  a progress panel in the 3D view shows the queue, the percentage, the elapsed time and the estimated time left, with a
  cancel button; the radiation/diffraction solves are chunked so the progress is real, not cosmetic.
* Header pipeline chips: ① still water (solved / coupled ok / failed / invalid input), ② BEM (exact pose / nearby
  pose / APPROXIMATE / needs compute), ③ waves (live, period, heading, moving).
* Live wave motion after every still-water solve when a usable BEM exists; two reuse tiers: "nearby pose" (within
  0.05 rad / 0.05 m) and "APPROXIMATE PREVIEW" (within 0.17 rad / 0.30 m), both labelled with the pose difference.
* Collapsible input sections, sticky action bar, busy strip during a solve, boot retry when the server is slow,
  boots directly into the `with_hydronaute` scenario.
* Mooring-line editor (table + draggable end spheres, presets), motor control (off / 20 / 50 / 100 %, pods or boat
  engine), optimisation panel (battery positions, line arrangements) with ranked tables and "apply best".

Physics / numerics
* Flofiz floats (1.60 × Ø 0.60 m, sled nose), layout from the user's figure (batteries upright at the side rails,
  cabinet port side, two POD 5.0 rim drives aft of the float rows).
* Quasi-static propulsion/tow: thrust setting → steady speed from explicit resistance models → thrust and drag
  wrenches in the (coupled) equilibrium → trim, heel, line tensions and slack; encounter frequency in the wave model.
* BEM computed about each body's CAD origin and moved to the COM by the exact reference-point transform: the cache
  is keyed on the pose, not on the mass distribution (moving a battery is an exact hit); pose index for reuse.
* Coupled equilibrium with tension-only lines solved by an active-set outer loop (smooth Newton solves, no kink
  chatter): the stiff-line / yawed-berth case that stalled at 1e-3 now converges to 1e-11; bad warm starts are
  compared with the cold start and rejected; a bounded trust-region least-squares pass finishes the rare stalls
  (boat shift limited to 1 m / 0.3 rad so the numerical centering spring cannot fake a balance).
* HTTP API covered by tests (JSON errors with 400 for bad input, best balance point, cached wave response, jobs).
* Line snatch check: 12-DOF time-domain integration with tension-only lines (peak tension, slack fraction, snatch
  ratio per line), in the Waves tab and in the line-arrangement sweep; reduces to the linear model for small waves.
* Boat lid for irregular-frequency removal clamped to half the draught (was silently empty for ω_max ≥ 5 rad/s).
* Numeric inputs validated (NaN, negative masses, density/depth ranges, line points); every unexpected server error
  returns a JSON message instead of a blank 500.
* Cache keys normalised (int vs float inputs from the interface gave different keys).

Results shipped
* BEM cache for the built-in scenarios at headings 0/45/90/135/180° (EXO alone and EXO + boat), verification report,
  6-scenario comparison, battery and line sweeps (`results/optimisation/`).

## v0.3 (28 Oct 2026)
* Review fixes (COB, per-corner deck wetting, measured-mesh import, API guards), open berth, coupled static
  equilibrium with unilateral lines, fresh water and 3 m depth.

## v0.2 / v0.1 (28 Oct 2026)
* Two-body wave response with the Hydronaute, interactive 3D, first release.
