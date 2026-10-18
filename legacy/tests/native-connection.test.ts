import test from "node:test";
import assert from "node:assert/strict";
import {NativeBridge} from "../extension/native";

function fakeNative() {
  class Port {
    replies:Array<(message:any)=>void>=[];
    disconnectListeners:Array<()=>void>=[];
    sent:any[]=[];
    disconnects=0;
    failHello=false;
    onMessage={addListener:(listener:(message:any)=>void)=>this.replies.push(listener)};
    onDisconnect={addListener:(listener:()=>void)=>this.disconnectListeners.push(listener)};
    postMessage(message:any) {
      this.sent.push(message);
      if(message.op==="hello")queueMicrotask(()=>this.reply(message.id,
        this.failHello?{ok:false,error:{message:"Handshake rejected"}}:{ok:true,result:{version:"qa"}}));
    }
    disconnect(){this.disconnects++;}
    reply(id:string,value:any){for(const listener of this.replies)listener({v:1,id,...value});}
    emitDisconnect(){for(const listener of this.disconnectListeners)listener();}
  }
  const first=new Port(),second=new Port();first.failHello=true;
  let connections=0;
  globalThis.chrome={
    runtime:{connectNative:()=>connections++===0?first:second},
    storage:{local:{get:async()=>({profileId:"isolated-native-unit"}),set:async()=>{}}},
  } as unknown as typeof chrome;
  return {first,second,connections:()=>connections};
}

test("failed handshake disconnects its own port before a reader retries",async()=>{
  const native=fakeNative(),bridge=new NativeBridge();
  await assert.rejects(bridge.connect(),/Handshake rejected/);
  assert.equal(native.first.disconnects,1,"A failed hello must not retain a native host");
  await bridge.connect();
  assert.equal(native.connections(),2);
  native.second.emitDisconnect();
});

test("late disconnect from an old port cannot break its replacement",async()=>{
  const native=fakeNative(),bridge=new NativeBridge();
  await assert.rejects(bridge.connect(),/Handshake rejected/);
  await bridge.connect();
  const request=bridge.call("status");
  await new Promise<void>(resolve=>setImmediate(resolve));
  const status=native.second.sent.find(message=>message.op==="status");assert(status);
  // Failure is observed immediately so a regression cannot become an
  // unhandled rejection or wait for the production 180-second timeout.
  const outcome=request.then(value=>({value}),error=>({error}));
  native.first.reply(status.id,{ok:true,result:{wrongChannel:true}});
  native.first.emitDisconnect();
  native.second.reply(status.id,{ok:true,result:{engineWarm:false}});
  assert.deepEqual(await outcome,{value:{engineWarm:false}});
  assert.equal(native.second.disconnects,0);
  native.second.emitDisconnect();
});

test("a dead channel fails pending work and reconnects exactly once",async()=>{
  const native=fakeNative(),bridge=new NativeBridge();native.first.failHello=false;
  await bridge.connect();
  const one=bridge.call("status"),two=bridge.call("memory.get",{storyId:"fixture"});
  const outcomes=Promise.allSettled([one,two]);
  await new Promise<void>(resolve=>setImmediate(resolve));native.first.emitDisconnect();
  assert((await outcomes).every(result=>result.status==="rejected"));
  await Promise.all([bridge.connect(),bridge.connect()]);
  assert.equal(native.connections(),2);
  native.second.emitDisconnect();
});

test("native errors retain a bounded code so stale-context UI can restore the source",async()=>{
  const native=fakeNative(),bridge=new NativeBridge();native.first.failHello=false;
  await bridge.connect();
  try{
    for(const [code,expected] of [["STALE_CONTEXT","STALE_CONTEXT"],["x".repeat(500),undefined]]){
      const request=bridge.call("pipeline",{},undefined,crypto.randomUUID());
      const outcome=request.then(()=>assert.fail("Expected native rejection"),error=>error);
      await new Promise<void>(resolve=>setImmediate(resolve));
      const sent=[...native.first.sent].reverse().find(message=>message.op==="pipeline");assert(sent);
      native.first.reply(sent.id,{ok:false,error:{code,message:"Ngữ cảnh vừa đổi."}});
      const error=await outcome;
      assert.equal(error.message,"Ngữ cảnh vừa đổi.");
      assert.equal(error.code,expected);
    }
  }finally{native.first.emitDisconnect();}
});

test("transport diagnostics never connect or expose the reader profile and ignore old failures",async()=>{
  const native=fakeNative(),bridge=new NativeBridge();native.first.failHello=false;
  assert.deepEqual(bridge.diagnostics(),{host:"vn.mangalive.companion",state:"disconnected",failure:"NONE",pendingCalls:0});
  assert.equal(native.connections(),0,"Inspection is not permission to open a native host");
  await bridge.connect();
  assert.equal(bridge.diagnostics().state,"ready");
  (chrome.runtime as any).lastError={message:"Specified native messaging host not found."};
  native.first.emitDisconnect();delete (chrome.runtime as any).lastError;
  assert.equal(bridge.diagnostics().failure,"NATIVE_HOST_NOT_FOUND");
  await bridge.connect();
  assert.equal(bridge.diagnostics().failure,"NONE");
  (chrome.runtime as any).lastError={message:"Specified native messaging host not found."};
  native.first.emitDisconnect();delete (chrome.runtime as any).lastError;
  assert.equal(bridge.diagnostics().state,"ready");
  assert.equal(bridge.diagnostics().failure,"NONE","Old port must not poison a recovered channel's diagnostics");
  native.second.emitDisconnect();
});
