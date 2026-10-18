import test from "node:test";
import assert from "node:assert/strict";

test("options opened in a browser tab may use admin operations; ordinary pages may not",async()=>{
  const extensionId="epcjjhbilmmmbojldhnfblgmgiamajpl";
  const root="chrome-extension://"+extensionId+"/";
  let receiver:any;
  const incoming:Array<(message:any)=>void>=[];
  const disconnected:Array<()=>void>=[];
  let nativeCalls=0;const opened:string[]=[];
  let nativeFailure=false;
  (globalThis as any).chrome={
    runtime:{id:extensionId,getURL:(path:string)=>root+path,getManifest:()=>({version:"0.1.0",version_name:"0.1.0-dev.test"}),
      onMessage:{addListener:(fn:any)=>{receiver=fn;}},
      connectNative:()=>({
        onMessage:{addListener:(fn:any)=>incoming.push(fn)},
        onDisconnect:{addListener:(fn:any)=>disconnected.push(fn)},
        postMessage:(msg:any)=>{nativeCalls++;queueMicrotask(()=>incoming.forEach(fn=>fn({v:1,id:msg.id,
          ...(nativeFailure&&msg.op==="status"?{ok:false,error:{code:"STALE_CONTEXT",message:"Ngữ cảnh vừa đổi."}}:
            {ok:true,result:{version:"test"}})})));}
      })},
    storage:{local:{get:async()=>({profileId:"test-profile"}),set:async()=>{}}},
    tabs:{onRemoved:{addListener:()=>{}},onUpdated:{addListener:()=>{}},
      query:async()=>[{id:123,url:"https://example.com/",title:"QA"}],
      get:async()=>({id:123,active:true,url:"https://example.com/",title:"QA"}),
      create:async({url}:{url:string})=>{opened.push(url);},sendMessage:async()=>({started:true})},
    scripting:{executeScript:async()=>{}}
  };
  await import("../extension/background");
  const send=(sender:any,op="status")=>new Promise<any>(resolve=>receiver({op},sender,resolve));
  try{
    const before=nativeCalls;
    const diagnostic=await send({id:extensionId,url:root+"options.html",frameId:0,tab:{id:123}},"diagnostics");
    assert.equal(diagnostic.ok,true,diagnostic.error);
    assert.equal(diagnostic.result.host,"vn.mangalive.companion");
    assert.equal(diagnostic.result.state,"disconnected");
    assert.equal(diagnostic.result.extensionId,extensionId);
    assert.equal(diagnostic.result.manifestBuild,"0.1.0-dev.test");
    assert.equal(nativeCalls,before,"Diagnostic operation must not hello, inspect keys or read story memory");
    assert.deepEqual(Object.keys(diagnostic.result).sort(),["browser","extensionId","failure","host","manifestBuild","pendingCalls","state","v"].sort());
    const reply=await send({id:extensionId,url:root+"options.html",frameId:0,tab:{id:123}});
    assert.equal(reply.ok,true,"Tab-hosted options must not be mistaken for a stale reader session: "+reply.error);
    assert.equal(reply.result.version,"test");
    nativeFailure=true;
    const stale=await send({id:extensionId,url:root+"options.html",frameId:0,tab:{id:123}});
    assert.equal(stale.ok,false);assert.equal(stale.code,"STALE_CONTEXT");
    assert.equal(stale.error,"Ngữ cảnh vừa đổi.");
    nativeFailure=false;
    const callsBefore=nativeCalls;
    assert.equal((await send({id:extensionId,url:"https://example.com/",frameId:0,tab:{id:123}})).ok,false);
    assert.equal((await send({id:extensionId,url:root+"not-a-ui.html",frameId:0,tab:{id:123}})).ok,false);
    assert.equal((await send({id:extensionId,url:root+"options.html",frameId:7,tab:{id:123}})).ok,false);
    assert.equal((await send({id:extensionId,url:"https://example.com/",frameId:0,tab:{id:123}},"diagnostics")).ok,false);
    assert.equal(nativeCalls,callsBefore,"Untrusted senders must never reach native admin operations");
    const reader={id:extensionId,url:"https://example.com/",frameId:0,tab:{id:123}};
    assert.equal((await send(reader,"reader.settings")).ok,false,"No settings navigation from a stale/non-reader tab");
    const start=await new Promise<any>(resolve=>receiver({op:"reader.start",params:{storyId:"qa",title:"QA",at:{chapter:1,page:0},autoScan:false,prefetch:false,
      target:{tabId:123,url:"https://example.com/"}}},
      {id:extensionId,url:root+"popup.html",frameId:0},resolve));
    assert.equal(start.ok,true,start.error);
    const beforeOpen=nativeCalls;
    assert.equal((await send({...reader,frameId:1},"reader.settings")).ok,false);
    assert.equal((await send({...reader,url:"https://other.example/"},"reader.settings")).ok,false);
    assert.equal((await send(reader,"reader.settings")).ok,true);
    assert.deepEqual(opened,[root+"options.html#settings"]);
    assert.equal(nativeCalls,beforeOpen,"Opening model configuration must not change settings, call warmup or pay for translation");
    assert.equal((await send({id:extensionId,url:root+"options.html#settings",frameId:0},"status")).ok,true);
  }finally{disconnected.forEach(fn=>fn());}
});
