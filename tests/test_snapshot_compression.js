const fs=require('fs'),vm=require('vm'),assert=require('assert');
let saved=false,closed=false;
const ctx={app:{},DocumentMode:{RGB:'RGB'},ChangeMode:{RGB:'RGB'},BitsPerChannelType:{EIGHT:8},Extension:{LOWERCASE:'lower'},SaveOptions:{DONOTSAVECHANGES:'no'},PNGSaveOptions:function(){},File:function(path){this.fsName=path;}};
const copy={mode:'RGB',saveAs(file,opts){assert.strictEqual(opts.compression,3);assert.strictEqual(opts.interlaced,false);saved=true;},close(){closed=true;}};
const doc={duplicate(name,merged){assert.strictEqual(merged,true);return copy;}};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('scripts/core.jsxinc','utf8'),ctx);
const result=ctx.MTA.snapshot(doc,{fsName:'/temp/page'});
assert(saved && closed);assert.strictEqual(result.fsName,'/temp/page/input.png');assert.strictEqual(ctx.app.activeDocument,doc);
console.log('Snapshots use lossless PNG compression and restore the original document PASS');
