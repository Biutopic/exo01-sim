// EXO-01 exploratory viewer. Rendering only: every number shown comes from the Python backend.
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { TransformControls } from 'three/addons/controls/TransformControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const $ = (id) => document.getElementById(id);
const fmt = (v, d = 3) => (v === null || v === undefined || Number.isNaN(v)) ? '<span class="nc">not computed</span>' : (typeof v === 'number' ? v.toFixed(d) : v);
const DOF = ['surge', 'sway', 'heave', 'roll', 'pitch', 'yaw'];
const MOVABLE = ['BATTERY_1', 'BATTERY_2', 'ELECTRONICS_50'];
const POSTURE_H = { standing: 1.0, seated_on_chair: 0.7, seated_on_deck: 0.4 };
const BODY_OF_SURFACE = (s) => (s && s.startsWith('boat_') ? 'BOAT' : 'EXO');

const S = {
  meta: null, base: 'illustrative', config: null,
  overrides: { components: {}, people: [], environment: {}, host_boat: { people: [] } },
  still: null, waveRes: null, hydroMeta: null, hydroReady: false,
  anim: { playing: false, t: 0, last: 0 }, selected: null, scenarioName: null,
  refPose: null,            // still-water pose of the loaded scenario: reference for the static-Δ exaggeration (display only)
  waveBusy: false, wavePending: false,
};

// ============================================================ HTTP
async function api(path, body) {
  const r = await fetch(path, body ? { method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) } : {});
  const j = await r.json();
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
}
function statePayload() {
  const env = {};
  const rho = parseFloat($('rho').value); if (!Number.isNaN(rho)) env.rho_kg_m3 = rho;
  const depth = $('depth').value.trim(); env.water_depth_m = depth === '' ? null : parseFloat(depth);
  S.overrides.environment = env;
  readBoatInputs();
  const p = { base: S.base, overrides: S.overrides, scenario_name: S.scenarioName || S.base,
              hydro_settings: hydroSettings(), wave: waveInput(), damping: dampingInput() };
  const sp = S.still && S.still.propulsion && S.still.propulsion.speed_m_s;
  if (sp) p.speed_m_s = sp;
  return p;
}
function hydroSettings() {
  return { omega_min: +$('omMin').value, omega_max: +$('omMax').value, omega_step: +$('omStep').value,
           panel_size_m: +$('panel').value, lid: $('lid').checked, refine_bands: $('refine').checked,
           two_body_panel_exo_m: +$('panelExo2').value, two_body_panel_boat_m: +$('panelBoat2').value, two_body_omega_max: +$('omMax2').value };
}
function waveInput() { return { H_m: +$('H').value, T_s: +$('T').value, heading_deg: +$('heading').value }; }
function dampingInput() {
  // legacy single set (= EXO values, accepted by every backend) + per-body sets (v0.4 contract: damping.EXO / damping.BOAT)
  const exo = { zeta: { heave: +$('zHeave').value, roll: +$('zRoll').value, pitch: +$('zPitch').value },
                absolute: { surge: +$('bSurge').value, sway: +$('bSway').value, yaw: +$('bYaw').value } };
  const boat = { zeta: { heave: +$('zHeaveB').value, roll: +$('zRollB').value, pitch: +$('zPitchB').value },
                 absolute: { surge: +$('bSurgeB').value, sway: +$('bSwayB').value, yaw: +$('bYawB').value } };
  return { ...exo, EXO: exo, BOAT: boat };
}
function setStatus(msg, cls = '') { $('status').innerHTML = `<span class="${cls}">${msg}</span>`; }

// ============================================================ config / tables
function effectiveComponents() {
  return S.config.components.map((c) => {
    const o = S.overrides.components[c.id] || {};
    return { ...c, mass_kg: o.mass_kg ?? c.mass_kg, com_m: o.com_m ?? c.com_m,
             com_source: o.com_m ? 'user_edit' : c.com_source, mass_source: o.mass_kg !== undefined ? 'user_edit' : c.mass_source };
  });
}
function effectiveBoat() {
  const b = S.config.host_boat; if (!b) return null;
  const o = S.overrides.host_boat || {};
  return { ...b, ...o, placement_in_exo_frame: { ...b.placement_in_exo_frame, ...(o.placement_in_exo_frame || {}) },
           line_defaults: { ...b.line_defaults, ...(o.line_defaults || {}) }, people: o.people || [], lines: o.lines || b.lines || [] };
}
// ---- mooring lines (edit list; the full list is sent as host_boat.lines when edited)
function linesList() { const b = effectiveBoat(); return b ? JSON.parse(JSON.stringify(b.lines)) : []; }
function writeLines(list) {
  S.overrides.host_boat = S.overrides.host_boat || { people: [] };
  S.overrides.host_boat.lines = list;
  setTimeout(() => { renderLines(); placeLineHandles(); }, 0);      // deferred: never replace the table while one of its inputs still has focus
  evaluate();
}
function lineResult(id) { return ((S.still && S.still.lines) || []).find((l) => l.id === id); }
function renderLines() {
  const b = effectiveBoat(); $('linesSection').style.display = (b && b.included !== false) ? '' : 'none'; if (!b) return;
  const d = b.line_defaults || {};
  const num = (i, k, j, v, step = 0.05) => `<input type="number" step="${step}" data-i="${i}" data-k="${k}" data-j="${j}" value="${v === undefined || v === null ? '' : v}">`;
  const rows = b.lines.map((l, i) => {
    const r = lineResult(l.id);
    const ten = r ? (r.slack ? '<b class="nc">slack</b>' : `${r.tension_N.toFixed(0)} N`) : '<span class="nc">—</span>';
    return `<tr class="${S.selected && S.selected.startsWith('LINE:' + l.id + ':') ? 'sel' : ''}" data-line="${l.id}"><td><input type="text" data-i="${i}" data-k="id" value="${l.id}" style="width:74px"></td>` +
      `<td>${num(i, 'exo_point_m', 0, l.exo_point_m[0])}${num(i, 'exo_point_m', 1, l.exo_point_m[1])}${num(i, 'exo_point_m', 2, l.exo_point_m[2])}</td>` +
      `<td>${num(i, 'boat_point_m', 0, l.boat_point_m[0])}${num(i, 'boat_point_m', 1, l.boat_point_m[1])}${num(i, 'boat_point_m', 2, l.boat_point_m[2])}</td>` +
      `<td><input type="number" step="500" data-i="${i}" data-k="stiffness_N_per_m" placeholder="${d.stiffness_N_per_m ?? ''}" value="${l.stiffness_N_per_m ?? ''}" style="width:52px"></td>` +
      `<td><input type="number" step="10" data-i="${i}" data-k="pretension_N" placeholder="${d.pretension_N ?? ''}" value="${l.pretension_N ?? ''}" style="width:46px"></td>` +
      `<td class="small">${ten}</td><td><button data-i="${i}" data-k="rm">✕</button></td></tr>`;
  });
  $('lines').innerHTML = `<tr><th>id</th><th>EXO x, y, z [m]</th><th>boat x, y, z [m]</th><th>k</th><th>T₀</th><th>tension</th><th></th></tr>${rows.join('')}`;
  $('lines').querySelectorAll('input').forEach((el) => el.addEventListener('change', (e) => {
    const list = linesList(); const { i, k, j } = e.target.dataset; const l = list[+i];
    if (k === 'id') l.id = e.target.value || l.id;
    else if (j !== undefined) l[k][+j] = parseFloat(e.target.value) || 0;
    else { const v = parseFloat(e.target.value); if (Number.isNaN(v)) delete l[k]; else l[k] = v; }
    writeLines(list);
  }));
  $('lines').querySelectorAll('button').forEach((bt) => bt.addEventListener('click', () => { const list = linesList(); list.splice(+bt.dataset.i, 1); if (S.selected && S.selected.startsWith('LINE:')) { S.selected = null; tctl.detach(); } writeLines(list); }));
  $('lines').querySelectorAll('tr[data-line]').forEach((tr) => tr.addEventListener('click', (e) => { if (e.target.tagName === 'INPUT' || e.target.tagName === 'BUTTON') return; selectComponent(`LINE:${tr.dataset.line}:exo`); }));
  const presets = (S.meta && S.meta.line_presets) || (S.config && S.config.host_boat && S.config.host_boat.line_presets) || [];
  const cur = $('linePreset').value;
  $('linePreset').innerHTML = presets.length ? presets.map((p) => `<option value="${p.id}" title="${p.note || ''}">${p.title || p.id}</option>`).join('') : '<option value="">no presets (backend without line_presets)</option>';
  if (cur) $('linePreset').value = cur;
  const rs = (S.still && S.still.lines) || [];
  $('linesNote').textContent = rs.length ? (S.still.lines_note || '') : (S.still && S.still.bodies && S.still.bodies.boat ? 'lines not in the equilibrium (boat not solved?)' : '');
}
$('applyPreset').onclick = () => {
  const p = ((S.meta && S.meta.line_presets) || (S.config && S.config.host_boat && S.config.host_boat.line_presets) || []).find((x) => x.id === $('linePreset').value); if (!p) { setStatus('no preset selected', 'nc'); return; }
  writeLines(JSON.parse(JSON.stringify(p.lines)));
  setStatus(`line preset "${p.title || p.id}" applied${p.note ? ' — ' + p.note : ''}`, 'muted');
};
$('addLine').onclick = () => {
  const list = linesList(); const n = list.length + 1;
  list.push({ id: `LINE_${n}`, exo_point_m: [2.1, 0.0, 0.0], boat_point_m: [0.3, 0.0, 0.8] });
  writeLines(list);
};
// ---- propulsion (quasi-static thrust setting)
function setThrust(fraction, fromButtons = true) {
  const f = Math.max(0, Math.min(1, fraction));
  if (f > 0) S.overrides.propulsion = { thrust_fraction: f, unit: $('thrUnit').value }; else delete S.overrides.propulsion;
  if (fromButtons) $('thrCustom').value = Math.round(f * 100);
  document.querySelectorAll('button.thr').forEach((b) => b.classList.toggle('on', +b.id.slice(3) === Math.round(f * 100)));
  evaluate();
}
[0, 20, 50, 100].forEach((v) => { $(`thr${v}`).onclick = () => setThrust(v / 100); });
$('thrCustom').addEventListener('change', () => setThrust((+$('thrCustom').value || 0) / 100, false));
$('thrUnit').addEventListener('change', () => { if (S.overrides.propulsion) setThrust(S.overrides.propulsion.thrust_fraction, false); });
function syncPropulsionUI() {
  const p = S.overrides.propulsion; const f = p ? p.thrust_fraction : 0;
  $('thrCustom').value = Math.round(f * 100); if (p && p.unit) $('thrUnit').value = p.unit;
  document.querySelectorAll('button.thr').forEach((b) => b.classList.toggle('on', +b.id.slice(3) === Math.round(f * 100)));
}
function allSurfaces() {
  const s = { ...S.config.standing_surfaces };
  const b = effectiveBoat(); if (b && b.included !== false) Object.assign(s, b.standing_surfaces);
  return s;
}
function renderComponents() {
  const rows = effectiveComponents().map((c) => {
    const com = c.com_m || [null, null, null];
    const cell = (k, v) => `<input type="number" step="0.01" data-id="${c.id}" data-k="${k}" value="${v === null ? '' : v}" ${c.category === 'float' && k !== 'mass' ? 'disabled title="float COM follows the buoyant proxy; replace the surface instead"' : ''}>`;
    const src = c.com_m ? (c.com_source === 'user_edit' ? '<b>edited</b>' : c.com_source) : '<span class="nc">null</span>';
    return `<tr class="${S.selected === c.id ? 'sel' : ''}" data-id="${c.id}"><td>${c.id}</td><td>${cell('mass', c.mass_kg)}</td><td>${cell('x', com[0])}</td><td>${cell('y', com[1])}</td><td>${cell('z', com[2])}</td><td class="small">${src}</td></tr>`;
  });
  $('components').innerHTML = `<tr><th>id</th><th>kg</th><th>COM x</th><th>y</th><th>z [m]</th><th>COM src</th></tr>${rows.join('')}`;
  $('components').querySelectorAll('input').forEach((inp) => inp.addEventListener('change', onComponentEdit));
  $('components').querySelectorAll('tr[data-id]').forEach((tr) => tr.addEventListener('click', (e) => { if (e.target.tagName !== 'INPUT') selectComponent(tr.dataset.id); }));
}
function onComponentEdit(e) {
  const { id, k } = e.target.dataset;
  const base = S.config.components.find((c) => c.id === id);
  const o = S.overrides.components[id] = S.overrides.components[id] || {};
  if (k === 'mass') { o.mass_kg = parseFloat(e.target.value); }
  else {
    const cur = o.com_m || base.com_m || [NaN, NaN, NaN];
    const idx = { x: 0, y: 1, z: 2 }[k];
    const v = [...cur]; v[idx] = parseFloat(e.target.value);
    if (v.some((x) => Number.isNaN(x))) { setStatus(`${id}: all three COM coordinates are needed`, 'nc'); o.com_m = v.map((x) => Number.isNaN(x) ? null : x); return; }
    o.com_m = v;
  }
  renderComponents(); placeHandles(); evaluate();
}
function allPeople() {   // [{person, list}] merged view of EXO + boat people
  const out = S.overrides.people.map((p) => ({ p, list: S.overrides.people }));
  (S.overrides.host_boat.people || []).forEach((p) => out.push({ p, list: S.overrides.host_boat.people }));
  return out;
}
function renderPeople() {
  const surfs = Object.keys(allSurfaces());
  const rows = allPeople().map(({ p }, i) => `<tr class="${S.selected === p.id ? 'sel' : ''}">
    <td><input type="text" data-i="${i}" data-k="id" value="${p.id}" style="width:60px"></td>
    <td><input type="number" step="1" data-i="${i}" data-k="mass_kg" value="${p.mass_kg}"></td>
    <td><select data-i="${i}" data-k="surface">${surfs.map((s) => `<option ${s === p.surface ? 'selected' : ''}>${s}</option>`).join('')}</select></td>
    <td><select data-i="${i}" data-k="posture">${Object.keys(POSTURE_H).map((s) => `<option ${s === p.posture ? 'selected' : ''}>${s}</option>`).join('')}</select></td>
    <td><input type="number" step="0.05" data-i="${i}" data-k="x_m" value="${p.x_m}"></td>
    <td><input type="number" step="0.05" data-i="${i}" data-k="y_m" value="${p.y_m}"></td>
    <td><input type="number" step="0.05" data-i="${i}" data-k="com_height_m" value="${p.com_height_m ?? POSTURE_H[p.posture]}"></td>
    <td><button data-i="${i}" data-k="rm">✕</button></td></tr>`);
  $('people').innerHTML = `<tr><th>id</th><th>kg</th><th>surface</th><th>posture</th><th>x</th><th>y</th><th>COM h</th><th></th></tr>${rows.join('')}`;
  $('people').querySelectorAll('input,select').forEach((el) => el.addEventListener('change', (e) => {
    const { p, list } = allPeople()[+e.target.dataset.i]; const k = e.target.dataset.k;
    p[k] = (k === 'id' || k === 'surface' || k === 'posture') ? e.target.value : parseFloat(e.target.value);
    if (k === 'posture') p.com_height_m = POSTURE_H[p.posture];
    if (k === 'surface') {               // move between the EXO and boat lists, snap into the surface
      const target = BODY_OF_SURFACE(p.surface) === 'BOAT' ? S.overrides.host_boat.people : S.overrides.people;
      if (target !== list) { list.splice(list.indexOf(p), 1); target.push(p); }
      const sf = allSurfaces()[p.surface]; p.x_m = (sf.x_range_m[0] + sf.x_range_m[1]) / 2; p.y_m = 0;
    }
    renderPeople(); placePeople(); evaluate();
  }));
  $('people').querySelectorAll('button').forEach((b) => b.addEventListener('click', () => { const { p, list } = allPeople()[+b.dataset.i]; list.splice(list.indexOf(p), 1); renderPeople(); placePeople(); evaluate(); }));
}
$('addPerson').onclick = () => {
  const n = allPeople().length + 1;
  S.overrides.people.push({ id: `PERSON_${n}`, name: `Person ${n} (illustrative)`, mass_kg: 80, mass_source: 'illustrative',
                            surface: 'observation_deck', posture: 'standing', x_m: 2.81, y_m: (n % 2 ? -1 : 1) * 0.8, com_height_m: 1.0 });
  renderPeople(); placePeople(); evaluate();
};
// ---- boat inputs
function renderBoatInputs() {
  const b = effectiveBoat();
  $('boatSection').style.display = b ? '' : 'none'; if (!b) return;
  $('boatIncluded').checked = b.included !== false;
  $('boatMass').value = b.mass_kg ?? ''; const c = b.com_m || [null, null, null];
  $('boatCx').value = c[0] ?? ''; $('boatCy').value = c[1] ?? ''; $('boatCz').value = c[2] ?? '';
  $('boatX').value = b.placement_in_exo_frame.x_m; $('boatY').value = b.placement_in_exo_frame.y_m; $('boatYaw').value = b.placement_in_exo_frame.yaw_deg;
  $('lineT0').value = b.line_defaults.pretension_N; $('lineK').value = b.line_defaults.stiffness_N_per_m;
  $('boatNote').textContent = `${b.name}. Mass: ${b.mass_source}. Hull: proxy, unverified. Placement: ${b.placement_in_exo_frame.source}`;
}
function readBoatInputs() {
  if (!S.config || !S.config.host_boat) return;
  const o = S.overrides.host_boat = S.overrides.host_boat || { people: [] };
  o.included = $('boatIncluded').checked;
  const m = parseFloat($('boatMass').value); if (!Number.isNaN(m)) o.mass_kg = m;
  const c = [parseFloat($('boatCx').value), parseFloat($('boatCy').value), parseFloat($('boatCz').value)];
  if (c.every((x) => !Number.isNaN(x))) o.com_m = c;
  o.placement_in_exo_frame = { x_m: +$('boatX').value, y_m: +$('boatY').value, yaw_deg: +$('boatYaw').value };
  o.line_defaults = { pretension_N: +$('lineT0').value, stiffness_N_per_m: +$('lineK').value };
}
['boatIncluded', 'boatMass', 'boatCx', 'boatCy', 'boatCz', 'boatX', 'boatY', 'boatYaw', 'lineT0', 'lineK'].forEach((id) => $(id).addEventListener('change', () => { readBoatInputs(); renderPeople(); placePeople(); renderLines(); placeLineHandles(); evaluate(); }));

async function loadBase(name, keepOverrides = false) {
  S.base = name; $('base').value = name;
  S.config = await api(`/api/config/${name}`);
  if (!keepOverrides) { S.overrides = { components: {}, people: [], environment: {}, host_boat: { people: [] } }; S.scenarioName = null; }
  const env = { ...S.config.environment, ...S.overrides.environment };
  $('rho').value = env.rho_kg_m3 ?? ''; $('depth').value = env.water_depth_m ?? '';
  S.hydroReady = false; S.waveRes = null; S.still = null; S.refPose = null; stopAnim();
  $('banner').textContent = S.config.result_label; $('banner').className = 'banner ' + (S.config.mode === 'baseline' ? 'baseline' : '');
  $('label').textContent = S.config.result_label; $('label').className = 'label ' + (S.config.mode === 'baseline' ? 'baseline' : '');
  renderBoatInputs(); renderComponents(); renderPeople(); renderLines(); syncPropulsionUI(); renderNotes(); placeHandles(); placePeople(); placeLineHandles(); applyVisualOverrides();
}
$('base').onchange = () => loadBase($('base').value).then(evaluate);
$('loadScenario').onclick = async () => {
  const sc = await api(`/api/scenario/${$('scenario').value}`);
  await loadBase(sc.base);
  const ov = JSON.parse(JSON.stringify(sc.overrides || {}));
  S.overrides = { components: {}, people: [], environment: {}, ...ov };
  S.overrides.people = S.overrides.people || []; S.overrides.host_boat = { people: [], ...(S.overrides.host_boat || {}) }; S.overrides.host_boat.people = S.overrides.host_boat.people || [];
  S.scenarioName = sc.name;
  if (sc.hydro_settings) for (const [k, id] of Object.entries({ omega_min: 'omMin', omega_max: 'omMax', omega_step: 'omStep', panel_size_m: 'panel' })) if (sc.hydro_settings[k] !== undefined) $(id).value = sc.hydro_settings[k];
  if (sc.wave) { $('H').value = sc.wave.H_m; $('T').value = sc.wave.T_s; $('heading').value = sc.wave.heading_deg; }
  if (sc.damping) {
    const de = sc.damping.EXO || sc.damping, db = sc.damping.BOAT;
    if (de.zeta) { $('zHeave').value = de.zeta.heave; $('zRoll').value = de.zeta.roll; $('zPitch').value = de.zeta.pitch; $('bSurge').value = de.absolute.surge; $('bSway').value = de.absolute.sway; $('bYaw').value = de.absolute.yaw; }
    if (db && db.zeta) { $('zHeaveB').value = db.zeta.heave; $('zRollB').value = db.zeta.roll; $('zPitchB').value = db.zeta.pitch; $('bSurgeB').value = db.absolute.surge; $('bSwayB').value = db.absolute.sway; $('bYawB').value = db.absolute.yaw; }
  }
  const env = { ...S.config.environment, ...S.overrides.environment }; $('rho').value = env.rho_kg_m3 ?? ''; $('depth').value = env.water_depth_m ?? '';
  $('scenarioNotes').textContent = `${sc.title} — ${sc.notes || ''}`;
  S.refPose = null;
  renderBoatInputs(); renderComponents(); renderPeople(); renderLines(); syncPropulsionUI(); placeHandles(); placePeople(); placeLineHandles(); await evaluate();
};
$('saveScenario').onclick = async () => {
  const name = $('saveName').value.trim() || `scenario_${Date.now()}`;
  const p = statePayload();
  const r = await api('/api/scenario/save', { ...p, name, title: name, notes: 'user-saved scenario' });
  S.scenarioName = name; fillScenarios(r.scenarios, name); setStatus(`saved ${r.saved}`, 'muted');
};
function fillScenarios(list, sel) { $('scenario').innerHTML = list.map((s) => `<option ${s === sel ? 'selected' : ''}>${s}</option>`).join(''); }

// ============================================================ still water
let evalTimer = null; let evalSeq = 0;
function evaluate(quick = false) { clearTimeout(evalTimer); return new Promise((res) => { evalTimer = setTimeout(() => res(doEvaluate(quick)), quick ? 0 : 120); }); }
async function doEvaluate(quick = false) {
  const seq = ++evalSeq; const t0 = performance.now();
  if (!quick) setStatus('still-water solve…');
  busy(true);
  const slow = setTimeout(() => { if (seq === evalSeq) setStatus('still-water solve… (coupled EXO + boat equilibrium: 1–3 s; the server is otherwise busy if this persists)', 'nc'); }, 4000);
  try {
    const r = await api('/api/evaluate', statePayload());
    clearTimeout(slow); if (seq === evalSeq) busy(false);
    if (seq !== evalSeq) return;
    const hadWave = !!S.waveRes;
    S.still = r; S.hydroReady = false; S.waveRes = null; pipelineAfterStill(r);
    if (!S.refPose && r.bodies && r.bodies.exo && r.bodies.exo.pose) S.refPose = refPoseOf(r);
    renderStill(r); renderLines(); applyPose(r); if (tctl.dragging) firstOrderPreview();
    const ms = (performance.now() - t0).toFixed(0);
    setStatus(r.status.equilibrium === 'solved' ? `still water: solved in ${ms} ms (${r.equilibrium.solver.n_evaluations} evaluations${r.bodies && r.bodies.boat && r.bodies.boat.equilibrium ? ', boat ' + (r.bodies.boat.equilibrium.solver ? r.bodies.boat.equilibrium.solver.n_evaluations : '-') : ''})` : `still water: ${r.status.equilibrium || r.status.all}`, r.status.equilibrium === 'solved' ? 'ok' : 'nc');
    if (r.status.equilibrium === 'solved' && $('autoWave').checked) autoWave(seq);
    else if (S.anim.playing || hadWave) stopAnim();
  } catch (e) { clearTimeout(slow); busy(false); setStatus('evaluate failed: ' + e.message, 'nc'); }
}
function refPoseOf(r) {
  const o = {};
  for (const [k, b] of Object.entries(r.bodies || {})) if (b.pose) o[k === 'exo' ? 'EXO' : 'BOAT'] = { R: b.pose.R_world, com: b.pose.com_world.slice() };
  return o;
}
$('setRef').onclick = () => { if (S.still) { S.refPose = refPoseOf(S.still); applyPose(S.still); setStatus('reference pose for the static-Δ exaggeration set to the current still-water pose', 'muted'); } };
$('exag').addEventListener('input', () => { $('exagVal').textContent = $('exag').value; if (S.still && !S.anim.playing) applyPose(S.still); });
// Live wave motion: after each still-water solve, fetch the wave response again if the BEM for this (or a nearby) pose exists.
// The animation clock is kept so that a battery or line move updates the motion in place.
async function autoWave(seq) {
  if (S.waveBusy) { S.wavePending = true; return; }
  S.waveBusy = true; GP.wave = true; renderGlobalProgress();
  try {
    const r = await api('/api/wave', { ...statePayload(), allow_pose_reuse: true });
    if (seq !== evalSeq) return;
    if (r.status === 'no_hydro' || r.status === 'not_computed') { stopAnim(); pipelineAfterWave(r); $('animNote').textContent = 'no BEM for this pose yet — 2 · Compute BEM (the motion then follows every edit, reusing the coefficients of nearby poses)'; return; }
    S.waveRes = r; S.hydroReady = true; renderWaves(r); pipelineAfterWave(r);
    if (r.status === 'out_of_range') { stopAnim(); return; }
    startAnim(false);
    const pr = r.hydro_meta && r.hydro_meta.pose_reuse;
    if (pr) $('animNote').textContent = (pr.tier === 'approximate' ? 'APPROXIMATE PREVIEW — ' : 'nearby-pose BEM — ') + `Δz ${((pr.dz_m || 0) * 1000).toFixed(0)} mm, Δtrim ${(pr.dtrim_deg || 0).toFixed(2)}°, Δheel ${(pr.dheel_deg || 0).toFixed(2)}° from the computed pose; 2 · Compute BEM for exact coefficients`;
  } catch (e) { if (!/not computed|hydrodynamic/i.test(e.message)) setStatus('live wave update failed: ' + e.message, 'nc'); else { stopAnim(); $('animNote').textContent = 'no BEM for this pose — 2 · Compute BEM'; } }
  finally { S.waveBusy = false; GP.wave = false; renderGlobalProgress(); if (S.wavePending) { S.wavePending = false; autoWave(evalSeq); } }
}
function kv(rows) { return `<table class="res">${rows.map(([k, v, u]) => `<tr><td>${k}</td><td>${v}</td><td class="muted">${u || ''}</td></tr>`).join('')}</table>`; }
function renderStill(r) {
  const m = r.mass; const e = r.equilibrium; const st = r.stability_static; const fb = e && e.freeboard;
  let h = `<div class="flag ${r.mode === 'baseline' ? 'info' : ''}">${r.label}</div>`;
  (r.issues || []).forEach(([l, msg]) => { h += `<div class="flag ${l}">${msg}</div>`; });
  if (!m) { $('tab-still').innerHTML = h + '<div class="flag error">Invalid input — nothing computed. Fix the errors above.</div>'; return; }
  h += '<h3>EXO — mass accounting (each parent once)</h3>' + kv([
    ['listed subtotal', fmt(m.total_listed_mass_kg, 1), 'kg — ' + Object.entries(m.by_category_kg).map(([k, v]) => `${k} ${v}`).join(', ')],
    ['total of items incl. people', fmt(m.total_mass_kg, 1), 'kg'],
    ['COM (body/CAD)', m.com_m ? m.com_m.map((x) => x.toFixed(3)).join(', ') : fmt(null), 'm'],
    ['inertia about COM (diag)', m.inertia_com_kgm2 ? [0, 1, 2].map((i) => m.inertia_com_kgm2[i][i].toFixed(0)).join(', ') : fmt(null), 'kg·m² (Ixx, Iyy, Izz)'],
  ]);
  h += `<div class="small">${m.scope_note}</div>`;
  if (m.missing_com && m.missing_com.length) h += `<div class="flag">COM missing for ${m.missing_com.length} item(s): ${m.missing_com.join(', ')}</div>`;
  if (r.not_computed && Object.keys(r.not_computed).length) h += '<h3>Not computed</h3>' + Object.entries(r.not_computed).map(([k, v]) => `<div class="flag">${k}: ${v.join('; ')}</div>`).join('');
  h += '<h3>EXO — buoyant volume (six float proxies)</h3>' + kv([['total volume', fmt(r.buoyant_volume_total_m3), 'm³'], ['≙ max buoyant mass at ρ', r.level_keel_screening ? fmt(r.level_keel_screening.max_buoyant_mass_kg, 0) : fmt(null), 'kg']]);
  if (r.level_keel_screening) { const l = r.level_keel_screening; h += kv([['level-keel draft (listed subtotal)', fmt(l.level_draft_m), 'm'], ['reserve buoyancy', fmt(l.reserve_buoyancy_mass_kg, 0), `kg (${(l.reserve_fraction * 100).toFixed(0)} %)`]]) + `<div class="small">${l.note}</div>`; }
  if (e && e.feasible) {
    h += '<h3>EXO — still-water equilibrium</h3>' + kv([
      ['heel φ', fmt(e.heel_deg, 3), 'deg (+ = +Y side up)'], ['trim θ', fmt(e.trim_deg, 3), 'deg (+ = +X end down)'],
      ['displaced volume / mass', `${fmt(e.displaced_volume_m3, 4)} / ${fmt(e.displaced_mass_kg, 1)}`, 'm³ / kg'],
      ['COM height above WL', fmt(e.com_height_above_waterline_m), 'm'],
      ['centre of buoyancy (body)', e.centre_of_buoyancy_body_m.map((x) => x.toFixed(3)).join(', '), 'm'],
      ['residual Fz / Mx / My', `${e.residuals.Fz_N.toExponential(1)} / ${e.residuals.Mx_Nm.toExponential(1)} / ${e.residuals.My_Nm.toExponential(1)}`, 'N, N·m, N·m'],
    ]);
    h += '<h3>EXO — freeboards &amp; draft</h3>' + kv([
      ['max draft (float bottom)', fmt(fb.draft_max_m), 'm'], ['min float-top freeboard', fmt(fb.float_top_freeboard_min_m), 'm'],
      ['min lower-deck freeboard', fmt(fb.lower_deck_freeboard_min_m), 'm (deck plate corners)'],
      ['observation deck centre height', fmt(fb.observation_deck_centre_height_m), 'm above WL'],
    ]);
    h += '<table class="res"><tr><th>float</th><th>volume m³</th><th>top above WL</th><th>bottom below WL</th></tr>' +
      Object.entries(e.per_float_volume_m3).map(([k, v]) => `<tr><td>${k}</td><td>${v.toFixed(4)}</td><td>${fb.per_float[k].top_above_waterline_m.toFixed(3)}</td><td>${fb.per_float[k].bottom_below_waterline_m.toFixed(3)}</td></tr>`).join('') + '</table>';
    h += '<h3>EXO — static initial stability</h3>' + kv([
      ['GM transverse / longitudinal', `${fmt(st.GM_transverse_m)} / ${fmt(st.GM_longitudinal_m)}`, 'm'],
      ['C33 / C44 / C55', `${st.C_hydrostatic_NmPerUnit[0][0].toFixed(0)} / ${st.C_hydrostatic_NmPerUnit[1][1].toFixed(0)} / ${st.C_hydrostatic_NmPerUnit[2][2].toFixed(0)}`, 'N/m, N·m/rad, N·m/rad'],
      ['restoring matrix positive definite', st.statically_stable_here ? 'yes' : '<b>no</b>', ''],
    ]) + `<div class="small">${st.scope}</div>`;
  } else if (e && !e.feasible) {
    h += `<div class="flag error"><b>EXO: no feasible equilibrium.</b> ${e.reason}</div>`;
  }
  // ---- boat
  const b = r.bodies && r.bodies.boat;
  if (b) {
    const be = b.equilibrium; const bm = b.mass;
    h += `<h3>Hydronaute — ${b.name}</h3><div class="small">${b.mass_note}</div><div class="small">${b.hull_note}</div>`;
    h += kv([['boat mass incl. people', fmt(bm.total_mass_kg ?? bm.total_listed_mass_kg, 0), 'kg'], ['COM (boat frame)', bm.com_m ? bm.com_m.map((x) => x.toFixed(2)).join(', ') : fmt(null), 'm'],
             ['proxy hull volume at the package waterline', b.proxy_hull_at_drawn_waterline ? `${fmt(b.proxy_hull_at_drawn_waterline.displaced_volume_m3, 2)} m³ ≙ ${fmt(b.proxy_hull_at_drawn_waterline.equivalent_mass_kg, 0)} kg` : fmt(null), 'consistency check vs 2.1–3.0 t']]);
    if (be && be.feasible) {
      h += kv([['heel / trim', `${fmt(be.heel_deg, 3)} / ${fmt(be.trim_deg, 3)}`, 'deg (boat frame; + = port up / bow down)'],
               ['draft (hull proxy, keel excluded)', fmt(be.draft_hull_proxy_m), 'm — catalogue 0.75 m incl. keel'],
               ['min deck-edge freeboard', fmt(be.deck_edge_freeboard_min_m), 'm'],
               ['displaced mass', fmt(be.displaced_mass_kg, 0), 'kg'],
               ['GM transverse / longitudinal', `${fmt(b.stability_static.GM_transverse_m, 2)} / ${fmt(b.stability_static.GM_longitudinal_m, 2)}`, 'm']]);
      (b.flags || []).forEach((f) => { h += `<div class="flag">${f}</div>`; });
    } else if (be) h += `<div class="flag error"><b>Boat: no feasible equilibrium.</b> ${be.reason}</div>`;
    else h += `<div class="flag">Boat equilibrium not computed: ${Object.values(b.not_computed || {}).flat().join('; ')}</div>`;
    if (r.clearances) {
      const c = r.clearances;
      h += '<h3>Berth geometry (still water, assumed placement)</h3>' + kv([
        ['boat roof under EXO headers / observation deck / panels', Object.values(c.vertical_clearance_m).map((v) => v === null ? 'n/a' : v.toFixed(2)).join(' / '), 'm'],
        ['hull to float inner face, port / starboard', `${fmt(c.lateral_clearance_to_float_inner_face_m.port, 2)} / ${fmt(c.lateral_clearance_to_float_inner_face_m.starboard, 2)}`, 'm'],
        ['transom to EXO rear-deck plate', fmt(c.transom_to_rear_deck_plate_m, 2), 'm (negative = overlap)'],
        ['EXO deck datum / boat deck above WL', `${fmt(c.relative_levels_m.exo_deck_datum_above_wl, 2)} / ${fmt(c.relative_levels_m.boat_deck_above_wl, 2)}`, 'm'],
      ]);
      c.flags.forEach((f) => { h += `<div class="flag ${f.startsWith('INTERFERENCE') ? 'error' : ''}">${f}</div>`; });
    }
    if (r.lines) {
      const ce = r.coupled_equilibrium;
      h += '<h3>Mooring lines (still water)</h3>';
      if (ce) h += kv([['coupled equilibrium', ce.converged ? (ce.converged_at_slack_boundary ? 'converged (at a slack/taut boundary)' : 'converged') : '<b>not converged</b>', `residual ${ce.residual_relative.toExponential(1)} of Mg`],
                       ['boat shift from nominal berth', `${(ce.boat_shift_from_nominal.dx_m * 1000).toFixed(0)} / ${(ce.boat_shift_from_nominal.dy_m * 1000).toFixed(0)} mm, ${ce.boat_shift_from_nominal.dyaw_deg.toFixed(2)}°`, 'x / y / yaw']]);
      h += '<table class="res"><tr><th>line</th><th>length</th><th>tension at rest</th><th>nominal T₀</th><th>vertical comp.</th><th>k</th></tr>' +
        r.lines.map((l) => `<tr><td>${l.id}</td><td>${l.length_m.toFixed(2)} m</td><td>${l.slack ? '<b>slack</b>' : l.tension_N.toFixed(0) + ' N'}</td><td>${(l.nominal_pretension_N ?? l.pretension_N).toFixed(0)} N</td><td>${l.vertical_component_N.toFixed(0)} N</td><td>${l.stiffness_N_per_m.toFixed(0)} N/m</td></tr>`).join('') + '</table>' + `<div class="small">${r.lines_note}</div>`;
    }
    if (r.combined_note) h += `<div class="small">${r.combined_note}</div>`;
  }
  h += renderPropulsion(r);
  (r.flags || []).forEach((f) => { if (!(r.clearances && r.clearances.flags.includes(f))) h += `<div class="flag">${f}</div>`; });
  $('tab-still').innerHTML = h;
}
function renderPropulsion(r) {
  const want = S.overrides.propulsion && S.overrides.propulsion.thrust_fraction > 0;
  const p = r.propulsion;
  if (!want && !p) return '';
  let h = '<h3>Propulsion (quasi-static)</h3>';
  if (!p) return h + `<div class="flag">thrust ${Math.round(S.overrides.propulsion.thrust_fraction * 100)} % requested — <span class="nc">not computed</span> (backend without propulsion support, or no solved equilibrium)</div>`;
  const res = p.resistance || {};
  h += kv([
    ['unit / setting', `${p.unit_title || p.unit || '?'} at ${fmt((p.thrust_fraction ?? 0) * 100, 0)} %`, p.bollard_thrust_N ? `bollard ${fmt(p.bollard_thrust_N, 0)} N` : ''],
    ['thrust (total)', fmt(p.thrust_total_N, 0), 'N' + (p.thrust_points_world ? ` at ${p.thrust_points_world.length} point(s), orange arrows in 3D` : '')],
    ['steady speed', p.speed_m_s === undefined ? fmt(null) : `${fmt(p.speed_m_s, 2)} m/s = ${fmt(p.speed_kn ?? p.speed_m_s * 1.943844, 2)} kn`, p.converged === false ? '<b>not converged</b>' : 'thrust = total resistance'],
    ['resistance EXO / boat / total', `${fmt(res.exo_N, 0)} / ${fmt(res.boat_N, 0)} / ${fmt(res.total_N, 0)}`, 'N'],
    ['force carried by the lines', fmt(p.line_load_N, 0), 'N' + (p.line_load_note ? ' — ' + p.line_load_note : '')],
  ]);
  if (res.breakdown) {
    const rows = []; const walk = (o, pre) => { for (const [k, v] of Object.entries(o)) { if (v && typeof v === 'object') walk(v, pre ? `${pre} · ${k}` : k); else rows.push([pre ? `${pre} · ${k}` : k, v]); } };
    walk(res.breakdown, '');
    const fv = (k, v) => typeof v !== 'number' ? fmt(v) : /_N$/.test(k) ? v.toFixed(1) : /^Re|Re$/.test(k) ? v.toExponential(2) : Math.abs(v) < 0.1 ? v.toPrecision(3) : v.toFixed(3);
    h += '<table class="res"><tr><th>resistance term</th><th>value</th></tr>' + rows.map(([k, v]) => `<tr><td>${k.replace(/_/g, ' ')}</td><td>${fv(k, v)}</td></tr>`).join('') + '</table>';
  }
  (p.notes || []).forEach((n) => { h += `<div class="small">${n}</div>`; });
  if (p.label) h += `<div class="flag">${p.label}</div>`;
  return h;
}

// ============================================================ pipeline chips (header): what is current, what is cached, what is approximate
function setPipeline(part, cls, text, title) { const el = $(part); if (!el) return; el.className = 'chip ' + (cls || ''); el.textContent = text; el.title = title || ''; }
function pipelineAfterStill(r) {
  if (!r || r.status.all === 'invalid_input') { setPipeline('pipStill', 'err', '① still water: invalid input'); return; }
  if (r.status.equilibrium !== 'solved') { setPipeline('pipStill', 'err', `① still water: ${r.status.equilibrium === 'no_feasible_equilibrium' ? 'no equilibrium' : 'not computed'}`); setPipeline('pipBem', '', '② BEM'); setPipeline('pipWave', '', '③ waves'); return; }
  const ce = r.coupled_equilibrium;
  const cstate = ce ? (!ce.converged ? 'coupled FAILED' : ce.interference ? 'coupled: CONTACT (boat into the EXO)' : 'coupled ok') : 'solved';
  setPipeline('pipStill', ce && (!ce.converged || ce.interference) ? 'warn' : 'ok', `① still water: ${cstate}${r.propulsion ? ` · motor ${Math.round(r.propulsion.thrust_fraction * 100)} %` : ''}`);
}
function pipelineAfterWave(r) {
  if (!r || r.status === 'no_hydro' || r.status === 'not_computed') { setPipeline('pipBem', 'warn', '② BEM: needs compute for this pose'); setPipeline('pipWave', '', '③ waves: off'); return; }
  const pr = r.hydro_meta && r.hydro_meta.pose_reuse;
  setPipeline('pipBem', pr ? (pr.tier === 'approximate' ? 'warn' : 'ok') : 'ok', pr ? (pr.tier === 'approximate' ? '② BEM: APPROXIMATE (nearby pose)' : '② BEM: nearby pose') : '② BEM: exact pose', pr ? pr.note : 'coefficients computed for this exact pose');
  const rw = r.regular_wave || {};
  setPipeline('pipWave', rw.in_range ? 'ok' : 'warn', rw.in_range ? `③ waves: live · T ${rw.period_s} s · ${rw.heading_deg}°${r.encounter ? ' · moving' : ''}` : '③ waves: out of range');
}

// ============================================================ background jobs panel (BEM / sweeps): progress, ETA, queue, cancel
const JOBS = { list: [], timer: null, watched: new Set() };
function fmtT(s) { if (s === null || s === undefined || !isFinite(s)) return '…'; s = Math.max(0, Math.round(s)); return s >= 60 ? `${Math.floor(s / 60)} min ${String(s % 60).padStart(2, '0')} s` : `${s} s`; }
function renderJobs() {
  const act = JOBS.list.filter((j) => j.status === 'queued' || j.status === 'running' || (Date.now() / 1000 - (j.finished || 0)) < 60);
  $('jobs').innerHTML = act.map((j) => {
    const p = Math.round((j.progress || 0) * 100);
    const kind = j.kind === 'hydro' ? `BEM${j.two_body ? ' (EXO + boat)' : ' (EXO)'}${j.wave && j.wave.heading_deg !== undefined ? ` · ${j.wave.heading_deg}°` : ''}` : `sweep: ${j.target}`;
    const state = j.status === 'queued' ? `queued (position ${j.queue_position})` : j.status === 'running' ? `${p} % · ${fmtT(j.elapsed_s)} elapsed${j.eta_s !== undefined && j.eta_s !== null ? ` · ~${fmtT(j.eta_s)} left` : ''}` : j.status === 'done' ? `done in ${fmtT(j.seconds || j.elapsed_s)}` : j.status === 'cancelled' ? 'cancelled' : `error: ${(j.error || '').slice(0, 160)}`;
    const cancel = (j.status === 'queued' || j.status === 'running') ? `<button class="jcancel" data-cancel="${j.id}">cancel</button>` : '';
    return `<div class="job ${j.status}"><div class="jhead"><span class="jkind">${kind}</span><span class="jstate">${state}</span>${cancel}</div><div class="bar"><i style="width:${j.status === 'done' ? 100 : p}%"></i></div><div class="jmsg">${j.message || ''}</div></div>`;
  }).join('');
  $('jobs').querySelectorAll('[data-cancel]').forEach((b) => { b.onclick = async () => { await api(`/api/job/${b.dataset.cancel}/cancel`, {}); pollJobs(); }; });
}
async function pollJobs() {
  try { JOBS.list = await fetch('/api/jobs').then((r) => r.json()); } catch (e) { return; }
  renderJobs(); renderGlobalProgress();
  const active = JOBS.list.some((j) => j.status === 'queued' || j.status === 'running');
  clearTimeout(JOBS.timer);
  JOBS.timer = setTimeout(pollJobs, active ? 1500 : 8000);
}
// thin "busy" strip at the top of the 3D view while a still-water solve is pending
function busy(on) { const b = $('busy'); if (b) b.classList.toggle('on', !!on); GP.evaluate = !!on; renderGlobalProgress(); }
// ---- global progress strip (header): aggregates the still-water solve, the wave update and the background jobs
const GP = { evaluate: false, wave: false, glb: 0, glbTotal: 2 };
function renderGlobalProgress() {
  const g = $('gprog'); if (!g) return;
  const fill = $('gprogFill'), txt = $('gprogText');
  const list = (JOBS.list || []);
  const running = list.find((j) => j.status === 'running');
  const queued = list.filter((j) => j.status === 'queued').length;
  const lastErr = list.find((j) => j.status === 'error' && Date.now() / 1000 - (j.finished || 0) < 20);
  let cls = 'idle', text = 'ready', pct = null;
  if (GP.glb < GP.glbTotal) { cls = 'busy'; text = `loading 3D models (${GP.glb}/${GP.glbTotal})…`; }
  else if (GP.evaluate) { cls = 'busy'; text = 'computing still-water equilibrium…'; }
  else if (GP.wave) { cls = 'busy'; text = 'updating wave response…'; }
  if (running) {
    const p = Math.round(100 * (running.progress || 0));
    cls = 'job'; pct = p;
    const kind = running.kind === 'hydro' ? (running.two_body ? 'BEM EXO + boat' : 'BEM EXO') : `optimising ${running.target || ''}`;
    text = `${kind}: ${p} % · ${fmtT(running.elapsed_s)} elapsed${running.eta_s ? ` · ~${fmtT(running.eta_s)} left` : ''}${queued ? ` · ${queued} queued` : ''}${GP.evaluate ? ' · still water…' : ''}`;
    if (running.message) text += ` — ${running.message}`;
  } else if (queued && cls === 'idle') { cls = 'busy'; text = `${queued} job(s) queued — starting…`; }
  else if (lastErr && cls === 'idle') { cls = 'err'; text = `job failed: ${(lastErr.error || '').slice(0, 120)}`; }
  g.className = cls;
  if (pct !== null) { fill.style.animation = 'none'; fill.style.marginLeft = '0'; fill.style.width = `${pct}%`; }
  else { fill.style.animation = ''; fill.style.marginLeft = ''; fill.style.width = ''; }
  txt.textContent = text;
}

// ============================================================ hydro + waves
$('hydro').onclick = () => ensureHydro();
async function ensureHydro() {
  if (!S.still || S.still.status.equilibrium !== 'solved') { setStatus('compute a solved still-water equilibrium first', 'nc'); return false; }
  setStatus('BEM: submitting…');
  try {
    let r = await api('/api/hydro', { ...statePayload(), allow_pose_reuse: false });     // the button always computes the EXACT pose
    if (r.status === 'error') throw new Error(r.error);
    if (r.status !== 'done') {
      const t0 = Date.now(); const jid = r.job_id; pollJobs();
      while (true) {
        await new Promise((res) => setTimeout(res, 1500));
        r = await api(`/api/job/${jid}`);
        if (r.status === 'error') throw new Error(r.error);
        if (r.status === 'cancelled') { setStatus('BEM cancelled', 'nc'); pollJobs(); return false; }
        if (r.status === 'done') break;
        setStatus(`BEM ${r.status}${r.two_body ? ' (two bodies, 12 DOF)' : ''}: ${r.n_problems || '?'} problems (+ band refinement), ${((Date.now() - t0) / 1000).toFixed(0)} s elapsed (typ. 1–2 min single body, 4–8 min with the boat; ~20–60 s for a new heading)…`);
      }
    }
    S.hydroReady = true; S.hydroMeta = r.meta;
    if ($('autoWave').checked) autoWave(evalSeq);           // the motion follows as soon as the coefficients exist
    const pr = r.meta.pose_reuse ? ` — coefficients of a nearby pose reused (Δz ${fmt((r.meta.pose_reuse.dz_m || 0) * 1000, 0)} mm, Δheel ${fmt(r.meta.pose_reuse.dheel_deg, 2)}°, Δtrim ${fmt(r.meta.pose_reuse.dtrim_deg, 2)}°)` : '';
    setStatus(`BEM done: ${r.meta.n_faces} panels, ${r.meta.n_omega} ω, heading ${r.meta.headings_deg.map((x) => x.toFixed(0)).join('/')}° exact, ${(r.meta.seconds || 0).toFixed(0)} s (${r.meta.cache}; ${r.meta.excitation_cache})${pr}`, 'ok');
    return true;
  } catch (e) { setStatus('BEM failed: ' + e.message, 'nc'); return false; }
}
$('snatch').onclick = async () => {
  if (!S.waveRes) { $('snatchStatus').textContent = 'run 3 · Wave response first'; return; }
  $('snatchStatus').textContent = 'integrating…';
  try {
    const r = await api('/api/snatch', { ...statePayload(), allow_pose_reuse: true });
    const rows = r.lines.map((l) => `<tr><td>${l.id}</td><td>${fmt(l.static_N, 0)}</td><td>${fmt(l.peak_N, 0)}</td><td>${fmt(l.min_N, 0)}</td><td>${fmt(100 * l.slack_fraction_of_cycle, 0)} %</td><td>${l.linear_amp_N === null ? '—' : fmt(l.linear_amp_N, 0)}</td><td>${l.snatch_ratio === null ? '—' : fmt(l.snatch_ratio, 2)}</td></tr>`).join('');
    const worst = Math.max(...r.lines.map((l) => l.snatch_ratio || 0));
    $('snatchOut').innerHTML = `<div class="flag ${worst > 1.5 ? 'warn' : 'info'}">Tension-only lines in the time domain (${r.n_periods} periods at T_e ${fmt(r.period_e_s, 2)} s): peak line tension up to ${fmt(Math.max(...r.lines.map((l) => l.peak_N)), 0)} N; motion amplitudes up to ${fmt(r.max_amplitude_ratio, 2)}× the linear-line model. ${r.note}</div>
      <table class="res"><tr><th>line</th><th>static [N]</th><th>peak [N]</th><th>min [N]</th><th>slack (cycle)</th><th>linear amp [N]</th><th>snatch ratio</th></tr>${rows}</table>`;
    $('snatchStatus').textContent = '';
  } catch (e) { $('snatchStatus').textContent = 'snatch check: ' + e.message; }
};
$('wave').onclick = runWave;
async function runWave() {
  if (!(await ensureHydro())) return;
  setStatus('wave response…');
  try {
    const r = await api('/api/wave', { ...statePayload(), allow_pose_reuse: $('autoWave').checked });
    pipelineAfterWave(r);
    if (r.status === 'no_hydro') { setStatus('wave: ' + (r.error || 'no hydrodynamic coefficients for this pose'), 'nc'); return; }
    S.waveRes = r; renderWaves(r); startAnim(true); setStatus(r.status === 'out_of_range' ? 'wave period outside the computed band' : 'wave response computed (linear, reconstructed)', r.status === 'out_of_range' ? 'nc' : 'ok');
    document.querySelector('nav button[data-tab=waves]').click();
  } catch (e) { setStatus('wave failed: ' + e.message, 'nc'); }
}
function dampSet(d, body) { return (d && d[body]) || d || {}; }
function renderWaves(r) {
  const rw = r.regular_wave; const nat = r.natural_frequencies;
  let h = `<div class="flag">${r.label}</div><div class="small">${r.motion_note || ''}</div>`;
  if (r.encounter) h += `<div class="flag info">Forward speed ${fmt(r.encounter.speed_m_s, 2)} m/s: encounter frequency ω_e = ${fmt(r.encounter.omega_e, 3)} rad/s (T_e = ${fmt(r.encounter.period_e_s, 2)} s). ${r.encounter.note || ''}</div>`;
  if (r.hydro_meta && r.hydro_meta.pose_reuse) { const pr = r.hydro_meta.pose_reuse; h += `<div class="flag ${pr.tier === 'approximate' ? 'warn' : 'info'}"><span class="badge ${pr.tier === 'approximate' ? 'approx' : 'near'}">${pr.tier === 'approximate' ? 'APPROXIMATE' : 'NEARBY POSE'}</span> BEM coefficients reused from a nearby pose: Δz ${fmt((pr.dz_m || 0) * 1000, 0)} mm, Δheel ${fmt(pr.dheel_deg, 2)}°, Δtrim ${fmt(pr.dtrim_deg, 2)}°${pr.boat_dx_m !== undefined ? `, boat Δx ${fmt(pr.boat_dx_m * 1000, 0)} mm` : ''}. ${pr.note || 'Mass and restoring matrices are exact for this pose; run 2 · Compute BEM for exact coefficients.'}</div>`; }
  h += '<h3>Natural periods (undamped, potential-flow added mass)</h3><table class="res"><tr><th>body / mode</th><th>T uncoupled [s] (all roots in band)</th></tr>' +
    Object.entries(nat.bodies).map(([bn, bb]) => ['heave', 'roll', 'pitch'].map((l) => `<tr><td>${bn} ${l}</td><td>${bb.uncoupled_roots[l].length ? bb.uncoupled_roots[l].map((w) => (2 * Math.PI / w).toFixed(2)).join(', ') : '<span class="nc">none in band</span>'}</td></tr>`).join('')).join('') +
    `<tr><td>coupled</td><td>${nat.coupled_roots.map((w, i) => (2 * Math.PI / w).toFixed(2) + ' (' + nat.coupled_labels[i] + ')').join(', ') || '<span class="nc">none</span>'}</td></tr></table>`;
  if (nat.gap_resonance_bands_rad_s.length) h += `<div class="flag">Potential-flow gap-resonance bands: ${nat.gap_resonance_bands_rad_s.map(([a, b]) => `T ${(2 * Math.PI / b).toFixed(2)}–${(2 * Math.PI / a).toFixed(2)} s`).join('; ')}. Coefficients are sharp and over-predicted there without viscous damping.</div>`;
  h += `<div class="small">${nat.note}</div>`;
  if (!rw.in_range) { h += `<div class="flag error">${rw.error}</div>`; $('waveResults').innerHTML = h; return; }
  h += `<h3>Regular wave H=${rw.H_m} m (A=${rw.amplitude_m} m), T=${rw.period_s} s, β=${rw.heading_deg}°</h3>` + kv([
    ['wavelength', fmt(rw.wavelength_m, 2), `m (k=${rw.wavenumber.toFixed(3)} 1/m)`], ['steepness H/L', fmt(rw.H_m / rw.wavelength_m, 4), ''], ['heading convention', rw.heading_convention, '']]);
  for (const [bn, bo] of Object.entries(rw.bodies)) {
    h += `<h3>${bn}</h3><table class="res"><tr><th>DOF</th><th>amplitude</th><th>RAO per m wave amp.</th><th>phase lag [deg]</th></tr>` +
      DOF.map((d, i) => `<tr><td>${d}</td><td>${i < 3 ? bo.amplitude[d].toFixed(4) + ' m' : bo.amplitude_deg[d].toFixed(3) + ' °'}</td><td>${i < 3 ? bo.rao_amplitude[d].toFixed(3) : (bo.rao_amplitude[d] * 180 / Math.PI).toFixed(2) + ' °/m'}</td><td>${bo.phase_lag_deg[d].toFixed(1)}</td></tr>`).join('') + '</table>';
    if (bo.points && Object.keys(bo.points).length) h += '<table class="res"><tr><th>point</th><th>vert. accel [m/s²]</th><th>[g]</th><th>horiz. accel [m/s²]</th><th>vert. disp [m]</th></tr>' +
      Object.entries(bo.points).map(([k, p]) => `<tr><td>${k}</td><td>${p.accel_vertical_amp_ms2.toFixed(3)}</td><td>${p.accel_vertical_amp_g.toFixed(3)}</td><td>${p.accel_horizontal_amp_ms2.toFixed(3)}</td><td>${p.disp_amp_m[2].toFixed(3)}</td></tr>`).join('') + '</table>';
  }
  if (rw.lines) {
    const n0 = (v, d = 0) => (v === undefined || v === null ? '<span class="nc">—</span>' : (+v).toFixed(d));
    h += '<h3>Mooring lines (linear, about the static tensions)</h3><table class="res"><tr><th>line</th><th>static T</th><th>dyn. amp.</th><th>min / max in cycle</th><th>stretch amp.</th><th>slack in cycle?</th></tr>' +
      rw.lines.map((l) => { const mean = l.tension_mean_N ?? l.pretension_N; const amp = l.tension_amp_N ?? l.dynamic_tension_amp_N; const mn = l.min_N ?? (mean !== undefined && amp !== undefined ? mean - amp : undefined); const mx = l.max_N ?? (mean !== undefined && amp !== undefined ? mean + amp : undefined); const sl = l.slack_in_cycle ?? l.goes_slack;
        return `<tr><td>${l.id}</td><td>${n0(mean)} N</td><td>${n0(amp)} N</td><td>${n0(mn)} / ${n0(mx)} N</td><td>${l.relative_stretch_amp_m !== undefined ? (l.relative_stretch_amp_m * 1000).toFixed(0) + ' mm' : '—'}</td><td>${sl ? '<b>yes</b>' : 'no'}</td></tr>`; }).join('') + '</table>';
  }
  if (rw.relative_motion) h += '<h3>Relative motion boat ↔ EXO (amplitudes / extremes in the cycle)</h3>' + kv(Object.entries(rw.relative_motion).filter(([k, v]) => typeof v !== 'object' || v === null).map(([k, v]) => [k.replace(/_/g, ' '), typeof v === 'number' ? v.toFixed(3) : fmt(v), '']));
  const du = r.damping_used || {}; const bodiesD = (du.EXO || du.BOAT) ? ['EXO', 'BOAT'].filter((b) => du[b]) : [''];
  h += '<h3>Viscous damping used</h3>' + bodiesD.map((b) => { const d = b ? du[b] : du; if (!d || !d.zeta) return ''; return `<div class="small mono">${b ? b + ': ' : ''}ζ heave/roll/pitch = ${[d.zeta.heave, d.zeta.roll, d.zeta.pitch].join(' / ')} ; abs. surge/sway/yaw = ${[d.absolute.surge, d.absolute.sway, d.absolute.yaw].join(' / ')}</div>`; }).join('') +
    `<div class="small mono">→ B_visc diag = ${(r.viscous_matrix_diag || []).map((x) => x.toFixed(0)).join(', ')}</div>`;
  h += '<table class="res"><tr><th>ζ roll</th><th>EXO roll amp [°]</th><th>heave amp [m]</th><th>max deck vert. accel [m/s²]</th></tr>' +
    r.roll_damping_sensitivity.map((s) => `<tr><td>${s.zeta_roll}</td><td>${s.roll_amp_deg.toFixed(3)}</td><td>${s.heave_amp_m.toFixed(4)}</td><td>${(s.deck_accel_vertical_max_amp_ms2 ?? NaN).toFixed(3)}</td></tr>`).join('') + '</table>';
  (rw.flags || []).forEach(([l, f]) => { h += `<div class="flag ${l === 'error' ? 'error' : l === 'info' ? 'info' : ''}">${f}</div>`; });
  const hm = r.hydro_meta;
  h += `<div class="small">BEM: Capytaine ${hm.capytaine}, ${hm.n_faces} panels (+${hm.n_lid_faces} lid)${hm.bodies ? ' [' + hm.bodies.map((b) => `${b.name} ${b.n_faces} @ ${b.panel_size_m} m`).join(', ') + ']' : ''}, ω ${hm.omega_range.map((x) => x.toFixed(2)).join('–')} rad/s (${hm.n_omega} points${hm.refinement ? '; ' + hm.refinement : ''}), excitation at the exact heading, depth ${hm.water_depth ?? '∞'} m, ρ ${hm.rho}. ${hm.conventions}</div>`;
  h += '<div class="row" style="margin-top:8px"><label>JONSWAP Hs [m]</label><input id="Hs" type="number" step="0.1" value="0.5"><label>Tp [s]</label><input id="Tp" type="number" step="0.5" value="4"><button id="irr">irregular (spectral)</button></div>';
  $('waveResults').innerHTML = h;
  $('irr').onclick = async () => {
    try {
      const o = await api('/api/irregular', { ...statePayload(), sea: { Hs_m: +$('Hs').value, Tp_s: +$('Tp').value, heading_deg: +$('heading').value } });
      let t = `<h3>Irregular sea Hs=${o.Hs_m} m, Tp=${o.Tp_s} s (γ=${o.gamma}), β=${o.heading_deg}°</h3>`;
      for (const [bn, bo] of Object.entries(o.bodies)) {
        t += `<table class="res"><tr><th>${bn}</th><th>σ (RMS)</th><th>significant single amp.</th><th>Tz [s]</th></tr>` +
          DOF.map((d, i) => `<tr><td>${d}</td><td>${i < 3 ? bo.response[d].sigma.toFixed(4) + ' m' : bo.response[d].sigma_deg.toFixed(3) + ' °'}</td><td>${i < 3 ? bo.response[d].sig_amplitude.toFixed(4) + ' m' : (2 * bo.response[d].sigma_deg).toFixed(3) + ' °'}</td><td>${bo.response[d].Tz_s ? bo.response[d].Tz_s.toFixed(2) : '-'}</td></tr>`).join('') + '</table>';
        if (Object.keys(bo.points).length) t += '<table class="res"><tr><th>point</th><th>σ vert. accel [m/s²]</th><th>[g]</th></tr>' + Object.entries(bo.points).map(([k, p]) => `<tr><td>${k}</td><td>${p.sigma_vertical_accel_ms2.toFixed(3)}</td><td>${p.sigma_vertical_accel_g.toFixed(3)}</td></tr>`).join('') + '</table>';
      }
      $('irregular').innerHTML = t + `<div class="small">${o.note} Spectrum energy inside the computed band: ${(o.energy_fraction_inside_band * 100).toFixed(1)} %.</div>`;
    } catch (e) { $('irregular').innerHTML = `<div class="flag error">${e.message}</div>`; }
  };
  const c = r.rao_curve; const col = ['#90caf9', '#ce93d8', '#80cbc4', '#ffcc80', '#ef9a9a', '#c5e1a5'];
  const series = [];
  for (const [bn, amp] of Object.entries(c.bodies)) DOF.forEach((d, i) => { if (i === 2 || i === 3 || i === 4) series.push({ x: c.period_s, y: i < 3 ? amp[d] : amp[d].map((v) => v * 180 / Math.PI), color: col[i], dash: bn === 'BOAT', label: `${bn} ${d}${i < 3 ? ' [m/m]' : ' [°/m]'}` }); });
  plot($('raoPlot'), series, { title: `RAO vs wave period, β=${c.heading_deg}° (heave m/m, roll & pitch °/m; dashed = boat)`, xlabel: 'T [s]', marker: { x: rw.period_s } });
  plot($('rollDampPlot'), Object.entries(r.roll_rao_vs_damping_deg_per_m).map(([z, y], i) => ({ x: c.period_s, y, color: col[i], label: `ζ roll = ${z}` })), { title: 'EXO roll RAO sensitivity to viscous roll damping [°/m]', xlabel: 'T [s]', marker: { x: rw.period_s } });
  if (r.time_series) {
    const ts = r.time_series;
    plot($('tsPlot'), [{ x: ts.t, y: ts.eta_com, color: '#4fc3f7', label: 'wave η at phase origin [m]' }, { x: ts.t, y: ts.x.map((v) => v[2]), color: '#80cbc4', label: 'EXO heave [m]' },
                       { x: ts.t, y: ts.x.map((v) => v[3] * 180 / Math.PI), color: '#ffcc80', label: 'EXO roll [°]' }, { x: ts.t, y: ts.x.map((v) => v[4] * 180 / Math.PI), color: '#ef9a9a', label: 'EXO pitch [°]' }],
         { title: 'Reconstructed linear time history (3 periods)', xlabel: 't [s]' });
  }
}

// ============================================================ compare
$('compare').onclick = async () => {
  document.querySelector('nav button[data-tab=compare]').click();
  $('compareOut').innerHTML = 'comparing…';
  try {
    const cur = { ...statePayload(), scenario_name: 'current (' + (S.scenarioName || S.base) + ')' };
    const body = { scenarios: [{ scenario: 'baseline_illustrative' }, { scenario: 'battery_relocated' }, { scenario: 'battery_float_frame' }, { scenario: 'occupants_symmetric' }, { scenario: 'occupants_asymmetric' }, { scenario: 'with_hydronaute' }, cur],
                   wave: S.hydroReady ? waveInput() : null, damping: dampingInput(), hydro_settings: hydroSettings() };
    const r = await api('/api/compare', body);
    const cols = [['name', 'scenario', (v) => v], ['total_listed_mass_kg', 'mass kg', (v) => fmt(v, 0)], ['com_x_m', 'COM x', fmt], ['com_y_m', 'COM y', fmt], ['com_z_m', 'COM z', fmt],
                  ['heel_deg', 'heel °', fmt], ['trim_deg', 'trim °', fmt], ['draft_max_m', 'draft', fmt], ['lower_deck_freeboard_min_m', 'deck fb', fmt], ['GM_transverse_m', 'GMt', (v) => fmt(v, 2)], ['GM_longitudinal_m', 'GMl', (v) => fmt(v, 2)],
                  ['heave_amp_m', 'heave amp m', fmt], ['roll_amp_deg', 'roll amp °', fmt], ['pitch_amp_deg', 'pitch amp °', fmt], ['deck_accel_vertical_max_amp_ms2', 'deck a_z m/s²', fmt]];
    let h = `<div class="flag">${r.label}</div><div class="small">EXO values; the boat row shows the EXO as moored to the boat.</div><table class="res"><tr>${cols.map((c) => `<th>${c[1]}</th>`).join('')}</tr>` +
      r.rows.map((row) => `<tr>${cols.map((c) => `<td>${c[2](row[c[0]])}</td>`).join('')}</tr>`).join('') + '</table>';
    const miss = Object.entries(r.hydro_status).filter(([, v]) => v !== 'computed');
    if (!S.hydroReady) h += '<div class="flag info">Wave columns need the BEM: run step 2 and 3 on the current configuration, then compare again. <button id="bemAll">compute BEM for the built-in scenarios</button> (sequential, 10–20 min).</div>';
    else if (miss.length) h += `<div class="flag">BEM not yet computed for: ${miss.map((m) => m[0]).join(', ')}. <button id="bemAll">compute them now</button> (sequential, several minutes).</div>`;
    h += '<div class="small">Every row: same float proxies, same assumed COMs. Differences between rows are meaningful only relative to each other, not as absolute predictions.</div>';
    $('compareOut').innerHTML = h;
    const bars = [['heel_deg', 'heel °'], ['trim_deg', 'trim °'], ['draft_max_m', 'draft m'], ['lower_deck_freeboard_min_m', 'deck fb m'], ['roll_amp_deg', 'roll amp °'], ['heave_amp_m', 'heave amp m'], ['deck_accel_vertical_max_amp_ms2', 'deck a_z']];
    barPlot($('comparePlot'), r.rows.map((x) => x.name), bars.map(([k, l]) => ({ label: l, values: r.rows.map((x) => x[k]) })));
    const b = $('bemAll'); if (b) b.onclick = computeBemForScenarios;
  } catch (e) { $('compareOut').innerHTML = `<div class="flag error">${e.message}</div>`; }
};
async function computeBemForScenarios() {
  for (const name of ['baseline_illustrative', 'battery_relocated', 'battery_float_frame', 'occupants_symmetric', 'occupants_asymmetric', 'with_hydronaute']) {
    const sc = await api(`/api/scenario/${name}`);
    setStatus(`BEM for ${name}…`);
    let r = await api('/api/hydro', { base: sc.base, overrides: sc.overrides, scenario_name: name, hydro_settings: hydroSettings(), wave: waveInput() });
    const jid = r.job_id;
    while (r.status !== 'done') { await new Promise((res) => setTimeout(res, 2000)); r = await api(`/api/job/${jid}`); if (r.status === 'error') { setStatus(`${name}: ${r.error}`, 'nc'); break; } }
  }
  setStatus('BEM done for built-in scenarios', 'ok'); S.hydroReady = true; $('compare').click();
}
$('export').onclick = async () => {
  try { const r = await api('/api/export', { ...statePayload(), name: S.scenarioName || S.base }); setStatus(`exported ${r.json}, ${r.csv} and ${r.md} — <a href="${r.download}" style="color:#4fc3f7">download JSON</a> · <a href="${r.download_md}" style="color:#4fc3f7">summary (markdown)</a>`, 'ok'); }
  catch (e) { setStatus('export failed: ' + e.message, 'nc'); }
};

// ============================================================ optimise (backend sweeps; ranked tables)
async function runOptimise(target) {
  document.querySelector('nav button[data-tab=optimise]').click();
  if (!S.still || S.still.status.equilibrium !== 'solved') { $('optStatus').innerHTML = '<span class="nc">compute a solved still-water equilibrium first</span>'; return; }
  $('optStatus').textContent = `optimising ${target}… submitting`; $('optOut').innerHTML = '';
  try {
    let r = await api('/api/optimise', { ...statePayload(), target });
    const t0 = Date.now(); const jid = r.job_id;
    while (r.status !== 'done') {
      if (r.status === 'error') throw new Error(r.error);
      await new Promise((res) => setTimeout(res, 1500));
      r = await api(`/api/job/${jid}`);
      $('optStatus').textContent = `optimising ${target}: ${r.status}${r.progress !== undefined ? ` ${(r.progress * 100).toFixed(0)} %` : ''}, ${((Date.now() - t0) / 1000).toFixed(0)} s`;
    }
    renderOptimise(r.result || r, target);
    $('optStatus').textContent = `${target}: done in ${((Date.now() - t0) / 1000).toFixed(0)} s`;
  } catch (e) {
    const pending = /404|500|not found|unknown|optimise/i.test(e.message);
    $('optStatus').innerHTML = `<span class="nc">${pending ? 'optimisation backend pending: ' : ''}${e.message}</span>`;
  }
}
function renderOptimise(res, target) {
  const rows = res.rows || [];
  if (!rows.length) { $('optOut').innerHTML = `<div class="flag">${res.label || ''} no candidates returned</div>`; return; }
  // curated columns per target (label, accessor, decimals); the full rows stay in the result for export
  const num = (v, d) => (v === null || v === undefined || Number.isNaN(v)) ? '—' : (typeof v === 'number' ? v.toFixed(d) : v);
  const list = (v) => (Array.isArray(v) ? (v.length ? v.join(', ') : 'none') : (v ?? '—'));
  const yn = (v) => (v === true ? 'yes' : v === false ? 'NO' : '—');
  const zone = (z) => (z === 'float_frame' ? 'float frame' : z === 'rear_deck' ? 'rear deck' : (z ?? '—'));
  const COLS = target === 'battery' ? [
    ['zone', (r) => zone(r.candidate.zone)],
    ['x [m]', (r) => num(r.candidate.x_m, 2)], ['y stbd [m]', (r) => num(r.candidate.y_stbd_m, 2)], ['y port [m]', (r) => num(r.candidate.y_port_m, 2)],
    ['trim [°]', (r) => num(r.trim_deg, 2)], ['heel [°]', (r) => num(r.heel_deg, 2)], ['deck fb min [m]', (r) => num(r.deck_freeboard_min_m, 3)],
    ['GM_T [m]', (r) => num(r.GM_T_m, 1)], ['roll amp [°]', (r) => num(r.roll_amp_deg, 2)], ['pitch amp [°]', (r) => num(r.pitch_amp_deg, 2)],
    ['heave amp [m]', (r) => num(r.heave_amp_m, 3)], ['deck a_z [m/s²]', (r) => num(r.deck_accel_max_ms2, 2)], ['line min [N]', (r) => num(r.line_min_N, 0)],
    ['slack at rest', (r) => list(r.slack_lines)], ['score', (r) => num(r.score, 2)]] : [
    ['arrangement', (r) => r.candidate.title || r.candidate.id], ['can push', (r) => yn(r.can_push)], ['can tow', (r) => yn(r.can_tow)],
    ['rest min/max [N]', (r) => `${num(r.line_min_N, 0)} / ${num(r.line_max_N, 0)}`], ['slack at rest', (r) => list(r.slack_lines)],
    ['push max [N]', (r) => num(r.push_line_max_N, 0)], ['push boat shift [m]', (r) => num(r.push_boat_shift_m, 2)], ['tow max [N]', (r) => num(r.tow_line_max_N, 0)],
    ['wave slack', (r) => list(r.lines_slack_in_cycle)], ['min rel. clearance [m]', (r) => num(r.min_relative_clearance_m, 3)],
    ['EXO roll amp [°]', (r) => num(r.roll_amp_deg, 2)], ['boat roll amp [°]', (r) => num(r.boat_roll_amp_deg, 2)], ['score', (r) => num(r.score, 2)]];
  const top = rows.filter((r) => r.feasible !== false).sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9)).slice(0, 12);
  const nInf = rows.length - rows.filter((r) => r.feasible !== false).length;
  let h = `<div class="flag">${res.label || S.still.label}</div><h3>${target === 'battery' ? 'Battery position' : 'Line arrangement'} — best ${top.length} of ${rows.length} candidates${nInf ? ` (${nInf} without a static equilibrium)` : ''}</h3>`;
  h += `<table class="res opt"><tr><th>#</th>${COLS.map(([c]) => `<th>${c}</th>`).join('')}</tr>` +
    top.map((row) => `<tr class="${row.rank === 1 ? 'best' : ''}"><td>${row.rank ?? ''}</td>${COLS.map(([, f]) => `<td>${f(row)}</td>`).join('')}</tr>`).join('') + '</table>';
  if (res.best) {
    const c = res.best.candidate || {};
    const desc = target === 'battery' ? `batteries on the ${zone(c.zone)} at x ${num(c.x_m, 2)} m, |y| stbd ${num(c.y_stbd_m, 2)} / port ${num(c.y_port_m, 2)} m` : (c.title || c.id || '');
    h += `<div class="row"><button id="applyBest" class="primary">Apply best</button><span class="small">${desc}</span></div>`;
  }
  if (target === 'battery' && res.zones) {
    const zs = Object.entries(res.zones).map(([z, v]) => `<b>${zone(z)}</b>: least trim ${num(v.trim_deg, 2)}° at x ${num(v.x_min_trim_m, 2)} m (deck freeboard ${num(v.deck_freeboard_min_m, 2)} m, best rank ${v.best_rank})`);
    h += `<div class="small">${zs.join(' · ')}${res.x_zero_trim_m != null ? ` · <b>zero trim at x ≈ ${num(res.x_zero_trim_m, 2)} m</b> on the |y| 2.05 m column` : ''}</div>`;
  }
  (res.notes || []).forEach((n) => { h += `<div class="small">${n}</div>`; });
  if (res.hydro_note) h += `<div class="flag info">${res.hydro_note}</div>`;
  $('optOut').innerHTML = h;
  const ab = $('applyBest');
  if (ab) ab.onclick = () => {
    const ov = res.best.overrides_to_apply || {};
    if (ov.components) for (const [id, f] of Object.entries(ov.components)) S.overrides.components[id] = { ...(S.overrides.components[id] || {}), ...f };
    if (ov.host_boat) { S.overrides.host_boat = S.overrides.host_boat || { people: [] }; Object.assign(S.overrides.host_boat, JSON.parse(JSON.stringify(ov.host_boat))); }
    if (ov.people) S.overrides.people = JSON.parse(JSON.stringify(ov.people));
    renderComponents(); renderLines(); placeHandles(); placeLineHandles(); evaluate();
    setStatus(`best ${target} candidate applied — exact solve running`, 'muted');
  };
}
$('optBattery').onclick = () => runOptimise('battery');
$('optLines').onclick = () => runOptimise('lines');

// ============================================================ notes tab
function renderNotes() {
  const c = S.config; const five = S.meta.five_missing;
  let h = `<h3>Five most consequential missing measurements</h3><ol>${five.map((f) => `<li><b>${f.item}</b><div class="small">${f.why}</div></li>`).join('')}</ol>`;
  h += `<h3>All missing inputs (baseline keeps them null)</h3><ul>${c.missing_inputs.map((x) => `<li>${x}</li>`).join('')}</ul>`;
  h += `<h3>Drawing dimensions (preserved as transcribed)</h3>` + kv([['frame length (section chain)', c.drawing_dimensions.frame_length_m, 'm'], ['drawing overall length', c.drawing_dimensions.drawing_overall_length_m, 'm — 30 mm unresolved'], ['width', c.drawing_dimensions.frame_width_m, 'm'], ['top frame / observation surface', `${c.drawing_dimensions.top_frame_z_m} / ${c.drawing_dimensions.observation_surface_z_m}`, 'm above deck datum'], ['end-view 3200 vs top-view 3353', '3.200 / 3.353', 'm — not both consistent with the float proxy spacing']]);
  if (c.visual_overrides) h += `<h3>Visual corrections</h3><div class="small">Hidden sub-parts: <code>${c.visual_overrides.hidden_subparts.join(', ')}</code> — ${c.visual_overrides.reason} (${c.visual_overrides.mass_effect}; ${c.visual_overrides.buoyancy_effect})</div>`;
  if (c.host_boat_berth) h += `<div class="small">Host-boat berth: clear width between float proxies ${c.host_boat_berth.clear_width_between_float_proxies_m} m — ${c.host_boat_berth.note}</div>`;
  if (c.host_boat) h += `<h3>Host boat</h3><ul>${c.host_boat.notes.map((n) => `<li>${n}</li>`).join('')}<li>${c.host_boat.line_defaults.source}</li><li>Hull: ${c.host_boat.buoyant_surface.source}</li></ul>`;
  h += `<h3>Model limits</h3><ul><li>Linear potential-flow model about the still-water equilibrium: no capsize limit, no breaking waves, no slamming, no green water, no structural strength, no joint loads, no deck capacity.</li><li>Six floats + frame = one rigid body (${c.rigid_connection_assumption}); the boat is a second rigid body; lines are linear springs (no slack/snatch).</li><li>Buoyancy only from the six float proxies and the proxy boat hull (visual envelopes, unverified).</li><li>No safe occupancy limit, operating sea state or construction approval is given or implied.</li></ul>`;
  if (c.propulsion) {
    const u = c.propulsion.units, rs = c.propulsion.resistance;
    h += `<h3>Propulsion / tow model (quasi-static)</h3><ul>${Object.entries(u).map(([k, v]) => `<li><b>${k}</b>: ${v.title} — bollard ${v.bollard_thrust_N === null ? 'null' : fmt(v.bollard_thrust_N, 0) + ' N'} (${v.thrust_source}); points ${JSON.stringify(v.thrust_points_m)} (${v.position_source})</li>`).join('')}
      <li>${c.propulsion.thrust_model.note}</li><li>EXO resistance: ${rs.exo.note} (k = ${rs.exo.form_factor_k}, C_d = ${rs.exo.pressure_drag_cd})</li><li>Boat resistance: ${rs.boat.note} (k = ${rs.boat.form_factor_k}, appendages ×${rs.boat.appendage_factor}, C_R = ${rs.boat.residuary_c_at_fr02}·(Fr/0.2)^${rs.boat.residuary_exponent})</li><li>${c.propulsion.label}</li></ul>`;
  }
  h += `<h3>How the BEM cache is reused</h3><div class="small">The BEM is computed about each body's CAD origin and moved exactly to the current centre of gravity, so moving a mass that leaves the pose unchanged is an exact hit. Otherwise the coefficients of a <b>nearby pose</b> (within ${S.meta.pose_tolerance ? S.meta.pose_tolerance.angle_rad : 0.05} rad, ${S.meta.pose_tolerance ? S.meta.pose_tolerance.z_m : 0.05} m) are reused and labelled; beyond that an <b>APPROXIMATE PREVIEW</b> tier (0.17 rad, 0.30 m) keeps the motion following large load changes — the header chip and the wave panel say which tier is in use; 2 · Compute BEM always computes the exact pose in a background worker (progress panel in the 3D view).</div>`;
  h += `<h3>Mooring lines in waves</h3><div class="small">The wave model uses linear springs about the static tension; a line whose dynamic tension amplitude exceeds its static tension would go slack. The <b>line snatch check</b> (Waves tab) integrates the motion with tension-only lines and reports the peak tensions and slack fractions: use those peaks for rope sizing, not the linear amplitudes.</div>`;
  h += '<div class="small">See ASSUMPTIONS.md, AUDIT.md and CHANGELOG.md in the project for the full register.</div>';
  $('tab-notes').innerHTML = h;
}
document.querySelectorAll('nav button').forEach((b) => b.onclick = () => { document.querySelectorAll('nav button').forEach((x) => x.classList.remove('on')); b.classList.add('on'); document.querySelectorAll('.tab').forEach((t) => t.classList.toggle('on', t.id === 'tab-' + b.dataset.tab)); });

// ============================================================ plots (hand-rolled)
function plot(cv, series, o = {}) {
  const ctx = cv.getContext('2d'); const W = cv.width, H = cv.height; ctx.clearRect(0, 0, W, H);
  ctx.fillStyle = '#0d151d'; ctx.fillRect(0, 0, W, H);
  const L = 46, R = 10, T = 22, B = 30;
  const xs = series.flatMap((s) => s.x), ys = series.flatMap((s) => s.y).filter((v) => Number.isFinite(v));
  let x0 = Math.min(...xs), x1 = Math.max(...xs), y0 = Math.min(0, ...ys), y1 = Math.max(...ys);
  if (y1 === y0) y1 = y0 + 1;
  const X = (x) => L + (x - x0) / (x1 - x0) * (W - L - R), Y = (y) => T + (1 - (y - y0) / (y1 - y0)) * (H - T - B);
  ctx.strokeStyle = '#243242'; ctx.fillStyle = '#8fa3b8'; ctx.font = '10px system-ui'; ctx.lineWidth = 1;
  for (let i = 0; i <= 5; i++) { const y = y0 + (y1 - y0) * i / 5; ctx.beginPath(); ctx.moveTo(L, Y(y)); ctx.lineTo(W - R, Y(y)); ctx.stroke(); ctx.fillText(y.toPrecision(3), 2, Y(y) + 3); }
  for (let i = 0; i <= 6; i++) { const x = x0 + (x1 - x0) * i / 6; ctx.beginPath(); ctx.moveTo(X(x), T); ctx.lineTo(X(x), H - B); ctx.stroke(); ctx.fillText(x.toPrecision(3), X(x) - 10, H - B + 12); }
  if (o.xlabel) ctx.fillText(o.xlabel, W / 2 - 10, H - 4);
  if (o.title) { ctx.fillStyle = '#dce6f0'; ctx.fillText(o.title, L, 12); }
  series.forEach((s, i) => {
    ctx.strokeStyle = s.color; ctx.lineWidth = 1.5; ctx.setLineDash(s.dash ? [5, 3] : []); ctx.beginPath();
    s.x.forEach((x, j) => { const y = s.y[j]; if (!Number.isFinite(y)) return; if (j === 0) ctx.moveTo(X(x), Y(y)); else ctx.lineTo(X(x), Y(y)); }); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = s.color; ctx.fillText(s.label, W - R - 120, T + 12 + 11 * i);
  });
  if (o.marker) { ctx.strokeStyle = '#ffb74d'; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(X(o.marker.x), T); ctx.lineTo(X(o.marker.x), H - B); ctx.stroke(); ctx.setLineDash([]); }
}
function barPlot(cv, names, groups) {
  const ctx = cv.getContext('2d'); const W = cv.width, H = cv.height; ctx.clearRect(0, 0, W, H); ctx.fillStyle = '#0d151d'; ctx.fillRect(0, 0, W, H);
  const n = groups.length, m = names.length; const gw = (W - 40) / n; const col = ['#90caf9', '#ce93d8', '#80cbc4', '#ffcc80', '#ef9a9a', '#c5e1a5', '#b0bec5'];
  ctx.font = '10px system-ui';
  groups.forEach((g, gi) => {
    const vals = g.values.map((v) => (v === null || v === undefined) ? NaN : v); const mx = Math.max(1e-9, ...vals.map((v) => Math.abs(v)).filter(Number.isFinite));
    const x0 = 20 + gi * gw; const bw = (gw - 10) / m;
    ctx.fillStyle = '#8fa3b8'; ctx.fillText(g.label, x0, 12);
    vals.forEach((v, i) => {
      const h = Number.isFinite(v) ? (v / mx) * (H - 70) : 0; const y = H - 40;
      ctx.fillStyle = col[i % col.length]; ctx.fillRect(x0 + i * bw, h >= 0 ? y - h : y, bw - 2, Math.abs(h));
      if (!Number.isFinite(v)) { ctx.fillStyle = '#ffb74d'; ctx.fillText('n/c', x0 + i * bw, y - 4); }
      else { ctx.fillStyle = '#dce6f0'; ctx.save(); ctx.translate(x0 + i * bw + 3, y + 4); ctx.rotate(Math.PI / 2); ctx.fillText(v.toPrecision(3), 0, 0); ctx.restore(); }
    });
  });
  names.forEach((nm, i) => { ctx.fillStyle = col[i % col.length]; ctx.fillRect(20 + i * 90, H - 10, 8, 8); ctx.fillStyle = '#8fa3b8'; ctx.fillText(nm.slice(0, 15), 32 + i * 90, H - 2); });
}

// ============================================================ 3D
const viewer = $('viewer');
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setPixelRatio(Math.min(2, window.devicePixelRatio)); viewer.appendChild(renderer.domElement);
const scene = new THREE.Scene(); scene.background = new THREE.Color(0x0f1720);
const camera = new THREE.PerspectiveCamera(45, 1, 0.05, 500);
const orbit = new OrbitControls(camera, renderer.domElement);
scene.add(new THREE.HemisphereLight(0xdfe9f3, 0x30404a, 1.1));
const sun = new THREE.DirectionalLight(0xffffff, 1.2); sun.position.set(6, 10, 4); scene.add(sun);
// Physics frame: world W is Z-up (EXO CAD axes, EXO CAD origin horizontally, waterline z=0). Exactly ONE conversion to glTF Y-up
// is applied here: (x,y,z) -> (x,z,-y). Both GLB roots carry the same -90 deg X rotation; it is removed from the nodes and applied once here.
const physics = new THREE.Group(); physics.quaternion.set(-Math.SQRT1_2, 0, 0, Math.SQRT1_2); scene.add(physics);
physics.add(new THREE.AxesHelper(1.0));
// bodies: outer (COM world position + wave motion) > inner (equilibrium attitude R_world) > model (offset -G, holds the GLB, handles, people)
const bodies3d = {};
function makeBody(name) {
  const outer = new THREE.Group(), inner = new THREE.Group(), model = new THREE.Group();
  physics.add(outer); outer.add(inner); inner.add(model);
  const com = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 16), new THREE.MeshBasicMaterial({ color: 0xef5350 }));
  const cob = new THREE.Mesh(new THREE.SphereGeometry(0.09, 16, 16), new THREE.MeshBasicMaterial({ color: 0x4fc3f7 }));
  const people = new THREE.Group(); model.add(com, cob, people);
  outer.visible = false;
  bodies3d[name] = { name, outer, inner, model, com, cob, people, glb: null, handles: {}, peopleHandles: {}, lineEnds: {}, nodes: {}, lineAnchors: [] };
  return bodies3d[name];
}
makeBody('EXO'); makeBody('BOAT');
// water
const WATER = 40, NW = 80;
const waterGeo = new THREE.PlaneGeometry(WATER, WATER, NW, NW); waterGeo.translate(3, 0, 0);
const water = new THREE.Mesh(waterGeo, new THREE.MeshPhongMaterial({ color: 0x1565c0, transparent: true, opacity: 0.55, side: THREE.DoubleSide, shininess: 80 }));
physics.add(water);
const wl = new THREE.GridHelper(WATER, 40, 0x4fc3f7, 0x1d3a52); wl.rotation.x = Math.PI / 2; wl.position.set(3, 0, 0.001); physics.add(wl);
// mooring lines
const linesGroup = new THREE.Group(); physics.add(linesGroup);
const tctl = new TransformControls(camera, renderer.domElement); tctl.setSpace('local'); tctl.setSize(0.7);
scene.add(tctl.getHelper());
tctl.addEventListener('dragging-changed', (e) => { orbit.enabled = !e.value; if (!e.value && S.selected) commitHandle(S.selected); });
let dragThrottle = 0;
tctl.addEventListener('objectChange', () => {
  if (!S.selected) return;
  const sel = findHandle(S.selected); if (!sel) return;
  if (sel.kind === 'person') clampPerson(S.selected);
  if (sel.kind === 'lineEnd') { $('poseInfo').textContent = `${sel.lineId} ${sel.end} end: ${['x', 'y', 'z'].map((k) => k + ' ' + sel.obj.position[k].toFixed(2)).join(', ')} m (${sel.body.name} frame) — exact coupled solve on release`; return; }
  firstOrderPreview();
  const now = performance.now();
  if (now - dragThrottle > 400) { dragThrottle = now; commitHandle(S.selected, true); }
});
function findHandle(id) {
  if (!id) return null;
  if (id.startsWith('LINE:')) {
    const [, lineId, end] = id.split(':'); const b = bodies3d[end === 'exo' ? 'EXO' : 'BOAT']; const obj = b.lineEnds[lineId];
    return obj ? { kind: 'lineEnd', body: b, obj, lineId, end } : null;
  }
  for (const b of Object.values(bodies3d)) { if (b.handles[id]) return { kind: 'component', body: b, obj: b.handles[id] }; if (b.peopleHandles[id]) return { kind: 'person', body: b, obj: b.peopleHandles[id] }; }
  return null;
}
function personById(id) { return allPeople().find((x) => x.p.id === id); }
function commitHandle(id, keepDragging = false) {
  const sel = findHandle(id); if (!sel) return;
  if (sel.kind === 'component') {
    const h = sel.obj; S.overrides.components[id] = { ...(S.overrides.components[id] || {}), com_m: [+h.position.x.toFixed(4), +h.position.y.toFixed(4), +h.position.z.toFixed(4)] };
    if (!keepDragging) renderComponents();
  } else if (sel.kind === 'lineEnd') {
    if (keepDragging) return;                     // lines: exact coupled solve on release only
    const list = linesList(); const l = list.find((x) => x.id === sel.lineId); if (!l) return;
    const h = sel.obj; l[sel.end === 'exo' ? 'exo_point_m' : 'boat_point_m'] = [+h.position.x.toFixed(3), +h.position.y.toFixed(3), +h.position.z.toFixed(3)];
    S.overrides.host_boat = S.overrides.host_boat || { people: [] }; S.overrides.host_boat.lines = list; renderLines();
  } else {
    const h = sel.obj; const { p } = personById(id);
    p.x_m = +h.position.x.toFixed(3); p.y_m = +h.position.y.toFixed(3);
    if (!keepDragging) renderPeople();
  }
  evaluate(keepDragging);
}
function clampPerson(id) {
  const sel = findHandle(id); const { p } = personById(id); const surf = allSurfaces()[p.surface]; const h = sel.obj;
  h.position.x = Math.min(Math.max(h.position.x, surf.x_range_m[0]), surf.x_range_m[1]);
  h.position.y = Math.min(Math.max(h.position.y, surf.y_range_m[0]), surf.y_range_m[1]);
  h.position.z = surf.z_m;
}
// First-order preview while dragging: dq = C^-1 dW with C the restoring matrix of the body from the last exact solve.
// dW = wrench change (about the COM) from moving mass m by r (world): dMx = -m g r_y, dMy = +m g r_x.
function firstOrderPreview() {
  const r = S.still; if (!r || !S.selected) return;
  const sel = findHandle(S.selected); if (!sel) return;
  if (sel.kind === 'lineEnd') return;
  const isBoat = sel.body.name === 'BOAT';
  const src = isBoat ? (r.bodies && r.bodies.boat) : r;
  if (!src || !src.stability_static || !src.equilibrium || !src.equilibrium.feasible) return;
  const C = src.stability_static.C_hydrostatic_NmPerUnit; const g = r.equilibrium.g; const pose = (isBoat ? r.bodies.boat : r.bodies.exo).pose;
  let m, dBody;
  if (sel.kind === 'component') {
    const c = effectiveComponents().find((x) => x.id === S.selected); m = c.mass_kg; const ref = c.com_m || c.preview_anchor_m; dBody = [sel.obj.position.x - ref[0], sel.obj.position.y - ref[1], sel.obj.position.z - ref[2]];
  } else { const { p } = personById(S.selected); m = p.mass_kg; dBody = [sel.obj.position.x - p.x_m, sel.obj.position.y - p.y_m, 0]; }
  const R = pose.R_world; const rw = [0, 1, 2].map((i) => R[i][0] * dBody[0] + R[i][1] * dBody[1] + R[i][2] * dBody[2]);
  const dq = solve3(C, [0, -m * g * rw[1], m * g * rw[0]]); if (!dq) return;
  const ex = staticExag();      // display only: the preview delta is drawn exaggerated like the static Δ
  const b3 = sel.body; b3.outer.position.set(pose.com_world[0], pose.com_world[1], pose.com_world[2] + dq[0] * ex); b3.outer.rotation.set(dq[1] * ex, dq[2] * ex, 0, 'XYZ');
  $('poseInfo').textContent = `preview (1st order, exact solve on release): ${b3.name} heel ≈ ${(src.equilibrium.heel_deg + dq[1] * 180 / Math.PI).toFixed(2)}°, trim ≈ ${(src.equilibrium.trim_deg + dq[2] * 180 / Math.PI).toFixed(2)}°, Δz ≈ ${(dq[0] * 1000).toFixed(0)} mm — ${S.selected}${ex > 1 ? ` · static Δ exaggerated ×${ex} (display only)` : ''}`;
}
function staticExag() { return Math.max(1, +$('exag').value || 1); }
function solve3(A, b) {
  const [[a, b1, c], [d, e, f], [g, h, i]] = A;
  const det = a * (e * i - f * h) - b1 * (d * i - f * g) + c * (d * h - e * g);
  if (Math.abs(det) < 1e-12) return null;
  const inv = [[(e * i - f * h) / det, (c * h - b1 * i) / det, (b1 * f - c * e) / det], [(f * g - d * i) / det, (a * i - c * g) / det, (c * d - a * f) / det], [(d * h - e * g) / det, (b1 * g - a * h) / det, (a * e - b1 * d) / det]];
  return inv.map((row) => row[0] * b[0] + row[1] * b[1] + row[2] * b[2]);
}
function loadGlb(url, bodyName, after) {
  new GLTFLoader().load(url, (g) => {
    const root = g.scene.children[0];
    const expected = new THREE.Quaternion(-Math.SQRT1_2, 0, 0, Math.SQRT1_2);
    console.log(`${bodyName} GLB root rotation = -90deg about X:`, Math.abs(root.quaternion.dot(expected)) > 0.9999, root.name);
    root.quaternion.identity(); root.updateMatrix();
    const b = bodies3d[bodyName]; b.glb = root; b.model.add(root);
    root.traverse((o) => { if (o.userData && o.userData.component_id) b.nodes[o.userData.component_id] = o; if (o.isMesh) { o.material = o.material.clone(); o.material.side = THREE.DoubleSide; } });
    after && after(b);
  }, undefined, (e) => console.error(`${bodyName} GLB load failed`, e));
}
loadGlb('/reference.glb', 'EXO', () => { GP.glb++; renderGlobalProgress(); applyVisualOverrides(); placeHandles(); placePeople(); if (S.still) applyPose(S.still); });
loadGlb('/boat.glb', 'BOAT', () => { GP.glb++; renderGlobalProgress(); placePeople(); placeLineHandles(); if (S.still) applyPose(S.still); });
function hiddenList() {
  const ov = S.overrides.visual_overrides;
  return (ov && ov.hidden_subparts) || ((S.config.visual_overrides || {}).hidden_subparts || []);
}
function applyVisualOverrides() {
  const b = bodies3d.EXO; if (!b.glb || !S.config) return;
  const hidden = new Set(hiddenList()); let n = 0;
  b.glb.traverse((o) => {
    if (o.isMesh && o.userData.component_id === undefined) {
      const nm = o.userData.name || o.name; const sec = o.parent && o.parent.userData && o.parent.userData.component_id;
      const h = hidden.has(nm) || (sec && hidden.has(`${sec}/${nm}`)); o.visible = !h; if (h) n++;
    }
  });
  if ($('hidden').value !== [...hidden].join(', ')) $('hidden').value = [...hidden].join(', ');
  console.log(`hidden ${n} sub-part meshes:`, [...hidden].join(', '));
}
$('hidden').addEventListener('change', () => {
  S.overrides.visual_overrides = { hidden_subparts: $('hidden').value.split(',').map((x) => x.trim()).filter(Boolean) };
  applyVisualOverrides();
});
function placeHandles() {
  const b = bodies3d.EXO; if (!b.glb || !S.config) return;
  const eff = effectiveComponents();
  for (const id of MOVABLE) {
    const node = b.nodes[id]; const c = eff.find((x) => x.id === id); if (!node || !c) continue;
    const anchor = c.preview_anchor_m; const pos = c.com_m || anchor;
    if (!b.handles[id]) { const h = new THREE.Group(); h.name = id; b.model.add(h); h.add(node); node.position.set(-anchor[0], -anchor[1], -anchor[2]); b.handles[id] = h; }
    b.handles[id].position.set(pos[0], pos[1], pos[2]);
  }
}
function selectComponent(id) {
  S.selected = (S.selected === id) ? null : id; renderComponents(); renderPeople(); renderLines();
  const sel = S.selected && findHandle(S.selected);
  if (sel && S.config.mode !== 'baseline') { tctl.attach(sel.obj); tctl.showZ = sel.kind !== 'person'; } else tctl.detach();
  if (S.selected && !sel) $('poseInfo').textContent = `${S.selected}: numeric COM edit only (no 3D handle)`;
  if (sel && sel.kind === 'lineEnd') $('poseInfo').textContent = `${sel.lineId}: ${sel.end} end selected — drag the gizmo (axes = ${sel.body.name} body frame); the other end is the small sphere on the ${sel.end === 'exo' ? 'boat' : 'EXO'}`;
}
renderer.domElement.addEventListener('pointerdown', (e) => {
  if (tctl.dragging || e.button !== 0) return; const r = renderer.domElement.getBoundingClientRect();
  const m = new THREE.Vector2(((e.clientX - r.left) / r.width) * 2 - 1, -((e.clientY - r.top) / r.height) * 2 + 1);
  const rc = new THREE.Raycaster(); rc.setFromCamera(m, camera);
  const targets = Object.values(bodies3d).flatMap((b) => [...Object.values(b.handles), ...Object.values(b.peopleHandles), ...Object.values(b.lineEnds)]);
  const hits = rc.intersectObjects(targets, true);
  if (hits.length) { let o = hits[0].object; while (o && !findHandle(o.name)) o = o.parent; if (o && S.selected !== o.name) selectComponent(o.name); }
});
function placePeople() {
  const selIsPerson = S.selected && findHandle(S.selected) && findHandle(S.selected).kind === 'person'; if (selIsPerson) tctl.detach();
  for (const b of Object.values(bodies3d)) { b.people.clear(); b.peopleHandles = {}; }
  if (!S.config) return;
  const surfs = allSurfaces();
  for (const { p } of allPeople()) {
    const surf = surfs[p.surface]; if (!surf) continue;
    const b = bodies3d[BODY_OF_SURFACE(p.surface)];
    const hgt = { standing: 1.75, seated_on_chair: 1.3, seated_on_deck: 0.9 }[p.posture] || 1.5;
    const h = new THREE.Group(); h.name = p.id; h.position.set(p.x_m, p.y_m, surf.z_m);
    const body = new THREE.Mesh(new THREE.CapsuleGeometry(0.17, hgt - 0.34, 4, 10), new THREE.MeshPhongMaterial({ color: 0x81c784, transparent: true, opacity: 0.85 }));
    body.rotation.x = Math.PI / 2; body.position.set(0, 0, hgt / 2);
    const com = new THREE.Mesh(new THREE.SphereGeometry(0.06, 10, 10), new THREE.MeshBasicMaterial({ color: 0xffeb3b })); com.position.set(0, 0, p.com_height_m ?? POSTURE_H[p.posture]);
    h.add(body, com); b.people.add(h); b.peopleHandles[p.id] = h;
  }
  if (selIsPerson) { const sel = findHandle(S.selected); if (sel && S.config.mode !== 'baseline') { tctl.attach(sel.obj); tctl.showZ = false; } }
}
// ---- mooring-line end handles: persistent spheres in each body frame (draggable), one cylinder per line in the physics frame
const LINE_COL = { taut: 0xffeb3b, slack: 0xef5350, unknown: 0x90a4ae };
function placeLineHandles() {
  const E = bodies3d.EXO, B = bodies3d.BOAT;
  const selId = S.selected && S.selected.startsWith('LINE:') ? S.selected : null;
  for (const b of [E, B]) { for (const o of Object.values(b.lineEnds)) o.parent && o.parent.remove(o); b.lineEnds = {}; }
  linesGroup.clear(); E.lineAnchors = [];
  const eb = S.config && effectiveBoat(); if (!eb || eb.included === false) { if (selId) { S.selected = null; tctl.detach(); } return; }
  for (const ln of eb.lines) {
    const mk = (body, end, pt) => {
      const h = new THREE.Mesh(new THREE.SphereGeometry(0.07, 12, 12), new THREE.MeshBasicMaterial({ color: LINE_COL.unknown }));
      h.name = `LINE:${ln.id}:${end}`; h.position.set(pt[0], pt[1], pt[2]); body.model.add(h); body.lineEnds[ln.id] = h; return h;
    };
    const a = mk(E, 'exo', ln.exo_point_m), b = mk(B, 'boat', ln.boat_point_m);
    const cyl = new THREE.Mesh(new THREE.CylinderGeometry(1, 1, 1, 8, 1, true), new THREE.MeshBasicMaterial({ color: LINE_COL.unknown }));
    linesGroup.add(cyl);
    E.lineAnchors.push({ id: ln.id, a, b, cyl, r: 0.012 });
  }
  colourLines();
  if (selId) { const sel = findHandle(selId); if (sel) tctl.attach(sel.obj); else { S.selected = null; tctl.detach(); } }
}
function colourLines() {
  const rs = (S.still && S.still.lines) || [];
  const tmax = Math.max(1, ...rs.map((l) => l.tension_N || 0));
  for (const an of bodies3d.EXO.lineAnchors) {
    const r = rs.find((l) => l.id === an.id);
    const col = r ? (r.slack ? LINE_COL.slack : LINE_COL.taut) : LINE_COL.unknown;
    an.cyl.material.color.setHex(col); an.a.material.color.setHex(col); an.b.material.color.setHex(col);
    an.r = r && !r.slack ? 0.012 + 0.03 * (r.tension_N / tmax) : 0.008;
  }
}
// ---- thrust arrows (quasi-static propulsion result)
const thrustGroup = new THREE.Group(); physics.add(thrustGroup);
function placeThrust(r) {
  thrustGroup.clear();
  const p = r && r.propulsion; if (!p || !p.thrust_points_world || !(p.thrust_total_N > 0)) return;
  const dir = p.thrust_direction_world || [1, 0, 0];
  const n = p.thrust_points_world.length; const len = 0.4 + 1.2 * Math.min(1, p.thrust_total_N / 1500);
  for (const pt of p.thrust_points_world) {
    const arrow = new THREE.ArrowHelper(new THREE.Vector3(dir[0], dir[1], dir[2]).normalize(), new THREE.Vector3(pt[0], pt[1], pt[2]).addScaledVector(new THREE.Vector3(dir[0], dir[1], dir[2]).normalize(), -len), len, 0xff7043, 0.25, 0.12);
    thrustGroup.add(arrow);
  }
  thrustGroup.userData.note = `${n} thrust point(s), ${p.thrust_total_N.toFixed(0)} N total`;
}
// ---- static pose with the optional display-only exaggeration of the change relative to the reference pose
const _qRef = new THREE.Quaternion(), _qCur = new THREE.Quaternion(), _qDel = new THREE.Quaternion(), _mRef = new THREE.Matrix4(), _axis = new THREE.Vector3();
function matrixOf(R) { return new THREE.Matrix4().set(R[0][0], R[0][1], R[0][2], 0, R[1][0], R[1][1], R[1][2], 0, R[2][0], R[2][1], R[2][2], 0, 0, 0, 0, 1); }
function setBodyPose(b, pose, cobBody) {
  _qCur.setFromRotationMatrix(matrixOf(pose.R_world));
  const ex = staticExag(); const ref = S.refPose && S.refPose[b.name];
  b.inner.quaternion.copy(_qCur); b.inner.position.set(0, 0, 0);
  if (ex > 1 && ref) {
    _qRef.setFromRotationMatrix(matrixOf(ref.R));
    _qDel.copy(_qCur).multiply(_qRef.clone().invert());          // q_cur = q_del * q_ref  (delta in world axes)
    let ang = 2 * Math.acos(Math.min(1, Math.abs(_qDel.w))); const sgn = _qDel.w < 0 ? -1 : 1;
    if (ang > 1e-9) { _axis.set(_qDel.x, _qDel.y, _qDel.z).multiplyScalar(sgn).normalize(); _qDel.setFromAxisAngle(_axis, ang * ex); b.inner.quaternion.copy(_qDel.multiply(_qRef)); }
    b.inner.position.set(0, 0, (ex - 1) * (pose.com_world[2] - ref.com[2]));
  }
  b.model.position.set(-pose.G_body[0], -pose.G_body[1], -pose.G_body[2]);
  b.outer.position.set(pose.com_world[0], pose.com_world[1], pose.com_world[2]); b.outer.rotation.set(0, 0, 0);
  b.com.position.set(pose.G_body[0], pose.G_body[1], pose.G_body[2]); if (cobBody) b.cob.position.set(cobBody[0], cobBody[1], cobBody[2]);
  b.com.visible = b.cob.visible = $('showMarkers').checked; b.outer.visible = true;
}
function applyPose(r) {
  const solved = r.bodies && r.bodies.exo && r.bodies.exo.pose && r.equilibrium && r.equilibrium.feasible;
  water.visible = wl.visible = solved && $('showWater').checked;
  const E = bodies3d.EXO, B = bodies3d.BOAT;
  placeThrust(solved ? r : null);
  if (!solved) {
    const bp = r.equilibrium && r.equilibrium.best_point;
    if (bp && r.bodies && r.bodies.exo && r.bodies.exo.pose) {
      // no equilibrium: show the solver's best balance point (the tendency: which end sinks) with the water, clearly labelled
      setBodyPose(E, r.bodies.exo.pose, null); E.cob.visible = false;
      water.visible = wl.visible = $('showWater').checked;
      B.outer.visible = false; linesGroup.visible = false;
      $('poseInfo').textContent = `NO EQUILIBRIUM — shown at the solver's best balance point (heel ${bp.heel_deg.toFixed(1)}°, trim ${bp.trim_deg.toFixed(1)}°, residual ${(100 * bp.residual_relative).toFixed(0)} % of the weight unbalanced)` +
        (bp.full_floats.length ? ` · fully submerged: ${bp.full_floats.join(', ')}` : '') + (bp.dry_floats.length ? ` · out of the water: ${bp.dry_floats.join(', ')}` : '') + ' — the floats cannot hold this load; the body would keep going';
      $('label').textContent = 'NO STATIC EQUILIBRIUM'; $('label').classList.add('error');
      flatWater(); updateLines();
      return;
    }
    E.outer.visible = true; E.outer.position.set(0, 0, 0); E.outer.rotation.set(0, 0, 0); E.inner.quaternion.identity(); E.inner.position.set(0, 0, 0); E.model.position.set(0, 0, 0); E.com.visible = E.cob.visible = false;
    B.outer.visible = false; linesGroup.visible = false;
    $('poseInfo').textContent = r.mode === 'baseline' ? 'baseline: no equilibrium (COM / density unknown) — EXO shown at CAD datum, no waterline' : 'no feasible equilibrium — model shown at CAD datum';
    return;
  }
  if ($('label').classList.contains('error')) { $('label').classList.remove('error'); $('label').textContent = S.config.result_label; }
  setBodyPose(E, r.bodies.exo.pose, r.equilibrium.centre_of_buoyancy_body_m);
  const ex = staticExag(); const exNote = ex > 1 && S.refPose ? ` · static Δ exaggerated ×${ex} (display only; numbers are true)` : '';
  const bb = r.bodies.boat;
  if (bb && bb.pose && bb.equilibrium && bb.equilibrium.feasible) {
    setBodyPose(B, bb.pose, bb.equilibrium.centre_of_buoyancy_body_m);
    linesGroup.visible = true; colourLines();
    const sl = (r.lines || []).filter((l) => l.slack).length;
    const prop = r.propulsion && r.propulsion.thrust_total_N > 0 ? ` · thrust ${r.propulsion.thrust_total_N.toFixed(0)} N, ${fmt(r.propulsion.speed_m_s, 2)} m/s` : '';
    $('poseInfo').textContent = `EXO: heel ${r.equilibrium.heel_deg.toFixed(2)}°, trim ${r.equilibrium.trim_deg.toFixed(2)}°, draft ${r.equilibrium.freeboard.draft_max_m.toFixed(3)} m · boat: heel ${bb.equilibrium.heel_deg.toFixed(2)}°, trim ${bb.equilibrium.trim_deg.toFixed(2)}°, draft ${bb.equilibrium.draft_hull_proxy_m.toFixed(2)} m${prop} — red: COM, blue: COB, lines yellow = taut, red = slack${sl ? ` (${sl} slack)` : ''}${exNote}`;
  } else {
    B.outer.visible = false; linesGroup.visible = false;
    $('poseInfo').textContent = `still water: heel ${r.equilibrium.heel_deg.toFixed(2)}°, trim ${r.equilibrium.trim_deg.toFixed(2)}°, draft ${r.equilibrium.freeboard.draft_max_m.toFixed(3)} m — red: COM, blue: COB` + (bb ? ' · boat: not solved' : '') + exNote;
  }
  flatWater(); updateLines();
}
const _va = new THREE.Vector3(), _vb = new THREE.Vector3(), _vd = new THREE.Vector3(), _up = new THREE.Vector3(0, 1, 0);
function updateLines() {
  for (const { a, b, cyl, r } of bodies3d.EXO.lineAnchors) {
    a.getWorldPosition(_va); b.getWorldPosition(_vb); physics.worldToLocal(_va); physics.worldToLocal(_vb);
    _vd.subVectors(_vb, _va); const L = _vd.length(); if (L < 1e-6) { cyl.visible = false; continue; }
    cyl.visible = true; cyl.position.copy(_va).addScaledVector(_vd, 0.5); cyl.scale.set(r, L, r);
    cyl.quaternion.setFromUnitVectors(_up, _vd.multiplyScalar(1 / L));
  }
}
function flatWater() { const pos = waterGeo.attributes.position; for (let i = 0; i < pos.count; i++) pos.setZ(i, 0); pos.needsUpdate = true; waterGeo.computeVertexNormals(); }
function startAnim(resetClock = true) { if (resetClock || !S.anim.playing) { S.anim.t = resetClock ? 0 : S.anim.t; S.anim.last = performance.now(); } S.anim.playing = true; $('play').textContent = '❚❚'; $('animNote').textContent = 'reconstructed LINEAR motion about the still-water equilibrium (exploratory)' + (S.waveRes && S.waveRes.hydro_meta && S.waveRes.hydro_meta.pose_reuse ? ' — BEM of a nearby pose reused' : '') + (S.waveRes && S.waveRes.encounter ? ` — at ${S.waveRes.encounter.speed_m_s.toFixed(2)} m/s (encounter period ${S.waveRes.encounter.period_e_s.toFixed(2)} s)` : ''); }
function stopAnim() { S.anim.playing = false; $('play').textContent = '▶'; if (S.still) applyPose(S.still); $('animNote').textContent = ''; }
$('previewWave').onchange = () => { if (!$('previewWave').checked) flatWater(); };
$('play').onclick = () => { if (!S.waveRes || !S.waveRes.regular_wave.in_range) return; S.anim.playing ? (S.anim.playing = false, $('play').textContent = '▶') : (S.anim.playing = true, S.anim.last = performance.now(), $('play').textContent = '❚❚'); };
$('showWater').onchange = $('showMarkers').onchange = () => { if (S.still) applyPose(S.still); };
function waveK(omega, depth) {
  const g = 9.80665; let k = omega * omega / g;
  if (depth && depth > 0) for (let i = 0; i < 50; i++) { const t = Math.tanh(k * depth); const f = g * k * t - omega * omega; const df = g * t + g * k * depth * (1 - t * t); const dk = f / df; k -= dk; if (Math.abs(dk) < 1e-12) break; }
  return k;
}
function setWater(A, k, b, w, t, ox, oy, ex) {
  const pos = waterGeo.attributes.position; const cb = Math.cos(b), sb = Math.sin(b);
  for (let i = 0; i < pos.count; i++) { const x = pos.getX(i), y = pos.getY(i); pos.setZ(i, ex * A * Math.cos(k * ((x - ox) * cb + (y - oy) * sb) - w * t)); }
  pos.needsUpdate = true; waterGeo.computeVertexNormals();
}
function animate(now) {
  requestAnimationFrame(animate);
  const solved = S.still && S.still.bodies && S.still.bodies.exo && S.still.bodies.exo.pose;
  if (solved && $('previewWave').checked && !(S.anim.playing && S.waveRes)) {
    const dt = (now - (S.anim.lastPrev || now)) / 1000 * (+$('speed').value); S.anim.lastPrev = now; S.anim.tPrev = (S.anim.tPrev || 0) + dt;
    const T = +$('T').value, H = +$('H').value, b = (+$('heading').value) * Math.PI / 180, w = 2 * Math.PI / T;
    setWater(H / 2, waveK(w, parseFloat($('depth').value) || null), b, w, S.anim.tPrev, 0, 0, +$('exag').value);
    $('animNote').textContent = 'incident wave preview only — body motion needs 2 · Compute BEM then 3 · Wave response';
  }
  if (S.anim.playing && S.waveRes && solved) {
    const rw = S.waveRes.regular_wave; const dt = (now - S.anim.last) / 1000 * (+$('speed').value); S.anim.last = now; S.anim.t += dt;
    const t = S.anim.t, w = rw.omega, k = rw.wavenumber, A = rw.amplitude_m, b = rw.heading_rad, ex = +$('exag').value;
    const dragSel = tctl.dragging && S.selected ? findHandle(S.selected) : null;
    for (const bp of S.waveRes.bodies) {
      const b3 = bodies3d[bp.name]; const bo = rw.bodies[bp.name]; if (!b3 || !bo) continue;
      if (dragSel && dragSel.body === b3 && dragSel.kind !== 'lineEnd') continue;      // keep the first-order preview visible while dragging a mass
      const X = bo.X_complex.map(([re, im]) => re * Math.cos(w * t) + im * Math.sin(w * t));
      b3.outer.position.set(bp.pose.com_world[0] + X[0] * ex, bp.pose.com_world[1] + X[1] * ex, bp.pose.com_world[2] + X[2] * ex);
      b3.outer.rotation.set(X[3] * ex, X[4] * ex, X[5] * ex, 'XYZ');
    }
    const o = S.waveRes.phase_origin_world || [0, 0];
    setWater(A, k, b, w, t, o[0], o[1], ex);
    $('tdisp').textContent = `t = ${t.toFixed(2)} s  (T=${rw.period_s} s)`;
  }
  updateLines();
  renderer.render(scene, camera);
}
function resize() { const w = viewer.clientWidth, h = viewer.clientHeight; renderer.setSize(w, h, false); camera.aspect = w / h; camera.updateProjectionMatrix(); }
window.addEventListener('resize', resize);
function view(kind) {
  const c = new THREE.Vector3(3.5, 1.0, 0); const d = 16;
  if (kind === 'top') camera.position.set(3.51, d, 0); else if (kind === 'side') camera.position.set(3.5, 2, d); else if (kind === 'end') camera.position.set(3.5 + d, 2, 0); else camera.position.set(12, 7, 11);
  camera.lookAt(c); orbit.target.copy(c); orbit.update();
}
$('viewTop').onclick = () => view('top'); $('viewSide').onclick = () => view('side'); $('viewEnd').onclick = () => view('end'); $('viewIso').onclick = () => view('iso');

// ============================================================ boot
(async () => {
  for (let attempt = 1; ; attempt++) {
    try { S.meta = await api('/api/meta'); break; }
    catch (e) { $('banner').textContent = `server not answering (attempt ${attempt}: ${e.message}) — is app.py running? retrying…`; await new Promise((r) => setTimeout(r, 2000)); }
  }
  $('version').textContent = `exo01 v${S.meta.version}`;
  fillScenarios(S.meta.scenarios, 'with_hydronaute');
  resize(); view('iso'); requestAnimationFrame(animate);
  if (S.meta.scenarios.includes('with_hydronaute')) { $('scenario').value = 'with_hydronaute'; await $('loadScenario').onclick(); }
  else { await loadBase('illustrative'); await doEvaluate(); }
  pollJobs();
  $('evaluate').onclick = doEvaluate;
  ['rho', 'depth'].forEach((id) => $(id).addEventListener('change', evaluate));
  window.__exo = { S, bodies3d, selectComponent, firstOrderPreview, commitHandle, findHandle, evaluate, doEvaluate, writeLines, linesList, setThrust, runWave, autoWave, runOptimise, applyPose, startAnim, stopAnim, camera, orbit, scene, renderer, resize, view, placeHandles, renderComponents };
})();
