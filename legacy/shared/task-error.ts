/** Preserve a safe native error classification across the MV3 relay. */
export class TaskError extends Error {
  readonly code?:string;
  constructor(message:string,code?:unknown){
    super(message);this.name="TaskError";
    if(typeof code==="string"&&/^[A-Z][A-Z0-9_]{0,63}$/.test(code))this.code=code;
  }
}

/** A generation ceiling is not evidence that the reader selected too much.
 * Override older host wording too; retain explicit retry without a paid loop.
 */
export function translationFailureNotice(error:unknown):string {
  const code=error instanceof TaskError?error.code:undefined;
  const reason=code==="TRUNCATED"
    ?"Model chưa hoàn tất bản dịch. Không thể kết luận vùng chọn quá lớn."
    :code==="MODEL_FORMAT"
    ?"Model trả sai định dạng bản dịch."
    :code==="MODEL_OUTPUT"
    ?"Model chưa giữ đúng cấu trúc, xưng hô hoặc nhịp thoại. Kiểm tra OCR hoặc đổi model."
    :code==="TERM_MISMATCH"
    ?"Model chưa giữ đúng tên đã khóa. Kiểm tra thuật ngữ hoặc đổi model."
    :String(error instanceof Error?error.message:error);
  return reason+" · Đã tạm dừng, không tự thử lại. Nguyên bản vẫn được giữ.";
}
