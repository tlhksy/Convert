#!/usr/bin/env node
/* build.js — inline src modules into a single self-contained dist/index.html */
const fs = require('fs');
const path = require('path');

const SRC = path.join(__dirname, 'src');
const OUT = path.join(__dirname, 'dist');
const TOKENS = { '/*__GEOCONV__*/': 'geoconv.js', '/*__PROJ__*/': 'proj.js', '/*__ZIP__*/': 'zip.js' };

let html = fs.readFileSync(path.join(SRC, 'app.html'), 'utf8');
for (const [token, file] of Object.entries(TOKENS)) {
  if (!html.includes(token)) throw new Error(`Yer tutucu bulunamadı: ${token}`);
  html = html.replace(token, () => fs.readFileSync(path.join(SRC, file), 'utf8'));
}
fs.mkdirSync(OUT, { recursive: true });
fs.writeFileSync(path.join(OUT, 'index.html'), html);
console.log(`dist/index.html yazıldı — ${(Buffer.byteLength(html) / 1024).toFixed(1)} KB, harici bağımlılık yok.`);
