"""Configuration / scenario loading, resolution and validation."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from .mass import validate_people

ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "configs"
SCENARIO_DIR = ROOT / "scenarios"


def load_config(name_or_path):
    p = Path(name_or_path)
    if not p.exists():
        p = CONFIG_DIR / f"{name_or_path}.json"
    cfg = json.loads(p.read_text())
    if cfg.get("schema") != "exo01_config_v1":
        raise ValueError("unsupported config schema")
    return cfg


def load_scenario(name_or_path):
    p = Path(name_or_path)
    if not p.exists():
        p = SCENARIO_DIR / f"{name_or_path}.json"
    sc = json.loads(p.read_text())
    if sc.get("schema") != "exo01_scenario_v1":
        raise ValueError("unsupported scenario schema")
    return sc


def list_scenarios():
    return sorted(p.stem for p in SCENARIO_DIR.glob("*.json"))


def _deep_merge(dst, src):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            _deep_merge(dst[k], v)
        else:
            dst[k] = copy.deepcopy(v)
    return dst


def resolve(cfg, overrides=None):
    """Apply scenario overrides to a configuration; returns a new, fully-resolved config.

    overrides = {"components": {id: {field: value}}, "people": [...], "environment": {...},
                 "buoyant_surfaces": {id: {...}}}. `people` replaces the list; other keys merge.
    Moving a component (com_m) also moves its COM provenance to 'user_edit'.
    """
    out = copy.deepcopy(cfg)
    ov = overrides or {}
    by_id = {c["id"]: c for c in out["components"]}
    for cid, fields in (ov.get("components") or {}).items():
        if cid not in by_id:
            if "mass_kg" in fields and "com_m" in fields:
                # a new item (ballast, payload, counterweight what-if): point inertia unless given
                item = dict(id=cid, name=fields.get("name", cid), category=fields.get("category", "payload"), mass_kg=float(fields["mass_kg"]),
                            mass_source=fields.get("mass_source", "user_edit"), com_m=list(fields["com_m"]), com_source=fields.get("com_source", "user_edit"),
                            inertia=fields.get("inertia", {"model": "point", "source": "assumption"}))
                out["components"].append(item); by_id[cid] = item
                continue
            raise KeyError(f"unknown component {cid} (a new item needs mass_kg and com_m)")
        for k, v in fields.items():
            if k == "inertia" and isinstance(v, dict) and by_id[cid].get("inertia"):
                by_id[cid]["inertia"] = _deep_merge(by_id[cid]["inertia"], v)
            else:
                by_id[cid][k] = copy.deepcopy(v)
        if "com_m" in fields:
            by_id[cid]["com_source"] = "user_edit" if out["mode"] == "exploratory" else "user_edit"
        if "mass_kg" in fields:
            by_id[cid]["mass_source"] = "user_edit"
    if "people" in ov:
        out["people"] = copy.deepcopy(ov["people"])
    if "environment" in ov:
        _deep_merge(out["environment"], ov["environment"])
    if "buoyant_surfaces" in ov:
        sby = {s["id"]: s for s in out["buoyant_surfaces"]}
        for sid, fields in ov["buoyant_surfaces"].items():
            sby[sid].update(copy.deepcopy(fields))
    if "host_boat" in ov and ov["host_boat"] is not None:
        if out.get("host_boat") is None:
            out["host_boat"] = copy.deepcopy(ov["host_boat"])
        else:
            hb = ov["host_boat"]
            if "lines" in hb:                                  # lines list replaces
                out["host_boat"]["lines"] = copy.deepcopy(hb["lines"])
            if "people" in hb:
                out["host_boat"]["people"] = copy.deepcopy(hb["people"])
            _deep_merge(out["host_boat"], {k: v for k, v in hb.items() if k not in ("lines", "people")})
            if "com_m" in hb:
                out["host_boat"]["com_source"] = "user_edit"
            if "mass_kg" in hb:
                out["host_boat"]["mass_source"] = "user_edit"
    if "propulsion" in ov and ov["propulsion"] is not None:
        out["propulsion"] = _deep_merge(copy.deepcopy(out.get("propulsion") or {}), ov["propulsion"])
    if "visual_overrides" in ov:
        out["visual_overrides"] = {**(out.get("visual_overrides") or {}), **copy.deepcopy(ov["visual_overrides"])}
    out["overrides_applied"] = copy.deepcopy(ov)
    return out


def resolve_scenario(scenario):
    base = load_config(scenario["base"])
    cfg = resolve(base, scenario.get("overrides"))
    cfg["scenario_name"] = scenario.get("name")
    cfg["scenario_title"] = scenario.get("title")
    return cfg


def validate(cfg):
    """Structural validation; returns list of (level, message)."""
    import math
    issues = []

    def finite(v):
        try:
            return v is None or (isinstance(v, (int, float)) and math.isfinite(float(v)))
        except (TypeError, ValueError):
            return False
    ids = [c["id"] for c in cfg["components"]]
    if len(ids) != len(set(ids)):
        issues.append(("error", "duplicate component ids (mass would be double counted)"))
    for c in cfg["components"]:
        if not finite(c.get("mass_kg")) or (c.get("mass_kg") is not None and c["mass_kg"] < 0):
            issues.append(("error", f"{c['id']}: mass must be a finite non-negative number"))
        com = c.get("com_m")
        if com is not None and (len(com) != 3 or not all(finite(v) and v is not None for v in com)):
            issues.append(("error", f"{c['id']}: COM must be three finite numbers"))
    env = cfg.get("environment") or {}
    if env.get("rho_kg_m3") is not None and not (finite(env["rho_kg_m3"]) and 500 < env["rho_kg_m3"] < 1500):
        issues.append(("error", "water density must be a finite number between 500 and 1500 kg/m3"))
    if env.get("water_depth_m") is not None and not (finite(env["water_depth_m"]) and env["water_depth_m"] > 0.3):
        issues.append(("error", "water depth must be blank (infinite) or a finite number > 0.3 m"))
    prop = cfg.get("propulsion") or {}
    if prop.get("thrust_fraction") is not None and not (finite(prop["thrust_fraction"]) and 0 <= prop["thrust_fraction"] <= 1):
        issues.append(("error", "thrust fraction must be between 0 and 1"))
    for ln in ((cfg.get("host_boat") or {}).get("lines") or []):
        for key in ("exo_point_m", "boat_point_m"):
            pt = ln.get(key)
            if pt is None or len(pt) != 3 or not all(finite(v) and v is not None for v in pt):
                issues.append(("error", f"line {ln.get('id')}: {key} must be three finite numbers"))
        for key in ("stiffness_N_per_m", "pretension_N"):
            if ln.get(key) is not None and not (finite(ln[key]) and ln[key] >= 0):
                issues.append(("error", f"line {ln.get('id')}: {key} must be a finite non-negative number"))
    ld = (cfg.get("host_boat") or {}).get("line_defaults") or {}
    for key in ("stiffness_N_per_m", "pretension_N"):
        if ld.get(key) is not None and not (finite(ld[key]) and ld[key] >= 0):
            issues.append(("error", f"line defaults: {key} must be a finite non-negative number"))
        if c.get("inertia") and c["inertia"]["model"] != "point" and not c["inertia"].get("dims_m"):
            issues.append(("error", f"{c['id']}: inertia model needs dims_m"))
    sids = {s["component_id"] for s in cfg["buoyant_surfaces"]}
    if not sids <= set(ids):
        issues.append(("error", "buoyant surface refers to unknown component"))
    issues += validate_people(cfg)
    hb = cfg.get("host_boat")
    if hb is None or not hb.get("included", False):
        issues.append(("info", "no host boat: EXO-only case; combined-vessel claims are not supported"))
    else:
        issues += validate_people({"people": hb.get("people", []), "standing_surfaces": hb["standing_surfaces"]})
        if hb.get("mass_kg") is None or hb["mass_kg"] <= 0:
            issues.append(("error", "host boat mass must be positive"))
    return issues
