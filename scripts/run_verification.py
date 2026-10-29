"""Numerical verification with actual errors. Writes results/verification/verification_report.{json,md}.

Distinguishes NUMERICAL VERIFICATION (is the code solving its equations correctly?) from VALIDATION (does the model
match a physical EXO-01?). Nothing here is a validation: no physical measurement exists yet.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results" / "verification"
OUT.mkdir(parents=True, exist_ok=True)

from exo01.analysis import build_response, evaluate, strip_private  # noqa: E402
from exo01.buoyancy import CapsuleX, wet_integrals, signed_volume  # noqa: E402
from exo01.config import load_config, load_scenario, resolve, resolve_scenario  # noqa: E402
from exo01.hydro import compute_hydro, HydroData  # noqa: E402
from exo01.response import time_domain_check  # noqa: E402
from exo01.reference import Reference, step_units_and_extent  # noqa: E402

RHO, G = 999.0, 9.80665          # fresh water (Erdre) - the illustrative configuration's density
rep = {"generated": time.strftime("%Y-%m-%d %H:%M:%S"), "checks": []}


def check(name, tol_text, actual, passed, detail=None):
    rep["checks"].append(dict(name=name, tolerance=tol_text, actual=actual, passed=bool(passed), detail=detail))
    print(("PASS " if passed else "FAIL ") + name, actual)


def timed(label, f):
    t = time.time()
    r = f()
    print(f"  [{label}: {time.time() - t:.1f}s]")
    return r


# ------------------------------------------------------------------ 0. pytest
def run_pytest():
    p = subprocess.run([sys.executable, "-m", "pytest", "tests", "-q", "-p", "no:cacheprovider", "--junitxml", str(OUT / "pytest.xml")],
                       cwd=ROOT, capture_output=True, text=True)
    tail = p.stdout.strip().splitlines()[-1]
    rep["pytest"] = dict(summary=tail, returncode=p.returncode)
    print("pytest:", tail)


# ------------------------------------------------------------------ 1. units / transforms / mass accounting
def reference_checks():
    ref = Reference(ROOT / "data" / "reference_v3")
    unit, scale, (lo, hi) = step_units_and_extent(ROOT / "data/reference_v3/EXO01_reference.step")
    glo, ghi = ref.model_bounds_cad()
    err = float(np.max(np.abs(hi - ghi)))
    check("STEP unit = mm and extent (max side) equals GLB metres", "<= 3 mm", f"unit={unit}, max |dx| = {err*1000:.3f} mm", unit == "mm" and err < 3e-3)
    p = np.array([1.3, -1.97, -0.29])
    d = float(np.abs(ref.cad_to_gltf(p) - [1.3, -0.29, 1.97]).max())
    check("CAD->glTF conversion (x,y,z)->(x,z,-y), applied once", "exact", f"max error {d:.1e}", d < 1e-12)
    expect = ref.artifact_validation["model_bounds_cad_m"]
    e = float(max(np.abs(glo - expect["minimum"]).max(), np.abs(ghi - expect["maximum"]).max()))
    check("GLB child bounds equal documented CAD bounds (no 2nd axis conversion)", "<= 1e-6 m", f"{e:.1e} m", e < 1e-6)
    tot = ref.total_listed_mass()
    check("Mass accounting: sum of 16 parents counted once", "840 kg exactly", f"{tot} kg; stray child masses: {ref.stray_mass_keys()}", tot == 840.0 and not ref.stray_mass_keys())
    fl = ref.float_surface_params()
    vglb = sum(v["tessellated_volume_m3"] for v in fl.values())
    ill = evaluate(resolve(load_config("illustrative"), {"host_boat": {"included": False}}))
    vprox = ill["buoyant_volume_total_m3"]
    from exo01.config import load_scenario
    glb_scen = evaluate(resolve(load_config("illustrative"), load_scenario("floats_glb_capsules")["overrides"]))
    vcap = glb_scen["buoyant_volume_total_m3"]
    check("Revision-3 float proxies (scenario floats_glb_capsules: capsules fitted to the GLB) vs GLB tessellated volume", "<= 1.5 %",
          f"capsules {vcap:.4f} m3 vs GLB {vglb:.4f} m3 ({(vcap/vglb-1)*100:+.2f} %)", abs(vcap / vglb - 1) < 0.015)
    check("Production floats (Flofiz 1.60 x D0.60 m, component list) vs GLB proxies: volume difference reported", "informational",
          f"Flofiz {vprox:.4f} m3 vs GLB {vglb:.4f} m3 ({(vprox/vglb-1)*100:+.2f} %): the drawing's proxies are smaller than the real floats", True)
    return ill


# ------------------------------------------------------------------ 2. analytic buoyancy
def analytic_buoyancy():
    r, Lc = 0.29, 1.02
    van = lambda d: (r * r * np.arccos(-d / r) + d * np.sqrt(r * r - d * d)) * Lc + np.pi * (d + r) ** 2 * (3 * r - (d + r)) / 3
    aan = lambda d: Lc * 2 * np.sqrt(r * r - d * d) + np.pi * (r * r - d * d)
    rows = []
    for n_circ, n_ax, n_cap in [(16, 4, 4), (32, 6, 8), (64, 12, 16), (96, 12, 24), (192, 24, 48)]:
        cap = CapsuleX("c", (0, 0, 0), 1.6, r, n_circ, n_ax, n_cap)
        T = cap.triangles()
        ev = max(abs(wet_integrals(T - np.array([0, 0, d]))["V"] / van(d) - 1) for d in (-0.2, -0.1, 0.0, 0.1, 0.25))
        ea = max(abs(wet_integrals(T - np.array([0, 0, d]))["Awp"] / aan(d) - 1) for d in (-0.2, -0.1, 0.0, 0.1, 0.25))
        rows.append(dict(n_circ=n_circ, n_axial=n_ax, n_cap=n_cap, triangles=len(T), max_rel_err_volume=ev, max_rel_err_waterplane_area=ea))
    rep["buoyancy_tessellation_convergence"] = rows
    base = rows[3]    # (96, 12, 24) = still-water default
    check("Analytic buoyancy test body (capsule, 5 waterlines): volume", "<= 1e-3 (default tessellation)", f"{base['max_rel_err_volume']:.2e}", base["max_rel_err_volume"] < 1e-3)
    check("Analytic buoyancy test body: waterplane area", "<= 1e-3", f"{base['max_rel_err_waterplane_area']:.2e}", base["max_rel_err_waterplane_area"] < 1e-3)
    # Flofiz float (v0.4 production surface): closed, outward, volume vs analytic pi r^2 (L_body + L_nose / 2), both nose directions
    from exo01.buoyancy import FlofizX, MeshSurface, signed_volume
    worst = 0.0
    for nd in (1, -1):
        f = FlofizX("f", 2.1, nd, (-1.97, -0.30), n_circ=96, n_axial=12, n_cap=24)
        T = f.triangles()
        key = np.round(T.reshape(-1, 3) / 1e-9).astype(np.int64)
        u, inv = np.unique(key, axis=0, return_inverse=True)
        chk = MeshSurface("m", u * 1e-9, inv.reshape(-1, 3)).check()
        worst = max(worst, abs(signed_volume(T) / f.analytic_volume() - 1))
        assert chk["closed"] and chk["outward"], chk
    rep["flofiz_float"] = dict(analytic_volume_m3=f.analytic_volume(), max_rel_err_volume=worst)
    check("Flofiz float surface (both nose directions): closed, outward, volume vs analytic", "<= 2e-4", f"{worst:.2e}", worst < 2e-4)


# ------------------------------------------------------------------ 3. equilibrium
def equilibrium_checks():
    out = {}
    for nm in ("baseline_illustrative", "battery_relocated", "occupants_symmetric", "occupants_asymmetric"):
        r = evaluate(resolve_scenario(load_scenario(nm)))
        e = r["equilibrium"]
        Mg = e["residuals"]["weight_N"]
        res = max(abs(e["residuals"]["Fz_N"]), abs(e["residuals"]["Mx_Nm"]), abs(e["residuals"]["My_Nm"])) / Mg
        out[nm] = dict(residual_relative=res, **e["residuals"])
        check(f"Equilibrium residuals [{nm}]", "|Fz|,|Mx|,|My| <= 1e-9 * M g", f"max {res:.1e} (Fz {e['residuals']['Fz_N']:.1e} N, Mx {e['residuals']['Mx_Nm']:.1e}, My {e['residuals']['My_Nm']:.1e} N m)", res < 1e-9)
    sym = evaluate(resolve(load_config("illustrative"), {"components": {"ELECTRONICS_50": {"com_m": [1.6, 0.0, 0.95]}}, "host_boat": {"included": False}}))
    e = sym["equilibrium"]
    v = e["per_float_volume_m3"]
    dv = max(abs(v[f"FLOAT_NEG_Y_{k}"] - v[f"FLOAT_POS_Y_{k}"]) for k in (1, 2, 3))
    check("Deliberately symmetric load: heel and port/starboard float volumes", "|heel| <= 1e-10 rad, |dV| <= 1e-12 m3", f"heel {e['heel_rad']:.1e} rad, max dV {dv:.1e} m3", abs(e["heel_rad"]) < 1e-10 and dv < 1e-12)
    rep["equilibrium_residuals"] = out
    # tessellation convergence of the equilibrium
    rows = []
    for res in (dict(n_circ=24, n_axial=4, n_cap=6), dict(n_circ=48, n_axial=8, n_cap=12), dict(n_circ=96, n_axial=16, n_cap=24), dict(n_circ=192, n_axial=32, n_cap=48)):
        e = evaluate(resolve(load_config("illustrative"), {"host_boat": {"included": False}}), resolution=res)["equilibrium"]
        rows.append(dict(resolution=res, trim_deg=e["trim_deg"], heel_deg=e["heel_deg"], draft_max_m=e["freeboard"]["draft_max_m"],
                         lower_deck_freeboard_min_m=e["freeboard"]["lower_deck_freeboard_min_m"], displaced_volume_m3=e["displaced_volume_m3"]))
    rep["equilibrium_tessellation_convergence"] = rows
    d = abs(rows[-1]["draft_max_m"] - rows[-2]["draft_max_m"])
    dt = abs(rows[-1]["trim_deg"] - rows[-2]["trim_deg"])
    check("Equilibrium mesh convergence (fine vs finer)", "|d draft| <= 5e-4 m, |d trim| <= 0.01 deg", f"d draft {d:.1e} m, d trim {dt:.1e} deg", d < 5e-4 and dt < 0.01)


# ------------------------------------------------------------------ 4. BEM convergence
def bem_panel_convergence(ill):
    eq, asm = ill["_eq"], ill["_assembly"]
    omegas = np.array([0.8, 2.0, 3.5])
    heads = np.array([0.0, np.pi / 2])
    rows = []
    for h in (0.20, 0.15, 0.12, 0.10, 0.08):
        hd = timed(f"BEM h={h}", lambda: compute_hydro(asm.surfaces, eq, omegas, heads, RHO, G, None, h))
        rows.append(dict(panel_size=h, n_faces=hd.meta["n_faces"],
                         A33=hd.A[:, 2, 2].tolist(), B33=hd.B[:, 2, 2].tolist(), A44=hd.A[:, 3, 3].tolist(), A55=hd.A[:, 4, 4].tolist(),
                         F3_head0=np.abs(hd.F[:, 0, 2]).tolist(), F4_beam=np.abs(hd.F[:, 1, 3]).tolist(), F2_beam=np.abs(hd.F[:, 1, 1]).tolist(),
                         F5_head0=np.abs(hd.F[:, 0, 4]).tolist()))
    ref = rows[-1]
    keys = ["A33", "B33", "A44", "A55", "F3_head0", "F4_beam", "F2_beam", "F5_head0"]
    for r in rows:
        r["rel_diff_to_finest"] = {k: [float(abs(a / b - 1)) for a, b in zip(r[k], ref[k])] for k in keys}
    rep["bem_panel_convergence"] = dict(omegas=omegas.tolist(), rows=rows)
    r12 = rows[2]    # h = 0.12 (app default) vs 0.08
    worst = max(max(v) for v in r12["rel_diff_to_finest"].values())
    check("BEM panel-size convergence: default h=0.12 vs h=0.08 (A, B, F on 3 omegas)", "<= 3 %", f"worst relative change {worst*100:.2f} %", worst < 0.03,
          detail={k: [f"{x*100:.2f}%" for x in v] for k, v in r12["rel_diff_to_finest"].items()})
    return rows


# ------------------------------------------------------------------ 5. frequency resolution
def frequency_resolution(ill, cfg):
    """Reference: 0.05 rad/s grid + 0.025 rad/s inside the gap-resonance bands (no interpolation at those nodes).
    Test grids: the app default (0.10 + refinement at 0.05 inside bands), 0.10 without refinement, 0.20."""
    from exo01.hydro import detect_gap_bands
    eq, asm = ill["_eq"], ill["_assembly"]
    om = np.round(np.arange(0.5, 6.0001, 0.05), 10)
    heads = np.array([np.pi / 3])                     # exact heading used by the test (no heading interpolation)
    base = timed("BEM reference 0.05 grid", lambda: compute_hydro(asm.surfaces, eq, om, heads, RHO, G, None, 0.12, refine_bands=False))
    bands = detect_gap_bands(base.omegas, base.A, base.B)
    extra = np.array(sorted({float(x) for lo, hi in bands for x in np.round(np.arange(lo, hi + 1e-9, 0.025), 10)} - set(np.round(om, 10))))
    fine_band = timed(f"BEM band reference 0.025 ({len(extra)} omegas)", lambda: compute_hydro(asm.surfaces, eq, extra, heads, RHO, G, None, 0.12, refine_bands=False))
    ref = base.merged_with(fine_band)
    model_ref = build_response(ill, ref, cfg)
    beta = np.pi / 3
    X_ref = np.array([model_ref.rao(w, beta) for w in ref.omegas])
    inband = np.zeros(len(ref.omegas), bool)
    for lo, hi in bands:
        inband |= (ref.omegas >= lo) & (ref.omegas <= hi)
    rows = []
    dofn = ["surge", "sway", "heave", "roll", "pitch", "yaw"]

    def test_grid(name, omegas_sel):
        sel = np.isin(np.round(ref.omegas, 10), np.round(omegas_sel, 10))
        hd = HydroData(ref.omegas[sel], heads, ref.A[sel], ref.B[sel], ref.F[sel], ref.meta)
        m = build_response(ill, hd, cfg)
        mask = ~sel
        X = np.array([m.rao(w, beta) for w in ref.omegas[mask]])
        rel = np.abs(X - X_ref[mask]) / np.maximum(np.abs(X_ref[mask]), 1e-3 * np.abs(X_ref).max(0))
        ib = inband[mask]
        rows.append(dict(grid=name, n_omega=int(sel.sum()),
                         max_rel_err_outside_bands={d: float(rel[~ib, i].max()) for i, d in enumerate(dofn)},
                         max_rel_err_inside_bands={d: float(rel[ib, i].max()) if ib.any() else None for i, d in enumerate(dofn)}))
    g01 = np.round(np.arange(0.5, 6.0001, 0.1), 10)
    refined = np.array(sorted(set(g01) | {float(x) for lo, hi in bands for x in np.round(np.arange(lo, hi + 1e-9, 0.05), 10) if 0.5 <= x <= 6.0}))
    test_grid("0.10 + 0.05 in bands (app default)", refined)
    test_grid("0.10 only", g01)
    test_grid("0.20 only", np.round(np.arange(0.5, 6.0001, 0.2), 10))
    rep["frequency_resolution"] = dict(reference="0.05 rad/s everywhere + 0.025 rad/s inside gap-resonance bands", heading_deg=60,
                                       gap_resonance_bands_rad_s=bands, rows=rows)
    r = rows[0]
    wo = max(r["max_rel_err_outside_bands"].values())
    wi = max(v for v in r["max_rel_err_inside_bands"].values() if v is not None)
    check("Frequency-grid resolution OUTSIDE gap-resonance bands (app default grid vs reference nodes)",
          "<= 2 % (set at the BEM panel-convergence level)", f"max {wo*100:.3f} %", wo < 0.02, detail=rows)
    check("Frequency-grid resolution INSIDE gap-resonance bands (app default grid)", "reported, no acceptance: potential-flow resonances are "
          "sharp and physically over-predicted; results there are flagged in the UI", f"max {wi*100:.1f} %", True, detail=rows)
    nat = model_ref.natural_frequencies()
    rep["natural_frequencies_illustrative"] = nat
    return ref


# ------------------------------------------------------------------ 6. heading interpolation (informational)
def heading_interpolation(ill, cfg, ref):
    """The app solves the diffraction problem at the exact requested heading, so no heading interpolation enters the
    results. This check documents why: the periodic-spline fallback on a 30 deg grid is only adequate for long waves
    (kL small); error = |F_interp - F_BEM| at 15 deg nodes not in the grid, relative to the DOF's peak over all headings and omegas."""
    eq, asm = ill["_eq"], ill["_assembly"]
    om = np.array([1.0, 2.0, 3.0, 4.5, 6.0])
    heads = np.arange(0, 360, 15) * np.pi / 180
    hd = timed("BEM 5 omegas x 24 headings", lambda: compute_hydro(asm.surfaces, eq, om, heads, RHO, G, None, 0.12, refine_bands=False))
    scale = np.abs(hd.F).max(axis=(0, 1))
    rows = []
    for stride in (3, 2):
        idx = np.arange(0, len(heads), stride)
        hs = HydroData(om, heads[idx], hd.A, hd.B, hd.F[:, idx, :], hd.meta)
        per = {}
        for i, w in enumerate(om):
            per[float(w)] = float(max(np.max(np.abs(hs.excitation(w, heads[j]) - hd.F[i, j]) / scale) for j in range(len(heads)) if j not in idx))
        rows.append(dict(heading_step_deg=float(np.degrees(heads[idx][1] - heads[idx][0])), n_headings=len(idx),
                         max_err_rel_to_global_peak_by_omega=per, wavelength_over_body_length={float(w): float(2 * np.pi * G / w ** 2 / 4.95) for w in om}))
    rep["heading_interpolation"] = dict(note="informational: the app uses exact headings; interpolation is a fallback only", rows=rows)
    r30 = rows[-1]
    check("Heading interpolation fallback (30 deg grid) - informational, not used for results", "reported only",
          "err/peak by omega: " + ", ".join(f"w={w:.1f}: {100*e:.1f}%" for w, e in r30["max_err_rel_to_global_peak_by_omega"].items()), True, detail=rows)


# ------------------------------------------------------------------ 7. time-step
def time_step(model):
    damp = {"zeta": {"heave": 0.3, "roll": 0.3, "pitch": 0.3}, "absolute": {"surge": 2000, "sway": 2000, "yaw": 4000}}
    res = time_domain_check(model, 2 * np.pi / 4.0, np.pi / 3, 0.3, damp, steps_per_period=(8, 16, 32, 64, 128))
    rep["time_step_convergence"] = res
    e = [r["max_rel_amp_error"] for r in res["results"]]
    order = [float(np.log2(e[i] / e[i + 1])) for i in range(len(e) - 1)]
    rep["time_step_convergence"]["observed_order"] = order
    check("Time integration (RK4, fixed coefficients) vs frequency-domain solve", "error decreases ~dt^4; <= 1e-4 at T/64", f"errors {[f'{x:.1e}' for x in e]}, observed orders {[round(o, 1) for o in order]}", e[-2] < 1e-4 and all(e[i] > e[i + 1] for i in range(len(e) - 1)))


# ------------------------------------------------------------------ 8. two bodies (EXO + Hydronaute)
def two_body_checks():
    from exo01.boat import hull_envelope, check_closed
    from exo01.buoyancy import signed_volume
    from exo01.hydro import compute_hydro_bodies
    from exo01.analysis import hydro_specs
    from exo01.response import line_stiffness
    P = json.loads((ROOT / "data/renaud8000_v1/parameters.json").read_text())
    h = hull_envelope(P["hull_stations_mm"], P["topside_top_z_mm"])
    V, F = h.vertices, h.faces
    de = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    key = de[:, 0] * len(V) + de[:, 1]
    consistent = len(np.unique(key)) == len(key) and np.isin(key, de[:, 1] * len(V) + de[:, 0]).all()
    v0 = signed_volume(V[F])
    hf = hull_envelope(P["hull_stations_mm"], P["topside_top_z_mm"], dx_max=0.05, ds_max=0.05)
    vf = signed_volume(hf.vertices[hf.faces])
    check("Boat hull proxy: closed, consistently oriented, volume invariant under subdivision (ruled surface)", "closed; |dV/V| <= 1e-9",
          f"closed={check_closed(F)}, consistent={consistent}, V={v0:.4f} m3, |dV/V|={abs(vf / v0 - 1):.1e}", check_closed(F) and consistent and abs(vf / v0 - 1) < 1e-9)
    cfg = resolve(load_config("illustrative"), {"components": {"ELECTRONICS_50": {"com_m": [1.6, 0.0, 0.95]}}})
    r = evaluate(cfg)
    from exo01.twobody import evaluate_boat
    bo, _, beq0 = evaluate_boat(cfg, RHO_F, G)
    be0 = bo["equilibrium"]
    Mg = be0["residuals"]["weight_N"]
    res0 = max(abs(be0["residuals"]["Fz_N"]), abs(be0["residuals"]["Mx_Nm"]), abs(be0["residuals"]["My_Nm"])) / Mg
    check("Boat alone: equilibrium residuals (2100 kg archival, proxy hull)", "<= 1e-9 * M g",
          f"{res0:.1e}; draft {be0['draft_hull_proxy_m']:.3f} m, GM_T {bo['stability_static']['GM_transverse_m']:.2f} m", res0 < 1e-9)
    ce = r["coupled_equilibrium"]
    be = r["bodies"]["boat"]["equilibrium"]
    lines = r["lines"]
    Fz_lines_exo = sum(l["tension_N"] * l["unit"][2] for l in lines)
    hydro_imbalance_exo = r["equilibrium"]["residuals"]["Fz_N"]
    check("EXO + boat coupled static equilibrium (buoyancy + weight + tension-only lines): residual and force consistency",
          "residual <= 1e-8 Mg; EXO hydrostatic imbalance == -vertical line force",
          f"residual {ce['residual_relative']:.1e}, lines {', '.join(f'{l['id']} {l['tension_N']:.0f} N' for l in lines)}, boat shift {ce['boat_shift_from_nominal']['dx_m']*1000:.0f} mm, "
          f"EXO hydrostatic Fz {hydro_imbalance_exo:.1f} N vs line Fz {Fz_lines_exo:.1f} N",
          ce["converged"] and ce["residual_relative"] < 1e-8 and abs(hydro_imbalance_exo + Fz_lines_exo) < 1e-6 * Mg)
    rep["two_body_still_water"] = dict(boat=strip_private(r["bodies"]["boat"]), clearances=r["clearances"], lines=r["lines"])
    ce = np.array(r["bodies"]["exo"]["pose"]["com_world"]); cb = np.array(r["bodies"]["boat"]["pose"]["com_world"])
    lines = [dict(l, body_i=0, body_j=1, pretension_N=0.0) for l in r["lines"]]
    K, _ = line_stiffness(lines, [ce, cb])
    Om = np.array([0.1, 0.2, 0.3]); q = np.concatenate([np.zeros(3), Om, np.cross(Om, cb - ce), Om]); q2 = np.zeros(12); q2[0] = q2[6] = 1
    nul = max(np.abs(K @ q).max(), np.abs(K @ q2).max()) / np.abs(K).max()
    check("Line-spring stiffness: symmetric PSD, rigid translation/rotation of both bodies in its null space", "<= 1e-9 (relative)",
          f"sym={np.allclose(K, K.T)}, min eig/max = {np.linalg.eigvalsh(K).min() / np.abs(K).max():.1e}, null-space residual {nul:.1e}", np.allclose(K, K.T) and nul < 1e-9)
    # two-body BEM: heading antisymmetry and panel convergence (coarse grids, cached)
    om = np.array([1.0, 2.0, 3.0])
    rows = []
    for he, hb in ((0.25, 0.35), (0.20, 0.30), (0.15, 0.22)):
        hd = timed(f"two-body BEM EXO {he} / boat {hb}", lambda: compute_hydro_bodies(hydro_specs(r, cfg, dict(dx_max=hb, ds_max=hb)), om, [np.pi / 2, 3 * np.pi / 2], RHO_F, G, None, panel_sizes=[he, hb], refine_bands=False))
        rows.append(dict(panels=[he, hb], n_faces=hd.meta["n_faces"], A_exo_heave=hd.A[:, 2, 2].tolist(), A_boat_heave=hd.A[:, 8, 8].tolist(),
                         A_couple_heave=hd.A[:, 2, 8].tolist(), B_boat_roll=hd.B[:, 9, 9].tolist(), F_boat_heave=np.abs(hd.F[:, 0, 8]).tolist(), F_exo_roll=np.abs(hd.F[:, 0, 3]).tolist(), _hd=hd))
    ref = rows[-1]
    keys = ["A_exo_heave", "A_boat_heave", "A_couple_heave", "B_boat_roll", "F_boat_heave", "F_exo_roll"]
    for row in rows:
        row["rel_diff_to_finest"] = {k: [float(abs(a / b - 1)) if abs(b) > 1e-9 else None for a, b in zip(row[k], ref[k])] for k in keys}
    worst = max(v for row in rows[1:2] for vals in row["rel_diff_to_finest"].values() for v in vals if v is not None)
    check("Two-body BEM panel convergence: default (0.20/0.30 m) vs finer (0.15/0.22 m), omegas 1-3 rad/s", "<= 8 % (reported; the 0.18 m hull-float gap is under-resolved by construction)",
          f"worst relative change {100 * worst:.1f} %", worst < 0.08, detail={k: [f"{100*x:.1f}%" if x is not None else "-" for x in v] for k, v in rows[1]["rel_diff_to_finest"].items()})
    hd = rows[1].pop("_hd"); [row.pop("_hd", None) for row in rows]
    rep["two_body_panel_convergence"] = dict(omegas=om.tolist(), rows=rows)
    model = build_response(r, hd, cfg)
    Xp, Xm = model.rao(2.0, np.pi / 2), model.rao(2.0, 3 * np.pi / 2)
    e_heave = max(abs(Xp[2] - Xm[2]) / abs(Xp[2]), abs(Xp[8] - Xm[8]) / abs(Xp[8]))
    e_odd = max(abs(Xp[1] + Xm[1]) / abs(Xp[1]), abs(Xp[3] + Xm[3]) / abs(Xp[3]), abs(Xp[7] + Xm[7]) / abs(Xp[7]), abs(Xp[9] + Xm[9]) / abs(Xp[9]))
    check("Two-body symmetric configuration: beam seas from +Y vs -Y give even heave / odd sway & roll on both bodies",
          "<= 5e-3 (lid/clipped panels are not mirror-exact at 0.2-0.3 m)", f"heave {e_heave:.1e}, sway/roll {e_odd:.1e}", e_heave < 5e-3 and e_odd < 5e-3)
    damp = {"zeta": {"heave": 0.3, "roll": 0.3, "pitch": 0.3}, "absolute": {"surge": 2000, "sway": 2000, "yaw": 4000}}
    tdc = time_domain_check(model, 2.0, np.pi / 2, 0.3, damp, steps_per_period=(16, 32, 64))
    e = [x["max_rel_amp_error"] for x in tdc["results"]]
    rep["two_body_time_step"] = tdc
    check("Two-body (12 DOF) RK4 time integration vs frequency-domain amplitudes", "decreasing, <= 1e-4 at T/64", f"errors {[f'{x:.1e}' for x in e]}", e[0] > e[1] > e[2] and e[2] < 1e-4)
    rw = model.regular_wave(0.3, 2.5, np.pi / 2, {"zeta": {"heave": 0.05, "roll": 0.05, "pitch": 0.05}})
    rep["two_body_example_wave"] = dict(H=0.3, T=2.5, heading_deg=90, bodies={k: dict(amplitude=v["amplitude"], amplitude_deg=v["amplitude_deg"]) for k, v in rw["bodies"].items()},
                                        lines=rw["lines"], flags=rw["flags"])


RHO_F = 999.0


# ------------------------------------------------------------------ 7. propulsion / tow force balance
def propulsion_checks():
    ill = load_config("illustrative")
    r = evaluate(resolve(ill, {"propulsion": {"thrust_fraction": 1.0, "unit": "EXO_PODS"}}))
    p = r["propulsion"]
    Fb = np.zeros(3)
    for l in r["lines"]:
        Fb += -l["tension_N"] * np.asarray(l["unit"])
    err = abs(Fb[0] - p["resistance"]["boat_N"]) / p["resistance"]["boat_N"]
    rep["propulsion_push_100"] = dict(speed_m_s=p["speed_m_s"], thrust_horizontal_N=p["thrust_horizontal_N"], R_exo_N=p["resistance"]["exo_N"],
                                      R_boat_N=p["resistance"]["boat_N"], line_force_on_boat_x_N=float(Fb[0]),
                                      lines=[(l["id"], l["tension_N"], l["slack"]) for l in r["lines"]],
                                      trim_deg=r["equilibrium"]["trim_deg"], net_external=r["coupled_equilibrium"]["external_net_force"])
    check("Propulsion (EXO pods 100 %, default lines): lines carry the boat's resistance", "<= 1e-3 relative",
          f"line Fx on boat {Fb[0]:.1f} N vs R_boat {p['resistance']['boat_N']:.1f} N (rel {err:.1e}); U {p['speed_m_s']:.2f} m/s, "
          f"trim {r['equilibrium']['trim_deg']:.2f} deg, aft lines slack {[l['id'] for l in r['lines'] if l['slack']]}",
          r["coupled_equilibrium"]["converged"] and err < 1e-3)
    lines = next(x for x in ill["host_boat"]["line_presets"] if x["id"] == "figure_all_forward")["lines"]
    r2 = evaluate(resolve(ill, {"host_boat": {"lines": lines}, "propulsion": {"thrust_fraction": 1.0, "unit": "EXO_PODS"}}))
    ce2 = r2["coupled_equilibrium"]
    shift2 = ce2.get("boat_shift_from_nominal") or {}
    check("Propulsion: four-lines-all-forward arrangement cannot carry the push without contact (no physical equilibrium, flagged)",
          "physical=False: no equilibrium, or one only with the boat slid into the EXO structure (INTERFERENCE)",
          f"converged={ce2['converged']}, physical={ce2.get('physical')}, boat shift dx {shift2.get('dx_m', 0) * 1000:.0f} mm, "
          f"flags: {[f[:70] for f in r2['flags'] if 'INTERF' in f or 'cannot' in f]}",
          not ce2.get("physical", ce2["converged"]) and any(("INTERFERENCE" in f) or ("cannot carry" in f) for f in r2["flags"]))
    r3 = evaluate(resolve(ill, {"host_boat": {"included": False}, "propulsion": {"thrust_fraction": 0.5, "unit": "EXO_PODS"}}))
    res = r3["equilibrium"]["residuals"]
    e = max(abs(res["Fz_N_incl_external"]), abs(res["Mx_Nm_incl_external"]), abs(res["My_Nm_incl_external"])) / res["weight_N"]
    check("Propulsion (EXO alone 50 %): equilibrium residual including the thrust/drag wrench", "<= 1e-8 Mg", f"{e:.1e}", e < 1e-8)


# ------------------------------------------------------------------ 8. BEM reference-point transform (COM-independent cache)
def reference_point_transform(ill):
    from exo01.hydro import _body, _solve_radiation, _solve_diffraction, compute_hydro
    eq = ill["_eq"]
    surf = ill["_assembly"].surfaces
    om, hd = np.array([1.0, 2.0]), np.radians([45.0])
    worst = 0.0
    for dG in (np.zeros(3), np.array([0.5, -0.2, 0.3])):
        eq2 = dict(eq, G_body=eq["G_body"] + dG, zG=eq["zG"] + float((eq["R"] @ dG)[2]))
        body, _, _ = _body(surf, eq2, om, G, 0.2, True)
        A0, B0 = _solve_radiation(body, om, RHO, G, None)
        F0 = _solve_diffraction(body, om, hd, RHO, G, None)
        h = timed(f"BEM about COM shifted by {dG.tolist()}", lambda: compute_hydro(surf, eq2, om, hd, RHO, G, None, 0.2))
        worst = max(worst, np.abs(h.A - A0).max() / np.abs(A0).max(), np.abs(h.B - B0).max() / np.abs(B0).max(), np.abs(h.F - F0).max() / np.abs(F0).max())
    rep["reference_point_transform_max_rel_err"] = worst
    check("BEM computed about the CAD origin and moved to the COM (exact transform) vs direct solves about two COMs", "<= 1e-9",
          f"{worst:.1e}", worst < 1e-9)


def main():
    t0 = time.time()
    run_pytest()
    ill = reference_checks()
    analytic_buoyancy()
    equilibrium_checks()
    cfg = resolve(load_config("illustrative"), {"host_boat": {"included": False}})
    ill = evaluate(cfg)
    bem_panel_convergence(ill)
    hd_fine = frequency_resolution(ill, cfg)
    heading_interpolation(ill, cfg, hd_fine)
    model = build_response(ill, hd_fine, cfg)
    time_step(model)
    two_body_checks()
    propulsion_checks()
    reference_point_transform(ill)
    rep["all_checks_passed"] = all(c["passed"] for c in rep["checks"])
    rep["seconds"] = time.time() - t0
    (OUT / "verification_report.json").write_text(json.dumps(rep, indent=1, default=str))
    print("ALL PASSED" if rep["all_checks_passed"] else "SOME FAILED", f"({rep['seconds']:.0f}s)")


if __name__ == "__main__":
    main()
