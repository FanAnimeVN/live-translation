import test from "node:test";
import assert from "node:assert/strict";
import {TaskError,translationFailureNotice} from "../shared/task-error";

test("a short generation failure never blames selection size, even with an old host message",()=>{
  for(const code of ["TRUNCATED","MODEL_FORMAT","MODEL_OUTPUT","TERM_MISMATCH"]){
    const notice=translationFailureNotice(new TaskError("Bản dịch quá dài. Hãy chọn vùng nhỏ hơn.",code));
    assert.doesNotMatch(notice,/quá dài|vùng nhỏ hơn|chọn vùng khác/i);
    assert.match(notice,/model/i);assert.match(notice,/không tự thử lại/i);
  }
});

test("failure notices keep specific safe recovery and never claim automatic cloud fallback",()=>{
  const notice=translationFailureNotice(new TaskError("Hết hạn mức API.","QUOTA"));
  assert.match(notice,/Hết hạn mức API/);assert.match(notice,/không tự thử lại/i);
  assert.doesNotMatch(notice,/chọn vùng khác|đã chuyển cloud/i);
});
