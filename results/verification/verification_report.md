# Numerical verification report — EXO-01 exploratory model

Generated 2026-10-29 09:59:00 · pytest: 84 passed in 96.62s (0:01:36) · overall: **ALL CHECKS PASSED** (824 s)

Verification = the code solves its own equations to the stated tolerance. It is **not** validation against the physical EXO-01 (no measurement exists yet).

| # | check | acceptance | actual | result |
|---|---|---|---|---|
| 1 | STEP unit = mm and extent (max side) equals GLB metres | <= 3 mm | unit=mm, max |dx| = 0.000 mm | PASS |
| 2 | CAD->glTF conversion (x,y,z)->(x,z,-y), applied once | exact | max error 4.4e-16 | PASS |
| 3 | GLB child bounds equal documented CAD bounds (no 2nd axis conversion) | <= 1e-6 m | 0.0e+00 m | PASS |
| 4 | Mass accounting: sum of 16 parents counted once | 840 kg exactly | 840.0 kg; stray child masses: [] | PASS |
| 5 | Revision-3 float proxies (scenario floats_glb_capsules: capsules fitted to the GLB) vs GLB tessellated volume | <= 1.5 % | capsules 2.1236 m3 vs GLB 2.1097 m3 (+0.66 %) | PASS |
| 6 | Production floats (Flofiz 1.60 x D0.60 m, component list) vs GLB proxies: volume difference reported | informational | Flofiz 2.4597 m3 vs GLB 2.1097 m3 (+16.59 %): the drawing's proxies are smaller than the real floats | PASS |
| 7 | Analytic buoyancy test body (capsule, 5 waterlines): volume | <= 1e-3 (default tessellation) | 5.02e-04 | PASS |
| 8 | Analytic buoyancy test body: waterplane area | <= 1e-3 | 5.40e-04 | PASS |
| 9 | Flofiz float surface (both nose directions): closed, outward, volume vs analytic | <= 2e-4 | 7.38e-05 | PASS |
| 10 | Equilibrium residuals [baseline_illustrative] | |Fz|,|Mx|,|My| <= 1e-9 * M g | max 1.1e-15 (Fz 9.1e-12 N, Mx 7.1e-12, My -3.8e-12 N m) | PASS |
| 11 | Equilibrium residuals [battery_relocated] | |Fz|,|Mx|,|My| <= 1e-9 * M g | max 2.1e-15 (Fz -3.6e-12 N, Mx 1.8e-11, My 2.0e-12 N m) | PASS |
| 12 | Equilibrium residuals [occupants_symmetric] | |Fz|,|Mx|,|My| <= 1e-9 * M g | max 2.4e-15 (Fz 2.4e-11 N, Mx -2.2e-12, My -1.5e-11 N m) | PASS |
| 13 | Equilibrium residuals [occupants_asymmetric] | |Fz|,|Mx|,|My| <= 1e-9 * M g | max 3.9e-15 (Fz 1.3e-11 N, Mx -3.0e-11, My -3.9e-11 N m) | PASS |
| 14 | Deliberately symmetric load: heel and port/starboard float volumes | |heel| <= 1e-10 rad, |dV| <= 1e-12 m3 | heel -1.1e-18 rad, max dV 2.8e-17 m3 | PASS |
| 15 | Equilibrium mesh convergence (fine vs finer) | |d draft| <= 5e-4 m, |d trim| <= 0.01 deg | d draft 7.8e-06 m, d trim 2.7e-04 deg | PASS |
| 16 | BEM panel-size convergence: default h=0.12 vs h=0.08 (A, B, F on 3 omegas) | <= 3 % | worst relative change 1.50 % | PASS |
| 17 | Frequency-grid resolution OUTSIDE gap-resonance bands (app default grid vs reference nodes) | <= 2 % (set at the BEM panel-convergence level) | max 1.414 % | PASS |
| 18 | Frequency-grid resolution INSIDE gap-resonance bands (app default grid) | reported, no acceptance: potential-flow resonances are sharp and physically over-predicted; results there are flagged in the UI | max 1.9 % | PASS |
| 19 | Heading interpolation fallback (30 deg grid) - informational, not used for results | reported only | err/peak by omega: w=1.0: 0.0%, w=2.0: 0.1%, w=3.0: 2.4%, w=4.5: 37.3%, w=6.0: 84.8% | PASS |
| 20 | Time integration (RK4, fixed coefficients) vs frequency-domain solve | error decreases ~dt^4; <= 1e-4 at T/64 | errors ['1.7e-01', '4.9e-03', '2.6e-04', '1.4e-05', '8.3e-07'], observed orders [5.1, 4.2, 4.2, 4.1] | PASS |
| 21 | Boat hull proxy: closed, consistently oriented, volume invariant under subdivision (ruled surface) | closed; |dV/V| <= 1e-9 | closed=True, consistent=True, V=22.4888 m3, |dV/V|=6.7e-16 | PASS |
| 22 | Boat alone: equilibrium residuals (2100 kg archival, proxy hull) | <= 1e-9 * M g | 5.4e-12; draft 0.381 m, GM_T 3.14 m | PASS |
| 23 | EXO + boat coupled static equilibrium (buoyancy + weight + tension-only lines): residual and force consistency | residual <= 1e-8 Mg; EXO hydrostatic imbalance == -vertical line force | residual 2.9e-15, lines LINE_AFT_PORT 88 N, LINE_AFT_STBD 88 N, SPRING_PORT 43 N, SPRING_STBD 43 N, boat shift 7 mm, EXO hydrostatic Fz -125.6 N vs line Fz 125.6 N | PASS |
| 24 | Line-spring stiffness: symmetric PSD, rigid translation/rotation of both bodies in its null space | <= 1e-9 (relative) | sym=True, min eig/max = -7.1e-17, null-space residual 8.1e-17 | PASS |
| 25 | Two-body BEM panel convergence: default (0.20/0.30 m) vs finer (0.15/0.22 m), omegas 1-3 rad/s | <= 8 % (reported; the 0.18 m hull-float gap is under-resolved by construction) | worst relative change 5.6 % | PASS |
| 26 | Two-body symmetric configuration: beam seas from +Y vs -Y give even heave / odd sway & roll on both bodies | <= 5e-3 (lid/clipped panels are not mirror-exact at 0.2-0.3 m) | heave 1.1e-03, sway/roll 1.1e-03 | PASS |
| 27 | Two-body (12 DOF) RK4 time integration vs frequency-domain amplitudes | decreasing, <= 1e-4 at T/64 | errors ['3.6e-03', '2.0e-04', '1.3e-05'] | PASS |
| 28 | Propulsion (EXO pods 100 %, default lines): lines carry the boat's resistance | <= 1e-3 relative | line Fx on boat 868.8 N vs R_boat 868.8 N (rel 4.5e-05); U 2.79 m/s, trim -5.11 deg, aft lines slack ['LINE_AFT_PORT', 'LINE_AFT_STBD'] | PASS |
| 29 | Propulsion: four-lines-all-forward arrangement cannot carry the push without contact (no physical equilibrium, flagged) | physical=False: no equilibrium, or one only with the boat slid into the EXO structure (INTERFERENCE) | converged=True, physical=False, boat shift dx -851 mm, flags: ['INTERFERENCE: boat transom 0.79 m over the EXO rear deck plate'] | PASS |
| 30 | Propulsion (EXO alone 50 %): equilibrium residual including the thrust/drag wrench | <= 1e-8 Mg | 8.4e-13 | PASS |
| 31 | BEM computed about the CAD origin and moved to the COM (exact transform) vs direct solves about two COMs | <= 1e-9 | 1.4e-15 | PASS |

## Tessellation convergence of the analytic buoyancy test body (capsule r=0.29 m, L=1.6 m, five waterlines)

| n_circ | n_axial | n_cap | triangles | max rel. error volume | max rel. error waterplane area |
|---|---|---|---|---|---|
| 16 | 4 | 4 | 352 | 1.66e-02 | 2.94e-02 |
| 32 | 6 | 8 | 1344 | 4.28e-03 | 8.22e-03 |
| 64 | 12 | 16 | 5504 | 1.10e-03 | 2.34e-03 |
| 96 | 12 | 24 | 11328 | 5.02e-04 | 5.40e-04 |
| 192 | 24 | 48 | 45696 | 1.29e-04 | 1.47e-04 |

## Equilibrium vs float tessellation (illustrative configuration)

| resolution | trim [deg] | heel [deg] | max draft [m] | min deck freeboard [m] | displaced volume [m3] |
|---|---|---|---|---|---|
| {'n_circ': 24, 'n_axial': 4, 'n_cap': 6} | -3.83121 | -0.17615 | 0.37615 | 0.16984 | 0.856857 |
| {'n_circ': 48, 'n_axial': 8, 'n_cap': 12} | -3.82664 | -0.17604 | 0.37447 | 0.17030 | 0.856857 |
| {'n_circ': 96, 'n_axial': 16, 'n_cap': 24} | -3.82554 | -0.17600 | 0.37405 | 0.17041 | 0.856857 |
| {'n_circ': 192, 'n_axial': 32, 'n_cap': 48} | -3.82527 | -0.17599 | 0.37404 | 0.17044 | 0.856857 |

## BEM panel-size convergence (omegas [0.8, 2.0, 3.5] rad/s; relative change vs the finest mesh h=0.08 m)

| panel size [m] | faces | A33 | B33 | A44 | A55 | F3 head 0 | F4 beam | F2 beam | F5 head 0 |
|---|---|---|---|---|---|---|---|---|---|
| 0.2 | 806 | 1.8% / 2.0% / 1.9% | 1.3% / 1.4% / 1.8% | 2.2% / 2.1% / 2.9% | 1.5% / 1.5% / 1.9% | 0.2% / 0.3% / 1.3% | 0.4% / 0.9% / 1.3% | 2.1% / 2.1% / 3.5% | 0.6% / 1.1% / 0.9% |
| 0.15 | 1056 | 1.7% / 2.0% / 1.9% | 1.3% / 1.3% / 1.0% | 2.2% / 2.0% / 3.7% | 1.4% / 1.4% / 1.7% | 0.2% / 0.3% / 0.3% | 0.4% / 0.9% / 1.1% | 2.0% / 2.1% / 3.3% | 0.6% / 1.0% / 1.0% |
| 0.12 | 1527 | 0.6% / 0.7% / 0.7% | 0.4% / 0.4% / 0.5% | 0.8% / 0.7% / 1.5% | 0.3% / 0.3% / 0.4% | 0.3% / 0.4% / 0.1% | 0.3% / 0.6% / 0.3% | 0.9% / 0.9% / 1.5% | 0.5% / 0.6% / 0.9% |
| 0.1 | 2133 | 0.3% / 0.3% / 0.3% | 0.2% / 0.2% / 0.4% | 0.4% / 0.4% / 0.4% | 0.1% / 0.1% / 0.1% | 0.1% / 0.1% / 0.1% | 0.2% / 0.3% / 0.3% | 0.4% / 0.4% / 0.7% | 0.3% / 0.3% / 0.3% |
| 0.08 | 2990 | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% |

## Frequency-grid resolution (RAO at heading 60 deg, reference: 0.05 rad/s everywhere + 0.025 rad/s inside gap-resonance bands)

Gap-resonance bands detected: [(3.55, 4.2), (4.35, 4.95), (5.1, 5.95)] rad/s

| grid | n omega | max rel. RAO error outside bands (surge/sway/heave/roll/pitch/yaw) | inside bands |
|---|---|---|---|
| 0.10 + 0.05 in bands (app default) | 79 | 0.77% / 0.02% / 1.41% / 0.07% / 0.49% / 0.05% | 0% / 1% / 0% / 2% / 0% / 1% |
| 0.10 only | 56 | 1.48% / 0.23% / 9.12% / 1.98% / 0.87% / 0.22% | 2% / 39% / 3% / 32% / 4% / 56% |
| 0.20 only | 28 | 35.04% / 960.89% / 110.02% / 2459.00% / 200.69% / 2599.31% | 60% / 359% / 50% / 629% / 81% / 1101% |

## Heading interpolation fallback (informational: the app uses exact headings; interpolation is a fallback only)

Error of the periodic cubic spline at 15-deg nodes not in the grid, relative to the DOF's peak excitation over all headings and omegas:

| heading step | ω=1.0 (λ/L=12.4) | ω=2.0 (λ/L=3.1) | ω=3.0 (λ/L=1.4) | ω=4.5 (λ/L=0.6) | ω=6.0 (λ/L=0.3) |
|---|---|---|---|---|---|
| 45 deg | 0.0% | 1.0% | 15.6% | 88.4% | 97.3% |
| 30 deg | 0.0% | 0.1% | 2.4% | 37.3% | 84.8% |

## Time-step convergence (RK4 on the 6-DOF equation with coefficients frozen at omega=1.571 rad/s, T=4.00 s, vs the frequency-domain amplitudes)

| steps per period | dt [s] | periods integrated | max rel. amplitude error |
|---|---|---|---|
| 8 | 0.5000 | 11 | 1.67e-01 |
| 16 | 0.2500 | 11 | 4.94e-03 |
| 32 | 0.1250 | 11 | 2.60e-04 |
| 64 | 0.0625 | 11 | 1.44e-05 |
| 128 | 0.0312 | 11 | 8.31e-07 |

Observed convergence orders between successive refinements: [5.1, 4.2, 4.2, 4.1] (RK4: 4).

## Natural frequencies (illustrative configuration, undamped, potential-flow added mass)

uncoupled roots (rad/s): heave: [4.444, 4.486, 5.404]; roll: [4.68, 5.443, 5.879]; pitch: [4.131, 4.597, 4.669, 4.758, 5.061]

coupled roots (rad/s): [3.847, 4.679, 5.443, 5.501, 5.879] labelled ['EXO pitch', 'EXO roll', 'EXO roll', 'EXO heave', 'EXO roll']

gap-resonance bands (rad/s): [(3.52, 4.2), (4.35, 4.98), (5.1, 5.95)]

Undamped roots on the computed band (added mass evaluated at the root). Several roots per DOF can occur because potential-flow added mass varies sharply near the resonances of the water trapped between the float rows (and between the boat hull and the floats); those bands are listed. Real viscous damping, absent from the BEM, limits them.

## Two-body BEM (EXO floats + Renaud 8000 hull proxy) panel convergence, omegas [1.0, 2.0, 3.0] rad/s (relative change vs the finest set)

| panels EXO/boat [m] | faces | A EXO heave | A boat heave | A coupling heave | B boat roll | F boat heave | F EXO roll |
|---|---|---|---|---|---|---|---|
| 0.25 / 0.35 | 1513 | 0.0% / 0.4% / 2.1% | 0.7% / 0.5% / 2.7% | 0.7% / 2.2% / 10.0% | 1.2% / 3.0% / 6.3% | 0.1% / 0.7% / 2.9% | 0.0% / 0.2% / 0.9% |
| 0.2 / 0.3 | 1699 | 0.0% / 0.3% / 0.6% | 0.7% / 0.5% / 1.6% | 0.6% / 1.7% / 5.6% | 0.9% / 1.7% / 3.7% | 0.1% / 0.4% / 2.0% | 0.0% / 0.1% / 0.5% |
| 0.15 / 0.22 | 2437 | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% | 0.0% / 0.0% / 0.0% |

Example two-body response, H=0.3 m, T=2.5 s, heading 90 deg (coarse grid, 5 % damping):

- EXO: heave 0.048 m, sway 0.045 m, roll 4.32 deg, pitch 0.27 deg
- BOAT: heave 0.107 m, sway 0.125 m, roll 9.97 deg, pitch 0.39 deg
- LINE_AFT_PORT: dynamic tension 335 N vs pretension 88 N -> SLACK (nonlinear, not modelled)
- LINE_AFT_STBD: dynamic tension 222 N vs pretension 88 N -> SLACK (nonlinear, not modelled)
- SPRING_PORT: dynamic tension 229 N vs pretension 43 N -> SLACK (nonlinear, not modelled)
- SPRING_STBD: dynamic tension 118 N vs pretension 43 N -> SLACK (nonlinear, not modelled)