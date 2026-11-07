#target photoshop
#include "../scripts/json.jsxinc"
#include "../scripts/core.jsxinc"
(function(){
 var root=new File($.fileName).parent.parent;
 // Copy docs/validation/photoshop-smoke.example.json to work/smoke/config.json.
 // Source images and generated PSDs stay local; each run gets its own folder.
 var cfgFile=new File(root.fsName+'/work/smoke/config.json');
 if(!cfgFile.exists){$.global.alert('Thiếu work/smoke/config.json. Xem docs/validation/photoshop-smoke.md.');return;}
 var cfg;try{cfg=MJSON.parse(MTA.read(cfgFile));}catch(configError){$.global.alert('Config smoke không hợp lệ: '+String(configError.message || configError));return;}
 function localPath(value){return new File(root.fsName+'/'+value).fsName;}
 var input=new Folder(localPath(cfg.input || 'work/smoke/input'));
 var sources=input.getFiles(function(f){return f instanceof File && MTA.sourceNameAllowed(f.name);});
 if(!sources.length){$.global.alert('Không có ảnh nguồn trong '+input.fsName);return;}
 var output=MTA.mkdir(localPath(cfg.output || 'work/smoke/output')+'/run_'+MTA.unique());
 var count=app.documents.length,initial=count?app.activeDocument:null,report={ok:false,ui_version:MTA.uiVersion,quality_ground_truth:false,review_checks:[],messages:[],expected_engine:null,input:input.fsName,output:output.fsName};
 var started=(new Date()).getTime();
 function alert(s){report.messages.push(String(s));}function confirm(){return true;}
 function assert(v,s){if(!v)throw Error(s);}
 function replaceOnce(code,needle,replacement){
  assert(code.indexOf(needle)>=0 && code.indexOf(needle)===code.lastIndexOf(needle),'UI test hook changed: '+needle);
  return code.replace(needle,replacement);
 }
 try{
  var code=MTA.read(new File(root.fsName+'/Photoshop_Typeset.jsx')).replace(/^#.*$/gm,'');
  code=replaceOnce(code,'var root = new File($.fileName).parent;','var root=new Folder('+MJSON.stringify(root.fsName)+');');
  code=replaceOnce(code,'MTA.confirmChapter(order,','(function(){return true;})(order,');
  code=replaceOnce(code,'win.center(); win.show();',"for(var ei=0;ei<engines.length;ei++)if(engines[ei].id==='1107'){engineChoice.selection=ei;report.expected_engine=engines[ei].version;}engineChoice.onChange();tabs.selection=engineTab;var startTest=win.add('button',undefined,'Chạy smoke engine 1107');startTest.onClick=function(){inputFolder=input;outputFolder=output;lang.selection=lang.find(cfg.language || 'jpn_vert');aiDetector.value=true;detailChoice.selection=1;reviewAll.value=true;batchCleanOnly.value=true;png.value=true;cmykOutput.value=cfg.cmyk!==false;syncInputs();chapter.onClick();win.close();};win.layout.layout(true);win.center();win.show();");
  code=replaceOnce(code,'if (dlg.show() !== 1)',"if ((function(){\n var testButton=dlg.add('button',undefined,'Ki\u1ec3m tra m\u1ecdi v\u00f9ng r\u1ed3i x\u00e1c nh\u1eadn');\n testButton.onClick=function(){\n  var check={page:s.doc.name,manifest:s.manifestPath,regions:[],ok:false};\n  try {\n   for(var ti=0;ti<regions.length;ti++){\n    list.selection=ti;list.onChange();\n    check.regions.push({id:regions[ti].id,baseline_auto_clean:regions[ti].auto_clean,checkbox:cleanBox.value,checkbox_enabled:cleanBox.enabled,mapping_before:mapping[ti].clean});\n    assert(cleanBox.enabled===true,'UI locked '+regions[ti].id);\n    assert(cleanBox.value===true,'UI dropped '+s.doc.name+'/'+regions[ti].id);\n    commit();assert(mapping[ti].clean===true,'Commit dropped '+regions[ti].id);assert(mapping[ti].force===false,'Unexpected force '+regions[ti].id);\n   }\n   if(regions.length){\n    list.selection=0;list.onChange();cleanBox.value=false;commit();\n    if(regions.length>1){list.selection=1;list.onChange();}\n    list.selection=0;list.onChange();assert(cleanBox.value===false,'Explicit opt-out lost');\n    cleanBox.value=true;commit();\n   }\n   check.final_mapping=MJSON.parse(MJSON.stringify(mapping));check.opt_out_preserved=true;check.ok=true;\n   report.review_checks.push(check);\n   MTA.write(new File(output.fsName+'/review_checks.json'),MJSON.stringify(report.review_checks));\n   accept.value=true;ok.notify('onClick');\n  } catch(err){check.error=String(err.message||err);report.review_checks.push(check);MTA.write(new File(output.fsName+'/review_checks.json'),MJSON.stringify(report.review_checks));dlg.close(0);}\n };\n dlg.layout.layout(true);return dlg.show();\n})()\n !== 1)");
  eval(code);
  var logs=output.getFiles('batch_*.json');assert(logs.length===1,'Expected one batch log');
  var rows=MJSON.parse(MTA.read(logs[0]));report.rows=rows;assert(report.review_checks.length===sources.length,'Missing review dialogs');assert(rows.length===sources.length,'Expected '+sources.length+' pages, got '+rows.length);
  for(var i=0;i<rows.length;i++){
   var row=rows[i];assert(row.ok && row.psd,'Failed '+row.source+': '+row.error);assert(row.engine_id==='1107','Wrong engine '+row.source);assert(row.engine_version===report.expected_engine,'Wrong backend version');var ft=MJSON.parse(MTA.read(new File(row.clean_trace)));assert(ft.flat_finish,'Missing integrated finish stage');assert(row.ui_version===MTA.uiVersion,'Wrong UI version '+row.source);
   var doc=app.open(new File(row.psd));try{if(cfg.cmyk!==false)assert(doc.mode===DocumentMode.CMYK,'PSD is not CMYK');if(row.clean_mask_pixels>0){var overlay=doc.artLayers.getByName('CLEAN AI THỬ NGHIỆM — KIỂM TRA');assert(overlay.visible,'Overlay hidden '+row.source);var snapFolder=MTA.mkdir(output.fsName+'/composites/'+i);row.composite_rgb=MTA.snapshot(doc,snapFolder).fsName;row.psd_mode=String(doc.mode);row.psd_profile=doc.colorProfileName;row.overlay_bounds=MTA.bounds(overlay);}}finally{doc.close(SaveOptions.DONOTSAVECHANGES);}
  }
  assert(app.documents.length===count,'Document count changed');report.ok=true;
 }catch(e){report.error=String(e.message||e);report.line=e.line;}
 finally{if(initial)app.activeDocument=initial;report.seconds=((new Date()).getTime()-started)/1000;MTA.write(new File(output.fsName+'/photoshop_1107_e2e.json'),MJSON.stringify(report));MTA.write(new File(root.fsName+'/work/smoke/latest.json'),MJSON.stringify({report:output.fsName+'/photoshop_1107_e2e.json',ok:report.ok}));}
 return MJSON.stringify(report);
})();
