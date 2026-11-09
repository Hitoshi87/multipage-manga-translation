const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

const existing = new Set();
function File(path) { this.fsName = path; }
Object.defineProperty(File.prototype, 'exists', {get() { return existing.has(this.fsName); }});
function Folder(path) { this.fsName = path; this.exists = true; }
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

const source = fs.readFileSync('Photoshop_Typeset.jsx', 'utf8');
assert(source.includes('draft:true,chapterOutput:!!cfg.streamLimit'), 'full chapter keeps draft review status');
assert(source.includes("s.chapterOutput?'chapter':(s.draft?'draft':'typeset')"), 'only chapter output uses the plain name');
assert(source.includes('TYPESET — NHÁP CHƯA DUYỆT'), 'draft layer remains labelled for review');
console.log('Chapter output names, collision handling and draft review status PASS');
