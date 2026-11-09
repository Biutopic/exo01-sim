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

## 12. Addendum (3 Nov): pulley position, rope length, and where the legs cross the gunwale

Two questions from the review, and a third thing they uncovered.

### 12.1 Is 2 × 4.7 m = 12 m enough? It depends where the pulley goes — and 4.7 m implies it is not at the stem

| pulley at boat station | leg | V path | V + drum wraps + lead | α | 2 cos α | tension for 2 kN | supplied 12 m? |
|---|---|---|---|---|---|---|---|
| 8.00 m (stemhead) | 5.55 m | 11.09 m | 12.24 m | 24.0° | 1.828 | 1 094 N | **≈ 240 mm short** |
| 7.50 m | 5.09 m | 10.19 m | 11.34 m | 26.2° | 1.794 | 1 115 N | OK |
| **7.00 m (≈ 1 m aft of the stem)** | **4.65 m** | **9.30 m** | **10.45 m** | **29.0°** | **1.750** | **1 143 N** | **OK, ~1.5 m spare** |
| 6.50 m | 4.22 m | 8.44 m | 9.59 m | 32.3° | 1.691 | 1 183 N | OK |

A 4.7 m leg corresponds to the pulley about **1 m aft of the stem**, on the foredeck, not at the stemhead where §3 put
it. With the pulley there the supplied 12 m coil is genuinely enough, and the penalty is small: α opens from 24° to 29°,
so the same 2 000 N of rear preload needs **1 143 N instead of 1 094 N of rope tension — 4.5 % more**. That is a fair
trade for not having to buy rope, and a foredeck cleat or bollard is also a more plausible structural anchor than the
stemhead itself.

(Drum wraps and lead are taken as 0.65 m + 0.50 m: five wraps on a ~40 mm drum, as the winch's own manual requires,
plus the run from the fairlead. Both are estimates — the drum diameter is not published.)

### 12.2 The thing both of us missed: the legs pass over the boat's gunwale

With the anchors at the frame at z 0.30 m, each leg crosses the hull edge at **boat station 4.1–4.6 m** — amidships,
not near the bow — and it does so only **154 mm above the deck line**. Moving the pulley does not fix this: the crossing
shifts by half a metre at most, because it is set by anchoring the V at y ±2.25 m and bringing it to the centreline.

The proxy hull has **no sheer, no rubbing strake, no toe rail and no guardrail stanchions**, so the model reports
"clears" where a real boat almost certainly does not. Raising the anchors on the forward posts fixes it, and cheaply:

| anchor height above the EXO rear deck | rope tension for the same preload | rope height at the crossing | bow lift |
|---|---|---|---|
| 0.30 m (as modelled) | 1 080 N | 154 mm above the deck | 91 N |
| 0.60 m | 935 N | 352 mm | 179 N |
| **1.00 m** (near the top of the posts, which reach 1.15 m) | **669 N** | **616 mm — clears a standard guardrail** | **222 N** |

Raising the anchors is better on three counts at once: the rope clears the deck furniture, the **tension needed falls
by 38 %** (1 080 → 669 N, because the leg direction lines up better with the pull), and the pulley reaction falls with
it (1 972 → 1 224 N), which directly eases the bow-fitting problem of §10. The cost is bow lift rising from 91 N to
222 N — still small against the boat's 2 100 kg, but it trims her down by the stern slightly and should be checked once
the real deck heights are known.

**This supersedes the anchor height assumed in §3.** It needs confirming against the real boat's guardrail and deck
geometry, which the proxy hull cannot represent.

### 12.3 Front fender: the Compass/Dan-Fender FenderFlex is the better product, but it changes nothing critical

| | OCEAN PVM2 (previous choice) | FenderFlex |
|---|---|---|
| What it is sold as | swim-platform **corner** fender | explicitly **bow**, stern, dock and topside protection; also pontoons, canals and locks |
| Geometry | fixed 90° corner | **hinged, settable up to 90°** — adapts to the real stem angle |
| Fixing | one through-hole with nylon bushings | **top, bottom and side fixing points** |
| Construction | soft PU foam, no air | pre-inflated low-pressure |
| Load rating | **not published** | **not published** |

It is the right product class where the PVM2 was not, the adjustable angle suits a stem, and three fixing points
distribute the mounting loads far better than one hole. Two reservations: it is **inflatable rather than closed-cell**,
so it is more vulnerable to puncture and abrasion exactly where a rope might bear on it; and its dimensions, material
and weight are not published on the retailer pages reached here, so it cannot yet be checked against the available
space at the bow.

**It does not change §10 item 1.** No load rating is published for it either, and it is still a fender. The pulley
reaction — 1 224 N with raised anchors, 1 972 N as previously modelled — must be carried by a structural fitting, with
the fender protecting the hull from chafe. A better fender makes the hull safer; it does not make the fender a padeye.

## 13. Addendum (3 Nov): does the front fender carry anything? And is the pulley helping?

The review put it plainly: the rope passes over the fender, so the fender is not really taking any pressure. That is
right, with one condition — and checking it turned up something better than the arrangement recommended in §10.

### 13.1 What the bow actually sees depends on how wide the contact is

The resultant on the bow is the same either way (1 972 N as modelled in §5, 1 224 N with the raised anchors of §12).
What changes is whether it arrives as a point load or a spread one:

| bearing footprint | pressure |
|---|---|
| bare 4.8 mm rope bedding into foam, ~10 × 200 mm | **986 kPa (9.9 bar)** — it cuts in and chafes through |
| 30 × 250 mm | 263 kPa (2.6 bar) |
| 50 × 300 mm | 132 kPa (1.3 bar) |
| **a saddle or bearing plate, 120 × 400 mm** | **41 kPa (0.41 bar)** — a fender takes this without noticing |

So: **a fender cannot be a padeye, but it can be a bearing surface.** Spread the direction change over a broad saddle and
the 1 972 N arrives at the hull as 0.4 bar over the fender's footprint, which is nothing for a hull or a fender. That is
why no load rating is needed for the fender in that arrangement — the correction in §10 item 1 was aimed at the wrong
risk. The risk is not that the fender is too weak; it is that a **thin rope on soft foam is a knife**.

### 13.2 And the free-running pulley is actively hurting yaw

Matched at the same 1 972 N of rear preload, under opposed pods (2 396 N·m):

| front arrangement | yaw | leg tensions | wheel |
|---|---|---|---|
| **A** one rope over a free pulley (as specified) | **−2.99°** | 1 399 N, equal by construction | 135 N |
| **B** two legs made off / bearing on a saddle, anchors 0.30 m | **−0.50°** | 1 381 / 772 N | 257 N |
| **C** same, anchors raised to 1.00 m | **−0.50°** | 1 389 / 777 N | 257 N |

**Fixed legs restrain yaw six times better**, and they cost nothing in peak rope tension (1 381 N against 1 399 N). The
reason is the one stated in §5: a pulley that equalises the tension cannot resist yaw. The brief specified the pulley so
the rope could "slide and approximately equalise tension" — but equalising the tension is precisely what throws the yaw
restraint away. The two legs carrying 1 381 and 772 N *are* the yaw couple.

### 13.3 What this changes

A rope bearing on a broad saddle over the fender is neither model exactly: friction at the saddle is somewhere between
free-running (A) and fully fixed (B), so the real behaviour sits between those two rows, which bracket it. That is
convenient rather than awkward:

* **at rigging**, partial sliding helps you pull both legs up evenly from one winch — the reason the brief wanted a
  pulley in the first place;
* **under load**, friction lets the legs differ, which is where the yaw restraint comes from.

**Revised recommendation, replacing §10 item 1:** lead the continuous rope over a **broad saddle or a wide-sheave
roller bearing on the bow fender**, not a small free-running block on a padeye. Size the bearing surface for ~120 ×
400 mm so the pressure stays near 0.4 bar, and keep the fender between the hardware and the hull. Then:

* the fender's missing load rating stops mattering — it is a bearing surface at 0.4 bar, not a structural attachment;
* no structural bow fitting has to be found or verified, which is what makes the "no modification to Hydronaute" rule
  easy to keep rather than hard;
* yaw restraint improves by roughly 6× over the specified free pulley;
* and the FenderFlex's three fixing points (§12.3) become the right feature for the job — they are what holds a broad
  saddle in place against a rope trying to drag it along the stem.

The thing still to verify on the real boat is the **anti-slip of that saddle along the stem**: nothing in this model
stops the saddle sliding up, down or sideways under an off-axis pull, and that, not the fender's strength, is now the
open question at the bow.

## 14. Addendum (3 Nov): the configuration in waves — and two of my own recommendations reversed

`scripts/run_coupling_waves.py` → `results/coupling/coupling_waves.json`, same three Erdre reference waves, damping and
settings as the six-rope study of 30 Oct, so the numbers compare directly.

### 14.1 What the time-domain check can and cannot say here

It cannot bound the snatch load in this configuration, and saying so is more useful than quoting a number. At a rear
preload of 2 000 N the tension-only peaks wander between **11.0 and 15.7 kN from 64 to 1 024 steps per period**, with a
time-domain/linear amplitude ratio of 6–22. With elements this stiff, **no damping in any element** (the model has
none — see the methodology) and the contacts opening twice per cycle, the integration does not settle. Those peaks are
therefore not reported as results.

What is well posed is the **engagement criterion**: the preload at which no rope goes slack and no bumper opens during
the cycle, in the linear model, which is converged. BEM reuse was checked against an exact solve for one case — leg peak
2 318 N exact against 2 332 N reused, 0.6 %, boat roll 11.84° against 12.20° — so the reuse is adequate here, which
matters because an exact BEM costs 347 s per configuration.

### 14.2 It works — with the anchors LOW

Anchors at 0.30 m, 12 mm polyester, sweeping leg pretension:

| leg pretension | rear compression | leg static | beam 0.3 / 2.5 | head 0.3 / 2.5 | beam 0.5 / 3.0 | peak leg tension |
|---|---|---|---|---|---|---|
| 700 N | 861 N | 472 N | slack | engaged | slack | 694 N |
| 900 N | 1 108 N | 607 N | engaged | engaged | engaged | 853 N |
| 1 100 N | 1 354 N | 742 N | engaged | engaged | *slack* | 1 009 N |
| **1 300 N** | **1 601 N** | **877 N** | **engaged** | **engaged** | **engaged** | **1 137 N** |
| 1 500 N | 1 848 N | 1 013 N | engaged | engaged | engaged | 1 246 N |

**From 1 300 N of leg pretension — 1 600 N of rear compression — the coupling stays engaged through all three reference
waves.** That is the same order as the quasi-static requirement of §5, so **waves do not drive the preload**: the
differential-thrust case of §5 (2 500 N) remains the governing one. The transom gap stays open throughout.

Peak leg tension at that setting is **1 137 N against the six-rope arrangement's 1 157 N** — the two are within 2 % of
each other on peak load. Boat roll is **11.8° against 9.4°**, so the preloaded coupling is somewhat harder on the boat's
roll: tying the two hulls together more stiffly makes the boat follow the EXO more closely.

### 14.3 Two recommendations of mine, reversed

Both were made from quasi-statics alone, and waves overturn them.

| | quasi-static conclusion | in waves |
|---|---|---|
| **Anchor height (§12.2)** | raise to 1.00 m: −38 % tension, clears the gunwale | **keep low.** At 1.00 m the preload needed to stay engaged rises from 1 600 N to **11 300 N of rear compression — a factor of 6.** A near-horizontal leg lines up with the relative surge it has to restrain; a raised one is pumped by the relative heave and pitch. |
| **Rope choice (§11)** | the supplied 4.8 mm UHMWPE works | **use the 12 mm polyester.** At 0.30 m anchors the 4.8 mm needs 3 200 N of rear compression against 1 600 N, and with raised anchors it never engages in beam seas at any preload the solver accepts. Stiffness is what drives slack-and-snatch, which the mooring study already showed and quasi-statics cannot see. |

### 14.4 The conflict this leaves, which is now the main open question

**Low anchors are required for wave behaviour, and low anchors put the rope legs across the boat's gunwale** (§12.2:
they cross the hull edge amidships, 154 mm above the deck line in a proxy hull that has no toe rail, rubbing strake or
stanchions). Raising the anchors is no longer available as the fix.

What is left to try, none of it modelled yet:

1. **Outboard standoffs on the EXO frame** so the legs clear the topsides at a low anchor height. The frame is already
   at y ±2.25 m against a hull half-beam of 1.49 m, so this means brackets, not a wider frame.
2. **Accept contact and protect it** — a rubbing strip or fender length where each leg crosses, which is cheap but puts
   a working rope against the boat's side for the whole time she is coupled.
3. **Move the legs' boat end aft** so they run more nearly fore-and-aft. That changes the V into something closer to two
   breast lines and loses the self-centring the V gives; it would need its own study.

**Revised bottom line.** The concept holds in waves: engaged from 1 600 N of rear compression, peak rope tension within
2 % of the six-rope arrangement it replaces, with somewhat more roll transmitted to the boat. The preload is still set by
the differential-thrust case, not by waves. The front hardware should be **12 mm polyester on low anchors over a broad
saddle** — not the 4.8 mm rope on raised anchors that §11 and §12 arrived at. And the legs' path over the gunwale is the
thing to resolve next, on the boat rather than in the model.

## 15. Addendum (3 Nov): a search over seventeen arrangements, and a better one than the brief's

`scripts/run_arrangement_search.py` → `results/coupling/arrangement_search.json`. Seventeen arrangements through one
gauntlet: the nine thrust-derived static load cases **gated on both rear bumpers staying loaded** (≥ 50 N each — they
are the forward-thrust load path, §5), the lowest preload that closes them, the three Erdre reference waves on the
linear engagement criterion, the lowest preload that keeps the primary path engaged, a single-loss redundancy probe,
and the closest approach of every rope to the hull **and** the superstructure.

### 15.1 Four flaws in the first version of this gauntlet

Worth recording, because the first run produced a plausible-looking ranking that was wrong, and because the same traps
apply to anything built on this code.

1. **The static gate did not require the bumpers to stay loaded.** Arrangements that let a bumper rattle open scored
   "passes at 1 N of preload". That is not a design; §5's requirement is both bumpers loaded in every case.
2. **Engagement counted a snug backup rope going slack as a failure.** The bisection then drove the primary preload to
   5–7 kN purely to stretch the 150 N backups taut — the uniform-preload artefact returning through displacement
   instead of through pretension. Engagement is now judged on the primary load path and the contacts only; a backup
   going slack in a wave is normal and is recorded, not failed.
3. **The clearance metric could not tell a rope lying on the deck edge from one through structure.** Both read as a
   large negative number. It now says which, with the side-deck width where there is one.
4. **The wave preload was found by bisection, which assumes engagement is monotone in preload.** §14 had already
   disproved that (engaged at 900 N, slack at 1100 N, engaged at 1300 N). Replaced with a ladder scan from the bottom.

### 15.2 The result

Every row below closes all nine static cases with both bumpers loaded and stays engaged in all three waves. Preload is
per primary element; secondary ropes are rigged snug at 150 N.

| arrangement | preload | peak rope | boat roll | yaw (diff_opp) | surge | single losses fatal | actions |
|---|---|---|---|---|---|---|---|
| **I** midship springs + crossed stern ropes | **600 N** | **647 N** | 10,2° | **0,46°** | **15,7 mm** | **0 / 4** | 4 |
| **C** fixed bow legs + crossed stern ropes | 600 N | 708 N | 10,2° | 0,28° | 13,8 mm | **0 / 4** | 4 |
| G the six-rope arrangement + dockwheels | 981 N | 1 089 N | 10,2° | — | — | 0 / 6 | 6 |
| J bow-pulley V + midship springs | 1 196 N | 1 129 N | 11,3° | — | — | 1 / 3 | 3 |
| B fixed bow legs alone | 1 300 N | 1 137 N | 11,4° | — | — | 2 / 2 | 2 |
| **A the brief's configuration** | **2 218 N** | **1 586 N** | **14,5°** | **1,66°** | **35,6 mm** | **1 / 1** | 1 |
| M the same without dockwheels | 2 324 N | 1 671 N | 15,2° | — | — | 1 / 1 | 1 |

**The brief's configuration is last but one.** Against it, arrangement I needs 3,7× less preload, carries 2,5× less peak
rope tension, transmits 1,4× less roll to the boat, holds yaw 3,6× tighter and surge 2,3× tighter, and survives the loss
of any single element where the brief's configuration survives none.

**Arrangement I** — two 1,92 m springs from the EXO forward posts to the boat's existing midship cleats, two crossed
stern ropes from the EXO mid posts to the opposite stern cleats, the two rear bumpers, the two dockwheels. **No bow rope
at all.** Transom gap 74–94 mm, open throughout. The crossed ropes go slack in the waves, which is what a backup is for.

**Arrangement C is the smallest correction to what the brief specifies**, as §-E asked for: keep the bow legs, swap the
pulley for two fixed legs (§13), and add two crossed stern ropes to the existing stern cleats. That alone takes the
configuration from 2 218 N / 1 586 N / no redundancy to 600 N / 708 N / full redundancy. Two ropes and no new fittings.

### 15.3 Why the short forward element wins

Not cleverness — geometry, and it was visible before the solver ran.

- **Compression cannot restrain forward surge.** The only hull surfaces whose outward normal has a forward component
  lie forward of station 6,20 m; the EXO reaches station 2,94 m. Between stations 1,2 and 6,2 m the hull is
  parallel-sided, so a pad there has a purely lateral normal. The forward restraint must be tension — that is proved,
  not chosen.
- **The bow leg's modelled path is not riggable.** A straight leg from the EXO forward frame to the stemhead crosses
  inboard of the hull side at station 4,65 m while sitting at z 0,46 m, and reaches **1,03 m inside the envelope at
  station 7,39 m**. No anchor height fixes it (0,30 / 1,00 / 2,10 m all fail). The real rope would lie in the ~160 mm
  side deck between the cabin side and the hull edge and be led forward — which means the V's α = 23,95° and its 1,828
  amplification (§4) describe a rope nobody can rig. **Those numbers need redoing against the led path.**
- **A 1,92 m spring to the midship cleats has a worst clearance of −102 mm, 81 mm from the cleat** — an ordinary cleat
  approach, not a fouled path.

### 15.4 Two of my own earlier claims corrected

- **The dockwheels do not "earn their place decisively".** That claim came from the flawed run. With the gates right:
  A 2 218 N / 14,5° against M 2 324 N / 15,2° — the wheels buy about 5 % of preload and 0,7° of roll. In arrangements I
  and C they carry **0 N in every static case**, because those arrangements are tight enough laterally that the 30 mm
  gap never closes. Keep them as a physical stop and insurance against contact, not as a load path — and stop treating
  the 30 mm gap as a dimension needing precision.
- **Aft breast ropes to the stern cleats are half an answer.** 2,73 m, surge direction cosine 0,92 against the bow leg's
  0,91, clean geometry, strap-length — and **no yaw stiffness**, because a rope that aligned with surge has only 0,35
  left for the athwartships motion yaw produces at the stern. Alone (arrangement O) it is unrestrained under
  `diff_opp`. With midship springs (Q) it needs 5 000 N and peaks at 6 879 N. Set aside.

### 15.5 What the preloads rest on

- **`diff_opp` — one pod full ahead, one full astern — binds the preload of thirteen of the seventeen arrangements.**
  It is the design driver. CORRECTION (8 Nov): it does not rest on a guess. Its 2 396 N·m is 1 216 N × 1,97 m, and
  1 216 N is the pods' datasheet figure (2 × Rim Drive POD 5.0, 62 kgf each). The 1 500 N order-of-magnitude guess
  belongs to the boat's Volvo inboard, which no load case uses. The real unknown is the **reverse** thrust fraction
  of a rim drive, typically 60–80 % of forward, where `diff_opp` assumes 100 % — so the case is more likely
  conservative than optimistic.
- The absolute preloads scale with the 50 N "bumper still loaded" threshold, which is a choice. The **ratios** between
  arrangements are the robust part of this table.
- Element lengths against a 10 ft (3,05 m) ratchet strap: midship spring **1,92 m fits**, aft breast **2,73 m fits**,
  crossed stern rope 3,62 m and bow leg 5,56 m do not.

## 16. Known defect (8 Nov): a fender with a declared contact axis applies a couple it cannot carry

Found while building the load note (`docs/STRUCTURAL.md`), by summing each element's own force system and checking
it closes. It does not.

**What is wrong.** A fender with a declared `axis_m` carries its force along that axis (`_line_forces` sets
`u = _u0` and measures penetration as `L = (b − a)·u`), but the moment is taken at `a` on the EXO and at `b` on the
boat. Once the bodies displace, `a − b` is no longer parallel to the force, so an equal-and-opposite pair applied at
two different points leaves a net couple of `cross(a − b, f)`. No pad, roller or strap can transmit a couple.

**How large.** Measured in the real `diff_opp` solve of the brief's configuration: `BUMPER_STBD` at 2 652 N applies
**178 N·m**, against an applied yaw demand of 2 396 N·m — **7,4 %**. The couple is *restoring*, so it is a spurious
yaw stiffness: **modelled yaw angles are too small, and any preload set by a yaw case is underestimated.** That is
non-conservative, and `diff_opp` binds thirteen of the seventeen arrangements in §15.

**What it does and does not affect.**

| | force residual | moment residual | verdict |
|---|---|---|---|
| six surge-only cases | 0,02 N | 0,0–1,8 N·m | sound; §15 and the load note rest on these |
| `diff_one` / `diff_opp`, arrangement I | 0,014 N | 8,3 / 11,5 N·m (0,5 %) | negligible |
| `diff_one` / `diff_opp`, arrangement A | 0,072 N | 147 / 181 N·m (7,6–12,3 %) | material |
| bridle elements | — | 0,00 N·m | the bridle itself closes exactly |

The error scales with fender load × the lateral offset of its endpoints, so it is smallest in the §15 recommendation
(whose dockwheels carry 0 N) and largest in the configuration that recommendation beats — and it *flatters* the
latter. **Correcting it would widen the §15 gap, not close it.** The ranking stands; the absolute yaw angles and the
yaw-governed preloads do not.

**A second, related defect found at the same time.** The two force-assembly sites disagreed for bridles:
`coupling_part` (the Jacobian block) takes one moment per leg at `a` and `a2`, while the full residual lumped both at
`a` — a difference of `cross(a − a2, T·u2)`. Residual and Jacobian describing different systems degrades convergence
and biases any bridle result.

**What was tried and rejected.** Applying the contact force at a single point on both bodies makes the couple vanish
identically and **destabilises the yaw equilibrium**: a symmetric arrangement under no external load then solves
grossly asymmetric (one bumper 7 131 N, the other 0 N, the bridle at 4 419 N against its 1 600 N pretension). The
model was reverted. A correct fix needs a contact point defined on the pad *surface* — the projection of one
reference point onto the other's contact plane, or the midpoint — not a choice between the two reference points, and
it needs the sway and yaw restraint of a frictionless pad pair formulated properly, since the spurious couple was
silently supplying it.

`tests/test_coupling_elements.py::test_no_element_applies_a_spurious_couple` reproduces it and is marked
`xfail(strict=True)`, so it will fail loudly the day the model is fixed. Note that `_u0` is the internal field the
solver reads; a raw element dict carrying only `axis_m` takes the geometric fallback and cannot exercise the defect.

## 17. The cahier des charges rules out the arrangement §15 recommends

Reading the project's own `Cahiers des charges` (Notion, last edited 12 May 2026) after §15 was written. Three rules
in it bear directly on the coupling, and the arrangement study met none of them because it never had them:

> **Zéro modification des bateaux hôtes.**
> **Le cadre reprend toutes les charges : le bateau ne porte rien.**
> **Compatible avec 80 % des bateaux (fluviaux pour l'instant).**

Against those:

| | what §15 recommends | the rule |
|---|---|---|
| **Fittings** | `docs/STRUCTURAL.md` §5.1 calls for verifying or refitting every cleat used — through-bolted, backing plate | a refit **is** a modification |
| **Load path** | 571 N into the midship cleats, 137 N into the stern cleats | the boat is to carry nothing |
| **Generality** | depends on *this* boat's cleat positions and ratings | must fit 80 % of boats |

### 17.1 The rule as written cannot be met, so the reading matters

Any coupling that propels the boat must put force into it: that is what propulsion is. Taken literally, "le bateau ne
porte rien" forbids the bumpers as much as the ropes. The reading that makes engineering sense is **the boat carries
none of the EXO's weight or structural loads** — which the next line supports ("la structure doit flotter
indépendamment et ne pas ajouter ni retirer de poids au bateau hôte").

**That distinction decides the recommendation, and it is a specification question rather than a physics one.** Under
the narrow reading (no weight), §15 stands. Under the broad reading (no load at all into boat fittings), every
rope-to-cleat arrangement in §15 is out.

### 17.2 What the broad reading promotes

**The sandwich sling** — set aside in §16 as a lifting idea and then shown unable to lift (the EXO frame spans boat
stations −2,27 to +2,94 m while the boat's centre of mass is at 3,60 m, so every sling sits aft of it). As a
*coupling* element it is the only arrangement tested that satisfies all three rules at once:

- it bears on the hull and needs **no boat fittings whatsoever**
- it therefore works on any hull form, which is what "80 % of boats" requires
- the boat carries no attachment load, only bearing pressure

Its known weaknesses stay real and are engineering problems rather than specification violations: **no surge
restraint at all** (a transverse strap has a surge direction cosine of exactly zero, and a frictionless wrap can only
transmit force normal to the hull), so it needs the bumpers plus a short forward tension element; it wants 200–300 mm
lifting slings rather than 50 mm tie-downs, for bearing; and its working length chafes under the hull where it cannot
be inspected. §16 also settled that it should be rigged **snug, not preloaded** — preloading costs 63 % more peak
load to buy 0,8° of roll.

### 17.3 Other spec items the coupling study did not have

- **Disassembly ≤ 45 min with 2 people, non-permanent connections.** This is a hard constraint on the "ops actions"
  column of §15.2, which counted actions without a budget to compare them against.
- **No superstructure component over 5 kg**, solar panels excepted. Relevant to anything bolted to the frame.
- **Dimensional envelope 3,00 × 4,50 × 9,00 m, air draft 3,80 m.** §15's arrangements all sit inside it, but the
  figure now drives the windage model in `docs/PERFORMANCE.md`.

**Open question for the project, not for the model:** which reading of "le bateau ne porte rien" is intended. The
answer changes the recommended arrangement.

## 18. Decision (9 Nov): arrangement I, scoped to a fixed route

**Selected: `I_fwd_midship_crossed`** — two 1,88 m springs from the EXO forward posts to the boat's midship cleats,
two crossed stern ropes from the mid posts to the opposite stern cleats, the two rear bumpers, the two dockwheels.

**Basis.** EXO-01 operates a known route with a known host boat. Generic compatibility across 80 % of hulls is a
goal for the product, not a constraint on the first boat, so the mechanical case decides. On that case I wins every
column of §15.2: 600 N of preload against 2 218 N, 647 N of peak rope load against 1 586 N, 10,2° of boat roll
against 14,5°, yaw 3,6× tighter, surge 2,3× tighter, and it survives the loss of any single element where the
brief's configuration survives none. It also holds all sixteen wind cases where the brief's holds twelve
(`docs/PERFORMANCE.md` §3.2).

**What this knowingly accepts.** §17 showed that any rope-to-cleat arrangement departs from two rules in the cahier
des charges — *zéro modification des bateaux hôtes* and *le cadre reprend toutes les charges* — under the broad
reading of the second. That departure is now a scoped decision rather than an oversight:

| | accepted | revisit when |
|---|---|---|
| Load into the host's cleats | 571 N at the midship cleats, 137 N at the stern cleats | a host boat whose cleats cannot take it |
| Dependence on cleat positions | this boat's geometry | a second host boat enters the programme |
| Generic compatibility | not met | the 80 % target becomes binding |

The fallback is `V_spec_zero_fittings`, which meets all three rules and costs a factor of 6 in peak rope load
(4 075 N against 647 N) and half the redundancy, buying a factor of 3 in transmitted roll.

### 18.1 The one thing that can actually fail

**No cleat on Hydronaute has a known rating.** A design load of 1 901 N is trivial for a through-bolted cleat on a
backing plate and entirely capable of tearing a screwed cleat out of a thin deck laminate — pull-out, not shear.
Everything else in `docs/STRUCTURAL.md` has comfortable margin; this does not, because it has no margin at all until
somebody looks.

**This gates powered trials.** Verify or refit the four cleats the arrangement uses before any trial under thrust.
Note the circularity to resolve with the project: a refit is itself the modification the cahier des charges
forbids, so either the rule is read narrowly (no structural load, weight) or the refit is an accepted exception.

### 18.2 What to build

| element | ×  | geometry | design load | specify |
|---|---|---|---|---|
| midship spring | 2 | EXO (4,95, ±2,25, 0,30) → boat midship cleat (4,30, ±1,35, 0,80); **1,88 m** | F_k 761 N, F_d 1 901 N | **MBL ≥ 9,5 kN** — 12 mm polyester is far inside it |
| crossed stern rope | 2 | EXO (2,10, ±2,25, 0,30) → **opposite** stern cleat (0,30, ∓1,30, 0,80); **3,60 m** | F_k 621 N (**wave**, DAF 4,2–4,5), F_d 1 553 N | **MBL ≥ 7,8 kN**; the longest, softest ropes in the set |
| rear bumper | 2 | EXO crossmember (2,10, ±0,90) bearing on the transom | ~800 N, ≈0,2 bar | load the crossmember in line, no cantilevered bracket |
| dockwheel | 2 | boat station 1,20, y ±1,49, 30 mm gap | **0 N in every static case** | physical stop and insurance; the gap needs no precision |

Preload **600 N** on the springs, read on an inline dynamometer; the crossed ropes rigged **snug** (≈150 N), not
tensioned. Four tensioning actions to couple, against the cahier des charges budget of 45 minutes for two people.

**The crossed ropes are the ones to watch.** Their dynamic amplification is 4,2–4,5 against ≤1,1 for everything
else: the wave governs them, not the statics. Keep them the longest and softest elements or they are what snatches.

### 18.3 Still open, and unchanged by this decision

1. **Cleat ratings** (§18.1) — gates trials.
2. **The fender-couple defect** (§16) — the yaw-governed preloads stay lower bounds until it is fixed.
3. **The capsize branch** (`docs/PERFORMANCE.md` §1) — resistance under thrust cannot be evaluated at the pose the
   boat is actually in.
4. **The pods' reverse-thrust fraction** — `diff_opp` assumes 100 % of forward, where a rim drive typically gives
   60–80 %, so the design case is probably conservative.
5. **The three contact stiffnesses**, still unmeasured.

## 19. Addendum (9 Nov): equalising the midship pair, and softening it — two routes to the same loss

Two proposals, from two sketches: a single rope equalising the midship pair over turning blocks with one winch, and
a shock absorber ("ressort") in series with the coupling rope. They look unrelated. They fail for the same reason,
and measuring both is how that became visible.

A new element was needed first. `bridle` is one rope from TWO points on the EXO over a turning point on the boat;
the mirror did not exist. `yoke` is now the general equalised pair: two legs, four points, ONE tension, path length
= the sum of the legs, with the rail run between the blocks folded into L0. `bridle` and the single-point yoke are
special cases of it. Implementing it also fixed §16 defect 2 — the full-residual assembly had been lumping both
bridle legs at one point while the Jacobian correctly took a moment per leg.

### 19.1 The measurement

Arrangement **X** is arrangement I with the two midship springs replaced by one equalised rope. Nothing else
changes — same points, same crossed ropes, same bumpers, same wheels, same gauntlet.

| | **I** — two independent springs | **X** — one equalised rope |
|---|---|---|
| minimum preload, statics | 558 N → design **600 N** | **2120 N** |
| peak rope load | **621 N** | **4066 N** |
| binding static case | `diff_opp` | `diff_opp` |
| fatal single losses | **0 / 4** | **1 / 3** (lose the rope, lose both legs) |
| beam wave 0,3 m / 2,5 s | engaged | **both bumpers open** — contact lost |
| boat roll | 9.83° | 8.9° |
| tensioning actions | 4 | **1** |

**3,5× the preload and 6,3× the peak load, to save three tensioning actions.**

### 19.2 Why: a symmetric equalised pair has exactly zero yaw capacity

Not "less" — zero, and provably so rather than approximately. `tests/test_yoke_element.py` asserts it directly:
mirrored legs at one tension produce no net sway force and no couple about either body, to machine precision.

Both arrangements bind on `diff_opp` — one pod full ahead, one full astern, 2 395 N·m of pure yaw. Two independent
springs resist that couple **by becoming unequal**: at the yawed pose one carries 524 N while the other falls to
76 N, and the difference *is* the restoring couple. Equalise them and the mechanism is deleted, not weakened. The
whole yaw demand then falls on the crossed stern ropes, on a short moment arm, and the preload has to climb until
they alone can carry it.

This is §13.2 reappearing at full size. There the free bow pulley restrained yaw 6× worse than two fixed legs, for
exactly this reason. The lesson generalises: **equalisation is only free where the pair has no differential job.**

### 19.3 The shock absorber reaches the same loss from the other side

A spring in series cannot change what the coupling must hold — statics are statics. It changes the stiffness the
boat feels, k_eff = 1/(1/k_rope + 1/k_shock), which the *softer* element dominates. Applied to the primary pair
(`scripts/run_shock_absorber.py`, all nine static cases, arrangement I otherwise untouched):

| absorber | k_eff (N/m) | min preload | at the design 600 N |
|---|---|---|---|
| none — rope alone | 13 500 | 600 N | holds |
| 27000 N/m | 9000 | 600 N | holds |
| 13500 N/m | 6750 | 800 N | **fails** (diff_opp) |
| 8000 N/m | 5023 | 800 N | **fails** (diff_opp) |
| 5000 N/m | 3648 | 1200 N | **fails** (diff_opp) |
| 3000 N/m | 2454 | 1200 N | **fails** (diff_opp) |
| 2000 N/m | 1741 | 1200 N | **fails** (diff_opp) |
| 1200 N/m | 1102 | 1200 N | **fails** (diff_opp) |
| 800 N/m | 755 | 1600 N | **fails** (diff_opp) |
| 500 N/m | 482 | 1600 N | **fails** (diff_opp) |

Softening the pair reduces the differential force available at any given yaw rotation, so `diff_opp` fails at the
design preload and the minimum climbs from 600 N to 1 600 N. Same mechanism, different route.

The absorber is modelled as a **linear spring of unlimited stroke**. A real mooring compensator is progressive and
hysteretic and bottoms out; past that point the rope stiffness returns in full and the peak is the rope-only peak.
That makes these figures optimistic for the absorber, which only strengthens the conclusion.

**Where an absorber would pay, and is not yet tested:** the crossed stern ropes. They are wave-governed with
amplification 4,2–4,5 against ≤1,1 for everything else (§18.2), and they carry no static preload job. That is the
open question this addendum leaves behind.

### 19.4 Tensioning: no winch is needed, but a dynamometer is

At 600 N per spring, hand tension is sufficient with any purchase:

| method | hand force for 600 N | verdict |
|---|---|---|
| ratchet strap (~12:1 lever) | ~50–150 N on the handle | ample, and controllable |
| 4:1 tackle on blocks | ~180 N including sheave friction | trivial |
| nœud de tendeur (~3:1, rope on rope) | ~200 N plus heavy friction | workable, marginal |
| bare direct pull | 600 N | **no** — sustained haul is 200–400 N, and it cannot be cleated off at the top of a pull |

The binding constraint is not reaching 600 N but **knowing** it was reached: the inline dynamometer of §18.2 stays
mandatory whatever pulls the rope. Note the asymmetry — arrangement X at 2 120 N *would* need a powered winch, so
the arrangement that saves three tensioning actions is also the one that forces a winch onto the frame.

### 19.5 Decision

**Arrangement I stands unchanged.** X is registered as `X_yoke_midship_crossed` and kept in the catalogue as a
measured negative result, not deleted: it is the cleanest demonstration in the study of why the midship pair must
stay independent.

## 20. Addendum (9 Nov): one continuous rope, and the shock absorber closed out negative

### 20.1 The rig as drawn

One continuous rope: dead-ended at one point, rove through a block at every turn, through the shock absorber and
the loop, with the free tail as the hauling part. One pull brings the whole coupling up to tension.

Mechanically that is **one tension everywhere, so rank 1** on the boat's three in-plane DOF — the §19 result at
maximum scale. The magnitude of the pattern is settable; the distribution is not. `diff_opp` needs the legs to be
unequal (524 N against 76 N), and a single rope cannot do that at any preload.

With one counter-intuitive wrinkle worth recording: **better blocks make the restraint worse.** A real rope holds
some tension difference up to the point it renders through the sheaves. Plain-bush blocks over 6 turns hold a
difference down to roughly 53 % before slipping — sloppy, but real differential capacity. Ball-bearing blocks
over the same path equalise to within ~83 %, and give nearly all of it up. (Catalogue efficiencies, not measured.)

### 20.2 But the drawing carries its own fix: the jammers

Reeve the rope as drawn, haul the single tail until every leg is up, **then close each clutch**. At that instant
the rope stops being one rope and becomes N independent springs, each at the preload just set and free to differ
under load. Arrangement I's mechanics, one tensioning action instead of four.

That depends on a question §15–§19 never asked, because every run so far used *equal* preloads: **how unequal can
the pair be before arrangement I stops closing?** The rove does not deliver equal legs — tension grades from the
hauling tail down to the dead end by eta^n. `scripts/run_preload_spread.py` holds the port spring at 600 N and
walks the starboard one down, all nine static cases:

| starboard / port | starboard | outcome |
|---|---|---|
| 100% | 600 N | holds, peak 760 N |
| 95% | 570 N | holds, peak 751 N |
| 90% | 540 N | holds, peak 742 N |
| 85% | 510 N | holds, peak 733 N |
| 80% | 480 N | holds, peak 724 N |
| 75% | 450 N | **fails** — a bumper opened at `rev100` |
| 70% | 420 N | **fails** — a bumper opened at `rev100` |
| 60% | 360 N | **fails** — a bumper opened at `rev100` |

**CORRECTED 9 Nov (see §21.3).** This table was produced with a bumper gate of 1 N where the gauntlet's own gate
is 50 N — below that a rear bumper is open and rattling, not loaded. On the correct gate the tolerance is **95 %**,
not 80 %, and no rove of any quality delivers that ratio.

But the ratio was the wrong thing to measure. The sweep pinned the STRONG leg at 600 N and let the weak one fall
below it, which starves the bumpers — the failures are all "a bumper opened at `rev100`". **The binding constraint
is the absolute floor on the weakest leg, not the ratio between them**, and §21.3 shows the scheme holds at every
rove quality once the floor is respected.

### 20.3 The shock absorber on the crossed stern ropes: I was wrong

§19 left this open and predicted it would pay, because the crossed ropes are the only wave-governed elements in
the set (amplification 4,2–4,5) and carry no differential job. The gauntlet says the opposite, on every axis:

| absorber in series with the crossed ropes | min preload | wave peak | beam 0,3 m | fatal single losses |
|---|---|---|---|---|
| none — the selected arrangement | 558 N | 621 N | engaged | **0 / 4** |
| 27000 N/m | 589 N | 660 N | engaged | **2 / 4** |
| 13500 N/m | 622 N | 1076 N | **contact lost** | **2 / 4** |
| 5000 N/m | 723 N | 929 N | engaged | **2 / 4** |
| 2000 N/m | 820 N | 819 N | engaged | **2 / 4** |
| 800 N/m | 847 N | 833 N | engaged | **2 / 4** |

**Redundancy collapses from 0/4 to 2/4 at every stiffness tested**, and the failures name themselves:
`SPRING_PORT@rev100` and `SPRING_STBD@rev100`. That is the mechanism. The crossed ropes are not only the
wave-governed elements — they are the **backup load path for the springs**. At full stiffness they pick up reverse
thrust when a spring is lost. Softened, they cannot, and losing either spring becomes fatal.

The peak rises for the same reason. A soft element in a *parallel* path does not absorb the load, it **hands it to
its stiff neighbour** — and goes slack sooner, which is why both crossed ropes slack in the beam wave at every
absorber stiffness where the baseline slacks only one.

### 20.4 The general rule, which explains §19 and §20.3 together

**A series spring only reduces peaks when it is in series with the WHOLE load path.** In a coupling with parallel
redundant paths, softening any single element does two bad things at once: it transfers that element's share to
the stiff elements beside it, and it removes that element as a backup when a neighbour fails.

There is therefore **no place in this coupling for a shock absorber**, forward or aft. Not a tuning problem — a
topology one. The only configuration where an absorber would help is one with a single load path, which is exactly
the configuration §19 ruled out for having no yaw capacity.

### 20.5 What stands

Arrangement I, unchanged, at 600 N on the springs and snug on the crossed ropes. What §20 adds is **how to tension
it**: rove it as one rope through ball-bearing blocks, haul one tail, read the dynamometer **at the dead end**,
then jam each leg. Four tensioning actions become one pull and four clutch closures, with the mechanics untouched.

### 20.6 The hardware check: a stainless mooring spring lands in the worst band

The absorber in §19 and §20.3 was a stiffness, not a part. Checked against the part actually proposed - a polished
stainless mooring spring of the common type (cnautiquefrance REM0013, 340 x 75 mm, 29,95 EUR):

| | 340 x 75 mm | 390 x 90 mm |
|---|---|---|
| maximum compression load | **200 kg = 1 962 N** | not published |
| rated boat length | 9 m | 13 m |
| rated hull weight | **3 500 kg** | 10 000 kg |
| published spring rate | **none** | none |

The pair is 2 956 kg (boat 2 100 + EXO 856), so the 340 x 75 is the nominal size and the 390 x 90 the safe one.

**No vendor publishes a spring rate**, so it has to be inferred: 1 962 N over a usable travel of 100-200 mm for a
340 mm spring gives **k ~ 10 000-20 000 N/m**. INFERRED, not measured - hanging a known load and reading the
deflection would settle it in five minutes, and should be done before anyone buys one.

That band is the problem. The rope is 13 500 N/m, so this spring is **comparable to or stiffer than the rope it is
meant to soften** - and 13 500 N/m is the single worst row of the §20.3 sweep: wave peak 1 076 N against the
baseline's 621 N, and the only stiffness at which the beam wave opens both bumpers and contact is lost outright.

Two further points the datasheet settles:

1. **The 1 962 N ceiling independently kills arrangement X.** That arrangement needs 2 120 N of preload (§19.1).
   The spring bottoms out before the coupling reaches working tension.
2. **It bottoms out, and §19.3's model did not.** The sweep treated the absorber as linear with unlimited stroke,
   which flatters it; a real coil goes solid and is then rigid steel. So the real part performs no better than the
   modelled one and probably worse.

**The rubber type is the better product and changes nothing.** The other candidate checked was a Unimer wrap-around
compensator (EPDM rubber, 520 mm, 710 g, for 14-18 mm rope): the line spirals around the body, the rubber stretches,
and when the wrap is used up the rope goes straight and takes over. That inherent end-stop is better engineering
than a coil going solid - it stops absorbing rather than becoming a rigid link - and the rubber is genuinely softer
with more travel than the steel coil. It is also sized for 14-18 mm rope against the coupling's 12 mm, so the
matching model would be the 10-12 mm one.

None of that matters, and the reason is worth stating because it is why no further hardware needs checking.
**Unimer publishes no force-elongation data either**, so the brief's rule applies: where manufacturer curves are
unavailable, run a sensitivity analysis rather than invent a specification. That is what §20.3 already is. The
sweep spans 800 to 27 000 N/m, which brackets everything a rubber compensator or a steel coil of this size could
plausibly be, and **every value in that range makes the coupling worse**. The missing datasheet therefore blocks
nothing: the conclusion does not depend on which absorber, because the whole space it could occupy has been tested.

**Where these parts do belong: the dock lines from the pair to the quay.** There it is in series with the whole
load path - one line, one path - which is the only topology §20.4 says a series spring helps. That is what a
mooring spring is designed for. Inside the coupling, between parallel redundant elements, it is the wrong part in
the wrong place, and this is not a sizing problem that a different model number fixes.

## 21. Addendum (9 Nov): can it be ONE line? Yes — and here is the bill

The operator's objection to §20 is that one line is easier to handle, and it is. §19 and §20 both answered "the
single rope cannot hold `diff_opp`", which is true and is also answering a question nobody asked. **`diff_opp` is a
load case we chose.** It assumes the pods are driven in full opposition — one full ahead, one full astern. If they
are not, the yaw demand falls and a simpler rig may be enough. That turns a rigging limit into a control limit,
which is a trade worth putting numbers on rather than refusing.

`yoke` was generalised to N legs for this (`legs_m`), so one rope through blocks at every turn can now be modelled
directly. `Y_full_rove` is arrangement I's four ropes on a single tension — the rig as drawn, with no clutches.

### 21.1 The differential-thrust ceiling

The largest opposed-pod thrust each rig holds with every pure-surge case also passing. f = 1,0 is `diff_opp`
(2 396 N·m); f = 0 is both pods commanded together.

| preload | **I** — four jammed legs | **X** — springs equalised | **Y** — everything one line |
|---|---|---|---|
| 600 N | **100%** | 20% | 0% |
| 1000 N | **100%** | 40% | 0% |
| 1500 N | **100%** | 60% | 0% |
| 2000 N | **100%** | 90% | 80% |

**Y holds nothing differential below 2 000 N**, and needs **2 500 N** to hold the full case (peak 1 684 N). So one
line is possible, at **4,2× the preload and 2,2× the peak** of arrangement I — plus the thing no preload buys back:

**One rope is one failure.** Arrangement I is 0/4 fatal single losses. A single rove is 1/1 by construction, and
§18.2 already records that the crossed ropes lie on the deck edge — chafe, leadable, but chafe. One chafe-through
takes the entire coupling, under way, rather than one leg of four.

2 500 N also changes the tensioning answer: a 4:1 tackle needs 625 N at the hauling part, past what a person
sustains. One line therefore brings back the ratchet strap or winch that §20.4 had removed.

### 21.2 So the clutches are the cheapest thing in the system

Both rigs are **one continuous rope, one pull**. The only difference is whether four clutches close afterwards —
perhaps thirty seconds. That thirty seconds buys a 4,2× reduction in preload, a 2,2× reduction in peak load, full
single-failure redundancy, hand tensioning without a strap, and no differential-thrust discipline to remember.

The one-line rig is not refused. It is **priced**: if the clutches are genuinely unacceptable, rig `Y_full_rove`
at 2 500 N, protect the deck-edge leads against chafe as a safety-critical item rather than a nicety, and accept
that the coupling has no redundancy.

### 21.3 Correction: the preload spread, and what actually binds

§20.2's 80 % tolerance was computed with a bumper gate of 1 N against the gauntlet's 50 N. Re-run correctly the
ratio tolerance is 95 %, which no rove delivers — but the ratio was the wrong quantity. Holding the WEAK leg at
600 N and letting the strong one rise by the rove loss:

| rove | eta^n | weak leg | strong leg | outcome |
|---|---|---|---|---|
| ball bearing, 4 turns | 88,5 % | 600 N | 678 N | holds, peak 800 N |
| ball bearing, 6 turns | 83,3 % | 600 N | 720 N | holds, peak 822 N |
| ball bearing, 8 turns | 78,4 % | 600 N | 766 N | holds, peak 845 N |
| plain bush, 4 turns | 65,6 % | 600 N | 914 N | holds, peak 922 N |
| plain bush, 8 turns | 43,0 % | 600 N | 1 394 N | holds, peak 1 169 N |

against tail measurement, where the weak leg falls below 600 N:

| ball bearing, 4 turns | 88,5 % | 531 N | 600 N | **fails** at `rev100`, bumper 41 N |
| ball bearing, 8 turns | 78,4 % | 470 N | 600 N | **fails** at `rev100`, bumper 0 N |

**The binding constraint is the floor, not the ratio.** Every leg at or above 600 N and the arrangement holds at
any rove quality, cheap blocks included; one leg below it and a bumper opens under reverse thrust. The dead-end
measurement rule of §20.2 survives, for a better reason than the one given for it, and it is now insensitive to
hardware quality rather than dependent on ball-bearing blocks.

### 21.4 What stands

Arrangement I at 600 N, rove as one rope, **measured at the dead end**, then jammed. One pull, four clutches.
`Y_full_rove` is registered and kept as the priced alternative, not deleted.

## 22. Addendum (9 Nov): emergency release — a requirement nobody wrote down

The operator's answer to §21 is that one rope being one failure is also one rope being one **release**: if
something goes wrong, the boat is free in seconds. That is a fair reframe and it exposes a gap. **The cahier des
charges does not state an emergency-release requirement, and nothing in §1–§21 tested for one.** Every load case
asked whether the coupling holds. None asked how fast it can be made to let go, or whether letting go is safe.

It is a real requirement: a powered platform strapped to a hull on a river needs a way off, for fire, flooding,
grounding, a person in the water, or an EXO fault.

### 22.1 Letting go is not free: stored energy

Every element is a spring holding 1/2 k x^2. At release that energy goes somewhere.

| rig | preload | moored | at `diff_opp` | most energetic single element |
|---|---|---|---|---|
| **I** — four legs | 600 N | 22,9 J | **32,5 J** | SPRING_PORT, 21,4 J, 56 mm of stretch |
| **Y** — one rope | 2 500 N | 134,8 J | **167,4 J** | ROVE, **85,9 J, 113 mm of stretch** |

This inverts the safety argument for the single rope. **The one-rope rig stores 5,2x the energy, and 86 J of it
sits in the one rope you would have to cut** — 113 mm of stretch in a single line, recoiling toward whoever is
holding the knife. Arrangement I's worst single element holds 21,4 J, a quarter of that, and releasing it does not
require getting a blade onto a loaded rope at all.

So one rope buys a fast release by making the release itself the dangerous part.

### 22.2 The arrangement that gives both

Four independent legs, each ending in a **quick-release shackle at the boat cleat**, with the four lanyards led to
a single ring. One pull frees all four. That keeps §21's redundancy under way — 0/4 fatal single losses — and
still releases in one action, with a fitting designed to let go under load rather than a knife on a loaded rope.
Working loads of 600–850 N are modest for sailing-grade release shackles.

Strictly better than the single rope on both axes: same one-action release, a quarter of the energy per element,
and full redundancy retained.

### 22.3 But sequential release has one sharp edge

Lanyards never let go at the same instant, so the real question is what the remaining ropes see as they go one at
a time:

| state | 4 ropes | 3 ropes | 2 ropes | 1 rope |
|---|---|---|---|---|
| moored | 491 N | 173 N | 147 N | 0 N |
| forward 100 % | 411 N | 171 N | 135 N | 0 N |
| **`diff_opp`** | 761 N | **2 419 N** | 583 N, **unrestrained** | 2 419 N |

With the pods neutral or driving together, release is completely benign — loads fall monotonically to zero as the
legs go. **Under full differential thrust it spikes to 2 419 N on a remaining leg, 3,2x the four-rope load**, and
by two ropes the boat is no longer restrained at all. Nothing breaks (MBL is 9,5 kN) but the coupling is briefly
carrying three times its design load in an uncontrolled state.

**So the release procedure has an interlock: pods to neutral, THEN release.** Ideally the same action does both —
a release that cuts propulsion before freeing the shackles. That is a control requirement, not a rigging one, and
it is now on the list.

### 22.4 What this changes

Arrangement I is unchanged mechanically. What changes is the **fittings at the boat end** — quick-release shackles
rather than plain eyes or bowlines — and a new requirement for the specification:

> **R-REL.** The coupling shall be releasable from the EXO in a single action, under load, without tools, and that
> action shall cut propulsion before or as it frees the boat.

Not modelled and still open: the separation transient (two free bodies in water), and whether the rear bumpers
push the hulls apart usefully or merely drop contact. Both matter for what happens in the five seconds after the
ring is pulled, and neither is a static question.

## 23. Addendum (9 Nov): the build — webbing against rope on the springs

Specifying what to actually buy raised a question the study had never asked: every run so far assumed 12 mm rope
everywhere, at the one stiffness K_ROPE["mid"] = 13 500 N/m. A ratchet strap is far stiffer, and it is also its own
tensioner, which would delete the tackle, the cleat and the clutch from the springs entirely. Worth measuring.

| spring element | min preload | wave peak | boat roll | fatal single losses |
|---|---|---|---|---|
| 12 mm rope, 13 500 N/m | **600 N** | 647 N | 10,20° | 0/4 |
| webbing ~50 000 N/m | **600 N** | **524 N** | 9,97° | 0/4 |
| webbing ~100 000 N/m | 800 N | 533 N | 9,86° | 0/4 |
| webbing ~150 000 N/m | 1 000 N | 536 N | 9,76° | 0/4 |
| webbing ~250 000 N/m | 1 600 N | 600 N | 9,68° | 0/4 |

**Stiffer springs lower the peak**, which is not obvious until you see where the peak lives: it is in the CROSSED
ropes, which are wave-governed. Stiffening the springs reduces the boat's motion, so the crossed ropes see less.
Every webbing case beats rope on peak load, on roll, and ties it on redundancy.

The cost is preload. The optimum sits near **50 000 N/m**, and above it the preload needed for `diff_opp` climbs:
600 → 800 → 1 000 → 1 600 N.

### 23.1 Which band is a real strap in? Unpublished, and it straddles the optimum

For 25 mm polyester webbing over the spring's 1,88 m, taking the usual 7–10 % elongation at break:

| strap | stretch at 600 N | implied k |
|---|---|---|
| 800 kg MBL, 7 % | 10,1 mm | **60 kN/m** |
| 2 000 kg MBL, 10 % | 5,8 mm | 104 kN/m |
| 2 000 kg MBL, 7 % | 4,0 mm | 149 kN/m |
| 5 000 kg MBL, 7 % | 1,6 mm | 373 kN/m |

So the **lighter** strap is the better one mechanically — which inverts the usual instinct to buy the strongest.
But an 800 kg strap is 7,8 kN MBL against the 9,5 kN the springs require, so the strap soft enough to be optimal
is too weak, and the strap strong enough is too stiff. That bind is real.

Worse, this table is the WEBBING alone. The ratchet mechanism, the wrap on the mandrel and the hooks all add
compliance, so installed stiffness is lower than these figures and **nobody publishes it**. The brief's rule
applies again: unknown, so either bound it or measure it.

**Measuring it takes five minutes**: rig the strap, pull to 600 N on the gauge, measure the extension. k = 600/x.
Until that is done, a strap-sprung build must be preloaded to **1 000 N** to cover the stiff case — which is still
a better peak (536 N) than rope at 600 N (647 N), but presses harder on the one gate that is already open: **the
host boat's cleat ratings are unknown** (§18.1), and 1 000 N is two-thirds more pull-out load than 600 N.

### 23.2 Build decision

**Crossed stern ropes: 12 mm polyester rope, always.** They are the wave-governed elements and §18.2 requires them
to stay the longest, softest elements in the set. Webbing there would be the wrong direction.

**Midship springs: rope at 600 N by default**, because it keeps the least load on unrated cleats, and the stiffness
is known rather than inferred. Ratchet straps are the better choice on peak load and much the better choice on
handling — they are their own tensioner — and become the recommendation the moment either of two things happens:
the strap's installed stiffness is measured, or the cleats are rated and 1 000 N is shown to be comfortable.

### 23.3 A limitation this exposed

The model carries ONE rope stiffness for every rope regardless of length. Real axial stiffness goes as 1/L, so the
1,88 m spring and the 3,60 m crossed rope cannot both be 13 500 N/m — they should differ by about a factor of two.
This has been true since §1 and does not change any ranking, since every arrangement was compared on the same
assumption, but it means the absolute stiffnesses are nominal. Fixing it is a per-element EA/L, and it should be
done before any number here is used as a procurement specification rather than a comparison.
