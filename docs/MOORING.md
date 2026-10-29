# EXO-01 ↔ L'Hydronaute coupling: what the study says (v1.2, 29 Oct 2026)

**Exploratory — assumed geometry and mass distribution; line and fender properties are assumptions, not measurements.**
Source: `scripts/run_mooring_study.py` → `results/mooring/` (121 configurations = 6 line arrangements × 4 line stiffnesses ×
5 pretensions + the rigid-strut case, which has no line to vary; moored / push 100 % / tow 100 %; three regular waves with
the linear 12-DOF model, then the separate tension-only time-domain check). Element model: ASSUMPTIONS §5e. Damping: potential-flow
radiation damping plus an assumed 5 % of critical in heave/roll/pitch (10 % for the boat's roll/pitch); lines, fenders and struts
are undamped springs. Occupants in the coupled cases: none (light EXO + light boat).

## 1. The short version

| question | answer from the model | confidence |
|---|---|---|
| Which arrangement closes the force loop in push *and* tow? | Correctly oriented tensioned lines can (`best_diagonals`, `six_lines`: lines from the forward posts to the stern cleats), but only with k ≥ 10 kN/m and with the boat sliding 20–45 mm into the 60 mm gap under push (120–230 mm = contact with 2 kN/m lines). **Stern fenders add a compression path** that closes the push loop at any line stiffness with 1–20 mm of travel (`fenders_crossed_lines`, `fenders_diagonals`). The drawing's four forward lines never push. | high (statics) |
| Where must it be rigid? | **Longitudinally, at the transom** (the push goes through fenders in compression, never through rope in tension). **Not vertically**: let heave/pitch/roll of the two hulls stay free — a rigid vertical coupling carries ≈ 1.1–1.3 kN cyclic per strut in 0.3 m waves, continuously. Sway and yaw: restrained by crossed lines or diagonals in tension. | high |
| Shock absorbers? | **Not demonstrated — what is shown is the effect of compliance (stiffness), not of damping**: the elements are undamped springs. Line peaks scale with rope stiffness: 2 kN/m → 0.5–1.3 kN, 10 kN/m → 0.6–1.5 kN, 50 kN/m → 1.5–3 kN, 200 kN/m → 3–5 kN in the same 0.3 m waves; but very soft lines (2 kN/m) with fenders let the boat accelerate into the fenders (fender peaks 2–5 kN). The results support investigating compliant connections around **≈ 10 kN/m lines with firm (≈ 50 kN/m) fenders**; selecting an actual snubber/damper needs a model with damping, available stroke and peak reaction (next step). | medium–low |
| Pretension? | **200–400 N** per line with 10 kN/m lines: slack fraction 20–30 % of the cycle in 0.3 m beam waves, peaks ≈ 0.7–1.3 kN. No-slack needs ≈ 800 N (then the static load alone is 0.8 kN, no benefit). Below 100 N every line snatches every cycle. | medium |
| Fender at the back? | **A promising option: two push fenders/knees at the quarters (y ≈ ±0.9 m) at transom height**, stroke ≥ 50 mm (the linear relative motion at the transom is ± 0.02–0.05 m in 0.3 m waves, ± 0.14 m with crossed lines in 0.5 m waves), capacity ≥ 3 kN each (static push 0.3–0.6 kN each at full thrust, time-domain peaks 0.4–1.4 kN with 10 kN/m lines, up to 1.7 kN in 0.5 m waves). | medium |
| Hardware sizing | Lines: working load 1–1.5 kN, snatch peaks up to 2–4.5 kN with stiff rope in 0.5 m waves → 12 mm polyester/nylon with snubbers (MBL ≥ 2 t), cleats/posts and their frame attachment ≥ 5 kN. Fenders ≥ 3 kN. Rigid-coupling option: 4 struts ≥ 2 kN cyclic + fatigue. | medium |

Design direction for EXO-01 (to be confirmed with a damped-element model and the real knee geometry): **two push knees with fenders on the
rear deck edge** (x ≈ 2.1 m, y ≈ ±0.9 m, at the transom height of the host boat), lines clamping the boat onto the knees and
restraining sway/yaw — the pusher-tug arrangement. Among the configurations tested, it is the one with the smallest boat travel
under push and the lowest line peaks at equal stiffness.

## 2. Statics: which loops close

| arrangement | push (pods 100 %) | tow (boat engine 100 %) | boat shift under push |
|---|---|---|---|
| figure_all_forward (drawing) | never (lines slack, boat slides 0.7–1.2 m into the deck) | yes up to T0 200 N, no beyond | — |
| simulator_default (aft breasts + backward springs) | only k ≥ 50 kN/m | yes | −25 to −45 mm (into the 60 mm gap) |
| best_diagonals (aft posts→midship, fwd posts→stern) | k ≥ 10 kN/m | yes | −1 to −46 mm; soft lines: −120 to −230 mm = contact |
| six_lines | k ≥ 10 kN/m | yes | −1 to −46 mm |
| fenders + crossed stern lines + tow lines | yes, all k | yes | −8 to −22 mm (fender compression) |
| fenders + diagonals | yes, all k | yes | −1 to −8 mm |
| rigid struts (k 1 MN/m) | yes | yes | −5 mm; forward struts −580 N, aft +140 N |

Push through fenders: 300–450 N compression per fender at full thrust (R_boat ≈ 870 N at 2.8 m/s, upper bound).

## 3. Waves: peaks, slack, impacts (time domain, tension-only elements)

Beam waves H 0.3 m, T 2.5 s (the reference wake), worst line of the arrangement:

| arrangement | k [kN/m] | T0 [N] | peak line [N] (time domain) | slack fraction | fender peak [N] (time domain) | transom gap min [m] (linear model, see note) |
|---|---|---|---|---|---|---|
| fenders + crossed lines | 10 | 200 | 760 | 0.22 | 560 | 0.02 |
| fenders + crossed lines | 10 | 400 | 1270 | 0.19 | 700 | −0.02 |
| fenders + crossed lines | 50 | 200 | 1860 | 0.22 | 430 | 0.04 |
| fenders + diagonals | 10 | 400 | 1260 | 0.32 | 1140 | 0.05 |
| fenders + diagonals | 2 | 400 | 1215 | 0.26 | 2740 (impact) | 0.04 |
| best_diagonals (no fenders) | 10 | 400 | 1210 | 0.19 | — | 0.05 |
| best_diagonals (no fenders) | 50 | 400 | 3030 | 0.40 | — | 0.05 |
| best_diagonals (no fenders) | 200 | 400 | 4440 | 0.52 | — | 0.05 |
| simulator_default | 10 | 400 | 950 | 0.22 | — | 0.05 |
| figure_all_forward | 50 | 100 | 2200 | 0.95 | — | −0.11 (contact) |
| rigid struts | 1000 (bilateral) | — | 1130 per strut (linear), 1180 (time domain) | 0 | — | 0.03 |

Note on the transom gap: the column is the rest gap minus the *linear* relative-motion amplitude at the transom; in the linear model a
compressed fender is a bilateral spring, so a negative value (e.g. −0.02 m for crossed lines at 10 kN/m / 400 N) means the linearised
motion exceeds the rest gap — fender compression beyond its rest state in the linear picture, not a predicted structure–hull
contact. The time-domain check (which applies the unilateral fender law) gives the fender peak loads in the same row; a time-domain
gap statistic is not computed yet (next version). For the arrangements without fenders a negative value does mean the boat's transom
reaches the deck-plate edge in the linear model.

Head waves H 0.3 m, T 2.5 s give similar line peaks (0.5–1.3 kN at 10 kN/m) but the soft-line configurations let the
boat surge into the deck (gap −0.09 m with 2 kN/m lines and no fenders). Beam waves H 0.5 m, T 3.0 s: line peaks
0.7–2 kN at 10 kN/m, 2–4.5 kN at ≥ 50 kN/m; fender peaks up to 1.7 kN.

Rigid coupling changes the boat's motion: its roll amplitude in 0.3 m beam waves drops from ≈ 9° (soft lines) to
≈ 2.3° (struts) because the wide EXO holds it — at the price of the cyclic strut loads above and of carrying the two
hulls' relative wave loads through the frame.

## 4. What is *not* in these numbers

* Viscous damping 5 % of critical (assumed); potential-flow coefficients frozen at the encounter frequency; lines massless
  and undamped; no wind, current, or wake impulse (a passing boat's wake is a short group, not a regular wave).
* The berth gap at the transom is 0.07 m from the assumed placement (boat stern 0.1 m forward of the deck plate at the
  CAD datum, then the flotations); the real gap depends on the knee geometry.
* Time-step convergence of the time-domain check was verified on the strut and the fender cases (64 → 512 steps per period: peak
  loads change < 2 %); the strut peaks agree with the linear amplitudes within 5 % (1176 vs 1131 N). The reported "motion ratio"
  is dominated by DOFs with near-zero linear amplitude and is not a quality metric. The 0.5 m / 3.0 s strut case diverged (NaN) and is
  excluded; the linear strut amplitudes are the ones to use.
* Nothing structural: the posts, knees and cleats are not analysed, only their loads are given.

## 5. Batteries: float frame vs the last beam of the frame (user question, 29 Oct)

Trim (− = rear deck down) / rear-deck freeboard [m], boat moored, batteries at |y| 2.05 m (`results/optimisation/battery_x_vs_occupants.json`):

| occupants | x 1.43 (drawing) | x 3.50 | x 3.60 | x 4.00 | **x 4.24 (end frame)** | x 4.40 |
|---|---|---|---|---|---|---|
| empty | −3.84 / 0.17 | −0.07 / 0.36 | +0.10 / 0.36 | +0.80 / 0.37 | **+1.22 / 0.38** | +1.50 / 0.38 |
| 1 at the table + 1 on the upper deck | −4.96 / 0.08 | −1.01 / 0.28 | −0.83 / 0.29 | −0.12 / 0.32 | **+0.30 / 0.33** | +0.58 / 0.34 |
| 2 at the rear table | −6.91 / −0.01 | −2.52 / 0.20 | −2.34 / 0.21 | −1.63 / 0.25 | **−1.21 / 0.27** | −0.93 / 0.28 |
| 4 on the rear deck | none | −4.66 / 0.07 | −4.46 / 0.08 | −3.68 / 0.11 | **−3.23 / 0.14** | −2.94 / 0.15 |
| 2 upper + 2 rear | −6.71 / −0.04 | −2.26 / 0.19 | −2.07 / 0.20 | −1.33 / 0.23 | **−0.89 / 0.25** | −0.60 / 0.27 |
| 4 on the upper deck | −4.16 / 0.09 | −0.06 / 0.30 | +0.12 / 0.30 | +0.88 / 0.31 | **+1.34 / 0.32** | +1.65 / 0.32 |

Reading: x ≈ 3.5 m zeroes the *empty* trim; the end frame (x 4.24 m) accepts +1.2° bow-down empty and buys 1.1–1.3° less
stern trim and 0.02–0.06 m more rear-deck freeboard in every loaded case. Since the EXO is almost never used empty, **the end
frame is the better compromise** — provided the end-frame beam / side rails take 2 × 120 kg (not checked here) and the
forward float noses keep ≥ 0.33 m freeboard (they do: 0.34–0.35 m). The forward floats are also where the boat's bow wave
arrives: keep the batteries' boxes watertight.

## 6. EXO-01 alone: registration sheet (DDTM / service instructeur) — separate from the coupled cases

`scripts/run_stability_sheet.py` → `results/stability/stability_sheet.md`. EXO-01 alone, no boat, **75 kg per person** (the
coupled cases above use 80 kg illustrative occupants — do not mix the two). Read against the ES-TRIN art. 19.03 passenger-vessel
figures (heel ≤ 12° under passenger + wind moment, residual freeboard ≥ 0.20 m) and, separately, the 0.30 m minimum freeboard of
art. 19.04; the wind moment uses the 19.03 pressure (0.25 kN/m²) on an *assumed* 6 m² lateral area (heel ≈ 0.7°); the turning
moment is not evaluated. The floating-equipment chapter has different provisions. Which regime applies to EXO-01 is for the
service instructeur, and it changes the assessment — the tables give the inputs for either reading.

* Heel is never the limit: GM_T ≈ 21 m; eight people on one side of the upper deck heel the platform 4°.
* **Freeboard is the limit.** Each 75 kg passenger sinks the platform ≈ 15 mm (waterplane ≈ 5.6 m²) plus the trim from
  where they stand. Rear-deck freeboard light: 0.17 m (drawing batteries) / 0.36 m (x 3.6) / 0.38 m (x 4.24).
* Capacity under "residual freeboard ≥ 0.20 m at the worst placement": **0 passengers** with the drawing's batteries,
  **1–2** with the batteries forward (limited by two people in the stern corner), 10 if everyone stays on the upper deck.
  Under the 0.30 m minimum freeboard of 19.04: 0–1 passenger in every configuration.
* **Zoning + batteries forward (recommended layout, `results/stability/recommended_layout_cases.json`)**: aft 1.0 m of the rear deck
  closed to passengers (no float under the aft 0.5 m), batteries 2 × 120 kg on a bracket beyond the forward post (x 5.05, raised
  0.3 m — height changes nothing measurable: 1 mm of freeboard, 0.2 m of GM on 21), cabinet on the rear deck centred at its forward
  edge (x 1.75, y 0), no ballast → **4 passengers anywhere in the allowed zones keep ≥ 0.219 m** (6 spread over both decks: 0.241 m);
  light ship trims +2.7° bow-down with 0.33 m forward float-top freeboard, ≥ 0.20 m with 4 people on one side of the upper deck.
  Alternatives examined: batteries at the end upright (x 4.24) need 150 kg of ballast at x 4.75 for the same capacity; four batteries
  (480 kg) reach it too but at +4.6° light and 0.11 m forward float freeboard in the worst upper-deck case. A counterweight does not add freeboard (it sinks the platform ≈ 15 mm per 100 kg); it works through the trim lever.
* Deck-edge-awash regular wave height, light ship (no crew), batteries forward: ≈ 0.27 m at T 2.0 s, 0.46 m at T 2.5 s, 0.68 m at
  T 3 s (linear, 5 % damping, worst heading, BEM of a nearby pose reused — the short-period values are resonance-driven and need
  the decay test and an exact-pose BEM before being quoted).

Consequence: as drawn, EXO-01 alone does not have the freeboard of a passenger craft; it has the freeboard of a work
platform for a crew of 1–2 on the rear deck. Options if passenger carriage is the goal: raise the rear deck freeboard
(third float row aft, longer/larger floats, or a higher deck), or restrict the lower deck and carry people on the upper
deck. In every case the registration file needs the measured light-ship weight, the inclining test and the float survey
before any of these numbers is quoted as a characteristic.

## 7. Final comparison: ropes + knees vs tubes vs hybrid (30 Oct) — `results/mooring/final_comparison.md`

Twelve candidates at the settings the study converged on (ropes k 10 kN/m, T0 400 N, EXO eyes raised to cleat level
z 0.3; fenders k 50 kN/m), plus tubes (bilateral struts) with an elastomer cartridge in series modelled as a lower
stiffness (50–200 kN/m; no damping element exists in the model). Script `scripts/run_mooring_final.py`; the score is an
explicit, editable weighting (worst element peak, slack fraction, transom overlap, boat roll, static shift) behind a hard
gate (push and tow must close).

| rank | arrangement | worst peak [N] | slack | boat roll H 0.5 [°] | note |
|---|---|---|---|---|---|
| 1 | four rigid tubes, pinned (aft posts → stern cleats, fwd posts → midship cleats) | 1261 | — | 4.3 | time-domain diverged in the 0.5 m case (nan), peak quoted from the 0.3 m cases; no quick release; fatigue at the pins |
| 2 | same with elastomer cartridges (100 kN/m) | 1379 | — | 8.2 | cartridges give back most of the roll benefit and do not lower the peak (no damping in the model) |
| 3 | six-line sketch + stern knees/fenders, eyes at cleat level | 1157 | 0.11 (0.3 m beam), 0 at 0.5 m | 9.4 | best rope arrangement; quick release; fenders 400–1160 N |
| 4 | fenders + diagonals, eyes at deck level (study best) | 1261 | 0.33 | 9.7 | |
| 5–6 | two tubes aft (100 kN/m) + crossed/diagonal ropes | 1817–1996 | 0.32–0.37 | 9.6–10.9 | tubes carry the pitch difference alone |
| 7 | fenders + diagonals, eyes at cleat level | 4196 | 0.47 | 10.1 | raising the eyes helps the six-line plan, not the diagonals (snatch in the 0.5 m case) |
| 8–12 | two tubes aft + two tow ropes only (any cartridge) | 3553–9190 | 0.7–0.9 | 10–10.5 | rejected: without stern ropes the two short tubes are the only stiff path for yaw and pitch difference |

Reading: a rigid four-tube coupling is the quietest for the boat's roll (the EXO's floats stabilise it) and has no slack
by construction, at the price of ~1.2–1.4 kN alternating in each tube and no quick release. The six-line sketch with stern
knees and eyes at cleat height is within 10 % on peak load, keeps rope's quick release, and is the arrangement to build
first. Shock absorbers: the model only sees stiffness, so it cannot credit energy absorption; a rubber snubber on the
ropes is justified to hold T0 ≈ 400 N over trim changes, cartridges on tubes are not justified by these numbers.
