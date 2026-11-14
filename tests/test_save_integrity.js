const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('scripts/core.jsxinc','utf8');
const code=source.slice(source.indexOf('    function saveAsWithTempFallback('),source.indexOf('    function saveCopy('));
let clears=0,calls=0,copied=0;
function File(path){this.fsName=path;this.name=path.split('/').pop();this.exists=false;this.remove=()=>{this.exists=false;};this.copy=()=>{copied++;return true;};}
const ctx={app:{displayDialogs:'ALL'},DialogModes:{NO:'NO'},Extension:{LOWERCASE:'lower'},File,Folder:{temp:{fsName:'/tmp'}},unique:()=>1,clearTextStrokeFX:()=>{clears++;return true;}};
vm.createContext(ctx);vm.runInContext(code,ctx);
const failed={saveAs(){calls++;assert.strictEqual(ctx.app.displayDialogs,'NO');throw Error('disk error (-1)');}};
assert.throws(()=>ctx.saveAsWithTempFallback(failed,new File('/out/page.pdf'),{layers:true,preserveEditing:true}),/disk error/);
assert.strictEqual(calls,2);assert.strictEqual(clears,0);assert.strictEqual(copied,0);assert.strictEqual(ctx.app.displayDialogs,'ALL');
calls=0;
const succeeds={saveAs(file){calls++;assert.strictEqual(ctx.app.displayDialogs,'NO');if(calls===1)throw Error('path error');file.exists=true;}};
ctx.saveAsWithTempFallback(succeeds,new File('/out/page.pdf'),{layers:true,preserveEditing:true});
assert.strictEqual(calls,2);assert.strictEqual(clears,0);assert.strictEqual(copied,1);assert.strictEqual(ctx.app.displayDialogs,'ALL');
console.log('Editable save errors preserve layers/effects and restore dialog settings PASS');
