// Exercise the production review callbacks with a small ScriptUI double.
// This does not replace the native Photoshop dialog/PSD smoke test.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const core = fs.readFileSync('scripts/core.jsxinc', 'utf8');
const source = fs.readFileSync('Photoshop_Typeset.jsx', 'utf8');
const reviewSource = source.slice(source.indexOf('        function review('), source.indexOf('        function prepareClean('));

function runReview(engineId, scenario) {
    const controls = [], calls = [], files = {};
    let dialog, accepted = false, context;
    function File(path) { this.fsName = path; this.exists = !path.includes('/masks/'); }
    function control(type, text) {
        const c = {type, text: typeof text === 'string' ? text : '', children: [], items: [],
            value: false, enabled: true, preferredSize: {}, size: [200, 200], image: {size: [200, 200]}, layout: {layout() {}},
            add(type, _, text) { const child = control(type, text); this.children.push(child); return child; },
            removeAll() { this.items = []; this.selection = null; },
            addEventListener(event, fn) { this[event] = fn; }, update() {},
            close(value) { accepted = value === 1; },
            show() { scenario({find, list: find('listbox'), picture: find('image'), calls, context}); return accepted ? 1 : 0; }
        };
        let selection = null;
        Object.defineProperty(c, 'selection', {
            get() { return selection; },
            set(v) { selection = typeof v === 'number' ? {index: v} : v; }
        });
        if (type === 'dropdownlist') c.add = function (_, value) {
            const item = {text: value, index: this.items.length}; this.items.push(item); return item;
        };
        if (type === 'listbox') c.add = function (_, value) {
            const item = {text: value, index: this.items.length}; this.items.push(item); return item;
        };
        controls.push(c); return c;
    }
    function find(type, prefix) {
        const found = controls.find(c => c.type === type && (!prefix || c.text.startsWith(prefix)));
        assert(found, `Missing ${type}: ${prefix}`); return found;
    }
    context = vm.createContext({File, console, assert,
        Window: function (_, title) { dialog = control('dialog', title); return dialog; },
        ScriptUI: {newImage() { return {size: [200, 200]}; }},
        translation: {text: ''}, autoRoles: {value: false}, alreadyClean:{value:false}, cancelled: false,
        featureReady() { return true; },
        selectedEngine() { return {id: engineId, version: 'test'}; },
        alert(message) { throw Error(message); },
        rpc(payload) {
            calls.push(payload);
            if (payload.operation === 'preview') return {preview: '/page/preview.png'};
            return {preview: '/page/clean.png', experimental: engineId !== 'baseline', blocked: {}, applied: ['B001']};
        }
    });
    vm.runInContext(fs.readFileSync('scripts/json.jsxinc', 'utf8') + '\n' + core, context);
    context.MTA.read = file => files[file.fsName];
    context.MTA.write = (file, text) => { files[file.fsName] = text; };
    vm.runInContext(reviewSource + `
        var data={schema:1,width:200,height:200,regions:[
            {id:'B001',box:[0,0,100,100],safe:[10,10,80,80],source:'ああ',warnings:['Baseline warning'],auto_clean:false},
            {id:'B002',box:[100,0,100,100],safe:[110,10,80,80],source:'はい',warnings:[],auto_clean:true}
        ],mapping:[{id:'B001',translation:'',clean:true,force:true},{id:'B002',translation:'',clean:true,force:true}]};
        var s={doc:{name:'sample.png'},folder:{fsName:'/page'},manifestPath:'/page/manifest.json',data:data,engine:{id:${JSON.stringify(engineId)},version:'test'},offline:false};
    `, context);
    files['/page/manifest.json'] = vm.runInContext('MJSON.stringify(data)', context);
    vm.runInContext('review(s, [], true)', context);
    return {mapping: JSON.parse(vm.runInContext('MJSON.stringify(s.mapping)', context)), calls};
}

let result = runReview('1107', ({find, list, picture, context}) => {
    const clean = find('checkbox', 'Clean vùng này');
    assert.strictEqual(clean.value, true, 'Baseline rejection must not uncheck 1107');
    assert.strictEqual(clean.enabled, true, 'Missing baseline mask must not lock 1107 opt-out');
    assert(list.items[0].text.includes('Engine 1107'), 'Do not claim baseline eligibility for 1107');
    clean.value = false;
    // The ScriptUI double deliberately does not emit onChange for a programmatic
    // list selection; clicking the preview must still commit the old region.
    picture.mousedown({clientX: 150, clientY: 50});
    assert.strictEqual(list.selection.index, 1);
    list.selection = 0; list.onChange();
    assert.strictEqual(clean.value, false, 'Image navigation lost explicit opt-out');
    find('checkbox', 'Tôi đã kiểm tra').value = true;
    find('button', 'Áp dụng').onClick();
});
assert.strictEqual(result.mapping[0].clean, false);
assert(result.mapping.every(m => m.force === false), 'Imported legacy force must be stripped for every region');

result = runReview('1107', ({find, calls}) => {
    find('button', 'Xem thử clean vùng đang chọn').onClick();
    const request = calls.find(c => c.operation === 'run_engine');
    assert.strictEqual(request.engine_id, '1107');
    assert.strictEqual(request.mapping[0].force, false);
    assert.strictEqual(request.preview, true);
    find('checkbox', 'Tôi đã kiểm tra').value = true;
    find('button', 'Áp dụng').onClick();
});
assert(result.mapping.every(m => m.clean && !m.force));

runReview('baseline', ({find, list}) => {
    assert.strictEqual(find('checkbox', 'Clean vùng này').enabled, false, 'Keep baseline missing-mask gate');
    assert(list.items[0].text.includes('CLEAN THỦ CÔNG'));
    find('checkbox', 'Tôi đã kiểm tra').value = true;
    find('button', 'Áp dụng').onClick();
});

const ctx = vm.createContext({});
vm.runInContext(core, ctx);
const m = ctx.MTA;
assert(!m.cleanControlEnabled(true, true, false, '1107'));
assert(!m.cleanControlEnabled(true, false, true, '1107'));
assert(m.cleanControlEnabled(false, false, false, 'future-engine'));
assert.strictEqual(m.savedEngine(null, {engine:{id:'1107'}}, {}).id, '1107');
assert.strictEqual(m.savedEngine(null, null, {engine_selection:{id:'1107'}}).id, '1107');
assert.strictEqual(m.savedEngine(null, null, {}).id, 'baseline');
assert.strictEqual(m.savedEngine({engine:{id:'pinned'}}, {engine:{id:'1107'}}, {}).id, 'pinned');
const summary = m.cleanResultSummary({skipped:['B001','B002'], review_ids:['B001']});
assert(summary.includes('cần duyệt kết quả: B001') && summary.includes('chưa clean: B002'));
assert(!summary.includes('chưa clean: B001'));
assert(source.includes('detailChoice.onChange = function () { state = null; }'));
console.log('Engine review callbacks: selection, missing mask, opt-out, preview dispatch, legacy force, saved engine and review status PASS');
