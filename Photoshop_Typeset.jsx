#target photoshop
#include "scripts/json.jsxinc"
#include "scripts/core.jsxinc"
/* Manga Typesetter — UI 1107-ui.4. File > Scripts > Browse. UTF-8. */
(function () {
    var root = new File($.fileName).parent;
    var oldRuler = app.preferences.rulerUnits, oldType = app.preferences.typeUnits;
    var oldDialogs = app.displayDialogs;
    var initial = app.documents.length ? app.activeDocument : null;
    var busy = false, cancelled = false, state = null, inputFolder = null;
    var docs = [], docNames = [], i, pendingPages = [], pendingLog = null;
    var outputFolder = new Folder(root.fsName + '/output');
    for (i = 0; i < app.documents.length; i++) { docs.push(app.documents[i]); docNames.push(app.documents[i].name); }
    try {
        app.preferences.rulerUnits = Units.PIXELS;
        app.preferences.typeUnits = TypeUnits.POINTS;
        app.displayDialogs = DialogModes.NO;
        var win = new Window('dialog', 'Manga Typesetter — ' + MTA.uiVersion);
        win.orientation = 'column'; win.alignChildren = 'fill';
        var tabs=win.add('tabbedpanel');tabs.alignChildren='fill';tabs.preferredSize=[780,570];
        function addTab(title){var tab=tabs.add('tab',undefined,title);tab.orientation='column';tab.alignChildren='fill';return tab;}
        var sourceTab=addTab('1. Nguồn & nhận diện'),engineTab=addTab('2. Engine clean');
        var typesetTab=addTab('3. Typeset & xuất'),advancedTab=addTab('4. Thử nghiệm nâng cao');tabs.selection=sourceTab;
        var info = sourceTab.add('group'); info.add('statictext', undefined, 'Trang hiện tại:');
        var page = info.add('dropdownlist', undefined, docNames.length ? docNames : ['Chưa mở tài liệu']);
        page.preferredSize.width = 360; page.selection = 0;
        for (i = 0; i < docs.length; i++) if (docs[i] === initial) page.selection = i;
        var sourceRow = sourceTab.add('group');
        var chooseFolder = sourceRow.add('button', undefined, 'Chọn thư mục ảnh/PSD');
        var openSources = sourceRow.add('button', undefined, 'Dùng trang đang mở');
        var sourceInfo = sourceRow.add('statictext', undefined, docs.length + ' tài liệu đang mở'); sourceInfo.characters = 32;
        typesetTab.add('statictext', undefined, 'Bản dịch: mỗi câu một dòng; cả chương dùng [PAGE 1], [PAGE 2]…; \\n để ngắt dòng trong câu.');
        var translation = typesetTab.add('edittext', undefined, '', {multiline: true, scrolling: true});
        translation.preferredSize = [720, 125];
        var imports = typesetTab.add('group');
        var sourceTools=sourceTab.add('group');
        var openText = imports.add('button', undefined, 'Mở TXT/DOCX');
        var openTranslations = imports.add('button', undefined, 'Thư mục bản dịch');
        var importResult = sourceTools.add('button', undefined, 'Mở manifest / dữ liệu chờ duyệt');
        var check = sourceTools.add('button', undefined, 'Kiểm tra Python');
        var settings = sourceTab.add('group');
        var rtl = settings.add('checkbox', undefined, 'Đọc phải sang trái'); rtl.value = true;
        settings.add('statictext', undefined, 'OCR:');
        var lang = settings.add('dropdownlist', undefined, ['eng', 'jpn', 'jpn_vert', 'chi_sim', 'chi_tra', 'kor', 'vie']); lang.selection = null; lang.helpTip = "Bắt buộc chọn: Nhật dọc = jpn_vert, Nhật ngang = jpn, Anh = eng";
        var presetRow=typesetTab.add('group');presetRow.add('statictext',undefined,'Preset chữ:');
        var presets = presetRow.add('dropdownlist', undefined, ['Thoại thường', 'Lời dẫn nhỏ', 'Thoại lớn']); presets.selection = 0;
        var aiDetector = settings.add('checkbox', undefined, 'AI bong bóng + chữ truyện');
        aiDetector.value = new File(root.fsName+'/models/balloon.onnx').exists;
        if(aiDetector.value)lang.selection=lang.find('jpn_vert');
        aiDetector.helpTip = 'Chọn detector cho bước scan. Engine 1107 còn chạy CTD/text/head riêng; tắt ô này không tắt inference của engine.';
        advancedTab.add('statictext',undefined,'Công cụ thử model riêng; không cấu hình engine clean. Chỉ dùng với Baseline.');
        var previewModels = advancedTab.add('group'); previewModels.add('statictext', undefined, 'Thử mask:');
        var maskChoice = previewModels.add('dropdownlist', undefined, ['CTD nâng cấp', 'Comic Text Mask', 'Koharu Layout 1152', 'CTD + Koharu']); maskChoice.selection = 0;
        var useLama = previewModels.add('dropdownlist', undefined, ['LaMa cục bộ', 'AOT Koharu', 'Tô nền trắng']); useLama.selection = 0;
        function inpaintMethod() { return ['lama','aot','white'][useLama.selection.index]; }
        var testModel = advancedTab.add('button', undefined, 'Thử model riêng — không phải preview engine');
        testModel.helpTip = 'Xem ảnh gốc, mask và kết quả thử; không thay đổi ảnh hoặc cài đặt clean cả chương.';
        var modelBatch = advancedTab.add('checkbox', undefined, 'Dùng mask + bộ phục hồi ở trên để clean cả chương (kiểm tra kết quả)');
        modelBatch.helpTip = 'Dùng mask toàn trang giống xem thử; có thể xóa nhầm tranh hoặc chữ ngoài thoại. Kết quả được đánh dấu cần kiểm tra.';
        var safetyOptions = advancedTab.add('group');
        var protectFaces = safetyOptions.add('checkbox', undefined, 'Bảo vệ đầu/mặt trong công cụ thử model'); protectFaces.value = true;
        protectFaces.helpTip = 'Không xóa trong vùng AI nhận ra là đầu/mặt; AI vẫn có thể bỏ sót mặt.';
        var layoutOptions=sourceTab.add('group');
        var koharuOrder = layoutOptions.add('checkbox', undefined, 'Sắp thứ tự theo panel Koharu'); koharuOrder.value = false;
        var magiOrder = layoutOptions.add('checkbox', undefined, 'Magi'); magiOrder.value = false; magiOrder.helpTip='Thử dùng Magi thay panel Koharu; nặng hơn.';
        var detectionRow = sourceTab.add('group'); detectionRow.add('statictext', undefined, 'Quét chữ:');
        var detailChoice = detectionRow.add('dropdownlist', undefined, ['Tiêu chuẩn', 'Kỹ — thêm ảnh phóng lớn', 'Kỹ + Koharu — thêm chữ ngoài bóng']); detailChoice.selection = 1;
        detailChoice.helpTip = 'Áp dụng khi scan bằng AI, gồm scan cho preview engine và cả chương. Không cấu hình công cụ thử model riêng.';
        var hwRow = sourceTab.add('group'); hwRow.add('statictext', undefined, 'Tăng tốc:');
        var hwChoice = hwRow.add('dropdownlist', undefined, ['Tự động (Auto)', 'CPU (Mát máy / Ổn định)', 'CoreML (Apple Silicon)', 'CUDA (NVIDIA GPU)']); hwChoice.selection = 0;
        hwChoice.helpTip = 'Chọn phần cứng chạy AI: Auto tự nhận diện; CPU chạy mát máy và tránh tràn RAM/leak bộ nhớ; CoreML cho Mac M-series; CUDA cho card NVIDIA.';
        var hwSettingsFile = new File(Folder.userData.fsName + '/MangaTypesetterLite/hardware_profile.json');
        if (hwSettingsFile.exists) {
            try {
                var savedHw = MJSON.parse(MTA.read(hwSettingsFile));
                if (savedHw && typeof savedHw.index === 'number' && savedHw.index >= 0 && savedHw.index < 4) hwChoice.selection = savedHw.index;
            } catch (_) {}
        }
        hwChoice.onChange = function () {
            try {
                MTA.mkdir(Folder.userData.fsName + '/MangaTypesetterLite');
                MTA.write(hwSettingsFile, MJSON.stringify({index: hwChoice.selection.index, value: ['auto', 'cpu', 'coreml', 'cuda'][hwChoice.selection.index]}));
            } catch (_) {}
            state = null;
        };
        var fontRow = typesetTab.add('group'); fontRow.add('statictext', undefined, 'Font thoại:');
        var fontNames = [], fontIds = [];
        for (i = 0; i < app.fonts.length; i++) { fontNames.push(app.fonts[i].name); fontIds.push(app.fonts[i].postScriptName); }
        var font = fontRow.add('dropdownlist', undefined, fontNames); font.preferredSize.width = 270;
        font.selection = 0;
        for (i = 0; i < fontIds.length; i++) if (fontIds[i] === 'ArialMT') font.selection = i;
        fontRow.add('statictext', undefined, 'Cỡ chuẩn:');
        var minSize = fontRow.add('edittext', undefined, '10'); minSize.characters = 4;
        minSize.helpTip='Quy ước trang 1008×1440; tự tăng theo ảnh lớn. Ảnh 3024×4320 dùng cỡ pixel gấp 3.';
        fontRow.add('statictext', undefined, 'đến');
        var maxSize = fontRow.add('edittext', undefined, '32'); maxSize.characters = 4;
        maxSize.helpTip=minSize.helpTip;
        fontRow.add('statictext', undefined, 'Giãn dòng:');
        var leading = fontRow.add('edittext', undefined, '1.15'); leading.characters = 4;
        var roleFontRow = typesetTab.add('group');
        roleFontRow.add('statictext', undefined, 'Font ô vuông:');
        var boxFont = roleFontRow.add('dropdownlist', undefined, fontNames); boxFont.preferredSize.width = 200; boxFont.selection = font.selection.index;
        roleFontRow.add('statictext', undefined, 'Font chữ hét:');
        var shoutFont = roleFontRow.add('dropdownlist', undefined, fontNames); shoutFont.preferredSize.width = 200; shoutFont.selection = font.selection.index;
        for (i = 0; i < fontIds.length; i++) {
            if (fontIds[i] === 'Arial-ItalicMT') boxFont.selection = i;
            if (fontIds[i] === 'Arial-BoldMT') shoutFont.selection = i;
        }
        var saveFonts = roleFontRow.add('button', undefined, 'Lưu font');
        var autoRoles = typesetTab.add('checkbox', undefined, 'Tự chọn font theo hình bong bóng (có thể sửa từng vùng)'); autoRoles.value = true;
        var fontSettingsFile = new File(Folder.userData.fsName + '/MangaTypesetterLite/font_profiles.json');
        function chooseFontById(control, id) {
            for (var n = 0; n < fontIds.length; n++) if (fontIds[n] === id) { control.selection = n; return true; }
            return false;
        }
        if (fontSettingsFile.exists) {
            try {
                var savedFonts = MJSON.parse(MTA.read(fontSettingsFile));
                chooseFontById(font, savedFonts.dialogue); chooseFontById(boxFont, savedFonts.box); chooseFontById(shoutFont, savedFonts.shout);
                if (typeof savedFonts.automatic === 'boolean') autoRoles.value = savedFonts.automatic;
            } catch (_) {}
        }
        var exportRow = typesetTab.add('group');
        var setOutput = exportRow.add('button', undefined, 'Thư mục lưu');
        var outInfo = exportRow.add('statictext', undefined, outputFolder.fsName); outInfo.characters = 42;
        var png = exportRow.add('checkbox', undefined, 'PNG'), jpg = exportRow.add('checkbox', undefined, 'JPG');
        var formatRow = typesetTab.add('group'); formatRow.add('statictext', undefined, 'Lưu file chỉnh sửa:');
        var savePsd = formatRow.add('checkbox', undefined, 'PSD'); savePsd.value = true;
        var savePdf = formatRow.add('checkbox', undefined, 'PDF (gọn, flatten)');
        savePdf.helpTip = 'PDF nén JPEG, không giữ layer — dung lượng gần lưu tay. Cần chỉnh sửa lại thì dùng PSD.';
        var pdfLayers = formatRow.add('checkbox', undefined, 'PDF giữ layer (rất nặng)');
        pdfLayers.helpTip = 'Nhúng toàn bộ PSD vào PDF nên file có thể lớn gấp nhiều lần. Chỉ bật khi thật sự cần.';
        var cmykOutput = typesetTab.add('checkbox', undefined, 'Xuất PSD/PDF/JPG CMYK theo Color Settings của Photoshop'); cmykOutput.value = true;
        cmykOutput.helpTip = 'Chọn profile CMYK phù hợp nhà in trong Photoshop Color Settings trước khi dùng. PNG xem trước vẫn xuất RGB.';
        var alreadyClean = engineTab.add('checkbox', undefined, 'Trang đã clean thủ công — chỉ tạo chữ, không thêm lớp clean tự động');
        var engineRow=engineTab.add('group');engineRow.add('statictext',undefined,'Engine clean:');
        var engineChoice=engineRow.add('dropdownlist',undefined,['Baseline']);engineChoice.selection=0;
        var engines=[{id:'baseline',version:'baseline-1',label:'Baseline',ready:true}],uiFeatures={};
        var reviewAll = engineTab.add('checkbox', undefined, 'Duyệt từng trang trước khi áp dụng (clean hoặc typeset)'); reviewAll.value = false;
        var batchCleanOnly=engineTab.add('checkbox',undefined,'Chỉ clean cả chương — không cần bản dịch, không typeset');
        var skipMismatch=engineTab.add('checkbox',undefined,'Chương: bỏ trang lệch số câu, lưu dữ liệu để duyệt sau'); skipMismatch.value=true;
        var previewEngine=engineTab.add('button',undefined,'Xem thử clean theo engine đang chọn');
        var engineNote=engineTab.add('statictext',undefined,'',{multiline:true});engineNote.preferredSize=[720,60];
        var advancedNote=advancedTab.add('statictext',undefined,'',{multiline:true});advancedNote.preferredSize=[720,55];
        var actions = win.add('group');
        var scan = actions.add('button', undefined, 'Nhận diện và xem trước');
        var clean = actions.add('button', undefined, 'Clean');
        var typeset = actions.add('button', undefined, 'Typeset trang hiện tại');
        var chapter = actions.add('button', undefined, 'Làm cả chương');
        var pendingButton = win.add('button', undefined, 'Trang chờ duyệt (0)'); pendingButton.enabled = false;
        var progress = win.add('progressbar', undefined, 0, 100); progress.preferredSize.height = 14;
        var status = win.add('statictext', undefined, 'Sẵn sàng. Bản gốc được giữ nguyên; kết quả nằm trong bản sao.'); status.characters = 90;
        var bottom = win.add('group'); bottom.alignment = 'right';
        var cancelButton = bottom.add('button', undefined, 'Hủy tác vụ');
        var close = bottom.add('button', undefined, 'Đóng');
        var controls = [chooseFolder, openSources, page, openText, openTranslations, aiDetector, maskChoice, useLama, detailChoice, hwChoice, previewEngine, testModel, modelBatch, protectFaces, koharuOrder, magiOrder, importResult, check, rtl, lang, presets, font, boxFont, shoutFont, autoRoles, saveFonts,
                        minSize, maxSize, leading, translation, setOutput, png, jpg, savePsd, savePdf, pdfLayers, cmykOutput, alreadyClean, engineChoice, reviewAll, batchCleanOnly, skipMismatch, scan, clean, typeset, chapter, pendingButton];
        function tick(message, fraction) {
            if (message) status.text = message;
            if (fraction !== undefined) progress.value = fraction;
            win.update();
            return !cancelled;
        }
        function run(fn) {
            if (busy) return;
            busy = true; cancelled = false;
            for (var k = 0; k < controls.length; k++) controls[k].enabled = false;
            close.enabled = false;
            try { fn(); }
            catch (e) { status.text = e.message; alert('Manga Typesetter AI\n' + e.message + (e.line ? '\nDòng: ' + e.line : '')); }
            finally {
                busy = false; syncInputs(); close.enabled = true; win.update();
            }
        }
        function rpc(payload) {
            payload.ui_version=MTA.uiVersion;
            if (typeof hwChoice !== 'undefined' && hwChoice && hwChoice.selection) {
                payload.accel = ['auto', 'cpu', 'coreml', 'cuda'][hwChoice.selection.index];
            }
            return MTA.request(root, payload, function () { return tick(); });
        }
        function currentEngineId(){var e=engineChoice.selection?engines[engineChoice.selection.index]:null;return e?e.id:'baseline';}
        function featureReady(name){return !!(uiFeatures[name] && uiFeatures[name].ready);}
        function modelExperimentReady(){
            var name=['ctd','mask','koharu','hybrid'][maskChoice.selection.index];
            return featureReady('mask_'+name) && featureReady('inpaint_'+inpaintMethod()) && (!protectFaces.value || featureReady('head_guard'));
        }
        function syncInputs(){
            for(var ci=0;ci<controls.length;ci++)controls[ci].enabled=!busy;
            if(busy)return;
            var p=MTA.inputPolicy(currentEngineId(),{alreadyClean:alreadyClean.value,cleanOnly:batchCleanOnly.value,modelBatch:modelBatch.value,reviewAll:reviewAll.value,aiDetector:aiDetector.value});
            var e=engineChoice.selection?engines[engineChoice.selection.index]:null;
            previewEngine.enabled=p.preview && !!(e && e.ready) && docs.length>0;
            clean.enabled=p.clean && docs.length>0;typeset.enabled=p.typeset && !modelBatch.value && docs.length>0;
            scan.enabled=docs.length>0;alreadyClean.enabled=!batchCleanOnly.value && !modelBatch.value;
            batchCleanOnly.enabled=!alreadyClean.value;reviewAll.enabled=p.review;skipMismatch.enabled=p.skipMismatch;
            detailChoice.enabled=p.detail;aiDetector.enabled=featureReady('scan_ai');
            koharuOrder.enabled=featureReady('koharu');magiOrder.enabled=featureReady('magi');
            maskChoice.enabled=p.legacyTools;useLama.enabled=p.legacyTools;
            protectFaces.enabled=p.legacyTools && featureReady('head_guard');
            testModel.enabled=p.legacyTools && modelExperimentReady() && docs.length>0;
            modelBatch.enabled=p.fullPage && modelExperimentReady();
            var textControls=[translation,openText,openTranslations,presets,font,boxFont,shoutFont,minSize,maxSize,leading,autoRoles,saveFonts];
            for(var ti=0;ti<textControls.length;ti++)textControls[ti].enabled=p.typeset;
            pendingButton.enabled=pendingPages.length>0;
            engineNote.text=alreadyClean.value?'Chỉ typeset ảnh đã clean; không gọi engine clean.':(modelBatch.value?'Đang dùng công cụ mask toàn trang riêng, không dùng clean từng region.':'Preview và clean dùng engine '+currentEngineId()+'. '+(currentEngineId()==='baseline'?'Baseline giữ các safety gate hiện tại.':'Engine tự kiểm tra mask/artwork; checkbox thử model bên tab 4 không thay đổi engine.'));
            advancedNote.text=currentEngineId()!=='baseline'?'Đã khóa công cụ legacy khi dùng '+currentEngineId()+'. Dùng preview ở tab Engine clean.':(modelExperimentReady()?'Công cụ riêng sẵn sàng. Kết quả cần kiểm tra; backend vẫn xác minh weights khi chạy.':'Thiếu model hoặc dependency cho tổ hợp đang chọn. Không tự tải thêm weights.');
        }
        function selectedEngine() {
            if(!engineChoice.selection)throw Error('Hãy chọn engine clean.');
            var e=engines[engineChoice.selection.index];
            if(!e || !e.ready)throw Error('Engine thiếu model: '+(e && e.missing_models ? e.missing_models.join(', ') : 'không xác định'));
            return {id:e.id,version:e.version};
        }
        function selectSavedEngine(chosen){
            for(var ei=0;ei<engines.length;ei++)if(engines[ei].id===chosen.id && engines[ei].version===chosen.version){
                if(!engines[ei].ready)throw Error('Engine đã lưu thiếu model; kiểm tra Python/model trước khi mở manifest.');
                engineChoice.selection=ei;return;
            }
            throw Error('Không có đúng engine/version đã lưu: '+chosen.id+' '+chosen.version);
        }
        function loadEngines() {
            try {
                var data=rpc({operation:'list_engines'});if(!data.engines || !data.engines.length)throw Error('Danh sách engine rỗng');
                engines=data.engines;uiFeatures=data.ui_features || {};if(!featureReady('scan_ai'))aiDetector.value=false;engineChoice.removeAll();var defaultIndex=0;
                for(var n=0;n<engines.length;n++){var item=engines[n];engineChoice.add('item',item.label+' — '+item.version+(item.ready?'':' [thiếu model]'));if(item.id===data.default)defaultIndex=n;}
                engineChoice.selection=defaultIndex;
            } catch(e) { status.text='Không tải được danh sách engine; dùng baseline offline khi có manifest.'; }
        }
        engineChoice.onChange=function(){state=null;if(currentEngineId()!=='baseline')modelBatch.value=false;syncInputs();};
        alreadyClean.onClick=function(){syncInputs();};
        batchCleanOnly.onClick=function(){syncInputs();};
        reviewAll.onClick=function(){syncInputs();};
        modelBatch.onClick=function(){if(modelBatch.value)reviewAll.value=false;syncInputs();};
        maskChoice.onChange=useLama.onChange=protectFaces.onClick=function(){syncInputs();};
        function selectedDoc() {
            if (!docs.length || !page.selection) throw Error('Hãy mở trang truyện trong Photoshop trước. Thư mục ảnh dùng nút Làm cả chương.');
            return docs[page.selection.index];
        }
        function options(doc) {
            var result = {font: fontIds[font.selection.index], fonts: {dialogue:fontIds[font.selection.index], box:fontIds[boxFont.selection.index], shout:fontIds[shoutFont.selection.index]}, automatic: autoRoles.value, min: Number(minSize.text), max: Number(maxSize.text), leading: Number(leading.text)};
            if (!(result.min >= 4 && result.max >= result.min && result.max <= 250 && result.leading >= 1 && result.leading <= 2.5))
                throw Error('Cỡ chuẩn cần 4–250, min ≤ max; giãn dòng cần 1–2.5.');
            if(doc){
                var scale=Math.max(1,Math.min(doc.width.as('px')/1008,doc.height.as('px')/1440));
                result.min*=scale;result.max*=scale;
            }
            return result;
        }
        function translations() {
            // Local parsing also works when using offline preprocessed manifests.
            var lines = translation.text.replace(/\r\n/g, '\n').replace(/\r/g, '\n').split('\n');
            var pages = {}, n = '1', marked = false;
            for (var j = 0; j < lines.length; j++) {
                var value = lines[j].replace(/^\s+|\s+$/g, ''); if (!value) continue;
                var marker = /^(?:\[(?:PAGE|Trang)\s+(\d+)\]|(\d+))$/i.exec(value);
                if (marker) {
                    n = String(Number(marker[1] || marker[2]));
                    if (Number(n) < 1 || (pages[n] && pages[n].length)) throw Error('Marker trang không hợp lệ hoặc lặp: ' + n);
                    marked = true; if (!pages[n]) pages[n] = [];
                } else { if (!pages[n]) pages[n] = []; pages[n].push(value.replace(/\\n/g, '\n')); }
            }
            return {pages: pages, marked: marked, filename_pages: /\[Trang\s+\d+\]/i.test(translation.text)};
        }
        function detect(doc) {
            var chosen=selectedEngine();
            if (!lang.selection) throw Error("Chọn OCR đúng chữ gốc: Nhật dọc = jpn_vert; Nhật ngang = jpn; Anh = eng.");
            if (doc.width.as('px') * doc.height.as('px') > 30000000) throw Error('Trang vượt 30 triệu pixel; hãy chia trang dài.');
            var folder = MTA.mkdir(root.fsName + '/work/pages/' + MTA.unique());
            tick('Xuất ảnh tổng hợp: ' + doc.name, 10);
            var input = MTA.snapshot(doc, folder);
            tick((aiDetector.value ? 'AI bo bong bóng + OCR: ' : 'OpenCV + OCR: ') + doc.name, 25);
            var result = rpc({operation: 'scan', input: input.fsName, out: folder.fsName,
                              lang: lang.selection.text, psm: lang.selection.text === 'jpn_vert' ? 5 : 11, rtl: rtl.value, detector: aiDetector.value ? 'ai' : 'opencv',layout:magiOrder.value?'magi':(koharuOrder.value?'koharu':'opencv'), detail:['standard','multiscale','koharu'][detailChoice.selection.index]});
            var stored=new File(result.manifest),savedData=MJSON.parse(MTA.read(stored));
            savedData.engine_selection=chosen;savedData.ui_version=MTA.uiVersion;MTA.write(stored,MJSON.stringify(savedData));result.engine_selection=chosen;
            return {doc: doc, folder: folder, manifestPath: result.manifest, data: result, mapping: null, engine:chosen,
                    translationText: null, offline: false};
        }
        function ensureState() { var doc = selectedDoc(),chosen=selectedEngine(); if (!state || state.doc !== doc || !state.engine || state.engine.id!==chosen.id || state.engine.version!==chosen.version) state = detect(doc); return state; }
        function review(s, lines, onlyClean) {
            var regions = MJSON.parse(MJSON.stringify(s.data.regions));
            var mapping = [], j;
            if (s.mapping && s.translationText === translation.text) mapping = MJSON.parse(MJSON.stringify(s.mapping));
            else if (s.data.mapping && s.data.mapping.length && !translation.text.replace(/\s/g, '')) mapping = MJSON.parse(MJSON.stringify(s.data.mapping));
            else for (j = 0; j < regions.length; j++) mapping.push({id: regions[j].id, translation: lines[j] || '', clean: true});
            // Include every region, even if the saved mapping omitted some.
            var all = [];
            for (j = 0; j < regions.length; j++) {
                var found = null;
                for (var m = 0; m < mapping.length; m++) if (mapping[m].id === regions[j].id) found = mapping[m];
                all.push(found || {id: regions[j].id, translation: '', clean: true});
            }
            mapping = all;
            var reviewEngine=s.engine || selectedEngine();
            // A force flag saved by the baseline must never leak into another engine.
            if(reviewEngine.id!=='baseline')for(j=0;j<mapping.length;j++)mapping[j].force=false;
            var dlg = new Window('dialog', 'Kiểm tra vùng thoại và sửa mapping — ' + s.doc.name);
            dlg.orientation = 'column'; dlg.alignChildren = 'fill'; dlg.spacing = 5;
            dlg.add('statictext', undefined, 'Bấm khung trên ảnh hoặc chọn ID trong danh sách. Nhận diện chưa thay đổi ảnh gốc.');
            if (s.experimentalClean) dlg.add('statictext', undefined, 'Clean AI sẽ áp dụng mask TOÀN TRANG, không phụ thuộc lựa chọn clean từng vùng.');
            var mismatch = lines.length !== regions.length;
            dlg.add('statictext', undefined, regions.length + ' vùng / ' + lines.length + ' câu. ' +
                    (mismatch ? 'SỐ LƯỢNG KHÔNG KHỚP — kiểm tra từng ID trước khi áp dụng.' : 'Kiểm tra thứ tự trước khi áp dụng.'));
            var reviewActions = dlg.add('group');
            var accept = reviewActions.add('checkbox', undefined, 'Tôi đã kiểm tra mapping và câu dư.');
            reviewActions.add('button', undefined, 'Hủy', {name: 'cancel'});
            var ok = reviewActions.add('button', undefined, 'Áp dụng', {name: 'ok'});
            var body = dlg.add('group'); body.alignChildren = 'top';
            var previewFile = new File(s.folder.fsName + '/preview_small.png');
            if (previewFile.exists) { var picture = body.add('image', undefined, previewFile); picture.maximumSize = [440, 520]; }
            var editor = body.add('group'); editor.orientation = 'column'; editor.alignChildren = 'fill'; editor.spacing = 2;
            var list = editor.add('listbox', undefined, [], {multiselect: false}); list.preferredSize = [390, 65];
            var note = editor.add('statictext', undefined, '', {multiline: true}); note.preferredSize = [390, 60];
            var aiSuggest=editor.add('button',undefined,'Baberu + E5: gợi ý ghép câu trang này'); aiSuggest.enabled=!onlyClean && !s.offline && lines.length>0 && featureReady('alignment');
            var aiRow=editor.add('group'); var aiChoices=aiRow.add('dropdownlist',undefined,[]); aiChoices.preferredSize.width=240;
            var applyAi=aiRow.add('button',undefined,'Dùng câu gợi ý');applyAi.enabled=false;
            var aiResults=null;
            var trialClean = editor.add('button', undefined, 'Xem thử clean vùng đang chọn'); trialClean.enabled = !alreadyClean.value && !s.offline && !s.experimentalClean;
            var reviewTools=editor.add('panel',undefined,'Nâng cao — thử guard riêng, không phải preview engine');reviewTools.alignChildren='fill';
            var guardPreview = reviewTools.add('button', undefined, 'Thử mask bảo vệ riêng (Baseline)'); guardPreview.enabled = false;
            var undoGuardPreview = reviewTools.add('button', undefined, 'Gỡ layer thử vừa thêm'); undoGuardPreview.enabled = false;
            var lastGuardLayer = null;
            var edit = editor.add('edittext', undefined, '', {multiline: true, scrolling: true}); edit.preferredSize = [390, 48];
            var coords = editor.add('group'), fields = [];
            coords.add('statictext', undefined, 'Khung đặt chữ x/y/w/h (px):');
            for (j = 0; j < 4; j++) { var field = coords.add('edittext', undefined, '0'); field.characters = 5; fields.push(field); }
            var geometry = editor.add('group');
            var applyRect = geometry.add('button', undefined, 'Sửa khung đặt chữ');
            var addRegion = geometry.add('button', undefined, 'Thêm vùng thủ công');
            var regionUp = geometry.add('button', undefined, 'Vùng ↑'), regionDown = geometry.add('button', undefined, 'Vùng ↓');
            var refreshPreview = editor.add('button', undefined, 'Cập nhật hình xem trước / thứ tự');
            refreshPreview.enabled = !s.offline;
            var cleanBox = editor.add('checkbox', undefined, 'Clean vùng này (bật để thử cả vùng thiếu tin cậy)');
            var roleRow = editor.add('group'); roleRow.add('statictext', undefined, 'Kiểu chữ vùng:');
            var roleChoice = roleRow.add('dropdownlist', undefined, ['Tự chọn', 'Thoại thường', 'Ô vuông / lời dẫn', 'Chữ hét']);
            var roleIds = ['auto', 'dialogue', 'box', 'shout']; roleChoice.selection = 0;
            var qwenFont = roleRow.add('button',undefined,'Qwen gợi ý'); qwenFont.enabled=!onlyClean && !s.offline && featureReady('font_qwen');
            var roleHint = editor.add('statictext', undefined, '');
            editor.add('statictext', undefined, 'Để trống để bỏ qua. Dùng ↑/↓ để đổi thứ tự câu giữa hai vùng.');
            var moves = editor.add('group');
            var up = moves.add('button', undefined, 'Đổi với vùng ↑'), down = moves.add('button', undefined, 'Đổi với vùng ↓');
            var mergeNext=editor.add('button',undefined,'Gộp câu kế vào vùng này, dồn lại các câu sau');
            mergeNext.helpTip='Dùng khi một cụm bóng nhận hai câu dịch. Tự dồn mapping và lấy câu dư vào vùng cuối, không bỏ câu.';
            var missingNote=editor.add('statictext',undefined,'');
            var pendingRow=editor.add('group');
            var pendingChoice=pendingRow.add('dropdownlist',undefined,[]);pendingChoice.preferredSize.width=255;
            var appendPending=pendingRow.add('button',undefined,'Ghép vào vùng');
            var omitPending=editor.add('checkbox',undefined,'Cho phép bỏ câu chưa ghép (file sẽ thiếu câu)');
            var typeReviewControls=[edit,coords,applyRect,addRegion,roleChoice,up,down,mergeNext,pendingChoice,omitPending];
            if(onlyClean)for(var tr=0;tr<typeReviewControls.length;tr++)typeReviewControls[tr].enabled=false;
            var selected = -1;
            function coverage() {
                var missing=MTA.unmappedTranslations(lines,mapping);pendingChoice.removeAll();
                for(var n=0;n<missing.length;n++){var item=pendingChoice.add('item',(missing[n]+1)+': '+lines[missing[n]].substr(0,35));item.lineIndex=missing[n];}
                if(missing.length)pendingChoice.selection=0;
                appendPending.enabled=!onlyClean && missing.length>0 && selected>=0;
                missingNote.text='Câu chưa ghép: '+missing.length+'/'+lines.length+'. Một vùng có thể nhận nhiều câu.';
                return missing;
            }
            function commit() { if (selected >= 0) { mapping[selected].translation = edit.text.replace(/\r/g, '\n'); mapping[selected].clean = cleanBox.value; mapping[selected].force = cleanBox.value && !regions[selected].auto_clean && reviewEngine.id === 'baseline'; mapping[selected].font_role = roleIds[roleChoice.selection ? roleChoice.selection.index : 0]; } coverage(); }
            appendPending.onClick=function(){
                if(selected<0 || !pendingChoice.selection)return;
                var index=pendingChoice.selection.lineIndex;
                edit.text+=(edit.text.replace(/\s/g,'')?'\n':'')+lines[index];commit();
            };
            aiSuggest.onClick=function(){
                try{commit();note.text='Đang đọc OCR và đối chiếu…';dlg.update();
                    aiResults=rpc({operation:'alignment_suggest',manifest:s.manifestPath,translations:lines});load();
                }catch(e){alert(e.message);}
            };
            applyAi.onClick=function(){
                if(selected<0 || !aiChoices.selection)return;
                commit();var idx=aiChoices.selection.lineIndex,newText=lines[idx], prior=mapping[selected].translation;
                for(var k=0;k<mapping.length;k++)if(k!==selected && mapping[k].translation===newText){mapping[k].translation=prior;break;}
                mapping[selected].translation=newText;load();
            };
            edit.onChange=commit;
            roleChoice.onChange=function(){ if (selected >= 0) { commit(); showRoleHint(); } };
            qwenFont.onClick=function(){
                try{if(selected<0)return;commit();roleHint.text='Đang hỏi Qwen; có thể mất một lúc…';dlg.update();
                    var result=rpc({operation:'font_suggest',manifest:s.manifestPath,region_id:regions[selected].id,text:edit.text});
                    var index=-1;for(var qi=0;qi<roleIds.length;qi++)if(roleIds[qi]===result.role)index=qi;
                    if(index<1){roleHint.text='Qwen chưa đưa nhãn hợp lệ; giữ lựa chọn hiện tại.';return;}
                    roleChoice.selection=index;commit();showRoleHint();roleHint.text+=' — Qwen gợi ý, hãy kiểm tra';
                }catch(e){alert(e.message);}
            };
            function showRoleHint() {
                if (selected < 0) return;
                var resolved = MTA.resolveTextRole(regions[selected], edit.text, roleIds[roleChoice.selection.index], autoRoles.value);
                var labels = {dialogue:'Thoại thường',box:'Ô vuông / lời dẫn',shout:'Chữ hét'};
                roleHint.text = 'Sẽ dùng font: ' + labels[resolved] + (roleChoice.selection.index === 0 ? ' (ước đoán)' : ' (đã chọn)');
            }
            mergeNext.onClick=function(){
                try{commit();var texts=MTA.mergeNextTranslation(lines,mapping,selected);
                    for(var n=0;n<texts.length;n++)mapping[n].translation=texts[n];load();
                }catch(e){alert(e.message);}
            };
            function load() {
                if (!list.selection) return;
                selected = list.selection.index; var region = regions[selected];
                for (var c = 0; c < 4; c++) fields[c].text = region.safe[c];
                edit.text = mapping[selected].translation;
                var choiceIndex = 0;
                for (var ri = 0; ri < roleIds.length; ri++) if (roleIds[ri] === mapping[selected].font_role) choiceIndex = ri;
                roleChoice.selection = choiceIndex; showRoleHint();
                var hasMask = new File(s.folder.fsName+'/masks/'+region.id+'.png').exists;
                guardPreview.enabled=reviewEngine.id==='baseline' && hasMask && !alreadyClean.value && !s.offline && !s.experimentalClean && featureReady('mask_ctd');
                cleanBox.value = MTA.cleanSelection(region,mapping[selected],reviewEngine.id);
                cleanBox.enabled = MTA.cleanControlEnabled(hasMask,s.offline,!!s.experimentalClean,reviewEngine.id);
                note.text = 'ĐANG CHỌN: ' + region.id + ' — CHƯA CLEAN\n' + (region.ocr_status==='punctuation_geometry' ? 'Dấu câu (hình học): ' : 'OCR: ') + region.source + '\n' + (reviewEngine.id!=='baseline' ? 'Cảnh báo scan/baseline: ' : '') + (region.warnings.join('; ') || 'Có thể xem thử clean.');
                aiChoices.removeAll();applyAi.enabled=false;
                if(aiResults){for(var ar=0;ar<aiResults.regions.length;ar++)if(aiResults.regions[ar].id===region.id){
                    var suggestion=aiResults.regions[ar];note.text='Baberu: '+suggestion.ocr+'\nĐiểm gợi ý chỉ để tham khảo; tự kiểm tra ngữ cảnh.';
                    for(var ac=0;ac<suggestion.candidates.length;ac++){var cand=suggestion.candidates[ac];var option=aiChoices.add('item',(cand.index+1)+' | '+lines[cand.index].substr(0,28)+' | '+cand.score);option.lineIndex=cand.index;}
                    if(aiChoices.items.length){aiChoices.selection=0;applyAi.enabled=true;}break;
                }}
                coverage();
            }
            function updatePicture() {
                if(s.offline || !picture) return;
                var previewData=MJSON.parse(MJSON.stringify(s.data));previewData.regions=regions;
                var result=rpc({operation:'preview',data:previewData,folder:s.folder.fsName,selected:selected>=0?regions[selected].id:null});
                picture.image=ScriptUI.newImage(new File(result.preview)); dlg.layout.layout(true);
            }
            function selectAt(x,y) {
                var imageSize=picture.image.size;
                var hit=MTA.hitRegion(regions,s.data.width,s.data.height,imageSize[0],imageSize[1],picture.size[0],picture.size[1],x,y);
                if(hit>=0){commit();list.selection=hit;load();updatePicture();}
                return hit;
            }
            if(picture) picture.addEventListener('mousedown',function(event){try{selectAt(event.clientX,event.clientY);}catch(e){alert(e.message);}});
            list.onChange = function () { commit(); load(); try{updatePicture();}catch(e){alert(e.message);} };
            trialClean.onClick=function(){
                try{
                    if(selected<0)return; commit(); var region=regions[selected];
                    if(reviewEngine.id==='baseline' && !region.auto_clean && !mapping[selected].force){note.text='Để thử clean '+region.id+', bật ô Clean vùng này bên dưới rồi bấm lại. Có thể cần sửa tay.';return;}
                    var chosen=reviewEngine;
                    var result=rpc({operation:'run_engine',engine_id:chosen.id,engine_version:chosen.version,manifest:s.manifestPath,mapping:[{id:region.id,translation:'Xem thử',clean:true,force:mapping[selected].force === true}],preview:true});
                    picture.image=ScriptUI.newImage(new File(result.images?result.images.clean:result.preview));dlg.layout.layout(true);
                    if(result.experimental){note.text='XEM THỬ '+region.id+' — cần duyệt: '+((result.blocked||{})[region.id]||'kiểm tra mask');return;}
                    if(result.blocked && result.blocked[region.id]){note.text='KHÔNG CLEAN '+region.id+': '+result.blocked[region.id];return;}
                    note.text='ĐÃ XEM THỬ CLEAN: '+result.applied.join(', ')+'\nChỉ ảnh xem trước; chưa thêm layer vào Photoshop. Nhấn Clean ở cửa sổ chính để tạo bản sao.';
                }catch(e){alert(e.message);}
            };

            guardPreview.onClick=function(){
                try {
                    if(reviewEngine.id!=='baseline')throw Error('Công cụ guard riêng chỉ dành cho Baseline; dùng Xem thử clean vùng đang chọn.');
                    if(selected<0)return; commit(); var region=regions[selected];
                    var result=rpc({operation:'region_shadow_preview',manifest:s.manifestPath,region_id:region.id});
                    var modal=new Window('dialog','Mask thử — '+region.id); modal.orientation='column'; modal.alignChildren='fill';
                    modal.add('statictext',undefined,'Gốc | mask đỏ | clean thử. Kiểm tra chữ, viền và artwork trước khi thêm layer.');
                    var pic=modal.add('image',undefined,new File(result.comparison));pic.maximumSize=[1200,450];
                    modal.add('statictext',undefined,'Mask: '+result.guarded_pixels+' pixel; đã loại '+result.removed_pixels+' pixel; chưa xác minh artwork.');
                    var buttons=modal.add('group');buttons.add('button',undefined,'Đóng',{name:'cancel'});
                    var add=buttons.add('button',undefined,'Thêm layer thử',{name:'ok'});add.enabled=!!result.preview_applicable;
                    if(modal.show()===1){lastGuardLayer=MTA.addOverlay(s.doc,result.overlay,'CLEAN THỬ — '+region.id+' — CẦN KIỂM TRA');undoGuardPreview.enabled=true;note.text='Đã thêm layer thử '+region.id+'. Có thể gỡ bằng nút Gỡ layer thử.';}
                } catch(e){alert(e.message);}
            };
            undoGuardPreview.onClick=function(){try{if(lastGuardLayer){lastGuardLayer.remove();lastGuardLayer=null;}undoGuardPreview.enabled=false;note.text='Đã gỡ layer thử.';}catch(e){alert(e.message);}};

            function swap(offset) {
                commit(); var target = selected + offset;
                if (selected < 0 || target < 0 || target >= mapping.length) return;
                var old = mapping[selected].translation; mapping[selected].translation = mapping[target].translation; mapping[target].translation = old;
                load();
            }
            up.onClick = function () { swap(-1); }; down.onClick = function () { swap(1); };
            function rebuild(index) {
                selected = -1; // ignore selection-change events while rebuilding
                list.removeAll();
                for (var n = 0; n < regions.length; n++) list.add('item', (n+1) + '. ' + regions[n].id + ' | ' + MTA.cleanRegionStatus(regions[n],reviewEngine.id) + ' | ' + regions[n].source.substr(0,24));
                selected = -1; if (regions.length) list.selection = index; load();
            }
            applyRect.onClick = function () {
                try { commit(); var rect = []; for (var c = 0; c < 4; c++) rect.push(Number(fields[c].text));
                    MTA.editSafe(regions[selected], rect); load();
                } catch (e) { alert(e.message); }
            };
            addRegion.onClick = function () {
                try { commit(); var rect = []; for (var c = 0; c < 4; c++) rect.push(Number(fields[c].text));
                    var id = 'B' + (10000 + regions.length), manual = {id:id,box:rect.slice(0),safe:rect.slice(0),source:'Vùng thủ công',auto_clean:false,warnings:['Clean thủ công'],fill:[255,255,255]};
                    var probe = {schema:1,width:s.data.width,height:s.data.height,regions:[manual]}; MTA.validateManifest(probe,s.data.width,s.data.height);
                    regions.push(manual); mapping.push({id:id,translation:'',clean:false}); rebuild(regions.length-1);
                } catch (e) { alert(e.message); }
            };
            function moveRegion(offset) {
                commit(); var target = selected + offset; if (selected < 0 || target < 0 || target >= regions.length) return;
                var r = regions[selected], m = mapping[selected]; regions[selected]=regions[target]; mapping[selected]=mapping[target]; regions[target]=r; mapping[target]=m; rebuild(target);
            }
            regionUp.onClick=function(){moveRegion(-1);}; regionDown.onClick=function(){moveRegion(1);};
            refreshPreview.onClick=function(){
                try { commit(); var previewData=MJSON.parse(MJSON.stringify(s.data));previewData.regions=regions;
                    var result=rpc({operation:'preview',data:previewData,folder:s.folder.fsName});
                    picture.image=ScriptUI.newImage(new File(result.preview)); dlg.layout.layout(true);
                } catch(e){alert(e.message);}
            };

            rebuild(0);
            ok.onClick = function () { commit(); if(!onlyClean && coverage().length && !omitPending.value){alert('Vẫn còn câu chưa ghép. Chọn câu trong danh sách và bấm Ghép vào vùng, hoặc thêm vùng thủ công.');return;} if (!accept.value) { alert('Hãy kiểm tra và đánh dấu xác nhận mapping.'); return; } dlg.close(1); };
            if (dlg.show() !== 1) { cancelled = true; throw Error('Đã hủy kiểm tra mapping'); }
            s.mapping = mapping; s.translationText = translation.text;
            s.reviewLines=lines.slice(0);s.allowOmitted=omitPending.value;
            // Offline mapping edits are persisted without requiring Python.
            s.data = MJSON.parse(MTA.read(new File(s.manifestPath)));
            s.data.regions = regions;
            s.data.ui_version=MTA.uiVersion;
            s.data.expected_translations=lines.slice(0);
            s.data.unmapped_translation_indexes=MTA.unmappedTranslations(lines,mapping);
            s.data.mapping = mapping; MTA.write(new File(s.manifestPath), MJSON.stringify(s.data));
            return mapping;
        }
        function prepareClean(s, onlyClean) {
            if(onlyClean && alreadyClean.value)throw Error('Trang đã clean thủ công: bỏ chọn chế độ này trước khi chạy Clean.');
            if (alreadyClean.value && s.experimentalClean) throw Error('Trang đang chờ dùng AI clean toàn trang; hãy bỏ chọn Trang đã clean thủ công.');
            if (alreadyClean.value) return {applied: [], skipped: [], overlay: null};
            if (onlyClean) {
                var anySelected=false;
                for(var si=0;si<s.mapping.length;si++)if(s.mapping[si].clean){anySelected=true;break;}
                if(!anySelected)throw Error('Chưa chọn vùng nào để clean. Bật Clean vùng này trong hộp duyệt rồi thử lại.');
            }
            if (s.experimentalClean) {
                if ((s.engine || selectedEngine()).id !== 'baseline') throw Error('Không thể dùng engine đã chọn cùng chế độ mask toàn trang; hãy bỏ chọn mask toàn trang.');
                if (s.offline) throw Error('Clean AI thử nghiệm cần ảnh và manifest trong dự án.');
                tick('AI clean thử nghiệm trên toàn trang…', 60);
                return rpc({operation:'model_batch_clean', manifest:s.manifestPath,
                            mapping:onlyClean ? cleanMapping(s.mapping) : s.mapping,
                            method:s.experimentalClean.method, lama:s.experimentalClean.lama, inpaint:s.experimentalClean.inpaint, protect_faces:s.experimentalClean.protect_faces !== false});
            }
            if (s.offline) {
                if ((s.engine || selectedEngine()).id !== 'baseline') throw Error('Manifest offline không hỗ trợ engine này; hãy scan lại để dùng engine đã lưu.');
                if (/(^|\+)(jpn|chi_|kor)/.test(s.data.lang || '') && (s.data.clean_ids || []).length && s.data.clean_policy_version !== 2)
                    throw Error('Overlay CJK cũ chưa qua bộ lọc an toàn mới. Chạy Python clean lại manifest trước khi nhập; không dùng lớp clean cũ.');
                var wanted = [], saved = s.data.clean_ids || [], skipped = [];
                for (var j = 0; j < s.mapping.length; j++) {
                    if (!s.mapping[j].translation.replace(/\s/g, '') || !s.mapping[j].clean) continue;
                    for (var k = 0; k < s.data.regions.length; k++) if (s.data.regions[k].id === s.mapping[j].id) {
                        if (s.data.regions[k].auto_clean || s.mapping[j].force === true) wanted.push(s.mapping[j].id); else skipped.push(s.mapping[j].id);
                    }
                }
                wanted.sort(); saved = saved.slice(0).sort();
                if (wanted.join(',') !== saved.join(','))
                    throw Error('Mapping clean khác kết quả tiền xử lý. Chạy CLI clean với manifest đã sửa, rồi nhập lại; hoặc chọn Trang đã clean thủ công.');
                var overlay = new File(s.folder.fsName + '/clean_overlay.png');
                if (wanted.length && !overlay.exists) throw Error('Thiếu clean_overlay.png. Chạy CLI clean trước.');
                return {applied: wanted, skipped: skipped, overlay: overlay.fsName};
            }
            tick('Tạo mặt nạ clean theo mapping đã duyệt…', 60);
            var engine=s.engine || selectedEngine();
            return rpc({operation:'run_engine',engine_id:engine.id,engine_version:engine.version,manifest:s.manifestPath,mapping:onlyClean ? cleanMapping(s.mapping) : s.mapping,preview:!!onlyClean});
        }
        function cleanMapping(mapping) {
            var copy=MJSON.parse(MJSON.stringify(mapping));
            for(var i=0;i<copy.length;i++) if(!copy[i].translation.replace(/\s/g,'')) copy[i].translation='Clean không typeset';
            return copy;
        }
        function build(s, onlyClean, save, keepOpen) {
            if (save && !savePsd.value && !savePdf.value) throw Error('Chọn ít nhất một định dạng lưu: PSD hoặc Photoshop PDF.');
            s.omittedTranslations=onlyClean?[]:MTA.unmappedTranslations(s.reviewLines||[],s.mapping);
            if(s.omittedTranslations.length && !s.allowOmitted)throw Error('Chưa ghép '+s.omittedTranslations.length+' câu dịch; chưa tạo file để tránh thiếu chữ.');
            var config = onlyClean ? null : options(s.doc), result, copy = null;
            try { result = prepareClean(s, onlyClean); }
            catch (cleanError) {
                if (!s.visibleFallback || cancelled) throw cleanError;
                s.cleanError = String(cleanError.message || cleanError);
                var skippedClean = [], blockedClean = {};
                for (var ci = 0; ci < s.mapping.length; ci++) if (s.mapping[ci].translation.replace(/\s/g, '') && s.mapping[ci].clean) {
                    skippedClean.push(s.mapping[ci].id); blockedClean[s.mapping[ci].id] = s.cleanError;
                }
                result = {applied:[], skipped:skippedClean, blocked:blockedClean};
            }
            s.cleanResult=result;
            s.manualText=[]; s.layoutFallback=[];
            try {
                app.activeDocument = s.doc;
                copy = s.doc.duplicate(s.doc.name.replace(/\.[^.]+$/, '') + (onlyClean ? ' — CLEAN' : ' — Typeset'));
                if (result.applied.length || (result.full_page && result.mask_pixels > 0)) MTA.addOverlay(copy, result.overlay, result.experimental ? 'CLEAN AI THỬ NGHIỆM — KIỂM TRA' : undefined);
                if (!onlyClean) {
                    var group = copy.layerSets.add(); group.name = 'TYPESET — Tiếng Việt';
                    for (var j = 0; j < s.mapping.length; j++) {
                        if (!tick('Dàn chữ ' + s.mapping[j].id, 65 + 25 * j / Math.max(1, s.mapping.length))) throw Error('Đã hủy');
                        if (!s.mapping[j].translation.replace(/\s/g, '')) continue;
                        var region = null;
                        for (var k = 0; k < s.data.regions.length; k++) if (s.data.regions[k].id === s.mapping[j].id) region = s.data.regions[k];
                        if (!region) throw Error('Không tìm thấy vùng ' + s.mapping[j].id);
                        var role = MTA.resolveTextRole(region, s.mapping[j].translation, s.mapping[j].font_role, config.automatic);
                        config.font = config.fonts[role];
                        var textLayer;
                        try { textLayer = MTA.addText(copy, group, region, s.mapping[j].translation, config); }
                        catch (fitError) {
                            if (!s.visibleFallback && !result.experimental) throw fitError;
                            var safe = region.safe;
                            textLayer = MTA.addFallbackText(copy, group, s.mapping[j].translation, config,
                                [safe[0]+safe[2]/2, safe[1]+safe[3]/2], '[CẦN CHỈNH KHUNG] ' + region.id, Math.max(safe[2], copy.width.as('px')*.16));
                            s.layoutFallback.push({id:region.id, reason:String(fitError.message || fitError)});
                        }
                        textLayer.name = '[' + ({dialogue:'THOẠI',box:'Ô VUÔNG',shout:'HÉT'})[role] + '] ' + textLayer.name;
                        var wasCleaned=false;
                        for(var cleanedIndex=0;cleanedIndex<result.applied.length;cleanedIndex++) if(result.applied[cleanedIndex]===region.id) wasCleaned=true;
                        if (!wasCleaned && !alreadyClean.value) {
                            textLayer.name = (result.experimental ? '[KIỂM TRA CLEAN AI — CHỮ HIỆN] ' : (s.visibleFallback ? '[CẦN CLEAN — CHỮ HIỆN] ' : '[CẦN CLEAN — CHỮ ẨN] ')) + textLayer.name;
                            if (!s.visibleFallback && !result.experimental) textLayer.visible = false;
                            s.manualText.push(region.id);
                        }
                    }
                    // Unassigned sentences stay editable; the explicit batch
                    // override puts them visibly in the centre for later edits.
                    for (var u = 0; u < s.omittedTranslations.length; u++) {
                        var index = s.omittedTranslations[u], unplaced;
                        if (s.visibleFallback) {
                            config.font = config.fonts.dialogue;
                            unplaced = MTA.addFallbackText(copy, group, s.reviewLines[index], config,
                                [copy.width.as('px')/2, copy.height.as('px')/2 + u*Math.max(12,config.min*1.5)], '[CHƯA GHÉP — Ở GIỮA] Câu ' + (index + 1), copy.width.as('px')*.35);
                        } else {
                            unplaced = group.artLayers.add(); unplaced.kind = LayerKind.TEXT;
                            unplaced.name = '[CHƯA GHÉP — CHỮ ẨN] Câu ' + (index + 1);
                            unplaced.textItem.contents = s.reviewLines[index]; unplaced.visible = false;
                        }
                    }
                }
                if (cmykOutput.value && copy.mode !== DocumentMode.CMYK) {
                    tick('Chuyển bản sao sang CMYK theo Color Settings…', 92);
                    copy.changeMode(ChangeMode.CMYK);
                }
                s.outputColorMode=String(copy.mode);s.outputColorProfile=null;
                try { s.outputColorProfile=copy.colorProfileName; } catch (_) {}
                if (!tick('Chuẩn bị lưu…', 95)) throw Error('Đã hủy trước khi lưu');
                s.savedFiles = {};
                var saved = save ? MTA.saveCopy(copy, outputFolder, s.doc.name, {psd:savePsd.value, pdf:savePdf.value, pdfLayers:pdfLayers.value, png: png.value, jpg: jpg.value, cmykJpeg:cmykOutput.value}, onlyClean ? 'clean' : 'typeset', s.savedFiles) : null;
                if (!keepOpen) { copy.close(SaveOptions.DONOTSAVECHANGES); copy = null; }
                tick((s.manualText.length ? 'Vùng cần clean/duyệt: '+s.manualText.length+'. ' : '') + (saved ? 'Đã lưu: ' + saved.fsName : 'Đã tạo bản sao CLEAN') + MTA.cleanResultSummary(result), 100);
                return saved ? saved.fsName : '';
            } catch (e) { if (copy) copy.close(SaveOptions.DONOTSAVECHANGES); throw e; }
        }
        function currentLines() { var parsed = translations(); return parsed.pages[MTA.translationKey(parsed,selectedDoc().name,page.selection.index)] || []; }
        page.onChange = function () { state = null; };
        rtl.onClick = function () { state = null; };
        aiDetector.onClick = function () { state = null; syncInputs(); };
        detailChoice.onChange = function () { state = null; };
        koharuOrder.onClick = function () { if(koharuOrder.value)magiOrder.value=false; state = null; };
        magiOrder.onClick = function () { if(magiOrder.value)koharuOrder.value=false; state = null; };
        lang.onChange = function () { state = null; };
        presets.onChange = function () {
            var values = [[10, 32, 1.15], [12, 28, 1.3], [18, 52, 1.1]][presets.selection.index];
            minSize.text = values[0]; maxSize.text = values[1]; leading.text = values[2];
            var preferred = ['ArialMT', 'Arial-ItalicMT', 'Arial-BoldMT'][presets.selection.index];
            for (var f = 0; f < fontIds.length; f++) if (fontIds[f] === preferred) font.selection = f;
        };
        saveFonts.onClick = function () { run(function () {
            MTA.mkdir(fontSettingsFile.parent.fsName);
            MTA.write(fontSettingsFile, MJSON.stringify({dialogue:fontIds[font.selection.index], box:fontIds[boxFont.selection.index], shout:fontIds[shoutFont.selection.index], automatic:autoRoles.value}));
            tick('Đã lưu ba font để dùng lần sau.');
        }); };
        chooseFolder.onClick = function () {
            var selected = Folder.selectDialog('Chọn thư mục chứa JPG, PNG, PSD');
            if (selected) { inputFolder = selected; sourceInfo.text = selected.fsName + ' (dùng cho cả chương)'; }
        };
        openSources.onClick = function () { inputFolder = null; sourceInfo.text = docs.length + ' tài liệu đang mở'; };
        setOutput.onClick = function () { var f = Folder.selectDialog('Thư mục lưu file kết quả'); if (f) { outputFolder = f; outInfo.text = f.fsName; restoreLatestQueue(); } };
        check.onClick = function () { run(function () { var r = rpc({operation: 'doctor'}); alert(MJSON.stringify(r)); }); };
        openText.onClick = function () {
            var file = File.openDialog('Chọn TXT hoặc DOCX'); if (!file) return;
            run(function () {
                translation.text = rpc({operation: 'import', path: file.fsName}).text;
            });
        };
        openTranslations.onClick = function () {
            var folder = Folder.selectDialog('Thư mục TXT/DOCX; ưu tiên bản _polished'); if (!folder) return;
            run(function () {
                var imported = rpc({operation:'import', path:folder.fsName}); translation.text=imported.text;
                tick('Đã nhập '+imported.files.length+' bản dịch; ghép theo số tên file ảnh.');
            });
        };
        importResult.onClick = function () {
            var file = File.openDialog('Chọn manifest.json đã tiền xử lý'); if (!file) return;
            run(function () {
                var doc = selectedDoc(), data = MJSON.parse(MTA.read(file));
                MTA.validateManifest(data, doc.width.as('px'), doc.height.as('px'));
                var queuedFile=new File(file.parent.fsName+'/translation_review.json'), queued=null;
                if(queuedFile.exists){
                    var pending=MJSON.parse(MTA.read(queuedFile));
                    if(pending.manifest && new File(pending.manifest).fsName===file.fsName)queued=pending;
                }
                if(queued){
                    if(decodeURI(doc.name)!==queued.source)throw Error('Hãy mở đúng trang '+queued.source+' trước khi nhập kết quả chờ duyệt.');
                    if(!translation.text.replace(/\s/g,'')){
                        var queuedLines=[];
                        for(var qi=0;qi<queued.translations.length;qi++)queuedLines.push(queued.translations[qi].replace(/\r?\n/g,'\\n'));
                        translation.text='[Trang '+queued.translation_page+']\n'+queuedLines.join('\n');
                    }
                }
                var pinned=MTA.savedEngine(null,queued,data);state=null;selectSavedEngine(pinned);
                var offline=!queued && pinned.id==='baseline';
                if(!offline && (!new File(file.parent.fsName+'/original.png').exists || !new Folder(file.parent.fsName+'/masks').exists))throw Error('Thiếu ảnh gốc hoặc thư mục masks của manifest; hãy scan lại ảnh gốc.');
                state = {doc: doc, folder: file.parent, manifestPath: file.fsName, data: data, mapping: null, offline: offline, engine:pinned};
                modelBatch.value=false;syncInputs();
                alert(offline ? 'Đã nhập Baseline offline; chỉ dùng overlay tiền xử lý khớp mapping đã duyệt.' : 'Đã mở dữ liệu với engine '+pinned.id+' '+pinned.version+'. Preview/clean tiếp tục qua backend với đúng engine đã lưu.');
                review(state, currentLines(),batchCleanOnly.value);
            });
        };
        function showEnginePreview(result){
            if(!result.images)throw Error('Backend chưa hỗ trợ preview engine; cập nhật đủ bộ source.');
            var dialog=new Window('dialog','Preview engine '+result.engine_id+' — '+result.version);dialog.orientation='column';dialog.alignChildren='center';
            dialog.add('statictext',undefined,'Gốc / mask / clean của đúng engine. Chỉ xem trước, chưa thêm layer hoặc sửa ảnh gốc.');
            var picture=dialog.add('image',undefined,new File(result.images.clean));picture.maximumSize=[540,600];
            var choices=dialog.add('group');
            function button(label,path){var b=choices.add('button',undefined,label);b.onClick=function(){picture.image=ScriptUI.newImage(new File(path));dialog.layout.layout(true);};}
            button('Ảnh gốc',result.images.original);button('Mask engine',result.images.mask);button('Clean engine',result.images.clean);
            choices.add('button',undefined,'Đóng',{name:'ok'});dialog.center();dialog.show();
        }
        previewEngine.onClick=function(){run(function(){
            if(alreadyClean.value || modelBatch.value)throw Error('Preview engine không dùng cùng chế độ đã clean hoặc mask toàn trang.');
            var s=ensureState();if(s.offline)throw Error('Manifest Baseline offline chỉ nhập overlay; scan ảnh để xem thử engine.');
            var chosen=s.engine || selectedEngine();
            var mapping=MTA.enginePreviewMapping(s.data.regions,s.mapping || s.data.mapping,chosen.id);
            tick('Xem thử engine '+chosen.id+'…',30);
            var result=rpc({operation:'run_engine',engine_id:chosen.id,engine_version:chosen.version,manifest:s.manifestPath,mapping:mapping,preview:true});
            showEnginePreview(result);tick('Đã xem thử '+chosen.id+MTA.cleanResultSummary(result),100);
        });};
        testModel.onClick = function () { run(function () {
            if(currentEngineId()!=='baseline' || alreadyClean.value || !modelExperimentReady())throw Error('Công cụ thử model chỉ dùng với Baseline và đủ model/dependency.');
            var doc=selectedDoc(), folder=MTA.mkdir(root.fsName+'/work/model_previews/'+MTA.unique());
            tick('Xuất ảnh để thử model…',10);
            var input=MTA.snapshot(doc,folder);
            tick('Đang chạy model thử; LaMa có thể mất một lúc…',25);
            var methods=['ctd','mask','koharu','hybrid'];
            var result=rpc({operation:'model_preview',input:input.fsName,out:folder.fsName+'/result',method:methods[maskChoice.selection.index],inpaint:inpaintMethod(),lama:inpaintMethod()==='lama',protect_faces:protectFaces.value});
            var dialog=new Window('dialog','Xem thử AI clean — '+doc.name);dialog.orientation='column';dialog.alignChildren='center';
            dialog.add('statictext',undefined,'Chỉ xem thử. Đỏ = mask. Nghi còn chữ/nét tranh: '+(result.quality ? result.quality.suspect_count : '?')+' vùng.');
            var picture=dialog.add('image',undefined,new File(result.images.clean));picture.maximumSize=[540,600];
            var choices=dialog.add('group');
            var original=choices.add('button',undefined,'Ảnh gốc');
            var mask=choices.add('button',undefined,'Mask màu đỏ');
            var cleaned=choices.add('button',undefined,'Kết quả clean');
            choices.add('button',undefined,'Đóng',{name:'ok'});
            function showImage(path){picture.image=ScriptUI.newImage(new File(path));dialog.layout.layout(true);}
            original.onClick=function(){showImage(result.images.original);};
            mask.onClick=function(){showImage(result.images.mask);};
            cleaned.onClick=function(){showImage(result.images.clean);};
            dialog.center();dialog.show();
            tick('Đã tạo bản xem thử. Ảnh gốc và clean chương không thay đổi.',100);
        }); };
        scan.onClick = function () { run(function () { state = detect(selectedDoc()); review(state, currentLines()); tick('Đã kiểm tra ' + state.data.regions.length + ' vùng.', 100); }); };
        clean.onClick = function () { run(function () { var s = ensureState(); review(s, currentLines(), true); build(s, true, false, true); }); };
        typeset.onClick = function () { run(function () { var s = ensureState(); review(s, currentLines()); build(s, false, true, true); }); };
        function loadPendingLog(file) {
            var rows = MJSON.parse(MTA.read(file)), found = [];
            if (!(rows instanceof Array)) throw Error('Log chương không hợp lệ');
            for (var n = 0; n < rows.length; n++)
                if (rows[n].status === 'review_required' && rows[n].manifest) found.push(rows[n]);
            pendingPages = found; pendingLog = file;
            pendingButton.text = 'Trang chờ duyệt (' + found.length + ')';
            pendingButton.enabled = found.length > 0;
        }
        // Restore the latest batch queue after the window or Photoshop closes.
        function restoreLatestQueue() {
            var previousLogs = outputFolder.exists ? outputFolder.getFiles('batch_*.json') : [];
            previousLogs.sort(function(a,b) { return b.modified.getTime() - a.modified.getTime(); });
            if (previousLogs.length) { try { loadPendingLog(previousLogs[0]); return; } catch (_) {} }
            pendingPages = []; pendingLog = null; pendingButton.text = 'Trang chờ duyệt (0)'; pendingButton.enabled = false;
        }
        restoreLatestQueue();
        pendingButton.onClick = function () {
            var dialog = new Window('dialog', 'Các trang chờ xử lý'); dialog.orientation = 'column'; dialog.alignChildren = 'fill';
            dialog.add('statictext', undefined, 'Chọn một trang để duyệt, hoặc xử lý tự động theo thứ tự hiện có.');
            var choices = dialog.add('listbox', undefined, [], {multiselect:false}); choices.preferredSize = [520, 170];
            for (var n = 0; n < pendingPages.length; n++) choices.add('item', pendingPages[n].source + ' — ' + pendingPages[n].regions + ' vùng / ' + pendingPages[n].lines + ' câu');
            if (pendingPages.length) choices.selection = 0;
            dialog.add('statictext', undefined, 'Vẫn làm tất cả: hiện chữ trên vùng chưa clean; câu thiếu vùng đặt giữa trang.');
            var buttons = dialog.add('group'), action = '';
            var doReview = buttons.add('button', undefined, 'Duyệt trang đã chọn');
            var doAuto = buttons.add('button', undefined, 'Vẫn làm trang đã chọn');
            var doAll = buttons.add('button', undefined, 'Vẫn làm tất cả');
            buttons.add('button', undefined, 'Đóng', {name:'cancel'});
            doReview.onClick = function () { action = 'review'; dialog.close(1); };
            doAuto.onClick = function () { action = 'auto'; dialog.close(1); };
            doAll.onClick = function () { action = 'all'; dialog.close(1); };
            if (dialog.show() !== 1 || !choices.selection) return;
            var selectedIndex = choices.selection.index;
            run(function () {
              function processPending(selectedIndex, action) {
                var entry = pendingPages[selectedIndex];
                var manifest = new File(entry.manifest), queueFile = new File(manifest.parent.fsName + '/translation_review.json');
                if (!manifest.exists || !queueFile.exists) throw Error('Không tìm thấy dữ liệu chờ duyệt của ' + entry.source);
                var queued = MJSON.parse(MTA.read(queueFile)), data = MJSON.parse(MTA.read(manifest));
                if (!queued.manifest || new File(queued.manifest).fsName !== manifest.fsName || queued.source !== entry.source)
                    throw Error('Dữ liệu chờ duyệt không khớp trang ' + entry.source);
                var doc = null, ownsDoc = false;
                for (var d = 0; d < app.documents.length; d++) {
                    var candidate = app.documents[d];
                    if (decodeURI(candidate.name) !== entry.source) continue;
                    if (entry.source_path) { try { if (candidate.fullName.fsName !== new File(entry.source_path).fsName) continue; } catch (_) { continue; } }
                    doc = candidate; break;
                }
                if (!doc && entry.source_path && new File(entry.source_path).exists) { doc = app.open(new File(entry.source_path)); ownsDoc = true; }
                if (!doc) throw Error('Hãy mở ảnh gốc ' + entry.source + ' trong Photoshop rồi thử lại.');
                try {
                    MTA.validateManifest(data, doc.width.as('px'), doc.height.as('px'));
                    var s = {doc:doc, folder:manifest.parent, manifestPath:manifest.fsName, data:data, mapping:null,
                             translationText:null, offline:false, reviewLines:queued.translations.slice(0), visibleFallback:action === 'all', experimentalClean:entry.experimental_clean || null, engine:MTA.savedEngine(entry,queued,data)};
                    if (action === 'review') review(s, s.reviewLines);
                    else {
                        s.mapping = [];
                        for (var i = 0; i < data.regions.length; i++)
                            s.mapping.push({id:data.regions[i].id, translation:s.reviewLines[i] || '', clean:true, force:false});
                        s.allowOmitted = true;
                    }
                    var saved = build(s, false, true, false);
                    var rows = MJSON.parse(MTA.read(pendingLog));
                    for (var r = 0; r < rows.length; r++) if (rows[r].manifest === entry.manifest && rows[r].status === 'review_required') {
                        rows[r].status = (s.omittedTranslations.length || s.manualText.length || s.cleanResult.skipped.length || s.layoutFallback.length || s.experimentalClean) ? 'partial' : 'processed';
                        rows[r].psd = s.savedFiles.psd || null; rows[r].pdf = s.savedFiles.pdf || null; rows[r].review_action = action;
                        rows[r].unmapped_translation_indexes = s.omittedTranslations;
                        rows[r].manual_text_ids = s.manualText; rows[r].clean_skipped = s.cleanResult.skipped;
                        rows[r].visible_over_uncleaned = (s.visibleFallback || s.experimentalClean) ? s.manualText : [];
                        rows[r].layout_fallback = s.layoutFallback;
                        rows[r].clean_error = s.cleanError || null;
                        rows[r].experimental_clean = s.experimentalClean || null; rows[r].clean_quality = s.cleanResult.quality || null;
                        rows[r].clean_mask_pixels = s.cleanResult.mask_pixels || 0;
                        rows[r].clean_region_results=s.cleanResult.region_results || [];rows[r].clean_review_ids=s.cleanResult.review_ids || [];rows[r].clean_counts=s.cleanResult.counts || null;
                        rows[r].engine_id=s.cleanResult.engine_id || null;rows[r].engine_version=s.cleanResult.version || null;rows[r].clean_trace=s.cleanResult.trace || null;
                        rows[r].ui_version=MTA.uiVersion;
                        break;
                    }
                    MTA.write(pendingLog, MJSON.stringify(rows));
                    pendingPages.splice(selectedIndex, 1); pendingButton.text = 'Trang chờ duyệt (' + pendingPages.length + ')';
                    if (action !== 'all') alert('Đã lưu: ' + saved + '\nCâu chưa ghép lưu thành layer ẩn: ' + s.omittedTranslations.length + (s.experimentalClean ? '\nChữ hiện cần kiểm tra clean AI: ' : '\nVùng cần clean tay: ') + s.manualText.length);
                } finally { if (ownsDoc && doc) doc.close(SaveOptions.DONOTSAVECHANGES); }
              }
              if (action === 'all') {
                  var batch = pendingPages.slice(0), failures = [], succeeded = 0;
                  for (var bi = 0; bi < batch.length && !cancelled; bi++) {
                      var at = -1;
                      for (var pi = 0; pi < pendingPages.length; pi++) if (pendingPages[pi].manifest === batch[bi].manifest) { at = pi; break; }
                      if (at < 0) continue;
                      try { processPending(at, 'all'); succeeded++; }
                      catch (error) { if (cancelled) break; failures.push(batch[bi].source + ': ' + String(error.message || error)); }
                  }
                  alert('Đã xử lý ' + succeeded + '/' + batch.length + ' trang. Vùng chưa clean và chữ đặt giữa trang cần chỉnh sau.' + (failures.length ? '\nCòn lỗi, vẫn giữ trong hàng chờ:\n' + failures.join('\n') : ''));
              } else processPending(selectedIndex, action);
            });
        };
        chapter.onClick = function () { run(function () {
            if (!savePsd.value && !savePdf.value) throw Error('Chọn ít nhất một định dạng lưu: PSD hoặc Photoshop PDF.');
            if (modelBatch.value && alreadyClean.value) throw Error('Bỏ chọn Trang đã clean thủ công để dùng AI clean toàn trang.');
            if (modelBatch.value && selectedEngine().id !== 'baseline') throw Error('Không thể dùng engine đã chọn cùng chế độ mask toàn trang.');
            if (modelBatch.value && reviewAll.value) throw Error('AI clean toàn trang không dùng lựa chọn clean từng vùng. Bỏ chọn kiểm tra/duyệt từng trang để chạy chế độ này.');
            if (!batchCleanOnly.value) options();
            var modelMethods=['ctd','mask','koharu','hybrid'];
            var experimentalClean=modelBatch.value ? {method:modelMethods[maskChoice.selection.index], lama:inpaintMethod()==='lama', inpaint:inpaintMethod(), protect_faces:!!protectFaces.value} : null;
            var parsed = translations(), sources = [], files = false, log = [], folder;
            if (inputFolder) {
                sources = inputFolder.getFiles(function (f) { return f instanceof File && MTA.sourceNameAllowed(f.name); });
                sources.sort(function (a, b) {
                    var aa = decodeURI(a.name).match(/\d+|\D+/g), bb = decodeURI(b.name).match(/\d+|\D+/g);
                    for (var k = 0; k < Math.min(aa.length, bb.length); k++) {
                        var av = /^\d+$/.test(aa[k]) ? Number(aa[k]) : aa[k].toLowerCase();
                        var bv = /^\d+$/.test(bb[k]) ? Number(bb[k]) : bb[k].toLowerCase();
                        if (av < bv) return -1; if (av > bv) return 1;
                    } return aa.length - bb.length;
                }); files = true;
            } else sources = docs.slice(0);
            if (!sources.length) throw Error('Không có trang để xử lý');
            if (!batchCleanOnly.value && sources.length > 1 && !parsed.marked) throw Error('Cả chương cần đánh dấu [PAGE 1], [PAGE 2]… trong bản dịch.');
            var order = [];
            for (var x = 0; x < sources.length; x++) order.push((x+1) + '. ' + decodeURI(sources[x].name) + ' ← bản dịch trang ' + MTA.translationKey(parsed,sources[x].name,x));
            if (!MTA.confirmChapter(order, (aiDetector.value ? 'AI local' : 'OpenCV') + (experimentalClean ? ' | Clean toàn trang: '+maskChoice.selection.text+(' + '+useLama.selection.text) : ''), experimentalClean ? 'Mask toàn trang có thể xóa nhầm tranh; mọi trang cần kiểm tra.' : (reviewAll.value ? 'Kiểm tra mapping từng trang.' : 'Tự động khi khớp mapping; vùng khó để sửa tay.'))) return;
            pendingPages = [];
            folder = MTA.mkdir(outputFolder.fsName);
            var logFile = new File(folder.fsName + '/batch_' + MTA.unique() + '.json');
            var good = 0,reviewPages=0,manualLayers=0,noTranslation=0,withoutWarnings=0,omittedLines=0;
            var batchStarted=(new Date()).getTime();
            for (var j = 0; j < sources.length; j++) {
                var estimate = j ? ' — ước tính còn ' + Math.ceil(((new Date()).getTime()-batchStarted)*(sources.length-j)/j/60000) + ' phút' : '';
                if (!tick('Trang ' + (j+1) + '/' + sources.length + estimate, 100*j/sources.length)) break;
                var pageStarted=(new Date()).getTime();
                var doc = null, ownsDoc = false, s = null;
                try {
                    var sourceKey=MTA.translationKey(parsed,sources[j].name,j);
                    if(!batchCleanOnly.value && parsed.filename_pages && parsed.pages[sourceKey] === undefined){
                        noTranslation++;
                        log.push({page:j+1,source:decodeURI(sources[j].name),ok:true,status:'skipped_no_translation',psd:null,translation_page:sourceKey});
                        continue;
                    }
                    if (files) {
                        for (var opened = 0; opened < app.documents.length; opened++) {
                            try { if (app.documents[opened].fullName.fsName === sources[j].fsName) doc = app.documents[opened]; } catch (_) {}
                        }
                        if (!doc) { doc = app.open(sources[j]); ownsDoc = true; }
                    } else doc = sources[j];
                    var s = detect(doc); s.experimentalClean=experimentalClean;
                    var pageKey=MTA.translationKey(parsed,sources[j].name,j);
                    var pageLines = parsed.pages[pageKey] || [], extraText = s.data.extra_text_regions || 0, needsReview = batchCleanOnly.value ? reviewAll.value : (reviewAll.value || extraText > 0 || pageLines.length !== s.data.regions.length);
                    if(!batchCleanOnly.value && !reviewAll.value && skipMismatch.value && (extraText > 0 || pageLines.length !== s.data.regions.length)){
                        reviewPages++;
                        MTA.write(new File(s.folder.fsName+'/translation_review.json'),MJSON.stringify({source:decodeURI(sources[j].name),translation_page:pageKey,translations:pageLines,manifest:s.manifestPath,engine:s.engine}));
                        var sourcePath = null;
                        try { sourcePath = files ? sources[j].fsName : doc.fullName.fsName; } catch (_) {}
                        var pendingEntry = {page:j+1,source:decodeURI(sources[j].name),source_path:sourcePath,ok:true,status:'review_required',psd:null,detector:s.data.detector,translation_page:pageKey,regions:s.data.regions.length,lines:pageLines.length,manifest:s.manifestPath,experimental_clean:experimentalClean,engine:s.engine};
                        log.push(pendingEntry); pendingPages.push(pendingEntry);
                        continue;
                    }
                    var regionIndex;
                    s.reviewLines=pageLines.slice(0);
                    if (needsReview) review(s, pageLines, batchCleanOnly.value);
                    else {
                        s.mapping = [];
                        for (regionIndex = 0; regionIndex < s.data.regions.length; regionIndex++)
                            s.mapping.push({id: s.data.regions[regionIndex].id, translation: batchCleanOnly.value ? '' : pageLines[regionIndex], clean: true, force: false});
                    }
                    var path = build(s, batchCleanOnly.value, true, false); good++;
                    manualLayers+=s.manualText.length;
                    omittedLines+=s.omittedTranslations.length;
                    var partial=s.manualText.length || s.omittedTranslations.length || s.cleanResult.skipped.length || !!experimentalClean;
                    if(!partial)withoutWarnings++;
                    log.push({page: j+1, source: decodeURI(sources[j].name), ok: true, status:partial?'partial':'processed', psd: s.savedFiles.psd || null, pdf: s.savedFiles.pdf || null, output_color_mode:s.outputColorMode, output_color_profile:s.outputColorProfile, manifest:s.manifestPath, detector:s.data.detector || 'opencv', translation_page: batchCleanOnly.value ? null : pageKey, translation_lines:pageLines.length, unmapped_translation_indexes:s.omittedTranslations, manual_text_ids:s.manualText, clean_result_schema:s.cleanResult.result_schema || null, clean_region_results:s.cleanResult.region_results || [], clean_review_ids:s.cleanResult.review_ids || [], clean_counts:s.cleanResult.counts || null, clean_applied:s.cleanResult.applied, clean_skipped:s.cleanResult.skipped, clean_blocked:s.cleanResult.blocked || {}, clean_skip_reason_codes:s.cleanResult.skip_reason_codes || {}, clean_trace:s.cleanResult.trace || null, clean_mask:s.cleanResult.mask || null, engine_id:s.cleanResult.engine_id || null, engine_version:s.cleanResult.version || null, scan_hardware:s.data.hardware || null, clean_hardware:s.cleanResult.hardware || null, experimental_clean:experimentalClean, clean_mask_pixels:s.cleanResult.mask_pixels || 0, clean_quality:s.cleanResult.quality || null});
                } catch (e) {
                    if (!cancelled && s && /không vừa/.test(String(e.message))) {
                        var failedPath=null;try{failedPath=files?sources[j].fsName:doc.fullName.fsName;}catch(_){}
                        var failedLines=parsed.pages[MTA.translationKey(parsed,sources[j].name,j)] || [];
                        MTA.write(new File(s.folder.fsName+'/translation_review.json'),MJSON.stringify({source:decodeURI(sources[j].name),translations:failedLines,manifest:s.manifestPath,engine:s.engine}));
                        var fitPending={page:j+1,source:decodeURI(sources[j].name),source_path:failedPath,ok:true,status:'review_required',psd:null,
                            manifest:s.manifestPath,regions:s.data.regions.length,lines:failedLines.length,error:String(e.message),experimental_clean:experimentalClean,engine:s.engine};
                        log.push(fitPending);pendingPages.push(fitPending);reviewPages++;
                    } else log.push({page: j+1, source: decodeURI(sources[j].name), ok: false, detector:aiDetector.value?'ai':'opencv', error: e.message});
                    if (cancelled) break;
                } finally {
                    if (ownsDoc && doc) doc.close(SaveOptions.DONOTSAVECHANGES);
                    try { app.purge(PurgeTarget.ALLCACHES); } catch (_) {}
                    if (log.length && log[log.length-1].page === j+1) {
                        log[log.length-1].seconds = Math.round(((new Date()).getTime()-pageStarted)/100)/10;
                        log[log.length-1].ui_version=MTA.uiVersion;
                    }
                    MTA.write(logFile, MJSON.stringify(log));
                }
            }
            state = null;
            pendingLog = logFile;
            pendingButton.text = 'Trang chờ duyệt (' + pendingPages.length + ')';
            tick('Đã lưu ' + good + '/' + sources.length + ' trang; không cảnh báo: '+withoutWarnings+'; có cảnh báo: '+(good-withoutWarnings)+'; trang chờ ghép: '+reviewPages+(experimentalClean?'; chữ hiện cần kiểm tra AI: ':'; chữ ẩn cần clean: ')+manualLayers+'; câu chưa ghép: '+omittedLines+'; thiếu bản dịch: '+noTranslation+'. Log: ' + logFile.fsName, 100);
            alert(status.text);
        }); };
        cancelButton.onClick = function () { cancelled = true; status.text = 'Đang hủy tại điểm an toàn…'; };
        close.onClick = function () { if (!busy) win.close(); };
        win.onClose = function () { if (busy) { cancelled = true; return false; } return true; };
        loadEngines();syncInputs();win.center(); win.show();
    } catch (e) { alert('Manga Typesetter AI: ' + e.message + (e.line ? '\nDòng: ' + e.line : '')); }
    finally {
        app.preferences.rulerUnits = oldRuler; app.preferences.typeUnits = oldType; app.displayDialogs = oldDialogs;
    }
})();
