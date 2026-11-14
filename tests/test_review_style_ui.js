const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('Photoshop_Typeset.jsx','utf8');
const review=source.slice(source.indexOf('        function openReview('),source.indexOf('        function currentLines('));
function run(action){
    const controls=[],applied=[],suggested=[];
    function control(type,text){let selection=null;const c={type,text:typeof text==='string'?text:'',items:[],preferredSize:{},
        add(type,_,text){if(type==='item'){const item={text:_,index:this.items.length};this.items.push(item);return item;}return control(type,text);},
        removeAll(){this.items=[];selection=null;},show(){action({find,controls,applied,suggested});}};
        Object.defineProperty(c,'selection',{get(){return selection;},set(value){selection=typeof value==='number'?this.items[value]:value;}});
        if(Array.isArray(text))text.forEach(t=>c.add('item',t));controls.push(c);return c;
    }
    const find=(type,prefix)=>{const c=controls.find(c=>c.type===type&&(!prefix||c.text.startsWith(prefix)));assert(c,`Missing ${type}: ${prefix}`);return c;};
    const ctx=vm.createContext({Window:function(type,text){return control(type,text);},
        File:function(path){this.fsName=path;this.exists=path.endsWith('.lettering.json');},outputFolder:{fsName:'/out'},reviewDoc:null,
        latestDraftLog:()=>({fsName:'/out/log.json'}),selectedStyleProfile:()=>{throw Error('Must not read another series profile');},
        rpc:()=>({run_id:'run1',items:[{key:'1',page:1,region:'B001',file:'/out/page.psd',vi:'Original',reasons:['overflow'],severity:'fix'}]}),
        reviewContext:(item,id)=>({at:{doc:{}},region:{id:item.region},options:{styleId:id}}),
        reviewRelayout:(...args)=>applied.push(args),
        MTA:{read:file=>file.fsName.endsWith('.lettering.json')?
            JSON.stringify({schema:1,options:{styleProfile:{id:'a',name:'Series A',styles:[{id:'regular',name:'Regular',font:'Comic',size:18}],roles:{dialogue:'regular'}}},regions:{$B001:{styleId:'regular',text:'Saved text'}}}):JSON.stringify({project:'/out/project.json',run_id:'run1'}),
            suggestLayouts:(doc,region,text,options)=>{suggested.push({text,styleId:options.styleId});return [{text:'Saved\ntext',size:18,lines:2},{text:'Saved text',size:17,lines:1}];}}});
    for(const file of ['scripts/json.jsxinc','scripts/lettering_styles.jsxinc'])vm.runInContext(fs.readFileSync(file,'utf8'),ctx);
    vm.runInContext(review+"\nopenReview('/out/project.json');",ctx);return {applied,suggested};
}
run(({find,controls,applied,suggested})=>{
    const text=find('edittext'),style=controls.find(c=>c.type==='dropdownlist'&&c.items[0]?.text==='Theo vai trò / tiền tố');
    assert.strictEqual(text.text,'Saved text');assert.strictEqual(style.selection.text,'Regular');
    find('button','Gợi ý xuống dòng').onClick();assert.strictEqual(applied.length,0,'Suggestions cannot apply edits');
    assert.deepStrictEqual(suggested,[{text:'Saved text',styleId:'regular'}]);
    const proposals=controls.find(c=>c.type==='dropdownlist'&&c.items[0]?.text.startsWith('2 dòng'));
    proposals.selection=0;proposals.onChange();assert.strictEqual(text.text,'Saved\ntext');
    find('button','Áp dụng lời sửa').onClick();
    assert.strictEqual(applied[0][1],'Saved\ntext');assert.strictEqual(applied[0][4],'regular');assert.strictEqual(applied[0][5],2);
});
run(({find,controls,applied})=>{
    find('button','Gợi ý xuống dòng').onClick();const proposals=controls.find(c=>c.type==='dropdownlist'&&c.items[0]?.text.startsWith('2 dòng'));
    proposals.selection=0;proposals.onChange();const text=find('edittext');text.text='Manual edit';text.onChanging();
    find('button','Áp dụng lời sửa').onClick();assert.strictEqual(applied[0][5],0,'Manual editing invalidates the chosen line count');
});
console.log('Review UI: page profile snapshot, remembered text/style, proposal preview, explicit apply and stale proposal invalidation PASS');
