# EXO-01 ↔ L'Hydronaute coupling: what the study says (v1.2, 29 Oct 2026)

**Exploratory — assumed geometry and mass distribution; line and fender properties are assumptions, not measurements.**
Source: `scripts/run_mooring_study.py` → `results/mooring/` (121 configurations: 7 arrangements × 4 line stiffnesses ×
5 pretensions; moored / push 100 % / tow 100 %; three regular waves with the linear 12-DOF model and the tension-only
time-domain check). Element model: ASSUMPTIONS §5e.

## 1. The short version

| question | answer from the model | confidence |
|---|---|---|
| Which arrangement closes the force loop in push *and* tow? | Only the ones with **stern fenders (push bars) + lines that run from the EXO aft/forward posts to boat cleats on both sides**: `fenders_crossed_lines` or `fenders_diagonals`. Lines alone need k ≥ 10 kN/m and still let the boat slide 20–45 mm into the gap under push; the drawing's four forward lines never push. | high (statics) |
| Where must it be rigid? | **Longitudinally, at the transom** (the push goes through fenders in compression, never through rope in tension). **Not vertically**: let heave/pitch/roll of the two hulls stay free — a rigid vertical coupling carries ≈ 1.1–1.3 kN cyclic per strut in 0.3 m waves, continuously. Sway and yaw: restrained by crossed lines or diagonals in tension. | high |
| Shock absorbers? | **Yes on the lines, no on the fenders.** Line peaks scale with rope stiffness: 2 kN/m → 0.5–1.3 kN, 10 kN/m → 0.6–1.5 kN, 50 kN/m → 1.5–3 kN, 200 kN/m → 3–5 kN in the same 0.3 m waves. But *very* soft lines (2 kN/m) with fenders let the boat accelerate into the fenders: fender impacts 2–5 kN. Sweet spot: **lines ≈ 10 kN/m (elastic snubber or nylon) with firm fenders (≈ 50 kN/m)**. | medium (5 % damping, linear hydro, frozen coefficients) |
| Pretension? | **200–400 N** per line with 10 kN/m lines: slack fraction 20–30 % of the cycle in 0.3 m beam waves, peaks ≈ 0.7–1.3 kN. No-slack needs ≈ 800 N (then the static load alone is 0.8 kN, no benefit). Below 100 N every line snatches every cycle. | medium |
| Fender at the back? | **Yes: two push fenders/knees at the quarters (y ≈ ±0.9 m) at transom height**, stroke ≥ 50 mm (the gap breathes ± 0.02–0.05 m in 0.3 m waves, ± 0.14 m with crossed lines in 0.5 m waves), capacity ≥ 3 kN each (static push 0.3–0.6 kN each at full thrust, wave impacts 0.4–1.4 kN with 10 kN/m lines, up to 1.7 kN in 0.5 m waves). | medium |
| Hardware sizing | Lines: working load 1–1.5 kN, snatch peaks up to 2–4.5 kN with stiff rope in 0.5 m waves → 12 mm polyester/nylon with snubbers (MBL ≥ 2 t), cleats/posts and their frame attachment ≥ 5 kN. Fenders ≥ 3 kN. Rigid-coupling option: 4 struts ≥ 2 kN cyclic + fatigue. | medium |

Design consequence for EXO-01: build **two push knees with fenders on the rear deck edge** (x ≈ 2.1 m, y ≈ ±0.9 m, at the
transom height of the host boat) and keep the mooring posts; lines then only clamp the boat onto the knees and restrain
sway/yaw. That is the standard pusher-tug arrangement and it is what the numbers favour.

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

| arrangement | k [kN/m] | T0 [N] | peak line [N] | slack fraction | fender peak [N] | transom gap min [m] |
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
* The time-domain check with 1 MN/m struts is at the limit of the integrator (NaN in the 0.5 m case): use the linear strut
  amplitudes.
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

## 6. EXO-01 alone: registration sheet (DDTM / service instructeur)

`scripts/run_stability_sheet.py` → `results/stability/stability_sheet.md`. Values read against the ES-TRIN art. 19.03
passenger-vessel figures (75 kg per person, heel ≤ 12°, residual freeboard ≥ 0.20 m); whether that text or a lighter
regime applies to EXO-01 (< 12 passengers, work platform, "engin flottant") is for the service instructeur — the numbers
are the same either way.

* Heel is never the limit: GM_T ≈ 21 m; eight people on one side of the upper deck heel the platform 4°.
* **Freeboard is the limit.** Each 75 kg passenger sinks the platform ≈ 15 mm (waterplane ≈ 5.6 m²) plus the trim from
  where they stand. Rear-deck freeboard light: 0.17 m (drawing batteries) / 0.36 m (x 3.6) / 0.38 m (x 4.24).
* Capacity under "residual freeboard ≥ 0.20 m at the worst placement": **0 passengers** with the drawing's batteries,
  **1–2** with the batteries forward (limited by two people in the stern corner), 10 if everyone stays on the upper deck.
* Deck-edge-awash regular wave height, light ship, batteries forward: ≈ 0.27 m at T 2.0 s, 0.46 m at T 2.5 s, 0.68 m at
  T 3 s (linear, 5 % damping, worst heading — the short-period values are resonance-driven and need the decay test).

Consequence: as drawn, EXO-01 alone does not have the freeboard of a passenger craft; it has the freeboard of a work
platform for a crew of 1–2 on the rear deck. Options if passenger carriage is the goal: raise the rear deck freeboard
(third float row aft, longer/larger floats, or a higher deck), or restrict the lower deck and carry people on the upper
deck. In every case the registration file needs the measured light-ship weight, the inclining test and the float survey
before any of these numbers is quoted as a characteristic.
