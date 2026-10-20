/**
 * Steps around the inpainting model, learned from manga-image-translator's pipeline and from
 * where our per-region redraw still failed on the team pages:
 * - the model never sees text it should not copy: every hole on the page is masked when any one
 *   of them is redrawn (they mask all text before one whole-page pass);
 * - a hole in plain paper keeps the paper colour: light smudges the model leaves there are
 *   snapped to the paper, while dark strokes it continues (an outline, a line) stay;
 * - the lettering takes the source text's colours (they read fg/bg colours per text block and
 *   outline the translation with the background colour).
 */
import type { Box, InpaintJob, RGB, RGBAImage } from "@lt/core";

const lumOf = (d: ArrayLike<number>, i: number) => 0.299 * d[i] + 0.587 * d[i + 1] + 0.114 * d[i + 2];
const median = (v: number[]) => {
  if (!v.length) return NaN;
  const s = [...v].sort((a, b) => a - b);
  return s[Math.floor(s.length / 2)];
};

/**
 * Last resort, closer to manga-image-translator, which redraws every text pixel its mask finds
 * whatever its thickness: a whole-box job (`rectJob`, filled shapes kept out) plus every kept-out
 * piece inside the boxes that is no bigger than a glyph (1.3 x `charSize` each way). Bold
 * lettering (a heavy title, a bold shout in a balloon) has strokes as thick as an eye, so it was
 * kept as art and the model drew it back in; a photo, a face or a long art line stays protected.
 * Used only when the whole-box redraw still left glyph ink.
 */
export function wholeBoxes(rectJob: InpaintJob, members: Box[], charSize: number, pad = 3): InpaintJob {
  const { crop } = rectJob;
  const W = crop.w, H = crop.h;
  const inBox = new Uint8Array(W * H);
  for (const m of members) {
    const x0 = Math.max(0, Math.floor(m.x - pad - crop.x)), y0 = Math.max(0, Math.floor(m.y - pad - crop.y));
    const x1 = Math.min(W, Math.ceil(m.x + m.w + pad - crop.x)), y1 = Math.min(H, Math.ceil(m.y + m.h + pad - crop.y));
    for (let y = y0; y < y1; y++) inBox.fill(1, y * W + x0, y * W + x1);
  }
  const hole = Uint8Array.from(rectJob.hole);
  const seen = new Uint8Array(W * H);
  const limit = 1.3 * charSize;
  for (let p0 = 0; p0 < W * H; p0++) {
    if (!inBox[p0] || rectJob.hole[p0] || seen[p0]) continue;
    // One kept-out piece (4-connected), within the boxes.
    const piece: number[] = [p0];
    seen[p0] = 1;
    let x0 = W, y0 = H, x1 = 0, y1 = 0;
    let edge = false;
    for (let k = 0; k < piece.length; k++) {
      const p = piece[k];
      const x = p % W, y = (p - x) / W;
      x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
      for (const q of [x > 0 ? p - 1 : -1, x < W - 1 ? p + 1 : -1, y > 0 ? p - W : -1, y < H - 1 ? p + W : -1]) {
        if (q < 0 || !inBox[q]) {
          edge = true;
          continue;
        }
        if (seen[q] || rectJob.hole[q]) continue;
        seen[q] = 1;
        piece.push(q);
      }
    }
    // Glyph-sized, or a few bold glyphs fused together that lie wholly inside the text boxes.
    const span = Math.max(x1 - x0 + 1, y1 - y0 + 1);
    if ((x1 - x0 + 1 <= limit && y1 - y0 + 1 <= limit) || (!edge && span <= 2 * charSize)) for (const p of piece) hole[p] = 1;
  }
  let n = 0;
  for (const v of hole) n += v;
  return { ...rectJob, hole, rect: true, coverage: n / Math.max(1, members.reduce((a, m) => a + m.w * m.h, 0)) };
}

/**
 * `job` without the pictures inside its boxes: a photo on an ID card, a portrait in a frame, a
 * screen. A loose text box often takes one in, and a whole-box redraw then wipes a face. A
 * picture is a connected area where three quarters of the pixels within 0.75 glyph are mid-tones
 * (not paper, not ink), at least 1.5 glyphs across both ways, in which the glyph pass (`glyphs`)
 * found few strokes. Text over screentone has strokes there, so it is still redrawn. The page
 * bounds of each picture kept are pushed to `found`, so lettering can keep off it too.
 */
export function keepPictures(full: RGBAImage, job: InpaintJob, glyphs: InpaintJob, charSize: number, found: Box[] = []): InpaintJob {
  const { crop } = job;
  const W = crop.w, H = crop.h;
  const glyphAt = (p: number) => {
    const x = (p % W) + crop.x - glyphs.crop.x, y = Math.floor(p / W) + crop.y - glyphs.crop.y;
    return x >= 0 && y >= 0 && x < glyphs.crop.w && y < glyphs.crop.h && glyphs.hole[y * glyphs.crop.w + x] === 1;
  };
  // Integral images of mid-tone pixels and of glyph-pass strokes.
  const S = new Int32Array((W + 1) * (H + 1));
  const G = new Int32Array((W + 1) * (H + 1));
  for (let y = 0; y < H; y++) {
    let row = 0, grow = 0;
    for (let x = 0; x < W; x++) {
      const l = lumOf(full.data, ((crop.y + y) * full.width + crop.x + x) * 4);
      row += l >= 50 && l <= 205 ? 1 : 0;
      grow += glyphAt(y * W + x) ? 1 : 0;
      S[(y + 1) * (W + 1) + x + 1] = S[y * (W + 1) + x + 1] + row;
      G[(y + 1) * (W + 1) + x + 1] = G[y * (W + 1) + x + 1] + grow;
    }
  }
  const r = Math.max(4, Math.round(0.75 * charSize));
  const cand = new Uint8Array(W * H);
  const sum = (T: Int32Array, x0: number, y0: number, x1: number, y1: number) => T[y1 * (W + 1) + x1] - T[y0 * (W + 1) + x1] - T[y1 * (W + 1) + x0] + T[y0 * (W + 1) + x0];
  for (let y = 0; y < H; y++)
    for (let x = 0; x < W; x++) {
      const x0 = Math.max(0, x - r), x1 = Math.min(W, x + r + 1), y0 = Math.max(0, y - r), y1 = Math.min(H, y + r + 1);
      const n = (x1 - x0) * (y1 - y0);
      // Dense small print is grey on average too (up to ~70% mid-tones around a point on the GT
      // card); a photo is 80-100%, and the glyph pass takes its fur or hair for strokes in places.
      if (sum(S, x0, y0, x1, y1) >= 0.75 * n && sum(G, x0, y0, x1, y1) <= 0.3 * n) cand[y * W + x] = 1;
    }
  const hole = Uint8Array.from(job.hole);
  const seen = new Uint8Array(W * H);
  const minSide = 1.5 * charSize;
  let kept = 0;
  for (let p0 = 0; p0 < W * H; p0++) {
    if (!cand[p0] || seen[p0]) continue;
    const comp = [p0];
    seen[p0] = 1;
    let x0 = W, y0 = H, x1 = 0, y1 = 0, strokes = 0;
    for (let k = 0; k < comp.length; k++) {
      const p = comp[k];
      const x = p % W, y = (p - x) / W;
      x0 = Math.min(x0, x); x1 = Math.max(x1, x); y0 = Math.min(y0, y); y1 = Math.max(y1, y);
      if (glyphAt(p)) strokes++;
      for (const q of [x > 0 ? p - 1 : -1, x < W - 1 ? p + 1 : -1, y > 0 ? p - W : -1, y < H - 1 ? p + W : -1]) {
        if (q < 0 || seen[q] || !cand[q]) continue;
        seen[q] = 1;
        comp.push(q);
      }
    }
    if (x1 - x0 + 1 < minSide || y1 - y0 + 1 < minSide || strokes > 0.2 * comp.length) continue;
    // The picture with what it encloses (an eye, a dark nose are not mid-tones), a little wider
    // (the window test shrinks it at its edges).
    const bw = x1 - x0 + 1, bh = y1 - y0 + 1;
    const pic = new Uint8Array(bw * bh);
    for (const p of comp) pic[(Math.floor(p / W) - y0) * bw + (p % W) - x0] = 1;
    const outside = new Uint8Array(bw * bh);
    const queue: number[] = [];
    for (let x = 0; x < bw; x++) for (const y of [0, bh - 1]) if (!pic[y * bw + x] && !outside[y * bw + x]) (outside[y * bw + x] = 1), queue.push(y * bw + x);
    for (let y = 0; y < bh; y++) for (const x of [0, bw - 1]) if (!pic[y * bw + x] && !outside[y * bw + x]) (outside[y * bw + x] = 1), queue.push(y * bw + x);
    for (let k = 0; k < queue.length; k++) {
      const q = queue[k];
      const x = q % bw, y = (q - x) / bw;
      for (const n of [x > 0 ? q - 1 : -1, x < bw - 1 ? q + 1 : -1, y > 0 ? q - bw : -1, y < bh - 1 ? q + bw : -1]) {
        if (n < 0 || pic[n] || outside[n]) continue;
        outside[n] = 1;
        queue.push(n);
      }
    }
    const grow = Math.max(1, Math.round(0.3 * charSize));
    const filled = new Uint8Array(W * H);
    for (let y = 0; y < bh; y++) for (let x = 0; x < bw; x++) if (!outside[y * bw + x]) filled[(y0 + y) * W + x0 + x] = 1;
    const wide = dilate(filled, W, H, grow);
    found.push({ x: crop.x + x0 - grow, y: crop.y + y0 - grow, w: bw + 2 * grow, h: bh + 2 * grow });
    for (let p = 0; p < W * H; p++) if (wide[p] && hole[p]) {
      hole[p] = 0;
      kept++;
    }
  }
  return kept ? { ...job, hole } : job;
}

/**
 * `job` without the text boxes of other regions (outside its own boxes): two balloons drawn
 * overlapping each erase their own letters, and a hole reaching into the neighbour leaves model
 * texture there that its own erase then counts as leftover ink. A sound effect kept as art next to
 * the text stays untouched too.
 */
export function clearOthers(job: InpaintJob, own: Box[], others: Box[], pad = 2): InpaintJob {
  const { crop } = job;
  const near = others.filter((o) => o.x < crop.x + crop.w && o.y < crop.y + crop.h && o.x + o.w > crop.x && o.y + o.h > crop.y);
  if (!near.length) return job;
  const inside = (bs: Box[], x: number, y: number, p: number) => bs.some((b) => x >= b.x - p && y >= b.y - p && x < b.x + b.w + p && y < b.y + b.h + p);
  let hole: Uint8Array | undefined;
  for (let p = 0; p < job.hole.length; p++) {
    if (!job.hole[p]) continue;
    const x = crop.x + (p % crop.w), y = crop.y + Math.floor(p / crop.w);
    if (!inside(near, x, y, 0) || inside(own, x, y, pad)) continue;
    hole ??= Uint8Array.from(job.hole);
    hole[p] = 0;
  }
  return hole ? { ...job, hole } : job;
}

/** `job` with every other pending hole that falls in its crop added to the model's mask. */
export function withNeighbours(job: InpaintJob, others: InpaintJob[]): InpaintJob {
  const { crop } = job;
  let hole: Uint8Array | undefined;
  for (const o of others) {
    const x0 = Math.max(crop.x, o.crop.x), y0 = Math.max(crop.y, o.crop.y);
    const x1 = Math.min(crop.x + crop.w, o.crop.x + o.crop.w), y1 = Math.min(crop.y + crop.h, o.crop.y + o.crop.h);
    if (x1 <= x0 || y1 <= y0) continue;
    for (let y = y0; y < y1; y++)
      for (let x = x0; x < x1; x++) {
        if (!o.hole[(y - o.crop.y) * o.crop.w + (x - o.crop.x)]) continue;
        hole ??= Uint8Array.from(job.hole);
        hole[(y - crop.y) * crop.w + (x - crop.x)] = 1;
      }
  }
  return hole ? { ...job, hole } : job;
}

function dilate(mask: Uint8Array, w: number, h: number, r: number): Uint8Array {
  // Separable square dilation (Chebyshev radius r).
  const tmp = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    let last = -Infinity;
    for (let x = 0; x < w; x++) {
      if (mask[y * w + x]) last = x;
      if (x - last <= r) tmp[y * w + x] = 1;
    }
    let next = Infinity;
    for (let x = w - 1; x >= 0; x--) {
      if (mask[y * w + x]) next = x;
      if (next - x <= r) tmp[y * w + x] = 1;
    }
  }
  const out = new Uint8Array(w * h);
  for (let x = 0; x < w; x++) {
    let last = -Infinity;
    for (let y = 0; y < h; y++) {
      if (tmp[y * w + x]) last = y;
      if (y - last <= r) out[y * w + x] = 1;
    }
    let next = Infinity;
    for (let y = h - 1; y >= 0; y--) {
      if (tmp[y * w + x]) next = y;
      if (next - y <= r) out[y * w + x] = 1;
    }
  }
  return out;
}

function erode(mask: Uint8Array, w: number, h: number, r: number): Uint8Array {
  const inv = new Uint8Array(w * h);
  for (let p = 0; p < inv.length; p++) inv[p] = mask[p] ? 0 : 1;
  // The crop edge counts as outside the hole.
  for (let x = 0; x < w; x++) inv[x] = inv[(h - 1) * w + x] = 1;
  for (let y = 0; y < h; y++) inv[y * w] = inv[y * w + w - 1] = 1;
  const grown = dilate(inv, w, h, r);
  const out = new Uint8Array(w * h);
  for (let p = 0; p < out.length; p++) out[p] = mask[p] && !grown[p] ? 1 : 0;
  return out;
}

/** Ring share that must sit close to one light paper tone for a hole to count as plain paper. */
const PAPER_SHARE = 0.85;
const PAPER_MIN_LUM = 200;

/**
 * A hole in plain paper (the ring around it, outside every pending hole, is one light tone):
 * reconstructed pixels lighter than `lum(paper) - 90` become the paper colour, darker ones (a
 * line the model continued) stay. Returns how many pixels were snapped.
 */
export function snapToPaper(full: RGBAImage, result: Uint8Array, job: InpaintJob, masked: InpaintJob = job): number {
  const { crop, hole } = job;
  const n = crop.w * crop.h;
  const ring = dilate(hole, crop.w, crop.h, 6);
  const lums: number[] = [];
  const idx: number[] = [];
  for (let p = 0; p < n; p++) {
    if (!ring[p] || masked.hole[p]) continue;
    const x = p % crop.w;
    const i = ((crop.y + (p - x) / crop.w) * full.width + crop.x + x) * 4;
    lums.push(lumOf(full.data, i));
    idx.push(i);
  }
  if (lums.length < 20) return 0;
  const m = median(lums);
  if (m < PAPER_MIN_LUM) return 0;
  const near = lums.filter((v) => Math.abs(v - m) <= 24).length;
  if (near / lums.length < PAPER_SHARE) return 0;
  const rgb: number[][] = [[], [], []];
  idx.forEach((i, k) => {
    if (Math.abs(lums[k] - m) > 24) return;
    for (let c = 0; c < 3; c++) rgb[c].push(full.data[i + c]);
  });
  const paper = rgb.map(median);
  let snapped = 0;
  for (let p = 0; p < n; p++) {
    if (!hole[p]) continue;
    const v = 0.299 * result[p] + 0.587 * result[n + p] + 0.114 * result[2 * n + p];
    if (v < m - 90) continue;
    result[p] = paper[0];
    result[n + p] = paper[1];
    result[2 * n + p] = paper[2];
    snapped++;
  }
  return snapped;
}

/**
 * Text set on plain paper inside its own boxes (a caption strip between two panels, a balloon
 * cut open by the panel edge), when redrawing still left glyph ink. The ring around the hole holds
 * art, so `snapToPaper` does not apply and the model fills the strip with the art around it, yet
 * behind the letters there was only paper. When the core of the boxes outside the glyph hole
 * (`glyphs`), stroke edges left out, is one light tone, each box is rebuilt from the source like an
 * erased balloon: ink reaching the box edge (a border rule, an outline, art passing through) and
 * solid shapes (an eye) keep their source pixels; everything else becomes that paper, i.e. the
 * letters, strokes the masks kept as hatching and the smudges of the model. Returns `job` with its
 * hole changed to match, or `job` itself when the ground is not plain paper.
 */
export function snapBoxesToPaper(full: RGBAImage, result: Uint8Array, job: InpaintJob, glyphs: InpaintJob, members: Box[], charSize: number): InpaintJob {
  const { crop } = job;
  const n = crop.w * crop.h;
  const lumXY = (x: number, y: number) => lumOf(full.data, (y * full.width + x) * 4);
  const glyphAt = (x: number, y: number) => {
    const gx = x - glyphs.crop.x, gy = y - glyphs.crop.y;
    return gx >= 0 && gy >= 0 && gx < glyphs.crop.w && gy < glyphs.crop.h && glyphs.hole[gy * glyphs.crop.w + gx] === 1;
  };
  // The ground behind the letters: light pixels in the core of the boxes, away from any stroke
  // (the glyph hole, dark pixels and their antialiased edges). Dense text leaves little of it, so
  // its being one light tone is what counts.
  const lums: number[] = [];
  const idx: number[] = [];
  let total = 0;
  for (const m of members) {
    const ex = Math.min(0.15 * m.w, 0.15 * m.h), ey = 0.2 * m.h;
    for (let y = Math.max(1, Math.round(m.y + ey)); y < Math.min(full.height - 1, Math.round(m.y + m.h - ey)); y++)
      for (let x = Math.max(1, Math.round(m.x + ex)); x < Math.min(full.width - 1, Math.round(m.x + m.w - ex)); x++) {
        total++;
        if (glyphAt(x, y) || lumXY(x, y) < 120) continue;
        let edge = false;
        for (let dy = -1; dy <= 1 && !edge; dy++) for (let dx = -1; dx <= 1 && !edge; dx++) if (lumXY(x + dx, y + dy) < 160) edge = true;
        if (edge) continue;
        lums.push(lumXY(x, y));
        idx.push((y * full.width + x) * 4);
      }
  }
  if (lums.length < 50 || lums.length < 0.12 * total) return job;
  const m = median(lums);
  if (m < PAPER_MIN_LUM || lums.filter((v) => Math.abs(v - m) <= 24).length / lums.length < PAPER_SHARE) return job;
  const near = idx.filter((_, k) => Math.abs(lums[k] - m) <= 24);
  const paper = [0, 1, 2].map((c) => median(near.map((i) => full.data[i + c])));
  const W = crop.w, H = crop.h;
  const hole = Uint8Array.from(job.hole);
  const long = 1.6 * charSize;
  for (const mb of members) {
    // A tight detector box cuts the first and last glyph of a line: reach a little past its ends.
    const pad = Math.round(0.3 * charSize);
    const across = mb.w >= mb.h;
    const x0 = Math.max(0, Math.round(mb.x) - crop.x - (across ? pad : 0)), y0 = Math.max(0, Math.round(mb.y) - crop.y - (across ? 0 : pad));
    const x1 = Math.min(W, Math.round(mb.x + mb.w) - crop.x + (across ? pad : 0)), y1 = Math.min(H, Math.round(mb.y + mb.h) - crop.y + (across ? 0 : pad));
    if (x1 <= x0 || y1 <= y0) continue;
    const bw = x1 - x0, bh = y1 - y0;
    const dark = (qx: number, qy: number) => lumXY(crop.x + x0 + qx, crop.y + y0 + qy) < 110;
    // The core of the box (where the letters are), in box coordinates.
    const ex = Math.min(0.15 * mb.w, 0.15 * mb.h), ey = 0.2 * mb.h;
    const cx0 = Math.round(mb.x) - crop.x - x0 + ex, cx1 = Math.round(mb.x + mb.w) - crop.x - x0 - ex;
    const cy0 = Math.round(mb.y) - crop.y - y0 + ey, cy1 = Math.round(mb.y + mb.h) - crop.y - y0 - ey;
    const inCore = (qx: number, qy: number) => qx >= cx0 && qx < cx1 && qy >= cy0 && qy < cy1;
    // Length of the straight dark run through a pixel, across and down.
    const run = (qx: number, qy: number) => {
      let a = 1, b = 1;
      for (let x = qx - 1; x >= 0 && dark(x, qy); x--) a++;
      for (let x = qx + 1; x < bw && dark(x, qy); x++) a++;
      for (let y = qy - 1; y >= 0 && dark(qx, y); y--) b++;
      for (let y = qy + 1; y < bh && dark(qx, y); y++) b++;
      return Math.max(a, b);
    };
    const keep = new Uint8Array(bw * bh);
    const seen = new Uint8Array(bw * bh);
    for (let q0 = 0; q0 < bw * bh; q0++) {
      if (seen[q0] || !dark(q0 % bw, Math.floor(q0 / bw))) continue;
      const piece = [q0];
      seen[q0] = 1;
      let touches = false, px0 = bw, py0 = bh, px1 = 0, py1 = 0;
      for (let k = 0; k < piece.length; k++) {
        const q = piece[k];
        const qx = q % bw, qy = (q - qx) / bw;
        px0 = Math.min(px0, qx); px1 = Math.max(px1, qx); py0 = Math.min(py0, qy); py1 = Math.max(py1, qy);
        if (qx === 0 || qy === 0 || qx === bw - 1 || qy === bh - 1) touches = true;
        for (let dy = -1; dy <= 1; dy++)
          for (let dx = -1; dx <= 1; dx++) {
            const nx = qx + dx, ny = qy + dy;
            if (nx < 0 || ny < 0 || nx >= bw || ny >= bh) continue;
            const nq = ny * bw + nx;
            if (seen[nq] || !dark(nx, ny)) continue;
            seen[nq] = 1;
            piece.push(nq);
          }
      }
      const pw = px1 - px0 + 1, ph = py1 - py0 + 1;
      const solid = piece.length >= 0.55 * pw * ph && Math.min(pw, ph) >= Math.max(3, 0.25 * charSize);
      if (solid) for (const q of piece) keep[q] = 1;
      else if (touches && Math.max(pw, ph) > long)
        // A rule, an outline or art running through. Letters touching it in the core are not part of it.
        for (const q of piece) {
          const qx = q % bw, qy = (q - qx) / bw;
          if (!inCore(qx, qy) || run(qx, qy) > long) keep[q] = 1;
        }
    }
    // Antialiased rims of what is kept stay too.
    const rim = dilate(keep, bw, bh, 1);
    for (let qy = 0; qy < bh; qy++)
      for (let qx = 0; qx < bw; qx++) {
        const q = qy * bw + qx;
        const p = (y0 + qy) * W + x0 + qx;
        if (keep[q] || (rim[q] && lumXY(crop.x + x0 + qx, crop.y + y0 + qy) < m - 24)) {
          hole[p] = 0;
          continue;
        }
        hole[p] = 1;
        result[p] = paper[0];
        result[n + p] = paper[1];
        result[2 * n + p] = paper[2];
      }
  }
  return { ...job, hole };
}

/**
 * Ink colour of the text in `members`: the smaller side of an Otsu split of the boxes' cores
 * (dark letters on paper, light letters on a dark ground), and of that side the half furthest
 * from the split, i.e. the stroke centres, not their antialiased edges. Undefined when the boxes
 * hold too little to tell.
 */
export function inkOf(full: RGBAImage, members: Box[]): RGB | undefined {
  const px: { l: number; i: number }[] = [];
  const hist = new Array<number>(256).fill(0);
  for (const m of members) {
    const x0 = Math.max(0, Math.round(m.x + 0.1 * m.w)), x1 = Math.min(full.width, Math.round(m.x + 0.9 * m.w));
    const y0 = Math.max(0, Math.round(m.y + 0.1 * m.h)), y1 = Math.min(full.height, Math.round(m.y + 0.9 * m.h));
    for (let y = y0; y < y1; y++)
      for (let x = x0; x < x1; x++) {
        const i = (y * full.width + x) * 4;
        const l = lumOf(full.data, i);
        px.push({ l, i });
        hist[Math.round(l)]++;
      }
  }
  if (px.length < 50) return undefined;
  let sum = 0;
  for (let v = 0; v < 256; v++) sum += v * hist[v];
  let sumB = 0, wB = 0, best = -1, t = 127;
  for (let v = 0; v < 256; v++) {
    wB += hist[v];
    if (!wB || wB === px.length) continue;
    sumB += v * hist[v];
    const between = wB * (px.length - wB) * (sumB / wB - (sum - sumB) / (px.length - wB)) ** 2;
    if (between > best) {
      best = between;
      t = v;
    }
  }
  const dark = px.filter((p) => p.l <= t);
  const side = dark.length <= px.length / 2 ? dark : px.filter((p) => p.l > t);
  if (side.length < 20) return undefined;
  const strong = [...side].sort((a, b) => Math.abs(b.l - t) - Math.abs(a.l - t)).slice(0, Math.max(10, Math.ceil(side.length / 2)));
  return [0, 1, 2].map((c) => median(strong.map((s) => full.data[s.i + c]))) as RGB;
}

/**
 * Colours of the source lettering: the ink from the text boxes (`inkOf`), and from the pixels
 * under a glyph-shaped hole the tone around the strokes. The hole is the strokes grown by `grow`
 * px, so its margin (outside the core eroded by `grow`) is what surrounded them: a white or black
 * outline, or the background. `outline` is set only when that margin is one clean tone, not
 * screentone or hatching, and never for a whole-box hole.
 */
export function textColours(full: RGBAImage, job: InpaintJob, members: Box[], grow: number): { ink?: RGB; outline?: RGB } {
  const ink = inkOf(full, members);
  if (!ink) return {};
  if (job.rect) return { ink };
  const { crop, hole } = job;
  const core = erode(hole, crop.w, crop.h, Math.max(1, Math.round(grow)));
  const margin: { l: number; i: number }[] = [];
  for (let p = 0; p < hole.length; p++) {
    if (!hole[p] || core[p]) continue;
    const x = p % crop.w;
    const i = ((crop.y + (p - x) / crop.w) * full.width + crop.x + x) * 4;
    margin.push({ l: lumOf(full.data, i), i });
  }
  const inkL = lumOf(ink, 0);
  // Margin pixels that are clearly not ink (antialiased stroke edges are in between).
  const bg = margin.filter((m) => Math.abs(m.l - inkL) > 60);
  if (bg.length < 20) return { ink };
  const ls = bg.map((m) => m.l);
  const mean = ls.reduce((a, b) => a + b, 0) / ls.length;
  const std = Math.sqrt(ls.reduce((a, b) => a + (b - mean) ** 2, 0) / ls.length);
  if (std > 28) return { ink };
  const outline = [0, 1, 2].map((c) => median(bg.map((m) => full.data[m.i + c]))) as RGB;
  return { ink, outline };
}
