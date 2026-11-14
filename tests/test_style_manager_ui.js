const fs=require('fs'),vm=require('vm'),assert=require('assert');
function scenario(action){
    const controls=[],saved=[],alerts=[];let ctx;
    function control(type,text){
        let selection=null;
        const c={type,text:typeof text==='string'?text:'',items:[],children:[],preferredSize:{},value:false,
            add(type,_,text){if(type==='item'){const item={text:_,index:this.items.length};this.items.push(item);return item;}const child=control(type,text);this.children.push(child);return child;},
            removeAll(){this.items=[];selection=null;},close(){},show(){action({find,controls,ctx,saved,alerts});}};
        Object.defineProperty(c,'selection',{get(){return selection;},set(value){selection=typeof value==='number'?this.items[value]||null:value;}});
        if(Array.isArray(text))for(const label of text)c.add('item',label);
        controls.push(c);return c;
    }
    function find(type,prefix){const c=controls.find(c=>c.type===type&&(!prefix||c.text.startsWith(prefix)));assert(c,`Missing ${type}: ${prefix}`);return c;}
    ctx=vm.createContext({Window:function(type,title){return control(type,title);},alert:s=>alerts.push(s),
        File:{openDialog:()=>({length:100,fsName:'import.json'}),saveDialog:()=>null},MTA:{read:()=>JSON.stringify({exportedStyles:[{name:'Imported',prefixes:['REG:'],textProps:{typeUnit:'pixelsUnit',layerText:{textStyleRange:[{textStyle:{fontPostScriptName:'MissingComic',size:22}}]}}}]})}});
    for(const file of ['scripts/json.jsxinc','scripts/lettering_styles.jsxinc','scripts/style_manager.jsxinc'])vm.runInContext(fs.readFileSync(file,'utf8'),ctx);
    ctx.save=p=>saved.push(JSON.parse(JSON.stringify(p)));
    vm.runInContext(`var serial=0;var initial=MTAStyles.defaults('Truyện A','seriesA',{fonts:{dialogue:'Arial',box:'Arial',shout:'Arial'},standardSize:18});
       var result=MTAStyleUI.edit(initial,{fontNames:['Arial'],fontIds:['Arial'],unique:function(){return ++serial;},save:save});`,ctx);
    return {saved,alerts,initial:JSON.parse(vm.runInContext('MJSON.stringify(initial)',ctx))};
}
scenario(({find,saved})=>{find('edittext','Thoại thường').text='Unsaved';assert.strictEqual(saved.length,0);});
let outcome=scenario(({find,controls,saved,alerts})=>{
    find('button','Nhập JSON').onClick();assert.strictEqual(saved.length,0,'Import only stages changes until Save');
    assert(alerts[0].includes('MissingComic'),'Missing fonts must be shown');
    const dropdowns=controls.filter(c=>c.type==='dropdownlist');
    const dialogue=dropdowns.find(c=>c.items[0]&&c.items[0].text==='Theo cấu hình');
    dialogue.selection=4; // Newly imported fourth style.
    find('button','Lưu bộ style').onClick();
});
assert.strictEqual(outcome.saved.length,1);assert.strictEqual(outcome.saved[0].styles.length,4);
assert.strictEqual(outcome.saved[0].roles.dialogue,outcome.saved[0].styles[3].id);
assert.strictEqual(outcome.initial.styles.length,3,'Editor cannot mutate its input profile');
outcome=scenario(({find,saved})=>{
    const size=find('edittext','18');size.text='-4';find('button','Lưu bộ style').onClick();
    assert.strictEqual(saved.length,0,'Invalid style cannot be persisted');
    size.text='24';find('button','Lưu bộ style').onClick();
});
assert.strictEqual(outcome.saved[0].styles[0].size,24);
console.log('Style manager UI: staged import, missing font notice, role assignment, validation, save and cancel isolation PASS');
