import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import * as ort from "onnxruntime-node";
import { createCanvas } from "@napi-rs/canvas";
import { area, artTextMask, clampBox, containment, expand, glyphResidue, holeRingStd, patchBlends, roundBox, textArea, type Box, type InpaintJob, type LearnedMask, type PageResult, type PatchData, type RGBAImage, type TextRegion } from "@lt/core";
import { cornersFlat } from "@lt/render";
import { detectInCrop } from "./detector";
import { INPAINT_DEVICE, INPAINT_ENGINE, LAMA_DEVICE, sessionOptions, type InpaintDevice } from "./device";
import { ROOT } from "./env";
import type { DecodedPage } from "./image";
import { LAMA_MODELS, loadLama, runLama, type LamaVariant } from "./lama";

/** andraniksargsyan/migan @ 406830d0fa60666da0071c342ad2fbc8f30c5c64, MIT (Picsart AI Research). */
export const MIGAN_FILE = join(ROOT, "models", "inpaint", "migan_pipeline_v2.onnx");
export const MIGAN_SHA256 = "6f1f3530a1a2324b19752018ce756088b07973cda8d7d890034ace5c8a48c40b";

const sessions = new Map<InpaintDevice, Promise<ort.InferenceSession>>();

export function loadInpainter(device: InpaintDevice = INPAINT_DEVICE): Promise<ort.InferenceSession> {
  let s = sessions.get(device);
  if (!s) {
    s = (async () => {
      const bytes = await readFile(MIGAN_FILE);
      const sha = createHash("sha256").update(bytes).digest("hex");
      if (sha !== MIGAN_SHA256) throw new Error(`MI-GAN checksum mismatch (${sha})`);
      return ort.InferenceSession.create(bytes, sessionOptions(device));
    })();
    sessions.set(device, s);
  }
  return s;
}

/**
 * TareHimself/comic-text-mask @ ebd37f1a9ae9298519678fb96a796573fb602977, MIT: a U-Net (ResNet-18) that
 * marks text pixels in a text crop. model.safetensors (sha256 ab28dd8450462c4f87ddfd05d13601813bb90414f26bea5590bf6a0a7540f988)
 * was rebuilt as this ONNX op by op, without torch or code from the download; /255, ImageNet
 * normalisation and the sigmoid are inside, so it takes letterboxed uint8 RGB 384x384.
 */
export const TEXTMASK_FILE = join(ROOT, "models", "textmask", "comic_text_mask_384.onnx");
export const TEXTMASK_SHA256 = "e8b5cb31222581b5c8b9ac9a567d5cac578f52c1db890e7045bd41ce453fcd01";
const TM = 384;

/**
 * comic-text-detector (dmMaze, GPL-3.0; trained on Manga109-s, Digital Comic Museum and synthetic
 * pages), the ONNX that manga-image-translator publishes (release beta-0.3, comictextdetector.pt.onnx,
 * used as is). Its "seg" output marks text pixels on the whole page from a 1024x1024 letterbox.
 */
export const CTD_FILE = join(ROOT, "models", "textmask", "comictextdetector.pt.onnx");
export const CTD_SHA256 = "1a86ace74961413cbd650002e7bb4dcec4980ffa21b2f19b86933372071d718f";
const CTD = 1024;

/** Learned text-mask models: comic-text-mask on each region's crop, comic-text-detector on the page. */
export type TextMaskModel = "ctm" | "ctd";
const TEXTMASK_MODELS: Record<TextMaskModel, { file: string; sha256: string }> = {
  ctm: { file: TEXTMASK_FILE, sha256: TEXTMASK_SHA256 },
  ctd: { file: CTD_FILE, sha256: CTD_SHA256 },
};

/** INPAINT_TEXTMASK adds a learned text mask to the rule-based hole (prototype, off by default): 1 or ctm, or ctd. */
const textMaskWanted: TextMaskModel | undefined = (() => {
  const v = process.env.INPAINT_TEXTMASK;
  if (!v) return undefined;
  if (v === "1") return "ctm";
  if (!(v in TEXTMASK_MODELS)) throw new Error("INPAINT_TEXTMASK must be 1, ctm or ctd");
  return v as TextMaskModel;
})();
const textMaskers = new Map<string, Promise<ort.InferenceSession>>();

export function loadTextMasker(model: TextMaskModel = "ctm", device: InpaintDevice = INPAINT_DEVICE): Promise<ort.InferenceSession> {
  let s = textMaskers.get(`${model}|${device}`);
  if (!s) {
    s = (async () => {
      const bytes = await readFile(TEXTMASK_MODELS[model].file);
      const sha = createHash("sha256").update(bytes).digest("hex");
      if (sha !== TEXTMASK_MODELS[model].sha256) throw new Error(`text mask model (${model}) checksum mismatch (${sha})`);
      return ort.InferenceSession.create(bytes, sessionOptions(device));
    })();
    textMaskers.set(`${model}|${device}`, s);
  }
  return s;
}

/**
 * comic-text-detector's text mask over the whole page: the page is scaled into the top-left of a
 * black 1024x1024 square (RGB / 255), and the "seg" map is sampled back to page pixels.
 */
export async function ctdPageMask(s: ort.InferenceSession, full: RGBAImage): Promise<LearnedMask> {
  const r = Math.min(CTD / full.width, CTD / full.height);
  const sw = Math.max(1, Math.round(full.width * r));
  const sh = Math.max(1, Math.round(full.height * r));
  const page = createCanvas(full.width, full.height);
  const pctx = page.getContext("2d");
  const id = pctx.createImageData(full.width, full.height);
  id.data.set(full.data);
  pctx.putImageData(id, 0, 0);
  const sq = createCanvas(CTD, CTD);
  const q = sq.getContext("2d");
  q.fillStyle = "#000";
  q.fillRect(0, 0, CTD, CTD);
  q.imageSmoothingQuality = "high";
  q.drawImage(page, 0, 0, sw, sh);
  const px = q.getImageData(0, 0, CTD, CTD).data;
  const input = new Float32Array(3 * CTD * CTD);
  for (let p = 0; p < CTD * CTD; p++) {
    input[p] = px[p * 4] / 255;
    input[CTD * CTD + p] = px[p * 4 + 1] / 255;
    input[2 * CTD * CTD + p] = px[p * 4 + 2] / 255;
  }
  const res = await s.run({ [s.inputNames[0]]: new ort.Tensor("float32", input, [1, 3, CTD, CTD]) });
  return { box: { x: 0, y: 0, w: full.width, h: full.height }, prob: sampleBack(res.seg.data as Float32Array, CTD, 0, 0, r, full.width, full.height) };
}

/** Bilinear sample of an n x n probability map at each output pixel's centre (map = offset + scale * pixel). */
function sampleBack(prob: Float32Array, n: number, dx: number, dy: number, sc: number, w: number, h: number): Uint8Array {
  const out = new Uint8Array(w * h);
  for (let y = 0; y < h; y++) {
    const fy = Math.min(n - 1, Math.max(0, dy + (y + 0.5) * sc - 0.5));
    const y0 = Math.floor(fy);
    const y1 = Math.min(n - 1, y0 + 1);
    const ty = fy - y0;
    for (let x = 0; x < w; x++) {
      const fx = Math.min(n - 1, Math.max(0, dx + (x + 0.5) * sc - 0.5));
      const x0 = Math.floor(fx);
      const x1 = Math.min(n - 1, x0 + 1);
      const tx = fx - x0;
      const v = (1 - ty) * ((1 - tx) * prob[y0 * n + x0] + tx * prob[y0 * n + x1]) + ty * ((1 - tx) * prob[y1 * n + x0] + tx * prob[y1 * n + x1]);
      out[y * w + x] = Math.round(255 * Math.min(1, Math.max(0, v)));
    }
  }
  return out;
}

/**
 * Learned text probability over a text region: the members' union with a little margin (the
 * crop a detector gives) is letterboxed into 384x384 on black, segmented, and the map is
 * sampled back to the crop's own pixels.
 */
export async function learnedTextMask(s: ort.InferenceSession, full: RGBAImage, members: Box[]): Promise<LearnedMask> {
  const u = members.reduce((a, m) => ({ x: Math.min(a.x, m.x), y: Math.min(a.y, m.y), w: Math.max(a.x + a.w, m.x + m.w) - Math.min(a.x, m.x), h: Math.max(a.y + a.h, m.y + m.h) - Math.min(a.y, m.y) }));
  const box = roundBox(clampBox(expand(u, Math.max(4, Math.round(0.06 * Math.max(u.w, u.h)))), full.width, full.height));
  const sc = TM / Math.max(box.w, box.h);
  const sw = Math.max(1, Math.round(box.w * sc));
  const sh = Math.max(1, Math.round(box.h * sc));
  const dx = Math.floor((TM - sw) / 2);
  const dy = Math.floor((TM - sh) / 2);
  const src = createCanvas(box.w, box.h);
  const sctx = src.getContext("2d");
  const id = sctx.createImageData(box.w, box.h);
  for (let y = 0; y < box.h; y++)
    for (let x = 0; x < box.w; x++) {
      const i = ((box.y + y) * full.width + box.x + x) * 4;
      const o = (y * box.w + x) * 4;
      id.data[o] = full.data[i];
      id.data[o + 1] = full.data[i + 1];
      id.data[o + 2] = full.data[i + 2];
      id.data[o + 3] = 255;
    }
  sctx.putImageData(id, 0, 0);
  const sq = createCanvas(TM, TM);
  const q = sq.getContext("2d");
  q.fillStyle = "#000";
  q.fillRect(0, 0, TM, TM);
  q.imageSmoothingQuality = "high";
  q.drawImage(src, dx, dy, sw, sh);
  const px = q.getImageData(0, 0, TM, TM).data;
  const input = new Uint8Array(3 * TM * TM);
  for (let p = 0; p < TM * TM; p++) {
    input[p] = px[p * 4];
    input[TM * TM + p] = px[p * 4 + 1];
    input[2 * TM * TM + p] = px[p * 4 + 2];
  }
  const res = await s.run({ image: new ort.Tensor("uint8", input, [1, 3, TM, TM]) });
  return { box, prob: sampleBack(res.prob.data as Float32Array, TM, dx, dy, sc, box.w, box.h) };
}

/**
 * AOT inpainter, manga-image-translator's default (GPL-3.0 project; training data not stated): release
 * beta-0.3 inpainting.ckpt (sha256 878d541c68648969bc1b042a6e997f3a58e49b6c07c5636ad55130736977149f),
 * gated convolutions with dilated AOT blocks, 5.7 M parameters. Exported with torch from tensors only
 * (weights_only); takes image 0..1 and mask (1 = hole) of any size that is a multiple of 8.
 */
export const AOT_FILE = join(ROOT, "models", "inpaint", "aot_manga.onnx");
export const AOT_SHA256 = "285d51b177010162ddbf4c5948d51173f0c75e90b0566a22e77eb22aeba01234";
const aotSessions = new Map<InpaintDevice, Promise<ort.InferenceSession>>();

export function loadAot(device: InpaintDevice = INPAINT_DEVICE): Promise<ort.InferenceSession> {
  let s = aotSessions.get(device);
  if (!s) {
    s = (async () => {
      const bytes = await readFile(AOT_FILE);
      const sha = createHash("sha256").update(bytes).digest("hex");
      if (sha !== AOT_SHA256) throw new Error(`AOT checksum mismatch (${sha})`);
      return ort.InferenceSession.create(bytes, sessionOptions(device));
    })();
    aotSessions.set(device, s);
  }
  return s;
}

/** Reconstruct the job's hole with AOT at the crop's own size (grown to a multiple of 8 from the page, edge pixels past it). */
export async function runAot(s: ort.InferenceSession, full: RGBAImage, job: InpaintJob): Promise<Uint8Array> {
  const { x, y, w, h } = job.crop;
  const W = Math.ceil(w / 8) * 8;
  const H = Math.ceil(h / 8) * 8;
  const image = new Float32Array(3 * W * H);
  const mask = new Float32Array(W * H);
  for (let yy = 0; yy < H; yy++)
    for (let xx = 0; xx < W; xx++) {
      const i = (Math.min(full.height - 1, y + yy) * full.width + Math.min(full.width - 1, x + xx)) * 4;
      const p = yy * W + xx;
      image[p] = full.data[i] / 255;
      image[W * H + p] = full.data[i + 1] / 255;
      image[2 * W * H + p] = full.data[i + 2] / 255;
      if (yy < h && xx < w && job.hole[yy * w + xx]) mask[p] = 1;
    }
  const res = await s.run({ image: new ort.Tensor("float32", image, [1, 3, H, W]), mask: new ort.Tensor("float32", mask, [1, 1, H, W]) });
  const out = res[s.outputNames[0]].data as Float32Array;
  const n = w * h;
  const result = new Uint8Array(3 * n);
  for (let yy = 0; yy < h; yy++)
    for (let xx = 0; xx < w; xx++)
      for (let c = 0; c < 3; c++) result[c * n + yy * w + xx] = Math.round(out[c * W * H + yy * W + xx]);
  return result;
}

/** INPAINT_ENGINE=aot redraws every hole with AOT (read here: device.ts types the auto|migan|lama choice). */
const aotWanted = process.env.INPAINT_ENGINE === "aot";

/**
 * How far the hole grows around the strokes (INPAINT_GROW): a fixed number of pixels (default 3),
 * "text" for 0.15 of the character size (at least 3), or "mit" for manga-image-translator's default
 * (an ellipse 0.3 x (size + 20) wide, then 1 px more).
 */
const GROW: (charSize: number) => number = (() => {
  const v = process.env.INPAINT_GROW ?? "3";
  if (v === "text") return (cs: number) => Math.max(3, 0.15 * cs);
  if (v === "mit") return (cs: number) => (Math.max(Math.floor(((cs + 20) * 0.3) / 2) * 2 + 1, 3) - 1) / 2 + 1;
  const px = Number(v);
  if (!(px >= 1)) throw new Error("INPAINT_GROW must be a pixel count, text or mit");
  return () => px;
})();

/** LaMa once loaded; until then (it takes ~20 s) every hole goes to MI-GAN rather than wait. */
let lama: ort.InferenceSession | undefined;
let lamaLoading: Promise<void> | undefined;
const lamaWanted = INPAINT_ENGINE === "lama" || (INPAINT_ENGINE === "auto" && INPAINT_DEVICE !== "cpu");

/** Which LaMa weights the "lama" engine runs (INPAINT_LAMA, see LAMA_MODELS): big-lama by default. */
export const LAMA_VARIANT: LamaVariant = (() => {
  const v = process.env.INPAINT_LAMA ?? "lama";
  if (!(v in LAMA_MODELS)) throw new Error(`INPAINT_LAMA must be one of ${Object.keys(LAMA_MODELS).join(", ")}`);
  return v as LamaVariant;
})();

/** Load the inpainters the settings call for, in the background (server start). */
export function warmInpainters(): Promise<void> {
  const migan = loadInpainter().then(() => undefined);
  if (lamaWanted)
    lamaLoading ??= loadLama(LAMA_VARIANT, LAMA_DEVICE).then(
      (s) => void (lama = s),
      (e: Error) => console.error(`LaMa (${LAMA_VARIANT}) failed to load on ${LAMA_DEVICE}, MI-GAN only:`, e.message),
    );
  return Promise.all([migan, lamaLoading]).then(() => undefined);
}

/** The engine for one hole: LaMa where it is ready and wanted, MI-GAN otherwise. */
function engineFor(full: RGBAImage, job: InpaintJob): "migan" | "lama" {
  if (!lama) return "migan";
  if (INPAINT_ENGINE === "lama") return "lama";
  // Textured surroundings (hatching, screentone): MI-GAN leaves grey ghosts of the letters there.
  return holeRingStd(full, job) > TEXTURED_RING ? "lama" : "migan";
}

/** Ring spread above which a hole counts as sitting in textured art. */
const TEXTURED_RING = 30;

export type Patch = PatchData;

/** Diagnostics for a reconstruction that needed the fallback (the text is still redrawn). */
export interface Rejected {
  id: string;
  /** bold-text: display lettering drawn with thick strokes stays part of the art (no patch). */
  reason: "rect-fallback" | "glyphs-survived" | "visible-patch" | "bold-text";
  coverage: number;
}

/** Glyph-shaped ink left in the text core after reconstruction that triggers a whole-box retry. */
const MAX_RESIDUE_AFTER = 0.02;

/** Reconstruct the artwork under each region's text (MI-GAN, or LaMa in textured art; see `engineFor`). */
export async function inpaintRegions(
  page: DecodedPage,
  regions: TextRegion[],
  charSizes: Record<string, number> = {},
  rejected: Rejected[] = [],
): Promise<Patch[]> {
  const s = await loadInpainter();
  const masker = textMaskWanted ? await loadTextMasker(textMaskWanted) : undefined;
  const pageMask = masker && textMaskWanted === "ctd" ? await ctdPageMask(masker, page.ctx.getImageData(0, 0, page.w, page.h)) : undefined;
  if (lamaWanted) void warmInpainters();
  const full = page.ctx.getImageData(0, 0, page.w, page.h);
  const aot = aotWanted ? await loadAot() : undefined;
  let engine: "migan" | "lama" | "aot" = "migan";
  const redraw = (job: InpaintJob) => {
    if (aot) {
      engine = "aot";
      return runAot(aot, full, job);
    }
    engine = engineFor(full, job);
    return engine === "lama" ? runLama(lama!, full, job) : runMigan(s, full, job);
  };
  const out: Patch[] = [];
  for (const r of regions) {
    const t0 = performance.now();
    const members = r.bubble ? textArea(r, cornersFlat(full, r.bubble)) : await refineTextBoxes(page, r);
    // The size guess is box area / character count: a tighter box means smaller glyphs.
    const cs = charSizes[r.id] && Math.sqrt((charSizes[r.id] ** 2 * members.reduce((a, m) => a + area(m), 0)) / area(r.box));
    const learned = pageMask ?? (masker ? await learnedTextMask(masker, full, members) : undefined);
    let job = artTextMask(full, members, { charSize: cs, learned, grow: GROW });
    if (job.bold) {
      rejected.push({ id: r.id, reason: "bold-text", coverage: job.coverage });
      continue;
    }
    let result = await redraw(job);
    if (job.rect) rejected.push({ id: r.id, reason: "rect-fallback", coverage: job.coverage });
    else if (residueAfter(full, result, job, members, cs) > MAX_RESIDUE_AFTER) {
      // Strokes escaped the glyph mask: reconstruct the whole text box instead (protected art stays).
      rejected.push({ id: r.id, reason: "glyphs-survived", coverage: job.coverage });
      job = artTextMask(full, members, { charSize: cs, rect: true });
      result = await redraw(job);
    } else if (!patchBlends(full, result, job).ok) {
      rejected.push({ id: r.id, reason: "visible-patch", coverage: job.coverage });
    }
    const { x, y, w, h } = job.crop;
    const n = w * h;
    const canvas = createCanvas(w, h);
    const ctx = canvas.getContext("2d");
    const patch = ctx.createImageData(w, h);
    for (let p = 0; p < n; p++) {
      const px = p % w;
      const py = (p - px) / w;
      const i = ((y + py) * page.w + (x + px)) * 4;
      const hole = job.hole[p] === 1;
      // Only hole pixels change; everything else stays the source pixel.
      patch.data[p * 4] = hole ? result[p] : full.data[i];
      patch.data[p * 4 + 1] = hole ? result[n + p] : full.data[i + 1];
      patch.data[p * 4 + 2] = hole ? result[2 * n + p] : full.data[i + 2];
      // Transparent outside the hole: overlapping patches must never paint back source pixels.
      patch.data[p * 4 + 3] = hole ? 255 : 0;
    }
    ctx.putImageData(patch, 0, 0);
    const png = await canvas.encode("png");
    out.push({ id: r.id, x, y, w, h, dataUrl: `data:image/png;base64,${png.toString("base64")}`, coverage: job.coverage, ms: Math.round(performance.now() - t0), textBoxes: members, textExtent: job.extent, engine: engine as Patch["engine"] }); // "aot" is a diagnostic label PatchData does not list yet
  }
  return out;
}

export async function runMigan(s: ort.InferenceSession, full: RGBAImage, job: InpaintJob): Promise<Uint8Array> {
  const { x, y, w, h } = job.crop;
  const n = w * h;
  const image = new Uint8Array(3 * n);
  const mask = new Uint8Array(n);
  for (let p = 0; p < n; p++) {
    const px = p % w;
    const py = (p - px) / w;
    const i = ((y + py) * full.width + (x + px)) * 4;
    image[p] = full.data[i];
    image[n + p] = full.data[i + 1];
    image[2 * n + p] = full.data[i + 2];
    mask[p] = job.hole[p] ? 0 : 255;
  }
  const res = await s.run({
    image: new ort.Tensor("uint8", image, [1, 3, h, w]),
    mask: new ort.Tensor("uint8", mask, [1, 1, h, w]),
  });
  return res.result.data as Uint8Array;
}

/**
 * Tight text boxes for a free-text region. The page detector sees small text at about
 * half size and returns loose boxes that swallow nearby art (a whisper beside a face);
 * detecting again on a zoomed crop boxes the text itself. Falls back to the region's
 * own boxes when nothing better is found.
 */
export async function refineTextBoxes(page: DecodedPage, r: TextRegion): Promise<Box[]> {
  const u = r.box;
  const crop = roundBox(clampBox(expand(u, Math.max(10, 0.4 * Math.max(u.w, u.h))), page.w, page.h));
  if (640 / Math.max(crop.w, crop.h) < 1.5) return r.members; // big text: page-level boxes are already tight
  const near = expand(u, 6);
  const boxes = (await detectInCrop(page, crop, 0.25)).map((d) => d.box).filter((b) => containment(b, near) >= 0.6);
  if (!boxes.length) return r.members;
  return boxes.reduce((a, b) => a + area(b), 0) < 0.9 * area(u) ? boxes : r.members;
}

/** Glyph residue of the text boxes after compositing the reconstruction into a copy of the crop. */
function residueAfter(full: RGBAImage, result: Uint8Array, job: InpaintJob, members: Box[], charSize?: number): number {
  const { x, y, w, h } = job.crop;
  const n = w * h;
  const data = new Uint8ClampedArray(n * 4);
  for (let p = 0; p < n; p++) {
    const px = p % w;
    const py = (p - px) / w;
    const i = ((y + py) * full.width + (x + px)) * 4;
    const hole = job.hole[p] === 1;
    data[p * 4] = hole ? result[p] : full.data[i];
    data[p * 4 + 1] = hole ? result[n + p] : full.data[i + 1];
    data[p * 4 + 2] = hole ? result[2 * n + p] : full.data[i + 2];
    data[p * 4 + 3] = 255;
  }
  const local = members.map((m) => ({ x: m.x - x, y: m.y - y, w: m.w, h: m.h }));
  return glyphResidue({ width: w, height: h, data }, local, charSize);
}

/** Estimated source glyph size per region, from the transcription length. */
export function charSizesFor(result: PageResult): Record<string, number> {
  const out: Record<string, number> = {};
  for (const r of result.regions) {
    const n = [...(result.translations[r.id]?.ja ?? "").replace(/\s/g, "")].length;
    if (n) out[r.id] = Math.sqrt(area(r.box) / n);
  }
  return out;
}
