const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const { JSDOM } = require('jsdom');
const html = fs.readFileSync('proofcheck/web/static/index.html', 'utf8');
const source = fs.readFileSync('proofcheck/web/static/app.js', 'utf8').replace(/boot\(\);\s*$/, '');
const tick = () => new Promise(resolve => setImmediate(resolve));

function setup() {
  const dom = new JSDOM(html, { url: 'http://localhost/#/check', runScripts: 'outside-only', pretendToBeVisual: true });
  const w = dom.window;
  w.fetch = async () => ({ok: true, json: async () => ({version: 'test', ocr_available: true, auth_enabled: false, max_upload_bytes: 50*1024*1024})});
  w.eval(source + '; window.testApp = { state, api, checkView, renderResults, renderTables, errorMessage, historyView, loginView };');
  w.testApp.state.health = {ocr_available: true, max_upload_bytes: 50*1024*1024};
  w.testApp.checkView();
  return { dom, w, app: w.testApp, get: (id) => w.document.getElementById(id) };
}
function file(ctx, id, name='sample.xlsx') {
  const value = new ctx.w.File(['data'], name);
  Object.defineProperty(ctx.get(id), 'files', {value:[value], configurable:true});
  ctx.get(id).dispatchEvent(new ctx.w.Event('change'));
}
const inspected = {sheets:['Main'],headers:{Main:['Last, First','City']}};


test('only a successfully inspected file and selected columns enable Run', async () => {
  const ctx=setup(); const {app,get}=ctx;
  let resolve;
  app.api.form=()=>new Promise(r=>{resolve=r;});
  file(ctx,'excel'); file(ctx,'pdf','doc.pdf');
  assert.equal(get('run').disabled,true);
  resolve(inspected); await tick();
  assert.equal(get('run').disabled,true);
  get('columns').options[0].selected=true;
  get('columns').dispatchEvent(new ctx.w.Event('change'));
  assert.equal(get('run').disabled,false);
  await tick(); ctx.dom.window.close();
});

test('out-of-order inspect replies cannot replace the newer workbook',async()=>{
  const ctx=setup(); const replies=[];
  ctx.app.api.form=()=>new Promise(r=>replies.push(r));
  file(ctx,'excel','old.xlsx'); file(ctx,'excel','new.xlsx');
  replies[1]({sheets:['New'],headers:{New:['New column']}}); await tick();
  replies[0]({sheets:['Old'],headers:{Old:['Old column']}}); await tick();
  assert.equal(ctx.get('sheet').value,'New');
  assert.equal(ctx.get('columns').options[0].value,'New column');
  await tick(); ctx.dom.window.close();
});

test('duplicate submissions are blocked and punctuation in headers is preserved',async()=>{
  const ctx=setup(); let checks=0,finish,fields;
  ctx.app.api.form=async(url,fd)=>{
    if(url.endsWith('inspect')) return inspected;
    checks++; fields=fd; return new Promise(resolve=>{finish=resolve;});
  };
  file(ctx,'excel'); await tick(); file(ctx,'pdf','doc.pdf');
  ctx.get('columns').options[0].selected=true;
  ctx.get('columns').dispatchEvent(new ctx.w.Event('change'));
  ctx.get('run').click(); ctx.get('run').click();
  assert.equal(checks,1);
  assert.equal(fields.get('columns_json'),'["Last, First"]');
  assert.equal(ctx.get('excel').disabled,true);
  finish(result(1)); await tick();
  assert.equal(ctx.get('excel').disabled,false);
  assert.equal(ctx.get('run').disabled,false);
  await tick(); ctx.dom.window.close();
});

function result(count) {
  return {summary:{total:count,exact:count,fuzzy:0,missing:0,skipped:0,pass_rate:1},warnings:[],report_urls:{html:'/reports/id.html',xlsx:'/reports/id.xlsx'},
    columns:[{name:'Names',results:Array.from({length:count},(_,i)=>({row:i+2,expected:i===0?'<img src=x onerror=alert(1)>':`Person ${i}`,status:'EXACT',page:1,score:100,source:'text',diff:[]}))}]};
}

test('large results render at most 100 rows; pagination and search work; values are escaped',async()=>{
  const ctx=setup(); const data=result(20050); ctx.app.state.lastResult=data;
  ctx.app.renderResults(data);
  assert.equal(ctx.w.document.querySelectorAll('#tables tbody tr').length,100);
  assert.equal(ctx.w.document.querySelector('#tables img'),null);
  ctx.w.document.querySelector('#pagination button:last-child').click();
  assert.match(ctx.get('tables').textContent,/Person 100/);
  ctx.get('search').value='Person 20049';ctx.app.renderTables();
  assert.equal(ctx.w.document.querySelectorAll('#tables tbody tr').length,1);
  await tick(); ctx.dom.window.close();
});

test('late history response does not overwrite another route',async()=>{
  const ctx=setup();let resolve;
  ctx.app.api.history=()=>new Promise(r=>{resolve=r;});
  const pending=ctx.app.historyView();ctx.app.checkView();
  resolve({runs:[]});await pending;
  assert.ok(ctx.get('checkPanel'));
  await tick(); ctx.dom.window.close();
});

test('API validation arrays become readable errors',async()=>{
  const ctx=setup();
  assert.equal(ctx.app.errorMessage({detail:[{loc:['body','ocr_dpi'],msg:'Too high'}]},''),'ocr_dpi: Too high');
  await tick(); ctx.dom.window.close();
});

test('failed inspection clears stale columns and keeps Run disabled',async()=>{
  const ctx=setup();ctx.app.api.form=async()=>inspected;
  file(ctx,'excel');await tick();
  ctx.app.api.form=async()=>{throw new Error('Invalid workbook');};
  file(ctx,'excel','bad.xlsx');await tick();
  assert.equal(ctx.get('columns').options.length,0);
  assert.equal(ctx.get('run').disabled,true);
  assert.match(ctx.get('msgs').textContent,/Invalid workbook/);
  await tick(); ctx.dom.window.close();
});

test('duplicate review is visible, filterable and safely escaped alongside exact results',async()=>{
  const ctx=setup(), data=result(3);
  data.summary.duplicate_review=2;
  Object.assign(data.columns[0].results[0],{expected:'Areeb Khan',needs_review:true,occurrence_count:3,
    occurrences:[{page:1,count:2},{page:4,count:1}],repeated_words:[]});
  Object.assign(data.columns[0].results[1],{expected:'Areeb Areeb Khan',needs_review:true,occurrence_count:1,
    occurrences:[{page:1,count:1}],repeated_words:[{word:'<img src=x onerror=alert(1)>',count:2,page:null},{word:'areeb',count:2,page:1}]});
  ctx.app.state.lastResult=data;ctx.app.renderResults(data);
  assert.match(ctx.get('results').textContent,/Review duplicates in 2 value/);
  assert.match(ctx.get('tables').textContent,/page 1: 2; page 4: 1/);
  assert.match(ctx.get('tables').textContent,/Review repeated word in spreadsheet value/);
  assert.match(ctx.get('tables').textContent,/PDF on page 1: “areeb”/);
  assert.equal(ctx.w.document.querySelector('#tables img'),null);
  ctx.get('statusFilter').value='REVIEW';
  ctx.get('statusFilter').dispatchEvent(new ctx.w.Event('change'));
  assert.equal(ctx.w.document.querySelectorAll('#tables tbody tr').length,2);
  ctx.get('search').value='Areeb Areeb';ctx.app.renderTables();
  assert.equal(ctx.w.document.querySelectorAll('#tables tbody tr').length,1);
  ctx.get('statusFilter').value='EXACT';ctx.get('search').value='';ctx.app.renderTables();
  assert.equal(ctx.w.document.querySelectorAll('#tables tbody tr').length,3);
  await tick();ctx.dom.window.close();
});
