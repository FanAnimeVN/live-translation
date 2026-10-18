import test from "node:test";
import assert from "node:assert/strict";

test("reader start captures the target before native wait and never follows a later tab or URL",async()=>{
  const extensionId="epcjjhbilmmmbojldhnfblgmgiamajpl",root="chrome-extension://"+extensionId+"/";
  let receiver:any,active:any={id:12,active:true,url:"https://reader.example/chapter/1",title:"Reader"};
  const tabs=new Map<number,any>([[12,active]]),disconnected:Array<()=>void>=[],incoming:Array<(m:any)=>void>=[];
  let hold=false,waiting:()=>void=()=>{},release:()=>void=()=>{};
  let injected=0,nativeCalls=0,sent=0,configWrites=0,navigateOnInject=false;
  let contentAck:any={started:true};
  (globalThis as any).chrome={runtime:{id:extensionId,getURL:(s:string)=>root+s,
    onMessage:{addListener:(fn:any)=>receiver=fn},connectNative:()=>({
      onMessage:{addListener:(fn:any)=>incoming.push(fn)},onDisconnect:{addListener:(fn:any)=>disconnected.push(fn)},
      postMessage:(msg:any)=>{nativeCalls++;const respond=()=>incoming.forEach(fn=>fn({v:1,id:msg.id,ok:true,result:{}}));
        if(msg.op==="story.ensure"&&hold){release=respond;waiting();}else queueMicrotask(respond);}
    })},storage:{local:{get:async()=>({profileId:"qa-reader-target"}),set:async(value:any)=>{
      for(const key of Object.keys(value).filter(key=>key.startsWith("reader:"))){
        configWrites++;assert.equal(value[key].target,undefined,"The transient tab/URL must not enter stored story configuration");
      }
    }}},
    tabs:{query:async()=>[active],get:async(id:number)=>{if(!tabs.has(id))throw new Error("No tab");return {...tabs.get(id)};},
      sendMessage:async(id:number,message:any)=>{sent++;assert.equal(id,12);assert.equal(message.expectedUrl,"https://reader.example/chapter/1");return contentAck;},
      onRemoved:{addListener:()=>{}},onUpdated:{addListener:()=>{}}},
    scripting:{executeScript:async()=>{injected++;if(navigateOnInject){active={...active,url:"https://reader.example/chapter/2"};tabs.set(12,active);}}}};
  await import("../extension/background");
  const expectedTarget={tabId:12,url:"https://reader.example/chapter/1"};
  const start=(target:any=expectedTarget)=>new Promise<any>(resolve=>receiver({op:"reader.start",params:{storyId:"qa-target",title:"QA",
    at:{chapter:1,page:0},autoScan:false,prefetch:false,target}},{id:extensionId,url:root+"popup.html",frameId:0},resolve));
  try{
    for(const target of [null,{...expectedTarget,url:"https://reader.example/chapter/2"},{...expectedTarget,tabId:13}]){
      const stale=await start(target);assert.equal(stale.ok,false,"A missing or stale UI target must fail before connecting");
      assert.match(stale.error,/popup/);
      assert.equal(nativeCalls,0);assert.equal(injected,0);assert.equal(sent,0);
    }
    const original=active;
    active={id:99,active:true,url:root+"options.html"};
    const invalid=await start();assert.equal(invalid.ok,false);
    assert.equal(nativeCalls,0,"An invalid reading target must be rejected before connecting/creating a story");
    active=original;hold=true;
    for(const change of ["other-tab","same-tab-url","closed"]){
      active={id:12,active:true,url:"https://reader.example/chapter/1",title:"Reader"};tabs.set(12,active);
      const reached=new Promise<void>(resolve=>waiting=resolve),pending=start();await reached;
      if(change==="other-tab"){
        tabs.set(12,{...active,active:false});active={id:13,active:true,url:"https://other.example/"};tabs.set(13,active);
      }else if(change==="same-tab-url"){active={...active,url:"https://reader.example/chapter/2"};tabs.set(12,active);}
      else tabs.delete(12);
      release();const result=await pending;
      assert.equal(result.ok,false,change+" must not start with the old confirmed chapter");
      assert.equal(injected,0);assert.equal(sent,0);
    }
    const restore=()=>{active={id:12,active:true,url:"https://reader.example/chapter/1",title:"Reader"};tabs.set(12,active);};
    hold=false;restore();navigateOnInject=true;
    const changedDuringInjection=await start();assert.equal(changedDuringInjection.ok,false);
    assert.equal(sent,0,"Navigation while injecting must not start the new page with old context");
    assert.equal(configWrites,0);navigateOnInject=false;
    for(const ack of [{started:false},undefined]){
      restore();contentAck=ack;
      const rejected=await start();assert.equal(rejected.ok,false);
      assert.equal(configWrites,0,"A rejected/missing content acknowledgement must not save the reader configuration");
      const info=await new Promise<any>(resolve=>receiver({op:"reader.info"},{id:extensionId,url:root+"popup.html",frameId:0},resolve));
      assert.equal(info.ok,true);assert.equal(info.result.session,undefined,"Failed start must remove its session");
    }
    restore();contentAck={started:true};
    const valid=await start();assert.equal(valid.ok,true,valid.error);assert.equal(valid.result.tabId,12);
    assert.equal(injected,4);assert.equal(sent,3);assert.equal(configWrites,1);
  }finally{disconnected.forEach(fn=>fn());}
});
