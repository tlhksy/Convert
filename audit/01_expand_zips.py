#!/usr/bin/env python3
"""
01_expand_zips.py — expand the zipped fixtures into loose members.

Archive packaging is not what this audit measures, so the ZIP module is stubbed
during stage 02 and the shapefile members are passed to the tool individually.

Usage: python3 01_expand_zips.py [--dir fixtures] [--out fixtures_x]
"""
import argparse
import zipfile
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("--dir", default="fixtures")
ap.add_argument("--out", default="fixtures_x")
a = ap.parse_args()

src, out = Path(a.dir), Path(a.out)
out.mkdir(parents=True, exist_ok=True)
n = 0
for z in sorted(src.glob("*.zip")):
    d = out / z.stem
    d.mkdir(exist_ok=True)
    with zipfile.ZipFile(z) as f:
        f.extractall(d)
    print(f"{z.name} -> {sorted(p.name for p in d.iterdir())}")
    n += 1
print(f"{n} archives expanded")
