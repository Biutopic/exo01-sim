"""Reader/auditor for the EXO-01 revision-3 reference package.

* GLB geometry is metres. Child nodes are already in CAD axes (X rear->front,
  Y transverse, Z up); the ONLY axis conversion is the root node's -90 deg
  rotation about X, giving glTF Y-up:  (x,y,z)_CAD -> (x, z, -y)_glTF.
  This module reads that rotation from the file and exposes explicit
  cad<->gltf conversions so the conversion is applied exactly once.
* STEP is millimetres (unit read from the file header, not assumed).
* Mass is read ONLY from the parent component nodes (`mass_kg`); child meshes
  carry `mass_owner`/`mass_is_in_parent` and are never summed.
"""
from __future__ import annotations

import json
import re
import struct
from pathlib import Path

import numpy as np

_CT = {5126: "f4", 5123: "u2", 5125: "u4", 5121: "u1"}
_NC = {"SCALAR": 1, "VEC2": 2, "VEC3": 3, "VEC4": 4}


def quat_to_matrix(q):
    x, y, z, w = q
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
    ])


class Reference:
    """Parsed revision-3 reference package."""

    def __init__(self, folder):
        self.folder = Path(folder)
        self.glb_path = self.folder / "EXO01_reference.glb"
        self.meta = json.loads((self.folder / "EXO01_mass_metadata.json").read_text())
        self.params = json.loads((self.folder / "parameters.json").read_text())
        self.artifact_validation = json.loads((self.folder / "artifact_validation.json").read_text())
        self._read_glb()

    # ------------------------------------------------------------------ GLB
    def _read_glb(self):
        b = self.glb_path.read_bytes()
        magic, version, length = struct.unpack("<4sII", b[:12])
        if magic != b"glTF" or version != 2 or length != len(b):
            raise ValueError("not a valid glTF 2.0 binary")
        cl, ctype = struct.unpack("<II", b[12:20])
        self.gltf = json.loads(b[20:20 + cl])
        off = 20 + cl
        bl, _ = struct.unpack("<II", b[off:off + 8])
        self.bin = b[off + 8:off + 8 + bl]
        self.nodes = self.gltf["nodes"]
        self.root_index = self.gltf["scenes"][self.gltf["scene"]]["nodes"][0]
        root = self.nodes[self.root_index]
        # The root's rotation is the single CAD(Z-up) -> glTF(Y-up) conversion.
        self.R_cad_to_gltf = quat_to_matrix(root["rotation"]) if "rotation" in root else np.eye(3)
        self.child_has_own_transform = [
            i for i, n in enumerate(self.nodes)
            if i != self.root_index and any(k in n for k in ("translation", "rotation", "scale", "matrix"))
        ]

    def cad_to_gltf(self, p):
        return np.asarray(p, float) @ self.R_cad_to_gltf.T

    def gltf_to_cad(self, p):
        return np.asarray(p, float) @ self.R_cad_to_gltf

    def _accessor(self, i):
        a = self.gltf["accessors"][i]
        bv = self.gltf["bufferViews"][a["bufferView"]]
        n = _NC[a["type"]]
        arr = np.frombuffer(self.bin, dtype=_CT[a["componentType"]], count=a["count"] * n,
                            offset=bv.get("byteOffset", 0) + a.get("byteOffset", 0))
        return arr.reshape(-1, n) if n > 1 else arr

    def mesh_triangles(self, node_index):
        """Welded (V, F) of a node's mesh, in CAD metres (child coordinates)."""
        prim = self.gltf["meshes"][self.nodes[node_index]["mesh"]]["primitives"][0]
        V = self._accessor(prim["attributes"]["POSITION"]).astype(float)
        if "indices" in prim:
            F = self._accessor(prim["indices"]).reshape(-1, 3).astype(int)
        else:
            F = np.arange(len(V)).reshape(-1, 3)
        key = np.round(V * 1e6).astype(np.int64)
        u, inv = np.unique(key, axis=0, return_inverse=True)
        return u / 1e6, inv.reshape(-1)[F.ravel()].reshape(-1, 3)

    # ------------------------------------------------------- register / mass
    def component_nodes(self):
        """Parent nodes that carry their own mass (one per mass-bearing group)."""
        return {n["extras"]["component_id"]: i for i, n in enumerate(self.nodes)
                if "extras" in n and "component_id" in n["extras"]}

    def children_of(self, idx):
        return self.nodes[idx].get("children", [])

    def glb_mass_register(self):
        out = {}
        for cid, i in self.component_nodes().items():
            e = self.nodes[i]["extras"]
            out[cid] = dict(mass_kg=e.get("mass_kg"), category=e.get("category"),
                            node=i, n_children=len(self.children_of(i)),
                            preview_anchor_m=e.get("preview_anchor_m"),
                            installed_centre_of_mass_m=e.get("installed_centre_of_mass_m"),
                            mass_status=e.get("mass_status"))
        return out

    def stray_mass_keys(self):
        """Nodes that are NOT component parents but carry a mass_kg (double-count risk)."""
        parents = set(self.component_nodes().values())
        return [i for i, n in enumerate(self.nodes)
                if i not in parents and "mass_kg" in (n.get("extras") or {})]

    def total_listed_mass(self):
        """Sum each mass-bearing parent exactly once."""
        return float(sum(v["mass_kg"] for v in self.glb_mass_register().values()))

    def component_bounds_cad(self, cid):
        """Axis-aligned bounds (m, CAD) of all child meshes of one component."""
        i = self.component_nodes()[cid]
        pts = []
        for c in self.children_of(i):
            if "mesh" in self.nodes[c]:
                pts.append(self.mesh_triangles(c)[0])
        P = np.vstack(pts)
        return P.min(0), P.max(0)

    def subpart_bounds_cad(self, cid, name_prefix):
        i = self.component_nodes()[cid]
        pts = [self.mesh_triangles(c)[0] for c in self.children_of(i)
               if "mesh" in self.nodes[c] and self.nodes[c]["name"].startswith(name_prefix)]
        P = np.vstack(pts)
        return P.min(0), P.max(0)

    def model_bounds_cad(self):
        pts = []
        for i, n in enumerate(self.nodes):
            if "mesh" in n:
                pts.append(self.mesh_triangles(i)[0])
        P = np.vstack(pts)
        return P.min(0), P.max(0)

    def float_surface_params(self):
        """Float proxy bounds from the GLB (x-span, y-centre, radius, z-centre)."""
        out = {}
        for cid, i in self.component_nodes().items():
            if not cid.startswith("FLOAT"):
                continue
            c = [c for c in self.children_of(i) if "mesh" in self.nodes[c]][0]
            V, F = self.mesh_triangles(c)
            lo, hi = V.min(0), V.max(0)
            vol = float(np.einsum("ij,ij->i", V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum() / 6)
            out[cid] = dict(lo=lo, hi=hi, centre=(lo + hi) / 2, length=hi[0] - lo[0],
                            diameter_y=hi[1] - lo[1], diameter_z=hi[2] - lo[2], tessellated_volume_m3=vol)
        return out


# -------------------------------------------------------------------- STEP
_UNIT_RE = re.compile(r"SI_UNIT\(\s*(\.MILLI\.)?\s*,\s*\.METRE\.\s*\)", re.I)
_PT_RE = re.compile(r"CARTESIAN_POINT\s*\(\s*'[^']*'\s*,\s*\(\s*([^)]*)\)\s*\)", re.I)


def step_units_and_extent(path):
    """Return (length_unit_text, scale_to_m, (min_xyz_m, max_xyz_m)) read from the STEP text.

    Extent is from CARTESIAN_POINT entries (a plausibility bound, not an exact
    B-rep bounding box: placements of circles/axes are included).
    """
    txt = Path(path).read_text(errors="ignore")
    milli = bool(re.search(r"SI_UNIT\(\s*\.MILLI\.\s*,\s*\.METRE\.\s*\)", txt, re.I))
    metre_only = bool(re.search(r"SI_UNIT\(\s*\$\s*,\s*\.METRE\.\s*\)", txt, re.I))
    scale = 1e-3 if milli else (1.0 if metre_only else None)
    pts = []
    for m in _PT_RE.finditer(txt):
        try:
            v = [float(s) for s in m.group(1).split(",")]
        except ValueError:
            continue
        if len(v) == 3:
            pts.append(v)
    P = np.array(pts)
    return ("mm" if milli else "m" if metre_only else "unknown"), scale, (P.min(0) * scale, P.max(0) * scale)
