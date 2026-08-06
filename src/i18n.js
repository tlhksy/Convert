/* i18n.js — message catalogue. No dependencies.
 *
 * Every user-facing string has a stable identifier. Log entries store the
 * identifier and its arguments rather than rendered text, so the language can
 * be switched at any time and so that a given diagnostic can be referred to
 * unambiguously regardless of display language.
 *
 * Placeholders are {0}, {1}, ... in argument order.
 */
(function (root) {
'use strict';

var STR = {
en: {
  /* ---- shell ---- */
  'ui.title':            'Pafta — vector data converter',
  'ui.eyebrow':          'Vector data converter · v1',
  'ui.h1sub':            '— between GIS and CAD',
  'ui.sub':              'Converts Shapefile, GeoJSON, KML, GPX and CSV between one another and to DXF. Transforms the coordinate system and reports, line by line, what was lost.',
  'ui.badge.local':      'Data never leaves the browser',
  'ui.badge.noserver':   'No server',
  'ui.panel.settings':   'Conversion settings',

  /* ---- steps ---- */
  'ui.step.file':        'File',
  'ui.step.srcCrs':      'Source system',
  'ui.step.dstCrs':      'Target system',
  'ui.step.output':      'Output',
  'ui.drop.aria':        'Choose or drag files',
  'ui.drop.main':        'Drop files here',
  'ui.hint.srcAuto':     'A .prj sidecar is read automatically when present.',
  'ui.hint.prjRead':     'Read from .prj: {0}',
  'ui.hint.prjUnmatched':'.prj was read but matched no system in the list — choose manually.',
  'ui.hint.guessed':     'Inferred from the coordinate range — please verify.',
  'ui.hint.dstDeg':      'Degrees — not suitable for CAD output.',
  'ui.hint.dstMetre':    'Metres — suitable for CAD and area calculation.',
  'ui.gpkg.soon':        'Not yet available',
  'ui.hint.srcManual':   'Chosen manually.',
  'ui.zip.rw':           'ZIP read/write',
  'ui.zip.wo':           'ZIP write (no compressed reading)',

  /* ---- options ---- */
  'ui.opt.layerField':   'Attribute that defines the layer',
  'ui.opt.labelField':   'Attribute to write as label text',
  'ui.opt.textHeight':   'Text height',
  'ui.opt.nameField':    'Attribute to use as name',

  /* ---- action ---- */
  'ui.go':               'Convert and download',
  'ui.hint.needFile':    'Load a file first.',
  'ui.hint.willDownload':'The output downloads straight to your device.',

  /* ---- viewport ---- */
  'ui.rd.cursor':        'Cursor',
  'ui.rd.features':      'Features',
  'ui.rd.width':         'Width',
  'ui.rd.height':        'Height',

  /* ---- panes ---- */
  'ui.tab.log':          'Conversion log',
  'ui.tab.attr':         'Attributes',
  'ui.log.heading':      'Log',
  'ui.log.empty':        'Nothing done yet.',
  'ui.log.count':        '{0} lines · {1} warnings',
  'ui.attr.empty':       'No data.',
  'ui.attr.first200':    'Showing the first 200 rows ({0} in total).',
  'ui.attr.first14':     'Showing the first 14 attributes ({0} in total).',
  'ui.value.blank':      '(blank)',

  /* ---- crs list ---- */
  'ui.crs.wgs84geo':     'WGS 84 — geographic (degrees)',
  'ui.crs.webmerc':      'Web Mercator (m)',
  'ui.crs.group.turef':  '── Türkiye · TUREF 3° zones (m) ──',
  'ui.crs.group.utm':    '── Türkiye · WGS84 UTM (m) ──',
  'ui.crs.group.ed50':   '── Türkiye · ED50 UTM (m, approximate) ──',
  'ui.crs.group.other':  '── Other UTM zones ──',

  /* ---- footer ---- */
  'ui.footer.local':     'Conversions run entirely in the browser; no file is uploaded.',
  'ui.footer.proj':      'Projections use Snyder series with the meridian arc carried to e^10 and the footpoint latitude solved by iteration (agreement with PROJ better than 0.01 mm within 2° of the central meridian, better than 0.4 mm at the zone edge).',
  'ui.footer.ed50':      'The ED50 transformation is a Europe-mean three-parameter shift — not for cadastral work.',
  'ui.lang':             'Türkçe',

  /* ---- log tags ---- */
  'tag.zip':        'zip',
  'tag.multiple':   'multiple',
  'tag.encoding':   'encoding',
  'tag.mismatch':   'mismatch',
  'tag.missing':    'missing',
  'tag.empty':      'empty',
  'tag.prj':        'prj',
  'tag.csv':        'csv',
  'tag.read':       'read',
  'tag.size':       'size',
  'tag.large':      'large',
  'tag.projection': 'projection',
  'tag.scale':      'scale',
  'tag.format':     'format',
  'tag.compat':     'compatibility',
  'tag.written':    'written',
  'tag.skipped':    'skipped',
  'tag.error':      'error',
  'tag.field':      'field',
  'tag.layer':      'layer',
  'tag.text':       'text',

  /* ---- log messages ---- */
  'log.zip.opened':          '{0} opened — {1} files.',
  'log.shp.multiple':        'More than one shapefile found; the first was used: {0}. Others: {1}',
  'log.shp.noCpg':           'No .cpg file — attributes assumed to be Latin-1. If non-ASCII characters look wrong, export the source as UTF-8.',
  'log.shp.recordMismatch':  'Record counts differ between .shp ({0}) and .dbf ({1}); the shorter one was used.',
  'log.shp.noDbf':           'No .dbf — geometry was read without attributes.',
  'log.shp.noShx':           'No .shx; records were read directly from .shp (not a problem).',
  'log.geom.emptyDropped':   '{0} records held empty geometry and were skipped.',
  'log.crs.noPrj':           'No .prj file — the source coordinate system must be chosen manually.',
  'log.crs.prjUnmatched':    '.prj was recognised but matched none of the systems in the list. The source system must be chosen manually.',
  'log.csv.columnsFound':    'Coordinate columns identified from the header names.',
  'log.read.summary':        '{0} features read — {1}.',
  'log.read.inputSize':      'Input {0}.',
  'log.read.large':          'More than 60,000 features; the browser may slow down. This tool is built for small to medium datasets.',
  'log.proj.failed':         '{0} coordinates could not be transformed to the target system (they may fall outside the zone).',
  'log.dxf.degreeUnits':     'The target system is in degrees. DXF has no units: the drawing would be about {0} × {1} units inside CAD, making scale and area meaningless. Choose a metre-based system.',
  'log.dxf.fixTarget':       'Set target to {0}',
  'log.dxf.formatNote':      'DXF R12 (AC1009) is written: areas become closed POLYLINEs and holes are emitted as separate POLYLINEs, so CAD will not treat them as holes automatically. Attributes are not carried beyond the layer name and TEXT.',
  'log.shp.multipleTypes':   'A shapefile holds a single geometry type. The data will be split into {0} types and delivered as separate files in one ZIP.',
  'log.shp.fieldNote':       'Attribute names are reduced to 10 characters and to ASCII; UTF-8 encoding is declared through a .cpg file.',
  'log.csv.centroidOnly':    'CSV writes only the centroid of each feature — line and area geometry is lost.',
  'log.kml.forcesWgs84':     'KML always expects WGS 84 degrees; the output will be converted to WGS 84 automatically.',
  'log.geojson.notWgs84':    'RFC 7946 GeoJSON recognises WGS 84 only. The file was written with {0} coordinates; the system must be stated manually when handing it to other software.',
  'log.dxf.written':         '{0} CAD entities, {1} layers: {2}.',
  'log.dxf.skipped':         '{0} features were not written because their geometry type is unsupported.',
  'log.out.nothing':         'No geometry left to write.',
  'log.shp.written':         '{0} — .shp/.shx/.dbf/.prj/.cpg in a single ZIP.',
  'log.error':               '{0}',

  /* ---- geoconv diagnostics ---- */
  'log.dbf.fieldRenamed':    'Attribute name "{0}" → "{1}" (DBF field names are limited to 10 characters and ASCII).',
  'log.dbf.valueTruncated':  'Values longer than 254 bytes in field "{0}" were truncated.',
  'log.dxf.layerRenamed':    'Layer name "{0}" → "{1}" (DXF R12 layer names are limited to ASCII and 31 characters).',
  'log.dxf.textAscii':       '{0} label texts had non-ASCII characters replaced by ASCII equivalents (depends on the DXF R12 code page).',

  /* ---- feature counts ---- */
  'count.point':   '{0} points',
  'count.line':    '{0} lines',
  'count.polygon': '{0} polygons',
  'count.other':   '{0} unrecognised',

  /* ---- errors ---- */
  'err.kml.parse':       'KML/XML could not be parsed.',
  'err.geojson.shape':   'GeoJSON structure not recognised.',
  'err.noVectorFile':    'No recognisable vector file found. A shapefile needs at least .shp and .dbf.',
  'err.noGeometry':      'The file was read but contains no geometry.',
  'err.shp.magic':       'Not a valid .shp file (file code 9994 was expected).',
  'err.csv.tooFewRows':  'A CSV must contain at least a header row and one data row.',
  'err.csv.noCoords':    'No coordinate column found in the CSV (lat/lon, x/y or their local equivalents were expected).',
  'err.prj.unmatched':   'PROJCS was recognised but matched nothing in the list'
},

tr: {
  'ui.title':            'Pafta — vektör veri dönüştürücü',
  'ui.eyebrow':          'Vektör veri dönüştürücü · v1',
  'ui.h1sub':            '— GIS ile CAD arasında',
  'ui.sub':              'Shapefile, GeoJSON, KML, GPX ve CSV dosyalarını birbirine ve DXF\'e çevirir. Koordinat sistemini dönüştürür, ne kaybedildiğini satır satır söyler.',
  'ui.badge.local':      'Veri tarayıcıdan çıkmaz',
  'ui.badge.noserver':   'Sunucu yok',
  'ui.panel.settings':   'Dönüştürme ayarları',

  'ui.step.file':        'Dosya',
  'ui.step.srcCrs':      'Kaynak sistem',
  'ui.step.dstCrs':      'Hedef sistem',
  'ui.step.output':      'Çıktı',
  'ui.drop.aria':        'Dosya seç veya sürükle',
  'ui.drop.main':        'Dosyaları buraya bırak',
  'ui.hint.srcAuto':     'Dosya yüklendiğinde .prj varsa otomatik okunur.',
  'ui.hint.prjRead':     '.prj dosyasından okundu: {0}',
  'ui.hint.prjUnmatched':'.prj okundu ama listedeki bir sisteme eşleşmedi — elle seç.',
  'ui.hint.guessed':     'Koordinat aralığına bakılarak tahmin edildi — doğrula.',
  'ui.hint.dstDeg':      'Derece cinsinden — CAD çıktısı için uygun değil.',
  'ui.hint.dstMetre':    'Metre cinsinden — CAD ve alan hesabı için uygun.',
  'ui.gpkg.soon':        'Henüz yok',
  'ui.hint.srcManual':   'Elle seçildi.',
  'ui.zip.rw':           'ZIP oku/yaz',
  'ui.zip.wo':           'ZIP yaz (sıkıştırılmış okuma yok)',

  'ui.opt.layerField':   'Katmanı belirleyen öznitelik',
  'ui.opt.labelField':   'Etiket olarak yazılacak öznitelik',
  'ui.opt.textHeight':   'Yazı yük.',
  'ui.opt.nameField':    'Ad olarak kullanılacak öznitelik',

  'ui.go':               'Dönüştür ve indir',
  'ui.hint.needFile':    'Önce bir dosya yükle.',
  'ui.hint.willDownload':'Çıktı doğrudan cihazına iner.',

  'ui.rd.cursor':        'İmleç',
  'ui.rd.features':      'Öge',
  'ui.rd.width':         'Genişlik',
  'ui.rd.height':        'Yükseklik',

  'ui.tab.log':          'Dönüşüm günlüğü',
  'ui.tab.attr':         'Öznitelikler',
  'ui.log.heading':      'Günlük',
  'ui.log.empty':        'Henüz bir şey yapılmadı.',
  'ui.log.count':        '{0} satır · {1} uyarı',
  'ui.attr.empty':       'Veri yok.',
  'ui.attr.first200':    'İlk 200 satır gösteriliyor ({0} toplam).',
  'ui.attr.first14':     'İlk 14 öznitelik gösteriliyor ({0} toplam).',
  'ui.value.blank':      '(boş)',

  'ui.crs.wgs84geo':     'WGS 84 — coğrafi (derece)',
  'ui.crs.webmerc':      'Web Mercator (m)',
  'ui.crs.group.turef':  '── Türkiye · TUREF 3° dilim (m) ──',
  'ui.crs.group.utm':    '── Türkiye · WGS84 UTM (m) ──',
  'ui.crs.group.ed50':   '── Türkiye · ED50 UTM (m, yaklaşık) ──',
  'ui.crs.group.other':  '── Diğer UTM dilimleri ──',

  'ui.footer.local':     'Dönüşümler tamamen tarayıcıda çalışır; hiçbir dosya yüklenmez.',
  'ui.footer.proj':      'Projeksiyon hesapları Snyder serileriyle yapılır; meridyen yayı e^10 mertebesine kadar alınır, ayak noktası enlemi iterasyonla çözülür (PROJ ile uyum, merkez meridyenden 2° içinde 0,01 mm\'den, dilim kenarında 0,4 mm\'den iyidir).',
  'ui.footer.ed50':      'ED50 dönüşümü Avrupa ortalaması 3 parametreli kaymadır — kadastral iş için kullanılmaz.',
  'ui.lang':             'English',

  'tag.zip':        'zip',
  'tag.multiple':   'çoklu',
  'tag.encoding':   'kodlama',
  'tag.mismatch':   'eşleşme',
  'tag.missing':    'eksik',
  'tag.empty':      'boş',
  'tag.prj':        'prj',
  'tag.csv':        'csv',
  'tag.read':       'okundu',
  'tag.size':       'boyut',
  'tag.large':      'büyük',
  'tag.projection': 'projeksiyon',
  'tag.scale':      'ölçek',
  'tag.format':     'format',
  'tag.compat':     'uyum',
  'tag.written':    'yazıldı',
  'tag.skipped':    'atlandı',
  'tag.error':      'hata',
  'tag.field':      'alan',
  'tag.layer':      'katman',
  'tag.text':       'metin',

  'log.zip.opened':          '{0} açıldı — {1} dosya.',
  'log.shp.multiple':        'Birden fazla shapefile bulundu; ilki kullanıldı: {0}. Diğerleri: {1}',
  'log.shp.noCpg':           '.cpg dosyası yok — öznitelikler Latin-1 varsayıldı. Türkçe karakterler bozuksa kaynağı UTF-8 olarak dışa aktarın.',
  'log.shp.recordMismatch':  '.shp ({0}) ile .dbf ({1}) kayıt sayısı farklı; kısa olan esas alındı.',
  'log.shp.noDbf':           '.dbf yok — öznitelikler olmadan sadece geometri okundu.',
  'log.shp.noShx':           '.shx yok; kayıtlar doğrudan .shp üzerinden okundu (sorun değil).',
  'log.geom.emptyDropped':   '{0} kayıt boş geometri içeriyordu, atlandı.',
  'log.crs.noPrj':           '.prj dosyası yok — kaynak koordinat sistemini elle seçmen gerekiyor.',
  'log.crs.prjUnmatched':    '.prj tanındı ama listedeki sistemlerden birine eşleşmedi. Kaynak sistemi elle seçmen gerekiyor.',
  'log.csv.columnsFound':    'Koordinat sütunları başlık adlarından bulundu.',
  'log.read.summary':        '{0} öge okundu — {1}.',
  'log.read.inputSize':      'Girdi {0}.',
  'log.read.large':          '60.000 üzeri öge var; tarayıcı yavaşlayabilir. Bu araç küçük–orta veri için tasarlandı.',
  'log.proj.failed':         '{0} koordinat hedef sisteme dönüştürülemedi (dilim dışı olabilir).',
  'log.dxf.degreeUnits':     'Hedef sistem derece cinsinden. DXF birimsizdir: çizim CAD içinde yaklaşık {0} × {1} birim olur, ölçek ve alan hesapları anlamsız hale gelir. Metre tabanlı bir sistem seç.',
  'log.dxf.fixTarget':       'Hedefi {0} yap',
  'log.dxf.formatNote':      'DXF R12 (AC1009) yazılır: alanlar kapalı POLYLINE olur, delikler ayrı POLYLINE olarak çıkar — CAD tarafında otomatik olarak "delik" sayılmaz. Öznitelikler katman adı ve TEXT dışında taşınmaz.',
  'log.shp.multipleTypes':   'Shapefile tek bir geometri türü tutabilir. Veri {0} türe ayrılıp ayrı dosyalar halinde tek ZIP içinde verilecek.',
  'log.shp.fieldNote':       'Öznitelik adları 10 karaktere ve ASCII\'ye indirilir; .cpg dosyasıyla UTF-8 kodlaması belirtilir.',
  'log.csv.centroidOnly':    'CSV yalnızca her ögenin ağırlık merkezini yazar — çizgi ve alan geometrisi kaybolur.',
  'log.kml.forcesWgs84':     'KML her zaman WGS 84 derece bekler; çıktı otomatik olarak WGS 84\'e çevrilecek.',
  'log.geojson.notWgs84':    'RFC 7946 GeoJSON yalnızca WGS 84 tanır. Dosya {0} koordinatlarıyla yazıldı; başka bir yazılıma verirken sistemi elle belirtmen gerekir.',
  'log.dxf.written':         '{0} CAD varlığı, {1} katman: {2}.',
  'log.dxf.skipped':         '{0} öge desteklenmeyen geometri türünde olduğu için yazılmadı.',
  'log.out.nothing':         'Yazılacak geometri kalmadı.',
  'log.shp.written':         '{0} — .shp/.shx/.dbf/.prj/.cpg tek ZIP içinde.',
  'log.error':               '{0}',

  'log.dbf.fieldRenamed':    'Öznitelik adı "{0}" → "{1}" (DBF alan adları 10 karakter ve ASCII ile sınırlı).',
  'log.dbf.valueTruncated':  '"{0}" alanında 254 baytı aşan değerler kısaltıldı.',
  'log.dxf.layerRenamed':    'Katman adı "{0}" → "{1}" (DXF R12 katman adları ASCII ve 31 karakterle sınırlı).',
  'log.dxf.textAscii':       '{0} etiket metninde Türkçe karakterler ASCII karşılığına çevrildi (DXF R12 kod sayfasına bağlıdır).',

  'count.point':   '{0} nokta',
  'count.line':    '{0} çizgi',
  'count.polygon': '{0} alan',
  'count.other':   '{0} tanınmayan',

  'err.kml.parse':       'KML/XML ayrıştırılamadı.',
  'err.geojson.shape':   'GeoJSON yapısı tanınmadı.',
  'err.noVectorFile':    'Tanınan bir vektör dosyası bulunamadı. Shapefile için en az .shp ve .dbf gerekir.',
  'err.noGeometry':      'Dosya okundu ama içinde hiç geometri yok.',
  'err.shp.magic':       'Geçerli bir .shp dosyası değil (dosya kodu 9994 bekleniyordu).',
  'err.csv.tooFewRows':  'CSV en az bir başlık ve bir veri satırı içermeli.',
  'err.csv.noCoords':    'CSV içinde koordinat sütunu bulunamadı (lat/lon, x/y, enlem/boylam bekleniyor).',
  'err.prj.unmatched':   'PROJCS tanındı ama listede eşleşmedi'
}
};

var lang = 'en';

function detect() {
  try {
    var saved = root.localStorage && root.localStorage.getItem('pafta.lang');
    if (saved && STR[saved]) return saved;
  } catch (e) { /* storage unavailable */ }
  var nav = (root.navigator && (root.navigator.language || root.navigator.userLanguage)) || '';
  return /^tr\b/i.test(nav) ? 'tr' : 'en';
}

function t(key) {
  var table = STR[lang] || STR.en;
  var s = table[key];
  if (s === undefined) s = STR.en[key];
  if (s === undefined) return key;              // visible, so a missing key is obvious
  var args = Array.prototype.slice.call(arguments, 1);
  return s.replace(/\{(\d+)\}/g, function (m, i) {
    return args[+i] === undefined ? m : String(args[+i]);
  });
}

function setLang(next) {
  if (!STR[next]) return lang;
  lang = next;
  try { root.localStorage && root.localStorage.setItem('pafta.lang', next); } catch (e) {}
  if (root.document) root.document.documentElement.setAttribute('lang', next);
  return lang;
}

function getLang() { return lang; }
function locale() { return lang === 'tr' ? 'tr' : 'en'; }

lang = detect();

root.I18N = { t: t, setLang: setLang, getLang: getLang, locale: locale, STR: STR };
root.t = t;

})(typeof window !== 'undefined' ? window : globalThis);
