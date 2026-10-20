import { area, clampBox, expand, intersect, iou, roundBox } from "./geometry";
import type { RGBAImage } from "./erase";
import type { Box, TextRegion } from "./types";

/**
 * A balloon the detector missed. Small balloons on screentone or hatching (a one-word reply, a
 * rustle) often come out as free text with no balloon around them: they were then rebuilt by the
 * inpainting model, which smears the tone outside into the white balloon. Here the page pixels
 * decide: the text sits in a small closed area of light paper, and nothing but the text is inside
 * it. Returns that balloon (its interior and outline) or undefined.
 *
 * The page detector usually saw these balloons too, below the score that makes a region
 * (`weak`: its bubble boxes from 0.035). A weak detection over the closed area is enough with a
 * rough outline (glyphs touching it, a burst's spikes); without one only a smooth, round outline
 * hugging the text counts.
 *
 * Only light paper and the strokes it encloses next to the text are ever repainted from this box
 * (see `bubbleInterior`), so a white patch of art taken for a balloon loses nothing: any other
 * drawing inside it rejects it.
 */
export function findBalloon(img: RGBAImage, r: Pick<TextRegion, "box">, weak: WeakBubble[] = [], stats?: Record<string, number>): Box | undefined {
  const tb = r.box;
  if (tb.w < 6 || tb.h < 6) return undefined;
  const win = roundBox(clampBox(expand(tb, Math.max(tb.w, tb.h) + 8), img.width, img.height));
  const { w, h } = win;
  if (w < 16 || h < 16) return undefined;
  const lum = new Uint8Array(w * h);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const i = ((win.y + y) * img.width + win.x + x) * 4;
      lum[y * w + x] = Math.round(0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2]);
    }
  // Text box in window coordinates.
  const tx0 = Math.max(0, Math.floor(tb.x - win.x));
  const ty0 = Math.max(0, Math.floor(tb.y - win.y));
  const tx1 = Math.min(w, Math.ceil(tb.x + tb.w - win.x));
  const ty1 = Math.min(h, Math.ceil(tb.y + tb.h - win.y));
  // Paper level: the light end of the text box (glyphs cover far less than half of it).
  const inBox: number[] = [];
  for (let y = ty0; y < ty1; y++) for (let x = tx0; x < tx1; x++) inBox.push(lum[y * w + x]);
  inBox.sort((a, b) => a - b);
  const paper = inBox[Math.floor(inBox.length * 0.85)] ?? 0;
  if (paper < 170) return undefined;

  // Free paper: light, and not within 1 px of ink (closes hairline gaps in an outline and the
  // gaps between screentone dots).
  const dark = new Uint8Array(w * h);
  for (let p = 0; p < w * h; p++) if (lum[p] < paper - 60) dark[p] = 1;
  const near = dilate1(dark, w, h);
  const freePx = (p: number) => !near[p] && lum[p] >= paper - 40;

  // 1) Fill the paper from the central half of the text box.
  const filled = new Uint8Array(w * h);
  const stack: number[] = [];
  const cx0 = Math.floor(tx0 + (tx1 - tx0) * 0.25), cx1 = Math.ceil(tx0 + (tx1 - tx0) * 0.75);
  const cy0 = Math.floor(ty0 + (ty1 - ty0) * 0.25), cy1 = Math.ceil(ty0 + (ty1 - ty0) * 0.75);
  for (let y = cy0; y < cy1; y++)
    for (let x = cx0; x < cx1; x++) {
      const p = y * w + x;
      if (freePx(p) && !filled[p]) {
        filled[p] = 1;
        stack.push(p);
      }
    }
  if (!stack.length) return undefined;
  let fill = 0;
  while (stack.length) {
    const p = stack.pop()!;
    fill++;
    const x = p % w;
    const y = (p - x) / w;
    // Open to the window edge: page margin, a panel's white ground, an open burst.
    if (x === 0 || y === 0 || x === w - 1 || y === h - 1) return undefined;
    for (const q of [p - 1, p + 1, p - w, p + w]) {
      if (!filled[q] && freePx(q)) {
        filled[q] = 1;
        stack.push(q);
      }
    }
  }
  if (fill < 0.15 * area(tb)) return undefined;

  // 2) Outside = everything not filled that reaches the window edge (outline, tone, art).
  const outside = new Uint8Array(w * h);
  for (let x = 0; x < w; x++) for (const y of [0, h - 1]) seed(y * w + x);
  for (let y = 0; y < h; y++) for (const x of [0, w - 1]) seed(y * w + x);
  function seed(p: number) {
    if (!filled[p] && !outside[p]) {
      outside[p] = 1;
      stack.push(p);
    }
  }
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

  // 3) Everything enclosed that is not paper must belong to the text: a piece that keeps clear of
  //    the text box (an eye, a button, a drawn prop) means this is art, not a balloon.
  const pad = Math.max(3, 0.15 * Math.min(tb.w, tb.h));
  const px0 = tx0 - pad, py0 = ty0 - pad, px1 = tx1 + pad, py1 = ty1 + pad;
  const seen = new Uint8Array(w * h);
  let stray = 0;
  let enclosed = 0;
  let minX = w, minY = h, maxX = -1, maxY = -1;
  for (let s = 0; s < w * h; s++) {
    if (outside[s]) continue;
    const sx = s % w;
    const sy = (s - sx) / w;
    if (sx < minX) minX = sx;
    if (sx > maxX) maxX = sx;
    if (sy < minY) minY = sy;
    if (sy > maxY) maxY = sy;
    if (filled[s] || seen[s]) continue;
    let size = 0;
    let touchesText = false;
    let bx0 = w, by0 = h, bx1 = 0, by1 = 0;
    seen[s] = 1;
    stack.push(s);
    while (stack.length) {
      const p = stack.pop()!;
      size++;
      const x = p % w;
      const y = (p - x) / w;
      if (x < bx0) bx0 = x;
      if (x > bx1) bx1 = x;
      if (y < by0) by0 = y;
      if (y > by1) by1 = y;
      if (x >= px0 && x < px1 && y >= py0 && y < py1) touchesText = true;
      for (const q of [p - 1, p + 1, p - w, p + w]) {
        if (!filled[q] && !outside[q] && !seen[q]) {
          seen[q] = 1;
          stack.push(q);
        }
      }
    }
    enclosed += size;
    // A long hair-thin piece is a rule or a drawn line (a table, a frame inside a sign), not a glyph.
    const long = Math.max(bx1 - bx0 + 1, by1 - by0 + 1);
    if (!touchesText || (long >= 40 && size / long < 3)) stray += size;
  }
  if (stray > Math.max(12, 0.03 * (fill + enclosed))) return undefined;
  // Mostly paper: text fills well under half of a balloon.
  if (fill < 0.45 * (fill + enclosed)) return undefined;

  // A ruled line crossing the text (a table, a form, lined paper) makes this a printed sheet: its
  // text is lettered line by line as free text (see slant.ts), not as one balloon.
  if (ruledAcross(dark, outside, w, tx0, ty0, tx1, ty1)) return undefined;

  const inner: Box = { x: win.x + minX, y: win.y + minY, w: maxX - minX + 1, h: maxY - minY + 1 };
  // Outer contour length: interior pixels next to the outside.
  const contour = (m: Uint8Array) => {
    let e = 0, a = 0;
    for (let p = 0; p < w * h; p++) {
      if (!m[p]) continue;
      a++;
      if (!m[p - 1] || !m[p + 1] || !m[p - w] || !m[p + w]) e++;
    }
    return (e * e) / (4 * Math.PI * Math.max(1, a));
  };
  const inside = new Uint8Array(w * h);
  for (let p = 0; p < w * h; p++) inside[p] = outside[p] ? 0 : 1;
  const compact = contour(inside);
  const close = (m: Uint8Array, r: number) => {
    let d = m;
    for (let i = 0; i < r; i++) d = dilate1(d, w, h);
    let e = d;
    for (let i = 0; i < r; i++) e = erode1(e, w, h);
    return e;
  };
  // Closing first: glyphs that touch the outline cut thin notches into the contour.
  const rough = contour(close(inside, 4));
  // A narrow strip (a caption box down the side of a panel): Vietnamese needs more width than the
  // Japanese column, and free text may grow out of it; as a balloon it would be held inside.
  if (inner.h >= 2.8 * inner.w || inner.w >= 2.8 * inner.h) return undefined;
  const ratio = area(inner) / area(tb);
  // A balloon hugs its text on every side: a panel or a poster around a caption leaves a wide
  // margin where the drawing is.
  const margin = Math.max(tb.x - inner.x, tb.y - inner.y, inner.x + inner.w - (tb.x + tb.w), inner.y + inner.h - (tb.y + tb.h));
  const balloon = roundBox(clampBox(expand(inner, 3), img.width, img.height));
  const over = (minScore: number, minIou: number) => weak.some((b) => b.score >= minScore && iou(b.box, balloon) >= minIou);
  if (stats) Object.assign(stats, { compact, rough, ratio, margin, paper: fill / (fill + enclosed) });
  if (ratio > 6 || margin > Math.max(12, 0.45 * Math.min(tb.w, tb.h))) return undefined;
  const shared = intersect(inner, tb);
  if (!shared || area(shared) < 0.85 * area(tb)) return undefined;
  // The detector finds big balloons by itself: a big closed area it did not call a balloon is
  // more likely a notice board or a white panel full of text (lettered as free text instead).
  if (Math.max(inner.w, inner.h) > 0.1 * Math.max(img.width, img.height) && !over(0.07, 0.7)) return undefined;
  // A burst balloon's spikes make the roughest outlines: it needs a surer detection.
  const confirmed = (over(0.035, 0.6) && rough <= 9) || (over(0.07, 0.7) && rough <= 16);
  const round = rough <= 1.35 && ratio <= 3.5;
  return confirmed || round ? balloon : undefined;
}

/** Balloons up to this size (px) are round enough to be repainted as the hull of their paper. */
const SMALL_BALLOON = 110;

/** A bubble detection too weak to make a region on its own. */
export interface WeakBubble {
  box: Box;
  score: number;
}

/** Bubble detections from this score can confirm a balloon found in the pixels. */
export const WEAK_BUBBLE_SCORE = 0.035;

/** Regions with no balloon get the one found in the page pixels, if any (`findBalloon`). */
export function adoptBalloons(img: RGBAImage, regions: TextRegion[], weak: WeakBubble[] = []): TextRegion[] {
  return regions.map((r) => {
    // Detector regions only: text the reader model reported as missed comes with a loose box.
    if (r.bubble || !/^r\d+$/.test(r.id)) return r;
    const bubble = findBalloon(img, r, weak);
    return bubble ? { ...r, kind: "bubble", bubble } : r;
  });
}

function dilate1(mask: Uint8Array, w: number, h: number): Uint8Array {
  const out = new Uint8Array(w * h);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      if (!mask[y * w + x]) continue;
      for (let yy = Math.max(0, y - 1); yy <= Math.min(h - 1, y + 1); yy++)
        for (let xx = Math.max(0, x - 1); xx <= Math.min(w - 1, x + 1); xx++) out[yy * w + xx] = 1;
    }
  return out;
}

function erode1(mask: Uint8Array, w: number, h: number): Uint8Array {
  const out = new Uint8Array(w * h);
  for (let y = 1; y < h - 1; y++)
    for (let x = 1; x < w - 1; x++) {
      const p = y * w + x;
      if (mask[p] && mask[p - 1] && mask[p + 1] && mask[p - w] && mask[p + w] && mask[p - w - 1] && mask[p - w + 1] && mask[p + w - 1] && mask[p + w + 1]) out[p] = 1;
    }
  return out;
}

/**
 * A straight dark rule of the outside (joined to a frame) right across the middle of the text
 * box: rows in its inner 70% (a balloon outline only passes along the box's own edges) with a run
 * over 80% of the box width within a 3-pixel band; the same for columns.
 */
function ruledAcross(dark: Uint8Array, outside: Uint8Array, w: number, x0: number, y0: number, x1: number, y1: number): boolean {
  const bw = x1 - x0, bh = y1 - y0;
  const rule = (p: number) => !!(dark[p] && outside[p]);
  if (bw >= 40)
    for (let y = Math.ceil(y0 + 0.15 * bh); y < y1 - 0.15 * bh; y++) {
      let run = 0;
      for (let x = x0; x < x1; x++) {
        run = rule((y - 1) * w + x) || rule(y * w + x) || rule((y + 1) * w + x) ? run + 1 : 0;
        if (run >= 0.8 * bw) return true;
      }
    }
  if (bh >= 40)
    for (let x = Math.ceil(x0 + 0.15 * bw); x < x1 - 0.15 * bw; x++) {
      let run = 0;
      for (let y = y0; y < y1; y++) {
        run = rule(y * w + x - 1) || rule(y * w + x) || rule(y * w + x + 1) ? run + 1 : 0;
        if (run >= 0.8 * bh) return true;
      }
    }
  return false;
}

/**
 * Repaint a balloon's whole inside with its paper, outline kept: the last resort when the fill
 * left text standing because the strokes touch the outline (a small balloon full of bold kana,
 * a shout filling a burst). Rays from the text centre find where the paper ends: a stroke inside
 * is followed by paper again within a stroke's width, the outline by tone, hatching or black.
 * Dips where a stroke meets the outline are bridged (convex hull of the ray ends, or a running
 * median for a burst's spikes), and a ray reaching far out (the tail) is cut back.
 *
 * Refuses (returns false, paints nothing) when a ray leaves the balloon box on paper (an open
 * balloon), when the shape misses the text, or when ink away from the text is inside it (art).
 * Painted pixels join `interior` (lettering room).
 */
export function paintBalloon(
  img: RGBAImage,
  bubble: Box,
  textBoxes: Box[],
  bg: [number, number, number],
  charSize = 20,
  interior?: { x: number; y: number; w: number; h: number; mask: Uint8Array },
): boolean {
  const bgL = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2];
  if (bgL < 170 || !textBoxes.length) return false;
  const win = roundBox(clampBox(expand(bubble, 2), img.width, img.height));
  const { w, h } = win;
  if (w < 12 || h < 12) return false;
  const lum = new Uint8Array(w * h);
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const i = ((win.y + y) * img.width + win.x + x) * 4;
      lum[y * w + x] = Math.round(0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2]);
    }
  const dark = new Uint8Array(w * h);
  for (let p = 0; p < w * h; p++) if (lum[p] < bgL - 60) dark[p] = 1;
  const near = dilate1(dark, w, h);
  const free = (x: number, y: number) => !near[y * w + x] && lum[y * w + x] >= bgL - 30;

  let ux0 = Infinity, uy0 = Infinity, ux1 = -Infinity, uy1 = -Infinity;
  for (const b of textBoxes) {
    ux0 = Math.min(ux0, b.x);
    uy0 = Math.min(uy0, b.y);
    ux1 = Math.max(ux1, b.x + b.w);
    uy1 = Math.max(uy1, b.y + b.h);
  }
  const cx = Math.min(w - 2, Math.max(1, (ux0 + ux1) / 2 - win.x));
  const cy = Math.min(h - 2, Math.max(1, (uy0 + uy1) / 2 - win.y));
  const shape = (Math.max(w, h) <= SMALL_BALLOON && paperHull()) || rayShape();
  if (!shape) return false;

  // A small balloon packed with text: from the centre every ray meets a glyph before the outline.
  // The paper between the glyphs reaches the outline all round, and a small balloon is round:
  // its convex hull is the inside.
  function paperHull(): Array<[number, number]> | undefined {
    const seen = new Uint8Array(w * h);
    const stack: number[] = [];
    for (let y = Math.floor(cy - (uy1 - uy0) / 4); y <= Math.ceil(cy + (uy1 - uy0) / 4); y++)
      for (let x = Math.floor(cx - (ux1 - ux0) / 4); x <= Math.ceil(cx + (ux1 - ux0) / 4); x++)
        if (x >= 0 && y >= 0 && x < w && y < h && free(x, y) && !seen[y * w + x]) {
          seen[y * w + x] = 1;
          stack.push(y * w + x);
        }
    const pts: Array<[number, number]> = [];
    while (stack.length) {
      const p = stack.pop()!;
      const x = p % w;
      const y = (p - x) / w;
      if (x === 0 || y === 0 || x === w - 1 || y === h - 1) return undefined; // open
      pts.push([x + 0.5, y + 0.5]);
      for (const q of [p - 1, p + 1, p - w, p + w])
        if (!seen[q] && free(q % w, Math.floor(q / w))) {
          seen[q] = 1;
          stack.push(q);
        }
    }
    if (pts.length < 20) return undefined;
    const hull = convexHull(pts);
    // One pixel out: the paper's halo next to the outline.
    return hull.map(([x, y]) => {
      const d = Math.hypot(x - cx, y - cy) || 1;
      return [x + (x - cx) / d, y + (y - cy) / d] as [number, number];
    });
  }

  function rayShape(): Array<[number, number]> | undefined {
  const N = Math.max(72, Math.min(360, Math.round(Math.PI * Math.max(w, h))));
  // How far past a stroke the paper must come back: bold strokes with their halo run 6-10 px.
  const L = Math.max(8, Math.round(0.9 * charSize));
  const ray = (k: number): [number, number] => [Math.cos((2 * Math.PI * k) / N), Math.sin((2 * Math.PI * k) / N)];
  const ends = new Float64Array(N);
  for (let k = 0; k < N; k++) {
    const [dx, dy] = ray(k);
    const F: number[] = [];
    for (let t = 0; ; t++) {
      const x = Math.round(cx + dx * t), y = Math.round(cy + dy * t);
      if (x < 0 || y < 0 || x >= w || y >= h) break;
      F.push(free(x, y) ? 1 : 0);
    }
    let last = -1;
    let end = -1;
    for (let t = 0; t < F.length && end < 0; t++) {
      if (F[t]) {
        last = t;
        continue;
      }
      if (last < 0) continue;
      let ahead = 0;
      for (let s = t; s < Math.min(F.length, t + L); s++) ahead += F[s];
      if (ahead < 0.3 * L) end = last;
    }
    // A ray that leaves the box on paper went down the tail (or out of an open balloon).
    ends[k] = end < 0 ? NaN : end + 1.5; // the paper's 1 px halo next to the outline
  }
  const open = ends.filter((e) => Number.isNaN(e)).length;
  if (open > 0.15 * N) return undefined;
  // Rays down the tail: interpolated between the nearest rays that met the outline.
  for (let k = 0; k < N && open; k++) {
    if (!Number.isNaN(ends[k])) continue;
    let a = 1, b = 1;
    while (Number.isNaN(ends[(k - a + N) % N])) a++;
    while (Number.isNaN(ends[(k + b) % N])) b++;
    ends[k] = (ends[(k - a + N) % N] * b + ends[(k + b) % N] * a) / (a + b);
  }
  // Tails: a ray far beyond its neighbours is cut back to them.
  const half = Math.max(3, Math.round(N / 50));
  const med = new Float64Array(N);
  for (let k = 0; k < N; k++) {
    const v: number[] = [];
    for (let j = -half; j <= half; j++) v.push(ends[(k + j + N) % N]);
    v.sort((a, b) => a - b);
    med[k] = v[half];
  }
  const cut = Array.from(ends, (e, k) => Math.min(e, 1.2 * med[k] + 2));
  const at = (k: number, r: number): [number, number] => [cx + r * ray(k)[0], cy + r * ray(k)[1]];
  const pts = cut.map((e, k) => at(k, e));
  // The convex hull bridges strokes that meet the outline; a burst (far from convex) keeps its
  // spikes and only has narrow dips lifted to the running median.
  const hull = convexHull(pts);
  return polygonArea(pts) >= 0.85 * polygonArea(hull) ? hull : cut.map((e, k) => at(k, Math.max(e, med[k])));
  }

  const mask = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    const xs: number[] = [];
    for (let i = 0; i < shape.length; i++) {
      const [x0, y0] = shape[i];
      const [x1, y1] = shape[(i + 1) % shape.length];
      if (y0 <= y + 0.5 !== y1 <= y + 0.5) xs.push(x0 + ((y + 0.5 - y0) / (y1 - y0)) * (x1 - x0));
    }
    xs.sort((a, b) => a - b);
    for (let i = 0; i + 1 < xs.length; i += 2)
      for (let x = Math.max(0, Math.ceil(xs[i] - 0.5)); x <= Math.min(w - 1, Math.floor(xs[i + 1] - 0.5)); x++) mask[y * w + x] = 1;
  }
  // Guards: the shape holds the text, and no ink away from the text (art) is inside it.
  const pad = Math.max(3, 0.25 * charSize);
  const inBoxes = (gx: number, gy: number, m: number) => textBoxes.some((b) => gx >= b.x - m && gy >= b.y - m && gx < b.x + b.w + m && gy < b.y + b.h + m);
  let textPx = 0, inText = 0, stray = 0, inside = 0;
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      const p = y * w + x;
      const gx = win.x + x, gy = win.y + y;
      if (inBoxes(gx, gy, 0)) {
        textPx++;
        if (mask[p]) inText++;
      }
      if (!mask[p]) continue;
      inside++;
      if (dark[p] && !inBoxes(gx, gy, pad)) stray++;
    }
  // (Text boxes often reach over the outline of a small balloon: 60% of them inside is enough.)
  if (!textPx || inText < 0.6 * textPx || stray > Math.max(15, 0.02 * inside)) return false;
  for (let y = 0; y < h; y++)
    for (let x = 0; x < w; x++) {
      if (!mask[y * w + x]) continue;
      const gx = win.x + x, gy = win.y + y;
      const i = (gy * img.width + gx) * 4;
      img.data[i] = bg[0];
      img.data[i + 1] = bg[1];
      img.data[i + 2] = bg[2];
      if (interior && gx >= interior.x && gy >= interior.y && gx < interior.x + interior.w && gy < interior.y + interior.h)
        interior.mask[(gy - interior.y) * interior.w + (gx - interior.x)] = 1;
    }
  return true;
}

function polygonArea(q: Array<[number, number]>): number {
  let s = 0;
  for (let i = 0; i < q.length; i++) {
    const [x0, y0] = q[i];
    const [x1, y1] = q[(i + 1) % q.length];
    s += x0 * y1 - x1 * y0;
  }
  return Math.abs(s) / 2;
}

function convexHull(points: Array<[number, number]>): Array<[number, number]> {
  const p = [...points].sort((a, b) => a[0] - b[0] || a[1] - b[1]);
  const cross = (o: [number, number], a: [number, number], b: [number, number]) => (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  const lower: Array<[number, number]> = [];
  for (const q of p) {
    while (lower.length >= 2 && cross(lower[lower.length - 2], lower[lower.length - 1], q) <= 0) lower.pop();
    lower.push(q);
  }
  const upper: Array<[number, number]> = [];
  for (const q of p.reverse()) {
    while (upper.length >= 2 && cross(upper[upper.length - 2], upper[upper.length - 1], q) <= 0) upper.pop();
    upper.push(q);
  }
  return lower.slice(0, -1).concat(upper.slice(0, -1));
}
