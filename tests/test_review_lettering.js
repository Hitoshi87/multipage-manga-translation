// Native geometry is simulated here. A real Photoshop smoke test is still required.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx=vm.createContext({});
vm.runInContext(`
function UnitValue(n,u){return {value:n,unit:u,as:function(){return n;}};}
function SolidColor(){this.rgb={red:0,green:0,blue:0};}
var Direction={HORIZONTAL:1},TextCase={NORMAL:1},LayerKind={TEXT:1},TextType={POINTTEXT:1,PARAGRAPHTEXT:2},
 Justification={CENTER:1},AntiAlias={SHARP:1},ElementPlacement={INSIDE:1};
var app={preferences:{smartQuotes:true}};
var rejectedLine=null,rejectAll=false,probeLayersCreated=0;
var doc={resolution:72,width:UnitValue(200,'px'),height:UnitValue(180,'px'),layers:[],activeLayer:{name:'original'}};
doc.artLayers={add:function(){
 probeLayersCreated++;
 var layer={textItem:{contents:'',size:UnitValue(18,'pt'),position:[UnitValue(100,'px'),UnitValue(90,'px')]},visible:true,opacity:100,parent:doc,typename:'ArtLayer',name:'',
  remove:function(){var i=doc.layers.indexOf(this);if(i>=0)doc.layers.splice(i,1);},move:function(){},
  translate:function(dx,dy){this.textItem.position[0]=UnitValue(this.textItem.position[0].value+dx.value,'px');this.textItem.position[1]=UnitValue(this.textItem.position[1].value+dy.value,'px');}};
 Object.defineProperty(layer,'bounds',{get:function(){
  var t=this.textItem,size=t.size.value,lines=t.contents.split('\\r'),width=0;
  for(var i=0;i<lines.length;i++)width=Math.max(width,lines[i].length*size*.5+Math.max(0,lines[i].length-1)*(t.tracking||0)*size/1000);
  if(size!==100&&(rejectAll||t.contents===rejectedLine))width+=10000;
  var x=t.position[0].value,y=t.position[1].value,lead=t.useAutoLeading?size*t.autoLeadingAmount/100:(t.leading?t.leading.value:size*1.3);
  return [UnitValue(x-width/2,'px'),UnitValue(y-size*.9,'px'),UnitValue(x+width/2,'px'),UnitValue(y+size*.2+(lines.length-1)*lead,'px')];
 }});Object.defineProperty(layer,'boundsNoEffects',{get:function(){return this.bounds;}});
 layer.duplicate=function(){var other=doc.artLayers.add();other.kind=this.kind;other.name=this.name;other.textItem=Object.assign({},this.textItem);other.visible=true;return other;};
 doc.layers.push(layer);doc.activeLayer=layer;return layer;
}};
`,ctx);
for(const file of ['scripts/json.jsxinc','scripts/lettering_styles.jsxinc','scripts/core.jsxinc'])vm.runInContext(fs.readFileSync(file,'utf8'),ctx);
vm.runInContext(`
var shape={box:[0,0,200,180],center:[100,90],rows:[]};for(var y=0;y<180;y++)shape.rows.push([y,0,200]);
var region={id:'B001',shape:shape,safe:shape.box};
var options={font:'Test',min:10,max:30,leading:1.3,autoLeading:false,sizePolicy:'adaptive',caseMode:'keep'};
var text='Cậu đang nói cái gì vậy hả tớ chẳng hiểu gì cả',original=doc.activeLayer;
var proposals=MTA.suggestLayouts(doc,region,text,options);
`,ctx);
const get=code=>JSON.parse(vm.runInContext('MJSON.stringify('+code+')',ctx));
const proposals=get('proposals');
assert(proposals.length>=2,'Offer different feasible line counts');
assert.strictEqual(new Set(proposals.map(p=>p.text)).size,proposals.length);
assert(proposals.every(p=>p.text.replace(/\n/g,' ')===get('text')));
assert.strictEqual(get('doc.layers.length'),0,'Suggestion probes must leave no text layers');
assert.strictEqual(get('probeLayersCreated'),1,'Rank proposals with one shared native probe layer');
assert(vm.runInContext('doc.activeLayer===original',ctx),'Restore active layer after suggestions');
assert(proposals.every((p,i)=>i===0||p.score>=proposals[i-1].score),'Proposals must be ranked best first');
vm.runInContext(`
options.autoLayout=true;
var automatic=MTA.addText(doc,doc,region,text,options),automaticInfo=MTA.lastLayout();
`,ctx);
assert.strictEqual(get('automatic.textItem.contents').replace(/\r/g,'\n'),proposals[0].text,'Automatic placement selects the top-ranked proposal without a click');
assert.strictEqual(get('automaticInfo.selection.method'),'ranked-v1');
assert.strictEqual(get('automaticInfo.sourceText'),get('text'),'Automatic ranking cannot rewrite the translation');
assert.strictEqual(get('automaticInfo.selection.score'),proposals[0].score);
vm.runInContext(`automatic.remove();rejectedLine=proposals[0].text.split('\\n')[0];
var alternative=MTA.addText(doc,doc,region,text,options),alternativeInfo=MTA.lastLayout();`,ctx);
assert(get('alternativeInfo.selection.attempts')>1,'Native rejection of the top proposal must try alternatives');
assert.notStrictEqual(get('alternative.textItem.contents').replace(/\r/g,'\n'),proposals[0].text);
vm.runInContext(`alternative.remove();rejectedLine=null;`,ctx);
vm.runInContext(`options.lineCount=proposals[1].lines;var placed=MTA.addText(doc,doc,region,proposals[1].text,options);`,ctx);
assert.strictEqual(get('placed.textItem.contents').replace(/\r/g,'\n'),proposals[1].text,'Final placement retains chosen breaks');
assert.strictEqual(get('MTA.lastLayout().selection.method'),'planner','Explicit manual proposal must override automatic ranking');
assert.strictEqual(get('placed.name').slice(0,7),'B001 | ','Keep the review region identifier');
assert.strictEqual(get('doc.layers.length'),1);
assert.strictEqual(get('app.preferences.smartQuotes'),true);
vm.runInContext(`options.uppercase=true;options.lineCount=0;var upperProposals=MTA.suggestLayouts(doc,region,text,options);`,ctx);
assert(get('upperProposals').length);
assert(get('upperProposals').every(p=>p.text.replace(/\n/g,' ')===get('text')),'Rendered uppercase must not rewrite the saved translation');
vm.runInContext(`
var profile=MTAStyles.defaults('A','A',{fonts:{dialogue:'Comic',box:'Comic',shout:'Comic'},standardSize:22});
profile.styles[0].color=[30,40,50];profile.styles[0].tracking=35;profile.styles[0].bold=true;
options.styleProfile=profile;options.fontRole='dialogue';options.styleScale=1;options.lineCount=0;
var styled=MTA.addText(doc,doc,region,'Chào bạn',options);
`,ctx);
assert.strictEqual(get('styled.textItem.font'),'Comic');assert.strictEqual(get('styled.textItem.tracking'),35);
assert.strictEqual(get('styled.textItem.fauxBold'),true);assert.deepStrictEqual(get('styled.textItem.color.rgb'),{red:30,green:40,blue:50});
assert.strictEqual(get('MTA.lastLayout().sourceText'),'Chào bạn','Metadata stores the source rather than rendered uppercase');
const count=get('doc.layers.length');
vm.runInContext(`options.sizePolicy='fixed';rejectAll=true;`,ctx);
assert.throws(()=>vm.runInContext(`MTA.addText(doc,doc,region,text,options)`,ctx),/không vừa cỡ cố định/);
assert.strictEqual(get('doc.layers.length'),count,'Reject all unsafe proposals without keeping a partial layer');
vm.runInContext(`rejectAll=false;`,ctx);
assert.throws(()=>vm.runInContext(`MTA.suggestLayouts(doc,{id:'B002',safe:[0,0,1,1]},'Không vừa',options)`,ctx),/không vừa/);
assert.strictEqual(get('doc.layers.length'),count,'Failed suggestion must clean up its probe');
vm.runInContext(`
var uniform=MTA.letteringSizeOptions({font:'Test',min:10,max:33,leading:1.3,autoLeading:true,sizePolicy:'uniform',standardSize:30,autoLayout:true,caseMode:'keep'},1);
var narrow={id:'B099',safe:[0,0,80,180]};
`,ctx);
assert.throws(()=>vm.runInContext("MTA.addText(doc,doc,narrow,'không?',uniform)",ctx),/không vừa/);
vm.runInContext("var rescued=MTA.addBubbleText(doc,doc,narrow,'không?',uniform),rescueInfo=MTA.lastLayout();",ctx);
assert(get('rescueInfo.size')<27 && get('rescueInfo.size')>=19.5,'Narrow balloon may use a bounded uniform-size exception');
assert.strictEqual(get('rescueInfo.sizeException.normalMin'),27);
const box=get('MTA.bounds(rescued)');assert(box[0]>=0&&box[2]<=80,'A narrow balloon cannot be widened over artwork');
assert.strictEqual(get('rescued.textItem.contents'),'không?','Keep the whole word and translation');
assert(get('rescueInfo.leading')<1.3,'Auto leading follows this sentence rather than an unconditional 130%');
vm.runInContext("rescued.remove();uniform.styleProfile=MTAStyles.defaults('Rescue','rescue',{fonts:{dialogue:'Test',box:'Test',shout:'Test'},standardSize:30});uniform.fontRole='dialogue';var styledRescue=MTA.addBubbleText(doc,doc,narrow,'không?',uniform);",ctx);
assert(get('MTA.lastLayout().sizeException'),'Imported/native style profiles must allow the same bounded uniform rescue');
vm.runInContext("styledRescue.remove();uniform.styleProfile=null;",ctx);
vm.runInContext("uniform.sizePolicy='fixed';uniform.min=30;uniform.max=30;",ctx);
assert.throws(()=>vm.runInContext("MTA.addBubbleText(doc,doc,narrow,'không?',uniform)",ctx),/cỡ cố định/);
// Photoshop may make a duplicated hidden text layer visible. Repair must explicitly restore visibility.
vm.runInContext(fs.readFileSync('scripts/repair.jsxinc','utf8'),ctx);
vm.runInContext(`
var hidden=MTA.addText(doc,doc,region,'Câu chưa clean',{font:'Test',min:12,max:18,leading:1.3,autoLeading:false});
hidden.visible=false;hidden.opacity=75;
var repaired=MTARepair.repairDocument(doc,{width:200,height:180,regions:[region]},null,{sizing:{sizePolicy:'uniform',standardSize:18}});
var kept=null;for(var i=0;i<doc.layers.length;i++)if(doc.layers[i].name===hidden.name)kept=doc.layers[i];
`,ctx);
assert.strictEqual(get('kept.visible'),false,'Repair cannot expose uncleaned hidden dialogue');
assert.strictEqual(get('kept.opacity'),75);
vm.runInContext(`
kept.name='[CẦN CLEAN — CHỮ ẨN] B001 | Câu chưa clean';kept.visible=true;
MTARepair.repairDocument(doc,{width:200,height:180,regions:[region]},null,{sizing:{sizePolicy:'uniform',standardSize:18}});
var protectedLayer=null;for(var i=0;i<doc.layers.length;i++)if(doc.layers[i].name.indexOf('[CẦN CLEAN — CHỮ ẨN]')===0)protectedLayer=doc.layers[i];
`,ctx);
assert.strictEqual(get('protectedLayer.visible'),false,'PDF import or text edits cannot reveal a layer explicitly marked as uncleaned and hidden');
console.log('Review lettering: native probe cleanup, unique proposals, content preservation, final application and styled measurements PASS (mocked Photoshop)');
