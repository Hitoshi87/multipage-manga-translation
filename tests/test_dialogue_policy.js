const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx=vm.createContext({});
for(const file of ['scripts/json.jsxinc','scripts/dialogue_policy.jsxinc'])vm.runInContext(fs.readFileSync(file,'utf8'),ctx);
const get=code=>JSON.parse(vm.runInContext('MJSON.stringify('+code+')',ctx));
vm.runInContext(`
var a=MTADialogue.entry({name:'Truyện A',address_policy:'A xưng tớ, gọi B là cậu.',style_prompt:'Giọng thân mật.',dialogue_review:true});
var b=MTADialogue.entry({name:'Truyện B',address_policy:'C xưng tôi, gọi D là ngài.',dialogue_review:false});
var bank=MTADialogue.library({schema:1,profiles:[a,b]});
`,ctx);
assert.strictEqual(get("MTADialogue.find(bank,'  TRUYỆN A  ')").address_policy,'A xưng tớ, gọi B là cậu.');
assert.strictEqual(get("MTADialogue.find(bank,'Truyện mới')"),null,'Never carry another book\'s policy into a new series');
assert.strictEqual(get('MTADialogue.merge({},false,a)').dialogue_review,true);
assert.strictEqual(get('MTADialogue.merge({},false,null)').dialogue_review,true,'Automatic new projects enable the explicitly advertised review');
assert.strictEqual(get("MTADialogue.merge({address_policy:'Frozen',dialogue_review:false},true,a)").address_policy,'Frozen');
assert.strictEqual(get("MTADialogue.merge({address_policy:'Frozen',dialogue_review:false},true,a)").dialogue_review,false,'Resume must not gain an extra paid API pass');
assert.throws(()=>vm.runInContext('MTADialogue.library({schema:1,profiles:[a,a]})',ctx),/bị lặp/);
assert.throws(()=>vm.runInContext("MTADialogue.entry({name:'X',dialogue_review:'false'})",ctx),/bật hoặc tắt/);
assert.throws(()=>vm.runInContext("MTADialogue.entry({name:'X',address_policy:Array(6002).join('a')})",ctx),/6000/);
assert(!('base_url' in get("MTADialogue.entry({name:'X',base_url:'private',api_key:'secret'})")),'Policy bank is not a credential store');

// Exercise the actual automatic profile builder: new volume vs frozen run.
const source=fs.readFileSync('Photoshop_Typeset.jsx','utf8');
ctx.rpc=()=>({profiles:[],runs:[]});ctx.dialogueSeriesName=()=> 'Truyện A';ctx.dialogueLoadError='';
ctx.easyHost={text:'https://example.test/v1'};ctx.easyModelName={text:'mock'};ctx.EASY_KEY_ENV='TEST_KEY';
vm.runInContext('var dialogueLibrary=bank;',ctx);
vm.runInContext(source.slice(source.indexOf('        function easyProfile('),source.indexOf('        // Resuming must keep',source.indexOf('        function easyProfile('))),ctx);
assert.strictEqual(get("easyProfile('/new/project.json',0)").address_policy,'A xưng tớ, gọi B là cậu.');
assert.strictEqual(get("easyProfile('/new/project.json',0)").dialogue_review,true);
ctx.rpc=()=>({profiles:[{values:{address_policy:'Old rules',dialogue_review:false}}],runs:[{id:'existing'}]});
assert.strictEqual(get("easyProfile('/existing/project.json',0)").address_policy,'Old rules');
assert.strictEqual(get("easyProfile('/existing/project.json',0)").dialogue_review,false);

// Editing is staged until Save; Cancel never mutates the original entry.
function editor(saveIt){
    const controls=[],saved=[];
    function control(type,text){const c={type,text:typeof text==='string'?text:'',value:false,preferredSize:{},
        add(type,_,text){return control(type,text);},close(){},show(){
            const fields=controls.filter(c=>c.type==='edittext');fields[3].text='A xưng mình, gọi B là cậu.';
            controls.find(c=>c.type==='checkbox').value=false;
            if(saveIt)controls.find(c=>c.type==='button'&&c.text==='Lưu').onClick();
        }};controls.push(c);return c;}
    ctx.Window=function(type,title){return control(type,title);};ctx.savePolicy=p=>saved.push(JSON.parse(JSON.stringify(p)));
    vm.runInContext('MTADialogue.edit(a,savePolicy)',ctx);return saved;
}
assert.strictEqual(editor(false).length,0);
const saved=editor(true)[0];assert.strictEqual(saved.address_policy,'A xưng mình, gọi B là cậu.');assert.strictEqual(saved.dialogue_review,false);
assert.strictEqual(get('a').address_policy,'A xưng tớ, gọi B là cậu.');
console.log('Dialogue policy: series isolation, explicit review cost setting, new volume reuse, frozen resume, validation and editor save/cancel PASS');
