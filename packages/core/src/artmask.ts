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
}

const CONTRAST = 38;
const MEAN_RADIUS = 7;

/**
 * Mask for text drawn over artwork: glyph strokes and their halo are the pixels
 * whose luminance departs strongly from the local mean. Long strokes crossing the
 * whole box (panel borders, art lines) are kept out of the hole. The mask is grown
 * a few pixels so antialiasing and outlines are reconstructed too; when nearly the
 * whole box qualifies, the full box becomes the hole.
 */
export function artTextMask(img: RGBAImage, members: Box[], opts: { charSize?: number } = {}): InpaintJob {
  const bounds = { w: img.width, h: img.height };
  const u = members.reduce((a, m) => ({
    x: Math.min(a.x, m.x),
    y: Math.min(a.y, m.y),
    w: Math.max(a.x + a.w, m.x + m.w) - Math.min(a.x, m.x),
    h: Math.max(a.y + a.h, m.y + m.h) - Math.min(a.y, m.y),
  }));
  const margin = Math.min(160, Math.max(24, Math.round(0.5 * Math.max(u.w, u.h))));
  const c = roundBox(clampBox(expand(u, margin), bounds.w, bounds.h));
  const W = c.w;
  const H = c.h;
  const lum = new Float32Array(W * H);
  for (let y = 0; y < H; y++) {
    for (let x = 0; x < W; x++) {
      const i = ((c.y + y) * img.width + (c.x + x)) * 4;
      lum[y * W + x] = 0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2];
    }
  }
  const mean = boxMean(lum, W, H, MEAN_RADIUS);
  const hole = new Uint8Array(W * H);
  let boxPixels = 0;
  for (const m of members) {
    // Glyphs often poke slightly out of a tight detector box: search a little wider.
    const reach = Math.max(2, Math.round((opts.charSize ?? 12) * 0.35));
    const b = roundBox(clampBox(intersectBox(expand(m, reach), c), bounds.w, bounds.h));
    const bx = b.x - c.x;
    const by = b.y - c.y;
    boxPixels += b.w * b.h;
    // Preferred: glyph-sized ink components (dark text, or light text on dark art).
    const cs = opts.charSize ?? Math.max(10, Math.min(b.w, b.h) * 0.8);
    let cand = glyphComponents(lum, W, bx, by, b.w, b.h, cs, (v) => v < 110, (v) => v < 175);
    if (coverageOf(cand) < 0.02) cand = glyphComponents(lum, W, bx, by, b.w, b.h, cs, (v) => v > 205, (v) => v > 150);
    let grow = 3;
    if (coverageOf(cand) < 0.02) {
      // Fallback: strong local contrast (stylised strokes, halos on texture).
      cand = new Uint8Array(b.w * b.h);
      for (let y = 0; y < b.h; y++) {
        for (let x = 0; x < b.w; x++) {
          const p = (by + y) * W + (bx + x);
          if (Math.abs(lum[p] - mean[p]) > CONTRAST) cand[y * b.w + x] = 1;
        }
      }
      dropEdgeSpanning(cand, b.w, b.h);
      grow = 4;
    }
    const grown = dilate(cand, b.w, b.h, grow);
    for (let y = 0; y < b.h; y++) for (let x = 0; x < b.w; x++) if (grown[y * b.w + x]) hole[(by + y) * W + (bx + x)] = 1;
  }
  let holes = 0;
  for (const v of hole) holes += v;
  const coverage = boxPixels ? holes / boxPixels : 0;
  return { crop: c, hole, coverage };
}

function intersectBox(a: Box, b: Box): Box {
  const x1 = Math.max(a.x, b.x);
  const y1 = Math.max(a.y, b.y);
  const x2 = Math.min(a.x + a.w, b.x + b.w);
  const y2 = Math.min(a.y + a.h, b.y + b.h);
  return { x: x1, y: y1, w: Math.max(1, x2 - x1), h: Math.max(1, y2 - y1) };
}

const coverageOf = (m: Uint8Array) => {
  let n = 0;
  for (const v of m) n += v;
  return m.length ? n / m.length : 0;
};

/**
 * Ink components no larger than a few characters: glyph strokes, punctuation and
 * furigana. Hair, panel borders and other big art masses are left out.
 */
function glyphComponents(
  lum: Float32Array,
  W: number,
  bx: number,
  by: number,
  w: number,
  h: number,
  charSize: number,
  isInk: (v: number) => boolean,
  isFaint: (v: number) => boolean,
): Uint8Array {
  // Components are traced on the faint mask (hysteresis) so line art stays connected;
  // only components that contain real ink count as glyphs.
  const ink = new Uint8Array(w * h);
  const strong = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    for (let x = 0; x < w; x++) {
      const v = lum[(by + y) * W + (bx + x)];
      if (isFaint(v)) ink[y * w + x] = 1;
      if (isInk(v)) strong[y * w + x] = 1;
    }
  }
  const out = new Uint8Array(w * h);
  const seen = new Uint8Array(w * h);
  const stack: number[] = [];
  // Touching glyphs in one column/line form elongated components: thin across the
  // text direction, a few characters long. Hair and art masses are wide in both.
  const maxThin = charSize * 1.6;
  const maxLong = charSize * 4.5;
  const maxArea = charSize * charSize * 3;
  for (let s = 0; s < ink.length; s++) {
    if (!ink[s] || seen[s]) continue;
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
        if (q >= 0 && ink[q] && !seen[q]) {
          seen[q] = 1;
          stack.push(q);
        }
      }
    }
    const cw = maxX - minX + 1;
    const ch = maxY - minY + 1;
    const small = Math.min(cw, ch) <= maxThin && Math.max(cw, ch) <= maxLong && comp.length <= maxArea && !isLineLike(cw, ch, comp.length, charSize) && comp.some((p) => strong[p]);
    if (small) for (const p of comp) out[p] = 1;
  }
  return out;
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

/** Remove components that touch the box edge and span most of it (art lines, borders). */
function dropEdgeSpanning(mask: Uint8Array, w: number, h: number): void {
  const seen = new Uint8Array(w * h);
  const stack: number[] = [];
  for (let s = 0; s < mask.length; s++) {
    if (!mask[s] || seen[s]) continue;
    const comp: number[] = [];
    seen[s] = 1;
    stack.push(s);
    let minX = w, minY = h, maxX = 0, maxY = 0, touches = false;
    while (stack.length) {
      const p = stack.pop()!;
      comp.push(p);
      const x = p % w;
      const y = (p - x) / w;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
      if (x === 0 || y === 0 || x === w - 1 || y === h - 1) touches = true;
      for (const q of [x > 0 ? p - 1 : -1, x < w - 1 ? p + 1 : -1, y > 0 ? p - w : -1, y < h - 1 ? p + w : -1]) {
        if (q >= 0 && mask[q] && !seen[q]) {
          seen[q] = 1;
          stack.push(q);
        }
      }
    }
    if (touches && ((maxX - minX + 1) / w > 0.8 || (maxY - minY + 1) / h > 0.8)) for (const p of comp) mask[p] = 0;
  }
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
 * artwork (hatching, speed lines, screentone) reads as a visible patch, so it is
 * rejected and the original art is kept instead.
 */
export function patchBlends(original: RGBAImage, result: Uint8Array, job: InpaintJob): { ok: boolean; holeStd: number; ringStd: number } {
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
  return { ok: !(ringStd > 30 && holeStd < 0.45 * ringStd), holeStd, ringStd };
}
