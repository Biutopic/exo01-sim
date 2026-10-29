"""Render results/verification/verification_report.json as Markdown (verification_report.md)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
p = ROOT / "results" / "verification" / "verification_report.json"
rep = json.loads(p.read_text())
L = ["# Numerical verification report — EXO-01 exploratory model", "",
     f"Generated {rep['generated']} · pytest: {rep['pytest']['summary']} · overall: **{'ALL CHECKS PASSED' if rep['all_checks_passed'] else 'SOME CHECKS FAILED'}** ({rep['seconds']:.0f} s)", "",
     "Verification = the code solves its own equations to the stated tolerance. It is **not** validation against the physical EXO-01 (no measurement exists yet).", "",
     "| # | check | acceptance | actual | result |", "|---|---|---|---|---|"]
for i, c in enumerate(rep["checks"], 1):
    L.append(f"| {i} | {c['name']} | {c['tolerance']} | {c['actual']} | {'PASS' if c['passed'] else 'FAIL'} |")
L += ["", "## Tessellation convergence of the analytic buoyancy test body (capsule r=0.29 m, L=1.6 m, five waterlines)", "",
      "| n_circ | n_axial | n_cap | triangles | max rel. error volume | max rel. error waterplane area |", "|---|---|---|---|---|---|"]
for r in rep["buoyancy_tessellation_convergence"]:
    L.append(f"| {r['n_circ']} | {r['n_axial']} | {r['n_cap']} | {r['triangles']} | {r['max_rel_err_volume']:.2e} | {r['max_rel_err_waterplane_area']:.2e} |")
L += ["", "## Equilibrium vs float tessellation (illustrative configuration)", "", "| resolution | trim [deg] | heel [deg] | max draft [m] | min deck freeboard [m] | displaced volume [m3] |", "|---|---|---|---|---|---|"]
for r in rep["equilibrium_tessellation_convergence"]:
    L.append(f"| {r['resolution']} | {r['trim_deg']:.5f} | {r['heel_deg']:.5f} | {r['draft_max_m']:.5f} | {r['lower_deck_freeboard_min_m']:.5f} | {r['displaced_volume_m3']:.6f} |")
b = rep["bem_panel_convergence"]
L += ["", f"## BEM panel-size convergence (omegas {b['omegas']} rad/s; relative change vs the finest mesh h=0.08 m)", "",
      "| panel size [m] | faces | A33 | B33 | A44 | A55 | F3 head 0 | F4 beam | F2 beam | F5 head 0 |", "|---|---|---|---|---|---|---|---|---|---|"]
for r in b["rows"]:
    d = r["rel_diff_to_finest"]
    cell = lambda k: " / ".join(f"{100*x:.1f}%" for x in d[k])
    L.append(f"| {r['panel_size']} | {r['n_faces']} | {cell('A33')} | {cell('B33')} | {cell('A44')} | {cell('A55')} | {cell('F3_head0')} | {cell('F4_beam')} | {cell('F2_beam')} | {cell('F5_head0')} |")
fr = rep["frequency_resolution"]
L += ["", f"## Frequency-grid resolution (RAO at heading {fr['heading_deg']} deg, reference: {fr['reference']})", "",
      f"Gap-resonance bands detected: {[(round(a, 2), round(b_, 2)) for a, b_ in fr['gap_resonance_bands_rad_s']]} rad/s", "",
      "| grid | n omega | max rel. RAO error outside bands (surge/sway/heave/roll/pitch/yaw) | inside bands |", "|---|---|---|---|"]
for r in fr["rows"]:
    o = " / ".join(f"{100*v:.2f}%" for v in r["max_rel_err_outside_bands"].values())
    i = " / ".join("-" if v is None else f"{100*v:.0f}%" for v in r["max_rel_err_inside_bands"].values())
    L.append(f"| {r['grid']} | {r['n_omega']} | {o} | {i} |")
hi = rep["heading_interpolation"]
L += ["", f"## Heading interpolation fallback ({hi['note']})", "", "Error of the periodic cubic spline at 15-deg nodes not in the grid, relative to the DOF's peak excitation over all headings and omegas:", "",
      "| heading step | " + " | ".join(f"ω={w} (λ/L={l:.1f})" for w, l in hi["rows"][0]["wavelength_over_body_length"].items()) + " |", "|---|" + "---|" * len(hi["rows"][0]["max_err_rel_to_global_peak_by_omega"])]
for r in hi["rows"]:
    L.append(f"| {r['heading_step_deg']:.0f} deg | " + " | ".join(f"{100*e:.1f}%" for e in r["max_err_rel_to_global_peak_by_omega"].values()) + " |")
t = rep["time_step_convergence"]
L += ["", f"## Time-step convergence (RK4 on the 6-DOF equation with coefficients frozen at omega={t['omega']:.3f} rad/s, T={t['period_s']:.2f} s, vs the frequency-domain amplitudes)", "",
      "| steps per period | dt [s] | periods integrated | max rel. amplitude error |", "|---|---|---|---|"]
for r in t["results"]:
    L.append(f"| {r['steps_per_period']} | {r['dt_s']:.4f} | {r['n_periods']} | {r['max_rel_amp_error']:.2e} |")
L.append(f"\nObserved convergence orders between successive refinements: {[round(x, 1) for x in t['observed_order']]} (RK4: 4).")
n = rep["natural_frequencies_illustrative"]
L += ["", "## Natural frequencies (illustrative configuration, undamped, potential-flow added mass)", "",
      "uncoupled roots (rad/s): " + "; ".join(f"{k}: {[round(x, 3) for x in v]}" for k, v in n["uncoupled_roots"].items()),
      "", f"coupled roots (rad/s): {[round(x, 3) for x in n['coupled_roots']]} labelled {n['coupled_labels']}", "",
      f"gap-resonance bands (rad/s): {[(round(a, 2), round(b_, 2)) for a, b_ in n['gap_resonance_bands_rad_s']]}", "", n["note"]]
if "two_body_panel_convergence" in rep:
    tb = rep["two_body_panel_convergence"]
    L += ["", f"## Two-body BEM (EXO floats + Renaud 8000 hull proxy) panel convergence, omegas {tb['omegas']} rad/s (relative change vs the finest set)", "",
          "| panels EXO/boat [m] | faces | A EXO heave | A boat heave | A coupling heave | B boat roll | F boat heave | F EXO roll |", "|---|---|---|---|---|---|---|---|"]
    for r in tb["rows"]:
        d = r["rel_diff_to_finest"]
        cell = lambda k: " / ".join("-" if x is None else f"{100*x:.1f}%" for x in d[k])
        L.append(f"| {r['panels'][0]} / {r['panels'][1]} | {r['n_faces']} | {cell('A_exo_heave')} | {cell('A_boat_heave')} | {cell('A_couple_heave')} | {cell('B_boat_roll')} | {cell('F_boat_heave')} | {cell('F_exo_roll')} |")
    ex = rep.get("two_body_example_wave")
    if ex:
        L += ["", f"Example two-body response, H={ex['H']} m, T={ex['T']} s, heading {ex['heading_deg']} deg (coarse grid, 5 % damping):", ""]
        for bn, bo in ex["bodies"].items():
            L.append(f"- {bn}: heave {bo['amplitude']['heave']:.3f} m, sway {bo['amplitude']['sway']:.3f} m, roll {bo['amplitude_deg']['roll']:.2f} deg, pitch {bo['amplitude_deg']['pitch']:.2f} deg")
        for ln in ex["lines"]:
            L.append(f"- {ln['id']}: dynamic tension {ln['dynamic_tension_amp_N']:.0f} N vs pretension {ln['pretension_N']:.0f} N -> {'SLACK (nonlinear, not modelled)' if ln['goes_slack'] else 'stays taut'}")
(p.with_suffix(".md")).write_text("\n".join(L))
print("\n".join(L[:12]))
