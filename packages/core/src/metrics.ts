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

/** Character n-gram counts for chrF (n = 1..6), whitespace ignored, case-folded. */
export interface ChrfStats {
  match: number[];
  hyp: number[];
  ref: number[];
}

export function chrfStats(hyp: string, ref: string, maxN = 6): ChrfStats {
  const prep = (s: string) => [...s.normalize("NFC").toLowerCase().replace(/\s+/g, "")];
  const h = prep(hyp);
  const r = prep(ref);
  const out: ChrfStats = { match: [], hyp: [], ref: [] };
  for (let n = 1; n <= maxN; n++) {
    const grams = (cs: string[]) => {
      const m = new Map<string, number>();
      for (let i = 0; i + n <= cs.length; i++) {
        const g = cs.slice(i, i + n).join("");
        m.set(g, (m.get(g) ?? 0) + 1);
      }
      return m;
    };
    const gh = grams(h);
    const gr = grams(r);
    let match = 0;
    for (const [g, c] of gh) match += Math.min(c, gr.get(g) ?? 0);
    out.match.push(match);
    out.hyp.push(Math.max(0, h.length - n + 1));
    out.ref.push(Math.max(0, r.length - n + 1));
  }
  return out;
}

/**
 * Corpus chrF (Popović 2015, beta = 2) from per-segment statistics, 0..100. Character
 * n-grams suit Vietnamese diacritics and short dialogue better than word BLEU; it rewards
 * closeness to one reference, so it ranks systems, it does not judge a single line.
 */
export function chrfScore(stats: ChrfStats[], beta = 2): number {
  if (!stats.length) return 0;
  const N = stats[0].match.length;
  let p = 0;
  let r = 0;
  let k = 0;
  for (let n = 0; n < N; n++) {
    const m = stats.reduce((a, s) => a + s.match[n], 0);
    const h = stats.reduce((a, s) => a + s.hyp[n], 0);
    const f = stats.reduce((a, s) => a + s.ref[n], 0);
    if (!h && !f) continue;
    p += h ? m / h : 0;
    r += f ? m / f : 0;
    k++;
  }
  if (!k) return 0;
  p /= k;
  r /= k;
  const b2 = beta * beta;
  return p + r ? (100 * (1 + b2) * p * r) / (b2 * p + r) : 0;
}

export function percentile(values: number[], p: number): number {
  if (!values.length) return NaN;
  const s = [...values].sort((a, b) => a - b);
  const k = (s.length - 1) * p;
  const lo = Math.floor(k);
  const hi = Math.ceil(k);
  return s[lo] + (s[hi] - s[lo]) * (k - lo);
}
