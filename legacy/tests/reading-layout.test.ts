import {test} from "node:test";
import assert from "node:assert/strict";
import {conflictedLetteringIds} from "../extension/reading-layout";

test("adjacent narrow columns with the reproduced source overlap use reading fallback",()=>{
  const regions=[{id:"r000",box:[720,61,42,119]}, {id:"r001",box:[698,62,39,153]},
    {id:"r003",box:[676,64,35,61]}, {id:"r004",box:[302,65,43,141]},
    {id:"r005",box:[279,66,42,169]}, {id:"balloon",box:[100,500,200,100]}];
  const before=structuredClone(regions);
  assert.deepEqual([...conflictedLetteringIds(regions)].sort(),["r000","r001","r003","r004","r005"]);
  assert.deepEqual(regions,before,"Planning cannot change source bounds or invent grouping/erasure");
});

test("touching boxes are not a conflict; all source IDs stay distinct",()=>{
  assert.equal(conflictedLetteringIds([{id:"a",box:[0,0,20,30]},{id:"b",box:[20,0,20,30]}]).size,0);
  assert.deepEqual([...conflictedLetteringIds([{id:"a",box:[0,0,20,30]},{id:"b",box:[19,0,20,30]}])].sort(),["a","b"]);
});

test("layout planner fails closed on duplicate or corrupt geometry",()=>{
  assert.throws(()=>conflictedLetteringIds([{id:"a",box:[0,0,20,30]},{id:"a",box:[50,0,20,30]}]));
  for(const value of [NaN,Infinity,-1,0])assert.throws(()=>conflictedLetteringIds([{id:"a",box:[0,0,value,30]}]));
});
