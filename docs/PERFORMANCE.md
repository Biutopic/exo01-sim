# EXO-01 — performance, wind and energy

`exo01/performance.py`, `exo01/aero.py`, `scripts/run_performance.py`, `scripts/run_wind_load_cases.py`
→ `results/performance/`. Interactive version: `docs/website/exo01-explorer.html`.

This closes three gaps `propulsion.py` records in its own docstring: thrust was *"taken constant with speed
(optimistic at speed)"*, and there was *"no wave-added resistance, wind or current"*.

## 1. A defect found first, because everything else depends on it

**The coupled solve with thrust applied converges to a capsized branch.** With the coupling fitted and the pods at
100 %, the boat settles at **88,6° of heel**. The solver converges to a relative residual of 1,5 × 10⁻¹⁰ and reports
the result as `physical: True`, `status: solved`. Nothing flags it, because the wetted area at that attitude
(11,30 m²) is a plausible-looking number.

`demands()` in `run_final_coupling.py` evaluates resistance at exactly that pose, and every load case in
`docs/COUPLING.md` is built from it.

| | capsized pose (used) | upright pose |
|---|---|---|
| boat wetted area | 11,30 m² | **16,25 m²** (+44 %) |
| R_boat at 2,96 m/s | 842 N | **1 151 N** (+37 %) |
| boat share of total | 69,4 % | 76,0 % |

**Direction of the error, which matters more than its size.** Two mistakes partly cancel: the capsized pose
*understates* resistance at a given speed, while constant thrust *overstates* the speed reached. The net is that the
forward-thrust load case the coupling study used, **841 N, is higher than the corrected 554 N**
at the realistic maximum speed. The reverse cases scale with the boat share, which barely moves (69,4 → 67,3 %), and
the yaw cases are bollard × lever and do not depend on the pose at all.

**So §15's preload table is conservative, not wrong.** That is the whole impact.

A pose-validity gate now refuses to compute resistance at an implausible attitude, and two anchors are kept: one
reproducing `propulsion.py` at its own pose (**2,960 m/s — the new module is validated**) and one at the upright pose.

## 2. Maximum speed

Three thrust models, all pinned to the same 1 216 N bollard figure (2 × Rim Drive POD 5.0 at 62 kgf), so they agree
at rest and diverge with speed. The spread is the honest uncertainty until the pod's measured curve exists.

| model | max speed | thrust there | what it assumes |
|---|---|---|---|
| constant | 2.81 m/s = 5.46 kn | 1214 N | what the project assumed — a hard upper bound |
| constant power | 2.74 m/s = 5.33 kn | 1101 N | fixed water power |
| **actuator disk** | **2.54 m/s = 4.93 kn** | 821 N | momentum theory, the physical one |

**The realistic figure is about 2,5 m/s (4,9 kn), against the 2,96 m/s (5,8 kn) the project has been quoting** — the
difference being the capsized pose and constant thrust together.

**An inconsistency in the pod data worth resolving.** 62 kgf of bollard thrust from 5 kW electrical implies, under
*ideal* momentum theory for a 0,25 m disk, only **30 % overall efficiency** — and ideal theory is an upper bound, so
the real figure is lower. A rim drive should do better. Either the 62 kgf is conservative or the 5 kW is a peak
rating. Disk diameter is not recorded; across 0,15–0,35 m the implied efficiency runs 50 % down to 22 % and the
maximum speed 2.64 down to 2.43 m/s.

## 3. Wind

Windage areas come from the real meshes clipped above the waterline, plus the recorded envelope (3,00 × 4,50 ×
9,00 m, air draft 3,80 m on the Erdre) and the panel geometry. **EXO 6.2 m² frontal
/ 8.5 m² lateral; boat 7.1 /
17.6 m².** The three force coefficients are assumed and are the largest single
uncertainty in everything below.

| true wind | max speed, head-on | beam: side force | beam: yaw |
|---|---|---|---|
| 10 kn | 2.21 m/s | 470 N | 283 N·m |
| 15 kn | 1.86 m/s | 999 N | 418 N·m |
| 20 kn | 1.27 m/s | 1740 N | 550 N·m |
| 25 kn | 0.36 m/s | 2692 N | 678 N·m |
| 30 kn | cannot make headway | 3856 N | 802 N·m |

**Operating envelope: the assembly cannot make way against a 30 kn head wind, and is down to 0,36 m/s at 25 kn.**
For a sheltered river that is probably acceptable; it should be stated rather than discovered.

### 3.1 Wind barely loads the coupling, and that is a coincidence

A beam wind at 30 kn puts 3856 N of side force on the pair — more than any load in
`docs/STRUCTURAL.md`. Almost none of it reaches the coupling:

- the boat carries **67 %** of the sail area
- and **65 %** of the sway reaction, by submerged lateral area

The two proportions nearly cancel, so the pair drifts as one and the coupling carries only the difference — **6 to
75 N of sway across every case tested.** Yaw demand reaches ±319 N·m at 30 kn on the quarter, against `diff_opp`'s
2 396 N·m, so wind stays a secondary case.

**Do not rely on this.** It is a coincidence of the current geometry and of a crude drag-share proxy. Tilt the
panels, add a cabin, raise the structure, or change the host boat, and the cancellation breaks. The interactive
explorer has a panel-tilt slider for exactly this reason: a flat array presents nothing, a 30° array presents 8 m².

### 3.2 What the wind cases do expose

| arrangement | wind cases held |
|---|---|
| §15 recommended (midship springs + crossed stern ropes) | **16 of 16**, ≤ 2,7 mm of sway, ≤ 0,04° of yaw |
| the brief's (bow-pulley V + bumpers + wheels) | 12 of 16 |

The brief's configuration fails on sway demands of **8 to 33 N** — a few tens of newtons — and the failures are not
monotonic in wind speed. That is the signature of the near-singular sway mode found in §16, not a physical pattern:
in that arrangement sway is essentially unrestrained, the bridle being a free pulley, the bumpers axial and the
dockwheels slack. The §15 recommendation holds every case comfortably.

## 4. Energy

From the recorded hardware: **28,8 kWh** (6 × 48 V/100 Ah) at 80 % usable, **3,8 kWp** of array derated to
3040 W at the battery, 150 W hotel load.

| sunlight | solar-neutral speed |
|---|---|
| full sun | **1.91 m/s = 3.70 kn** |
| half sun | 1.54 m/s = 2.99 kn |
| overcast | 1.19 m/s = 2.31 kn |

**The solar-neutral speed is the useful number for this boat** — the speed it holds indefinitely without touching
the battery. In full sun that is about **3.7 knots, roughly three-quarters of maximum
speed.** The battery buys bursts above that, not range.

A consistency check worth stating, because getting it wrong produced a 10 kW installation drawing 12,6 kW: at full
thrust the electrical draw must equal the installed power at **every** speed, since the momentum model holds water
power constant. It does, and `tests/test_performance_aero.py` keeps it that way. The bug was using the bollard
induced-velocity relation at speed, which overstates water power by 25 % at 2,4 m/s.

## 5. What would change these numbers

1. **The pod's measured thrust curve.** It collapses the 2,54–2,81 m/s band to one figure and resolves the
   efficiency inconsistency in §2.
2. **The pod disk diameter** — unrecorded, and worth 0,2 m/s across its plausible range.
3. **Wind coefficients**, currently assumed. Everything in §3 scales directly with them.
4. **The two structural solidity ratios.** The envelope is real; what fraction of it is solid is not.
5. **Fixing the capsize branch**, so resistance under thrust can be evaluated at the pose the boat is actually in.
6. **The array conflict**: the cahier des charges says 6 × Dualsun 500 W (3,0 kWp), the component list 8 × AIKO
   475 W (3,8 kWp). The solar-neutral speeds above use 3,8 kWp.

---

*Exploratory. Hull and float surfaces are proxies. Wind coefficients, structural solidity and the pod disk diameter
are assumed. Envelope, panel, battery and pod figures come from the cahier des charges and component list.*
