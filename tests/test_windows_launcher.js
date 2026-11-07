const fs=require('fs'),vm=require('vm'),assert=require('assert');
const files=new Map(),commands=[];let launched=false;
function File(p){if(!(this instanceof File))return new File(p);this.fsName=String(p);this.parent=new Folder(this.fsName.slice(0,this.fsName.lastIndexOf('/')));}
Object.defineProperty(File.prototype,'exists',{get(){return this.fsName.endsWith('/.venv/Scripts/python.exe')||files.has(this.fsName)||(launched&&this.fsName.endsWith('/response.json'));}});
File.prototype.open=function(){return true;};File.prototype.close=function(){};File.prototype.write=function(s){files.set(this.fsName,String(s));return true;};File.prototype.read=function(){return this.fsName.endsWith('/response.json')?'{"ok":true,"result":{"worked":true}}':files.get(this.fsName);};
function Folder(p){this.fsName=String(p);this.exists=true;this.parent=this;} Folder.prototype.create=function(){return true;};
const context={File,Folder,$:{os:'Windows 11',sleep(){}},app:{system(cmd){commands.push(cmd);launched=true;}},MJSON:{parse:JSON.parse,stringify:JSON.stringify}};
vm.runInNewContext(fs.readFileSync('scripts/core.jsxinc','utf8'),context);
const result=context.MTA.request(new Folder('C:/Công việc/Manga'),{operation:'doctor'});assert(result.worked);assert(commands[0].startsWith('wscript.exe //B "'));
const vb=[...files.entries()].find(([k])=>k.endsWith('/launch.vbs'));assert(vb);assert(vb[1].includes('C:/Công việc/Manga/.venv/Scripts/python.exe'));assert(vb[1].includes('sh.Run cmd, 0, False'));assert(!vb[1].includes('cmd.exe'));
assert.throws(()=>context.MTA.request(new Folder('C:/bad%value/Manga'),{operation:'doctor'}),/đường dẫn|Đường dẫn/);
console.log('Windows launcher command construction OK (mocked; not native Windows)');
