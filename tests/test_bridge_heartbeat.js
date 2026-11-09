const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync('scripts/core.jsxinc', 'utf8');

function run({mode, finishAt = Infinity, cancel = false, operation = 'scan'}) {
  let now = 0, launched = false;
  const files = new Map(), notices = [];
  function FakeDate() { this.getTime = () => now; }
  function Folder(path) { this.fsName = String(path); this.exists = true; this.parent = this; }
  Folder.prototype.create = () => true;
  function File(path) { this.fsName = String(path); this.parent = new Folder('/tmp'); }
  Object.defineProperty(File.prototype, 'exists', {get() {
    if (this.fsName.endsWith('/.venv/bin/python')) return true;
    if (this.fsName.endsWith('/response.json')) return launched && now >= finishAt;
    if (this.fsName.endsWith('/heartbeat')) return launched && mode !== 'missing';
    return files.has(this.fsName);
  }});
  Object.defineProperty(File.prototype, 'modified', {get() {
    if (!this.fsName.endsWith('/heartbeat')) return null;
    return {getTime: () => mode === 'live' ? now : 0};
  }});
  File.prototype.open = function () { return true; };
  File.prototype.write = function (value) { files.set(this.fsName, String(value)); return true; };
  File.prototype.close = function () {};
  File.prototype.read = function () { return this.fsName.endsWith('/response.json') ? '{"ok":true,"result":{"done":true}}' : files.get(this.fsName); };
  File.prototype.remove = function () { files.delete(this.fsName); return true; };
  const ctx = {File, Folder, Date: FakeDate, MJSON: JSON, isFinite,
    $: {os: 'Linux', sleep() { now += 1000; }}, app: {system() { launched = true; }}};
  vm.createContext(ctx); vm.runInContext(source, ctx);
  let result, error, workerUnresponsive = false;
  try { result = ctx.MTA.request(new Folder('/project'), {operation}, note => { if (note) notices.push(note); return !cancel; }); }
  catch (e) { error = String(e.message); workerUnresponsive = e.workerUnresponsive === true; }
  return {result, error, workerUnresponsive, now, notices, files};
}

const live = run({mode:'live', finishAt:250000});
assert(live.result.done && live.now > 180000, 'a live worker may take longer than 180 seconds');
assert(live.notices.some(s => /còn gửi tín hiệu/.test(s)), 'long-running work reports liveness');
assert(![...live.files.entries()].some(([k,v]) => k.endsWith('/cancel') && v === 'timeout'));
const reported = run({mode:'live', finishAt:198000, operation:'translation_autopilot'});
assert(reported.result.done && reported.now === 198000, 'the reported 198-second autopilot response is accepted');
for (const mode of ['stale','missing']) {
  const failed = run({mode});
  assert.match(failed.error, /không có tín hiệu trong 180 giây \(scan\)/);
  assert(failed.workerUnresponsive, 'silence must not start a conflicting worker');
  if (mode === 'missing') assert.strictEqual(failed.notices.length,0,'a missing heartbeat is never reported as live');
  assert([...failed.files.entries()].some(([k,v]) => k.endsWith('/cancel') && v === 'timeout'));
}
const cancelled = run({mode:'live', cancel:true});
assert.match(cancelled.error, /Đã hủy/);
assert(!cancelled.workerUnresponsive);
assert([...cancelled.files.entries()].some(([k,v]) => k.endsWith('/cancel') && v === 'cancel'));
console.log('Bridge waits while worker is alive; detects silence and preserves cancellation PASS');
