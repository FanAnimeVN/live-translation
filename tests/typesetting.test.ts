import {test} from "node:test";
import assert from "node:assert/strict";
import {fitLettering} from "../extension/typesetting";

const measure=(value:string,size:number)=>[...value].length*size*0.48;
test("lettering balances lines without dropping or changing Vietnamese words",()=>{
  const source="Nee-chan, chưa về à? Em vẫn đang chờ ở đây.";
  const result=fitLettering(source,180,120,measure);
  assert.equal(result.lines.join(" "),source);
  assert.equal(result.overflow,false);
  assert(result.lines.length>1);
  assert(result.lines.every(line=>measure(line,result.fontSize)<=174));
  assert(result.lines.length*result.lineHeight<=114);
});
test("explicit paragraph boundaries and honorific tokens are retained",()=>{
  const source="Asura-san!\nEm sẽ đợi chị ở đây.";
  const result=fitLettering(source,200,140,measure);
  assert.equal(result.lines[0],"Asura-san!");
  assert.equal(result.lines.slice(1).join(" "),"Em sẽ đợi chị ở đây.");
});
test("tiny balloons keep a readable floor and report overflow, not microscopic type",()=>{
  const result=fitLettering("Chúng ta không thể rời khỏi kết giới này khi chưa tìm được lối ra.",55,15,measure);
  assert.equal(result.fontSize,11);
  assert.equal(result.overflow,true);
  assert.equal(result.lines.join(" "),"Chúng ta không thể rời khỏi kết giới này khi chưa tìm được lối ra.");
});
test("long unbroken words and non-finite geometry are bounded",()=>{
  assert.equal(fitLettering("Asura-sama-very-long-name",25,60,measure).overflow,true);
  assert.equal(fitLettering("Cảm ơn.",NaN,100,measure).overflow,true);
  assert.equal(fitLettering("",100,100,measure).lines.length,0);
});
test("source font size is preferred, not forced to a fixed 24px",()=>{
  const large=fitLettering("Đi thôi!",300,180,measure,40);
  assert.equal(large.fontSize,40);
  const compact=fitLettering("Em sẽ về trước và đợi chị ở nhà.",100,55,measure,40);
  assert(compact.fontSize<40&&compact.fontSize>=11);
  assert.equal(compact.lines.join(" "),"Em sẽ về trước và đợi chị ở nhà.");
});

test("deliberate slow-speech gaps are not collapsed by fitting",()=>{
  const source="Tôi…   yêu…   em.";
  const result=fitLettering(source,360,160,measure);
  assert.equal(result.lines.join(" "),source);
  assert.equal(result.overflow,false);
});

test("a spelled Vietnamese word remains a readable unit at a physical line break",()=>{
  const result=fitLettering("Là T Ô I!",83,100,measure);
  assert.equal(result.lines.join(" "),"Là T Ô I!");
  assert(result.lines.some(line=>line.includes("T Ô I!")));
  assert.equal(result.overflow,false);
});

test("confirmed spelling intent also keeps two-letter units and uppercase accents",()=>{
  const source="E M   Y Ê U   A N H";
  const result=fitLettering(source,240,90,measure,24,{spelled:true});
  assert.equal(result.lines.join(" "),source);
  assert.equal(result.overflow,false);
  assert.equal(fitLettering("DỪNG LẠI!",180,90,measure).lines.join(" "),"DỪNG LẠI!");
});

test("stutters, stretched vowels and intentional breaks survive fit and overflow",()=>{
  const source="Đ-đợi…\nTô-i…   đââây!";
  const result=fitLettering(source,60,20,measure);
  assert(result.lines.includes("Đ-đợi…")&&result.lines.includes("Tô-i…   đââây!"));
  assert.equal(result.fontSize,11);
  assert.equal(result.overflow,true);
});
