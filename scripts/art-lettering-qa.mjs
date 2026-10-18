// Real local inpainting + renderer; authored detector/OCR/text, not model E2E.
import {chromium} from "playwright";
import {spawn,execFile} from "node:child_process";
import {promisify} from "node:util";
import {mkdir,writeFile} from "node:fs/promises";
import {createHash} from "node:crypto";
import os from "node:os";
import path from "node:path";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output=path.join(os.tmpdir(),"mangalive-art-lettering-qa");await mkdir(output,{recursive:true});
const python=path.join(root,".venv/Scripts/python.exe"),run=promisify(execFile);
const native=await run(python,["-c",`import sys,json,time;sys.path[:0]=['scripts','companion'];from fixture_server import synthetic_art_layout;from manga_live.ocr import group_regions;from manga_live.render_cleanup import render_patch;image,d=synthetic_art_layout();regions=group_regions(image,d);translations=['Mưa vẫn chưa tạnh.','Em vẫn đợi ở đây.','Dù vậy, chị vẫn bước tiếp.'];start=time.perf_counter();patches=[]
for r,vi in zip(regions,translations):
 r.update(ja='Author-created Japanese fixture',vi=vi,review=False);p=render_patch(image,r)
 if p:patches.append(p)
print(json.dumps({'regions':regions,'patches':patches,'cleanup_ms':(time.perf_counter()-start)*1000}))`],{cwd:root,windowsHide:true,maxBuffer:4*1024*1024});
const data=JSON.parse(native.stdout);assert.equal(data.patches.length,3,"Real cleanup must support all three authored texture regions");
const fixture=spawn(python,[path.join(root,"scripts/fixture_server.py")],{cwd:root,windowsHide:true,stdio:["ignore","pipe","pipe"]});
let browser;
const report={passed:false,browser:"isolated headless Edge; Browser plugin not available",checks:{},screenshots:[],
  cleanupMs:data.cleanup_ms,limitations:["Real OpenCV masks/inpainting; detector/OCR/translation authored and native transport mocked",
    "Synthetic rain is not evidence of manual redraw quality on real manga", "No cloud/image-generation API or credits used"]};
try{
  const url=await new Promise((resolve,reject)=>{
    let pending="";const timer=setTimeout(()=>reject(new Error("Fixture startup timeout")),15000);
    fixture.on("error",reject);fixture.stdout.on("data",chunk=>{pending+=chunk;const end=pending.indexOf("\n");if(end>=0){clearTimeout(timer);resolve(JSON.parse(pending.slice(0,end)).url.replace("chapter/1","art"));}});
  });
  browser=await chromium.launch({channel:"msedge",headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],requests=[];
  page.on("pageerror",e=>errors.push(e.message));page.on("console",m=>{if(m.type()==="error")errors.push(m.text());});
  page.on("request",r=>requests.push(r.url()));
  await page.route("**/assets/PatrickHand-Regular.ttf",route=>route.fulfill({path:path.join(root,"dist/extension/assets/PatrickHand-Regular.ttf"),contentType:"font/ttf"}));
  await page.addInitScript(data=>{
    window.__qaCleanup=data;window.__qaEnabled=true;window.__qaUrls=new Set();window.__qaLast=undefined;
    const create=URL.createObjectURL,revoke=URL.revokeObjectURL;
    URL.createObjectURL=function(blob){const value=create.call(URL,blob);window.__qaUrls.add(value);return value;};
    URL.revokeObjectURL=function(value){window.__qaUrls.delete(value);return revoke.call(URL,value);};
    const attach=Element.prototype.attachShadow;
    Element.prototype.attachShadow=function(options){const shadow=attach.call(this,options);window.__qaShadow=shadow;return shadow;};
    window.chrome={runtime:{getURL(resource){return new URL(resource,location.origin+"/").href;},onMessage:{addListener(fn){window.__qaReceiver=fn;}},async sendMessage({op,params}){
      if(op==="image"){
        window.__qaLast={id:params.id,revision:params.revision};
        window.__qaCapture= params.capture?.rect;
        if(window.__qaEnabled)for(const patch of window.__qaCleanup.patches)
          window.__qaReceiver({type:"result",id:params.id,event:"render-patch",result:{revision:params.revision,width:800,height:1050,patch}}, {}, ()=>{});
        return {ok:true,result:{revision:params.revision,width:800,height:1050,regions:window.__qaCleanup.regions,metrics:{total_ms:1}}};
      }
      return {ok:true,result:{}};
    }}};
  },data);
  await page.goto(url);await page.waitForFunction(()=>document.querySelector("#page").complete);
  report.url=page.url();report.title=await page.title();assert.equal(page.url(),url);assert.match(report.title,/Chapter 1/);
  assert(await page.locator("h1").isVisible());report.checks.pageIdentity=true;report.checks.notBlank=true;
  await page.addScriptTag({path:path.join(root,"dist/extension/content.js")});
  await page.waitForFunction(()=>[...document.fonts].some(f=>f.family==="MangaLiveLettering"&&f.status==="loaded"));
  const start=()=>page.evaluate(()=>window.__mangaLive.start({storyId:"art-qa",title:"Phục hồi nền · QA",at:{chapter:1,page:0},autoScan:true,prefetch:false}));
  await start();await page.waitForFunction(()=>window.__qaShadow.querySelectorAll(".region").length===3);
  await page.waitForFunction(()=>window.__qaShadow.querySelectorAll(".region.art").length===3);
  report.checks.defaultOn=true;
  await page.evaluate(()=>{window.__mangaLive.stop();window.__qaEnabled=false;});await start();
  await page.waitForFunction(()=>window.__qaShadow.querySelectorAll(".region").length===3);
  assert.equal(await page.evaluate(()=>window.__qaShadow.querySelectorAll("img.erase,.region.art").length),0);
  report.checks.explicitOptOut=true;
  await page.evaluate(()=>{window.__mangaLive.stop();window.__qaEnabled=true;});await start();
  await page.waitForFunction(()=>window.__qaShadow.querySelectorAll(".region.art").length===3);await page.waitForTimeout(100);
  assert.equal(await page.evaluate(()=>window.__qaUrls.size),3);report.checks.realTransientPatches=true;
  const measure=()=>page.evaluate(()=>[...window.__qaShadow.querySelectorAll(".region.art")].map(node=>{
    const css=getComputedStyle(node),r=node.getBoundingClientRect();return {text:node.textContent,x:r.x,y:r.y,width:r.width,height:r.height,
      background:css.backgroundColor,border:css.borderWidth,shadow:css.boxShadow,size:parseFloat(css.fontSize),overflow:node.dataset.overflow};
  }));
  let measured=await measure();assert(measured.every(n=>n.background==="rgba(0, 0, 0, 0)"&&n.border==="0px"&&n.shadow==="none"&&n.overflow==="false"));
  report.checks.transparentTextNoCard=true;
  const before=measured[0],scroll=await page.evaluate(()=>{const previous=scrollY;scrollBy(0,160);return scrollY-previous;});
  await page.waitForTimeout(100);measured=await measure();assert(Math.abs(measured[0].y-before.y+scroll)<2);
  report.checks.scrollAligned=true;
  await page.evaluate(()=>scrollTo(0,200));await page.waitForTimeout(100);
  const desktop=path.join(output,"inpaint-desktop.png");await page.screenshot({path:desktop});report.screenshots.push(desktop);
  // Zoom-like image resize without reprocessing: text and mask share transform.
  await page.evaluate(()=>document.querySelector("#page").style.width="620px");await page.waitForTimeout(100);
  assert((await measure()).every(n=>n.overflow==="false"));report.checks.resizedWithoutReprocessing=true;
  await page.evaluate(()=>document.querySelector("#page").style.width="");
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,180));await page.waitForTimeout(150);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
  assert((await measure()).every(n=>n.size>=11&&n.overflow==="false"));report.checks.mobileReadable=true;
  const mobile=path.join(output,"inpaint-mobile.png");await page.screenshot({path:mobile});report.screenshots.push(mobile);
  await page.evaluate(()=>{window.__qaShadow.querySelector(".bar").style.visibility="hidden";[...window.__qaShadow.querySelectorAll("button")].find(b=>b.textContent==="Xem gốc").click();});
  await page.waitForTimeout(100);const restored=await page.locator("#page").screenshot();
  await page.evaluate(()=>window.__mangaLive.stop());await page.waitForTimeout(100);const original=await page.locator("#page").screenshot();
  assert.equal(createHash("sha256").update(restored).digest("hex"),createHash("sha256").update(original).digest("hex"));
  assert.equal(await page.evaluate(()=>window.__qaUrls.size),0);report.checks.originalRestoredExactly=true;report.checks.objectUrlsReleasedOnStop=true;
  // A stale async/native patch must not resurrect the stopped job.
  await page.evaluate(()=>window.__qaReceiver({type:"result",id:window.__qaLast.id,event:"render-patch",result:{revision:window.__qaLast.revision,width:800,height:1050,patch:window.__qaCleanup.patches[0]}}, {}, ()=>{}));
  await page.waitForTimeout(100);assert.equal(await page.evaluate(()=>window.__qaUrls.size),0);report.checks.latePatchRejected=true;
  // Native capture pixels arrive before translated events. At 2x scale the
  // job initially has a 400x525 CSS anchor, but the patch is 800x1050 pixels.
  await page.setViewportSize({width:1280,height:900});
  await page.evaluate(()=>{document.querySelector("#page").style.width="400px";scrollTo(0,0);});
  await start();await page.waitForFunction(()=>window.__qaShadow.querySelectorAll(".region.art").length===3);
  const anchor=await page.locator("#page").boundingBox();
  await page.evaluate(()=>window.__qaReceiver({type:"select"},{},()=>{}));
  await page.mouse.move(anchor.x,anchor.y);await page.mouse.down();await page.mouse.move(anchor.x+anchor.width,anchor.y+anchor.height,{steps:3});await page.mouse.up();
  await page.waitForFunction(()=>window.__qaCapture&&window.__qaShadow.querySelectorAll(".region.art").length===3);
  const captured=await page.evaluate(()=>window.__qaCapture);assert.equal(captured.width,400);assert.equal(captured.height,525);
  report.checks.viewportNativePixelsBeforeTranslation=true;
  await page.evaluate(()=>window.__mangaLive.stop());assert.equal(await page.evaluate(()=>window.__qaUrls.size),0);
  assert.equal(await page.locator("vite-error-overlay,nextjs-portal").count(),0);assert.deepEqual(errors,[]);
  assert(requests.every(request=>request.startsWith(new URL(url).origin)||request.startsWith("blob:")));
  report.checks.noFrameworkOverlay=true;report.checks.consoleHealth=true;report.checks.noExternalApi=true;report.passed=true;
}catch(error){report.error=error.message;process.exitCode=1;}
finally{if(browser)await browser.close();fixture.kill();await writeFile(path.join(output,"result.json"),JSON.stringify(report,null,2));console.log(JSON.stringify({...report,evidence:output},null,2));}
