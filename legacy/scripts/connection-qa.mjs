// Persistent regression QA for the real React options UI with a failed/pending
// Native Messaging boundary. Never a personal profile or inference test.
import {chromium} from "playwright";
import {mkdir,mkdtemp,writeFile} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const output=await mkdtemp(path.join(os.tmpdir(),"mangalive-connection-qa-"));
const origin="http://127.0.0.1:65303";
const browser=await chromium.launch({channel:"msedge",headless:true});
const report={passed:false,browser:"Playwright isolated Edge; Browser skill not available",
  origin,transport:"mocked failed/pending status; production React bundle",cloud:false,
  checks:{},failures:[],screenshots:[],limitations:["Not the user's Native Messaging connection or OCR/translation quality proof."]};
const ramImages=[];

async function makePage(mode,width=1280){
  const page=await browser.newPage({viewport:{width,height:width===390?844:900}});
  const errors=[];
  page.on("pageerror",error=>errors.push(error.message));
  page.on("console",message=>{if(message.type()==="error")errors.push(message.text());});
  for(const [file,type] of [["options.html","text/html"],["ui.js","application/javascript"],["ui.css","text/css"]])
    await page.route(origin+"/"+file,route=>route.fulfill({path:path.join(root,"dist/extension",file),contentType:type,
      ...(file==="options.html"?{headers:{"Content-Security-Policy":"script-src 'self'; object-src 'self'"}}:{})}));
  await page.addInitScript(mode=>{
    window.__qaCspViolations=[];
    document.addEventListener("securitypolicyviolation",event=>window.__qaCspViolations.push({
      directive:event.effectiveDirective,blocked:event.blockedURI}));
    window.__qaMode=mode;window.__qaCalls=[];window.__qaPending=[];window.__qaDiagnosticsPending=[];
    window.__qaDiagnostic={v:1,browser:"edge",host:"vn.mangalive.companion",state:"disconnected",
      failure:"NATIVE_HOST_NOT_FOUND",pendingCalls:0,extensionId:"a".repeat(32),manifestBuild:"0.1.0-dev.qa-connection",
      profileId:"DO_NOT_COPY_PROFILE",keys:{key:"DO_NOT_COPY_KEY"},story:"DO_NOT_COPY_STORY",url:"https://do-not-copy.invalid/"};
    const settings={mode:"byok",provider:"openrouter",cloudConsent:false,metadataConsent:false,autoSummary:false,
      artCleanup:false,threads:4,detector:"paddle",ocr:"manga",ocrBatch:2,showSfx:false,
      openrouterModel:"test-model",deepseekModel:"deepseek-flash",geminiModel:"test-model"};
    window.__qaStatus={version:"0.1.0",runtimeBuild:"pkg-sha256:"+"a".repeat(64),settings,keys:{openrouter:false},models:{ocr:true,detector:true},
      stories:[{id:"stored-story",title:"Hồ sơ có sẵn",version:1}],engineWarm:false,
      promptVersion:"qa-prompt",ocrVersion:"qa-ocr",layoutVersion:"qa-layout",scopeVersion:"qa-scope",speakerBindingVersion:"qa-binding"};
    if(mode==="legacy")delete window.__qaStatus.runtimeBuild;
    window.chrome={runtime:{id:"a".repeat(32),getManifest:()=>({version:"0.1.0",version_name:"0.1.0-dev.qa-connection"}),
      async sendMessage(message){
        window.__qaCalls.push(message.op);
        if(message.op==="reader.info")return {ok:true,result:{tabId:12,title:"Trang tự tạo",url:"http://127.0.0.1:65303/chapter/1"}};
        if(message.op==="diagnostics"){
          if(window.__qaDiagnosticMode==="pending")return new Promise(resolve=>window.__qaDiagnosticsPending.push(resolve));
          return {ok:true,result:JSON.parse(JSON.stringify(window.__qaDiagnostic))};
        }
        if(message.op!=="status")throw new Error("Unexpected operation in connect-only QA: "+message.op);
        if(window.__qaMode==="failure")return {ok:false,error:"Specified native messaging host not found."};
        if(window.__qaMode==="malformed")return {ok:true,result:{version:"old-host",stories:[]}};
        if(window.__qaMode==="pending")return new Promise(resolve=>window.__qaPending.push(resolve));
        return {ok:true,result:JSON.parse(JSON.stringify(window.__qaStatus))};
      }}};
  },mode);
  await page.goto(origin+"/options.html");
  assert.equal(page.url(),origin+"/options.html");assert.equal(await page.title(),"Live translation");
  assert((await page.locator("main").innerText()).includes("Live translation"));
  assert.equal(await page.locator("vite-error-overlay,nextjs-portal").count(),0);
  // Even a caught Function/eval probe raises a CSP event. Console health or
  // rendered content alone misses the DevTools issue seen in a real MV3 page.
  await page.waitForTimeout(50);
  assert.deepEqual(await page.evaluate(()=>window.__qaCspViolations),[],"Strict extension CSP must not report dynamic evaluation");
  report.checks.strictCspWithoutEval=true;
  report.checks.identityNotBlankAndNoFrameworkOverlay=true;
  return {page,errors};
}

async function screenshot(page,name){
  ramImages.push({label:name,mimeType:"image/png",data:(await page.screenshot()).toString("base64")});
  report.screenshots.push(name+" (RAM-only)");
}
async function scenario(name,fn){
  try{await fn();report.checks[name]=true;}
  catch(error){report.checks[name]=false;report.failures.push({name,error:error.message});}
}

try{
  await scenario("manualDiagnosticsDoNotRetryNativeOrCopyPrivateData",async()=>{
    const {page,errors}=await makePage("failure",390);
    try{
      await page.getByRole("alert").waitFor();
      assert.equal(await page.getByRole("button",{name:"Chẩn đoán kết nối",exact:true}).count(),1);
      assert.equal(await page.evaluate(()=>window.__qaCalls.includes("diagnostics")),false,"No automatic diagnostics on load");
      const statusBefore=await page.evaluate(()=>window.__qaCalls.filter(op=>op==="status").length);
      await page.getByRole("button",{name:"Chẩn đoán kết nối",exact:true}).click();
      const input=page.getByLabel("Chẩn đoán kết nối · có thể sao chép",{exact:true});
      await input.waitFor({timeout:1500});
      const diagnostic=JSON.parse(await input.inputValue());
      assert.equal(diagnostic.host,"vn.mangalive.companion");assert.equal(diagnostic.browser,"edge");
      assert.equal(diagnostic.failure,"NATIVE_HOST_NOT_FOUND");assert.equal(await input.getAttribute("readonly"),"");
      assert(!(await input.inputValue()).includes("DO_NOT_COPY"));assert(!("url" in diagnostic)&&!("keys" in diagnostic));
      assert.equal(await page.evaluate(()=>window.__qaCalls.filter(op=>op==="status").length),statusBefore,
        "Diagnostic button must not reconnect or retry a native request");
      assert(await page.getByRole("alert").isVisible());
      await page.getByRole("button",{name:"Cài đặt",exact:true}).click();assert(await input.isVisible());
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await screenshot(page,"connection-diagnostics-mobile");
      assert.deepEqual(errors,[]);assert(await page.evaluate(()=>window.__qaCalls.every(op=>["status","reader.info","diagnostics"].includes(op))));
    }finally{await page.close();}
  });
  await scenario("lateDiagnosticCannotResurrectRecoveredConnectionError",async()=>{
    const {page,errors}=await makePage("failure");
    try{
      await page.getByRole("alert").waitFor();
      assert.equal(await page.getByRole("button",{name:"Chẩn đoán kết nối",exact:true}).count(),1);
      const input=page.getByLabel("Chẩn đoán kết nối · có thể sao chép",{exact:true});
      await page.getByRole("button",{name:"Chẩn đoán kết nối",exact:true}).click();
      await input.waitFor({timeout:1500});
      assert.equal(JSON.parse(await input.inputValue()).failure,"NATIVE_HOST_NOT_FOUND",
        "First prove the diagnostic is rendered and accessible before testing its removal");
      await page.evaluate(()=>{window.__qaDiagnosticMode="pending";});
      await page.getByRole("button",{name:"Chẩn đoán kết nối",exact:true}).click();
      await page.waitForFunction(()=>window.__qaDiagnosticsPending.length===1);
      assert.equal(await input.count(),0,"A new diagnostic request must clear the old result");
      assert(await page.getByRole("button",{name:"Đang đọc chẩn đoán…",exact:true}).isDisabled());
      await page.evaluate(()=>{window.__qaMode="success";});
      await page.getByRole("button",{name:"Kết nối lại",exact:true}).click();
      await page.getByRole("button",{name:/Hồ sơ có sẵn/}).waitFor();
      await page.evaluate(()=>{for(const resolve of window.__qaDiagnosticsPending.splice(0))resolve({ok:true,result:window.__qaDiagnostic});});
      await page.waitForTimeout(100);
      assert.equal(await page.getByRole("alert").count(),0);assert.equal(await page.locator("header .badge").innerText(),"Cloud BYOK");
      assert.equal(await input.count(),0);
      assert.deepEqual(errors,[]);assert(await page.evaluate(()=>window.__qaCalls.every(op=>["status","reader.info","diagnostics"].includes(op))));
    }finally{await page.close();}
  });
  await scenario("connectionErrorSurvivesNavigation",async()=>{
    const {page,errors}=await makePage("failure");
    try{
      await page.getByRole("alert").waitFor();
      await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
      await screenshot(page,"failed-settings-desktop");
      assert(await page.getByRole("alert").isVisible(),"Changing tab hid the companion connection error and left Settings blank");
      assert.equal(await page.locator("header .badge").innerText(),"Chưa kết nối");
      await page.getByRole("button",{name:"Thư viện",exact:true}).click();
      assert.equal(await page.getByText("Bật dịch và xác nhận truyện để tạo hồ sơ đầu tiên.",{exact:true}).count(),0,
        "Failed status must not be presented as an empty story database");
      await page.evaluate(()=>{window.__qaMode="success";});
      await page.getByRole("button",{name:"Kết nối lại",exact:true}).click();
      await page.getByRole("button",{name:/Hồ sơ có sẵn/}).waitFor();
      assert.equal(await page.getByRole("alert").count(),0);
      assert.equal(await page.locator("header .badge").innerText(),"Cloud BYOK");
      await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
      await page.getByRole("heading",{name:"Cấu hình engine"}).waitFor();
      assert((await page.locator("footer").innerText()).includes("0.1.0-dev.qa-connection"));
      assert.equal(await page.getByLabel("Chế độ dịch",{exact:true}).inputValue(),"byok");
      assert.equal(await page.getByLabel(/Hòa chữ vào tranh/).isChecked(),false,"Keep the reader's saved opt-out");
      assert.equal(await page.getByRole("checkbox",{name:/Cho phép gửi text/}).isChecked(),false);
      await page.locator(".runtime-details > summary").click();
      await page.getByText("qa-prompt",{exact:true}).waitFor();
      await page.getByText("pkg-sha256:"+"a".repeat(64),{exact:true}).waitFor();
      await page.locator(".runtime-details").scrollIntoViewIfNeeded();
      await screenshot(page,"recovered-settings-desktop");
      assert.deepEqual(errors,[]);assert(await page.evaluate(()=>window.__qaCalls.every(op=>["status","reader.info"].includes(op))));
    }finally{await page.close();}
  });
  await scenario("runtimeIdentityDoesNotOverflowMobileOrTriggerInference",async()=>{
    const {page,errors}=await makePage("success",390);
    try{
      await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
      await page.locator(".runtime-details > summary").click();
      await page.getByText("pkg-sha256:"+"a".repeat(64),{exact:true}).waitFor({timeout:1500});
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await page.locator(".runtime-details").scrollIntoViewIfNeeded();
      await screenshot(page,"runtime-identity-mobile");
      assert.deepEqual(errors,[]);
      assert(await page.evaluate(()=>window.__qaCalls.every(op=>["status","reader.info"].includes(op))));
    }finally{await page.close();}
  });
  await scenario("legacyHostDoesNotInventRuntimeIdentity",async()=>{
    const {page,errors}=await makePage("legacy",390);
    try{
      await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
      await page.locator(".runtime-details > summary").click();
      await page.getByText("Companion chưa báo mã runtime",{exact:true}).waitFor({timeout:1500});
      assert.equal(await page.getByText("pkg-sha256:",{exact:false}).count(),0);
      assert.deepEqual(errors,[]);
    }finally{await page.close();}
  });
  await scenario("pendingIsNotOfflineOrEmptyLibrary",async()=>{
    const {page,errors}=await makePage("pending",390);
    try{
      await page.waitForFunction(()=>window.__qaCalls.includes("status"));
      await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
      await screenshot(page,"pending-settings-mobile");
      assert.equal(await page.locator("header .badge").innerText(),"Đang kết nối");
      assert(await page.getByRole("heading",{name:"Đang kết nối companion…",exact:true}).isVisible());
      await page.getByRole("button",{name:"Thư viện",exact:true}).click();
      assert.equal(await page.getByText("Bật dịch và xác nhận truyện để tạo hồ sơ đầu tiên.",{exact:true}).count(),0);
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1));
      await page.evaluate(()=>{const reply={ok:true,result:window.__qaStatus};for(const resolve of window.__qaPending.splice(0))resolve(reply);});
      await page.getByRole("button",{name:/Hồ sơ có sẵn/}).waitFor();
      assert.deepEqual(errors,[]);assert(await page.evaluate(()=>window.__qaCalls.every(op=>["status","reader.info"].includes(op))));
    }finally{await page.close();}
  });
  await scenario("incompatibleStatusIsAnActionableError",async()=>{
    const {page,errors}=await makePage("malformed",390);
    try{
      await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
      await page.getByRole("alert").waitFor({timeout:1500});
      assert((await page.getByRole("alert").innerText()).includes("không tương thích"));
      await screenshot(page,"incompatible-settings-mobile");
      assert.equal(await page.locator("header .badge").innerText(),"Chưa kết nối");
      assert.deepEqual(errors,[]);
    }finally{await page.close();}
  });
  await scenario("expiredReplyCannotOverwriteExplicitRecovery",async()=>{
    const {page,errors}=await makePage("pending");
    try{
      await page.getByRole("alert").waitFor({timeout:18000});
      assert((await page.getByRole("alert").innerText()).includes("sau 15 giây"));
      await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
      assert(await page.getByRole("alert").isVisible());
      await page.evaluate(()=>{window.__qaMode="success";});
      await page.getByRole("button",{name:"Kết nối lại",exact:true}).click();
      await page.getByRole("heading",{name:"Cấu hình engine"}).waitFor();
      await page.evaluate(()=>{
        const old={...window.__qaStatus,settings:{...window.__qaStatus.settings,mode:"offline"},
          stories:[{id:"expired-story",title:"EXPIRED_REPLY_QA",version:1}]};
        for(const resolve of window.__qaPending.splice(0))resolve({ok:true,result:old});
      });
      await page.waitForTimeout(100);
      assert.equal(await page.getByLabel("Chế độ dịch",{exact:true}).inputValue(),"byok");
      await page.getByRole("button",{name:"Thư viện",exact:true}).click();
      await page.getByRole("button",{name:/Hồ sơ có sẵn/}).waitFor();
      assert.equal(await page.getByText("EXPIRED_REPLY_QA",{exact:true}).count(),0);
      assert.deepEqual(errors,[]);assert(await page.evaluate(()=>window.__qaCalls.every(op=>["status","reader.info"].includes(op))));
    }finally{await page.close();}
  });
  report.passed=report.failures.length===0;
}finally{
  await browser.close();await mkdir(output,{recursive:true});
  await writeFile(path.join(output,"result.json"),JSON.stringify(report,null,2));
  console.log(JSON.stringify({...report,evidence:output},null,2));
  if(process.argv.includes("--ram-preview"))console.log("QA_RAM_IMAGES="+JSON.stringify(ramImages));
}
if(!report.passed)process.exitCode=1;
