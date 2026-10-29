"""Host boat (Hydronaute / Renaud 8000) as a second floating body.

The hull is the package's closed "gull-wing" envelope PROXY, rebuilt here analytically from the same station table
and section profile as `build_model.py` of the reference package (ruled loft between 13-point station polygons,
flat stern cap, pointed bow), subdivided for hydrostatics/BEM. It is NOT a measured hull: no offsets exist.
`MeshSurface` can take a measured closed surface instead without changing anything downstream.

Boat CAD frame (package): X stern -> bow, Y to port, Z up, Z = 0 at the illustrative catalogue waterline.
"""
from __future__ import annotations

import numpy as np

from .buoyancy import MeshSurface

# section profile of build_model.py: (y fraction of half-beam, z in mm); z=top is clamped to the topside top
_SECTION = [(-1, "top"), (-1, 180), (-.93, -160), (-.75, -240), (-.52, -20), (-.23, -400), (0, -530), (.23, -400),
            (.52, -20), (.75, -240), (.93, -160), (1, 180), (1, "top")]


def station_polygon(x_mm, b_mm, rise_mm, top_mm):
    pts = []
    for yf, z in _SECTION:
        zz = top_mm if z == "top" else min(top_mm - 10, z + rise_mm)
        pts.append((x_mm, yf * b_mm, zz))
    return np.array(pts, float)


def hull_envelope(stations_mm, top_mm=780.0, dx_max=0.15, ds_max=0.15, name="RENAUD8000_HULL_PROXY"):
    """Closed triangulated hull envelope (metres, boat CAD frame, outward normals), from the station table."""
    polys = [station_polygon(*s, top_mm) / 1000.0 for s in stations_mm]
    # refine each polygon edge so that the ring has <= ds_max segments (same subdivision at every station: ruled)
    n_pts = len(polys[0])
    seg_n = []
    for k in range(n_pts):
        k2 = (k + 1) % n_pts
        L = max(np.linalg.norm(p[k2] - p[k]) for p in polys)
        seg_n.append(max(1, int(np.ceil(L / ds_max))))
    rings = []
    for p in polys:
        ring = []
        for k in range(n_pts):
            k2 = (k + 1) % n_pts
            for j in range(seg_n[k]):
                t = j / seg_n[k]
                ring.append(p[k] + t * (p[k2] - p[k]))
        rings.append(np.array(ring))
    # refine along x between stations (ruled surface: linear interpolation is exact)
    fine = [rings[0]]
    for a, b in zip(rings[:-1], rings[1:]):
        n = max(1, int(np.ceil(abs(b[0, 0] - a[0, 0]) / dx_max)))
        for j in range(1, n + 1):
            fine.append(a + (b - a) * j / n)
    m = len(fine[0])
    V = np.concatenate(fine, 0)
    F = []
    for i in range(len(fine) - 1):
        o0, o1 = i * m, (i + 1) * m
        for k in range(m):
            k2 = (k + 1) % m
            # orientation chosen so that normals point outward (checked by signed volume > 0 below)
            F.append([o0 + k, o1 + k, o0 + k2])
            F.append([o0 + k2, o1 + k, o1 + k2])
    # caps: stern (x = x0) and bow
    c0 = len(V)
    V = np.concatenate([V, fine[0].mean(0, keepdims=True), fine[-1].mean(0, keepdims=True)], 0)
    c1 = c0 + 1
    o = (len(fine) - 1) * m
    for k in range(m):
        k2 = (k + 1) % m
        F.append([c0, k2, k])                    # stern cap
        F.append([c1, o + k, o + k2])            # bow cap
    F = np.array(F, int)
    # drop degenerate triangles (coincident ring points where the section is clamped to the top)
    T = V[F]
    area2 = np.linalg.norm(np.cross(T[:, 1] - T[:, 0], T[:, 2] - T[:, 0]), axis=1)
    F = F[area2 > 1e-12]
    # orient consistently: sides from the loft are mutually consistent; make the whole set outward (signed volume > 0),
    # then fix each cap independently (stern cap normal must point -x, bow cap +x)
    def vol_of(Fs):
        return float(np.einsum("ij,ij->i", V[Fs[:, 0]], np.cross(V[Fs[:, 1]], V[Fs[:, 2]])).sum() / 6)
    is_cap0 = (F == c0).any(1)
    is_cap1 = (F == c1).any(1)
    sides = F[~is_cap0 & ~is_cap1]
    if vol_of(sides) < 0:
        sides = sides[:, [0, 2, 1]]
    cap0 = F[is_cap0]
    cap1 = F[is_cap1]
    n0 = np.cross(V[cap0[:, 1]] - V[cap0[:, 0]], V[cap0[:, 2]] - V[cap0[:, 0]]).sum(0)
    if n0[0] > 0:
        cap0 = cap0[:, [0, 2, 1]]
    n1 = np.cross(V[cap1[:, 1]] - V[cap1[:, 0]], V[cap1[:, 2]] - V[cap1[:, 0]]).sum(0)
    if n1[0] < 0:
        cap1 = cap1[:, [0, 2, 1]]
    F = np.concatenate([sides, cap0, cap1], 0)
    return MeshSurface(name, V, F)


def check_closed(F):
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    _, c = np.unique(e, axis=0, return_counts=True)
    return bool(np.all(c == 2))


def surface_from_config(spec, resolution=None):
    res = resolution or {}
    return hull_envelope(spec["stations_mm"], spec.get("topside_top_mm", 780.0),
                         dx_max=res.get("dx_max", spec.get("dx_max", 0.15)), ds_max=res.get("ds_max", spec.get("ds_max", 0.15)),
                         name=spec["id"])
