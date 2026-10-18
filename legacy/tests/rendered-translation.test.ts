import test from "node:test";
import assert from "node:assert/strict";
import {assertLetteredText,assertRenderedTranslations,hasClassToken} from "../scripts/rendered-translation-check.mjs";

test("native browser QA finds the reader toolbar after automatic compaction",()=>{
  assert(hasClassToken("bar","bar"));assert(hasClassToken("bar compact","bar"));
  assert(!hasClassToken("toolbar compact","bar"));assert(!hasClassToken(undefined,"bar"));
});

test("real reader lettering may insert soft wraps, not lose source words",()=>{
  assertLetteredText("Ta không có ý định","Ta\nkhông\ncó ý\nđịnh");
  assertLetteredText("A, trùm hoang đang quay về...","A, trùm hoang\nđang quay về...");
});
test("QA rejects missing, duplicated, added or changed letters and punctuation",()=>{
  for(const rendered of ["Ta không có","Ta không không có ý định","Ta không có ý định!","Ta không có ý định thôi"])
    assert.throws(()=>assertLetteredText("Ta không có ý định",rendered));
  assert.throws(()=>assertLetteredText("Chờ...","Chờ.."));
  assert.throws(()=>assertLetteredText("DỪNG LẠI!","Dừng lại!"));
});
test("QA preserves explicit paragraphs and deliberate wide pacing gaps",()=>{
  assertLetteredText("Đợi...\nTôi...   về đây!","Đợi...\nTôi...   về\nđây!");
  assert.throws(()=>assertLetteredText("Đợi...\nTôi...","Đợi... Tôi..."));
  assert.throws(()=>assertLetteredText("Tôi...   yêu...","Tôi...\nyêu..."));
  assert.throws(()=>assertLetteredText("Tôi...\u00a0yêu...","Tôi...\nyêu..."));
  assert.throws(()=>assertLetteredText("Tôi...\tyêu...","Tôi...\nyêu..."));
});
test("QA does not accept line breaks inside deliberately spelled units",()=>{
  assertLetteredText("Là T Ô I!","Là\nT Ô I!");
  assert.throws(()=>assertLetteredText("Là T Ô I!","Là T\nÔ I!"));
  assert.throws(()=>assertLetteredText("E M","E\nM",true));
  assertLetteredText("Là E M","Là\nE M",true);
});
test("QA matches every region ID, independent of DOM order and equal text",()=>{
  const regions=[{id:"a",vi:"Đợi thôi."},{id:"b",vi:"Đợi thôi."}];
  const node=(id:string,text="Đợi\nthôi.")=>({id,text,ariaLabel:"Xem và sửa bản dịch: Đợi thôi."});
  assertRenderedTranslations(regions,[node("b"),node("a")]);
  assert.throws(()=>assertRenderedTranslations(regions,[node("a"),node("a")]));
  assert.throws(()=>assertRenderedTranslations(regions,[node("a"),node("stale")]));
  assert.throws(()=>assertRenderedTranslations(regions,[node("a")]));
  assert.throws(()=>assertRenderedTranslations(regions,[node("a"),node("b","Đợi")]));
});
test("QA rejects stale accessible text and preserves deferred exclusions",()=>{
  assert.throws(()=>assertRenderedTranslations([{id:"a",vi:"Đợi thôi."}],
    [{id:"a",text:"Đợi thôi.",ariaLabel:"Xem và sửa bản dịch: Bản cũ."}]));
  assertRenderedTranslations([{id:"a",vi:"Đợi.",scope:{action:"defer"}}],[]);
  assert.throws(()=>assertRenderedTranslations([{id:"a",vi:"Đợi.",scope:{action:"defer"}}],
    [{id:"a",text:"Đợi.",ariaLabel:"Xem và sửa bản dịch: Đợi."}]));
});
