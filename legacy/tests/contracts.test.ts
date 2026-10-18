import test from "node:test";
import assert from "node:assert/strict";
import {inferChapter,readerConfigSchema,regionSchema,renderPatchSchema,latestFactsAt,expressionSchema,scopeSchema} from "../shared/contracts";
test("chapter hints still require reader confirmation",()=>{
  assert.equal(inferChapter("https://demo/chapter-100.5"),100.5);
  assert.equal(inferChapter("第23話"),23);
  assert.equal(inferChapter("Manga without a chapter"),undefined);
});
test("reject invalid coordinates/identities before displaying overlay",()=>{
  assert.equal(regionSchema.safeParse({id:"r",bbox:[0,0,-5,40],ja:"hello"}).success,false);
  assert.equal(readerConfigSchema.safeParse({storyId:"../escape",title:"test",at:{chapter:1,page:0}}).success,false);
});
test("fragmented layout keeps its review reason across native-to-renderer validation",()=>{
  const region={id:"r",bbox:[10,20,30,40],ja:"テスト",review:true,reviewReasons:["layout_fragment"]};
  assert(regionSchema.safeParse(region).success);
  assert(!regionSchema.safeParse({...region,reviewReasons:["arbitrary skip"]}).success);
});
test("parent OCR framing reaches the renderer without becoming artwork-erasure authority",()=>{
  const evidence={source_ids:["right","left"],reason:"group_parent_longitudinal_frame",orientation:"vertical",
    parent_source_bbox:[40,40,62,165],parent_inference_crop:[40,40,62,165],
    source_members_preserved:true,erasure_permitted:false};
  const region={id:"right",bbox:[80,40,22,120],ocrCropBox:[80,40,22,165],ja:"テスト",overlay:"label",
    review:true,reviewReasons:["layout_fragment","ocr_crop_partition"],ocrPartition:[evidence]};
  assert(regionSchema.safeParse(region).success,"The native frame evidence must survive the actual rendering contract");
});

test("unreadable OCR reaches recovery UI without becoming plot memory",()=>{
  const region={id:"source-unreadable",bbox:[10,20,30,40],ja:"",review:true,reviewReasons:["ocr_empty"],
    scope:{v:1,key:"captured-source",group:"captured-source",role:"unknown",action:"defer",reason:"visual_review",memory:false}};
  assert(regionSchema.safeParse(region).success);
  assert(!regionSchema.safeParse({...region,scope:{...region.scope,action:"translate",reason:"unclassified",memory:true}}).success);
});
test("unverified legacy speaker binding is review metadata, not a guessed identity",()=>{
  const region={id:"r",bbox:[10,20,30,40],ja:"テスト",speaker:"unknown",listener:"unknown",speakerBindingReview:true};
  assert.equal(regionSchema.parse(region).speakerBindingReview,true);
  assert(!regionSchema.safeParse({...region,speakerBindingReview:"apply old speaker"}).success);
});
test("bare multi-line OCR clusters keep review without inventing balloon ownership",()=>{
  const region={id:"r",bbox:[10,20,50,140],ja:"テスト",overlay:"label",review:true,reviewReasons:["layout_cluster"]};
  const parsed=regionSchema.parse(region);
  assert.equal(parsed.balloon,undefined);
  assert.deepEqual(parsed.reviewReasons,["layout_cluster"]);
});
test("expression metadata is versioned and bounded, never a provider instruction",()=>{
  const value={v:1,sourceHash:"a".repeat(64),cues:["spelled","uppercase"]};
  assert.equal(expressionSchema.safeParse(value).success,true);
  for(const invalid of [{...value,v:0},{...value,sourceHash:"fake"},{...value,cues:["shouting"]},
    {...value,cues:Array(7).fill("spelled")},{...value,command:"send image"}])
    assert.equal(expressionSchema.safeParse(invalid).success,false);
});
test("deferred secondary text has a bounded recoverable role and cannot enter plot memory",()=>{
  const value={v:1,key:"scope-a",group:"scope-b",role:"editorial",action:"defer",reason:"editorial_marker",memory:false};
  assert(scopeSchema.safeParse(value).success);
  assert(scopeSchema.safeParse({...value,action:"translate",reason:"reader"}).success);
  assert(!scopeSchema.safeParse({...value,memory:true}).success);
  assert(!scopeSchema.safeParse({...value,action:"translate",memory:true}).success);
  assert(!scopeSchema.safeParse({...value,command:"crawl"}).success);
  assert(!scopeSchema.safeParse({...value,key:"../other"}).success);
});
test("weak visual source remains translatable but cannot assert plot-memory trust",()=>{
  const scope={v:1,key:"scope-weak",group:"scope-weak",role:"unknown",action:"translate",reason:"visual_review",memory:false};
  for(const reason of ["visual_low_signal","visual_punctuation_support","cloud_ocr_uncertain","cloud_page_proposal"]){
  assert(regionSchema.safeParse({id:"r",bbox:[0,0,23,22],ja:"魔法団",vi:"Ma pháp đoàn",
    review:true,reviewReasons:[reason],scope}).success);
  assert(!scopeSchema.safeParse({...scope,memory:true}).success);
  assert(!regionSchema.safeParse({id:"r",bbox:[0,0,23,22],ja:"魔法団",reviewReasons:[reason],
    scope:{...scope,reason:"unclassified",memory:true}}).success);
  assert(scopeSchema.safeParse({...scope,reason:"reader",role:"dialogue",memory:true}).success);
  }
});
test("library shows latest temporal reader revisions without future or duplicate locks",()=>{
  const records=[
    {kind:"glossary",key:"weapon",chapter:1,page:0,value:"old"},
    {kind:"glossary",key:"weapon",chapter:1,page:0,value:"corrected"},
    {kind:"relationship",key:"weapon",chapter:1,page:0,value:"separate kind"},
    {kind:"glossary",key:"weapon",chapter:80,page:0,value:"future name"}];
  const before=JSON.stringify(records),visible=latestFactsAt(records,{chapter:20,page:1});
  assert.equal(visible.length,2);
  assert.equal(visible.find(v=>v.kind==="glossary")?.value,"corrected");
  assert.equal(JSON.stringify(records),before,"Do not mutate canonical export order");
});
test("transient cleanup accepts only bounded PNG patches, never external URLs or oversized art",()=>{
  const value={revision:"rev",width:800,height:1050,patch:{regionId:"r",bbox:[20,30,100,40],
    dataUrl:"data:image/png;base64,YQ==",ink:"#111111",stroke:"#ffffff",sourceFontPx:28,method:"opencv-telea-v1"}};
  assert.equal(renderPatchSchema.safeParse(value).success,true);
  for(const dataUrl of ["https://example.com/tracker.png","data:image/svg+xml;base64,YQ==","data:image/png;base64,A","data:image/png;base64,"+"a".repeat(512*1024+1)])
    assert.equal(renderPatchSchema.safeParse({...value,patch:{...value.patch,dataUrl}}).success,false);
  assert.equal(renderPatchSchema.safeParse({...value,patch:{...value.patch,bbox:[750,30,100,40]}}).success,false);
  assert.equal(renderPatchSchema.safeParse({...value,patch:{...value.patch,bbox:[0,0,800,500]}}).success,false);
});
