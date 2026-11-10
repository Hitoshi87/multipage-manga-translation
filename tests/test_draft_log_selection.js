const fs = require('fs'), vm = require('vm'), assert = require('assert');
const source = fs.readFileSync('Photoshop_Typeset.jsx','utf8');
const data = {
  '/out/draft_old.json':JSON.stringify({project:'/out/project.json',run_id:'current'}),
  '/out/draft_new.json':JSON.stringify({project:'/out/project.json',run_id:'different'})
};
function File(path){this.fsName=path;this.exists=Object.prototype.hasOwnProperty.call(data,path);this.modified=new Date(path.includes('new')?2000:1000);}
const folder={exists:true,getFiles:pattern=>Object.keys(data).filter(p=>pattern.endsWith('.bak')?p.endsWith('.json.bak'):p.endsWith('.json')).map(p=>new File(p))};
const ctx={File,MJSON:JSON,MTA:{read(file){if(!file.exists)throw Error('missing');return data[file.fsName];}}};
vm.createContext(ctx);
vm.runInContext(source.slice(source.indexOf('        function latestDraftLog('),source.indexOf('        var reviewDoc=')),ctx);
assert.strictEqual(ctx.latestDraftLog(folder,'/out/project.json','current').fsName,'/out/draft_old.json','newer unrelated run must not shadow the active checkpoint');
data['/out/draft_new.json']='{';
data['/out/draft_new.json.bak']=JSON.stringify({project:'/out/project.json',run_id:'current'});
assert.strictEqual(ctx.latestDraftLog(folder,'/out/project.json','current').fsName,'/out/draft_new.json.bak','a readable backup for the active run can recover a corrupt primary');
assert.strictEqual(ctx.latestDraftLog(folder,'/out/project.json','missing'),null);
delete data['/out/draft_old.json'];delete data['/out/draft_new.json'];
assert.strictEqual(ctx.latestDraftLog(folder,'/out/project.json','current').fsName,'/out/draft_new.json.bak','orphaned backup remains discoverable if the primary is missing');
console.log('Draft checkpoints matched by project and run PASS');
