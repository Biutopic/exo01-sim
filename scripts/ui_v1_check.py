"""Headless end-to-end check of the v1 interface (Playwright + Chromium, software WebGL).

    python scripts/ui_v1_check.py [http://127.0.0.1:8050]

Boot and global progress strip -> no-equilibrium display (800 kg on a deck corner) -> live waves in head seas from the
shipped cache (boat pitch amplitude read from the animation) -> motor 50 % -> figure_all_forward lines under push (CONTACT
chip) -> battery optimisation job (progress strip, ranked table). Screenshots and a JSON summary go to results/ui/.
"""
import json
import math
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

url = next((a for a in sys.argv[1:] if a.startswith("http")), "http://127.0.0.1:8050")
out = Path(__file__).resolve().parents[1] / "results" / "ui"
out.mkdir(parents=True, exist_ok=True)
res, errors = {}, []


def ev(pg, js):
    return pg.evaluate(js)


def wait_new_still(pg, timeout=180000):
    ev(pg, "window.__exo.__prev = window.__exo.S.still")
    return lambda: pg.wait_for_function("window.__exo.S.still !== window.__exo.__prev", timeout=timeout)


with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_page(viewport={"width": 1700, "height": 1000})
    pg.on("pageerror", lambda e: errors.append(str(e)))
    t0 = time.time()
    pg.goto(url)
    pg.wait_for_function("window.__exo && window.__exo.S.still && window.__exo.S.still.lines", timeout=240000)
    res["boot_s"] = round(time.time() - t0, 1)
    pg.wait_for_function("document.querySelector('#gprog').className === 'idle'", timeout=120000)
    res["strip_after_boot"] = pg.inner_text("#gprog").strip()
    pg.wait_for_function("window.__exo.S.waveRes && window.__exo.S.anim.playing", timeout=120000)
    res["pipeline_after_boot"] = pg.inner_text("#pipeline").replace("\n", " ")
    pg.screenshot(path=str(out / "30_v1_boot.png"))
    ev(pg, "document.querySelectorAll('details').forEach(d => d.open = true)")

    # ---- no equilibrium: 800 kg person on the rear-deck starboard corner
    done = wait_new_still(pg)
    ev(pg, """() => { const S = window.__exo.S; S.overrides.people = [{id: 'P_TEST', name: 'test', mass_kg: 800, mass_source: 'illustrative', surface: 'lower_deck', posture: 'standing', x_m: 0.4, y_m: -1.8}]; window.__exo.evaluate(); }""")
    done(); time.sleep(1.5)
    res["no_equilibrium"] = dict(status=ev(pg, "window.__exo.S.still.status.equilibrium"), label=pg.inner_text("#label"), pose_info=pg.inner_text("#poseInfo")[:220],
                                 pipeline=pg.inner_text("#pipeline").replace("\n", " "), exo_rot_y_deg=round(math.degrees(ev(pg, "window.__exo.bodies3d.EXO.inner.rotation.y")), 2))
    pg.screenshot(path=str(out / "31_v1_no_equilibrium.png"))
    done = wait_new_still(pg)
    ev(pg, "() => { window.__exo.S.overrides.people = []; window.__exo.evaluate(); }")
    done(); time.sleep(1)

    # ---- head seas from the shipped cache: boat pitch from the animation
    pg.fill("#heading", "180"); pg.dispatch_event("#heading", "change")
    pg.click("#wave")
    pg.wait_for_function("window.__exo.S.waveRes && window.__exo.S.waveRes.regular_wave.heading_deg === 180 && window.__exo.S.anim.playing", timeout=300000)
    time.sleep(1)
    samples = ev(pg, """() => new Promise((res) => { const B = window.__exo.bodies3d.BOAT, E = window.__exo.bodies3d.EXO; const o = []; const t0 = performance.now();
        const tick = () => { o.push([B.outer.rotation.y, E.outer.rotation.y, B.outer.position.z]); if (performance.now() - t0 < 3500) requestAnimationFrame(tick); else res(o); }; tick(); })""")
    amp = lambda i: math.degrees((max(s[i] for s in samples) - min(s[i] for s in samples)) / 2)
    rw = ev(pg, "window.__exo.S.waveRes.regular_wave")
    res["head_seas"] = dict(T=rw["period_s"], boat_pitch_model_deg=rw["bodies"]["BOAT"]["amplitude_deg"]["pitch"], boat_pitch_anim_deg=round(amp(0), 3),
                            exo_pitch_model_deg=rw["bodies"]["EXO"]["amplitude_deg"]["pitch"], exo_pitch_anim_deg=round(amp(1), 3), frames=len(samples),
                            hydro=ev(pg, "window.__exo.S.waveRes.hydro_meta.cache"), pose_reuse=ev(pg, "window.__exo.S.waveRes.hydro_meta.pose_reuse || null"),
                            pipeline=pg.inner_text("#pipeline").replace("\n", " "))
    pg.screenshot(path=str(out / "32_v1_head_seas.png"))

    # ---- motor 50 %
    done = wait_new_still(pg); pg.click("#thr50"); done()
    try:
        pg.wait_for_function("window.__exo.S.waveRes && window.__exo.S.waveRes.speed_m_s > 0", timeout=60000)   # live wave refreshed at speed
    except Exception:  # noqa: BLE001
        pass
    pr = ev(pg, "window.__exo.S.still.propulsion")
    res["motor_50"] = dict(speed_m_s=pr and round(pr["speed_m_s"], 2), thrust_N=pr and round(pr["thrust_total_N"]), lines=[(l["id"], round(l["tension_N"]), l["slack"]) for l in ev(pg, "window.__exo.S.still.lines")],
                           pipeline=pg.inner_text("#pipeline").replace("\n", " "), encounter=ev(pg, "window.__exo.S.waveRes && window.__exo.S.waveRes.encounter || null"))
    pg.screenshot(path=str(out / "33_v1_motor_50.png"))

    # ---- all-forward lines under push: CONTACT
    done = wait_new_still(pg)
    pg.select_option("#linePreset", "figure_all_forward"); pg.click("#applyPreset"); done(); time.sleep(1)
    res["all_forward_push"] = dict(pipeline=pg.inner_text("#pipeline").replace("\n", " "), flags=[f[:120] for f in ev(pg, "window.__exo.S.still.flags")],
                                   coupled=ev(pg, "(({converged, interference, physical, boat_shift_from_nominal}) => ({converged, interference, physical, dx: boat_shift_from_nominal && boat_shift_from_nominal.dx_m}))(window.__exo.S.still.coupled_equilibrium)"))
    pg.screenshot(path=str(out / "34_v1_all_forward_contact.png"))
    done = wait_new_still(pg); pg.select_option("#linePreset", "simulator_default"); pg.click("#applyPreset"); done()
    done = wait_new_still(pg); pg.click("#thr0"); done()

    # ---- battery optimisation job: strip shows progress, table rendered
    pg.click("nav button[data-tab='optimise']"); time.sleep(0.3)
    pg.click("#optBattery")
    seen = []
    t1 = time.time()
    while time.time() - t1 < 900:
        time.sleep(2)
        s_ = pg.inner_text("#gprog").strip()
        if s_ and (not seen or seen[-1] != s_):
            seen.append(s_)
        if "candidates" in pg.inner_text("#optOut") or "error" in pg.inner_text("#optStatus").lower():
            break
    res["optimise"] = dict(seconds=round(time.time() - t1), strip_samples=seen[:3] + seen[-2:], status=pg.inner_text("#optStatus")[:160], table_head=pg.inner_text("#optOut")[:400].replace("\n", " | "))
    pg.screenshot(path=str(out / "35_v1_optimise.png"))
    res["page_errors"] = errors
    (out / "ui_v1_check.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    b.close()
