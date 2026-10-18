import {test} from "node:test";
import assert from "node:assert/strict";
import {findLetteringBoxOverlaps} from "../scripts/lettering-overlap-check.mjs";

test("lettering overlap flags the exact IDs/geometry without modifying source",()=>{
  const items=[{id:"right",rect:{x:12,y:10,width:20,height:70}},
    {id:"left",rect:{x:0,y:0,width:20,height:100}},{id:"other",rect:{x:80,y:0,width:20,height:20}}];
  const before=structuredClone(items);
  assert.deepEqual(findLetteringBoxOverlaps(items),[{ids:["right","left"],width:8,height:70,minBoxFraction:.4}]);
  assert.deepEqual(items,before);
});

test("touching/rounding edges are not lettering overlap",()=>{
  const a={id:"a",rect:{x:0,y:0,width:20,height:20}};
  assert.deepEqual(findLetteringBoxOverlaps([a,{id:"b",rect:{x:20,y:0,width:20,height:20}}]),[]);
  assert.deepEqual(findLetteringBoxOverlaps([a,{id:"b",rect:{x:19.5,y:0,width:20,height:20}}]),[]);
  assert.equal(findLetteringBoxOverlaps([a,{id:"b",rect:{x:19,y:0,width:20,height:20}}]).length,1);
});

test("lettering diagnostics reject corrupt/duplicate geometry rather than pass",()=>{
  const a={id:"a",rect:{x:0,y:0,width:20,height:20}};
  assert.throws(()=>findLetteringBoxOverlaps([a,a]));
  for(const value of [NaN,Infinity,-1,0])assert.throws(()=>findLetteringBoxOverlaps([{...a,rect:{...a.rect,width:value}}]));
  assert.throws(()=>findLetteringBoxOverlaps([a],-1));
});
