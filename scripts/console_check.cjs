const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{const browser=await chromium.launch({channel:'chrome'}),page=await browser.newPage();const errors=[],failed=[];
page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});page.on('pageerror',e=>errors.push(e.message));page.on('requestfailed',r=>failed.push(new URL(r.url()).pathname));
await page.goto(process.env.FOODFLOW_BASE_URL);await page.locator('#api').filter({hasText:'disponível'}).waitFor();
for(const id of ['queue','evidence','care']){await page.locator(`[data-tab=${id}]`).click();await page.waitForLoadState('networkidle')}
assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
const out=process.env.FOODFLOW_VERIFICATION_DIR;fs.mkdirSync(out,{recursive:true});fs.writeFileSync(path.join(out,'console-results.json'),JSON.stringify({scope:'real final EXE, initial page and three sections',console_errors:errors,failed_requests:failed,status:'PASSED'},null,2));console.log('Console and section requests: PASSED');await browser.close()})().catch(e=>{console.error(e);process.exit(1)});
