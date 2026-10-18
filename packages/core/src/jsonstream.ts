/**
 * Incremental extractor of top-level JSON objects from a streamed model reply.
 * Works for JSON Lines, pretty-printed objects, arrays of objects and replies
 * wrapped in markdown fences; text outside objects is ignored.
 */
export class JsonObjectStream {
  private buf = "";
  private pos = 0;
  private depth = 0;
  private inString = false;
  private escaped = false;
  private start = -1;

  constructor(
    private readonly onObject: (value: unknown, raw: string) => void,
    private readonly onInvalid?: (raw: string) => void,
  ) {}

  push(chunk: string): void {
    this.buf += chunk;
    for (; this.pos < this.buf.length; this.pos++) {
      const c = this.buf[this.pos];
      if (this.inString) {
        if (this.escaped) this.escaped = false;
        else if (c === "\\") this.escaped = true;
        else if (c === '"') this.inString = false;
        continue;
      }
      if (c === '"') {
        if (this.depth > 0) this.inString = true;
      } else if (c === "{") {
        if (this.depth === 0) this.start = this.pos;
        this.depth++;
      } else if (c === "}" && this.depth > 0) {
        this.depth--;
        if (this.depth === 0) this.emit(this.buf.slice(this.start, this.pos + 1));
      }
    }
    if (this.depth === 0) {
      this.buf = "";
      this.pos = 0;
      this.start = -1;
    } else if (this.start > 0) {
      this.buf = this.buf.slice(this.start);
      this.pos -= this.start;
      this.start = 0;
    }
  }

  /** Text still inside an unterminated object (e.g. the reply was truncated). */
  get pending(): string {
    return this.depth > 0 ? this.buf.slice(Math.max(0, this.start)) : "";
  }

  private emit(raw: string): void {
    try {
      this.onObject(JSON.parse(raw), raw);
    } catch {
      this.onInvalid?.(raw);
    }
  }
}
