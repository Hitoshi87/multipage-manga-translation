const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const existing = new Set();
function File(path) {
  this.fsName = path;
  const parts = String(path).split('/');
  this.name = parts[parts.length - 1];
}
File.prototype.remove = function () { existing.delete(this.fsName); return true; };
File.prototype.copy = function (dest) { existing.add(dest); return true; };
Object.defineProperty(File.prototype, 'exists', {get() { return existing.has(this.fsName); }});
function Folder(path) { this.fsName = path; this.exists = true; }
Folder.temp = new Folder('/tmp');
const ctx = {
  File, Folder,
  PDFSaveOptions: function () {},
  PhotoshopSaveOptions: function () {},
  PDFEncoding: {JPEGHIGH: 'jpeg'},
  Extension: {LOWERCASE: 'lowercase'},
};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync('scripts/core.jsxinc', 'utf8'), ctx);
const saved = [];
const doc = {saveAs(file) { saved.push(file.fsName); existing.add(file.fsName); }};
const out = new Folder('/out');
const files = {};

ctx.MTA.saveCopy(doc, out, '100.jpg', {psd: false, pdf: true, pdfLayers: true}, 'chapter', files);
assert.strictEqual(files.pdf, '/out/100.pdf');
ctx.MTA.saveCopy(doc, out, '100.jpg', {psd: false, pdf: true}, 'chapter', files);
assert.strictEqual(files.pdf, '/out/100_1.pdf', 'existing output is not overwritten');
existing.add('/out/101.psd');
ctx.MTA.saveCopy(doc, out, '101.jpg', {psd: false, pdf: true}, 'chapter', files);
assert.strictEqual(files.pdf, '/out/101_1.pdf', 'another format also prevents a name collision');
ctx.MTA.saveCopy(doc, out, '100.jpg', {psd: false, pdf: true}, 'draft', files);
assert.strictEqual(files.pdf, '/out/100_DRAFT.pdf', 'trial draft naming is unchanged');

const layerAttempts = [];
const docWithCorruptPdfLayer = {
  saveAs(file, opts) {
    layerAttempts.push(Boolean(opts && opts.layers));
    if (opts && opts.layers === true) {
      throw new Error('Could not complete the Save a Copy command because of a disk error (-1).');
    }
    existing.add(file.fsName);
  }
};
ctx.MTA.saveCopy(docWithCorruptPdfLayer, out, '081.jpeg', {psd: false, pdf: true, pdfLayers: true}, 'chapter', files);
assert.strictEqual(files.pdf, '/out/081.pdf', 'falls back to flat PDF via temp file when layered PDF save throws disk error (-1)');
assert.deepStrictEqual(layerAttempts, [true, true, false]);

const source = fs.readFileSync('Photoshop_Typeset.jsx', 'utf8');
assert(source.includes('draft:true,chapterOutput:!!cfg.streamLimit'), 'full chapter keeps draft review status');
assert(source.includes("s.chapterOutput?'chapter':(s.draft?'draft':'typeset')"), 'only chapter output uses the plain name');
assert(source.includes('TYPESET — NHÁP CHƯA DUYỆT'), 'draft layer remains labelled for review');
console.log('Chapter output names, collision handling and draft review status PASS');
