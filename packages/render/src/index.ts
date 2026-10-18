import {
  area,
  eraseRegion,
  expand,
  intersect,
  layoutText,
  sampleBorder,
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
/** Free text with glyphs larger than this is display lettering (titles, logos): keep it. */
const MAX_FREE_CHAR_PX = 90;
const MARK_COLORS =["#e6194b", "#3cb44b", "#4363d8", "#f58231", "#911eb4", "#008080", "#f032e6", "#9a6324"];

export interface RegionRender {
  id: string;
  status: "lettered" | "kept-original" | "sfx" | "skipped" | "empty";
  erase?: EraseReport;
  area?: LayoutArea;
  layout?: TextLayout;
  rotated?: boolean;
  /** Text sits on artwork: a local inpainting patch would let it be lettered. */
  needsInpaint?: boolean;
}

/** Reconstructed artwork for one region (from MI-GAN), drawn before lettering. */
export interface PatchImage {
  x: number;
  y: number;
  image: unknown;
}

export interface RenderOptions {
  fontFamily?: string;
  /** Only draw these ids (progressive rendering keeps the rest original). */
  only?: ReadonlySet<string>;
  /** Inpainted artwork per region id; text on art is lettered only where a patch exists. */
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

/**
 * Erase source text where it is safe and letter the Vietnamese translation in place.
 * The page must already be painted on `ctx` (original pixels). Pure drawing: the
 * caller decides whether the canvas is shown, so "view original" is simply redrawing.
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
  const toLetter: Array<{ r: TextRegion; t: RegionTranslation; erase: EraseReport; onArt: boolean }> = [];
  const eligible = (r: TextRegion, t: RegionTranslation | undefined): t is RegionTranslation =>
    !!t && !(opts.only && !opts.only.has(r.id)) && TRANSLATABLE.has(t.role) && !!t.vi;

  // 1) Reconstructed artwork goes down first, so later erasure and lettering see it.
  const patched = new Set<string>();
  for (const r of regions) {
    const p = opts.patches?.[r.id];
    if (p && eligible(r, translations[r.id])) {
      ctx.drawImage(p.image as never, p.x, p.y);
      patched.add(r.id);
    }
  }
  const img = ctx.getImageData(0, 0, size.w, size.h);

  for (const r of regions) {
    const t = translations[r.id];
    if (!t || (opts.only && !opts.only.has(r.id))) continue;
    if (t.role === "none" || (!t.vi && !t.ja)) {
      out.push({ id: r.id, status: "empty" });
      continue;
    }
    if (t.role === "sfx" || t.role === "decorative") {
      // Keep stylised lettering intact; the reader sees the translation on demand.
      out.push({ id: r.id, status: t.role === "sfx" ? "sfx" : "skipped" });
      continue;
    }
    if (!eligible(r, t)) {
      out.push({ id: r.id, status: "skipped" });
      continue;
    }
    // Very large display lettering (titles drawn as art) keeps the original art.
    const jaChars = [...t.ja.replace(/\s/g, "")].length;
    const displaySize = jaChars ? Math.sqrt(area(r.box) / jaChars) : 0;
    if (!r.bubble && displaySize > MAX_FREE_CHAR_PX) {
      out.push({ id: r.id, status: "kept-original" });
      continue;
    }
    if (patched.has(r.id)) {
      const bg = sampleBorder(img, r.box).bg;
      toLetter.push({ r, t, onArt: true, erase: { mode: "inpaint", bg, ink: [20, 20, 20], flatness: 0, inkShare: 0, midShare: 0, erasedPixels: 0 } });
      continue;
    }
    const erase = eraseRegion(img, r.members, {
      bubble: r.bubble,
      mode: r.bubble ? "auto" : "glyph",
      maxMid: r.bubble ? MAX_MID_BUBBLE : MAX_MID_FREE,
      charSize: displaySize || undefined,
    });
    if (erase.mode === "skipped") {
      // Text on artwork: needs a reconstructed background (local inpainting) before lettering.
      out.push({ id: r.id, status: "kept-original", erase, needsInpaint: true });
      continue;
    }
    toLetter.push({ r, t, erase, onArt: false });
  }
  ctx.putImageData(img as never, 0, 0);

  // 2) Lay out every region, then harmonise sizes across the page like a letterer would.
  const fontFor = (px: number, bold: boolean) => `${bold ? "bold " : ""}${px}px ${family}`;
  const plans = toLetter.map(({ r, t, erase, onArt }) => {
    const others = regions.filter((o) => o.id !== r.id).map((o) => o.bubble ?? o.box);
    const { area: box, rotated } = onArt && !r.bubble
      ? { area: { ...avoid(grow(r.box, 0.2, size), r.box, others), shape: "rect" as const }, rotated: r.box.h > r.box.w * 4.5 && r.box.w < 70 }
      : letteringArea(img, r, size, others);
    const jaChars = [...t.ja.replace(/\s/g, "")].length || 4;
    const charSize = Math.sqrt(area(r.box) / jaChars);
    const bold = t.style.includes("shout");
    const measure = (text: string, px: number) => {
      ctx.font = fontFor(px, bold);
      return ctx.measureText(text).width;
    };
    // Rotated captions are laid out in a frame where width and height are swapped.
    const frame: LayoutArea = rotated ? { x: 0, y: 0, w: box.h, h: box.w, shape: "rect" } : box;
    const maxSize = Math.max(13, Math.min(34, Math.round(charSize * 0.95)));
    return { r, t, erase, onArt, box, rotated, bold, measure, frame, maxSize, layout: layoutText(t.vi, frame, measure, { maxSize, minSize: 9 }) };
  });
  const sizes = plans.filter((p) => !p.rotated).map((p) => p.layout.fontSize).sort((a, b) => a - b);
  const median = sizes.length ? sizes[Math.floor(sizes.length / 2)] : 0;
  const cap = Math.max(14, Math.round(median * 1.25));
  for (const p of plans) {
    if (sizes.length >= 3 && p.layout.fontSize > cap) p.layout = layoutText(p.t.vi, p.frame, p.measure, { maxSize: cap, minSize: 9 });
  }

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
    out.push({ id: p.r.id, status: "lettered", erase: p.erase, area: p.box, layout, rotated: p.rotated });
  }
  return out;
}

const luminance = (c: [number, number, number]) => 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2];

/**
 * Where the Vietnamese text may go: inside the bubble, or around free text on flat
 * paper without entering another region. Very tall, narrow captions are rotated.
 */
export function letteringArea(
  img: RGBAImage,
  r: TextRegion,
  size: { w: number; h: number },
  others: Box[] = [],
): { area: LayoutArea; rotated: boolean } {
  if (r.bubble) {
    const b = r.bubble;
    const inset = { x: b.x + b.w * 0.07, y: b.y + b.h * 0.08, w: b.w * 0.86, h: b.h * 0.84 };
    const covers = inset.w >= r.box.w * 0.9 && inset.h >= r.box.h * 0.9;
    if (covers) return { area: { ...inset, shape: cornersFlat(img, b) ? "rect" : "ellipse" }, rotated: false };
    return { area: { ...avoid(grow(r.box, 0.15, size), r.box, others), shape: "rect" }, rotated: false };
  }
  if (r.box.h > r.box.w * 4.5 && r.box.w < 70) {
    return { area: { ...grow(r.box, 0.1, size), shape: "rect" }, rotated: true };
  }
  // Free text: widen sideways only into flat paper and never into a neighbour.
  const wide = avoid(grow(r.box, 0.35, size), r.box, others);
  const flat = sampleBorder(img, wide).flatness >= 0.85;
  return { area: { ...(flat ? wide : grow(r.box, 0.04, size)), shape: "rect" }, rotated: false };
}

function grow(b: Box, fx: number, size: { w: number; h: number }): Box {
  const dx = b.w * fx;
  const x = Math.max(0, b.x - dx);
  const x2 = Math.min(size.w, b.x + b.w + dx);
  return { x, y: b.y, w: x2 - x, h: b.h };
}

/** Shrink a widened box horizontally so it stops before any neighbouring region. */
function avoid(wide: Box, own: Box, others: Box[]): Box {
  let x1 = wide.x;
  let x2 = wide.x + wide.w;
  for (const o of others) {
    if (!intersect({ x: x1, y: wide.y, w: x2 - x1, h: wide.h }, o)) continue;
    if (o.x >= own.x + own.w) x2 = Math.max(own.x + own.w, Math.min(x2, o.x - 3));
    else if (o.x + o.w <= own.x) x1 = Math.min(own.x, Math.max(x1, o.x + o.w + 3));
  }
  return { x: x1, y: wide.y, w: x2 - x1, h: wide.h };
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
