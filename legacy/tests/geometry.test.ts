import {test} from "node:test";
import assert from "node:assert/strict";
import {fittedImage,regionBox,intersect} from "../extension/geometry";

test("object-fit and object-position map source pixels without assuming centered contain",()=>{
  const box={x:10,y:20,width:400,height:400};
  assert.deepEqual(fittedImage(box,800,400,"contain","0% 100%"),{x:10,y:220,width:400,height:200});
  assert.deepEqual(fittedImage(box,800,400,"cover","50% 50%"),{x:-190,y:20,width:800,height:400});
  assert.deepEqual(regionBox([80,40,160,80],{x:10,y:-300,width:400,height:200},800,400),
    {x:50,y:-280,width:80,height:40});
  assert.deepEqual(intersect({x:-20,y:10,width:80,height:80},{x:0,y:0,width:100,height:100}),
    {x:0,y:10,width:60,height:80});
});
