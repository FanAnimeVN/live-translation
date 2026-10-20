/**
 * The direction and curve of source text, read from its ink, so the Vietnamese can be lettered
 * the way the raw is laid out. manga-image-translator keeps each text line's angle from its
 * detector and warps the rendered text onto the rotated box; our detector only gives upright
 * boxes, so the angle is measured here: rows and columns of Japanese glyphs sit on a grid, and
 * the ink's projections are sharpest when they are taken along that grid. A single line or
 * column whose centre bows (a caption along a curve) also gets its arc, which they do not do.
 */
import type { Box, RGBAImage } from "@lt/core";

export interface Slant {
  /** Rotation of the text grid, radians (positive = clockwise on screen). */
  angle: number;
  /** Centre of the text block on the page. */
  cx: number;
  cy: number;
  /** Size of the block in its own (deskewed) frame. */
  w: number;
  h: number;
  /** How much sharper the projections are at `angle` than upright (1 = no gain). */
  gain: number;
  /**
   * A single line or column that bows: its centre in the frame runs along
   * `across = bow * (1 - (2 * along / length - 1) ** 2)` from the chord through the block centre.
   * Positive bow bulges towards +y (or +x for a column) of the frame.
   */
  bow?: number;
  /** True when the block is a column (main axis along the frame's y). */
  column: boolean;
  /**
   * The printed lines of a left-aligned horizontal block (a card, a form, a letter written
   * across): extents in the frame, relative to its centre, top to bottom. Small ruby lines are left out.
   */
  lines?: Array<{ u0: number; u1: number; v0: number; v1: number }>;
}

/** Smallest tilt worth turning the lettering for, and the projection gain that proves it. */
const MIN_ANGLE = (4 * Math.PI) / 180;
const MIN_GAIN = 1.15;
const MAX_ANGLE = 35;

const lumAt = (img: RGBAImage, x: number, y: number) => {
  const i = (y * img.width + x) * 4;
  return 0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2];
};

/**
 * Ink pixels of the text inside `boxes`: the minority side of an Otsu split of their luminance
 * (dark letters on paper, or light letters on a dark ground), at most `max` of them.
 */
export function inkPoints(img: RGBAImage, boxes: Box[], max = 6000): Array<[number, number]> {
  const hist = new Array<number>(256).fill(0);
  const px: Array<[number, number, number]> = [];
  const seen = new Set<number>();
  for (const b of boxes) {
    const x0 = Math.max(0, Math.floor(b.x)), y0 = Math.max(0, Math.floor(b.y));
    const x1 = Math.min(img.width, Math.ceil(b.x + b.w)), y1 = Math.min(img.height, Math.ceil(b.y + b.h));
    for (let y = y0; y < y1; y++)
      for (let x = x0; x < x1; x++) {
        const k = y * img.width + x;
        if (seen.has(k)) continue;
        seen.add(k);
        const l = Math.round(lumAt(img, x, y));
        hist[l]++;
        px.push([x, y, l]);
      }
  }
  if (px.length < 50) return [];
  const t = otsu(hist, px.length);
  const dark = px.filter((p) => p[2] <= t).length;
  const wantDark = dark <= px.length / 2;
  const ink = px.filter((p) => (wantDark ? p[2] <= t : p[2] > t));
  if (ink.length <= max) return ink.map((p) => [p[0], p[1]]);
  // A fixed pseudo-random sample: every k-th pixel in raster order would put its own grid in the
  // projections and favour the upright angle.
  let seed = 1234567;
  const out: Array<[number, number]> = [];
  for (const p of ink) {
    seed = (seed * 1664525 + 1013904223) >>> 0;
    if (seed / 2 ** 32 < max / ink.length) out.push([p[0], p[1]]);
  }
  return out;
}

function otsu(hist: number[], n: number): number {
  let sum = 0;
  for (let i = 0; i < 256; i++) sum += i * hist[i];
  let sumB = 0, wB = 0, best = 0, t = 127;
  for (let i = 0; i < 256; i++) {
    wB += hist[i];
    if (!wB) continue;
    const wF = n - wB;
    if (!wF) break;
    sumB += i * hist[i];
    const mB = sumB / wB;
    const mF = (sum - sumB) / wF;
    const v = wB * wF * (mB - mF) ** 2;
    if (v > best) {
      best = v;
      t = i;
    }
  }
  return t;
}

/**
 * Projection sharpness of the points rotated by -a, across the frame's columns (`u`) and rows
 * (`v`) separately: horizontal lines of a form sharpen the rows only, glyphs of different widths
 * leave the columns flat.
 */
function sharpness(pts: Array<[number, number]>, cx: number, cy: number, a: number, reach: number): [number, number] {
  const c = Math.cos(a), s = Math.sin(a);
  const n = 2 * reach + 1;
  const hu = new Int32Array(n);
  const hv = new Int32Array(n);
  for (const [x, y] of pts) {
    const dx = x - cx, dy = y - cy;
    hu[Math.round(dx * c + dy * s) + reach]++;
    hv[Math.round(-dx * s + dy * c) + reach]++;
  }
  let qu = 0, qv = 0;
  for (let i = 0; i < n; i++) {
    qu += hu[i] * hu[i];
    qv += hv[i] * hv[i];
  }
  const nn = pts.length * pts.length;
  return [qu / nn, qv / nn];
}

/**
 * The slant of the text in `boxes`, or undefined when it is upright (within 4 degrees) or the
 * ink gives no clear answer. `charSize` is the source glyph size, used for the curve test.
 */
export function textSlant(img: RGBAImage, boxes: Box[], charSize: number): Slant | undefined {
  const pts = inkPoints(img, boxes);
  if (pts.length < 80) return undefined;
  let cx = 0, cy = 0;
  for (const [x, y] of pts) {
    cx += x;
    cy += y;
  }
  cx /= pts.length;
  cy /= pts.length;
  let reach = 1;
  for (const [x, y] of pts) reach = Math.max(reach, Math.ceil(Math.hypot(x - cx, y - cy)) + 1);
  const at = (deg: number) => sharpness(pts, cx, cy, (deg * Math.PI) / 180, reach);
  const scores = new Map<number, [number, number]>();
  for (let d = -MAX_ANGLE; d <= MAX_ANGLE; d++) scores.set(d, at(d));
  // For each profile (columns, rows): its sharpest angle, how much sharper than upright, and
  // whether that is a real peak (clearly above the angles 5 degrees either side).
  let bestDeg = 0, gain = 1, axis = 0;
  for (const k of [0, 1]) {
    let d0 = 0;
    for (let d = -MAX_ANGLE; d <= MAX_ANGLE; d++) if (scores.get(d)![k] > scores.get(d0)![k]) d0 = d;
    const g = scores.get(d0)![k] / Math.max(1e-12, scores.get(0)![k]);
    const side = Math.max(scores.get(Math.max(-MAX_ANGLE, d0 - 5))![k], scores.get(Math.min(MAX_ANGLE, d0 + 5))![k]);
    if (d0 !== 0 && scores.get(d0)![k] < 1.03 * side) continue;
    if (g > gain) {
      gain = g;
      bestDeg = d0;
      axis = k;
    }
  }
  let best = scores.get(bestDeg)![axis];
  const base = scores.get(0)![axis];
  for (let d = bestDeg - 0.75; d <= bestDeg + 0.75; d += 0.25) {
    const v = at(d)[axis];
    if (v > best) {
      best = v;
      bestDeg = d;
    }
  }
  const angle = (bestDeg * Math.PI) / 180;
  gain = base > 0 ? best / base : 1;
  const tilted = Math.abs(angle) >= MIN_ANGLE && gain >= MIN_GAIN;
  // An upright line can still curve (a caption along an arc has no single tilt), and an upright
  // card or letter still has printed lines to letter on.
  const frame = frameOf(pts, cx, cy, tilted ? angle : 0, tilted ? gain : 1, charSize);
  return tilted || frame.bow !== undefined || frame.lines ? frame : undefined;
}

/**
 * Printed lines of a horizontal block in its frame: bands of the ink's profile across the lines,
 * ruby (bands under half the usual height) dropped. Only for a left-aligned block of at least two
 * wide lines, the layout of a card, a form or a letter; a centred caption is not one.
 */
function printedLines(us: number[], vs: number[]): Slant["lines"] {
  const v0 = Math.floor(Math.min(...vs)), v1 = Math.ceil(Math.max(...vs));
  const hist = new Float64Array(v1 - v0 + 1);
  for (const v of vs) hist[Math.round(v) - v0]++;
  const smooth = hist.map((_, i) => (hist[i - 1] ?? 0) / 4 + hist[i] / 2 + (hist[i + 1] ?? 0) / 4);
  const peak = Math.max(...smooth);
  const runs: Array<[number, number]> = [];
  for (let i = 0; i < smooth.length; i++) {
    if (smooth[i] <= 0.12 * peak) continue;
    const last = runs[runs.length - 1];
    if (last && i - last[1] <= 2) last[1] = i;
    else runs.push([i, i]);
  }
  if (runs.length < 2) return undefined;
  const heights = runs.map(([a, b]) => b - a + 1).sort((a, b) => a - b);
  const typical = heights[Math.floor(heights.length / 2)];
  const bands = runs.filter(([a, b]) => b - a + 1 >= 0.5 * typical);
  if (bands.length < 2) return undefined;
  const lines = bands.map(([a, b]) => {
    const inBand = us.filter((_, i) => vs[i] >= v0 + a - 0.5 && vs[i] <= v0 + b + 0.5).sort((x, y) => x - y);
    return { u0: inBand[Math.floor(0.02 * inBand.length)], u1: inBand[Math.floor(0.98 * (inBand.length - 1))], v0: v0 + a, v1: v0 + b + 1 };
  });
  // Wide lines, starting at the same place.
  if (lines.some((l) => l.u1 - l.u0 < 2.5 * (l.v1 - l.v0))) return undefined;
  const starts = lines.map((l) => l.u0).sort((a, b) => a - b);
  const aligned = lines.filter((l) => l.u0 - starts[0] <= 0.8 * typical).length;
  if (aligned < Math.max(2, Math.ceil(0.75 * lines.length))) return undefined;
  return lines;
}

/** Block frame at `angle`: robust extents, and the bow of a single line or column. */
function frameOf(pts: Array<[number, number]>, cx: number, cy: number, angle: number, gain: number, charSize: number): Slant {
  const c = Math.cos(angle), s = Math.sin(angle);
  const us: number[] = [], vs: number[] = [];
  for (const [x, y] of pts) {
    const dx = x - cx, dy = y - cy;
    us.push(dx * c + dy * s);
    vs.push(-dx * s + dy * c);
  }
  const q = (v: number[], f: number) => [...v].sort((a, b) => a - b)[Math.min(v.length - 1, Math.max(0, Math.floor(f * v.length)))];
  const u0 = q(us, 0.01), u1 = q(us, 0.99), v0 = q(vs, 0.01), v1 = q(vs, 0.99);
  const w = u1 - u0 + 2, h = v1 - v0 + 2;
  // Centre of the extents, back on the page.
  const mu = (u0 + u1) / 2, mv = (v0 + v1) / 2;
  const slant: Slant = { angle, cx: cx + mu * c - mv * s, cy: cy + mu * s + mv * c, w, h, gain, column: h > w };
  const along = slant.column ? vs : us;
  const across = slant.column ? us : vs;
  const bow = arcBow(along, across, slant.column ? v0 : u0, slant.column ? h : w, slant.column ? mu : mv, charSize);
  if (bow !== undefined) slant.bow = bow;
  if (!slant.column && bow === undefined) {
    const lines = printedLines(us, vs);
    // Relative to the frame centre, like the rest of the frame.
    if (lines) slant.lines = lines.map((l) => ({ u0: l.u0 - mu, u1: l.u1 - mu, v0: l.v0 - mv, v1: l.v1 - mv }));
  }
  return slant;
}

/**
 * For one line of glyphs: fit the centre of the ink across the line, bin by bin along it, to a
 * parabola through the chord. Returns the bow (in px, at the middle) when the line clearly
 * curves: at least 0.35 of a glyph, the parabola fitting much better than a straight line, and
 * the ink no thicker than one glyph around the curve.
 */
export function arcBow(along: number[], across: number[], start: number, length: number, mid: number, charSize: number): number | undefined {
  if (length < 4 * charSize) return undefined;
  const bin = Math.max(2, charSize / 2);
  const bins = new Map<number, number[]>();
  along.forEach((a, i) => {
    const k = Math.floor((a - start) / bin);
    if (!bins.has(k)) bins.set(k, []);
    bins.get(k)!.push(across[i] - mid);
  });
  const xs: number[] = [], ys: number[] = [];
  for (const [k, v] of bins) {
    if (v.length < 3) continue;
    const t = (2 * ((k + 0.5) * bin)) / length - 1;
    xs.push(t);
    ys.push([...v].sort((a, b) => a - b)[Math.floor(v.length / 2)]);
  }
  if (xs.length < 6) return undefined;
  // Least squares for y = a + b t + c t^2, and for the straight line y = a + b t.
  const quad = lsq(xs, ys, 3);
  const line = lsq(xs, ys, 2);
  if (!quad || !line) return undefined;
  const bow = -quad.coef[2]; // y(t) = a + b t + c t^2: the middle sits -c above the chord through the ends
  if (Math.abs(bow) < 0.35 * charSize) return undefined;
  if (quad.rms > 0.3 * charSize || line.rms < 1.8 * quad.rms) return undefined;
  // Thickness around the curve: one glyph, not a block of several lines.
  const spread = across.map((v, i) => {
    const t = (2 * (along[i] - start)) / length - 1;
    return Math.abs(v - mid - (quad.coef[0] + quad.coef[1] * t + quad.coef[2] * t * t));
  });
  const p90 = [...spread].sort((a, b) => a - b)[Math.floor(0.9 * spread.length)];
  if (p90 > 0.85 * charSize) return undefined;
  return bow;
}

function lsq(xs: number[], ys: number[], k: 2 | 3): { coef: number[]; rms: number } | undefined {
  // Normal equations, solved by Gaussian elimination (k <= 3).
  const A = Array.from({ length: k }, () => new Array<number>(k + 1).fill(0));
  xs.forEach((x, i) => {
    const row = [1, x, x * x].slice(0, k);
    for (let r = 0; r < k; r++) {
      for (let c = 0; c < k; c++) A[r][c] += row[r] * row[c];
      A[r][k] += row[r] * ys[i];
    }
  });
  for (let c = 0; c < k; c++) {
    let p = c;
    for (let r = c + 1; r < k; r++) if (Math.abs(A[r][c]) > Math.abs(A[p][c])) p = r;
    if (Math.abs(A[p][c]) < 1e-9) return undefined;
    [A[c], A[p]] = [A[p], A[c]];
    for (let r = 0; r < k; r++) {
      if (r === c) continue;
      const f = A[r][c] / A[c][c];
      for (let j = c; j <= k; j++) A[r][j] -= f * A[c][j];
    }
  }
  const coef = A.map((row, i) => row[k] / row[i]);
  const rms = Math.sqrt(xs.reduce((a, x, i) => a + (ys[i] - (coef[0] + coef[1] * x + (k === 3 ? coef[2] * x * x : 0))) ** 2, 0) / xs.length);
  return { coef, rms };
}

/**
 * The frame cut back so it stops short of the pictures in `keep` (a photo on a card): a picture
 * running down one side of the frame cuts its width, one along the top or bottom cuts its height,
 * and the printed lines are shortened to match. Unchanged when nothing overlaps.
 */
export function avoidPictures(s: Slant, keep: Box[], gap = 4): Slant {
  return avoidAreas(s, keep.map((k) => [[k.x, k.y], [k.x + k.w, k.y], [k.x + k.w, k.y + k.h], [k.x, k.y + k.h]]), gap);
}

/** Corners of a slant frame on the page. */
export function frameQuad(s: Slant): Array<[number, number]> {
  const c = Math.cos(s.angle), sn = Math.sin(s.angle);
  return [[-s.w / 2, -s.h / 2], [s.w / 2, -s.h / 2], [s.w / 2, s.h / 2], [-s.w / 2, s.h / 2]].map(([u, v]) => [s.cx + u * c - v * sn, s.cy + u * sn + v * c]);
}

/** Is the page point inside the slant frame? */
export function frameHas(s: Slant, x: number, y: number): boolean {
  const c = Math.cos(s.angle), sn = Math.sin(s.angle);
  const dx = x - s.cx, dy = y - s.cy;
  return Math.abs(dx * c + dy * sn) <= s.w / 2 && Math.abs(-dx * sn + dy * c) <= s.h / 2;
}

/** `avoidPictures` for any convex areas given by their corners (another tilted block, a picture). */
export function avoidAreas(s: Slant, keep: Array<Array<[number, number]>>, gap = 4): Slant {
  const c = Math.cos(s.angle), sn = Math.sin(s.angle);
  let u0 = -s.w / 2, u1 = s.w / 2, v0 = -s.h / 2, v1 = s.h / 2;
  for (const k of keep) {
    // The area in frame coordinates.
    const pts = k.map(([x, y]) => {
      const dx = x - s.cx, dy = y - s.cy;
      return [dx * c + dy * sn, -dx * sn + dy * c];
    });
    const ku0 = Math.min(...pts.map((p) => p[0])), ku1 = Math.max(...pts.map((p) => p[0]));
    const kv0 = Math.min(...pts.map((p) => p[1])), kv1 = Math.max(...pts.map((p) => p[1]));
    const du = Math.min(u1, ku1) - Math.max(u0, ku0), dv = Math.min(v1, kv1) - Math.max(v0, kv0);
    if (du <= 0 || dv <= 0) continue;
    // Cut from the side the area is on, across or along the lines, whichever keeps more room.
    const right = (ku0 + ku1) / 2 > (u0 + u1) / 2, below = (kv0 + kv1) / 2 > (v0 + v1) / 2;
    const nu0 = right ? u0 : Math.max(u0, ku1 + gap), nu1 = right ? Math.min(u1, ku0 - gap) : u1;
    const nv0 = below ? v0 : Math.max(v0, kv1 + gap), nv1 = below ? Math.min(v1, kv0 - gap) : v1;
    if ((nu1 - nu0) * (v1 - v0) >= (u1 - u0) * (nv1 - nv0)) [u0, u1] = [nu0, nu1];
    else [v0, v1] = [nv0, nv1];
  }
  if (u0 === -s.w / 2 && u1 === s.w / 2 && v0 === -s.h / 2 && v1 === s.h / 2) return s;
  if (u1 - u0 < 0.3 * s.w || v1 - v0 < 0.3 * s.h) return s;
  const mu = (u0 + u1) / 2, mv = (v0 + v1) / 2;
  const lines = s.lines
    ?.filter((l) => l.v1 > v0 && l.v0 < v1)
    .map((l) => ({ u0: Math.max(l.u0, u0) - mu, u1: Math.min(l.u1, u1) - mu, v0: l.v0 - mv, v1: l.v1 - mv }))
    .filter((l) => l.u1 - l.u0 > 2 * (l.v1 - l.v0));
  return { ...s, cx: s.cx + mu * c - mv * sn, cy: s.cy + mu * sn + mv * c, w: u1 - u0, h: v1 - v0, lines: lines && lines.length >= 2 ? lines : undefined };
}

/**
 * Where each character of a one-line text sits along the arc `across = bow * (1 - t^2)` in a frame
 * `length` long (t = 2 * along / length - 1), centred on the frame, with its rotation. `widths`
 * are the character advances; the line is centred on the arc's middle by arc length.
 */
export function placeOnArc(widths: number[], length: number, bow: number): Array<{ along: number; across: number; angle: number }> {
  const steps = 400;
  const pos: number[] = [0];
  const y = (t: number) => bow * (1 - t * t);
  // Arc length table over the frame.
  for (let i = 1; i <= steps; i++) {
    const t0 = -1 + (2 * (i - 1)) / steps, t1 = -1 + (2 * i) / steps;
    const dx = (length * (t1 - t0)) / 2;
    pos.push(pos[i - 1] + Math.hypot(dx, y(t1) - y(t0)));
  }
  const total = widths.reduce((a, b) => a + b, 0);
  let s = pos[steps] / 2 - total / 2;
  const out: Array<{ along: number; across: number; angle: number }> = [];
  for (const wd of widths) {
    const target = s + wd / 2;
    let i = 1;
    while (i < steps && pos[i] < target) i++;
    const f = (target - pos[i - 1]) / Math.max(1e-6, pos[i] - pos[i - 1]);
    const t = -1 + (2 * (i - 1 + f)) / steps;
    // dy/d(along) = dy/dt * dt/d(along) = (-2 bow t) * (2 / length)
    out.push({ along: ((t + 1) * length) / 2, across: y(t), angle: Math.atan((-4 * bow * t) / length) });
    s += wd;
  }
  return out;
}

/** Length of the arc `across = bow * (1 - t^2)` over a frame `length` long. */
export function arcLength(length: number, bow: number): number {
  let total = 0;
  const steps = 200;
  for (let i = 1; i <= steps; i++) {
    const t0 = -1 + (2 * (i - 1)) / steps, t1 = -1 + (2 * i) / steps;
    total += Math.hypot((length * (t1 - t0)) / 2, bow * (1 - t1 * t1) - bow * (1 - t0 * t0));
  }
  return total;
}
