import {
  area,
  clampBox,
  eraseRegion,
  expand,
  intersect,
  glyphResidue,
  layoutText,
  sampleBorder,
  spansFromMask,
  type Box,
  type EraseReport,
  type LayoutArea,
  type RegionTranslation,
  type RGBAImage,
  type TextLayout,
  type TextRegion,
} from "@lt/core";

/** The subset of CanvasRenderingContext2D used here (browser and @napi-rs/canvas). */
export interface Ctx2D {
  font: string;
  fillStyle: unknown;
  strokeStyle: unknown;
  lineWidth: number;
  lineJoin: string;
  textAlign: string;
  textBaseline: string;
  globalAlpha: number;
  measureText(text: string): { width: number };
  fillText(text: string, x: number, y: number): void;
  strokeText(text: string, x: number, y: number): void;
  fillRect(x: number, y: number, w: number, h: number): void;
  strokeRect(x: number, y: number, w: number, h: number): void;
  getImageData(x: number, y: number, w: number, h: number): RGBAImage;
  putImageData(data: never, x: number, y: number): void;
  save(): void;
  restore(): void;
  translate(x: number, y: number): void;
  rotate(angle: number): void;
  drawImage(image: never, x: number, y: number): void;
}

export const LETTERING_FONT = "LT Lettering";
const FALLBACK = `"${LETTERING_FONT}", "Patrick Hand", "Segoe UI", sans-serif`;
const TRANSLATABLE = new Set(["dialogue", "thought", "narration", "sign"]);
/** Calibrated on the private GT pages: ordinary text <= 0.05, title logo 0.11, cover 0.21. */
const MAX_MID_FREE = 0.08;
const MAX_MID_BUBBLE = 0.12;
/** Glyph-shaped ink left in the text core above this share means lettering would sit on leftover Japanese. */
export const MAX_RESIDUE = 0.02;
const MARK_COLORS = ["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#008080", "#f032e6", "#9a6324"];

export interface RegionRender {
  id: string;
  /** needs-inpaint: the text sits on artwork and waits for a reconstructed background. */
  status: "lettered" | "needs-inpaint" | "sfx" | "skipped" | "empty";
  erase?: EraseReport;
  area?: LayoutArea;
  layout?: TextLayout;
  rotated?: boolean;
  /** Same as status === "needs-inpaint" (kept for callers that test a flag). */
  needsInpaint?: boolean;
  /** Share of ink left in the text core after erasure, measured before lettering. */
  residue?: number;
  /** Union of the drawn lines, page coordinates. */
  textBox?: Box;
  /** The text did not fit its area even at the minimum size. */
  overflow?: boolean;
}

/** Reconstructed artwork for one region (from MI-GAN), drawn before lettering. */
export interface PatchImage {
  x: number;
  y: number;
  image: unknown;
  /** Text boxes the reconstruction was built from; tighter than the region box for small text. */
  textBoxes?: Box[];
  /** Where the removed glyphs really sat; lettering starts there instead of a loose box. */
  textExtent?: Box;
}

export interface RenderOptions {
  fontFamily?: string;
  /** Only draw these ids (progressive rendering keeps the rest original). */
  only?: ReadonlySet<string>;
  /** Inpainted artwork per region id; text on art is lettered once its patch exists. */
  patches?: Record<string, PatchImage | undefined>;
}

/**
 * Draw outlined, numbered regions on a page that is already painted on `ctx`.
 * This is the image the vision model reads ("set of marks").
 */
export function drawMarks(ctx: Ctx2D, regions: TextRegion[], imgW: number): void {
  const label = Math.max(13, Math.round(imgW / 55));
  ctx.save();
  regions.forEach((r, i) => {
    const color = MARK_COLORS[i % MARK_COLORS.length];
    const b = expand(r.box, 3);
    ctx.strokeStyle = color;
    ctx.lineWidth = Math.max(2, Math.round(imgW / 400));
    ctx.strokeRect(b.x, b.y, b.w, b.h);
    ctx.font = `bold ${label}px sans-serif`;
    const tw = ctx.measureText(r.id).width + 6;
    const ly = b.y - label - 4 >= 0 ? b.y - label - 4 : b.y + b.h + 2;
    const lx = Math.max(0, Math.min(b.x + b.w - tw, imgW - tw));
    ctx.fillStyle = color;
    ctx.fillRect(lx, ly, tw, label + 4);
    ctx.fillStyle = "#ffffff";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.fillText(r.id, lx + 3, ly + 2);
  });
  ctx.restore();
}

interface Job {
  r: TextRegion;
  t: RegionTranslation;
  erase: EraseReport;
  onArt: boolean;
  residue: number;
  /** Where lettering starts for free text, when tighter than the region box. */
  seed?: Box;
}

/**
 * Erase the source text and letter the Vietnamese translation in place. The page must
 * already be painted on `ctx` (original pixels); "view original" is simply redrawing.
 * Nothing is lettered over leftover Japanese: a region whose erasure leaves ink behind
 * is restored and reported as needs-inpaint until a reconstructed patch arrives.
 */
export function renderTranslation(
  ctx: Ctx2D,
  size: { w: number; h: number },
  regions: TextRegion[],
  translations: Record<string, RegionTranslation | undefined>,
  opts: RenderOptions = {},
): RegionRender[] {
  const family = opts.fontFamily ? `"${opts.fontFamily}", ${FALLBACK}` : FALLBACK;
  const out: RegionRender[] = [];
  const eligible = (r: TextRegion, t: RegionTranslation | undefined): t is RegionTranslation =>
    !!t && !(opts.only && !opts.only.has(r.id)) && TRANSLATABLE.has(t.role) && !!t.vi;

  // 1) Reconstructed artwork goes down first, so erasure and lettering see it.
  const patched = new Set<string>();
  for (const r of regions) {
    const p = opts.patches?.[r.id];
    if (p && eligible(r, translations[r.id])) {
      ctx.drawImage(p.image as never, p.x, p.y);
      patched.add(r.id);
    }
  }
  const img = ctx.getImageData(0, 0, size.w, size.h);

  // 2) Erase. Anything that cannot be cleaned here waits for inpainting.
  const jobs: Job[] = [];
  for (const r of regions) {
    const t = translations[r.id];
    if (!t || (opts.only && !opts.only.has(r.id))) continue;
    if (t.role === "none" || (!t.vi && !t.ja)) {
      out.push({ id: r.id, status: "empty" });
      continue;
    }
    if (t.role === "sfx" || t.role === "decorative") {
      // Stylised sound effects and title lettering stay part of the art.
      out.push({ id: r.id, status: t.role === "sfx" ? "sfx" : "skipped" });
      continue;
    }
    if (!eligible(r, t)) {
      out.push({ id: r.id, status: "skipped" });
      continue;
    }
    const jaChars = [...t.ja.replace(/\s/g, "")].length;
    const charSize = jaChars ? Math.sqrt(area(r.box) / jaChars) : undefined;
    if (patched.has(r.id)) {
      const bg = sampleBorder(img, r.box).bg;
      const boxes = opts.patches?.[r.id]?.textBoxes ?? r.members;
      const boxArea = boxes.reduce((a, b) => a + area(b), 0);
      const ext = opts.patches?.[r.id]?.textExtent;
      jobs.push({
        r,
        t,
        onArt: true,
        // A loose box beside a face would put the Vietnamese on the face: start from the old text.
        seed: !r.bubble && ext && area(ext) < 0.85 * area(r.box) ? ext : undefined,
        residue: glyphResidue(img, boxes, charSize && Math.sqrt((charSize * charSize * boxArea) / area(r.box))),
        erase: { mode: "inpaint", bg, ink: [20, 20, 20], flatness: 0, inkShare: 0, midShare: 0, erasedPixels: 0 },
      });
      continue;
    }
    const snap = snapshot(img, r.bubble ? unionBox([...r.members, r.bubble]) : expand(unionBox(r.members), 6));
    const erase = eraseRegion(img, r.members, {
      bubble: r.bubble,
      mode: r.bubble ? "auto" : "glyph",
      maxMid: r.bubble ? MAX_MID_BUBBLE : MAX_MID_FREE,
      charSize,
    });
    if (erase.mode === "skipped") {
      out.push({ id: r.id, status: "needs-inpaint", needsInpaint: true, erase });
      continue;
    }
    const residue = glyphResidue(img, r.members, charSize);
    if (residue > MAX_RESIDUE) {
      restore(img, snap);
      out.push({ id: r.id, status: "needs-inpaint", needsInpaint: true, erase, residue });
      continue;
    }
    jobs.push({ r, t, erase, onArt: false, residue });
  }
  ctx.putImageData(img as never, 0, 0);

  // 3) Areas: the real balloon interior, or free space that avoids every other region.
  const fontFor = (px: number, bold: boolean) => `${bold ? "bold " : ""}${px}px ${family}`;
  const plans = jobs.map((job) => {
    const others = regions.filter((o) => o.id !== job.r.id).map((o) => o.bubble ?? o.box);
    const { area: box, rotated } = letteringArea(img, job, size, others);
    const jaChars = [...job.t.ja.replace(/\s/g, "")].length || 4;
    const charSize = Math.sqrt(area(job.r.box) / jaChars);
    const bold = job.t.style.includes("shout");
    const measure = (text: string, px: number) => {
      ctx.font = fontFor(px, bold);
      return ctx.measureText(text).width;
    };
    // Rotated captions are laid out in a frame where width and height are swapped.
    const frame: LayoutArea = rotated ? { x: 0, y: 0, w: box.h, h: box.w, shape: "rect" } : box;
    const maxSize = Math.max(13, Math.min(34, Math.round(charSize * 0.95)));
    let layout = layoutText(job.t.vi, frame, measure, { maxSize, minSize: 9 });
    let finalBox = box;
    let finalFrame = frame;
    if (layout.overflow && !rotated && box.shape === "rect" && !job.r.bubble) {
      // Free text that does not fit: grow into free space before shrinking further.
      const grown: LayoutArea = { ...avoid(grow(box, 0.3, 0.3, size), job.r.box, others), shape: "rect" };
      const retry = layoutText(job.t.vi, grown, measure, { maxSize, minSize: 8 });
      if (!retry.overflow || retry.fontSize >= layout.fontSize) {
        layout = retry;
        finalBox = grown;
        finalFrame = grown;
      }
    } else if (layout.overflow) {
      layout = layoutText(job.t.vi, frame, measure, { maxSize, minSize: 8 });
    }
    return { ...job, box: finalBox, frame: finalFrame, rotated, bold, measure, maxSize, layout };
  });

  // 4) Harmonise sizes across the page like a letterer would.
  const sizes = plans.filter((p) => !p.rotated).map((p) => p.layout.fontSize).sort((a, b) => a - b);
  const median = sizes.length ? sizes[Math.floor(sizes.length / 2)] : 0;
  const cap = Math.max(14, Math.round(median * 1.25));
  for (const p of plans) {
    if (sizes.length >= 3 && p.layout.fontSize > cap) p.layout = layoutText(p.t.vi, p.frame, p.measure, { maxSize: cap, minSize: 9 });
  }

  // 5) Draw.
  for (const p of plans) {
    const { layout } = p;
    ctx.save();
    if (p.rotated) {
      ctx.translate(p.box.x + p.box.w, p.box.y);
      ctx.rotate(Math.PI / 2);
    }
    ctx.font = fontFor(layout.fontSize, p.bold);
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    const dy = layout.fontSize * 0.06;
    if (p.onArt || !p.r.bubble) {
      // Text over artwork gets a halo, as letterers do for captions on screentone.
      ctx.lineJoin = "round";
      ctx.lineWidth = Math.max(2, layout.fontSize * (p.onArt ? 0.24 : 0.14));
      ctx.strokeStyle = luminance(p.erase.ink) < 128 ? "rgba(255,255,255,0.96)" : "rgba(15,15,15,0.9)";
      for (const line of layout.lines) ctx.strokeText(line.text, line.cx, line.top + dy);
    }
    ctx.fillStyle = `rgb(${p.erase.ink.join(",")})`;
    for (const line of layout.lines) ctx.fillText(line.text, line.cx, line.top + dy);
    ctx.restore();
    out.push({
      id: p.r.id,
      status: "lettered",
      erase: p.erase,
      area: p.box,
      layout,
      rotated: p.rotated,
      residue: p.residue,
      textBox: textBounds(layout, p.box, p.rotated),
      overflow: layout.overflow,
    });
  }
  return out;
}

const luminance = (c: [number, number, number]) => 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2];

/**
 * Where the Vietnamese text may go: the balloon interior when it is known, an inset
 * of the balloon box otherwise, or free space around free text that never enters
 * another region. Very tall, narrow captions get a wider horizontal band.
 */
function letteringArea(img: RGBAImage, job: Job, size: { w: number; h: number }, others: Box[]): { area: LayoutArea; rotated: boolean } {
  const r = job.r;
  const interior = job.erase.interior;
  if (interior) {
    const inset = Math.max(3, Math.round(Math.min(interior.w, interior.h) * 0.07));
    const spans = spansFromMask(interior, inset, r.box.x + r.box.w / 2);
    if (spans.some(Boolean)) return { area: { x: interior.x, y: interior.y, w: interior.w, h: interior.h, shape: "mask", spans }, rotated: false };
  }
  if (r.bubble) {
    const b = r.bubble;
    const inset = { x: b.x + b.w * 0.09, y: b.y + b.h * 0.1, w: b.w * 0.82, h: b.h * 0.8 };
    const covers = inset.w >= r.box.w * 0.9 && inset.h >= r.box.h * 0.9;
    if (covers) return { area: { ...inset, shape: cornersFlat(img, b) ? "rect" : "ellipse" }, rotated: false };
    return { area: { ...avoid(grow(r.box, 0.15, 0, size), r.box, others), shape: "rect" }, rotated: false };
  }
  // Free text (including tall Japanese columns): Vietnamese stays upright. Grow the
  // area only into genuinely free space — paper of the background colour or the
  // area just erased — and stop at art, panel borders and other regions. A narrow
  // column with no free space around it keeps its footprint and the words stack
  // one or two per line, which reads top-to-bottom like the original column.
  return { area: { ...growFree(img, job.seed ?? r.box, job.erase.bg, others, size), shape: "rect" }, rotated: false };
}

/** Grow `start` in 3 px strips while each new strip is free paper and touches no obstacle. */
function growFree(img: RGBAImage, start: Box, bg: [number, number, number], obstacles: Box[], size: { w: number; h: number }): Box {
  const step = 3;
  const maxW = Math.min(size.w * 0.45, Math.max(start.w * 3.5, start.w + 150));
  const maxH = start.h * 1.25;
  let b = clampBox(start, size.w, size.h);
  const open = { left: true, right: true, top: true, bottom: true };
  const freeShare = (s: Box) => {
    const c = clampBox(s, size.w, size.h);
    let free = 0;
    let n = 0;
    for (let y = Math.floor(c.y); y < Math.floor(c.y + c.h); y++) {
      for (let x = Math.floor(c.x); x < Math.floor(c.x + c.w); x++) {
        const i = (y * img.width + x) * 4;
        n++;
        if (Math.max(Math.abs(img.data[i] - bg[0]), Math.abs(img.data[i + 1] - bg[1]), Math.abs(img.data[i + 2] - bg[2])) <= 28) free++;
      }
    }
    return n ? free / n : 0;
  };
  for (let guard = 0; guard < 400 && (open.left || open.right || open.top || open.bottom); guard++) {
    for (const side of ["left", "right", "top", "bottom"] as const) {
      if (!open[side]) continue;
      const strip: Box =
        side === "left" ? { x: b.x - step, y: b.y, w: step, h: b.h }
        : side === "right" ? { x: b.x + b.w, y: b.y, w: step, h: b.h }
        : side === "top" ? { x: b.x, y: b.y - step, w: b.w, h: step }
        : { x: b.x, y: b.y + b.h, w: b.w, h: step };
      const next: Box =
        side === "left" ? { ...b, x: b.x - step, w: b.w + step }
        : side === "right" ? { ...b, w: b.w + step }
        : side === "top" ? { ...b, y: b.y - step, h: b.h + step }
        : { ...b, h: b.h + step };
      const outOfPage = next.x < 0 || next.y < 0 || next.x + next.w > size.w || next.y + next.h > size.h;
      if (outOfPage || next.w > maxW || next.h > maxH || obstacles.some((o) => intersect(strip, o)) || freeShare(strip) < 0.94) {
        open[side] = false;
        continue;
      }
      b = next;
    }
  }
  return b;
}

function grow(b: Box, fx: number, fy: number, size: { w: number; h: number }): Box {
  return clampBox({ x: b.x - b.w * fx, y: b.y - b.h * fy, w: b.w * (1 + 2 * fx), h: b.h * (1 + 2 * fy) }, size.w, size.h);
}

/**
 * Shrink a widened area so it stops before every neighbouring region, cutting on
 * the side where the neighbour lies; the region's own box always stays inside.
 */
function avoid(wide: Box, own: Box, others: Box[]): Box {
  let x1 = wide.x;
  let y1 = wide.y;
  let x2 = wide.x + wide.w;
  let y2 = wide.y + wide.h;
  for (const o of others) {
    if (!intersect({ x: x1, y: y1, w: x2 - x1, h: y2 - y1 }, o)) continue;
    if (o.x + o.w <= own.x + 2) x1 = Math.min(own.x, Math.max(x1, o.x + o.w + 3));
    else if (o.x >= own.x + own.w - 2) x2 = Math.max(own.x + own.w, Math.min(x2, o.x - 3));
    else if (o.y + o.h <= own.y + 2) y1 = Math.min(own.y, Math.max(y1, o.y + o.h + 3));
    else if (o.y >= own.y + own.h - 2) y2 = Math.max(own.y + own.h, Math.min(y2, o.y - 3));
  }
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

function unionBox(boxes: Box[]): Box {
  const x1 = Math.min(...boxes.map((b) => b.x));
  const y1 = Math.min(...boxes.map((b) => b.y));
  const x2 = Math.max(...boxes.map((b) => b.x + b.w));
  const y2 = Math.max(...boxes.map((b) => b.y + b.h));
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
}

interface Snapshot {
  x: number;
  y: number;
  w: number;
  h: number;
  data: Uint8ClampedArray;
}

function snapshot(img: RGBAImage, box: Box): Snapshot {
  const b = clampBox(box, img.width, img.height);
  const x = Math.floor(b.x);
  const y = Math.floor(b.y);
  const w = Math.max(0, Math.ceil(b.x + b.w) - x);
  const h = Math.max(0, Math.ceil(b.y + b.h) - y);
  const data = new Uint8ClampedArray(w * h * 4);
  for (let row = 0; row < h; row++) data.set(img.data.subarray(((y + row) * img.width + x) * 4, ((y + row) * img.width + x + w) * 4), row * w * 4);
  return { x, y, w, h, data };
}

function restore(img: RGBAImage, s: Snapshot): void {
  for (let row = 0; row < s.h; row++) img.data.set(s.data.subarray(row * s.w * 4, (row + 1) * s.w * 4), ((s.y + row) * img.width + s.x) * 4);
}

/** Union of the drawn line rectangles in page coordinates. */
function textBounds(layout: TextLayout, box: LayoutArea, rotated?: boolean): Box | undefined {
  if (!layout.lines.length) return undefined;
  const u0 = Math.min(...layout.lines.map((l) => l.cx - l.width / 2));
  const u1 = Math.max(...layout.lines.map((l) => l.cx + l.width / 2));
  const v0 = Math.min(...layout.lines.map((l) => l.top));
  const v1 = Math.max(...layout.lines.map((l) => l.top + layout.lineHeight));
  if (!rotated) return { x: u0, y: v0, w: u1 - u0, h: v1 - v0 };
  // Frame point (u, v) maps to page (box.x + box.w - v, box.y + u) after the 90° turn.
  return { x: box.x + box.w - v1, y: box.y + u0, w: v1 - v0, h: u1 - u0 };
}

/** Rectangular caption boxes have paper in their corners; round bubbles do not. */
function cornersFlat(img: RGBAImage, b: Box): boolean {
  const s = Math.max(3, Math.round(Math.min(b.w, b.h) * 0.06));
  const corners: Box[] = [
    { x: b.x + 2, y: b.y + 2, w: s, h: s },
    { x: b.x + b.w - s - 2, y: b.y + 2, w: s, h: s },
    { x: b.x + 2, y: b.y + b.h - s - 2, w: s, h: s },
    { x: b.x + b.w - s - 2, y: b.y + b.h - s - 2, w: s, h: s },
  ];
  const center = sampleBorder(img, { x: b.x + b.w * 0.3, y: b.y + b.h * 0.45, w: b.w * 0.4, h: 3 }).bg;
  return corners.every((c) => {
    const { bg, flatness, inkShare } = sampleBorder(img, c, 99);
    return flatness > 0.9 && inkShare < 0.05 && Math.abs(bg[0] - center[0]) + Math.abs(bg[1] - center[1]) + Math.abs(bg[2] - center[2]) < 40;
  });
}
