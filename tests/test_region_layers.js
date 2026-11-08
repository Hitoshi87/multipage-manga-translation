// Photoshop is not available here: drive MTA.addRegionOverlays against a recording mock of the DOM.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
function makeEnv(failOnFile){
  const log=[];
  const ctx={log};
  ctx.ElementPlacement={PLACEATBEGINNING:'begin',INSIDE:'inside'};ctx.SaveOptions={DONOTSAVECHANGES:'no'};
  ctx.UnitValue=(v,u)=>({v,u,as:()=>v});ctx.File=function(p){this.path=p;};
  const groups=[];
  const doc={layerSets:{add(){const g={name:'',removed:false,layers:[],remove(){this.removed=true;}};groups.push(g);return g;}}};
  ctx.app={activeDocument:null,open(file){
    if(failOnFile&&file.path===failOnFile)throw new Error('cannot open');
    const layer={
      bounds:[[0,'px'],[0,'px'],[40,'px'],[30,'px']].map(([v])=>({as:()=>v})),name:'',x:0,y:0,
      duplicate(target){const copy={bounds:[10,10,50,40].map(v=>({as:()=>v})),name:'',moved:null,
        translate(dx,dy){this.moved=[dx.v,dy.v];},move(g){g.layers.push(this);this.group=g;}};log.push('dup');return copy;}};
    return {activeLayer:layer,close(){log.push('close');}};}};
  return {ctx,doc,groups,log};
}
function load(ctx){
  vm.createContext(ctx);
  vm.runInContext(fs.readFileSync('scripts/core.jsxinc','utf8'),ctx);
  return ctx.MTA;
}
// Success: one layer per bubble, placed at its page position, inside a single named group.
{
  const {ctx,doc,groups}=makeEnv();const MTA=load(ctx);
  const made=MTA.addRegionOverlays(doc,[{id:'B001',file:'a.png',x:100,y:200},{id:'B002',file:'b.png',x:300,y:50},{id:'REST',file:'r.png',x:5,y:6}],{aiIds:['B002']});
  assert.strictEqual(made,3);
  assert.strictEqual(groups.length,1);assert.strictEqual(groups[0].name,'CLEAN — từng bubble');
  const names=groups[0].layers.map(l=>l.name);
  assert.deepStrictEqual(names,['CLEAN B001','CLEAN AI — CẦN DUYỆT B002','CLEAN (phần còn lại)']);
  // duplicate() reported bounds starting at (10,10): translate must land it on (x,y)
  assert.deepStrictEqual(groups[0].layers[0].moved,[100-10,200-10]);
  assert.deepStrictEqual(groups[0].layers[1].moved,[300-10,50-10]);
}
// Failure midway: the partial group is removed and 0 tells the caller to use the single overlay.
{
  const {ctx,doc,groups}=makeEnv('b.png');const MTA=load(ctx);
  const made=MTA.addRegionOverlays(doc,[{id:'B001',file:'a.png',x:1,y:1},{id:'B002',file:'b.png',x:2,y:2}],{});
  assert.strictEqual(made,0);
  assert.strictEqual(groups[0].removed,true);
}
console.log('Per-bubble clean layers PASS');
// Review: find one bubble's text and clean layers in nested groups, without confusing similar ids.
{
  const {ctx}=makeEnv();const MTA=load(ctx);
  const L=(name)=>({typename:'ArtLayer',name});
  const G=(name,layers)=>({typename:'LayerSet',name,layers});
  const doc={layers:[
    L('Background'),
    G('CLEAN — từng bubble',[L('CLEAN B001'),L('CLEAN AI — CẦN DUYỆT B007'),L('CLEAN B0070')]),
    G('TYPESET — Tiếng Việt',[L('[THOẠI] B001 | Xin chào'),L('[AI PHỤC HỒI NỀN — CẦN DUYỆT] [THOẠI] B007 | Thầy ơi'),L('[THOẠI] B0070 | khác'),G('Con',[L('[HÉT] B012 | Trời ơi')])])]};
  let r=MTA.findRegionLayers(doc,'B007');
  assert.strictEqual(r.text.name,'[AI PHỤC HỒI NỀN — CẦN DUYỆT] [THOẠI] B007 | Thầy ơi');
  assert.strictEqual(r.clean.name,'CLEAN AI — CẦN DUYỆT B007');
  r=MTA.findRegionLayers(doc,'B012');assert.strictEqual(r.text.name,'[HÉT] B012 | Trời ơi');assert.strictEqual(r.clean,null);
  r=MTA.findRegionLayers(doc,'B999');assert.deepStrictEqual([r.text,r.clean],[null,null]);
  console.log('Review layer lookup PASS');
}

// Photoshop PDF: layered (editable) or flattened, and Photoshop's Auto leading with a safe fallback.
{
  const ctx={};vm.createContext(ctx);
  ctx.PDFSaveOptions=function(){};ctx.PDFEncoding={JPEGHIGH:'JPEGHIGH'};ctx.UnitValue=(v,u)=>({v,u});
  vm.runInContext(fs.readFileSync('scripts/core.jsxinc','utf8'),ctx);
  const layered=ctx.MTA.pdfSaveOptions({pdfLayers:true});
  assert.strictEqual(layered.preserveEditing,true);assert.strictEqual(layered.layers,true);
  assert.strictEqual(layered.encoding,'JPEGHIGH');assert.strictEqual(layered.jpegQuality,10);assert.strictEqual(layered.embedColorProfile,true);
  const flat=ctx.MTA.pdfSaveOptions({});
  assert.strictEqual(flat.preserveEditing,false);assert.strictEqual(flat.layers,false);
  // Auto leading: set as a percentage and read back; the planner then uses that ratio.
  const t1={};const a=ctx.MTA.configureLeading(t1,{autoLeading:true,leading:1.05});
  assert.deepStrictEqual([a.auto,a.ratio],[true,1.05]);assert.strictEqual(t1.useAutoLeading,true);assert.strictEqual(t1.autoLeadingAmount,105);
  // A Photoshop that ignores the percentage (reads back 120) falls back to explicit leading so the layout stays true.
  const t2={set autoLeadingAmount(v){this._v=120;},get autoLeadingAmount(){return this._v;}};
  const b=ctx.MTA.configureLeading(t2,{autoLeading:true,leading:1.05});
  assert.deepStrictEqual([b.auto,b.ratio],[false,1.05]);assert.strictEqual(t2.useAutoLeading,false);
  // The property missing altogether (throws): same fallback.
  const t3={set autoLeadingAmount(v){throw new Error('no such property');}};
  assert.strictEqual(ctx.MTA.configureLeading(t3,{autoLeading:true,leading:1.05}).auto,false);
  // Manual mode never touches Auto leading.
  const t4={};assert.deepStrictEqual(Object.assign({},ctx.MTA.configureLeading(t4,{autoLeading:false,leading:1.2})),{auto:false,ratio:1.2});
  assert.ok(!('useAutoLeading' in t4));
  console.log('Photoshop PDF options and Auto leading PASS');
}
