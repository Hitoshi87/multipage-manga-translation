const assert = require('assert'), fs = require('fs'), os = require('os'), path = require('path'), vm = require('vm');
const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'mta-checkpoint-'));
function File(name) { this.fsName = name; this.pos = 0; }
Object.defineProperties(File.prototype, {exists:{get(){return fs.existsSync(this.fsName);}}, length:{get(){return fs.statSync(this.fsName).size;}}});
File.prototype.open = function(mode){this.mode=mode;this.pos=0;if(mode==='w')fs.writeFileSync(this.fsName,'');return true;};
File.prototype.read = function(n){const b=fs.readFileSync(this.fsName);const v=b.subarray(this.pos,n===undefined?b.length:this.pos+n);this.pos+=v.length;return v.toString(this.encoding==='BINARY'?'latin1':'utf8');};
File.prototype.write = function(s){fs.appendFileSync(this.fsName,s);return true;};
File.prototype.close = function(){};
File.prototype.seek = function(n){this.pos=n;};
File.prototype.copy = function(p){fs.copyFileSync(this.fsName,p);return true;};
const ctx={File,MJSON:JSON};vm.createContext(ctx);vm.runInContext(fs.readFileSync('scripts/core.jsxinc','utf8'),ctx);
try {
  const pdf=path.join(dir,'page.pdf');fs.writeFileSync(pdf,'%PDF-1.7\ncontent\n%%EOF\n');
  assert(ctx.MTA.validOutput(pdf));fs.writeFileSync(pdf,'%PDF-1.7\ntruncated');assert(!ctx.MTA.validOutput(pdf));
  fs.writeFileSync(pdf,'');assert(!ctx.MTA.validOutput(pdf));
  const log=new File(path.join(dir,'draft.json'));
  ctx.MTA.writeCheckpoint(log,JSON.stringify({pages:[1]}));
  ctx.MTA.writeCheckpoint(log,JSON.stringify({pages:[1,2]}));
  assert.deepStrictEqual(JSON.parse(fs.readFileSync(log.fsName+'.bak')), {pages:[1]});
  fs.writeFileSync(log.fsName,'{');ctx.MTA.writeCheckpoint(log,JSON.stringify({pages:[1,2,3]}));
  assert.deepStrictEqual(JSON.parse(fs.readFileSync(log.fsName+'.bak')), {pages:[1]});
  console.log('Checkpoint backup and incomplete PDF detection PASS');
} finally {fs.rmSync(dir,{recursive:true,force:true});}
