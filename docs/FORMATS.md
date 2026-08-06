# What each conversion loses

Every format is less expressive than some other format, so conversion loses
information. This document lists what is lost, per target, and states which
losses the tool reports and which it does not.

The table is not written from memory. It is derived from an audit in which a
corpus of fixtures, each isolating one loss mechanism, was pushed through the
shipped conversion path, and the outputs were read back with independent
libraries (`pyshp`, `ezdxf`) and compared against the sources. The audit lives
in [`audit/`](../audit/) and can be re-run.

Loss mechanisms are named by the codes of the taxonomy in
[`audit/taxonomy.json`](../audit/taxonomy.json): family A attributes and
schema, B geometry, C reference system, D structure and metadata.

**Reported** means the conversion log names the loss. **Silent** means it does
not. A silent loss is not always a defect: some follow inevitably from the
target format, and reporting every one of them on every conversion would
produce a wall of text users stop reading. Where that is the reasoning, it is
stated below.

---

## Shapefile output

The most capable target here, and the most constrained by a 1990s file format.

| Code | Loss | Reported |
|---|---|---|
| A1 | Field name shortened to 10 characters | yes, per field, with both names |
| A2 | Two field names collide after shortening | yes |
| A4 | Text value beyond 254 bytes truncated | yes, per field |
| B1 | Elevation dropped; shapefile output is written as plan geometry | yes |
| B2 | Measure values dropped | yes, at read time |
| B5 | Mixed geometry types split into separate files | yes |
| B7 | Features without geometry not written | yes |
| C1 | Source system undeclared, so it has been assumed | yes |
| D4 | GeoJSON `id` member not carried | yes |
| A3 | Type coercion, for instance a 64-bit integer stored as a double | **silent** |
| A6 | Null and empty string become indistinguishable in DBF | **silent** |
| B6 | Ring orientation normalised to clockwise exterior | **silent** |
| D2 | Style from a KML source dropped | **silent** |
| D3 | Folder hierarchy from a KML source flattened | **silent** |

Notes.

**B6 is a normalisation, not a loss.** The shapefile specification requires a
clockwise exterior ring, where GeoJSON requires counter-clockwise. Reversing
the ring is the correct behaviour and no information is destroyed. It appears
here because the audit observes it as a difference between source and output,
and hiding it would be less honest than explaining it.

**A3 and A6 are real gaps.** DBF has no 64-bit integer and no way to
distinguish null from empty. Neither is currently reported.

Encoding is not in the table because it does not occur: the writer emits a
`.cpg` declaring UTF-8, and non-ASCII attribute values survive intact. The
`log.shp.fieldNote` message states this rather than warning about it.

## DXF output

DXF R12 (AC1009) is a drawing exchange format, not a data format. It carries
geometry, layers and text, and nothing else.

| Code | Loss | Reported |
|---|---|---|
| A8 | All attributes; DXF has no attribute table | yes, on every conversion |
| B2 | Measure values | yes |
| B7 | Features without geometry | yes |
| D4 | GeoJSON `id` member | yes |
| C3 | Angular units in a unitless format | yes, and the conversion is refused |
| D5 | Placemark names from a KML source | **silent** |
| D2 | Style | **silent** |
| D3 | Folder hierarchy | **silent** |

Notes.

**Elevation is carried.** Vertices are written with group code 30 holding the
real Z value. This was not always true; the audit found it hard-coded to zero.

**Holes are separate polylines.** DXF R12 has no concept of a ring inside
another ring. An area with holes is written as several closed polylines, and
CAD will not treat the inner ones as holes automatically. This is stated on
every DXF conversion, in `log.dxf.formatNote`, together with the attribute
loss.

**Degrees are refused, not warned about.** DXF has no units. A drawing built
from geographic coordinates measures a fraction of a unit across, and every
scale, length and area calculation in CAD becomes meaningless. The tool blocks
the conversion and offers a switch to the nearest metre-based zone.

**One attribute survives, by choice.** The layer field is written as the DXF
layer name, and the label field as TEXT entities. Layer names are transliterated
to ASCII and shortened to 31 characters; that transliteration is reported per
layer.

## GeoJSON output

The least lossy target, and the only one that preserves feature identifiers.

| Code | Loss | Reported |
|---|---|---|
| B2 | Measure values, which RFC 7946 cannot represent | yes, at read time |
| C1 | Source system undeclared, so it has been assumed | yes |
| D2 | Style from a KML source | **silent** |
| D3 | Folder hierarchy from a KML source | **silent** |

Notes.

**Elevation is carried** as the third coordinate element, which RFC 7946
permits.

**Coordinate precision is preserved.** Nine decimal places survive unchanged.

**RFC 7946 recognises WGS 84 only.** If the output is written in another
system, the file itself cannot say so, and `log.geojson.notWgs84` states that
the system must be communicated separately.

## KML output

| Code | Loss | Reported |
|---|---|---|
| B2 | Measure values | yes |
| B7 | Features without geometry | yes |
| C1 | Source system undeclared, so it has been assumed | yes |
| D4 | GeoJSON `id` member | yes |
| A3 | All attribute values become strings in ExtendedData | **silent** |
| B6 | Ring orientation | **silent** |

Notes.

**Elevation is carried** as the third component of each coordinate.

**KML is defined on WGS 84.** Output is converted to WGS 84 automatically, and
this is stated.

**A3 is the largest silent gap in the tool.** Every numeric and boolean value
becomes text. A table exported to KML and read back has lost its types.

## CSV output

A tabular format, so geometry beyond a point cannot survive.

| Code | Loss | Reported |
|---|---|---|
| B10 | Lines and areas reduced to a representative point | yes |
| B1 | Elevation | yes |
| B2 | Measure values | yes |
| B7 | Features without geometry | yes |
| C1 | Source system undeclared; CSV has nowhere to record one | yes |
| D4 | GeoJSON `id` member | yes |
| A3 | All values become strings | **silent** |
| A6 | Null and empty string indistinguishable | **silent** |
| D2 | Style | **silent** |
| D3 | Folder hierarchy | **silent** |

Notes.

**Coordinate precision is preserved.** Nine decimal places survive.

**The file is written with a UTF-8 byte order mark** so that spreadsheet
software opens non-ASCII text correctly.

---

## Reference system

The source system is read from a `.prj` sidecar when one is present. When it is
absent the tool says so (`log.crs.noPrj`) and asks for a manual choice, after
guessing from the coordinate range.

**A zone cannot be guessed, and the tool no longer pretends otherwise.**
Coordinate ranges distinguish geographic from projected, and a false-easting
grid from Web Mercator, but they cannot identify which zone a grid belongs to:
every three-degree zone places its central meridian at 500,000, so TM27 and
TM45 data look identical. In that case the tool says so and asks, rather than
returning a guess dressed as a determination.

**CSV carries no reference system at all.** There is no `.prj` equivalent and
no header convention, so the ambiguity is structural rather than an omission by
whoever produced the file. Every CSV read is reported as such, with a reminder
to check column order, since latitude-first files are common.

**ED50 is approximate.** The transformation is a Europe-mean three-parameter
shift, not the national grid-based transformation. It is accurate to a few
metres and must not be used for cadastral, zoning or setting-out work. It
exists because much CAD data circulating in Türkiye is in ED50, and treating
that data as WGS 84 without saying so would be a far larger error.

## Projection accuracy

Transverse Mercator agreement with PROJ, measured over 19,459 points in 11
zones, maximum values in metres:

| | zone interior (within 2°) | zone edge (2° to 3°) |
|---|---|---|
| Forward | 3.05e-6 | 4.85e-5 |
| Inverse | 1.88e-5 | 3.22e-4 |
| Round trip | 2.12e-5 | 3.60e-4 |

Details and the method are in the main [README](../README.md).

---

## Summary of what is not reported

Five mechanisms are never reported, and they are the honest answer to "what
would you improve first":

- **A3, type coercion** to KML and CSV. Silent in 17 of the audited
  conversions, the largest single gap by a wide margin.
- **D2, style**, and **D3, folder hierarchy**, from KML sources into every
  other target.
- **D5, label text**, into DXF.
- **A6, null against empty**, in DBF and CSV.

A sixth, **B6, ring winding**, is counted as silent by the audit but is not
information loss: shapefile requires a clockwise exterior ring where GeoJSON
requires counter-clockwise, so reversing it is correct behaviour.

Across the audited corpus, 111 losses occurred in 100 conversions and 77 were
reported, leaving 31 per cent silent. Thirty of the hundred conversions carried
at least one silent loss. By target the silent share runs from 11 per cent for
DXF, where the format carries so little that the losses are stated wholesale,
to 64 per cent for KML, where every attribute value quietly becomes a string.

That figure measures a trade-off rather than counting defects. Reporting every
format-inherent limit on every conversion would bury the per-feature
diagnostics that are actually actionable. The corpus makes the trade-off
measurable, which is the point of publishing it.
