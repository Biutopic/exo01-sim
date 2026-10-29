"""Mass, centre of mass and inertia tensor from explicitly assigned component properties.

Rules (see ASSUMPTIONS.md):
* each mass-bearing PARENT counts exactly once; child meshes never carry mass;
* mass, COM and inertia are only ever taken from the configuration. Anything
  that is `null` stays unknown and is reported, never replaced by a guess;
* assembly inertia about the assembly COM = sum( I_i(own, about its COM)
  + m_i (|d|^2 1 - d d^T) ), d = COM_i - COM_assembly   (parallel-axis theorem).
  Component bodies are axis-aligned (no component rotation).
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# posture presets: whole-body COM height above the surface the person occupies [m].
# ILLUSTRATIVE anthropometric values; every one is editable per person.
POSTURE_COM_HEIGHT_M = {"standing": 1.00, "seated_on_chair": 0.70, "seated_on_deck": 0.40}


class MissingInput(Exception):
    """Raised when a requested quantity needs inputs that are null in the configuration."""

    def __init__(self, what, missing):
        self.what = what
        self.missing = list(missing)
        super().__init__(f"{what} not computed; missing: {', '.join(self.missing)}")


# ---------------------------------------------------------------- inertia models
def inertia_point(m, dims=None):
    return np.zeros((3, 3))


def inertia_solid_box(m, dims):
    a, b, c = dims
    return np.diag([m / 12 * (b * b + c * c), m / 12 * (a * a + c * c), m / 12 * (a * a + b * b)])


def inertia_shell_box(m, dims):
    """Thin-walled closed box, uniform surface density, about its centre."""
    a, b, c = dims
    faces = [  # (area, normal axis, in-plane dims along the two other axes)
        (b * c, 0, (b, c)), (a * c, 1, (a, c)), (a * b, 2, (a, b)),
    ]
    S = 2 * sum(f[0] for f in faces)
    sigma = m / S
    I = np.zeros((3, 3))
    half = (a / 2, b / 2, c / 2)
    for area, n, (p, q) in faces:
        mp = sigma * area
        axes = [i for i in range(3) if i != n]       # in-plane axes u,v with extents p,q
        own = np.zeros(3)
        own[axes[0]] = mp * q * q / 12               # rotation about u spans the v-extent
        own[axes[1]] = mp * p * p / 12
        own[n] = mp * (p * p + q * q) / 12
        for sgn in (+1, -1):
            d = np.zeros(3)
            d[n] = sgn * half[n]
            I += np.diag(own) + mp * (d @ d * np.eye(3) - np.outer(d, d))
    return I


def inertia_cylinder_shell_x(m, dims):
    L, r = dims
    return np.diag([m * r * r, m * (r * r / 2 + L * L / 12), m * (r * r / 2 + L * L / 12)])


INERTIA_MODELS = {
    "point": inertia_point,
    "solid_box": inertia_solid_box,
    "shell_box": inertia_shell_box,
    "cylinder_shell_x": inertia_cylinder_shell_x,
}


# ---------------------------------------------------------------- items
@dataclass
class Item:
    id: str
    name: str
    category: str
    mass: float | None
    com: np.ndarray | None
    inertia_model: str | None = None
    inertia_dims: tuple | None = None
    mass_status: str = "unknown"
    com_status: str = "missing_input"
    inertia_status: str = "missing_input"
    extra: dict = field(default_factory=dict)

    def own_inertia(self):
        if self.mass is None or self.inertia_model is None:
            return None
        fn = INERTIA_MODELS[self.inertia_model]
        return fn(self.mass, self.inertia_dims)


def items_from_config(cfg) -> list[Item]:
    """Build mass items (components + people) from a resolved configuration."""
    items = []
    for c in cfg["components"]:
        com = None if c.get("com_m") is None else np.asarray(c["com_m"], float)
        inertia = c.get("inertia")
        items.append(Item(
            id=c["id"], name=c.get("name", c["id"]), category=c.get("category", "other"),
            mass=c.get("mass_kg"), com=com,
            inertia_model=None if inertia is None else inertia["model"],
            inertia_dims=None if inertia is None else tuple(inertia.get("dims_m") or ()),
            mass_status=c.get("mass_source", "unknown"), com_status=c.get("com_source", "missing_input"),
            inertia_status="missing_input" if inertia is None else inertia.get("source", "assumption"),
        ))
    for p in cfg.get("people", []):
        surf = cfg["standing_surfaces"][p["surface"]]
        h = p.get("com_height_m")
        if h is None:
            h = POSTURE_COM_HEIGHT_M[p["posture"]]
        com = None
        if p.get("x_m") is not None and p.get("y_m") is not None and p.get("mass_kg") is not None:
            com = np.array([p["x_m"], p["y_m"], surf["z_m"] + h])
        items.append(Item(
            id=p["id"], name=p.get("name", p["id"]), category="person", mass=p.get("mass_kg"), com=com,
            inertia_model="point", inertia_dims=(), mass_status=p.get("mass_source", "illustrative"),
            com_status="illustrative", inertia_status="assumption",
            extra=dict(posture=p["posture"], surface=p["surface"], com_height_m=h),
        ))
    return items


def validate_people(cfg):
    """Return list of (level, message). People need a COM strictly above the occupied surface and inside it."""
    issues = []
    for p in cfg.get("people", []):
        surf = cfg["standing_surfaces"].get(p.get("surface"))
        if surf is None:
            issues.append(("error", f"{p['id']}: unknown surface '{p.get('surface')}'"))
            continue
        h = p.get("com_height_m", POSTURE_COM_HEIGHT_M.get(p.get("posture")))
        if h is None or h <= 0:
            issues.append(("error", f"{p['id']}: body COM must be above the surface (height {h})"))
        if p.get("mass_kg") is None or p["mass_kg"] <= 0:
            issues.append(("error", f"{p['id']}: mass must be a positive number"))
        x, y = p.get("x_m"), p.get("y_m")
        if x is None or y is None:
            issues.append(("error", f"{p['id']}: position missing"))
        else:
            (x0, x1), (y0, y1) = surf["x_range_m"], surf["y_range_m"]
            if not (x0 <= x <= x1 and y0 <= y <= y1):
                issues.append(("error", f"{p['id']}: ({x:.2f},{y:.2f}) lies outside surface '{p['surface']}' "
                                         f"x[{x0},{x1}] y[{y0},{y1}]"))
    return issues


# ---------------------------------------------------------------- assembly properties
def mass_properties(items: list[Item], strict=True):
    """Total mass, COM and inertia tensor (about COM, body axes) of the assembly.

    Returns a dict. Quantities that cannot be computed are None and the reasons
    are listed in `missing`. With strict=True, raises MissingInput if the COM is not computable.
    """
    missing_mass = [i.id for i in items if i.mass is None]
    missing_com = [i.id for i in items if i.com is None]
    missing_inertia = [i.id for i in items if i.inertia_model is None]
    known = [i for i in items if i.mass is not None]
    total_known = float(sum(i.mass for i in known))
    out = dict(total_listed_mass_kg=total_known, n_items=len(items),
               missing_mass=missing_mass, missing_com=missing_com, missing_inertia=missing_inertia,
               total_mass_kg=None, com_m=None, inertia_com_kgm2=None, by_item=[])
    out["by_item"] = [dict(id=i.id, category=i.category, mass_kg=i.mass,
                           com_m=None if i.com is None else i.com.tolist(),
                           com_status=i.com_status, inertia_model=i.inertia_model,
                           inertia_status=i.inertia_status) for i in items]
    if not missing_mass:
        out["total_mass_kg"] = total_known
    if not missing_mass and not missing_com:
        M = total_known
        com = sum(i.mass * i.com for i in items) / M
        out["com_m"] = com.tolist()
        if not missing_inertia:
            I = np.zeros((3, 3))
            for i in items:
                d = i.com - com
                I += i.own_inertia() + i.mass * (d @ d * np.eye(3) - np.outer(d, d))
            out["inertia_com_kgm2"] = I.tolist()
    elif strict:
        raise MissingInput("centre of mass", [f"COM of {x}" for x in missing_com] + [f"mass of {x}" for x in missing_mass])
    return out


def aggregate_by_category(items):
    cats = {}
    for i in items:
        if i.mass is not None:
            cats[i.category] = cats.get(i.category, 0.0) + i.mass
    return cats


def boat_items_from_config(cfg) -> list[Item]:
    """Mass items of the host boat (its own frame): the whole-boat reference mass + people on the boat."""
    hb = cfg["host_boat"]
    com = None if hb.get("com_m") is None else np.asarray(hb["com_m"], float)
    inertia = hb.get("inertia")
    items = [Item(id=hb["id"], name=hb.get("name", hb["id"]), category="host_boat", mass=hb.get("mass_kg"), com=com,
                  inertia_model=None if inertia is None else inertia["model"],
                  inertia_dims=None if inertia is None else tuple(inertia.get("dims_m") or ()),
                  mass_status=hb.get("mass_source", "unknown"), com_status=hb.get("com_source", "missing_input"),
                  inertia_status="missing_input" if inertia is None else inertia.get("source", "assumption"))]
    items += items_from_config({"components": [], "people": hb.get("people", []), "standing_surfaces": hb["standing_surfaces"]})
    return items
