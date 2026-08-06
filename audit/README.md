# Loss disclosure audit

Measures what each conversion actually loses against what the tool reports.

Three stages. Each writes into `work/`, which is disposable.

    npm install jsdom
    pip install pyshp ezdxf

    python 01_build_fixtures.py --out fixtures   # regenerate the corpus
    python 01_expand_zips.py                     # expand the zipped fixtures
    python 01_verify_fixtures.py --dir fixtures  # confirm each fixture holds its condition
    node   02_run_audit.mjs                      # drive the shipped conversion path
    python 03_ground_truth.py                    # read the outputs back, compare, score

## What each stage does

**01** generates 21 synthetic fixtures, each isolating one loss mechanism from
`taxonomy.json`, and emits `manifest.json` from the same specification table so
the two cannot drift apart. `01_verify_fixtures.py` then confirms every fixture
actually exhibits the condition it claims to test; a fixture that does not would
inflate every downstream number silently.

**02** assembles the page from `src/` and loads it in a DOM, then calls the same
`ingest`, `checkOutput` and `convert` entry points the interface uses. Nothing is
reimplemented, so what is measured is what a user would get. For every fixture and
every target format it records the diagnostics reported, as message identifiers,
and writes the bytes produced under `work/<fixture>/<target>/`.

`app.harness.html` is a copy of `src/app.html` with one added block exposing those
entry points. It is regenerated from the current source at the top of `02`, so it
cannot fall behind. The shipped file never carries the hook.

Archive packaging is out of scope: the ZIP module is stubbed and shapefile members
are written to disk individually, so the real `.shp`, `.dbf`, `.prj` and `.cpg`
bytes can be read back with independent libraries.

**03** loads source and output into one normalised model (geometry with its
dimensionality, attributes, identifier, label) and maps differences onto the
taxonomy. Codes that follow from what the target format is, rather than from a
model difference, are derived from format capability plus source content and are
reported separately, so the two kinds of evidence are never conflated.

Reported diagnostics are mapped to codes through a fixed table in `03`, keyed on
message identifiers rather than on message text.

## Reading the result

Per family: how many losses occurred, how many were reported, and the share that
were not. A high silent share is not by itself a defect. Some mechanisms are
limits of the target format that no converter can avoid, and reporting every one
of them on every conversion would produce a wall of text that users stop reading.
The measurement makes that trade-off visible rather than resolving it.

## A caution learned twice

The ground-truth reader needs validating as much as the software under test. Two
early versions of `03` attributed losses to the tool that it had not caused: one
treated a GeoJSON without a `crs` member as having an undeclared reference system,
though RFC 7946 fixes it; the other took the first two CSV columns as coordinates
regardless of their headers. Both inflated the silent count. Any detector added
here should be checked against a case where the answer is already known.
