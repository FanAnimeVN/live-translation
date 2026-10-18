import test from "node:test";
import assert from "node:assert/strict";
import {readContextPack,importContextPack} from "../shared/context-transfer";

const part=(facts:any[]=[],next:any=null,version=1)=>({schema:1,story:{id:"s",title:"Story",version},facts,
  summaries:[],snapshotVersion:version,snapshotId:"snapshot-"+version,next});

test("context pages retain all records and bind story/version",async()=>{
  let requests=0;
  const pack=await readContextPack(async(op,params)=>{
    assert.equal(op,"memory.export.page");assert.deepEqual(params.at,{chapter:20,page:0});requests++;
    return requests===1?part([{id:"one"}],{offset:1}):part([{id:"two"}]);
  },"s",{at:{chapter:20,page:0}});
  assert.equal(requests,2);assert.deepEqual(pack.facts.map(f=>f.id),["one","two"]);
  let count=0;
  await assert.rejects(()=>readContextPack(async()=>++count===1?part([{id:"one"}],{offset:1}):part([{id:"two"}],null,2),"s"),/vừa đổi/);
});

test("context reader rejects duplicate rows, cursor loops and wrong stories",async()=>{
  let count=0;
  await assert.rejects(()=>readContextPack(async()=>++count===1?part([{id:"one"}],{offset:1}):part([{id:"one"}]),"s"),/trùng/);
  await assert.rejects(()=>readContextPack(async()=>({...part(),story:{id:"other",title:"Other"}}),"s"),/không hợp lệ/);
  count=0;
  await assert.rejects(()=>readContextPack(async()=>part([{id:String(count++)}],{offset:1}),"s"),/bị lặp/);
});

test("context pages preserve resume progress and reject a moving reading snapshot",async()=>{
  const progress={last_chapter:20,last_page:3,furthest_chapter:100};let count=0;
  const pack=await readContextPack(async()=>({...part(),progress}),"s");
  assert.deepEqual(pack.progress,progress);
  await assert.rejects(()=>readContextPack(async()=>({...part([{id:String(count)}],++count===1?{offset:1}:null),
    snapshotId:count===1?"before-read":"after-read"}),"s"),/vừa đổi/);
});

test("changing selected story aborts before accepting its delayed reply",async()=>{
  const controller=new AbortController();let requests=0;
  await assert.rejects(()=>readContextPack(async()=>{requests++;controller.abort();return part();},"s",{signal:controller.signal}),
    error=>error instanceof Error&&error.name==="AbortError");
  assert.equal(requests,1);
});

test("large UTF-8 imports fit native frames, hash exact bytes and preserve offsets",async()=>{
  const source={schema:1,story:{id:"s",title:"Nhật Việt"},facts:[{value:"日本語 và tiếng Việt ".repeat(40000)}],summaries:[]};
  const bytes=new TextEncoder().encode(JSON.stringify(source));const chunks:Uint8Array[]=[];let metadata:any,offset=0;
  const result=await importContextPack(async(op,params)=>{
    assert(new TextEncoder().encode(JSON.stringify({op,params})).length<200000);
    if(op==="context.begin")metadata=params;
    if(op==="context.chunk"){
      assert.equal(params.offset,offset);const chunk=Uint8Array.from(atob(params.data as string),c=>c.charCodeAt(0));
      chunks.push(chunk);offset+=chunk.length;
    }
    return op==="context.commit"?{storyId:"s"}:{};
  },source);
  assert.equal(result.storyId,"s");assert.equal(metadata.bytes,bytes.length);assert.equal(offset,bytes.length);
  const expected=Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256",bytes)),b=>b.toString(16).padStart(2,"0")).join("");
  assert.equal(metadata.sha256,expected);
  assert.deepEqual(Buffer.concat(chunks.map(chunk=>Buffer.from(chunk))),Buffer.from(bytes));
});

test("failed context import releases its in-RAM reservation",async()=>{
  const calls:string[]=[];
  await assert.rejects(()=>importContextPack(async(op)=>{calls.push(op);if(op==="context.chunk")throw new Error("interrupted");return {};},{x:"small"}),/interrupted/);
  assert.deepEqual(calls,["context.begin","context.chunk","context.cancel"]);
});
