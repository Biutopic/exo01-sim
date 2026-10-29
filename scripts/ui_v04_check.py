"""Headless checks of the v0.4 interface features (Playwright + Chromium, software WebGL).

    python scripts/ui_v04_check.py [http://127.0.0.1:8050] [--waves] [--backend]

Steps: battery move -> exact re-solve changes the attitude; static-Δ exaggeration (display only); line end-point editing
(table + 3D handle) -> coupled re-solve changes the tensions; motor buttons; live wave motion (needs a cached BEM: --waves);
optimise panel (--backend). Backend-dependent checks report "backend pending" instead of failing when the endpoints or
fields are not there. Screenshots and a JSON summary go to results/ui/.
"""
import json, sys, time, math
from pathlib import Path
from playwright.sync_api import sync_playwright

url = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8050")
WAVES = "--waves" in sys.argv
BACKEND = "--backend" in sys.argv
out = Path(__file__).resolve().parents[1] / "results" / "ui"
out.mkdir(parents=True, exist_ok=True)
logs, errors, res = [], [], {}


def ev(pg, js):
    return pg.evaluate(js)


def wait_solved(pg, prev_seq, timeout=120000):
    """wait until a NEW still-water result (evalSeq advanced and S.still replaced) is rendered"""
    pg.wait_for_function(f"window.__exo.S.still && window.__exo.S.still.__seq !== undefined ? false : (window.__exo.S.still && window.__exo.S.still !== window.__exo.__prevStill)", timeout=timeout)


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1700, "height": 1000})
    pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url)
    pg.wait_for_function("document.querySelector('#tab-still').innerText.includes('still-water equilibrium')", timeout=120000)
    pg.select_option("#scenario", "with_hydronaute"); pg.click("#loadScenario")
    pg.evaluate("document.querySelectorAll('details.sec').forEach((d) => { d.open = true; })")   # inputs live in collapsible sections
    pg.wait_for_function("document.querySelector('#tab-still').innerText.includes('Mooring lines') && window.__exo.S.refPose", timeout=120000)
    time.sleep(2)
    pg.screenshot(path=str(out / "20_v04_loaded.png"))

    # ---------------------------------------------------------------- 1. battery move -> exact solve changes the attitude
    t0 = ev(pg, "window.__exo.S.still.equilibrium.trim_deg")
    q0 = ev(pg, "window.__exo.bodies3d.EXO.inner.quaternion.toArray()")
    ev(pg, "window.__exo.__prevStill = window.__exo.S.still")
    prev = ev(pg, """() => { window.__exo.selectComponent('BATTERY_1'); const h = window.__exo.findHandle('BATTERY_1'); h.obj.position.x += 0.8; window.__exo.firstOrderPreview();
        const E = window.__exo.bodies3d.EXO; return { preview: document.querySelector('#poseInfo').innerText, outerRotY: E.outer.rotation.y }; }""")
    ev(pg, "window.__exo.commitHandle('BATTERY_1')")
    pg.wait_for_function("window.__exo.S.still !== window.__exo.__prevStill", timeout=120000)
    time.sleep(0.5)
    t1 = ev(pg, "window.__exo.S.still.equilibrium.trim_deg")
    q1 = ev(pg, "window.__exo.bodies3d.EXO.inner.quaternion.toArray()")
    res["battery_move"] = dict(trim_before_deg=t0, trim_after_deg=t1, delta_deg=t1 - t0, preview_text=prev["preview"], preview_outer_rot_y_rad=prev["outerRotY"],
                               attitude_quaternion_changed=max(abs(a - b_) for a, b_ in zip(q0, q1)) > 1e-4,
                               ok=abs(t1 - t0) > 0.5 and max(abs(a - b_) for a, b_ in zip(q0, q1)) > 1e-4)
    pg.screenshot(path=str(out / "21_v04_battery_moved.png"))
    # static-Δ exaggeration: display attitude differs from the true one, numbers unchanged
    ev(pg, "document.querySelector('#exag').value = 5; document.querySelector('#exag').dispatchEvent(new Event('input'))")
    time.sleep(0.3)
    q5 = ev(pg, "window.__exo.bodies3d.EXO.inner.quaternion.toArray()")
    info5 = ev(pg, "document.querySelector('#poseInfo').innerText")
    t5 = ev(pg, "window.__exo.S.still.equilibrium.trim_deg")
    # displayed pitch angle vs the true one (about the reference pose)
    ang = lambda q: 2 * math.degrees(math.asin(max(-1, min(1, q[1]))))
    res["static_exaggeration"] = dict(displayed_attitude_changed=max(abs(a - b_) for a, b_ in zip(q1, q5)) > 1e-4, label_present="static Δ exaggerated ×5" in info5,
                                      true_trim_unchanged=abs(t5 - t1) < 1e-12, displayed_pitch_deg_x1=ang(q1), displayed_pitch_deg_x5=ang(q5), true_trim_deg=t1, ref_trim_deg=t0)
    pg.screenshot(path=str(out / "22_v04_static_exaggeration_x5.png"))
    ev(pg, "document.querySelector('#exag').value = 1; document.querySelector('#exag').dispatchEvent(new Event('input'))")

    # ---------------------------------------------------------------- 2. lines: table edit + 3D handle drag
    lines0 = ev(pg, "window.__exo.S.still.lines.map((l) => ({id: l.id, T: l.tension_N, slack: l.slack}))")
    n_handles = ev(pg, "Object.keys(window.__exo.bodies3d.EXO.lineEnds).length + Object.keys(window.__exo.bodies3d.BOAT.lineEnds).length")
    n_rows = ev(pg, "document.querySelectorAll('#lines tr[data-line]').length")
    ev(pg, "window.__exo.__prevStill = window.__exo.S.still")
    # drag the boat end of SPRING_PORT 0.5 m aft (boat frame) via the handle object, then commit (= mouse release)
    ev(pg, """() => { window.__exo.selectComponent('LINE:SPRING_PORT:boat'); const h = window.__exo.findHandle('LINE:SPRING_PORT:boat'); h.obj.position.x -= 0.5; window.__exo.commitHandle('LINE:SPRING_PORT:boat'); }""")
    pg.wait_for_function("window.__exo.S.still !== window.__exo.__prevStill", timeout=120000)
    time.sleep(0.5)
    lines1 = ev(pg, "window.__exo.S.still.lines.map((l) => ({id: l.id, T: l.tension_N, slack: l.slack}))")
    ov1 = ev(pg, "window.__exo.S.overrides.host_boat.lines.map((l) => [l.id, l.boat_point_m])")
    # table edit: move LINE_AFT_STBD EXO end z to 0.3 through the input
    ev(pg, "window.__exo.__prevStill = window.__exo.S.still")
    pg.fill("#lines input[data-k='exo_point_m'][data-j='2'][data-i='1']", "0.3")
    pg.dispatch_event("#lines input[data-k='exo_point_m'][data-j='2'][data-i='1']", "change")
    pg.wait_for_function("window.__exo.S.still !== window.__exo.__prevStill", timeout=120000)
    time.sleep(0.5)
    lines2 = ev(pg, "window.__exo.S.still.lines.map((l) => ({id: l.id, T: l.tension_N, slack: l.slack}))")
    colours = ev(pg, "window.__exo.bodies3d.EXO.lineAnchors.map((a) => ({id: a.id, col: a.cyl.material.color.getHexString(), r: a.r}))")
    res["lines"] = dict(n_handles=n_handles, n_rows=n_rows, tensions_initial=lines0, after_handle_drag=lines1, override_after_drag=ov1, after_table_edit=lines2, colours=colours,
                        presets=ev(pg, "Array.from(document.querySelectorAll('#linePreset option')).map((o) => o.value)"),
                        ok=n_handles == 2 * n_rows and n_rows >= 4 and any(abs(a['T'] - b_['T']) > 1 for a, b_ in zip(lines0, lines1)))
    pg.screenshot(path=str(out / "23_v04_lines_edited.png"))
    # add + remove a line
    ev(pg, "window.__exo.__prevStill = window.__exo.S.still"); pg.click("#addLine")
    pg.wait_for_function("window.__exo.S.still !== window.__exo.__prevStill", timeout=120000)
    n_after_add = ev(pg, "window.__exo.linesList().length")
    ev(pg, "window.__exo.__prevStill = window.__exo.S.still"); pg.click("#lines button[data-k='rm'][data-i='4']")
    pg.wait_for_function("window.__exo.S.still !== window.__exo.__prevStill", timeout=120000)
    res["lines"]["add_remove"] = dict(after_add=n_after_add, after_remove=ev(pg, "window.__exo.linesList().length"))

    # ---------------------------------------------------------------- 3. motor
    ev(pg, "window.__exo.__prevStill = window.__exo.S.still"); pg.click("#thr50")
    pg.wait_for_function("window.__exo.S.still !== window.__exo.__prevStill", timeout=120000)
    time.sleep(0.5)
    prop = ev(pg, "window.__exo.S.still.propulsion || null")
    still_txt = ev(pg, "document.querySelector('#tab-still').innerText")
    res["propulsion"] = dict(override=ev(pg, "window.__exo.S.overrides.propulsion"), result=prop if prop is None else {k: prop[k] for k in prop if k in ('unit', 'thrust_fraction', 'thrust_total_N', 'speed_m_s', 'speed_kn', 'resistance', 'line_load_N', 'converged')},
                             panel_shows="Propulsion (quasi-static)" in still_txt, arrows=ev(pg, "window.__exo.bodies3d && document.querySelector('#poseInfo').innerText.includes('thrust')"),
                             status="computed" if prop else "backend pending (no propulsion field in /api/evaluate)")
    if prop:
        res["propulsion"]["lines_under_thrust"] = ev(pg, "window.__exo.S.still.lines.map((l) => ({id: l.id, T: l.tension_N, slack: l.slack}))")
        res["propulsion"]["trim_deg_under_thrust"] = ev(pg, "window.__exo.S.still.equilibrium.trim_deg")
    pg.screenshot(path=str(out / "24_v04_motor_50.png"))
    ev(pg, "window.__exo.__prevStill = window.__exo.S.still"); pg.click("#thr0")
    pg.wait_for_function("window.__exo.S.still !== window.__exo.__prevStill", timeout=120000)

    # ---------------------------------------------------------------- 4. live wave motion (needs a BEM for this pose or a nearby one)
    if WAVES:
      try:
          # back to the loaded scenario state: reload it so the pose matches the precomputed BEM
          pg.click("#loadScenario")
          pg.wait_for_function("document.querySelector('#tab-still').innerText.includes('Mooring lines')", timeout=120000)
          time.sleep(1.5)
          pg.fill("#heading", "180"); pg.dispatch_event("#heading", "change")
          pg.click("#hydro")
          pg.wait_for_function("document.querySelector('#status').innerText.startsWith('BEM done') || document.querySelector('#status').innerText.startsWith('BEM failed')", timeout=3600000)
          bem_status = ev(pg, "document.querySelector('#status').innerText")
          pg.click("#wave")
          pg.wait_for_function("document.querySelector('#waveResults').innerText.includes('Regular wave') || document.querySelector('#status').innerText.includes('wave')", timeout=300000)
          time.sleep(3.0)
          samples = ev(pg, """() => new Promise((res) => { const B = window.__exo.bodies3d.BOAT, E = window.__exo.bodies3d.EXO; const out = []; const t0 = performance.now();
              const tick = () => { out.push([B.outer.rotation.y, B.outer.rotation.x, B.outer.position.z, E.outer.rotation.y, E.outer.rotation.x]); if (performance.now() - t0 < 4000) requestAnimationFrame(tick); else res(out); }; tick(); })""")
          import statistics
          col = lambda i: [s[i] for s in samples]
          amp = lambda v: (max(v) - min(v)) / 2
          rw = ev(pg, "window.__exo.S.waveRes && window.__exo.S.waveRes.regular_wave ? { period: window.__exo.S.waveRes.regular_wave.period_s, heading: window.__exo.S.waveRes.regular_wave.heading_deg, boat: window.__exo.S.waveRes.regular_wave.bodies.BOAT && window.__exo.S.waveRes.regular_wave.bodies.BOAT.amplitude_deg, exo: window.__exo.S.waveRes.regular_wave.bodies.EXO.amplitude_deg, status: window.__exo.S.waveRes.status } : null")
          res["live_wave"] = dict(bem_status=bem_status, wave=rw, playing=ev(pg, "window.__exo.S.anim.playing"), n_frames=len(samples),
                                  boat_pitch_anim_amp_deg=math.degrees(amp(col(0))), boat_roll_anim_amp_deg=math.degrees(amp(col(1))), boat_heave_anim_amp_m=amp(col(2)),
                                  exo_pitch_anim_amp_deg=math.degrees(amp(col(3))), exo_roll_anim_amp_deg=math.degrees(amp(col(4))),
                                  encounter=ev(pg, "window.__exo.S.waveRes && window.__exo.S.waveRes.encounter || null"), pose_reuse=ev(pg, "window.__exo.S.waveRes && window.__exo.S.waveRes.hydro_meta && window.__exo.S.waveRes.hydro_meta.pose_reuse || null"))
          res["live_wave"]["boat_pitches_in_head_seas"] = res["live_wave"]["boat_pitch_anim_amp_deg"] > 0.01
          pg.screenshot(path=str(out / "25_v04_live_wave_head_seas.png"))
          # live update: move the battery while the animation runs -> the response is refetched (pose reuse) or the prompt shows
          clock0 = ev(pg, "window.__exo.S.anim.t")
          ev(pg, "window.__exo.__prevStill = window.__exo.S.still")
          ev(pg, "() => { window.__exo.selectComponent('BATTERY_2'); const h = window.__exo.findHandle('BATTERY_2'); h.obj.position.x += 0.3; window.__exo.commitHandle('BATTERY_2'); }")
          pg.wait_for_function("window.__exo.S.still !== window.__exo.__prevStill", timeout=120000)
          time.sleep(4)
          res["live_wave"]["after_battery_move"] = dict(waveRes_present=ev(pg, "!!window.__exo.S.waveRes"), playing=ev(pg, "window.__exo.S.anim.playing"), clock_kept=ev(pg, "window.__exo.S.anim.t") > clock0,
                                                        note=ev(pg, "document.querySelector('#animNote').innerText"), status=ev(pg, "document.querySelector('#status').innerText"),
                                                        pose_reuse=ev(pg, "window.__exo.S.waveRes && window.__exo.S.waveRes.hydro_meta && window.__exo.S.waveRes.hydro_meta.pose_reuse || null"))
          pg.screenshot(path=str(out / "26_v04_live_wave_after_move.png"))
      except Exception as e:  # noqa: BLE001
        res.setdefault("live_wave", {})["error"] = f"{type(e).__name__}: {str(e)[:400]}"
        try: pg.screenshot(path=str(out / "26_v04_live_wave_error.png"))
        except Exception: pass

    # ---------------------------------------------------------------- 5. optimise panel
    if BACKEND:
      try:
        for target in ("battery", "lines"):
            pg.click("#optBattery" if target == "battery" else "#optLines")
            pg.wait_for_function("document.querySelector('#optStatus').innerText.includes('done') || document.querySelector('#optStatus').innerText.includes('pending') || document.querySelector('#optStatus').innerText.includes('failed') || document.querySelector('#optStatus').innerText.includes('Error')", timeout=1800000)
            res[f"optimise_{target}"] = dict(status=ev(pg, "document.querySelector('#optStatus').innerText"), rows=ev(pg, "document.querySelectorAll('#optOut table tr').length"),
                                             text=ev(pg, "document.querySelector('#optOut').innerText")[:800])
            pg.screenshot(path=str(out / f"27_v04_optimise_{target}.png"))
      except Exception as e:  # noqa: BLE001
        res["optimise_error"] = f"{type(e).__name__}: {str(e)[:400]}"
    else:
        res["optimise"] = "skipped (run with --backend)"
    b.close()

res["page_errors"] = errors
res["console_errors"] = [l for l in logs if l.startswith("error")][:20]
(out / "ui_v04_check.json").write_text(json.dumps(res, indent=1, default=str))
print(json.dumps(res, indent=1, default=str))
