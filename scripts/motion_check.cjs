/* Additional V2 checks; original UI suites remain untouched. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const base=process.env.FOODFLOW_BASE_URL,out=process.env.FOODFLOW_VERIFICATION_DIR;
 fs.mkdirSync(out,{recursive:true});const browser=await chromium.launch({channel:'chrome'});
 const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage();
 const checks=[],external=[],errors=[];let posts=0;const pass=name=>checks.push({name,status:'passed'});
 context.on('request',r=>{if(new URL(r.url()).origin!==new URL(base).origin)external.push(new URL(r.url()).origin);if(r.method()==='POST')posts++});
 page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error')errors.push(m.text())});
 await page.goto(base);await page.locator('#api').filter({hasText:'disponível'}).waitFor();
 const nav=()=>page.locator('.rail-nav').evaluate(e=>getComputedStyle(e,'::before').transform);
 const before=await nav();await page.evaluate(()=>document.querySelector('[data-tab=queue]').click());
 await page.waitForTimeout(60);const middle=await nav();await page.waitForTimeout(320);const end=await nav();
 assert.notEqual(before,end);assert.notEqual(middle,end);assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Fila demonstrativa');pass('sidebar transform moves through intermediate position; focus preserved');
 await page.locator('[data-tab=care]').click();await page.getByRole('button',{name:'1. Consultar com fonte'}).click();await page.waitForTimeout(350);
 const first=await page.locator('#scenario-indicator').evaluate(e=>getComputedStyle(e).transform);
 await page.getByRole('button',{name:'2. Encaminhar e recuperar'}).click();await page.waitForTimeout(80);
 assert.notEqual(await page.locator('#scenario-indicator').evaluate(e=>getComputedStyle(e).transform),first);assert.equal(posts,0);assert.match(await page.locator('#flow-preview').innerText(),/ainda não consultado/);pass('scenario slider moves without posting or claiming consultation');
 await page.locator('#message').press('Enter');await page.locator('.confirmation').waitFor();assert.equal(await page.locator('.journey').getAttribute('data-flow'),'proposed');
 let release;const gate=new Promise(r=>release=r);let responseReady=false;
 await page.route('**/api/v1/actions/*/confirm',async route=>{const response=await route.fetch();responseReady=true;await gate;await route.fulfill({response})});
 await page.getByRole('button',{name:'Confirmar registro'}).click();
 while(!responseReady)await page.waitForTimeout(30);
 assert.equal(await page.locator('.journey').getAttribute('data-flow'),'confirming');assert.equal(await page.locator('.journey[data-flow=confirmed]').count(),0);pass('confirmation animation waits for real server response delivery');
 release();await page.waitForFunction(()=>document.querySelector('.journey').dataset.flow==='confirmed');assert.match(await page.locator('#flow-preview').innerText(),/TCK-/);pass('confirmed rail identifies server-persisted ticket');
 await page.locator('[data-tab=evidence]').focus();await page.keyboard.press('Enter');assert.equal(await page.locator('[data-tab=evidence]').getAttribute('aria-current'),'page');pass('keyboard navigation remains functional during motion');
 await page.emulateMedia({reducedMotion:'reduce'});await page.locator('[data-tab=care]').click();await page.waitForTimeout(50);
 assert.equal(await page.evaluate(()=>document.getAnimations().filter(a=>a.playState==='running').length),0);assert.equal(await page.locator('#scenario-indicator').evaluate(e=>getComputedStyle(e).transitionDuration),'0s');pass('reduced motion disables CSS and WAAPI effects');
 await page.emulateMedia({reducedMotion:'no-preference'});let maxOverflow=0;
 for(const width of [320,375,390]){await page.setViewportSize({width,height:844});await page.reload();await page.evaluate(()=>new Promise(resolve=>{let frames=0;function tick(){window.maxOverflow=Math.max(window.maxOverflow||0,document.documentElement.scrollWidth-innerWidth);if(++frames<50)requestAnimationFrame(tick);else resolve()}tick()}));maxOverflow=Math.max(maxOverflow,await page.evaluate(()=>window.maxOverflow));}
 assert.equal(maxOverflow,0);pass('mobile entrance has no horizontal overflow across animation frames');
 let bytes=0;for(const url of ['/','/static/style.css','/static/app.js','/static/motion.css','/static/motion.js','/static/favicon.svg']){const r=await context.request.get(base+url);assert(r.ok());bytes+=(await r.body()).length}assert(bytes<150000);pass('all six local visual resources below 150 KB');
 assert.deepEqual(external,[]);assert.deepEqual(errors,[]);pass('no external requests, console errors or page errors');
 fs.writeFileSync(path.join(out,'motion-results.json'),JSON.stringify({run_id:'motion-v2-'+Date.now(),browser:browser.version(),checks,bytes,maxOverflow,external_requests:0,confirmation_response:'Real backend, delivery held by test only'},null,2));console.log(JSON.stringify({passed:checks.length,bytes}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
