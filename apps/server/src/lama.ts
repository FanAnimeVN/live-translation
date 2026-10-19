/**
 * LaMa (big-lama, Apache-2.0) as an alternative inpainter to MI-GAN. The ONNX exports take
 * a fixed 512x512 image: the square context around the text is resized to 512, reconstructed,
 * and resized back; only hole pixels are used afterwards. Model files are pinned by SHA-256.
 */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import * as ort from "onnxruntime-node";
import { createCanvas } from "@napi-rs/canvas";
import type { InpaintJob, RGBAImage } from "@lt/core";
import { ROOT } from "./env";
import { INPAINT_DEVICE, sessionOptions, type InpaintDevice } from "./device";

export const LAMA_MODELS = {
  /** Carve/LaMa-ONNX @ c3c0c9e468934d62e79c329e35d82dd09ff8c444 (lama_fp32.onnx), Apache-2.0. */
  lama: { file: join(ROOT, "models", "inpaint", "lama_fp32.onnx"), sha256: "1faef5301d78db7dda502fe59966957ec4b79dd64e16f03ed96913c7a4eb68d6" },
  /** opencv/inpainting_lama @ aee6d22f0a13e5e35af1c9a1c3afd62841fc6f3f (inpainting_lama_2025jan.onnx), Apache-2.0. */
  "lama-cv": { file: join(ROOT, "models", "inpaint", "inpainting_lama_2025jan.onnx"), sha256: "7df918ac3921d3daf0aae1d219776cf0dc4e4935f035af81841b40adcf74fdf2" },
} as const;
export type LamaVariant = keyof typeof LAMA_MODELS;

const sessions = new Map<string, Promise<ort.InferenceSession>>();

export function loadLama(v: LamaVariant = "lama", device: InpaintDevice = INPAINT_DEVICE): Promise<ort.InferenceSession> {
  let s = sessions.get(`${v}|${device}`);
  if (!s) {
    s = (async () => {
      const bytes = await readFile(LAMA_MODELS[v].file);
      const sha = createHash("sha256").update(bytes).digest("hex");
      if (sha !== LAMA_MODELS[v].sha256) throw new Error(`LaMa (${v}) checksum mismatch (${sha})`);
      return ort.InferenceSession.create(bytes, sessionOptions(device));
    })();
    sessions.set(`${v}|${device}`, s);
  }
  return s;
}

const N = 512;
const clamp = (v: number, lo: number, hi: number) => Math.max(lo, Math.min(hi, v));

/** Reconstruct the job's hole with LaMa; returns planar RGB for `job.crop`, like the MI-GAN runner. */
export async function runLama(s: ort.InferenceSession, full: RGBAImage, job: InpaintJob): Promise<Uint8Array> {
  const { x, y, w, h } = job.crop;
  // Square context around the crop, so the 512x512 resize keeps the aspect ratio.
  const side = Math.min(Math.max(w, h), full.width, full.height);
  const sx = clamp(Math.round(x + w / 2 - side / 2), 0, full.width - side);
  const sy = clamp(Math.round(y + h / 2 - side / 2), 0, full.height - side);
  const src = createCanvas(side, side);
  const sctx = src.getContext("2d");
  const id = sctx.createImageData(side, side);
  for (let yy = 0; yy < side; yy++)
    for (let xx = 0; xx < side; xx++) {
      const i = ((sy + yy) * full.width + (sx + xx)) * 4;
      const o = (yy * side + xx) * 4;
      id.data[o] = full.data[i];
      id.data[o + 1] = full.data[i + 1];
      id.data[o + 2] = full.data[i + 2];
      id.data[o + 3] = 255;
    }
  sctx.putImageData(id, 0, 0);
  const hole = new Uint8Array(side * side);
  for (let yy = 0; yy < h; yy++)
    for (let xx = 0; xx < w; xx++) {
      if (!job.hole[yy * w + xx]) continue;
      const qx = x + xx - sx;
      const qy = y + yy - sy;
      if (qx >= 0 && qy >= 0 && qx < side && qy < side) hole[qy * side + qx] = 1;
    }
  const big = createCanvas(N, N);
  const bctx = big.getContext("2d");
  bctx.imageSmoothingQuality = "high";
  bctx.drawImage(src, 0, 0, N, N);
  const px = bctx.getImageData(0, 0, N, N).data;
  const mask = new Float32Array(N * N);
  const grow = Math.max(1, Math.ceil(N / side));
  for (let yy = 0; yy < N; yy++)
    for (let xx = 0; xx < N; xx++) {
      if (!hole[Math.min(side - 1, Math.floor((yy * side) / N)) * side + Math.min(side - 1, Math.floor((xx * side) / N))]) continue;
      for (let dy = -grow; dy <= grow; dy++)
        for (let dx = -grow; dx <= grow; dx++) {
          const yq = yy + dy;
          const xq = xx + dx;
          if (yq >= 0 && xq >= 0 && yq < N && xq < N) mask[yq * N + xq] = 1;
        }
    }
  const image = new Float32Array(3 * N * N);
  for (let p = 0; p < N * N; p++) {
    const keep = mask[p] ? 0 : 1;
    image[p] = (px[p * 4] / 255) * keep;
    image[N * N + p] = (px[p * 4 + 1] / 255) * keep;
    image[2 * N * N + p] = (px[p * 4 + 2] / 255) * keep;
  }
  const res = await s.run({ image: new ort.Tensor("float32", image, [1, 3, N, N]), mask: new ort.Tensor("float32", mask, [1, 1, N, N]) });
  const out = res[s.outputNames[0]].data as Float32Array;
  const oc = createCanvas(N, N);
  const octx = oc.getContext("2d");
  const od = octx.createImageData(N, N);
  for (let p = 0; p < N * N; p++) {
    od.data[p * 4] = clamp(Math.round(out[p]), 0, 255);
    od.data[p * 4 + 1] = clamp(Math.round(out[N * N + p]), 0, 255);
    od.data[p * 4 + 2] = clamp(Math.round(out[2 * N * N + p]), 0, 255);
    od.data[p * 4 + 3] = 255;
  }
  octx.putImageData(od, 0, 0);
  const back = createCanvas(side, side);
  const bk = back.getContext("2d");
  bk.imageSmoothingQuality = "high";
  bk.drawImage(oc, 0, 0, side, side);
  const bp = bk.getImageData(0, 0, side, side).data;
  const n = w * h;
  const result = new Uint8Array(3 * n);
  for (let yy = 0; yy < h; yy++)
    for (let xx = 0; xx < w; xx++) {
      const p = yy * w + xx;
      const qx = x + xx - sx;
      const qy = y + yy - sy;
      const inside = qx >= 0 && qy >= 0 && qx < side && qy < side;
      const i = inside ? (qy * side + qx) * 4 : ((y + yy) * full.width + (x + xx)) * 4;
      const from = inside ? bp : full.data;
      result[p] = from[i];
      result[n + p] = from[i + 1];
      result[2 * n + p] = from[i + 2];
    }
  return result;
}
