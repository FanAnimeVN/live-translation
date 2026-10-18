// Private source pixels + captured OCR/translation + real local cleanup.
// No native registration, model load, key or API. Every raster stays in RAM.
import {chromium} from "playwright";
import {spawn,execFile} from "node:child_process";
import {promisify} from "node:util";
import {readFile,writeFile} from "node:fs/promises";
import {createHash} from "node:crypto";
import path from "node:path";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";
import {assertRenderedTranslations} from "./rendered-translation-check.mjs";
import {findLetteringBoxOverlaps} from "./lettering-overlap-check.mjs";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const argument=(name,fallback)=>{const i=process.argv.indexOf(name);return i<0?fallback:process.argv[i+1];};
const folder=argument("--folder"),pageId=argument("--page"),evidence=argument("--native-result");
const originalCycles=Number(argument("--original-cycles","1"));
assert(Number.isInteger(originalCycles)&&originalCycles>=1&&originalCycles<=25,"Original cycles must be 1..25");
const rawCycles=Number(argument("--raw-cycles","1"));
assert(Number.isInteger(rawCycles)&&rawCycles>=1&&rawCycles<=25,"Raw cycles must be 1..25");
assert(folder&&pageId&&evidence,"Explicit folder, page and native result are required");
const python=path.join(root,".venv/Scripts/python.exe"),run=promisify(execFile);
const payload=JSON.parse((await run(python,[path.join(root,"scripts/private_render_payload.py"),
  "--folder",folder,"--page",pageId,"--native-result",evidence,
  ...(argument("--reference")?["--reference",argument("--reference")]:[]),
  ...(process.argv.includes("--current-scope")?["--current-scope"]:[])],{cwd:root,windowsHide:true,maxBuffer:4*1024*1024})).stdout);
const output=path.resolve(root,argument("--output",path.join(root,"artifacts/private-render-replay-"+pageId.toLowerCase()+".json")));
assert.equal(path.dirname(output),path.join(root,"artifacts"),"Replay diagnostics must stay in private artifacts");
const fixture=spawn(python,[path.join(root,"scripts/fixture_server.py"),"--folder",folder,"--private-page",pageId],
  {cwd:root,windowsHide:true,stdio:["ignore","pipe","pipe"]});
let browser,reader,ramPreview;
const report={passed:false,source:pageId,fingerprint:payload.fingerprint,cloud:false,inference:false,
  imagePersistence:false,browser:"isolated headless Edge; Browser plugin not available",checks:{},
  limitations:["Replay, not a new OCR/translation or Native Messaging run.","No independent translation or clean-background gold."]};
report.scopeVersion=payload.scope_version;report.scopeRecomputed=payload.scope_recomputed;
report.visualReviewIds=payload.visual_review_ids;
const hash=buffer=>createHash("sha256").update(buffer).digest("hex");
const comparePixels=(before,after)=>new Promise((resolve,reject)=>{
  const child=spawn(python,[path.join(root,"scripts/ram_pixel_compare.py")],{cwd:root,windowsHide:true,stdio:["pipe","pipe","pipe"]});
  let output="",error="";const timer=setTimeout(()=>{child.kill();reject(new Error("Pixel comparison timeout"));},15000);
  child.on("error",e=>{clearTimeout(timer);reject(e);});
  child.stdout.on("data",chunk=>{output+=chunk;if(output.length>16384){child.kill();reject(new Error("Unbounded pixel diagnostic"));}});
  child.stderr.on("data",chunk=>{error+=chunk;});
  child.on("exit",code=>{clearTimeout(timer);if(code)reject(new Error(error.slice(0,2048)));else try{resolve(JSON.parse(output));}catch(e){reject(e);}});
  child.stdin.end(JSON.stringify({before:before.toString("base64"),after:after.toString("base64")}));
});
try{
  const url=await new Promise((resolve,reject)=>{
    let buffer="";const timer=setTimeout(()=>reject(new Error("Fixture startup timeout")),15000);
    fixture.on("error",reject);fixture.stdout.on("data",chunk=>{buffer+=chunk;const end=buffer.indexOf("\n");if(end>=0){
      clearTimeout(timer);const state=JSON.parse(buffer.slice(0,end));
      assert.deepEqual(state.private_page_ids,[pageId]);resolve(new URL("/private-reader",state.url).href);
    }});
  });
  const executablePath=argument("--edge-executable");
  browser=await chromium.launch({...executablePath?{executablePath}:{channel:"msedge"},headless:true});
  reader=await browser.newPage({viewport:process.argv.includes("--mobile")?{width:390,height:844}:{width:1280,height:900}});
  const errors=[],requests=[];
  reader.on("pageerror",e=>errors.push(e.message));reader.on("console",m=>{if(m.type()==="error")errors.push(m.text());});
  reader.on("request",r=>requests.push(r.url()));
  await reader.route("**/assets/PatrickHand-Regular.ttf",route=>route.fulfill({path:path.join(root,"dist/extension/assets/PatrickHand-Regular.ttf"),contentType:"font/ttf"}));
  await reader.addInitScript(payload=>{
    window.__qaPayload=payload;
    const attach=Element.prototype.attachShadow;
    Element.prototype.attachShadow=function(options){const shadow=attach.call(this,options);window.__qaShadow=shadow;return shadow;};
    window.chrome={runtime:{getURL(resource){return new URL(resource,location.origin+"/").href;},onMessage:{addListener(fn){window.__qaReceiver=fn;}},async sendMessage({op,params}){
      if(op==="image"){
        const {native,patches}=window.__qaPayload;
        for(const patch of patches)window.__qaReceiver({type:"result",id:params.id,event:"render-patch",
          result:{revision:params.revision,width:native.width,height:native.height,patch}}, {},()=>{});
        return {ok:true,result:{...native,revision:params.revision}};
      }
      return {ok:true,result:{}};
    }}};
  },payload);
  await reader.goto(url);await reader.waitForFunction(()=>document.querySelector("#page").complete);
  if(process.argv.includes("--mobile"))await reader.evaluate(()=>document.body.style.paddingBottom="300px");
  report.url=reader.url();report.title=await reader.title();assert.equal(reader.url(),url);assert.match(report.title,/Private benchmark/);
  assert(await reader.locator("h1").isVisible());report.checks.identity=true;report.checks.notBlank=true;
  if(process.argv.includes("--native-pixel-geometry")){
    await reader.evaluate(()=>{
      const image=document.querySelector("#page");
      Object.assign(image.style,{width:image.naturalWidth+"px",height:image.naturalHeight+"px",maxWidth:"none",position:"relative"});
      const {x,y}=image.getBoundingClientRect();
      image.style.top=(Math.ceil(y)-y)+"px";image.style.left=(Math.ceil(x)-x)+"px";
    });
    report.exactPixelGeometry="QA only: native-size image and integer CSS origin; no interpolation/tolerance";
  }
  const sourceGeometry=()=>reader.evaluate(()=>({scroll:[scrollX,scrollY],
    image:document.querySelector("#page").getBoundingClientRect().toJSON(),viewport:[innerWidth,innerHeight,devicePixelRatio]}));
  report.initialGeometry=await sourceGeometry();
  const initial=await reader.locator("#page").screenshot();
  report.captureGeometry=await sourceGeometry();
  for(let cycle=2;cycle<=rawCycles;cycle++){
    if(process.argv.includes("--raw-scroll")){await reader.evaluate(()=>scrollBy(0,220));await reader.waitForTimeout(60);}
    if(process.argv.includes("--raw-return-scroll")){
      await reader.evaluate(([x,y])=>scrollTo(x,y),report.captureGeometry.scroll);await reader.waitForTimeout(80);
      assert.deepEqual(await sourceGeometry(),report.captureGeometry,"Raw control must return to identical capture geometry");
    }
    const untouched=await reader.locator("#page").screenshot();
    if(hash(untouched)!==hash(initial)){
      report.failedUntouchedCycle=cycle;report.untouchedPixelDiff=await comparePixels(initial,untouched);
      report.untouchedGeometry=await sourceGeometry();
      throw new Error("Untouched source screenshot varies before extension injection");
    }
  }
  report.rawCycles=rawCycles;report.checks.untouchedScreenshotStable=true;
  await reader.evaluate(([x,y])=>scrollTo(x,y),report.captureGeometry.scroll);
  await reader.addScriptTag({path:path.join(root,"dist/extension/content.js")});
  await reader.waitForFunction(()=>[...document.fonts].some(f=>f.family==="MangaLiveLettering"&&f.status==="loaded"));
  await reader.evaluate(()=>window.__mangaLive.start({storyId:"private-replay",title:"Private replay",at:{chapter:1,page:0},autoScan:true,prefetch:false}));
  // Deferred secondary text stays in the original image and is recoverable
  // from the reader affordance; it must not be counted as a painted
  // lettering surface in this renderer gate.
  const expectedPaintedRegions=payload.native.regions.filter(region=>region.vi&&region.scope?.action!=="defer").length;
  await reader.waitForFunction(count=>window.__qaShadow.querySelectorAll(".region").length===count,expectedPaintedRegions);
  await reader.waitForFunction(count=>window.__qaShadow.querySelectorAll("img.erase").length===count,payload.patches.length);
  if(process.argv.includes("--ram-preview")){
    await reader.waitForTimeout(100);
    ramPreview=(await reader.screenshot({type:"jpeg",quality:80})).toString("base64");
    report.ramPreviewStage="translated-first-viewport";
  }
  const snapshot=()=>reader.evaluate(()=>[...window.__qaShadow.querySelectorAll(".region")].map(n=>({
    id:n.dataset.regionId,text:n.textContent,ariaLabel:n.getAttribute("aria-label"),visibility:getComputedStyle(n).visibility,
    fallback:n.dataset.readingFallback==="true",sourcePosition:{x:parseFloat(n.style.left),y:parseFloat(n.style.top)},
    rect:{x:n.getBoundingClientRect().x,y:n.getBoundingClientRect().y,width:n.getBoundingClientRect().width,height:n.getBoundingClientRect().height}})));
  const before=await snapshot();assertRenderedTranslations(payload.native.regions,before);report.checks.idsAndWording=true;
  const unsafePaint=await reader.evaluate(ids=>[...window.__qaShadow.querySelectorAll(".region")]
    .filter(n=>ids.includes(n.dataset.regionId)&&n.classList.contains("integrated")).map(n=>n.dataset.regionId),payload.visual_review_ids);
  assert.deepEqual(unsafePaint,[],"Visually unsupported OCR cannot erase source pixels");
  assert(!payload.patches.some(p=>payload.visual_review_ids.includes(p.regionId)));
  report.checks.visualReviewPreservesSource=true;
  // Keep exact wording/ID coverage above, including every offscreen note. The
  // collision diagnostic concerns painted geometry; hidden rail rows have no
  // box. Rail is explicitly a fallback, never integrated-lettering acceptance.
  report.readingFallbackIds=before.filter(n=>n.fallback).map(n=>n.id);
  report.visualDiagnostics={letteringBoxOverlapCandidates:findLetteringBoxOverlaps(before.filter(n=>n.visibility==="visible"&&n.rect.width>0&&n.rect.height>0)),
    meaning:"Visible presentation boxes only. A reading rail is not integrated-lettering/clean-background acceptance."};
  if(process.argv.includes("--assert-reading-fallback")){
    assert(report.readingFallbackIds.length>=5,"Reproduced narrow columns must remain fully readable, not silently dropped");
    const notes=await reader.evaluate(()=>[...window.__qaShadow.querySelectorAll(".region.reading-text")].map(n=>({
      id:n.dataset.regionId,size:parseFloat(getComputedStyle(n).fontSize),whiteSpace:getComputedStyle(n).whiteSpace,
      eraseVisible:[...window.__qaShadow.querySelectorAll(".erase")].some(e=>e.dataset.regionId===n.dataset.regionId&&getComputedStyle(e).visibility!=="hidden")
    })));
    assert(notes.every(n=>n.size>=16&&n.whiteSpace==="pre-wrap"&&!n.eraseVisible));
    report.checks.readingFallbackPreservesArtAndFullText=true;
    const interaction=await reader.evaluate(()=>{
      const s=window.__qaShadow,rail=s.querySelector(".reading-rail"),summary=rail.querySelector("summary");
      summary.click();const collapsed=!rail.open;
      const marker=[...s.querySelectorAll(".source-marker")].find(n=>getComputedStyle(n).visibility==="visible");
      marker.click();
      const focused=s.activeElement,reopened=rail.open&&focused?.classList.contains("reading-text");
      const id=focused?.dataset.regionId;focused.click();
      const detail=s.querySelector(".detail"),exactDetail=detail?.querySelector(".vi")?.textContent===focused.textContent;
      [...detail.querySelectorAll("button")].find(n=>n.textContent==="Đóng").click();
      return {collapsed,reopened,exactDetail,id};
    });
    assert(interaction.collapsed&&interaction.reopened&&interaction.exactDetail);
    report.checks.readingRailCollapseMarkerAndSourceDetail=true;
    report.readingRailInteraction=interaction;
  }
  const scroll=await reader.evaluate(()=>{const y=scrollY;scrollBy(0,220);return scrollY-y;});assert(scroll>0);
  await reader.waitForTimeout(200);const after=await snapshot();
  assertRenderedTranslations(payload.native.regions,after);
  assert(Math.abs(after[0].sourcePosition.y-before[0].sourcePosition.y+scroll)<2);report.checks.scrollAligned=true;
  await reader.evaluate(()=>window.__qaShadow.querySelector(".bar").style.visibility="hidden");
  if(process.argv.includes("--hold-visibility-frame"))await reader.evaluate(()=>{
    const original=window.requestAnimationFrame;let next=1000000;const pending=new Map();
    window.requestAnimationFrame=callback=>{const id=next++;pending.set(id,callback);return id;};
    window.__qaReleaseVisibilityFrame=()=>{
      window.requestAnimationFrame=original;for(const callback of pending.values())original.call(window,callback);pending.clear();
    };
  });
  await reader.keyboard.press("Alt+T");await reader.waitForTimeout(100);
  report.originalVisibility=await reader.evaluate(()=>[...window.__qaShadow.querySelectorAll(".region,.erase")].map(n=>({
    id:n.dataset.regionId,className:n.className,visibility:getComputedStyle(n).visibility,display:getComputedStyle(n).display})));
  if(process.argv.includes("--hold-visibility-frame")){
    assert(report.originalVisibility.every(node=>node.visibility==="hidden"),"Original view must hide every translation/erasure before a deferred animation frame");
    report.checks.originalHiddenBeforeAnimationFrame=true;
    await reader.evaluate(()=>window.__qaReleaseVisibilityFrame());await reader.waitForTimeout(100);
  }
  // Compare at the identical viewport/source origin, not at a different
  // compositor tile after scrolling a fractionally scaled image. Keep the
  // held-RAF conceal assertion above and the exact (zero-tolerance) pixel gate.
  await reader.evaluate(([x,y])=>scrollTo(x,y),report.captureGeometry.scroll);await reader.waitForTimeout(80);
  const restoredGeometry=await sourceGeometry();
  assert.deepEqual(restoredGeometry,report.captureGeometry,"Pixel comparison must use identical source/viewport geometry");
  report.checks.identicalCaptureGeometry=true;
  const restored=await reader.locator("#page").screenshot();
  report.hashes={initial:hash(initial),restored:hash(restored)};
  if(hash(restored)!==hash(initial)){
    report.originalPixelDiff=await comparePixels(initial,restored);
    report.originalDom=await reader.evaluate(()=>({scroll:[scrollX,scrollY],image:document.querySelector("#page").getBoundingClientRect().toJSON(),
      activeElement:document.activeElement?.tagName,focused:window.__qaShadow.activeElement?.className,
      bar:{visibility:getComputedStyle(window.__qaShadow.querySelector(".bar")).visibility,
        rect:window.__qaShadow.querySelector(".bar").getBoundingClientRect().toJSON()}}));
  }
  if(hash(restored)===hash(initial)&&originalCycles>1){
    for(let cycle=2;cycle<=originalCycles;cycle++){
      await reader.keyboard.press("Alt+T");await reader.waitForTimeout(60);
      await reader.keyboard.press("Alt+T");await reader.waitForTimeout(60);
      const sample=await reader.locator("#page").screenshot();
      if(hash(sample)!==hash(initial)){
        report.failedOriginalCycle=cycle;report.originalPixelDiff=await comparePixels(initial,sample);
        report.cycleGeometry=await sourceGeometry();
        throw new Error("Original pixels differ during repeated toggle");
      }
    }
    report.checks.repeatedOriginalRestoration=true;report.originalCycles=originalCycles;
  }
  await reader.evaluate(()=>window.__mangaLive.stop());await reader.waitForTimeout(100);
  const stopped=await reader.locator("#page").screenshot();report.hashes.stopped=hash(stopped);
  report.pngSizes={initial:initial.length,restored:restored.length,stopped:stopped.length};
  report.checks.stoppedMatchesInitial=hash(stopped)===hash(initial);
  assert.equal(hash(restored),hash(initial),"Original view must restore exact source pixels");
  report.checks.originalRestoredExactly=true;
  assert.equal(await reader.locator("vite-error-overlay,nextjs-portal").count(),0);assert.deepEqual(errors,[]);
  assert(requests.every(r=>r.startsWith(new URL(url).origin)||r.startsWith("blob:")));
  report.checks.noFrameworkOverlay=true;report.checks.consoleHealth=true;report.checks.noExternalApi=true;
  if(process.argv.includes("--assert-no-lettering-overlap")){
    report.requestedLetteringGate="FAIL";
    assert.equal(report.visualDiagnostics.letteringBoxOverlapCandidates.length,0,"Translated lettering boxes overlap; functional replay is not visual acceptance");
    report.requestedLetteringGate="PASS";
  }
  report.passed=true;
}catch(error){report.error=error.message;process.exitCode=1;}
finally{
  if(reader&&process.argv.includes("--ram-preview")&&!ramPreview)try{
    ramPreview=(await reader.screenshot({type:"jpeg",quality:80})).toString("base64");report.ramPreviewStage="failure";
  }catch{}
  if(browser)await browser.close();fixture.kill();
  await writeFile(output,JSON.stringify(report,null,2));console.log(JSON.stringify({...report,evidence:output},null,2));
  if(ramPreview)console.log("QA_RAM_PREVIEW="+ramPreview);
}
