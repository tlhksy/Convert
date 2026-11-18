#!/usr/bin/env python3
"""
02c_run_mapshaper.py — put the same corpus through mapshaper.

A third converter is included because two cannot show whether the procedure
generalises, and because one of the first two was written by the author of this
study. mapshaper is independent of both, is widely used for exactly the
conversions in this corpus, and sits between them in design: a command-line
tool like GDAL, but written for interactive cartographic work rather than for
pipelines.

The same fairness rules apply: default configuration, no verbosity flags,
everything written to the standard streams is captured. mapshaper writes its
ordinary progress lines to the same stream as its warnings, so lines that
merely report a file being written are filtered by an explicit list rather than
by guesswork about what looks important.

Usage: python3 02c_run_mapshaper.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def resolve(cmd):
    """Absolute path to an executable.

    On Windows a globally installed npm package is a .cmd shim, which
    subprocess does not locate from the bare name the way a shell would.
    shutil.which applies PATHEXT and returns the real file.
    """
    return shutil.which(cmd) or shutil.which(cmd + ".cmd")

HERE = Path(__file__).resolve().parent
FIX = HERE / "fixtures"
FIXX = HERE / "fixtures_x"
WORK = HERE / "work_ms"

# Output file name per target; mapshaper infers the format from the extension.
TARGET_EXT = {
    "shp": "out.shp",
    "geojson": "out.json",
    "csv": "out.csv",
    # mapshaper writes TopoJSON and SVG but neither DXF nor KML, so those two
    # targets are recorded as unsupported rather than scored as losses.
}
UNSUPPORTED = ["dxf", "kml"]

MAPSHAPER = None

# Lines that report progress rather than a consequence of the conversion.
NOISE = [
    r"^\[o\] Wrote ",
    r"^\[i\] ",
    r"^Wrote ",
]


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
    dst = outdir / TARGET_EXT[target]
    p = subprocess.run([MAPSHAPER, str(src), "-o", str(dst)],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    lines = [ln.strip() for ln in (p.stdout + p.stderr).splitlines() if ln.strip()]
    msgs = [ln for ln in lines if not any(re.search(n, ln) for n in NOISE)]
    return msgs, p.returncode


def main():
    global MAPSHAPER
    MAPSHAPER = resolve("mapshaper")
    if MAPSHAPER is None:
        print("mapshaper not found on PATH", file=sys.stderr)
        return 1
    ver = subprocess.run([MAPSHAPER, "--version"], capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout.strip()

    shutil.rmtree(WORK, ignore_errors=True)
    WORK.mkdir(parents=True)

    results = []
    for fid, name, src in fixtures():
        for target in list(TARGET_EXT) + UNSUPPORTED:
            if target in UNSUPPORTED:
                results.append({
                    "fixture": fid, "file": name, "target": target,
                    "src": None, "features": 0, "readError": None,
                    "writeError": "target not supported by this converter",
                    "outputs": [], "messages": [], "reported": [],
                    "unsupported": True,
                })
                continue
            outdir = WORK / fid / target
            msgs, code = run(src, target, outdir)
            produced = sorted(p.name for p in outdir.rglob("*") if p.is_file())
            results.append({
                "fixture": fid, "file": name, "target": target,
                "src": None, "features": 0, "readError": None,
                "writeError": None if code == 0 else f"exit {code}",
                "outputs": produced, "messages": msgs, "reported": [],
                "unsupported": False,
            })

    (WORK / "reported.json").write_text(json.dumps(results, indent=1), encoding="utf-8")

    scored = [r for r in results if not r["unsupported"]]
    print(f"mapshaper {ver}")
    print(f"conversions attempted: {len(scored)}   "
          f"targets not supported: {len(results) - len(scored)}")
    print(f"messages: {sum(len(r['messages']) for r in scored)}   "
          f"conversions with no message: {sum(1 for r in scored if not r['messages'])}")

    forms = {}
    for r in scored:
        for m in r["messages"]:
            stem = re.sub(r"\d+", "N", re.sub(r"'[^']*'", "'X'", m))[:100]
            forms[stem] = forms.get(stem, 0) + 1
    print(f"\ndistinct message forms: {len(forms)}")
    for k, v in sorted(forms.items(), key=lambda x: -x[1]):
        print(f"  {v:4d}  {k}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
