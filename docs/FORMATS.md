# What each conversion loses

Every format is less expressive than some other format, so conversion loses
information. This document lists what is lost, per target, and states which
losses the tool reports and which it does not.

The tables are not written from memory. They are derived from an audit in which
a corpus of fixtures, each isolating one source condition, was pushed through
the shipped conversion path, and the outputs were read back with independent
libraries (`pyshp`, `ezdxf`) and compared against the sources. The audit lives
in [`audit/`](../audit/) and can be re-run.

Loss mechanisms are named by the codes of the taxonomy in
[`audit/taxonomy.json`](../audit/taxonomy.json).

Taxonomy version 1.2. 100 conversions, 113 losses, 78 reported. The tables below are generated; do not edit them by hand.

**Reported** means the conversion log named the loss while it happened. A
loss that is not reported is not necessarily worse, but the user has no way
to know it occurred.

## Shapefile

20 conversions in the audit corpus.

| Code | Mechanism | Occurred | Reported |
|---|---|---|---|
| A1 | Field name truncation | 3 | 3 |
| A2 | Field name collision after truncation | 1 | 1 |
| A3 | Type coercion | 1 | 0  ⚠ |
| A4 | Width or precision overflow | 1 | 1 |
| A6 | Null indistinguishable from empty | 1 | 0  ⚠ |
| B1 | Z coordinate loss | 1 | 1 |
| B2 | M coordinate loss | 1 | 1 |
| B5 | Mixed geometry type coercion | 2 | 2 |
| B6 | Ring winding convention change | 3 | 0  ⚠ |
| B7 | Empty or null geometry dropped | 1 | 1 |
| C1 | Undeclared source CRS | 2 | 2 |
| D2 | Style loss | 1 | 0  ⚠ |
| D3 | Hierarchy flattening | 1 | 0  ⚠ |
| D4 | Feature identifier loss | 1 | 1 |

Not fully reported: A3 (type coercion), A6 (null indistinguishable from empty), B6 (ring winding convention change), D2 (style loss), D3 (hierarchy flattening).

## DXF (AC1009 / R12)

20 conversions in the audit corpus.

| Code | Mechanism | Occurred | Reported |
|---|---|---|---|
| A8 | Complete attribute loss | 17 | 17 |
| B2 | M coordinate loss | 1 | 1 |
| B3 | Ring containment loss | 1 | 1 |
| B4 | Multipart feature split | 1 | 0  ⚠ |
| B7 | Empty or null geometry dropped | 1 | 1 |
| C1 | Undeclared source CRS | 2 | 2 |
| C3 | Angular units in a linear-unit target | 20 | 20 |
| D2 | Style loss | 1 | 0  ⚠ |
| D3 | Hierarchy flattening | 1 | 0  ⚠ |
| D4 | Feature identifier loss | 1 | 1 |
| D5 | Label or annotation loss | 3 | 0  ⚠ |

Not fully reported: B4 (multipart feature split), D2 (style loss), D3 (hierarchy flattening), D5 (label or annotation loss).

## GeoJSON

20 conversions in the audit corpus.

| Code | Mechanism | Occurred | Reported |
|---|---|---|---|
| B2 | M coordinate loss | 1 | 1 |
| C1 | Undeclared source CRS | 2 | 2 |
| D2 | Style loss | 1 | 0  ⚠ |
| D3 | Hierarchy flattening | 1 | 0  ⚠ |

Not fully reported: D2 (style loss), D3 (hierarchy flattening).

## KML

20 conversions in the audit corpus.

| Code | Mechanism | Occurred | Reported |
|---|---|---|---|
| A3 | Type coercion | 8 | 0  ⚠ |
| B2 | M coordinate loss | 1 | 1 |
| B6 | Ring winding convention change | 1 | 0  ⚠ |
| B7 | Empty or null geometry dropped | 1 | 1 |
| C1 | Undeclared source CRS | 2 | 2 |
| D4 | Feature identifier loss | 1 | 1 |

Not fully reported: A3 (type coercion), B6 (ring winding convention change).

## CSV

20 conversions in the audit corpus.

| Code | Mechanism | Occurred | Reported |
|---|---|---|---|
| A3 | Type coercion | 8 | 0  ⚠ |
| A6 | Null indistinguishable from empty | 1 | 0  ⚠ |
| B1 | Z coordinate loss | 1 | 1 |
| B2 | M coordinate loss | 1 | 1 |
| B7 | Empty or null geometry dropped | 1 | 1 |
| B10 | Geometry degraded to a representative position | 8 | 8 |
| C1 | Undeclared source CRS | 2 | 2 |
| D2 | Style loss | 1 | 0  ⚠ |
| D3 | Hierarchy flattening | 1 | 0  ⚠ |
| D4 | Feature identifier loss | 1 | 1 |

Not fully reported: A3 (type coercion), A6 (null indistinguishable from empty), D2 (style loss), D3 (hierarchy flattening).


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

These mechanisms occur and are never reported, in any conversion:

- **A3, type coercion** — 17 occurrences.
- **A6, null indistinguishable from empty** — 2 occurrences.
- **B4, multipart feature split** — 1 occurrence.
- **B6, ring winding convention change** — 4 occurrences.
- **D2, style loss** — 4 occurrences.
- **D3, hierarchy flattening** — 4 occurrences.
- **D5, label or annotation loss** — 3 occurrences.

Across the audited corpus, 113 losses occurred in 100 conversions and 78 were reported, leaving 31 per cent silent. 31 of the 100 conversions carried at least one silent loss. By target the silent share runs:

| Target | Occurred | Reported | Silent |
|---|---|---|---|
| Shapefile | 20 | 13 | 35% |
| DXF (AC1009 / R12) | 49 | 43 | 12% |
| GeoJSON | 5 | 3 | 40% |
| KML | 14 | 5 | 64% |
| CSV | 25 | 14 | 44% |


One entry in that list is not information loss. Ring winding is reversed
because the target specification requires it: a shapefile wants a clockwise
exterior ring where GeoJSON wants a counter-clockwise one, so reversing it is
correct behaviour and nothing is destroyed. It is counted because the audit
records a mechanism when it is observed rather than when the observer judges
it harmful, and separating the two is what lets a reader disagree with the
judgement without having to re-measure.

Those figures measure a trade-off rather than counting defects. Reporting every
format-inherent limit on every conversion would bury the per-feature
diagnostics that are actually actionable. The corpus makes the trade-off
measurable, which is the point of publishing it.
