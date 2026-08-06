#!/usr/bin/env python3
"""
verify_fixtures.py — confirm that each generated fixture actually exhibits the
property it is supposed to isolate.

A fixture that does not contain the condition it claims to test would silently
inflate every downstream result, so this check runs before any conversion.

Usage: python3 verify_fixtures.py [--dir fixtures]
"""

import argparse
import json
import zipfile
from io import BytesIO
from pathlib import Path

import shapefile

CHECKS = []
def check(fid, label):
    def deco(fn):
        CHECKS.append((fid, label, fn))
        return fn
    return deco


def load_gj(d, name):
    return json.loads((d / name).read_text(encoding="utf-8"))


def signed_area(ring):
    """Positive => counter-clockwise in (x=lon, y=lat)."""
    s = 0.0
    for i in range(len(ring) - 1):
        x1, y1 = ring[i]
        x2, y2 = ring[i + 1]
        s += x1 * y2 - x2 * y1
    return s / 2.0


def seg_intersect(p1, p2, p3, p4):
    def orient(a, b, c):
        v = (b[0]-a[0])*(c[1]-a[1]) - (b[1]-a[1])*(c[0]-a[0])
        return (v > 1e-15) - (v < -1e-15)
    o1, o2 = orient(p1, p2, p3), orient(p1, p2, p4)
    o3, o4 = orient(p3, p4, p1), orient(p3, p4, p2)
    return o1 != o2 and o3 != o4


def ring_self_intersects(ring):
    n = len(ring) - 1
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if seg_intersect(ring[i], ring[i+1], ring[j], ring[j+1]):
                return True
    return False


def read_zip_shp(d, name):
    """Return (reader, member_names) for a zipped shapefile."""
    zf = zipfile.ZipFile(d / name)
    names = zf.namelist()
    parts = {}
    for ext in ("shp", "dbf", "shx"):
        m = [n for n in names if n.lower().endswith("." + ext)]
        parts[ext] = BytesIO(zf.read(m[0]))
    return shapefile.Reader(**parts), names


# ---------------------------------------------------------------- checks

@check("F01", "two field names collide in first 10 characters")
def _(d):
    gj = load_gj(d, "F01_long_field_names.geojson")
    keys = list(gj["features"][0]["properties"].keys())
    assert all(14 <= len(k) <= 24 for k in keys), [len(k) for k in keys]
    heads = [k[:10] for k in keys]
    dupes = {h for h in heads if heads.count(h) > 1}
    assert dupes, "no truncation collision present"
    return f"{len(keys)} fields, colliding stem {sorted(dupes)}"


@check("F02", "integers exceed 32-bit range; nulls and date-times present")
def _(d):
    gj = load_gj(d, "F02_attribute_types.geojson")
    vals = [f["properties"]["big_int"] for f in gj["features"]]
    assert max(abs(v) for v in vals) > 2**31, vals
    props = [f["properties"] for f in gj["features"]]
    assert any(p["optional"] is None for p in props)
    assert any(p["optional"] == "" for p in props)
    assert any(p["is_valid"] is None for p in props)
    assert all("T" in p["observed_at"] for p in props)
    return f"max |int| = {max(abs(v) for v in vals)}; null and empty both present"


@check("F03", "text value exceeds 254 characters")
def _(d):
    gj = load_gj(d, "F03_wide_text.geojson")
    n = len(gj["features"][0]["properties"]["description"])
    assert n > 254, n
    return f"{n} characters"


@check("F04", "non-ASCII characters present in five languages")
def _(d):
    gj = load_gj(d, "F04_non_ascii.geojson")
    names = [f["properties"]["place_name"] for f in gj["features"]]
    assert all(any(ord(c) > 127 for c in nm) for nm in names), names
    assert any("İ" in nm for nm in names), "dotted capital I absent"
    return f"{len(names)} values, all non-ASCII"


@check("F05", "polygon has exactly two interior rings inside the exterior")
def _(d):
    gj = load_gj(d, "F05_polygon_with_holes.geojson")
    rings = gj["features"][0]["geometry"]["coordinates"]
    assert len(rings) == 3, len(rings)
    ext = rings[0]
    xs = [p[0] for p in ext]; ys = [p[1] for p in ext]
    for hole in rings[1:]:
        assert all(min(xs) < p[0] < max(xs) and min(ys) < p[1] < max(ys) for p in hole)
    return "1 exterior + 2 interior, both contained"


@check("F06", "single feature with three disjoint parts")
def _(d):
    gj = load_gj(d, "F06_multipart_single_feature.geojson")
    assert len(gj["features"]) == 1
    parts = gj["features"][0]["geometry"]["coordinates"]
    assert len(parts) == 3, len(parts)
    boxes = []
    for p in parts:
        r = p[0]
        boxes.append((min(q[0] for q in r), max(q[0] for q in r)))
    boxes.sort()
    for a, b in zip(boxes, boxes[1:]):
        assert a[1] < b[0], f"parts overlap in x: {a} {b}"
    return "1 feature, 3 disjoint parts"


@check("F07", "three distinct geometry types in one collection")
def _(d):
    gj = load_gj(d, "F07_mixed_geometry_types.geojson")
    types = {f["geometry"]["type"] for f in gj["features"]}
    assert types == {"Point", "LineString", "Polygon"}, types
    return "Point, LineString, Polygon"


@check("F08", "shapefile stores non-trivial Z and M arrays")
def _(d):
    r, names = read_zip_shp(d, "F08_polyline_zm.zip")
    assert r.shapeType == shapefile.POLYLINEZ, r.shapeType
    shp = r.shape(0)
    assert len(set(shp.z)) > 1, shp.z
    assert len(set(shp.m)) > 1, shp.m
    assert any(n.lower().endswith(".prj") for n in names)
    assert any(n.lower().endswith(".cpg") for n in names)
    return f"shapeType {r.shapeType}, z range {min(shp.z)}-{max(shp.z)}, m range {min(shp.m)}-{max(shp.m)}"


@check("F09", "exterior ring is clockwise, contrary to RFC 7946")
def _(d):
    gj = load_gj(d, "F09_clockwise_exterior_ring.geojson")
    ring = gj["features"][0]["geometry"]["coordinates"][0]
    a = signed_area(ring)
    assert a < 0, f"signed area {a} is not clockwise"
    return f"signed area {a:.3e} (negative = clockwise)"


@check("F10", "two of five features carry null geometry")
def _(d):
    gj = load_gj(d, "F10_null_geometry.geojson")
    nulls = [f for f in gj["features"] if f["geometry"] is None]
    assert len(gj["features"]) == 5 and len(nulls) == 2
    assert all(f["properties"] for f in nulls), "null-geometry rows lost attributes"
    return "5 features, 2 null geometries, attributes retained"


@check("F11", "exterior ring self-intersects")
def _(d):
    gj = load_gj(d, "F11_self_intersecting_ring.geojson")
    ring = gj["features"][0]["geometry"]["coordinates"][0]
    assert ring_self_intersects(ring), "ring does not self-intersect"
    return "bow-tie confirmed"


@check("F12", "coordinates carry nine decimal places")
def _(d):
    raw = (d / "F12_coordinate_precision.geojson").read_text(encoding="utf-8")
    gj = json.loads(raw)
    decs = []
    for f in gj["features"]:
        for v in f["geometry"]["coordinates"]:
            s = repr(v)
            decs.append(len(s.split(".")[1]) if "." in s else 0)
    assert min(decs) >= 9, decs
    return f"min decimal places = {min(decs)}"


@check("F13", "zipped shapefile contains no .prj and no .cpg")
def _(d):
    r, names = read_zip_shp(d, "F13_no_prj.zip")
    assert not any(n.lower().endswith(".prj") for n in names), names
    assert not any(n.lower().endswith(".cpg") for n in names), names
    x, y = r.shape(0).points[0]
    assert x > 1000 and y > 1000, (x, y)
    return f"members {sorted(n.split('.')[-1] for n in names)}; first point ({x}, {y})"


@check("F14", "fifty control locations spanning the national extent")
def _(d):
    gj = load_gj(d, "F14_datum_control_points.geojson")
    assert len(gj["features"]) == 50, len(gj["features"])
    lons = [f["geometry"]["coordinates"][0] for f in gj["features"]]
    lats = [f["geometry"]["coordinates"][1] for f in gj["features"]]
    assert max(lons) - min(lons) > 10 and max(lats) - min(lats) > 4
    assert all(f["properties"]["reference_easting"] is None for f in gj["features"])
    return f"50 points, lon {min(lons)}-{max(lons)}, lat {min(lats)}-{max(lats)}; references empty"


@check("F15", "extent is well under one degree")
def _(d):
    gj = load_gj(d, "F15_geographic_units.geojson")
    ring = gj["features"][0]["geometry"]["coordinates"][0]
    w = max(p[0] for p in ring) - min(p[0] for p in ring)
    assert w < 0.05, w
    return f"width {w} degrees"


@check("F16", "layer names contain spaces, solidus, dots, non-ASCII and >31 characters")
def _(d):
    gj = load_gj(d, "F16_layer_names.geojson")
    names = [f["properties"]["layer_name"] for f in gj["features"]]
    assert any(" " in n for n in names)
    assert any("/" in n for n in names)
    assert any("." in n for n in names)
    assert any(any(ord(c) > 127 for c in n) for n in names)
    assert any(len(n) > 31 for n in names), [len(n) for n in names]
    return f"{len(names)} names, max length {max(len(n) for n in names)}"


@check("F17", "KML declares line, polygon and icon styles")
def _(d):
    s = (d / "F17_styled.kml").read_text(encoding="utf-8")
    for tag in ("<LineStyle>", "<PolyStyle>", "<IconStyle>", "<styleUrl>"):
        assert tag in s, tag
    return "LineStyle, PolyStyle, IconStyle all present"


@check("F18", "three levels of folder nesting with placemarks at each level")
def _(d):
    s = (d / "F18_nested_folders.kml").read_text(encoding="utf-8")
    assert s.count("<Folder>") == 3, s.count("<Folder>")
    assert s.count("<Placemark>") == 3
    return "3 folders, 3 placemarks at 3 depths"


@check("F19", "identifiers live in the GeoJSON id member, not in properties")
def _(d):
    gj = load_gj(d, "F19_feature_identifiers.geojson")
    assert all("id" in f for f in gj["features"])
    assert all("id" not in f["properties"] for f in gj["features"])
    return f"{len(gj['features'])} features with top-level id"


@check("F20", "placemark names present and non-ASCII in at least one")
def _(d):
    s = (d / "F20_labels.kml").read_text(encoding="utf-8")
    assert s.count("<name>") >= 4
    assert any(ord(c) > 127 for c in s)
    return f"{s.count('<name>') - 1} placemark names"


@check("F24", "CSV columns are latitude-first and a swap stays geographically plausible")
def _(d):
    lines = (d / "F24_axis_order.csv").read_text(encoding="utf-8").strip().splitlines()
    header = [h.strip().lower() for h in lines[0].split(",")]
    assert header.index("latitude") < header.index("longitude"), header
    li, gi = header.index("latitude"), header.index("longitude")
    for row in lines[1:]:
        c = row.split(",")
        lat, lon = float(c[li]), float(c[gi])
        # both readings must be inside valid ranges, so a range test cannot
        # detect the swap
        assert -90 <= lat <= 90 and -180 <= lon <= 180
        assert -90 <= lon <= 90 and -180 <= lat <= 180
    return f"{len(lines)-1} rows, header {header}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default="fixtures")
    args = ap.parse_args()
    d = Path(args.dir)

    ok = fail = 0
    for fid, label, fn in CHECKS:
        try:
            detail = fn(d)
            print(f"PASS  {fid}  {label}\n         -> {detail}")
            ok += 1
        except Exception as e:
            print(f"FAIL  {fid}  {label}\n         -> {type(e).__name__}: {e}")
            fail += 1
    print(f"\n{ok} passed, {fail} failed")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
