/** NFKC + whitespace removal, the comparison used for Japanese OCR CER. */
export const normalizeJa = (s: string) => s.normalize("NFKC").replace(/\s+/g, "");

export function levenshtein(a: string, b: string): number {
  const x = [...a];
  const y = [...b];
  if (!x.length) return y.length;
  if (!y.length) return x.length;
  let prev = Array.from({ length: y.length + 1 }, (_, j) => j);
  for (let i = 1; i <= x.length; i++) {
    const cur = [i];
    for (let j = 1; j <= y.length; j++) {
      cur[j] = Math.min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x[i - 1] === y[j - 1] ? 0 : 1));
    }
    prev = cur;
  }
  return prev[y.length];
}

/** Character error rate of `hyp` against `ref` after normalization. */
export function cer(hyp: string, ref: string): { edits: number; refLen: number; rate: number } {
  const h = normalizeJa(hyp);
  const r = normalizeJa(ref);
  const edits = levenshtein(h, r);
  const refLen = [...r].length;
  return { edits, refLen, rate: refLen ? edits / refLen : h ? 1 : 0 };
}

export function percentile(values: number[], p: number): number {
  if (!values.length) return NaN;
  const s = [...values].sort((a, b) => a - b);
  const k = (s.length - 1) * p;
  const lo = Math.floor(k);
  const hi = Math.ceil(k);
  return s[lo] + (s[hi] - s[lo]) * (k - lo);
}
