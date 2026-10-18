// Real extension -> Native Messaging -> OCR/translation -> rendered overlay.
// Disposable localhost-only permission and native host; never a personal profile.
import {chromium} from "playwright";
import {spawn,execFile} from "node:child_process";
import {promisify} from "node:util";
import {createHash,randomUUID} from "node:crypto";
import {cp,copyFile,mkdir,mkdtemp,readFile,writeFile,symlink} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";
import {assertRenderedTranslations,hasClassToken} from "./rendered-translation-check.mjs";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const temporary=await mkdtemp(path.join(os.tmpdir(),"mangalive-real-browser-"));
const extension=path.join(temporary,"extension"),output=path.join(temporary,"evidence");
const python=path.join(root,".venv/Scripts/python.exe"),run=promisify(execFile);
const host="vn.mangalive.qa."+randomUUID().replaceAll("-","");
const hostManifest=path.join(temporary,host+".json");
const portable=process.argv.includes("--portable"),connectOnly=process.argv.includes("--connect-only");
const directSource=process.argv.includes("--direct-source");
const cloudTest=process.argv.includes("--cloud-test");
const cloudImageOcr=process.argv.includes("--image-ocr");
const renderReplay=process.argv.includes("--render-replay");
const replayResultIndex=process.argv.indexOf("--replay-native-result");
const replayNativeResult=replayResultIndex>=0?process.argv[replayResultIndex+1]:undefined;
const cloudModelIndex=process.argv.indexOf("--cloud-model"),cloudBudgetIndex=process.argv.indexOf("--cloud-budget");
const cloudModel=cloudModelIndex>=0?process.argv[cloudModelIndex+1]:"google/gemini-3.5-flash-lite";
const cloudBudget=cloudBudgetIndex>=0?Number(process.argv[cloudBudgetIndex+1]):.03;
const privateFolderIndex=process.argv.indexOf("--private-folder"),privatePageIndex=process.argv.indexOf("--private-page");
const privateFolder=privateFolderIndex>=0?process.argv[privateFolderIndex+1]:undefined;
const privatePage=privatePageIndex>=0?process.argv[privatePageIndex+1]:undefined;
assert(privateFolderIndex<0||(privateFolder&&!privateFolder.startsWith("--")),"Private folder value is required; no fixture fallback");
assert(privatePageIndex<0||(privatePage&&!privatePage.startsWith("--")),"Private page value is required; no sample substitution");
const privateTest=privateFolder!==undefined;
assert(!privateTest||(directSource&&(cloudTest||renderReplay)&&privateFolder&&privatePage),
  "Private inference QA requires an explicit folder/page and the bounded source cloud entry");
assert(!renderReplay||(directSource&&privateTest&&replayNativeResult&&!cloudTest&&!connectOnly),
  "Private renderer replay requires explicit source evidence, not a cloud/model run");
assert(!privatePage||privateTest,"Private page needs an explicit private folder");
assert(!cloudTest||directSource,"Paid QA must use a disposable development source entry");
assert(!cloudTest||(Number.isFinite(cloudBudget)&&cloudBudget>0&&cloudBudget<=.10),"Cloud QA budget must be <=0.10 USD");
assert(!cloudImageOcr||(cloudTest&&directSource&&!privateTest&&!connectOnly&&cloudBudget<=.04),
  "Image OCR browser QA requires explicit cloud mode, authored source and <=0.04 USD");
const sourceRelay=process.argv.includes("--source-relay");
assert(!renderReplay||!sourceRelay,"Renderer replay must use its isolated entry");
assert(!sourceRelay||directSource,"Source relay requires direct source bootstrap");
assert(!cloudTest||!sourceRelay,"Cloud QA must use its own bounded source entry");
const launcherIndex=process.argv.indexOf("--launcher");
const launcher=launcherIndex>=0?path.resolve(process.argv[launcherIndex+1]):undefined;
const nativeTrace=process.argv.includes("--native-trace");
const primeLibraries=process.argv.includes("--prime-libraries");
const detachStdio=process.argv.includes("--detach-stdio");
const detachWin32=process.argv.includes("--detach-win32");
const cwdRoot=process.argv.includes("--cwd-root");
const moduleLines=process.argv.includes("--module-lines");
const primeBaseModel=process.argv.includes("--prime-base-model");
const libraryIndex=process.argv.indexOf("--library-probe");
const libraryProbe=libraryIndex>=0?process.argv[libraryIndex+1]:undefined;
assert(!libraryProbe||["torch","paddle","paddleocr","pydantic"].includes(libraryProbe),"Invalid diagnostic library");
const waitIndex=process.argv.indexOf("--wait-ms");
const readerDeadline=waitIndex>=0?Number(process.argv[waitIndex+1]):240000;
assert(Number.isInteger(readerDeadline)&&readerDeadline>=30000&&readerDeadline<=240000,"QA reader deadline must be bounded");
assert(!(portable&&nativeTrace),"Diagnostic entry is source-only");
assert(!primeLibraries||nativeTrace,"Library priming is a diagnostic-entry experiment only");
assert(!detachStdio||(directSource&&nativeTrace),"Private stdio is a source diagnostic-entry experiment only");
assert(!detachWin32||detachStdio,"Win32 handles require the private stdio experiment");
assert(!(cwdRoot||libraryProbe)||(directSource&&nativeTrace),"Cwd/library probes require the isolated diagnostic source entry");
assert(!moduleLines||(directSource&&nativeTrace),"Module line traces require the isolated diagnostic source entry");
assert(!primeBaseModel||(directSource&&nativeTrace&&libraryProbe),"BaseModel priming requires a diagnostic import probe");
assert(!(directSource&&(portable||launcher)),"Direct-source isolates the development launcher; do not mix modes");
const assets=portable?path.join(root,"dist/portable/MangaLiveHost"):root;
let context,worker,fixture,registered=false,cdp,readerPage;
const ramScreenshots=[];
const report={passed:false,source:connectOnly?"no image; isolated Native Messaging status only":privateTest?"user-authorized private page; all raster buffers RAM-only":"author-created in-RAM image only",cloud:cloudTest,portable,connectOnly,
  privateTest,privatePage,
  renderReplay,
  cloudImageOcr,
  directSource,sourceRelay,primeLibraries,detachStdio,detachWin32,cwdRoot,moduleLines,primeBaseModel,libraryProbe,readerDeadline,
  browser:"Playwright isolated headless Edge; Browser plugin not available",checks:{},
  limitations:["QA-only localhost permission: not proof of production activeTab/browser-action grant UX.",
    "One page is not manga-quality certification or a reliable latency percentile.",
    "Not the user's installed Edge profile or a clean-Windows installation."],screenshots:[]};
if(privateTest){
  report.qualityGate="NOT_CERTIFIED: source annotation audit and independent JA-VI grading remain required";
  report.limitations.push("Private screenshots are returned in RAM, never written to disk; only text/metrics enter local QA evidence.",
    "Technical completion is not a perfect OCR, translation, role-filtering or clean-background verdict.");
}
if(renderReplay)report.limitations.push("Captured OCR/translation replay; actual MV3/native/rendering and local cleanup only. No new inference, translation cache or performance certification.");

async function registration(action){
  await run(python,[path.join(root,"scripts/browser_native_registration.py"),action,host,hostManifest],{windowsHide:true});
}
async function shadowSnapshot(){
  const {root:document}=await cdp.send("DOM.getDocument",{depth:-1,pierce:true});
  const nodes=[];
  function visit(node){
    const attributes={};for(let i=0;i<(node.attributes?.length??0);i+=2)attributes[node.attributes[i]]=node.attributes[i+1];
    if(attributes.class?.split(" ").some(c=>["region","status","bar","erase"].includes(c)))nodes.push({...node,attributes});
    for(const child of [...(node.children??[]),...(node.shadowRoots??[])])visit(child);
  }
  visit(document);
  const text=node=>node.nodeValue+(node.children??[]).map(text).join("");
  return {bar:nodes.find(n=>hasClassToken(n.attributes.class,"bar")),regions:nodes.filter(n=>n.attributes.class.split(" ").includes("region")),
    translations:nodes.filter(n=>n.attributes.class.split(" ").includes("region")).map(text),
    renderedItems:nodes.filter(n=>n.attributes.class.split(" ").includes("region")).map(n=>({
      id:n.attributes["data-region-id"],text:text(n),ariaLabel:n.attributes["aria-label"]})),
    status:text(nodes.find(n=>n.attributes.class==="status")??{nodeValue:""})};
}
async function surfaceVisibility(){
  const {regions}=await shadowSnapshot();
  const values=[];
  for(const node of regions){
    const {object}=await cdp.send("DOM.resolveNode",{nodeId:node.nodeId});
    const {result}=await cdp.send("Runtime.callFunctionOn",{objectId:object.objectId,returnByValue:true,
      functionDeclaration:"function(){const css=getComputedStyle(this);return {id:this.dataset.regionId,visibility:css.visibility,display:css.display};}"});
    values.push(result.value);await cdp.send("Runtime.releaseObject",{objectId:object.objectId});
  }
  return values;
}
async function awaitOverlay(finalCount,label){
  const until=Date.now()+readerDeadline;
  let previous="";
  while(Date.now()<until){
    const snapshot=await shadowSnapshot();
    if(snapshot.status!==previous){console.log(JSON.stringify({stage:label,status:snapshot.status}));previous=snapshot.status;}
    // A translated event can arrive before the pipeline has persisted its
    // final result. Wait for the reader's completion state, not just four
    // painted nodes, before awarding completion or starting another run.
    const finished=await worker.evaluate(count=>globalThis.__qaNativeResults.length>=count,finalCount);
    if(finished){
      const expected=await worker.evaluate(()=>globalThis.__qaNativeResults.at(-1).result.regions.filter(r=>r.vi&&r.scope?.action!=="defer").length);
      if(snapshot.regions.length===expected&&expected>0&&snapshot.translations.every(text=>text.trim()))return snapshot;
    }
    if(/Thử lại|lỗi|Không |chưa giữ/i.test(snapshot.status))throw new Error("Reader error: "+snapshot.status);
    await new Promise(resolve=>setTimeout(resolve,250));
  }
  throw new Error("No completed overlay within the reader pipeline timeout");
}
async function bounds(node){
  const {model}=await cdp.send("DOM.getBoxModel",{nodeId:node.nodeId});
  return {x:model.border[0],y:model.border[1],width:model.width,height:model.height};
}
async function capture(reader,label){
  ramScreenshots.push({label,mimeType:"image/jpeg",data:(await reader.screenshot({type:"jpeg",quality:80})).toString("base64")});
  report.screenshots.push(label+" (RAM-only)");
}

try{
  await mkdir(output,{recursive:true});await cp(path.join(root,"dist/extension"),extension,{recursive:true});
  const backgroundPath=path.join(extension,"background.js"),background=await readFile(backgroundPath,"utf8");
  assert.equal(background.split('"vn.mangalive.companion"').length,2,"QA host replacement must be unique");
  await writeFile(backgroundPath,background.replace('"vn.mangalive.companion"',JSON.stringify(host)));
  const manifestPath=path.join(extension,"manifest.json"),manifest=JSON.parse(await readFile(manifestPath,"utf8"));
  manifest.host_permissions=["http://127.0.0.1/*"];await writeFile(manifestPath,JSON.stringify(manifest));
  if(!directSource)await copyFile(launcher??path.join(root,portable?"dist/portable/MangaLiveHost/MangaLiveHost.exe":"dist/windows/MangaLiveHost.exe"),path.join(temporary,"MangaLiveHost.exe"));
  if(portable)await symlink(path.join(assets,"_internal"),path.join(temporary,"_internal"),"junction");
  context=await chromium.launchPersistentContext(path.join(temporary,"browser"),{channel:"msedge",headless:true,
    ignoreDefaultArgs:["--disable-extensions"],args:["--disable-extensions-except="+extension,"--load-extension="+extension]});
  [worker]=context.serviceWorkers();if(!worker)worker=await context.waitForEvent("serviceworker",{timeout:15000});
  // Observe real native replies before the first connection. No generated
  // result is mocked/replaced; only this disposable extension has the hook.
  await worker.evaluate(()=>{
    globalThis.__qaNativeResults=[];
    const original=chrome.runtime.connectNative;
    chrome.runtime.connectNative=function(...args){
      const port=original.apply(chrome.runtime,args);
      port.onMessage.addListener(message=>{
        if(message?.ok&&message.result?.metrics&&Array.isArray(message.result.regions))
          globalThis.__qaNativeResults.push({id:message.id,result:message.result});
      });
      return port;
    };
  });
  const id=new URL(worker.url()).hostname,origin="chrome-extension://"+id+"/";report.extensionId=id;
  const configuration={models:path.join(assets,"models"),runtime:path.join(assets,"runtime/llama"),
    dataRoot:path.join(temporary,"data"),allowedOrigins:[origin]};
  if(!portable)Object.assign(configuration,{python,entry:path.join(root,renderReplay?"scripts/qa_render_replay_entry.py":cloudImageOcr?"scripts/qa_image_entry.py":cloudTest?"scripts/qa_cloud_entry.py":sourceRelay?"scripts/qa_relay_entry.py":nativeTrace?"scripts/qa_native_entry.py":"companion/entry.py")});
  if(renderReplay)configuration.qaRenderReplay={enabled:true,folder:privateFolder,page:privatePage,nativeResult:path.resolve(replayNativeResult)};
  if(cloudTest){
    // Catalogue/read-only preflight before credential use. The native entry
    // independently enforces the ceiling before every paid attempt.
    const {stdout}=await run(python,[path.join(root,"scripts/benchmark_cloud.py"),"--plan-only","--models",cloudModel,
      "--cases","siblings","--budget",String(cloudBudget)],{windowsHide:true,maxBuffer:1024*1024});
    const preflight=JSON.parse(stdout.trim());
    configuration.qaCloud={consent:true,model:cloudModel,budgetUsd:cloudBudget,
      prices:preflight.provider_price_ceilings[cloudModel],imageConsent:cloudImageOcr};
    report.cloudModel=cloudModel;report.cloudBudgetUsd=cloudBudget;
  }
  if(nativeTrace&&cloudTest)configuration.qaStackTrace=true;
  if(primeLibraries)configuration.qaPrimeLibraries=true;
  if(detachStdio)configuration.qaDetachStdio=true;
  if(detachWin32)configuration.qaDetachWin32=true;
  if(cwdRoot)configuration.qaCwdRoot=true;
  if(moduleLines)configuration.qaModuleLines=true;
  if(primeBaseModel)configuration.qaPrimeBaseModel=true;
  if(libraryProbe)configuration.qaLibraryProbe=libraryProbe;
  await writeFile(path.join(temporary,"native-config.json"),JSON.stringify(configuration));
  // QA-only counterfactual: same entry, interpreter, config and browser pipe,
  // without inheriting a frozen bootloader's DLL/process environment.
  if(directSource)await writeFile(path.join(temporary,"MangaLiveHost.cmd"),
    `@echo off\r\n"${python}" "${configuration.entry}" %* --config "${path.join(temporary,"native-config.json")}" 2>NUL\r\n`);
  await writeFile(hostManifest,JSON.stringify({name:host,description:"Isolated author-fixture QA",type:"stdio",
    path:path.join(temporary,directSource?"MangaLiveHost.cmd":"MangaLiveHost.exe"),allowed_origins:[origin]}));
  await registration("register");registered=true;
  const options=await context.newPage(),errors=[];
  options.on("pageerror",error=>errors.push(error.message));
  options.on("console",message=>{if(message.type()==="error")errors.push(message.text());});
  await options.goto(origin+"options.html");
  await options.getByRole("heading",{name:"Thư viện của bạn"}).waitFor();
  report.optionsUrl=options.url();report.optionsTitle=await options.title();
  assert.equal(report.optionsUrl,origin+"options.html");assert.equal(report.optionsTitle,"Live translation");
  assert(await options.getByRole("heading",{name:"Thư viện của bạn"}).isVisible());
  assert.equal(await options.locator("vite-error-overlay,nextjs-portal").count(),0);
  report.checks.optionsIdentity=true;report.checks.optionsNotBlank=true;report.checks.optionsNoFrameworkOverlay=true;
  const call=(op,params={})=>{
    console.log(JSON.stringify({stage:"native-call",op}));
    let timer;
    const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>reject(new Error("QA setup call timed out: "+op)),35000);});
    return Promise.race([options.evaluate(async({op,params})=>{
      const reply=await chrome.runtime.sendMessage({op,params});if(!reply.ok)throw new Error(reply.error);return reply.result;
    },{op,params}),deadline]).finally(()=>clearTimeout(timer));
  };
  const status=await call("status");assert.equal(status.engineWarm,false);report.runtime={runtimeBuild:status.runtimeBuild,promptVersion:status.promptVersion,ocrVersion:status.ocrVersion,layoutVersion:status.layoutVersion,scopeVersion:status.scopeVersion,speakerBindingVersion:status.speakerBindingVersion,scheduleVersion:status.scheduleVersion};
  const expectedRuntime=(await run(python,["-B","-c","import sys;sys.path.insert(0,'companion');from manga_live.runtime_build import source_build;print(source_build())"],{cwd:root,windowsHide:true})).stdout.trim();
  assert.equal(status.runtimeBuild,expectedRuntime,"QA host must identify the current package before inference");
  report.checks.runtimePackageMatches=true;
  report.extensionBuild=await worker.evaluate(()=>chrome.runtime.getManifest().version_name);
  const promptSource=await readFile(path.join(root,"companion/manga_live/prompts.py"),"utf8");
  const version=promptSource.match(/^PROMPT_VERSION\s*=\s*"([^"]+)"/m)?.[1];assert(version);
  assert.equal(status.promptVersion,version,"QA runtime must match current source prompt version");
  const ocrSource=await readFile(path.join(root,"companion/manga_live/ocr.py"),"utf8");
  const layoutVersion=ocrSource.match(/^LAYOUT_VERSION\s*=\s*"([^"]+)"/m)?.[1];assert(layoutVersion);
  assert.equal(status.layoutVersion,layoutVersion,"QA runtime must match current source layout version");
  const ocrVersion=cloudImageOcr?(await run(python,["-B","-c","import sys;sys.path.insert(0,'companion');from manga_live.cloud_ocr import CloudCropOcr;print(CloudCropOcr.name)"],{cwd:root,windowsHide:true})).stdout.trim()
    :ocrSource.match(/^class MangaEngine:\r?\n\s+name\s*=\s*"([^"]+)"/m)?.[1];assert(ocrVersion);
  assert.equal(status.ocrVersion,ocrVersion,"QA runtime must match current source OCR version");
  const scopeSource=await readFile(path.join(root,"companion/manga_live/text_scope.py"),"utf8");
  const scopeVersion=scopeSource.match(/^SCOPE_VERSION\s*=\s*"([^"]+)"/m)?.[1];assert(scopeVersion);
  assert.equal(status.scopeVersion,scopeVersion,"QA runtime must match current source text-scope version");
  const memorySource=await readFile(path.join(root,"companion/manga_live/memory.py"),"utf8");
  const bindingVersion=memorySource.match(/^SPEAKER_BINDING_VERSION\s*=\s*"([^"]+)"/m)?.[1];assert(bindingVersion);
  assert.equal(status.speakerBindingVersion,bindingVersion,"QA runtime must match current source speaker-binding version");
  const scheduleSource=await readFile(path.join(root,"companion/manga_live/translation_schedule.py"),"utf8");
  const scheduleVersion=scheduleSource.match(/^SCHEDULE_VERSION\s*=\s*"([^"]+)"/m)?.[1];assert(scheduleVersion);
  assert.equal(status.scheduleVersion,scheduleVersion,"QA runtime must match current source translation scheduling");
  report.checks.realNativeHandshake=true;report.checks.allSourceVersionsMatch=true;
  if(connectOnly&&!libraryProbe){
    // Navigation only: no settings write, model load, API-key use or cloud API
    // call. Verify the real options page can consume the native status before
    // treating a version-only handshake as a rendered smoke-test pass.
    await options.setViewportSize({width:1280,height:900});
    await options.getByRole("button",{name:"Cài đặt",exact:true}).click();
    await options.getByRole("heading",{name:"Cấu hình engine"}).waitFor();
    assert(await options.getByLabel("Chế độ dịch",{exact:true}).isVisible());
    report.checks.settingsNavigation=true;await capture(options,"native-settings-desktop");
    await options.locator(".runtime-details > summary").click();
    await options.getByText(version,{exact:true}).waitFor();
    const uiBuild=await worker.evaluate(()=>chrome.runtime.getManifest().version_name);
    assert.match(uiBuild,/^0\.1\.0-dev\.[a-f0-9]{12}$/);
    await options.locator("footer").scrollIntoViewIfNeeded();
    await options.getByText("Build extension: "+uiBuild,{exact:true}).waitFor();
    report.extensionBuild=uiBuild;report.checks.visibleBuildAndRuntime=true;
    await capture(options,"native-versions-desktop");
    await options.setViewportSize({width:390,height:844});
    await options.evaluate(()=>scrollTo(0,0));
    assert(await options.getByRole("heading",{name:"Cấu hình engine"}).isVisible());
    await capture(options,"native-settings-mobile");
    await options.getByRole("button",{name:"Thư viện",exact:true}).click();
    await options.getByRole("heading",{name:"Thư viện của bạn"}).waitFor();
    assert.equal((await call("status")).engineWarm,false);
    report.checks.navigationDoesNotLoadModels=true;report.viewports=["1280x900","390x844"];
    report.limitations.push("Connect-only: no OCR/translation or manga overlay inference was run.");
  }
  if(libraryProbe){
    const loaded=await call("warmup");
    assert.equal(loaded.loadedLibrary,libraryProbe);
    assert.equal(loaded.modelsLoaded,false);
    report.libraryImport=loaded;report.checks.libraryImportAfterHandshake=true;
    report.limitations.push("Diagnostic warmup imports one library only; no OCR/model/translation run.");
  }else if(!connectOnly){
    await call("settings",cloudTest?{mode:"byok",provider:"openrouter",openrouterModel:cloudModel,cloudConsent:true,
      ...(cloudImageOcr?{ocr:"cloud-gemini",cloudOcrConsent:true,ocrBatch:4}:{}),autoSummary:false,metadataConsent:false}:{mode:"offline",autoSummary:false});
    const storyId=privateTest?"browser-private-qa":"browser-fixture",storyTitle=privateTest?"Trang manga kiểm thử riêng":"Trang tự tạo";
    await call("story.ensure",{storyId,title:storyTitle,genre:privateTest?"":"fantasy"});
    // Authored demo name, not a benchmark gold label. An exact reader lock
    // remains authoritative even when awkward; don't 'fix' it in the renderer.
    if(!privateTest)await call("memory.term",{storyId,category:"skill",ja:"氷結結界",vi:"Kết Giới Băng Giá",at:{chapter:1,page:0}});
    const fixtureArgs=[path.join(root,"scripts/fixture_server.py")];
    if(privateTest)fixtureArgs.push("--folder",privateFolder,"--private-page",privatePage);
    fixture=spawn(python,fixtureArgs,{cwd:root,windowsHide:true,stdio:["ignore","pipe","pipe"]});
    const url=await new Promise((resolve,reject)=>{
      let buffer="";const timer=setTimeout(()=>reject(new Error("Fixture startup timeout")),15000);
      fixture.on("error",error=>{clearTimeout(timer);reject(error);});
      fixture.on("exit",code=>{clearTimeout(timer);reject(new Error("Fixture exited: "+code));});
      fixture.stdout.on("data",chunk=>{buffer+=chunk;const end=buffer.indexOf("\n");if(end>=0){
        clearTimeout(timer);const actual=JSON.parse(buffer.slice(0,end));
        if(privateTest&&(!actual.private_sample||actual.private_page_ids?.length!==1||actual.private_page_ids[0]!==privatePage)){
          reject(new Error("Private fixture identity differs from the selected audited page"));return;
        }
        resolve(privateTest?new URL("/private-reader",actual.url).href:actual.url);
      }});
    });
    const reader=await context.newPage();readerPage=reader;await reader.setViewportSize({width:1280,height:900});
    reader.on("pageerror",error=>errors.push(error.message));
    reader.on("console",message=>{if(message.type()==="error")errors.push(message.text());});
    await reader.goto(url);await reader.locator("#page").waitFor();report.url=reader.url();report.title=await reader.title();
    await reader.waitForFunction(()=>document.querySelector("#page").complete&&document.querySelector("#page").naturalWidth>0);
    const original=privateTest?await reader.locator("#page").screenshot():undefined;
    assert.equal(reader.url(),url);assert.match(report.title,/Chapter 1/);assert(await reader.locator("h1").isVisible());
    report.checks.pageIdentity=true;report.checks.notBlank=true;
    assert.equal(await reader.locator("vite-error-overlay,nextjs-portal").count(),0);report.checks.noFrameworkOverlay=true;
    cdp=await context.newCDPSession(reader);await cdp.send("DOM.enable");await reader.bringToFront();
    if(privateTest)await reader.evaluate(()=>{
      window.__qaAltTReceived=0;document.addEventListener("keydown",event=>{
        if(event.altKey&&event.key.toLowerCase()==="t")window.__qaAltTReceived++;
      },true);
    });
    const readerConfig={storyId,title:storyTitle,genre:privateTest?"":"fantasy",at:{chapter:1,page:0},autoScan:true,prefetch:false};
    report.runs=[];
    const startReader=async()=>{const info=await call("reader.info");
      return call("reader.start",{...readerConfig,target:{tabId:info.tabId,url:info.url}});};
    const started=performance.now();await startReader();
    const overlay=await awaitOverlay(1,"cold");report.firstPageMs=performance.now()-started;report.regions=overlay.regions.length;
    const nativeResult=async()=>worker.evaluate(()=>globalThis.__qaNativeResults.at(-1).result);
    report.runs.push({name:"cold",readerTotalMs:report.firstPageMs,status:overlay.status,translations:overlay.translations,native:await nativeResult()});
    report.checks[renderReplay?"nativeReplayOverlay":"realOcrTranslationOverlay"]=true;
    const surfaces=report.runs[0].native.regions;
    if(privateTest){
      const translated=surfaces.filter(region=>region.vi&&region.scope?.action!=="defer");
      assertRenderedTranslations(surfaces,overlay.renderedItems);
      assert(surfaces.every(region=>region.speaker==="unknown"&&region.listener==="unknown"),
        "Private QA must not manufacture confirmed speaker/listener assignments");
      report.checks.completedTranslationsRenderedOnce=true;report.checks.sourceBoundIdsAndLettering=true;report.checks.unknownSpeakersPreserved=true;
      report.visualModes={flat:translated.filter(r=>r.balloon).length,
        integratedNodes:overlay.regions.filter(n=>n.attributes.class.split(" ").includes("integrated")).length,
        fallbackNodes:overlay.regions.filter(n=>!n.attributes.class.split(" ").includes("integrated")).length};
      // Hide toolbar only for the pixel-original probe/captures. This is QA,
      // not a product default; the user's reading controls stay functional.
      assert(overlay.bar);await cdp.send("DOM.setAttributeValue",{nodeId:overlay.bar.nodeId,name:"style",value:"visibility:hidden"});
    }else{
      assert.equal(surfaces.length,4,"The authored fixture has four dialogue balloons");
      assert(surfaces.every(region=>region.overlay==="white"&&region.balloon?.erasePolygons?.length),
        "A real detector crop fell back to translucent labeling in a known flat balloon");
      assert(overlay.regions.every(node=>node.attributes.class.split(" ").includes("integrated")),
        "Every real fixture balloon must use its measured integrated surface");
      report.checks.allRealBalloonsIntegrated=true;
    }
    const before=await bounds(overlay.regions[0]),scroll=await reader.evaluate(()=>{const before=scrollY;window.scrollBy(0,220);return scrollY-before;});
    assert(scroll>0,"Scroll test must actually move the page");
    await new Promise(resolve=>setTimeout(resolve,200));const after=await bounds((await shadowSnapshot()).regions[0]);
    assert(Math.abs(after.x-before.x)<2&&Math.abs(after.y-before.y+scroll)<2,"Real overlay drift after scroll");report.checks.scrollAligned=true;
    await capture(reader,"real-overlay-desktop");
    if(privateTest){
      await reader.keyboard.press("Alt+T");await reader.waitForTimeout(100);
      report.originalVisibility=await surfaceVisibility();report.altTReceived=await reader.evaluate(()=>window.__qaAltTReceived);
      const restored=await reader.locator("#page").screenshot();
      const pixelHash=buffer=>createHash("sha256").update(buffer).digest("hex");
      report.originalHashes={initial:pixelHash(original),restored:pixelHash(restored)};
      if(pixelHash(restored)!==pixelHash(original)){
        await call("reader.stop");report.originalHashes.stopped=pixelHash(await reader.locator("#page").screenshot());
      }
      assert.equal(createHash("sha256").update(restored).digest("hex"),createHash("sha256").update(original).digest("hex"),
        "Original view must restore exact source pixels, not a reconstructed page");
      report.checks.originalPixelsRestoredExactly=true;
      await reader.keyboard.press("Alt+T");await reader.waitForTimeout(100);
    }
    await reader.setViewportSize({width:390,height:844});await new Promise(resolve=>setTimeout(resolve,200));
    assert(await reader.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
    report.checks.mobileNoHorizontalOverflow=true;
    await capture(reader,"real-overlay-mobile");
    await call("reader.stop");report.checks.stoppedCleanly=true;report.viewports=["1280x900","390x844"];
    await reader.setViewportSize({width:1280,height:900});
    // A distinct URL yields a distinct page identity with the same authored
    // pixels. This exercises warm OCR/LLM, not a translation cache hit.
    let next,completed,actual;
    if(!privateTest){
      await reader.goto(url+"?qa=warm");await reader.bringToFront();
      next=performance.now();await startReader();completed=await awaitOverlay(2,"warm");
      actual=await nativeResult();
      report.runs.push({name:"warm-new-page",readerTotalMs:performance.now()-next,status:completed.status,translations:completed.translations,native:actual});
      assert.equal(actual.cached,false,"New page identity must not be reported as a cache sample");
      await call("reader.stop");
    }
    if(!renderReplay){
    next=performance.now();await startReader();completed=await awaitOverlay(privateTest?2:3,"cache");actual=await nativeResult();
    assert.equal(actual.cached,true,"Same page must reuse validated local translation cache");
    report.runs.push({name:"cached-revisit",readerTotalMs:performance.now()-next,status:completed.status,translations:completed.translations,native:actual});
    await call("reader.stop");report.checks[privateTest?"cachedRevisitSeparated":"warmAndCacheSeparated"]=true;
    }
    console.log(JSON.stringify({stage:"real-reader",runs:report.runs.map(({name,readerTotalMs,status})=>({name,readerTotalMs,status}))}));
  }
  assert.deepEqual(errors,[]);report.checks.consoleHealth=true;report.passed=true;
}catch(error){
  report.error=error.message;process.exitCode=1;
  // Preserve the completed native result even if the fixture's required
  // four bubbles were not all detected/painted. Otherwise an OCR coverage
  // failure is indistinguishable from a hung engine. Authored QA data only.
  if(worker)try{report.partialNativeResults=await worker.evaluate(()=>globalThis.__qaNativeResults);}catch{}
  if(cdp)try{
    const snapshot=await shadowSnapshot();
    report.partialOverlay={regionCount:snapshot.regions.length,translations:snapshot.translations,status:snapshot.status};
  }catch{}
  if(privateTest&&readerPage)try{await capture(readerPage,"real-overlay-failure");}catch(error){report.captureError=error.message;}
}
finally{
  if(cloudTest)try{report.cloudUsage=JSON.parse(await readFile(path.join(temporary,"cloud-usage.json"),"utf8"));}catch{/* No request may have started. */}
  // Persist a partial verdict before cleanup, so a shutdown failure cannot
  // silently erase useful evidence or be mistaken for a successful run.
  await mkdir(output,{recursive:true});await writeFile(path.join(output,"result.json"),JSON.stringify({...report,cleanupPending:true},null,2));
  if(!report.passed&&directSource)await run(python,[path.join(root,"scripts/qa_native_cleanup.py"),temporary],{windowsHide:true})
    .then(({stdout})=>{report.ownedNativeCleanup=JSON.parse(stdout);}).catch(error=>{report.nativeCleanupError=error.message;});
  if(context){
    let closeTimer;
    const closing=context.close();
    try{
      await Promise.race([closing,new Promise((_,reject)=>{
        closeTimer=setTimeout(()=>reject(new Error("QA browser shutdown exceeded 20 seconds")),20000);
      })]);
    }catch(error){
      report.closeError=error.message;process.exitCode=1;report.passed=false;
      // A successful import is not a successful lifetime check. Shut down
      // only native processes owned by this installation before retrying
      // the already requested browser close; never kill Edge by name.
      if(directSource)await run(python,[path.join(root,"scripts/qa_native_cleanup.py"),temporary],{windowsHide:true})
        .then(({stdout})=>{report.shutdownNativeCleanup=JSON.parse(stdout);}).catch(error=>{report.nativeCleanupError=error.message;});
      let retryTimer;
      await Promise.race([closing,new Promise(resolve=>{retryTimer=setTimeout(resolve,10000);})]).finally(()=>clearTimeout(retryTimer));
    }finally{clearTimeout(closeTimer);}
  }
  if(fixture)fixture.kill();
  if(registered)await registration("unregister")
    .then(()=>{report.checks.qaHostUnregistered=true;})
    .catch(error=>{report.cleanupError=error.message;process.exitCode=1;report.passed=false;});
  await mkdir(output,{recursive:true});await writeFile(path.join(output,"result.json"),JSON.stringify(report,null,2));
  // Full geometry stays in the local text evidence file. Printing
  // thousands of polygon points hid the useful failure/latency signal.
  const compactNative=result=>result&&({cached:result.cached,metrics:result.metrics,
    regions:result.regions.map(({id,ja,vi,overlay,review,balloon})=>({id,ja,vi,overlay,review,maskCount:balloon?.erasePolygons?.length??0}))});
  console.log(JSON.stringify({...report,evidence:output,
    runs:report.runs?.map(run=>({...run,native:compactNative(run.native)})),
    partialNativeResults:report.partialNativeResults?.map(reply=>({id:reply.id,result:compactNative(reply.result)}))},null,2));
  if(ramScreenshots.length)console.log("QA_RAM_IMAGES="+JSON.stringify(ramScreenshots));
}
