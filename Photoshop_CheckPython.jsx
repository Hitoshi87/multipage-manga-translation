#target photoshop
#include "scripts/json.jsxinc"
#include "scripts/core.jsxinc"
(function () {
    var root = new File($.fileName).parent;
    try {
        var result = MTA.request(root, {operation: 'doctor'});
        MTA.mkdir(root.fsName + '/work');
        MTA.write(new File(root.fsName + '/work/environment.json'), MJSON.stringify(result));
        alert((result.ready ? 'SẴN SÀNG' : 'THIẾU DEPENDENCY') + '\nPhotoshop → Python: OK' +
              '\nPython: ' + result.python + ' — ' + result.cpu + '\n.venv: ' + result.venv +
              '\n' + result.unicode + '\nOCR còn thiếu: ' + result.missing_languages.join(', ') +
              '\nChi tiết: work/environment.json');
    } catch (e) { alert('Không gọi được Python: ' + e.message + '\nXem README_VI.md để chạy chế độ tiền xử lý độc lập.'); }
})();
