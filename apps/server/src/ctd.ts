/**
 * comic-text-detector (dmMaze, GPL-3.0; trained on Manga109-s, Digital Comic Museum and synthetic
 * pages), the ONNX that manga-image-translator publishes (release beta-0.3, comictextdetector.pt.onnx,
 * used as is). One run on a 1024x1024 letterbox of the page gives text blocks ("blk", YOLO rows of
 * cx, cy, w, h, objectness and two class scores), a text-pixel mask ("seg") and text-line maps ("det").
 *
 * Here it is the second detector: manga-image-translator finds text with a segmentation model at
 * 2048 px, and our page detector (640 px) misses small balloons on dark ground, name labels and
 * handwriting. On the 60 GT/team pages its blocks found 17 of the 32 text boxes no region covered,
 * for 0.17 s/page on DirectML. Its Manga109-s training data allows commercial use of results with the
 * dataset credited (licenses.ts: "credit"); the paid tier still only runs it while that record allows it.
 */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import * as ort from "onnxruntime-node";
import { createCanvas } from "@napi-rs/canvas";
import type { Box } from "@lt/core";
import { INPAINT_DEVICE, sessionOptions, type InpaintDevice } from "./device";
import { ROOT } from "./env";
import { modelAllowed } from "./licenses";
import type { DecodedPage } from "./image";

export const CTD_FILE = join(ROOT, "models", "textmask", "comictextdetector.pt.onnx");
export const CTD_SHA256 = "1a86ace74961413cbd650002e7bb4dcec4980ffa21b2f19b86933372071d718f";
export const CTD_INPUT = 1024;

/**
 * Second detector: on with a GPU (DirectML/WebGPU: +0.1 s per page, it runs beside the page
 * detector), off on CPU only (1.6 s per page, the first bubble would wait for it) unless
 * DETECT_CTD=1; DETECT_CTD=0 always turns it off. A missing model file only logs a warning.
 */
export const CTD_WANTED = modelAllowed("comic-text-detector") && (process.env.DETECT_CTD === "1" || (process.env.DETECT_CTD !== "0" && INPAINT_DEVICE !== "cpu"));

/** Block confidence (objectness x class) kept: 0.4 found the most missed text; most extra blocks were real (sound effects). */
export const CTD_MIN_CONF = 0.4;

const sessions = new Map<InpaintDevice, Promise<ort.InferenceSession>>();

export function loadCtd(device: InpaintDevice = INPAINT_DEVICE): Promise<ort.InferenceSession> {
  let s = sessions.get(device);
  if (!s) {
    s = (async () => {
      const bytes = await readFile(CTD_FILE);
      const sha = createHash("sha256").update(bytes).digest("hex");
      if (sha !== CTD_SHA256) throw new Error(`comic-text-detector checksum mismatch (${sha})`);
      return ort.InferenceSession.create(bytes, sessionOptions(device));
    })();
    sessions.set(device, s);
  }
  return s;
}

/** Text blocks on the page, in page pixels, best first, overlapping ones (IoU > 0.45) merged away. */
export async function ctdBlocks(page: DecodedPage, minConf = CTD_MIN_CONF): Promise<Array<{ box: Box; score: number }>> {
  const s = await loadCtd();
  const n = CTD_INPUT;
  const r = Math.min(n / page.w, n / page.h);
  const sq = createCanvas(n, n);
  const q = sq.getContext("2d");
  q.fillStyle = "#000";
  q.fillRect(0, 0, n, n);
  q.imageSmoothingQuality = "high";
  q.drawImage(page.canvas, 0, 0, Math.round(page.w * r), Math.round(page.h * r));
  const px = q.getImageData(0, 0, n, n).data;
  const input = new Float32Array(3 * n * n);
  for (let p = 0; p < n * n; p++) {
    input[p] = px[p * 4] / 255;
    input[n * n + p] = px[p * 4 + 1] / 255;
    input[2 * n * n + p] = px[p * 4 + 2] / 255;
  }
  const res = await s.run({ [s.inputNames[0]]: new ort.Tensor("float32", input, [1, 3, n, n]) });
  const blk = res.blk;
  const a = blk.data as Float32Array;
  const rows = blk.dims[1] as number;
  const k = blk.dims[2] as number;
  const cand: Array<{ box: Box; score: number }> = [];
  for (let i = 0; i < rows; i++) {
    const o = i * k;
    let cls = 0;
    for (let c = o + 5; c < o + k; c++) cls = Math.max(cls, a[c]);
    const score = a[o + 4] * cls;
    if (score < minConf) continue;
    const box = { x: (a[o] - a[o + 2] / 2) / r, y: (a[o + 1] - a[o + 3] / 2) / r, w: a[o + 2] / r, h: a[o + 3] / r };
    // Clip to the page (the letterbox pads it with black on the right or bottom).
    const x0 = Math.max(0, box.x), y0 = Math.max(0, box.y);
    const x1 = Math.min(page.w, box.x + box.w), y1 = Math.min(page.h, box.y + box.h);
    if (x1 - x0 < 4 || y1 - y0 < 4) continue;
    cand.push({ box: { x: x0, y: y0, w: x1 - x0, h: y1 - y0 }, score });
  }
  cand.sort((x, y) => y.score - x.score);
  const keep: typeof cand = [];
  for (const c of cand) if (!keep.some((kp) => iou(kp.box, c.box) > 0.45)) keep.push(c);
  return keep;
}

function iou(a: Box, b: Box): number {
  const x0 = Math.max(a.x, b.x), y0 = Math.max(a.y, b.y);
  const x1 = Math.min(a.x + a.w, b.x + b.w), y1 = Math.min(a.y + a.h, b.y + b.h);
  const i = Math.max(0, x1 - x0) * Math.max(0, y1 - y0);
  return i / (a.w * a.h + b.w * b.h - i);
}
