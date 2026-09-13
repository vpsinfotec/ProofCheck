/* Live Chromium smoke test. Requires Python dev dependencies and Playwright Chromium.
 * python -m ... via PROOFCHECK_TEST_PYTHON; optional CHROMIUM_PATH for installed browsers.
 */
const { chromium } = require('playwright');
const { spawn, execFileSync } = require('node:child_process');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');
const assert = require('node:assert/strict');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'proofcheck-e2e-'));
const python=process.env.PROOFCHECK_TEST_PYTHON || path.resolve(process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
const port=18765, base=`http://127.0.0.1:${port}`;
execFileSync(python,['-c',`
from openpyxl import Workbook
from reportlab.pdfgen import canvas
from pathlib import Path
p=Path(${JSON.stringify(temp)})
w=Workbook(); w.active.append(['Last, First'])
for i in range(350): w.active.append([f'Person {i}'])
w.save(p/'delegates.xlsx')
c=canvas.Canvas(str(p/'program.pdf'))
for offset in range(0,350,35):
 for i in range(35): c.drawString(40,800-20*i,f'Person {offset+i}')
 if offset == 0:
  c.drawString(40,70,'Person Person 349')
  c.drawString(40,50,'Person 349')
 c.showPage()
c.save()
`]);
const server=spawn(python,['-m','uvicorn','proofcheck.web.app:app','--host','127.0.0.1','--port',String(port)],{
  env:{...process.env,PROOFCHECK_AUTH:'off',PROOFCHECK_DB:path.join(temp,'db.sqlite'),PROOFCHECK_REPORT_DIR:path.join(temp,'reports')},stdio:['ignore','ignore','pipe']});
let log='';server.stderr.on('data',buf=>{log+=buf.toString();});
const delay=(ms)=>new Promise(r=>setTimeout(r,ms));
(async()=>{
  let browser;
  try {
    let ready=false;
    for(let i=0;i<60;i++){try{if((await fetch(base+'/api/health')).ok){ready=true;break;}}catch{}await delay(200);}
    if(!ready)throw new Error('Server failed to start: '+log);
    browser=await chromium.launch({headless:true,...(process.env.CHROMIUM_PATH?{executablePath:process.env.CHROMIUM_PATH}:{}),args:['--no-sandbox','--disable-dev-shm-usage','--no-zygote','--single-process','--disable-gpu']});
    const page=await browser.newPage({viewport:{width:1366,height:1000}});
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base);await page.locator('#excel').waitFor();
    await page.locator('#excel').setInputFiles(path.join(temp,'delegates.xlsx'));
    await page.locator('#columns option').waitFor();
    await page.locator('#columns').selectOption('Last, First');
    await page.locator('#pdf').setInputFiles(path.join(temp,'program.pdf'));
    assert.equal(await page.locator('#run').isEnabled(),true);
    const responsePromise=page.waitForResponse(r=>r.url().endsWith('/api/check'));
    await page.locator('#run').click();
    const response=await responsePromise;assert.equal(response.status(),200);
    const payload=await response.json();assert.equal(payload.summary.exact,350);
    await page.waitForFunction(()=>document.querySelectorAll('#tables tbody tr').length===100);
    assert.match(await page.locator('#pagination').innerText(),/Page 1 of 4/);
    await page.locator('#pagination button').last().click();
    assert.match(await page.locator('#tables tbody tr').first().innerText(),/Person 100/);
    await page.locator('#search').fill('Person 349');
    await page.waitForFunction(()=>document.querySelectorAll('#tables tbody tr').length===1);
    assert.equal(payload.summary.duplicate_review,1);
    const repeated=payload.columns[0].results.find(r=>r.expected==='Person 349');
    assert.equal(repeated.occurrence_count,3);
    assert.deepEqual(repeated.occurrences,[{page:1,count:2},{page:10,count:1}]);
    assert.match(await page.locator('#tables').innerText(),/Review duplicates/);
    assert.match(await page.locator('#tables').innerText(),/Review repeated word in PDF on page 1/);
    await page.locator('#search').fill('');
    await page.locator('#statusFilter').selectOption('REVIEW');
    await page.waitForFunction(()=>document.querySelectorAll('#tables tbody tr').length===1);
    assert.match(await page.locator('#tables').innerText(),/Person 349/);
    assert.equal((await page.request.get(base+payload.report_urls.xlsx)).status(),200);
    // A cancelled file picker retains its current file and valid Run state.
    await page.locator('#excel').dispatchEvent('cancel');
    assert.equal(await page.locator('#run').isEnabled(),true);
    await page.locator('a[data-route="history"]').click();
    await page.locator('#histPanel .history-row').waitFor();
    await page.locator('a[data-route="check"]').click();
    await page.locator('#tables tbody tr').first().waitFor();
    // Mobile layout: tables scroll within the card rather than widening the page.
    await page.setViewportSize({width:390,height:844});
    await page.waitForTimeout(50);
    const sizes=await page.evaluate(()=>({width:document.documentElement.clientWidth,scroll:document.documentElement.scrollWidth}));
    assert.ok(sizes.scroll<=sizes.width+2,JSON.stringify(sizes));
    assert.deepEqual(errors,[]);
    if(process.env.PROOFCHECK_SCREENSHOT)await page.screenshot({path:process.env.PROOFCHECK_SCREENSHOT,fullPage:true});
    console.log('PASS: live upload/check, comma header, 350 exact matches, duplicate counts/words/filter, pagination/search, report download, picker cancellation, route return, mobile layout, no page errors.');
  } finally {
    if(browser)await browser.close();
    server.kill();await new Promise(resolve=>{if(server.exitCode!==null)resolve();else server.once('exit',resolve);});
    fs.rmSync(temp,{recursive:true,force:true});
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
