#!/usr/bin/env python3
"""
02b_run_ogr.py — put the same corpus through ogr2ogr and record what it says.

The comparison exists to show that the taxonomy and the corpus are not specific
to one converter. GDAL is the reference implementation of vector format
conversion, so if the method says something useful it has to say it about GDAL
too.

Fairness rules, fixed before the run and identical to those used for the
browser tool: default configuration, no verbosity flags, and everything the
tool writes to its standard streams is captured. GDAL says considerably more
with -debug ON, and that is exactly why it is not enabled: what is measured is
what an ordinary user sees.

Outputs work_ogr/reported.json in the same shape stage 03 already consumes, and
the converted files under work_ogr/<fixture>/<target>/.

Usage: python3 02b_run_ogr.py
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path


def resolve(cmd):
    """Absolute path to an executable, applying PATHEXT on Windows."""
    return shutil.which(cmd) or shutil.which(cmd + ".exe")

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
FIXX = HERE / "fixtures_x"
WORK = HERE / "work_ogr"

OGR = None

DRIVER = {
    "shp": "ESRI Shapefile",
    "dxf": "DXF",
    "geojson": "GeoJSON",
    "kml": "KML",
    "csv": "CSV",
}


def fixtures():
    out = []
    for p in sorted(FIX.iterdir()):
        if p.suffix == ".zip":
            continue
        out.append((p.stem[:3], p.name, p))
    for d in sorted(FIXX.iterdir()) if FIXX.exists() else []:
        shp = next(d.glob("*.shp"), None)
        if shp:
            out.append((d.name[:3], d.name, shp))
    return sorted(out, key=lambda t: t[0])


def run(src, target, outdir):
    outdir.mkdir(parents=True, exist_ok=True)
    if target == "shp":
        dst = outdir
    else:
        ext = {"dxf": ".dxf", "geojson": ".geojson", "kml": ".kml", "csv": ".csv"}[target]
        dst = outdir / (src.stem + ext)
    cmd = [OGR, "-f", DRIVER[target], str(dst), str(src)]
    p = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    msgs = [ln.strip() for ln in (p.stdout + p.stderr).splitlines() if ln.strip()]
    return msgs, p.returncode


def main():
    global OGR
    OGR = resolve("ogr2ogr")
    if OGR is None:
        print("ogr2ogr not found on PATH", file=sys.stderr)
        return 1
    ver = subprocess.run([OGR, "--version"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout.strip()

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)

    results = []
    for fid, name, src in fixtures():
        for target in DRIVER:
            outdir = WORK / fid / target
            msgs, code = run(src, target, outdir)
            produced = sorted(p.name for p in outdir.rglob("*") if p.is_file())
            results.append({
                "fixture": fid, "file": name, "target": target,
                "src": None, "features": 0, "readError": None,
                "writeError": None if code == 0 else f"exit {code}",
                "outputs": produced,
                "messages": msgs,
                "reported": [],          # filled by the mapping in stage 03
            })

    (WORK / "reported.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

    total = sum(len(r["messages"]) for r in results)
    silent = sum(1 for r in results if not r["messages"])
    print(f"{ver}")
    print(f"conversions: {len(results)}   messages: {total}   "
          f"conversions with no message: {silent}")
    print(f"\nwritten to {WORK}/reported.json")

    # a first look at the message vocabulary, which is what the mapping needs
    seen = {}
    for r in results:
        for m in r["messages"]:
            head, _, rest = m.partition(":")
            key = f"{head}: {' '.join(rest.split()[:6])}" if rest else head
            seen[key] = seen.get(key, 0) + 1
    print("\ndistinct message stems:")
    for k, v in sorted(seen.items(), key=lambda x: -x[1]):
        print(f"  {v:4d}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
