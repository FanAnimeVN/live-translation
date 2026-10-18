/** Width of `text` at `fontSize` in the target font (canvas measureText). */
export type Measure = (text: string, fontSize: number) => number;

export interface LayoutArea {
  x: number;
  y: number;
  w: number;
  h: number;
  /** Ellipse = rounded speech bubble; lines get narrower near top/bottom. */
  shape: "rect" | "ellipse";
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
      const widths = lineWidths(area, k, lh, o.padding);
      const lines = wrap(paragraphs, widths, size, measure);
      if (lines) return place(lines, area, size, lh, measure, false);
    }
  }
  // Nothing fits: smallest size, rectangular widths, report overflow honestly.
  const size = o.minSize;
  const lh = size * o.lineHeight;
  const widths = new Array(200).fill(area.w * (1 - o.padding));
  const lines = wrap(paragraphs, widths, size, measure, true) ?? [text];
  return place(lines, area, size, lh, measure, true);
}

function lineWidths(area: LayoutArea, k: number, lh: number, padding: number): number[] {
  const top0 = area.y + (area.h - k * lh) / 2;
  const out: number[] = [];
  for (let i = 0; i < k; i++) {
    const t = top0 + i * lh;
    const w = area.shape === "ellipse" ? Math.min(chord(area, t), chord(area, t + lh)) : area.w;
    out.push(Math.max(0, w * (1 - padding)));
  }
  return out;
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
  for (const words of paragraphs) {
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
        // A single word wider than the line: only allowed when forced.
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

function place(lines: string[], area: LayoutArea, size: number, lh: number, measure: Measure, overflow: boolean): TextLayout {
  const top0 = area.y + (area.h - lines.length * lh) / 2;
  return {
    fontSize: size,
    lineHeight: lh,
    overflow,
    lines: lines.map((text, i) => ({ text, cx: area.x + area.w / 2, top: top0 + i * lh, width: measure(text, size) })),
  };
}
