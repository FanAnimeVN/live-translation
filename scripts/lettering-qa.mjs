// Real balloon geometry and packaged font; authored translations/native mocked.
// This proves rendering, never OCR/translation quality or end-to-end latency.
import {chromium} from "playwright";
import {spawn,execFile} from "node:child_process";
import {promisify} from "node:util";
import {mkdir,readFile,writeFile} from "node:fs/promises";
import {createHash} from "node:crypto";
import os from "node:os";
import path from "node:path";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";
import {assertRenderedTranslations} from "./rendered-translation-check.mjs";
import {findLetteringBoxOverlaps} from "./lettering-overlap-check.mjs";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const realCrops=process.argv.includes("--real-crops");
const expressive=process.argv.includes("--expressive");
const nativeIndex=process.argv.indexOf("--native-result"),nativePath=nativeIndex>=0?process.argv[nativeIndex+1]:undefined;
assert(nativeIndex<0||(nativePath&&!nativePath.startsWith("--")),"Explicit native result path required");
assert(!nativePath||(!realCrops&&!expressive),"Native authored evidence cannot be mixed with another fixture mode");
const output=path.join(os.tmpdir(),nativePath?"mangalive-lettering-native-result-qa":expressive?"mangalive-expressive-lettering-qa":realCrops?"mangalive-lettering-real-crops-qa":"mangalive-lettering-qa");await mkdir(output,{recursive:true});
const python=path.join(root,".venv/Scripts/python.exe"),run=promisify(execFile);
const geometry=await run(python,["-c",`import sys,json,hashlib;sys.path[:0]=['scripts','companion'];from fixture_server import synthetic_layout,synthetic_detected_layout,synthetic_page;from manga_live.ocr import group_regions;${realCrops?"image,detections,glyphs=synthetic_detected_layout()":"image,detections=synthetic_layout();glyphs=detections"};print(json.dumps({'regions':group_regions(image,detections),'detections':glyphs,'sourcePngSha256':hashlib.sha256(synthetic_page()).hexdigest()}))`],{cwd:root,windowsHide:true});
const {regions,detections,sourcePngSha256}=JSON.parse(geometry.stdout);
const translations=expressive?["Tô-i… đââây!","Tôi…   yêu…   em.","E M   Y Ê U   A N H","DỪNG LẠI!"]:
  ["Nee-chan, chưa về à?","Em cứ về trước đi. Chị sẽ đến sau.","Triển khai Kết giới băng giá!","Ngày mai không cần đến đâu."];
const sources=expressive?["わ・た・し〜〜！","わたし…好き…あなた…","I L O V E Y O U","STOP!"]:translations.map(()=>"Author-created fixture dialogue");
let nativeEvidence;
if(nativePath){
  const raw=await readFile(nativePath);assert(raw.length<=4*1024*1024,"Native evidence exceeds bound");
  nativeEvidence=JSON.parse(raw);
  assert.equal(nativeEvidence.passed,true);assert.equal(nativeEvidence.source,"author-created four-bubble image only");
  assert.equal(nativeEvidence.sourcePngSha256,sourcePngSha256,"Native output belongs to a different source image");
  const result=nativeEvidence.runs.find(row=>row.name==="cold")?.native;
  assert(result&&result.width===800&&result.height===1050&&result.regions.length===4,"Incomplete native fixture");
  regions.splice(0,regions.length,...result.regions);
}else regions.forEach((r,i)=>Object.assign(r,{ja:sources[i],vi:translations[i],ambiguous:true}));
if(expressive){
  const metadata=await run(python,["-c","import sys,json;sys.path.insert(0,'companion');from manga_live.expression import bind_expression;print(json.dumps([bind_expression(r) for r in json.loads(sys.argv[1])]))",JSON.stringify(regions)],{cwd:root,windowsHide:true});
  regions.splice(0,regions.length,...JSON.parse(metadata.stdout));
}
assert(regions.every(r=>r.balloon));
const fixture=spawn(python,[path.join(root,"scripts/fixture_server.py")],{cwd:root,windowsHide:true,stdio:["ignore","pipe","pipe"]});
let browser;
const ramScreenshots=[];
const report={passed:false,browser:"isolated headless Edge; Browser plugin not available",realCrops,expressive,checks:{},screenshots:[],
  limitations:["Native calls/translation mocked; real local balloon geometry and packaged font only","Authored fixture, not representative manga/SFX quality","Not the user's installed profile or a phone browser"]};
if(nativeEvidence){
  report.nativeEvidence=path.resolve(nativePath);report.runtime=nativeEvidence.runtime;
  report.limitations[0]="Captured real native OCR/cloud output replayed; browser transport mocked. No new inference or E2E latency measurement.";
}
async function capture(page,label){
  ramScreenshots.push({label,mimeType:"image/jpeg",data:(await page.screenshot({type:"jpeg",quality:80})).toString("base64")});
  report.screenshots.push(label+" (RAM-only)");
}
if(realCrops)report.limitations.push("Recorded real detector crop geometry replayed; not a fresh OCR/LLM end-to-end run.");
function residualSourcePixels(imageBytes){
  return new Promise((resolve,reject)=>{
    const child=spawn(python,["-c",`import sys,json,base64,io;import numpy as np;from PIL import Image;p=json.load(sys.stdin);a=np.asarray(Image.open(io.BytesIO(base64.b64decode(p['image']))).convert('RGB'));s=a.shape[1]/800;counts=[]
for d in p['detections']:
 x,y=d['polygon'][0];r,b=d['polygon'][2];crop=a[int(y*s):int((b+1)*s),int(x*s):int((r+1)*s)];counts.append(int((crop.min(axis=2)<250).sum()))
print(json.dumps(counts))`],{cwd:root,windowsHide:true,stdio:["pipe","pipe","pipe"]});
    let result="";child.stdout.on("data",part=>result+=part);child.on("error",reject);
    child.on("exit",code=>code===0?resolve(JSON.parse(result)):reject(new Error("Raster residual check failed")));
    child.stdin.end(JSON.stringify({image:imageBytes.toString("base64"),detections}));
  });
}
try{
  const url=await new Promise((resolve,reject)=>{
    let pending="";const timer=setTimeout(()=>reject(new Error("Fixture startup timeout")),15000);
    fixture.on("error",reject);fixture.stdout.on("data",chunk=>{pending+=chunk;const end=pending.indexOf("\n");if(end>=0){clearTimeout(timer);resolve(JSON.parse(pending.slice(0,end)).url);}});
  });
  const edgeArg=process.argv.indexOf("--edge-executable");
  browser=await chromium.launch({...(edgeArg>=0?{executablePath:process.argv[edgeArg+1]}:{channel:"msedge"}),headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:900}}),errors=[],requests=[];
  page.on("pageerror",e=>errors.push(e.message));page.on("console",m=>{if(m.type()==="error")errors.push(m.text());});
  page.on("request",request=>requests.push(request.url()));
  await page.route("**/assets/PatrickHand-Regular.ttf",route=>route.fulfill({path:path.join(root,"dist/extension/assets/PatrickHand-Regular.ttf"),contentType:"font/ttf"}));
  await page.addInitScript(regions=>{
    window.__letteringRegions=regions;
    const attach=Element.prototype.attachShadow;
    Element.prototype.attachShadow=function(options){const shadow=attach.call(this,options);window.__readerShadow=shadow;return shadow;};
    window.chrome={runtime:{getURL(resource){return new URL(resource,location.origin+"/").href;},onMessage:{addListener(){}},async sendMessage({op,params}){
      if(op==="image")return {ok:true,result:{revision:params.revision,width:800,height:1050,regions:window.__letteringRegions,metrics:{total_ms:1}}};
      return {ok:true,result:{}};
    }}};
  },regions);
  await page.goto(url);await page.waitForFunction(()=>document.querySelector("#page").complete);
  report.url=page.url();report.title=await page.title();assert.match(report.title,/Chapter 1/);assert(await page.locator("h1").isVisible());
  report.checks.pageIdentity=true;report.checks.notBlank=true;
  const untouchedSource=await page.locator("#page").screenshot();
  await page.addScriptTag({path:path.join(root,"dist/extension/content.js")});
  await page.waitForFunction(()=>[...document.fonts].some(font=>font.family==="MangaLiveLettering"&&font.status==="loaded"));
  report.checks.packagedVietnameseFontLoaded=true;
  await page.evaluate(()=>window.__mangaLive.start({storyId:"lettering-qa",title:"Lettering QA",at:{chapter:1,page:0},genre:"fantasy",autoScan:true,prefetch:false}));
  await page.waitForFunction(()=>window.__readerShadow.querySelectorAll(".integrated").length===4);
  await page.waitForTimeout(150);
  const inspect=()=>page.evaluate(()=>[...window.__readerShadow.querySelectorAll(".region")].map(node=>{
    const css=getComputedStyle(node),b=node.getBoundingClientRect();
    return {id:node.dataset.regionId,ariaLabel:node.getAttribute("aria-label"),rect:{x:b.x,y:b.y,width:b.width,height:b.height},text:node.textContent,font:css.fontFamily,size:parseFloat(css.fontSize),height:b.height,width:b.width,
      lineHeight:parseFloat(css.lineHeight),border:css.borderWidth,shadow:css.boxShadow,outline:css.outlineStyle,
      background:css.backgroundColor,overflow:node.dataset.overflow,scrollHeight:node.scrollHeight,clientHeight:node.clientHeight};
  }));
  let measured=await inspect();
  assertRenderedTranslations(regions,measured);report.checks.nativeIdsAndWordingPreserved=true;
  assert.deepEqual(findLetteringBoxOverlaps(measured),[]);report.checks.noLetteringOverlap=true;
  assert(measured.every(n=>n.shadow==="none"&&n.border==="0px"&&n.outline==="none"));report.checks.noPermanentCardsOrReviewOutlines=true;
  assert(measured.every(n=>n.overflow==="false"&&n.scrollHeight<=n.clientHeight+1&&n.size>=11));report.checks.desktopReadableNoOverflow=true;
  report.desktop=measured;
  const firstBeforeScroll=measured[0].rect;
  const scrollDelta=await page.evaluate(()=>{const before=scrollY;scrollBy(0,160);return scrollY-before;});
  assert(scrollDelta>0);await page.waitForTimeout(100);
  assert(Math.abs((await inspect())[0].rect.y-firstBeforeScroll.y+scrollDelta)<2);
  report.checks.scrollAligned=true;
  await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(100);
  const normalImage=await page.locator("#page").boundingBox(),normalSurface=(await inspect())[0].rect;
  await page.evaluate(()=>document.querySelector("#page").style.width="620px");await page.waitForTimeout(100);
  const scaledImage=await page.locator("#page").boundingBox(),scaled=await inspect();
  assertRenderedTranslations(regions,scaled);assert(scaled.every(n=>n.overflow==="false"));
  assert(Math.abs((scaled[0].rect.x-scaledImage.x)/scaledImage.width-(normalSurface.x-normalImage.x)/normalImage.width)<.005);
  assert(Math.abs(scaled[0].rect.width/scaledImage.width-normalSurface.width/normalImage.width)<.005);
  report.checks.imageResizeAligned=true;
  await page.evaluate(()=>document.querySelector("#page").style.width="");await page.waitForTimeout(100);
  if(expressive){
    assert(measured.some(n=>n.text.includes("Tô-i… đââây!")));
    assert(measured.some(n=>n.text==="Tôi…   yêu…   em."));
    assert(measured.some(n=>n.text==="E M   Y Ê U   A N H"));
    assert(measured.some(n=>n.text==="DỪNG LẠI!"));
    assert(await page.evaluate(()=>[...window.__readerShadow.querySelectorAll(".region")].every(n=>getComputedStyle(n).whiteSpace==="pre")));
    report.checks.desktopExpressionPreserved=true;
  }
  // Screenshot the actual SVG rasterization without translated text. Checking
  // only the integer OpenCV mask misses antialiased Japanese still peeking out.
  await page.setViewportSize({width:1280,height:1600});await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(100);
  await page.evaluate(()=>{window.__readerShadow.querySelector(".bar").style.visibility="hidden";
    for(const node of window.__readerShadow.querySelectorAll(".region"))node.style.opacity="0";});
  const blank=await page.locator("#page").screenshot();
  const residual=await residualSourcePixels(blank);
  report.residualSourcePixels=residual;assert(residual.every(count=>count===0),"Old antialiased Japanese must not remain in the rendered balloon");
  report.checks.noResidualOriginalInk=true;
  await page.evaluate(()=>{window.__readerShadow.querySelector(".bar").style.visibility="";
    for(const node of window.__readerShadow.querySelectorAll(".region"))node.style.opacity="";});
  await page.setViewportSize({width:1280,height:900});
  // Screenshot typography as it actually appears inside the source balloons.
  await page.evaluate(()=>scrollTo(0,200));await page.waitForTimeout(100);
  await capture(page,"integrated-desktop");
  // Exact pixel restoration is stronger than checking visibility flags alone.
  await page.evaluate(()=>{window.__readerShadow.querySelector(".bar").style.visibility="hidden";window.__mangaLive.stop();});
  await page.waitForTimeout(100);const source=await page.locator("#page").screenshot();
  assert.equal(createHash("sha256").update(source).digest("hex"),createHash("sha256").update(untouchedSource).digest("hex"),"Stop must restore the untouched image, not merely match another concealed state");
  report.checks.stoppedMatchesUntouchedSource=true;
  await page.evaluate(()=>window.__mangaLive.start({storyId:"lettering-qa",title:"Lettering QA",at:{chapter:1,page:0},autoScan:true,prefetch:false}));
  await page.waitForFunction(()=>window.__readerShadow.querySelectorAll(".integrated").length===4);
  await page.evaluate(()=>{window.__readerShadow.querySelector(".bar").style.visibility="hidden";[...window.__readerShadow.querySelectorAll("button")].find(b=>b.textContent==="Xem gốc").click();});
  await page.waitForTimeout(100);const restored=await page.locator("#page").screenshot();
  assert.equal(createHash("sha256").update(restored).digest("hex"),createHash("sha256").update(source).digest("hex"));
  report.checks.originalPixelsRestoredExactly=true;
  await page.evaluate(()=>{window.__readerShadow.querySelector(".bar").style.visibility="";[...window.__readerShadow.querySelectorAll("button")].find(b=>b.textContent==="Xem gốc").click();});
  await page.setViewportSize({width:390,height:844});await page.evaluate(()=>scrollTo(0,180));await page.waitForTimeout(150);
  measured=await inspect();report.mobile=measured;
  assertRenderedTranslations(regions,measured);
  assert.deepEqual(findLetteringBoxOverlaps(measured),[]);
  assert(measured.every(n=>n.overflow==="false"&&n.scrollHeight<=n.clientHeight+1&&n.size>=11));report.checks.mobileReadableNoOverflow=true;
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));report.checks.mobileNoHorizontalOverflow=true;
  await page.evaluate(()=>{window.__readerShadow.querySelector(".bar").style.visibility="hidden";
    for(const node of window.__readerShadow.querySelectorAll(".region"))node.style.opacity="0";});
  report.mobileResidualSourcePixels=await residualSourcePixels(await page.locator("#page").screenshot());
  await page.evaluate(()=>{window.__readerShadow.querySelector(".bar").style.visibility="";
    for(const node of window.__readerShadow.querySelectorAll(".region"))node.style.opacity="";});
  assert(report.mobileResidualSourcePixels.every(count=>count===0),"Mobile scaling must not reveal original antialiased glyphs");
  report.checks.mobileNoResidualOriginalInk=true;
  await capture(page,"integrated-mobile");
  if(expressive){
    assert(measured.some(n=>n.text==="Tôi…   yêu…   em."));
    assert(measured.some(n=>n.text==="E M   Y Ê U   A N H"));
    assert(measured.some(n=>n.text==="DỪNG LẠI!"));
    await page.evaluate(()=>window.__readerShadow.querySelectorAll(".region")[2].click());
    await page.waitForFunction(()=>window.__readerShadow.querySelector(".detail .vi")?.textContent==="E M   Y Ê U   A N H");
    assert.equal(await page.evaluate(()=>getComputedStyle(window.__readerShadow.querySelector(".detail .vi")).whiteSpace),"pre-wrap");
    await page.evaluate(()=>[...window.__readerShadow.querySelectorAll(".detail button")].find(b=>b.textContent==="Đóng").click());
    await page.waitForFunction(()=>!window.__readerShadow.querySelector(".detail"));
    report.checks.mobileExpressionAndFullTextInteraction=true;
  }
  assert(requests.every(url=>url.startsWith(new URL(report.url).origin)));report.checks.noRemoteFontOrApiRequests=true;
  assert.equal(await page.locator("vite-error-overlay,nextjs-portal").count(),0);report.checks.noFrameworkOverlay=true;
  assert.deepEqual(errors,[]);report.checks.consoleHealth=true;report.passed=true;
}catch(error){report.error=error.message;process.exitCode=1;}
finally{
  if(browser)await browser.close();fixture.kill();
  await writeFile(path.join(output,"result.json"),JSON.stringify(report,null,2));console.log(JSON.stringify({...report,evidence:output},null,2));
  if(ramScreenshots.length)console.log("QA_RAM_IMAGES="+JSON.stringify(ramScreenshots));
}
