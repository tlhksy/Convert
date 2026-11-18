"""diag_b9.py — is B9 absent, or merely unmeasured?

The displacement test returns no answer when the vertices of the source and of
the output cannot be put in correspondence. A mechanism that never fires and a
mechanism that is never scored look identical in the results table, so this
prints the split: how many conversions were measured, what the largest
displacement was in each, and how many were left unscored and why.

    python diag_b9.py
"""
import json
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("gt", HERE / "03_ground_truth.py")
gt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gt)

TOL = gt.B9_TOLERANCE_M


def run(label, work):
    rows = json.loads((work / "reported.json").read_text(encoding="utf-8"))
    gt.WORK = work
    measured, over, unscored, skipped, failed = [], [], [], 0, 0
    for r in rows:
        if r.get("unsupported") or r["fixture"] == "F14":
            continue
        crs = r.get("src") or ("EPSG:3857" if r["fixture"] == "F13" else "EPSG:4326")
        angular = crs in gt.ANGULAR_CRS
        comparable = r["target"] in ("geojson", "dxf") or (
            r["target"] == "kml" and angular)
        if not comparable:
            skipped += 1
            continue
        try:
            src = gt.load_source(r["file"])
            out = gt.load_output(r["fixture"], r["target"], r["outputs"])
        except Exception:
            failed += 1
            continue
        sv, ov = len(gt.vertices(src)), len(gt.vertices(out))
        shift = gt.max_shift_metres(src, out, angular)
        if shift is None:
            unscored.append((r["fixture"], r["target"], sv, ov))
            continue
        measured.append((r["fixture"], r["target"], shift))
        if shift > TOL:
            over.append((r["fixture"], r["target"], shift))

    print(f"=== {label}   tolerance {TOL} m")
    print(f"    measured {len(measured)}   unscored {len(unscored)}   "
          f"target not comparable {skipped}   load failed {failed}")
    if measured:
        worst = sorted(measured, key=lambda t: -t[2])[:6]
        print("    largest displacements measured:")
        for f, t, s in worst:
            print(f"        {f:4} {t:8} {s:.6f} m"
                  f"{'   OVER TOLERANCE' if s > TOL else ''}")
    if unscored:
        print("    unscored (source vertices -> output vertices):")
        for f, t, sv, ov in unscored:
            print(f"        {f:4} {t:8} {sv} -> {ov}")
    print()


for label, d in (("Pafta", "work"), ("GDAL", "work_ogr"), ("mapshaper", "work_ms")):
    w = HERE / d
    if w.exists():
        run(label, w)
    else:
        print(f"=== {label}: {d} missing\n")
