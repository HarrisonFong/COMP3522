const fs=require('fs');const path=require('path');const {pathToFileURL,fileURLToPath}=require('url');
const {chromium}=require('C:/Users/Sena/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const root='Z:/study/yr4/sem1/comp3522/5_Part1_Finalisation/COMP3522_Geographic_Factors';
const qa=path.join(root,'qa');fs.mkdirSync(qa,{recursive:true});
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1440,height:1000},deviceScaleFactor:1});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(pathToFileURL(path.join(root,'index.html')).href);await page.waitForFunction(()=>document.querySelectorAll('#group-results tbody tr').length>0);
 const base=await page.evaluate(()=>({title:document.title,figures:document.querySelectorAll('figure').length,captions:document.querySelectorAll('figcaption').length,images:[...document.images].every(x=>x.complete&&x.naturalWidth>0),overflow:document.documentElement.scrollWidth>innerWidth}));
 const missing=[];const hrefs=await page.locator('a').evaluateAll(els=>els.map(e=>e.href));for(const href of hrefs)if(href.startsWith('file:')&&!href.includes('#')&&!fs.existsSync(fileURLToPath(href)))missing.push(href);
 const combinations=await page.evaluate(()=>{let n=0;for(const target of ['Tmax','Tmin','rain_event','rain_amount'])for(const design of ['temporal','spatial']){document.getElementById('target').value=target;document.getElementById('design').value=design;draw(true);const methods=[...document.getElementById('method').options].map(x=>x.value);for(const method of methods)for(const factor of ['elevation','coast','urban','terrain']){document.getElementById('method').value=method;document.getElementById('factor').value=factor;draw(false);const rows=[...document.querySelectorAll('#group-results tbody tr')];if(rows.length!==(factor==='terrain'?4:3))throw new Error('Wrong rows '+[target,design,method,factor]);if(document.getElementById('group-results').textContent.match(/NaN|undefined/))throw new Error('Invalid text');n++}}return n});
 await page.selectOption('#target','Tmax');await page.selectOption('#design','temporal');await page.selectOption('#method','raw');await page.selectOption('#factor','coast');
 await page.screenshot({path:path.join(qa,'desktop_top.png')});
 for(const [name,selector] of [['coast_figure','figure:nth-of-type(3)'],['model_figure','#models figure'],['interactive','#explore']]){
  const loc=page.locator(selector).first();await loc.screenshot({path:path.join(qa,name+'.png')});
 }
 await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,0));await page.screenshot({path:path.join(qa,'mobile_top.png')});
 const mobile=await page.evaluate(()=>({width:innerWidth,documentWidth:document.documentElement.scrollWidth,overflow:document.documentElement.scrollWidth>innerWidth}));
 await page.locator('#explore').screenshot({path:path.join(qa,'mobile_interactive.png')});
 const result={passed:errors.length===0&&missing.length===0&&base.images&&!base.overflow&&!mobile.overflow&&base.figures===7&&base.captions===7,desktop:base,mobile,interactive_combinations:combinations,missing_local_links:missing,javascript_errors:errors};
 fs.writeFileSync(path.join(qa,'browser_verification.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));await browser.close();if(!result.passed)process.exitCode=1;
})().catch(e=>{console.error(e);process.exit(1)});
