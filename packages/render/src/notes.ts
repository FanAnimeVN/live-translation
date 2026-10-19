import type { Box, Gutter } from "@lt/core";
import type { Ctx2D } from "./index";

/** One P/S to place: its text and the balloon of the line that refers back. */
export interface NoteInput {
  id: string;
  text: string;
  anchor: Box;
}

/**
 * Where a P/S goes. "inline": lettered in a gutter next to its balloon. "dot": a small
 * marker the reader taps to open the note (no gutter with room nearby). Never over art.
 */
export interface NotePlacement {
  id: string;
  text: string;
  mode: "inline" | "dot";
  /** Inline: the text block. Dot: the marker's square. */
  box: Box;
  fontSize: number;
  lines: string[];
  tone: Gutter["tone"];
}

export interface PlaceOptions {
  /** Boxes a note must not cover (text regions, their balloons). */
  avoid?: Box[];
  minFont?: number;
  maxFont?: number;
  /** Farthest a note may sit from its balloon, as a share of the page height. */
  maxDistance?: number;
}

const overlaps = (a: Box, b: Box) => a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h;
const gap = (a: Box, b: Box) => {
  const dx = Math.max(0, b.x - (a.x + a.w), a.x - (b.x + b.w));
  const dy = Math.max(0, b.y - (a.y + a.h), a.y - (b.y + b.h));
  return Math.hypot(dx, dy);
};

/** Greedy word wrap into at most `max` lines of width `w`, or null when it does not fit. */
function wrap(text: string, w: number, px: number, measure: (t: string, px: number) => number, max: number): string[] | null {
  const words = text.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let cur = "";
  for (const word of words) {
    const next = cur ? `${cur} ${word}` : word;
    if (measure(next, px) <= w) cur = next;
    else {
      if (!cur || measure(word, px) > w) return null;
      lines.push(cur);
      cur = word;
    }
  }
  if (cur) lines.push(cur);
  return lines.length <= max ? lines : null;
}

/**
 * Place each note in the nearest gutter that holds its text (one or two lines, 9–14 px),
 * centred on its balloon along the band and clear of every text region and earlier note.
 * Notes that find no room within `maxDistance` become dots by their balloon.
 */
export function placeNotes(
  notes: NoteInput[],
  gutters: Gutter[],
  measure: (text: string, px: number) => number,
  size: { w: number; h: number },
  opts: PlaceOptions = {},
): NotePlacement[] {
  // Readable once the page is scaled to the screen: about the size of small lettering.
  const minFont = opts.minFont ?? Math.max(9, Math.round(size.h / 120));
  const maxFont = opts.maxFont ?? Math.max(minFont + 2, Math.round(size.h / 75));
  const reach = (opts.maxDistance ?? 0.25) * size.h;
  const taken: Box[] = [...(opts.avoid ?? [])];
  const out: NotePlacement[] = [];
  for (const n of notes) {
    let best: { p: NotePlacement; d: number } | undefined;
    for (const g of gutters) {
      const pad = 2;
      const inner = { x: g.x + pad, y: g.y + pad, w: g.w - 2 * pad, h: g.h - 2 * pad };
      for (let px = maxFont; px >= minFont; px--) {
        const lh = Math.round(px * 1.2);
        const rows = Math.floor(inner.h / lh);
        if (rows < 1) continue;
        const lines = wrap(n.text, inner.w, px, measure, Math.min(2, rows));
        if (!lines) continue;
        const w = Math.ceil(Math.max(...lines.map((l) => measure(l, px)))) + 2;
        const h = lines.length * lh;
        // Centre on the balloon along the band, clamped inside it.
        const cx = n.anchor.x + n.anchor.w / 2;
        const cy = n.anchor.y + n.anchor.h / 2;
        const x = Math.max(inner.x, Math.min(inner.x + inner.w - w, cx - w / 2));
        const y = Math.max(inner.y, Math.min(inner.y + inner.h - h, cy - h / 2));
        const box = { x: Math.round(x), y: Math.round(y), w, h };
        if (taken.some((t) => overlaps(t, box))) break;
        const d = gap(n.anchor, box);
        if (d <= reach && (!best || d < best.d)) best = { p: { id: n.id, text: n.text, mode: "inline", box, fontSize: px, lines, tone: g.tone }, d };
        break;
      }
    }
    if (best) {
      taken.push(best.p.box);
      out.push(best.p);
      continue;
    }
    // A dot just outside the balloon's top-right corner (inside the page).
    const s = Math.max(14, Math.round(size.w / 60));
    const x = Math.min(size.w - s, Math.max(0, n.anchor.x + n.anchor.w - s / 2));
    const y = Math.min(size.h - s, Math.max(0, n.anchor.y - s / 2));
    out.push({ id: n.id, text: n.text, mode: "dot", box: { x, y, w: s, h: s }, fontSize: 0, lines: [], tone: "white" });
  }
  return out;
}

/** Letter the inline notes (dots are drawn by the viewer as tappable markers). */
export function drawNotes(ctx: Ctx2D, placements: NotePlacement[], fontFamily: string): void {
  ctx.save();
  for (const p of placements) {
    if (p.mode !== "inline") continue;
    const lh = Math.round(p.fontSize * 1.2);
    ctx.font = `italic ${p.fontSize}px ${fontFamily}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    ctx.fillStyle = p.tone === "black" ? "rgba(235,235,235,0.95)" : "rgba(40,40,40,0.9)";
    p.lines.forEach((l, i) => ctx.fillText(l, p.box.x + p.box.w / 2, p.box.y + i * lh + 1));
  }
  ctx.restore();
}
