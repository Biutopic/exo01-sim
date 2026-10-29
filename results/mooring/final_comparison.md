# Mooring — final comparison of the candidate arrangements

> Exploratory — assumed geometry and mass distribution; line/fender/tube properties are assumptions; no damping in elements.

All ropes k 10 kN/m, T0 400 N, EXO eyes at z 0.3 (cleat level) unless stated; fenders k 50 kN/m; tubes pinned at (2.1, ±0.9) → transom quarters, k = elastomer cartridge in series (1 MN/m = rigid). Waves: beam 0.3 m / 2.5 s, head 0.3 / 2.5, beam 0.5 / 3.0 (Erdre test case). Damping: radiation + assumed 5 % (boat roll/pitch 10 %).

Score (lower is better, a choice): worst element peak [kN] + 2 × slack fraction + 5 × transom overlap [m] + boat roll [°]/10 + |dx| [mm]/100; hard gate: push and tow must close.

| rank | id | elements | push dx [mm] | tow dx [mm] | worst peak [N] | slack frac | gap min [m] | boat roll [°] | score |
|---|---|---|---|---|---|---|---|---|---|
| 1 | C_four_tubes_rigid | 4 | -5 | 2 | 1261 | 0.0 | 0.015 | 4.3 | 1.741 |
| 2 | D_four_tubes_cartridge | 4 | -10 | 5 | 1379 | 0.0 | 0.014 | 8.2 | 2.3 |
| 3 | B_six_lines_knees | 8 | -5 | 7 | 1157 | 0.11 | 0.015 | 9.4 | 2.384 |
| 4 | A_fenders_diagonals_deck | 6 | -3 | 9 | 1261 | 0.33 | 0.02 | 9.7 | 2.97 |
| 5 | F_hybrid_tubes_100k_crossed | 6 | -5 | -3 | 1817 | 0.32 | 0.032 | 9.6 | 3.458 |
| 6 | G_hybrid_tubes_100k_diagonals | 6 | 0 | 1 | 1996 | 0.37 | 0.032 | 10.9 | 3.848 |
| 7 | A2_fenders_diagonals_cleat | 6 | -5 | 9 | 4196 | 0.47 | 0.012 | 10.1 | 6.237 |
| 8 | E_hybrid_tubes_50k_ropes10k | 4 | -11 | -4 | 3553 | 0.88 | 0.029 | 10.1 | 6.423 |
| 9 | E_hybrid_tubes_100k_ropes10k | 4 | -5 | -3 | 4917 | 0.84 | 0.03 | 10.1 | 7.664 |
| 10 | E_hybrid_tubes_200k_ropes10k | 4 | -1 | -2 | 5214 | 0.89 | 0.031 | 10.2 | 8.034 |
| 11 | E_hybrid_tubes_100k_snubber2k | 4 | -5 | -3 | 5777 | 0.7 | 0.03 | 10.1 | 8.232 |
| 12 | E_hybrid_tubes_rigid_ropes10k | 4 | -3 | -1 | 9190 | 0.91 | 0.032 | 10.5 | 12.081 |

## Per wave

| id | wave | line peak [N] | slack | fender peak [N] | fender free | tube peak [N] | gap min [m] | boat roll [°] |
|---|---|---|---|---|---|---|---|---|
| A_fenders_diagonals_deck | beam_03_25 | 1261 | 0.32 | 1141 | 0.64 | — | 0.047 | 9.0 |
| A_fenders_diagonals_deck | head_03_25 | 684 | 0.00 | 590 | 0.58 | — | 0.020 | 0.1 |
| A_fenders_diagonals_deck | beam_05_30 | 1162 | 0.33 | 691 | 0.67 | — | 0.045 | 9.7 |
| A2_fenders_diagonals_cleat | beam_03_25 | 1033 | 0.13 | 1030 | 0.65 | — | 0.042 | 9.3 |
| A2_fenders_diagonals_cleat | head_03_25 | 639 | 0.00 | 532 | 0.59 | — | 0.012 | 0.1 |
| A2_fenders_diagonals_cleat | beam_05_30 | 4196 | 0.47 | 1497 | 0.88 | — | 0.038 | 10.1 |
| B_six_lines_knees | beam_03_25 | 1157 | 0.11 | 1156 | 0.63 | — | 0.049 | 8.8 |
| B_six_lines_knees | head_03_25 | 647 | 0.00 | 434 | 0.41 | — | 0.015 | 0.1 |
| B_six_lines_knees | beam_05_30 | 908 | 0.00 | 549 | 0.53 | — | 0.048 | 9.4 |
| C_four_tubes_rigid | beam_03_25 | — | — | — | — | 1176 | 0.031 | 2.3 |
| C_four_tubes_rigid | head_03_25 | — | — | — | — | 1261 | 0.015 | 0.0 |
| C_four_tubes_rigid | beam_05_30 | — | — | — | — | nan | 0.028 | 4.3 |
| D_four_tubes_cartridge | beam_03_25 | — | — | — | — | 1127 | 0.021 | 5.7 |
| D_four_tubes_cartridge | head_03_25 | — | — | — | — | 1379 | 0.014 | 0.0 |
| D_four_tubes_cartridge | beam_05_30 | — | — | — | — | 1028 | 0.022 | 8.2 |
| E_hybrid_tubes_rigid_ropes10k | beam_03_25 | 1157 | 0.33 | — | — | 5274 | 0.054 | 9.7 |
| E_hybrid_tubes_rigid_ropes10k | head_03_25 | 587 | 0.15 | — | — | 1271 | 0.032 | 0.0 |
| E_hybrid_tubes_rigid_ropes10k | beam_05_30 | 1120 | 0.91 | — | — | 9190 | 0.051 | 10.5 |
| E_hybrid_tubes_200k_ropes10k | beam_03_25 | 848 | 0.89 | — | — | 4258 | 0.050 | 9.7 |
| E_hybrid_tubes_200k_ropes10k | head_03_25 | 436 | 0.13 | — | — | 657 | 0.031 | 0.1 |
| E_hybrid_tubes_200k_ropes10k | beam_05_30 | 1548 | 0.82 | — | — | 5214 | 0.050 | 10.2 |
| E_hybrid_tubes_100k_ropes10k | beam_03_25 | 1954 | 0.83 | — | — | 4917 | 0.047 | 9.6 |
| E_hybrid_tubes_100k_ropes10k | head_03_25 | 474 | 0.16 | — | — | 748 | 0.030 | 0.2 |
| E_hybrid_tubes_100k_ropes10k | beam_05_30 | 712 | 0.84 | — | — | 2702 | 0.047 | 10.1 |
| E_hybrid_tubes_50k_ropes10k | beam_03_25 | 1359 | 0.88 | — | — | 2967 | 0.045 | 9.6 |
| E_hybrid_tubes_50k_ropes10k | head_03_25 | 559 | 0.19 | — | — | 710 | 0.029 | 0.1 |
| E_hybrid_tubes_50k_ropes10k | beam_05_30 | 1559 | 0.84 | — | — | 3553 | 0.046 | 10.1 |
| E_hybrid_tubes_100k_snubber2k | beam_03_25 | 877 | 0.68 | — | — | 5777 | 0.051 | 9.7 |
| E_hybrid_tubes_100k_snubber2k | head_03_25 | 672 | 0.38 | — | — | 3578 | 0.030 | 0.0 |
| E_hybrid_tubes_100k_snubber2k | beam_05_30 | 638 | 0.70 | — | — | 2658 | 0.052 | 10.1 |
| F_hybrid_tubes_100k_crossed | beam_03_25 | 1535 | 0.32 | — | — | 1817 | 0.051 | 9.0 |
| F_hybrid_tubes_100k_crossed | head_03_25 | 569 | 0.15 | — | — | 741 | 0.032 | 0.0 |
| F_hybrid_tubes_100k_crossed | beam_05_30 | 1057 | 0.05 | — | — | 1371 | 0.052 | 9.6 |
| G_hybrid_tubes_100k_diagonals | beam_03_25 | 1987 | 0.37 | — | — | 1996 | 0.053 | 9.4 |
| G_hybrid_tubes_100k_diagonals | head_03_25 | 1024 | 0.00 | — | — | 504 | 0.032 | 0.0 |
| G_hybrid_tubes_100k_diagonals | beam_05_30 | 1373 | 0.10 | — | — | 1008 | 0.043 | 10.9 |

## Static

| id | case | ok | dx [mm] | yaw [°] | line max [N] | fender max [N] | tube max [N] | slack |
|---|---|---|---|---|---|---|---|---|
| A_fenders_diagonals_deck | moored | True | 2 | -0.01 | 391 | 45 | — | — |
| A_fenders_diagonals_deck | push | True | -3 | 0.01 | 435 | 354 | — | — |
| A_fenders_diagonals_deck | tow | True | 9 | -0.00 | 471 | -0 | — | FENDER_PORT, FENDER_STBD |
| A2_fenders_diagonals_cleat | moored | True | 1 | -0.00 | 398 | 30 | — | — |
| A2_fenders_diagonals_cleat | push | True | -5 | 0.02 | 446 | 366 | — | — |
| A2_fenders_diagonals_cleat | tow | True | 9 | 0.00 | 484 | -0 | — | FENDER_PORT, FENDER_STBD |
| B_six_lines_knees | moored | True | 1 | -0.00 | 396 | 68 | — | — |
| B_six_lines_knees | push | True | -5 | 0.01 | 440 | 401 | — | — |
| B_six_lines_knees | tow | True | 7 | 0.00 | 461 | -0 | — | FENDER_PORT, FENDER_STBD |
| C_four_tubes_rigid | moored | True | 0 | 0.00 | — | — | 0 | — |
| C_four_tubes_rigid | push | True | -5 | 0.00 | — | — | 581 | — |
| C_four_tubes_rigid | tow | True | 2 | -0.00 | — | — | 255 | — |
| D_four_tubes_cartridge | moored | True | 0 | 0.00 | — | — | 0 | — |
| D_four_tubes_cartridge | push | True | -10 | 0.00 | — | — | 554 | — |
| D_four_tubes_cartridge | tow | True | 5 | -0.00 | — | — | 240 | — |
| E_hybrid_tubes_rigid_ropes10k | moored | True | -0 | -0.00 | 400 | — | 357 | — |
| E_hybrid_tubes_rigid_ropes10k | push | True | -3 | -0.05 | 601 | — | 1679 | — |
| E_hybrid_tubes_rigid_ropes10k | tow | True | -1 | -0.00 | 396 | — | 166 | — |
| E_hybrid_tubes_200k_ropes10k | moored | True | -2 | -0.01 | 390 | — | 354 | — |
| E_hybrid_tubes_200k_ropes10k | push | True | -1 | 0.01 | 376 | — | 775 | — |
| E_hybrid_tubes_200k_ropes10k | tow | True | -2 | -0.01 | 391 | — | 161 | — |
| E_hybrid_tubes_100k_ropes10k | moored | True | -3 | -0.03 | 384 | — | 370 | — |
| E_hybrid_tubes_100k_ropes10k | push | True | -5 | 0.01 | 343 | — | 739 | — |
| E_hybrid_tubes_100k_ropes10k | tow | True | -3 | -0.01 | 385 | — | 156 | — |
| E_hybrid_tubes_50k_ropes10k | moored | True | -6 | 0.04 | 356 | — | 332 | — |
| E_hybrid_tubes_50k_ropes10k | push | True | -11 | 0.01 | 287 | — | 687 | — |
| E_hybrid_tubes_50k_ropes10k | tow | True | -4 | -0.01 | 374 | — | 148 | — |
| E_hybrid_tubes_100k_snubber2k | moored | True | -3 | 0.00 | 396 | — | 346 | — |
| E_hybrid_tubes_100k_snubber2k | push | True | -5 | 0.01 | 388 | — | 773 | — |
| E_hybrid_tubes_100k_snubber2k | tow | True | -3 | -0.03 | 406 | — | 204 | — |
| F_hybrid_tubes_100k_crossed | moored | True | -4 | -0.00 | 391 | — | 357 | — |
| F_hybrid_tubes_100k_crossed | push | True | -5 | -0.00 | 400 | — | 775 | — |
| F_hybrid_tubes_100k_crossed | tow | True | -3 | -0.00 | 386 | — | 192 | — |
| G_hybrid_tubes_100k_diagonals | moored | True | 1 | -0.00 | 398 | — | 31 | — |
| G_hybrid_tubes_100k_diagonals | push | True | 0 | 0.00 | 414 | — | 431 | — |
| G_hybrid_tubes_100k_diagonals | tow | True | 1 | -0.00 | 410 | — | 141 | — |

## Titles

- `A_fenders_diagonals_deck` — Study best: 2 stern fenders + diagonals, eyes at deck level (reference)
- `A2_fenders_diagonals_cleat` — Same, eyes raised to cleat level (+0.3 m)
- `B_six_lines_knees` — Elven's six-line sketch + stern knees/fenders, eyes at cleat level
- `C_four_tubes_rigid` — Four rigid tubes (study limit case, k 1 MN/m)
- `D_four_tubes_cartridge` — Four tubes with elastomer cartridges (k 100 kN/m)
- `E_hybrid_tubes_rigid_ropes10k` — Hybrid: 2 tubes aft (rigid) + 2 ropes fwd posts->midship (k 10k, T0 400)
- `E_hybrid_tubes_200k_ropes10k` — Hybrid: 2 tubes aft (200k) + 2 ropes fwd posts->midship (k 10k, T0 400)
- `E_hybrid_tubes_100k_ropes10k` — Hybrid: 2 tubes aft (100k) + 2 ropes fwd posts->midship (k 10k, T0 400)
- `E_hybrid_tubes_50k_ropes10k` — Hybrid: 2 tubes aft (50k) + 2 ropes fwd posts->midship (k 10k, T0 400)
- `E_hybrid_tubes_100k_snubber2k` — Hybrid: 2 tubes aft (100k) + 2 ropes with snubber (k 2k, T0 400)
- `F_hybrid_tubes_100k_crossed` — Hybrid: 2 tubes aft (100k) + crossed stern ropes + tow ropes (k 10k, T0 400)
- `G_hybrid_tubes_100k_diagonals` — Hybrid: 2 tubes aft (100k) + diagonals (aft->mid, fwd->stern), k 10k T0 400
