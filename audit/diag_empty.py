"""diag_empty.py — geometry that went in and did not come out.

B7 is currently recorded only when the source itself carried a null geometry.
A feature with real geometry that the writer failed to write is a different
case and may be going uncounted. This lists every conversion whose output
holds less geometry than its source, with what was detected and what the tool
said, so the size of the gap can be seen before any detector is changed.

    python diag_empty.py
"""
import json
import importlib.util
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gt", HERE / "03_ground_truth.py")
gt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gt)

ABORTED = r"Terminating translation prematurely"


def geom_count(model, target):
    if target == "dxf":
        return getattr(model, "dxf_entities", 0)
    return sum(1 for f in model.features if f["geom"])


def run(label, work, aborted_pattern=None):
    rows = json.loads((work / "reported.json").read_text(encoding="utf-8"))
    gt.WORK = work
    hits, total = [], 0
    for r in rows:
        if r.get("unsupported") or r["fixture"] == "F14":
            continue
        total += 1
        crs = r.get("src") or ("EPSG:3857" if r["fixture"] == "F13" else "EPSG:4326")
        try:
            src = gt.load_source(r["file"])
            out = gt.load_output(r["fixture"], r["target"], r["outputs"])
        except Exception as e:
            hits.append((r["fixture"], r["target"], "-", "LOAD FAILED", False, [], str(e)[:40]))
            continue
        sg = sum(1 for f in src.features if f["geom"])
        if out is None:
            # No output model at all. detect() returns empty lists for this,
            # so the conversion is currently scored as having lost nothing.
            obs, inh = gt.detect(src, out, r["target"], crs)
            msgs = [str(m) for m in r.get("messages", [])]
            ab = bool(aborted_pattern) and any(re.search(aborted_pattern, m) for m in msgs)
            hits.append((r["fixture"], r["target"], sg, "none", ab,
                         sorted(set(obs) | set(inh)), "  NO OUTPUT"))
            continue
        og = geom_count(out, r["target"])
        if og >= sg:
            continue
        obs, inh = gt.detect(src, out, r["target"], crs)
        msgs = [str(m) for m in r.get("messages", [])]
        ab = bool(aborted_pattern) and any(re.search(aborted_pattern, m) for m in msgs)
        hits.append((r["fixture"], r["target"], sg, og, ab,
                     sorted(set(obs) | set(inh)), ""))

    print(f"=== {label}   {len(hits)} of {total} conversions lost geometry outright")
    if hits:
        print(f"    {'fix':5}{'target':9}{'src':>5}{'out':>5}  {'aborted':8} detected")
        for f, t, sg, og, ab, codes, err in hits:
            mark = "ABORTED" if ab else ""
            print(f"    {f:5}{t:9}{str(sg):>5}{str(og):>5}  {mark:8} "
                  f"{','.join(codes) if codes else '(nothing)'}{err}")
    print()


for label, d, pat in (("Pafta", "work", None),
                      ("GDAL", "work_ogr", ABORTED),
                      ("mapshaper", "work_ms", None)):
    w = HERE / d
    if w.exists():
        run(label, w, pat)
    else:
        print(f"=== {label}: {d} missing\n")
