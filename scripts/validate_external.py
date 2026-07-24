#!/usr/bin/env python3
"""Pafta'nın ürettiği dosyaları bağımsız kütüphanelerle doğrular.

Kendi yazdığımız okuyucunun kendi yazdığımız yazıcıyı okuyabilmesi hiçbir şey
kanıtlamaz. Asıl soru, dosyaların başkalarının kütüphanelerinde açılıp
açılmadığıdır. Bu betik onu sorar.

    pip install pyshp ezdxf pyproj
    node scripts/make_fixtures.js && python scripts/validate_external.py
"""
import sys
from pathlib import Path

TMP = Path(__file__).resolve().parent.parent / "tmp"
fails = []


def check(cond, msg):
    print(("  OK   " if cond else "  FAIL ") + msg)
    if not cond:
        fails.append(msg)


print("shapefile — pyshp ile okunuyor")
import shapefile  # noqa: E402

r = shapefile.Reader(str(TMP / "fixture"))
r.encoding = "utf-8"
check(r.shapeType == 5, f"şekil tipi Polygon (5), bulunan {r.shapeType}")
check(len(r) == 2, f"kayıt sayısı 2, bulunan {len(r)}")
check([f[0] for f in r.fields[1:]] == ["AD", "ALAN", "TIP"], "alan adları 10 karaktere indirilmiş")
recs = list(r.iterShapeRecords())
check(recs[0].record[0] == "Meşe Parseli", f"UTF-8 öznitelik korunmuş: {recs[0].record[0]!r}")
check(abs(recs[0].record[1] - 1234.56) < 1e-6, "ondalıklı sayı korunmuş")
check(list(recs[0].shape.parts) == [0, 5], f"delik ayrı parça, parts={list(recs[0].shape.parts)}")
check(len(recs[0].shape.points) == 10, "dış halka + delik köşe sayısı")
check([round(v, 1) for v in recs[0].shape.bbox] == [0.0, 0.0, 10.0, 10.0], "bbox doğru")

print("\nDXF — ezdxf ile okunuyor")
import ezdxf  # noqa: E402
from collections import Counter  # noqa: E402

doc = ezdxf.readfile(str(TMP / "fixture.dxf"))
check(doc.dxfversion == "AC1009", f"R12/AC1009 olarak tanındı: {doc.dxfversion}")
layers = {l.dxf.name for l in doc.layers}
check({"ORMAN", "ULASIM", "NOKTA"} <= layers, f"katmanlar üretilmiş: {sorted(layers)}")
msp = doc.modelspace()
kinds = Counter(e.dxftype() for e in msp)
check(kinds["POLYLINE"] == 4, f"POLYLINE sayısı 4 (2 halka + 1 üçgen + 1 çizgi), bulunan {kinds['POLYLINE']}")
check(kinds["POINT"] == 1, "POINT yazılmış")
check(kinds["TEXT"] == 4, f"TEXT sayısı 4, bulunan {kinds['TEXT']}")
closed = [e.is_closed for e in msp if e.dxftype() == "POLYLINE"]
check(closed == [True, True, True, False], f"kapalılık bayrakları — poligonlar kapalı, çizgi açık: {closed}")
texts = [e.dxf.text for e in msp if e.dxftype() == "TEXT"]
check(all(t.isascii() for t in texts), f"etiketler ASCII'ye çevrilmiş: {texts}")

print("\nprojeksiyon — pyproj ile karşılaştırılıyor")
import json  # noqa: E402
import subprocess  # noqa: E402
from pyproj import Transformer  # noqa: E402

js = """
const P=require('./src/proj.js').Proj;
const out={};
for (const c of ['EPSG:32635','EPSG:5255','EPSG:3857','EPSG:5254','EPSG:32636'])
  out[c]=P.REG[c].fromWgs84(28.9784,41.0082);
console.log(JSON.stringify(out));
"""
root = Path(__file__).resolve().parent.parent
ours = json.loads(subprocess.check_output(["node", "-e", js], cwd=root).decode())
for code, xy in ours.items():
    epsg = int(code.split(":")[1])
    ref = Transformer.from_crs(4326, epsg, always_xy=True).transform(28.9784, 41.0082)
    d = ((xy[0] - ref[0]) ** 2 + (xy[1] - ref[1]) ** 2) ** 0.5
    check(d < 0.001, f"{code} sapması {d * 1000:.4f} mm")

print()
if fails:
    print(f"{len(fails)} DOĞRULAMA BAŞARISIZ")
    sys.exit(1)
print("bağımsız doğrulama tamam — dosyalar üçüncü taraf kütüphanelerde açılıyor")
