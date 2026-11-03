# EXO-01 — final coupling configuration: statics, preload and failure modes

> **Exploratory.** Geometry from the assembly drawing; masses declared, not weighed; the boat's hull is a station-table
> proxy. **No manufacturer force-deflection curve or working load limit is published for any of the three contact
> products**, so all three stiffnesses are swept (27 combinations), never assumed. Thrust and resistance come from the
> existing configuration — no motor performance was invented. Generated 2026-11-03 by
> `scripts/run_final_coupling.py` → `results/coupling/final_coupling.json`.

## 1. Verdict

**The concept works mechanically and the force path closes. One component is wrongly specified and must change before
any powered trial: the bow pulley cannot bear on the PVM2.**

The front V-rope does produce the intended rear bumper compression, and the geometry is favourable: with a V half-angle
of **α = 24.0°**, the aft resultant on the boat is **1.83 × the rope tension**. The winch pulls *less* than the
force it creates. But that same resultant is the **pulley reaction**, 1:1 — and it lands on the bow.

## 2. What changed in the model

Two element types were added to `exo01/twobody.py`; the 89 existing tests still pass.

* **`bridle`** — one continuous rope from two EXO points over a pulley on the boat. The pulley equalises the tension, so
  a single tension acts along both legs and the rope's length is the sum of the two legs. This is not the same as two
  independent lines: a real pulley cannot resist yaw, and the model now reproduces that.
* **`axis_m` / `gap_m` on a contact** — a bumper or guide wheel declares its own contact normal and the free travel
  before it touches, instead of inheriting the line of centres. Without this the dockwheels' 30 mm lateral clearance was
  being measured along a near-vertical axis and the wheels never engaged.

## 3. Geometry: what the hardware fixes

| | value | source |
|---|---|---|
| Rear bumper projection (3/4 profile, Ø 220) | 165 mm | product dimensions |
| **Berth moves forward to** | **x = 2.265 m** | set by the bumper — 65 mm ahead of the previously modelled 2.20 m |
| V half-angle α | 23.95° | anchors at x 5.20, y ±2.25 → bow pulley |
| Aft resultant ÷ rope tension | **1.828** | 2 cos α |
| Lateral clearance, hull → float inner face | 180 mm per side | drawing |
| Bow pulley vs the EXO anchors | 233 mm **below** | the rope lifts the bow by 5 % of its tension |

The last line is as much a modelling caveat as a result: the proxy hull has no sheer, so its deck is flat at 0.78 m. A
real stemhead sits higher, which increases the upward component and the bow-lifting moment.

## 4. The force law, and why the load cell is the right instrument

Across the whole preload sweep and **all 27 stiffness combinations**, one relation holds exactly:

```
rear bumper compression  =  pulley reaction  =  1.828 x rope tension
```

It contains no stiffness term, because it is pure statics at the pulley. That gives a design rule:

* **Commanding a winch pull does not determine the bumper force.** At the same commanded preload of
  1600 N, the delivered rear compression ranges **880 – 2626 N** across the 27 combinations — a factor
  of three — because the boat settles by a different amount depending on how the unknown stiffnesses share the travel.
* **Measuring rope tension does determine it**, exactly, whatever those stiffnesses are. The inline load cell is
  therefore not a nicety: it is the only thing that makes the preload a known quantity. Set the system by rope tension,
  never by winch turns, current or time.

## 5. Load cases, at the design preload of 1600 N

| case | surge demand [N] | yaw demand [N·m] | both bumpers loaded from [N] | bumper min/max [N] | rope [N] | pulley [N] | wheel [N] | yaw [°] | clearance [mm] |
|---|---|---|---|---|---|---|---|---|---|
| Moored, no thrust | +0 | 0 | 200 | 986 / 986 | 1080 | 1972 | -0 | +0.00 | 178 |
| Forward, EXO pods 100 % | +841 | 0 | 1 | 1280 / 1281 | 943 | 1721 | -0 | +0.00 | 178 |
| Reverse, pods 50 % of forward bollard | -422 | 0 | 400 | 838 / 838 | 1149 | 2099 | -0 | +0.00 | 178 |
| Reverse, pods 70 % of forward bollard | -590 | 0 | 400 | 779 / 779 | 1177 | 2149 | -0 | +0.00 | 178 |
| Reverse, pods 100 % of forward bollard | -843 | 0 | 600 | 690 / 691 | 1218 | 2225 | -0 | +0.00 | 178 |
| Emergency stop (full reverse 70 % at 3.0 m/s) | -625 | 0 | 400 | 767 / 767 | 1183 | 2160 | -0 | +0.00 | 178 |
| Differential: one pod 100 %, other off | +422 | 1198 | 1200 | 469 / 1784 | 1004 | 1832 | 21 | -0.84 | 143 |
| Differential: one pod full ahead, one full astern | +0 | 2396 | 2500 | -0 / 2551 | 1399 | 2556 | 135 | -2.99 | 107 |

* **Forward propulsion is the easy direction.** The EXO pushes the boat through the bumpers, which carry the
  841 N of boat resistance at 2.96 m/s; the rope only has to stop the boat running away forward.
* **Reverse is what the rope is for.** The boat is 69 % of total resistance, so full reverse asks the rope for
  ~843 N of aft pull. Both bumpers stay loaded from **600 N** of commanded preload.
* **An emergency stop is less demanding than steady full reverse** (625 N against 843 N): the pair's own drag does
  part of the decelerating.
* **Differential thrust governs.** Opposed pods (2396 N·m) need **2 500 N** of commanded preload before both
  bumpers stay loaded. Below that one bumper lifts — not a failure: the boat still turns, with -2.99° of yaw and
  135 N on one wheel at the design preload.

**Yaw goes through the bumpers and the wheels, not the rope.** A pulley that equalises tension gives no first-order yaw
restraint, and the model shows it: the two bumpers carry yaw as a couple (capacity = bumper force × 0.90 m) until one
lifts, after which the wheels take over.

## 6. Lateral behaviour and the dockwheels

| clearance per wheel | wheel force, one pod | wheel force, opposed pods | yaw, opposed pods |
|---|---|---|---|
| 0 mm | 30 N | 142 N | -2.86° |
| 30 mm | 21 N | 135 N | -2.99° |
| 60 mm | 11 N | 129 N | -3.11° |

Wheel loads are small — **at most 142 N** in the worst differential case — and the hull never reaches the floats: the
minimum clearance across every case at the design preload is **107 mm** of the 180 mm available. The wheels are
lightly loaded guides, not structural members. Their diameter is not published, so the 30 mm clearance is an assumption;
the sweep shows the result is insensitive to it — yaw changes by 0.25° between 0 and 60 mm.

## 7. Failure modes

| mode | moored | forward 100 % | reverse 70 % |
|---|---|---|---|
| intact | dx -22 mm, yaw +0.00° | dx -27 mm, yaw +0.00° | dx -18 mm, yaw +0.00° |
| front rope parts | dx +0 mm, yaw +0.00° | dx -8 mm, yaw +0.00° | **no static equilibrium** |
| winch released (rope rigged, no tension) | dx +0 mm, yaw +0.00° | not restrained in the model | dx +13 mm, yaw +0.00° |
| one rear bumper lost | dx -67 mm, yaw -4.27° | not restrained in the model | dx -48 mm, yaw -2.89° |
| one dockwheel lost | dx -22 mm, yaw +0.00° | dx -27 mm, yaw +0.00° | dx -18 mm, yaw +0.00° |

* **Front rope parts → there is no static equilibrium in reverse.** Nothing else can pull the boat aft; the solver does
  not converge, which is the correct answer rather than a number. Moored and forward are unaffected — the bumpers hold.
  **This is a single point of failure with no redundancy, and it fails exactly when the boat is being driven astern.**
* **Winch released**: the forces are right (the bumpers still carry the 838 N of forward demand) but the fore-aft
  *position* is not resolved at zero preload — the boat is free to move within the slack. That is the physical message
  as much as a numerical one, and it is why the system is preloaded at all.
* **One rear bumper lost**: moored and reverse stay restrained (-4.27° and -2.89° of yaw). Under full forward thrust the
  surviving bumper pushes off-centre and the model loses a static solution: the boat yaws past the range where a
  single-point wheel contact is still valid. Read this as a warning about asymmetric push *and* as a limit of the model,
  not as a prediction of what the boat does.
* **One dockwheel lost**: no measurable effect in these cases. The wheels only matter once a bumper has lifted.

## 8. Bill of materials, with what is and is not known

| item | qty | selected product | known | **not published** |
|---|---|---|---|---|
| Front bow bumper | 1 | OCEAN PVM2 | 430 × 240 × 250 mm, 2.5 kg, soft PU foam, through-hole with nylon bushings | **any load rating**; sold as a *swim-platform corner fender*, not a bow fender |
| Continuous front V-rope | 1 | 12–14 mm polyester | works at 943–1399 N here, ≈ 6 % of a 12 mm polyester MBL | exact rope not yet chosen |
| Load-rated bow pulley | 1 | — | must carry **2556 N** at the design preload | not yet selected |
| Electric winch | 1 | VEVOR 12 V, 1 134 kgf advertised | class data: 11.1 kN first drum layer → 5.8 kN fifth, 170 A at full pull, 5 min cooling | **no continuous rating, no duty cycle**; supplied rope is **4.8 mm**, not 12–14 mm |
| Inline load cell | 1 | — | the one instrument that makes preload a known quantity (§4) | range should cover 0–3 kN |
| Mechanical lock | 1 | — | **essential**: an ATV winch brake is not a berth-holding device | — |
| Rear bumpers | 2 | OCEAN foam-filled 3/4 | Ø 220 × 640 mm; sets the berth at x 2.265 m | **no load rating, no force-deflection curve** |
| Lateral dockwheels | 2 | Talamex Dockwheel + holder | loaded to ≤ 142 N here | **diameter, material and load rating not published** |

The winch is heavily oversized for the tension required (943–1399 N against 11.1 kN at the first layer), which is
comfortable — but it brings a practical conflict: **a 12–14 mm rope will not spool on a drum and fairlead sized for
4.8 mm.** Either run the winch on a short small-diameter tail spliced to the V-rope through a thimble, with the
mechanical lock taking the load once set, or choose a winch whose drum suits the rope.

## 9. Comparison with the previous coupling configuration

| | six ropes + stern knees (30 Oct) | this configuration |
|---|---|---|
| Elements | 6 ropes + 2 fenders | 1 rope + 1 pulley + 2 bumpers + 2 wheels |
| Preload | 400 N per rope, set by hand | one measured tension, set by winch |
| Peak element load, Erdre waves | 1 157 N | **not yet run in waves** — see §10 |
| Surge restraint | tension-only ropes both ways | rope aft, bumpers forward: preloaded, so no slack either way |
| Yaw restraint | crossed ropes | bumper couple, then wheels |
| Single point of failure | none (6 ropes) | **the front rope** |
| Release | cast off 6 ropes | release one winch |

Honest summary: this configuration is **simpler to operate and better instrumented**, and preloading removes the
slack-then-snatch behaviour that dominated the rope study. It buys that with **one load path at the front instead of
six**, and with a bow reaction the previous arrangement never created.

## 10. Minimum changes before powered trials

1. **Do not let the pulley bear on the PVM2.** It must be carried by a structural bow fitting — the existing stemhead,
   anchor roller or mooring cleat, whose strength must be verified against **2556 N** — with the PVM2 left to do what
   it is for: protecting the hull from chafe. If no fitting is strong enough, a strop led to two points keeps the "no
   modification" rule. Without this change the configuration should not be tested under power.
2. **Set preload by rope tension, not by winch command.** **600 N** commanded covers everything up to full reverse;
   **2 500 N** is needed before both bumpers stay loaded under opposed-pod turning.
3. **Resolve the rope/drum mismatch** (§8) before rigging.
4. **Measure the three contact stiffnesses.** A compression test on one bumper and one wheel — a scale and a ruler —
   collapses a factor-three uncertainty into a number, and is an afternoon's work.
5. **Run this configuration in waves.** The study is quasi-static. The previous arrangement was judged on peak loads and
   snatch in the Erdre test case; this one has not been through that yet. The preloaded system should behave *better*
   there, but that is a prediction, not a result.

## 11. Addendum (3 Nov): can the winch's own 4.8 mm rope be used for the V?

Yes. `scripts/run_rope_choice.py` → `results/coupling/rope_choice.json` compares rope stiffness over the real V path
(2 × 5.54 m = 11.08 m) for a target rear preload of 2 000 N.

| rope | EA [kN] | k over the path [kN/m] | tension to hold 2 000 N | tension change per mm of surge | preload kept after 5 mm of bumper creep |
|---|---|---|---|---|---|
| polyester 12 mm, bedded in | 80 | 7.3 | 1 096 N | 13 N/mm | 95 % |
| polyester 12 mm, typical | 150 | 13.6 | 1 096 N | 25 N/mm | 92 % |
| polyester 14 mm, stiff | 300 | 27.2 | 1 096 N | 50 N/mm | 88 % |
| **UHMWPE 4.8 mm (supplied)** | **1 810** | **164** | **1 096 N** | **300 N/mm** | **80 %** |

**The tension required is identical for every rope** — 1 096 N — because the force law of §4 has no stiffness term. The
rope diameter changes nothing about what the winch must pull or what the bow must carry.

What it does change:

* **Strength is a non-issue either way.** 1 096 N working against a UHMWPE 4.8 mm MBL of order 10–24 kN is 5–11 % of
  breaking load. The 12 mm polyester would be at ~4 % — both are far oversized; the rope is not sized by strength here.
* **Preload stability is mildly worse and manageable.** A stiff rope stops the boat following the bumpers as they take a
  set, so the lost compression is not recovered: 5 mm of creep costs 20 % of preload with 4.8 mm against 8 % with 12 mm
  polyester. Re-tensioning to the load cell fixes it either way; the 4.8 mm rope just needs it more often.
* **Two real advantages for 4.8 mm.** It spools on the drum and fairlead it was supplied with, which removes the
  rope/drum conflict of §8 entirely. And it needs a far smaller sheave — a 4.8 mm rope wants a sheave of roughly 40 mm
  against ~110 mm for 14 mm rope, which matters a great deal at the bow, where the hardware has to be carried by an
  existing fitting.
* **Two cautions specific to UHMWPE.** It creeps under sustained load (grade-dependent, and this rope's grade is not
  published), which adds to the bumper creep above; and it has poorer abrasion and UV resistance than polyester, which
  matters where it passes over the pulley and bears near the bow. Chafe protection at those two points, and periodic
  inspection, are the price.
* **The supplied length is the real constraint.** The V path alone is **11.08 m of the 12 m supplied**, leaving under a
  metre for the lead to the winch and the five drum wraps the winch's own manual requires. **Buy ~15 m of the same
  4.8 mm rope** rather than re-rigging around the 12 m coil.

**Revised recommendation:** use 4.8 mm UHMWPE for the whole V, in a ~15 m length, with chafe protection at the pulley
and the bow, and re-tension to the load cell more often than you would with polyester. This replaces item 3 of §10 — the
rope/drum mismatch disappears instead of needing a splice. Items 1, 2, 4 and 5 of §10 stand unchanged; the bow fitting
remains the thing that must be sorted before any powered trial.
