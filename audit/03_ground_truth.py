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

    def n_interior_rings(self):
        """Interior rings (holes) across every polygon in the collection."""
        n = 0
        for f in self.features:
            for poly in rings_of(f["geom"]):
                n += max(0, len(poly) - 1)
        return n

    def n_multipart(self):
        """Features whose geometry carries more than one disjoint part."""
        n = 0
        for f in self.features:
            g = f["geom"]
            if g and str(g.get("type", "")).startswith("Multi") \
                    and len(g.get("coordinates") or []) > 1:
                n += 1
        return n


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


# B9 is a question about position, not about notation. Counting the decimal
# places of the written text answers neither: the count depends on the
# formatting (scientific notation, trailing zeros) rather than on where the
# vertex ended up, and taking the maximum over a layer lets one high-precision
# coordinate mask truncation everywhere else. The mechanism is therefore
# measured as the largest distance any vertex moved, against a stated
# tolerance.
B9_TOLERANCE_M = 0.001


DATETIME = re.compile(r"^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")


def has_time_of_day(v):
    """True when the value states a time of day, not only a calendar date."""
    return isinstance(v, str) and bool(DATETIME.match(v.strip()))


def _crosses(a, b, c, d):
    """Do segments ab and cd cross at a point interior to both?"""
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    d1, d2 = side(c, d, a), side(c, d, b)
    d3, d4 = side(a, b, c), side(a, b, d)
    return ((d1 > 0) != (d2 > 0)) and ((d3 > 0) != (d4 > 0))


def self_intersects(ring):
    """A ring crosses itself. Shared endpoints of neighbouring segments and the
    closing point are not crossings, so only non-adjacent pairs are tested."""
    r = list(ring)
    if len(r) > 1 and list(r[0][:2]) == list(r[-1][:2]):
        r = r[:-1]
    n = len(r)
    if n < 4:
        return False
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            if _crosses(r[i], r[(i + 1) % n], r[j], r[(j + 1) % n]):
                return True
    return False


def any_invalid_ring(model):
    return any(self_intersects(ring)
               for f in model.features
               for poly in rings_of(f["geom"])
               for ring in poly)


def vertices(model):
    """Every distinct vertex of the collection, in document order.

    A closed ring repeats its first point as its last in GeoJSON and KML; a
    closed DXF POLYLINE does not. The repeat carries no position of its own, so
    it is dropped here and the same geometry yields the same vertex count in
    every format."""
    out = []
    for f in model.features:
        g = f["geom"]
        polys = rings_of(g)
        if not polys:
            out.extend(coords_of(g))
            continue
        for poly in polys:
            for ring in poly:
                r = list(ring)
                if len(r) > 1 and list(r[0][:2]) == list(r[-1][:2]):
                    r = r[:-1]
                out.extend(r)
    return out


def max_shift_metres(src, out, angular):
    """Largest distance any vertex moved, or None where the question cannot be
    put. Vertices are matched to their nearest counterpart rather than by
    position in the file: a writer may reverse a ring or reorder parts without
    moving anything, and index matching would read that as displacement.
    A differing vertex count means the output is not a vertex-for-vertex copy,
    so no correspondence exists and the conversion is left unscored."""
    a, b = vertices(src), vertices(out)
    if not a or len(a) != len(b):
        return None

    def metres(p, q):
        dx, dy = q[0] - p[0], q[1] - p[1]
        if angular:
            dy *= 110540.0
            dx *= 111320.0 * math.cos(math.radians(p[1]))
        return math.hypot(dx, dy)

    worst = 0.0
    for q in b:
        worst = max(worst, min(metres(p, q) for p in a))
    return worst


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
    # Only the ENTITIES section holds drawing geometry. The HEADER carries
    # $EXTMIN and $EXTMAX, which are written with the same group codes; reading
    # those as vertices made the output longer than the source by a fixed
    # amount and so made every DXF conversion unscorable for displacement.
    in_entities = False
    cur_ent = None
    while i + 1 < len(lines):
        code, val = lines[i].strip(), lines[i + 1]
        if code == "2" and val.strip() == "ENTITIES":
            in_entities = True
        elif code == "0" and val.strip() == "ENDSEC":
            in_entities = False
        if code == "0":
            cur_ent = val.strip()
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
                # A POLYLINE entity carries a dummy 10/20/30 of its own before
                # its VERTEX list, and a TEXT entity an insertion point; neither
                # is drawing geometry, and the dummy sits at the origin, which a
                # nearest-vertex search would pair with a real point half a world
                # away. Only VERTEX and POINT carry coordinates to compare.
                if y is not None and in_entities and cur_ent in ("VERTEX", "POINT"):
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

    # Does any geometry at all survive into the output? A CSV written with no
    # coordinate column, or a DXF holding no entity, carries none, and the
    # mechanisms below that assume something was written must not be recorded
    # for it.
    if target == "dxf":
        out_has_geom = getattr(out, "dxf_entities", 0) > 0
    else:
        out_has_geom = any(f["geom"] for f in out.features)
    src_has_geom = any(f["geom"] for f in src.features)

    # ---- format-inherent, conditioned on the source actually carrying it
    if target == "dxf" and src.prop_keys():
        inh.append("A8")
    if target == "csv" and (src.geom_types() - {"Point", "MultiPoint"}) \
            and out_has_geom:
        inh.append("B10")
    # B11, complete geometry loss: the counterpart of A8. Recorded only where
    # the target can carry geometry and the writer emitted none, so it is a
    # writer's choice rather than a limit of the format.
    if src_has_geom and not out_has_geom:
        obs.append("B11")
    # DXF R12 has no construct that groups entities into one feature, so every
    # part of a multipart feature becomes an independent entity. Conditioned on
    # the source actually carrying a multipart feature, as A8 is on attributes.
    if target == "dxf" and src.n_multipart():
        inh.append("B4")
    # DXF R12 writes each ring as its own closed POLYLINE with nothing to say
    # which ring encloses which, so a hole arrives as an independent outline.
    # Conditioned on the source actually carrying an interior ring.
    if target == "dxf" and src.n_interior_rings():
        inh.append("B3")
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
        # type coercion: a non-string source value arriving as a string.
        # Writers differ in the case they give DBF field names: this tool
        # upper-cases them, GDAL and mapshaper keep the source case. Matching
        # case-sensitively made every value-level mechanism invisible for the
        # latter two, so the source field is matched without regard to case.
        for f_s, f_o in zip(src.features, out.features):
            oprops = f_o["props"] or {}
            folded = {str(key).lower(): key for key in oprops}
            for k in skeys:
                if k not in (f_s["props"] or {}):
                    continue
                sv = f_s["props"][k]
                stem = (k[:10] if target == "shp" else k).lower()
                if stem not in folded:
                    continue
                ov = oprops[folded[stem]]
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
                # A5: the source states a time of day and the output does not.
                if has_time_of_day(sv) and not has_time_of_day(ov):
                    obs.append("A5")
            break  # one feature is enough to establish the schema behaviour

    # ---- geometry
    # B8: an invalid ring is repaired by the writer with nothing said. A ring
    # written through unchanged is not recorded: nothing is then absent,
    # altered or unrecoverable, and counting it would score faithfulness as
    # loss. DXF and CSV are excluded because neither preserves rings at all,
    # so repair cannot be distinguished from the format's own behaviour.
    if target in ("shp", "geojson", "kml") and any_invalid_ring(src) \
            and out_has_geom and not any_invalid_ring(out):
        obs.append("B8")
    # C4: the output places the points where the source would be if its two
    # axes were read the other way round. Decidable because the source's own
    # axis semantics are fixed by its header or its reference system, not
    # guessed from the coordinates.
    if out_has_geom and target != "csv":
        a, b = vertices(src), vertices(out)
        if a and len(a) == len(b):
            flipped = [[p[1], p[0]] for p in a]
            straight = max(min(math.dist(p[:2], q[:2]) for p in a) for q in b)
            swapped = max(min(math.dist(p[:2], q[:2]) for p in flipped) for q in b)
            if swapped < straight and swapped < 1e-9:
                obs.append("C4")

    if src.max_dim() > 2 and out.max_dim() == 2:
        obs.append("B1")
    if src.had_m:
        obs.append("B2")

    src_types = src.geom_types()
    if target == "shp" and len(
            {("point" if "Point" in t else "line" if "Line" in t else "poly")
             for t in src_types}) > 1:
        obs.append("B5")

    # B3 outside DXF: shapefile, KML and GeoJSON can all express a hole, so
    # losing one there is the writer's doing rather than the format's. CSV is
    # excluded because B10 already accounts for the whole geometry going.
    si = src.n_interior_rings()
    if target not in ("dxf", "csv") and si and out.n_interior_rings() < si:
        obs.append("B3")

    # B4 outside DXF: a split shows up as more output features than source
    # features. Counting features, not parts, keeps the test independent of how
    # each reader chooses to represent a multipart geometry.
    if target != "dxf" and src.n_multipart() \
            and len(out.features) > len(src.features):
        obs.append("B4")

    if src.n_null_geom() and target != "geojson":
        kept = sum(1 for f in out.features if f["geom"])
        if kept < len(src.features):
            obs.append("B7")

    # Shapefile stores coordinates as binary doubles and cannot truncate them;
    # CSV is excluded because it writes a centroid in place of the geometry,
    # which B10 already records, leaving no vertex to compare.
    # KML is defined on WGS 84, so a projected source is reprojected on the way
    # out and the two sets of coordinates are not in the same frame; that is a
    # reference-system matter, not precision, and is excluded here.
    comparable = target in ("geojson", "dxf") or (
        target == "kml" and src_crs in ANGULAR_CRS)
    if comparable:
        shift = max_shift_metres(src, out, src_crs in ANGULAR_CRS)
        if shift is not None and shift > B9_TOLERANCE_M:
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
    # Added after the identifiers were introduced in the interface: both
    # state that the source declares no reference system, which is C1.
    "log.crs.csvUndeclared":  ["C1"],
    "log.crs.zoneUndetermined": ["C1"],
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
