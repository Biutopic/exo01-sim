"""Build the interactive EXO-01 performance explorer -> docs/website/exo01-explorer.html

    python scripts/build_explorer.py

Inlines the geometry-derived physics card from results/performance/ so the browser evaluates the SAME resistance,
thrust, wind and energy models as exo01/performance.py and exo01/aero.py. Nothing in the page is hand-typed.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
P = json.loads((ROOT / "results" / "performance" / "performance.json").read_text())
W = json.loads((ROOT / "results" / "performance" / "wind_load_cases.json").read_text())
# per-element loads live in the connection-load study, not the arrangement search
A = json.loads((ROOT / "results" / "coupling" / "connection_loads.json").read_text())

card = P["card"]
st = P["windage"]["EXO"]["structure"]
card["exo_frame"] = {k: st.get(k) for k in ("frame_A_front_m2", "frame_A_lateral_m2", "panel_A_plan_m2",
                                            "solidity_frontal", "solidity_lateral", "envelope_height_m",
                                            "envelope_width_m")}
card["boat_windage"] = {"A_front_m2": P["windage"]["BOAT"]["A_front_m2"],
                        "A_lateral_m2": P["windage"]["BOAT"]["A_lateral_m2"],
                        "z_lateral_m": P["windage"]["BOAT"]["z_lateral_m"],
                        "L_m": P["windage"]["BOAT"]["L_m"]}
card["sway_share"] = W["sway_share"]["boat_share"]
card["max_speed_ref"] = {k: v["U_m_s"] for k, v in P["max_speed"].items()}
card["disk_sensitivity"] = [{"D": r["D_m"], "eff": r["implied_efficiency"], "U": r["U_max_m_s"]}
                            for r in P["disk_sensitivity"]]
card["pose"] = P["pose"]

# coupling geometry for the plan view (EXO frame; boat points shifted by the berth)
XB = 2.265
ARRANGEMENTS = {
    "I": {"name": "Recommended (§15): midship springs + crossed stern ropes",
          "preload": 600,
          "els": [["SPRING_PORT", [4.95, 2.25], [4.30 + XB, 1.35], "line"],
                  ["SPRING_STBD", [4.95, -2.25], [4.30 + XB, -1.35], "line"],
                  ["CROSS_P2S", [2.10, 2.25], [0.30 + XB, -1.30], "line"],
                  ["CROSS_S2P", [2.10, -2.25], [0.30 + XB, 1.30], "line"],
                  ["BUMPER_PORT", [2.10, 0.90], [0.0 + XB, 0.90], "fender"],
                  ["BUMPER_STBD", [2.10, -0.90], [0.0 + XB, -0.90], "fender"],
                  ["WHEEL_PORT", [1.20 + XB, 1.52], [1.20 + XB, 1.49], "fender"],
                  ["WHEEL_STBD", [1.20 + XB, -1.52], [1.20 + XB, -1.49], "fender"]]},
    "A": {"name": "The brief's configuration: bow-pulley V + bumpers + dockwheels",
          "preload": 2218,
          "els": [["VEE_PORT", [5.20, 2.25], [8.00 + XB, 0.0], "line"],
                  ["VEE_STBD", [5.20, -2.25], [8.00 + XB, 0.0], "line"],
                  ["BUMPER_PORT", [2.10, 0.90], [0.0 + XB, 0.90], "fender"],
                  ["BUMPER_STBD", [2.10, -0.90], [0.0 + XB, -0.90], "fender"],
                  ["WHEEL_PORT", [1.20 + XB, 1.52], [1.20 + XB, 1.49], "fender"],
                  ["WHEEL_STBD", [1.20 + XB, -1.52], [1.20 + XB, -1.49], "fender"]]},
}
# per-element static envelope and wave peak, from the arrangement search
peaks = {}
for aid, row in A["arrangements"].items():
    if aid not in ("I_fwd_midship_crossed", "A_vee_pulley"):
        continue
    key = "I" if aid.startswith("I") else "A"
    peaks[key] = {eid: {"static": e["max_abs_T_N"], "wave": e["wave_peak_N"], "case": e["governing_case"]}
                  for eid, e in (row.get("elements") or {}).items()}
assert peaks.get("I") and peaks.get("A"), "per-element loads missing from connection_loads.json"
# wind verdicts
verdicts = {}
for aid, r in W["arrangements"].items():
    key = "I" if aid.startswith("I") else "A"
    verdicts[key] = {cid: {"ok": bool(c["converged"] and not c["unrestrained"] and c["bumper_min_N"] >= 50),
                           "dy_mm": c["dy_mm"], "dyaw_deg": c["dyaw_deg"], "maxT": c["max_tension_N"],
                           "bump": c["bumper_min_N"], "sway": c["demand"]["sway_N"], "yaw": c["demand"]["yaw_Nm"]}
                     for cid, c in r["cases"].items()}

DATA = {"card": card, "arrangements": ARRANGEMENTS, "peaks": peaks, "verdicts": verdicts,
        "hull": json.loads((ROOT / "configs" / "illustrative.json").read_text())["host_boat"]["buoyant_surface"]["stations_mm"],
        "envelope": P["spec_sources"]["envelope"], "energy": P["spec_sources"]["energy"],
        "corrected_thrust": W["corrected_thrust"]}

HTML = """<title>EXO-01 Performance Explorer</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@500;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap">
<style>
/* Layout: a control rail above a results grid; instrument-panel palette, condensed labels, tabular figures. */
:root{
  --paper:#f5f7f8; --panel:#ffffff; --sunk:#eef1f3;
  --ink:#11191f; --ink-soft:#5d6d79; --ink-faint:#8b9aa5;
  --rule:#d3dce2; --rule-soft:#e5ebef;
  --accent:#0d6f78; --accent-soft:#d9eced; --accent-2:#23506b;
  --good:#2c6e4a; --warn:#9c5a06; --bad:#9c2f26;
  --f-ui:"IBM Plex Sans","Helvetica Neue",Arial,sans-serif;
  --f-lab:"IBM Plex Sans Condensed","Helvetica Neue",Arial,sans-serif;
  --f-num:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#0d1317; --panel:#151d23; --sunk:#111a1f;
  --ink:#e4ecf1; --ink-soft:#9aabb6; --ink-faint:#6b7c88;
  --rule:#26323a; --rule-soft:#1d272d;
  --accent:#3fb3bd; --accent-soft:#12343a; --accent-2:#6aa6cc;
  --good:#5bb37f; --warn:#d99a3c; --bad:#e0685c; color-scheme:dark;
}}
:root[data-theme="dark"]{
  --paper:#0d1317; --panel:#151d23; --sunk:#111a1f;
  --ink:#e4ecf1; --ink-soft:#9aabb6; --ink-faint:#6b7c88;
  --rule:#26323a; --rule-soft:#1d272d;
  --accent:#3fb3bd; --accent-soft:#12343a; --accent-2:#6aa6cc;
  --good:#5bb37f; --warn:#d99a3c; --bad:#e0685c; color-scheme:dark;
}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font-family:var(--f-ui);line-height:1.5;margin:0}
.wrap{max-width:1180px;margin:0 auto;padding-left:max(16px,env(safe-area-inset-left,0px));
  padding-right:max(16px,env(safe-area-inset-right,0px));padding-block:22px 40px}
h1{font-family:var(--f-lab);font-size:1.5rem;font-weight:700;letter-spacing:.01em;margin:0;text-wrap:balance}
.sub{color:var(--ink-soft);font-size:.9rem;margin:.35rem 0 0;max-width:68ch}
.lab{font-family:var(--f-lab);font-size:.7rem;font-weight:600;letter-spacing:.09em;text-transform:uppercase;color:var(--ink-faint)}
.num{font-family:var(--f-num);font-variant-numeric:tabular-nums}
hr.rule{border:0;border-top:1px solid var(--rule);margin:22px 0}
/* controls */
.ctl{background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:16px;margin-top:18px}
.ctl-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px 20px}
.field{display:flex;flex-direction:column;gap:5px;min-width:0}
.field .top{display:flex;justify-content:space-between;align-items:baseline;gap:8px}
.field .val{font-family:var(--f-num);font-size:.84rem;font-weight:500;color:var(--accent)}
input[type=range]{width:100%;accent-color:var(--accent);margin:0}
.seg{display:flex;flex-wrap:wrap;gap:0;border:1px solid var(--rule);border-radius:6px;overflow:hidden}
.seg button{flex:1 1 auto;min-width:76px;border:0;border-right:1px solid var(--rule);background:var(--panel);
  color:var(--ink-soft);font-family:var(--f-lab);font-size:.76rem;font-weight:600;padding:7px 8px;cursor:pointer}
.seg button:last-child{border-right:0}
.seg button[aria-pressed=true]{background:var(--accent);color:#fff}
.seg button:focus-visible{outline:2px solid var(--accent);outline-offset:-2px}
/* figures */
.figs{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:18px}
.fig{background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:12px 14px;min-width:0}
.fig .v{font-family:var(--f-num);font-size:1.5rem;font-weight:500;line-height:1.15;letter-spacing:-.01em}
.fig .u{font-size:.8rem;color:var(--ink-soft);font-family:var(--f-num)}
.fig .n{font-size:.74rem;color:var(--ink-faint);margin-top:4px}
.fig.alert{border-color:var(--bad)} .fig.alert .v{color:var(--bad)}
.fig.ok .v{color:var(--good)}
/* panes */
.cols{display:grid;grid-template-columns:1fr 1fr;gap:18px;margin-top:18px}
@media (max-width:860px){.cols{grid-template-columns:1fr}}
.pane{background:var(--panel);border:1px solid var(--rule);border-radius:8px;padding:14px;min-width:0}
.pane h2{font-family:var(--f-lab);font-size:.82rem;font-weight:700;letter-spacing:.07em;text-transform:uppercase;
  color:var(--ink-soft);margin:0 0 10px}
canvas{display:block;width:100%;height:auto;max-width:100%}
table{width:100%;border-collapse:collapse;font-size:.83rem}
th,td{text-align:right;padding:5px 6px;border-bottom:1px solid var(--rule-soft)}
th:first-child,td:first-child{text-align:left}
th{font-family:var(--f-lab);font-size:.7rem;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--ink-faint)}
td.n{font-family:var(--f-num);font-variant-numeric:tabular-nums}
tr.tot td{border-top:1px solid var(--rule);border-bottom:0;font-weight:600}
.chip{display:inline-block;font-family:var(--f-lab);font-size:.68rem;font-weight:700;letter-spacing:.06em;
  text-transform:uppercase;padding:2px 7px;border-radius:99px}
.chip.ok{background:var(--accent-soft);color:var(--accent)}
.chip.bad{background:var(--bad);color:#fff}
.note{font-size:.79rem;color:var(--ink-soft);margin:10px 0 0}
.warnbox{border-left:3px solid var(--warn);background:var(--sunk);padding:10px 12px;border-radius:0 6px 6px 0;
  font-size:.83rem;margin-top:14px}
.srcs{font-size:.78rem;color:var(--ink-faint);margin-top:8px}
.srcs li{margin:3px 0}
footer{margin-top:28px;padding-top:14px;border-top:1px solid var(--rule);font-size:.78rem;color:var(--ink-faint)}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
</style>

<div class="wrap">
<h1>EXO-01 Performance Explorer</h1>
<p class="sub">Speed, wind and energy for the solar-electric exoskeleton coupled to <em>L'Hydronaute</em> on the Erdre.
Every curve is evaluated in the browser from the same resistance, thrust and windage model as the Python simulation,
with the geometry taken from the solved floating pose.</p>

<div class="ctl">
  <div class="ctl-grid">
    <div class="field"><div class="top"><span class="lab">Thrust setting</span><span class="val" id="v-thr">100 %</span></div>
      <input type="range" id="thr" min="0" max="100" step="5" value="100"></div>
    <div class="field"><div class="top"><span class="lab">True wind</span><span class="val" id="v-wind">0 kn</span></div>
      <input type="range" id="wind" min="0" max="35" step="1" value="0"></div>
    <div class="field"><div class="top"><span class="lab">Wind from</span><span class="val" id="v-dir">0&deg; ahead</span></div>
      <input type="range" id="dir" min="0" max="180" step="15" value="0"></div>
    <div class="field"><div class="top"><span class="lab">River current</span><span class="val" id="v-cur">0.0 m/s</span></div>
      <input type="range" id="cur" min="-150" max="150" step="10" value="0"></div>
    <div class="field"><div class="top"><span class="lab">Pod disk diameter</span><span class="val" id="v-disk">0.25 m</span></div>
      <input type="range" id="disk" min="15" max="35" step="1" value="25"></div>
    <div class="field"><div class="top"><span class="lab">Panel tilt</span><span class="val" id="v-tilt">0&deg;</span></div>
      <input type="range" id="tilt" min="0" max="35" step="1" value="0"></div>
    <div class="field"><div class="top"><span class="lab">Sunlight</span><span class="val" id="v-sun">100 %</span></div>
      <input type="range" id="sun" min="0" max="100" step="5" value="100"></div>
    <div class="field"><span class="lab">Thrust model</span>
      <div class="seg" id="seg-model" role="group" aria-label="Thrust model">
        <button data-m="constant" aria-pressed="false">Constant</button>
        <button data-m="constant_power" aria-pressed="false">Const. power</button>
        <button data-m="momentum" aria-pressed="true">Actuator disk</button>
      </div></div>
    <div class="field"><span class="lab">Coupling arrangement</span>
      <div class="seg" id="seg-arr" role="group" aria-label="Arrangement">
        <button data-a="I" aria-pressed="true">&sect;15 recommended</button>
        <button data-a="A" aria-pressed="false">The brief's</button>
      </div></div>
  </div>
</div>

<div class="figs" id="figs"></div>

<div class="cols">
  <div class="pane"><h2>Thrust against resistance</h2>
    <canvas id="c-speed" width="860" height="430" aria-label="Thrust and resistance against speed"></canvas>
    <p class="note" id="n-speed"></p></div>
  <div class="pane"><h2>Endurance and range</h2>
    <canvas id="c-range" width="860" height="430" aria-label="Range and endurance against speed"></canvas>
    <p class="note" id="n-range"></p></div>
</div>

<div class="cols">
  <div class="pane"><h2>Plan view &mdash; wind and the coupling</h2>
    <canvas id="c-plan" width="860" height="470" aria-label="Plan view of the assembly with wind and coupling loads"></canvas>
    <p class="note" id="n-plan"></p></div>
  <div class="pane"><h2>Where the resistance goes</h2>
    <div style="overflow-x:auto"><table id="t-res"></table></div>
    <h2 style="margin-top:16px">Wind load</h2>
    <div style="overflow-x:auto"><table id="t-wind"></table></div></div>
</div>

<div class="pane" style="margin-top:18px"><h2>Coupling &mdash; element loads and the wind verdict</h2>
  <div style="overflow-x:auto"><table id="t-coup"></table></div>
  <p class="note" id="n-coup"></p></div>

<div class="warnbox" id="posewarn"></div>

<div class="pane" style="margin-top:18px"><h2>What these numbers rest on</h2>
  <ul class="srcs" id="assump"></ul></div>

<footer>Exploratory model, EXO-01. Hull and float surfaces are proxies, not measured displacement surfaces.
Wind coefficients, structural solidity and the pod disk diameter are assumed. Envelope, panel, battery and pod
figures come from the project's cahier des charges and component list, whose own disagreements are listed above.
Verification is not validation: the equations are solved correctly, the inputs are not all confirmed.</footer>
</div>

<script id="exo-data" type="application/json">__DATA__</script>
<script>
(function(){
"use strict";
var D = JSON.parse(document.getElementById("exo-data").textContent);
var C = D.card, KN = 0.514444, RHO = C.rho_water, RHOA = C.rho_air, G = C.g, NU = C.resistance_cfg.nu_m2_s;

/* ---- resistance: the same ITTC-57 + form-factor + residuary model as propulsion.py ---- */
function cf(Re){ Re = Math.max(Re,1e3); return 0.075/Math.pow(Math.log10(Re)-2,2); }
function exoRes(U){
  var c = C.resistance_cfg.exo, tot=0, fr=0, pr=0;
  for (var k in C.exo_rows){ var r=C.exo_rows[k];
    var L=Math.max(r.xmax-r.xmin,0.1), q=0.5*RHO*U*U;
    var Rf=q*(1+c.form_factor_k)*cf(U*L/NU)*r.S_wet, Rp=q*c.pressure_drag_cd*r.A_front_max;
    fr+=Rf; pr+=Rp; tot+=Rf+Rp; }
  return {total:tot, friction:fr, pressure:pr};
}
function boatRes(U){
  var c=C.resistance_cfg.boat, g=C.boat_geo, L=Math.max(g.L_wl,0.5), q=0.5*RHO*U*U;
  var Fr=U/Math.sqrt(G*L);
  var Rf=q*g.S_wet*(1+c.form_factor_k)*cf(U*L/NU)*c.appendage_factor;
  var Rr=q*g.S_wet*c.residuary_c_at_fr02*Math.pow(Fr/0.2,c.residuary_exponent);
  return {total:Rf+Rr, friction:Rf, residuary:Rr, Fr:Fr};
}
function hydro(U){ U=Math.abs(U); if(U<1e-9) return {total:0,exo:{total:0,friction:0,pressure:0},boat:{total:0,friction:0,residuary:0,Fr:0}};
  var e=exoRes(U), b=boatRes(U); return {total:e.total+b.total, exo:e, boat:b}; }

/* ---- thrust: all three models, pinned to the same bollard figure ---- */
function aDisk(){ var d=state.disk/100; return 2*Math.PI*Math.pow(d/2,2); }
function w0(T0,A){ return Math.sqrt(Math.max(T0,0)/(2*RHO*A)); }
function pWater(T0,A){ return T0*w0(T0,A); }
function thrust(U,T0,model,A){
  if(T0<=0) return 0;
  if(model==="constant") return T0;
  var P=pWater(T0,A);
  if(model==="constant_power") return Math.min(T0,P/Math.max(U,1e-6));
  U=Math.max(U,0);
  if(U<1e-9) return 2*RHO*A*Math.pow(P/(2*RHO*A),2/3);
  var lo=1e-12, hi=Math.max(Math.pow(P/(2*RHO*A),1/3),1e-6);
  var f=function(w){ return 2*RHO*A*w*Math.pow(U+w,2)-P; };
  while(f(hi)<0 && hi<1e4) hi*=2;
  for(var i=0;i<80;i++){ var m=0.5*(lo+hi); if(f(m)<0) lo=m; else hi=m; }
  var w=0.5*(lo+hi); return 2*RHO*A*(U+w)*w;
}

/* ---- windage: panel tilt moves area between the two silhouettes ---- */
function areas(){
  var fr=C.exo_frame, tilt=state.tilt*Math.PI/180, pan=(fr.panel_A_plan_m2||0)*Math.abs(Math.sin(tilt));
  return { EXO:{A_front_m2:(fr.frame_A_front_m2||0)+pan, A_lateral_m2:(fr.frame_A_lateral_m2||0)+pan,
                z_lateral_m:C.areas.EXO.z_lateral_m, L_m:C.areas.EXO.L_m},
           BOAT:C.boat_windage };
}
function apparent(Ug,V,fromDeg){
  var th=fromDeg*Math.PI/180, wx=-V*Math.cos(th), wy=-V*Math.sin(th);
  var ax=wx-Ug, ay=wy;
  return {V:Math.hypot(ax,ay), beta:Math.atan2(-ay,-ax)*180/Math.PI};
}
function windWrench(a,V,betaDeg){
  var co=C.coefficients, q=0.5*RHOA*V*V, b=betaDeg*Math.PI/180;
  var Fx=-q*co.Cx0*Math.cos(b)*a.A_front_m2, Fy=q*co.Cy0*Math.sin(b)*a.A_lateral_m2;
  var Mz=q*co.Cn0*Math.sin(2*b)*a.A_lateral_m2*a.L_m;
  return {Fx:Fx,Fy:Fy,Mz:Mz,Mx:Fy*a.z_lateral_m,q:q};
}
function windTotal(Ug){
  var V=state.wind*KN, ar=areas(), ap=apparent(Ug,V,state.dir);
  var e=windWrench(ar.EXO,ap.V,ap.beta), b=windWrench(ar.BOAT,ap.V,ap.beta);
  return {V_app:ap.V, beta:ap.beta, exo:e, boat:b,
          Fx:e.Fx+b.Fx, Fy:e.Fy+b.Fy, Mz:e.Mz+b.Mz, areas:ar};
}

/* ---- speed balance ---- */
function T0(){ return C.T0_horizontal_N*(state.thr/100); }
function net(Ug){
  var Uw=Ug-state.cur/100;
  var T=thrust(Math.max(Uw,0),T0(),state.model,aDisk());
  var R=hydro(Uw).total*(Uw<0?-1:1);
  return T-R+windTotal(Ug).Fx;
}
function solveSpeed(){
  if(net(0)<=0) return null;
  var hi=12; if(net(hi)>0) return hi;
  var lo=1e-6; for(var i=0;i<90;i++){ var m=0.5*(lo+hi); if(net(m)>0) lo=m; else hi=m; }
  return 0.5*(lo+hi);
}
/* ---- energy ---- */
function wAt(T,A,U){ U=Math.max(U,0); return 0.5*(-U+Math.sqrt(U*U+2*Math.max(T,0)/(RHO*A))); }
function pElecFor(T,Uw){
  var A=aDisk(), eff=pWater(C.T0_horizontal_N,A)/C.P_electrical_W;
  if(!(eff>0)||T<=0) return T<=0?0:NaN;
  /* induced velocity AT SPEED, not the bollard relation: the latter overstates water power by ~25 % at 2.4 m/s */
  return T*(Math.max(Uw,0)+wAt(T,A,Uw))/eff;
}
function solarW(){ return C.solar_full_w*(state.sun/100); }
function endurance(Ug){
  var Uw=Ug-state.cur/100, R=hydro(Uw).total, Fw=windTotal(Ug).Fx;
  var Treq=Math.max(R-Fw,0), P=pElecFor(Treq,Uw)+C.hotel_w-solarW();
  var kwh=C.battery_kwh*C.usable_fraction;
  var h=P>1e-9?kwh*1000/P:Infinity;
  return {Treq:Treq, Tavail:thrust(Math.max(Uw,0),T0(),state.model,aDisk()), P:P,
          Pprop:pElecFor(Treq,Uw), hours:h, km:isFinite(h)?h*Ug*3.6:Infinity};
}
function solarNeutral(){
  var budget=solarW()-C.hotel_w; if(budget<=0) return null;
  var f=function(U){ var Uw=U-state.cur/100; return pElecFor(hydro(Uw).total,Uw)-budget; };
  if(f(1e-3)>0) return 0; if(f(6)<0) return 6;
  var lo=1e-3,hi=6; for(var i=0;i<80;i++){ var m=0.5*(lo+hi); if(f(m)<0) lo=m; else hi=m; }
  return 0.5*(lo+hi);
}

/* ---- state ---- */
var state={thr:100,wind:0,dir:0,cur:0,disk:25,tilt:0,sun:100,model:"momentum",arr:"I"};
function fmt(x,n){ if(x===null||x===undefined||!isFinite(x)) return "\\u2014"; return x.toFixed(n===undefined?0:n); }

/* ---- canvas helpers ---- */
function css(v){ return getComputedStyle(document.documentElement).getPropertyValue(v).trim(); }
function setup(cv){
  var r=cv.getBoundingClientRect(), dpr=Math.min(window.devicePixelRatio||1,2);
  var w=Math.max(r.width||cv.width,280), h=cv.height*(w/cv.width);
  cv.style.height=h+"px"; cv.width=Math.round(w*dpr); cv.height=Math.round(h*dpr);
  var g=cv.getContext("2d"); g.setTransform(dpr,0,0,dpr,0,0); g.clearRect(0,0,w,h);
  return {g:g,w:w,h:h};
}
function axes(g,w,h,m,xr,yr,xl,yl){
  var ink=css("--ink-faint"), rule=css("--rule-soft");
  g.strokeStyle=rule; g.lineWidth=1; g.fillStyle=ink;
  g.font="10px "+ (css("--f-num")||"monospace");
  var X=function(v){ return m.l+(v-xr[0])/(xr[1]-xr[0])*(w-m.l-m.r); };
  var Y=function(v){ return h-m.b-(v-yr[0])/(yr[1]-yr[0])*(h-m.t-m.b); };
  var i,t;
  for(i=0;i<=5;i++){ t=yr[0]+(yr[1]-yr[0])*i/5;
    g.beginPath(); g.moveTo(m.l,Y(t)); g.lineTo(w-m.r,Y(t)); g.stroke();
    g.textAlign="right"; g.textBaseline="middle"; g.fillText(t>=1000?(t/1000).toFixed(1)+"k":t.toFixed(t<10?1:0), m.l-6, Y(t)); }
  for(i=0;i<=5;i++){ t=xr[0]+(xr[1]-xr[0])*i/5;
    g.textAlign="center"; g.textBaseline="top"; g.fillText(t.toFixed(1), X(t), h-m.b+6); }
  g.strokeStyle=css("--rule"); g.beginPath(); g.moveTo(m.l,m.t); g.lineTo(m.l,h-m.b); g.lineTo(w-m.r,h-m.b); g.stroke();
  g.font="600 10px "+(css("--f-lab")||"sans-serif"); g.fillStyle=ink;
  g.textAlign="center"; g.textBaseline="bottom"; g.fillText(xl, m.l+(w-m.l-m.r)/2, h-2);
  g.save(); g.translate(10,m.t+(h-m.t-m.b)/2); g.rotate(-Math.PI/2);
  g.textAlign="center"; g.textBaseline="top"; g.fillText(yl,0,0); g.restore();
  return {X:X,Y:Y};
}
function line(g,pts,col,wid,dash){
  g.save(); g.strokeStyle=col; g.lineWidth=wid||2; if(dash) g.setLineDash(dash);
  g.beginPath(); pts.forEach(function(p,i){ i?g.lineTo(p[0],p[1]):g.moveTo(p[0],p[1]); }); g.stroke(); g.restore();
}
function tag(g,x,y,txt,col){
  g.save(); g.font="600 10px "+(css("--f-lab")||"sans-serif"); g.fillStyle=col;
  g.textAlign="left"; g.textBaseline="middle"; g.fillText(txt,x,y); g.restore();
}

/* ---- chart: thrust vs resistance ---- */
function drawSpeed(){
  var cv=document.getElementById("c-speed"), s=setup(cv), g=s.g, m={l:52,r:14,t:14,b:34};
  var Umax=5, N=70, A=aDisk(), t0=T0();
  var curves={}, ymax=100;
  ["constant","constant_power","momentum"].forEach(function(md){
    curves[md]=[]; for(var i=0;i<=N;i++){ var U=Umax*i/N; var T=thrust(U,t0,md,A); curves[md].push([U,T]); ymax=Math.max(ymax,T); }});
  var res=[], resW=[];
  for(var i=0;i<=N;i++){ var U=Umax*i/N; var R=hydro(U).total; res.push([U,R]);
    resW.push([U,Math.max(R-windTotal(U).Fx,0)]); ymax=Math.max(ymax,Math.min(R,4000)); }
  ymax=Math.min(Math.ceil(ymax/250)*250,4000);
  var ax=axes(g,s.w,s.h,m,[0,Umax],[0,ymax],"speed over ground  (m/s)","force  (N)");
  var P=function(a){ return a.map(function(p){ return [ax.X(p[0]),ax.Y(Math.min(p[1],ymax))]; }); };
  line(g,P(res),css("--ink-soft"),2);
  if(state.wind>0) line(g,P(resW),css("--warn"),2,[5,4]);
  line(g,P(curves.constant),css("--accent-2"),1.5,[2,3]);
  line(g,P(curves.constant_power),css("--accent-2"),1.5,[7,4]);
  line(g,P(curves.momentum),css("--accent"),2.5);
  var U=solveSpeed();
  if(U!==null && U<Umax){ var T=thrust(Math.max(U-state.cur/100,0),t0,state.model,A);
    g.save(); g.fillStyle=css("--accent"); g.beginPath(); g.arc(ax.X(U),ax.Y(Math.min(T,ymax)),4.5,0,7); g.fill();
    g.strokeStyle=css("--accent"); g.setLineDash([2,3]); g.beginPath();
    g.moveTo(ax.X(U),ax.Y(0)); g.lineTo(ax.X(U),ax.Y(Math.min(T,ymax))); g.stroke(); g.restore();
    tag(g,ax.X(U)+7,ax.Y(Math.min(T,ymax))-10,U.toFixed(2)+" m/s",css("--accent")); }
  tag(g,m.l+8,ax.Y(ymax*0.94),"resistance",css("--ink-soft"));
  tag(g,m.l+8,ax.Y(ymax*0.86),"thrust: actuator disk",css("--accent"));
  tag(g,m.l+8,ax.Y(ymax*0.78),"\\u2014 \\u2014 constant power   \\u00b7\\u00b7\\u00b7 constant",css("--accent-2"));
  if(state.wind>0) tag(g,m.l+8,ax.Y(ymax*0.70),"resistance + wind",css("--warn"));
  var nd=document.getElementById("n-speed");
  nd.textContent = U===null
    ? "At this setting the assembly cannot make headway: the wind drag at rest already exceeds the available thrust."
    : "Operating point "+U.toFixed(2)+" m/s ("+(U/KN).toFixed(2)+" kn). The three thrust curves share the same bollard "
      +"figure of "+Math.round(C.T0_horizontal_N)+" N and diverge with speed; the spread between them is the honest "
      +"uncertainty until the pod's measured thrust curve is available.";
}

/* ---- chart: endurance and range ---- */
function drawRange(){
  var cv=document.getElementById("c-range"), s=setup(cv), g=s.g, m={l:52,r:46,t:14,b:34};
  var Umax=4, N=48, km=[], hr=[], kmax=1, hmax=1;
  for(var i=1;i<=N;i++){ var U=Umax*i/N, e=endurance(U);
    if(isFinite(e.km)&&e.km<2000){ km.push([U,e.km]); kmax=Math.max(kmax,e.km); }
    if(isFinite(e.hours)&&e.hours<200){ hr.push([U,e.hours]); hmax=Math.max(hmax,e.hours); } }
  /* the range asymptote near the solar-neutral speed would squash everything else, so cap the axis and say so */
  var snv=solarNeutral(), capped=false;
  if(kmax>260){ kmax=260; capped=true; } else { kmax=Math.ceil(kmax/25)*25; }
  if(hmax>60){ hmax=60; } else { hmax=Math.ceil(hmax/2)*2; }
  var ax=axes(g,s.w,s.h,m,[0,Umax],[0,kmax],"speed held  (m/s)","range  (km)");
  line(g,km.map(function(p){return [ax.X(p[0]),ax.Y(Math.min(p[1],kmax))];}),css("--accent"),2.5);
  var Yh=function(v){ return s.h-m.b-(v/hmax)*(s.h-m.t-m.b); };
  line(g,hr.map(function(p){return [ax.X(p[0]),Yh(Math.min(p[1],hmax))];}),css("--accent-2"),2,[6,4]);
  g.save(); g.font="10px "+(css("--f-num")||"monospace"); g.fillStyle=css("--ink-faint");
  g.textAlign="left"; g.textBaseline="middle";
  for(var j=0;j<=5;j++){ var t=hmax*j/5; g.fillText(t.toFixed(0)+" h", s.w-m.r+6, Yh(t)); }
  g.restore();
  var sn=snv;
  if(sn!==null && sn>0.02 && sn<Umax){
    g.save(); g.strokeStyle=css("--good"); g.setLineDash([3,3]); g.lineWidth=1.5;
    g.beginPath(); g.moveTo(ax.X(sn),m.t); g.lineTo(ax.X(sn),s.h-m.b); g.stroke(); g.restore();
    tag(g,ax.X(sn)+6,m.t+12,"solar-neutral "+sn.toFixed(2)+" m/s",css("--good")); }
  tag(g,m.l+8,ax.Y(kmax*0.94),"range, km (left)",css("--accent"));
  tag(g,m.l+8,ax.Y(kmax*0.86),"\\u2014 \\u2014 endurance, h (right)",css("--accent-2"));
  var sw=solarW();
  document.getElementById("n-range").textContent =
    "From "+C.battery_kwh.toFixed(1)+" kWh at "+Math.round(C.usable_fraction*100)+" % usable, with "
    +Math.round(sw)+" W of solar and a "+Math.round(C.hotel_w)+" W hotel load. "
    +(sn===null ? "At this light level the hotel load alone outruns the array, so nothing is sustainable without the battery."
      : "Below "+sn.toFixed(2)+" m/s the array covers propulsion and the hotel load, so endurance is limited by "
        +"daylight rather than by the battery"+(capped?" \u2014 the axis is capped at "+kmax+" km, since range runs "
        +"away to infinity as that speed is approached":"")+".");
}

/* ---- plan view ---- */
function drawPlan(){
  var cv=document.getElementById("c-plan"), s=setup(cv), g=s.g;
  var pad=34, xr=[-1.2,11.6], yr=[-3.0,3.0];
  var sc=Math.min((s.w-2*pad)/(xr[1]-xr[0]),(s.h-2*pad)/(yr[1]-yr[0]));
  var ox=pad+((s.w-2*pad)-(xr[1]-xr[0])*sc)/2, oy=s.h/2;
  var X=function(x){ return ox+(x-xr[0])*sc; }, Y=function(y){ return oy-y*sc; };
  var ar=D.arrangements[state.arr];

  /* EXO frame + floats */
  g.save(); g.strokeStyle=css("--rule"); g.lineWidth=1.5;
  g.strokeRect(X(0),Y(2.25),(5.2-0)*sc,4.5*sc);
  g.fillStyle=css("--sunk");
  [1.97,-1.97].forEach(function(y){ g.fillRect(X(0.5),Y(y+0.3),(5.34-0.5)*sc,0.6*sc);
    g.strokeRect(X(0.5),Y(y+0.3),(5.34-0.5)*sc,0.6*sc); });
  g.restore();
  /* hull outline from the real station table */
  g.save(); g.beginPath();
  var H=D.hull, XB=2.265, k;
  for(k=0;k<H.length;k++){ var x=XB+H[k][0]/1000, y=H[k][1]/1000; k?g.lineTo(X(x),Y(y)):g.moveTo(X(x),Y(y)); }
  for(k=H.length-1;k>=0;k--){ g.lineTo(X(XB+H[k][0]/1000),Y(-H[k][1]/1000)); }
  g.closePath(); g.fillStyle=css("--panel"); g.fill(); g.strokeStyle=css("--ink-soft"); g.lineWidth=1.5; g.stroke(); g.restore();
  /* coupling elements, coloured by their governing load */
  var pk=(D.peaks[state.arr])||{};
  ar.els.forEach(function(e){
    var id=e[0], a=e[1], b=e[2], kind=e[3];
    var info=pk[id]||pk[id.replace("VEE_PORT","VEE_ROPE").replace("VEE_STBD","VEE_ROPE")]||null;
    var mag=info?Math.max(Math.abs(info.static||0),info.wave||0):0;
    var col = kind==="fender" ? css("--accent-2") : (mag>900?css("--bad"):mag>400?css("--warn"):css("--accent"));
    g.save(); g.strokeStyle=col; g.lineWidth=kind==="fender"?4:2;
    if(kind==="fender") g.lineCap="round";
    g.beginPath(); g.moveTo(X(a[0]),Y(a[1])); g.lineTo(X(b[0]),Y(b[1])); g.stroke(); g.restore();
  });
  /* wind arrow */
  if(state.wind>0){
    var th=state.dir*Math.PI/180, L=Math.min(2.4,0.6+state.wind*0.06);
    var cx=X(5.6), cy=Y(2.55);
    var dx=-Math.cos(th), dy=-Math.sin(th);
    g.save(); g.strokeStyle=css("--warn"); g.fillStyle=css("--warn"); g.lineWidth=2.5;
    g.beginPath(); g.moveTo(cx-dx*L*sc,cy+dy*L*sc); g.lineTo(cx,cy); g.stroke();
    g.beginPath(); g.moveTo(cx,cy);
    g.lineTo(cx-(dx*0.95+dy*0.28)*0.5*sc, cy+(dy*0.95-dx*0.28)*0.5*sc);
    g.lineTo(cx-(dx*0.95-dy*0.28)*0.5*sc, cy+(dy*0.95+dx*0.28)*0.5*sc);
    g.closePath(); g.fill();
    g.font="600 11px "+(css("--f-lab")||"sans-serif"); g.textAlign="left"; g.textBaseline="middle";
    g.fillText(state.wind+" kn from "+state.dir+"\\u00b0", cx+10, cy); g.restore();
  }
  /* labels */
  g.save(); g.font="600 10px "+(css("--f-lab")||"sans-serif"); g.fillStyle=css("--ink-faint");
  g.textAlign="center"; g.textBaseline="top";
  g.fillText("EXO frame 4.50 m \\u00d7 5.20 m", X(2.6), Y(-2.25)+6);
  g.fillText("L'Hydronaute", X(XB+4), Y(0)-5);
  g.restore();
  document.getElementById("n-plan").textContent =
    ar.name+". Ropes are coloured by their governing load (static envelope or wave peak, whichever is larger); "
    +"bumpers and dockwheels are drawn as contacts. The wind arrow shows the direction the wind blows from.";
}

/* ---- tables ---- */
function tables(){
  var U=solveSpeed(), Uw=(U||0)-state.cur/100, h=hydro(Math.max(Uw,0)), wt=windTotal(U||0);
  var t=document.getElementById("t-res");
  t.innerHTML="<tr><th>component</th><th>force</th><th>share</th></tr>"+
    [["EXO floats \\u2014 friction",h.exo.friction],["EXO floats \\u2014 pressure",h.exo.pressure],
     ["Hull \\u2014 friction",h.boat.friction],["Hull \\u2014 residuary (wave-making)",h.boat.residuary]]
    .map(function(r){ return "<tr><td>"+r[0]+"</td><td class='n'>"+fmt(r[1])+" N</td><td class='n'>"
      +(h.total>0?fmt(100*r[1]/h.total,1):"\\u2014")+" %</td></tr>"; }).join("")+
    "<tr class='tot'><td>total hydrodynamic</td><td class='n'>"+fmt(h.total)+" N</td><td class='n'>100 %</td></tr>"+
    "<tr><td>Froude number</td><td class='n'>"+fmt(h.boat.Fr,3)+"</td><td></td></tr>";
  var w=document.getElementById("t-wind");
  w.innerHTML="<tr><th>body</th><th>drag F<sub>x</sub></th><th>side F<sub>y</sub></th><th>yaw M<sub>z</sub></th></tr>"+
    [["EXO",wt.exo],["Boat",wt.boat]].map(function(r){ return "<tr><td>"+r[0]+"</td><td class='n'>"+fmt(r[1].Fx)
      +" N</td><td class='n'>"+fmt(r[1].Fy)+" N</td><td class='n'>"+fmt(r[1].Mz)+" N\\u00b7m</td></tr>"; }).join("")+
    "<tr class='tot'><td>pair</td><td class='n'>"+fmt(wt.Fx)+" N</td><td class='n'>"+fmt(wt.Fy)
      +" N</td><td class='n'>"+fmt(wt.Mz)+" N\\u00b7m</td></tr>"+
    "<tr><td>apparent wind</td><td class='n'>"+fmt(wt.V_app,2)+" m/s</td><td class='n'>"+fmt(wt.beta,0)
      +"\\u00b0</td><td></td></tr>"+
    "<tr><td>windage area (front / lateral)</td><td class='n'>"+fmt(wt.areas.EXO.A_front_m2+wt.areas.BOAT.A_front_m2,1)
      +" m\\u00b2</td><td class='n'>"+fmt(wt.areas.EXO.A_lateral_m2+wt.areas.BOAT.A_lateral_m2,1)+" m\\u00b2</td><td></td></tr>";

  /* coupling */
  var pk=D.peaks[state.arr]||{}, rows=Object.keys(pk).sort(function(a,b){
    return Math.max(Math.abs(pk[b].static||0),pk[b].wave||0)-Math.max(Math.abs(pk[a].static||0),pk[a].wave||0); });
  var ct=document.getElementById("t-coup");
  var vkey="wind"+(state.wind>=28?30:state.wind>=23?25:state.wind>=18?20:state.wind>=13?15:10)+"_"
          +(state.dir<=67?45:state.dir<=112?90:135);
  var vd=(D.verdicts[state.arr]||{})[vkey];
  ct.innerHTML="<tr><th>element</th><th>static envelope</th><th>wave peak</th><th>governing case</th></tr>"+
    rows.map(function(id){ var e=pk[id];
      return "<tr><td>"+id+"</td><td class='n'>"+fmt(e.static)+" N</td><td class='n'>"+fmt(e.wave)
        +" N</td><td>"+(e.case||"\\u2014")+"</td></tr>"; }).join("");
  var nc=document.getElementById("n-coup");
  if(state.wind===0){ nc.innerHTML="Set a wind speed to see whether this arrangement holds the resulting sway and yaw."; }
  else if(!vd){ nc.innerHTML="No precomputed wind case matches this setting."; }
  else {
    nc.innerHTML="<span class='chip "+(vd.ok?"ok":"bad")+"'>"+(vd.ok?"holds":"runs away")+"</span> "
      +"Nearest computed case: "+vkey.replace("wind","").replace("_"," kn from ")+"\\u00b0, demanding "
      +fmt(vd.sway)+" N of sway and "+fmt(vd.yaw)+" N\\u00b7m of yaw on the coupling. Response: "
      +fmt(vd.dy_mm,1)+" mm of sway, "+fmt(vd.dyaw_deg,2)+"\\u00b0 of yaw, peak rope "+fmt(vd.maxT)+" N."
      +(vd.ok?"":" This is the near-singular sway mode rather than a physical prediction: in this arrangement sway is "
        +"essentially unrestrained, so a demand of a few tens of newtons sends the solver off. The failures are not "
        +"monotonic in wind speed, which is the signature of that.");
  }
}

/* ---- figures ---- */
function figures(){
  var U=solveSpeed(), e=U===null?null:endurance(U), sn=solarNeutral();
  var A=aDisk(), eff=pWater(C.T0_horizontal_N,A)/C.P_electrical_W;
  var cards=[
    {v:U===null?"\\u2014":U.toFixed(2),u:"m/s",n:U===null?"cannot make headway":(U/KN).toFixed(2)+" kn over ground",
     cls:U===null?"alert":""},
    {v:e&&isFinite(e.hours)?e.hours.toFixed(1):"\\u221e",u:"h",n:e&&isFinite(e.km)?e.km.toFixed(0)+" km at this speed":"solar covers the draw"},
    {v:sn===null?"\\u2014":sn.toFixed(2),u:"m/s",n:"solar-neutral speed",cls:sn===null?"":"ok"},
    {v:e?Math.round(e.Pprop+C.hotel_w):"\\u2014",u:"W",n:"electrical draw"},
    {v:(100*eff).toFixed(0),u:"%",n:"implied pod efficiency, upper bound"}
  ];
  document.getElementById("figs").innerHTML=cards.map(function(c){
    return "<div class='fig "+(c.cls||"")+"'><div class='v'>"+c.v+" <span class='u'>"+c.u+"</span></div>"
      +"<div class='n'>"+c.n+"</div></div>"; }).join("");
}

/* ---- assumptions ---- */
function assumptions(){
  var co=C.coefficients, fr=C.exo_frame, en=D.energy;
  var items=[
    "Wind coefficients Cx0 "+co.Cx0+", Cy0 "+co.Cy0+", Cn0 "+co.Cn0+" \\u2014 assumed for a bluff, partly open "
      +"structure. No wind-tunnel, CFD or full-scale basis. The largest single uncertainty in every wind figure here.",
    "Structural solidity "+fr.solidity_frontal+" frontal, "+fr.solidity_lateral+" lateral, applied to the recorded "
      +fr.envelope_width_m+" \\u00d7 "+fr.envelope_height_m+" m envelope. The envelope is real; the two ratios are not measured.",
    "Pod disk diameter is not recorded. At the "+(state.disk/100).toFixed(2)+" m set here, the recorded 62 kgf bollard "
      +"and 5 kW per pod imply only "+(100*pWater(C.T0_horizontal_N,aDisk())/C.P_electrical_W).toFixed(0)
      +" % overall efficiency under ideal theory \\u2014 so either the thrust figure is conservative or the power rating is a peak.",
    "The sway reaction is split between the bodies by submerged lateral area, giving the boat "
      +(100*C.sway_share).toFixed(0)+" % of it. A crude proxy for sway drag share.",
    "Battery "+en.battery.total_kwh+" kWh at "+Math.round(100*en.battery.usable_fraction)+" % usable, array "
      +en.solar.array_kwp+" kWp derated "+Math.round(100*en.solar.derate_to_dc_fraction)+" % to DC. "
      +"The cahier des charges and the component list disagree on the array: "+en.solar.array_kwp+" kWp against "
      +en.solar.array_kwp_alternative+" kWp. Unresolved.",
    "The coupled solve WITH thrust applied converges to a capsized branch (boat heel "
      +fmt(C.pose.thrust_on_heel_deg,1)+"\\u00b0) and reports itself physical. All geometry here is taken at the "
      +"thrust-off pose, heel "+fmt(C.pose.heel_deg,2)+"\\u00b0.",
    "Hull and float surfaces are proxies. Sinkage and trim at speed, wave-added resistance and gusts are not modelled."
  ];
  document.getElementById("assump").innerHTML=items.map(function(s){return "<li>"+s+"</li>";}).join("");
  var pw=document.getElementById("posewarn");
  pw.innerHTML="<strong>Known defect carried into this page.</strong> "+C.pose.warning+" The forward-thrust load case "
    +"the coupling study used (841 N) was computed there; at an upright pose and a realistic thrust curve the same "
    +"case is "+fmt(D.corrected_thrust.R_boat_N)+" N, so the published preloads are conservative rather than wrong.";
}

/* ---- wiring ---- */
function render(){ figures(); drawSpeed(); drawRange(); drawPlan(); tables(); assumptions(); }
function bind(id,key,fmtv){
  var el=document.getElementById(id);
  el.addEventListener("input",function(){ state[key]=+el.value;
    document.getElementById("v-"+id).textContent=fmtv(+el.value); render(); });
  document.getElementById("v-"+id).textContent=fmtv(+el.value);
}
bind("thr","thr",function(v){return v+" %";});
bind("wind","wind",function(v){return v+" kn";});
bind("dir","dir",function(v){return v+"\\u00b0 "+(v<23?"ahead":v<68?"bow":v<113?"beam":v<158?"quarter":"astern");});
bind("cur","cur",function(v){return (v/100).toFixed(1)+" m/s";});
bind("disk","disk",function(v){return (v/100).toFixed(2)+" m";});
bind("tilt","tilt",function(v){return v+"\\u00b0";});
bind("sun","sun",function(v){return v+" %";});
function seg(id,key){
  var box=document.getElementById(id);
  box.addEventListener("click",function(ev){
    var b=ev.target.closest("button"); if(!b) return;
    [].forEach.call(box.querySelectorAll("button"),function(x){ x.setAttribute("aria-pressed", x===b?"true":"false"); });
    state[key]=b.dataset.m||b.dataset.a; render();
  });
}
seg("seg-model","model"); seg("seg-arr","arr");
var rt; window.addEventListener("resize",function(){ clearTimeout(rt); rt=setTimeout(render,120); });
if(window.matchMedia) try{ window.matchMedia("(prefers-color-scheme:dark)").addEventListener("change",render); }catch(e){}
render();
})();
</script>
"""

out = ROOT / "docs" / "website" / "exo01-explorer.html"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(HTML.replace("__DATA__", json.dumps(DATA, separators=(",", ":"))))
print(f"written {out} ({out.stat().st_size/1024:.0f} kB)")
