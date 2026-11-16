/* Real rendered UI acceptance. No model or external service requests. */
const {chromium}=require('playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const base=process.env.FOODFLOW_BASE_URL||'http://127.0.0.1:8007';
 const out=process.env.FOODFLOW_VERIFICATION_DIR||path.resolve(__dirname,'../artifacts/redesign/motion');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});
 const checks=[],errors=[],external=[];const pass=name=>checks.push({name,status:'passed'});
 const context=await browser.newContext({viewport:{width:1440,height:900}});
 await context.addInitScript(()=>{window.layoutShifts=[];new PerformanceObserver(list=>{for(const e of list.getEntries())if(!e.hadRecentInput)window.layoutShifts.push(e.value)}).observe({type:'layout-shift',buffered:true})});
 context.on('request',r=>{if(new URL(r.url()).origin!==new URL(base).origin)external.push(r.url())});
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base);await page.locator('#api').filter({hasText:'disponível'}).waitFor();
 assert.equal(await page.title(),'FoodFlow AI · Control Room');pass('new Control Room resources served');
 assert.equal(await page.locator('#notice').getAttribute('aria-live'),'polite');pass('text live status retained');
 const desktop=await page.locator('.rail').boundingBox();const main=await page.locator('main').boundingBox();assert(desktop.x===0&&main.x>=desktop.width);pass('structural desktop navigation rail');
 await page.screenshot({path:path.join(out,'after-empty-1440.png'),fullPage:true});
 let chatRequests=0;page.on('request',r=>{if(r.url().endsWith('/api/v1/chat'))chatRequests++});
 await page.getByRole('button',{name:'1. Consultar com fonte'}).click();assert.equal(chatRequests,0);assert.equal(await page.locator('#scenarios [aria-pressed=true]').count(),1);assert.match(await page.locator('#message').inputValue(),/ORD-1001/);pass('scenario selection prepares composer without submitting');
 await page.locator('#message').press('Enter');await page.locator('#facts').getByText('Em preparo',{exact:true}).waitFor();
 await page.screenshot({path:path.join(out,'after-order-1440.png'),fullPage:true});
 const animation=await page.locator('.bubble').first().evaluate(e=>getComputedStyle(e).animationName);assert.equal(animation,'message-in');pass('response motion belongs to real returned message');
 await page.locator('#facts-toggle').click();assert(await page.locator('#interaction-evidence').isHidden());assert.equal(await page.locator('#facts-toggle').getAttribute('aria-expanded'),'false');
 await page.locator('#facts-toggle').click();await page.locator('#facts summary').focus();await page.keyboard.press('Escape');assert(await page.locator('#interaction-evidence').isHidden());assert.equal(await page.evaluate(()=>document.activeElement.id),'facts-toggle');await page.locator('#facts-toggle').click();pass('evidence collapse, expand, Escape and restored focus');
 let confirmRequests=0;page.on('request',r=>{if(r.url().includes('/confirm'))confirmRequests++});
 await page.getByRole('button',{name:'2. Encaminhar e recuperar'}).click();await page.locator('#message').press('Enter');await page.locator('.confirmation').waitFor();assert.equal(confirmRequests,0);
 await page.screenshot({path:path.join(out,'after-confirmation-1440.png'),fullPage:true});pass('confirmation visually distinct without automatic side effect');
 await page.getByRole('button',{name:'Confirmar registro'}).click();await page.getByText(/Solicitação (já )?registrada: TCK-/).waitFor();assert.equal(confirmRequests,1);pass('human click produces one confirmation');
 await page.locator('[data-tab=queue]').click();await page.locator('#ticket-list article').first().waitFor();assert.equal(await page.evaluate(()=>document.activeElement.textContent),'Fila demonstrativa');await page.screenshot({path:path.join(out,'after-queue-1440.png'),fullPage:true});pass('queue focus and real persisted record');
 // Rapid keyboard activation; visual snapshots must not acquire IDs/focus or issue actions.
 const initialChat=chatRequests;
 await page.evaluate(()=>{for(const id of ['evidence','care','queue','evidence','care'])document.querySelector(`[data-tab=${id}]`).click()});
 await page.waitForFunction(()=>!document.querySelector('.panel-exit'));
 assert.equal(await page.locator('.area:not([hidden])').getAttribute('id'),'care');assert.equal(await page.evaluate(()=>document.activeElement.id),'care-title');assert.equal(chatRequests,initialChat);
 assert(await page.evaluate(()=>{const ids=[...document.querySelectorAll('[id]')].map(x=>x.id);return ids.length===new Set(ids).size}));pass('rapid section transitions preserve focus, unique IDs and no chat action');
 await page.getByRole('button',{name:'3. Testar acesso e conferir'}).click();await page.locator('#message').press('Enter');await page.locator('.bubble.error').waitFor();await page.screenshot({path:path.join(out,'after-denied-1440.png'),fullPage:true});
 await page.locator('[data-tab=evidence]').click();await page.locator('#cards .card').first().waitFor();await page.screenshot({path:path.join(out,'after-evidence-1440.png'),fullPage:true});
 assert.equal(await page.locator('#cards').getAttribute('aria-busy'),'false');pass('metric loading marker clears when real response arrives');
 for(const size of [{width:1440,height:900},{width:1280,height:800},{width:390,height:844},{width:375,height:812},{width:320,height:700}]){
   const p=await context.newPage();await p.setViewportSize(size);await p.goto(base);await p.locator('#api').filter({hasText:'disponível'}).waitFor();
   assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(size.width<768){assert(await p.locator('#interaction-evidence').isHidden());await p.locator('#scenario-menu summary').click();}
   await p.getByRole('button',{name:'1. Consultar com fonte'}).click();await p.locator('#message').press('Enter');await p.locator('.bubble:not(.user)').waitFor();
   assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   if(size.width<768){for(const sel of ['#send','#customer','#facts-toggle','[data-tab=queue]'])assert((await p.locator(sel).boundingBox()).height>=44);await p.locator('#facts-toggle').click();await p.locator('#facts').getByText('Em preparo',{exact:true}).waitFor();}
   await p.screenshot({path:path.join(out,`after-${size.width}x${size.height}.png`),fullPage:true});
   pass(`viewport ${size.width}x${size.height}: no overflow, real order and accessible proof`);await p.close();
 }
 await page.locator('[data-tab=care]').click();await page.evaluate(()=>document.body.style.zoom='200%');assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));await page.evaluate(()=>document.body.style.zoom='100%');pass('200% CSS zoom reflows without clipping content');
 await page.emulateMedia({reducedMotion:'reduce'});
 await page.evaluate(()=>document.querySelector('[data-tab=queue]').click());await page.locator('#ticket-list article').first().waitFor();
 assert.equal(await page.locator('.panel-exit').count(),0);
 assert.equal(await page.locator('#queue').evaluate(e=>getComputedStyle(e).animationName),'none');
 assert.equal(await page.locator('.rail-nav').evaluate(e=>getComputedStyle(e,'::before').transitionDuration),'0s');
 assert.equal(await page.evaluate(()=>document.getAnimations().filter(a=>a.playState==='running').length),0);pass('reduced motion disables transitions including navigation pseudo-element');
 await page.locator('[data-tab=care]').focus();await page.keyboard.press('Enter');assert.equal(await page.evaluate(()=>document.activeElement.id),'care-title');pass('keyboard section activation routes focus');
 const contrasts=[];function lum(hex){const v=hex.match(/\w\w/g).map(n=>parseInt(n,16)/255).map(n=>n<=.04045?n/12.92:((n+.055)/1.055)**2.4);return v[0]*.2126+v[1]*.7152+v[2]*.0722}
 for(const [fg,bg] of [['101417','f5f4ef'],['59615f','f5f4ef'],['28150f','ff694a'],['ecf0ec','293231'],['f4f6ee','253b34'],['8d2c17','fff0e9'],['7b2a17','ffe3d8']]){const a=lum(fg),b=lum(bg),ratio=(Math.max(a,b)+.05)/(Math.min(a,b)+.05);assert(ratio>=4.5);contrasts.push({fg,bg,ratio})}pass('seven principal text color pairs meet 4.5:1');
 const cls=await page.evaluate(()=>window.layoutShifts.reduce((a,b)=>a+b,0));assert(cls<.1);pass('observed non-input layout shift below 0.1');
 let bytes=0;for(const url of ['/','/static/style.css','/static/app.js']){const r=await context.request.get(base+url);bytes+=(await r.body()).length}assert(bytes<150000);pass('HTML CSS JS below 150 KB uncompressed');
 assert.deepEqual(external,[]);assert.deepEqual(errors,[]);pass('no external UI requests or page errors');
 fs.writeFileSync(path.join(out,'redesign-results.json'),JSON.stringify({run_id:process.env.FOODFLOW_EVIDENCE_RUN_ID||'redesign-'+Date.now(),browser:browser.version(),checks,contrast:contrasts,cls,html_css_js_bytes:bytes,external_requests:external.length,limitations:['CSS zoom, not browser native zoom','No screen-reader or full WCAG certification','Motion tested via rendered styles/DOM; no video fabricated']},null,2));
 console.log(JSON.stringify({passed:checks.length,failed:0,bytes,cls}));await browser.close();
})().catch(e=>{console.error(e);process.exit(1)});
