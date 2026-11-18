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

{{TABLES}}

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

{{SUMMARY}}

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
