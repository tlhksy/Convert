# Formatlar ve kayıplar

Format dönüşümü hiçbir zaman saf bir kopyalama değildir. Her hedef formatın veri modeli
farklıdır ve bir şeyler ya kısaltılır, ya yeniden yorumlanır, ya da tamamen düşer. Bu belge
Pafta'nın her formatta ne yaptığını ve neyi kaybettiğini tek tek sayar. Uygulamadaki
**dönüşüm günlüğü** aynı bilgiyi çalışma anında, senin verine bakarak verir.

---

## Girdi formatları

| Format | Uzantı | Koordinat sistemi | Notlar |
|---|---|---|---|
| Shapefile | `.shp` + `.dbf` (+ `.shx`, `.prj`, `.cpg`) | `.prj`'den okunur | `.zip` içinde de olabilir |
| GeoJSON | `.geojson`, `.json` | RFC 7946 gereği WGS 84 varsayılır | eski `crs` üyesi varsa okunur |
| KML | `.kml` | her zaman WGS 84 | `ExtendedData` ve `SimpleData` öznitelik olarak alınır |
| GPX | `.gpx` | her zaman WGS 84 | `wpt` nokta, `trk`/`rte` çizgi olur |
| CSV | `.csv`, `.txt` | elle seçilir | başlıklardan `lat/lon`, `x/y`, `enlem/boylam` aranır |

`.shx` yoksa kayıtlar doğrudan `.shp` üzerinden sırayla okunur — sorun değil.
`.cpg` yoksa öznitelik kodlaması **Latin-1 varsayılır**; Türkçe karakterler bozuk görünürse
kaynağı UTF-8 olarak yeniden dışa aktar.

---

## Çıktı formatları

### DXF (R12 / AC1009)

R12 seçildi çünkü en geniş uyumlu ASCII DXF sürümü; AutoCAD, BricsCAD, NetCAD, QCAD,
LibreCAD ve ezdxf sorunsuz açar.

Yazılanlar:

- Nokta → `POINT`
- Çizgi → açık `POLYLINE` (grup kodu `70 = 0`)
- Alan → kapalı `POLYLINE` (`70 = 1`)
- Etiket → `TEXT`, seçilen özniteliğin değeri, ögenin ağırlık merkezinde
- Katman tablosu, ACI renkleriyle

Kaybedilenler — bunlar formatın sınırı, hata değil:

- **Öznitelikler taşınmaz.** DXF'in öznitelik modeli yoktur. Bir öznitelik katman adına,
  bir tanesi de `TEXT` içeriğine dönüşebilir; gerisi düşer. Öznitelik gerekiyorsa
  shapefile veya GeoJSON'u da yanında sakla.
- **Delikler delik olarak gitmez.** Poligon delikleri ayrı kapalı `POLYLINE` olarak yazılır.
  CAD tarafında görünürler ama otomatik olarak "boşluk" sayılmazlar; alan hesabında
  dış halkadan elle çıkarman gerekir. (Gerçek delik desteği `HATCH` gerektirir; `HATCH`
  R12'de yoktur.)
- **Katman adları ASCII'ye ve 31 karaktere indirilir.** R12'nin Unicode bildirimi yoktur;
  kod sayfasına bağlıdır. `çayır` → `CAYIR`. Her değişiklik günlüğe yazılır.
- **`TEXT` içeriği de öntanımlı olarak ASCII'ye çevrilir**, aynı gerekçeyle.
- **Z değerleri yazılmaz.** Bütün varlıklar `Z = 0` düzlemindedir.

Kritik uyarı: **DXF birimsizdir.** Dosya "derece" diye bir şey bilmez, sadece sayı bilir.
Coğrafi koordinatlarla (WGS 84, derece) DXF üretirsen çizim CAD içinde 0.04 × 0.03 birim
büyüklüğünde olur; ölçek, uzunluk ve alan hesaplarının hepsi anlamsızlaşır. Pafta bu durumda
dönüştürmeyi hata olarak işaretler ve tek tıkla metre tabanlı bir sisteme geçmeyi önerir.

### Shapefile

Beşli olarak yazılır ve tek ZIP içinde verilir: `.shp`, `.shx`, `.dbf`, `.prj`, `.cpg`.

- **Tek dosya tek geometri türü tutar.** Veri karışıksa nokta / çizgi / alan olarak ayrılır ve
  aynı ZIP içinde `_nokta`, `_cizgi`, `_alan` ekleriyle üç dosya seti yazılır.
- **Öznitelik adları 10 karakter ve ASCII.** dBase III sınırı. `cokUzunOznitelikAdi` →
  `COKUZUNOZN`. Çakışma olursa sonuna sayı eklenir. Hepsi günlüğe yazılır.
- **Metin alanları en fazla 254 bayt.** Uzun metinler kesilir.
- **Kodlama UTF-8**, `.cpg` dosyasıyla bildirilir. Bunu okumayan eski yazılımlar
  Türkçe karakterleri bozuk gösterebilir.
- Halka yönü şartname uyarınca düzeltilir: dış halka saat yönünde, delikler tersine.
  (GeoJSON'un kuralı bunun tam tersidir; dönüşüm otomatik yapılır.)
- Alan tipi değerlerden çıkarılır: hepsi sayıysa `N`, değilse `C`.

### GeoJSON

Kayıpsıza en yakın çıktı. Tek uyarı: RFC 7946 yalnızca WGS 84 tanır. Projeksiyonlu bir
hedef sistem seçip GeoJSON yazarsan dosya o koordinatlarla üretilir ama standarda
uymaz — başka bir yazılıma verirken sistemi elle bildirmen gerekir. Günlük bunu söyler.

### KML

Her zaman WGS 84'e çevrilerek yazılır. Öznitelikler `ExtendedData` içinde korunur,
seçilen bir öznitelik `<name>` olur. Stil bilgisi yazılmaz.

### CSV

**En kayıplı çıktı.** Yalnızca her ögenin ağırlık merkezi yazılır; çizgi ve alan
geometrisi tamamen kaybolur. Nokta verisi veya hızlı bir öznitelik dökümü dışında kullanma.

---

## Koordinat dönüşümü

Transverse Mercator ileri/geri dönüşümleri Snyder'ın altıncı dereceden serileriyle
hesaplanır (*Map Projections — A Working Manual*, USGS PP 1395).

Doğruluk, PROJ referansına karşı ölçülmüş hâliyle:

| Sistem | Sapma |
|---|---|
| WGS84 / UTM 35N | 0.00016 m |
| TUREF / TM30 | 0.00016 m |
| TUREF / TM33 | 0.00036 m |
| Web Mercator | 0.0 m |

Dilim ortasından ±3° içinde milimetre altı, dilim kenarında santimetre altı kalır.
Bu ölçüm `scripts/validate_external.py` içinde otomatik olarak tekrarlanır.

**ED50 uyarısı.** ED50 ↔ WGS 84 dönüşümü Avrupa ortalaması üç parametreli kaymayla
(`dx = -87, dy = -98, dz = -121`) yapılır. Türkiye için resmî bir parametre seti değildir;
beklenen hata birkaç metre mertebesindedir. Kadastral, imar veya aplikasyon işi için
kullanma — o işler için resmî dönüşüm parametreleriyle çalışan bir yazılım gerekir.
ED50 desteğinin buraya konma sebebi, Türkiye'de dolaşan CAD verisinin çoğunun ED50
olması ve bunu sessizce WGS 84 sanmanın çok daha büyük bir hata olmasıdır.

---

## Bilerek yapılmayanlar

- **DWG yazma.** Kapalı format. Üretmek için Open Design Alliance lisansı gerekir.
  Pratikte AutoCAD ve NetCAD dahil bütün CAD yazılımları DXF'i sorunsuz açar.
- **GPKG.** SQLite gerektirir; tarayıcıda WASM olmadan makul değil.
- **Topoloji doğrulama.** Kendi kesen poligonlar, kapanmayan halkalar veya çakışan
  sınırlar düzeltilmez. Bunun için QGIS'in geometri denetleyicisini kullan.
- **Öznitelik yeniden eşleme.** Alan adı/tipi değiştirme arayüzü yok.
