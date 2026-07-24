# Pafta

**GIS ile CAD arasında vektör veri dönüştürücü.** Shapefile, GeoJSON, KML, GPX ve CSV
dosyalarını birbirine ve DXF'e çevirir; koordinat sistemini dönüştürür; ne kaybedildiğini
satır satır söyler.

Tamamen tarayıcıda çalışır. Sunucu yok, yükleme yok, harici bağımlılık yok — tek bir HTML
dosyası, çevrimdışı da açılır. Veri cihazdan çıkmaz.

[English summary below](#english)
siteyi kullanmak için: https://tlhksy.github.io/Convert/dist/ 
---

## Neden

Shapefile → CAD geçişi saf bir format dönüşümü değildir. Koordinat sistemi, öznitelik–katman
eşlemesi, etiketlerin nasıl yazılacağı, poligon deliklerinin ne olacağı, alan adı sınırları,
karakter kodlaması — hepsi karar gerektirir. Mevcut çevrimiçi dönüştürücülerin çoğu bu
kararları ya sormaz ya da sessizce, çoğu zaman yanlış verir. Sonuç, açıldığında bozuk olduğu
belli olmayan dosyalardır.

Pafta'nın ayrım noktası dönüştürme değil, **ne kaybettiğini söylemesidir**. Her çalıştırmada
bir dönüşüm günlüğü üretir: alan adın 10 karaktere indi, katman adın ASCII'ye çevrildi,
`.cpg` yoktu Latin-1 varsayıldı, poligon deliğin ayrı polyline oldu.

En sert kontrol şu: hedef koordinat sistemi derece cinsindeyken DXF istersen dönüştürmeyi
**hata** olarak işaretler. DXF birimsizdir; coğrafi koordinatlarla üretilen bir çizim CAD
içinde 0.04 birim genişliğinde olur ve bütün ölçü hesapları anlamsızlaşır. Uygulama bunu
söyler ve tek tıkla en yakın metre tabanlı dilime geçirir.

## Ne yapar

**Girdi:** Shapefile (`.zip` veya `.shp`+`.dbf`+…), GeoJSON, KML, GPX, CSV
**Çıktı:** DXF (R12/AC1009), Shapefile (beşli, ZIP), GeoJSON, KML, CSV

**Koordinat sistemleri:** WGS 84, Web Mercator, TUREF 3° dilimleri (TM27–TM45),
WGS 84 UTM ve ED50 UTM dilimleri. Kaynak sistem `.prj` dosyasından otomatik okunur.

**Önizleme:** Geometri hedef koordinat sisteminde çizilir; imleç gerçek dünya koordinatını
gösterir, ölçek çubuğu ve genişlik/yükseklik okuması birimin ne olduğunu görünür kılar.
Derece cinsinden bir DXF'in neden bozuk olacağı böylece uyarıyı okumadan önce anlaşılır.

Her formatta tam olarak neyin kaybedildiği: **[docs/FORMATS.md](docs/FORMATS.md)**

## Kullanım

`dist/index.html` dosyasını indirip çift tıkla. Hepsi bu — kurulum yok, internet bile gerekmez.

GitHub Pages üzerinden yayınlamak için: depo ayarlarında **Settings → Pages → Source: GitHub Actions**
seç. `main` dalına her itmede `dist/` otomatik yayınlanır.

## Geliştirme

```bash
npm test          # 35 birim testi, bağımlılık yok (node:test)
npm run build     # src/ dosyalarını dist/index.html içine gömer
npm run check     # ikisi birden
```

Kaynak dört dosyadan ibaret ve hiçbirinin bağımlılığı yok:

| Dosya | İş |
|---|---|
| `src/geoconv.js` | Shapefile/DBF ikili okuma-yazma, DXF R12 yazıcı, KML/CSV |
| `src/proj.js` | Transverse Mercator ve Web Mercator, ileri/geri |
| `src/zip.js` | ZIP yazıcı (stored) ve okuyucu (stored + deflate) |
| `src/app.html` | Arayüz; derlemede diğer üçü buraya gömülür |

`dist/index.html` derleme çıktısıdır ama depoda tutulur; böylece indirip doğrudan
çalıştırılabilir. CI, gömülü sürümün kaynakla aynı olduğunu her itmede doğrular.

## Doğrulama

Kendi yazdığın okuyucunun kendi yazdığın yazıcıyı okuyabilmesi hiçbir şey kanıtlamaz.
Asıl soru, üretilen dosyaların **başkalarının kütüphanelerinde** açılıp açılmadığıdır.

```bash
pip install pyshp ezdxf pyproj
node scripts/make_fixtures.js && python scripts/validate_external.py
```

Bu betik CI'da her itmede koşar ve şunları doğrular:

- Yazılan shapefile **pyshp** ile açılıyor: çoklu halka, delik ayrı parça olarak,
  doğru bbox, UTF-8 öznitelikler.
- Yazılan DXF **ezdxf** ile AC1009 olarak açılıyor: katman tablosu, kapalılık bayrakları
  (poligonlar kapalı, çizgiler açık), ASCII'ye çevrilmiş etiketler.
- Projeksiyon çıktısı **pyproj/PROJ** referansından **1 mm'den az** sapıyor
  (ölçülen: UTM 35N için 0.00016 m, TUREF TM33 için 0.00036 m).
- Yazılan ZIP arşivleri sistem `unzip` aracıyla hatasız geçiyor.

## Sınırlar

Bunlar bilinçli tercihler, eksik değil:

- **DWG yazılmaz.** Kapalı format; Open Design Alliance lisansı gerekir. AutoCAD ve
  NetCAD dahil bütün CAD yazılımları DXF'i açar.
- **GPKG yok.** SQLite gerektirir.
- **ED50 dönüşümü yaklaşıktır** (Avrupa ortalaması 3 parametreli kayma, birkaç metre hata).
  Kadastral, imar veya aplikasyon işi için kullanılmaz. Türkiye'de dolaşan CAD verisinin
  çoğu ED50 olduğu ve bunu sessizce WGS 84 sanmak çok daha büyük bir hata olduğu için var.
- **Topoloji düzeltilmez.** Kendi kesen poligonlar için QGIS geometri denetleyicisi.
- **Büyük veri için değil.** Her şey bellekte; 60.000 ögeden sonra uyarı verir.
  Milyonluk veri için `ogr2ogr`.

## Lisans

MIT — [LICENSE](LICENSE)

---

<a name="english"></a>

## English

**Pafta** is a browser-based vector data converter between GIS and CAD formats.
It reads Shapefile, GeoJSON, KML, GPX and CSV; writes DXF, Shapefile, GeoJSON, KML and CSV;
transforms coordinate reference systems; and reports exactly what each conversion loses.

Everything runs client-side in a single self-contained HTML file. No server, no upload,
no external dependencies, works offline. Data never leaves the device.

The distinguishing feature is not the conversion but the **conversion log**. Field name
truncated to 10 characters, layer name transliterated to ASCII, no `.cpg` so Latin-1
assumed, polygon hole written as a separate polyline — each is reported. The strictest
check refuses DXF export when the target CRS is in degrees, because DXF is unitless and a
geographic-coordinate drawing measures 0.04 units across, making every scale and area
calculation meaningless.

Coordinate transformations use Snyder's sixth-order Transverse Mercator series and agree
with PROJ to **better than 1 mm**. Written shapefiles and DXF files are verified in CI
against **pyshp** and **ezdxf** — third-party readers, not our own.

The UI is in Turkish. Coordinate system presets favour Turkish TUREF 3° zones and ED50 UTM
alongside the standard WGS 84 UTM grid, but the format handling is not region-specific.

Run `npm test` for the unit suite, `npm run build` to produce `dist/index.html`.
See [docs/FORMATS.md](docs/FORMATS.md) for the full loss inventory per format.
