// Exercise the real runner's startup with ExtendScript File.exists as a boolean.
// This verifies input handling, not Photoshop rendering or image quality.
const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const code = fs.readFileSync('tests/photoshop_engine_smoke.jsx', 'utf8').replace(/^#.*$/gm, '');
new vm.Script(code);
function startup(exists, configText) {
    const messages = [];
    function File(path) {
        this.fsName = path;
        this.exists = exists;
        this.parent = {parent: {fsName: '/project'}};
    }
    function Folder() {
        this.getFiles = () => [];
    }
    const context = {
        File, Folder, MJSON: JSON,
        $: {fileName: '/project/tests/photoshop_engine_smoke.jsx', global: {alert: s => messages.push(s)}},
        MTA: {read: () => configText},
        // app is deliberately absent: validation must stop before app access.
    };
    vm.runInNewContext(code, context);
    return messages;
}
assert.match(startup(false, '')[0], /config.json/);
assert.match(startup(true, '{broken')[0], /không hợp lệ/);
assert.match(startup(true, '{}')[0], /Không có ảnh nguồn/);
console.log('Native smoke startup: syntax, File.exists, missing/invalid config, empty input PASS (mocked)');
