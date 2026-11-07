const fs = require('fs');
const vm = require('vm');
const assert = require('assert');

let windowInstance;
let returnValue = 1;
function control(type, text, options) {
    return {type, text, options, children: [], add(type, _, text, options) {
        const child = control(type, text, options);
        this.children.push(child);
        return child;
    }};
}
function Window(type, title) {
    windowInstance = control(type, title);
    windowInstance.center = function () {};
    windowInstance.show = function () { return returnValue; };
    return windowInstance;
}
const context = {Window};
vm.runInNewContext(fs.readFileSync('scripts/core.jsxinc', 'utf8'), context);
const rows = Array.from({length: 300}, (_, i) => `${i + 1}. Trang ${i + 1}`);
assert.strictEqual(context.MTA.confirmChapter(rows, 'AI local', 'Kiểm tra từng trang.'), true);
const list = windowInstance.children.find(c => c.type === 'listbox');
assert.strictEqual(list.text.length, 300);
assert.deepStrictEqual(Array.from(list.preferredSize), [560, 280]);
const buttons = windowInstance.children.find(c => c.type === 'group').children;
assert.deepStrictEqual(buttons.map(c => c.options.name), ['cancel', 'ok']);
returnValue = 2;
assert.strictEqual(context.MTA.confirmChapter(rows, 'AI local', 'Kiểm tra từng trang.'), false);
console.log('Chapter dialog: 300 rows, bounded list, confirm and cancel OK');
