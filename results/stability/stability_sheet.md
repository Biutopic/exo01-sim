# EXO-01 alone — flotation and stability sheet (Exploratory — assumed geometry and mass distribution; not a measured stability test.)

Passenger mass 75 kg. Criteria used to read the tables (orders of magnitude, to be confirmed with the service instructeur): heel ≤ 12° under crowding, residual freeboard ≥ 0.20 m at the rear deck edge. Nothing here replaces the weighing and the inclining test.

## Batteries: figure_x1.43

Light ship: 856 kg listed, draught 0.37 m, trim -3.83°, heel -0.18°, rear-deck freeboard 0.17 m, float-top freeboard 0.31 m, GM_T 20.6 m, GM_L 9.4 m, KG 0.64 m.

Wind heel estimate (0.25 kN/m² on an ASSUMED 6 m² lateral area at 1.5 m): 0.75° light ship.

| load case | max passengers (19.03: residual fb ≥ 0.20 m, heel+wind ≤ 12°) | max passengers if fb ≥ 0.30 m (19.04 minimum) | limited by |
|---|---|---|---|
| rear_deck_spread | 0 | 0 | — |
| upper_deck_spread | 0 | 0 | — |
| both_decks_spread | 0 | 0 | — |
| rear_deck_one_side | 0 | 0 | — |
| upper_deck_one_side | 0 | 0 | — |
| rear_deck_stern_corner | 0 | 0 | — |
| zoned_rear_deck_fwd_spread | 0 | 0 | — |
| zoned_rear_deck_fwd_one_side | 0 | 0 | — |
| zoned_both_decks_spread | 0 | 0 | — |

**Capacity, passengers anywhere: 0 (residual fb 0.20 m) / 0 (fb 0.30 m). With the aft 1.0 m of the rear deck closed to passengers: 0 / 0.** The worst placement governs.
Counterweight what-if ({'added_kg': 100, 'at_x_m': 4.6, 'people': '4 in the stern corner', 'without': {'trim_deg': None, 'deck_fb_m': None}, 'with_cw': 'no equilibrium'}).

| load case | n | heel [°] | trim [°] | deck freeboard [m] | float-top freeboard [m] |
|---|---|---|---|---|---|
| rear_deck_spread | 1 | -0.2 | -4.9 | 0.10 | 0.28 |
| rear_deck_spread | 2 | -0.2 | -6.0 | 0.03 | 0.25 |
| upper_deck_spread | 1 | -0.2 | -3.9 | 0.15 | 0.29 |
| upper_deck_spread | 2 | -0.2 | -4.0 | 0.13 | 0.28 |
| upper_deck_spread | 4 | -0.2 | -4.3 | 0.09 | 0.24 |
| upper_deck_spread | 6 | -0.2 | -4.7 | 0.04 | 0.21 |
| upper_deck_spread | 8 | -0.2 | -5.3 | -0.03 | 0.17 |
| both_decks_spread | 1 | -0.2 | -4.9 | 0.10 | 0.28 |
| both_decks_spread | 2 | -0.2 | -5.0 | 0.08 | 0.27 |
| both_decks_spread | 4 | -0.2 | -6.4 | -0.02 | 0.22 |
| rear_deck_one_side | 1 | -0.7 | -4.9 | 0.08 | 0.27 |
| rear_deck_one_side | 2 | -1.2 | -6.2 | -0.01 | 0.22 |
| upper_deck_one_side | 1 | -0.6 | -4.0 | 0.13 | 0.28 |
| upper_deck_one_side | 2 | -1.1 | -4.1 | 0.09 | 0.24 |
| upper_deck_one_side | 4 | -2.2 | -4.7 | -0.01 | 0.17 |
| rear_deck_stern_corner | 1 | -0.7 | -5.3 | 0.06 | 0.26 |
| rear_deck_stern_corner | 2 | -1.4 | -7.5 | -0.08 | 0.20 |
| zoned_rear_deck_fwd_spread | 1 | -0.2 | -4.7 | 0.11 | 0.29 |
| zoned_rear_deck_fwd_spread | 2 | -0.2 | -5.6 | 0.06 | 0.26 |
| zoned_rear_deck_fwd_spread | 4 | -0.2 | -7.9 | -0.09 | 0.20 |
| zoned_rear_deck_fwd_one_side | 1 | -0.7 | -4.7 | 0.09 | 0.27 |
| zoned_rear_deck_fwd_one_side | 2 | -1.2 | -5.7 | 0.01 | 0.23 |
| zoned_both_decks_spread | 1 | -0.2 | -4.7 | 0.11 | 0.29 |
| zoned_both_decks_spread | 2 | -0.2 | -4.8 | 0.09 | 0.27 |
| zoned_both_decks_spread | 4 | -0.2 | -5.9 | 0.00 | 0.22 |
| zoned_both_decks_spread | 6 | +0.7 | -9.3 | -0.22 | 0.12 |

Deck-edge-awash regular wave height (linear relative motion at the worst rear-deck corner, scaled from H 0.3 m; linear theory, read values above ~0.6 m as 'outside the model'):

| loading | T 1.5 s | T 2.0 s | T 2.5 s | T 3.0 s | T 4.0 s |
|---|---|---|---|---|---|
| light_ship_no_crew | 0.17 (β 45°) | 0.10 (β 0°) | 0.20 (β 0°) | 0.32 (β 45°) | 0.64 (β 45°) |
| 1_passengers_zoned_both_decks | 0.13 (β 45°) | 0.06 (β 0°) | 0.12 (β 0°) | 0.22 (β 135°) | 0.47 (β 135°) |

## Batteries: float_frame_x3.60

Light ship: 856 kg listed, draught 0.24 m, trim +0.12°, heel -0.17°, rear-deck freeboard 0.36 m, float-top freeboard 0.36 m, GM_T 21.9 m, GM_L 9.2 m, KG 0.64 m.

Wind heel estimate (0.25 kN/m² on an ASSUMED 6 m² lateral area at 1.5 m): 0.70° light ship.

| load case | max passengers (19.03: residual fb ≥ 0.20 m, heel+wind ≤ 12°) | max passengers if fb ≥ 0.30 m (19.04 minimum) | limited by |
|---|---|---|---|
| rear_deck_spread | 2 | 1 | deck freeboard |
| upper_deck_spread | 10 | 4 | — |
| both_decks_spread | 4 | 1 | deck freeboard |
| rear_deck_one_side | 2 | 0 | deck freeboard |
| upper_deck_one_side | 4 | 1 | deck freeboard |
| rear_deck_stern_corner | 1 | 0 | deck freeboard |
| zoned_rear_deck_fwd_spread | 3 | 1 | deck freeboard |
| zoned_rear_deck_fwd_one_side | 2 | 0 | deck freeboard |
| zoned_both_decks_spread | 4 | 1 | deck freeboard |

**Capacity, passengers anywhere: 1 (residual fb 0.20 m) / 0 (fb 0.30 m). With the aft 1.0 m of the rear deck closed to passengers: 2 / 0.** The worst placement governs.
Counterweight what-if ({'added_kg': 100, 'at_x_m': 4.6, 'people': '4 in the stern corner', 'without': {'trim_deg': -5.635822027908912, 'deck_fb_m': -0.05884350903243618}, 'with_cw': {'trim_deg': -4.013481700248241, 'deck_fb_m': 0.006291845648507044}}).

| load case | n | heel [°] | trim [°] | deck freeboard [m] | float-top freeboard [m] |
|---|---|---|---|---|---|
| rear_deck_spread | 1 | -0.2 | -0.8 | 0.30 | 0.33 |
| rear_deck_spread | 2 | -0.2 | -1.7 | 0.24 | 0.31 |
| rear_deck_spread | 4 | -0.2 | -3.7 | 0.12 | 0.25 |
| rear_deck_spread | 6 | -0.2 | -6.0 | -0.03 | 0.19 |
| upper_deck_spread | 1 | -0.2 | +0.1 | 0.35 | 0.34 |
| upper_deck_spread | 2 | -0.2 | +0.1 | 0.33 | 0.33 |
| upper_deck_spread | 4 | -0.2 | +0.0 | 0.30 | 0.30 |
| upper_deck_spread | 6 | -0.2 | -0.0 | 0.27 | 0.27 |
| upper_deck_spread | 8 | -0.2 | -0.1 | 0.24 | 0.24 |
| upper_deck_spread | 10 | -0.2 | -0.2 | 0.20 | 0.21 |
| both_decks_spread | 1 | -0.2 | -0.8 | 0.30 | 0.33 |
| both_decks_spread | 2 | -0.2 | -0.8 | 0.29 | 0.32 |
| both_decks_spread | 4 | -0.2 | -1.9 | 0.21 | 0.28 |
| both_decks_spread | 6 | +0.4 | -3.4 | 0.09 | 0.22 |
| both_decks_spread | 8 | -0.2 | -4.4 | 0.02 | 0.18 |
| rear_deck_one_side | 1 | -0.6 | -0.8 | 0.29 | 0.32 |
| rear_deck_one_side | 2 | -1.0 | -1.7 | 0.21 | 0.28 |
| rear_deck_one_side | 4 | -2.0 | -3.8 | 0.04 | 0.19 |
| upper_deck_one_side | 1 | -0.6 | +0.1 | 0.33 | 0.33 |
| upper_deck_one_side | 2 | -1.0 | +0.0 | 0.30 | 0.30 |
| upper_deck_one_side | 4 | -2.0 | -0.1 | 0.23 | 0.24 |
| upper_deck_one_side | 6 | -3.0 | -0.2 | 0.15 | 0.17 |
| upper_deck_one_side | 8 | -4.2 | -0.5 | 0.05 | 0.09 |
| rear_deck_stern_corner | 1 | -0.6 | -1.2 | 0.27 | 0.32 |
| rear_deck_stern_corner | 2 | -1.0 | -2.5 | 0.17 | 0.27 |
| rear_deck_stern_corner | 4 | -2.2 | -5.6 | -0.06 | 0.16 |
| zoned_rear_deck_fwd_spread | 1 | -0.2 | -0.6 | 0.31 | 0.34 |
| zoned_rear_deck_fwd_spread | 2 | -0.2 | -1.4 | 0.26 | 0.31 |
| zoned_rear_deck_fwd_spread | 3 | +0.1 | -2.3 | 0.20 | 0.29 |
| zoned_rear_deck_fwd_spread | 4 | -0.2 | -3.0 | 0.15 | 0.26 |
| zoned_rear_deck_fwd_spread | 6 | -0.2 | -4.7 | 0.03 | 0.21 |
| zoned_rear_deck_fwd_spread | 8 | -0.2 | -7.5 | -0.15 | 0.13 |
| zoned_rear_deck_fwd_one_side | 1 | -0.6 | -0.6 | 0.30 | 0.32 |
| zoned_rear_deck_fwd_one_side | 2 | -1.0 | -1.4 | 0.23 | 0.28 |
| zoned_rear_deck_fwd_one_side | 4 | -2.0 | -3.1 | 0.08 | 0.20 |
| zoned_rear_deck_fwd_one_side | 6 | -3.3 | -5.6 | -0.14 | 0.08 |
| zoned_both_decks_spread | 1 | -0.2 | -0.6 | 0.31 | 0.34 |
| zoned_both_decks_spread | 2 | -0.2 | -0.7 | 0.30 | 0.32 |
| zoned_both_decks_spread | 4 | -0.2 | -1.5 | 0.23 | 0.28 |
| zoned_both_decks_spread | 6 | +0.4 | -2.8 | 0.12 | 0.23 |
| zoned_both_decks_spread | 8 | -0.2 | -3.5 | 0.06 | 0.19 |

Deck-edge-awash regular wave height (linear relative motion at the worst rear-deck corner, scaled from H 0.3 m; linear theory, read values above ~0.6 m as 'outside the model'):

| loading | T 1.5 s | T 2.0 s | T 2.5 s | T 3.0 s | T 4.0 s |
|---|---|---|---|---|---|
| light_ship_no_crew | 0.29 (β 45°) | 0.27 (β 0°) | 0.46 (β 45°) | 0.68 (β 45°) | 1.36 (β 45°) |
| 2_passengers_zoned_both_decks | 0.25 (β 45°) | 0.19 (β 0°) | 0.36 (β 45°) | 0.56 (β 45°) | 1.18 (β 45°) |

## Batteries: end_frame_x4.24

Light ship: 856 kg listed, draught 0.29 m, trim +1.24°, heel -0.17°, rear-deck freeboard 0.38 m, float-top freeboard 0.34 m, GM_T 21.8 m, GM_L 9.3 m, KG 0.64 m.

Wind heel estimate (0.25 kN/m² on an ASSUMED 6 m² lateral area at 1.5 m): 0.70° light ship.

| load case | max passengers (19.03: residual fb ≥ 0.20 m, heel+wind ≤ 12°) | max passengers if fb ≥ 0.30 m (19.04 minimum) | limited by |
|---|---|---|---|
| rear_deck_spread | 3 | 1 | deck freeboard |
| upper_deck_spread | 10 | 5 | — |
| both_decks_spread | 4 | 2 | deck freeboard |
| rear_deck_one_side | 2 | 1 | deck freeboard |
| upper_deck_one_side | 5 | 2 | deck freeboard |
| rear_deck_stern_corner | 2 | 1 | deck freeboard |
| zoned_rear_deck_fwd_spread | 4 | 2 | deck freeboard |
| zoned_rear_deck_fwd_one_side | 3 | 1 | deck freeboard |
| zoned_both_decks_spread | 5 | 3 | deck freeboard |

**Capacity, passengers anywhere: 2 (residual fb 0.20 m) / 1 (fb 0.30 m). With the aft 1.0 m of the rear deck closed to passengers: 3 / 1.** The worst placement governs.
Counterweight what-if ({'added_kg': 100, 'at_x_m': 4.6, 'people': '4 in the stern corner', 'without': {'trim_deg': -4.162921545541936, 'deck_fb_m': 0.019405263527470518}, 'with_cw': {'trim_deg': -2.7528578672720623, 'deck_fb_m': 0.0724678253020058}}).

| load case | n | heel [°] | trim [°] | deck freeboard [m] | float-top freeboard [m] |
|---|---|---|---|---|---|
| rear_deck_spread | 1 | -0.2 | +0.3 | 0.35 | 0.34 |
| rear_deck_spread | 2 | -0.2 | -0.6 | 0.30 | 0.32 |
| rear_deck_spread | 3 | +0.1 | -1.7 | 0.23 | 0.29 |
| rear_deck_spread | 4 | -0.2 | -2.5 | 0.18 | 0.27 |
| rear_deck_spread | 6 | -0.2 | -4.6 | 0.04 | 0.21 |
| rear_deck_spread | 8 | -0.2 | -8.1 | -0.18 | 0.11 |
| upper_deck_spread | 1 | -0.2 | +1.2 | 0.36 | 0.33 |
| upper_deck_spread | 2 | -0.2 | +1.2 | 0.35 | 0.31 |
| upper_deck_spread | 4 | -0.2 | +1.2 | 0.32 | 0.28 |
| upper_deck_spread | 6 | -0.2 | +1.3 | 0.29 | 0.25 |
| upper_deck_spread | 8 | -0.2 | +1.3 | 0.26 | 0.22 |
| upper_deck_spread | 10 | -0.2 | +1.4 | 0.23 | 0.19 |
| both_decks_spread | 1 | -0.2 | +0.3 | 0.35 | 0.34 |
| both_decks_spread | 2 | -0.2 | +0.3 | 0.33 | 0.33 |
| both_decks_spread | 4 | -0.2 | -0.7 | 0.27 | 0.29 |
| both_decks_spread | 6 | +0.4 | -2.1 | 0.16 | 0.24 |
| both_decks_spread | 8 | -0.2 | -3.0 | 0.09 | 0.20 |
| rear_deck_one_side | 1 | -0.6 | +0.3 | 0.33 | 0.33 |
| rear_deck_one_side | 2 | -1.0 | -0.6 | 0.27 | 0.29 |
| rear_deck_one_side | 4 | -1.9 | -2.6 | 0.10 | 0.21 |
| rear_deck_one_side | 6 | -3.3 | -5.3 | -0.12 | 0.09 |
| upper_deck_one_side | 1 | -0.6 | +1.2 | 0.34 | 0.31 |
| upper_deck_one_side | 2 | -1.0 | +1.2 | 0.31 | 0.28 |
| upper_deck_one_side | 4 | -2.0 | +1.2 | 0.25 | 0.22 |
| upper_deck_one_side | 5 | -2.5 | +1.2 | 0.21 | 0.19 |
| upper_deck_one_side | 6 | -3.0 | +1.2 | 0.18 | 0.16 |
| upper_deck_one_side | 8 | -4.2 | +1.3 | 0.09 | 0.08 |
| rear_deck_stern_corner | 1 | -0.6 | -0.0 | 0.33 | 0.33 |
| rear_deck_stern_corner | 2 | -1.0 | -1.3 | 0.23 | 0.28 |
| rear_deck_stern_corner | 4 | -2.0 | -4.2 | 0.02 | 0.18 |
| zoned_rear_deck_fwd_spread | 1 | -0.2 | +0.5 | 0.35 | 0.34 |
| zoned_rear_deck_fwd_spread | 2 | -0.2 | -0.3 | 0.32 | 0.33 |
| zoned_rear_deck_fwd_spread | 4 | -0.2 | -1.8 | 0.21 | 0.28 |
| zoned_rear_deck_fwd_spread | 6 | -0.2 | -3.4 | 0.10 | 0.23 |
| zoned_rear_deck_fwd_spread | 8 | -0.2 | -5.4 | -0.03 | 0.16 |
| zoned_rear_deck_fwd_one_side | 1 | -0.6 | +0.5 | 0.33 | 0.32 |
| zoned_rear_deck_fwd_one_side | 2 | -1.0 | -0.3 | 0.28 | 0.30 |
| zoned_rear_deck_fwd_one_side | 3 | -1.5 | -1.1 | 0.21 | 0.26 |
| zoned_rear_deck_fwd_one_side | 4 | -1.9 | -1.9 | 0.14 | 0.22 |
| zoned_rear_deck_fwd_one_side | 6 | -3.0 | -3.8 | -0.03 | 0.12 |
| zoned_both_decks_spread | 1 | -0.2 | +0.5 | 0.35 | 0.34 |
| zoned_both_decks_spread | 2 | -0.2 | +0.5 | 0.34 | 0.32 |
| zoned_both_decks_spread | 4 | -0.2 | -0.3 | 0.28 | 0.30 |
| zoned_both_decks_spread | 5 | +0.1 | -1.3 | 0.22 | 0.27 |
| zoned_both_decks_spread | 6 | +0.4 | -1.5 | 0.19 | 0.24 |
| zoned_both_decks_spread | 8 | -0.2 | -2.2 | 0.13 | 0.21 |

Deck-edge-awash regular wave height (linear relative motion at the worst rear-deck corner, scaled from H 0.3 m; linear theory, read values above ~0.6 m as 'outside the model'):

| loading | T 1.5 s | T 2.0 s | T 2.5 s | T 3.0 s | T 4.0 s |
|---|---|---|---|---|---|
| light_ship_no_crew | 0.34 (β 45°) | 0.29 (β 0°) | 0.50 (β 45°) | 0.74 (β 45°) | 1.39 (β 45°) |
| 3_passengers_zoned_both_decks | 0.28 (β 45°) | 0.17 (β 0°) | 0.35 (β 45°) | 0.55 (β 45°) | 1.16 (β 45°) |
