"""Remove BEM cache files that results/cache/pose_index.json no longer references (stale poses from earlier versions).

    python scripts/prune_cache.py                   # report only
    python scripts/prune_cache.py --apply           # delete the unreferenced files
    python scripts/prune_cache.py --apply --stage   # ... and git add -f the referenced ones (results/cache/* is git-ignored)

Keeps the repository / package to the files the interface can actually find through the pose index.
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
cache = ROOT / "results" / "cache"
idx = cache / "pose_index.json"
keep = {"pose_index.json"}
if idx.exists():
    for e in json.loads(idx.read_text()):
        keep |= set(e.get("files", []))
stale = sorted(p for p in cache.iterdir() if p.is_file() and p.name not in keep)
size = sum(p.stat().st_size for p in stale)
print(f"{len(keep) - 1} referenced files, {len(stale)} unreferenced ({size / 1e6:.1f} MB)")
if "--apply" in sys.argv:
    for p in stale:
        p.unlink()
    print("deleted")
if "--stage" in sys.argv:
    files = [str(cache / n) for n in sorted(keep) if (cache / n).exists()]
    subprocess.run(["git", "add", "-f", "--"] + files, cwd=ROOT, check=True)
    print(f"staged {len(files)} cache files")
