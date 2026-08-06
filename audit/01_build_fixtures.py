#!/usr/bin/env python3
"""
build_fixtures.py — generate the loss-audit fixture corpus.

Each fixture isolates one or a small number of loss mechanisms defined in
taxonomy.json. Fixtures are deliberately tiny (<= 20 features) so that ground
truth can be established by inspection as well as programmatically.

The expected-loss manifest is emitted from the same specification table that
drives generation, so fixtures and manifest cannot drift apart.

Usage:
    python3 build_fixtures.py [--out DIR]

Requires: pyshp (shapefile)
"""

import argparse
import json
import os
import shutil
import zipfile
from pathlib import Path

import shapefile  # pyshp

# --------------------------------------------------------------------------
# Geographic anchor. All synthetic geographic fixtures sit near 33.0E / 39.0N,
# which falls inside TUREF / TM33 (central meridian 33E) and UTM zone 36N.
# This lets the same corpus exercise both a national and an international grid.
# --------------------------------------------------------------------------
LON0, LAT0 = 33.0, 39.0


def pt(dx=0.0, dy=0.0):
    return [round(LON0 + dx, 6), round(LAT0 + dy, 6)]


def feat(geom, props, fid=None):
    f = {"type": "Feature", "geometry": geom, "properties": props}
    if fid is not None:
        f["id"] = fid
    return f


def fc(features):
    return {"type": "FeatureCollection", "features": features}


def write_geojson(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def write_text(path, s):
    path.write_text(s, encoding="utf-8")


def zip_dir(src_dir: Path, zip_path: Path):
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        for p in sorted(src_dir.iterdir()):
            z.write(p, p.name)


# ==========================================================================
# Fixture builders
# ==========================================================================

def f01(d):
    """Long field names, two colliding in their first 10 characters."""
    props = {
        "administrative_unit_name": "Central",
        "administrative_unit_code": "TR-33-001",
        "survey_reference_number": 41207,
        "vegetation_cover_class": "broadleaf",
        "canopy_height_metres": 12.4,
        "measurement_operator": "field team A",
        "instrument_serial_id": "LDM-2291",
        "acquisition_platform": "terrestrial",
        "quality_flag_primary": 1,
        "quality_flag_secondary": 0,
        "notes_field_general": "reference stem",
        "last_revision_author": "TK",
    }
    features = [feat({"type": "Point", "coordinates": pt(i * 0.001, 0)}, dict(props))
                for i in range(5)]
    write_geojson(d / "F01_long_field_names.geojson", fc(features))


def f02(d):
    """Mixed attribute types: large integer, float, boolean, null, date-time."""
    rows = [
        {"big_int": 12345678901234, "ratio": 0.333333333, "is_valid": True,
         "optional": None, "observed_at": "2026-03-14T09:27:41Z", "label": "A"},
        {"big_int": -9876543210987, "ratio": -1.5, "is_valid": False,
         "optional": "", "observed_at": "2026-03-14T18:02:00Z", "label": "B"},
        {"big_int": 0, "ratio": 0.0, "is_valid": None,
         "optional": "present", "observed_at": "2026-12-31T23:59:59Z", "label": "C"},
    ]
    features = [feat({"type": "Point", "coordinates": pt(i * 0.001, 0.001)}, r)
                for i, r in enumerate(rows)]
    write_geojson(d / "F02_attribute_types.geojson", fc(features))


def f03(d):
    """Text value exceeding the 254-character DBF limit."""
    long_text = ("This description exceeds the two hundred and fifty four character "
                 "limit imposed by the dBASE III field format used inside shapefiles, "
                 "and is included so that a converter must either truncate the value, "
                 "reject it, or promote the field to an alternative storage strategy. "
                 "Total length is stated in the manifest.")
    features = [feat({"type": "Point", "coordinates": pt(0.002, 0.002)},
                     {"description": long_text, "char_count": len(long_text)})]
    write_geojson(d / "F03_wide_text.geojson", fc(features))
    return {"char_count": len(long_text)}


def f04(d):
    """Non-ASCII attribute values across several Latin-script languages."""
    rows = [
        {"place_name": "Çağlayan Sokağı No:12/İ", "language": "Turkish"},
        {"place_name": "Ærøskøbing", "language": "Danish"},
        {"place_name": "Kraków Śródmieście", "language": "Polish"},
        {"place_name": "Ñuñoa", "language": "Spanish"},
        {"place_name": "Nový Jičín", "language": "Czech"},
    ]
    features = [feat({"type": "Point", "coordinates": pt(i * 0.001, 0.003)}, r)
                for i, r in enumerate(rows)]
    write_geojson(d / "F04_non_ascii.geojson", fc(features))


def f05(d):
    """Polygon with two interior rings."""
    outer = [pt(0, 0), pt(0.02, 0), pt(0.02, 0.02), pt(0, 0.02), pt(0, 0)]
    hole1 = [pt(0.004, 0.004), pt(0.004, 0.008), pt(0.008, 0.008),
             pt(0.008, 0.004), pt(0.004, 0.004)]
    hole2 = [pt(0.012, 0.012), pt(0.012, 0.016), pt(0.016, 0.016),
             pt(0.016, 0.012), pt(0.012, 0.012)]
    g = {"type": "Polygon", "coordinates": [outer, hole1, hole2]}
    write_geojson(d / "F05_polygon_with_holes.geojson",
                  fc([feat(g, {"parcel_id": "P-001", "area_class": "urban"})]))


def f06(d):
    """One feature, three disjoint polygon parts."""
    def sq(ox, oy):
        return [pt(ox, oy), pt(ox + 0.004, oy), pt(ox + 0.004, oy + 0.004),
                pt(ox, oy + 0.004), pt(ox, oy)]
    g = {"type": "MultiPolygon",
         "coordinates": [[sq(0, 0.03)], [sq(0.01, 0.03)], [sq(0.02, 0.03)]]}
    write_geojson(d / "F06_multipart_single_feature.geojson",
                  fc([feat(g, {"holding_id": "H-77", "part_count": 3})]))


def f07(d):
    """Point, line and polygon in one collection."""
    features = [
        feat({"type": "Point", "coordinates": pt(0, 0.04)}, {"kind": "point"}),
        feat({"type": "LineString",
              "coordinates": [pt(0.005, 0.04), pt(0.01, 0.042), pt(0.015, 0.04)]},
             {"kind": "line"}),
        feat({"type": "Polygon",
              "coordinates": [[pt(0.02, 0.04), pt(0.024, 0.04),
                               pt(0.024, 0.044), pt(0.02, 0.044), pt(0.02, 0.04)]]},
             {"kind": "polygon"}),
    ]
    write_geojson(d / "F07_mixed_geometry_types.geojson", fc(features))


def f08(d):
    """Shapefile source carrying genuine Z and M values (PolyLineZ)."""
    sub = d / "F08_polyline_zm"
    sub.mkdir(exist_ok=True)
    base = str(sub / "F08_polyline_zm")
    w = shapefile.Writer(base, shapeType=shapefile.POLYLINEZ)
    w.field("route_id", "C", 12)
    w.field("survey_run", "N", 6, 0)
    # [x, y, z, m]
    w.linez([[[LON0 + 0.000, LAT0 + 0.050, 812.35, 0.0],
              [LON0 + 0.005, LAT0 + 0.052, 845.10, 431.7],
              [LON0 + 0.010, LAT0 + 0.051, 903.62, 887.2],
              [LON0 + 0.015, LAT0 + 0.053, 951.08, 1352.9]]])
    w.record("R-01", 1)
    w.linez([[[LON0 + 0.020, LAT0 + 0.050, 640.00, 0.0],
              [LON0 + 0.025, LAT0 + 0.055, 702.45, 705.3]]])
    w.record("R-02", 2)
    w.close()
    (sub / "F08_polyline_zm.prj").write_text(
        'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
        'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
        'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
        encoding="utf-8")
    (sub / "F08_polyline_zm.cpg").write_text("UTF-8", encoding="utf-8")
    zip_dir(sub, d / "F08_polyline_zm.zip")
    shutil.rmtree(sub)


def f09(d):
    """Polygon whose exterior ring is clockwise, violating RFC 7946."""
    ring_ccw = [pt(0, 0.06), pt(0.006, 0.06), pt(0.006, 0.066),
                pt(0, 0.066), pt(0, 0.06)]
    ring_cw = list(reversed(ring_ccw))
    g = {"type": "Polygon", "coordinates": [ring_cw]}
    write_geojson(d / "F09_clockwise_exterior_ring.geojson",
                  fc([feat(g, {"winding": "clockwise_exterior"})]))


def f10(d):
    """Five features, two of which carry no geometry."""
    features = [
        feat({"type": "Point", "coordinates": pt(0.000, 0.07)}, {"row": 1, "state": "geom"}),
        feat(None, {"row": 2, "state": "null_geometry"}),
        feat({"type": "Point", "coordinates": pt(0.002, 0.07)}, {"row": 3, "state": "geom"}),
        feat(None, {"row": 4, "state": "null_geometry"}),
        feat({"type": "Point", "coordinates": pt(0.004, 0.07)}, {"row": 5, "state": "geom"}),
    ]
    write_geojson(d / "F10_null_geometry.geojson", fc(features))


def f11(d):
    """Self-intersecting exterior ring (bow-tie)."""
    ring = [pt(0, 0.08), pt(0.008, 0.008 + 0.08), pt(0.008, 0.08),
            pt(0, 0.008 + 0.08), pt(0, 0.08)]
    g = {"type": "Polygon", "coordinates": [ring]}
    write_geojson(d / "F11_self_intersecting_ring.geojson",
                  fc([feat(g, {"validity": "self_intersecting"})]))


def f12(d):
    """Coordinates carried to nine decimal places."""
    coords = [[33.123456789, 39.987654321],
              [33.234567891, 39.876543219],
              [33.345678912, 39.765432198]]
    features = [feat({"type": "Point", "coordinates": c},
                     {"vertex": i + 1}) for i, c in enumerate(coords)]
    write_geojson(d / "F12_coordinate_precision.geojson", fc(features))


def f13(d):
    """Shapefile in projected coordinates with no .prj sidecar."""
    sub = d / "F13_no_prj"
    sub.mkdir(exist_ok=True)
    base = str(sub / "F13_no_prj")
    w = shapefile.Writer(base, shapeType=shapefile.POINT)
    w.field("station", "C", 10)
    # Plausible TUREF / TM33 easting-northing values (false easting 500000)
    for i, (x, y) in enumerate([(500123.456, 4317890.123),
                                (501987.654, 4318456.789),
                                (499876.543, 4316234.567)]):
        w.point(x, y)
        w.record(f"ST-{i+1:02d}")
    w.close()
    # deliberately no .prj and no .cpg
    zip_dir(sub, d / "F13_no_prj.zip")
    shutil.rmtree(sub)


def f14(d):
    """Datum-shift accuracy probe: a regular grid of control locations.

    This fixture does NOT test loss reporting. It supplies the test locations
    for a separate accuracy measurement. Authoritative reference coordinates
    must be supplied externally (see fixtures/EXTERNAL_DATA.md).
    """
    features = []
    n = 0
    for i in range(10):
        for j in range(5):
            lon = 26.0 + i * 1.4
            lat = 36.5 + j * 1.3
            n += 1
            features.append(feat({"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]},
                                 {"control_id": f"C-{n:03d}",
                                  "reference_easting": None,
                                  "reference_northing": None,
                                  "reference_source": None}))
    write_geojson(d / "F14_datum_control_points.geojson", fc(features))
    return {"point_count": n}


def f15(d):
    """Geographic coordinates destined for a linear-unit target."""
    ring = [pt(0, 0.09), pt(0.01, 0.09), pt(0.01, 0.10), pt(0, 0.10), pt(0, 0.09)]
    write_geojson(d / "F15_geographic_units.geojson",
                  fc([feat({"type": "Polygon", "coordinates": [ring]},
                           {"note": "extent is 0.01 degrees across"})]))


def f16(d):
    """Layer-defining attribute with spaces, punctuation, non-ASCII and length."""
    names = [
        "Protected Area / Zone A",
        "Sürdürülebilir Peyzaj Birimi",
        "very long layer name used to exceed target limits 01",
        "layer.with.dots",
    ]
    features = [feat({"type": "Point", "coordinates": pt(i * 0.002, 0.11)},
                     {"layer_name": nm, "seq": i + 1}) for i, nm in enumerate(names)]
    write_geojson(d / "F16_layer_names.geojson", fc(features))


def f17(d):
    """KML carrying explicit styles."""
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
 <Document>
  <name>F17 styled</name>
  <Style id="thickRed">
   <LineStyle><color>ff0000ff</color><width>4</width></LineStyle>
   <PolyStyle><color>7f0000ff</color></PolyStyle>
  </Style>
  <Style id="greenPin">
   <IconStyle><color>ff00ff00</color><scale>1.4</scale>
    <Icon><href>http://maps.google.com/mapfiles/kml/paddle/grn-circle.png</href></Icon>
   </IconStyle>
  </Style>
  <Placemark>
   <name>styled polygon</name><styleUrl>#thickRed</styleUrl>
   <Polygon><outerBoundaryIs><LinearRing><coordinates>
    {LON0},{LAT0+0.12},0 {LON0+0.01},{LAT0+0.12},0 {LON0+0.01},{LAT0+0.13},0 {LON0},{LAT0+0.13},0 {LON0},{LAT0+0.12},0
   </coordinates></LinearRing></outerBoundaryIs></Polygon>
  </Placemark>
  <Placemark>
   <name>styled point</name><styleUrl>#greenPin</styleUrl>
   <Point><coordinates>{LON0+0.02},{LAT0+0.125},0</coordinates></Point>
  </Placemark>
 </Document>
</kml>
"""
    write_text(d / "F17_styled.kml", kml)


def f18(d):
    """KML with three levels of nested folders."""
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
 <Document>
  <name>F18 nested folders</name>
  <Folder><name>Level 1 - Region</name>
   <Folder><name>Level 2 - District</name>
    <Folder><name>Level 3 - Block</name>
     <Placemark><name>deep point</name>
      <Point><coordinates>{LON0},{LAT0+0.14},0</coordinates></Point></Placemark>
    </Folder>
    <Placemark><name>district point</name>
     <Point><coordinates>{LON0+0.005},{LAT0+0.14},0</coordinates></Point></Placemark>
   </Folder>
   <Placemark><name>region point</name>
    <Point><coordinates>{LON0+0.01},{LAT0+0.14},0</coordinates></Point></Placemark>
  </Folder>
 </Document>
</kml>
"""
    write_text(d / "F18_nested_folders.kml", kml)


def f19(d):
    """Stable feature identifiers at the GeoJSON member level."""
    features = [feat({"type": "Point", "coordinates": pt(i * 0.002, 0.15)},
                     {"name": f"node {i+1}"}, fid=f"NODE-{i+1:04d}")
                for i in range(4)]
    write_geojson(d / "F19_feature_identifiers.geojson", fc(features))


def f20(d):
    """KML placemark names used as map labels."""
    pts = [("Kayalı Reservoir", 0.0), ("Longoz Forest edge", 0.006),
           ("Survey benchmark 12", 0.012)]
    body = "".join(
        f"""
  <Placemark><name>{nm}</name>
   <Point><coordinates>{LON0+dx},{LAT0+0.16},0</coordinates></Point></Placemark>"""
        for nm, dx in pts)
    kml = f"""<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
 <Document>
  <name>F20 labels</name>{body}
 </Document>
</kml>
"""
    write_text(d / "F20_labels.kml", kml)


def f24(d):
    """CSV whose coordinate columns are ordered latitude-first.

    EPSG:4326 declares latitude before longitude, while GeoJSON, KML and most
    software order longitude first. A CSV that follows the authority order is
    the commonest way this ambiguity reaches a converter, and the values here
    are chosen so that a swap is unmistakable rather than merely wrong: the
    latitudes are valid longitudes and vice versa.
    """
    rows = [
        ("BM-01", 39.010000, 33.010000),
        ("BM-02", 39.020000, 33.020000),
        ("BM-03", 39.030000, 33.030000),
    ]
    lines = ["station,latitude,longitude"]
    lines += [f"{n},{lat:.6f},{lon:.6f}" for n, lat, lon in rows]
    write_text(d / "F24_axis_order.csv", "\n".join(lines) + "\n")


# ==========================================================================
# Specification table: fixture -> expected loss codes per target format
# "conditional" codes are those whose occurrence depends on a writer choice
# the target format permits but does not require. They are the most
# diagnostic cases and are scored separately.
# ==========================================================================

TARGETS = ["shapefile", "dxf", "geojson", "kml", "csv"]

SPEC = [
    {"id": "F01", "file": "F01_long_field_names.geojson", "source": "geojson",
     "builder": f01, "role": "audit",
     "rationale": "Twelve field names of 14-22 characters; 'administrative_unit_name' and 'administrative_unit_code' share their first ten characters.",
     "expected": {"shapefile": ["A1", "A2"], "dxf": ["A8"], "geojson": [], "kml": [], "csv": []}},

    {"id": "F02", "file": "F02_attribute_types.geojson", "source": "geojson",
     "builder": f02, "role": "audit",
     "rationale": "Integers beyond 32-bit range, floats, booleans, nulls and ISO 8601 date-times in one table.",
     "expected": {"shapefile": ["A3", "A5", "A6"], "dxf": ["A8"], "geojson": [],
                  "kml": ["A3"], "csv": ["A3", "A6"]}},

    {"id": "F03", "file": "F03_wide_text.geojson", "source": "geojson",
     "builder": f03, "role": "audit",
     "rationale": "Single text value longer than the 254-character dBASE III limit.",
     "expected": {"shapefile": ["A4"], "dxf": ["A8"], "geojson": [], "kml": [], "csv": []}},

    {"id": "F04", "file": "F04_non_ascii.geojson", "source": "geojson",
     "builder": f04, "role": "audit",
     "rationale": "Latin-script non-ASCII characters from five languages, including the dotted capital I.",
     "expected": {"shapefile": ["A7"], "dxf": ["A7", "A8"], "geojson": [], "kml": [],
                  "csv": ["A7"]},
     "conditional": {"shapefile": ["A7"], "csv": ["A7"]}},

    {"id": "F05", "file": "F05_polygon_with_holes.geojson", "source": "geojson",
     "builder": f05, "role": "audit",
     "rationale": "One exterior ring enclosing two interior rings.",
     "expected": {"shapefile": ["B6"], "dxf": ["B3", "A8", "D1"], "geojson": [],
                  "kml": [], "csv": ["B10"]}},

    {"id": "F06", "file": "F06_multipart_single_feature.geojson", "source": "geojson",
     "builder": f06, "role": "control",
     "rationale": "Negative control. Shapefile and KML both represent multipart geometry natively; a converter that splits this feature has introduced loss the format did not require.",
     "expected": {"shapefile": ["B6"], "dxf": ["B4", "A8", "D1"], "geojson": [],
                  "kml": [], "csv": ["B4", "B10"]}},

    {"id": "F07", "file": "F07_mixed_geometry_types.geojson", "source": "geojson",
     "builder": f07, "role": "audit",
     "rationale": "Point, line and polygon in a single collection; shapefile permits only one geometry type per file.",
     "expected": {"shapefile": ["B5"], "dxf": ["A8"], "geojson": [], "kml": [],
                  "csv": ["B5", "B10"]}},

    {"id": "F08", "file": "F08_polyline_zm.zip", "source": "shapefile",
     "builder": f08, "role": "audit",
     "rationale": "PolyLineZ with populated Z and M arrays; M has no representation in GeoJSON, KML or DXF R12.",
     "expected": {"shapefile": [], "dxf": ["B2", "A8"], "geojson": ["B1", "B2"],
                  "kml": ["B2"], "csv": ["B1", "B2", "B10"]},
     "conditional": {"geojson": ["B1"]}},

    {"id": "F09", "file": "F09_clockwise_exterior_ring.geojson", "source": "geojson",
     "builder": f09, "role": "audit",
     "rationale": "Exterior ring wound clockwise, contrary to RFC 7946. Shapefile requires exactly this orientation, so the direction of any correction is diagnostic.",
     "expected": {"shapefile": [], "dxf": ["A8"], "geojson": ["B6"], "kml": [], "csv": ["B10"]}},

    {"id": "F10", "file": "F10_null_geometry.geojson", "source": "geojson",
     "builder": f10, "role": "audit",
     "rationale": "Two of five features carry null geometry. Shapefile can encode these as null shapes, so dropping them is a writer choice rather than a format limit.",
     "expected": {"shapefile": ["B7"], "dxf": ["B7", "A8"], "geojson": [],
                  "kml": ["B7"], "csv": ["B10"]},
     "conditional": {"shapefile": ["B7"]}},

    {"id": "F11", "file": "F11_self_intersecting_ring.geojson", "source": "geojson",
     "builder": f11, "role": "audit",
     "rationale": "Bow-tie exterior ring. Both silent pass-through and silent repair count as unreported alteration.",
     "expected": {"shapefile": ["B8"], "dxf": ["B8", "A8"], "geojson": ["B8"],
                  "kml": ["B8"], "csv": ["B10"]}},

    {"id": "F12", "file": "F12_coordinate_precision.geojson", "source": "geojson",
     "builder": f12, "role": "audit",
     "rationale": "Nine decimal places, roughly 0.1 mm at this latitude. Binary shapefile storage is lossless; every ASCII target depends on writer formatting.",
     "expected": {"shapefile": [], "dxf": ["B9", "A8"], "geojson": ["B9"],
                  "kml": ["B9"], "csv": ["B9"]},
     "conditional": {"dxf": ["B9"], "geojson": ["B9"], "kml": ["B9"], "csv": ["B9"]}},

    {"id": "F13", "file": "F13_no_prj.zip", "source": "shapefile",
     "builder": f13, "role": "audit",
     "rationale": "Projected coordinates with neither .prj nor .cpg. Any output CRS is an assumption the converter must declare.",
     "expected": {"shapefile": ["C1"], "dxf": ["C1", "A8"], "geojson": ["C1"],
                  "kml": ["C1"], "csv": ["C1"]}},

    {"id": "F14", "file": "F14_datum_control_points.geojson", "source": "geojson",
     "builder": f14, "role": "accuracy",
     "rationale": "Fifty control locations on a regular grid spanning the national extent. Used for the datum-shift accuracy measurement, not the reporting audit. Reference coordinates must be supplied externally.",
     "expected": {t: [] for t in TARGETS},
     "accuracy_codes": ["C2"],
     "note": "Excluded from reporting-audit totals. Exercises C2 as a metric measurement rather than a disclosure observation. See EXTERNAL_DATA.md."},

    {"id": "F15", "file": "F15_geographic_units.geojson", "source": "geojson",
     "builder": f15, "role": "audit",
     "rationale": "Geographic coordinates written to a CAD target whose consumers assume linear units; the drawing extent would be 0.01 units across.",
     "expected": {"shapefile": [], "dxf": ["C3", "A8"], "geojson": [], "kml": [],
                  "csv": ["B10"]}},

    {"id": "F16", "file": "F16_layer_names.geojson", "source": "geojson",
     "builder": f16, "role": "audit",
     "rationale": "Layer-defining values containing spaces, a solidus, dots, non-ASCII characters and a name exceeding 31 characters.",
     "expected": {"shapefile": ["D1"], "dxf": ["D1", "A8"], "geojson": [], "kml": [],
                  "csv": []}},

    {"id": "F17", "file": "F17_styled.kml", "source": "kml",
     "builder": f17, "role": "audit",
     "rationale": "Explicit line, polygon and icon styles. DXF can carry colour on layers, so partial retention is possible.",
     "expected": {"shapefile": ["D2"], "dxf": ["D2", "A8"], "geojson": ["D2"],
                  "kml": [], "csv": ["D2", "B10"]},
     "conditional": {"dxf": ["D2"]}},

    {"id": "F18", "file": "F18_nested_folders.kml", "source": "kml",
     "builder": f18, "role": "audit",
     "rationale": "Three levels of folder nesting with placemarks at each level.",
     "expected": {"shapefile": ["D3"], "dxf": ["D3", "A8"], "geojson": ["D3"],
                  "kml": [], "csv": ["D3"]},
     "conditional": {"dxf": ["D3"]}},

    {"id": "F19", "file": "F19_feature_identifiers.geojson", "source": "geojson",
     "builder": f19, "role": "audit",
     "rationale": "Identifiers live in the GeoJSON 'id' member, not in properties, so a converter that copies only properties will drop them.",
     "expected": {"shapefile": ["D4"], "dxf": ["D4", "A8"], "geojson": [],
                  "kml": ["D4"], "csv": ["D4"]},
     "conditional": {"shapefile": ["D4"], "kml": ["D4"], "csv": ["D4"]}},

    {"id": "F20", "file": "F20_labels.kml", "source": "kml",
     "builder": f20, "role": "audit",
     "rationale": "Placemark names carry label text. Retention depends on whether the writer maps them to an attribute or a text entity.",
     "expected": {"shapefile": ["D5"], "dxf": ["D5", "A8"], "geojson": ["D5"],
                  "kml": [], "csv": ["D5", "B10"]},
     "conditional": {"shapefile": ["D5"], "dxf": ["D5"], "geojson": ["D5"], "csv": ["D5"]}},

    {"id": "F24", "file": "F24_axis_order.csv", "source": "csv",
     "builder": f24, "role": "audit",
     "rationale": "Coordinate columns ordered latitude-first, matching the EPSG:4326 authority order but contradicting the longitude-first convention of GeoJSON and KML. Values lie in a band where a swap remains geographically plausible, so it cannot be caught by a range test alone.",
     "expected": {"shapefile": ["C4", "C1"], "dxf": ["C4", "C1", "C3", "A8"],
                  "geojson": ["C4", "C1"], "kml": ["C4", "C1"], "csv": ["C4"]},
     "conditional": {"shapefile": ["C4"], "dxf": ["C4"], "geojson": ["C4"],
                     "kml": ["C4"], "csv": ["C4"]}},

    # ---- Real-world fixtures, supplied externally ----
    {"id": "F21", "file": "F21_cadastral_parcels.zip", "source": "shapefile",
     "builder": None, "role": "audit",
     "rationale": "Real cadastral parcel extract. Compound case: holes, long Turkish field names, projected national CRS.",
     "expected": None, "external": True},

    {"id": "F22", "file": "F22_tree_inventory.zip", "source": "shapefile",
     "builder": None, "role": "audit",
     "rationale": "Real campus tree inventory. Compound case: Z values, non-ASCII species and location names, wide text notes.",
     "expected": None, "external": True},

    {"id": "F23", "file": "F23_linear_network.geojson", "source": "geojson",
     "builder": None, "role": "audit",
     "rationale": "Real linear network extract. Compound case: multipart lines, dense vertices, mixed attribute types.",
     "expected": None, "external": True},
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="fixtures")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    extras = {}
    for spec in SPEC:
        if spec["builder"] is None:
            continue
        r = spec["builder"](out)
        if r:
            extras[spec["id"]] = r

    manifest = {
        "manifest_version": "1.0",
        "taxonomy": "taxonomy.json",
        "coordinate_anchor": {"lon": LON0, "lat": LAT0,
                              "note": "TUREF / TM33 and UTM zone 36N both apply at this location."},
        "targets": TARGETS,
        "scoring": {
            "audit_denominator": "codes listed in 'expected' for fixtures with role == 'audit' or 'control'",
            "conditional_handling": "codes listed in 'conditional' are scored in a separate stratum; their occurrence is a writer choice the target format permits but does not require",
            "excluded": "fixtures with role == 'accuracy' contribute no codes to the reporting audit"
        },
        "fixtures": []
    }

    for spec in SPEC:
        entry = {k: v for k, v in spec.items() if k != "builder"}
        if spec["id"] in extras:
            entry["measured"] = extras[spec["id"]]
        manifest["fixtures"].append(entry)

    (out.parent / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    files = sorted(p.name for p in out.iterdir())
    print(f"{len(files)} fixture files written to {out}/")
    for f in files:
        print("  ", f)


if __name__ == "__main__":
    main()
