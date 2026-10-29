# HTTP API (backend ↔ web interface), v1.0

All endpoints keep their v0.3 behaviour; additions only. Payload "state" = `{base, overrides, scenario_name?, scenario_title?}` as before.

## Overrides (in `overrides`)
- `host_boat.lines`: full list replaces. Each line: `{id, exo_point_m:[x,y,z] (EXO CAD frame), boat_point_m:[x,y,z] (boat frame), stiffness_N_per_m?, pretension_N?}`.
- `propulsion`: `{thrust_fraction: 0..1, unit: "EXO_PODS"|"BOAT_ENGINE", coefficients?: {…editable resistance/thrust coefficients, see config.propulsion}}`. Merged into the config's `propulsion` block. `thrust_fraction: 0` (or missing) = motor off → identical to v0.3.

## GET /api/meta  (additions)
- `line_presets`: `[{id, title, note, lines:[…]}]` named line arrangements (from configs/illustrative.json → host_boat.line_presets).
- `propulsion_defaults`: the config's propulsion block (units, bollard thrust, pod positions, coefficients) for display/editing.

## POST /api/evaluate  (additions to the response)
- `propulsion`: present when thrust_fraction > 0 and the equilibrium is solved:
  `{unit, thrust_fraction, thrust_total_N, thrust_points_world:[[x,y,z]…], speed_m_s, speed_kn, resistance:{exo_N, boat_N, total_N, breakdown:{…}}, line_load_N (force the lines carry = boat resistance when EXO pushes), converged, notes:[…], label}`
  The `equilibrium`, `bodies.*.pose`, `lines` (tensions, slack) and `flags` already include the thrust/drag forces.
- `lines[i]` keep `tension_N`, `slack`, `a_world`, `b_world`, `unit`.

## POST /api/wave  (additions)
- payload: `speed_m_s?` (number; UI passes `propulsion.speed_m_s` from the last evaluate), `allow_pose_reuse?: true`,
  `damping`: either the v0.3 single set `{zeta:{heave,roll,pitch}, absolute:{surge,sway,yaw}}` applied to every body, or per body `{EXO:{zeta…,absolute…}, BOAT:{…}}`.
- response: `encounter: {speed_m_s, omega_e, period_e_s, note}` when speed > 0 (zero-speed coefficients at the encounter frequency — labelled approximation);
  `hydro_meta.pose_reuse`: `{dz_m, dheel_deg, dtrim_deg, boat_dx_m?, …, note}` when the BEM of a nearby pose was reused instead of this exact pose;
  status `"no_hydro"` (HTTP 200, `error` text) when nothing usable exists → UI shows "Compute BEM".
  `regular_wave.bodies[NAME].X_complex` unchanged (6 complex per body); `regular_wave.lines`: per line `{id, tension_mean_N, tension_amp_N, min_N, max_N, slack_in_cycle}` (exists in v0.3 as `lines`), `regular_wave.relative_motion`: `{min_clearance_hull_float_m, roof_vs_headers_min_m, …}` when the boat is present.

## POST /api/hydro  (additions)
- payload `allow_pose_reuse?: true`: a nearby-pose BEM counts as done (response `status:"done", meta.pose_reuse`).

## POST /api/optimise  → job (poll /api/job/<id>)
- payload: `{...state, target: "battery"|"lines", wave:{H_m,T_s,heading_deg}, damping, hydro_settings?}`
- job result (`result` field when status == done):
  `{target, label, rows:[{…candidate fields…, heel_deg, trim_deg, freeboard_min_m, roll_amp_deg, pitch_amp_deg, heave_amp_m, deck_accel_max, line_min_N, line_max_N, slack_lines:[…], score, rank}], best:{candidate, overrides_to_apply:{…}}, notes:[…], hydro_note}`
  - battery: candidates are mirrored (x, |y|) positions of BATTERY_1/2 on the rear deck grid; `overrides_to_apply` = `{components:{BATTERY_1:{com_m}, BATTERY_2:{com_m}}}`.
  - lines: candidates are arrangements built from EXO attachment points (posts) × boat cleats; `overrides_to_apply` = `{host_boat:{lines:[…]}}`.

## POST /api/export (unchanged) — includes `propulsion` and `lines` in the JSON/CSV when present.

## Jobs (v1)
- `POST /api/hydro` and `POST /api/optimise` return `{job_id, status: "queued", queue_position}` (or `status: "done"` at once when the
  BEM exists). Jobs run one at a time in a worker process.
- `GET /api/jobs` → list of the last 20 jobs: `{id, kind: "hydro"|"optimise", status: queued|running|done|error|cancelled, progress 0..1,
  message (current solver step), elapsed_s, eta_s, queue_position, error?, result? (optimise), meta? (hydro)}`.
- `GET /api/job/<id>` → the same record; `POST /api/job/<id>/cancel` → cancels a queued job or terminates a running one.
- `GET /api/health` → `{ok, version, cached_poses, jobs_active}`.

## POST /api/snatch (v1)
Time-domain tension-only line check for the current state and wave: `{...state, wave, damping, allow_pose_reuse?}` →
`{period_e_s, n_periods, lines: [{id, static_N, peak_N, min_N, slack_fraction_of_cycle, linear_amp_N, snatch_ratio}], note}`.

## Errors
Every error is JSON: `{error, status: "error", kind: "input"|"server"}` with HTTP 400 for bad input (unknown component, non-finite
numbers, out-of-range density/depth) and 500 otherwise.
