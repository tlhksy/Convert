# Changes from the loss audit

Four files change: `src/geoconv.js`, `src/app.html`, `src/i18n.js`,
`test/geoconv.test.js`.

## What the audit found

Driving the fixture corpus through the shipped conversion path revealed three
undisclosed losses.

**Elevation and measure values were discarded on read.** `parseShape`
recognised shape types 13 and 23 but read only the X and Y arrays, so a
PolyLineZ carrying real surveyed heights arrived in the tool as plan geometry.
The loss happened before the data reached the screen, and nothing was
reported. For a tool used on tree inventories, contours and levelling data this
is the most consequential of the three.

**Feature identifiers were dropped silently.** A GeoJSON `id` member survived
GeoJSON output but vanished in shapefile, DXF, KML and CSV, with no diagnostic.

**Empty geometry was reported under the wrong cause.** Features without
geometry were counted as "unsupported geometry type", which points the user at
the wrong problem.

## What changed

**Elevation is now read and carried.** `parseShape` reads the Z array of the
11/13/15/18 shape family and keeps it as a third ordinate. `reproject` no
longer discards it. Writers that can represent elevation now do: DXF emits the
real value on group code 30 rather than a hard-coded zero, and KML writes it as
the altitude component.

**Losses that cannot be avoided are stated.** Measure values have no
representation in GeoJSON, so their loss is reported at read time rather than
discovered later. Shapefile and CSV output store plan coordinates only, so
elevation loss is reported before writing. Identifier loss is reported for
every target except GeoJSON.

Identifiers are reported rather than preserved. Writing them into an attribute
column would add a field the user did not ask for, which is its own surprise;
stating the loss leaves the decision with them.

**Empty geometry is counted separately** from unsupported geometry types, and
each has its own message.

## Interface note

`readShp(buf, warn)` takes an optional second argument. Existing single-argument
calls behave as before.

## Tests

Four added, covering: elevation read from a PolyLineZ, measure loss reported at
read time, elevation detection across a collection, and elevation surviving
into KML and DXF. The PolyLineZ used is constructed inside the test rather than
loaded from a file, so the test states exactly what it asserts against.

36 of 36 pass locally, excluding the zip suite, which was not run here.
