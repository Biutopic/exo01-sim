"""Build the distributable zip: code, data, configs, docs, and the BEM cache files referenced by results/cache/pose_index.json."""
import json
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1] if len(sys.argv) > 1 else ROOT.parent / "EXO01_simulation_v0.4.zip")
skip_dirs = {"results", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
idx = ROOT / "results" / "cache" / "pose_index.json"
cache_files = {"pose_index.json"}
if idx.exists():
    for e in json.loads(idx.read_text()):
        cache_files |= set(e.get("files", []))
n = 0
with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
    for p in sorted(ROOT.rglob("*")):
        rel = p.relative_to(ROOT)
        if p.is_dir() or any(part in skip_dirs for part in rel.parts[:-1]) or rel.parts[0] in skip_dirs:
            continue
        if p.suffix in (".pyc",):
            continue
        z.write(p, Path("exo01_sim") / rel); n += 1
    for name in sorted(cache_files):
        p = ROOT / "results" / "cache" / name
        if p.exists():
            z.write(p, Path("exo01_sim") / "results" / "cache" / name); n += 1
    for name in ("comparison", "optimisation", "verification"):
        d = ROOT / "results" / name
        if d.exists() and (d / ".fresh").exists():          # only outputs regenerated with this version (touch results/<name>/.fresh)
            for p in sorted(d.glob("*")):
                if p.is_file():
                    z.write(p, Path("exo01_sim") / "results" / name / p.name); n += 1
print(out, f"{out.stat().st_size / 1e6:.1f} MB, {n} files, cache files {len(cache_files)}")
