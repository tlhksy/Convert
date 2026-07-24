const { test } = require('node:test');
const assert = require('node:assert');
const { Zip } = require('../src/zip.js');

const enc = new TextEncoder();

test('yazılan ZIP kendi okuyucusuyla geri açılır', async () => {
  const z = Zip.zipStore([
    { name: 'katman.shp', data: new Uint8Array([1, 2, 3, 255, 0, 128]) },
    { name: 'katman.prj', data: enc.encode('GEOGCS["GCS_WGS_1984"...]') },
  ]);
  const back = await Zip.unzip(z);
  assert.strictEqual(back.length, 2);
  assert.strictEqual(back[0].name, 'katman.shp');
  assert.deepStrictEqual(Array.from(back[0].data), [1, 2, 3, 255, 0, 128]);
});

test('UTF-8 dosya adları ve içerik korunur', async () => {
  const z = Zip.zipStore([{ name: 'meşe_çalışması.txt', data: enc.encode('Kırklareli — İğneada') }]);
  const back = await Zip.unzip(z);
  assert.strictEqual(back[0].name, 'meşe_çalışması.txt');
  assert.strictEqual(new TextDecoder().decode(back[0].data), 'Kırklareli — İğneada');
});

test('CRC32 bilinen değeri üretir', () => {
  assert.strictEqual(Zip.crc32(enc.encode('123456789')), 0xCBF43926);
});

test('bozuk arşiv anlaşılır hata verir', async () => {
  await assert.rejects(() => Zip.unzip(new Uint8Array(64)), /ZIP dizini bulunamadı/);
});

test('merkezî dizin ve yerel başlık ofsetleri tutarlı', async () => {
  const z = Zip.zipStore([{ name: 'a', data: enc.encode('x') }, { name: 'b', data: enc.encode('yy') }]);
  const dv = new DataView(z.buffer, z.byteOffset, z.byteLength);
  assert.strictEqual(dv.getUint32(0, true), 0x04034b50, 'yerel başlık imzası');
  const back = await Zip.unzip(z);
  assert.deepStrictEqual(back.map(e => e.name), ['a', 'b']);
});
