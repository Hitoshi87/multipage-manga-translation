// Pure-arithmetic checks of MTA.planLayout; Photoshop metrics are not exercised here.
const fs=require('fs'),vm=require('vm'),assert=require('assert');
const ctx={};vm.createContext(ctx);vm.runInContext(fs.readFileSync('scripts/core.jsxinc','utf8'),ctx);
const {planLayout}=ctx.MTA;
// A placed block can fit its bounding rectangle while a long middle line crosses
// a curved bubble boundary. The fixture uses the re-detected shape and PDF word
// boxes from page 100, in the same 1434x2048 coordinate system.
{
  const fixture=JSON.parse(fs.readFileSync('tests/fixtures/lettering_overflow_100.json','utf8'));
  const lines=['a','b','c','d'], leading=34.79347;
  const measure=line=>{
    const i=lines.indexOf(line),b=fixture.pdf_word_boxes[i];
    return [b[0],b[1]-i*leading,b[2],b[3]-i*leading];
  };
  assert.strictEqual(ctx.MTA.placedLinesFit(fixture.shape,lines,leading,measure),false,
    'the observed third line crossing the bubble must be rejected');
  const rows=[];for(let y=0;y<100;y++)rows.push([y,0,100]);
  const shape={rows,box:[0,0,100,100],center:[50,50]};
  assert.strictEqual(ctx.MTA.placedLinesFit(shape,['a','b'],20,()=>[25,10,75,20]),true);
  assert.strictEqual(ctx.MTA.placedLinesFit(shape,['a','b'],20,line=>line==='b'?[-1,10,40,20]:[25,10,75,20]),false);
  console.log('Placed line bounds checked against bubble PASS');
}
let calls=0;const unit=s=>{calls++;return s.length*.5;};
function ellipse(cx,cy,rx,ry,reportedCenter){
  const rows=[];for(let y=Math.ceil(cy-ry)+1;y<Math.floor(cy+ry);y++){
    const k=Math.sqrt(1-((y-cy)/ry)**2);rows.push([y,Math.round(cx-rx*k),Math.round(cx+rx*k)]);}
  return {box:[cx-rx,cy-ry,2*rx,2*ry],center:reportedCenter||[cx,cy],rows};}
const text=['Cậu đang nói cái gì vậy hả tớ chẳng hiểu gì cả'];
const o={min:10,max:80,leading:1.1};
const round=planLayout(ellipse(200,150,120,90),text,unit,1,o);
assert(round&&round.size>o.min,'ellipse should fit above the minimum');
// every planned line must lie inside the ellipse at its own band
round.lines.forEach((l,i)=>assert(unit(l)*round.size<=240,'line wider than bubble'));
// Reported centre is 25px off: the planner derives the centre from the rows instead.
const off=ellipse(200,150,120,90,[175,150]);
const shifted=planLayout(off,text,unit,1,o);
assert(Math.abs(shifted.dx)<=1,'a wrongly reported centre must be ignored in favour of the row geometry');
const centred=planLayout(ellipse(200,150,120,90),text,unit,1,o);
assert(Math.abs(shifted.size-centred.size)<=1.5,'size should not depend on the reported centre');
// Too long for the minimum size -> null instead of overflowing.
assert.strictEqual(planLayout(ellipse(60,40,40,30),['x '.repeat(200)],unit,1,{min:20,max:60,leading:1.1}),null);
// Short text is capped by max, not by an ever-shrinking fit.
assert.strictEqual(planLayout(ellipse(200,150,120,90),['Ừ'],unit,1,o).size,80);
// Planning cost is independent of Photoshop: unit width is only string arithmetic.
console.log('Lettering planner PASS; width lookups:',calls);
// Review hints
const flags=ctx.MTA.layoutFlags([{id:'a',size:30,fill:.4},{id:'b',size:31,fill:.4},{id:'c',size:20,fill:.4},{id:'d',size:10,fill:.4},{id:'e',size:40,fill:.05},{id:'f',size:80,fill:.02}],{min:10,max:80});
const byId=Object.fromEntries(Array.from(flags).map(f=>[f.id,Array.from(f.flags)]));
assert.deepStrictEqual(byId.c,['small_vs_page']);assert.deepStrictEqual(byId.d,['at_min_size']);
assert.deepStrictEqual(byId.e,['low_fill']);assert(!byId.f,'short text capped by max is not a problem');assert(!byId.a);
const done=ctx.MTA.finishedPages([{ok:true,status:'processed',source:'1.png'},{ok:true,status:'review_required',source:'2.png'},{ok:false,source:'3.png'},{ok:true,status:'partial',source:'4.png'}]);
assert.deepStrictEqual(Object.keys(done),['1.png','4.png']);
console.log('Review flags and resume bookkeeping PASS');
// Notched bubble: right part of the top rows is cut away, so the block must
// move left and use the roomy lower-left area instead of shrinking.
{
  const rows=[];for(let y=0;y<100;y++)rows.push([y,0,y<40?60:200]);
  const notch={box:[0,0,200,100],center:[100,50],rows};
  const u=s=>s.length*.5,t=['Mỗi ngày vào nửa đêm những câu chuyện vẩn vơ'];
  const p=planLayout(notch,t,u,1,{min:8,max:40,leading:1.1});
  assert(p&&p.size>=14,'notched bubble should not collapse to tiny text, got '+(p&&p.size));
  console.log('Notched bubble size',p.size,'dx',p.dx.toFixed(1),'lines',p.lines.length);
}
// Page-level cap: 1.25 x median, never below the minimum size, undefined for an empty page.
assert.strictEqual(ctx.MTA.pageSizeCap([20,24,28,60],1.25,10),1.25*24);
assert.strictEqual(ctx.MTA.pageSizeCap([38,62],1.25,10),1.25*38);
assert.strictEqual(ctx.MTA.pageSizeCap([4],1.25,10),10);
assert.strictEqual(ctx.MTA.pageSizeCap([],1.25,10),undefined);
console.log('Page size cap PASS');
// Japanese brackets/full-width marks are replaced for display so comic fonts do not draw boxes.
{
  const n=ctx.MTA.normalizeQuotes;
  assert.strictEqual(n('…và nói\u300cEm yêu anh\u300dđi.'),'…và nói \u201cEm yêu anh\u201d đi.');
  assert.strictEqual(n('\u300eMayonaka\u300f'),'\u201cMayonaka\u201d');
  assert.strictEqual(n('Thầy ơi\uff01\uff1f'),'Thầy ơi!?');
  assert.strictEqual(n('Ừ nhé\u2661'),'Ừ nhé\u2661');
  assert.strictEqual(n('Giỏi\u266a\u266a'),'Giỏi\u266a\u266a');
  assert.strictEqual(n('Hay quá\u2605'),'Hay quá\u2605');
  assert.strictEqual(n('Đã “ổn” rồi.'),'Đã “ổn” rồi.');
  console.log('Quote normalisation PASS');
}
// Readable breaks: no word stranded on its own line, no break straight after an opening quote.
{
  const u=s=>s.length*.5;
  const shape=ellipse(150,110,95,100);
  const text=['…và nói “Em yêu anh” đi.'];
  const plan=planLayout(shape,text,u,1,{min:10,max:56,leading:1.1});
  const lines=Array.from(plan.lines);
  lines.forEach(l=>assert(!/[“‘(]$/.test(l),'break after opening quote: '+l));
  assert(!lines.some(l=>l==='yêu'||l==='…và'||l==='đi.'),'stranded word: '+lines.join(' | '));
  const scored=ctx.MTA.wrapScored(['một hai ba bốn'],[9,9],s=>s.length);
  assert(scored&&Array.from(scored.lines).join('|')==='một hai|ba bốn');
  console.log('Readable breaks PASS ->',lines.join(' | '),'size',plan.size.toFixed(1));
}
// Vertical centring: a balloon with a long pointed tail must not pull the text off the body's centre.
{
  const rows=[];for(let y=0;y<100;y++)rows.push([y,0,200]);                 // body 0..99
  for(let y=100;y<160;y++)rows.push([y,90,110]);                          // thin tail
  const shape={box:[0,0,200,160],center:[100,95],rows};                    // centroid is dragged down
  const u=s=>s.length*.5;
  const p=planLayout(shape,['Đó mà là ưu điểm?'],u,1,{min:10,max:40,leading:1.1});
  const blockCentre=p.cy;
  assert(Math.abs(blockCentre-50)<=6,'block centre should stay near body centre 50, got '+blockCentre);
  console.log('Vertical centring PASS: centre',blockCentre.toFixed(1),'size',p.size.toFixed(1));
}
// Shared display-normalisation cases (the Python module reads the same file).
{
  const cases=JSON.parse(fs.readFileSync('tests/fixtures/textnorm_cases.json','utf8'));
  cases.forEach(c=>{
    const got=ctx.MTA.normalizeText(c.in,c.case||'sentence');
    assert.strictEqual(got,c.out,'normalizeText('+JSON.stringify(c.in)+') -> '+JSON.stringify(got)+' expected '+JSON.stringify(c.out));
    // Idempotent: lettering a display string again must not change it.
    assert.strictEqual(ctx.MTA.normalizeText(got,c.case||'sentence'),got,'not idempotent: '+JSON.stringify(c.in));
  });
  console.log('Text normalisation parity PASS ('+cases.length+' cases)');
}
