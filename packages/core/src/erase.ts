import { clampBox, expand } from "./geometry";
import type { Box } from "./types";

/** Minimal RGBA image (browser ImageData and @napi-rs/canvas ImageData both fit). */
export interface RGBAImage {
  width: number;
  height: number;
  data: Uint8ClampedArray;
}

export type RGB = [number, number, number];

export interface EraseReport {
  /** box: whole text box repainted (plain bubble). glyph: only glyph strokes repainted. inpaint: art reconstructed by a model. */
  mode: "box" | "glyph" | "inpaint" | "skipped";
  bg: RGB;
  ink: RGB;
  /** Share of non-ink border samples close to the background colour (1 = perfectly flat). */
  flatness: number;
  /** Share of border samples that are ink (art lines, outlines, glyphs crossing the edge). */
  inkShare: number;
  /** Share of mid-tone pixels inside the text box: grey fills, screentone, painted art. */
  midShare: number;
  erasedPixels: number;
  /** Balloon interior found by flood fill (1 = inside), for shape-aware lettering. */
  interior?: InteriorMask;
}

export interface InteriorMask {
  x: number;
  y: number;
  w: number;
  h: number;
  mask: Uint8Array;
}

/** Pixel classes inside a box relative to the background colour. */
export function toneShares(img: RGBAImage, box: Box, bg: RGB): { mid: number; ink: number } {
  const b = clampBox(box, img.width, img.height);
  let mid = 0;
  let ink = 0;
  let n = 0;
  for (let y = Math.floor(b.y); y < Math.floor(b.y + b.h); y++) {
    for (let x = Math.floor(b.x); x < Math.floor(b.x + b.w); x++) {
      const d = dist(img.data, (y * img.width + x) * 4, bg);
      n++;
      if (d > INK_DISTANCE) ink++;
      else if (d > FLAT_DISTANCE) mid++;
    }
  }
  return { mid: n ? mid / n : 0, ink: n ? ink / n : 0 };
}

const FLAT_DISTANCE = 28;
const INK_DISTANCE = 70;
const FAINT_DISTANCE = 35;
const MIN_FLATNESS = 0.82;

const dist = (d: Uint8ClampedArray, i: number, c: RGB) =>
  Math.max(Math.abs(d[i] - c[0]), Math.abs(d[i + 1] - c[1]), Math.abs(d[i + 2] - c[2]));

/**
 * Background colour and flatness from a thin band just inside `box`. Ink pixels
 * (glyphs crossing the edge, panel borders, line art) are excluded from flatness:
 * a background is "flat" when the remaining pixels are almost all paper colour,
 * while screentone and painted art produce many mid tones.
 */
export function sampleBorder(img: RGBAImage, box: Box, band = 2): { bg: RGB; flatness: number; inkShare: number } {
  const b = clampBox(box, img.width, img.height);
  const rs: number[] = [];
  const gs: number[] = [];
  const bs: number[] = [];
  const idx: number[] = [];
  const x2 = Math.floor(b.x + b.w) - 1;
  const y2 = Math.floor(b.y + b.h) - 1;
  for (let y = Math.floor(b.y); y <= y2; y++) {
    for (let x = Math.floor(b.x); x <= x2; x++) {
      const edge = x - b.x < band || y - b.y < band || x2 - x < band || y2 - y < band;
      if (!edge) continue;
      const i = (y * img.width + x) * 4;
      rs.push(img.data[i]);
      gs.push(img.data[i + 1]);
      bs.push(img.data[i + 2]);
      idx.push(i);
    }
  }
  if (!idx.length) return { bg: [255, 255, 255], flatness: 0, inkShare: 0 };
  const bg: RGB = [median(rs), median(gs), median(bs)];
  let close = 0;
  let ink = 0;
  for (const i of idx) {
    const d = dist(img.data, i, bg);
    if (d > INK_DISTANCE) ink++;
    else if (d <= FLAT_DISTANCE) close++;
  }
  const nonInk = idx.length - ink;
  return { bg, flatness: nonInk ? close / nonInk : 0, inkShare: ink / idx.length };
}

/**
 * The paper colour of a balloon or caption box: the most common light tone in its inner
 * area. Undefined when no light tone dominates (a toned or dark balloon), so the caller
 * falls back to sampling around the text.
 */
export function dominantPaper(img: RGBAImage, box: Box): RGB | undefined {
  const b = clampBox({ x: box.x + box.w * 0.1, y: box.y + box.h * 0.1, w: box.w * 0.8, h: box.h * 0.8 }, img.width, img.height);
  const bins = new Array(32).fill(0);
  const sums = Array.from({ length: 32 }, () => [0, 0, 0]);
  let n = 0;
  for (let y = Math.floor(b.y); y < Math.floor(b.y + b.h); y++) {
    for (let x = Math.floor(b.x); x < Math.floor(b.x + b.w); x++) {
      const i = (y * img.width + x) * 4;
      const l = 0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2];
      const k = Math.min(31, Math.floor(l / 8));
      bins[k]++;
      sums[k][0] += img.data[i];
      sums[k][1] += img.data[i + 1];
      sums[k][2] += img.data[i + 2];
      n++;
    }
  }
  if (!n) return undefined;
  let best = -1;
  for (let k = 20; k < 32; k++) if (best < 0 || bins[k] > bins[best]) best = k; // light tones only (lum >= 160)
  // The bin and its neighbours must cover a good part of the box: paper, not a highlight.
  const share = (bins[best] + (bins[best - 1] ?? 0) + (bins[best + 1] ?? 0)) / n;
  if (share < 0.35) return undefined;
  return [Math.round(sums[best][0] / bins[best]), Math.round(sums[best][1] / bins[best]), Math.round(sums[best][2] / bins[best])];
}

/**
 * Erase the text of one region in place when its background is flat paper or a
 * plain bubble. In a bubble the whole text box is repainted (except protected
 * outlines); free text near art only has its glyph strokes repainted, so line art
 * inside the box survives. Textured backgrounds are skipped: the caller keeps the
 * original art and offers the translation on demand.
 */
export function eraseRegion(
  img: RGBAImage,
  members: Box[],
  opts: { bubble?: Box; mode?: "auto" | "glyph"; maxMid?: number; charSize?: number } = {},
): EraseReport {
  const bounds = { w: img.width, h: img.height };
  const union = members.reduce((u, m) => ({
    x: Math.min(u.x, m.x),
    y: Math.min(u.y, m.y),
    w: Math.max(u.x + u.w, m.x + m.w) - Math.min(u.x, m.x),
    h: Math.max(u.y + u.h, m.y + m.h) - Math.min(u.y, m.y),
  }));
  // A balloon or caption box is erased by filling its interior, with the paper colour
  // that dominates inside it. Sampling around the text box instead can land on the
  // box's own border when the text fills it, which would skip a plain caption box.
  if (opts.bubble && opts.mode !== "glyph") {
    const paper = dominantPaper(img, opts.bubble);
    const interior = paper && bubbleInterior(img, opts.bubble, paper);
    if (paper && interior) {
      return { mode: "box", bg: paper, ink: interior.inkSamples ?? guessInk(paper), flatness: 1, inkShare: 0, midShare: 0, erasedPixels: interior.erased, interior: interior.interior };
    }
  }
  let probe = expand(union, 4, bounds);
  if (opts.bubble) probe = clampBox(intersectOr(probe, opts.bubble), img.width, img.height);
  const { bg, flatness, inkShare } = sampleBorder(img, probe);
  const midShare = toneShares(img, union, bg).mid;
  if (flatness < MIN_FLATNESS || inkShare > 0.45 || midShare > (opts.maxMid ?? 1)) {
    return { mode: "skipped", bg, ink: guessInk(bg), flatness, inkShare, midShare, erasedPixels: 0 };
  }
  // Repaint the whole box only inside a plain bubble; any line work around the text
  // (speed lines, hatching inside a burst balloon) keeps glyph-only erasure.
  const mode: EraseReport["mode"] = opts.bubble && opts.mode !== "glyph" && inkShare < 0.08 && midShare < 0.06 ? "box" : "glyph";

  // Inside a balloon, repaint its interior found by flood fill: the outline and
  // everything outside it (speed lines in the box corners, tails, art) stay intact.
  if (opts.bubble && opts.mode !== "glyph") {
    const interior = bubbleInterior(img, opts.bubble, bg);
    if (interior) {
      const ink = interior.inkSamples;
      return { mode: "box", bg, ink: ink ?? guessInk(bg), flatness, inkShare, midShare, erasedPixels: interior.erased, interior: interior.interior };
    }
  }

  // Snapshot so an erasure that would leave a visible flat patch can be undone.
  const snap = clampBox(expand(union, 3, bounds), img.width, img.height);
  const sx = Math.floor(snap.x);
  const sy = Math.floor(snap.y);
  const sw = Math.floor(snap.x + snap.w) - sx;
  const sh = Math.floor(snap.y + snap.h) - sy;
  const saved = new Uint8ClampedArray(sw * sh * 4);
  for (let y = 0; y < sh; y++) saved.set(img.data.subarray(((sy + y) * img.width + sx) * 4, ((sy + y) * img.width + sx + sw) * 4), y * sw * 4);
  const ringStd = lumStd(img, expand(snap, 8, bounds), snap);

  let erased = 0;
  const inkSamples: number[][] = [[], [], []];
  for (const m of members) {
    const box = clampBox(expand(m, 3, bounds), img.width, img.height);
    const bx = Math.floor(box.x);
    const by = Math.floor(box.y);
    const w = Math.floor(box.x + box.w) - bx;
    const h = Math.floor(box.y + box.h) - by;
    if (w <= 0 || h <= 0) continue;
    const ink = new Uint8Array(w * h);
    const faint = new Uint8Array(w * h);
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const i = ((by + y) * img.width + (bx + x)) * 4;
        const d = dist(img.data, i, bg);
        if (d > INK_DISTANCE) ink[y * w + x] = 1;
        if (d > FAINT_DISTANCE) faint[y * w + x] = 1;
      }
    }
    // Hysteresis: components are judged on the faint mask so antialiased line art
    // stays one long stroke; the halo around manga lettering keeps glyphs separate.
    // Long components touching the box edge (outlines, tails, panel borders, art) stay.
    const protectedMask = protectedComponents(faint, w, h, opts.charSize);
    let paint: Uint8Array;
    if (mode === "box") {
      const keep = dilate(protectedMask, w, h, 1);
      paint = new Uint8Array(w * h);
      for (let p = 0; p < paint.length; p++) paint[p] = keep[p] ? 0 : 1;
    } else {
      const glyphs = new Uint8Array(w * h);
      for (let p = 0; p < glyphs.length; p++) glyphs[p] = ink[p] && !protectedMask[p] ? 1 : 0;
      paint = dilate(glyphs, w, h, 2);
      const keep = protectedMask;
      for (let p = 0; p < paint.length; p++) if (keep[p]) paint[p] = 0;
    }
    for (let y = 0; y < h; y++) {
      for (let x = 0; x < w; x++) {
        const p = y * w + x;
        if (!paint[p]) continue;
        const i = ((by + y) * img.width + (bx + x)) * 4;
        if (ink[p] && !protectedMask[p]) {
          inkSamples[0].push(img.data[i]);
          inkSamples[1].push(img.data[i + 1]);
          inkSamples[2].push(img.data[i + 2]);
        }
        if (img.data[i] !== bg[0] || img.data[i + 1] !== bg[1] || img.data[i + 2] !== bg[2]) erased++;
        img.data[i] = bg[0];
        img.data[i + 1] = bg[1];
        img.data[i + 2] = bg[2];
      }
    }
  }
  // A flat patch inside busy line work (speed lines, hatching) is visible: undo it
  // and let the caller reconstruct the art instead (inpainting) or keep it.
  const boxStd = lumStd(img, snap);
  if (!opts.bubble && ringStd > 35 && boxStd < 0.4 * ringStd) {
    for (let y = 0; y < sh; y++) img.data.set(saved.subarray(y * sw * 4, (y + 1) * sw * 4), ((sy + y) * img.width + sx) * 4);
    return { mode: "skipped", bg, ink: guessInk(bg), flatness, inkShare, midShare, erasedPixels: 0 };
  }
  const ink: RGB = inkSamples[0].length > 20
    ? [median(inkSamples[0]), median(inkSamples[1]), median(inkSamples[2])]
    : guessInk(bg);
  return { mode, bg, ink, flatness, inkShare, midShare, erasedPixels: erased };
}

/**
 * Flood-fill the paper inside a balloon from its centre, then add everything the
 * fill encloses (the glyphs). Paints that interior with the paper colour. Returns
 * null when the fill leaks out to the box edge (open outline, loose box), so the
 * caller falls back to erasing glyph strokes only.
 */
export function bubbleInterior(img: RGBAImage, bubble: Box, bg: RGB): { erased: number; inkSamples?: RGB; interior: InteriorMask } | null {
  const b = clampBox(bubble, img.width, img.height);
  const bx = Math.floor(b.x);
  const by = Math.floor(b.y);
  const w = Math.floor(b.x + b.w) - bx;
  const h = Math.floor(b.y + b.h) - by;
  if (w < 8 || h < 8) return null;
  const at = (x: number, y: number) => ((by + y) * img.width + (bx + x)) * 4;
  // Paper = not within 1 px of ink, which closes hairline gaps in the outline.
  const inkPx = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < w; x++) if (dist(img.data, at(x, y), bg) > INK_DISTANCE * 0.6) inkPx[y * w + x] = 1;
  const nearInk = dilate(inkPx, w, h, 1);
  const paper = new Uint8Array(w * h);
  for (let p = 0; p < w * h; p++) paper[p] = nearInk[p] ? 0 : 1;

  // 1) Fill paper from seeds in the central area.
  const filled = new Uint8Array(w * h);
  const stack: number[] = [];
  for (let y = Math.floor(h * 0.3); y < Math.ceil(h * 0.7); y++) {
    for (let x = Math.floor(w * 0.3); x < Math.ceil(w * 0.7); x++) {
      const p = y * w + x;
      if (paper[p] && !filled[p]) {
        filled[p] = 1;
        stack.push(p);
      }
    }
  }
  if (!stack.length) return null;
  while (stack.length) {
    const p = stack.pop()!;
    const x = p % w;
    const y = (p - x) / w;
    for (const q of [x > 0 ? p - 1 : -1, x < w - 1 ? p + 1 : -1, y > 0 ? p - w : -1, y < h - 1 ? p + w : -1]) {
      if (q >= 0 && paper[q] && !filled[q]) {
        filled[q] = 1;
        stack.push(q);
      }
    }
  }
  // Leak test: an enclosed interior only grazes the box edge.
  let edge = 0;
  let edgeFilled = 0;
  for (let x = 0; x < w; x++) for (const y of [0, h - 1]) { edge++; edgeFilled += filled[y * w + x]; }
  for (let y = 1; y < h - 1; y++) for (const x of [0, w - 1]) { edge++; edgeFilled += filled[y * w + x]; }
  if (edgeFilled / edge > 0.18) return null;

  // 2) Outside = everything not filled that connects to the box edge (outline, art).
  const outside = new Uint8Array(w * h);
  for (let x = 0; x < w; x++) for (const y of [0, h - 1]) { const p = y * w + x; if (!filled[p] && !outside[p]) { outside[p] = 1; stack.push(p); } }
  for (let y = 0; y < h; y++) for (const x of [0, w - 1]) { const p = y * w + x; if (!filled[p] && !outside[p]) { outside[p] = 1; stack.push(p); } }
  while (stack.length) {
    const p = stack.pop()!;
    const x = p % w;
    const y = (p - x) / w;
    for (const q of [x > 0 ? p - 1 : -1, x < w - 1 ? p + 1 : -1, y > 0 ? p - w : -1, y < h - 1 ? p + w : -1]) {
      if (q >= 0 && !filled[q] && !outside[q]) {
        outside[q] = 1;
        stack.push(q);
      }
    }
  }
  // A burst balloon can open into speed lines: the fill then slips between the lines and
  // encloses stretches of them. When the fill reached the box edge, long hair-thin strokes
  // are art, not glyphs: keep them. (A closed balloon erases everything inside, dashes too.)
  const keepArt = edgeFilled / edge > 0.03 ? enclosedLines(filled, outside, w, h) : new Uint8Array(w * h);

  // 3) Interior = filled paper + enclosed pixels (glyphs). Accept it, then paint it.
  let interiorPx = 0;
  for (let p = 0; p < w * h; p++) if (!outside[p]) interiorPx++;
  if (interiorPx < 0.15 * w * h) return null;
  let erased = 0;
  const ink: number[][] = [[], [], []];
  for (let p = 0; p < w * h; p++) {
    if (outside[p] || keepArt[p]) continue;
    const x = p % w;
    const y = (p - x) / w;
    const i = at(x, y);
    if (!filled[p] && dist(img.data, i, bg) > INK_DISTANCE) {
      ink[0].push(img.data[i]);
      ink[1].push(img.data[i + 1]);
      ink[2].push(img.data[i + 2]);
    }
    if (img.data[i] !== bg[0] || img.data[i + 1] !== bg[1] || img.data[i + 2] !== bg[2]) erased++;
    img.data[i] = bg[0];
    img.data[i + 1] = bg[1];
    img.data[i + 2] = bg[2];
  }
  const mask = new Uint8Array(w * h);
  for (let p = 0; p < w * h; p++) mask[p] = outside[p] ? 0 : 1;
  return {
    erased,
    inkSamples: ink[0].length > 20 ? [median(ink[0]), median(ink[1]), median(ink[2])] : undefined,
    interior: { x: bx, y: by, w, h, mask },
  };
}

/** Enclosed (neither paper nor outside) components that are long and hair-thin: speed lines, not glyphs. */
function enclosedLines(filled: Uint8Array, outside: Uint8Array, w: number, h: number): Uint8Array {
  const keep = new Uint8Array(w * h);
  const seen = new Uint8Array(w * h);
  const minLong = 0.25 * Math.min(w, h);
  const stack: number[] = [];
  for (let s = 0; s < w * h; s++) {
    if (filled[s] || outside[s] || seen[s]) continue;
    const comp: number[] = [];
    seen[s] = 1;
    stack.push(s);
    let minX = w, minY = h, maxX = 0, maxY = 0;
    while (stack.length) {
      const p = stack.pop()!;
      comp.push(p);
      const x = p % w;
      const y = (p - x) / w;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      for (const q of [x > 0 ? p - 1 : -1, x < w - 1 ? p + 1 : -1, y > 0 ? p - w : -1, y < h - 1 ? p + w : -1]) {
        if (q >= 0 && !filled[q] && !outside[q] && !seen[q]) {
          seen[q] = 1;
          stack.push(q);
        }
      }
    }
    const long = Math.hypot(maxX - minX + 1, maxY - minY + 1);
    // The 1 px halo around each line belongs to the component, so a 1-2 px line reads ~4 px thick.
    if (long >= minLong && comp.length / long < 4.5) for (const p of comp) keep[p] = 1;
  }
  return keep;
}

/**
 * Share of ink pixels left in the core of the text boxes (outer 12% trimmed) after
 * erasure. Near zero means the source glyphs are gone; lettering over a high value
 * would put Vietnamese on top of leftover Japanese.
 */
export function residueShare(img: RGBAImage, members: Box[], bg: RGB): number {
  let ink = 0;
  let n = 0;
  for (const m of members) {
    const core = clampBox({ x: m.x + m.w * 0.12, y: m.y + m.h * 0.12, w: m.w * 0.76, h: m.h * 0.76 }, img.width, img.height);
    for (let y = Math.floor(core.y); y < Math.floor(core.y + core.h); y++) {
      for (let x = Math.floor(core.x); x < Math.floor(core.x + core.w); x++) {
        n++;
        if (dist(img.data, (y * img.width + x) * 4, bg) > INK_DISTANCE) ink++;
      }
    }
  }
  return n ? ink / n : 0;
}

/** Luminance standard deviation inside `outer`, excluding `hole` when given (a ring). */
function lumStd(img: RGBAImage, outer: Box, hole?: Box): number {
  const o = clampBox(outer, img.width, img.height);
  let n = 0;
  let sum = 0;
  let sq = 0;
  for (let y = Math.floor(o.y); y < Math.floor(o.y + o.h); y++) {
    for (let x = Math.floor(o.x); x < Math.floor(o.x + o.w); x++) {
      if (hole && x >= hole.x && x < hole.x + hole.w && y >= hole.y && y < hole.y + hole.h) continue;
      const i = (y * img.width + x) * 4;
      const v = 0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2];
      n++;
      sum += v;
      sq += v * v;
    }
  }
  if (!n) return 0;
  const m = sum / n;
  return Math.sqrt(Math.max(0, sq / n - m * m));
}

function intersectOr(a: Box, b: Box): Box {
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  const x2 = Math.min(a.x + a.w, b.x + b.w);
  const y2 = Math.min(a.y + a.h, b.y + b.h);
  return x2 > x1 && y2 > y1 ? { x: x1, y: y1, w: x2 - x1, h: y2 - y1 } : a;
}

const guessInk = (bg: RGB): RGB => (0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2] > 128 ? [20, 20, 20] : [245, 245, 245]);

/**
 * Ink that must survive erasure: long components crossing the box (outlines, tails,
 * panel borders, art), big masses, and — when the glyph size is known — hair-thin
 * strokes much longer than a character (speed lines, hatching).
 */
function protectedComponents(mask: Uint8Array, w: number, h: number, charSize?: number): Uint8Array {
  const seen = new Uint8Array(w * h);
  const out = new Uint8Array(w * h);
  const stack: number[] = [];
  for (let start = 0; start < mask.length; start++) {
    if (!mask[start] || seen[start]) continue;
    const comp: number[] = [];
    seen[start] = 1;
    stack.push(start);
    let minX = w, minY = h, maxX = 0, maxY = 0, touches = false;
    while (stack.length) {
      const p = stack.pop()!;
      comp.push(p);
      const x = p % w;
      const y = (p - x) / w;
      if (x < minX) minX = x;
      if (x > maxX) maxX = x;
      if (y < minY) minY = y;
      if (y > maxY) maxY = y;
      if (x === 0 || y === 0 || x === w - 1 || y === h - 1) touches = true;
      if (x > 0 && mask[p - 1] && !seen[p - 1]) { seen[p - 1] = 1; stack.push(p - 1); }
      if (x < w - 1 && mask[p + 1] && !seen[p + 1]) { seen[p + 1] = 1; stack.push(p + 1); }
      if (y > 0 && mask[p - w] && !seen[p - w]) { seen[p - w] = 1; stack.push(p - w); }
      if (y < h - 1 && mask[p + w] && !seen[p + w]) { seen[p + w] = 1; stack.push(p + w); }
    }
    const spanX = (maxX - minX + 1) / w;
    const spanY = (maxY - minY + 1) / h;
    const big = comp.length > 0.3 * w * h;
    const lineLike = charSize ? isLineLike(maxX - minX + 1, maxY - minY + 1, comp.length, charSize) : false;
    if ((touches && (spanX > 0.6 || spanY > 0.6)) || big || lineLike) for (const p of comp) out[p] = 1;
  }
  return out;
}

/** A thin stroke clearly longer than one character: line art, not a glyph (a dash "ー" stays a glyph). */
export function isLineLike(bw: number, bh: number, pixels: number, charSize: number): boolean {
  const long = Math.max(bw, bh);
  const meanThickness = pixels / Math.max(1, long);
  return long > charSize * 1.3 && meanThickness < Math.max(2.2, charSize * 0.12);
}

function dilate(mask: Uint8Array, w: number, h: number, r: number): Uint8Array {
  if (r <= 0) return mask;
  const out = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      if (!mask[y * w + x]) continue;
      for (let dy = -r; dy <= r; dy++) {
        const yy = y + dy;
        if (yy < 0 || yy >= h) continue;
        for (let dx = -r; dx <= r; dx++) {
          const xx = x + dx;
          if (xx >= 0 && xx < w) out[yy * w + xx] = 1;
        }
      }
    }
  }
  return out;
}

function median(v: number[]): number {
  const s = [...v].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)] ?? 255;
}
