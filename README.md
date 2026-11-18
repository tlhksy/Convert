# Pafta

[![DOI](https://zenodo.org/badge/1311182553.svg)](https://doi.org/10.5281/zenodo.21842591)

**A vector data converter between GIS and CAD that tells you what it lost.**
Reads Shapefile, GeoJSON, KML, GPX and CSV; writes DXF, Shapefile, GeoJSON, KML
and CSV; transforms coordinate reference systems; and reports, line by line,
what each conversion changed.

Everything runs in the browser. No server, no upload, no external dependencies,
works offline from a single HTML file. Data never leaves the device.

Use it: <https://tlhksy.github.io/Convert/dist/>

[TÃ¼rkÃ§e aÃ§Ä±klama aÅŸaÄŸÄ±da](#tÃ¼rkÃ§e)

## Why

Shapefile to CAD is not a pure format conversion. Coordinate system, attribute
to layer mapping, how labels are written, what happens to polygon holes, field
name limits, character encoding: each one is a decision. Most online converters
either do not ask or answer silently, often wrongly. The result is a file that
does not look broken until someone opens it downstream.

The distinguishing feature is not the conversion but the **conversion log**.
Field name shortened to ten characters, layer name transliterated to ASCII, no
`.cpg` so Latin-1 assumed, polygon hole written as a separate polyline,
elevation values not representable in the target: each is reported, with the
affected item named.

The strictest check refuses DXF export when the target coordinate system is in
degrees. DXF is unitless, so a drawing built from geographic coordinates
measures a fraction of a unit across and every scale and area calculation
becomes meaningless. The tool says so and offers a one-click switch to the
nearest metre-based zone.

## What it does

**Input:** Shapefile (`.zip`, or `.shp` + `.dbf` + siblings), GeoJSON, KML,
GPX, CSV
**Output:** DXF (R12 / AC1009), Shapefile (five files in a ZIP), GeoJSON, KML,
CSV

**Coordinate systems:** WGS 84 geographic, Web Mercator, the Turkish TUREF
three-degree zones (TM27 to TM45, EPSG:5253 to EPSG:5259), all 60 WGS 84 UTM
zones north and south, and the ED50 UTM zones. The source system is read
automatically from a `.prj` sidecar when present.

**Elevation:** Z values are read from the Z shape types (11, 13, 15, 18) and
carried through to GeoJSON, KML and DXF. Shapefile and CSV output store plan
coordinates only, and the loss is reported. Measure values have no
representation in GeoJSON and their loss is reported at read time.

**Preview:** geometry is drawn in the target coordinate system, the cursor
reads out real-world coordinates, and a scale bar plus width and height
readings make the unit visible. Why a degree-based DXF would be broken is
apparent before the warning is read.

**Interface:** English and Turkish, switchable from the header. Defaults to
English unless the browser reports a Turkish locale.

Full per-format loss inventory: **[docs/FORMATS.md](docs/FORMATS.md)**

## Use

Download `dist/index.html` and open it. That is all: no installation, no
network.

To publish from a fork: **Settings â†’ Pages â†’ Source: GitHub Actions**. Every
push to `main` publishes `dist/`.

## Development

```
npm test          # 41 unit tests, no dependencies (node:test)
npm run build     # inlines src/ into dist/index.html and index.html
npm run check     # both
```

Five source files, none with dependencies:

| File | Role |
|---|---|
| `src/i18n.js` | Message catalogue. Every diagnostic has a stable identifier |
| `src/geoconv.js` | Shapefile and DBF binary reading and writing, DXF R12 writer, KML and CSV |
| `src/proj.js` | Transverse Mercator and Web Mercator, forward and inverse |
| `src/zip.js` | ZIP writer (stored) and reader (stored and deflate) |
| `src/app.html` | Interface; the other four are inlined into it at build time |

Diagnostics are stored as identifiers with arguments, not as rendered text, so
the display language can change at any time and a given diagnostic can be
referred to unambiguously in any language. This is also what makes the loss
audit below possible.

`dist/index.html` is a build product but is kept in the repository so it can be
downloaded and run directly. CI verifies on every push that the inlined build
matches the sources.

## Validation

A reader written by the same author as the writer proves nothing by round trip.
The question is whether the files open in **other people's libraries**, and
whether the numbers hold under dense sampling rather than at a few convenient
points.

### Format conformance

```
pip install pyshp ezdxf pyproj
node scripts/make_fixtures.js && python scripts/validate_external.py
```

Runs in CI on every push. Written shapefiles open in **pyshp** with correct
multi-ring geometry, holes as separate parts, correct bounding boxes and UTF-8
attributes. Written DXF opens in **ezdxf** as AC1009 with a valid layer table,
correct closure flags (areas closed, lines open) and transliterated labels.
Written ZIP archives pass the system `unzip`.

### Coordinate accuracy

Compared against PROJ over **19,459 points in 11 zones**: latitude 35.5 to
42.5 degrees in steps of 0.25, and minus 3 to plus 3 degrees from each central
meridian in steps of 0.10. Results are stratified into the zone interior
(within 2 degrees of the central meridian) and the zone edge (2 to 3 degrees),
because a truncated series degrades fastest in the outer degree.

Maximum agreement with PROJ, in metres:

| | interior | edge |
|---|---|---|
| Forward | 3.05e-6 | 4.85e-5 |
| Inverse | 1.88e-5 | 3.22e-4 |
| Round trip | 2.12e-5 | 3.60e-4 |

The grid study found a defect that the earlier tests had missed. The forward
residual sat at a flat 1.9e-4 m across the whole zone, growing only two per
cent from the central meridian to the edge, which pointed away from the
transverse series and toward the meridian arc. The classical Snyder arc
truncated at the sixth power of eccentricity accounts for it exactly. The arc
is now carried to the tenth power and the footpoint latitude is solved by
Newton iteration on the same function, which removed the floor and reduced the
zone-interior residual by more than two orders of magnitude.

The unit test tolerances had been 1 mm forward and 1 cm closure, roughly three
hundred times looser than the measured performance, which is why the defect
survived. They are now 0.01 mm and 0.5 mm, with an explicit zone-edge case.

### Loss disclosure

A taxonomy of 28 loss mechanisms in four families (attribute and schema,
geometry, coordinate reference system, structure and metadata), and a corpus of
21 fixtures, each isolating one source condition, are used to measure what the
conversion log actually reports against what actually happened. Occurrence is
established by reading the converted file with an independent library, not by
trusting the converter; disclosure is coded separately from a frozen rule
table. The same corpus is run through GDAL (ogr2ogr) and mapshaper for
comparison.

Across 100 conversions, 113 losses occurred and 78 were reported. The audit
found three undisclosed losses in this tool and they are fixed: elevation and
measure values discarded while reading shapefiles, feature identifiers dropped
for every target except GeoJSON, and empty geometry reported under the wrong
cause. It also found eight errors in the measurement itself, which are
documented rather than quietly corrected.

Full results per format: **[docs/FORMATS.md](docs/FORMATS.md)**. The corpus,
the taxonomy and the scripts are in **[audit/](audit/)** and can be re-run.

## Limits

These are deliberate, not gaps:

- **No DWG.** Closed format requiring an Open Design Alliance licence. Every
  CAD package, AutoCAD and NetCAD included, opens DXF.
- **No GeoPackage.** Requires SQLite.
- **ED50 transformation is approximate.** A Europe-mean three-parameter shift,
  accurate to a few metres. Not for cadastral, zoning or setting-out work. It
  exists because most CAD data circulating in TÃ¼rkiye is ED50, and silently
  treating it as WGS 84 is a much larger error.
- **No topology repair.** For self-intersecting polygons, use the QGIS geometry
  checker.
- **Not for large datasets.** Everything is held in memory; a warning appears
  above 60,000 features. For millions, use `ogr2ogr`.
- **Zone-edge projection accuracy** is bounded as stated above. Ample for
  planning and design work; not a substitute for a geodetic library where
  sub-millimetre agreement at extreme longitudes matters.

## Citing

Aksoy, T. Pafta: a vector data converter between GIS and CAD.
https://doi.org/10.5281/zenodo.21842591

The DOI above resolves to the most recent release; each release also carries
its own version DOI, which is the one to cite when reproducing a specific
result. An article describing the tool and its validation is in preparation for
*SoftwareX*.

## Contact

Talha Aksoy, Department of Landscape Architecture, KÄ±rklareli University
<talha.aksoy@klu.edu.tr> Â· ORCID [0000-0001-8577-3990](https://orcid.org/0000-0001-8577-3990)

## License

MIT, see [LICENSE](LICENSE).

---

## TÃ¼rkÃ§e

**Pafta**, GIS ile CAD arasÄ±nda vektÃ¶r veri dÃ¶nÃ¼ÅŸtÃ¼rÃ¼cÃ¼sÃ¼dÃ¼r. Shapefile,
GeoJSON, KML, GPX ve CSV okur; DXF, Shapefile, GeoJSON, KML ve CSV yazar;
koordinat sistemini dÃ¶nÃ¼ÅŸtÃ¼rÃ¼r ve her dÃ¶nÃ¼ÅŸÃ¼mde neyi deÄŸiÅŸtirdiÄŸini satÄ±r satÄ±r
sÃ¶yler.

Her ÅŸey tarayÄ±cÄ±da Ã§alÄ±ÅŸÄ±r. Sunucu yok, yÃ¼kleme yok, harici baÄŸÄ±mlÄ±lÄ±k yok; tek
bir HTML dosyasÄ±, Ã§evrimdÄ±ÅŸÄ± da aÃ§Ä±lÄ±r. Veri cihazdan Ã§Ä±kmaz.

AyrÄ±m noktasÄ± dÃ¶nÃ¼ÅŸtÃ¼rme deÄŸil, **dÃ¶nÃ¼ÅŸÃ¼m gÃ¼nlÃ¼ÄŸÃ¼dÃ¼r**. Alan adÄ± 10 karaktere
indi, katman adÄ± ASCII'ye Ã§evrildi, `.cpg` yoktu Latin-1 varsayÄ±ldÄ±, poligon
deliÄŸi ayrÄ± polyline oldu, yÃ¼kseklik deÄŸerleri hedef formatta taÅŸÄ±namÄ±yor:
hepsi, etkilenen Ã¶ge adÄ±yla birlikte bildirilir.

En sert kontrol ÅŸudur: hedef koordinat sistemi derece cinsindeyken DXF istenirse
dÃ¶nÃ¼ÅŸtÃ¼rme hata olarak iÅŸaretlenir. DXF birimsizdir; coÄŸrafi koordinatlarla
Ã¼retilen bir Ã§izim CAD iÃ§inde bir birimin kÃ¼Ã§Ã¼k bir kesri kadar olur ve bÃ¼tÃ¼n
Ã¶lÃ§Ã¼ hesaplarÄ± anlamsÄ±zlaÅŸÄ±r. Uygulama bunu sÃ¶yler ve tek tÄ±kla en yakÄ±n metre
tabanlÄ± dilime geÃ§irir.

**Koordinat sistemleri:** WGS 84, Web Mercator, TUREF 3Â° dilimleri (TM27â€“TM45),
WGS 84 UTM ve ED50 UTM dilimleri. Kaynak sistem `.prj` dosyasÄ±ndan otomatik
okunur.

**YÃ¼kseklik:** Z deÄŸerleri Z tipli shapefile'lardan okunur ve GeoJSON, KML ve
DXF Ã§Ä±ktÄ±larÄ±na taÅŸÄ±nÄ±r. Shapefile ve CSV yalnÄ±zca dÃ¼zlem koordinatÄ± sakladÄ±ÄŸÄ±
iÃ§in kayÄ±p bildirilir.

**ArayÃ¼z:** Ä°ngilizce ve TÃ¼rkÃ§e, baÅŸlÄ±ktan deÄŸiÅŸtirilebilir.

Format bazÄ±nda tam kayÄ±p dÃ¶kÃ¼mÃ¼: **[docs/FORMATS.md](docs/FORMATS.md)**

DoÄŸrulama, sÄ±nÄ±rlar ve geliÅŸtirme notlarÄ± iÃ§in yukarÄ±daki Ä°ngilizce bÃ¶lÃ¼me
bakÄ±nÄ±z. Lisans: MIT.
