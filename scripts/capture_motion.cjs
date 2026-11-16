/* Real application recording, no mocked API, no artificial delay in product. */
const {chromium}=require('playwright');const fs=require('node:fs'),path=require('node:path');
(async()=>{
 const out=process.env.FOODFLOW_VERIFICATION_DIR,base=process.env.FOODFLOW_BASE_URL;fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome'}),context=await browser.newContext({viewport:{width:1440,height:1000},recordVideo:{dir:out,size:{width:1440,height:1000}}}),page=await context.newPage();
 const start=Date.now(),pause=()=>page.waitForTimeout(2400);
 await page.goto(base);await page.locator('#api').filter({hasText:'disponível'}).waitFor();await pause();
 await page.locator('.intro').hover();await pause();
 await page.locator('[data-tab=queue]').hover();await page.locator('[data-tab=queue]').click();await pause();
 await page.locator('[data-tab=evidence]').click();await pause();await page.locator('[data-tab=care]').click();
 await page.getByRole('button',{name:'1. Consultar com fonte'}).click();await pause();await page.locator('#message').press('Enter');await page.locator('#facts').getByText('Em preparo',{exact:true}).waitFor();await pause();
 await page.getByRole('button',{name:'2. Encaminhar e recuperar'}).click();await pause();await page.locator('#message').press('Enter');await page.locator('.confirmation').waitFor();await pause();
 await page.getByRole('button',{name:'Confirmar registro'}).click();await page.getByText(/Solicitação (já )?registrada: TCK-/).waitFor();await pause();
 await page.locator('#facts-toggle').click();await pause();await page.locator('#facts-toggle').click();await pause();
 await page.screenshot({path:path.join(out,'video-final-frame.png'),fullPage:true});
 const elapsed=(Date.now()-start)/1000,video=page.video();await context.close();await video.saveAs(path.join(out,'FoodFlow-Motion-V2.webm'));const original=await video.path();if(path.basename(original)!=='FoodFlow-Motion-V2.webm')fs.unlinkSync(original);
 fs.writeFileSync(path.join(out,'video.json'),JSON.stringify({source:'Actual Windows EXE served over loopback; Playwright Chrome screen recording',duration_wall_seconds:elapsed,format:'WebM/VP8',api_mocks:false,viewport:'1440x1000',note:'Available bundled encoder has no MP4/GIF encoder; no installation performed'},null,2));await browser.close();console.log('Real recording: '+elapsed.toFixed(1)+' s');
})().catch(e=>{console.error(e);process.exit(1)});
