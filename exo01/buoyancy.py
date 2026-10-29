"""Hydrostatic integrals of closed triangulated buoyant surfaces cut by the plane z = 0.

Independent of rendering and of Capytaine. Exact (to machine precision) for the
triangulated surface given: the submerged part is obtained by clipping triangles
against z <= 0 and applying the divergence theorem with F = (0,0,z), (0,0,xz),
(0,0,yz), (0,0,z^2/2). The waterplane cap lies at z = 0 and contributes nothing
to these integrals. Any measured displacement surface (closed, outward normals)
can replace the proxy capsules without touching the solver: see `MeshSurface`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


# ------------------------------------------------------------------ surfaces
def revolve_profile(xs, rs, n_circ, area_preserving=True, zc=None):
    """Triangulated surface of revolution about the local x-axis, outward normals.

    xs, rs : profile (axial position, radius); rs[0] and rs[-1] may be 0 (closed ends).
    zc     : optional per-ring vertical offset of the ring centre (a nose whose top stays level while the bottom
             curves up); the mirror symmetry about the x-z plane is kept.
    The ring radius is scaled so the polygon cross-section has the area of the true circle
    (removes the systematic inscribed-polygon volume bias). With n_circ a multiple of 4 the triangulation
    is exactly mirror-symmetric about the x-z plane (quad diagonals alternate with the sign of cos(mid-angle)),
    so a port/starboard pair of floats gives an exactly symmetric hydrodynamic mesh.
    """
    xs = np.asarray(xs, float)
    rs = np.asarray(rs, float)
    zc = np.zeros_like(xs) if zc is None else np.asarray(zc, float)
    s = np.sqrt(2 * np.pi / (n_circ * np.sin(2 * np.pi / n_circ))) if area_preserving else 1.0
    ang = 2 * np.pi * np.arange(n_circ) / n_circ
    ca, sa = np.cos(ang), np.sin(ang)
    ca2, sa2 = np.roll(ca, -1), np.roll(sa, -1)
    diag_A = np.cos(ang + np.pi / n_circ) > 0           # which diagonal each quad uses (mirror-symmetric choice)
    out = []
    for a in range(len(xs) - 1):
        x0, x1, r0, r1 = xs[a], xs[a + 1], rs[a] * s, rs[a + 1] * s
        z0, z1 = zc[a], zc[a + 1]
        p00 = np.stack([np.full(n_circ, x0), r0 * ca, r0 * sa + z0], 1)
        p01 = np.stack([np.full(n_circ, x0), r0 * ca2, r0 * sa2 + z0], 1)
        p10 = np.stack([np.full(n_circ, x1), r1 * ca, r1 * sa + z1], 1)
        p11 = np.stack([np.full(n_circ, x1), r1 * ca2, r1 * sa2 + z1], 1)
        # type A: diagonal p00-p11; type B: diagonal p01-p10 (normals point away from the axis)
        t1 = np.where(diag_A[:, None, None], np.stack([p00, p01, p11], 1), np.stack([p00, p01, p10], 1))
        t2 = np.where(diag_A[:, None, None], np.stack([p00, p11, p10], 1), np.stack([p01, p11, p10], 1))
        if r0 > 1e-12:
            out.append(t1)
        if r1 > 1e-12:
            out.append(t2)
    return np.concatenate(out, 0)


def capsule_profile(length, radius, n_axial, n_cap):
    """Profile of a capsule (cylinder + two hemispheres) of overall `length`, centred at 0."""
    Lc = length - 2 * radius
    if Lc < 0:
        raise ValueError("capsule length must be >= 2*radius")
    t = np.linspace(0.0, 1.0, n_cap + 1) * (np.pi / 2)   # left cap: tip at x=-L/2, radius grows to r
    left_x = -length / 2 + radius * (1 - np.cos(t))
    left_r = radius * np.sin(t)
    cyl_x = np.linspace(-Lc / 2, Lc / 2, n_axial + 1)[1:-1]
    cyl_r = np.full_like(cyl_x, radius)
    right_x = Lc / 2 + radius * np.sin(t)
    right_r = radius * np.cos(t)
    xs = np.concatenate([left_x, cyl_x, right_x])
    rs = np.concatenate([left_r, cyl_r, right_r])
    return xs, rs


@dataclass
class CapsuleX:
    """Horizontal capsule (cylinder + hemispherical ends) with its axis along +X: a *visual-proxy* float."""
    id: str
    centre: tuple
    length: float
    radius: float
    n_circ: int = 64
    n_axial: int = 12
    n_cap: int = 16

    def triangles(self):
        xs, rs = capsule_profile(self.length, self.radius, self.n_axial, self.n_cap)
        T = revolve_profile(xs, rs, self.n_circ)
        return T + np.asarray(self.centre, float)

    def analytic_volume(self):
        r, L = self.radius, self.length
        return np.pi * r * r * (L - 2 * r) + 4.0 / 3.0 * np.pi * r ** 3

    def with_resolution(self, n_circ, n_axial, n_cap):
        return CapsuleX(self.id, self.centre, self.length, self.radius, n_circ, n_axial, n_cap)


@dataclass
class FlofizX:
    """Flofiz-type pontoon float along X (flofiz.com plan, "mesures approximatives", via the EXO-01 component list):
    a cylinder Ø `diameter` × `body_length` closed by a flat disc at one end, and at the other end a `nose_length`
    sled nose whose top stays level with the cylinder top while its underside curves up to a point at the tip.
    The nose is modelled as rings of radius r(ξ) = R cos(π ξ / 2 L_n) whose centres rise so the top stays at +R
    (volume π R² L_n / 2). The moulded beam channel on top (38.7 cm wide, 5 cm deep) is NOT subtracted: it only
    matters once the float is submerged to within 5 cm of its top, which is flagged separately.
    `flat_end_x`: x of the flat end; `nose_dir`: +1 nose toward +x, -1 nose toward -x; `centre_yz`: (y, z) of the
    cylinder axis."""
    id: str
    flat_end_x: float
    nose_dir: int
    centre_yz: tuple
    diameter: float = 0.60
    body_length: float = 1.30
    nose_length: float = 0.30
    n_circ: int = 64
    n_axial: int = 12
    n_cap: int = 16

    @property
    def radius(self):
        return self.diameter / 2

    @property
    def length(self):
        return self.body_length + self.nose_length

    @property
    def centre(self):
        """Centre of the cylindrical body (used for display/inertia anchors and cache keys)."""
        return (self.flat_end_x + self.nose_dir * self.body_length / 2, self.centre_yz[0], self.centre_yz[1])

    @property
    def x_span(self):
        a, b = self.flat_end_x, self.flat_end_x + self.nose_dir * self.length
        return (min(a, b), max(a, b))

    def triangles(self):
        R, Lb, Ln = self.radius, self.body_length, self.nose_length
        # local frame: flat end at x=0, nose toward +x; cylinder axis at (y, z) = 0
        t = np.linspace(0.0, 1.0, self.n_cap + 1)[1:] * (np.pi / 2)      # nose rings (the last has r = 0: the tip)
        nose_x = Lb + Ln * (t / (np.pi / 2))
        nose_r = R * np.cos(t)
        nose_z = R - nose_r                                                  # ring centre rises: top stays at +R
        body_x = np.linspace(0.0, Lb, self.n_axial + 1)
        xs = np.concatenate([[0.0], body_x, nose_x])                        # leading 0-radius ring at x=0: flat disc
        rs = np.concatenate([[0.0], np.full(len(body_x), R), nose_r])
        zc = np.concatenate([[0.0], np.zeros(len(body_x)), nose_z])
        T = revolve_profile(xs, rs, self.n_circ, zc=zc)
        if self.nose_dir < 0:
            T = T * np.array([-1.0, 1.0, 1.0])
            T = T[:, [0, 2, 1], :]                                           # mirror flips the winding: restore outward normals
        return T + np.array([self.flat_end_x, self.centre_yz[0], self.centre_yz[1]])

    def analytic_volume(self):
        R = self.radius
        return np.pi * R * R * self.body_length + np.pi * R * R * self.nose_length / 2

    def with_resolution(self, n_circ, n_axial, n_cap):
        return FlofizX(self.id, self.flat_end_x, self.nose_dir, self.centre_yz, self.diameter, self.body_length,
                       self.nose_length, n_circ, n_axial, n_cap)


@dataclass
class MeshSurface:
    """A measured / imported closed surface (vertices (n,3), faces (m,3), outward normals, CAD metres).
    Used as-is by the hydrostatics and by the BEM (no re-tessellation): mesh it at the resolution you need."""
    id: str
    vertices: np.ndarray
    faces: np.ndarray
    source: str = "mesh"

    def triangles(self):
        return self.vertices[self.faces]

    def with_resolution(self, **kw):        # measured surfaces keep their own resolution
        return self

    @property
    def centre(self):
        return tuple((self.vertices.min(0) + self.vertices.max(0)) / 2)

    def check(self):
        """Closed (every edge shared by two faces, each directed edge once) and outward-oriented (signed volume > 0)."""
        F = self.faces
        de = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
        key = de[:, 0] * len(self.vertices) + de[:, 1]
        closed = len(np.unique(key)) == len(key) and np.isin(key, de[:, 1] * len(self.vertices) + de[:, 0]).all()
        vol = signed_volume(self.triangles())
        return dict(closed=bool(closed), outward=bool(vol > 0), volume_m3=float(vol), n_faces=int(len(F)))


def load_mesh_file(path, scale=1.0, translate=(0.0, 0.0, 0.0)):
    """Read a closed triangle mesh: .obj (v/f lines), .stl (ascii or binary) or .npz (vertices, faces).
    Quads are split; `scale` converts units (e.g. 0.001 for mm); `translate` is added after scaling (metres)."""
    from pathlib import Path as _P
    path = _P(path)
    ext = path.suffix.lower()
    if ext == ".npz":
        d = np.load(path, allow_pickle=False)
        V, F = np.asarray(d["vertices"], float), np.asarray(d["faces"], int)
    elif ext == ".obj":
        V, F = [], []
        for line in path.read_text().splitlines():
            t = line.split()
            if not t:
                continue
            if t[0] == "v":
                V.append([float(x) for x in t[1:4]])
            elif t[0] == "f":
                idx = [int(x.split("/")[0]) - 1 for x in t[1:]]
                for k in range(1, len(idx) - 1):
                    F.append([idx[0], idx[k], idx[k + 1]])
        V, F = np.array(V, float), np.array(F, int)
    elif ext == ".stl":
        raw = path.read_bytes()
        tris = None
        if not raw[:5].lower().startswith(b"solid") or b"facet" not in raw[:1000]:
            n = int.from_bytes(raw[80:84], "little")
            data = np.frombuffer(raw, dtype=np.dtype([("n", "<f4", 3), ("v", "<f4", (3, 3)), ("a", "<u2")]), count=n, offset=84)
            tris = data["v"].astype(float)
        else:
            vals = []
            for line in raw.decode(errors="ignore").splitlines():
                t = line.split()
                if t and t[0] == "vertex":
                    vals.append([float(x) for x in t[1:4]])
            tris = np.array(vals, float).reshape(-1, 3, 3)
        key = np.round(tris.reshape(-1, 3) / 1e-7).astype(np.int64)
        u, inv = np.unique(key, axis=0, return_inverse=True)
        V, F = u * 1e-7, inv.reshape(-1, 3)
    else:
        raise ValueError(f"unsupported mesh format {ext} (use .obj, .stl or .npz)")
    V = V * scale + np.asarray(translate, float)
    return V, F


def save_mesh_obj(path, vertices, faces):
    with open(path, "w") as f:
        for v in vertices:
            f.write(f"v {v[0]:.9f} {v[1]:.9f} {v[2]:.9f}\n")
        for t in faces:
            f.write(f"f {t[0] + 1} {t[1] + 1} {t[2] + 1}\n")


def signed_volume(tris):
    a, b, c = tris[:, 0], tris[:, 1], tris[:, 2]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def surfaces_from_config(cfg, resolution=None):
    out = []
    for s in cfg["buoyant_surfaces"]:
        if s["type"] == "capsule_x":
            kw = dict(resolution or {})
            out.append(CapsuleX(s["id"], tuple(s["centre_m"]), s["length_m"], s["radius_m"], **kw))
        elif s["type"] == "flofiz_x":
            kw = dict(resolution or {})
            out.append(FlofizX(s["id"], float(s["flat_end_x_m"]), int(s["nose_dir"]), (float(s["y_m"]), float(s["z_axis_m"])),
                               float(s.get("diameter_m", 0.60)), float(s.get("body_length_m", 1.30)),
                               float(s.get("nose_length_m", 0.30)), **kw))
        elif s["type"] == "mesh_file":
            # measured / CAD float geometry: {"id", "type": "mesh_file", "path", "scale" (1 for m, 0.001 for mm),
            # "translate_m" (optional), "units"}; closed outward-oriented triangle mesh in the EXO CAD frame
            from .config import ROOT
            path = s["path"] if str(s["path"]).startswith("/") else str(ROOT / s["path"])
            V, F = load_mesh_file(path, s.get("scale", 1.0), s.get("translate_m", (0.0, 0.0, 0.0)))
            ms = MeshSurface(s["id"], V, F, source=f"mesh_file {s['path']}")
            chk = ms.check()
            if not chk["closed"]:
                raise ValueError(f"{s['id']}: mesh {s['path']} is not closed / consistently oriented")
            if not chk["outward"]:
                ms = MeshSurface(s["id"], V, F[:, [0, 2, 1]], source=ms.source)
            out.append(ms)
        else:
            raise ValueError(f"unknown buoyant surface type {s['type']}")
    return out


# ------------------------------------------------------------------ rotations
def Rx(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def Ry(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


def attitude(phi, theta):
    """Body->world rotation for heel phi (about +x, right-handed) and trim theta (about +y, right-handed).
    Positive theta lowers the +X end of the body. R = Ry(theta) @ Rx(phi)."""
    return Ry(theta) @ Rx(phi)


# ------------------------------------------------------------------ clipping + integrals
def clip_below(tris):
    """Clip triangles (N,3,3) to z <= 0. Returns (wet_triangles, waterline_segments (M,2,3))."""
    tris = tris.copy()
    tris[:, :, 2][np.abs(tris[:, :, 2]) < 1e-12] = 0.0     # snap vertices lying on the waterline (robust classification)
    z = tris[:, :, 2]
    below = z <= 0.0
    nb = below.sum(1)
    wet = [tris[nb == 3]]
    segs = []

    # one vertex below
    idx = np.where(nb == 1)[0]
    if len(idx):
        T = tris[idx]
        i = np.argmax(below[idx], axis=1)
        r = np.arange(len(idx))
        Vi = T[r, i]
        Vj = T[r, (i + 1) % 3]
        Vk = T[r, (i + 2) % 3]
        tj = Vi[:, 2] / (Vi[:, 2] - Vj[:, 2])
        tk = Vi[:, 2] / (Vi[:, 2] - Vk[:, 2])
        Pij = Vi + tj[:, None] * (Vj - Vi)
        Pik = Vi + tk[:, None] * (Vk - Vi)
        Pij[:, 2] = 0.0
        Pik[:, 2] = 0.0
        wet.append(np.stack([Vi, Pij, Pik], 1))
        segs.append(np.stack([Pij, Pik], 1))

    # two vertices below
    idx = np.where(nb == 2)[0]
    if len(idx):
        T = tris[idx]
        i = np.argmax(~below[idx], axis=1)            # the vertex above water
        r = np.arange(len(idx))
        Vi = T[r, i]
        Vj = T[r, (i + 1) % 3]
        Vk = T[r, (i + 2) % 3]
        tj = Vi[:, 2] / (Vi[:, 2] - Vj[:, 2])
        tk = Vi[:, 2] / (Vi[:, 2] - Vk[:, 2])
        Pij = Vi + tj[:, None] * (Vj - Vi)
        Pki = Vi + tk[:, None] * (Vk - Vi)
        Pij[:, 2] = 0.0
        Pki[:, 2] = 0.0
        wet.append(np.stack([Pij, Vj, Vk], 1))
        wet.append(np.stack([Pij, Vk, Pki], 1))
        segs.append(np.stack([Pki, Pij], 1))
    wet = np.concatenate(wet, 0) if wet else np.zeros((0, 3, 3))
    segs = np.concatenate(segs, 0) if segs else np.zeros((0, 2, 3))
    return wet, segs


def _mean_prod(f, g):
    """Exact mean of f*g over a triangle for linear f,g given by vertex values (N,3)."""
    return ((f * g).sum(1) + f.sum(1) * g.sum(1)) / 12.0


def wet_integrals(tris_world):
    """Volume, volume-moments and waterplane properties of the part of the closed surface below z=0.

    Returns dict(V, B (3,), Awp, Sx, Sy, Ixx, Iyy, Ixy) with waterplane quantities about the world origin.
    """
    wet, segs = clip_below(tris_world)
    if len(wet) == 0:
        return dict(V=0.0, B=np.zeros(3), Awp=0.0, Sx=0.0, Sy=0.0, Ixx=0.0, Iyy=0.0, Ixy=0.0, n_wet=0)
    a, b, c = wet[:, 0], wet[:, 1], wet[:, 2]
    nvec = 0.5 * np.cross(b - a, c - a)            # outward area vector
    nz = nvec[:, 2]
    x, y, z = wet[:, :, 0], wet[:, :, 1], wet[:, :, 2]
    V = float((nz * z.mean(1)).sum())
    Mx = float((nz * _mean_prod(x, z)).sum())      # int x dV
    My = float((nz * _mean_prod(y, z)).sum())
    Mz = float((nz * 0.5 * _mean_prod(z, z)).sum())
    B = np.array([Mx, My, Mz]) / V if V > 0 else np.zeros(3)
    # waterplane (Green's theorem on oriented waterline segments)
    Awp = Sx = Sy = Ixx = Iyy = Ixy = 0.0
    if len(segs):
        x1, y1 = segs[:, 0, 0], segs[:, 0, 1]
        x2, y2 = segs[:, 1, 0], segs[:, 1, 1]
        cr = x1 * y2 - x2 * y1
        A = 0.5 * cr.sum()
        s = 1.0 if A >= 0 else -1.0
        Awp = s * A
        Sx = s * ((x1 + x2) * cr).sum() / 6.0                 # int x dA
        Sy = s * ((y1 + y2) * cr).sum() / 6.0                 # int y dA
        Ixx = s * ((y1 ** 2 + y1 * y2 + y2 ** 2) * cr).sum() / 12.0   # int y^2 dA
        Iyy = s * ((x1 ** 2 + x1 * x2 + x2 ** 2) * cr).sum() / 12.0   # int x^2 dA
        Ixy = s * ((x1 * y2 + 2 * x1 * y1 + 2 * x2 * y2 + x2 * y1) * cr).sum() / 24.0  # int xy dA
    return dict(V=V, B=B, Awp=Awp, Sx=Sx, Sy=Sy, Ixx=Ixx, Iyy=Iyy, Ixy=Ixy, n_wet=len(wet))


# ------------------------------------------------------------------ assembly
class BuoyantAssembly:
    """All buoyant surfaces as one rigid assembly, in the body (CAD) frame."""

    def __init__(self, surfaces):
        self.surfaces = list(surfaces)
        self.tris = [s.triangles() for s in self.surfaces]
        self.all_tris = np.ascontiguousarray(np.concatenate(self.tris, 0))
        self._flat = self.all_tris.reshape(-1, 3)                       # (3N, 3) view for fast transforms
        self._flat_each = [t.reshape(-1, 3) for t in self.tris]
        self.slices = np.cumsum([0] + [len(t) for t in self.tris])
        self.max_volume = sum(signed_volume(t) for t in self.tris)   # fully submerged
        self.z_extent_body = (float(self.all_tris[:, :, 2].min()), float(self.all_tris[:, :, 2].max()))

    def world_tris(self, R, G_body, zG, which=None):
        """Triangles in the world frame: w = R (p - G) + (0, 0, zG)  (COM horizontally at origin)."""
        flat = self._flat if which is None else self._flat_each[which]
        shift = np.array([0.0, 0.0, zG]) - np.asarray(R, float) @ np.asarray(G_body, float)
        return (flat @ np.asarray(R, float).T + shift).reshape(-1, 3, 3)

    def integrals(self, R, G_body, zG):
        return wet_integrals(self.world_tris(R, G_body, zG))

    def per_surface_volume(self, R, G_body, zG):
        return {s.id: wet_integrals(self.world_tris(R, G_body, zG, i))["V"] for i, s in enumerate(self.surfaces)}
