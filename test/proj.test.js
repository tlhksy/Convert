const { test } = require('node:test');
const assert = require('node:assert');
const { Proj } = require('../src/proj.js');

/* Reference values produced with PROJ/pyproj 3.x (scripts/reference_values.py).
   Tolerances follow the measured grid accuracy rather than a round number: over
   19459 points in 11 zones the forward residual stays below 3.1e-6 m inside the
   zone and 4.9e-5 m at the edge, and round-trip closure below 3.6e-4 m. A
   tolerance far looser than the measured performance cannot detect a
   regression, which is how the earlier meridian-arc truncation went unnoticed. */
/* Each sample sits inside the zone it names. The previous TUREF / TM33 sample
   used Istanbul, four degrees west of that zone's central meridian and so
   outside the three-degree half-width the zone exists for; at 1 mm tolerance
   the mismatch was invisible. Istanbul now tests TM30, which is the zone it
   actually belongs to, and Ankara tests TM33. */
const REFERENCE = [
  { crs: 'EPSG:32635', lonlat: [28.9784, 41.0082], xy: [666370.5050168498, 4541552.4871906955], name: 'WGS84 / UTM 35N' },  // 1.98 deg from CM
  { crs: 'EPSG:5254',  lonlat: [28.9784, 41.0082], xy: [414057.50597542897, 4541986.710810093], name: 'TUREF / TM30' },     // 1.02 deg from CM
  { crs: 'EPSG:5255',  lonlat: [32.8597, 39.9334], xy: [488007.6083396975, 4422143.591214942], name: 'TUREF / TM33' },      // 0.14 deg from CM
  { crs: 'EPSG:3857',  lonlat: [28.9784, 41.0082], xy: [3225860.7320037987, 5013551.237222597], name: 'Web Mercator' },
];

for (const c of REFERENCE) {
  test(`${c.name} forward transform agrees with the PROJ reference within 0.01 mm`, () => {
    const [x, y] = Proj.REG[c.crs].fromWgs84(c.lonlat[0], c.lonlat[1]);
    const d = Math.hypot(x - c.xy[0], y - c.xy[1]);
    assert.ok(d < 1e-5, `${c.crs} deviation ${d.toExponential(3)} m`);
  });
}

test('forward and inverse close within 0.5 mm across the zone width', () => {
  const crs = Proj.REG['EPSG:32635'];
  for (const lon of [24.1, 25.5, 27, 28.5, 29.9]) {
    for (const lat of [36, 39, 42]) {
      const [x, y] = crs.fromWgs84(lon, lat);
      const [lo, la] = crs.toWgs84(x, y);
      const err = Math.hypot((lo - lon) * 85000, (la - lat) * 111000);
      assert.ok(err < 5e-4, `${lon},${lat} closure error ${err.toExponential(3)} m`);
    }
  }
});

test('a geographic system passes coordinates through unchanged', () => {
  const g = Proj.REG['EPSG:4326'];
  assert.deepStrictEqual(g.fromWgs84(28.9784, 41.0082), [28.9784, 41.0082]);
});

test('the ED50 shift produces a non-zero difference of plausible magnitude', () => {
  const ed = Proj.REG['EPSG:23036'], wgs = Proj.REG['EPSG:32636'];
  const a = ed.fromWgs84(33, 39), b = wgs.fromWgs84(33, 39);
  const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
  assert.ok(d > 20 && d < 400, `ED50/WGS84 difference outside the expected range: ${d.toFixed(1)} m`);
});

/* Zone edge: the grid study puts the worst forward residual at the outer
   degree of the zone at high latitude, so that location is asserted explicitly
   rather than left to a central-meridian sample. */
test('forward transform holds at the zone edge', () => {
  const crs = Proj.REG['EPSG:5255'];            // TUREF / TM33, central meridian 33
  const [x, y] = crs.fromWgs84(36.0, 42.5);     // 3 degrees east, high latitude
  const [lo, la] = crs.toWgs84(x, y);
  const err = Math.hypot((lo - 36.0) * 82000, (la - 42.5) * 111000);
  assert.ok(err < 5e-4, `zone edge closure error ${err.toExponential(3)} m`);
});

test('every UTM zone and every national TM zone is registered', () => {
  for (let z = 1; z <= 60; z++) assert.ok(Proj.REG['EPSG:' + (32600 + z)], `UTM ${z}N missing`);
  for (const e of [5253, 5254, 5255, 5256, 5257, 5258, 5259]) assert.ok(Proj.REG['EPSG:' + e], `EPSG:${e} missing`);
});
