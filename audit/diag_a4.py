"""diag_a4.py — why does GDAL show no A4 occurrence?

A4 is width or precision overflow: F03 carries a 309-character text value that
a DBF character field cannot hold. GDAL warns about it on screen, so it plainly
incurs the mechanism; the scoring shows no occurrence. One of the two is wrong
and this prints enough to say which.

    python diag_a4.py
"""
import json
from pathlib import Path

import importlib.util

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gt", HERE / "03_ground_truth.py")
gt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gt)


def look(label, work):
    rows = json.loads((work / "reported.json").read_text(encoding="utf-8"))
    for r in rows:
        if r["fixture"] != "F03" or r["target"] != "shp":
            continue
        print(f"--- {label}  F03 -> shp")
        print("    outputs :", r.get("outputs"))
        print("    unsupported:", r.get("unsupported"))
        for m in r.get("messages", []):
            print("    msg     :", str(m)[:110])
        gt.WORK = work
        try:
            src = gt.load_source(r["file"])
            out = gt.load_output(r["fixture"], r["target"], r["outputs"])
        except Exception as e:
            print("    LOAD FAILED:", e)
            return
        sv = {k: v for k, v in (src.features[0]["props"] or {}).items()
              if isinstance(v, str) and len(v) > 254}
        print("    source long values:", {k: len(v) for k, v in sv.items()})
        ov = out.features[0]["props"] or {}
        print("    output keys       :", sorted(ov)[:14])
        for k in sv:
            for cand in (k, k[:10].upper(), k.upper()):
                if cand in ov:
                    print(f"    {k} -> {cand}: length {len(str(ov[cand]))}")
                    break
            else:
                print(f"    {k}: NOT FOUND in output under any expected name")
        obs, inh = gt.detect(src, out, "shp", "EPSG:4326")
        print("    detected:", sorted(set(obs) | set(inh)))
        return
    print(f"--- {label}: no F03 -> shp row at all")


for label, d in (("Pafta", "work"), ("GDAL", "work_ogr"), ("mapshaper", "work_ms")):
    w = HERE / d
    if w.exists():
        look(label, w)
    else:
        print(f"--- {label}: {d} missing")
