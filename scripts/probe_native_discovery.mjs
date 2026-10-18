// Read-only native discovery probe. Loads the installed development extension
// in a disposable Edge profile, but uses its REAL host name/registration.
// Send status before hello: the actual host must reject it with PROFILE. This
// proves transport/launch without initializing a memory profile or reading keys.
import {chromium} from "playwright";
import {mkdtemp,readFile} from "node:fs/promises";
import {fileURLToPath} from "node:url";
import os from "node:os";
import path from "node:path";
import assert from "node:assert/strict";

const root=path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const idIndex=process.argv.indexOf("--extension-id");
const expectedId=idIndex>=0?process.argv[idIndex+1]:undefined;
const bridgeMode=process.argv.includes("--bridge");
const headed=process.argv.includes("--headed");
assert(typeof expectedId==="string"&&/^[a-p]{32}$/.test(expectedId),"Explicit installed extension ID required");
const extension=path.join(root,"dist/extension");
const manifest=JSON.parse(await readFile(path.join(extension,"manifest.json"),"utf8"));
assert(manifest.permissions.includes("nativeMessaging"));
const profile=await mkdtemp(path.join(os.tmpdir(),"mangalive-discovery-"));
const report={passed:false,browser:"isolated Edge; actual installed host registration",
  build:manifest.version_name,expectedId,host:"vn.mangalive.companion",
  cloud:false,modelLoad:false,readerProfileInitialized:bridgeMode,registryChanged:false,
  headed,
  transportMode:bridgeMode?"production bridge and options; new isolated reader profile":"raw status before hello"};
let context;
try{
  context=await chromium.launchPersistentContext(profile,{channel:"msedge",headless:!headed,
    ignoreDefaultArgs:["--disable-extensions"],args:["--disable-extensions-except="+extension,"--load-extension="+extension]});
  let [worker]=context.serviceWorkers();
  if(!worker)worker=await context.waitForEvent("serviceworker",{timeout:15000});
  report.actualId=new URL(worker.url()).hostname;
  assert.equal(report.actualId,expectedId,"Different extension ID; refusing a misleading discovery result");
  if(bridgeMode){
    // This profile was just created above. Never attach to personal Edge or
    // copy its storage. The normal UI hello initializes only this QA profile;
    // status must leave engines cold and must not call a model/API.
    const page=await context.newPage();
    await page.goto("chrome-extension://"+report.actualId+"/options.html");
    report.bridge=await page.evaluate(async()=>{
      const result=await chrome.runtime.sendMessage({op:"status"});
      const diagnostics=await chrome.runtime.sendMessage({op:"diagnostics"});
      return {ok:result?.ok,error:result?.ok?undefined:result?.error,
        engineWarm:result?.result?.engineWarm,runtimeBuild:result?.result?.runtimeBuild,
        failure:diagnostics?.result?.failure,state:diagnostics?.result?.state};
    });
    assert.equal(report.bridge.ok,true,report.bridge.error??"Production bridge status failed");
    assert.equal(report.bridge.engineWarm,false,"Connection test must not load inference engines");
    assert.equal(report.bridge.failure,"NONE");
    assert.equal(report.bridge.state,"ready");
    report.passed=true;
    // Release only the disposable profile's Native Messaging port.
    await worker.evaluate(()=>chrome.runtime.reload()).catch(()=>{});
  }else{
  report.transport=await worker.evaluate(host=>new Promise(resolve=>{
    const requestId=crypto.randomUUID();let port,settled=false;
    const finish=value=>{
      if(settled)return;settled=true;clearTimeout(timer);
      try{port?.disconnect();}catch{/* Already closed. */}
      resolve(value);
    };
    const timer=setTimeout(()=>finish({kind:"timeout",error:"No native response after 15 seconds"}),15000);
    try{
      port=chrome.runtime.connectNative(host);
      port.onDisconnect.addListener(()=>finish({kind:"disconnect",error:chrome.runtime.lastError?.message??"Native host disconnected"}));
      port.onMessage.addListener(reply=>finish({kind:"reply",v:reply?.v,idMatches:reply?.id===requestId,
        ok:reply?.ok,errorCode:reply?.error?.code}));
      // Never hello: it would initialize a reader profile and query the Vault.
      port.postMessage({v:1,id:requestId,profile:"discovery-uninitialized",op:"status",params:{}});
    }catch(error){finish({kind:"exception",error:error.message});}
  }),report.host);
  assert.equal(report.transport.kind,"reply",report.transport.error??"No framed native reply");
  assert.equal(report.transport.v,1);assert.equal(report.transport.idMatches,true);
  assert.equal(report.transport.ok,false);assert.equal(report.transport.errorCode,"PROFILE");
  report.passed=true;
  }
}catch(error){report.error=error.message;process.exitCode=1;}
finally{if(context)await context.close();console.log(JSON.stringify(report,null,2));}
