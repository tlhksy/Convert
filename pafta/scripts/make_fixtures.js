#!/usr/bin/env node
/* Bağımsız kütüphanelerle doğrulanmak üzere örnek çıktı dosyaları üretir. */
const fs = require('fs');
const path = require('path');
const G = require('../src/geoconv.js').GeoConv;

const OUT = path.join(__dirname, '..', 'tmp');
fs.mkdirSync(OUT, { recursive: true });

const fc = {
  type: 'FeatureCollection',
  features: [
    { properties: { ad: 'Meşe Parseli', alan: 1234.56, tip: 'orman' },
      geometry: { type: 'Polygon', coordinates: [
        [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]],
        [[3, 3], [3, 6], [6, 6], [6, 3], [3, 3]]] } },
    { properties: { ad: 'Çayır', alan: 12.5, tip: 'cayir' },
      geometry: { type: 'Polygon', coordinates: [[[20, 0], [25, 0], [25, 5], [20, 0]]] } },
  ],
};

const fields = G.inferFields(fc.features, () => {});
const { shp, shx } = G.writeShpShx(fc.features, 'polygon');
fs.writeFileSync(path.join(OUT, 'fixture.shp'), shp);
fs.writeFileSync(path.join(OUT, 'fixture.shx'), shx);
fs.writeFileSync(path.join(OUT, 'fixture.dbf'), G.writeDbf(fc.features, fields));
fs.writeFileSync(path.join(OUT, 'fixture.prj'), G.WKT[4326]);
fs.writeFileSync(path.join(OUT, 'fixture.cpg'), 'UTF-8');

const line = { properties: { ad: 'Yol', tip: 'ulasim' },
  geometry: { type: 'LineString', coordinates: [[0, 20], [15, 25], [30, 20]] } };
const pt = { properties: { ad: 'Kuyu', tip: 'nokta' },
  geometry: { type: 'Point', coordinates: [5, 5] } };
const dxf = G.writeDxf({ features: fc.features.concat([line, pt]) },
  { layerField: 'tip', labelField: 'ad', textHeight: 1.5 }, () => {});
fs.writeFileSync(path.join(OUT, 'fixture.dxf'), dxf.text);

console.log('tmp/ içine fixture dosyaları yazıldı');
