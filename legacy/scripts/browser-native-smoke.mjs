// Actual browser Native Messaging handshake, isolated temporary Edge profile.
// No personal browser control, no cloud calls, no modification of permissions.
import {chromium} from "playwright";
import {mkdtemp,mkdir,writeFile} from "node:fs/promises";
import os from "node:os";
import path from "node:path";
import {fileURLToPath} from "node:url";
import assert from "node:assert/strict";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const profile=await mkdtemp(path.join(os.tmpdir(),"manga-edge-native-"));
const output=path.join(os.tmpdir(),"mangalive-native-browser-qa");await mkdir(output,{recursive:true});
let context;
const ramImages=[];
async function screenshot(page,label){
  ramImages.push({label,mimeType:"image/png",data:(await page.screenshot()).toString("base64")});
  report.screenshots.push(label+" (RAM-only)");
}
const report={profile:"isolated temporary profile",cloud:false,passed:false,
  browser:"Playwright isolated headless Edge; Browser plugin not available",
  checks:{},screenshots:[],limitations:["Native settings/library only; not installed personal-browser overlay, OCR or translation-quality proof."]};
try{
  context=await chromium.launchPersistentContext(profile,{channel:"msedge",headless:true,
    ignoreDefaultArgs:["--disable-extensions"],
    args:["--disable-extensions-except="+path.join(root,"dist/extension"),"--load-extension="+path.join(root,"dist/extension")]});
  let [worker]=context.serviceWorkers();
  if(!worker)worker=await context.waitForEvent("serviceworker",{timeout:15000});
  const id=new URL(worker.url()).hostname;report.extensionId=id;
  const errors=[];const page=await context.newPage();
  page.on("pageerror",error=>errors.push(error.message));
  page.on("console",message=>{if(message.type()==="error")errors.push(message.text());});
  await page.setViewportSize({width:1280,height:900});
  const url="chrome-extension://"+id+"/options.html";await page.goto(url);
  // Fail with the transport error itself, rather than an unrelated 30-second
  // heading timeout when the current account cannot discover the host.
  const result=await page.evaluate(async()=>chrome.runtime.sendMessage({op:"status"}));
  assert.equal(result.ok,true,result.error??"Native handshake failed");
  await page.getByRole("heading",{name:"Thư viện của bạn"}).waitFor();
  report.url=page.url();report.title=await page.title();
  assert.equal(report.url,url);assert.match(report.title,/Live translation/i);
  report.checks.pageIdentity=true;
  assert((await page.locator("main").innerText()).includes("Thư viện của bạn"));
  report.checks.notBlank=true;
  assert.equal(await page.locator("vite-error-overlay,nextjs-portal").count(),0);
  report.checks.noFrameworkOverlay=true;
  report.status=result;assert.equal(result.ok,true,result.error??"Native handshake failed");
  assert.equal(result.result.engineWarm,false,"Library must not load inference models");
  report.checks.nativeHandshake=true;report.checks.coldLibrary=true;
  await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
  await page.getByRole("heading",{name:"Cấu hình engine"}).waitFor();
  await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).click();
  await page.getByText("Đã lưu. Thay đổi luồng CPU áp dụng sau khi companion khởi động lại. Chưa gửi tác vụ dịch; bật dịch lại để dùng cấu hình mới.",{exact:true}).waitFor();
  const saved=await page.evaluate(async()=>chrome.runtime.sendMessage({op:"status"}));
  assert.equal(saved.ok,true);assert.equal(saved.result.settings.mode,"offline");
  assert.equal(saved.result.settings.cloudConsent,false);assert.equal(saved.result.settings.metadataConsent,false);
  assert.equal(saved.result.engineWarm,false);
  report.checks.realSettingsInteraction=true;
  await page.getByRole("button",{name:"Thư viện",exact:true}).click();
  await page.getByRole("heading",{name:"Thư viện của bạn"}).waitFor();
  await screenshot(page,"native-library-desktop");
  await page.setViewportSize({width:390,height:844});
  await page.getByRole("button",{name:"Cài đặt",exact:true}).click();
  await page.getByRole("heading",{name:"Cấu hình engine"}).waitFor();
  assert(await page.getByRole("button",{name:"Lưu cấu hình",exact:true}).isEnabled());
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),"Mobile must not overflow sideways");
  await screenshot(page,"native-settings-mobile");
  report.checks.mobileNoHorizontalOverflow=true;report.viewports=["1280x900","390x844"];
  assert.deepEqual(errors,[]);report.checks.consoleHealth=true;
  report.checks.screenshotEvidence=true;report.passed=true;
  await writeFile(path.join(output,"result.json"),JSON.stringify(report,null,2));
  console.log(JSON.stringify({stage:"handshake",...report},null,2));
  // Release persistent native ports before shutting the test browser down.
  // This reload affects only this disposable profile, never the user's Edge.
  await worker.evaluate(()=>chrome.runtime.reload()).catch(()=>{});
}catch(error){report.error=error.message;process.exitCode=1;}
finally{
  if(context)await context.close();
  await writeFile(path.join(output,"result.json"),JSON.stringify(report,null,2));
  console.log(JSON.stringify(report,null,2));
  if(process.argv.includes("--emit-ram-images"))console.log("QA_RAM_IMAGES="+JSON.stringify(ramImages));
}
