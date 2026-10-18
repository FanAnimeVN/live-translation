import test from "node:test";
import assert from "node:assert/strict";
import {checkedNativeDiagnostics,loadNativeDiagnostics,nativeBrowser,nativeFailure} from "../shared/native-diagnostics";
const fixture=()=>({v:1,browser:"edge",host:"vn.mangalive.companion",state:"disconnected",failure:"NATIVE_HOST_NOT_FOUND",
  pendingCalls:0,extensionId:"a".repeat(32),manifestBuild:"0.1.0-dev.test"});

test("diagnostic serialization discards all fields outside the public transport allowlist",()=>{
  const clean=fixture();
  assert.deepEqual(checkedNativeDiagnostics({...clean,profileId:"private-profile",keys:{key:"private-key"},
    story:"private-story",url:"https://private.invalid/",prompt:"private-prompt"}),clean);
});
test("malformed or unbounded service-worker metadata is not shown as a valid diagnostic",()=>{
  for(const value of [null,{}, {...fixture(),extensionId:"invalid"},{...fixture(),host:"../host"},
    {...fixture(),failure:"private error"},{...fixture(),manifestBuild:"<script>"},
    {...fixture(),pendingCalls:NaN},{...fixture(),pendingCalls:-1},{...fixture(),pendingCalls:1025}])
    assert.throws(()=>checkedNativeDiagnostics(value),/tương thích/);
});
test("browser identification is a label, never proof of native registration",()=>{
  assert.equal(nativeBrowser("Chrome/155.0.0.0 Safari/537.36 Edg/155.0.0.0"),"edge");
  assert.equal(nativeBrowser("Chrome/155.0.0.0 Safari/537.36"),"chrome");
  assert.equal(nativeBrowser("Chrome/155.0.0.0 OPR/100.0"),"other");
  assert.equal(nativeBrowser("unknown"),"other");
  assert.equal(nativeFailure("Specified native messaging host not found."),"NATIVE_HOST_NOT_FOUND");
  assert.equal(nativeFailure("Private provider error or content"),"NATIVE_DISCONNECTED");
});
test("diagnostics timeout never retry or apply an expired reply",async()=>{
  let calls=0,finish!:(v:unknown)=>void;
  const result=loadNativeDiagnostics(()=>{calls++;return new Promise(resolve=>{finish=resolve;});},5);
  await assert.rejects(result,/sau 5 giây/);
  finish(fixture());await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(calls,1);
});
