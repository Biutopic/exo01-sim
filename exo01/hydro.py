"""Linear potential-flow coefficients (added mass, radiation damping, wave excitation) from Capytaine.

Zero forward speed, small amplitude, about the solved still-water equilibrium. The six floats are ONE rigid
assembly; hydrodynamic interactions between the floats are inside the BEM problem. Only the submerged part of the
float surfaces is meshed (the frame/deck/panels are assumed above water and have no hydrodynamics here).

Capytaine version is pinned (3.0.0). Conventions: time dependence exp(-i omega t); wave elevation of unit
amplitude is eta = exp(i k (x cos b + y sin b)) at the world origin (= assembly COM, horizontally); the
heading b is the direction the waves travel TOWARDS, measured counter-clockwise from +X; DOF order is
[surge, sway, heave, roll, pitch, yaw] about the COM, axes aligned with the world axes.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicSpline

from .buoyancy import CapsuleX, FlofizX
from .config import ROOT

DOF_NAMES = ["Surge", "Sway", "Heave", "Roll", "Pitch", "Yaw"]
CACHE_DIR = ROOT / "results" / "cache"
MESH_VERSION = "2-mirror-symmetric-capsule"   # bump when the surface triangulation changes (part of the cache key)


def weld(tris, tol=1e-7):
    V = tris.reshape(-1, 3)
    key = np.round(V / tol).astype(np.int64)
    u, idx, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    return V[idx], inv.reshape(-1, 3)


def surface_signature(s):
    """Cache-key description of a buoyant surface."""
    if isinstance(s, CapsuleX):
        return (s.id, "capsule", [round(float(c), 9) for c in s.centre], round(s.length, 9), round(s.radius, 9))
    if isinstance(s, FlofizX):
        return (s.id, "flofiz", round(s.flat_end_x, 9), int(s.nose_dir), [round(float(c), 9) for c in s.centre_yz],
                round(s.diameter, 9), round(s.body_length, 9), round(s.nose_length, 9))
    return (s.id, "mesh", int(len(s.vertices)), hashlib.sha256(np.round(s.vertices, 6).tobytes()).hexdigest()[:16],
            hashlib.sha256(np.asarray(s.faces).tobytes()).hexdigest()[:16])


def surface_tris_for_bem(s, panel_size):
    """Welded (V, F) at BEM resolution: capsule proxies are re-tessellated, measured meshes are used as they are."""
    if isinstance(s, (CapsuleX, FlofizX)):
        return weld(s.with_resolution(**panel_params(s, panel_size)).triangles())
    return np.asarray(s.vertices, float), np.asarray(s.faces, int)


def panel_params(surface, h):
    r = surface.radius
    if isinstance(surface, FlofizX):
        Lc, cap_len = surface.body_length, max(surface.nose_length, np.pi * r / 2)
    else:
        Lc, cap_len = surface.length - 2 * r, np.pi * r / 2
    return dict(n_circ=max(12, 4 * int(round(2 * np.pi * r / h / 4))), n_axial=max(2, int(round(Lc / h))),
                n_cap=max(4, int(round(cap_len / h))))


def world_triangles(surfaces, eq, panel_size):
    """Un-clipped closed triangles (n,3,3) of all float surfaces at the equilibrium pose, BEM panel resolution."""
    R, G, zG = eq["R"], eq["G_body"], eq["zG"]
    out = []
    for s in surfaces:
        V, F = surface_tris_for_bem(s, panel_size)
        out.append(((V - G) @ R.T + np.array([0.0, 0.0, zG]))[F])
    return np.concatenate(out, 0)


def build_world_mesh(surfaces, eq, panel_size):
    """Immersed Capytaine mesh of all float surfaces at the equilibrium pose (world frame, waterline z=0)."""
    import capytaine as cpt
    R, G, zG = eq["R"], eq["G_body"], eq["zG"]
    meshes = []
    for s in surfaces:
        V, F = surface_tris_for_bem(s, panel_size)
        Vw = (V - G) @ R.T + np.array([0.0, 0.0, zG])
        meshes.append(cpt.Mesh(Vw, F, name=s.id))
    m = cpt.Mesh.join_meshes(*meshes) if len(meshes) > 1 else meshes[0]
    return m.immersed_part()


def canonical_eq(eq):
    """Pose of the body's CAD origin: the BEM is computed about it (COM-independent), then moved to the COM."""
    R = np.asarray(eq["R"], float)
    G = np.asarray(eq["G_body"], float)
    z0 = float(eq["zG"] - (R @ G)[2])
    return dict(R=R, G_body=np.zeros(3), zG=z0, mass=eq.get("mass", 0.0))


def pose_from_angles(phi, theta, z_origin):
    from .buoyancy import attitude
    return dict(R=attitude(float(phi), float(theta)), G_body=np.zeros(3), zG=float(z_origin), mass=0.0)


def _angles(R):
    from .equilibrium import _euler_from_R
    phi, theta, _ = _euler_from_R(np.asarray(R, float))
    return float(phi), float(theta)


POSE_INDEX = CACHE_DIR / "pose_index.json"
POSE_TOL = dict(angle_rad=0.05, z_m=0.05, xy_m=0.10, yaw_rad=0.03)                 # "near": coefficients change little
POSE_TOL_COARSE = dict(angle_rad=0.17, z_m=0.30, xy_m=0.50, yaw_rad=0.10)          # "approximate": preview only, labelled


def _index_load():
    try:
        return json.loads(POSE_INDEX.read_text()) if POSE_INDEX.exists() else []
    except Exception:  # noqa: BLE001
        return []


def _index_add(entry):
    """Record a computed pose (idempotent on (kind, sig, pose); headings are merged)."""
    idx = _index_load()
    for e in idx:
        if e["kind"] == entry["kind"] and e["sig"] == entry["sig"] and e["pose"] == entry["pose"]:
            e["headings"] = sorted(set(np.round(e["headings"], 10).tolist()) | set(np.round(entry["headings"], 10).tolist()))
            e["files"] = sorted(set(e.get("files", [])) | set(entry.get("files", [])))
            break
    else:
        idx.append(entry)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = POSE_INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(idx))
    tmp.replace(POSE_INDEX)


def _sig(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=float).encode()).hexdigest()[:20]


def _pose_distance(kind, pose, want, t=None):
    """Normalised distance (<= 1 within the tolerance `t` on every component) between two index poses."""
    t = t or POSE_TOL
    comps = []
    for b in pose:
        q, w = pose[b], want[b]
        comps += [abs(q["phi"] - w["phi"]) / t["angle_rad"], abs(q["theta"] - w["theta"]) / t["angle_rad"], abs(q["z"] - w["z"]) / t["z_m"]]
        if "x" in q:
            comps += [abs(q["x"] - w["x"]) / t["xy_m"], abs(q["y"] - w["y"]) / t["xy_m"], abs(q["yaw"] - w["yaw"]) / t["yaw_rad"]]
    return max(comps)


def find_reusable_pose(kind, sig, want_pose, headings, tol=None):
    """Nearest recorded pose with the same signature (geometry, grid, settings), within `tol` (POSE_TOL), covering the headings."""
    best = None
    hs = set(np.round(np.atleast_1d(headings), 10).tolist())
    for e in _index_load():
        if e["kind"] != kind or e["sig"] != sig or set(e["pose"]) != set(want_pose):
            continue
        if not hs <= set(e["headings"]):
            continue
        dist = _pose_distance(kind, e["pose"], want_pose, tol)
        if dist <= 1.0 and (best is None or dist < best[0]):
            best = (dist, e)
    return best


def find_reusable_pose_tiered(kind, sig, want_pose, headings):
    """(hit, tier): 'near' within POSE_TOL, else 'approximate' within POSE_TOL_COARSE, else (None, None)."""
    hit = find_reusable_pose(kind, sig, want_pose, headings, POSE_TOL)
    if hit is not None:
        return hit, "near"
    hit = find_reusable_pose(kind, sig, want_pose, headings, POSE_TOL_COARSE)
    return (hit, "approximate") if hit is not None else (None, None)


def _key(surfaces, eq, omegas, headings, rho, g, depth, panel_size, lid, refine=False):
    import capytaine
    payload = dict(
        surfaces=[surface_signature(s) for s in surfaces],
        R=np.round(eq["R"], 10).tolist(), G=np.round(eq["G_body"], 10).tolist(), zG=round(eq["zG"], 10),
        omegas=np.round(omegas, 10).tolist(), headings=np.round(headings, 10).tolist(),
        rho=float(rho), g=float(g), depth=None if depth in (None, np.inf) else float(depth), h=float(panel_size), lid=bool(lid),
        refine=(float(refine) if refine else False), capytaine=capytaine.__version__, mesh_version=MESH_VERSION)
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]


def detect_gap_bands(omegas, A, B, dofs=(1, 2, 3, 4), window=0.6, spike=2.5, margin=0.15):
    """Frequency bands where potential-flow coefficients behave resonantly (water trapped between the float rows):
    negative diagonal added mass, or radiation damping spiking above `spike` x its running median (+-window).
    Returns a list of [omega_lo, omega_hi] (rad/s) with a margin added on both sides."""
    omegas = np.asarray(omegas, float)
    mask = np.zeros(len(omegas), bool)
    for i in dofs:
        a = A[:, i, i]
        b = B[:, i, i]
        med = np.array([np.median(b[(omegas >= w - window) & (omegas <= w + window)]) for w in omegas])
        mask |= (a < 0) | (b > spike * np.maximum(med, 1e-9))
    bands = []
    k = 0
    while k < len(omegas):
        if mask[k]:
            j = k
            while j + 1 < len(omegas) and mask[j + 1]:
                j += 1
            lo, hi = omegas[k] - margin, omegas[j] + margin
            if bands and lo <= bands[-1][1]:
                bands[-1][1] = hi
            else:
                bands.append([float(lo), float(hi)])
            k = j + 1
        else:
            k += 1
    return bands


class HydroData:
    """Hydrodynamic coefficients on a (omega, heading) grid with smooth interpolation."""

    def __init__(self, omegas, headings, A, B, F, meta):
        self.omegas, self.headings, self.A, self.B, self.F, self.meta = omegas, headings, A, B, F, meta
        self._A = CubicSpline(omegas, A, axis=0)
        self._B = CubicSpline(omegas, B, axis=0)
        # excitation: exact at computed headings; periodic cubic spline in heading only as a fallback (>= 4 headings)
        self._Fh = None
        if len(headings) >= 4:
            hh = np.concatenate([headings, [headings[0] + 2 * np.pi]])
            Fp = np.concatenate([F, F[:, :1, :]], axis=1)
            self._Fh = [CubicSpline(hh, Fp[i], axis=0, bc_type="periodic") for i in range(len(omegas))]

    def coeffs(self, omega):
        return self._A(omega), self._B(omega)

    def has_heading(self, heading):
        return bool(np.any(np.abs(np.mod(self.headings - heading + np.pi, 2 * np.pi) - np.pi) < 1e-9))

    def excitation(self, omega, heading):
        d = np.abs(np.mod(self.headings - heading + np.pi, 2 * np.pi) - np.pi)
        if d.min() < 1e-9:                                 # exact heading: no heading interpolation
            Fo = self.F[:, int(np.argmin(d)), :]
        elif self._Fh is None:
            raise ValueError(f"heading {np.degrees(heading):.1f} deg not computed and too few headings to interpolate")
        else:
            b = np.mod(heading, 2 * np.pi)
            Fo = np.array([f(b) for f in self._Fh])        # (n_omega, 6) complex at this heading (interpolated)
        re = CubicSpline(self.omegas, Fo.real, axis=0)(omega)
        im = CubicSpline(self.omegas, Fo.imag, axis=0)(omega)
        return re + 1j * im

    def gap_bands(self):
        n = self.A.shape[1]
        return detect_gap_bands(self.omegas, self.A, self.B, dofs=[i for i in range(n) if i % 6 in (1, 2, 3, 4)])

    def merged_with(self, other):
        """Union of two datasets on the same headings (used for band refinement)."""
        om = np.concatenate([self.omegas, other.omegas])
        order = np.argsort(om)
        om = om[order]
        keep = np.concatenate([[True], np.diff(om) > 1e-9])
        A = np.concatenate([self.A, other.A])[order][keep]
        B = np.concatenate([self.B, other.B])[order][keep]
        F = np.concatenate([self.F, other.F])[order][keep]
        meta = dict(self.meta, n_omega=int(keep.sum()), refined_omegas=other.omegas.tolist(),
                    seconds=self.meta.get("seconds", 0) + other.meta.get("seconds", 0))
        return HydroData(om[keep], self.headings, A, B, F, meta)

    def transformed(self, shifts, phase_shift_xy=None, depth=None, g=9.80665):
        """Exact change of the rigid-body reference point of each 6-DOF block and, optionally, of the wave phase origin.

        shifts: list of 3-vectors d_i = (new reference point - old reference point) of body i, world axes.
        With q_old = P q_new, P = [[I, skew(d)], [0, I]] (u_old = u_new + d x omega), the coefficients transform as
        A' = P^T A P, B' = P^T B P, F' = P^T F (virtual-work invariance: M' = M - d x F).
        phase_shift_xy: horizontal position (x, y) of the NEW wave-phase origin in the OLD frame; the excitation of a
        unit wave whose crest is at the new origin at t = 0 is F' = F exp(-i k (x cos b + y sin b)) (eta = exp(i k x.n)),
        verified against direct BEM solutions about shifted reference points (tests/test_hydro_response.py)."""
        n = self.A.shape[1]
        P = np.eye(n)
        for i, d in enumerate(shifts):
            d = np.asarray(d, float)
            S = np.array([[0.0, -d[2], d[1]], [d[2], 0.0, -d[0]], [-d[1], d[0], 0.0]])
            P[6 * i:6 * i + 3, 6 * i + 3:6 * i + 6] = S
        A = np.einsum("ji,wjk,kl->wil", P, self.A, P)
        B = np.einsum("ji,wjk,kl->wil", P, self.B, P)
        F = np.einsum("ji,whj->whi", P, self.F)
        if phase_shift_xy is not None and np.any(np.abs(phase_shift_xy) > 0):
            from .response import wavenumber
            k = np.array([wavenumber(w, depth, g) for w in self.omegas])
            ph = np.exp(-1j * k[:, None] * (phase_shift_xy[0] * np.cos(self.headings)[None, :] + phase_shift_xy[1] * np.sin(self.headings)[None, :]))
            F = F * ph[:, :, None]
        meta = dict(self.meta, reference_shift_m=[np.asarray(d, float).tolist() for d in shifts],
                    phase_origin_shift_m=None if phase_shift_xy is None else np.asarray(phase_shift_xy, float).tolist())
        return HydroData(self.omegas, self.headings, A, B, F, meta)

    def save(self, path):
        np.savez_compressed(path, omegas=self.omegas, headings=self.headings, A=self.A, B=self.B,
                            F_re=self.F.real, F_im=self.F.imag, meta=json.dumps(self.meta))

    @classmethod
    def load(cls, path):
        d = np.load(path, allow_pickle=False)
        return cls(d["omegas"], d["headings"], d["A"], d["B"], d["F_re"] + 1j * d["F_im"], json.loads(str(d["meta"])))


def make_lid(mesh, omega_max, g):
    """Internal free-surface lid for irregular-frequency removal.

    Capytaine's ``lowest_lid_position`` is the deepest lid that still works up to ``omega_max``; any lid between that
    depth and the free surface is at least as effective.  For a shallow hull (the host boat floating high on its proxy
    hull) that depth lies below the keel and the generated lid is empty, which silently disables the removal.  The lid
    is therefore clamped to half the draught of the mesh, and falls back to the free surface (z = 0, Capytaine's
    default) if it is still empty.  Returns (lid, z_lid)."""
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)      # arctanh(>1): irregular frequencies above omega_max
        z = float(mesh.lowest_lid_position(omega_max=float(omega_max), g=g))
    if not np.isfinite(z):
        z = 0.0
    z_min = float(mesh.vertices[:, 2].min())
    z = max(z, 0.5 * z_min)
    lid = mesh.generate_lid(z=z)
    if lid.nb_faces == 0:
        z = 0.0
        lid = mesh.generate_lid(z=z)
    return lid, z


def _body(surfaces, eq, omegas, g, panel_size, use_lid):
    import capytaine as cpt
    mesh = build_world_mesh(surfaces, eq, panel_size)
    com = np.array([0.0, 0.0, eq["zG"]])
    lid = make_lid(mesh, np.max(omegas), g)[0] if use_lid else None
    body = cpt.FloatingBody(mesh=mesh, lid_mesh=lid, dofs=cpt.rigid_body_dofs(rotation_center=com),
                            center_of_mass=com, mass=eq["mass"])
    return body, mesh, lid


# ---- progress reporting for long solves (set by the job worker; no-op otherwise)
PROGRESS = {"cb": None, "done": 0.0, "total": 1.0, "t0": None}


def set_progress(cb, total_units=1.0):
    """cb(fraction, message, eta_s) is called after every chunk of BEM work; total_units = radiation omegas + headings."""
    PROGRESS.update(cb=cb, done=0.0, total=max(float(total_units), 1e-9), t0=time.time())


def _tick(units, message):
    PROGRESS["done"] += units
    cb = PROGRESS["cb"]
    if cb is None:
        return
    frac = min(PROGRESS["done"] / PROGRESS["total"], 1.0)
    el = time.time() - (PROGRESS["t0"] or time.time())
    eta = el * (1 - frac) / frac if frac > 0.02 else None
    try:
        cb(frac, message, eta)
    except Exception:  # noqa: BLE001
        pass


def _chunks(omegas, n_chunks=12):
    omegas = np.asarray(omegas, float)
    k = max(1, int(np.ceil(len(omegas) / n_chunks)))
    return [omegas[i:i + k] for i in range(0, len(omegas), k)]


def _solve_radiation(body, omegas, rho, g, depth, label="radiation", dofs=None):
    """Radiation solve in omega chunks so that progress can be reported (identical results: one problem per omega)."""
    import capytaine as cpt
    import xarray as xr
    As, Bs = [], []
    dofs = list(dofs) if dofs is not None else list(DOF_NAMES)
    for ch in _chunks(omegas):
        ds = xr.Dataset(coords=dict(omega=np.asarray(ch, float), radiating_dof=dofs, influenced_dof=dofs,
                                    rho=[rho], g=[g], water_depth=[np.inf if depth is None else depth]))
        res = cpt.BEMSolver().fill_dataset(ds, body, n_jobs=1, progress_bar=False)
        As.append(res["added_mass"].sel(radiating_dof=dofs, influenced_dof=dofs).transpose("omega", "influenced_dof", "radiating_dof").values)
        Bs.append(res["radiation_damping"].sel(radiating_dof=dofs, influenced_dof=dofs).transpose("omega", "influenced_dof", "radiating_dof").values)
        _tick(len(ch), f"{label}: {ch[-1]:.2f} rad/s (T {2 * np.pi / ch[-1]:.2f} s)")
    return np.concatenate(As), np.concatenate(Bs)


def _solve_diffraction(body, omegas, headings, rho, g, depth, dofs=None):
    import capytaine as cpt
    import xarray as xr
    dofs = list(dofs) if dofs is not None else list(DOF_NAMES)
    out = []
    n_om = len(omegas)
    for b in np.atleast_1d(headings):
        Fs = []
        for ch in _chunks(omegas, 6):
            ds = xr.Dataset(coords=dict(omega=np.asarray(ch, float), wave_direction=[float(b)], influenced_dof=dofs,
                                        rho=[rho], g=[g], water_depth=[np.inf if depth is None else depth]))
            res = cpt.BEMSolver().fill_dataset(ds, body, n_jobs=1, progress_bar=False)
            Fs.append(res["excitation_force"].sel(influenced_dof=dofs).transpose("omega", "wave_direction", "influenced_dof").values)
            _tick(len(ch) * 0.35, f"diffraction {np.degrees(b):.0f} deg: {ch[-1]:.2f} rad/s")
        out.append(np.concatenate(Fs))
    return np.concatenate(out, axis=1)


CONVENTIONS = ("exp(-i w t); heading = direction waves travel toward, CCW from +X; DOF about COM, world axes; "
               "unit-amplitude wave has eta=exp(i k (x cos b + y sin b)) at the world origin (COM)")


class HydroNotComputed(Exception):
    pass


def compute_hydro(surfaces, eq, omegas, headings, rho, g, water_depth=None, panel_size=0.12,
                  use_lid=True, use_cache=True, refine_bands=True, refine_step=0.05, cache_only=False, pose_from=None):
    """Hydrodynamic coefficients for one configuration. `water_depth=None` means infinite depth.

    Radiation (A, B) is solved once per configuration/grid and cached; with refine_bands=True a second radiation
    pass adds omegas at `refine_step` inside the detected gap-resonance bands. Diffraction/excitation is then solved
    at the EXACT requested headings (cached per heading) on the full omega list, so no heading interpolation is
    needed for the results; HydroData still interpolates in heading if asked for one that was not computed."""
    import capytaine
    omegas = np.asarray(omegas, float)
    headings = np.atleast_1d(np.asarray(headings, float))
    depth = None if water_depth in (None, np.inf) else float(water_depth)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    eq_req = eq
    eq = canonical_eq(eq_req) if pose_from is None else pose_from_angles(pose_from["phi"], pose_from["theta"], pose_from["z"])
    rkey = _key(surfaces, eq, omegas, np.array([]), rho, g, depth, panel_size, use_lid, refine_bands and refine_step)
    if pose_from is not None and pose_from.get("key"):
        rkey = pose_from["key"]                      # recorded key of the reused pose (avoids round-off in the rebuilt pose)
    rpath = CACHE_DIR / f"rad_{rkey}.npz"
    t0 = time.time()
    body = None
    if use_cache and rpath.exists():
        d = np.load(rpath, allow_pickle=False)
        om_all, A, B, rmeta = d["omegas"], d["A"], d["B"], json.loads(str(d["meta"]))
        rmeta["cache"] = "hit"
    else:
        if cache_only:
            raise HydroNotComputed("radiation coefficients not computed for this configuration/grid")
        body, mesh, lid = _body(surfaces, eq, omegas, g, panel_size, use_lid)
        A, B = _solve_radiation(body, omegas, rho, g, depth)
        om_all = omegas
        bands = detect_gap_bands(omegas, A, B)
        rmeta = dict(capytaine=capytaine.__version__, panel_size_m=panel_size, n_faces=int(mesh.nb_faces),
                     n_lid_faces=0 if lid is None else int(lid.nb_faces), rho=rho, g=g, water_depth=depth,
                     omega_range=[float(omegas.min()), float(omegas.max())], gap_bands_base_grid=bands,
                     disp_volume_mesh_m3=float(mesh.disp_volume), cache="miss", conventions=CONVENTIONS)
        if refine_bands and bands:
            extra = sorted({float(x) for lo, hi in bands for x in np.round(np.arange(max(lo, omegas[0]), min(hi, omegas[-1]) + 1e-9, refine_step), 10)}
                           - set(np.round(omegas, 10).tolist()))
            if extra:
                A2, B2 = _solve_radiation(body, np.array(extra), rho, g, depth)
                om_all = np.concatenate([omegas, extra])
                order = np.argsort(om_all)
                om_all, A, B = om_all[order], np.concatenate([A, A2])[order], np.concatenate([B, B2])[order]
                rmeta["refinement"] = f"{len(extra)} omegas added at {refine_step} rad/s inside gap-resonance bands"
        rmeta["gap_bands"] = detect_gap_bands(om_all, A, B)
        rmeta["seconds_radiation"] = time.time() - t0
        np.savez_compressed(rpath, omegas=om_all, A=A, B=B, meta=json.dumps(rmeta))
    # excitation per heading (exact)
    F = np.zeros((len(om_all), len(headings), 6), complex)
    hits = 0
    for j, b in enumerate(headings):
        hkey = _key(surfaces, eq, om_all, np.array([b]), rho, g, depth, panel_size, use_lid, refine_bands and refine_step)
        if pose_from is not None and pose_from.get("exc_keys"):
            hkey = pose_from["exc_keys"].get(f"{b:.10f}", hkey)
        hpath = CACHE_DIR / f"exc_{hkey}.npz"
        if use_cache and hpath.exists():
            d = np.load(hpath, allow_pickle=False)
            F[:, j, :] = d["F_re"] + 1j * d["F_im"]
            hits += 1
        else:
            if cache_only:
                raise HydroNotComputed(f"excitation not computed for heading {np.degrees(b):.1f} deg")
            if body is None:
                body, _, _ = _body(surfaces, eq, om_all, g, panel_size, use_lid)
            Fj = _solve_diffraction(body, om_all, [b], rho, g, depth)[:, 0, :]
            F[:, j, :] = Fj
            np.savez_compressed(hpath, F_re=Fj.real, F_im=Fj.imag, omegas=om_all, heading=b)
    meta = dict(rmeta, n_omega=len(om_all), n_headings=len(headings), headings_deg=np.degrees(headings).tolist(),
                excitation_cache=f"{hits}/{len(headings)} headings from cache", seconds=time.time() - t0,
                cache="hit" if (rmeta["cache"] == "hit" and hits == len(headings)) else "miss")
    phi, theta = _angles(eq["R"])
    _index_add(dict(kind="single", sig=single_signature(surfaces, omegas, rho, g, depth, panel_size, use_lid, refine_bands and refine_step),
                    pose={"EXO": dict(phi=phi, theta=theta, z=float(eq["zG"]))}, headings=np.round(headings, 10).tolist(), key=rkey,
                    files=[rpath.name] + [f"exc_{_key(surfaces, eq, om_all, np.array([b]), rho, g, depth, panel_size, use_lid, refine_bands and refine_step)}.npz" for b in headings],
                    exc_keys={f"{b:.10f}": _key(surfaces, eq, om_all, np.array([b]), rho, g, depth, panel_size, use_lid, refine_bands and refine_step) for b in headings}))
    hd = HydroData(om_all, headings, A, B, F, meta)
    # computed about the CAD origin at (0, 0, z_origin): move to the requested COM (exact) and to the COM phase origin
    R, G = np.asarray(eq_req["R"], float), np.asarray(eq_req["G_body"], float)
    d = R @ G
    hd = hd.transformed([d], phase_shift_xy=d[:2], depth=depth, g=g)
    hd.meta["reference"] = "6 rigid DOF about the COM (world axes); wave phase origin at the COM (horizontal)"
    if pose_from is not None:
        phr, thr = _angles(R)
        tier = pose_from.get("tier", "near")
        hd.meta["pose_reuse"] = dict(tier=tier, dheel_deg=float(np.degrees(phr - pose_from["phi"])), dtrim_deg=float(np.degrees(thr - pose_from["theta"])),
                                     dz_m=float(canonical_eq(eq_req)["zG"] - pose_from["z"]),
                                     note=("APPROXIMATE PREVIEW: " if tier == "approximate" else "") +
                                          "BEM of a nearby pose reused (same geometry and grid); coefficients moved exactly to the current COM; "
                                          "the pose difference is NOT accounted for (run Compute BEM for the exact pose)")
    return hd


def single_signature(surfaces, omegas, rho, g, depth, panel_size, lid, refine):
    import capytaine
    return _sig(dict(surfaces=[surface_signature(s) for s in surfaces], omegas=np.round(omegas, 10).tolist(), rho=float(rho), g=float(g),
                     depth=None if depth in (None, np.inf) else float(depth), h=float(panel_size), lid=bool(lid),
                     refine=(float(refine) if refine else False), capytaine=capytaine.__version__, mesh_version=MESH_VERSION))


# ====================================================================== several bodies in the common world frame W
def mesh_from_pose(V, F, pose, name):
    """World-frame Capytaine mesh of a closed surface (V, F in the body's own CAD frame) at `pose`."""
    import capytaine as cpt
    R = np.asarray(pose["R_world"], float)
    G = np.asarray(pose["G_body"], float)
    c = np.asarray(pose["com_world"], float)
    return cpt.Mesh((V - G) @ R.T + c, F, name=name)


def body_mesh(spec, panel_size):
    """spec: dict(name, surfaces=[CapsuleX...]) or dict(name, vertices, faces) (already at BEM resolution)."""
    import capytaine as cpt
    if "surfaces" in spec:
        ms = []
        for s in spec["surfaces"]:
            V, F = surface_tris_for_bem(s, panel_size)
            ms.append(mesh_from_pose(V, F, spec["pose"], s.id))
        m = cpt.Mesh.join_meshes(*ms) if len(ms) > 1 else ms[0]
    else:
        m = mesh_from_pose(spec["vertices"], spec["faces"], spec["pose"], spec["name"])
    return m.immersed_part()


def origin_world(pose):
    """World position of the body's CAD origin: com_world - R_world G_body."""
    return np.asarray(pose["com_world"], float) - np.asarray(pose["R_world"], float) @ np.asarray(pose["G_body"], float)


def canonical_specs(specs):
    """Specs whose DOFs are about each body's CAD origin (COM-independent BEM); the result is moved to the COMs after."""
    out = []
    for sp in specs:
        o = origin_world(sp["pose"])
        pose = dict(R_world=np.asarray(sp["pose"]["R_world"], float).tolist(), com_world=o.tolist(), G_body=[0.0, 0.0, 0.0])
        out.append(dict(sp, pose=pose))
    return out


def multi_signature(specs, omegas, rho, g, depth, panel_sizes, lid, refine):
    bodies = []
    for sp in specs:
        bodies.append(dict(name=sp["name"], geom=[surface_signature(x) for x in sp["surfaces"]] if "surfaces" in sp
                           else dict(n=int(len(sp["vertices"])), hash=hashlib.sha256(np.round(sp["vertices"], 6).tobytes()).hexdigest()[:16])))
    return _sig(dict(bodies=bodies, omegas=np.round(omegas, 10).tolist(), rho=float(rho), g=float(g),
                     depth=None if depth in (None, np.inf) else float(depth), h=[float(x) for x in panel_sizes], lid=("clamped" if lid else False),
                     refine=(float(refine) if refine else False), capytaine=capytaine_version(), mesh_version=MESH_VERSION))


def multi_pose(specs):
    """Index pose of a multibody problem: per body heel/trim, CAD-origin height, and (x, y, yaw) of the origin."""
    out = {}
    for sp in specs:
        R = np.asarray(sp["pose"]["R_world"], float)
        o = origin_world(sp["pose"])
        from .equilibrium import _euler_from_R
        phi, theta, psi = _euler_from_R(R)
        out[sp["name"]] = dict(phi=float(phi), theta=float(theta), z=float(o[2]), x=float(o[0]), y=float(o[1]), yaw=float(psi))
    return out


def specs_from_index_pose(specs, pose):
    """Rebuild canonical specs at an indexed pose (same geometry): R from (yaw, heel, trim), origin from (x, y, z)."""
    from .buoyancy import attitude
    out = []
    for sp in specs:
        q = pose[sp["name"]]
        Rw = Rz_(q["yaw"]) @ attitude(q["phi"], q["theta"])
        out.append(dict(sp, pose=dict(R_world=Rw.tolist(), com_world=[q["x"], q["y"], q["z"]], G_body=[0.0, 0.0, 0.0])))
    return out


def Rz_(psi):
    c, s_ = np.cos(psi), np.sin(psi)
    return np.array([[c, -s_, 0.0], [s_, c, 0.0], [0.0, 0.0, 1.0]])


def _multibody(specs, omegas, g, panel_sizes, use_lid):
    import capytaine as cpt
    bodies, info = [], []
    for spec, h in zip(specs, panel_sizes):
        m = body_mesh(spec, h)
        lid, z_lid = make_lid(m, np.max(omegas), g) if use_lid else (None, None)
        c = np.asarray(spec["pose"]["com_world"], float)
        b = cpt.FloatingBody(mesh=m, lid_mesh=lid, dofs=cpt.rigid_body_dofs(rotation_center=c), center_of_mass=c,
                             mass=spec["mass"], name=spec["name"])
        bodies.append(b)
        info.append(dict(name=spec["name"], n_faces=int(m.nb_faces), n_lid_faces=0 if lid is None else int(lid.nb_faces),
                         lid_z_m=z_lid, panel_size_m=h, disp_volume_mesh_m3=float(m.disp_volume)))
    mb = bodies[0]
    for b in bodies[1:]:
        mb = mb + b
    return mb, info


def _dof_order(specs):
    return [f"{s['name']}__{d}" for s in specs for d in DOF_NAMES]


def compute_hydro_bodies(specs, omegas, headings, rho, g, water_depth=None, panel_sizes=None, use_lid=True,
                         use_cache=True, refine_bands=True, refine_step=0.05, cache_only=False, pose_from=None):
    """Radiation + exact-heading diffraction for N rigid bodies in the common world frame (hydrodynamic
    interaction included). DOF order: body0 (surge..yaw), body1 (...), ... about each body's COM, world axes.
    Computed about each body's CAD origin (COM-independent, cached), then moved exactly to the COMs."""
    import capytaine as cpt
    import xarray as xr
    omegas = np.asarray(omegas, float)
    headings = np.atleast_1d(np.asarray(headings, float))
    depth = None if water_depth in (None, np.inf) else float(water_depth)
    panel_sizes = panel_sizes or [0.15] * len(specs)
    specs_req = specs
    specs = canonical_specs(specs_req) if pose_from is None else specs_from_index_pose(specs_req, pose_from["pose"])
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    payload = dict(bodies=[dict(name=s["name"], pose=np.round(np.asarray(s["pose"]["R_world"]), 10).tolist() + np.round(s["pose"]["com_world"], 10).tolist()
                                + np.round(s["pose"]["G_body"], 10).tolist(),
                                geom=[surface_signature(x) for x in s["surfaces"]] if "surfaces" in s
                                else dict(n=int(len(s["vertices"])), hash=hashlib.sha256(np.round(s["vertices"], 6).tobytes()).hexdigest()[:16]))
                           for s in specs],
                   omegas=np.round(omegas, 10).tolist(), rho=float(rho), g=float(g), depth=None if depth is None else float(depth),
                   h=[float(x) for x in panel_sizes], lid=("clamped" if use_lid else False),
                   refine=(float(refine_step) if refine_bands else False), capytaine=capytaine_version(), mesh_version=MESH_VERSION)
    rkey = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:20]
    if pose_from is not None and pose_from.get("key"):
        rkey = pose_from["key"]                      # recorded key of the reused pose
    rpath = CACHE_DIR / f"mrad_{rkey}.npz"
    dofs = _dof_order(specs)
    n = len(dofs)
    t0 = time.time()
    mb = None
    if use_cache and rpath.exists():
        d = np.load(rpath, allow_pickle=False)
        om_all, A, B, rmeta = d["omegas"], d["A"], d["B"], json.loads(str(d["meta"]))
        rmeta["cache"] = "hit"
    else:
        if cache_only:
            raise HydroNotComputed("multi-body radiation coefficients not computed for this configuration/grid")
        mb, info = _multibody(specs, omegas, g, panel_sizes, use_lid)

        def rad(om):
            return _solve_radiation(mb, om, rho, g, depth, label="two-body radiation", dofs=dofs)
        A, B = rad(omegas)
        om_all = omegas
        bands = detect_gap_bands(omegas, A, B, dofs=[i for i in range(n) if i % 6 in (1, 2, 3, 4)])
        rmeta = dict(capytaine=capytaine_version(), bodies=info, n_faces=sum(i["n_faces"] for i in info),
                     n_lid_faces=sum(i["n_lid_faces"] for i in info), rho=rho, g=g, water_depth=depth,
                     omega_range=[float(omegas.min()), float(omegas.max())], gap_bands_base_grid=bands, cache="miss",
                     conventions=CONVENTIONS + "; multi-body: DOF blocks per body, each about its own COM; wave phase origin = world origin (EXO CAD origin)",
                     dof_names=dofs)
        if refine_bands and bands:
            extra = sorted({float(x) for lo, hi in bands for x in np.round(np.arange(max(lo, omegas[0]), min(hi, omegas[-1]) + 1e-9, refine_step), 10)}
                           - set(np.round(omegas, 10).tolist()))
            if extra:
                A2, B2 = rad(np.array(extra))
                om_all = np.concatenate([omegas, extra])
                order = np.argsort(om_all)
                om_all, A, B = om_all[order], np.concatenate([A, A2])[order], np.concatenate([B, B2])[order]
                rmeta["refinement"] = f"{len(extra)} omegas added at {refine_step} rad/s inside gap-resonance bands"
        rmeta["gap_bands"] = detect_gap_bands(om_all, A, B, dofs=[i for i in range(n) if i % 6 in (1, 2, 3, 4)])
        rmeta["seconds_radiation"] = time.time() - t0
        np.savez_compressed(rpath, omegas=om_all, A=A, B=B, meta=json.dumps(rmeta))
    F = np.zeros((len(om_all), len(headings), n), complex)
    hits = 0
    for j, b in enumerate(headings):
        hkey = hashlib.sha256((rkey + f"|{b:.12f}|{len(om_all)}").encode()).hexdigest()[:20]
        hpath = CACHE_DIR / f"mexc_{hkey}.npz"
        if use_cache and hpath.exists():
            d = np.load(hpath, allow_pickle=False)
            F[:, j, :] = d["F_re"] + 1j * d["F_im"]
            hits += 1
        else:
            if cache_only:
                raise HydroNotComputed(f"multi-body excitation not computed for heading {np.degrees(b):.1f} deg")
            if mb is None:
                mb, _ = _multibody(specs, om_all, g, panel_sizes, use_lid)
            Fj = _solve_diffraction(mb, om_all, [b], rho, g, depth, dofs=dofs)[:, 0, :]
            F[:, j, :] = Fj
            np.savez_compressed(hpath, F_re=Fj.real, F_im=Fj.imag, omegas=om_all, heading=b)
    meta = dict(rmeta, n_omega=len(om_all), n_headings=len(headings), headings_deg=np.degrees(headings).tolist(),
                excitation_cache=f"{hits}/{len(headings)} headings from cache", seconds=time.time() - t0,
                cache="hit" if (rmeta["cache"] == "hit" and hits == len(headings)) else "miss", n_bodies=len(specs))
    _index_add(dict(kind="multi", sig=multi_signature(specs, omegas, rho, g, depth, panel_sizes, use_lid, refine_bands and refine_step),
                    pose=multi_pose(specs), headings=np.round(headings, 10).tolist(), key=rkey,
                    files=[rpath.name] + [f"mexc_{hashlib.sha256((rkey + f'|{b:.12f}|{len(om_all)}').encode()).hexdigest()[:20]}.npz" for b in headings]))
    hd = HydroData(om_all, headings, A, B, F, meta)
    shifts = [np.asarray(sp["pose"]["com_world"], float) - origin_world(sp["pose"]) for sp in specs_req]
    hd = hd.transformed(shifts, phase_shift_xy=None)          # multibody phase origin = world origin (unchanged)
    hd.meta["reference"] = "DOF blocks per body about its COM (world axes); wave phase origin = world origin"
    if pose_from is not None:
        want = multi_pose(canonical_specs(specs_req))
        pf = pose_from["pose"]
        tier = pose_from.get("tier", "near")
        hd.meta["pose_reuse"] = dict({b: dict(dheel_deg=float(np.degrees(want[b]["phi"] - pf[b]["phi"])),
                                               dtrim_deg=float(np.degrees(want[b]["theta"] - pf[b]["theta"])),
                                               dz_m=float(want[b]["z"] - pf[b]["z"]), dx_m=float(want[b]["x"] - pf[b]["x"]),
                                               dy_m=float(want[b]["y"] - pf[b]["y"]), dyaw_deg=float(np.degrees(want[b]["yaw"] - pf[b]["yaw"])))
                                      for b in want}, tier=tier,
                                     dz_m=float(want["EXO"]["z"] - pf["EXO"]["z"]), dheel_deg=float(np.degrees(want["EXO"]["phi"] - pf["EXO"]["phi"])),
                                     dtrim_deg=float(np.degrees(want["EXO"]["theta"] - pf["EXO"]["theta"])),
                                     boat_dx_m=float(want["BOAT"]["x"] - pf["BOAT"]["x"]) if "BOAT" in want else None,
                                     note=("APPROXIMATE PREVIEW: " if tier == "approximate" else "") +
                                          "BEM of nearby poses reused (same geometry and grid); coefficients moved exactly to the current COMs; "
                                          "the pose differences are NOT accounted for (run Compute BEM for the exact poses)")
    return hd


def capytaine_version():
    import capytaine
    return capytaine.__version__
