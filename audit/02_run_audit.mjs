/*
 * run_audit.mjs — drive the shipped conversion path over the fixture corpus.
 *
 *   node run_audit.mjs
 *
 * The page is assembled and loaded in a DOM exactly as it is served, and the
 * audit calls the same ingest / checkOutput / convert entry points the
 * interface uses. Nothing is reimplemented, so what is measured is what a user
 * would actually get.
 *
 * For every fixture and every target format two things are recorded:
 *   - the diagnostics the tool reported, as message identifiers
 *   - the bytes it produced, written to work/<fixture>/<target>/
 *
 * Whether a loss actually occurred is determined separately, by reading the
 * output back with independent libraries. This file only captures behaviour.
 */

import { JSDOM } from 'jsdom';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.join(HERE, '..', 'src');
if (!fs.existsSync(path.join(SRC, 'app.html'))) {
  console.error(`Cannot find the sources at ${SRC}.`);
  console.error('This directory must sit inside the repository, alongside src/.');
  process.exit(1);
}
const WORK = path.join(HERE, 'work');
const TARGETS = ['dxf', 'shp', 'geojson', 'kml', 'csv'];

/* ---------------------------------------------------------------- page */

/* The harness copy is regenerated from the shipped source on every run, so it
   cannot fall behind it. The hook exists only in this copy. */
function makeHarness() {
  const anchor = "$('lang').addEventListener('click',switchLang);";
  let html = fs.readFileSync(path.join(SRC, 'app.html'), 'utf8');
  if (!html.includes(anchor)) throw new Error('anchor for the harness hook not found in src/app.html');
  const hook = anchor + `

/* Test-harness hook. Injected at audit time, never present in src/app.html. */
window.__pafta={
  S:S, ingest:ingest, checkOutput:checkOutput, convert:convert,
  clearLog:clearLog, fillAttrSelects:fillAttrSelects, reproject:reproject,
  setDl:function(f){dl=f;},
  setOpt:function(o){ if(o.fmt!==undefined) S.fmt=o.fmt;
                      if(o.src!==undefined) S.src=o.src;
                      if(o.dst!==undefined) S.dst=o.dst; },
  log:function(){ return S.log.map(function(l){
        return {level:l.level,tag:l.tag,key:l.key,args:l.args}; }); }
};`;
  fs.writeFileSync(path.join(HERE, 'work', 'app.harness.html'), html.replace(anchor, hook));
}

function assemble() {
  let html = fs.readFileSync(path.join(HERE, 'work', 'app.harness.html'), 'utf8');
  const parts = { '/*__I18N__*/': 'i18n.js', '/*__GEOCONV__*/': 'geoconv.js', '/*__PROJ__*/': 'proj.js' };
  for (const [tok, f] of Object.entries(parts)) {
    if (!html.includes(tok)) throw new Error('placeholder missing: ' + tok);
    html = html.replace(tok, () => fs.readFileSync(path.join(SRC, f), 'utf8'));
  }
  // Archive handling is out of scope for this audit: zipped fixtures are
  // expanded beforehand and their members passed individually.
  /* Archive packaging is not what this audit measures. The stub records the
     entries geoconv produced and hands back a marker, so the real .shp, .dbf,
     .prj and .cpg bytes can be written to disk individually and read back with
     independent libraries. */
  html = html.replace('/*__ZIP__*/',
    "window.__zipEntries=[];"
    + "window.Zip={zipStore:function(entries){window.__zipEntries=entries.map(function(e){"
    + "return {name:e.name,data:e.data};});return new Uint8Array([80,75,3,4]);},"
    + "unzip:function(){throw new Error('zip reading is out of scope for the audit harness');},"
    + "crc32:function(){return 0;}};");
  return html;
}

async function openPage() {
  const errors = [];
  const dom = new JSDOM(assemble(), {
    url: 'http://localhost/', runScripts: 'dangerously', pretendToBeVisual: true,
    beforeParse(w) {
      w.HTMLCanvasElement.prototype.getContext = () => new Proxy({}, {
        get: (_, k) => (k === 'canvas' ? { width: 900, height: 600 } : () => {})
      });
      w.addEventListener('error', e => errors.push(e.message));
    }
  });
  await new Promise(r => setTimeout(r, 60));
  if (!dom.window.__pafta) throw new Error('harness hook missing');
  return { window: dom.window, errors };
}

/* ------------------------------------------------------------- fixtures */

/** Each entry lists the files a user would select for that fixture. */
function fixtureFiles() {
  const fx = path.join(HERE, 'fixtures');
  const xf = path.join(HERE, 'fixtures_x');
  const list = [];
  for (const name of fs.readdirSync(fx).sort()) {
    if (name.endsWith('.zip')) continue;                 // expanded form used instead
    list.push({ id: name.slice(0, 3), name, files: [path.join(fx, name)] });
  }
  for (const dir of fs.existsSync(xf) ? fs.readdirSync(xf).sort() : []) {
    const members = fs.readdirSync(path.join(xf, dir)).sort().map(m => path.join(xf, dir, m));
    list.push({ id: dir.slice(0, 3), name: dir, files: members });
  }
  return list.sort((a, b) => a.id.localeCompare(b.id));
}

function toFiles(window, paths) {
  return paths.map(p => {
    const buf = fs.readFileSync(p);
    return new window.File([new Uint8Array(buf)], path.basename(p),
      { type: 'application/octet-stream' });
  });
}

/* ------------------------------------------------------------------ run */

const results = [];
fs.mkdirSync(WORK, { recursive: true });
makeHarness();
const page = await openPage();
const { window } = page;
const P = window.__pafta;

// English throughout, so that captured identifiers are unambiguous and any
// untranslated string is visible.
window.I18N.setLang('en');

const captured = [];
P.setDl((blob, fname) => captured.push({ fname, blob }));

for (const fx of fixtureFiles()) {
  for (const target of TARGETS) {
    /* Reload the file for every target. The log accumulates within a session,
       so converting several formats in one session would attribute an earlier
       format's diagnostics to a later one. A user loads a file and picks a
       format; that is the unit being measured. */
    const entry = {
      fixture: fx.id, file: fx.name, target,
      src: null, features: 0, readError: null,
      reported: [], writeError: null, outputs: []
    };

    try {
      await P.ingest(toFiles(window, fx.files));
    } catch (e) {
      entry.readError = String(e && e.message || e);
    }
    entry.src = P.S.src;
    entry.features = P.S.fc ? P.S.fc.features.length : 0;

    if (!P.S.fc) {
      entry.reported = P.log();
      results.push(entry);
      continue;
    }

    /* Target CRS equals source, so this measures format conversion rather than
       reprojection. Consequences of that choice, such as writing geographic
       coordinates into DXF, are themselves things the tool should disclose. */
    P.setOpt({ fmt: target, dst: entry.src });
    try {
      P.reproject();
      P.fillAttrSelects();
      P.checkOutput();
      captured.length = 0;
      window.__zipEntries = [];
      P.convert();
    } catch (e) {
      entry.writeError = String(e && e.message || e);
    }

    entry.reported = P.log().map(l => ({ level: l.level, tag: l.tag, key: l.key, args: l.args }));

    const outDir = path.join(WORK, fx.id, target);
    fs.mkdirSync(outDir, { recursive: true });
    if (window.__zipEntries.length) {
      // shapefile: write the members the writer produced, unpackaged
      for (const e of window.__zipEntries) {
        fs.writeFileSync(path.join(outDir, e.name), Buffer.from(e.data));
        entry.outputs.push(e.name);
      }
    } else {
      for (const c of captured) {
        const ab = await c.blob.arrayBuffer();
        fs.writeFileSync(path.join(outDir, c.fname), Buffer.from(ab));
        entry.outputs.push(c.fname);
      }
    }
    results.push(entry);
  }
}

fs.writeFileSync(path.join(WORK, 'reported.json'), JSON.stringify(results, null, 1));

/* --------------------------------------------------------------- report */

const byFixture = new Map();
for (const r of results) {
  if (!byFixture.has(r.fixture)) byFixture.set(r.fixture, []);
  byFixture.get(r.fixture).push(r);
}
console.log(`fixtures: ${byFixture.size}   conversions: ${results.length}`);
console.log(`page errors: ${page.errors.length ? page.errors.join('; ') : 'none'}\n`);

for (const [id, rows] of byFixture) {
  const r0 = rows[0];
  console.log(`${id}  ${r0.file}   src=${r0.src}  features=${r0.features}` +
    (r0.readError ? `  READ ERROR: ${r0.readError}` : ''));
  for (const r of rows) {
    const keys = [...new Set(r.reported
      .filter(x => x.level !== 'ok' && x.key !== 'log.read.summary' && x.key !== 'log.read.inputSize')
      .map(x => x.key))];
    const files = r.outputs.length ? r.outputs.join(', ') : '(no output)';
    console.log(`    ${r.target.padEnd(8)} ${files.padEnd(34)} ${keys.length ? keys.join(' ') : '-'}`
      + (r.writeError ? `  WRITE ERROR: ${r.writeError}` : ''));
  }
}
