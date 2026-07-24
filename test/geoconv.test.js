const { test } = require('node:test');
const assert = require('node:assert');
const G = require('../src/geoconv.js').GeoConv;

const noop = () => {};
const collect = () => { const w = []; const fn = (k, m) => w.push(k + ': ' + m); fn.list = w; return fn; };

const POLY_WITH_HOLE = {
  type: 'Feature',
  properties: { ad: 'Meşe Parseli', alan_m2: 1234.56, tip: 'orman', cokUzunOznitelikAdi: 7 },
  geometry: {
    type: 'Polygon',
    coordinates: [
      [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],   // dış halka, GeoJSON kuralınca CCW
      [[3, 3], [3, 6], [6, 6], [6, 3], [3, 3]],       // delik, CW
    ],
  },
};
const TRIANGLE = {
  type: 'Feature',
  properties: { ad: 'İkinci', alan_m2: 9.5, tip: 'çayır', cokUzunOznitelikAdi: 8 },
  geometry: { type: 'Polygon', coordinates: [[[20, 0], [25, 0], [25, 5], [20, 0]]] },
};
const FC = { type: 'FeatureCollection', features: [POLY_WITH_HOLE, TRIANGLE] };

/* ------------------------------- geometri ------------------------------- */
test('işaretli alan CCW için pozitif, CW için negatif', () => {
  const ccw = [[0, 0], [1, 0], [1, 1], [0, 1], [0, 0]];
  assert.ok(G.signedArea(ccw) > 0);
  assert.ok(G.signedArea(ccw.slice().reverse()) < 0);
});

test('shapefile yazımında dış halka CW, delik CCW yönlendirilir', () => {
  const parts = G.partsOf(POLY_WITH_HOLE.geometry);
  assert.strictEqual(parts.length, 2);
  assert.ok(G.signedArea(parts[0]) < 0, 'dış halka CW olmalı');
  assert.ok(G.signedArea(parts[1]) > 0, 'delik CCW olmalı');
});

/* -------------------------------- .shp ---------------------------------- */
test('SHP başlığı geçerli ve dosya uzunluğu tutarlı', () => {
  const { shp, shx } = G.writeShpShx(FC.features, 'polygon');
  const dv = new DataView(shp.buffer, shp.byteOffset, shp.byteLength);
  assert.strictEqual(dv.getInt32(0, false), 9994, 'dosya kodu');
  assert.strictEqual(dv.getInt32(24, false) * 2, shp.length, 'başlıktaki uzunluk');
  assert.strictEqual(dv.getInt32(32, true), 5, 'şekil tipi = Polygon');
  const dx = new DataView(shx.buffer, shx.byteOffset, shx.byteLength);
  assert.strictEqual(dx.getInt32(24, false) * 2, shx.length);
  assert.strictEqual(shx.length, 100 + 8 * FC.features.length);
});

test('SHX ofsetleri gerçek kayıt başlıklarına işaret eder', () => {
  const { shp, shx } = G.writeShpShx(FC.features, 'polygon');
  const ds = new DataView(shp.buffer, shp.byteOffset, shp.byteLength);
  const dx = new DataView(shx.buffer, shx.byteOffset, shx.byteLength);
  for (let i = 0; i < FC.features.length; i++) {
    const offsetWords = dx.getInt32(100 + i * 8, false);
    assert.strictEqual(ds.getInt32(offsetWords * 2, false), i + 1, `kayıt ${i + 1} ofseti`);
  }
});

test('poligon tur atışı deliği ayrı poligona kaçırmadan korur', () => {
  const { shp } = G.writeShpShx(FC.features, 'polygon');
  const back = G.readShp(shp);
  assert.strictEqual(back.length, 2);
  assert.strictEqual(back[0].type, 'Polygon');
  assert.strictEqual(back[0].coordinates.length, 2, 'dış halka + delik');
  assert.ok(G.signedArea(back[0].coordinates[0]) > 0, 'okunan dış halka GeoJSON kuralınca CCW');
  assert.ok(G.signedArea(back[0].coordinates[1]) < 0, 'okunan delik CW');
  assert.ok(Math.abs(Math.abs(G.signedArea(back[0].coordinates[0])) - 100) < 1e-9);
  assert.ok(Math.abs(Math.abs(G.signedArea(back[0].coordinates[1])) - 9) < 1e-9);
});

test('nokta ve çizgi tur atışı', () => {
  const pt = { properties: {}, geometry: { type: 'Point', coordinates: [27.2, 41.5] } };
  const ln = { properties: {}, geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1], [2, 0]] } };
  assert.deepStrictEqual(G.readShp(G.writeShpShx([pt], 'point').shp)[0], pt.geometry);
  const back = G.readShp(G.writeShpShx([ln], 'line').shp)[0];
  assert.strictEqual(back.type, 'LineString');
  assert.strictEqual(back.coordinates.length, 3);
});

test('bozuk .shp anlaşılır hata verir', () => {
  assert.throws(() => G.readShp(new Uint8Array(200)), /Geçerli bir \.shp/);
});

/* -------------------------------- .dbf ---------------------------------- */
test('alan tipleri değerlerden çıkarılır', () => {
  const f = G.inferFields(FC.features, noop);
  assert.strictEqual(f.find(x => x.src === 'alan_m2').type, 'N');
  assert.strictEqual(f.find(x => x.src === 'ad').type, 'C');
});

test('alan adları 10 karaktere indirilir ve uyarı üretilir', () => {
  const w = collect();
  const f = G.inferFields(FC.features, w);
  assert.ok(f.every(x => x.name.length <= 10), 'hepsi <= 10 karakter');
  assert.ok(f.every(x => /^[A-Z0-9_]+$/.test(x.name)), 'hepsi ASCII büyük harf');
  assert.ok(w.list.some(m => m.includes('cokUzunOznitelikAdi')), 'kısaltma bildirilmeli');
});

test('DBF tur atışında Türkçe karakterler ve sayılar korunur', () => {
  const fields = G.inferFields(FC.features, noop);
  const dbf = G.writeDbf(FC.features, fields);
  const read = G.readDbf(dbf, 'utf8');
  assert.strictEqual(read.rows.length, 2);
  assert.strictEqual(read.rows[0].AD, 'Meşe Parseli');
  assert.strictEqual(read.rows[1].TIP, 'çayır');
  assert.ok(Math.abs(read.rows[0].ALAN_M2 - 1234.56) < 1e-6);
});

test('DBF toplam boyutu başlık + kayıtlar + EOF eder', () => {
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

test('DXF grup kodu / değer çiftleri dengelidir', () => {
  const d = G.writeDxf(FC, { layerField: 'tip', labelField: 'ad', textHeight: 1 }, noop);
  const l = pairs(d.text);
  assert.strictEqual(l.length % 2, 0, 'tek sayıda satır = bozuk DXF');
  assert.strictEqual(l[0], '0'); assert.strictEqual(l[1], 'SECTION');
  assert.strictEqual(l[l.length - 1], 'EOF');
});

test('DXF bölümleri ve varlık blokları eşleşir', () => {
  const d = G.writeDxf(FC, { layerField: 'tip', labelField: 'ad', textHeight: 1 }, noop);
  const l = pairs(d.text);
  assert.strictEqual(countEntity(l, 'SECTION'), 3);
  assert.strictEqual(countEntity(l, 'ENDSEC'), 3);
  assert.strictEqual(countEntity(l, 'POLYLINE'), 3, '2 halka + 1 üçgen');
  assert.strictEqual(countEntity(l, 'SEQEND'), 3, 'her POLYLINE bir SEQEND ile kapanmalı');
  assert.strictEqual(countEntity(l, 'TEXT'), 2);
});

test('poligonlar kapalı bayrağıyla yazılır', () => {
  const d = G.writeDxf(FC, {}, noop);
  const l = pairs(d.text);
  // her POLYLINE bloğu içinde, bir sonraki '0' varlığından önceki 70 grup kodunu bul
  const flags = [];
  for (let i = 1; i < l.length; i += 2) {
    if (!(l[i] === 'POLYLINE' && l[i - 1] === '0')) continue;
    for (let j = i + 1; j < l.length; j += 2) {
      if (l[j] === '0') break;                 // blok bitti
      if (l[j] === '70') { flags.push(l[j + 1]); break; }
    }
  }
  assert.strictEqual(flags.length, 3, 'üç POLYLINE de 70 grup kodu taşımalı');
  assert.ok(flags.every(f => f === '1'), `poligon polyline kapalı olmalı, bulunan: ${flags}`);
});

test('çizgiler kapalı bayrağı taşımaz', () => {
  const fc = { features: [{ properties: {}, geometry: { type: 'LineString', coordinates: [[0, 0], [1, 1], [2, 0]] } }] };
  const l = pairs(G.writeDxf(fc, {}, noop).text);
  const i = l.findIndex((v, k) => v === 'POLYLINE' && l[k - 1] === '0');
  let flag = null;
  for (let j = i + 1; j < l.length; j += 2) { if (l[j] === '0') break; if (l[j] === '70') { flag = l[j + 1]; break; } }
  assert.strictEqual(flag, '0', 'açık polyline 70=0 olmalı');
});

test('katman adları ASCII\'ye çevrilir ve uyarı verilir', () => {
  const w = collect();
  const d = G.writeDxf(FC, { layerField: 'tip' }, w);
  assert.deepStrictEqual(d.layers, ['0', 'ORMAN', 'CAYIR']);
  assert.ok(w.list.some(m => m.includes('CAYIR')));
});

test('etiket metninde Türkçe karakter çevrimi bildirilir', () => {
  const w = collect();
  G.writeDxf(FC, { labelField: 'ad', asciiText: true }, w);
  assert.ok(w.list.some(m => m.startsWith('text:')));
});

/* ---------------------------- KML / CSV --------------------------------- */
test('KML deliği innerBoundaryIs olarak yazar', () => {
  const kml = G.writeKml(FC, { labelField: 'ad' });
  assert.ok(kml.includes('<innerBoundaryIs>'));
  assert.strictEqual((kml.match(/<Placemark>/g) || []).length, 2);
  assert.ok(kml.includes('<name>Meşe Parseli</name>'));
});

test('KML XML kaçışı uygular', () => {
  const fc = { features: [{ properties: { ad: 'A & B <test>' }, geometry: { type: 'Point', coordinates: [1, 2] } }] };
  const kml = G.writeKml(fc, { labelField: 'ad' });
  assert.ok(kml.includes('A &amp; B &lt;test&gt;'));
  assert.ok(!kml.includes('<test>'));
});

test('CSV başlıklardan koordinat sütunlarını bulur', () => {
  const fc = G.csvToFc('ad,enlem,boylam,deger\nA,41.5,27.2,3\nB,41.6,27.3,4\n');
  assert.strictEqual(fc.features.length, 2);
  assert.deepStrictEqual(fc.features[0].geometry.coordinates, [27.2, 41.5]);
  assert.strictEqual(fc.features[0].properties.deger, 3);
});

test('koordinat sütunu yoksa CSV anlaşılır hata verir', () => {
  assert.throws(() => G.csvToFc('a,b\n1,2\n'), /koordinat sütunu bulunamadı/);
});

test('CSV tırnaklı ve ayraç içeren alanları çözer', () => {
  const rows = G.parseCsv('a,"b,c",d\n1,"iki ""tırnak""",3\n');
  assert.deepStrictEqual(rows[0], ['a', 'b,c', 'd']);
  assert.deepStrictEqual(rows[1], ['1', 'iki "tırnak"', '3']);
});

test('geometri sınıfları doğru ayrışır', () => {
  assert.strictEqual(G.shapeClass({ type: 'MultiPoint' }), 'point');
  assert.strictEqual(G.shapeClass({ type: 'MultiLineString' }), 'line');
  assert.strictEqual(G.shapeClass({ type: 'MultiPolygon' }), 'polygon');
  assert.strictEqual(G.shapeClass({ type: 'GeometryCollection' }), null);
});
