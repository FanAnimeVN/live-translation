import { clampBox, expand } from "./geometry";
import { isLineLike, type RGBAImage } from "./erase";
import type { Box } from "./types";

export interface InpaintJob {
  /** Crop of the page sent to the inpainter (context around the text). */
  crop: Box;
  /** Crop-local hole mask, 1 = pixel to reconstruct. */
  hole: Uint8Array;
  /** Hole pixels / member-box pixels. */
  coverage: number;
  /** True when no glyph strokes could be isolated and the whole text box is the hole. */
  rect: boolean;
  /** Page-space bounds of the glyph strokes found (the text's real footprint), when any. */
  extent?: Box;
}

/** Ink must be this much darker (or lighter) than the local background; faint parts half as much. */
const STRONG = 55;
const FAINT = 25;

/**
 * Hole mask for text drawn over artwork. Glyph strokes are the pixels much darker
 * (or lighter, for white text on dark art) than the local background, measured over
 * a window about one character wide, so grey screentone or a tinted panel does not
 * swallow the text. Only glyph-like components count (see `textStrokes`): hair, panel
 * borders, speed lines, eyes and filled shapes stay out of the hole. The mask grows a
 * few pixels to take antialiasing and halos with it. When no glyphs can be isolated, or
 * `rect` is set, the whole text box becomes the hole except protected art: the text is
 * always redrawn, an eye inside the box never is.
 */
export function artTextMask(img: RGBAImage, members: Box[], opts: { charSize?: number; rect?: boolean } = {}): InpaintJob {
  const bounds = { w: img.width, h: img.height };
  const u = union(members);
  const margin = Math.min(160, Math.max(24, Math.round(0.5 * Math.max(u.w, u.h))));
  const c = roundBox(clampBox(expand(u, margin), bounds.w, bounds.h));
  const W = c.w;
  const lum = luminance(img, c);
  const cs0 = opts.charSize ?? Math.max(10, Math.min(...members.map((m) => Math.min(m.w, m.h))) * 0.8);
  const hole = new Uint8Array(W * c.h);
  let boxPixels = 0;
  let rect = !!opts.rect;
  let ex0 = Infinity, ey0 = Infinity, ex1 = -Infinity, ey1 = -Infinity;
  for (const m of members) {
    // Glyphs often poke slightly out of a tight detector box: search a little wider.
    const reach = Math.max(2, Math.round(cs0 * 0.35));
    const b = local(roundBox(clampBox(intersectBox(expand(m, reach), c), bounds.w, bounds.h)), c);
    boxPixels += b.w * b.h;
    const dark = textStrokes(lum, W, c.h, b, cs0, true);
    const light = coverageIn(dark, b) < 0.02 ? textStrokes(lum, W, c.h, b, cs0, false) : undefined;
    const st = light && coverageIn(light, b) > coverageIn(dark, b) ? light : dark;
    // Filled shapes found by either pass are art, whichever pass found the text.
    const protect = new Uint8Array(W * c.h);
    for (const pass of [dark, light]) {
      if (!pass) continue;
      const g = dilate(pass.blob, pass.win.w, pass.win.h, 1);
      for (let y = 0; y < pass.win.h; y++) for (let x = 0; x < pass.win.w; x++) if (g[y * pass.win.w + x]) protect[(pass.win.y + y) * W + (pass.win.x + x)] = 1;
    }
    if (rect || coverageIn(st, b) < 0.02) {
      rect = true;
      const r = local(roundBox(clampBox(intersectBox(expand(m, 3), c), bounds.w, bounds.h)), c);
      for (let y = r.y; y < r.y + r.h; y++) for (let x = r.x; x < r.x + r.w; x++) if (!protect[y * W + x]) hole[y * W + x] = 1;
      continue;
    }
    const grown = dilate(st.glyph, st.win.w, st.win.h, 3);
    for (let y = 0; y < st.win.h; y++)
      for (let x = 0; x < st.win.w; x++) {
        const q = y * st.win.w + x;
        const pc = (st.win.y + y) * W + (st.win.x + x);
        if (grown[q] && !protect[pc]) hole[pc] = 1;
        if (st.glyph[q]) {
          ex0 = Math.min(ex0, st.win.x + x);
          ey0 = Math.min(ey0, st.win.y + y);
          ex1 = Math.max(ex1, st.win.x + x);
          ey1 = Math.max(ey1, st.win.y + y);
        }
      }
  }
  let holes = 0;
  for (const v of hole) holes += v;
  const extent = !rect && ex1 >= ex0 ? { x: c.x + ex0, y: c.y + ey0, w: ex1 - ex0 + 1, h: ey1 - ey0 + 1 } : undefined;
  return { crop: c, hole, coverage: boxPixels ? holes / boxPixels : 0, rect, extent };
}

/**
 * Share of each text box's core (outer 12% trimmed) covered by glyph-sized ink after
 * erasure or inpainting. Art lines, eyes and big shapes do not count, so a high value
 * means Japanese is still there and must not be lettered over.
 */
export function glyphResidue(img: RGBAImage, members: Box[], charSize?: number): number {
  let ink = 0;
  let n = 0;
  for (const m of members) {
    const core = roundBox(clampBox({ x: m.x + m.w * 0.12, y: m.y + m.h * 0.12, w: m.w * 0.76, h: m.h * 0.76 }, img.width, img.height));
    if (core.w < 3 || core.h < 3) continue;
    const cs = charSize ?? Math.max(10, Math.min(m.w, m.h) * 0.8);
    const r = Math.max(6, Math.round(cs * 0.9));
    const c = roundBox(clampBox(expand(core, r), img.width, img.height));
    const lum = luminance(img, c);
    const b = local(core, c);
    const st = textStrokes(lum, c.w, c.h, b, cs, true);
    for (let y = 0; y < st.win.h; y++)
      for (let x = 0; x < st.win.w; x++) if (st.glyph[y * st.win.w + x] && inside(b, st.win.x + x, st.win.y + y)) ink++;
    n += core.w * core.h;
  }
  return n ? ink / n : 0;
}

interface Strokes {
  /** Window (crop-local) the masks cover: the search box plus about a character around it. */
  win: Box;
  glyph: Uint8Array;
  /** Filled shapes (eyes, pupils, solid areas) inside the search box: never part of a hole. */
  blob: Uint8Array;
}

/**
 * Text strokes for one search box `b` of a luminance crop. Components are traced on the
 * faint mask (hysteresis) over a window about a character wider than the box, so art
 * that merely crosses the box is seen whole. A glyph component lies almost entirely
 * inside the box, carries strong ink, has a glyph-like size, is not a hair-thin long
 * line, and its thickest point is not much thicker than the pen stroke of the other
 * glyphs: an eye next to small handwriting is a filled blob, not a letter.
 * The character size is re-estimated from the glyphs themselves when the caller's
 * guess (box area / character count) is far too large, as it is for loose boxes.
 */
function textStrokes(lum: Float32Array, W: number, H: number, b: Box, charSize: number, dark: boolean, calibrated = false): Strokes {
  const ext = Math.max(6, Math.round(charSize));
  const win = intersectBox({ x: b.x - ext, y: b.y - ext, w: b.w + 2 * ext, h: b.h + 2 * ext }, { x: 0, y: 0, w: W, h: H });
  const w = win.w;
  const h = win.h;
  const mean = boxMeanOf(lum, W, win, Math.max(6, Math.round(charSize * 0.9)));
  const faint = new Uint8Array(w * h);
  const strong = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const v = lum[(win.y + y) * W + (win.x + x)];
      const d = dark ? mean[y * w + x] - v : v - mean[y * w + x];
      if (d > FAINT) faint[y * w + x] = 1;
      if (d > STRONG) strong[y * w + x] = 1;
    }
  }
  const depth = chamfer(strong, w, h);
  const inBoxLocal = { x: b.x - win.x, y: b.y - win.y, w: b.w, h: b.h };
  // Touching glyphs in one column/line form elongated components: thin across the
  // text direction, a few characters long. Hair and art masses are wide in both.
  const maxThin = charSize * 1.6;
  const maxLong = charSize * 4.5;
  const maxArea = charSize * charSize * 3;
  const minArea = Math.max(6, charSize * charSize * 0.006);
  const cands: Array<{ px: number[]; cw: number; ch: number; core: number }> = [];
  const seen = new Uint8Array(w * h);
  const stack: number[] = [];
  for (let s = 0; s < faint.length; s++) {
    if (!faint[s] || seen[s]) continue;
    const comp: number[] = [];
    seen[s] = 1;
    stack.push(s);
    let minX = w, minY = h, maxX = 0, maxY = 0, hasStrong = false, inBox = 0, core = 0;
    while (stack.length) {
      const p = stack.pop()!;
      comp.push(p);
      if (strong[p]) {
        hasStrong = true;
        if (depth[p] > core) core = depth[p];
      }
      const x = p % w;
      const y = (p - x) / w;
      if (inside(inBoxLocal, x, y)) inBox++;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      if (x > 0 && faint[p - 1] && !seen[p - 1]) { seen[p - 1] = 1; stack.push(p - 1); }
      if (x < w - 1 && faint[p + 1] && !seen[p + 1]) { seen[p + 1] = 1; stack.push(p + 1); }
      if (y > 0 && faint[p - w] && !seen[p - w]) { seen[p - w] = 1; stack.push(p - w); }
      if (y < h - 1 && faint[p + w] && !seen[p + w]) { seen[p + w] = 1; stack.push(p + w); }
    }
    if (inBox === 0) continue;
    const cw = maxX - minX + 1;
    const ch = maxY - minY + 1;
    const glyphLike =
      hasStrong &&
      inBox >= 0.8 * comp.length &&
      comp.length >= minArea &&
      comp.length <= maxArea &&
      Math.min(cw, ch) <= maxThin &&
      Math.max(cw, ch) <= maxLong &&
      !isLineLike(cw, ch, comp.length, charSize);
    if (glyphLike) cands.push({ px: comp, cw, ch, core: core / 3 });
  }
  // A loose box (text beside a character's face) inflates the size guess: re-estimate
  // it from the components' cross-section and trace again with tighter limits.
  if (!calibrated && cands.length >= 3) {
    const est = quantile(cands.map((k) => Math.min(k.cw, k.ch)), 0.75) * 1.15;
    if (est < 0.65 * charSize) return textStrokes(lum, W, H, b, Math.max(6, est), dark, true);
  }
  const pen = cands.length >= 3 ? quantile(cands.map((k) => k.core), 0.5) : 0;
  const blobAt = Math.max(2.5, 0.2 * charSize, 1.8 * pen);
  const glyph = new Uint8Array(w * h);
  const blob = new Uint8Array(w * h);
  for (const k of cands) {
    const target = k.core > blobAt ? blob : glyph;
    for (const p of k.px) target[p] = 1;
  }
  return { win, glyph, blob };
}

/** Chamfer (3-4) distance from each set pixel to the nearest unset pixel, in thirds of a pixel. */
function chamfer(mask: Uint8Array, w: number, h: number): Uint16Array {
  const d = new Uint16Array(w * h);
  for (let i = 0; i < d.length; i++) d[i] = mask[i] ? 60000 : 0;
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const p = y * w + x;
      if (!d[p]) continue;
      d[p] = Math.min(
        d[p],
        x > 0 ? d[p - 1] + 3 : 3,
        y > 0 ? d[p - w] + 3 : 3,
        x > 0 && y > 0 ? d[p - w - 1] + 4 : 4,
        x < w - 1 && y > 0 ? d[p - w + 1] + 4 : 4,
      );
    }
  for (let y = h - 1; y >= 0; y--)
    for (let x = w - 1; x >= 0; x--) {
      const p = y * w + x;
      if (!d[p]) continue;
      d[p] = Math.min(
        d[p],
        x < w - 1 ? d[p + 1] + 3 : 3,
        y < h - 1 ? d[p + w] + 3 : 3,
        x < w - 1 && y < h - 1 ? d[p + w + 1] + 4 : 4,
        x > 0 && y < h - 1 ? d[p + w - 1] + 4 : 4,
      );
    }
  return d;
}

function quantile(v: number[], q: number): number {
  const s = [...v].sort((a, b) => a - b);
  return s[Math.min(s.length - 1, Math.floor(q * s.length))] ?? 0;
}

const inside = (b: Box, x: number, y: number) => x >= b.x && y >= b.y && x < b.x + b.w && y < b.y + b.h;
const local = (b: Box, c: Box): Box => ({ x: b.x - c.x, y: b.y - c.y, w: b.w, h: b.h });

/** Glyph pixels inside box `b` (crop-local) over the box area. */
function coverageIn(st: Strokes, b: Box): number {
  let n = 0;
  for (let y = 0; y < st.win.h; y++) for (let x = 0; x < st.win.w; x++) if (st.glyph[y * st.win.w + x] && inside(b, st.win.x + x, st.win.y + y)) n++;
  return b.w * b.h ? n / (b.w * b.h) : 0;
}

/** Box mean of a window of the crop, so a stroke is compared with its own surroundings. */
function boxMeanOf(lum: Float32Array, W: number, win: Box, r: number): Float32Array {
  const sub = new Float32Array(win.w * win.h);
  for (let y = 0; y < win.h; y++) for (let x = 0; x < win.w; x++) sub[y * win.w + x] = lum[(win.y + y) * W + (win.x + x)];
  return boxMean(sub, win.w, win.h, r);
}

function luminance(img: RGBAImage, c: Box): Float32Array {
  const lum = new Float32Array(c.w * c.h);
  for (let y = 0; y < c.h; y++) {
    for (let x = 0; x < c.w; x++) {
      const i = ((c.y + y) * img.width + (c.x + x)) * 4;
      lum[y * c.w + x] = 0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2];
    }
  }
  return lum;
}

function union(boxes: Box[]): Box {
  return boxes.reduce((a, m) => ({
    x: Math.min(a.x, m.x),
    y: Math.min(a.y, m.y),
    w: Math.max(a.x + a.w, m.x + m.w) - Math.min(a.x, m.x),
    h: Math.max(a.y + a.h, m.y + m.h) - Math.min(a.y, m.y),
  }));
}

function intersectBox(a: Box, b: Box): Box {
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  const x2 = Math.min(a.x + a.w, b.x + b.w);
  const y2 = Math.min(a.y + a.h, b.y + b.h);
  return { x: x1, y: y1, w: Math.max(1, x2 - x1), h: Math.max(1, y2 - y1) };
}

function roundBox(b: Box): Box {
  const x = Math.floor(b.x);
  const y = Math.floor(b.y);
  return { x, y, w: Math.max(1, Math.ceil(b.x + b.w) - x), h: Math.max(1, Math.ceil(b.y + b.h) - y) };
}

function boxMean(v: Float32Array, w: number, h: number, r: number): Float32Array {
  const integral = new Float64Array((w + 1) * (h + 1));
  for (let y = 0; y < h; y++) {
    let row = 0;
    for (let x = 0; x < w; x++) {
      row += v[y * w + x];
      integral[(y + 1) * (w + 1) + x + 1] = integral[y * (w + 1) + x + 1] + row;
    }
  }
  const out = new Float32Array(w * h);
  for (let y = 0; y < h; y++) {
    const y1 = Math.max(0, y - r);
    const y2 = Math.min(h, y + r + 1);
    for (let x = 0; x < w; x++) {
      const x1 = Math.max(0, x - r);
      const x2 = Math.min(w, x + r + 1);
      const s = integral[y2 * (w + 1) + x2] - integral[y1 * (w + 1) + x2] - integral[y2 * (w + 1) + x1] + integral[y1 * (w + 1) + x1];
      out[y * w + x] = s / ((x2 - x1) * (y2 - y1));
    }
  }
  return out;
}

function dilate(mask: Uint8Array, w: number, h: number, r: number): Uint8Array {
  const out = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (!mask[y * w + x]) continue;
      for (let yy = Math.max(0, y - r); yy <= Math.min(h - 1, y + r); yy++) {
        out.fill(1, yy * w + Math.max(0, x - r), yy * w + Math.min(w - 1, x + r) + 1);
      }
    }
  }
  return out;
}

/**
 * Does a reconstructed patch blend in? A hole filled with flat tone inside busy
 * artwork (hatching, speed lines, screentone) reads as a visible patch. Used to pick
 * the better of two reconstructions, never to leave text un-redrawn.
 */
export function patchBlends(original: RGBAImage, result: Uint8Array, job: InpaintJob): { ok: boolean; score: number; holeStd: number; ringStd: number } {
  const { crop, hole } = job;
  const W = crop.w;
  const H = crop.h;
  const n = W * H;
  const ring = dilate(hole, W, H, 6);
  const hv: number[] = [];
  const rv: number[] = [];
  for (let p = 0; p < n; p++) {
    if (hole[p]) hv.push(0.299 * result[p] + 0.587 * result[n + p] + 0.114 * result[2 * n + p]);
    else if (ring[p]) {
      const x = p % W;
      const y = (p - x) / W;
      const i = ((crop.y + y) * original.width + (crop.x + x)) * 4;
      rv.push(0.299 * original.data[i] + 0.587 * original.data[i + 1] + 0.114 * original.data[i + 2]);
    }
  }
  const std = (v: number[]) => {
    if (!v.length) return 0;
    const m = v.reduce((a, b) => a + b, 0) / v.length;
    return Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / v.length);
  };
  const holeStd = std(hv);
  const ringStd = std(rv);
  const score = ringStd > 0 ? Math.min(1, holeStd / ringStd) : 1;
  return { ok: !(ringStd > 30 && holeStd < 0.45 * ringStd), score, holeStd, ringStd };
}
