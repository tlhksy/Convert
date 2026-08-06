/* zip.js — minimal ZIP writer (stored) + reader (stored/deflate). No dependencies. */
(function (root) {
'use strict';

/* Translation helper. The catalogue loads before this file, but the lookup is
   deferred so that zip.js stays usable on its own: without a catalogue it
   returns the identifier rather than throwing. */
function T(){ var f=(typeof window!=='undefined'&&window.t); return f?f.apply(null,arguments):arguments[0]; }

var TBL = (function () { var t = new Uint32Array(256); for (var n = 0; n < 256; n++) { var c = n; for (var k = 0; k < 8; k++) c = c & 1 ? 0xEDB88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; } return t; })();
function crc32(b) { var c = 0xFFFFFFFF; for (var i = 0; i < b.length; i++) c = TBL[(c ^ b[i]) & 0xFF] ^ (c >>> 8); return (c ^ 0xFFFFFFFF) >>> 0; }
function utf8(s) { return new TextEncoder().encode(s); }
function dosTime(d) { return ((d.getHours() << 11) | (d.getMinutes() << 5) | (d.getSeconds() >> 1)) & 0xFFFF; }
function dosDate(d) { return (((d.getFullYear() - 1980) << 9) | ((d.getMonth() + 1) << 5) | d.getDate()) & 0xFFFF; }

function zipStore(entries) { // [{name, data:Uint8Array}]
  var now = new Date(), t = dosTime(now), dt = dosDate(now);
  var parts = [], central = [], offset = 0;
  entries.forEach(function (e) {
    var nm = utf8(e.name), crc = crc32(e.data), sz = e.data.length;
    var lh = new Uint8Array(30 + nm.length), v = new DataView(lh.buffer);
    v.setUint32(0, 0x04034b50, true); v.setUint16(4, 20, true); v.setUint16(6, 0x0800, true);
    v.setUint16(8, 0, true); v.setUint16(10, t, true); v.setUint16(12, dt, true);
    v.setUint32(14, crc, true); v.setUint32(18, sz, true); v.setUint32(22, sz, true);
    v.setUint16(26, nm.length, true); v.setUint16(28, 0, true);
    lh.set(nm, 30);
    parts.push(lh, e.data);
    var ch = new Uint8Array(46 + nm.length), cv = new DataView(ch.buffer);
    cv.setUint32(0, 0x02014b50, true); cv.setUint16(4, 20, true); cv.setUint16(6, 20, true);
    cv.setUint16(8, 0x0800, true); cv.setUint16(10, 0, true); cv.setUint16(12, t, true); cv.setUint16(14, dt, true);
    cv.setUint32(16, crc, true); cv.setUint32(20, sz, true); cv.setUint32(24, sz, true);
    cv.setUint16(28, nm.length, true); cv.setUint32(42, offset, true);
    ch.set(nm, 46);
    central.push(ch);
    offset += lh.length + sz;
  });
  var cdSize = central.reduce(function (a, c) { return a + c.length; }, 0);
  var eocd = new Uint8Array(22), ev = new DataView(eocd.buffer);
  ev.setUint32(0, 0x06054b50, true);
  ev.setUint16(8, entries.length, true); ev.setUint16(10, entries.length, true);
  ev.setUint32(12, cdSize, true); ev.setUint32(16, offset, true);
  var all = parts.concat(central, [eocd]);
  var total = all.reduce(function (a, c) { return a + c.length; }, 0);
  var out = new Uint8Array(total), p = 0;
  all.forEach(function (c) { out.set(c, p); p += c.length; });
  return out;
}

async function unzip(buf) {
  var u8 = new Uint8Array(buf), dv = new DataView(u8.buffer, u8.byteOffset, u8.byteLength);
  var eocd = -1;
  for (var i = u8.length - 22; i >= 0 && i > u8.length - 65558; i--) if (dv.getUint32(i, true) === 0x06054b50) { eocd = i; break; }
  if (eocd < 0) throw new Error(T('err.zip.noDirectory'));
  var n = dv.getUint16(eocd + 10, true), cdOff = dv.getUint32(eocd + 16, true);
  var out = [], p = cdOff;
  for (var k = 0; k < n; k++) {
    if (dv.getUint32(p, true) !== 0x02014b50) break;
    var method = dv.getUint16(p + 10, true), csize = dv.getUint32(p + 20, true), usize = dv.getUint32(p + 24, true);
    var nl = dv.getUint16(p + 28, true), el = dv.getUint16(p + 30, true), cl = dv.getUint16(p + 32, true);
    var lo = dv.getUint32(p + 42, true);
    var name = new TextDecoder().decode(u8.subarray(p + 46, p + 46 + nl));
    p += 46 + nl + el + cl;
    if (/\/$/.test(name)) continue;
    var lnl = dv.getUint16(lo + 26, true), lel = dv.getUint16(lo + 28, true);
    var ds = lo + 30 + lnl + lel;
    var raw = u8.subarray(ds, ds + csize);
    var data;
    if (method === 0) data = raw.slice();
    else if (method === 8) {
      if (typeof DecompressionStream === 'undefined') throw new Error(T('err.zip.noDecompression'));
      var rs = new Blob([raw]).stream().pipeThrough(new DecompressionStream('deflate-raw'));
      data = new Uint8Array(await new Response(rs).arrayBuffer());
    } else throw new Error(T('err.zip.method', method));
    out.push({ name: name, data: data, size: usize });
  }
  return out;
}
root.Zip = { zipStore: zipStore, unzip: unzip, crc32: crc32 };
})(typeof module !== 'undefined' && module.exports ? module.exports : (typeof window !== 'undefined' ? window : globalThis));
