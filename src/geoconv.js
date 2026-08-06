/* geoconv.js — format core. No DOM dependencies except where noted. */
(function (root) {
'use strict';

/* Translation helper. The catalogue is loaded before this file, but the lookup
   is done lazily so that geoconv remains usable without it: a missing
   catalogue yields the identifier itself rather than an exception. */
function T(){ var f=(typeof window!=='undefined'&&window.t); return f?f.apply(null,arguments):arguments[0]; }


/* ============================ geometry utils ============================ */
function signedArea(ring) { // >0 = CCW
  let a = 0;
  for (let i = 0, n = ring.length - 1; i < n; i++) {
    a += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1];
  }
  return a / 2;
}
function closeRing(r) {
  if (r.length < 3) return r.slice();
  const f = r[0], l = r[r.length - 1];
  if (f[0] !== l[0] || f[1] !== l[1]) return r.concat([[f[0], f[1]]]);
  return r.slice();
}
function orient(ring, wantCCW) {
  const r = closeRing(ring);
  const ccw = signedArea(r) > 0;
  return ccw === wantCCW ? r : r.slice().reverse();
}
function bboxOf(coordsList) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const c of coordsList) {
    if (c[0] < x0) x0 = c[0]; if (c[1] < y0) y0 = c[1];
    if (c[0] > x1) x1 = c[0]; if (c[1] > y1) y1 = c[1];
  }
  return [x0, y0, x1, y1];
}
function eachCoord(geom, fn) {
  if (!geom) return;
  const t = geom.type;
  if (t === 'GeometryCollection') { (geom.geometries || []).forEach(g => eachCoord(g, fn)); return; }
  const walk = (a, d) => {
    if (d === 0) { fn(a); return; }
    for (const s of a) walk(s, d - 1);
  };
  const depth = { Point: 0, MultiPoint: 1, LineString: 1, MultiLineString: 2, Polygon: 2, MultiPolygon: 3 }[t];
  if (depth === undefined) return;
  walk(geom.coordinates, depth);
}
function fcBbox(fc) {
  let x0 = Infinity, y0 = Infinity, x1 = -Infinity, y1 = -Infinity;
  for (const f of fc.features) eachCoord(f.geometry, c => {
    if (c[0] < x0) x0 = c[0]; if (c[1] < y0) y0 = c[1];
    if (c[0] > x1) x1 = c[0]; if (c[1] > y1) y1 = c[1];
  });
  if (!isFinite(x0)) return null;
  return [x0, y0, x1, y1];
}
function shapeClass(g) {
  if (!g) return null;
  if (g.type === 'Point' || g.type === 'MultiPoint') return 'point';
  if (g.type === 'LineString' || g.type === 'MultiLineString') return 'line';
  if (g.type === 'Polygon' || g.type === 'MultiPolygon') return 'polygon';
  return null;
}
/* Explode a geometry into parts (arrays of [x,y]) for line/polygon writing */
function partsOf(g) {
  const t = g.type;
  if (t === 'LineString') return [g.coordinates];
  if (t === 'MultiLineString') return g.coordinates.slice();
  if (t === 'Polygon') return polyParts(g.coordinates);
  if (t === 'MultiPolygon') { let out = []; for (const p of g.coordinates) out = out.concat(polyParts(p)); return out; }
  return [];
}
function polyParts(rings) {
  const out = [];
  rings.forEach((r, i) => out.push(orient(r, i !== 0 ? true : false))); // shapefile: outer CW, holes CCW
  return out;
}
function pointsOf(g) {
  if (g.type === 'Point') return [g.coordinates];
  if (g.type === 'MultiPoint') return g.coordinates.slice();
  return [];
}

/* ============================ binary helpers ============================ */
function Writer(initial) {
  this.buf = new ArrayBuffer(initial || 1024);
  this.dv = new DataView(this.buf);
  this.u8 = new Uint8Array(this.buf);
  this.pos = 0;
}
Writer.prototype._need = function (n) {
  if (this.pos + n <= this.buf.byteLength) return;
  let cap = this.buf.byteLength;
  while (cap < this.pos + n) cap *= 2;
  const nb = new ArrayBuffer(cap), nu = new Uint8Array(nb);
  nu.set(this.u8.subarray(0, this.pos));
  this.buf = nb; this.dv = new DataView(nb); this.u8 = nu;
};
Writer.prototype.i32 = function (v, le) { this._need(4); this.dv.setInt32(this.pos, v, !!le); this.pos += 4; };
Writer.prototype.f64 = function (v, le) { this._need(8); this.dv.setFloat64(this.pos, v, le === undefined ? true : !!le); this.pos += 8; };
Writer.prototype.u8w = function (v) { this._need(1); this.u8[this.pos++] = v & 0xff; };
Writer.prototype.bytes = function (arr) { this._need(arr.length); this.u8.set(arr, this.pos); this.pos += arr.length; };
Writer.prototype.done = function () { return this.u8.slice(0, this.pos); };

function utf8(s) {
  const out = [];
  for (let i = 0; i < s.length; i++) {
    let c = s.codePointAt(i);
    if (c > 0xffff) i++;
    if (c < 0x80) out.push(c);
    else if (c < 0x800) out.push(0xc0 | (c >> 6), 0x80 | (c & 63));
    else if (c < 0x10000) out.push(0xe0 | (c >> 12), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
    else out.push(0xf0 | (c >> 18), 0x80 | ((c >> 12) & 63), 0x80 | ((c >> 6) & 63), 0x80 | (c & 63));
  }
  return out;
}
function fromUtf8(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length;) {
    const b = bytes[i];
    if (b < 0x80) { s += String.fromCharCode(b); i++; }
    else if (b >= 0xc0 && b < 0xe0 && i + 1 < bytes.length) { s += String.fromCharCode(((b & 31) << 6) | (bytes[i + 1] & 63)); i += 2; }
    else if (b >= 0xe0 && b < 0xf0 && i + 2 < bytes.length) { s += String.fromCharCode(((b & 15) << 12) | ((bytes[i + 1] & 63) << 6) | (bytes[i + 2] & 63)); i += 3; }
    else if (b >= 0xf0 && i + 3 < bytes.length) {
      const cp = ((b & 7) << 18) | ((bytes[i + 1] & 63) << 12) | ((bytes[i + 2] & 63) << 6) | (bytes[i + 3] & 63);
      s += String.fromCodePoint(cp); i += 4;
    } else { s += String.fromCharCode(b); i++; }
  }
  return s;
}
function latin1(bytes) { let s = ''; for (const b of bytes) s += String.fromCharCode(b); return s; }

/* ============================ DBF ============================ */
const SHP_TYPE = { point: 1, line: 3, polygon: 5 };

function inferFields(features, warn) {
  const keys = [];
  const seen = new Set();
  for (const f of features) for (const k of Object.keys(f.properties || {})) if (!seen.has(k)) { seen.add(k); keys.push(k); }
  const used = new Set();
  const fields = [];
  for (const k of keys) {
    let numeric = true, maxLen = 1, maxDec = 0, any = false;
    for (const f of features) {
      const v = (f.properties || {})[k];
      if (v === null || v === undefined || v === '') continue;
      any = true;
      if (typeof v === 'number' && isFinite(v)) {
        const s = String(v);
        maxLen = Math.max(maxLen, s.length);
        const dot = s.indexOf('.');
        if (dot >= 0) maxDec = Math.max(maxDec, Math.min(10, s.length - dot - 1));
      } else if (typeof v === 'boolean') {
        numeric = false; maxLen = Math.max(maxLen, 1);
      } else {
        numeric = false;
        const s = typeof v === 'object' ? JSON.stringify(v) : String(v);
        maxLen = Math.max(maxLen, utf8(s).length);
      }
    }
    if (!any) numeric = false;
    let name = toAscii(k).replace(/[^A-Za-z0-9_]/g, '_').replace(/^_+/, '');
    if (!name) name = 'FLD';
    name = name.substring(0, 10).toUpperCase();
    let base = name, n = 1;
    while (used.has(name)) { const suf = String(n++); name = base.substring(0, 10 - suf.length) + suf; }
    used.add(name);
    if (name !== k.toUpperCase()) warn('field', 'log.dbf.fieldRenamed', [k, name]);
    const len = numeric ? Math.min(18, Math.max(1, maxLen)) : Math.min(254, Math.max(1, maxLen));
    if (!numeric && maxLen > 254) warn('field', 'log.dbf.valueTruncated', [k]);
    fields.push({ src: k, name: name, type: numeric ? 'N' : 'C', len: len, dec: numeric ? Math.min(maxDec, Math.max(0, len - 2)) : 0 });
  }
  if (!fields.length) fields.push({ src: null, name: 'ID', type: 'N', len: 10, dec: 0 });
  return fields;
}

function writeDbf(features, fields) {
  const recLen = 1 + fields.reduce((a, f) => a + f.len, 0);
  const headLen = 32 + 32 * fields.length + 1;
  const w = new Writer(headLen + recLen * features.length + 1);
  const d = new Date();
  w.u8w(0x03); w.u8w(d.getFullYear() - 1900); w.u8w(d.getMonth() + 1); w.u8w(d.getDate());
  w.i32(features.length, true);
  w.dv.setUint16(w.pos, headLen, true); w.pos += 2;
  w.dv.setUint16(w.pos, recLen, true); w.pos += 2;
  for (let i = 0; i < 20; i++) w.u8w(0);
  for (const f of fields) {
    const nb = utf8(f.name).slice(0, 11);
    for (let i = 0; i < 11; i++) w.u8w(i < nb.length ? nb[i] : 0);
    w.u8w(f.type.charCodeAt(0));
    for (let i = 0; i < 4; i++) w.u8w(0);
    w.u8w(f.len); w.u8w(f.dec);
    for (let i = 0; i < 14; i++) w.u8w(0);
  }
  w.u8w(0x0d);
  for (const feat of features) {
    w.u8w(0x20);
    for (const f of fields) {
      let v = f.src === null ? '' : (feat.properties || {})[f.src];
      let s;
      if (v === null || v === undefined) s = '';
      else if (f.type === 'N') { s = (typeof v === 'number' && isFinite(v)) ? (f.dec > 0 ? v.toFixed(f.dec) : String(Math.round(v))) : ''; }
      else s = typeof v === 'object' ? JSON.stringify(v) : String(v);
      let b = utf8(s);
      if (b.length > f.len) b = b.slice(0, f.len);
      if (f.type === 'N') { const pad = f.len - b.length; for (let i = 0; i < pad; i++) w.u8w(0x20); w.bytes(b); }
      else { w.bytes(b); const pad = f.len - b.length; for (let i = 0; i < pad; i++) w.u8w(0x20); }
    }
  }
  w.u8w(0x1a);
  return w.done();
}

function readDbf(buf, encoding) {
  const dv = new DataView(buf.buffer || buf, buf.byteOffset || 0, buf.byteLength);
  const u8 = new Uint8Array(buf.buffer || buf, buf.byteOffset || 0, buf.byteLength);
  const nRec = dv.getUint32(4, true), headLen = dv.getUint16(8, true), recLen = dv.getUint16(10, true);
  const fields = [];
  for (let p = 32; p + 32 <= headLen - 1; p += 32) {
    if (u8[p] === 0x0d) break;
    let name = '';
    for (let i = 0; i < 11 && u8[p + i]; i++) name += String.fromCharCode(u8[p + i]);
    fields.push({ name: name, type: String.fromCharCode(u8[p + 11]), len: u8[p + 16], dec: u8[p + 17] });
  }
  const dec = encoding === 'utf8' ? fromUtf8 : latin1;
  const rows = [];
  for (let r = 0; r < nRec; r++) {
    let p = headLen + r * recLen;
    if (p + recLen > u8.length) break;
    const del = u8[p]; p += 1;
    const o = {};
    for (const f of fields) {
      const raw = dec(u8.subarray(p, p + f.len)).replace(/\u0000/g, '').trim();
      p += f.len;
      if (f.type === 'N' || f.type === 'F') o[f.name] = raw === '' ? null : (isNaN(Number(raw)) ? raw : Number(raw));
      else if (f.type === 'L') o[f.name] = /^[YyTt]$/.test(raw) ? true : (/^[NnFf]$/.test(raw) ? false : null);
      else o[f.name] = raw;
    }
    if (del !== 0x2a) rows.push(o);
  }
  return { fields: fields, rows: rows };
}

/* ============================ SHP write ============================ */
function writeShpShx(features, cls) {
  const type = SHP_TYPE[cls];
  const recs = [];
  for (const f of features) {
    const g = f.geometry;
    const w = new Writer(256);
    if (cls === 'point') {
      const p = pointsOf(g)[0] || [0, 0];
      w.i32(1, true); w.f64(p[0]); w.f64(p[1]);
    } else {
      const parts = partsOf(g).filter(p => p.length >= 2);
      const all = [].concat.apply([], parts);
      if (!all.length) { w.i32(0, true); recs.push(w.done()); continue; }
      const bb = bboxOf(all);
      w.i32(type, true);
      w.f64(bb[0]); w.f64(bb[1]); w.f64(bb[2]); w.f64(bb[3]);
      w.i32(parts.length, true); w.i32(all.length, true);
      let acc = 0;
      for (const p of parts) { w.i32(acc, true); acc += p.length; }
      for (const c of all) { w.f64(c[0]); w.f64(c[1]); }
    }
    recs.push(w.done());
  }
  let totalContent = 0;
  for (const r of recs) totalContent += r.length + 8;
  const allC = [];
  for (const f of features) eachCoord(f.geometry, c => allC.push(c));
  const bb = allC.length ? bboxOf(allC) : [0, 0, 0, 0];

  function header(w, fileLenWords) {
    w.i32(9994, false);
    for (let i = 0; i < 5; i++) w.i32(0, false);
    w.i32(fileLenWords, false);
    w.i32(1000, true); w.i32(type, true);
    w.f64(bb[0]); w.f64(bb[1]); w.f64(bb[2]); w.f64(bb[3]);
    for (let i = 0; i < 4; i++) w.f64(0);
  }
  const shp = new Writer(100 + totalContent);
  header(shp, (100 + totalContent) / 2);
  const shx = new Writer(100 + 8 * recs.length);
  header(shx, (100 + 8 * recs.length) / 2);
  let offsetWords = 50;
  recs.forEach((r, i) => {
    shp.i32(i + 1, false); shp.i32(r.length / 2, false); shp.bytes(r);
    shx.i32(offsetWords, false); shx.i32(r.length / 2, false);
    offsetWords += 4 + r.length / 2;
  });
  return { shp: shp.done(), shx: shx.done() };
}

/* ============================ SHP read ============================ */
function readShp(buf) {
  const ab = buf.buffer || buf;
  const off = buf.byteOffset || 0;
  const dv = new DataView(ab, off, buf.byteLength);
  if (dv.getInt32(0, false) !== 9994) throw new Error(T('err.shp.magic'));
  const geoms = [];
  let p = 100;
  const end = buf.byteLength;
  while (p + 8 <= end) {
    const contentWords = dv.getInt32(p + 4, false);
    const cp = p + 8;
    const clen = contentWords * 2;
    if (clen <= 0 || cp + clen > end) break;
    geoms.push(parseShape(dv, cp, clen));
    p = cp + clen;
  }
  return geoms;
}
function parseShape(dv, p, len) {
  const t = dv.getInt32(p, true);
  const base = t % 10 === 0 ? t : t; // 1/11/21 pt, 3/13/23 line, 5/15/25 poly, 8/18/28 mpoint
  const kind = t === 1 || t === 11 || t === 21 ? 'pt'
    : t === 3 || t === 13 || t === 23 ? 'line'
      : t === 5 || t === 15 || t === 25 ? 'poly'
        : t === 8 || t === 18 || t === 28 ? 'mpt' : null;
  if (t === 0 || !kind) return null;
  if (kind === 'pt') return { type: 'Point', coordinates: [dv.getFloat64(p + 4, true), dv.getFloat64(p + 12, true)] };
  if (kind === 'mpt') {
    const n = dv.getInt32(p + 36, true); const cs = [];
    for (let i = 0; i < n; i++) cs.push([dv.getFloat64(p + 40 + i * 16, true), dv.getFloat64(p + 48 + i * 16, true)]);
    return cs.length === 1 ? { type: 'Point', coordinates: cs[0] } : { type: 'MultiPoint', coordinates: cs };
  }
  const nParts = dv.getInt32(p + 36, true), nPts = dv.getInt32(p + 40, true);
  const partIdx = [];
  for (let i = 0; i < nParts; i++) partIdx.push(dv.getInt32(p + 44 + i * 4, true));
  const ptBase = p + 44 + nParts * 4;
  const parts = [];
  for (let i = 0; i < nParts; i++) {
    const s = partIdx[i], e = (i === nParts - 1) ? nPts : partIdx[i + 1];
    const ring = [];
    for (let j = s; j < e; j++) ring.push([dv.getFloat64(ptBase + j * 16, true), dv.getFloat64(ptBase + j * 16 + 8, true)]);
    if (ring.length) parts.push(ring);
  }
  if (!parts.length) return null;
  if (kind === 'line') return parts.length === 1 ? { type: 'LineString', coordinates: parts[0] } : { type: 'MultiLineString', coordinates: parts };
  // polygon: negative signed area (CW) = outer
  const polys = [];
  for (const ring of parts) {
    if (signedArea(ring) <= 0) polys.push([orient(ring, true)]);
    else if (polys.length) polys[polys.length - 1].push(orient(ring, false));
    else polys.push([orient(ring, true)]);
  }
  return polys.length === 1 ? { type: 'Polygon', coordinates: polys[0] } : { type: 'MultiPolygon', coordinates: polys };
}

/* ============================ DXF (R12 / AC1009) ============================ */
const ACI = [5, 3, 1, 2, 4, 6, 30, 140, 90, 210, 8, 250, 40, 170, 200];
const TR_MAP = { 'ç':'c','Ç':'C','ğ':'g','Ğ':'G','ı':'i','İ':'I','ö':'o','Ö':'O','ş':'s','Ş':'S','ü':'u','Ü':'U',
  'â':'a','Â':'A','î':'i','Î':'I','û':'u','Û':'U','é':'e','É':'E','ñ':'n','Ñ':'N','á':'a','í':'i','ó':'o','ú':'u' };
function toAscii(s) {
  let out = '';
  for (const ch of String(s)) out += (TR_MAP[ch] !== undefined ? TR_MAP[ch] : (ch.charCodeAt(0) < 128 ? ch : '_'));
  return out;
}
function dxfLayerName(v, used, warn) {
  let s = (v === null || v === undefined || v === '') ? '0' : String(v);
  s = toAscii(s).replace(/[<>\/\\":;?*|='`,\s]/g, '_').toUpperCase().substring(0, 31);
  if (!s) s = 'LAYER';
  let base = s, n = 1;
  while (used.has(s) && used.get(s) !== v) { const suf = String(n++); s = base.substring(0, 31 - suf.length) + suf; }
  if (String(v).toUpperCase() !== s) warn('layer', 'log.dxf.layerRenamed', [v, s]);
  used.set(s, v);
  return s;
}
function writeDxf(fc, opt, warn) {
  opt = opt || {};
  const g = [];
  const p = (code, val) => { g.push(String(code)); g.push(String(val)); };
  const num = v => (Math.round(v * 1e8) / 1e8).toFixed(8).replace(/\.?0+$/, '') || '0';

  const layerOf = new Map();
  const usedNames = new Map();
  const layers = [];
  for (const f of fc.features) {
    const raw = opt.layerField ? (f.properties || {})[opt.layerField] : '0';
    const key = String(raw === undefined || raw === null || raw === '' ? '0' : raw);
    if (!layerOf.has(key)) {
      const nm = opt.layerField ? dxfLayerName(key, usedNames, warn) : '0';
      layerOf.set(key, nm);
      if (!layers.includes(nm)) layers.push(nm);
    }
  }
  if (!layers.length) layers.push('0');
  if (!layers.includes('0')) layers.unshift('0');

  const bb = fcBbox(fc) || [0, 0, 0, 0];
  p(0, 'SECTION'); p(2, 'HEADER');
  p(9, '$ACADVER'); p(1, 'AC1009');
  p(9, '$INSBASE'); p(10, '0'); p(20, '0'); p(30, '0');
  p(9, '$EXTMIN'); p(10, num(bb[0])); p(20, num(bb[1])); p(30, '0');
  p(9, '$EXTMAX'); p(10, num(bb[2])); p(20, num(bb[3])); p(30, '0');
  p(9, '$LIMMIN'); p(10, num(bb[0])); p(20, num(bb[1]));
  p(9, '$LIMMAX'); p(10, num(bb[2])); p(20, num(bb[3]));
  p(0, 'ENDSEC');

  p(0, 'SECTION'); p(2, 'TABLES');
  p(0, 'TABLE'); p(2, 'LTYPE'); p(70, 1);
  p(0, 'LTYPE'); p(2, 'CONTINUOUS'); p(70, 64); p(3, 'Solid line'); p(72, 65); p(73, 0); p(40, '0');
  p(0, 'ENDTAB');
  p(0, 'TABLE'); p(2, 'LAYER'); p(70, layers.length);
  layers.forEach((nm, i) => {
    p(0, 'LAYER'); p(2, nm); p(70, 0); p(62, nm === '0' ? 7 : ACI[i % ACI.length]); p(6, 'CONTINUOUS');
  });
  p(0, 'ENDTAB');
  p(0, 'TABLE'); p(2, 'STYLE'); p(70, 1);
  p(0, 'STYLE'); p(2, 'STANDARD'); p(70, 0); p(40, '0'); p(41, '1'); p(50, '0'); p(71, 0); p(42, '2.5');
  p(3, 'txt'); p(4, '');
  p(0, 'ENDTAB');
  p(0, 'ENDSEC');

  p(0, 'SECTION'); p(2, 'ENTITIES');
  const th = opt.textHeight || 1;
  let nEnt = 0, asciiHit = 0;
  for (const f of fc.features) {
    const raw = opt.layerField ? (f.properties || {})[opt.layerField] : '0';
    const key = String(raw === undefined || raw === null || raw === '' ? '0' : raw);
    const lay = layerOf.get(key) || '0';
    const geom = f.geometry;
    if (!geom) continue;
    const cls = shapeClass(geom);
    if (cls === 'point') {
      for (const c of pointsOf(geom)) { p(0, 'POINT'); p(8, lay); p(10, num(c[0])); p(20, num(c[1])); p(30, '0'); nEnt++; }
    } else if (cls) {
      const isPoly = cls === 'polygon';
      for (const part of partsOf(geom)) {
        if (part.length < 2) continue;
        let pts = part;
        if (isPoly) { pts = closeRing(part); pts = pts.slice(0, pts.length - 1); }
        p(0, 'POLYLINE'); p(8, lay); p(66, 1); p(70, isPoly ? 1 : 0);
        p(10, '0'); p(20, '0'); p(30, '0');
        for (const c of pts) { p(0, 'VERTEX'); p(8, lay); p(10, num(c[0])); p(20, num(c[1])); p(30, '0'); }
        p(0, 'SEQEND'); p(8, lay);
        nEnt++;
      }
    }
    if (opt.labelField) {
      const v = (f.properties || {})[opt.labelField];
      if (v !== undefined && v !== null && v !== '') {
        const anchor = labelAnchor(geom);
        if (anchor) {
          p(0, 'TEXT'); p(8, lay); p(10, num(anchor[0])); p(20, num(anchor[1])); p(30, '0');
          let txt = String(v).replace(/\r?\n/g, ' ').substring(0, 250);
          if (opt.asciiText !== false) { const a = toAscii(txt); if (a !== txt) { txt = a; asciiHit++; } }
          p(40, num(th)); p(1, txt); p(7, 'STANDARD');
          nEnt++;
        }
      }
    }
  }
  p(0, 'ENDSEC'); p(0, 'EOF');
  if (asciiHit) warn('text', 'log.dxf.textAscii', [asciiHit]);
  return { text: g.join('\r\n') + '\r\n', entities: nEnt, layers: layers };
}
function labelAnchor(g) {
  const cs = [];
  eachCoord(g, c => cs.push(c));
  if (!cs.length) return null;
  if (g.type === 'Point') return cs[0];
  let sx = 0, sy = 0;
  for (const c of cs) { sx += c[0]; sy += c[1]; }
  return [sx / cs.length, sy / cs.length];
}

/* ============================ KML / GPX / CSV ============================ */
function xmlEsc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
function writeKml(fc, opt) {
  opt = opt || {};
  const nameField = opt.labelField;
  const L = ['<?xml version="1.0" encoding="UTF-8"?>',
    '<kml xmlns="http://www.opengis.net/kml/2.2"><Document>'];
  const cstr = c => c[0] + ',' + c[1] + ',0';
  const ringStr = r => '<coordinates>' + closeRing(r).map(cstr).join(' ') + '</coordinates>';
  for (const f of fc.features) {
    const g = f.geometry; if (!g) continue;
    L.push('<Placemark>');
    const props = f.properties || {};
    if (nameField && props[nameField] !== undefined && props[nameField] !== null) L.push('<name>' + xmlEsc(props[nameField]) + '</name>');
    const keys = Object.keys(props);
    if (keys.length) {
      L.push('<ExtendedData>');
      for (const k of keys) {
        const v = props[k];
        L.push('<Data name="' + xmlEsc(k) + '"><value>' + xmlEsc(v === null || v === undefined ? '' : (typeof v === 'object' ? JSON.stringify(v) : v)) + '</value></Data>');
      }
      L.push('</ExtendedData>');
    }
    L.push(kmlGeom(g, cstr, ringStr));
    L.push('</Placemark>');
  }
  L.push('</Document></kml>');
  return L.join('\n');
}
function kmlGeom(g, cstr, ringStr) {
  switch (g.type) {
    case 'Point': return '<Point><coordinates>' + cstr(g.coordinates) + '</coordinates></Point>';
    case 'MultiPoint': return '<MultiGeometry>' + g.coordinates.map(c => '<Point><coordinates>' + cstr(c) + '</coordinates></Point>').join('') + '</MultiGeometry>';
    case 'LineString': return '<LineString><coordinates>' + g.coordinates.map(cstr).join(' ') + '</coordinates></LineString>';
    case 'MultiLineString': return '<MultiGeometry>' + g.coordinates.map(l => '<LineString><coordinates>' + l.map(cstr).join(' ') + '</coordinates></LineString>').join('') + '</MultiGeometry>';
    case 'Polygon': return kmlPoly(g.coordinates, ringStr);
    case 'MultiPolygon': return '<MultiGeometry>' + g.coordinates.map(p => kmlPoly(p, ringStr)).join('') + '</MultiGeometry>';
    default: return '';
  }
}
function kmlPoly(rings, ringStr) {
  let s = '<Polygon><outerBoundaryIs><LinearRing>' + ringStr(orient(rings[0], true)) + '</LinearRing></outerBoundaryIs>';
  for (let i = 1; i < rings.length; i++) s += '<innerBoundaryIs><LinearRing>' + ringStr(orient(rings[i], false)) + '</LinearRing></innerBoundaryIs>';
  return s + '</Polygon>';
}

function parseCoordText(t) {
  const out = [];
  const toks = String(t).trim().split(/\s+/);
  for (const tok of toks) {
    const a = tok.split(',');
    if (a.length >= 2) {
      const x = parseFloat(a[0]), y = parseFloat(a[1]);
      if (isFinite(x) && isFinite(y)) out.push([x, y]);
    }
  }
  return out;
}

/* CSV → points */
function parseCsv(text) {
  const rows = []; let row = [], cur = '', q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') { if (text[i + 1] === '"') { cur += '"'; i++; } else q = false; }
      else cur += c;
    } else if (c === '"') q = true;
    else if (c === ',' || c === ';' || c === '\t') { row.push(cur); cur = ''; }
    else if (c === '\n') { row.push(cur); rows.push(row); row = []; cur = ''; }
    else if (c === '\r') { /* skip */ }
    else cur += c;
  }
  if (cur !== '' || row.length) { row.push(cur); rows.push(row); }
  return rows.filter(r => r.length && !(r.length === 1 && r[0] === ''));
}
const LAT_KEYS = ['lat', 'latitude', 'y', 'enlem', 'ykoord', 'y_koord', 'north', 'northing'];
const LON_KEYS = ['lon', 'lng', 'long', 'longitude', 'x', 'boylam', 'xkoord', 'x_koord', 'east', 'easting'];
function csvToFc(text) {
  const rows = parseCsv(text);
  if (rows.length < 2) throw new Error(T('err.csv.tooFewRows'));
  const head = rows[0].map(h => h.trim());
  const low = head.map(h => h.toLowerCase().replace(/[^a-z_]/g, ''));
  let xi = -1, yi = -1;
  low.forEach((h, i) => { if (yi < 0 && LAT_KEYS.includes(h)) yi = i; if (xi < 0 && LON_KEYS.includes(h)) xi = i; });
  if (xi < 0 || yi < 0) throw new Error(T('err.csv.noCoords'));
  const feats = [];
  for (let r = 1; r < rows.length; r++) {
    const rw = rows[r];
    const x = parseFloat(rw[xi]), y = parseFloat(rw[yi]);
    if (!isFinite(x) || !isFinite(y)) continue;
    const props = {};
    head.forEach((h, i) => { if (i !== xi && i !== yi) { const v = rw[i]; props[h] = (v !== '' && v !== undefined && !isNaN(Number(v))) ? Number(v) : v; } });
    feats.push({ type: 'Feature', properties: props, geometry: { type: 'Point', coordinates: [x, y] } });
  }
  return { type: 'FeatureCollection', features: feats };
}
function fcToCsv(fc) {
  const keys = [];
  const seen = new Set();
  for (const f of fc.features) for (const k of Object.keys(f.properties || {})) if (!seen.has(k)) { seen.add(k); keys.push(k); }
  const esc = v => { const s = v === null || v === undefined ? '' : (typeof v === 'object' ? JSON.stringify(v) : String(v)); return /[",;\n]/.test(s) ? '"' + s.replace(/"/g, '""') + '"' : s; };
  const L = [['x', 'y'].concat(keys).map(esc).join(',')];
  for (const f of fc.features) {
    const a = labelAnchor(f.geometry);
    if (!a) continue;
    L.push([a[0], a[1]].concat(keys.map(k => (f.properties || {})[k])).map(esc).join(','));
  }
  return L.join('\n');
}

/* ============================ PRJ / WKT ============================ */
const WKT = {
  4326: 'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]',
  3857: 'PROJCS["WGS_1984_Web_Mercator_Auxiliary_Sphere",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Mercator_Auxiliary_Sphere"],PARAMETER["False_Easting",0.0],PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",0.0],PARAMETER["Standard_Parallel_1",0.0],PARAMETER["Auxiliary_Sphere_Type",0.0],UNIT["Meter",1.0]]'
};
function utmWkt(zone, north, datum) {
  const cm = zone * 6 - 183;
  if (datum === 'ED50') {
    return 'PROJCS["ED_1950_UTM_Zone_' + zone + 'N",GEOGCS["GCS_European_1950",DATUM["D_European_1950",SPHEROID["International_1924",6378388.0,297.0]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",' + cm + '.0],PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]';
  }
  return 'PROJCS["WGS_1984_UTM_Zone_' + zone + (north ? 'N' : 'S') + '",GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",SPHEROID["WGS_1984",6378137.0,298.257223563]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",' + (north ? '0.0' : '10000000.0') + '],PARAMETER["Central_Meridian",' + cm + '.0],PARAMETER["Scale_Factor",0.9996],PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]';
}
function tmWkt(cm) {
  return 'PROJCS["TUREF_TM' + cm + '",GEOGCS["GCS_TUREF",DATUM["D_Turkish_National_Reference_Frame",SPHEROID["GRS_1980",6378137.0,298.257222101]],PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]],PROJECTION["Transverse_Mercator"],PARAMETER["False_Easting",500000.0],PARAMETER["False_Northing",0.0],PARAMETER["Central_Meridian",' + cm + '.0],PARAMETER["Scale_Factor",1.0],PARAMETER["Latitude_Of_Origin",0.0],UNIT["Meter",1.0]]';
}

/* ============================ exports ============================ */
root.GeoConv = {
  signedArea, closeRing, orient, bboxOf, fcBbox, eachCoord, shapeClass, partsOf, pointsOf, labelAnchor,
  utf8, fromUtf8, latin1,
  inferFields, writeDbf, readDbf, writeShpShx, readShp,
  writeDxf, writeKml, toAscii, parseCoordText, csvToFc, fcToCsv, parseCsv,
  WKT, utmWkt, tmWkt, SHP_TYPE
};
})(typeof module !== 'undefined' && module.exports ? module.exports : (typeof window !== 'undefined' ? window : globalThis));
