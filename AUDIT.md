# Audit of the EXO-01 reference package, revision 3 (28 Oct 2026)

Files audited: `EXO01_mass_metadata.json`, `parameters.json`, `EXO01_reference.glb` (binary parsed directly),
`EXO01_reference.step` (unit header and point extent), `source_plan.webp`, `source_annotation.jpeg`,
`EXO01_reference_views.png`, `validation.json`, `artifact_validation.json`, `viewer_validation.json`,
`EXO01_3D_viewer.html` (byte-identical to the copy sent separately, md5 `3c0db582…`; raw-WebGL viewer with the
tessellation embedded as JSON — not reused, the project renders the GLB with three.js instead).

## What is consistent

| Check | Result |
|---|---|
| GLB is glTF 2.0 binary, 207 nodes, 190 meshes, one scene, one root `EXO01_REFERENCE_V3` | OK |
| Root rotation quaternion `(-0.7071, 0, 0, 0.7071)` = −90° about X, exactly `(x,y,z)CAD → (x,z,−y)glTF` | OK — the only axis conversion in the file |
| No child node carries its own `translation`/`rotation`/`scale`/`matrix` | OK — child vertices are already in CAD metres |
| 16 parent nodes with `component_id` + `mass_kg`; 190 child meshes with `mass_owner` + `mass_is_in_parent` | OK — sum of parents = **840.0 kg** exactly; no child carries `mass_kg` |
| Register in `EXO01_mass_metadata.json` == GLB extras == `parameters.json` masses | OK |
| STEP header `SI_UNIT(.MILLI.,.METRE.)`; CARTESIAN_POINT extent max = (5585, 2276.5, 2763.5) mm | OK — matches the GLB bounds (5.585, 2.2765, 2.7635) m within 3 mm |
| Documented bounds `artifact_validation.json` == bounds recomputed from GLB vertices | OK (error 0) |
| Observation surface top at Z = 2.200 m; ladder lands at 2.207 m; headers under the 24 mm deck | OK |
| Four panels in one transverse row, x 3.525→5.585 (0.635 m front overhang), |y| ≤ 2.2735 (no side overhang) | OK |
| Six float proxies: closed, manifold (every edge used twice), consistent outward orientation | OK |

## Discrepancies and findings (beyond those already listed in the package)

1. **Float proxy tessellation is unusable for hydrodynamics.** The GLB floats are 1036 long thin triangles each
   (strips the full float length, panel "radius" 0.68 m). Capytaine needs panels ≲ λ/8. The project therefore
   rebuilds each float analytically as a capsule (cylinder + hemispherical ends, r = 0.290 m, same x-span and
   y-centre as the GLB envelope) and keeps the GLB only for display. Volume check: analytic proxies 2.1228 m³ vs GLB
   tessellation 2.1097 m³ (+0.6 %, within the expected inscribed-polygon bias of the coarse GLB).
   `buoyancy.MeshSurface` accepts any measured closed surface later without touching the solver.
2. **Float spacing vs the drawing.** The proxy float centrelines are at y = ±1.970 m, inner faces at ±1.681 m
   (clear gap 3.36 m). The drawing shows **3200** (end view, under the deck) and **3353** (top view). 3353 ≈ the clear
   gap between float inner faces (3362 mm); 3200 does not match any proxy dimension. Roll stiffness goes with the
   square of the spacing, so the real installed spacing is a priority measurement. *User note 28 Oct 15:18: the two
   longitudinal walkway plates drawn in the bays do not exist; the gap between the float rows must stay free to berth
   the Hydronaute. 18:18: the members touching the boat do not exist* — an intersection test of every EXO member against
   the berthed boat (hull section + cabin, at the still-water poses) finds exactly two: the transverse base members
   `base_crossmember_end` at x = 3.5 m and x = 4.95 m spanning the gap at deck level. Recorded in
   `configs/*.json → visual_overrides` (viewer hides `walkway_±1` and `base_crossmember_end`); no mass or buoyancy
   effect. Structural remark outside this model: without those members the two sides of each bay are joined only by the
   headers at 2.1 m and the top members. Whether 3353 is the berth width is a **hypothesis**, not a confirmed reading.
3. **Deck-plate thickness vs datum.** The rear deck plate is drawn from Z = −0.018 to 0 m, with edge/cross members
   down to −0.08 m; the bay longerons sit at −0.065…−0.005 m; the float tops are at Z = 0. So the "deck datum" is the
   top of the deck plate and the floats' top tangent. Freeboards in the project are reported at the deck plate
   corners (Z = 0) — a conservative "water reaches the deck surface" measure, not the lowest structural member.
4. **4950 vs 4980 mm** — preserved as in the package (model length 4.950 m; 30 mm unresolved). End frame posts end
   at x = 4.95 m; the panel row overhangs to 5.585 m.
5. **Observation deck mass** — `upper_observation_deck_proxy` has `mass_is_in_parent: null`, `surface_mass_kg: null`.
   The project keeps it unresolved: the 70 kg middle-section mass is used as reported, and an explicit
   `pending_loads.observation_deck_surface_mass_kg = null` remains in both configurations.
6. **Equipment "preview anchors" are centres of visual boxes** (battery box centre is at Z = 0.266 m, anchor says 0.25;
   electronics box centre at 0.95 = anchor). The baseline keeps every COM `null`; the illustrative configuration
   uses the anchors as *assumed* COMs and says so per component.
7. **`viewer_validation.json` reports no real-browser WebGL test** for the package viewer. This project's interface
   was exercised in headless Chromium (`results/ui/`), see README.
8. Minor: `parameters.json` carries `float_diameter_proxy_mm: 580` while the GLB tessellation is 578.4 mm wide in Y
   (inscribed polygon) and 580 mm in Z — purely a tessellation artefact; r = 0.290 m is used.

## Missing inputs (kept `null` in `configs/baseline.json`)

See `configs/baseline.json → missing_inputs` and the ranked list in `configs/five_missing_measurements.json`:

1. Float displacement geometry and installed positions (true section, lengths, end shapes, lateral spacing, foam/air fill).
2. Installed centre of mass of every component (especially vertical) and inertia distribution.
3. Mass accounting and total operating displacement (sections exclusive of floats/equipment? deck surface? propulsion, payload, cabling).
4. Host boat (Hydronaute): mass, buoyancy geometry, COM, berth position and connection stiffness.
5. Operational loads and environment: occupants, water depth, wave climate, measured roll/heave/pitch damping.

Everything that needs one of these is reported as **not computed** in the baseline; the illustrative configuration
fills them with labelled assumptions and every output carries the label *"Exploratory — assumed geometry and mass
distribution."*


## Renaud 8000 reference package (v1, 28 Oct 2026) — audit

| Check | Result |
|---|---|
| GLB: glTF 2.0, one root `RENAUD8000_REFERENCE_V1` with the same −90° X rotation; one mass-bearing parent `RENAUD8000_BOAT_REFERENCE` (2 100 kg), 7 visual subsystems with `mass_kg: null` | OK — counted once |
| STEP hull envelope PROXY: mm, extent (0…8.0, ±1.49, −0.53…0.78) m | OK, matches the station table |
| Hull envelope rebuilt analytically from `hull_stations_mm` + the `build_model.py` section profile (ruled loft) | closed, consistently oriented, volume 22.49 m³ (total envelope), invariant under subdivision |
| **Displacement at the drawn waterline (z = 0)**: 4.87 m³ ≈ 4.9 t | **inconsistent** with the 2.1 t archival / 3.0 t published references (and with the catalogue draft 0.75 m incl. keel). The proxy hull form and/or its waterline datum are not credible; flotation is solved from the mass, not read from the drawing. |
| Mass: 2 100 kg "light weight 2.1 T" (archival sheet) vs 3 000 kg (Fluvial) | kept as alternatives, neither verified for the restored boat; current loading (batteries, tanks, refit) unknown |
| COM, inertia, engine mass/position, tank fills | `null` in the package → null in the baseline; illustrative assumptions labelled |
| Berth position in the EXO, line arrangement | not in either package → `placement_in_exo_frame` and `lines` are explicit assumptions (editable) |

Berth geometry at the default placement (illustrative flotation of both bodies): hull-to-float clearance ≈ 0.19 m per
side, roof clearance 0.34 m under the EXO headers / 0.42 m under the observation deck / 0.83 m under the panels,
transom 0.05 m forward of the rear-deck plate. All of it moves with heel/trim and with the real hull shape.


## User's anatomy figure `exo01-hydronaute.html` (build.mjs, 28 Oct 2026, 20:55) — what was taken from it

The figure is a 2-D isometric SVG (not a 3-D model) built from the La Mutine sheet, the simulator's v0.2 configs, the Renaud
package and the "EXO-01 component list (2026-09-12)". Facts new to the model, all labelled `user_statement` in the configs:

| Item | Figure | Used in v0.4 |
|---|---|---|
| Floats | 6 × Flofiz 1.60 m × Ø 0.60 m, nose 0.30 m, moulded top channel 38.7 cm, 2" filler; rear float nose aft, others nose forward | `flofiz_x` surfaces (body 1.30 m + sled nose), end to end from the rear float's drawn position; +16.6 % volume vs the GLB proxies |
| Batteries | 2 × Dyness PowerBrick Plus 51.2 V / 16.07 kWh, standing upright, one strapped to each side rail, mirrored (≈ 0.55 × 0.30 × 1.00 m drawn) | COM (1.425, ±2.05, 0.50) m; masses stay at the register's 120 kg each (datasheet mass not supplied) |
| Cabinet | port side of the rear deck, back against the frame, opening aft (0.46 × 0.92 × 1.00 m) | ELECTRONICS_50 COM (1.73, 1.08, 0.50) m |
| Propulsion | 2 × RDT POD 5.0 (5 kW, 48 V, 106 A, 62 kgf each) at the back behind each float row | `propulsion.units.EXO_PODS`: 1 216 N bollard, points (0.34, ±1.97, −0.44) (hub depth assumed); pods 8 kg each assumed, not in the register |
| Mooring | four lines all running forward: EXO x 2.18 / 4.87 → boat stern x 0.30 / midship x 4.30 | preset `figure_all_forward`; the solver shows it cannot transmit the pods' push (all lines slack) |
| Float vertical position | figure draws the float axis 0.41 m below the deck ("channel top 5 cm under the beams") | NOT adopted: the GLB has the float tops at the deck datum with the beam in the channel; the figure's −0.41 m is unexplained — to measure |
| Boat | Renaud 8000 1987, 8.00 × 2.98 m, archival draft 0.75 m | unchanged (proxy hull) |

Not in the figure, still missing: battery and pod masses, cleat positions on the boat, the thrust-vs-speed curve of the
pods, the boat's real hull and loading.
