---
title: "EXO-01 in simulation: buoyancy, trim, waves, mooring"
description: "What the numerical model of EXO-01 says about the platform before it touches the water — and what it cannot say."
maturity: "Exploratory — assumed geometry and mass distribution"
date: 2026-10-29
version: "exo01-sim v1.1"
repo: "https://github.com/Biutopic/exo01-sim"
lang: en
---

> **Status: exploratory.** Every number below comes from a model built on the assembly drawing and on declared, not measured, masses. They are there to guide the integration and prepare the trials; they are not certified characteristics. Code, configurations and reports are public: [Biutopic/exo01-sim](https://github.com/Biutopic/exo01-sim).

## Why simulate before launching

EXO-01 is a floating exoskeleton: two rows of floats, an aluminium frame, a rear deck, an observation platform, 2 kWp of panels, 240 kg of batteries and two electric pods, which couples to an existing boat — here *L'Hydronaute*. Before the first launch (autumn 2026), three questions drive the integration: **where to put the masses** (batteries, electrical cabinet), **how to tie the boat in** (mooring lines), and **how the whole thing moves** in the chop and boat wakes of the Erdre. A numerical model answers them with orders of magnitude before welding makes them permanent.

![EXO-01 and L'Hydronaute moored, still water](img/web/01_moored_still_iso.webp)
*EXO-01 and L'Hydronaute alongside, still water. Render from the simulation tool (assembly-drawing geometry, reconstructed Hydronaute hull).*

## Method

The simulator (`exo01-sim`) is an open Python code with a 3D interface. It chains five calculations, each verifiable on its own:

1. **Geometry and masses.** Six Flofiz floats (Ø 0.60 × 1.60 m, sled nose) in two rows, the frame of the La Mutine assembly drawing (28 May 2026), and a list of 18 masses: structure 290 kg, floats 180 kg, batteries 2 × 120 kg, panels 80 kg, electronics 50 kg, pods 16 kg — **856 kg light**, without payload or people. Every mass carries its provenance (declared / estimated / assumption).
2. **Exact hydrostatics.** Immersed volume and centre of buoyancy computed on the triangulated float surfaces, then the static equilibrium (draught, trim, heel) solved by Newton's method. Initial stability (GM) the same way. Checked against the analytic cylinder formulas.
3. **Linear hydrodynamics.** Potential-flow theory (boundary element method, [Capytaine 3.0](https://capytaine.github.io/)), 6 degrees of freedom for EXO-01 alone, **12 coupled degrees of freedom** for EXO-01 + L'Hydronaute (hydrodynamic interaction between the two hulls), finite depth 3 m, fresh water. The coefficients are precomputed and cached; the interface animates the reconstructed motion in regular waves.
4. **Mooring and propulsion.** Four lines modelled as springs that only work in tension (slack as soon as they unload), 100 N pretension; coupled equilibrium of the two bodies. Quasi-static propulsion: two RDT POD 5.0 pods (bollard thrust 2 × 62 kgf = 1,216 N), ITTC-57 hull resistance + form factors → equilibrium speed and the forces carried by the lines, when pushing (EXO-01 pods) and when towing (the boat's engine).
5. **Design sweeps.** Battery position (44 positions in two zones), line arrangement (36 combinations + presets), each evaluated with the solvers above — the full table is returned, not just a "best" pick.

Verification: 84 automated tests and 31 checks (analytic vs numerical, reference-point transform of the hydrodynamic coefficients exact to 10⁻¹⁵, mesh convergence ≤ 8 % on the coupled case). The assumptions live in an `ASSUMPTIONS.md` versioned with the code.

## What the model says

### 1. Trim: the rear deck carries too much

Light, with the batteries at the rear-deck side rails (the drawing's position), EXO-01 floats **rear deck down by 3.8°**, rear-deck freeboard **0.17 m**, draught 0.37 m. The cause is geometric: the floats' centre of buoyancy is at x ≈ 2.9 m from the stern, the centre of mass at x ≈ 2.3 m.

![Battery position: before / after](img/web/10_battery_position_comparison.webp)
*Same state, side view: batteries at the rear-deck side rails (top) and moved forward onto the float-top frames (bottom).*

The battery-position sweep leaves no ambiguity: on the rear deck itself the best achievable is −3.3°. **Moved forward onto the float-top side frames, at x ≈ 3.5 m** (between the mid and forward uprights, above the floats, clear of the boat's hull), the 240 kg of batteries cancel the trim: **0°, freeboard 0.36 m**, and the roll amplitude in beam waves drops from 4.7° to 3.8°.

![Trim vs battery position](img/web/11_battery_sweep_trim_vs_x.webp)
*Trim (left) and roll/pitch amplitudes (right) against the longitudinal position of both batteries; L'Hydronaute moored, no occupants.*

Necessary, not sufficient. The rear deck stays the weak point under load: two 80 kg people at the rear table bring the trim back to −2.2° even with the batteries forward (−6.9° with the deck edge awash in the drawing's position); four people on the rear deck leave 0.09 m of freeboard (no static equilibrium at all in the drawing's position). The design consequences are listed below.

### 2. Stability is not the issue, sinkage is

Transverse metacentric height ≈ 20 m, longitudinal ≈ 9 m: a 4.5 m wide catamaran on 0.60 m floats is extremely stiff. The risk is not capsizing; it is losing freeboard and burying a float when the load is badly distributed — which is what the trim figures above describe.

### 3. In waves, the platform follows the surface

Natural periods, light: ≈ 1.3–1.5 s (heave 1.4 s, roll 1.3 s, pitch 1.5 s). The chop and boat wakes of the Erdre have longer periods (2–3 s): the platform does not resonate, it **rides the wave slope**. In regular beam waves of 0.3 m height and 2.5 s period, EXO-01 rolls ≈ 4.3–4.5° (the wave slope is 5.5°), with a vertical deck acceleration ≈ 1.2 m/s² (0.12 g). The moored Hydronaute rolls more (≈ 8°): its hull is narrower.

![Beam sea, instant of maximum roll](img/web/04_beam_sea_max_roll.webp)
*Regular beam waves H 0.3 m, T 2.5 s: instant of maximum EXO-01 roll (reconstructed linear motion, scale 1:1).*

Important reservation: potential-flow theory has no viscous damping. Near the resonances of the water trapped between the floats (T ≈ 1.2–1.6 s) the coefficients are over-predicted; only a roll decay test will give the real damping.

### 4. Mooring: the four "forward" lines hold a tow, not a push

The drawing's arrangement (four lines from EXO-01's uprights to the boat's forward cleats) balances a **tow** by L'Hydronaute's engine, but not a **push** by EXO-01's pods: the horizontal forces cannot close, and the model only finds an equilibrium by sliding the boat 0.7 m back into the structure. The sweep over 36 arrangements gives the best compromise: **aft uprights → midship cleats + forward uprights → stern cleats** (two long diagonals), 472 N maximum in a line at full thrust, no slack line at rest.

![Top view: L'Hydronaute berthed between the two float rows](img/web/02_moored_still_top.webp)
*Top view: the boat is berthed between the two float rows; the space under the frame bays stays free.*

With 100 N of pretension, **every line goes slack each cycle** in 0.3 m waves, with snatch loads estimated at 0.9–1.2 kN: pretension and stiffness (or line dampers) have to be revisited before the trials.

### 5. Propulsion: order of magnitude only

At 100 % of both pods, EXO-01 + L'Hydronaute would reach ≈ 2.8 m/s (10 km/h), with 870 N carried to the boat through the lines. These speeds are **upper bounds**: the model assumes the bollard thrust stays constant with speed, which is false for a propeller; the pods' thrust–speed curve is not known.

## What the model does not say

- **Masses and positions are declared, not weighed.** The whole trim story rests on the 0.6 m offset between centre of mass and centre of buoyancy.
- **L'Hydronaute's hull is a reconstruction** from the builder's station table (Renaud 8000), not a survey; its mass (2.1 or 3.0 t depending on the source) is not measured.
- **No viscous damping, no wind, no current, no contact** between frame and hull, massless linear lines.
- **Nothing structural**: the model does not check that the float frames carry 120 kg per battery, nor the loads in the uprights.
- **Nothing on energy**: range and the solar balance are treated separately.

## The five measurements that would change everything

1. The floats' real positions on the chassis (x, axis height, spacing) — all buoyancy and hydrodynamics depend on it.
2. The installed centre of gravity of every component, height above all, and the weighed total mass.
3. Mass accounting: payload, cabling, fluids, deck surface.
4. For the coupling: L'Hydronaute's mass and hull, cleat positions, line material/length/pretension; the pods' thrust–speed curve.
5. Operational loads and environment: occupants, water depth, wave climate, a **decay test** in roll/heave (damping).

## What it changes for EXO-01

- **Move the batteries forward** onto the float-top frames (or any equivalent ≈ 400 kg·m forward), subject to the frame's structural capacity.
- **Rework the mooring**: long diagonals, matched pretension and stiffness, snatch protection.
- **Load the rear deck with care** until the trim is corrected; write occupant positions into the operating instructions.
- **Measure before calibrating**: weighing, float survey and decay test at the first launch, then recalibrate the model.

*Tool: [Biutopic/exo01-sim](https://github.com/Biutopic/exo01-sim) — Python / Capytaine 3.0 / three.js. Full reports: `results/optimisation`, `results/comparison`, `results/verification` in the repository.*
