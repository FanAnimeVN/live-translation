import type { Box } from "./types";
import type { RGBAImage } from "./erase";

/** A blank band between panels (or a page margin): somewhere a note can go without covering art. */
export interface Gutter extends Box {
  /** "h" runs across the page (between panel rows); "v" splits a row of panels. */
  dir: "h" | "v";
  /** Paper of the band: white gutters, or the black gutters of dark scenes and flashbacks. */
  tone: "white" | "black";
}

export interface GutterOptions {
  /** Thinnest band kept, px (default: 0.6% of the page height, at least 6). */
  minThickness?: number;
  /** Share of a row/column that must be blank paper (default 0.985: specks and screentone dots break nothing). */
  blankShare?: number;
  /** Levels of the recursive XY cut (default 3: rows → panels in a row → rows inside a column). */
  depth?: number;
}

const WHITE = 1;
const BLACK = 2;

/**
 * Blank bands between panels, found with projection profiles in a recursive XY cut:
 * rows that are (almost) all white or all black across the area form horizontal bands;
 * the strips between them are cut by columns the same way, and so on. Panel borders stop
 * a band, so the inside of a framed panel never counts as a gutter. Slanted gutters are
 * not found (the caller falls back to a marker).
 */
export function findGutters(img: RGBAImage, opts: GutterOptions = {}): Gutter[] {
  const { width: W, height: H, data } = img;
  const minT = opts.minThickness ?? Math.max(6, Math.round(H * 0.006));
  const share = opts.blankShare ?? 0.985;
  const cls = new Uint8Array(W * H);
  for (let i = 0, p = 0; i < cls.length; i++, p += 4) {
    const r = data[p];
    const g = data[p + 1];
    const b = data[p + 2];
    const hi = Math.max(r, g, b);
    const lo = Math.min(r, g, b);
    if (lo >= 225 && hi - lo < 30) cls[i] = WHITE;
    else if (hi <= 40) cls[i] = BLACK;
  }
  const out: Gutter[] = [];
  const cut = (a: Box, dir: "h" | "v", depth: number) => {
    const len = dir === "h" ? a.h : a.w;
    const span = dir === "h" ? a.w : a.h;
    if (len < minT || span < minT) return;
    // Per row (dir h) or column (dir v): which tone, if any, fills it. Isolated specks are
    // tolerated; a line crossing it (a panel border, 2 px or more) is not.
    const tone = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      let w = 0;
      let k = 0;
      let runW = 0;
      let runK = 0;
      let crossW = false;
      let crossK = false;
      for (let j = 0; j < span; j++) {
        const x = dir === "h" ? a.x + j : a.x + i;
        const y = dir === "h" ? a.y + i : a.y + j;
        const c = cls[y * W + x];
        if (c === WHITE) w++;
        else if (c === BLACK) k++;
        runW = c === WHITE ? 0 : runW + 1;
        runK = c === BLACK ? 0 : runK + 1;
        if (runW >= 2) crossW = true;
        if (runK >= 2) crossK = true;
      }
      tone[i] = !crossW && w >= share * span ? WHITE : !crossK && k >= share * span ? BLACK : 0;
    }
    // A blank band far thicker than a gutter, away from the page edge, is an empty panel or
    // sky, not the space between panels.
    const full = dir === "h" ? H : W;
    const segments: Array<[number, number]> = [];
    for (let i = 0; i < len; ) {
      let j = i + 1;
      while (j < len && tone[j] === tone[i]) j++;
      const atEdge = (dir === "h" ? a.y : a.x) + i === 0 || (dir === "h" ? a.y : a.x) + j === full;
      // [i, j) is one run: a band when blank, thick enough and not too thick.
      if (tone[i] && j - i >= minT && (atEdge || j - i <= Math.max(0.08 * full, 4 * minT))) {
        const band: Box = dir === "h" ? { x: a.x, y: a.y + i, w: a.w, h: j - i } : { x: a.x + i, y: a.y, w: j - i, h: a.h };
        out.push({ ...band, dir, tone: tone[i] === WHITE ? "white" : "black" });
        segments.push([i, j]);
      }
      i = j;
    }
    if (depth <= 1) return;
    // Cut what lies between the bands the other way.
    let from = 0;
    for (const [s, e] of [...segments, [len, len] as [number, number]]) {
      if (s - from >= minT * 4) {
        const part: Box = dir === "h" ? { x: a.x, y: a.y + from, w: a.w, h: s - from } : { x: a.x + from, y: a.y, w: s - from, h: a.h };
        cut(part, dir === "h" ? "v" : "h", depth - 1);
      }
      from = e;
    }
  };
  cut({ x: 0, y: 0, w: W, h: H }, "h", opts.depth ?? 3);
  return out;
}
