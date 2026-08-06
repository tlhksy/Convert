#!/usr/bin/env python3
"""
03_ground_truth.py — determine what each conversion actually lost, and compare
that with what the tool reported.

Losses are not detected by twenty-seven bespoke rules. Source and output are
both loaded into one normalised model (geometry with its dimensionality,
attributes, identifier, label), and differences between the two models are
mapped onto the taxonomy. A handful of codes cannot be seen this way because
they follow from what the target format is rather than from a difference in the
model; those are derived from format capability plus source content, and are
flagged separately in the output so the two kinds of evidence are never
conflated.

Reads:  work/reported.json, work/<fixture>/<target>/*, fixtures/
Writes: work/ground_truth.json, work/audit_table.md

Usage: python3 03_ground_truth.py
"""

import csv
import io
import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

import shapefile  # pyshp

HERE = Path(__file__).resolve().parent
WORK = HERE / "work"
FIX = HERE / "fixtures"
FIXX = HERE / "fixtures_x"

KML_NS = "{http://www.opengis.net/kml/2.2}"


# --------------------------------------------------------------------------
# normalised model
# --------------------------------------------------------------------------

class Model:
    """What a dataset carries, independent of the file it came from."""

    def __init__(self):
        self.features = []       # list of dicts: geom, props, fid, label
        self.crs_declared = None
        self.styles = 0
        self.folder_depth = 0
        self.had_m = False

    def prop_keys(self):
        keys = []
        for f in self.features:
            for k in (f["props"] or {}):
                if k not in keys:
                    keys.append(k)
        return keys

    def max_dim(self):
        d = 2
        for f in self.features:
            for c in coords_of(f["geom"]):
                d = max(d, len(c))
        return d

    def geom_types(self):
        return {f["geom"]["type"] for f in self.features if f["geom"]}

    def n_null_geom(self):
        return sum(1 for f in self.features if not f["geom"])


def coords_of(geom):
    """Every coordinate tuple in a GeoJSON-shaped geometry."""
    if not geom:
        return
    t = geom.get("type")
    c = geom.get("coordinates")
    if t == "Point":
        yield c
    elif t in ("MultiPoint", "LineString"):
        yield from c
    elif t in ("MultiLineString", "Polygon"):
        for part in c:
            yield from part
    elif t == "MultiPolygon":
        for poly in c:
            for ring in poly:
                yield from ring
    elif t == "GeometryCollection":
        for g in geom.get("geometries", []):
            yield from coords_of(g)


def rings_of(geom):
    """Polygon rings, as lists, with their nesting preserved."""
    if not geom:
        return []
    if geom["type"] == "Polygon":
        return [geom["coordinates"]]
    if geom["type"] == "MultiPolygon":
        return list(geom["coordinates"])
    return []


def signed_area(ring):
    s = 0.0
    for i in range(len(ring) - 1):
        s += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return s / 2.0


def decimals(v):
    s = repr(float(v))
    return len(s.split(".")[1]) if "." in s and "e" not in s else 0


def max_decimals(model):
    d = 0
    for f in model.features:
        for c in coords_of(f["geom"]):
            d = max(d, decimals(c[0]), decimals(c[1]))
    return d


# --------------------------------------------------------------------------
# loaders
# --------------------------------------------------------------------------

def load_geojson(path):
    m = Model()
    o = json.loads(Path(path).read_text(encoding="utf-8"))
    feats = o.get("features", [o]) if o.get("type") != "Feature" else [o]
    for f in feats:
        m.features.append({
            "geom": f.get("geometry"),
            "props": f.get("properties") or {},
            "fid": f.get("id"),
            "label": None,
        })
    # RFC 7946 fixes the reference system for GeoJSON, so absence of a crs
    # member is a definition, not an omission.
    m.crs_declared = "legacy crs member" if "crs" in o else "RFC 7946 default"
    return m


def load_kml(path):
    m = Model()
    root = ET.fromstring(Path(path).read_text(encoding="utf-8"))
    text = Path(path).read_text(encoding="utf-8")
    m.crs_declared = "KML is defined on WGS 84"
    m.styles = text.count("<Style") + text.count("<styleUrl>")

    def depth(el, d=0):
        best = d
        for ch in el:
            if ch.tag == KML_NS + "Folder":
                best = max(best, depth(ch, d + 1))
            else:
                best = max(best, depth(ch, d))
        return best
    m.folder_depth = depth(root)

    for pm in root.iter(KML_NS + "Placemark"):
        name_el = pm.find(KML_NS + "name")
        geom = None
        for tag, gtype in (("Point", "Point"), ("LineString", "LineString"),
                           ("Polygon", "Polygon")):
            el = pm.find(".//" + KML_NS + tag)
            if el is None:
                continue
            if gtype == "Polygon":
                rings = []
                for b in (KML_NS + "outerBoundaryIs", KML_NS + "innerBoundaryIs"):
                    for bb in pm.iter(b):
                        ct = bb.find(".//" + KML_NS + "coordinates")
                        if ct is not None:
                            rings.append(parse_coord_text(ct.text))
                geom = {"type": "Polygon", "coordinates": rings}
            else:
                ct = el.find(KML_NS + "coordinates")
                pts = parse_coord_text(ct.text if ct is not None else "")
                geom = ({"type": "Point", "coordinates": pts[0]} if gtype == "Point"
                        else {"type": "LineString", "coordinates": pts})
            break
        props = {}
        for sd in pm.iter(KML_NS + "SimpleData"):
            props[sd.get("name")] = sd.text
        for d in pm.iter(KML_NS + "Data"):
            v = d.find(KML_NS + "value")
            props[d.get("name")] = v.text if v is not None else None
        m.features.append({
            "geom": geom, "props": props, "fid": None,
            "label": name_el.text if name_el is not None else None,
        })
    return m


def parse_coord_text(t):
    out = []
    for tok in (t or "").split():
        parts = tok.split(",")
        if len(parts) < 2:
            continue
        c = [float(parts[0]), float(parts[1])]
        if len(parts) > 2 and float(parts[2]) != 0.0:
            c.append(float(parts[2]))
        out.append(c)
    return out


def load_shapefile(base):
    """base is a path without extension."""
    m = Model()
    kw = {"shp": str(base) + ".shp"}
    for ext in ("dbf", "shx"):
        if Path(str(base) + "." + ext).exists():
            kw[ext] = str(base) + "." + ext
    enc = "utf-8"
    cpg = Path(str(base) + ".cpg")
    if cpg.exists():
        enc = cpg.read_text().strip()
    r = shapefile.Reader(encoding=enc, encodingErrors="replace", **kw)
    m.crs_declared = "prj" if Path(str(base) + ".prj").exists() else None

    fields = [f[0] for f in r.fields[1:]]
    recs = r.records() if "dbf" in kw else [None] * len(r.shapes())
    for i, sh in enumerate(r.shapes()):
        st = sh.shapeType
        if st in (11, 13, 15, 18):
            m.had_m = True
        elif st in (21, 23, 25, 28):
            m.had_m = True
        geom = shape_to_geojson(sh)
        props = dict(zip(fields, recs[i])) if recs[i] is not None else {}
        m.features.append({"geom": geom, "props": props, "fid": None, "label": None})
    return m


def shape_to_geojson(sh):
    st = sh.shapeType
    if st == 0:
        return None
    pts = list(sh.points)
    zs = list(getattr(sh, "z", []) or [])
    if zs and len(zs) == len(pts):
        pts = [[p[0], p[1], z] for p, z in zip(pts, zs)]
    else:
        pts = [[p[0], p[1]] for p in pts]
    base = st % 10
    if base == 1:
        return {"type": "Point", "coordinates": pts[0]} if pts else None
    if base == 8:
        return {"type": "MultiPoint", "coordinates": pts}
    parts = list(sh.parts) + [len(pts)]
    rings = [pts[parts[i]:parts[i + 1]] for i in range(len(parts) - 1)]
    rings = [r for r in rings if r]
    if base == 3:
        return ({"type": "LineString", "coordinates": rings[0]} if len(rings) == 1
                else {"type": "MultiLineString", "coordinates": rings})
    polys = []
    for ring in rings:
        if signed_area(ring) <= 0:
            polys.append([ring])
        elif polys:
            polys[-1].append(ring)
        else:
            polys.append([ring])
    return ({"type": "Polygon", "coordinates": polys[0]} if len(polys) == 1
            else {"type": "MultiPolygon", "coordinates": polys})


def load_csv(path):
    m = Model()
    rows = list(csv.reader(io.StringIO(Path(path).read_text(encoding="utf-8-sig"))))
    if not rows:
        return m
    head = rows[0]
    # Column identification mirrors the tool's own rule: named coordinate
    # columns first, positional fallback only when nothing matches.
    lower = [h.strip().lower() for h in head]
    X_NAMES = ("x", "lon", "long", "longitude", "boylam", "easting", "east")
    Y_NAMES = ("y", "lat", "latitude", "enlem", "northing", "north")
    xi = next((i for i, h in enumerate(lower) if h in X_NAMES), 0)
    yi = next((i for i, h in enumerate(lower) if h in Y_NAMES), 1)
    keys = [h for i, h in enumerate(head) if i not in (xi, yi)]
    for row in rows[1:]:
        if len(row) < 2:
            continue
        try:
            geom = {"type": "Point", "coordinates": [float(row[xi]), float(row[yi])]}
        except ValueError:
            geom = None
        props = {k: row[head.index(k)] for k in keys if head.index(k) < len(row)}
        m.features.append({"geom": geom, "props": props, "fid": None, "label": None})
    return m


def load_dxf(path):
    """Only what the taxonomy needs: layers, entity count, vertex dimensionality."""
    m = Model()
    lines = Path(path).read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n").split("\n")
    layers, verts, ent = set(), [], 0
    i = 0
    cur_layer = None
    while i + 1 < len(lines):
        code, val = lines[i].strip(), lines[i + 1]
        if code == "0" and val in ("POLYLINE", "POINT", "TEXT", "LINE"):
            ent += 1
        if code == "8":
            layers.add(val)
            cur_layer = val
        if code == "10":
            try:
                x = float(val)
                y = float(lines[i + 3]) if lines[i + 2].strip() == "20" else None
                z = float(lines[i + 5]) if i + 5 < len(lines) and lines[i + 4].strip() == "30" else None
                if y is not None:
                    verts.append([x, y] + ([z] if z not in (None, 0.0) else []))
            except (ValueError, IndexError):
                pass
        i += 2
    m.features.append({
        "geom": {"type": "MultiPoint", "coordinates": verts} if verts else None,
        "props": {}, "fid": None, "label": None,
    })
    m.dxf_layers = layers
    m.dxf_entities = ent
    m.dxf_text = sum(1 for i in range(1, len(lines), 2) if lines[i] == "TEXT")
    return m


# --------------------------------------------------------------------------
# source loading
# --------------------------------------------------------------------------

def load_source(fixture_file):
    p = FIX / fixture_file
    if p.suffix == ".geojson":
        return load_geojson(p)
    if p.suffix == ".kml":
        return load_kml(p)
    if p.suffix == ".csv":
        return load_csv(p)
    d = FIXX / fixture_file
    if d.is_dir():
        base = next(d.glob("*.shp")).with_suffix("")
        return load_shapefile(base)
    raise FileNotFoundError(fixture_file)


def load_output(fixture_id, target, outputs):
    d = WORK / fixture_id / target
    if not outputs:
        return None
    if target == "geojson":
        return load_geojson(d / outputs[0])
    if target == "kml":
        return load_kml(d / outputs[0])
    if target == "csv":
        return load_csv(d / outputs[0])
    if target == "dxf":
        return load_dxf(d / outputs[0])
    if target == "shp":
        shp = [o for o in outputs if o.endswith(".shp")]
        if not shp:
            return None
        return load_shapefile(d / shp[0][:-4])
    return None


# --------------------------------------------------------------------------
# loss detection
# --------------------------------------------------------------------------

# Codes that follow from the target format rather than from a model difference.
FORMAT_INHERENT = {
    "dxf": ["A8"],
    "csv": ["B10"],
}


ANGULAR_CRS = {"EPSG:4326", "EPSG:4258", "EPSG:4230"}


def detect(src, out, target, src_crs=None):
    """Return (observed, inherent) code lists."""
    obs, inh = [], []
    if out is None:
        return obs, inh

    # ---- format-inherent, conditioned on the source actually carrying it
    if target == "dxf" and src.prop_keys():
        inh.append("A8")
    if target == "csv" and (src.geom_types() - {"Point", "MultiPoint"}):
        inh.append("B10")
    # DXF has no units, so angular coordinates make every length and area in
    # the drawing meaningless. The condition is the source system, not the data.
    if target == "dxf" and src_crs in ANGULAR_CRS:
        inh.append("C3")

    # ---- attributes
    skeys, okeys = src.prop_keys(), out.prop_keys()
    if target not in ("dxf",):
        if any(len(k) > 10 for k in skeys) and target == "shp":
            obs.append("A1")
            heads = [k[:10].upper() for k in skeys]
            if len(set(heads)) < len(heads):
                obs.append("A2")
        # type coercion: a non-string source value arriving as a string
        for f_s, f_o in zip(src.features, out.features):
            for k in skeys:
                if k not in (f_s["props"] or {}):
                    continue
                sv = f_s["props"][k]
                ok = k[:10].upper() if target == "shp" else k
                if ok not in (f_o["props"] or {}):
                    continue
                ov = f_o["props"][ok]
                if isinstance(sv, bool) and not isinstance(ov, bool):
                    obs.append("A3")
                elif isinstance(sv, int) and not isinstance(sv, bool) \
                        and not isinstance(ov, int) and ov not in (None, ""):
                    obs.append("A3")
                if sv is None and ov == "":
                    obs.append("A6")
                if isinstance(sv, str) and len(sv) > 254 and isinstance(ov, str) and len(ov) < len(sv):
                    obs.append("A4")
                if isinstance(sv, str) and any(ord(c) > 127 for c in sv):
                    if isinstance(ov, str) and not any(ord(c) > 127 for c in ov):
                        obs.append("A7")
            break  # one feature is enough to establish the schema behaviour

    # ---- geometry
    if src.max_dim() > 2 and out.max_dim() == 2:
        obs.append("B1")
    if src.had_m:
        obs.append("B2")

    src_types = src.geom_types()
    if target == "shp" and len(
            {("point" if "Point" in t else "line" if "Line" in t else "poly")
             for t in src_types}) > 1:
        obs.append("B5")

    if src.n_null_geom() and target != "geojson":
        kept = sum(1 for f in out.features if f["geom"])
        if kept < len(src.features):
            obs.append("B7")

    if target in ("geojson", "kml", "csv"):
        ds, do = max_decimals(src), max_decimals(out)
        if ds > do:
            obs.append("B9")

    # winding: compare exterior orientation of the first polygon
    sr, orr = rings_of(src.features[0]["geom"] if src.features else None), \
        rings_of(out.features[0]["geom"] if out.features else None)
    if sr and orr and sr[0] and orr[0]:
        a, b = signed_area(sr[0][0]), signed_area(orr[0][0])
        if a != 0 and b != 0 and (a > 0) != (b > 0):
            obs.append("B6")

    # ---- reference system
    # Only a source with neither a declaration nor a specification-fixed default
    # leaves the reference system to be assumed.
    if src.crs_declared is None:
        obs.append("C1")

    # ---- structure
    if src.styles and target != "kml":
        obs.append("D2")
    if src.folder_depth > 1 and target != "kml":
        obs.append("D3")
    if any(f["fid"] is not None for f in src.features) and \
            not any(f["fid"] is not None for f in (out.features or [])) and target != "geojson":
        obs.append("D4")
    if any(f["label"] for f in src.features):
        got = any(f["label"] for f in out.features) or \
            (target == "dxf" and getattr(out, "dxf_text", 0) > 0) or \
            any("name" in str(k).lower() for k in out.prop_keys())
        if not got:
            obs.append("D5")

    return sorted(set(obs)), sorted(set(inh))


# --------------------------------------------------------------------------
# mapping reported identifiers onto taxonomy codes
# --------------------------------------------------------------------------

# Fixed before the outputs were inspected. One identifier may evidence several
# codes; a format-level note counts as a disclosure of the mechanisms it names.
KEY_TO_CODES = {
    "log.dbf.fieldRenamed":   ["A1", "A2", "A7"],
    "log.shp.fieldNote":      ["A1", "A7"],
    "log.dbf.valueTruncated": ["A4"],
    "log.shp.noCpg":          ["A7"],
    "log.dxf.formatNote":     ["A8", "B3"],
    "log.shp.mDropped":       ["B2"],
    "log.geom.zDropped":      ["B1"],
    "log.shp.multipleTypes":  ["B5"],
    "log.out.emptySkipped":   ["B7"],
    "log.geom.emptyDropped":  ["B7"],
    "log.dxf.skipped":        ["B5"],
    "log.csv.centroidOnly":   ["B10"],
    "log.crs.noPrj":          ["C1"],
    "log.crs.prjUnmatched":   ["C1"],
    "log.crs.zoneUndetermined": ["C1"],
    "log.crs.csvUndeclared": ["C1"],
    "log.dxf.degreeUnits":    ["C3"],
    "log.geojson.notWgs84":   ["C1"],
    "log.kml.forcesWgs84":    ["C1"],
    "log.dxf.layerRenamed":   ["D1"],
    "log.geom.idDropped":     ["D4"],
    "log.dxf.textAscii":      ["A7"],
}

IGNORE_KEYS = {"log.read.summary", "log.read.inputSize", "log.zip.opened",
               "log.shp.written", "log.dxf.written", "log.csv.columnsFound",
               "log.shp.noShx", "log.shp.noDbf", "log.read.large",
               "log.shp.recordMismatch", "log.shp.multiple", "log.error",
               "log.out.nothing", "log.proj.failed", "log.dxf.fixTarget"}


def reported_codes(entries):
    codes, unmapped = set(), set()
    for e in entries:
        k = e["key"]
        if k in IGNORE_KEYS:
            continue
        if k in KEY_TO_CODES:
            codes.update(KEY_TO_CODES[k])
        else:
            unmapped.add(k)
    return codes, unmapped


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------

def main():
    reported = json.loads((WORK / "reported.json").read_text(encoding="utf-8"))
    tax = json.loads((HERE / "taxonomy.json").read_text(encoding="utf-8"))
    fam = {c: tax["codes"][c]["family"] for c in tax["codes"]}

    rows, all_unmapped = [], set()
    for r in reported:
        if r["fixture"] == "F14":          # accuracy fixture, not part of this audit
            continue
        try:
            src = load_source(r["file"])
        except Exception as e:
            rows.append({**{k: r[k] for k in ("fixture", "target")},
                         "error": f"source: {e}"})
            continue
        try:
            out = load_output(r["fixture"], r["target"], r["outputs"])
        except Exception as e:
            rows.append({**{k: r[k] for k in ("fixture", "target")},
                         "error": f"output: {e}"})
            continue

        obs, inh = detect(src, out, r["target"], r.get("src"))
        occurred = sorted(set(obs) | set(inh))
        rep, unmapped = reported_codes(r["reported"])
        all_unmapped |= unmapped

        rows.append({
            "fixture": r["fixture"], "target": r["target"],
            "occurred": occurred, "observed": obs, "inherent": inh,
            "reported": sorted(rep),
            "silent": sorted(set(occurred) - rep),
            # A format-level note states what the target format cannot carry,
            # whether or not this particular dataset triggers it. Counting that
            # as a false alarm would misread it, so it is kept apart.
            "notice_not_applicable": sorted(set(rep) - set(occurred)),
            "error": None,
        })

    (WORK / "ground_truth.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")

    # ---------------- summary ----------------
    occ = defaultdict(int)
    rep = defaultdict(int)
    for row in rows:
        if row.get("error"):
            continue
        for c in row["occurred"]:
            occ[fam[c]] += 1
            if c in row["reported"]:
                rep[fam[c]] += 1

    print(f"conversions analysed: {sum(1 for r in rows if not r.get('error'))}"
          f"   errors: {sum(1 for r in rows if r.get('error'))}")
    if all_unmapped:
        print(f"identifiers with no taxonomy mapping: {sorted(all_unmapped)}")
    print()
    print(f"{'family':<40} {'occurred':>9} {'reported':>9} {'silent':>7} {'rate':>7}")
    print("-" * 76)
    tot_o = tot_r = 0
    for f in sorted(tax["families"]):
        o, rp = occ[f], rep[f]
        tot_o += o
        tot_r += rp
        rate = (o - rp) / o if o else 0
        print(f"{f + ' ' + tax['families'][f]:<40} {o:>9} {rp:>9} {o - rp:>7} {rate:>6.0%}")
    print("-" * 76)
    print(f"{'all':<40} {tot_o:>9} {tot_r:>9} {tot_o - tot_r:>7} "
          f"{((tot_o - tot_r) / tot_o if tot_o else 0):>6.0%}")

    # per-code detail
    occ_c, rep_c = defaultdict(int), defaultdict(int)
    for row in rows:
        if row.get("error"):
            continue
        for c in row["occurred"]:
            occ_c[c] += 1
            if c in row["reported"]:
                rep_c[c] += 1
    print("\nper code (occurred / reported)")
    line = []
    for c in sorted(occ_c, key=lambda x: (x[0], int(x[1:]))):
        line.append(f"{c}:{rep_c[c]}/{occ_c[c]}")
    print("  " + "  ".join(line))

    errs = [r for r in rows if r.get("error")]
    if errs:
        print("\nerrors")
        for e in errs[:10]:
            print(f"  {e['fixture']}/{e['target']}: {e['error']}")


if __name__ == "__main__":
    sys.exit(main())
