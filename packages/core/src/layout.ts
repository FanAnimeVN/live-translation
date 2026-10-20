/** Width of `text` at `fontSize` in the target font (canvas measureText). */
export type Measure = (text: string, fontSize: number) => number;

export interface LayoutArea {
  x: number;
  y: number;
  w: number;
  h: number;
  /** Ellipse = rounded speech bubble; mask = real balloon interior given by `spans`. */
  shape: "rect" | "ellipse" | "mask";
  /** For shape "mask": usable [x0, x1] per pixel row from `y` (null = no room), page coordinates. */
  spans?: Array<[number, number] | null>;
}

export interface LaidLine {
  text: string;
  /** Horizontal center of the line. */
  cx: number;
  /** Top of the line box. */
  top: number;
  width: number;
}

export interface TextLayout {
  fontSize: number;
  lineHeight: number;
  lines: LaidLine[];
  overflow: boolean;
}

export interface LayoutOptions {
  maxSize: number;
  minSize: number;
  lineHeight: number;
  /** Fraction of each line width kept free as padding. */
  padding: number;
}

const DEFAULTS: LayoutOptions = { maxSize: 30, minSize: 9, lineHeight: 1.16, padding: 0.08 };

/**
 * Fit Vietnamese text into a bubble: largest font size whose greedy line breaking
 * fits the shape (ellipse chords shrink near the top and bottom), lines centered.
 */
export function layoutText(text: string, area: LayoutArea, measure: Measure, opts: Partial<LayoutOptions> = {}): TextLayout {
  const o = { ...DEFAULTS, ...opts };
  const paragraphs = text
    .replace(/\r\n?/g, "\n")
    .split("\n")
    .map((p) => p.trim().split(/ +/).filter(Boolean));
  if (!paragraphs.some((p) => p.length)) return { fontSize: o.minSize, lineHeight: o.minSize * o.lineHeight, lines: [], overflow: false };

  for (let size = Math.floor(o.maxSize); size >= o.minSize; size--) {
    const lh = size * o.lineHeight;
    const maxLines = Math.floor(area.h / lh);
    for (let k = 1; k <= maxLines; k++) {
      const slots = lineSlots(area, k, lh, o.padding);
      const lines = wrap(paragraphs, slots.map((s) => s.width), size, measure);
      if (lines) return place(lines, area, size, lh, measure, false, o.padding);
    }
  }
  // Nothing fits: smallest size, rectangular widths, report overflow honestly.
  const size = o.minSize;
  const lh = size * o.lineHeight;
  const widths = new Array(200).fill(area.w * (1 - o.padding));
  const lines = wrap(paragraphs, widths, size, measure, true) ?? [text];
  return place(lines, area, size, lh, measure, true, o.padding);
}

interface Slot {
  width: number;
  cx: number;
}

/** Width and centre available to each of k lines stacked in the middle of the area. */
function lineSlots(area: LayoutArea, k: number, lh: number, padding: number): Slot[] {
  const top0 = area.y + (area.h - k * lh) / 2;
  const out: Slot[] = [];
  for (let i = 0; i < k; i++) {
    const t = top0 + i * lh;
    if (area.shape === "mask" && area.spans) {
      const band = spanBand(area, t, t + lh);
      const width = band ? band[1] - band[0] : 0;
      out.push({ width: Math.max(0, width - Math.max(3, width * padding)), cx: band ? (band[0] + band[1]) / 2 : area.x + area.w / 2 });
      continue;
    }
    const w = area.shape === "ellipse" ? Math.min(chord(area, t), chord(area, t + lh)) : area.w;
    out.push({ width: Math.max(0, w * (1 - padding)), cx: area.x + area.w / 2 });
  }
  return out;
}

/** Horizontal span free on every pixel row of [y0, y1) (intersection of row spans). */
function spanBand(area: LayoutArea, y0: number, y1: number): [number, number] | null {
  const spans = area.spans!;
  let x0 = -Infinity;
  let x1 = Infinity;
  for (let y = Math.floor(y0); y < Math.ceil(y1); y++) {
    const s = spans[y - Math.floor(area.y)];
    if (!s) return null;
    x0 = Math.max(x0, s[0]);
    x1 = Math.min(x1, s[1]);
    if (x1 <= x0) return null;
  }
  return Number.isFinite(x0) ? [x0, x1] : null;
}

function chord(area: LayoutArea, y: number): number {
  const b = area.h / 2;
  const dy = y - (area.y + b);
  if (Math.abs(dy) >= b) return 0;
  return area.w * Math.sqrt(1 - (dy / b) ** 2);
}

/** Greedy wrap into exactly widths.length lines at most; null if it does not fit. */
function wrap(paragraphs: string[][], widths: number[], size: number, measure: Measure, force = false): string[] | null {
  const lines: string[] = [];
  let li = 0;
  for (const source of paragraphs) {
    const words = [...source];
    let line = "";
    for (let wi = 0; wi < words.length; wi++) {
      const word = words[wi];
      const cand = line ? `${line} ${word}` : word;
      const limit = widths[li] ?? 0;
      if (measure(cand, size) <= limit) {
        line = cand;
        continue;
      }
      if (!line) {
        // A single word wider than the line: break it after a hyphen when a part fits (a name
        // with its honorific, "Moriguo-|kuuun!"); otherwise only allowed when forced.
        const cut = hyphenCut(word, limit, size, measure);
        if (cut) {
          lines.push(cut[0]);
          li++;
          words.splice(wi + 1, 0, cut[1]);
          if (li >= widths.length) return force ? [...lines, words.slice(wi + 1).join(" ")] : null;
          continue;
        }
        if (!force) return null;
        lines.push(word);
        li++;
        continue;
      }
      lines.push(line);
      li++;
      if (li >= widths.length) return force ? [...lines, words.slice(wi).join(" ")] : null;
      line = "";
      wi--;
    }
    if (line || !words.length) {
      lines.push(line);
      li++;
    }
    if (li > widths.length && !force) return null;
  }
  return lines.length <= widths.length || force ? lines : null;
}

/** The longest head of `word` ending in a hyphen that fits `limit`, and the rest; null if none. */
function hyphenCut(word: string, limit: number, size: number, measure: Measure): [string, string] | null {
  for (let i = word.length - 2; i > 0; i--) {
    if (word[i] !== "-") continue;
    const head = word.slice(0, i + 1);
    if (measure(head, size) <= limit) return [head, word.slice(i + 1)];
  }
  return null;
}

function place(lines: string[], area: LayoutArea, size: number, lh: number, measure: Measure, overflow: boolean, padding: number): TextLayout {
  const top0 = area.y + (area.h - lines.length * lh) / 2;
  const slots = overflow ? undefined : lineSlots(area, lines.length, lh, padding);
  return {
    fontSize: size,
    lineHeight: lh,
    overflow,
    lines: lines.map((text, i) => ({ text, cx: slots?.[i]?.cx ?? area.x + area.w / 2, top: top0 + i * lh, width: measure(text, size) })),
  };
}

/**
 * Row spans of a balloon interior mask, trimmed by `inset` pixels, for shape-aware
 * lettering. Each row keeps the run around `centerX` so a neighbouring lobe or a
 * tail does not widen a line.
 */
export function spansFromMask(
  m: { x: number; y: number; w: number; h: number; mask: Uint8Array },
  inset: number,
  centerX: number,
): Array<[number, number] | null> {
  const out: Array<[number, number] | null> = [];
  const cx = Math.max(0, Math.min(m.w - 1, Math.round(centerX - m.x)));
  for (let y = 0; y < m.h; y++) {
    const row = y * m.w;
    let x = cx;
    if (!m.mask[row + x]) {
      let best = -1;
      for (let d = 1; d < m.w && best < 0; d++) {
        if (x - d >= 0 && m.mask[row + x - d]) best = x - d;
        else if (x + d < m.w && m.mask[row + x + d]) best = x + d;
      }
      if (best < 0) {
        out.push(null);
        continue;
      }
      x = best;
    }
    let l = x;
    let r = x;
    while (l > 0 && m.mask[row + l - 1]) l--;
    while (r < m.w - 1 && m.mask[row + r + 1]) r++;
    const x0 = m.x + l + inset;
    const x1 = m.x + r + 1 - inset;
    out.push(x1 - x0 > 2 ? [x0, x1] : null);
  }
  // Keep text off the top and bottom outline as well.
  let first = out.findIndex((v) => v);
  let last = out.length - 1 - [...out].reverse().findIndex((v) => v);
  for (let i = 0; first >= 0 && i < inset; i++) {
    if (first + i < out.length) out[first + i] = null;
    if (last - i >= 0) out[last - i] = null;
  }
  return out;
}
