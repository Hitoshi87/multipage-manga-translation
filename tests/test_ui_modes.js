const fs=require('fs'), vm=require('vm'), assert=require('assert');
const source=fs.readFileSync('Photoshop_Typeset.jsx','utf8');
const names=/var controls = \[([\s\S]*?)\];/.exec(source)[1].split(',').map(s=>s.trim());
const ctx={console,busy:false,cancelled:false,state:{},docs:[{}],pendingPages:[],uiFeatures:{},
    engineNote:{},advancedNote:{},close:{},win:{update(){}},alert(s){throw Error(s);}};
for(const name of names)ctx[name]={value:false,enabled:true,selection:{index:0},text:''};
ctx.controls=names.map(n=>ctx[n]);
ctx.engines=[{id:'baseline',version:'baseline-1',ready:true},{id:'1107',version:'1107-shadow-0.2',ready:true}];
for(const key of ['mask_ctd','mask_mask','inpaint_lama','inpaint_white','head_guard','scan_ai','koharu','magi'])ctx.uiFeatures[key]={ready:true};
vm.createContext(ctx);vm.runInContext(fs.readFileSync('scripts/core.jsxinc','utf8'),ctx);
vm.runInContext(/function inpaintMethod\(\) \{[^\n]+\}/.exec(source)[0],ctx);
vm.runInContext(source.slice(source.indexOf('        function currentEngineId('),source.indexOf('        function selectedEngine(')),ctx);
vm.runInContext(source.slice(source.indexOf('        function run(fn)'),source.indexOf('        function rpc(')),ctx);
vm.runInContext(source.slice(source.indexOf('        engineChoice.onChange='),source.indexOf('        function selectedDoc(')),ctx);
ctx.aiDetector.value=true;
vm.runInContext('syncInputs()',ctx);
assert(ctx.modelBatch.enabled && ctx.testModel.enabled && ctx.protectFaces.enabled);
ctx.modelBatch.value=true;
ctx.engineChoice.selection.index=1;ctx.engineChoice.onChange();
assert.strictEqual(ctx.modelBatch.value,false);
for(const name of ['maskChoice','useLama','modelBatch','protectFaces','testModel'])assert.strictEqual(ctx[name].enabled,false,name);
assert(ctx.previewEngine.enabled && ctx.clean.enabled);
{
  let ready=true;
  const choice={removeAll(){},add(){},selection:null};
  const startup={rpc:()=>({engines:[{id:'baseline',label:'Baseline',version:'1',ready:true}],default:'baseline',ui_features:{magi:{ready},scan_ai:{ready:true}}}),
    featureReady(name){return !!(startup.uiFeatures[name]&&startup.uiFeatures[name].ready);},
    engines:[],uiFeatures:{},aiDetector:{value:true},magiOrder:{value:false},engineChoice:choice,status:{}};
  vm.createContext(startup);
  vm.runInContext(source.slice(source.indexOf('        function loadEngines()'),source.indexOf('        engineChoice.onChange=')),startup);
  startup.loadEngines();assert.strictEqual(startup.magiOrder.value,true,'installed MAGI is selected at startup');
  ready=false;startup.loadEngines();assert.strictEqual(startup.magiOrder.value,false,'missing MAGI falls back to OpenCV');
}
ctx.run(()=>{});
for(const name of ['modelBatch','protectFaces','testModel'])assert.strictEqual(ctx[name].enabled,false,'run finally re-enabled '+name);
ctx.batchCleanOnly.value=true;ctx.batchCleanOnly.onClick();
for(const name of ['translation','font','typeset','alreadyClean','skipMismatch'])assert.strictEqual(ctx[name].enabled,false,name);
assert(ctx.clean.enabled && ctx.reviewAll.enabled);
ctx.batchCleanOnly.value=false;ctx.alreadyClean.value=true;ctx.alreadyClean.onClick();
assert(!ctx.clean.enabled && !ctx.previewEngine.enabled && !ctx.batchCleanOnly.enabled && ctx.typeset.enabled);
ctx.alreadyClean.value=false;ctx.reviewAll.value=true;ctx.reviewAll.onClick();assert(!ctx.skipMismatch.enabled);
ctx.aiDetector.value=false;ctx.syncInputs();assert(!ctx.detailChoice.enabled);
ctx.pendingPages=[{}];ctx.syncInputs();assert(ctx.pendingButton.enabled);
// Execute the actual primary preview handler; no legacy experiment request.
const requests=[];let shown;
ctx.ensureState=()=>({engine:ctx.engines[1],manifestPath:'page/manifest.json',data:{regions:[{id:'B001'},{id:'B002'}]},mapping:[{id:'B001',clean:false,force:true},{id:'B002',clean:true,force:true}]});
ctx.selectedEngine=()=>ctx.engines[1];ctx.tick=()=>true;
ctx.rpc=q=>{requests.push(JSON.parse(JSON.stringify(q)));return {engine_id:'1107',version:'1107-shadow-0.2',review_ids:['B002'],skipped:['B002']};};
ctx.showEnginePreview=r=>{shown=r;};
vm.runInContext(source.slice(source.indexOf('        previewEngine.onClick='),source.indexOf('        testModel.onClick =')),ctx);
ctx.previewEngine.onClick();
assert.strictEqual(requests.length,1);assert.strictEqual(requests[0].operation,'run_engine');
assert.strictEqual(requests[0].engine_id,'1107');assert.strictEqual(requests[0].engine_version,'1107-shadow-0.2');
assert.strictEqual(requests[0].mapping[0].clean,false);assert.strictEqual(requests[0].mapping[1].clean,true);
assert(requests[0].mapping.every(m=>!m.force));assert(shown);
// No two overlapping review checkboxes remain.
assert(!source.includes('batchForce'));assert.strictEqual((source.match(/addTab\('/g)||[]).length,5);
for(const title of ['Tự động (khuyên dùng)','1. Nguồn & nhận diện','2. Engine clean','3. Typeset & xuất','4. Thử nghiệm nâng cao'])assert(source.includes(title));
assert(source.indexOf("addTab('Tự động")<source.indexOf("addTab('1. Nguồn"),'the automatic tab must come first');
assert(source.includes('tabs.selection=easyTab'));
// Host, model name and API key are three separate editable fields; the key is masked and never remembered on screen.
for(const label of ['Host (địa chỉ API):','Tên model:','API key:'])assert(source.includes(label),label);
assert(source.includes("easyKey=easyKeyRow.add('edittext',undefined,'',{noecho:true})"));
assert(source.includes('p.base_url=easyHost.text;p.model=easyModelName.text;'));
assert(!source.includes('easyKeyButton'),'the key dialog button was replaced by the key field');
assert(source.includes("easyKey.text='';"),'the key is cleared from the field once saved');
// The main output is one layered Adobe Photoshop PDF per page; PSD is optional and off by default.
assert(source.includes('savePdf.value=true;pdfLayers.value=(easyPdfKind.selection?easyPdfKind.selection.index:0)===0;savePsd.value=easyKeepPsd.value===true;'),'layered PDF is the default kind; PSD is optional');
assert(source.includes('easyKeepPsd.value=false'));
assert(source.includes("chooseFontById(font,'Pangolin-Regular')"),'automatic tab picks an installed comic font');
// Line spacing is Auto by default; the number is used only when Auto is unticked.
assert(source.includes("leadingAuto.value = true"));
assert(source.includes('autoLeading: leadingAuto.value === true, leading: leadingAuto.value === true ? 1.05 : Number(leading.text)'));
console.log('Four-tab UI: engine locks, busy restore, clean/typeset modes, dependencies, one review toggle and real preview dispatch PASS');

// rpc() returns response.result as is. Operations returning a plain dict have no `.data`; reading it gives undefined
// ("undefined is not an object"). Only envelope operations (service.* results) may be followed by `.data`.
{
  const plainOps=['translation_key_status','translation_preflight_pick','translation_preflight_decide','translation_autopilot',
    'translation_auto_shorten','translation_auto_exclude','translation_estimate','translation_report','review_queue','review_mark','translation_env_check'];
  for(const op of plainOps){
    const uses=source.match(new RegExp("operation:'"+op+"'[^;]*?\\)\\s*\\.data","g"))||[];
    assert.strictEqual(uses.length,0,op+' returns a plain dict; do not read .data');
  }
  console.log('rpc result shape contract PASS');
}

// Fail fast and be explicit: the environment is checked before the run, the plan names the engine and models,
// and the engine and the output folder are choices the user can see.
{
  assert(source.includes("operation:'translation_env_check'"));
  assert(source.indexOf('var chk=easyEnvCheck();')<source.indexOf('var inputFiles=easyFiles()'),'environment is checked before any work');
  for(const label of ['Engine xoá chữ:','Kiểm tra môi trường','Đổi thư mục lưu kết quả','Sẽ chạy:'])assert(source.includes(label),label);
  assert(source.includes("var out=MTA.mkdir(easyOutFolder().fsName)"));
  assert(source.includes('easyEngineChoice.selection?easyEngineChoice.selection.index:0'));
  console.log('Automatic tab environment, engine and output folder PASS');
}

// One click, one run; PDF size choices are visible; lettering uses the refined balloon when present.
{
  assert.strictEqual(ctx.MTA.automaticClickAllowed(false,true,1000,false,1200),true,'start after sample is a distinct user action');
  assert.strictEqual(ctx.MTA.automaticClickAllowed(false,true,1000,true,1200),false,'duplicate sample click is suppressed');
  assert.strictEqual(ctx.MTA.automaticClickAllowed(true,true,1000,false,3000),false,'no overlapping runs');
  assert.strictEqual(ctx.MTA.automaticClickAllowed(false,true,1000,true,2600),true,'later retry is allowed');
  assert(source.includes('inputFolder=f;sourceInfo.text=f.fsName'), 'automatic folder also feeds the chapter button');
  assert(source.includes('syncEasyFolder(selected)'), 'the chapter folder also updates the automatic tab');
  const chosen={fsName:'/manga/new',name:'new'};
  const folderCtx={easyChoose:{},sourceInfo:{},Folder:{selectDialog:()=>chosen},syncEasyFolder:f=>{folderCtx.easyFolder=f;}};
  vm.createContext(folderCtx);
  vm.runInContext(source.slice(source.indexOf('        easyChoose.onClick='),source.indexOf('        easyReport.onClick=')),folderCtx);
  folderCtx.easyChoose.onClick();
  assert.strictEqual(folderCtx.inputFolder,chosen,'selecting automatic input updates the folder consumed by chapter');
  assert.strictEqual(folderCtx.easyFolder,chosen);
  const file=(name,size,modified)=>({fsName:name,length:size,modified:new Date(modified)});
  const inputs=[file('/a/001.png',100,1000),file('/a/002.png',200,2000)];
  const key=ctx.MTA.sourceProjectKey('/a',inputs);
  assert.strictEqual(key,ctx.MTA.sourceProjectKey('/a',inputs.slice().reverse()),'input order does not change project identity');
  assert.notStrictEqual(key,ctx.MTA.sourceProjectKey('/b',inputs),'different input folder uses a separate project');
  assert.notStrictEqual(key,ctx.MTA.sourceProjectKey('/a',[inputs[0],file('/a/002.png',201,2000)]),'changed inputs use a separate project');
  assert.notStrictEqual(key,ctx.MTA.sourceProjectKey('/a',[inputs[0],file('/a/002.png',200,3000)]),'modified files use a separate project');
  assert(source.includes("'/project_'+sourceKey+'.json'"),'full volume is scoped to its source files');
  assert(!source.includes('if(pf.exists)pf.remove()'),'sample runs do not erase existing projects');
  assert(source.includes('Chưa chạy cả tập.'),'sample-only completion must not imply the chapter already started');
  assert(source.includes('openReview(projectFile.fsName,out)'),'review opens the current input project');
  {
    const calls=[],folder={fsName:'/output'}, directCtx={
      run:fn=>fn(),easyFolder:{fsName:'/input'},easySaveApi(){calls.push('save-api');},
      easyEnvCheck(){throw Error('direct run must not execute preflight environment check');},
      easyFiles:()=>[{fsName:'/input/1.png',length:10}],MTA:{sourceProjectKey:()=> 'key',mkdir:()=>folder},
      aiDetector:{value:true},lang:{find:()=>({text:'jpn_vert'})},rtl:{},savePdf:{},pdfLayers:{},savePsd:{},colorMode:{},
      easyPdfKind:{selection:{index:0}},easyKeepPsd:{value:false},easyColor:{selection:{index:0}},fontSettingsFile:{exists:true},
      easyOutFolder:()=>folder,outInfo:{},easyMode:{selection:{index:0}},easyEngine:()=>({id:'baseline'}),
      easyProfile:()=>({}),easyName:{text:'test'},easySay(){},easyReport:{},alert(){},
      File:function(p){this.fsName=p;},
      rpc(){throw Error('direct run must not call preflight RPC');},
      runStreamingVolume(cfg){calls.push('volume');assert.strictEqual(cfg.folder.fsName,'/input');return {summary:{pages:1,ok:1,look:0,fix:0}};}
    };
    vm.createContext(directCtx);
    vm.runInContext(source.slice(source.indexOf('        function easyRunBody('),source.indexOf('        easyReview.onClick=')),directCtx);
    directCtx.easyRunBody('direct');
    assert.deepStrictEqual(calls,['save-api','volume'],'direct action runs the volume once without a trial');
  }
  {
    const refreshCtx={};vm.createContext(refreshCtx);
    vm.runInContext(source.slice(source.indexOf('        function canRefreshPageLayout('),source.indexOf('        function runVolume(')),refreshCtx);
    const page={page_id:'p',segments:[{id:'s',source_status:'unreviewed'}]};
    assert(refreshCtx.canRefreshPageLayout({runs:[]},page,'opencv','magi'),'untranslated scan may be refreshed');
    assert(!refreshCtx.canRefreshPageLayout({runs:[]},page,'magi','magi'));
    assert(!refreshCtx.canRefreshPageLayout({runs:[{groups:[{targets:[{id:'s'}],context:[]}]}]},page,'opencv','magi'),'referenced scan is immutable');
    assert(!refreshCtx.canRefreshPageLayout({runs:[]},{page_id:'p',segments:[{id:'s',source_status:'user_corrected'}]},'opencv','magi'),'manual OCR is never discarded');
    assert(!refreshCtx.canRefreshPageLayout({runs:[{groups:[],blocked_ids:['s']}]},page,'opencv','magi'),'blocked source is immutable');
  }
  {
    const files=['1.png','2.png'].map(name=>({name})),written={},calls=[];let pages=[],failNumeric=false,staleWorker=false;
    function File(path){this.fsName=path;this.name=path.split('/').pop();this.parent={fsName:'/tmp'};this.exists=true;}
    files.forEach(f=>Object.setPrototypeOf(f,File.prototype));
    const volumeCtx={File,MJSON:JSON,cancelled:false,volumeProgress:'',inputFolder:null,outputFolder:{fsName:'/out'},
      lang:{selection:{text:'jpn_vert'}},savePsd:{value:false},savePdf:{value:true},docs:[],root:{fsName:'/tmp'},
      magiOrder:{value:true},koharuOrder:{value:false},
      selectedEngine:()=>({id:'baseline'}),tick:()=>true,
      app:{open:f=>({name:f.name,width:{as:()=>10},height:{as:()=>10},close(){}})},SaveOptions:{DONOTSAVECHANGES:0},
      MTA:{sourceNameAllowed:()=>true,mkdir:()=>({fsName:'/tmp'}),unique:()=>1,snapshot:()=>({fsName:'/tmp/snapshot.png'}),read:()=>JSON.stringify({regions:[],layout_model:'opencv'}),write:(f,s)=>{written[f.fsName]=JSON.parse(s);},validateManifest(){}},
      detect(doc){if(doc.name==='1.png')throw Error('Không đọc được trang');return {manifestPath:'/tmp/manifest.json'};},
      build(s){s.cleanResult={skipped:[],applied:[]};s.savedFiles={pdf:'/out/2.pdf'};},
      rpc(req){
        calls.push(req.operation);
        if(req.operation==='translation_load')return {pages,runs:[{id:'run1',groups:[],blocked_ids:[]}]};
        if(req.operation==='translation_autopilot')return {run_id:'run1',done:true,parked:[]};
        if(req.operation==='translation_visual_ocr_page'){
          if(staleWorker){const error=Error('worker không có tín hiệu');error.workerUnresponsive=true;throw error;}
          if(failNumeric)throw Error('vision unavailable');return {data:{done:true}};
        }
        if(req.operation==='translation_auto_shorten')return {done:true,shortened:[]};
        if(req.operation==='translation_draft_mapping')return {data:{pages:[{page_id:'2.png',manifest:'/tmp/manifest.json',mapping:[],review:[],required_count:0}]}};
        if(req.operation==='translation_report')return {summary:{ok:1,look:0,fix:1,pages:2}};
        return {};
      }};
    vm.createContext(volumeCtx);
    vm.runInContext(source.slice(source.indexOf('        function runVolume('),source.indexOf('        // Bounded, chronological batches')),volumeCtx);
    const result=volumeCtx.runVolume({folder:{getFiles:()=>files},project:'/out/project.json',profile:{},output:{fsName:'/out'},note(){},streamLimit:2,openReport:false});
    assert.deepStrictEqual(Array.from(result.log,x=>x.status),['failed','draft'],'scan failure does not prevent another page from exporting');
    assert.match(result.log[0].error,/Không đọc được trang/);
    assert.strictEqual(written['/out/draft_run1.json'].pages.length,2,'failure and exported page are checkpointed');
    pages=[{page_id:'2.png',ordinal:2,manifest:'/tmp/old.json',segments:[{id:'s',source_status:'unreviewed'}]}];calls.length=0;
    vm.runInContext(source.slice(source.indexOf('        function canRefreshPageLayout('),source.indexOf('        function runVolume(')),volumeCtx);
    volumeCtx.runVolume({folder:{getFiles:()=>files},project:'/out/project.json',profile:{},output:{fsName:'/out'},note(){},streamLimit:2,openReport:false});
    assert(calls.includes('translation_verify_page')&&calls.includes('translation_index'),'unreferenced old OpenCV scan is refreshed to MAGI');
    pages=[];calls.length=0;failNumeric=true;
    const degraded=volumeCtx.runVolume({folder:{getFiles:()=>files},project:'/out/project.json',profile:{vision_mode:'target_crop'},output:{fsName:'/out'},note(){},streamLimit:2,openReport:false});
    assert(calls.includes('translation_visual_ocr_page'));
    assert(degraded.failed.some(f=>f.stage==='visual_ocr'),'vision OCR failure is reported');
    assert(degraded.log.some(p=>p.status==='draft'),'vision OCR failure does not block ordinary translation and export');
    calls.length=0;staleWorker=true;
    assert.throws(()=>volumeCtx.runVolume({folder:{getFiles:()=>files},project:'/out/project.json',profile:{vision_mode:'target_crop'},output:{fsName:'/out'},note(){},streamLimit:2,openReport:false}),/worker không có tín hiệu/);
    assert(!calls.includes('translation_autopilot'),'do not start a second worker while the timed-out one may still be alive');
  }
  {
    const all=Array.from({length:9},(_,i)=>({name:String(i+1)+'.png'}));
    function MockFile(path){this.fsName=path;this.exists=true;}
    all.forEach(f=>Object.setPrototypeOf(f,MockFile.prototype));
    const batches=[],cfg={folder:{getFiles:()=>all},output:{fsName:'/out'},project:'/out/p.json',profile:{},title:'test',note(){},engine:{id:'baseline'}};
    const streamCtx={File:MockFile,MTA:{sourceNameAllowed:()=>true},latestDraftLog:()=>null,
      rpc(req){if(req.operation==='translation_load')return {runs:[],profiles:[{revision:'a'}]};return {};},
      runVolume(part){
        batches.push({indices:Array.from(part.indices),limit:part.streamLimit});
        part.indices.forEach(i=>part.sharedLog.push({page:all[i].name,status:'draft',mapped:1,required:1,files:{pdf:'/out/'+all[i].name+'.pdf'}}));
        return {log:part.sharedLog,summary:{pages:part.sharedLog.length},html:null};
      }};
    vm.createContext(streamCtx);
    vm.runInContext(source.slice(source.indexOf('        function runStreamingVolume('),source.indexOf('        // ---------- Rà soát nhanh')),streamCtx);
    const result=streamCtx.runStreamingVolume(cfg);
    assert.deepStrictEqual(batches.map(b=>b.indices),[[0,1,2,3],[4,5,6,7],[8]]);
    assert.deepStrictEqual(batches.map(b=>b.limit),[4,8,9]);
    assert.strictEqual(result.log.length,9,'all batch logs are accumulated');
    const saved={run_id:'run1',pages:[0,1,2].map(i=>({page:all[i].name,status:'draft',mapped:1,required:1,files:{pdf:'/out/'+all[i].name+'.pdf'}}))};
    streamCtx.latestDraftLog=()=>({fsName:'/out/draft_run1.json'});
    streamCtx.MTA.read=()=>JSON.stringify(saved);streamCtx.MJSON=JSON;
    streamCtx.rpc=req=>req.operation==='translation_load'?{runs:[{id:'run1',streaming:true,profile_revision:'a'}],profiles:[{revision:'a'}]}:{};
    batches.length=0;
    const resumed=streamCtx.runStreamingVolume(cfg);
    assert.deepStrictEqual(batches.map(b=>b.indices),[[3],[4,5,6,7],[8]],'resume skips existing exported pages');
    assert.strictEqual(resumed.log.length,9);
  }
  assert(source.includes('Giữ layer (nặng, sửa lại được)')&&source.includes('Phẳng (nhẹ, chỉ xem hoặc in)'));
  // Export colour is an explicit choice (keep / RGB / CMYK), never a hard-set CMYK.
  assert(!source.includes('cmykOutput'),'the hard-set CMYK checkbox is gone');
  assert(source.includes("'Giữ nguyên như ảnh gốc (khuyên dùng)', 'RGB', 'CMYK"),'three colour choices, keeping the source mode first');
  assert(source.includes('var colorMode = colorRow.add(\'dropdownlist\', undefined, colorChoices); colorMode.selection = 0;'),'default keeps the source mode');
  assert(source.includes('colorMode.selection=easyColor.selection?easyColor.selection.index:0;'),'the automatic tab passes its choice on');
  assert(source.includes('wantColor === 2 && copy.mode !== DocumentMode.CMYK')&&source.includes('wantColor === 1 && copy.mode !== DocumentMode.RGB'));
  assert(source.includes('cmykJpeg:colorModeIndex() === 2'));
  assert(source.includes('pdf_mb:'),'the log records the PDF size');
  assert(source.includes('(result.refined_shapes || {})[region.id]'),'refined balloon shape is used for lettering');
  console.log('One run per click, PDF size choices and refined shape PASS');
}
