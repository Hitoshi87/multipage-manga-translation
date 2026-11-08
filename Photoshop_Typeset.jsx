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
        var easyTab=addTab('Tự động (khuyên dùng)');
        var sourceTab=addTab('1. Nguồn & nhận diện'),engineTab=addTab('2. Engine clean');
        var typesetTab=addTab('3. Typeset & xuất'),advancedTab=addTab('4. Thử nghiệm nâng cao');tabs.selection=easyTab;
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
        var leadingAuto = fontRow.add('checkbox', undefined, 'Tự động (Auto)'); leadingAuto.value = true;
        leadingAuto.helpTip = 'Dùng Auto leading của Photoshop để khoảng cách dòng đi theo cỡ chữ khi bạn chỉnh về sau. Bỏ tick để nhập số.';
        var leading = fontRow.add('edittext', undefined, '1.05'); leading.characters = 4;
        leading.helpTip = 'Chỉ dùng khi bỏ tick Tự động.';
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
        var sampleFonts = roleFontRow.add('button', undefined, 'Font comic mẫu');
        var autoRoles = typesetTab.add('checkbox', undefined, 'Tự chọn font theo hình bong bóng (có thể sửa từng vùng)'); autoRoles.value = true;
        var autoSize = typesetTab.add('checkbox', undefined, 'Cỡ chữ lớn tự động theo bubble (tối đa 1,3× cỡ trung vị của trang)');
        autoSize.value = true;
        var uppercaseText = typesetTab.add('checkbox', undefined, 'In hoa chữ khi typeset (không đổi bản dịch đã lưu)');
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
        var controls = [chooseFolder, openSources, page, openText, openTranslations, aiDetector, maskChoice, useLama, detailChoice, hwChoice, previewEngine, testModel, modelBatch, protectFaces, koharuOrder, magiOrder, importResult, check, rtl, lang, presets, font, boxFont, shoutFont, autoRoles, saveFonts, sampleFonts, uppercaseText, autoSize, leadingAuto,
                        minSize, maxSize, leading, translation, setOutput, png, jpg, savePsd, savePdf, pdfLayers, cmykOutput, alreadyClean, engineChoice, reviewAll, batchCleanOnly, skipMismatch, scan, clean, typeset, chapter, pendingButton];
        var activeTaskDialog=null;
        function tick(message, fraction) {
            if (message) status.text = message;
            if (fraction !== undefined) progress.value = fraction;
            win.update();
            if(activeTaskDialog)activeTaskDialog.update();
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
            var textControls=[translation,openText,openTranslations,presets,font,boxFont,shoutFont,minSize,maxSize,leading,autoRoles,saveFonts,sampleFonts,uppercaseText,autoSize,leadingAuto];
            for(var ti=0;ti<textControls.length;ti++)textControls[ti].enabled=p.typeset;
            pendingButton.enabled=pendingPages.length>0;
            engineNote.text=alreadyClean.value?'Chỉ typeset ảnh đã clean; không gọi engine clean.':(modelBatch.value?'Đang dùng công cụ mask toàn trang riêng, không dùng clean từng region.':'Preview và clean dùng engine '+currentEngineId()+'. '+(currentEngineId()==='baseline'?'Baseline giữ các safety gate hiện tại.':(currentEngineId()==='art_draft'?'AI tái tạo nền, kết quả cần kiểm tra; ảnh gốc được giữ.':'Engine kiểm tra mask/artwork; checkbox thử model bên tab 4 không thay đổi engine.')));
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
            var result = {font: fontIds[font.selection.index], fonts: {dialogue:fontIds[font.selection.index], box:fontIds[boxFont.selection.index], shout:fontIds[shoutFont.selection.index]}, automatic: autoRoles.value, uppercase: uppercaseText.value, autoSize: autoSize.value, min: Number(minSize.text), max: Number(maxSize.text), autoLeading: leadingAuto.value === true, leading: leadingAuto.value === true ? 1.05 : Number(leading.text)};
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
            s.manualText=[]; s.layoutFallback=[];s.contrastReview=[];s.layoutReview=[];var layoutInfos=[];
            try {
                app.activeDocument = s.doc;
                copy = s.doc.duplicate(s.doc.name.replace(/\.[^.]+$/, '') + (onlyClean ? ' — CLEAN' : ' — Typeset'));
                if (result.applied.length || (result.full_page && result.mask_pixels > 0)) {
                    // Prefer one layer per bubble; the single page overlay is the fallback.
                    var cleanLayers = 0;
                    if (result.layer_split === 'regions' && result.region_layers && result.region_layers.length)
                        cleanLayers = MTA.addRegionOverlays(copy, result.region_layers, {aiIds: result.art_inpaint_ids || []});
                    s.cleanLayerCount = cleanLayers;
                    if (!cleanLayers) MTA.addOverlay(copy, result.overlay, (result.experimental || (result.art_inpaint_ids && result.art_inpaint_ids.length)) ? 'CLEAN AI PHỤC HỒI NỀN — CẦN KIỂM TRA' : undefined);
                }
                if (!onlyClean) {
                    var group = copy.layerSets.add(); group.name = s.draft ? 'TYPESET — NHÁP CHƯA DUYỆT' : 'TYPESET — Tiếng Việt';
                    // Pass 1 (no layers kept): fit every bubble with a generous cap, then
                    // limit oversized ones to 1.25x the page median for consistent lettering.
                    if (config.autoSize) {
                        var dryConfig = {}, sizes = [];
                        for (var dk in config) dryConfig[dk] = config[dk];
                        dryConfig.dryRun = true; dryConfig.maxCap = config.max * 4;
                        for (var pj = 0; pj < s.mapping.length; pj++) {
                            if (!s.mapping[pj].translation.replace(/\s/g, '')) continue;
                            var pregion = null;
                            for (var pk = 0; pk < s.data.regions.length; pk++) if (s.data.regions[pk].id === s.mapping[pj].id) pregion = s.data.regions[pk];
                            if (!pregion) continue;
                            dryConfig.font = config.fonts[MTA.resolveTextRole(pregion, s.mapping[pj].translation, s.mapping[pj].font_role, config.automatic)];
                            try { MTA.addText(copy, copy, pregion, s.mapping[pj].translation, dryConfig); } catch (_) {}
                            var info = MTA.lastLayout();
                            if (info && info.id === pregion.id) sizes.push(info.size);
                        }
                        config.maxCap = MTA.pageSizeCap(sizes, 1.3, config.min);
                    }
                    for (var j = 0; j < s.mapping.length; j++) {
                        if (!tick('Dàn chữ ' + s.mapping[j].id, 65 + 25 * j / Math.max(1, s.mapping.length))) throw Error('Đã hủy');
                        if (!s.mapping[j].translation.replace(/\s/g, '')) continue;
                        var region = null;
                        for (var k = 0; k < s.data.regions.length; k++) if (s.data.regions[k].id === s.mapping[j].id) region = s.data.regions[k];
                        if (!region) throw Error('Không tìm thấy vùng ' + s.mapping[j].id);
                        var role = MTA.resolveTextRole(region, (s.mapping[j].display || s.mapping[j].translation), s.mapping[j].font_role, config.automatic);
                        config.font = config.fonts[role];
                        var textLayer;
                        try { textLayer = MTA.addText(copy, group, region, (s.mapping[j].display || s.mapping[j].translation), config); var placed=MTA.lastLayout(); if(placed){placed.layer=textLayer;layoutInfos.push(placed);} }
                        catch (fitError) {
                            if (!s.visibleFallback && !result.experimental && !s.draft) throw fitError;
                            var safe = region.safe;
                            textLayer = MTA.addFallbackText(copy, group, s.mapping[j].translation, config,
                                [safe[0]+safe[2]/2, safe[1]+safe[3]/2], '[CẦN CHỈNH KHUNG] ' + region.id, Math.max(safe[2], copy.width.as('px')*.16));
                            s.layoutFallback.push({id:region.id, reason:String(fitError.message || fitError)});
                        }
                        textLayer.name = '[' + ({dialogue:'THOẠI',box:'Ô VUÔNG',shout:'HÉT'})[role] + '] ' + (region.merged_suspect ? '[NGHI GỘP Ô — CẦN TÁCH] ' : '') + textLayer.name;
                        if(result.art_inpaint_ids){for(var ai=0;ai<result.art_inpaint_ids.length;ai++)if(result.art_inpaint_ids[ai]===region.id){textLayer.name='[AI PHỤC HỒI NỀN — CẦN DUYỆT] '+textLayer.name;if(!MTA.addWhiteStroke(copy,textLayer,Math.max(1,Math.min(4,copy.width.as('px')/480))))s.contrastReview.push(region.id);break;}}
                        if(s.draft && s.draftReview){for(var dri=0;dri<s.draftReview.length;dri++)if(s.draftReview[dri].region_id===region.id){var dr=s.draftReview[dri];if(dr.flags.length || dr.source_status!=='verified')textLayer.name='[NHÁP CẦN DUYỆT] '+textLayer.name;break;}}
                        var wasCleaned=false;
                        for(var cleanedIndex=0;cleanedIndex<result.applied.length;cleanedIndex++) if(result.applied[cleanedIndex]===region.id) wasCleaned=true;
                        if (!wasCleaned && !alreadyClean.value) {
                            textLayer.name = (result.experimental ? '[KIỂM TRA CLEAN AI — CHỮ HIỆN] ' : (s.visibleFallback ? '[CẦN CLEAN — CHỮ HIỆN] ' : '[CẦN CLEAN — CHỮ ẨN] ')) + textLayer.name;
                            if (!s.visibleFallback && !result.experimental) textLayer.visible = false;
                            s.manualText.push(region.id);
                        }
                    }
                    // Flag cramped or sparse lettering so review starts there.
                    var flagged=MTA.layoutFlags(layoutInfos,{min:config.min,max:config.max});
                    for(var fi=0;fi<flagged.length;fi++){
                        for(var li2=0;li2<layoutInfos.length;li2++)if(layoutInfos[li2].id===flagged[fi].id){layoutInfos[li2].layer.name='[RÀ SOÁT CHỮ: '+flagged[fi].flags.join('+')+'] '+layoutInfos[li2].layer.name;break;}
                        s.layoutReview.push(flagged[fi]);
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
                var saved = save ? MTA.saveCopy(copy, outputFolder, s.doc.name, {psd:savePsd.value, pdf:savePdf.value, pdfLayers:pdfLayers.value, png: png.value, jpg: jpg.value, cmykJpeg:cmykOutput.value}, onlyClean ? 'clean' : (s.draft?'draft':'typeset'), s.savedFiles) : null;
                if (!keepOpen) { copy.close(SaveOptions.DONOTSAVECHANGES); copy = null; }
                tick((s.manualText.length ? 'Vùng cần clean/duyệt: '+s.manualText.length+'. ' : '') + (saved ? 'Đã lưu: ' + saved.fsName : 'Đã tạo bản sao CLEAN') + MTA.cleanResultSummary(result), 100);
                return saved ? saved.fsName : '';
            } catch (e) { if (copy) copy.close(SaveOptions.DONOTSAVECHANGES); throw e; }
        }
        // Shared volume pipeline: scan -> OCR -> translate -> clean -> typeset for a list of pages.
        // cfg: project, profile, title, note(text), label, [engine], [folder], [indices], [output].
        function runVolume(cfg){
            var project=cfg.project;cfg.label=cfg.label||'';
            function loadProject(){return rpc({operation:'translation_load',project:project});}
            function latestRun(data){if(!data.runs.length)throw Error('Chưa có lượt dịch');return data.runs[data.runs.length-1];}
            var srcFolder=cfg.folder||inputFolder,savedOutput=outputFolder,rep2=null,logFile=null,log=[],failed=[];
            if(cfg.output)outputFolder=cfg.output;
            try{
                if(!lang.selection || !/^jpn/.test(lang.selection.text))throw Error('Hãy chọn OCR Nhật trước khi chạy volume.');
                if(!savePsd.value && !savePdf.value)throw Error('Hãy bật lưu PSD hoặc PDF ở phần xuất.');
                var chosen=cfg.engine||selectedEngine();rpc({operation:'translation_profile',project:project,profile:cfg.profile});
                var sources=srcFolder?srcFolder.getFiles(function(f){return f instanceof File && MTA.sourceNameAllowed(f.name);}):docs.slice(0);
                if(!sources.length)throw Error('Không có trang để xử lý.');
                if(srcFolder)sources.sort(function(a,b){var aa=decodeURI(a.name).match(/\d+|\D+/g),bb=decodeURI(b.name).match(/\d+|\D+/g);for(var z=0;z<Math.min(aa.length,bb.length);z++){var av=/^\d+$/.test(aa[z])?Number(aa[z]):aa[z].toLowerCase(),bv=/^\d+$/.test(bb[z])?Number(bb[z]):bb[z].toLowerCase();if(av<bv)return -1;if(av>bv)return 1;}return aa.length-bb.length;});
                var names={};for(var ck=0;ck<sources.length;ck++){var nm=decodeURI(sources[ck].name);if(names[nm])throw Error('Tên trang bị trùng: '+nm);names[nm]=true;}
                var order=[];if(cfg.indices){for(var oi=0;oi<cfg.indices.length;oi++)if(cfg.indices[oi]>=0&&cfg.indices[oi]<sources.length)order.push(cfg.indices[oi]);}else{for(var oj=0;oj<sources.length;oj++)order.push(oj);}
                for(var ox=0;ox<order.length;ox++){
                    var ix=order[ox];if(!tick(cfg.label+'Đọc chữ trang '+(ox+1)+'/'+order.length,5+10*ox/order.length))throw Error('Đã hủy');var doc=null,own=false;
                    try{doc=srcFolder?app.open(sources[ix]):sources[ix];own=!!srcFolder;var existing=null,data=loadProject();
                        for(var pi=0;pi<data.pages.length;pi++)if(data.pages[pi].page_id===decodeURI(doc.name))existing=data.pages[pi];
                        if(existing){if(existing.ordinal!==ix+1)throw Error('Thứ tự trang đã đổi; hãy tạo project mới hoặc index lại.');var tmp=MTA.mkdir(root.fsName+'/work/pages/'+MTA.unique());var snap=MTA.snapshot(doc,tmp);rpc({operation:'translation_verify_page',manifest:existing.manifest,snapshot:snap.fsName});}
                        else{var scanned=detect(doc);rpc({operation:'translation_index',project:project,manifest:scanned.manifestPath,page_id:decodeURI(doc.name),ordinal:ix+1});}
                        rpc({operation:'translation_auto_ocr_page',project:project,page_id:decodeURI(doc.name)});
                    }finally{if(own&&doc)doc.close(SaveOptions.DONOTSAVECHANGES);}
                }
                // Autopilot: auto-exclude non-dialogue, retry transient errors with backoff,
                // park groups that keep failing; one slice per request (the bridge waits 180 s).
                // Optional: infer characters and address terms once from the first pages (hints, not facts).
                try{tick(cfg.label+'Phân tích nhân vật và xưng hô…',28);rpc({operation:'translation_cast_analyse',project:project});}
                catch(ce){if(/hủy/.test(String(ce.message)))throw ce;}
                var run=null,failed=[],report=null,autoExcluded=0;
                do{
                    if(!tick(cfg.label+'Dịch tự động'+(report?': '+report.completed+'/'+report.total+' nhóm':'…'),30))throw Error('Đã hủy');
                    var autoRequest={operation:'translation_autopilot',project:project,budget_seconds:140};
                    if(run)autoRequest.run_id=run.id;
                    report=rpc(autoRequest).data;run={id:report.run_id};
                    if(report.auto_excluded)autoExcluded=report.auto_excluded.count;
                }while(!report.done && !report.aborted);
                for(var pk=0;pk<report.parked.length;pk++)failed.push({group_id:report.parked[pk].group_id,error:report.parked[pk].error});
                if(report.aborted)failed.push({stage:'autopilot',error:report.abort_reason});
                // Tighten only the lines that would be lettered cramped (non-fatal if it cannot run).
                try{
                    var shortened=0,sr=null;
                    do{
                        if(!tick(cfg.label+'Rút gọn dòng quá dài'+(shortened?' ('+shortened+')':'…'),45))throw Error('Đã hủy');
                        sr=rpc({operation:'translation_auto_shorten',project:project,run_id:run.id,budget_seconds:140}).data;shortened+=sr.shortened.length;
                    }while(!sr.done);
                }catch(se){if(/hủy/.test(String(se.message)))throw se;failed.push({stage:'auto_shorten',error:String(se.message||se)});}
                var current=latestRun(loadProject());
                for(var qr=0;qr<current.groups.length;qr++){
                    var qg=current.groups[qr],needsQuote=false;if(qg.status!=='completed')continue;
                    for(var qv=0;qv<qg.results.length;qv++){var qt=qg.results[qv].semantic_translation.toLowerCase();if(/(?:anh|em|chị|cô|chú|bác|ông|bà)\s+yêu|yêu\s+(?:anh|em|chị|cô|chú|bác|ông|bà)/.test(qt))needsQuote=true;}
                    if(needsQuote){if(!tick('Rà xưng hô nhóm '+(qr+1)+'/'+current.groups.length,55))throw Error('Đã hủy');try{rpc({operation:'translation_repair_quote',project:project,run_id:run.id,group_id:qg.id});}catch(qe){failed.push({group_id:qg.id,stage:'quote_retry',error:String(qe.message||qe)});}}
                }
                current=latestRun(loadProject());var remaining=[];for(var rg=0;rg<current.groups.length;rg++)if(current.groups[rg].status!=='completed')remaining.push(current.groups[rg].id);
                var maps=rpc({operation:'translation_draft_mapping',project:project,run_id:run.id}).data.pages,log=[];
                for(var bx=0;bx<order.length;bx++){
                    var bi=order[bx];if(!tick(cfg.label+'Xoá chữ gốc và chèn chữ trang '+(bx+1)+'/'+order.length,65+30*bx/order.length))throw Error('Đã hủy');var d=null,owned=false;
                    try{d=srcFolder?app.open(sources[bi]):sources[bi];owned=!!srcFolder;var found=null;for(var mi=0;mi<maps.length;mi++)if(maps[mi].page_id===decodeURI(d.name))found=maps[mi];
                        if(!found)throw Error('Thiếu mapping trang');var mf=new File(found.manifest),saved=MJSON.parse(MTA.read(mf));MTA.validateManifest(saved,d.width.as('px'),d.height.as('px'));
                        var s={doc:d,folder:mf.parent,manifestPath:mf.fsName,data:saved,mapping:found.mapping,reviewLines:[],allowOmitted:true,offline:false,engine:chosen,draft:true,draftReview:found.review};
                        build(s,false,true,false);var priority=[];for(var pr=0;pr<found.review.length;pr++)if(found.review[pr].priority==='high')priority.push(found.review[pr]);
                        log.push({page:found.page_id,manifest:found.manifest,status:'draft',engine:chosen,required:found.required_count,mapped:found.mapping.length,priority_review:priority,review:found.review,clean_skipped:s.cleanResult.skipped,clean_applied:(s.cleanResult.applied||[]).length,clean_layers:s.cleanLayerCount||0,art_inpaint_review:s.cleanResult.art_inpaint_ids || [],manual_text:s.manualText,layout_fallback:s.layoutFallback,contrast_review:s.contrastReview,files:s.savedFiles});
                    }catch(be){log.push({page:decodeURI(sources[bi].name),status:'failed',error:String(be.message||be)});}
                    finally{if(owned&&d)d.close(SaveOptions.DONOTSAVECHANGES);}
                    var logFile=new File(outputFolder.fsName+'/draft_'+run.id+'.json');MTA.write(logFile,MJSON.stringify({run_id:run.id,project:project,auto_excluded:autoExcluded,blocked_source_ids:current.blocked_ids,remaining_groups:remaining,translation_failures:failed,pages:log}));
                }
                var reportNote='';
                try{
                    var rep2=rpc({operation:'translation_report',project:project,log:logFile.fsName,title:cfg.title}).data;
                    reportNote=' Báo cáo: '+rep2.summary.ok+' trang ổn, '+rep2.summary.look+' nên xem, '+rep2.summary.fix+' cần sửa.';
                    if(cfg.openReport!==false){try{(new File(rep2.html)).execute();}catch(_){}}
                }catch(re){reportNote=' (Không tạo được báo cáo: '+String(re.message||re)+')';}
                cfg.note('Đã xuất bản nháp; kiểm tra báo cáo '+logFile.fsName+'. Nhóm lỗi: '+failed.length+'; OCR/dịch chưa được tự xác nhận.'+reportNote);
                return {log:log,logFile:logFile,failed:failed,summary:rep2?rep2.summary:null,html:rep2?rep2.html:null,engine:chosen,autoExcluded:autoExcluded};
            }finally{outputFolder=savedOutput;}
        }

        // ---------- Rà soát nhanh: fix the few flagged bubbles without hunting through layers ----------
        // Items come from the report queue (urgent first). Each can be opened (page + layer selected),
        // re-lettered with edited text, nudged or resized, then marked done; progress is remembered.
        function latestDraftLog(folder){
            var logs=folder.exists?folder.getFiles('draft_*.json'):[];
            if(!logs.length)return null;
            logs.sort(function(a,b){return b.modified.getTime()-a.modified.getTime();});
            return logs[0];
        }
        var reviewDoc=null,reviewDocPath=null;
        // Save back to the file the page came from: a layered Photoshop PDF is saved as a layered PDF again.
        function reviewSave(doc){
            var name=String(doc.name);
            if(/\.pdf$/i.test(name)){var o=MTA.pdfSaveOptions({pdfLayers:true});doc.saveAs(doc.fullName,o,false,Extension.LOWERCASE);}
            else doc.save();
        }
        function reviewFocus(item){
            var itemFile=item.file||item.psd;
            if(!itemFile)throw Error('Mục này chưa có file Photoshop (trang chưa xuất được).');
            var f=new File(itemFile);if(!f.exists)throw Error('Không thấy file: '+itemFile);
            if(reviewDoc && reviewDocPath!==f.fsName){
                // Leave the previous page saved and closed so hundreds of pages do not pile up in memory.
                try{reviewSave(reviewDoc);reviewDoc.close(SaveOptions.DONOTSAVECHANGES);}catch(_){}
                reviewDoc=null;reviewDocPath=null;
            }
            var doc=null;
            for(var di=0;di<app.documents.length;di++){try{if(app.documents[di].fullName.fsName===f.fsName)doc=app.documents[di];}catch(_){}}
            if(!doc){doc=app.open(f);reviewDoc=doc;reviewDocPath=f.fsName;}
            app.activeDocument=doc;
            var layers=item.region?MTA.findRegionLayers(doc,item.region):{text:null,clean:null};
            if(layers.text)doc.activeLayer=layers.text;else if(layers.clean)doc.activeLayer=layers.clean;
            try{app.runMenuItem(charIDToTypeID('FtOn'));}catch(_){}
            return {doc:doc,text:layers.text,clean:layers.clean};
        }
        function reviewRelayout(item, newText, runId, project){
            var at=reviewFocus(item);
            if(!at.text)throw Error('Không tìm thấy layer chữ của '+item.region+'. Có thể bubble này chưa được chèn chữ.');
            if(!item.manifest)throw Error('Thiếu dữ liệu vùng chữ (manifest).');
            var data=MJSON.parse(MTA.read(new File(item.manifest))),region=null,ri;
            for(ri=0;ri<data.regions.length;ri++)if(data.regions[ri].id===item.region)region=data.regions[ri];
            if(!region)throw Error('Không tìm thấy vùng '+item.region+' trong dữ liệu trang.');
            var old=at.text,group=old.parent;
            if(!group || group.typename!=='LayerSet')throw Error('Layer chữ không nằm trong nhóm TYPESET.');
            var cfg=options(at.doc),role=/\[(Ô VUÔNG)\]/.test(old.name)?'box':(/\[(HÉT)\]/.test(old.name)?'shout':'dialogue');
            cfg.font=cfg.fonts[role];
            var cut=old.name.indexOf(item.region+' |'),prefix=cut>0?old.name.substr(0,cut):'';
            var created=MTA.addText(at.doc,group,region,newText,cfg);
            created.name=prefix+item.region+' | '+newText.substr(0,40).replace(/[\r\n]/g,' ');
            created.visible=old.visible;
            if(/AI PHỤC HỒI/.test(old.name))MTA.addWhiteStroke(at.doc,created,Math.max(1,Math.min(4,at.doc.width.as('px')/480)));
            old.remove();
            reviewSave(at.doc);
            // Keep the correction in the project so a re-run does not undo it (non-fatal).
            try{if(item.segment_id&&runId)rpc({operation:'translation_accept',project:project,run_id:runId,edits:[{id:item.segment_id,text:newText}]});}catch(_){}
        }
        function openReview(){
            var logFile=latestDraftLog(outputFolder);
            if(!logFile){alert('Chưa có kết quả để rà soát. Hãy chạy cả tập trước.');return;}
            var logData=MJSON.parse(MTA.read(logFile));
            var project=logData.project||(outputFolder.fsName+'/project.json');
            var stateFile=new File(outputFolder.fsName+'/review_state.json');
            var queue=rpc({operation:'review_queue',project:project,log:logFile.fsName,state:stateFile.fsName});
            var d=new Window('dialog','Rà soát nhanh');d.orientation='column';d.alignChildren='fill';
            var head=d.add('statictext',undefined,'');head.characters=88;
            var body=d.add('group');body.orientation='row';body.alignChildren='top';
            var list=body.add('listbox',undefined,[],{multiselect:false});list.preferredSize=[340,330];
            var right=body.add('group');right.orientation='column';right.alignChildren='fill';
            var why=right.add('statictext',undefined,'',{multiline:true});why.preferredSize=[420,62];
            right.add('statictext',undefined,'Câu đang chèn (sửa trực tiếp rồi bấm Áp dụng):');
            var textBox=right.add('edittext',undefined,'',{multiline:true,scrolling:true});textBox.preferredSize=[420,86];
            var srcLine=right.add('statictext',undefined,'',{multiline:true});srcLine.preferredSize=[420,38];
            var row1=right.add('group');
            var openBtn=row1.add('button',undefined,'Mở trang và chọn layer');
            var applyBtn=row1.add('button',undefined,'Áp dụng lời sửa');
            var row2=right.add('group');row2.add('statictext',undefined,'Chỉnh nhanh:');
            var bLeft=row2.add('button',undefined,'Trái'),bRight=row2.add('button',undefined,'Phải'),bUp=row2.add('button',undefined,'Lên'),bDown=row2.add('button',undefined,'Xuống');
            var bBig=row2.add('button',undefined,'Chữ to hơn'),bSmall=row2.add('button',undefined,'Chữ nhỏ hơn');
            var row3=right.add('group');
            var doneBtn=row3.add('button',undefined,'Đã ổn, mục tiếp theo');
            var skipLook=row3.add('button',undefined,'Bỏ qua các mục "nên xem"');
            var msg=d.add('statictext',undefined,'');msg.characters=88;
            var bottom=d.add('group');bottom.alignment='right';bottom.add('button',undefined,'Đóng',{name:'ok'});
            var shown=[];
            function current(){return list.selection?shown[list.selection.index]:null;}
            function refill(keepKey){
                var keep=keepKey,open=0,i,it,idx=0;
                list.removeAll();shown=[];
                for(i=0;i<queue.items.length;i++){it=queue.items[i];if(it.done)continue;open++;shown.push(it);
                    list.add('item',(it.severity==='fix'?'[SỬA] ':'[XEM] ')+'Trang '+it.page+(it.region?' · '+it.region:'')+' — '+(it.reasons[0]||''));
                    if(keep&&it.key===keep)idx=shown.length-1;}
                head.text=open?('Còn '+open+' mục cần rà soát. [SỬA] làm trước, [XEM] chỉ cần nhìn qua.'):'Hết rồi! Không còn mục nào cần rà soát.';
                if(shown.length){list.selection=Math.min(idx,shown.length-1);}else{why.text='';textBox.text='';srcLine.text='';}
            }
            list.onChange=function(){var it=current();if(!it)return;why.text=it.reasons.join('\n');textBox.text=it.vi||'';srcLine.text=it.jp?'Gốc: '+it.jp:'';msg.text='';};
            function guard(fn){try{fn();}catch(e){msg.text='Lỗi: '+String(e.message||e);}}
            function layerStep(doc){return Math.max(2,Math.round(doc.width.as('px')/240));}
            function move(dx,dy){guard(function(){var it=current();if(!it)return;var at=reviewFocus(it);var l=at.text||at.clean;if(!l)throw Error('Không tìm thấy layer để chỉnh.');var k=layerStep(at.doc);l.translate(UnitValue(dx*k,'px'),UnitValue(dy*k,'px'));reviewSave(at.doc);msg.text='Đã chỉnh vị trí.';});}
            function scale(pct){guard(function(){var it=current();if(!it)return;var at=reviewFocus(it);if(!at.text)throw Error('Không tìm thấy layer chữ.');at.text.resize(pct,pct,AnchorPosition.MIDDLECENTER);reviewSave(at.doc);msg.text='Đã đổi cỡ chữ.';});}
            bLeft.onClick=function(){move(-1,0);};bRight.onClick=function(){move(1,0);};bUp.onClick=function(){move(0,-1);};bDown.onClick=function(){move(0,1);};
            bBig.onClick=function(){scale(106);};bSmall.onClick=function(){scale(94);};
            openBtn.onClick=function(){guard(function(){var it=current();if(!it)return;var at=reviewFocus(it);msg.text=at.text?'Đã mở trang và chọn layer chữ '+it.region+'.':'Đã mở trang (không thấy layer chữ riêng của vùng này).';});};
            applyBtn.onClick=function(){guard(function(){var it=current();if(!it)return;var t=textBox.text.replace(/^\s+|\s+$/g,'');if(!t)throw Error('Câu trống.');reviewRelayout(it,t,queue.run_id,project);it.vi=t;msg.text='Đã chèn lại bằng lời mới và lưu PSD.';});};
            function markDone(items){
                var keys=[],i;for(i=0;i<items.length;i++){items[i].done=true;keys.push(items[i].key);}
                rpc({operation:'review_mark',state:stateFile.fsName,keys:keys,status:'done'});
            }
            doneBtn.onClick=function(){guard(function(){var it=current();if(!it)return;var at=null;if(reviewDoc){try{reviewSave(reviewDoc);}catch(_){}}markDone([it]);refill();});};
            skipLook.onClick=function(){guard(function(){var rest=[],i;for(i=0;i<queue.items.length;i++)if(!queue.items[i].done&&queue.items[i].severity!=='fix')rest.push(queue.items[i]);if(!rest.length){msg.text='Không có mục "nên xem" nào.';return;}markDone(rest);refill();});};
            refill();
            d.show();
            if(reviewDoc){try{reviewSave(reviewDoc);}catch(_){}}
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
            var values = [[10, 32, 1.05], [12, 28, 1.2], [18, 52, 1.05]][presets.selection.index];
            minSize.text = values[0]; maxSize.text = values[1]; leading.text = values[2];
            var preferred = ['ArialMT', 'Arial-ItalicMT', 'Arial-BoldMT'][presets.selection.index];
            for (var f = 0; f < fontIds.length; f++) if (fontIds[f] === preferred) font.selection = f;
        };
        saveFonts.onClick = function () { run(function () {
            MTA.mkdir(fontSettingsFile.parent.fsName);
            MTA.write(fontSettingsFile, MJSON.stringify({dialogue:fontIds[font.selection.index], box:fontIds[boxFont.selection.index], shout:fontIds[shoutFont.selection.index], automatic:autoRoles.value}));
            tick('Đã lưu ba font để dùng lần sau.');
        }); };
        sampleFonts.onClick = function () {
            var ids=['Itim-Regular','PatrickHand-Regular','Bangers-Regular'], present=[];
            for(var si=0;si<ids.length;si++){
                var ok=false;for(var sj=0;sj<fontIds.length;sj++)if(fontIds[sj]===ids[si])ok=true;
                if(!ok)present.push(ids[si]);
            }
            if(present.length){alert('Hãy cài các font mẫu và khởi động lại Photoshop: '+present.join(', '));return;}
            chooseFontById(font,ids[0]);chooseFontById(boxFont,ids[1]);chooseFontById(shoutFont,ids[2]);
            uppercaseText.value=true;leading.text='1.08';
            status.text='Đã chọn font comic mẫu; kiểm tra từng vùng trước khi xuất.';
        };
        chooseFolder.onClick = function () {
            var selected = Folder.selectDialog('Chọn thư mục chứa JPG, PNG, PSD');
            if (selected) { inputFolder = selected; sourceInfo.text = selected.fsName + ' (dùng cho cả chương)'; }
        };
        openSources.onClick = function () { inputFolder = null; sourceInfo.text = docs.length + ' tài liệu đang mở'; };
        setOutput.onClick = function () { var f = Folder.selectDialog('Thư mục lưu file kết quả'); if (f) { outputFolder = f; outInfo.text = f.fsName; restoreLatestQueue(); } };
        check.onClick = function () { run(function () { var r = rpc({operation: 'doctor'}); alert(MJSON.stringify(r)); }); };
        var translationSetup = sourceTools.add('button', undefined, 'Dịch AI / project');
        controls.push(translationSetup);
        translationSetup.onClick = function () { run(function () {
            var projectFile=File.saveDialog('Chọn hoặc tạo project dịch (.json)', '*.json');
            if(!projectFile)return;
            var project=projectFile.fsName, stored=rpc({operation:'translation_load',project:project});
            var prior=stored.profiles.length ? stored.profiles[stored.profiles.length-1].values : {};
            var dlg=new Window('dialog','Dịch Nhật → Việt — '+projectFile.name);dlg.orientation='column';dlg.alignChildren='fill';
            dlg.add('statictext',undefined,'OCR/ngữ cảnh được gửi tới API; nếu bật vision, ảnh truyện cũng được gửi. API key lấy từ môi trường Photoshop.');
            function field(label,value,multi){
                dlg.add('statictext',undefined,label);
                var e=dlg.add('edittext',undefined,value || '',multi?{multiline:true,scrolling:true}:{});
                e.preferredSize=multi?[700,45]:[700,22];return e;
            }
            var series=field('Tên bộ truyện',prior.series_name,false);
            var general=field('Prompt chung / bối cảnh bộ truyện',prior.general_prompt,true);
            var style=field('Văn phong tiếng Việt',prior.style_prompt || 'Tự nhiên, sát nghĩa.',true);
            var localization=field('Quy tắc Việt hóa',prior.localization_policy,true);
            var glossary=field('Glossary / nhân vật',prior.glossary,true);
            var url=field('API base URL',prior.base_url || 'https://api.vilao.ai/v1',false);
            var model=field('Model ID',prior.model || 'deepseek-ai/deepseek-v4.1-flash-1017',false);
            var opts=dlg.add('group');opts.add('statictext',undefined,'Biến API key:');
            var keyEnv=opts.add('edittext',undefined,prior.key_env || 'MANGA_TRANSLATION_API_KEY');keyEnv.characters=25;
            opts.add('statictext',undefined,'Tokens:');var tokens=opts.add('edittext',undefined,String(prior.max_tokens || 4096));tokens.characters=6;
            opts.add('statictext',undefined,'Nhóm:');var groupSize=opts.add('edittext',undefined,String(prior.group_size || 20));groupSize.characters=4;
            opts.add('statictext',undefined,'Ký tự đầu vào:');var inputLimit=opts.add('edittext',undefined,String(prior.max_input_chars || 24000));inputLimit.characters=6;
            opts.add('statictext',undefined,'Câu trước:');var contextLimit=opts.add('edittext',undefined,String(prior.context_segments===undefined?2:prior.context_segments));contextLimit.characters=3;
            var pricing=dlg.add('group');pricing.add('statictext',undefined,'Timeout (giây):');var timeout=pricing.add('edittext',undefined,String(prior.timeout || 90));timeout.characters=4;
            pricing.add('statictext',undefined,'Retry:');var retries=pricing.add('edittext',undefined,String(prior.retries===undefined?1:prior.retries));retries.characters=3;
            pricing.add('statictext',undefined,'Giá / triệu token vào:');var priceIn=pricing.add('edittext',undefined,prior.input_price_per_million===null || prior.input_price_per_million===undefined?'':String(prior.input_price_per_million));priceIn.characters=6;
            pricing.add('statictext',undefined,'ra:');var priceOut=pricing.add('edittext',undefined,prior.output_price_per_million===null || prior.output_price_per_million===undefined?'':String(prior.output_price_per_million));priceOut.characters=6;
            var capabilities=dlg.add('group');var jsonMode=capabilities.add('checkbox',undefined,'API hỗ trợ JSON mode');jsonMode.value=!!prior.json_mode;
            capabilities.add('statictext',undefined,'Thinking:');var thinking=capabilities.add('dropdownlist',undefined,['default','disabled','enabled']);
            thinking.selection=prior.thinking==='disabled'?1:(prior.thinking==='enabled'?2:0);
            capabilities.add('statictext',undefined,'Ảnh:');var vision=capabilities.add('dropdownlist',undefined,['off','target_crop','page']);
            vision.selection=prior.vision_mode==='target_crop'?1:(prior.vision_mode==='page'?2:0);
            vision.helpTip='Chỉ bật nếu provider hỗ trợ ảnh. Crop có thể chứa nội dung lân cận; page gửi cả trang và có thể lộ diễn biến.';
            var autoAccept=dlg.add('checkbox',undefined,'Tự chấp nhận câu không có flag sau QA kỹ thuật (không kiểm chứng nghĩa)');autoAccept.value=!!prior.auto_accept;
            var action=dlg.add('group');
            var saveProfile=action.add('button',undefined,'Lưu profile');var previewPrompt=action.add('button',undefined,'Xem prompt');var previewGroup=action.add('button',undefined,'Xem nhóm');var sampleProfile=action.add('button',undefined,'Mẫu Mayonaka');
            var indexPages=action.add('button',undefined,'Scan / index trang');var newRun=action.add('button',undefined,'Tạo lượt mới');var runTranslation=action.add('button',undefined,'Dịch / tiếp tục');
            var editOcr=action.add('button',undefined,'Sửa OCR');var reviewTranslation=action.add('button',undefined,'Duyệt câu');var applyPage=action.add('button',undefined,'Dùng trang đang mở');
            var draftReview=dlg.add('button',undefined,'Xem bản dịch nháp trang đang mở (chưa duyệt)');
            var oneClick=dlg.add('button',undefined,'Chạy volume: scan → OCR → dịch → PSD nháp');
            oneClick.helpTip='Xử lý các trang đã mở hoặc thư mục ảnh; tự lưu checkpoint, không tự xác nhận OCR hay bản dịch. Chữ chưa clean được giữ dạng layer ẩn; chữ không vừa có layer dự phòng và cảnh báo.';
            var stopVolume=dlg.add('button',undefined,'Dừng tại điểm an toàn');stopVolume.enabled=false;
            action.add('button',undefined,'Đóng',{name:'cancel'});
            var note=dlg.add('statictext',undefined,'',{multiline:true});note.preferredSize=[700,44];
            function profile(){return {series_name:series.text,general_prompt:general.text,style_prompt:style.text,localization_policy:localization.text,glossary:glossary.text,base_url:url.text,model:model.text,key_env:keyEnv.text,max_tokens:Number(tokens.text),group_size:Number(groupSize.text),max_input_chars:Number(inputLimit.text),context_segments:Number(contextLimit.text),timeout:Number(timeout.text),retries:Number(retries.text),input_price_per_million:priceIn.text?Number(priceIn.text):null,output_price_per_million:priceOut.text?Number(priceOut.text):null,json_mode:jsonMode.value,thinking:thinking.selection.text,vision_mode:vision.selection.text,auto_accept:autoAccept.value};}
            function loadProject(){return rpc({operation:'translation_load',project:project});}
            function latestRun(data){if(!data.runs.length)throw Error('Chưa có lượt dịch');return data.runs[data.runs.length-1];}
            var volumeRunning=false;
            stopVolume.onClick=function(){cancelled=true;note.text='Đang dừng tại điểm an toàn…';};
            dlg.onClose=function(){if(volumeRunning){cancelled=true;return false;}return true;};
            oneClick.onClick=function(){if(volumeRunning)return;volumeRunning=true;cancelled=false;activeTaskDialog=dlg;oneClick.enabled=false;draftReview.enabled=false;action.enabled=false;stopVolume.enabled=true;try{
                runVolume({project:project,profile:profile(),title:'Báo cáo: '+(series.text||'bộ truyện'),note:function(t){note.text=t;}});
            }catch(e){alert(e.message);}finally{volumeRunning=false;activeTaskDialog=null;oneClick.enabled=true;draftReview.enabled=true;action.enabled=true;stopVolume.enabled=false;cancelled=false;dlg.update();}};
            saveProfile.onClick=function(){try{rpc({operation:'translation_profile',project:project,profile:profile()});note.text='Đã lưu profile theo revision.';}catch(e){alert(e.message);}};
            sampleProfile.onClick=function(){try{var p=rpc({operation:'translation_preset',name:'mayonaka_sample'});series.text=p.series_name;general.text=p.general_prompt;style.text=p.style_prompt;localization.text=p.localization_policy;glossary.text=p.glossary;note.text='Đã điền mẫu từ trang 04–07; kiểm tra rồi bấm Lưu profile. Không tự tạo canon.';}catch(e){alert(e.message);}};
            previewPrompt.onClick=function(){try{
                var p=rpc({operation:'translation_preview_prompt',project:project,profile:profile()});
                var d=new Window('dialog','Prompt đã ghép');var t=d.add('edittext',undefined,p.prompt,{multiline:true,scrolling:true,readonly:true});t.preferredSize=[700,500];d.add('button',undefined,'Đóng',{name:'ok'});d.show();
            }catch(e){alert(e.message);}};
            previewGroup.onClick=function(){try{
                var run=latestRun(loadProject()),selected=null;
                for(var n=0;n<run.groups.length;n++)if(run.groups[n].status!=='completed'){selected=run.groups[n];break;}
                if(!selected && run.groups.length)selected=run.groups[0];if(!selected)throw Error('Lượt này không có nhóm.');
                var p=rpc({operation:'translation_preview_group',project:project,run_id:run.id,group_id:selected.id});
                var d=new Window('dialog','Prompt + dữ liệu nhóm');var t=d.add('edittext',undefined,'SYSTEM:\n'+p.system+'\n\nUSER JSON:\n'+MJSON.stringify(p.payload)+'\n\nKý tự: '+p.input_chars+'; context cũ bị giới hạn: '+p.omitted_context_count,{multiline:true,scrolling:true,readonly:true});t.preferredSize=[700,500];d.add('button',undefined,'Đóng',{name:'ok'});d.show();
            }catch(e){alert(e.message);}};
            indexPages.onClick=function(){try{
                var sources=inputFolder?inputFolder.getFiles(function(f){return f instanceof File && MTA.sourceNameAllowed(f.name);}):docs.slice(0);
                if(!sources.length)throw Error('Không có trang');
                if(inputFolder)sources.sort(function(a,b){var aa=decodeURI(a.name).match(/\d+|\D+/g),bb=decodeURI(b.name).match(/\d+|\D+/g);for(var z=0;z<Math.min(aa.length,bb.length);z++){var av=/^\d+$/.test(aa[z])?Number(aa[z]):aa[z].toLowerCase(),bv=/^\d+$/.test(bb[z])?Number(bb[z]):bb[z].toLowerCase();if(av<bv)return -1;if(av>bv)return 1;}return aa.length-bb.length;});
                for(var ix=0;ix<sources.length;ix++){
                    if(cancelled)throw Error('Đã hủy');var doc=null,own=false;
                    try{if(inputFolder){doc=app.open(sources[ix]);own=true;}else doc=sources[ix];
                        note.text='Đang scan '+(ix+1)+'/'+sources.length;dlg.update();
                        var scanned=detect(doc);rpc({operation:'translation_index',project:project,manifest:scanned.manifestPath,page_id:decodeURI(doc.name),ordinal:ix+1});
                    }finally{if(own&&doc)doc.close(SaveOptions.DONOTSAVECHANGES);}
                }
                note.text='Đã index '+sources.length+' trang. Kiểm tra OCR trước khi dịch.';
            }catch(e){alert(e.message);}};
            newRun.onClick=function(){try{rpc({operation:'translation_profile',project:project,profile:profile()});var r=rpc({operation:'translation_prepare',project:project}).data;note.text='Đã tạo lượt mới: '+r.groups.length+' nhóm, '+r.blocked_ids.length+' vùng thiếu nguồn.';}catch(e){alert(e.message);}};
            runTranslation.onClick=function(){try{
                rpc({operation:'translation_profile',project:project,profile:profile()});
                var data=loadProject(), run=data.runs.length?data.runs[data.runs.length-1]:null;
                var incomplete=false;if(run)for(var k=0;k<run.groups.length;k++)if(run.groups[k].status!=='completed')incomplete=true;
                var rep=null,runId=(run&&incomplete)?run.id:null;
                do{
                    var req={operation:'translation_autopilot',project:project,budget_seconds:140};
                    if(runId)req.run_id=runId;
                    rep=rpc(req).data;runId=rep.run_id;
                    note.text='Đang dịch: '+rep.completed+'/'+rep.total+' nhóm'+(rep.parked.length?' — '+rep.parked.length+' nhóm lỗi':'');dlg.update();
                }while(!rep.done && !rep.aborted);
                var finalRun=loadProject();finalRun=finalRun.runs[finalRun.runs.length-1];
                note.text=(rep.aborted?'Dừng: '+rep.abort_reason+'. ':'Dịch xong. ')+(rep.parked.length?rep.parked.length+' nhóm lỗi nhiều lần, cần dịch lại. ':'')+(rep.auto_excluded&&rep.auto_excluded.count?'Đã tự loại '+rep.auto_excluded.count+' vùng không phải hội thoại. ':'')+finalRun.blocked_ids.length+' vùng chưa đọc được; duyệt trước khi dùng.';
            }catch(e){alert(e.message);}};
            editOcr.onClick=function(){try{
                var data=loadProject(),items=[];for(var p=0;p<data.pages.length;p++)for(var s=0;s<data.pages[p].segments.length;s++)items.push(data.pages[p].segments[s]);
                if(!items.length)throw Error('Chưa index trang');var d=new Window('dialog','Kiểm tra và sửa OCR');d.orientation='column';d.alignChildren='fill';
                var list=d.add('listbox',undefined,[]);list.preferredSize=[700,220];for(var i=0;i<items.length;i++)list.add('item',items[i].page_id+' / '+items[i].region_id+' | '+(items[i].jp || '[chưa đọc được]'));
                var firstCrop=rpc({operation:'translation_ocr_crop',project:project,segment_id:items[0].id}).data;
                var picture=d.add('image',undefined,new File(firstCrop.crop));picture.maximumSize=[400,300];
                var original=d.add('statictext',undefined,'',{multiline:true});original.preferredSize=[700,60];
                var edit=d.add('edittext',undefined,'',{multiline:true,scrolling:true});edit.preferredSize=[700,80];
                d.add('statictext',undefined,'Furigana (mỗi dòng: chữ gốc=âm đọc; không tự nhận diện)');
                var ruby=d.add('edittext',undefined,'',{multiline:true,scrolling:true});ruby.preferredSize=[700,45];
                var candidate=d.add('edittext',undefined,'',{multiline:true,scrolling:true,readonly:true});candidate.preferredSize=[700,60];
                var suggestions={},basedOn='manual';
                var buttons=d.add('group'),suggest=buttons.add('button',undefined,'Baberu gợi ý'),suggestPage=buttons.add('button',undefined,'Baberu cả trang'),useSuggestion=buttons.add('button',undefined,'Dùng gợi ý'),save=buttons.add('button',undefined,'Lưu nguồn đã sửa'),verify=buttons.add('button',undefined,'Xác nhận đã kiểm tra'),exclude=buttons.add('button',undefined,'Bỏ qua / dùng lại vùng');buttons.add('button',undefined,'Đóng',{name:'cancel'});
                var rubyActions=d.add('group'),saveRuby=rubyActions.add('button',undefined,'Lưu furigana gợi ý'),verifyRuby=rubyActions.add('button',undefined,'Xác nhận furigana');
                list.onChange=function(){if(!list.selection)return;try{var item=items[list.selection.index];var info=rpc({operation:'translation_ocr_crop',project:project,segment_id:item.id}).data;picture.image=ScriptUI.newImage(new File(info.crop));original.text='OCR gốc: '+(item.raw_ocr || '')+'\nTrạng thái: '+(item.source_status || 'unreviewed');edit.text=item.jp || '';basedOn=(item.source_provenance && item.source_provenance.based_on)||'manual';candidate.text=suggestions[item.id]||'';var lines=[];for(var ri=0;ri<(item.ruby||[]).length;ri++)lines.push(item.ruby[ri].base+'='+item.ruby[ri].reading);ruby.text=lines.join('\n');d.layout.layout(true);}catch(e){alert(e.message);}};
                function storeRuby(confirmed){if(!list.selection)return;var item=items[list.selection.index],lines=ruby.text.split(/\r?\n/),entries=[];for(var ri=0;ri<lines.length;ri++){if(!lines[ri].replace(/\s/g,''))continue;var eq=lines[ri].indexOf('=');if(eq<1)throw Error('Mỗi dòng furigana phải có dạng chữ gốc=âm đọc');entries.push({base:lines[ri].slice(0,eq).replace(/^\s+|\s+$/g,''),reading:lines[ri].slice(eq+1).replace(/^\s+|\s+$/g,'')});}var result=rpc({operation:'translation_ruby',project:project,segment_id:item.id,entries:entries,confirmed:confirmed}).data;item.ruby=result.ruby;note.text='Đã lưu furigana; tạo lượt dịch mới nếu cần.';}
                saveRuby.onClick=function(){try{storeRuby(false);}catch(e){alert(e.message);}};verifyRuby.onClick=function(){try{storeRuby(true);}catch(e){alert(e.message);}};
                save.onClick=function(){try{if(!list.selection)return;var item=items[list.selection.index];rpc({operation:'translation_source',project:project,segment_id:item.id,text:edit.text,based_on:basedOn});item.jp=edit.text;item.source_status='user_corrected';item.source_provenance={based_on:basedOn};list.selection.text=item.page_id+' / '+item.region_id+' | '+edit.text;note.text='Nguồn đã đổi; tạo lượt dịch mới nếu cần.';}catch(e){alert(e.message);}};
                verify.onClick=function(){try{if(!list.selection)return;var item=items[list.selection.index];rpc({operation:'translation_source',project:project,segment_id:item.id,text:edit.text,verified:true,based_on:basedOn});item.jp=edit.text;item.source_status='verified';item.source_provenance={based_on:basedOn};list.selection.text=item.page_id+' / '+item.region_id+' [đã kiểm tra] | '+edit.text;note.text='Đã xác nhận OCR; tạo lượt dịch mới.';}catch(e){alert(e.message);}};
                exclude.onClick=function(){try{if(!list.selection)return;var item=items[list.selection.index],excluded=item.source_status!=='excluded';var changed=rpc({operation:'translation_exclude',project:project,segment_id:item.id,excluded:excluded}).data;items[list.selection.index]=changed;list.selection.text=item.page_id+' / '+item.region_id+(excluded?' [bỏ qua]':' [dùng lại]')+' | '+(item.jp || '');note.text='Đã thay đổi vùng cần dịch; tạo lượt mới.';}catch(e){alert(e.message);}};
                suggest.onClick=function(){try{if(!list.selection)return;candidate.text='Đang đọc Baberu…';d.update();var item=items[list.selection.index],info=rpc({operation:'translation_ocr_crop',project:project,segment_id:item.id,candidate:true}).data;suggestions[item.id]=info.candidate || '';candidate.text=suggestions[item.id]; }catch(e){candidate.text='';alert(e.message);}};
                suggestPage.onClick=function(){try{if(!list.selection)return;var pageId=items[list.selection.index].page_id,ids=[];for(var bi=0;bi<items.length;bi++)if(items[bi].page_id===pageId && items[bi].source_status!=='excluded')ids.push(items[bi].id);
                    for(var bo=0;bo<ids.length;bo+=8){if(cancelled)throw Error('Đã hủy');candidate.text='Đang đọc '+Math.min(bo+8,ids.length)+'/'+ids.length+' vùng…';d.update();var batch=rpc({operation:'translation_ocr_suggest_batch',project:project,segment_ids:ids.slice(bo,bo+8)}).data.items;for(var bj=0;bj<batch.length;bj++)suggestions[batch[bj].segment_id]=batch[bj].candidate || '';}
                    candidate.text=suggestions[items[list.selection.index].id]||'';note.text='Đã tạo gợi ý OCR, chưa thay nguồn hay xác nhận.';
                }catch(e){candidate.text='';alert(e.message);}};
                useSuggestion.onClick=function(){if(candidate.text){edit.text=candidate.text;basedOn='baberu';}};
                list.selection=0;list.onChange();d.show();
            }catch(e){alert(e.message);}};
            reviewTranslation.onClick=function(){try{
                var data=loadProject(),run=latestRun(data),rows=[],source={},owners={};
                for(var p=0;p<data.pages.length;p++)for(var s=0;s<data.pages[p].segments.length;s++)source[data.pages[p].segments[s].id]=data.pages[p].segments[s];
                for(var g=0;g<run.groups.length;g++)for(var j=0;j<run.groups[g].results.length;j++){rows.push(run.groups[g].results[j]);owners[run.groups[g].results[j].id]=run.groups[g].id;}
                if(!rows.length)throw Error('Chưa có bản dịch');
                var r=new Window('dialog','Duyệt bản dịch');r.orientation='column';r.alignChildren='fill';
                var list=r.add('listbox',undefined,[]);list.preferredSize=[700,180];
                for(var n=0;n<rows.length;n++)list.add('item',rows[n].id+' | '+rows[n].status+' ['+rows[n].flags.join(', ')+'] | '+rows[n].semantic_translation.substr(0,50));
                var jp=r.add('edittext',undefined,'',{multiline:true,readonly:true});jp.preferredSize=[700,60];
                var vi=r.add('edittext',undefined,'',{multiline:true,scrolling:true});vi.preferredSize=[700,80];
                var buttons=r.add('group');buttons.add('statictext',undefined,'Điểm thủ công (1–5, tùy chọn):');var score=buttons.add('edittext',undefined,'');score.characters=3;var approve=buttons.add('button',undefined,'Lưu và xác nhận câu');var qa=buttons.add('button',undefined,'QA nhóm (dùng API)');buttons.add('button',undefined,'Đóng',{name:'cancel'});
                qa.helpTip='Gợi ý độc lập cùng provider, có thể vẫn sai hoặc trùng thiên lệch; không tự sửa bản dịch.';
                list.onChange=function(){if(!list.selection)return;var row=rows[list.selection.index];jp.text=source[row.id]?source[row.id].jp:'';if(row.source_evidence)jp.text+='\nVision gợi ý (chưa xác nhận): '+row.source_evidence.main_text+'\nFurigana: '+MJSON.stringify(row.source_evidence.furigana);vi.text=row.semantic_translation;};
                approve.onClick=function(){try{if(!list.selection)return;var row=rows[list.selection.index];rpc({operation:'translation_accept',project:project,run_id:run.id,edits:[{id:row.id,text:vi.text,quality_score:score.text?Number(score.text):null}]});row.semantic_translation=vi.text;row.status='human_approved';list.selection.text=row.id+' | đã duyệt | '+vi.text.substr(0,50);}catch(e){alert(e.message);}};
                qa.onClick=function(){try{if(!list.selection)return;var row=rows[list.selection.index];var q=rpc({operation:'translation_review_group',project:project,run_id:run.id,group_id:owners[row.id]}).data;alert('QA chỉ gợi ý, hãy đối chiếu nguồn:\n'+MJSON.stringify(q.issues));}catch(e){alert(e.message);}};
                list.selection=0;list.onChange();r.show();
            }catch(e){alert(e.message);}};
            draftReview.onClick=function(){try{
                var run=latestRun(loadProject()),doc=selectedDoc(),pages=rpc({operation:'translation_draft_mapping',project:project,run_id:run.id}).data.pages,found=null;
                for(var q=0;q<pages.length;q++)if(pages[q].page_id===decodeURI(doc.name))found=pages[q];
                if(!found)throw Error('Không tìm thấy trang trong project');var lines=['BẢN NHÁP — chưa kiểm chứng, không tự chấp nhận hay đưa vào typeset.'];
                for(var q2=0;q2<found.mapping.length;q2++){var m=found.mapping[q2],info=found.review[q2];lines.push(m.id+' ['+info.translation_status+' / OCR '+info.source_status+' / flag '+(info.flags.join(', ')||'không')+']\n'+m.translation);}
                var r=new Window('dialog','Bản dịch nháp — '+decodeURI(doc.name));var t=r.add('edittext',undefined,lines.join('\n\n'),{multiline:true,scrolling:true,readonly:true});t.preferredSize=[700,500];r.add('button',undefined,'Đóng',{name:'ok'});r.show();
            }catch(e){alert(e.message);}};
            applyPage.onClick=function(){try{
                var data=loadProject(),run=latestRun(data),doc=selectedDoc(),result=rpc({operation:'translation_mapping',project:project,run_id:run.id}).data.pages, found=null;
                for(var n=0;n<result.length;n++)if(result[n].page_id===decodeURI(doc.name))found=result[n];
                if(!found)throw Error('Không tìm thấy trang trong project');
                var manifest=new File(found.manifest),saved=MJSON.parse(MTA.read(manifest));MTA.validateManifest(saved,doc.width.as('px'),doc.height.as('px'));
                if(found.mapping.length!==found.required_count)throw Error('Trang còn vùng chưa được chấp nhận hoặc nguồn đã thay đổi.');
                var verifyFolder=MTA.mkdir(root.fsName+'/work/pages/'+MTA.unique());
                var verifySnapshot=MTA.snapshot(doc,verifyFolder);
                rpc({operation:'translation_verify_page',manifest:manifest.fsName,snapshot:verifySnapshot.fsName});
                var chosen=MTA.savedEngine(null,null,saved);selectSavedEngine(chosen);
                state={doc:doc,folder:manifest.parent,manifestPath:manifest.fsName,data:saved,mapping:found.mapping,translationText:translation.text,offline:false,engine:chosen};
                note.text='Đã đưa mapping đã duyệt vào trang hiện tại. Bấm Typeset và kiểm tra mapping.';
                dlg.close();
            }catch(e){alert(e.message);}};
            dlg.center();dlg.show();
        }); };
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
            var layoutReviewCount=0,resumed=0,good = 0,reviewPages=0,manualLayers=0,noTranslation=0,withoutWarnings=0,omittedLines=0;
            var batchStarted=(new Date()).getTime(), finished={};
            // Resume: a batch of 100-200 pages can be interrupted; offer to keep finished pages.
            var oldLogs=folder.getFiles('batch_*.json');oldLogs.sort(function(a,b){return b.modified.getTime()-a.modified.getTime();});
            if(oldLogs.length){
                try{
                    var previous=MJSON.parse(MTA.read(oldLogs[0])),done=MTA.finishedPages(previous),count=0;
                    for(var dk in done)count++;
                    if(count && confirm('Log gần nhất đã xong '+count+' trang. Tiếp tục và bỏ qua các trang đó?\n(Chọn Không để làm lại từ đầu.)')){
                        finished=done;for(var fk in done)log.push(done[fk]);
                    }
                }catch(_){}
            }
            for (var j = 0; j < sources.length; j++) {
                var estimate = j ? ' — ước tính còn ' + Math.ceil(((new Date()).getTime()-batchStarted)*(sources.length-j)/j/60000) + ' phút' : '';
                if (!tick('Trang ' + (j+1) + '/' + sources.length + estimate, 100*j/sources.length)) break;
                var pageStarted=(new Date()).getTime();
                var doc = null, ownsDoc = false, s = null;
                if(finished[decodeURI(sources[j].name)]){resumed++;continue;}
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
                    manualLayers+=s.manualText.length;layoutReviewCount+=(s.layoutReview||[]).length;
                    omittedLines+=s.omittedTranslations.length;
                    var partial=s.manualText.length || s.omittedTranslations.length || s.cleanResult.skipped.length || !!experimentalClean;
                    if(!partial)withoutWarnings++;
                    log.push({page: j+1, source: decodeURI(sources[j].name), ok: true, status:partial?'partial':'processed', psd: s.savedFiles.psd || null, pdf: s.savedFiles.pdf || null, output_color_mode:s.outputColorMode, output_color_profile:s.outputColorProfile, manifest:s.manifestPath, detector:s.data.detector || 'opencv', translation_page: batchCleanOnly.value ? null : pageKey, translation_lines:pageLines.length, unmapped_translation_indexes:s.omittedTranslations, manual_text_ids:s.manualText,layout_review:s.layoutReview||[], clean_result_schema:s.cleanResult.result_schema || null, clean_region_results:s.cleanResult.region_results || [], clean_review_ids:s.cleanResult.review_ids || [], clean_counts:s.cleanResult.counts || null, clean_applied:s.cleanResult.applied, clean_skipped:s.cleanResult.skipped, clean_blocked:s.cleanResult.blocked || {}, clean_skip_reason_codes:s.cleanResult.skip_reason_codes || {}, clean_trace:s.cleanResult.trace || null, clean_mask:s.cleanResult.mask || null, engine_id:s.cleanResult.engine_id || null, engine_version:s.cleanResult.version || null, scan_hardware:s.data.hardware || null, clean_hardware:s.cleanResult.hardware || null, experimental_clean:experimentalClean, clean_mask_pixels:s.cleanResult.mask_pixels || 0, clean_quality:s.cleanResult.quality || null});
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
            tick('Đã lưu ' + good + '/' + sources.length + ' trang; không cảnh báo: '+withoutWarnings+'; có cảnh báo: '+(good-withoutWarnings)+'; trang chờ ghép: '+reviewPages+(experimentalClean?'; chữ hiện cần kiểm tra AI: ':'; chữ ẩn cần clean: ')+manualLayers+'; chữ cần rà soát cỡ/độ lấp: '+layoutReviewCount+'; bỏ qua vì đã xong: '+resumed+'; câu chưa ghép: '+omittedLines+'; thiếu bản dịch: '+noTranslation+'. Log: ' + logFile.fsName, 100);
            alert(status.text);
        }); };
        cancelButton.onClick = function () { cancelled = true; status.text = 'Đang hủy tại điểm an toàn…'; };
        close.onClick = function () { if (!busy) win.close(); };
        win.onClose = function () { if (busy) { cancelled = true; return false; } return true; };

        // ---------- Tab "Tự động": the one screen a non-technical user needs ----------
        // Choose a folder, press Start, do something else. The machine tries three sample pages first
        // (a hopeless run is caught in minutes), then runs the whole volume unattended and reports.
        var EASY_KEY_ENV='MANGA_TRANSLATION_API_KEY', easyFolder=null, lastReportHtml=null;
        var easyIntro=easyTab.add('statictext',undefined,'Dịch và chèn chữ cả tập truyện. Chọn thư mục ảnh, bấm Bắt đầu rồi làm việc khác: máy tự thử 3 trang, tự chạy cả tập và báo khi xong. Bản gốc luôn được giữ nguyên.',{multiline:true});
        easyIntro.preferredSize=[740,42];
        var easyFolderRow=easyTab.add('group');
        var easyChoose=easyFolderRow.add('button',undefined,'1. Chọn thư mục truyện');
        var easyFolderInfo=easyFolderRow.add('statictext',undefined,'Chưa chọn thư mục');easyFolderInfo.characters=62;
        var easyNameRow=easyTab.add('group');easyNameRow.add('statictext',undefined,'Tên bộ truyện:');
        var easyName=easyNameRow.add('edittext',undefined,'');easyName.characters=30;
        easyNameRow.add('statictext',undefined,'Chế độ:');
        var easyMode=easyNameRow.add('dropdownlist',undefined,['Nhanh (khuyên dùng)','Chất lượng (đọc cả ảnh, tốn hơn)']);easyMode.selection=0;
        var easyHostRow=easyTab.add('group');var easyHostLabel=easyHostRow.add('statictext',undefined,'Host (địa chỉ API):');easyHostLabel.characters=17;
        var easyHost=easyHostRow.add('edittext',undefined,'https://api.vilao.ai/v1');easyHost.characters=48;
        var easyModelRow=easyTab.add('group');var easyModelLabel=easyModelRow.add('statictext',undefined,'Tên model:');easyModelLabel.characters=17;
        var easyModelName=easyModelRow.add('edittext',undefined,'deepseek-ai/deepseek-v4.1-flash-1017');easyModelName.characters=48;
        var easyKeyRow=easyTab.add('group');var easyKeyLabel=easyKeyRow.add('statictext',undefined,'API key:');easyKeyLabel.characters=17;
        var easyKey=easyKeyRow.add('edittext',undefined,'',{noecho:true});easyKey.characters=48;
        var easyKeyInfo=easyTab.add('statictext',undefined,'Đang kiểm tra API key…');easyKeyInfo.characters=90;
        var easyActions=easyTab.add('group');
        var easyStart=easyActions.add('button',undefined,'2. Bắt đầu: thử 3 trang rồi chạy cả tập');
        var easyTry=easyActions.add('button',undefined,'Chỉ thử 3 trang');
        var easyAfter=easyTab.add('group');
        var easyReport=easyAfter.add('button',undefined,'Mở báo cáo gần nhất');easyReport.enabled=false;
        var easyReview=easyAfter.add('button',undefined,'3. Rà soát nhanh trong Photoshop');
        var easyKeepPsd=easyTab.add('checkbox',undefined,'Lưu thêm file PSD (nặng hơn; mặc định chỉ lưu Photoshop PDF giữ layer)');easyKeepPsd.value=false;
        var easyNote=easyTab.add('statictext',undefined,'',{multiline:true});easyNote.preferredSize=[740,84];
        controls.push(easyChoose,easyName,easyMode,easyHost,easyModelName,easyKey,easyStart,easyTry,easyReport,easyReview,easyKeepPsd);
        function easySay(text){easyNote.text=text;status.text=text;win.update();}
        function easyRefreshKey(){
            try{
                var k=rpc({operation:'translation_key_status',key_env:EASY_KEY_ENV}).data;
                easyKeyInfo.text=k.present?'Đã có API key ('+(k.source==='env'?'từ biến môi trường':'đã lưu trên máy này')+'). Để trống ô API key nếu không muốn đổi.':'CHƯA CÓ API key: hãy dán key vào ô API key.';
            }catch(e){easyKeyInfo.text='Không kiểm tra được API key.';}
        }
        // Host and model are remembered (not secret); the key goes only to the per-user key file.
        var easySettingsFile=new File('~/.manga_typesetter/easy_settings.json');
        try{if(easySettingsFile.exists){var es=MJSON.parse(MTA.read(easySettingsFile));if(es.base_url)easyHost.text=es.base_url;if(es.model)easyModelName.text=es.model;}}catch(_){}
        function easySaveApi(){
            var host=easyHost.text.replace(/^\s+|\s+$/g,''),model=easyModelName.text.replace(/^\s+|\s+$/g,'');
            if(!/^https:\/\/[^\s\/]+/.test(host))throw Error('Host phải bắt đầu bằng https:// (ví dụ https://api.vilao.ai/v1).');
            if(!model)throw Error('Hãy nhập tên model.');
            easyHost.text=host;easyModelName.text=model;
            var dir=new Folder('~/.manga_typesetter');if(!dir.exists)dir.create();
            MTA.write(easySettingsFile,MJSON.stringify({base_url:host,model:model}));
            var value=easyKey.text.replace(/^\s+|\s+$/g,'');
            if(value){
                var keyFile=new File(dir.fsName+'/'+EASY_KEY_ENV+'.key');MTA.write(keyFile,value);
                if(!/^windows/i.test($.os))app.system('/bin/chmod 600 '+MTA.shell(keyFile.fsName));
                easyKey.text='';       // the key is not kept on screen once saved
            }
            easyRefreshKey();
        }
        easyHost.onChange=function(){try{easySaveApi();}catch(e){easySay(e.message);}};
        easyModelName.onChange=easyHost.onChange;
        easyKey.onChange=easyHost.onChange;
        function easyFiles(){return easyFolder?easyFolder.getFiles(function(f){return f instanceof File && MTA.sourceNameAllowed(f.name);}):[];}
        // Prefer the AI redraw engine so ordinary bubbles are cleaned, not skipped; redrawn areas are flagged for review.
        function easyEngineById(id){for(var i=0;i<engines.length;i++)if(engines[i].id===id&&engines[i].ready)return {id:id,version:engines[i].version};return null;}
        function easyEngine(){
            var e=easyEngineById('art_draft');
            if(!e){
                // Never fall back silently: without the AI redraw model many ordinary bubbles will not be cleaned.
                e=easyEngineById('baseline');
                if(!e)throw Error('Không tìm thấy engine clean. Bấm "Kiểm tra Python" ở tab Nguồn.');
                if(!confirm('Chưa có model AI vẽ lại nền (LaMa), nên máy chỉ dùng engine thường. Nhiều bong bóng có thể KHÔNG được xoá chữ gốc.\n\nNên tải model trước, rồi mở lại script:\npython manga_typesetter.py download-models --profile preview --download\n\nVẫn tiếp tục với engine thường?'))throw Error('Đã dừng. Hãy tải model LaMa rồi chạy lại.');
            }
            return e;
        }
        function easyProfile(project,mode){
            var prior={},st,k;
            try{st=rpc({operation:'translation_load',project:project});if(st.profiles.length)prior=st.profiles[st.profiles.length-1].values;}catch(_){}
            var p={};for(k in prior)p[k]=prior[k];
            p.series_name=easyName.text;p.base_url=easyHost.text;p.model=easyModelName.text;
            p.group_size=7;p.max_tokens=24576;p.timeout=150;p.retries=1;p.json_mode=true;p.thinking='disabled';p.context_segments=2;
            p.vision_mode=mode===1?'target_crop':'off';p.key_env=p.key_env||EASY_KEY_ENV;p.auto_accept=false;
            return p;
        }
        easyChoose.onClick=function(){
            var f=Folder.selectDialog('Chọn thư mục chứa ảnh truyện (JPG, PNG hoặc PSD)');if(!f)return;
            easyFolder=f;var n=easyFiles().length;
            easyFolderInfo.text=f.fsName+' — '+n+' trang';
            if(!easyName.text)easyName.text=decodeURI(f.name);
            easySay(n?'Đã chọn '+n+' trang. Bấm "Bắt đầu" khi sẵn sàng.':'Thư mục này không có ảnh JPG, PNG hoặc PSD.');
        };
        easyReport.onClick=function(){if(lastReportHtml){try{(new File(lastReportHtml)).execute();}catch(e){alert('Không mở được báo cáo: '+e.message);}}};
        function easyRun(sampleOnly){
            run(function(){
                if(!easyFolder)throw Error('Hãy chọn thư mục truyện trước.');
                easySaveApi();
                var key=rpc({operation:'translation_key_status',key_env:EASY_KEY_ENV}).data;
                if(!key.present)throw Error('Chưa có API key. Hãy dán key vào ô API key rồi thử lại.');
                if(!aiDetector.value)throw Error('Chưa có model AI nhận diện bong bóng. Hãy cài model (xem hướng dẫn cài đặt) rồi mở lại script.');
                var count=easyFiles().length;if(!count)throw Error('Thư mục không có ảnh JPG, PNG hoặc PSD.');
                lang.selection=lang.find('jpn_vert');rtl.value=true;
                // Output: one Adobe Photoshop PDF per page that keeps every layer (the main file); PSD only if asked.
                savePdf.value=true;pdfLayers.value=true;savePsd.value=easyKeepPsd.value===true;
                // No saved font yet: use an installed comic font (Pangolin, then Itim) instead of the Arial default.
                if(!fontSettingsFile.exists){
                    var comic=chooseFontById(font,'Pangolin-Regular')?'Pangolin-Regular':(chooseFontById(font,'Itim-Regular')?'Itim-Regular':null);
                    if(comic){chooseFontById(boxFont,comic);chooseFontById(shoutFont,comic);}
                    else easySay('Chưa cài font comic (Pangolin hoặc Itim) nên chữ sẽ dùng '+font.selection.text+'. Cài font trong thư mục assets/fonts rồi mở lại script để đẹp hơn.');
                }
                var out=MTA.mkdir(easyFolder.fsName+'/_MangaTypesetter');outputFolder=out;outInfo.text=out.fsName;
                var mode=easyMode.selection?easyMode.selection.index:0;
                var engine=easyEngine(),escalated=false,decision=null,trial=null;
                var pick=rpc({operation:'translation_preflight_pick',count:count}).data.indices;
                // 1) Preflight on three spread-out pages: weak cleaning escalates to the AI engine once; a hopeless run stops here.
                for(var attempt=0;attempt<2;attempt++){
                    var sub=MTA.mkdir(out.fsName+'/chay_thu_'+(attempt===0?'1':'2_AI'));
                    var pf=new File(sub.fsName+'/project.json');if(pf.exists)pf.remove();
                    trial=runVolume({project:pf.fsName,profile:easyProfile(pf.fsName,mode),title:'Báo cáo chạy thử',note:easySay,label:'[Chạy thử '+(attempt+1)+'] ',engine:engine,folder:easyFolder,indices:pick,output:sub,openReport:false});
                    decision=rpc({operation:'translation_preflight_decide',pages:trial.log,engine:engine.id,escalated:escalated}).data;
                    if(trial.html)lastReportHtml=trial.html;
                    if(decision.action==='escalate'){
                        var next=easyEngineById(decision.next_engine);
                        if(next){easySay(decision.message);engine=next;escalated=true;continue;}
                        decision={action:'go',message:decision.message+' Engine AI chưa sẵn sàng nên tiếp tục bằng engine thường; nhiều bong bóng sẽ cần xử lý tay.'};
                    }
                    break;
                }
                easyReport.enabled=!!lastReportHtml;easySay(decision.message);
                if(decision.action==='stop'){alert('Chưa nên chạy cả tập.\n\n'+decision.message+(lastReportHtml?'\n\nBáo cáo chạy thử có ở nút "Mở báo cáo gần nhất".':''));return;}
                if(sampleOnly){alert('Chạy thử xong.\n\n'+decision.message);if(lastReportHtml){try{(new File(lastReportHtml)).execute();}catch(_){}}return;}
                // 2) The whole volume, unattended.
                var projectFile=new File(out.fsName+'/project.json');
                var res=runVolume({project:projectFile.fsName,profile:easyProfile(projectFile.fsName,mode),title:'Báo cáo: '+(easyName.text||'bộ truyện'),note:easySay,label:'',engine:engine,folder:easyFolder,output:out});
                if(res.html){lastReportHtml=res.html;easyReport.enabled=true;}
                var sm=res.summary||{ok:0,look:0,fix:0,pages:0};
                var done='XONG '+sm.pages+' trang: '+sm.ok+' trang ổn, '+sm.look+' nên xem lại, '+sm.fix+' cần sửa.';
                easySay(done+' Báo cáo chi tiết đã mở trong trình duyệt.');
                alert(done+'\n\nBáo cáo (có ảnh từng chỗ cần xem) đã mở trong trình duyệt. file Photoshop PDF (giữ layer) nằm trong:\n'+out.fsName);
                if(sm.fix+sm.look>0&&confirm('Mở rà soát nhanh ngay bây giờ?\n(Bạn cũng có thể mở sau bằng nút "3. Rà soát nhanh trong Photoshop".)'))openReview();
            });
        }
        easyReview.onClick=function(){try{openReview();}catch(e){alert('Không mở được rà soát: '+(e.message||e));}};
        easyStart.onClick=function(){easyRun(false);};
        easyTry.onClick=function(){easyRun(true);};
        loadEngines();easyRefreshKey();syncInputs();win.center(); win.show();
    } catch (e) { alert('Manga Typesetter AI: ' + e.message + (e.line ? '\nDòng: ' + e.line : '')); }
    finally {
        app.preferences.rulerUnits = oldRuler; app.preferences.typeUnits = oldType; app.displayDialogs = oldDialogs;
    }
})();
