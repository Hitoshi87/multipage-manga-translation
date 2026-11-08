#target photoshop
#include "../scripts/json.jsxinc"
#include "../scripts/core.jsxinc"
(function () {
    var root = new File($.fileName).parent.parent;
    var report = {ok: false, checks: [], photoshop: app.version};
    var dir = MTA.mkdir(root.fsName + '/work/kiểm thử Photoshop có dấu ' + MTA.unique());
    var oldRuler = app.preferences.rulerUnits, oldType = app.preferences.typeUnits, oldDialogs = app.displayDialogs;
    var active = app.documents.length ? app.activeDocument : null;
    var source = null, doc = null, reopened = null;
    var preexisting = [];
    for (var openIndex = 0; openIndex < app.documents.length; openIndex++) preexisting.push(app.documents[openIndex]);
    try {
        app.preferences.rulerUnits = Units.PIXELS; app.preferences.typeUnits = TypeUnits.POINTS; app.displayDialogs = DialogModes.NO;
        var unicode = "Tiếng Việt: Đường dẫn có dấu — xin chào! ' $() ` \\ \"";
        if (MJSON.parse(MJSON.stringify({s: unicode})).s !== unicode) throw Error('JSON Unicode roundtrip');
        var rejects = ['{"x":1,}', '[1,]', '{"__proto__":{}}', 'alert(1)', 'NaN'];
        for (var j = 0; j < rejects.length; j++) {
            var rejected = false; try { MJSON.parse(rejects[j]); } catch (_) { rejected = true; }
            if (!rejected) throw Error('Unsafe JSON accepted');
        }
        report.checks.push('ES3 JSON Unicode and invalid-input rejection');
        var doctor = MTA.request(root, {operation: 'doctor'});
        if (!doctor.ready || doctor.unicode.indexOf('Tiếng Việt') !== 0) throw Error('Python bridge doctor failed');
        report.python = doctor;
        report.checks.push('Photoshop app.system -> .venv Python -> UTF-8 JSON');
        source = app.open(new File(root.fsName + '/demo_project/pages/001_page1/original.png'));
        var before = source.layers.length;
        var snapshot = MTA.snapshot(source, dir);
        var scan = MTA.request(root, {operation: 'scan', input: snapshot.fsName, out: dir.fsName, lang: 'eng', rtl: true});
        if (scan.regions.length !== 2) throw Error('Expected 2 sample bubbles, got ' + scan.regions.length);
        var mapping = [{id: scan.regions[0].id, translation: 'Xin chào!\nBạn có khỏe không?', clean: true},
                       {id: scan.regions[1].id, translation: 'Chào mừng bạn đến với thế giới truyện tranh!', clean: true}];
        var clean = MTA.request(root, {operation: 'clean', manifest: scan.manifest, mapping: mapping});
        if (clean.applied.length !== 2) throw Error('Sample bubbles not auto-cleanable: ' + MJSON.stringify(scan));
        report.checks.push('Actual OCR + OpenCV through Photoshop on sample');
        doc = source.duplicate('MTA Unicode smoke test');
        doc.resizeImage(undefined, undefined, 300, ResampleMethod.NONE);
        MTA.addOverlay(doc, clean.overlay);
        var group = doc.layerSets.add(); group.name = 'TYPESET — Tiếng Việt';
        for (var i = 0; i < mapping.length; i++) {
            var layer = MTA.addText(doc, group, scan.regions[i], mapping[i].translation,
                                    {font: 'ArialMT', min: 12, max: 38, leading: 1.15, uppercase:i===0});
            if (layer.kind !== LayerKind.TEXT) throw Error('Rasterized text');
            if (i===0 && (layer.textItem.contents.indexOf('XIN')<0 || mapping[i].translation.indexOf('Xin')<0))
                throw Error('Uppercase rendering changed source mapping or failed');
        }
        var saved = MTA.saveCopy(doc, dir, 'Trang tiếng Việt', {png: true, jpg: true});
        var second = MTA.saveCopy(doc, dir, 'Trang tiếng Việt', {});
        if (saved.fsName === second.fsName) throw Error('Overwrote output');
        report.psd = saved.fsName;
        doc.close(SaveOptions.DONOTSAVECHANGES); doc = null;
        reopened = app.open(saved);
        var textGroup = reopened.layerSets.getByName('TYPESET — Tiếng Việt');
        if (textGroup.artLayers.length !== 2) throw Error('Missing editable layers after reopen');
        for (i = 0; i < textGroup.artLayers.length; i++) {
            if (textGroup.artLayers[i].kind !== LayerKind.TEXT) throw Error('Text not editable after PSD reopen');
        }
        var longTextRejected = false, beforeLayers = textGroup.artLayers.length;
        try { MTA.addText(reopened, textGroup, {id: 'TOO_LONG', safe: [10, 10, 20, 20]},
                         'Đây là câu quá dài không thể nằm trong vùng rất nhỏ', {font: 'ArialMT', min: 14, max: 38, leading: 1.15}); }
        catch (_) { longTextRejected = true; }
        if (!longTextRejected || textGroup.artLayers.length !== beforeLayers) throw Error('Overflow must fail without a stray layer');
        report.checks.push('300 dpi fit and overflow refusal');
        report.checks.push('Optional uppercase rendered without modifying translation');
        report.checks.push('Editable Vietnamese text, rendered fit, PSD save/reopen, PNG/JPG, no overwrite');
        if (source.layers.length !== before) throw Error('Changed original document');
        report.checks.push('Original layer stack unchanged');
        report.ok = true;
    } catch (e) { report.error = e.message; report.line = e.line; }
    finally {
        if (reopened) reopened.close(SaveOptions.DONOTSAVECHANGES);
        if (doc) doc.close(SaveOptions.DONOTSAVECHANGES);
        var borrowed = false;
        for (var existingIndex = 0; existingIndex < preexisting.length; existingIndex++) if (source === preexisting[existingIndex]) borrowed = true;
        if (source && !borrowed) source.close(SaveOptions.DONOTSAVECHANGES);
        if (active) app.activeDocument = active;
        app.preferences.rulerUnits = oldRuler; app.preferences.typeUnits = oldType; app.displayDialogs = oldDialogs;
        MTA.write(new File(root.fsName + '/work/photoshop_smoke.json'), MJSON.stringify(report));
    }
    return MJSON.stringify(report);
})();
