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
  assert(source.indexOf('var chk=easyEnvCheck();')<source.indexOf('var count=easyFiles().length'),'environment is checked before any work');
  for(const label of ['Engine xoá chữ:','Kiểm tra môi trường','Đổi thư mục lưu kết quả','Sẽ chạy:'])assert(source.includes(label),label);
  assert(source.includes("var out=MTA.mkdir(easyOutFolder().fsName)"));
  assert(source.includes('easyEngineChoice.selection?easyEngineChoice.selection.index:0'));
  console.log('Automatic tab environment, engine and output folder PASS');
}

// One click, one run; PDF size choices are visible; lettering uses the refined balloon when present.
{
  assert(source.includes('if(easyRunning||(new Date()).getTime()-easyLastEnd<1500)return;'),'a queued second click must not start a second run');
  assert(source.includes('easyRunning=false;easyLastEnd=(new Date()).getTime();'));
  assert(source.includes('Giữ layer (nặng, sửa lại được)')&&source.includes('Phẳng (nhẹ, chỉ xem hoặc in)'));
  assert(source.includes('cmykOutput.value=easyCmyk.value===true'),'CMYK is opt-in in the automatic tab');
  assert(source.includes('easyCmyk.value=false'));
  assert(source.includes('pdf_mb:'),'the log records the PDF size');
  assert(source.includes('(result.refined_shapes || {})[region.id]'),'refined balloon shape is used for lettering');
  console.log('One run per click, PDF size choices and refined shape PASS');
}
