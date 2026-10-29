"""Clean renders of the simulation for the web (Playwright + Chromium, software WebGL): the three.js scene without the
interface panels, at 1920x1080, for a few documented states.

    python scripts/render_website.py [http://127.0.0.1:8050] [out_dir]

States: (1) EXO + Hydronaute moored, still water, isometric; (2) same, top view; (3) beam sea H 0.3 m T 2.5 s, frame at
maximum roll; (4) head sea, frame at maximum boat pitch; (5) batteries forward (battery_float_frame overrides) with the
boat, iso; (6) EXO alone, end view. A JSON next to the images records the exact state of every frame (scenario, wave,
pose numbers), so each picture can be captioned from data rather than memory.
"""
import json
import math
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

url = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8050")
out = Path(next((a for a in sys.argv[1:] if not a.startswith("http")), Path(__file__).resolve().parents[1] / "docs" / "website" / "img"))
out.mkdir(parents=True, exist_ok=True)
meta = {}

HIDE_CSS = """
#left, #right, header, #gprog, #overlay, #jobs, #anim, #busy { display: none !important; }
main { display: block !important; height: 100vh !important; }
#centre { position: fixed !important; inset: 0 !important; width: 100vw !important; height: 100vh !important; }
#viewer { position: absolute !important; inset: 0 !important; }
"""


def ev(pg, js):
    return pg.evaluate(js)


def wait_new_still(pg, timeout=180000):
    ev(pg, "window.__exo.__prev = window.__exo.S.still")
    return lambda: pg.wait_for_function("window.__exo.S.still !== window.__exo.__prev", timeout=timeout)


def setv(pg, values):
    """Set hidden form inputs by script (the panels are display:none for the renders)."""
    for sel, v in values.items():
        ev(pg, f"() => {{ const e = document.querySelector('{sel}'); e.value = '{v}'; e.dispatchEvent(new Event('change')); }}")


def set_camera(pg, pos, target=(3.5, 0.6, 0)):
    ev(pg, f"""() => {{ const X = window.__exo; X.camera.position.set({pos[0]}, {pos[1]}, {pos[2]}); X.orbit.target.set({target[0]}, {target[1]}, {target[2]});
        X.camera.lookAt({target[0]}, {target[1]}, {target[2]}); X.orbit.update(); X.renderer.render(X.scene, X.camera); }}""")


def shot(pg, name, note):
    time.sleep(0.4)
    pg.screenshot(path=str(out / f"{name}.png"))
    s = ev(pg, """() => { const S = window.__exo.S; const e = S.still && S.still.equilibrium; const b = S.still && S.still.bodies && S.still.bodies.boat;
        return { trim_deg: e && e.trim_deg, heel_deg: e && e.heel_deg, draft_m: e && e.freeboard && e.freeboard.draft_max_m,
                 deck_freeboard_m: e && e.freeboard && e.freeboard.lower_deck_freeboard_min_m,
                 boat: b && b.equilibrium && { trim_deg: b.equilibrium.trim_deg, heel_deg: b.equilibrium.heel_deg },
                 lines: (S.still.lines || []).map((l) => [l.id, Math.round(l.tension_N), l.slack]),
                 wave: S.waveRes && S.waveRes.regular_wave && { H_m: S.waveRes.regular_wave.height_m, T_s: S.waveRes.regular_wave.period_s, heading_deg: S.waveRes.regular_wave.heading_deg,
                        exo_amp_deg: S.waveRes.regular_wave.bodies.EXO.amplitude_deg, boat_amp_deg: S.waveRes.regular_wave.bodies.BOAT && S.waveRes.regular_wave.bodies.BOAT.amplitude_deg },
                 label: S.config && S.config.result_label }; }""")
    meta[name] = dict(note=note, **s)
    print(name, json.dumps({k: v for k, v in s.items() if k in ("trim_deg", "deck_freeboard_m", "wave")}, default=str)[:300])


def freeze_at_extreme(pg, body, dof_index, seconds=4.0):
    """Let the animation run, record the pose, then stop it at the time of the largest |rotation| of the given body/axis."""
    ev(pg, "window.__exo.startAnim && window.__exo.startAnim()")
    samples = ev(pg, f"""() => new Promise((res) => {{ const X = window.__exo; const B = X.bodies3d.{body}; const o = []; const t0 = performance.now();
        const tick = () => {{ o.push([X.S.anim.t, B.outer.rotation.x, B.outer.rotation.y, B.outer.rotation.z]); if (performance.now() - t0 < {seconds * 1000}) requestAnimationFrame(tick); else res(o); }}; tick(); }})""")
    best = max(samples, key=lambda s: abs(s[1 + dof_index]))
    ev(pg, f"() => {{ const X = window.__exo; X.stopAnim && X.stopAnim(); X.S.anim.t = {best[0]}; X.S.anim.playing = true; }}")
    # one more frame at that time, then freeze
    time.sleep(0.2)
    ev(pg, "() => { const X = window.__exo; X.S.anim.playing = false; }")
    return dict(t=best[0], rot_deg=[round(math.degrees(v), 2) for v in best[1:]])


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1920, "height": 1080}, device_scale_factor=1)
    pg.goto(url)
    pg.wait_for_function("window.__exo && window.__exo.S.still && window.__exo.S.still.lines", timeout=240000)
    pg.wait_for_function("document.querySelector('#gprog').className === 'idle'", timeout=120000)
    pg.wait_for_function("window.__exo.S.waveRes && window.__exo.S.anim.playing", timeout=120000)
    pg.add_style_tag(content=HIDE_CSS)
    ev(pg, "() => { document.querySelector('#showMarkers').checked = false; document.querySelector('#showMarkers').dispatchEvent(new Event('change')); window.__exo.resize(); }")
    # background close to the (translucent) water colour so the finite water plane has no visible edge on the renders
    ev(pg, "() => { window.__exo.scene.background.set(0x0d2b4e); }")
    time.sleep(0.5)

    # 1-2: still water, moored
    ev(pg, "() => { window.__exo.stopAnim && window.__exo.stopAnim(); window.__exo.S.anim.playing = false; window.__exo.applyPose(window.__exo.S.still); }")
    set_camera(pg, (10.5, 5.2, 8.8), (4.2, 0.9, 0))
    shot(pg, "01_moored_still_iso", "EXO-01 + Hydronaute moored (simulator default lines), still water, isometric")
    set_camera(pg, (4.2, 12.5, 0.01), (4.2, 0, 0))
    shot(pg, "02_moored_still_top", "same state, top view: the boat berthed between the float rows, four lines")
    set_camera(pg, (4.0, 1.3, 11.5), (4.0, 0.7, 0))
    shot(pg, "03_moored_still_side", "same state, side view: 3.8 deg stern trim of the EXO at the figure's battery position")

    # 3: beam sea, frame at max EXO roll
    setv(pg, {"#heading": "90", "#T": "2.5", "#H": "0.3"}); ev(pg, "document.querySelector('#wave').click()")
    pg.wait_for_function("window.__exo.S.waveRes && window.__exo.S.waveRes.regular_wave.heading_deg === 90 && Math.abs(window.__exo.S.waveRes.regular_wave.period_s - 2.5) < 1e-6 && window.__exo.S.anim.playing", timeout=300000)
    fr = freeze_at_extreme(pg, "EXO", 0)
    set_camera(pg, (11, 4.5, -8), (4.0, 0.7, 0))
    shot(pg, "04_beam_sea_max_roll", f"beam sea H 0.3 m T 2.5 s, frame at maximum EXO roll (t = {fr['t']:.2f} s, rotation {fr['rot_deg']} deg)")

    # 4: head sea, frame at max boat pitch
    ev(pg, "() => { window.__exo.startAnim && window.__exo.startAnim(); }")
    setv(pg, {"#heading": "180"}); ev(pg, "document.querySelector('#wave').click()")
    pg.wait_for_function("window.__exo.S.waveRes && window.__exo.S.waveRes.regular_wave.heading_deg === 180 && window.__exo.S.anim.playing", timeout=300000)
    fr = freeze_at_extreme(pg, "BOAT", 1)
    set_camera(pg, (-3.5, 2.4, 8.5), (4.8, 0.9, 0))
    shot(pg, "05_head_sea_max_boat_pitch", f"head sea H 0.3 m T 2.5 s, frame at maximum boat pitch (t = {fr['t']:.2f} s, rotation {fr['rot_deg']} deg)")

    # 5: batteries forward on the float frames (x 3.60), moored, still water
    ev(pg, "() => { window.__exo.stopAnim && window.__exo.stopAnim(); window.__exo.S.anim.playing = false; }")
    done = wait_new_still(pg)
    ev(pg, """() => { const S = window.__exo.S; S.overrides.components = S.overrides.components || {};
        S.overrides.components.BATTERY_1 = { ...(S.overrides.components.BATTERY_1 || {}), com_m: [3.6, -2.05, 0.5] };
        S.overrides.components.BATTERY_2 = { ...(S.overrides.components.BATTERY_2 || {}), com_m: [3.6, 2.05, 0.5] }; window.__exo.renderComponents(); window.__exo.placeHandles(); window.__exo.evaluate(); }""")
    done(); time.sleep(1.0)
    ev(pg, "() => { window.__exo.S.anim.playing = false; window.__exo.applyPose(window.__exo.S.still); }")
    set_camera(pg, (10.5, 5.2, 8.8), (4.2, 0.9, 0))
    shot(pg, "06_batteries_forward_iso", "batteries moved to the float-top side frames (x 3.60 m): the EXO floats level, still water")
    set_camera(pg, (4.0, 1.3, 11.5), (4.0, 0.7, 0))
    shot(pg, "07_batteries_forward_side", "same state, side view (compare with 03)")

    # 6: EXO alone, end view, batteries at the figure position
    done = wait_new_still(pg)
    ev(pg, """() => { const S = window.__exo.S; delete S.overrides.components.BATTERY_1; delete S.overrides.components.BATTERY_2;
        window.__exo.renderComponents(); window.__exo.placeHandles();
        document.querySelector('#boatIncluded').checked = false; document.querySelector('#boatIncluded').dispatchEvent(new Event('change')); window.__exo.evaluate(); }""")
    done(); time.sleep(1.0)
    ev(pg, "() => { window.__exo.S.anim.playing = false; window.__exo.applyPose(window.__exo.S.still); }")
    set_camera(pg, (3.5 + 10, 2.2, 0.01), (3.5, 0.7, 0))
    shot(pg, "08_exo_alone_end", "EXO-01 alone, end view: the two Flofiz float rows and the open berth between them")
    set_camera(pg, (9.5, 4.8, 8), (3.3, 0.9, 0))
    shot(pg, "09_exo_alone_iso", "EXO-01 alone, isometric")

    (out / "renders.json").write_text(json.dumps(meta, indent=1, default=str))
    print("written", sorted(p.name for p in out.iterdir()))
    b.close()
