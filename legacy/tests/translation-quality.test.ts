import test from "node:test";
import assert from "node:assert/strict";
import {repeatedNameWord} from "../extension/translation-quality";

test("repeated syllable is a naming advisory, never an automatic edit",()=>{
  const name="Băng Kết Kết Giới";
  assert.equal(repeatedNameWord(name),"Kết");
  assert.equal(name,"Băng Kết Kết Giới");
  assert.equal(repeatedNameWord("Băng kết KẾT giới"),"kết");
  assert.equal(repeatedNameWord("Kết giới băng giá"),undefined);
  assert.equal(repeatedNameWord("Băng kết giới"),undefined);
  assert.equal(repeatedNameWord("Kết giới · Kết băng"),undefined);
  assert.equal(repeatedNameWord("A A 11 11"),undefined);
});
