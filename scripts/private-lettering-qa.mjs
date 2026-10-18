// Private image -> production geometry/renderer -> reversible lettering.
// Native/OCR/translation are mocked; this is NOT an inference/meaning gate.
// All private raster buffers, screenshots and crops remain in RAM. No traces,
// video, screenshot files, image caches or external requests are permitted.
import {chromium} from "playwright";
import {execFile,spawn} from "node:child_process";
import {promisify} from "node:util";
import {readFile} from "node:fs/promises";
import {createServer} from "node:http";
import {createHash} from "node:crypto";
import path from "node:path";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const python=path.join(root,".venv/Scripts/python.exe"),run=promisify(execFile);
function argument(name){const idx=process.argv.indexOf(name);return idx<0?undefined:process.argv[idx+1];}
function boxArgument(name){const idx=process.argv.indexOf(name);assert(idx>=0,"Missing "+name);
  const box=process.argv.slice(idx+1,idx+5).map(Number);assert(box.length===4&&box.every(Number.isInteger));return box;}
function boxesArgument(name){return process.argv.flatMap((value,index)=>value===name?[process.argv.slice(index+1,index+5).map(Number)]:[]);}
const imagePath=argument("--image"),box=boxArgument("--box"),glyphBoxes=boxesArgument("--glyph-box"),protectedBoxes=boxesArgument("--protected-box");
assert(glyphBoxes.length>0,"At least one glyph probe required");
assert(imagePath&&argument("--ja")&&argument("--vi"),"Image and QA-supplied source/translation required");
const experimentalSourceSupport=process.argv.includes("--experimental-source-support");
const nativeDefault=process.argv.includes("--native-default");
assert(!(experimentalSourceSupport&&nativeDefault),"Choose native default or experiment");
const {stdout}=await run(python,["-B","-c",`import sys,json;sys.path[:0]=['companion','scripts'];from probe_balloon import selected_geometry;from manga_live.ocr import LAYOUT_VERSION,PRESENTATION_VERSION;im,regions=selected_geometry(sys.argv[1],json.loads(sys.argv[2]),sys.argv[3] or None,sys.argv[4] or None,experimental_source_support=sys.argv[5]=='yes',native_default=sys.argv[6]=='yes');print(json.dumps({'size':im.size,'regions':regions,'layout':LAYOUT_VERSION,'presentation':PRESENTATION_VERSION if 'yes' in sys.argv[5:7] else LAYOUT_VERSION}))`,imagePath,JSON.stringify(box),argument("--detector-replay")??"",argument("--page")??"",experimentalSourceSupport?"yes":"no",nativeDefault?"yes":"no"],{cwd:root,windowsHide:true});
const geometry=JSON.parse(stdout),region=geometry.regions[0];assert(geometry.regions.length===1&&region.balloon?.erasePolygons?.length,"Selected source crop must pass the production safe-balloon gate");
Object.assign(region,{ja:argument("--ja"),vi:argument("--vi"),ambiguous:true});
const [imageBytes,font]=await Promise.all([readFile(imagePath),readFile(path.join(root,"dist/extension/assets/PatrickHand-Regular.ttf"))]);
const [width,height]=geometry.size;
for(const roi of [...glyphBoxes,...protectedBoxes])assert(roi.length===4&&roi.every(Number.isInteger)&&roi[0]>=0&&roi[1]>=0&&roi[2]>0&&roi[3]>0&&roi[0]+roi[2]<=width&&roi[1]+roi[3]<=height);
const html=Buffer.from(`<!doctype html><meta charset="utf-8"><title>Private lettering QA</title><style>body{margin:24px;background:#555}#page{display:block;width:${width}px;max-width:100%;height:auto}</style><img id="page" src="/source">`);
const server=createServer((req,res)=>{
  res.setHeader("Cache-Control","no-store");
  if(req.url==="/qa"){res.setHeader("Content-Type","text/html;charset=utf-8");res.end(html);}
  else if(req.url==="/source"){res.setHeader("Content-Type","image/jpeg");res.end(imageBytes);}
  else if(req.url==="/assets/PatrickHand-Regular.ttf"){res.setHeader("Content-Type","font/ttf");res.end(font);}
  else{res.writeHead(404);res.end();}
});
await new Promise(resolve=>server.listen(0,"127.0.0.1",resolve));
const url="http://127.0.0.1:"+server.address().port+"/qa";
let browser;const errors=[],requests=[];
const report={passed:false,browser:"isolated headless Edge; Browser plugin not available",layout:geometry.layout,presentation:geometry.presentation,experimentalSourceSupport,productionDefault:nativeDefault,checks:{},url,
  limitations:["One manually selected real balloon only; no private-page coverage or inference-quality certification.",
    "Production geometry/font/renderer, mocked transport and QA-supplied translation.",
    "Glyph ROI is a narrow visual probe, not a complete text/clean-background gold mask.",
    "No user's installed Edge profile, API request or credit; private screenshots kept in RAM."]};
const screenshots=[];
function pixels(original,blank){return new Promise((resolve,reject)=>{
  const child=spawn(python,["-B","-c",`import sys,json,base64,io;import cv2,numpy as np;from PIL import Image;p=json.load(sys.stdin);a=np.asarray(Image.open(io.BytesIO(base64.b64decode(p['original']))).convert('RGB'));b=np.asarray(Image.open(io.BytesIO(base64.b64decode(p['blank']))).convert('RGB'));w,h=p['size'];mask=np.zeros((h,w),dtype='uint8')
for poly in p['polygons']:cv2.fillPoly(mask,[np.asarray(poly,dtype='int32')],1)
mask=cv2.resize(mask,(a.shape[1],a.shape[0]),interpolation=cv2.INTER_NEAREST);mask=cv2.dilate(mask,np.ones((5,5),np.uint8));sx,sy=a.shape[1]/w,a.shape[0]/h
def roi(box):
 x,y,cw,ch=box;return (slice(round(y*sy),round((y+ch)*sy)),slice(round(x*sx),round((x+cw)*sx)))
probes=[{'box':box,'source_dark_glyph_pixels':int((a[roi(box)].min(axis=2)<200).sum()),'remaining_dark_glyph_pixels':int((b[roi(box)].min(axis=2)<200).sum())} for box in p['glyphs']]
print(json.dumps({'source_dark_glyph_pixels':sum(r['source_dark_glyph_pixels'] for r in probes),'remaining_dark_glyph_pixels':sum(r['remaining_dark_glyph_pixels'] for r in probes),'glyph_probes':probes,'protected_probes':[{'box':box,'changed_pixels':int((a[roi(box)]!=b[roi(box)]).any(axis=2).sum())} for box in p['protected']],'changes_outside_erasure_halo':int(((a!=b).any(axis=2)&(mask==0)).sum())}))`],{cwd:root,windowsHide:true,stdio:["pipe","pipe","pipe"]});
  let output="";child.stdout.on("data",part=>output+=part);child.on("error",reject);
  child.on("exit",code=>code===0?resolve(JSON.parse(output)):reject(new Error("Private RAM-only pixel probe failed")));
  child.stdin.end(JSON.stringify({original:original.toString("base64"),blank:blank.toString("base64"),size:geometry.size,glyphs:glyphBoxes,protected:protectedBoxes,polygons:region.balloon.erasePolygons}));
});}
function hash(bytes){return createHash("sha256").update(bytes).digest("hex");}
try{
  const executablePath=argument("--edge-executable");
  browser=await chromium.launch({...executablePath?{executablePath}:{channel:"msedge"},headless:true});
  const page=await browser.newPage({viewport:{width:1280,height:1480}});
  await page.route("**/*",route=>new URL(route.request().url()).origin===new URL(url).origin?route.continue():route.abort());
  page.on("pageerror",e=>errors.push(e.message));page.on("console",m=>{if(m.type()==="error")errors.push(m.text());});page.on("request",r=>requests.push(r.url()));
  await page.addInitScript(({region,width,height})=>{
    const attach=Element.prototype.attachShadow;
    Element.prototype.attachShadow=function(options){const shadow=attach.call(this,options);window.__readerShadow=shadow;return shadow;};
    window.chrome={runtime:{getURL(resource){return new URL(resource,location.origin+"/").href;},onMessage:{addListener(){}},async sendMessage({op,params}){
      if(op==="image")return {ok:true,result:{revision:params.revision,width,height,regions:[region],metrics:{total_ms:1}}};
      return {ok:true,result:{}};
    }}};
  },{region,width,height});
  await page.goto(url);assert.equal(page.url(),url);assert.equal(await page.title(),"Private lettering QA");
  await page.waitForFunction(()=>document.querySelector("#page").complete&&document.querySelector("#page").naturalWidth>0);
  report.checks.pageIdentity=true;report.checks.notBlank=await page.locator("#page").isVisible();
  const original=await page.locator("#page").screenshot();
  await page.addScriptTag({path:path.join(root,"dist/extension/content.js")});
  await page.waitForFunction(()=>[...document.fonts].some(f=>f.family==="MangaLiveLettering"&&f.status==="loaded"));
  await page.evaluate(()=>window.__mangaLive.start({storyId:"private-lettering-qa",title:"Private QA",at:{chapter:1,page:0},autoScan:true,prefetch:false}));
  await page.waitForFunction(()=>window.__readerShadow.querySelectorAll(".integrated").length===1);
  await page.evaluate(()=>window.__readerShadow.querySelector(".bar").style.visibility="hidden");
  const inspect=()=>page.evaluate(()=>{const node=window.__readerShadow.querySelector(".region"),css=getComputedStyle(node),b=node.getBoundingClientRect();return {text:node.textContent,background:css.backgroundColor,border:css.borderWidth,shadow:css.boxShadow,font:css.fontFamily,size:parseFloat(css.fontSize),overflow:node.dataset.overflow,bounds:{x:b.x,y:b.y,width:b.width,height:b.height}};});
  report.desktop=await inspect();assert.equal(report.desktop.background,"rgba(0, 0, 0, 0)");assert.equal(report.desktop.border,"0px");assert.equal(report.desktop.shadow,"none");assert.equal(report.desktop.overflow,"false");report.checks.transparentIntegratedText=true;
  await page.evaluate(()=>window.__readerShadow.querySelector(".region").style.opacity="0");
  report.pixelProbe=await pixels(original,await page.locator("#page").screenshot());
  assert(report.pixelProbe.source_dark_glyph_pixels>10,"Glyph probe must contain source ink");assert.equal(report.pixelProbe.remaining_dark_glyph_pixels,0);assert.equal(report.pixelProbe.changes_outside_erasure_halo,0);report.checks.glyphProbeCleanAndOutsideMaskUnchanged=true;
  for(const probe of report.pixelProbe.glyph_probes)assert(probe.source_dark_glyph_pixels>0,"Every glyph ROI must contain real source ink");
  for(const probe of report.pixelProbe.protected_probes)assert.equal(probe.changed_pixels,0,"Protected artwork must remain exactly original");
  await page.evaluate(()=>window.__readerShadow.querySelector(".region").style.opacity="");
  const capture=async(label)=>{const rect=await page.locator("#page").boundingBox(),[x,y,w,h]=box;const sx=rect.width/width,sy=rect.height/height;
    const crop={x:Math.max(rect.x,rect.x+(x-20)*sx),y:Math.max(rect.y,rect.y+(y-20)*sy),width:(w+40)*sx,height:(h+40)*sy};
    crop.width=Math.min(crop.width,rect.x+rect.width-crop.x);crop.height=Math.min(crop.height,rect.y+rect.height-crop.y);
    screenshots.push({label,mimeType:"image/png",data:(await page.screenshot({clip:crop})).toString("base64")});};
  await capture("private-desktop-selected-balloon");
  // The full-source pixel probe needs a tall viewport; it cannot scroll. Use
  // a real reading viewport for this check and assert that it REALLY moves.
  await page.setViewportSize({width:1280,height:900});await page.evaluate(()=>scrollTo(0,0));await page.waitForTimeout(80);
  const before=(await inspect()).bounds;
  const moved=await page.evaluate(()=>{const before=scrollY;scrollBy(0,120);return scrollY-before;});
  assert(moved>0,"Scroll probe must actually scroll");await page.waitForTimeout(80);const after=(await inspect()).bounds;
  assert(Math.abs(before.y-after.y-moved)<2);report.checks.scrollAligned=true;await page.evaluate(()=>scrollTo(0,0));
  await page.setViewportSize({width:1280,height:1480});await page.waitForTimeout(80);
  await page.evaluate(()=>[...window.__readerShadow.querySelectorAll("button")].find(b=>b.textContent==="Xem gốc").click());await page.waitForTimeout(80);
  assert.equal(hash(await page.locator("#page").screenshot()),hash(original));report.checks.originalPixelsRestoredExactly=true;
  await page.evaluate(()=>[...window.__readerShadow.querySelectorAll("button")].find(b=>b.textContent==="Xem gốc").click());
  await page.setViewportSize({width:390,height:844});await page.waitForTimeout(100);report.mobile=await inspect();
  assert.equal(report.mobile.overflow,"false");assert(report.mobile.size>=11);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));report.checks.mobileReadableAndAligned=true;
  await capture("private-mobile-selected-balloon");
  report.checks.noFrameworkOverlay=await page.locator("vite-error-overlay,nextjs-portal").count()===0;
  assert.deepEqual(errors,[]);report.checks.consoleHealth=true;
  assert(requests.every(u=>new URL(u).origin===new URL(url).origin));report.checks.noExternalRequests=true;
  await page.evaluate(()=>window.__mangaLive.stop());report.passed=true;
}catch(error){report.error=error.message;process.exitCode=1;}
finally{if(browser)await browser.close();await new Promise(resolve=>server.close(resolve));}
// Caller can display these RAM-only PNGs; never persist stdout/screenshots.
console.log(JSON.stringify({report,screenshots}));
