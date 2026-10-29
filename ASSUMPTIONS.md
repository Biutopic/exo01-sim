# Assumptions, conventions and limits — EXO-01 exploratory model

Status: **exploratory engineering tool, numerically verified, not validated against any measurement.**
Every number produced on the illustrative configuration carries the label
*"Exploratory — assumed geometry and mass distribution."* Nothing here is a safe occupancy limit, a certified operating
sea state or a construction approval.

## 1. Provenance classes

| Class | Meaning | Where |
|---|---|---|
| `user_reported` | mass list of 28 Oct 2026 (840 kg subtotal, 16 groups), six floats confirmed | `configs/*.json → components[].mass_source` |
| `drawing_dimension` | labels transcribed from La Mutine sheet 1/3 (raster) | `drawing_dimensions` |
| `modelling_assumption` | needed to run a calculation; **not measured** | illustrative config, `com_note`, `inertia.source`, float capsules |
| `illustrative` | demonstration values (80 kg people, positions) | `people[]`, scenarios |
| `missing_input` | unknown; `null` in the baseline | `missing_inputs`, `pending_loads` |

The baseline never substitutes an assumption for a null; the corresponding outputs are reported as *not computed* with
the list of missing items.

## 2. Units and coordinates

* SI internally (m, kg, s, N, rad). STEP is mm (read from its header), GLB is m. Angles are shown in degrees.
* Body frame = CAD frame of the package: X from the open rear deck edge toward the framed/panel end, Y transverse
  (+Y = the `FLOAT_POS_Y_*` side), Z up from the deck datum (top of the rear deck plate = float top tangent).
  Port/starboard and bow/stern are **not** asserted; "front" = +X per the package.
* The GLB root carries the single −90° X rotation to glTF Y-up. The viewer strips it from the node and applies the
  same conversion once through a parent group (checked at load; console message). The Python side never converts.
* World frame: Z up, still waterline at Z = 0, origin at the horizontal position of the assembly COM.
  Pose: `w = R(φ, θ) (p − G) + (0, 0, zG)`, `R = Ry(θ)·Rx(φ)`. Heel φ right-handed about +X (+Y side goes **up** for
  φ > 0); trim θ right-handed about +Y (the +X end goes **down** for θ > 0).
* Wave heading β = direction the waves travel **toward**, counter-clockwise from +X (β = 0: along +X toward the panel
  end; β = 90°: beam seas toward +Y). Wave height H is crest-to-trough; amplitude A = H/2. Time convention exp(−iωt);
  the unit-amplitude wave is η = exp(ik(x cos β + y sin β)) at the COM, i.e. a crest at the COM at t = 0.
  Phase lags in the tables are relative to that crest.

## 3. Mass model

* Each mass-bearing parent counted exactly once; child meshes never carry mass (checked against the GLB).
* Assembly COM = Σ mᵢ rᵢ / Σ mᵢ; inertia about the COM = Σ [Iᵢ(own) + mᵢ(|d|²1 − d dᵀ)] (parallel axis), components
  axis-aligned.
* Illustrative inertia models (all visible in the config, `inertia.model`):
  structure sections = thin-walled box shell of the bay envelope (2.1×4.547×0.76 m rear; 1.425×4.547×2.7 m bays);
  floats = thin cylindrical shell along X; panels/batteries/electronics = solid boxes of the proxy sizes; people =
  point masses. These are **not** measured distributions.
* Illustrative COMs: structure at the centre of its envelope (rear at Z 0.38 m, bays at Z 1.35 m); floats at the
  centre of the float body (Z −0.30 m); panels at the package preview anchors. **Layout stated by the user (28/10,
  anatomy figure)**: the two Dyness PowerBrick Plus batteries stand upright, one strapped to each side rail of the rear
  deck (footprint x 1.15–1.70 m, |y| 1.90–2.20 m, 1.0 m tall — drawn size), COM assumed at mid-height (1.425, ±2.05,
  0.50); the electrical cabinet on the port side against the frame (x 1.50–1.96, y 0.62–1.54 m, 1.0 m tall), COM
  (1.73, 1.08, 0.50); the two POD 5.0 rim drives aft of each float row at (0.34, ±1.97, −0.44) with an ASSUMED 8 kg
  each (5 kg motor + bracket/cable) — **not in the 840 kg register** (`register: false`, null in the baseline), so the
  illustrative total is 856 kg. Masses of the batteries (120 kg each) and cabinet (50 kg) remain the register's values.
* People: editable mass, surface (`lower_deck` Z = 0, `observation_deck` Z = 2.2), posture (standing 1.00 m,
  seated on chair 0.70 m, seated on deck 0.40 m body-COM height above the surface, editable), x/y position validated
  to lie inside the chosen surface. 80 kg is an illustrative mass.
* The 840 kg is a listed subtotal. Unlisted: host boat, deck-surface mass if separate, propulsion, cabling, fluids,
  payload. The rigid-connection assumption: frame + six floats = one rigid body.

## 4. Buoyancy and still-water equilibrium

* Buoyant surfaces: **only** the six floats, modelled since v0.4 as **Flofiz** pontoon floats (`buoyancy.FlofizX`,
  from the EXO-01 component list of 2026-09-12 via the user's figure of 28/10: 1.60 m × Ø 0.60 m, body 1.30 m flat at
  one end, 0.30 m sled nose whose top stays level and whose underside curves up to the tip; rear float nose aft, middle
  and end floats nose forward). Rows at y = ±1.970 m (GLB), axis z = −0.300 m (top at the deck datum, beam in the top
  channel as drawn), x placed end to end from the rear float's drawn position: 0.50–2.10, 2.12–3.72, 3.74–5.34 m
  (the GLB proxies are 1.6/1.425/1.575 m long and end at 5.1 m; three real 1.60 m floats cannot fit that). Analytic
  volume πr²(L_body + L_nose/2) = 0.410 m³ each, 2.460 m³ for six (+16.6 % vs the GLB envelopes, 2.11 m³); the top
  channel (38.7 cm × 5 cm) is not subtracted. Scenario `floats_glb_capsules` keeps the v0.1–v0.3 capsules for
  sensitivity. Installed positions, fill and the real section remain measurement #1. `buoyancy.MeshSurface`
  (config type `mesh_file`) takes a measured closed mesh in their place.
  Frame, deck, panels and equipment have **no** buoyancy (they are not treated as a watertight hull).
* Submerged volume, centre of buoyancy and waterplane properties: exact integrals of the clipped triangulation
  (divergence theorem + Green's theorem); default tessellation 96×(12+2×24) per float, verified against the analytic
  Flofiz volume to 7·10⁻⁵ (closed, outward-oriented, exactly mirror-symmetric mesh).
* Equilibrium: Newton on the exact wrench (Fz, Mx, My about the COM) with a finite-difference Jacobian (= −hydrostatic
  stiffness), backtracking, brentq/hybr fallback. Acceptance |Fz|, |Mx|, |My| ≤ 10⁻⁹·Mg; achieved ~10⁻¹³.
* If M/ρ ≥ total float volume, **no equilibrium** is reported; buoyancy is never increased to float the structure.
* Freeboard definitions (all heights above the still waterline): `float_top_freeboard_min` (lowest float top),
  `draft_max` (deepest float bottom), `lower_deck_freeboard_min` (the four corners of the 2.1 m rear deck plate at
  Z = 0), `frame_footprint_deck_datum_freeboard_min` (four corners of the 4.95 × 4.547 m footprint at Z = 0),
  `observation_deck_centre_height`.
* Static stability: restoring matrix C (heave, roll, pitch about the COM) from central differences of the exact
  wrench, verified against ρg·A_wp, ρg(I_xx + V·z_B,rel), ρg·S_y … to ~10⁻⁷; GM_T = C44/(ρgV), GM_L = C55/(ρgV).
  It is initial, static stability only: not a righting-arm curve, not a capsize limit, no flooding, no frame buoyancy.

## 5. Wave response (linear, zero speed)

* Capytaine 3.0.0 BEM (Delhommeau Green function, indirect method, internal lid for irregular frequencies) on the
  immersed part of the float capsules at the solved equilibrium pose; default panels 0.12 m (1503 faces + 348 lid),
  ω 0.5–6.0 rad/s step 0.1 (T 1.05–12.6 s) plus 0.05 rad/s refinement inside the detected gap-resonance bands,
  infinite depth unless a depth is given. Radiation (A, B) is solved once per configuration; the diffraction problem
  is solved **at the exact requested heading** (no heading interpolation in the results — verification showed a
  30° heading grid is inadequate for λ/L < ~3). Hydrodynamic interaction between the six floats is included (one
  body, six rigid DOF).
* Lid placement: Capytaine's `lowest_lid_position(ω_max)` is used, clamped to half the body's draught (`hydro.make_lid`).
  For the floats this is the free surface (their irregular frequencies lie above 7 rad/s). For the host boat floating
  high on its proxy hull (draught 0.38 m) the unclamped position (−0.30 m at ω_max 6, −1.0 m at ω_max 5) lies below
  the keel and Capytaine silently drops the lid — the v0.3 comparison run was affected; results computed since carry
  `lid_z_m` per body in the BEM metadata.
* Equation: [−ω²(M + A(ω)) − iω(B(ω) + B_visc) + C] X = F(ω, β). Surge/sway/yaw have no restoring (no mooring);
  without explicit damping they are unbounded as ω → 0 (reported, not hidden).
* **Viscous damping is an explicit input**: ζ (fraction of critical, applied at the lowest uncoupled natural frequency)
  for heave/roll/pitch and absolute coefficients for surge/sway/yaw. Default 0.05 in the UI; the Waves tab shows the
  roll response for ζ = 0, 0.02, 0.05, 0.1, 0.2 so the sensitivity is always visible. No hidden tuning.
* **Gap resonances**: the water between the two float rows (and between float sections) resonates in potential
  flow near T ≈ 1.1–1.8 s (bands are detected automatically from negative added mass / damping spikes, refined with
  extra BEM frequencies at 0.05 rad/s, and flagged whenever the wave period falls inside). Potential flow
  over-predicts those responses; the real amplitude depends on viscous dissipation that is not modelled.
* Observation-platform accelerations: linear, at the deck centre and four corners, from a = −ω²(X_trans + Ω × r).
* Regular-wave applicability flags: steepness H/L > 1/10 (warn) or > 1/7 (error), H/depth > 0.78, roll/pitch > 10°,
  relative float motion reaching the local draft/freeboard (emergence/submergence), wave crest above the lowest
  deck freeboard (deck wetting — not modelled), panel size vs wavelength, proximity to natural frequencies with low
  damping, gap-resonance bands.
* Irregular sea: JONSWAP spectral statistics (σ, significant amplitude, T_z) on the computed band only — linear,
  long-crested, no extremes.
* The 3D animation is the **reconstructed linear motion** x(t) = Re(X·A·e^{−iωt}) with the water surface drawn at
  the same phase; the "exaggeration" slider scales both for visibility and is labelled as such.

## 5b. Host boat (Hydronaute, Renaud 8000) as a second body

* Source: `data/renaud8000_v1/` (reference reconstruction v1, 28 Oct 2026). Whole-boat mass 2 100 kg = archival
  light-weight reference (Fluvial page: 3 000 kg); the restored boat has not been weighed. COM/inertia `null` in the
  baseline; illustrative: COM (3.6, 0, 0.35) m in the boat frame (45 % L from the stern, 0.35 m above the package
  datum), inertia = thin-walled box 8.0 × 2.98 × 2.3 m — assumptions.
* Hull = the package's closed "gull-wing" envelope PROXY rebuilt analytically from its station table (same ruled loft
  as the package's `build_model.py`; stern cap flat, bow cap pointed, keel excluded), closed and consistently oriented
  (checked). **Not a measured hull.** Consistency check: at the package's drawn waterline (z = 0) the proxy displaces
  ≈ 4.9 m³ (≈ 4.9 t of fresh water), far above the 2.1–3.0 t references — the proxy form and/or its datum are wrong.
  The model therefore floats the boat at the waterline that balances its mass (2 100 kg → hull draft ≈ 0.38 m, keel
  excluded; catalogue 0.75 m incl. keel), and reports the inconsistency.
* Frames: boat CAD X stern→bow, Y to port, Z up. Common world W: Z up, waterline Z = 0, horizontal axes = EXO CAD,
  EXO CAD origin at (0, 0). Berth placement `placement_in_exo_frame` (x, y, yaw of the boat CAD origin in the EXO CAD
  frame) is an **assumption** (default x = 2.2 m: transom 0.1 m forward of the EXO rear-deck plate, centred between the
  float rows, zero yaw); the boat's vertical position and attitude come from its own flotation, never from the transform.
* **Coupled still-water equilibrium**: both bodies are solved together with the lines as tension-only springs
  (T = max(0, k(L − L₀)), L₀ = L_nominal − T₀/k so that each line carries its nominal pretension at the nominal
  berth and the independent flotations). Unknowns: EXO heave/heel/trim, boat heave/heel/trim and the boat's
  horizontal shift and yaw from the nominal berth (the EXO fixes the frame); equations: full 6-component balance of
  the EXO and vertical/heel/trim balance of the boat (its horizontal balance is the EXO's with opposite sign).
  Solved by an **active-set** outer loop (v1): the lines currently taut are treated as bilateral springs, so each
  inner Newton solve is smooth (quadratic convergence); a line whose tension comes out negative leaves the set, a
  slack line whose extension becomes positive joins it, until the set is consistent with the tension-only law; the
  result is then verified with the tension-only residual (tolerance 1e-9·Mg) and the former damped Newton on the kink
  model is kept as a fallback. A warm start from a previous solve is used only if it is closer to equilibrium than the
  cold start (independent flotations). The EXO's reported hydrostatic residual is then exactly the
  line force on it (≈ −124 N vertical with the defaults). Lines slack at rest are reported and carry no stiffness in
  the wave model; when every line is slack the boat position is undetermined and a 1 N/m numerical centering spring
  holds it at the nominal berth (flagged). No contact/fenders: an arrangement that cannot balance ends with slack lines,
  not with a fake pretension.
* The coupled solve uses an active-set outer loop (lines in the set are bilateral springs: smooth Newton with the
  analytic hydrostatic Jacobian from the restoring matrices and finite differences of the cheap line/external terms
  only; one exact finite-difference step when the approximate φ-columns stall), then verifies with the tension-only
  law; a bounded trust-region least-squares pass finishes the rare stalls. Typical cost 0.3–0.6 s per state.
  No contact model: an equilibrium that exists only with the boat displaced into the EXO structure (transom over the
  rear-deck plate, hull into a float) is reported as CONTACT / not physical, e.g. the v0.3 default lines (10 kN/m)
  let the boat slide 107 mm aft under full push and the transom meets the rear deck plate (62 mm overlap); long push
  springs leave 11 mm.
* When no static equilibrium exists (e.g. 800 kg on a deck corner) the solver's best balance point (attitude, which
  floats are fully submerged, unbalanced fraction of the weight) is returned and drawn, clearly labelled, so the
  tendency is visible; it is not an equilibrium.
* Geometric clearances at the solved poses are reported and flagged (INTERFERENCE when negative): boat roof vs EXO
  header/observation-deck/panel undersides, hull vs float inner faces, transom vs the EXO rear-deck plate. Of the 190
  EXO members only the two transverse base members crossing the float gap intersected the berthed boat; per the user
  they do not exist and are hidden (with the walkways and the end-bay top rails).
* Mooring lines (assumed arrangement): two aft breast lines (EXO aft posts → stern cleats, slight aft pull) and two
  springs (EXO forward posts → midship cleats aft of them, forward pull) so the horizontal forces can balance; defaults
  k = 10 kN/m, T₀ = 100 N, editable. Attachment points are editable in the interface (table and 3D handles) and
  `host_boat.line_presets` holds named arrangements, including the four-lines-all-forward arrangement of the user's
  figure (which can hold a tow but cannot transmit the pods' push: every line runs forward of its EXO point). Dynamic model: linear spring about the equilibrium tension — stiffness
  k·uuᵀ + (T/L)(I − uuᵀ) (axial + geometric). A bare taut polyester line is ~5–10× stiffer and **unilateral**: the
  response flags every line whose dynamic tension amplitude exceeds its rest tension (it would go slack and snatch).
  The **line snatch check** (v1, `response.line_snatch_check`, interface: Waves tab) integrates the 12-DOF motion in
  the time domain with the tension-only law on the instantaneous attachment positions (RK4, hydrodynamic coefficients
  frozen at the encounter frequency, static line forces balanced by the equilibrium) and reports per line the peak and
  minimum tension, the fraction of the cycle spent slack and the snatch ratio (peak dynamic tension / linear
  amplitude). Checked: for a 2 mm wave (no slack) it reproduces the linear amplitudes within 3 %. With the default
  "slightly tense" 10 kN/m lines in a 0.3 m, 2.5 s beam sea, the lines are slack 30–65 % of each cycle and the peaks
  reach 2–3× the linear amplitude (~1.1 kN on a line pretensioned at 88 N): rope sizing must use these peaks, or the
  lines must be made compliant (nylon, snubbers) / pretensioned harder — a design conclusion of the model, not a
  measured fact.
* Wave response with the boat: 12 DOF (6 per body about its own COM, world axes), Capytaine `Multibody`
  (hydrodynamic interaction between the hull and the floats included), M and C block-diagonal, K = C + K_lines.
  Default two-body panels 0.20 m (floats) / 0.30 m (hull), ω 0.5–5.0 rad/s; the 0.19 m hull–float gap is therefore
  under-resolved and its viscous dissipation absent: gap-resonance periods are indicative only (flagged).
* People can stand on the boat too (`boat_aft_deck` 0.78 m, `boat_forward_terrace` 0.49 m, `boat_roof` 2.28 m —
  walking on the roof is an assumption).

## 5c. Interactive solve and first-order preview

* Still-water solve: Newton on the exact wrench with the analytic Jacobian (−restoring matrix), warm-started from the
  previous pose expressed through the CAD-origin height (COM-independent), typically 4–6 wrench evaluations
  (≈ 0.1–0.3 s). Step limiter 0.25 m / 0.15 rad; a warm start that lands on a statically unstable second root is
  rejected and re-solved cold. When no stable equilibrium exists the reason is stated (which floats are fully
  submerged / dry, indefinite restoring matrix).
* While dragging a battery, the electronics or a person in 3D, the viewer shows a **first-order preview**
  Δq = C⁻¹ ΔW (ΔW = wrench of the moved weight about the COM, C = restoring matrix of the last exact solve) and
  labels it as such; the exact solve runs every ~0.4 s during the drag and on release. Since v0.4 the wave response
  is refreshed after every exact solve when a usable BEM exists (exact COM transform, or a nearby pose), so the
  animation follows the moved masses, the edited lines and the motor setting.
* **Design sweeps** (`exo01/optimise.py`, interface "Optimise"): battery positions in two zones — the rear deck
  (mirrored rows and port-battery-inboard variants, footprints kept clear of the cabinet, ladder and pod brackets) and,
  since v1.1 (user proposal 29/10), the **float-top side frames forward of the deck** (x 2.1–4.9 m, |y| 2.05 m: above
  the float row, outboard of the boat's half-beam 1.49 m, clear of the mid and end uprights at x 2.81 / 4.24 m) — and
  mooring-line arrangements (pairs of symmetric lines between assumed post and cleat positions, plus the presets), each
  evaluated with the same solvers: still water, push at 100 % (pods), tow at 100 % (boat engine) and the reference wave
  with the base pose's BEM. The scores are stated in the result notes; the full tables are returned, not just a winner.
  The battery result also reports, per zone, the position of least trim and the zero-trim position interpolated along
  the |y| = 2.05 m column. Physics behind it: the float centroid is at x ≈ 2.9 m while the structure, cabinet and rear
  deck put the empty-EXO COM at x ≈ 2.3 m with the batteries at the figure's position (x 1.425 m), hence −3.8° stern
  trim; moving 240 kg of batteries forward by ~2.1 m (to x ≈ 3.5 m) brings the COM over the centroid. Mass on the rear
  deck (people at the table) adds stern trim the batteries can only partly compensate. Whether the float cradle can
  carry 120 kg per battery is a structural question outside this model (nothing here checks the frame).
* Water density default 999 kg/m³ (fresh water, river Erdre) in the illustrative configuration; null in the baseline.
* **BEM reuse (v0.4)**: the BEM is computed about each body's CAD origin and moved to the COM by the exact
  reference-point transform A' = PᵀAP, B' = PᵀBP, F' = PᵀF·e^{−ik·Δ} (P = [[I, [d]ₓ],[0, I]]), verified against direct
  solves about shifted points to 10⁻¹⁵. Hence the cache is keyed on the **pose** (heel, trim, draught, and for the
  boat its x, y, yaw), not on the mass distribution: moving a battery that leaves the pose unchanged is an exact cache
  hit. With "pose reuse" (default in the interface) a cached BEM of a nearby pose is used and flagged `pose_reuse`
  with two tiers: **nearby** (within 0.05 rad, 0.05 m, boat 0.10 m / 0.03 rad — `hydro.POSE_TOL`: coefficients change
  little) and **APPROXIMATE PREVIEW** (within 0.17 rad, 0.30 m, boat 0.50 m / 0.10 rad — `POSE_TOL_COARSE`: the
  motion keeps following large load changes, but the added mass/damping/excitation belong to a pose up to 10° and
  0.3 m away — run *2 · Compute BEM* for the exact pose). The pose difference itself is never corrected.
  `results/cache/pose_index.json` lists the available poses. Long solves run in a worker process with real progress
  (the radiation and diffraction problems are solved in chunks) and can be cancelled; the cache stays consistent
  because every file is written atomically.

## 5d. Propulsion and towing (quasi-static, v0.4)

* Units: the two **RDT POD 5.0** rim drives on the EXO (62 kgf each per the component list; 5 kg in air per the
  manufacturer's page; at x = 0.34 m behind each float row, hub 0.44 m below the deck datum — depth ASSUMED), or the
  boat's inboard (19 CV archival; bollard thrust **unknown**, 1 500 N order-of-magnitude assumption). Thrust = setting
  × bollard thrust, constant with speed (optimistic: a rim drive's thrust falls with advance speed).
* Steady state: the horizontal thrust component balances the total resistance, R_EXO(U) + R_boat(U), solved for U.
  Resistance models are explicit and editable in `configs/*.json → propulsion.resistance`: EXO floats — ITTC-57
  friction on the wetted area of each row × (1 + k = 1.30) + C_d = 0.15 × the submerged frontal area of one float
  (nose/flat-end junctions); boat — ITTC-57 on the proxy hull's wetted area × (1 + k = 1.25) × 1.15 appendages +
  residuary C_R = 0.0015·(Fr/0.2)⁴ on the wetted area. No wave-making term for the floats, no wave-added resistance,
  wind or current: the speeds are indicative (≈ 1.7 / 2.3 / 2.8 m/s at 20 / 50 / 100 % with the boat; the EXO alone
  comes out at 5.5 m/s, an upper bound).
* Forces: thrust at the configured points along the body x-axis; each body's drag along the thrust axis at its
  submerged-centroid depth and x, on its centreline (steering holds the assembly straight; the lateral offset of the
  true drag centroid is reported). These world-frame wrenches enter the single-body equilibrium (external wrench) or
  the coupled equilibrium (both bodies), so trim, heel, draught and the **line tensions / slack** reflect the push or
  tow; the drag points are frozen per outer pass and the speed/resistance split is iterated to 0.1 % of the thrust.
  Force balance verified: the lines carry exactly the pushed body's resistance (tests/test_propulsion.py).
* An arrangement whose lines cannot transmit the force (all lines run the wrong way) has no static equilibrium: the
  result is flagged and the no-thrust flotations are shown — physically the bodies would move until they touch.
* With forward speed the wave response is solved at the **encounter frequency** ω_e = ω − kU cos β with zero-speed
  coefficients at ω_e (low-Froude approximation, labelled in the output); no speed-dependent hydrodynamics.

## 5e. Mooring elements, fenders and the rigid-coupling limit (v1.2)

* Every connection between the EXO frame and the boat is an element with a `kind`: **line** = tension-only spring
  (T = max(0, k (L − L0)), L0 = L_nominal − T0/k so that it carries the pretension T0 at the nominal berth); **fender** =
  compression-only (push bar / stern fender between the EXO rear deck edge and the boat's transom, T = min(0, k (L − L0)),
  L0 = L_nominal + T0/k: preload T0 in compression, T0 = 0 just touching; the contact is measured as the signed
  penetration along the fender's nominal axis, so a transom pushed past the contact point keeps compressing it);
  **strut** = bilateral spring (a bolted or rigid link in the limit k → large; k = 1 MN/m in the preset). The coupled
  static solver treats unilateral elements with an active set; a 1 N/m numerical centering spring keeps an in-plane
  mode that no element restrains (sway with fenders only) determined. In the wave model a compressed fender or a strut is
  a spring about its static load; the time-domain check applies the unilateral laws.
* Assumed element properties (no measurements): line stiffness 2 kN/m (elastic snubber / long nylon), 10 kN/m
  (default), 50 kN/m (short polyester), 200 kN/m (Dyneema-like); fenders 50 kN/m (foam / pneumatic); struts 1 MN/m.
  Lines are massless, linear, undamped; no friction at the fenders; no wind, current or wake impulse.
* Fender points: EXO rear deck edge (x 2.1, y ±0.9, z 0.25) to the boat's transom (boat x 0, y ±0.9, z 0.40), levelled
  so that the element axis is horizontal at the nominal berth (gap ≈ 0.07 m there, from the assumed berth placement).
* `scripts/run_mooring_study.py` sweeps arrangement × line stiffness × pretension in the moored, push (pods 100 %) and
  tow (boat engine 100 %) states and in three regular waves (beam 0.3 m / 2.5 s, head 0.3 m / 2.5 s, beam 0.5 m / 3 s),
  with the linear response and the tension-only time-domain check (peak loads, slack fraction, fender impact, transom gap
  breathing, strut loads for the rigid limit). Results in `results/mooring/`; reading in `docs/MOORING.md`.

## 6. What the model cannot say

Capsize limits, breaking-wave impacts, slamming, green water, surf-riding, mooring loads, joint stresses, deck load
capacity, fatigue, structural strength — none of these follow from a linear rigid-body model. Global forces do not
determine member or joint loads. Any attached host boat (Hydronaute) is a separate source of mass, buoyancy and
connection stiffness and is **not** modelled: all results are EXO-only.

## 7. Verification vs validation

`scripts/run_verification.py` (report in `results/verification/`) checks that the code solves its own equations:
unit/transform checks, mass accounting, analytic buoyancy of a capsule and a sphere, equilibrium residuals, a
deliberately symmetric load, hydrostatic stiffness vs analytic formulas and vs Capytaine on the same mesh, long-wave
limits of the excitation, heading symmetry, tessellation / BEM panel / frequency / heading / time-step convergence
with the actual errors. None of this is validation. Validation needs measurements of the real structure.

## 8. Measurement and physical-validation plan (to turn this into a trustworthy tool)

1. **Floats**: measure section shape along the length (template or 3D scan), end shapes, installed x/y/z of each
   float relative to the frame, and the lateral spacing (resolve 3200/3353). Fill or foam? Weigh one float.
2. **Weigh and locate**: weigh each section as installed (confirm 150/70/70 exclusive of floats/equipment), weigh the
   observation deck surface, batteries, panels, electronics; record installed positions; a two-point lift or
   crane-scale inclining gives the assembly COM (x, y) directly.
3. **Flotation test (still water, EXO alone)**: measure the waterline on each float (draft marks) at a known total
   mass; compare with `draft_max`, heel/trim. Repeat with a known mass moved transversely (inclining experiment,
   e.g. 80 kg moved 2 m): the measured heel angle gives GM_T directly and validates the COM height and the float
   waterplane. Repeat with people on the observation deck.
4. **Decay tests**: excite roll, pitch and heave by hand in calm water and record with an IMU on the observation deck:
   natural periods validate the inertia + added mass; the logarithmic decrement gives the viscous damping ζ to use
   instead of the 0.05 placeholder.
5. **Wave transit / boat-wake tests**: an IMU on the deck and a wave probe (or a second IMU on a float) during passing
   boat wakes give measured RAOs at a few periods; compare with the linear RAOs, in particular in the 1–2 s range
   where the gap resonance is predicted.
6. **Hydronaute berthed**: weigh the boat (crane scale or draft marks against a measured hull), survey the underwater hull
   (offsets or 3D scan) to replace `renaud8000_hull_proxy`, measure the berth position and the real line/fender
   arrangement (lengths, material, pretension), then validate the two-body model against a relative-motion
   measurement (two IMUs, one per body, in boat wakes).
7. **Structure**: member sections, wall thickness, alloy, joint type — for a separate structural model (not this tool).
