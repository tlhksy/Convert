/* proj.js — self-contained Transverse Mercator / Web Mercator. No dependencies. */
(function (root) {
'use strict';
var D = Math.PI / 180;
var ELL = {
  WGS84: { a: 6378137.0, f: 1 / 298.257223563 },
  GRS80: { a: 6378137.0, f: 1 / 298.257222101 },
  INTL24: { a: 6378388.0, f: 1 / 297.0 }
};
// ED50 -> WGS84, Europe-mean 3-parameter (approximate; NOT an official Turkish transform)
var ED50_SHIFT = { dx: -87, dy: -98, dz: -121 };

function geo2ecef(lon, lat, h, ell) {
  var e2 = 2 * ell.f - ell.f * ell.f, sp = Math.sin(lat * D), cp = Math.cos(lat * D);
  var N = ell.a / Math.sqrt(1 - e2 * sp * sp);
  return [(N + h) * cp * Math.cos(lon * D), (N + h) * cp * Math.sin(lon * D), (N * (1 - e2) + h) * sp];
}
function ecef2geo(x, y, z, ell) {
  var e2 = 2 * ell.f - ell.f * ell.f, lon = Math.atan2(y, x), p = Math.hypot(x, y);
  var lat = Math.atan2(z, p * (1 - e2)), N, sp, h = 0;
  for (var i = 0; i < 6; i++) {
    sp = Math.sin(lat); N = ell.a / Math.sqrt(1 - e2 * sp * sp);
    h = p / Math.cos(lat) - N;
    lat = Math.atan2(z, p * (1 - e2 * N / (N + h)));
  }
  return [lon / D, lat / D, h];
}
function datumToWgs(lon, lat, from) {
  if (from !== 'ED50') return [lon, lat];
  var c = geo2ecef(lon, lat, 0, ELL.INTL24);
  return ecef2geo(c[0] + ED50_SHIFT.dx, c[1] + ED50_SHIFT.dy, c[2] + ED50_SHIFT.dz, ELL.WGS84);
}
function wgsToDatum(lon, lat, to) {
  if (to !== 'ED50') return [lon, lat];
  var c = geo2ecef(lon, lat, 0, ELL.WGS84);
  return ecef2geo(c[0] - ED50_SHIFT.dx, c[1] - ED50_SHIFT.dy, c[2] - ED50_SHIFT.dz, ELL.INTL24);
}
function tmFwd(lon, lat, p) {
  var ell = p.ell, a = ell.a, e2 = 2 * ell.f - ell.f * ell.f, ep2 = e2 / (1 - e2);
  var phi = lat * D, lam = lon * D, lam0 = p.lon0 * D, k0 = p.k0;
  var sp = Math.sin(phi), cp = Math.cos(phi), tp = Math.tan(phi);
  var N = a / Math.sqrt(1 - e2 * sp * sp), T = tp * tp, C = ep2 * cp * cp;
  var dl = lam - lam0;
  while (dl > Math.PI) dl -= 2 * Math.PI; while (dl < -Math.PI) dl += 2 * Math.PI;
  var A = dl * cp;
  var M = a * ((1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2 * e2 * e2 / 256) * phi
    - (3 * e2 / 8 + 3 * e2 * e2 / 32 + 45 * e2 * e2 * e2 / 1024) * Math.sin(2 * phi)
    + (15 * e2 * e2 / 256 + 45 * e2 * e2 * e2 / 1024) * Math.sin(4 * phi)
    - (35 * e2 * e2 * e2 / 3072) * Math.sin(6 * phi));
  var A2 = A * A, A3 = A2 * A, A4 = A3 * A, A5 = A4 * A, A6 = A5 * A;
  var x = p.fe + k0 * N * (A + (1 - T + C) * A3 / 6 + (5 - 18 * T + T * T + 72 * C - 58 * ep2) * A5 / 120);
  var y = p.fn + k0 * (M + N * tp * (A2 / 2 + (5 - T + 9 * C + 4 * C * C) * A4 / 24
    + (61 - 58 * T + T * T + 600 * C - 330 * ep2) * A6 / 720));
  return [x, y];
}
function tmInv(x, y, p) {
  var ell = p.ell, a = ell.a, e2 = 2 * ell.f - ell.f * ell.f, ep2 = e2 / (1 - e2), k0 = p.k0;
  var M = (y - p.fn) / k0;
  var mu = M / (a * (1 - e2 / 4 - 3 * e2 * e2 / 64 - 5 * e2 * e2 * e2 / 256));
  var e1 = (1 - Math.sqrt(1 - e2)) / (1 + Math.sqrt(1 - e2)), e1_2 = e1 * e1, e1_3 = e1_2 * e1, e1_4 = e1_3 * e1;
  var p1 = mu + (3 * e1 / 2 - 27 * e1_3 / 32) * Math.sin(2 * mu)
    + (21 * e1_2 / 16 - 55 * e1_4 / 32) * Math.sin(4 * mu)
    + (151 * e1_3 / 96) * Math.sin(6 * mu) + (1097 * e1_4 / 512) * Math.sin(8 * mu);
  var sp = Math.sin(p1), cp = Math.cos(p1), tp = Math.tan(p1);
  var C1 = ep2 * cp * cp, T1 = tp * tp;
  var N1 = a / Math.sqrt(1 - e2 * sp * sp);
  var R1 = a * (1 - e2) / Math.pow(1 - e2 * sp * sp, 1.5);
  var Dd = (x - p.fe) / (N1 * k0), D2 = Dd * Dd, D3 = D2 * Dd, D4 = D3 * Dd, D5 = D4 * Dd, D6 = D5 * Dd;
  var lat = p1 - (N1 * tp / R1) * (D2 / 2 - (5 + 3 * T1 + 10 * C1 - 4 * C1 * C1 - 9 * ep2) * D4 / 24
    + (61 + 90 * T1 + 298 * C1 + 45 * T1 * T1 - 252 * ep2 - 3 * C1 * C1) * D6 / 720);
  var lon = p.lon0 * D + (Dd - (1 + 2 * T1 + C1) * D3 / 6
    + (5 - 2 * C1 + 28 * T1 - 3 * C1 * C1 + 8 * ep2 + 24 * T1 * T1) * D5 / 120) / cp;
  return [lon / D, lat / D];
}
var R_MERC = 6378137.0;
function CRS(def) { Object.assign(this, def); }
CRS.prototype.fromWgs84 = function (lon, lat) {
  if (this.kind === 'geo') { var g = wgsToDatum(lon, lat, this.datum); return [g[0], g[1]]; }
  if (this.kind === 'merc') return [R_MERC * lon * D, R_MERC * Math.log(Math.tan(Math.PI / 4 + lat * D / 2))];
  var d = wgsToDatum(lon, lat, this.datum);
  return tmFwd(d[0], d[1], this);
};
CRS.prototype.toWgs84 = function (x, y) {
  if (this.kind === 'geo') { var g = datumToWgs(x, y, this.datum); return [g[0], g[1]]; }
  if (this.kind === 'merc') return [x / R_MERC / D, (2 * Math.atan(Math.exp(y / R_MERC)) - Math.PI / 2) / D];
  var ll = tmInv(x, y, this);
  return datumToWgs(ll[0], ll[1], this.datum);
};
function tm(lon0, k0, fe, fn, ell, datum) { return new CRS({ kind: 'tm', lon0: lon0, k0: k0, fe: fe, fn: fn, ell: ell, datum: datum || 'WGS84', units: 'm' }); }
var REG = {
  'EPSG:4326': new CRS({ kind: 'geo', datum: 'WGS84', units: 'deg', label: 'WGS 84 (coğrafi, derece)' }),
  'EPSG:4258': new CRS({ kind: 'geo', datum: 'WGS84', units: 'deg', label: 'ETRS89 / TUREF (coğrafi, derece)' }),
  'EPSG:4230': new CRS({ kind: 'geo', datum: 'ED50', units: 'deg', label: 'ED50 (coğrafi, derece)' }),
  'EPSG:3857': new CRS({ kind: 'merc', datum: 'WGS84', units: 'm', label: 'Web Mercator' })
};
for (var z = 1; z <= 60; z++) {
  REG['EPSG:' + (32600 + z)] = tm(z * 6 - 183, 0.9996, 500000, 0, ELL.WGS84, 'WGS84');
  REG['EPSG:' + (32700 + z)] = tm(z * 6 - 183, 0.9996, 500000, 10000000, ELL.WGS84, 'WGS84');
  REG['EPSG:' + (23000 + z)] = tm(z * 6 - 183, 0.9996, 500000, 0, ELL.INTL24, 'ED50');
}
[[5253, 27], [5254, 30], [5255, 33], [5256, 36], [5257, 39], [5258, 42], [5259, 45]].forEach(function (t) {
  REG['EPSG:' + t[0]] = tm(t[1], 1.0, 500000, 0, ELL.GRS80, 'WGS84');
});
root.Proj = { REG: REG, ELL: ELL, tm: tm, CRS: CRS, R_MERC: R_MERC };
})(typeof module !== 'undefined' && module.exports ? module.exports : (typeof window !== 'undefined' ? window : globalThis));
