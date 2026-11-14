// Native geometry is simulated here. A real Photoshop smoke test is still required.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx=vm.createContext({});
vm.runInContext(`
function UnitValue(n,u){return {value:n,unit:u,as:function(){return n;}};}
function SolidColor(){this.rgb={red:0,green:0,blue:0};}
var Direction={HORIZONTAL:1},TextCase={NORMAL:1},LayerKind={TEXT:1},TextType={POINTTEXT:1,PARAGRAPHTEXT:2},
 Justification={CENTER:1},AntiAlias={SHARP:1},ElementPlacement={INSIDE:1};
var app={preferences:{smartQuotes:true}};
var doc={resolution:72,width:UnitValue(200,'px'),height:UnitValue(180,'px'),layers:[],activeLayer:{name:'original'}};
doc.artLayers={add:function(){
 var layer={textItem:{contents:'',size:UnitValue(18,'pt'),position:[UnitValue(100,'px'),UnitValue(90,'px')]},visible:true,name:'',
  remove:function(){var i=doc.layers.indexOf(this);if(i>=0)doc.layers.splice(i,1);},move:function(){},
  translate:function(dx,dy){this.textItem.position[0]=UnitValue(this.textItem.position[0].value+dx.value,'px');this.textItem.position[1]=UnitValue(this.textItem.position[1].value+dy.value,'px');}};
 Object.defineProperty(layer,'bounds',{get:function(){
  var t=this.textItem,size=t.size.value,lines=t.contents.split('\\r'),width=0;
  for(var i=0;i<lines.length;i++)width=Math.max(width,lines[i].length*size*.5+Math.max(0,lines[i].length-1)*(t.tracking||0)*size/1000);
  var x=t.position[0].value,y=t.position[1].value,lead=t.leading?t.leading.value:size*1.3;
  return [UnitValue(x-width/2,'px'),UnitValue(y-size*.9,'px'),UnitValue(x+width/2,'px'),UnitValue(y+size*.2+(lines.length-1)*lead,'px')];
 }});doc.layers.push(layer);doc.activeLayer=layer;return layer;
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
assert(vm.runInContext('doc.activeLayer===original',ctx),'Restore active layer after suggestions');
vm.runInContext(`options.lineCount=proposals[1].lines;var placed=MTA.addText(doc,doc,region,proposals[1].text,options);`,ctx);
assert.strictEqual(get('placed.textItem.contents').replace(/\r/g,'\n'),proposals[1].text,'Final placement retains chosen breaks');
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
assert.throws(()=>vm.runInContext(`MTA.suggestLayouts(doc,{id:'B002',safe:[0,0,1,1]},'Không vừa',options)`,ctx),/không vừa/);
assert.strictEqual(get('doc.layers.length'),count,'Failed suggestion must clean up its probe');
console.log('Review lettering: native probe cleanup, unique proposals, content preservation, final application and styled measurements PASS (mocked Photoshop)');
