import test from "node:test";
import assert from "node:assert/strict";
import {checkedStatus,loadStatus} from "../extension/companion-status";

function fixture(){return {version:"0.1.0",settings:{mode:"byok",provider:"openrouter",detector:"paddle",threads:4,
  cloudConsent:false,metadataConsent:false,autoSummary:false,artCleanup:false,
  deepseekModel:"deepseek-flash",geminiModel:"gemini-test",openrouterModel:"test"},
  models:{ocr:true},keys:{openrouter:false},stories:[{id:"story",title:"Reader story",version:1}],engineWarm:false};}

test("status preserves reader settings and does not infer consent or offline defaults",()=>{
  const value=fixture();assert.equal(checkedStatus(value),value);
  assert.equal(checkedStatus(value).settings.artCleanup,false);
  assert.equal(checkedStatus(value).settings.cloudConsent,false);
});
test("runtime package identity is optional for legacy hosts and strictly bounded when supplied",()=>{
  assert.equal(checkedStatus(fixture()).runtimeBuild,undefined);
  const runtimeBuild="pkg-sha256:"+"a".repeat(64);
  assert.equal(checkedStatus({...fixture(),runtimeBuild}).runtimeBuild,runtimeBuild);
  for(const value of [null,7,"", "private source text",runtimeBuild+"extra",runtimeBuild+"\n", "pkg-sha256:"+"A".repeat(64)])
    assert.throws(()=>checkedStatus({...fixture(),runtimeBuild:value}),/không tương thích/);
});
test("malformed native status cannot become an empty connected library",()=>{
  const valid=fixture();
  for(const value of [undefined,null,{}, {version:"old",stories:[]}, {...valid,settings:null},
    {...valid,stories:null},{...valid,stories:[{}]},{...valid,keys:[]},{...valid,models:{ocr:"yes"}},
    {...valid,settings:{...valid.settings,mode:"other"}},{...valid,cloudModels:{}},
    {...valid,cloudModels:[{provider:"openrouter"}]}]){
    assert.throws(()=>checkedStatus(value),/không tương thích/);
  }
});
test("translation scheduling version is optional for old hosts and remains typed",()=>{
  assert.equal(checkedStatus(fixture()).scheduleVersion,undefined);
  assert.equal(checkedStatus({...fixture(),scheduleVersion:"translation-schedule-v1-seam-neighbours"}).scheduleVersion,
    "translation-schedule-v1-seam-neighbours");
  assert.throws(()=>checkedStatus({...fixture(),scheduleVersion:42}),/không tương thích/);
});
test("presentation provenance is independent and optional for legacy companions",()=>{
  assert.equal(checkedStatus(fixture()).presentationVersion,undefined);
  assert.equal(checkedStatus({...fixture(),presentationVersion:"balloon-mask-v21-actual-source-support"}).presentationVersion,
    "balloon-mask-v21-actual-source-support");
  assert.throws(()=>checkedStatus({...fixture(),presentationVersion:42}),/không tương thích/);
});
test("summary capability is versioned and never inferred from model settings",()=>{
  assert.equal(checkedStatus(fixture()).summaryVersion,undefined);
  assert.equal(checkedStatus({...fixture(),summaryVersion:"read-evidence-cloud-v1"}).summaryVersion,"read-evidence-cloud-v1");
  for(const fields of [{summaryVersion:1},{settings:{...fixture().settings,summaryBackend:"wiki"}},
    {settings:{...fixture().settings,summaryCloudConsent:"yes"}},{summaryUsage:[{costUsd:-1}]},{summaryUsageUnavailable:"yes"}])
    assert.throws(()=>checkedStatus({...fixture(),...fields}),/không tương thích/);
});
test("status request is bounded, does not retry, and ignores a late reply",async()=>{
  let finish!:(value:unknown)=>void;let calls=0;
  const pending=new Promise(resolve=>{finish=resolve;});
  const result=loadStatus(()=>{calls++;return pending;},5);
  await assert.rejects(result,/Chưa nhận được phản hồi/);
  finish(fixture());await new Promise(resolve=>setTimeout(resolve,0));
  assert.equal(calls,1);
});
test("failed status can be retried explicitly without another operation",async()=>{
  let calls=0;
  await assert.rejects(loadStatus(async()=>{calls++;throw new Error("native unavailable");}),/native unavailable/);
  const expected=fixture();assert.equal(await loadStatus(async()=>{calls++;return expected;}),expected);
  assert.equal(calls,2);
});
