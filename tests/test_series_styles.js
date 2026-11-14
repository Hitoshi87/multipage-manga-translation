const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx=vm.createContext({});
for(const file of ['scripts/json.jsxinc','scripts/lettering_styles.jsxinc','scripts/core.jsxinc'])vm.runInContext(fs.readFileSync(file,'utf8'),ctx);
const evaluate=code=>JSON.parse(vm.runInContext('MJSON.stringify('+code+')',ctx));
vm.runInContext(`
var typeR={name:'Series',exportedStyles:[{name:'Regular',prefixes:['REG:'],textProps:{typeUnit:'pointsUnit',layerText:{
 textStyleRange:[{textStyle:{fontPostScriptName:'Comic-Regular',size:18,leading:24,autoLeading:false,tracking:15,syntheticBold:true,color:{red:20,green:40,blue:60}}}],
 paragraphStyleRange:[{paragraphStyle:{autoLeadingPercentage:1.2}}]}},stroke:{enabled:true,size:2,color:{r:255,g:255,b:255}}}]};
var imported=MTAStyles.importTypeR(typeR,'fixture');
var profile=MTAStyles.profile({id:'series1',name:'Truyện A',styles:imported.styles,roles:{dialogue:imported.styles[0].id}});
`,ctx);
let imported=evaluate('imported');
assert.strictEqual(imported.styles[0].font,'Comic-Regular');
assert.strictEqual(imported.styles[0].unit,'pt');
assert.strictEqual(imported.styles[0].leading,24/18);
assert.deepStrictEqual(imported.styles[0].color,[20,40,60]);
assert.deepStrictEqual(imported.styles[0].stroke,{size:2,color:[255,255,255]});
assert(imported.warnings.length,'Partial TypeR support must be disclosed');
vm.runInContext(`var settings={styleProfile:profile,fontRole:'dialogue',sizePolicy:'fixed',styleScale:3,min:10,max:32};`,ctx);
let prepared=evaluate("MTAStyles.prepare(settings,null,'REG: Xin chào',300)");
assert.strictEqual(prepared.text,'Xin chào');
assert.strictEqual(prepared.options.min,75);assert.strictEqual(prepared.options.max,75);
assert.strictEqual(prepared.options.font,'Comic-Regular');
assert.strictEqual(prepared.options.fauxBold,true);
assert.strictEqual(evaluate('settings').min,10,'Applying a style cannot mutate global sizing');
assert.deepStrictEqual(evaluate("MTAStyles.missingFonts(profile,['Other'])"),['Comic-Regular']);
assert.deepStrictEqual(evaluate("MTAStyles.missingFonts(profile,['Comic-Regular'])"),[]);
assert.strictEqual(evaluate("MTAStyles.resolve(profile,'REG: Chào','dialogue',profile.styles[0].id)").text,'Chào');
assert.strictEqual(evaluate("MTAStyles.resolve(profile,'Tôi dùng REG: trong câu','dialogue')").text,'Tôi dùng REG: trong câu');
assert.throws(()=>vm.runInContext("MTAStyles.resolve(profile,'Chào','dialogue','missing')",ctx),/không còn/);
assert.throws(()=>vm.runInContext("MTAStyles.profile({id:'x',name:'X',styles:profile.styles,roles:{box:'missing'}})",ctx),/không tồn tại/);
assert.throws(()=>vm.runInContext("MTAStyles.library({schema:1,profiles:[profile,profile]})",ctx),/bị lặp/);
assert.throws(()=>vm.runInContext("MTAStyles.style({id:'x',name:'X',font:'Test',size:18,color:[-1,0,0]})",ctx),/RGB/);
assert.throws(()=>vm.runInContext("MTAStyles.importTypeR({styles:[{name:'broken',textProps:{}}]},'x')",ctx),/thiếu/);
assert.throws(()=>vm.runInContext("MTAStyles.importTypeR({styles:[]},'x')",ctx),/JSON/);
vm.runInContext(`
var px=MTAStyles.copy(typeR);px.exportedStyles[0].textProps.typeUnit='pixelsUnit';
px.exportedStyles[0].textProps.layerText.textStyleRange[0].textStyle.autoLeading=true;
var pxStyles=MTAStyles.importTypeR(px,'px');
var pxProfile=MTAStyles.profile({id:'b',name:'Truyện B',styles:pxStyles.styles,roles:{dialogue:pxStyles.styles[0].id}});
`,ctx);
assert.strictEqual(evaluate('pxStyles.styles[0]').leading,1.2,'Auto leading ignores stale explicit leading');
assert.strictEqual(evaluate("MTAStyles.prepare({styleProfile:pxProfile,styleScale:3,sizePolicy:'uniform'},null,'REG: Câu',300)").options.min,48.6);
assert.deepStrictEqual(evaluate('MTAStyles.importTypeR({schema:1,id:profile.id,name:profile.name,roles:profile.roles,styles:profile.styles},"native").styles'),evaluate('profile.styles'));
assert.strictEqual(evaluate("MTAStyles.resolve(pxProfile,'REG: Câu','dialogue')").style.unit,'px','Profiles must remain isolated');
vm.runInContext(`
var shape={box:[0,0,200,180],center:[100,90],rows:[]};for(var y=0;y<180;y++)shape.rows.push([y,0,200]);
var phrase='Cậu đang nói cái gì vậy hả tớ chẳng hiểu gì cả';
var two=MTA.planLayout(shape,[phrase],function(s){return s.length*.5;},1.15,{min:10,max:30,leading:1.3,lineCount:2});
var three=MTA.planLayout(shape,[phrase],function(s){return s.length*.5;},1.15,{min:10,max:30,leading:1.3,lineCount:3});
var locked=MTA.planLayout(shape,three.lines,function(s){return s.length*.5;},1.15,{min:10,max:30,leading:1.3,lineCount:3});
`,ctx);
assert.strictEqual(evaluate('two').lines.length,2);assert.strictEqual(evaluate('three').lines.length,3);
assert.deepStrictEqual(evaluate('locked').lines,evaluate('three').lines,'Applying a proposal must preserve its breaks');
assert.strictEqual(evaluate('three').lines.join(' '),evaluate('phrase'),'Vietnamese content is preserved without adding hyphens');
console.log('Series styles: TypeR/native import, validation, fonts, units, roles, profile isolation and locked line breaks PASS');
