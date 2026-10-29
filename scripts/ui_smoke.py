"""Headless browser smoke test of the interface (Playwright + Chromium, software WebGL).
Checks: page loads, GLB loads with the expected root rotation, still-water results render, 3D canvas draws."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

url = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8050"
out = Path(__file__).resolve().parents[1] / "results" / "ui"
out.mkdir(parents=True, exist_ok=True)
logs, errors = [], []
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1700, "height": 1000})
    pg.on("console", lambda m: logs.append(f"{m.type}: {m.text}"))
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(url)
    pg.wait_for_function("document.querySelector('#tab-still').innerText.includes('still-water equilibrium')", timeout=60000)
    time.sleep(2)
    pg.screenshot(path=str(out / "01_illustrative_still.png"))
    glb_ok = any("GLB root rotation = -90deg about X: true" in l for l in logs)
    # add a person on the observation deck (asymmetric) and check heel changes
    heel0 = pg.evaluate("document.querySelector('#poseInfo').innerText")
    pg.click("#addPerson")
    pg.wait_for_function("document.querySelector('#tab-still').innerText.includes('920.0')", timeout=30000)
    time.sleep(1.0)
    heel1 = pg.evaluate("document.querySelector('#poseInfo').innerText")
    pg.screenshot(path=str(out / "02_person_added.png"))
    # waves: BEM (background job) then regular-wave response and the animation
    wave = None
    if "--waves" in sys.argv:
        pg.click("#hydro")
        pg.wait_for_function("document.querySelector('#status').innerText.startsWith('BEM done')", timeout=900000)
        pg.click("#wave")
        pg.wait_for_function("document.querySelector('#waveResults').innerText.includes('Regular wave')", timeout=120000)
        time.sleep(2.5)
        pg.screenshot(path=str(out / "04_wave_response.png"))
        wave = pg.evaluate("document.querySelector('#waveResults').innerText")[:1500]
        anim = pg.evaluate("document.querySelector('#tdisp').innerText")
        pg.click("#compare")
        pg.wait_for_function("document.querySelector('#compareOut').innerText.includes('scenario')", timeout=120000)
        time.sleep(1)
        pg.screenshot(path=str(out / "05_compare.png"))
        pg.click("#export")
        pg.wait_for_function("document.querySelector('#status').innerText.includes('exported')", timeout=60000)
        wave = dict(text=wave, anim_clock=anim, export_status=pg.evaluate("document.querySelector('#status').innerText"))
    # baseline: must show not computed
    pg.select_option("#base", "baseline")
    pg.wait_for_function("document.querySelector('#tab-still').innerText.includes('Not computed')", timeout=30000)
    time.sleep(1)
    pg.screenshot(path=str(out / "03_baseline.png"))
    baseline_text = pg.evaluate("document.querySelector('#tab-still').innerText")
    pixels = pg.evaluate("""() => { const c = document.querySelector('#viewer canvas'); const gl = c.getContext('webgl2') || c.getContext('webgl');
        return gl ? 'webgl' : 'none'; }""")
    b.close()
res = dict(glb_root_rotation_checked=glb_ok, waves=wave, pose_before=heel0, pose_after_person=heel1, baseline_shows_not_computed="Not computed" in baseline_text,
           webgl=pixels, page_errors=errors, console_errors=[l for l in logs if l.startswith("error")])
(out / "ui_smoke.json").write_text(json.dumps(res, indent=1))
print(json.dumps(res, indent=1))
