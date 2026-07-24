const { test } = require('node:test');
const assert = require('node:assert');
const { Proj } = require('../src/proj.js');

/* Referans değerler PROJ/pyproj 3.x ile üretildi (scripts/reference_values.py).
   Kabul eşiği 1 mm — Snyder serilerinin dilim içi doğruluk sınırı. */
const REFERENCE = [
  { crs: 'EPSG:32635', lonlat: [28.9784, 41.0082], xy: [666370.5050168498, 4541552.4871906955], name: 'WGS84 / UTM 35N' },
  { crs: 'EPSG:5255',  lonlat: [28.9784, 41.0082], xy: [161644.86839905696, 4549282.552879264], name: 'TUREF / TM33' },
  { crs: 'EPSG:3857',  lonlat: [28.9784, 41.0082], xy: [3225860.7320037987, 5013551.237222597], name: 'Web Mercator' },
];

for (const c of REFERENCE) {
  test(`${c.name} ileri dönüşüm PROJ referansıyla 1 mm içinde uyuşur`, () => {
    const [x, y] = Proj.REG[c.crs].fromWgs84(c.lonlat[0], c.lonlat[1]);
    const d = Math.hypot(x - c.xy[0], y - c.xy[1]);
    assert.ok(d < 0.001, `${c.crs} sapması ${d.toFixed(6)} m`);
  });
}

test('ileri/geri dönüşüm dilim genişliği boyunca 1 cm içinde kapanır', () => {
  const crs = Proj.REG['EPSG:32635'];
  for (const lon of [24.1, 25.5, 27, 28.5, 29.9]) {
    for (const lat of [36, 39, 42]) {
      const [x, y] = crs.fromWgs84(lon, lat);
      const [lo, la] = crs.toWgs84(x, y);
      const err = Math.hypot((lo - lon) * 85000, (la - lat) * 111000);
      assert.ok(err < 0.01, `${lon},${lat} kapanma hatası ${err.toFixed(4)} m`);
    }
  }
});

test('coğrafi sistem koordinatları değiştirmeden geçirir', () => {
  const g = Proj.REG['EPSG:4326'];
  assert.deepStrictEqual(g.fromWgs84(28.9784, 41.0082), [28.9784, 41.0082]);
});

test('ED50 kayması sıfır olmayan ve makul büyüklükte bir fark üretir', () => {
  const ed = Proj.REG['EPSG:23036'], wgs = Proj.REG['EPSG:32636'];
  const a = ed.fromWgs84(33, 39), b = wgs.fromWgs84(33, 39);
  const d = Math.hypot(a[0] - b[0], a[1] - b[1]);
  assert.ok(d > 20 && d < 400, `ED50/WGS84 farkı beklenen aralıkta değil: ${d.toFixed(1)} m`);
});

test('bütün UTM dilimleri ve Türkiye TM dilimleri kayıtlı', () => {
  for (let z = 1; z <= 60; z++) assert.ok(Proj.REG['EPSG:' + (32600 + z)], `UTM ${z}N eksik`);
  for (const e of [5253, 5254, 5255, 5256, 5257, 5258, 5259]) assert.ok(Proj.REG['EPSG:' + e], `EPSG:${e} eksik`);
});
