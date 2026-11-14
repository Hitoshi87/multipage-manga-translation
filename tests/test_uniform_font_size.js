const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('scripts/core.jsxinc','utf8'),ctx);
const api=ctx.MTA;
let options=api.letteringSizeOptions({min:10,max:32,autoSize:true,sizePolicy:'uniform',standardSize:18},3);
assert.strictEqual(options.targetSize,54);assert.strictEqual(options.min,48.6);assert(Math.abs(options.max-59.4)<1e-9);
assert.strictEqual(options.autoSize,false);assert.strictEqual(options.sparseBoost,1);
function rect(w,h){return {box:[0,0,w,h],center:[w/2,h/2],rows:Array.from({length:h},(_,y)=>[y,0,w])};}
options=api.letteringSizeOptions({min:10,max:32,sizePolicy:'fixed',standardSize:18},1);
for(const shape of [rect(200,100),rect(400,400)]){
 const p=api.planLayout(shape,['Chờ tôi'],s=>s.length*.5,1,{min:options.min,max:options.max,leading:1.3,sparseBoost:options.sparseBoost});
 assert(p);assert.strictEqual(p.size,18,'bubble size cannot change the fixed font size');
}
assert.strictEqual(api.planLayout(rect(8,8),['Đây là câu quá dài'],s=>s.length*.5,1,{min:18,max:18,leading:1.3,sparseBoost:1}),null);
const adaptive=api.letteringSizeOptions({min:10,max:32,autoSize:true},3);assert.strictEqual(adaptive.min,30);assert.strictEqual(adaptive.max,96);
assert.throws(()=>api.letteringSizeOptions({sizePolicy:'fixed',standardSize:NaN}),/4 đến 250/);
assert.throws(()=>api.letteringSizeOptions({sizePolicy:'bogus',standardSize:18}),/không hợp lệ/);
const source=fs.readFileSync('Photoshop_Typeset.jsx','utf8');
assert(source.includes("st.sizePolicy||'adaptive'"),'legacy supervised jobs retain adaptive sizing');
assert(source.includes('sizePolicy:options().sizePolicy,standardSize:standardSize.text'),'supervised settings include the chosen sizing');
console.log('Global uniform/fixed sizing: resolution scaling, strict bounds, no sparse boost and legacy resume PASS');
