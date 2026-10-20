import {
  area,
  artTextMask,
  clampBox,
  eraseRegion,
  expand,
  intersect,
  glyphResidue,
  layoutText,
  paintBalloon,
  roundBox,
  sampleBorder,
  spansFromMask,
  textArea,
  type Box,
  type EraseReport,
  type InteriorMask,
  type LayoutArea,
  type RegionTranslation,
  type RGBAImage,
  type TextLayout,
  type TextRegion,
} from "@lt/core";
import { arcLength, avoidAreas, avoidPictures, frameHas, frameQuad, placeOnArc, textSlant, type Slant } from "./slant";

export { textSlant, type Slant } from "./slant";

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
/** Free text at least this many times taller than wide is a column: it may be lettered along it. */
const COLUMN_RATIO = 3.5;
/** Clear space kept between two regions' lettering, px. */
const LETTER_GAP = 3;
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
  /** Lettered at the source text's angle (radians), when it was tilted. */
  angle?: number;
  /** Lettered along the source line's curve. */
  curved?: boolean;
  /** Corners of the drawn lettering (tilted lettering is not its upright `textBox`). */
  textQuad?: Array<[number, number]>;
  /** Lettered line by line on this many printed lines of the source (a card, a form). */
  printedLines?: number;
  /** A shout lettered big in capitals: "stacked" letter by letter down its column, or "across". */
  display?: "stacked" | "across";
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
  /** Source glyph colour and the clean tone around it, when the server could read them. */
  ink?: [number, number, number];
  outline?: [number, number, number];
  /** Pictures inside the text boxes that were kept (a photo on a card): lettering keeps off them. */
  keepOut?: Box[];
}

export interface RenderOptions {
  fontFamily?: string;
  /** Regions kept as art (bold display lettering): no erasing, a marker opens the translation. */
  keep?: Set<string>;
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
  /** One clean tone the source strokes sat in (their outline or a flat ground), when known. */
  outline?: [number, number, number];
  /** Free text drawn at an angle or along a curve in the raw. */
  slant?: Slant;
}

/**
 * Which regions will need a reconstructed background? The same erase test as
 * `renderTranslation`, run on a copy before any translation exists, so inpainting can
 * start while the reader model is still translating. Roles are not known yet: a sound
 * effect predicted here simply never uses its patch, and a region the final render
 * still needs is requested afterwards as before.
 */
export function predictInpaint(img: RGBAImage, regions: TextRegion[]): string[] {
  const copy: RGBAImage = { width: img.width, height: img.height, data: new Uint8ClampedArray(img.data) };
  const out: string[] = [];
  for (const r of regions) {
    const snap = snapshot(copy, r.bubble ? unionBox([...r.members, r.bubble]) : expand(unionBox(r.members), 6));
    const area_ = textArea(r, !!r.bubble && cornersFlat(copy, r.bubble));
    const erase = eraseRegion(copy, area_, { bubble: r.bubble, mode: r.bubble ? "auto" : "glyph", maxMid: r.bubble ? MAX_MID_BUBBLE : MAX_MID_FREE });
    let residue = erase.mode === "skipped" ? Infinity : glyphResidue(copy, area_);
    if (residue > MAX_RESIDUE && r.bubble) residue = retouch(copy, r, area_, erase.bg);
    const needs = residue > MAX_RESIDUE;
    restore(copy, snap);
    if (needs) out.push(r.id);
  }
  return out;
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

  // 0) Tilted or curved free text, read from the untouched source before anything is drawn.
  const slants = new Map<string, Slant>();
  const loose = regions.filter((r) => !r.bubble && eligible(r, translations[r.id]) && !opts.keep?.has(r.id));
  if (loose.length) {
    const source = ctx.getImageData(0, 0, size.w, size.h);
    for (const r of loose) {
      const jaChars = [...translations[r.id]!.ja.replace(/\s/g, "")].length || 4;
      const s = textSlant(source, opts.patches?.[r.id]?.textBoxes ?? r.members, Math.sqrt(area(r.box) / jaChars));
      const keep = opts.patches?.[r.id]?.keepOut;
      if (s) slants.set(r.id, keep?.length ? avoidPictures(s, keep) : s);
    }
    // A loose box often reaches over a neighbour on the same card: the bigger frame gives way to
    // any smaller tilted block whose centre it holds, so their lettering does not collide.
    const frames = [...slants];
    for (const [id, s] of frames) {
      const inside = frames.filter(([o, t]) => o !== id && t.w * t.h < s.w * s.h && frameHas(s, t.cx, t.cy)).map(([, t]) => frameQuad(t));
      if (inside.length) slants.set(id, avoidAreas(s, inside));
    }
  }

  // 1) Regions with reconstructed artwork. Their patches go down after the other regions are
  //    erased on the source (step 2), so a region erases exactly as it did before any patch
  //    existed: a patch overlapping its balloon (two balloons drawn overlapping) cannot turn a
  //    clean erase into "needs inpainting" on the second pass.
  const patched = new Set<string>();
  for (const r of regions) if (opts.patches?.[r.id] && eligible(r, translations[r.id])) patched.add(r.id);
  let img = ctx.getImageData(0, 0, size.w, size.h);

  // 2) Erase. Anything that cannot be cleaned here waits for inpainting.
  const jobs: Job[] = [];
  const deferred: Array<{ r: TextRegion; t: RegionTranslation; charSize?: number }> = [];
  for (const r of regions) {
    const t = translations[r.id];
    if (!t || (opts.only && !opts.only.has(r.id))) continue;
    if (t.role === "none" || (!t.vi && !t.ja)) {
      out.push({ id: r.id, status: "empty" });
      continue;
    }
    if (opts.keep?.has(r.id)) {
      out.push({ id: r.id, status: "skipped" });
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
      deferred.push({ r, t, charSize });
      continue;
    }
    const snap = snapshot(img, r.bubble ? unionBox([...r.members, r.bubble]) : expand(unionBox(r.members), 6));
    const area_ = textArea(r, !!r.bubble && cornersFlat(img, r.bubble));
    // A balloon erased glyph by glyph (no closed interior) only loses ink near its own text boxes.
    const glyphBoxes = r.bubble ? r.members.map((m) => clipTo(expand(m, Math.max(3, 0.25 * (charSize ?? 16))), r.bubble!)) : undefined;
    const inkBefore = r.bubble ? coreInk(img, area_) : 0;
    const erase = eraseRegion(img, area_, {
      bubble: r.bubble,
      mode: r.bubble ? "auto" : "glyph",
      maxMid: r.bubble ? MAX_MID_BUBBLE : MAX_MID_FREE,
      charSize,
      glyphBoxes,
    });
    let residue = erase.mode === "skipped" ? Infinity : glyphResidue(img, erase.mode === "glyph" && glyphBoxes ? glyphBoxes : area_, charSize);
    if (residue > MAX_RESIDUE && r.bubble) residue = retouch(img, r, area_, erase.bg, charSize, erase.interior);
    // Hollow outlined letters crossing a burst's edge join the outline: the fill leaves them all and
    // the residue test (glyph-shaped ink) can miss thin outlines. Most of a balloon's text ink must be gone.
    if (r.bubble && inkBefore >= 0.04 && coreInk(img, area_) > 0.5 * inkBefore) residue = Infinity;
    // Text boxes reaching well out of the balloon (a shout running past a burst's edge into speed
    // lines): the balloon fill stops at the edge, so the strokes out there are erased like free text
    // (line work kept). Kept only when that comes out clean: sending the whole balloon to the
    // inpainting model for a strip brings back ghosts of every glyph.
    const outside = r.bubble ? stripsOutside(area_, r.bubble) : [];
    if (outside.length && residue <= MAX_RESIDUE) {
      const before = outside.map((s) => snapshot(img, s));
      const strip = eraseRegion(img, outside, { mode: "glyph", maxMid: MAX_MID_FREE, charSize });
      if (strip.mode === "skipped" || glyphResidue(img, outside, charSize) > MAX_RESIDUE) for (const s of before) restore(img, s);
    }
    if (erase.mode === "skipped" && residue > MAX_RESIDUE) {
      restore(img, snap);
      out.push({ id: r.id, status: "needs-inpaint", needsInpaint: true, erase });
      continue;
    }
    if (residue > MAX_RESIDUE) {
      restore(img, snap);
      out.push({ id: r.id, status: "needs-inpaint", needsInpaint: true, erase, residue });
      continue;
    }
    // Free text: start the lettering where the old glyphs were, not in a loose detector box
    // that may cover art below a short caption.
    const ext = erase.extent && expand(erase.extent, 4);
    jobs.push({ r, t, erase, onArt: false, residue, seed: !r.bubble && ext && area(ext) < 0.85 * area(r.box) ? ext : undefined, slant: slants.get(r.id) });
  }
  ctx.putImageData(img as never, 0, 0);

  // Now the reconstructed artwork, which lettering then sees.
  for (const { r } of deferred) {
    const p = opts.patches![r.id]!;
    ctx.drawImage(p.image as never, p.x, p.y);
  }
  if (deferred.length) img = ctx.getImageData(0, 0, size.w, size.h);
  for (const { r, t, charSize } of deferred) {
    const p = opts.patches![r.id]!;
    const bg = sampleBorder(img, r.box).bg;
    const boxes = p.textBoxes ?? r.members;
    const boxArea = boxes.reduce((a, b) => a + area(b), 0);
    const ext = p.textExtent;
    jobs.push({
      r,
      t,
      onArt: true,
      // A loose box beside a face would put the Vietnamese on the face: start from the old text.
      seed: !r.bubble && ext && area(ext) < 0.85 * area(r.box) ? ext : undefined,
      residue: glyphResidue(img, boxes, charSize && Math.sqrt((charSize * charSize * boxArea) / area(r.box))),
      erase: { mode: "inpaint", bg, ink: p.ink ?? [20, 20, 20], flatness: 0, inkShare: 0, midShare: 0, erasedPixels: 0 },
      outline: p.outline,
      slant: slants.get(r.id),
    });
  }
  // Keep reading order: the regions' order, not erased-first.
  const order0 = new Map(regions.map((r, i) => [r.id, i]));
  jobs.sort((a, b) => order0.get(a.r.id)! - order0.get(b.r.id)!);

  // 3) Areas: the real balloon interior, or free space that avoids every other region.
  //    `hard` is lettering already placed that free text must stay clear of (step 5).
  const fontFor = (px: number, bold: boolean) => `${bold ? "bold " : ""}${px}px ${family}`;
  const glyphSize = (job: Job) => Math.sqrt(area(job.r.box) / ([...job.t.ja.replace(/\s/g, "")].length || 4));
  const glyphSizes = jobs.map(glyphSize).sort((a, b) => a - b);
  const typicalGlyph = glyphSizes.length ? glyphSizes[Math.floor(glyphSizes.length / 2)] : 0;
  const planFor = (job: Job, hard: Box[] = [], cap = 34): Plan => {
    const others = regions.filter((o) => o.id !== job.r.id).map((o) => o.bubble ?? o.box);
    const { area: box, rotated } = letteringArea(img, job, size, others, hard);
    const charSize = glyphSize(job);
    const bold = job.t.style.includes("shout");
    const measure = (text: string, px: number) => {
      ctx.font = fontFor(px, bold);
      return ctx.measureText(text).width;
    };
    // A shout drawn big (or one or two words marked as shouting): lettered like the raw, see displayPlan.
    const display = displayPlan(img, job, box, charSize, typicalGlyph, (text, px) => {
      ctx.font = fontFor(px, true);
      return ctx.measureText(text).width;
    });
    if (display) return { ...job, ...display, bold: true, angle: undefined, centre: undefined, arc: undefined, doc: undefined };
    const maxSize = Math.min(cap, Math.max(13, Math.min(34, Math.round(charSize * 0.95))));
    // Free text that sits at an angle or along a curve in the raw is lettered the same way.
    const slanted = job.slant && planSlanted(job.slant, job.t.vi, measure, maxSize);
    if (slanted) {
      // Upright printed lines: keep them only if the usual block (which may grow into free paper) is not clearly bigger.
      if (slanted.doc && job.slant!.angle === 0) {
        const upright = planFor({ ...job, slant: undefined }, hard, cap);
        if (!upright.layout.overflow && slanted.layout.fontSize < 0.9 * upright.layout.fontSize) return upright;
      }
      return { ...job, ...slanted, rotated: false, bold, measure, maxSize };
    }
    // Rotated captions are laid out in a frame where width and height are swapped.
    const frame: LayoutArea = rotated ? { x: 0, y: 0, w: box.h, h: box.w, shape: "rect" } : box;
    let layout = layoutText(job.t.vi, frame, measure, { maxSize, minSize: 9 });
    let finalBox = box;
    let finalFrame = frame;
    if (layout.overflow && job.r.bubble && box.shape === "mask") {
      // An open balloon (cut by the panel edge) leaves a ragged interior mask: try its inner box.
      const b = job.r.bubble;
      const inner: LayoutArea = { x: b.x + b.w * 0.09, y: b.y + b.h * 0.1, w: b.w * 0.82, h: b.h * 0.8, shape: cornersFlat(img, b) ? "rect" : "ellipse" };
      const retry = layoutText(job.t.vi, inner, measure, { maxSize, minSize: 9 });
      if (!retry.overflow || retry.fontSize > layout.fontSize) {
        layout = retry;
        finalBox = inner;
        finalFrame = inner;
      }
    }
    if (layout.overflow && !rotated && box.shape === "rect" && !job.r.bubble) {
      // Free text that does not fit: grow into free space before shrinking further.
      const grown: LayoutArea = { ...clipAway(avoid(grow(box, 0.3, 0.3, size), job.r.box, others), hard), shape: "rect" };
      const retry = layoutText(job.t.vi, grown, measure, { maxSize, minSize: 8 });
      if (!retry.overflow || retry.fontSize >= layout.fontSize) {
        layout = retry;
        finalBox = grown;
        finalFrame = grown;
      }
    } else if (layout.overflow) {
      layout = layoutText(job.t.vi, frame, measure, { maxSize, minSize: 8 });
    }
    // A tall narrow column of free text (a sign, a caption down the page margin): stacked a word
    // per line it reads badly, and spread sideways it leaves the column; turned 90 degrees along
    // the column it reads like the original and stays where the Japanese was.
    let turned = rotated;
    const col = job.seed ?? job.r.box;
    const upright = textBounds(layout, finalBox);
    const wanders = !!upright && upright.w > 1.6 * col.w;
    if (!rotated && !job.r.bubble && !hard.length && col.h >= COLUMN_RATIO * col.w && (layout.overflow || layout.lines.length >= 5 || wanders)) {
      const colFrame: LayoutArea = { x: 0, y: 0, w: col.h, h: col.w, shape: "rect" };
      const along = layoutText(job.t.vi, colFrame, measure, { maxSize, minSize: 9 });
      if (!along.overflow && along.lines.length <= 3 && along.fontSize >= 0.8 * Math.min(layout.fontSize, maxSize)) {
        layout = along;
        finalBox = { x: col.x, y: col.y, w: col.w, h: col.h, shape: "rect" };
        finalFrame = colFrame;
        turned = true;
      }
    }
    return { ...job, box: finalBox, frame: finalFrame, rotated: turned, bold, measure, maxSize, layout, angle: undefined as number | undefined, centre: undefined as [number, number] | undefined, arc: undefined as number | undefined, doc: undefined as DocLine[] | undefined };
  };
  // A picture kept inside the text boxes (a photo on a card) is an obstacle like other lettering.
  const keepOut = (job: Job) => opts.patches?.[job.r.id]?.keepOut ?? [];
  const plans = jobs.map((job) => planFor(job, keepOut(job)));

  // 4) Harmonise sizes across the page like a letterer would.
  const sizes = plans.filter((p) => !p.rotated).map((p) => p.layout.fontSize).sort((a, b) => a - b);
  const median = sizes.length ? sizes[Math.floor(sizes.length / 2)] : 0;
  const cap = Math.max(14, Math.round(median * 1.25));
  for (const p of plans) {
    if (sizes.length >= 3 && p.layout.fontSize > cap && p.arc === undefined && !p.doc && !p.display) p.layout = layoutText(p.t.vi, p.frame, p.measure, { maxSize: cap, minSize: 9 });
  }

  // 5) Lettering never overlaps. Free text grows into free paper and so does its neighbour,
  //    so two captions can claim the same gap; two balloons joined into one (one paper area)
  //    share an interior. In reading order, balloons first and free text last, lettering that
  //    touches lettering already placed is laid out again, clear of it.
  const free = (p: (typeof plans)[number]) => !p.r.bubble && !p.rotated;
  // Lettering is compared as it is drawn: two parallel tilted blocks on a card do not touch even
  // though the upright boxes around them do.
  const placed: Quad[] = [];
  const order = plans.map((_, i) => i).sort((a, b) => Number(free(plans[a])) - Number(free(plans[b])));
  for (const i of order) {
    const p = plans[i];
    if (!p.rotated) {
      const text = quadOf(p);
      // Lettering that would touch lettering already placed is laid out again (upright), clear of it.
      if (text && placed.some((q) => quadsTouch(q, text, LETTER_GAP))) {
        const hard = placed.map((q) => expand(quadBounds(q), LETTER_GAP));
        plans[i] = planFor({ ...p, slant: undefined }, [...hard, ...keepOut(p)], sizes.length >= 3 ? cap : 34);
      }
    }
    const after = quadOf(plans[i]);
    if (after) placed.push(after);
  }

  // 6) Draw.
  for (const p of plans) {
    const { layout } = p;
    ctx.save();
    if (p.rotated) {
      ctx.translate(p.box.x + p.box.w, p.box.y);
      ctx.rotate(Math.PI / 2);
    } else if (p.angle !== undefined && p.centre) {
      // The frame is centred on the source block and turned with it.
      ctx.translate(p.centre[0], p.centre[1]);
      ctx.rotate(p.angle);
      ctx.translate(-p.frame.w / 2, -p.frame.h / 2);
    }
    // Along a curve each character is placed and turned on its own (see placeOnArc).
    const glyphs =
      p.arc !== undefined && layout.lines.length
        ? (() => {
            const chars = [...layout.lines[0].text.normalize("NFC")];
            const at = placeOnArc(chars.map((ch) => p.measure(ch, layout.fontSize)), p.frame.w, p.arc!);
            return chars.map((ch, k) => ({ ch, x: at[k].along, y: p.frame.h / 2 + at[k].across - p.arc! / 2, a: at[k].angle }));
          })()
        : undefined;
    const draw = (paint: (text: string, x: number, y: number) => void) => {
      if (p.doc) {
        // Card or letter lines: each at its own size, from the printed line's left edge.
        ctx.textAlign = "left";
        ctx.textBaseline = "middle";
        for (const d of p.doc) {
          ctx.font = fontFor(d.px, p.bold);
          paint(d.text, d.x, d.y);
        }
        return;
      }
      if (!glyphs) {
        for (const line of layout.lines) paint(line.text, line.cx, line.top + layout.fontSize * 0.06);
        return;
      }
      for (const g of glyphs) {
        ctx.save();
        ctx.translate(g.x, g.y);
        ctx.rotate(g.a);
        paint(g.ch, 0, 0);
        ctx.restore();
      }
    };
    ctx.font = fontFor(layout.fontSize, p.bold);
    ctx.textAlign = "center";
    ctx.textBaseline = glyphs ? "middle" : "top";
    if (p.onArt || !p.r.bubble) {
      // Text over artwork gets a halo, as letterers do for captions on screentone.
      ctx.lineJoin = "round";
      ctx.lineWidth = Math.max(2, layout.fontSize * (p.onArt ? 0.24 : 0.14));
      ctx.strokeStyle = haloColour(p.erase.ink, p.outline);
      draw((s, x, y) => ctx.strokeText(s, x, y));
    }
    ctx.fillStyle = `rgb(${p.erase.ink.join(",")})`;
    draw((s, x, y) => ctx.fillText(s, x, y));
    ctx.restore();
    out.push({
      id: p.r.id,
      status: "lettered",
      erase: p.erase,
      area: p.box,
      layout,
      rotated: p.rotated,
      residue: p.residue,
      textBox: boundsOf(p),
      overflow: layout.overflow,
      angle: p.angle,
      curved: p.arc !== undefined || undefined,
      textQuad: quadOf(p),
      printedLines: p.doc?.length,
      display: p.display ? (p.layout.lines.length > 1 && p.layout.lines.every((l) => [...l.text].length === 1) ? "stacked" : "across") : undefined,
    });
  }
  return out;
}

const luminance = (c: [number, number, number]) => 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2];

/**
 * The halo around lettering on art: the source's own outline or flat ground when it stands
 * clear of the ink (white text outlined in black stays so), otherwise white around dark ink
 * and black around light ink (manga-image-translator's rule when fg and bg are too close).
 */
export function haloColour(ink: [number, number, number], outline?: [number, number, number]): string {
  if (outline && Math.abs(luminance(outline) - luminance(ink)) >= 60) return `rgba(${outline.join(",")},0.96)`;
  return luminance(ink) < 128 ? "rgba(255,255,255,0.96)" : "rgba(15,15,15,0.9)";
}

/** Share of the band just outside the text boxes that must be balloon paper for a retouch. */
const PLAIN_BAND = 0.75;

/**
 * A balloon whose fill left letters behind (bold strokes touching each other or the outline,
 * furigana, a balloon cut by the panel edge): repaint with the paper colour every ink blob
 * that lies wholly inside the text boxes, and keep any ink that runs out of them (the outline,
 * art). Only when the paper just outside the boxes is plain, i.e. the text sits on a light
 * balloon, not on art. No inpainting is needed: a model asked to redraw a white balloon full of
 * bold text paints grey smudges. `area_` is what the residue is measured on. Returns the
 * residue afterwards, or Infinity when nothing was painted.
 */
function retouchBalloon(img: RGBAImage, textBoxes: Box[], area_: Box[], bg: [number, number, number], charSize?: number, interior?: InteriorMask): number {
  const W = img.width;
  const lumAt = (p: number) => 0.299 * img.data[p * 4] + 0.587 * img.data[p * 4 + 1] + 0.114 * img.data[p * 4 + 2];
  const bgL = 0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2];
  if (bgL < 170 || !textBoxes.length) return Infinity;
  const isInk = (p: number) => bgL - lumAt(p) > 45;
  const pad = Math.max(3, Math.round(0.2 * (charSize ?? 16)));
  const boxes = textBoxes.map((m) => roundBox(clampBox(expand(m, pad), W, img.height)));
  const u = roundBox(clampBox(unionBox(boxes), W, img.height));
  const inBoxes = (x: number, y: number) => boxes.some((b) => x >= b.x && y >= b.y && x < b.x + b.w && y < b.y + b.h);
  // Guard: the band 2-6 px outside the boxes is mostly paper.
  let band = 0;
  let paper = 0;
  for (let y = Math.max(0, u.y - 6); y < Math.min(img.height, u.y + u.h + 6); y++)
    for (let x = Math.max(0, u.x - 6); x < Math.min(W, u.x + u.w + 6); x++) {
      if (inBoxes(x, y) || boxes.some((b) => x >= b.x - 2 && y >= b.y - 2 && x < b.x + b.w + 2 && y < b.y + b.h + 2)) continue;
      band++;
      if (Math.abs(lumAt(y * W + x) - bgL) < 30) paper++;
    }
  if (!band || paper / band < PLAIN_BAND) return Infinity;
  // Ink blobs inside the boxes; a blob with ink right across the boxes' edge runs on (outline, art).
  const seen = new Uint8Array(u.w * u.h);
  const paint: number[] = [];
  for (let sy = 0; sy < u.h; sy++)
    for (let sx = 0; sx < u.w; sx++) {
      const s0 = sy * u.w + sx;
      const gx = u.x + sx;
      const gy = u.y + sy;
      if (seen[s0] || !inBoxes(gx, gy) || !isInk(gy * W + gx)) continue;
      const comp: number[] = [];
      let escapes = false;
      const stack = [s0];
      seen[s0] = 1;
      while (stack.length) {
        const q = stack.pop()!;
        const qx = u.x + (q % u.w);
        const qy = u.y + Math.floor(q / u.w);
        comp.push(qy * W + qx);
        for (let dy = -1; dy <= 1; dy++)
          for (let dx = -1; dx <= 1; dx++) {
            const nx = qx + dx;
            const ny = qy + dy;
            if (nx < 0 || ny < 0 || nx >= W || ny >= img.height || !isInk(ny * W + nx)) continue;
            if (!inBoxes(nx, ny)) {
              escapes = true;
              continue;
            }
            const n = (ny - u.y) * u.w + (nx - u.x);
            if (!seen[n]) {
              seen[n] = 1;
              stack.push(n);
            }
          }
      }
      if (!escapes) paint.push(...comp);
    }
  if (!paint.length) return Infinity;
  // One pixel more around each blob takes the antialiasing with it.
  const grown = new Set<number>();
  for (const p of paint) {
    const x = p % W;
    const y = (p - x) / W;
    for (let dy = -1; dy <= 1; dy++)
      for (let dx = -1; dx <= 1; dx++) if (inBoxes(x + dx, y + dy)) grown.add((y + dy) * W + x + dx);
  }
  for (const p of grown) {
    img.data[p * 4] = bg[0];
    img.data[p * 4 + 1] = bg[1];
    img.data[p * 4 + 2] = bg[2];
    const px = p % W;
    const py = (p - px) / W;
    // The repainted letters are balloon interior now: lettering may use that room.
    if (interior && px >= interior.x && py >= interior.y && px < interior.x + interior.w && py < interior.y + interior.h)
      interior.mask[(py - interior.y) * interior.w + (px - interior.x)] = 1;
  }
  return glyphResidue(img, area_, charSize);
}

/**
 * Second retouch pass for a balloon: paint the glyph strokes the text mask isolates (it follows
 * strokes that touch each other or run close to the outline better than ink blobs do), again
 * only where the paper around them is plain. Returns the residue, or Infinity when unsafe.
 */
function retouchGlyphs(img: RGBAImage, area_: Box[], bg: [number, number, number], charSize?: number, interior?: InteriorMask): number {
  const job = artTextMask(img, area_, { charSize });
  if (job.rect || job.coverage <= 0) return Infinity;
  const { x, y, w, h } = job.crop;
  const near = new Uint8Array(w * h);
  for (let py = 0; py < h; py++)
    for (let px = 0; px < w; px++) {
      if (!job.hole[py * w + px]) continue;
      for (let dy = -4; dy <= 4; dy++)
        for (let dx = -4; dx <= 4; dx++) {
          const qx = px + dx;
          const qy = py + dy;
          if (qx >= 0 && qy >= 0 && qx < w && qy < h) near[qy * w + qx] = 1;
        }
    }
  let ring = 0;
  let plain = 0;
  for (let p = 0; p < w * h; p++) {
    if (!near[p] || job.hole[p]) continue;
    const i = ((y + Math.floor(p / w)) * img.width + x + (p % w)) * 4;
    ring++;
    if (Math.abs(img.data[i] - bg[0]) + Math.abs(img.data[i + 1] - bg[1]) + Math.abs(img.data[i + 2] - bg[2]) < 60) plain++;
  }
  if (!ring || plain / ring < 0.85) return Infinity;
  for (let p = 0; p < w * h; p++) {
    if (!job.hole[p]) continue;
    const px = x + (p % w);
    const py = y + Math.floor(p / w);
    const i = (py * img.width + px) * 4;
    img.data[i] = bg[0];
    img.data[i + 1] = bg[1];
    img.data[i + 2] = bg[2];
    if (interior && px >= interior.x && py >= interior.y && px < interior.x + interior.w && py < interior.y + interior.h)
      interior.mask[(py - interior.y) * interior.w + (px - interior.x)] = 1;
  }
  return glyphResidue(img, area_, charSize);
}

/** Both retouch passes, ink blobs first; the residue left (Infinity when neither could run). */
/**
 * Parts of the text boxes beyond the balloon box: above, below, left and right of it, kept only when
 * they are a real stretch of text (at least 8% of the box and 6 px), not a loose box's margin.
 */
function stripsOutside(boxes: Box[], b: Box): Box[] {
  const out: Box[] = [];
  for (const m of boxes) {
    const y0 = Math.max(m.y, b.y), y1 = Math.min(m.y + m.h, b.y + b.h);
    const keep = (s: Box, along: number) => s.w > 0 && s.h > 0 && Math.min(s.w, s.h) >= Math.max(6, 0.08 * along) && out.push(s);
    keep({ x: m.x, y: m.y, w: m.w, h: b.y - m.y }, m.h);
    keep({ x: m.x, y: b.y + b.h, w: m.w, h: m.y + m.h - (b.y + b.h) }, m.h);
    if (y1 > y0) {
      keep({ x: m.x, y: y0, w: b.x - m.x, h: y1 - y0 }, m.w);
      keep({ x: b.x + b.w, y: y0, w: m.x + m.w - (b.x + b.w), h: y1 - y0 }, m.w);
    }
  }
  return out;
}

/** Share of dark pixels in the cores of the text boxes (outer 15% left out: a small balloon's outline runs there). */
function coreInk(img: RGBAImage, boxes: Box[]): number {
  let dark = 0;
  let all = 0;
  for (const b of boxes) {
    const c = roundBox(clampBox({ x: b.x + 0.15 * b.w, y: b.y + 0.15 * b.h, w: 0.7 * b.w, h: 0.7 * b.h }, img.width, img.height));
    for (let y = c.y; y < c.y + c.h; y++)
      for (let x = c.x; x < c.x + c.w; x++) {
        const i = (y * img.width + x) * 4;
        all++;
        if (0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2] < 110) dark++;
      }
  }
  return all ? dark / all : 0;
}

function retouch(img: RGBAImage, r: TextRegion, area_: Box[], bg: [number, number, number], charSize?: number, interior?: InteriorMask): number {
  const first = retouchBalloon(img, r.members, area_, bg, charSize, interior);
  if (first <= MAX_RESIDUE) return first;
  const second = retouchGlyphs(img, area_, bg, charSize, interior);
  if (Math.min(first, second) <= MAX_RESIDUE || !r.bubble) return Math.min(first, second);
  // Strokes joined to the outline: repaint the balloon's whole inside, outline kept.
  return paintBalloon(img, r.bubble, area_, bg, charSize, interior) ? glyphResidue(img, area_, charSize) : Math.min(first, second);
}

/**
 * Where the Vietnamese text may go: the balloon interior when it is known, an inset
 * of the balloon box otherwise, or free space around free text that never enters
 * another region. Very tall, narrow captions get a wider horizontal band.
 */
function letteringArea(img: RGBAImage, job: Job, size: { w: number; h: number }, others: Box[], hard: Box[] = []): { area: LayoutArea; rotated: boolean } {
  const r = job.r;
  // Laid out again clear of a neighbour's lettering (balloons joined into one): the balloon's
  // inner box without the part the neighbour's text takes, as long as it still holds this text.
  if (r.bubble && hard.length) {
    const b = r.bubble;
    const clipped = clipAway({ x: b.x + b.w * 0.09, y: b.y + b.h * 0.1, w: b.w * 0.82, h: b.h * 0.8 }, hard);
    if (clipped.w > 8 && clipped.h > 8 && intersect(clipped, r.box)) return { area: { ...clipped, shape: "rect" }, rotated: false };
  }
  const interior = job.erase.interior;
  if (interior) {
    const inset = Math.max(3, Math.round(Math.min(interior.w, interior.h) * 0.07));
    const spans = spansFromMask(interior, inset, r.box.x + r.box.w / 2);
    if (spans.some(Boolean)) return { area: { x: interior.x, y: interior.y, w: interior.w, h: interior.h, shape: "mask", spans }, rotated: false };
  }
  if (r.bubble) {
    const b = r.bubble;
    // No closed interior (a burst balloon, one open into speed lines): its real paper, row by
    // row, so the lettering stays off the spikes and the outline that erasing now keeps.
    const scanned = scanBalloon(img, b, r.box);
    if (scanned) return { area: scanned, rotated: false };
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
  const start = clipAway(job.seed ?? r.box, hard);
  return { area: { ...growFree(img, start, job.erase.bg, [...others, ...hard], size), shape: "rect" }, rotated: false };
}

/**
 * Cut `b` so it no longer enters any of `hard`: for each box it enters, keep the largest
 * part that lies entirely on one side of it. A box swallowed whole is left as it is.
 */
/**
 * The paper of a balloon whose interior could not be flood-filled, as row spans for a "mask"
 * layout: from the middle of the text, each row runs left and right over light pixels until ink
 * (the outline, a spike, a speed line); rows above and below must overlap the row next to them, so
 * the scan stops where the balloon ends. Undefined when it finds less room than the text needs.
 */
function scanBalloon(img: RGBAImage, b: Box, text: Box): LayoutArea | undefined {
  const W = img.width;
  const lightAt = (x: number, y: number) => {
    const i = (y * W + x) * 4;
    return 0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2] >= 110;
  };
  const x0 = Math.max(0, Math.ceil(b.x)), x1 = Math.min(W - 1, Math.floor(b.x + b.w) - 1);
  const y0 = Math.max(0, Math.ceil(b.y + 0.04 * b.h)), y1 = Math.min(img.height - 1, Math.floor(b.y + 0.96 * b.h) - 1);
  if (x1 - x0 < 10 || y1 - y0 < 10) return undefined;
  const rowSpan = (y: number, l: number, r: number): [number, number] | null => {
    // Start from the light pixel nearest the middle of the neighbouring row's span.
    const c = Math.round((l + r) / 2);
    let s = -1;
    for (let d = 0; d <= (r - l) / 2 + 1 && s < 0; d++) {
      if (c - d >= x0 && lightAt(c - d, y)) s = c - d;
      else if (c + d <= x1 && lightAt(c + d, y)) s = c + d;
    }
    if (s < 0) return null;
    let a = s, z = s;
    while (a - 1 >= x0 && lightAt(a - 1, y)) a--;
    while (z + 1 <= x1 && lightAt(z + 1, y)) z++;
    return z - a >= 4 ? [a, z] : null;
  };
  const raw: Array<[number, number] | null> = new Array(y1 - y0 + 1).fill(null);
  const cy = Math.min(y1, Math.max(y0, Math.round(text.y + text.h / 2)));
  const cx = Math.min(x1, Math.max(x0, Math.round(text.x + text.w / 2)));
  for (const dir of [-1, 1]) {
    let prev: [number, number] = [cx - 2, cx + 2];
    for (let y = dir < 0 ? cy : cy + 1; y >= y0 && y <= y1; y += dir) {
      const sp = rowSpan(y, prev[0], prev[1]);
      if (!sp || sp[1] < prev[0] - 2 || sp[0] > prev[1] + 2) break;
      raw[y - y0] = sp;
      prev = sp;
    }
  }
  const rows = raw.filter(Boolean).length;
  if (rows < 0.8 * Math.min(text.h, b.h * 0.9)) return undefined;
  const inset = Math.max(3, Math.round(0.06 * Math.min(b.w, b.h)));
  const spans = raw.map((s) => (s && s[1] - s[0] - 2 * inset > 6 ? ([s[0] + inset, s[1] - inset] as [number, number]) : null));
  return { x: x0, y: y0, w: x1 - x0 + 1, h: y1 - y0 + 1, shape: "mask", spans };
}

/** `b` cut to `frame` (or `b` itself when they do not meet). */
function clipTo(b: Box, frame: Box): Box {
  const x0 = Math.max(b.x, frame.x), y0 = Math.max(b.y, frame.y);
  const x1 = Math.min(b.x + b.w, frame.x + frame.w), y1 = Math.min(b.y + b.h, frame.y + frame.h);
  return x1 > x0 && y1 > y0 ? { x: x0, y: y0, w: x1 - x0, h: y1 - y0 } : b;
}

function clipAway(b: Box, hard: Box[]): Box {
  let x1 = b.x;
  let y1 = b.y;
  let x2 = b.x + b.w;
  let y2 = b.y + b.h;
  for (const h of hard) {
    if (!intersect({ x: x1, y: y1, w: x2 - x1, h: y2 - y1 }, h)) continue;
    const sides = [
      { x1: Math.max(x1, h.x + h.w), y1, x2, y2 },
      { x1, y1, x2: Math.min(x2, h.x), y2 },
      { x1, y1: Math.max(y1, h.y + h.h), x2, y2 },
      { x1, y1, x2, y2: Math.min(y2, h.y) },
    ].filter((s) => s.x2 > s.x1 && s.y2 > s.y1);
    if (!sides.length) continue;
    const best = sides.reduce((a, s) => ((s.x2 - s.x1) * (s.y2 - s.y1) > (a.x2 - a.x1) * (a.y2 - a.y1) ? s : a));
    ({ x1, y1, x2, y2 } = best);
  }
  return { x: x1, y: y1, w: x2 - x1, h: y2 - y1 };
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
/**
 * Layout for free text tilted or curved in the raw, in the source block's own frame (centred on
 * it, turned by its angle; manga-image-translator warps its rendered text onto the rotated box
 * the same way). A long text in a tilted column runs along the column. A single line on an arc
 * follows it when the whole text fits along the arc at a size close to the straight layout.
 * Undefined when the text does not fit that frame: the upright plan may grow into free paper.
 */
function planSlanted(
  s: Slant,
  text: string,
  measure: (text: string, px: number) => number,
  maxSize: number,
): { box: LayoutArea; frame: LayoutArea; layout: TextLayout; angle: number; centre: [number, number]; arc: number | undefined; doc: DocLine[] | undefined } | undefined {
  const fw = s.w * 1.1 + 4, fh = s.h * 1.1 + 4;
  const docFrame: LayoutArea = { x: 0, y: 0, w: fw, h: fh, shape: "rect" };
  const doc = s.lines && lettersOnLines(s.lines, text, measure, maxSize, fw, fh);
  if (doc) {
    const layout: TextLayout = {
      fontSize: Math.min(...doc.map((d) => d.px)),
      lineHeight: Math.max(...doc.map((d) => d.px)) * 1.16,
      lines: doc.map((d) => ({ text: d.text, cx: d.x + d.width / 2, top: d.y - d.px * 0.58, width: d.width })),
      overflow: false,
    };
    const box = rotatedBounds([s.cx, s.cy], s.angle, -fw / 2, -fh / 2, fw / 2, fh / 2);
    return { box: { ...box, shape: "rect" }, frame: docFrame, layout, angle: s.angle, centre: [s.cx, s.cy], arc: undefined, doc };
  }
  // An upright block with printed lines that the text does not suit is laid out as usual.
  if (s.angle === 0 && s.bow === undefined) return undefined;
  let frame: LayoutArea = { x: 0, y: 0, w: fw, h: fh, shape: "rect" };
  let along = false;
  let layout = layoutText(text, frame, measure, { maxSize, minSize: 9 });
  if (s.column) {
    // A column is only lettered along itself when it is long and the text does not sit well
    // across it (the margin-column rule); otherwise the upright plan, which may grow into free
    // paper beside the column, reads better.
    // Text printed in rows that only happens to sit in a tall box (a poster) is never turned.
    if (s.written === "rows" || s.h < COLUMN_RATIO * s.w || !(layout.overflow || layout.lines.length >= 5)) return undefined;
    const colFrame: LayoutArea = { x: 0, y: 0, w: fh, h: fw, shape: "rect" };
    const alt = layoutText(text, colFrame, measure, { maxSize, minSize: 9 });
    if (alt.overflow || alt.lines.length > 3) return undefined;
    layout = alt;
    frame = colFrame;
    along = true;
  }
  if (layout.overflow) layout = layoutText(text, frame, measure, { maxSize, minSize: 8 });
  // Small print on a tilted card may go a size smaller; laid out upright instead, it would cut
  // across the card, which reads worse than slightly cramped lettering on it.
  if (layout.overflow && s.angle !== 0) layout = layoutText(text, frame, measure, { maxSize, minSize: 7 });
  if (layout.overflow && s.angle === 0) return undefined;
  let arc: number | undefined;
  if (s.bow !== undefined && (!s.column || along)) {
    // Turning a column by another 90 degrees maps its +x bulge to -y in the drawing frame.
    const bow = along ? -s.bow : s.bow;
    const room = 0.95 * arcLength(frame.w, bow);
    const line = text.replace(/\s+/g, " ").trim();
    const ratio = layout.lineHeight / layout.fontSize;
    for (let px = maxSize; px >= Math.max(9, Math.round(0.8 * layout.fontSize)); px--) {
      const width = measure(line, px);
      if (width > room) continue;
      arc = bow;
      layout = { fontSize: px, lineHeight: px * ratio, lines: [{ text: line, cx: frame.w / 2, top: frame.h / 2 - (px * ratio) / 2, width }], overflow: false };
      break;
    }
  }
  const angle = s.angle + (along ? Math.PI / 2 : 0);
  const box = rotatedBounds([s.cx, s.cy], angle, -frame.w / 2, -frame.h / 2, frame.w / 2, frame.h / 2);
  return { box: { ...box, shape: "rect" }, frame, layout, angle, centre: [s.cx, s.cy], arc, doc: undefined };
}

/** A region's lettering plan: where and how its Vietnamese is set (see `renderTranslation`, step 3). */
type Plan = Job & {
  box: LayoutArea;
  frame: LayoutArea;
  rotated: boolean;
  bold: boolean;
  measure: (text: string, px: number) => number;
  maxSize: number;
  layout: TextLayout;
  angle: number | undefined;
  centre: [number, number] | undefined;
  arc: number | undefined;
  doc: DocLine[] | undefined;
  /** A shout lettered big, in capitals (displayPlan). */
  display?: boolean;
};

/** Source glyphs at least this many times the page's usual size are display lettering (see displayPlan). */
const DISPLAY_GLYPHS = 2;

/**
 * A shout is lettered as the raw draws it. Japanese has no capitals: a scream is drawn with
 * glyphs two or three times the dialogue size, often down a tall column of its own. The
 * Vietnamese keeps that: capitals, bold, sized from the source glyphs (not the page's dialogue
 * size), filling the place the Japanese took. One short word in a tall column is stacked letter
 * by letter like the raw (a stretched sound keeps at most three repeats then, so the letters stay
 * big); anything else is one or two big lines across. Nothing is turned on its side.
 *
 * Only short text (one or two words) that the reader model marked as a shout and that is drawn
 * bigger than the page's usual text, or a short word drawn at twice the usual size; ordinary lines
 * (a relieved "thank goodness!") keep their case and size.
 */
function displayPlan(
  img: RGBAImage,
  job: Job,
  box: LayoutArea,
  charSize: number,
  typicalGlyph: number,
  measure: (text: string, px: number) => number,
): Pick<Plan, "box" | "frame" | "rotated" | "measure" | "maxSize" | "layout" | "display"> | undefined {
  const vi = job.t.vi.trim().normalize("NFC");
  const words = vi.split(/\s+/).length;
  const letters = vi.replace(/[^\p{L}\p{N}]/gu, "").length;
  // Size alone is weak evidence (a loose box around one or two kana looks big): without the model's
  // "shout" it takes glyphs twice the usual size and a short word.
  const big = typicalGlyph > 0 && charSize >= DISPLAY_GLYPHS * typicalGlyph && letters <= 8;
  const shout = job.t.style.includes("shout") && charSize >= 1.3 * typicalGlyph;
  if (words > 2 || letters > 14 || charSize < 30 || !(big || shout)) return undefined;
  const text = vi.toLocaleUpperCase("vi");
  const src = job.seed ?? job.r.box;
  // Big letters go where the paper is clean: a stroke the erase could not take (a hollow glyph
  // joined to a burst's edge) must not end up under a capital.
  const room = cleanRows(img, intersect(src, box) ?? src);
  if (!room) return undefined;
  const rect: LayoutArea = { x: room.x, y: room.y, w: room.w, h: room.h, shape: "rect" };
  const cap = Math.min(110, Math.round(0.9 * charSize));
  const base = { box: rect, measure, maxSize: cap, display: true as const };
  const across = layoutText(text, rect, measure, { maxSize: cap, minSize: 12 });
  // Never turned on its side: a reader tilts the head for that. Upright letters stacked down a
  // tall column read like the raw, but only for one short word (UWA!, HỪ?, KHÔNGGG!): a name or a
  // phrase stacked letter by letter (H-A-M-C-H-A-N) is hard to read, so it goes across in capitals.
  const word = text.replace(/(\p{L})\1{3,}/gu, "$1$1$1");
  const plain = words === 1 && /^[\p{L}]+[!?.…~]*$/u.test(word) && word.replace(/[^\p{L}]/gu, "").length <= 7;
  if (plain && rect.h >= 1.8 * rect.w) {
    const stacked = stackLetters(word, rect, measure, cap);
    if (stacked && stacked.fontSize >= Math.max(18, 0.8 * across.fontSize)) return { ...base, frame: rect, rotated: false, layout: stacked };
  }
  return across.overflow ? undefined : { ...base, frame: rect, rotated: false, layout: across };
}

/** The longest run of rows of `r` with almost no ink across its middle 80%, if it keeps half of `r`. */
function cleanRows(img: RGBAImage, r: Box): Box | undefined {
  const b = roundBox(clampBox(r, img.width, img.height));
  const x0 = Math.round(b.x + 0.1 * b.w), x1 = Math.round(b.x + 0.9 * b.w);
  let best = { y: b.y, h: 0 };
  let start = b.y;
  for (let y = b.y; y <= b.y + b.h; y++) {
    let dark = 0;
    if (y < b.y + b.h)
      for (let x = x0; x < x1; x++) {
        const i = (y * img.width + x) * 4;
        if (0.299 * img.data[i] + 0.587 * img.data[i + 1] + 0.114 * img.data[i + 2] < 110) dark++;
      }
    if (y === b.y + b.h || dark > 0.06 * (x1 - x0)) {
      if (y - start > best.h) best = { y: start, h: y - start };
      start = y + 1;
    }
  }
  return best.h >= 0.5 * b.h ? { x: b.x, y: best.y, w: b.w, h: best.h } : undefined;
}

/** Capitals stacked one per line down a column, centred, as big as the column allows. */
function stackLetters(text: string, r: LayoutArea, measure: (text: string, px: number) => number, cap: number): TextLayout | undefined {
  const chars = [...text.replace(/\s+/g, "")];
  if (chars.length < 2) return undefined;
  const step = 1.04;
  let size = Math.min(cap, Math.floor((r.h * 0.96) / (chars.length * step)));
  while (size >= 12 && Math.max(...chars.map((c) => measure(c, size))) > r.w * 0.92) size--;
  if (size < 12) return undefined;
  const lh = size * step;
  const top0 = r.y + (r.h - chars.length * lh) / 2;
  return { fontSize: size, lineHeight: lh, overflow: false, lines: chars.map((c, i) => ({ text: c, cx: r.x + r.w / 2, top: top0 + i * lh, width: measure(c, size) })) };
}

/** One lettered line of a card, form or letter, in its frame (top-left origin, `y` = middle). */
interface DocLine {
  text: string;
  x: number;
  y: number;
  px: number;
  width: number;
}

/**
 * The Vietnamese set line by line on the printed lines of the source (manga-image-translator
 * translates and letters each text line on its own, so a form keeps its rows): each line keeps
 * its place, left edge and height. Line breaks the model gave are used when they match the
 * printed lines; otherwise the words are split so every line is about as full as its source line.
 * Undefined when the text cannot fill the lines at 0.6 of their size or is far shorter than them
 * (then one block reads better).
 */
function lettersOnLines(
  lines: NonNullable<Slant["lines"]>,
  text: string,
  measure: (text: string, px: number) => number,
  maxSize: number,
  fw: number,
  fh: number,
): DocLine[] | undefined {
  const n = lines.length;
  // Vietnamese at the height of the printed line (its diacritics take the room ruby or leading leaves).
  const base = lines.map((l) => Math.max(8, Math.min(maxSize, Math.round(l.v1 - l.v0))));
  const room = lines.map((l, k) => (k === n - 1 ? fw / 2 - l.u0 : l.u1 - l.u0));
  const given = text.split("\n").map((p) => p.trim()).filter(Boolean);
  let parts: string[];
  if (given.length === n) parts = given;
  else {
    const words = text.replace(/\s+/g, " ").trim().split(" ");
    if (words.length < n) return undefined;
    // Width of words[i..j) on line k, from per-word widths at that line's size.
    const wd = base.map((px) => words.map((w) => measure(w, px)));
    const space = base.map((px) => measure(" ", px) || px * 0.28);
    const width = (k: number, i: number, j: number) => {
      let s = space[k] * (j - i - 1);
      for (let q = i; q < j; q++) s += wd[k][q];
      return s;
    };
    const natural = lines.reduce((a, _, k) => a + width(k, 0, words.length) / n, 0);
    if (natural < 0.5 * room.reduce((a, b) => a + b, 0)) return undefined;
    // Split minimising the fullest line (fill = width / room), every line non-empty.
    const W = words.length;
    const best = Array.from({ length: n + 1 }, () => new Array<number>(W + 1).fill(Infinity));
    const cut = Array.from({ length: n + 1 }, () => new Array<number>(W + 1).fill(0));
    best[0][0] = 0;
    for (let k = 1; k <= n; k++)
      for (let j = k; j <= W - (n - k); j++)
        for (let i = k - 1; i < j; i++) {
          if (best[k - 1][i] === Infinity) continue;
          const v = Math.max(best[k - 1][i], width(k - 1, i, j) / room[k - 1]);
          if (v < best[k][j]) {
            best[k][j] = v;
            cut[k][j] = i;
          }
        }
    parts = new Array<string>(n);
    for (let k = n, j = W; k > 0; k--) {
      const i = cut[k][j];
      parts[k - 1] = words.slice(i, j).join(" ");
      j = i;
    }
  }
  const fill = Math.max(...parts.map((p, k) => measure(p, base[k]) / room[k]));
  const scale = Math.min(1, 0.98 / fill);
  // Breaks the model gave are meant for these rows: they may set a little smaller before giving up.
  if (scale < (given.length === n ? 0.45 : 0.6)) return undefined;
  return parts.map((p, k) => {
    const px = Math.max(8, Math.floor(base[k] * scale));
    const l = lines[k];
    return { text: p, x: fw / 2 + l.u0, y: fh / 2 + (l.v0 + l.v1) / 2, px, width: measure(p, px) };
  });
}

/** Page bounds of the frame rectangle (u0, v0)-(u1, v1), relative to `centre`, turned by `angle`. */
function rotatedBounds(centre: [number, number], angle: number, u0: number, v0: number, u1: number, v1: number): Box {
  const c = Math.cos(angle), s = Math.sin(angle);
  const pts = [[u0, v0], [u1, v0], [u1, v1], [u0, v1]].map(([u, v]) => [centre[0] + u * c - v * s, centre[1] + u * s + v * c]);
  const xs = pts.map((p) => p[0]), ys = pts.map((p) => p[1]);
  const x = Math.min(...xs), y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

type Quad = Array<[number, number]>;
type PlanShape = { layout: TextLayout; box: LayoutArea; frame: LayoutArea; rotated: boolean; angle?: number; centre?: [number, number]; arc?: number };

/** Corners of a plan's lettering on the page, whether upright, turned along a column, tilted or on an arc. */
function quadOf(p: PlanShape): Quad | undefined {
  if (p.angle === undefined || !p.centre) {
    const b = textBounds(p.layout, p.box, p.rotated);
    return b && [[b.x, b.y], [b.x + b.w, b.y], [b.x + b.w, b.y + b.h], [b.x, b.y + b.h]];
  }
  const t =
    p.arc !== undefined && p.layout.lines.length
      ? { x: p.frame.w / 2 - p.layout.lines[0].width / 2, y: p.frame.h / 2 - Math.abs(p.arc) / 2 - p.layout.lineHeight / 2, w: p.layout.lines[0].width, h: Math.abs(p.arc) + p.layout.lineHeight }
      : textBounds(p.layout, p.frame);
  if (!t) return undefined;
  const c = Math.cos(p.angle), s = Math.sin(p.angle);
  const [cx, cy] = p.centre;
  const u0 = t.x - p.frame.w / 2, v0 = t.y - p.frame.h / 2, u1 = u0 + t.w, v1 = v0 + t.h;
  return [[u0, v0], [u1, v0], [u1, v1], [u0, v1]].map(([u, v]) => [cx + u * c - v * s, cy + u * s + v * c]);
}

function quadBounds(q: Quad): Box {
  const xs = q.map((p) => p[0]), ys = q.map((p) => p[1]);
  const x = Math.min(...xs), y = Math.min(...ys);
  return { x, y, w: Math.max(...xs) - x, h: Math.max(...ys) - y };
}

/** Do two convex quads come within `gap` px of each other? (Separating axis test on their edges.) */
export function quadsTouch(a: Quad, b: Quad, gap: number): boolean {
  for (const poly of [a, b])
    for (let i = 0; i < poly.length; i++) {
      const [x1, y1] = poly[i], [x2, y2] = poly[(i + 1) % poly.length];
      const len = Math.hypot(x2 - x1, y2 - y1);
      if (!len) continue;
      const nx = (y1 - y2) / len, ny = (x2 - x1) / len;
      const pa = a.map(([x, y]) => x * nx + y * ny), pb = b.map(([x, y]) => x * nx + y * ny);
      if (Math.max(...pa) + gap <= Math.min(...pb) || Math.max(...pb) + gap <= Math.min(...pa)) return false;
    }
  return true;
}

/** Page bounds of a plan's lettering. */
function boundsOf(p: PlanShape): Box | undefined {
  const q = quadOf(p);
  return q && quadBounds(q);
}

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
export function cornersFlat(img: RGBAImage, b: Box): boolean {
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

export * from "./notes";
