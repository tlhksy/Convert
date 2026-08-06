const { test } = require('node:test');
const assert = require('node:assert');
const G = require('../src/geoconv.js').GeoConv;

const noop = () => {};
/* The diagnostic callback receives (tag, messageKey, args). Assertions target
   the message identifier rather than rendered text, so they hold regardless of
   display language. */
const collect = () => {
  const w = [];
  const fn = (tag, key, args) => w.push({ tag, key, args: args || [] });
  fn.list = w;
  fn.has = (key) => w.some(e => e.key === key);
  fn.argsFor = (key) => (w.find(e => e.key === key) || {}).args || [];
  return fn;
};

const POLY_WITH_HOLE = {
  type: 'Feature',
  properties: { ad: 'Meşe Parseli', alan_m2: 1234.56, tip: 'orman', cokUzunOznitelikAdi: 7 },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],   // exterior ring, CCW per GeoJSON
      [[3, 3], [3, 6], [6, 6], [6, 3], [3, 3]],       // hole, CW
    ],
  },
};
const TRIANGLE = {
  type: 'Feature',
  properties: { ad: 'İkinci', alan_m2: 9.5, tip: 'çayır', cokUzunOznitelikAdi: 8 },
  geometry: { type: 'Polygon', coordinates: [[[20, 0], [25, 0], [25, 5], [20, 0]]] },
};
const FC = { type: 'FeatureCollection', features: [POLY_WITH_HOLE, TRIANGLE] };

/* ------------------------------- geometry ------------------------------- */
test('signed area is positive for CCW and negative for CW', () => {
  const ccw = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]];
  assert.ok(G.signedArea(ccw) > 0);
  assert.ok(G.signedArea(ccw.slice().reverse()) < 0);
});

test('shapefile writing orients the exterior ring CW and holes CCW', () => {
  const parts = G.partsOf(POLY_WITH_HOLE.geometry);
  assert.strictEqual(parts.length, 2);
  assert.ok(G.signedArea(parts[0]) < 0, 'exterior ring must be CW');
  assert.ok(G.signedArea(parts[1]) > 0, 'hole must be CCW');
});

/* -------------------------------- .shp ---------------------------------- */
test('SHP header is valid and the file length is consistent', () => {
  const { shp, shx } = G.writeShpShx(FC.features, 'polygon');
  const dv = new DataView(shp.buffer, shp.byteOffset, shp.byteLength);
  assert.strictEqual(dv.getInt32(0, false), 9994, 'file code');
  assert.strictEqual(dv.getInt32(24, false) * 2, shp.length, 'length stated in the header');
  assert.strictEqual(dv.getInt32(32, true), 5, 'shape type is Polygon');
  const dx = new DataView(shx.buffer, shx.byteOffset, shx.byteLength);
  assert.strictEqual(dx.getInt32(24, false) * 2, shx.length);
  assert.strictEqual(shx.length, 100 + 8 * FC.features.length);
});

test('SHX offsets point at real record headers', () => {
  const { shp, shx } = G.writeShpShx(FC.features, 'polygon');
  const ds = new DataView(shp.buffer, shp.byteOffset, shp.byteLength);
  const dx = new DataView(shx.buffer, shx.byteOffset, shx.byteLength);
  for (let i = 0; i < FC.features.length; i++) {
    const offsetWords = dx.getInt32(100 + i * 8, false);
    assert.strictEqual(ds.getInt32(offsetWords * 2, false), i + 1, `offset of record ${i + 1}`);
  }
});

test('polygon round trip preserves the hole without splitting it off', () => {
  const { shp } = G.writeShpShx(FC.features, 'polygon');
  const back = G.readShp(shp);
  assert.strictEqual(back.length, 2);
  assert.strictEqual(back[0].type, 'Polygon');
  assert.strictEqual(back[0].coordinates.length, 2, 'exterior ring plus hole');
  assert.ok(G.signedArea(back[0].coordinates[0]) > 0, 'exterior ring read back is CCW per GeoJSON');
  assert.ok(G.signedArea(back[0].coordinates[1]) < 0, 'hole read back is CW');
  assert.ok(Math.abs(Math.abs(G.signedArea(back[0].coordinates[0])) - 100) < 1e-9);
  assert.ok(Math.abs(Math.abs(G.signedArea(back[0].coordinates[1])) - 9) < 1e-9);
});

test('point and line round trip', () => {
  const pt = { properties: {}, geometry: { type: 'Point', coordinates: [27.2, 41.5] } };
  const ln = { properties: {}, geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1], [2, 0]] } };
  assert.deepStrictEqual(G.readShp(G.writeShpShx([pt], 'point').shp)[0], pt.geometry);
  const back = G.readShp(G.writeShpShx([ln], 'line').shp)[0];
  assert.strictEqual(back.type, 'LineString');
  assert.strictEqual(back.coordinates.length, 3);
});

test('a corrupt .shp raises an identifiable error', () => {
  assert.throws(() => G.readShp(new Uint8Array(200)), /err\.shp\.magic/);
});

/* -------------------------------- .dbf ---------------------------------- */
test('field types are inferred from the values', () => {
  const f = G.inferFields(FC.features, noop);
  assert.strictEqual(f.find(x => x.src === 'alan_m2').type, 'N');
  assert.strictEqual(f.find(x => x.src === 'ad').type, 'C');
});

test('field names are reduced to 10 characters and the change is reported', () => {
  const w = collect();
  const f = G.inferFields(FC.features, w);
  assert.ok(f.every(x => x.name.length <= 10), 'all at most 10 characters');
  assert.ok(f.every(x => /^[A-Z0-9_]+$/.test(x.name)), 'all ASCII upper case');
  assert.ok(w.has('log.dbf.fieldRenamed'), 'truncation must be reported');
  assert.strictEqual(w.argsFor('log.dbf.fieldRenamed')[0], 'cokUzunOznitelikAdi');
});

test('DBF round trip preserves non-ASCII characters and numbers', () => {
  const fields = G.inferFields(FC.features, noop);
  const dbf = G.writeDbf(FC.features, fields);
  const read = G.readDbf(dbf, 'utf8');
  assert.strictEqual(read.rows.length, 2);
  assert.strictEqual(read.rows[0].AD, 'Meşe Parseli');
  assert.strictEqual(read.rows[1].TIP, 'çayır');
  assert.ok(Math.abs(read.rows[0].ALAN_M2 - 1234.56) < 1e-6);
});

test('DBF total size equals header plus records plus EOF', () => {
  const fields = G.inferFields(FC.features, noop);
  const dbf = G.writeDbf(FC.features, fields);
  const dv = new DataView(dbf.buffer, dbf.byteOffset, dbf.byteLength);
  const headLen = dv.getUint16(8, true), recLen = dv.getUint16(10, true);
  assert.strictEqual(dbf.length, headLen + recLen * FC.features.length + 1);
});

/* -------------------------------- DXF ----------------------------------- */
function pairs(text) {
  const lines = text.split('\r\n');
  if (lines[lines.length - 1] === '') lines.pop();
  return lines;
}
function countEntity(lines, name) {
  let n = 0;
  for (let i = 1; i < lines.length; i += 2) if (lines[i] === name && lines[i - 1] === '0') n++;
  return n;
}

test('DXF group code and value lines are balanced', () => {
  const d = G.writeDxf(FC, { layerField: 'tip', labelField: 'ad', textHeight: 1 }, noop);
  const l = pairs(d.text);
  assert.strictEqual(l.length % 2, 0, 'an odd line count means a malformed DXF');
  assert.strictEqual(l[0], '0'); assert.strictEqual(l[1], 'SECTION');
  assert.strictEqual(l[l.length - 1], 'EOF');
});

test('DXF sections and entity blocks match', () => {
  const d = G.writeDxf(FC, { layerField: 'tip', labelField: 'ad', textHeight: 1 }, noop);
  const l = pairs(d.text);
  assert.strictEqual(countEntity(l, 'SECTION'), 3);
  assert.strictEqual(countEntity(l, 'ENDSEC'), 3);
  assert.strictEqual(countEntity(l, 'POLYLINE'), 3, '2 rings plus 1 triangle');
  assert.strictEqual(countEntity(l, 'SEQEND'), 3, 'every POLYLINE must close with a SEQEND');
  assert.strictEqual(countEntity(l, 'TEXT'), 2);
});

test('polygons are written with the closed flag', () => {
  const d = G.writeDxf(FC, {}, noop);
  const l = pairs(d.text);
  // within each POLYLINE block, find group code 70 before the next '0' entity
  const flags = [];
  for (let i = 1; i < l.length; i += 2) {
    if (!(l[i] === 'POLYLINE' && l[i - 1] === '0')) continue;
    for (let j = i + 1; j < l.length; j += 2) {
      if (l[j] === '0') break;                 // blok bitti
      if (l[j] === '70') { flags.push(l[j + 1]); break; }
    }
  }
  assert.strictEqual(flags.length, 3, 'all three POLYLINEs must carry group code 70');
  assert.ok(flags.every(f => f === '1'), `polygon polylines must be closed, found: ${flags}`);
});

test('lines do not carry the closed flag', () => {
  const fc = { features: [{ properties: {}, geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1], [2, 0]] } }] };
  const l = pairs(G.writeDxf(fc, {}, noop).text);
  const i = l.findIndex((v, k) => v === 'POLYLINE' && l[k - 1] === '0');
  let flag = null;
  for (let j = i + 1; j < l.length; j += 2) { if (l[j] === '0') break; if (l[j] === '70') { flag = l[j + 1]; break; } }
  assert.strictEqual(flag, '0', 'an open polyline must have 70=0');
});

test('layer names are transliterated to ASCII and the change is reported', () => {
  const w = collect();
  const d = G.writeDxf(FC, { layerField: 'tip' }, w);
  assert.deepStrictEqual(d.layers, ['0', 'ORMAN', 'CAYIR']);
  assert.ok(w.has('log.dxf.layerRenamed'), 'layer rename must be reported');
  assert.ok(w.list.some(e => e.key === 'log.dxf.layerRenamed' && e.args[1] === 'CAYIR'));
});

test('transliteration of label text is reported', () => {
  const w = collect();
  G.writeDxf(FC, { labelField: 'ad', asciiText: true }, w);
  assert.ok(w.has('log.dxf.textAscii'), 'transliteration must be reported');
});

/* ---------------------------- KML / CSV --------------------------------- */
test('KML writes holes as innerBoundaryIs', () => {
  const kml = G.writeKml(FC, { labelField: 'ad' });
  assert.ok(kml.includes('<innerBoundaryIs>'));
  assert.strictEqual((kml.match(/<Placemark>/g) || []).length, 2);
  assert.ok(kml.includes('<name>Meşe Parseli</name>'));
});

test('KML applies XML escaping', () => {
  const fc = { features: [{ properties: { ad: 'A & B <test>' }, geometry: { type: 'Point', coordinates: [1, 2] } }] };
  const kml = G.writeKml(fc, { labelField: 'ad' });
  assert.ok(kml.includes('A &amp; B &lt;test&gt;'));
  assert.ok(!kml.includes('<test>'));
});

test('CSV finds coordinate columns from the header names', () => {
  const fc = G.csvToFc('ad,enlem,boylam,deger\nA,41.5,27.2,3\nB,41.6,27.3,4\n');
  assert.strictEqual(fc.features.length, 2);
  assert.deepStrictEqual(fc.features[0].geometry.coordinates, [27.2, 41.5]);
  assert.strictEqual(fc.features[0].properties.deger, 3);
});

test('CSV raises an identifiable error when no coordinate column exists', () => {
  assert.throws(() => G.csvToFc('a,b\n1,2\n'), /err\.csv\.noCoords/);
});

test('CSV parses quoted fields containing the delimiter', () => {
  const rows = G.parseCsv('a,"b,c",d\n1,"iki ""tırnak""",3\n');
  assert.deepStrictEqual(rows[0], ['a', 'b,c', 'd']);
  assert.deepStrictEqual(rows[1], ['1', 'iki "tırnak"', '3']);
});

test('geometry classes are resolved correctly', () => {
  assert.strictEqual(G.shapeClass({ type: 'MultiPoint' }), 'point');
  assert.strictEqual(G.shapeClass({ type: 'MultiLineString' }), 'line');
  assert.strictEqual(G.shapeClass({ type: 'MultiPolygon' }), 'polygon');
  assert.strictEqual(G.shapeClass({ type: 'GeometryCollection' }), null);
});
