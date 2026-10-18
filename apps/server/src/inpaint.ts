import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { join } from "node:path";
import * as ort from "onnxruntime-node";
import { createCanvas } from "@napi-rs/canvas";
import { area, artTextMask, patchBlends, type PageResult, type TextRegion } from "@lt/core";
import { ROOT } from "./env";
import type { DecodedPage } from "./image";

/** andraniksargsyan/migan @ 406830d0fa60666da0071c342ad2fbc8f30c5c64, MIT (Picsart AI Research). */
export const MIGAN_FILE = join(ROOT, "models", "inpaint", "migan_pipeline_v2.onnx");
export const MIGAN_SHA256 = "6f1f3530a1a2324b19752018ce756088b07973cda8d7d890034ace5c8a48c40b";

let session: Promise<ort.InferenceSession> | undefined;

export function loadInpainter(): Promise<ort.InferenceSession> {
  session ??= (async () => {
    const bytes = await readFile(MIGAN_FILE);
    const sha = createHash("sha256").update(bytes).digest("hex");
    if (sha !== MIGAN_SHA256) throw new Error(`MI-GAN checksum mismatch (${sha})`);
    return ort.InferenceSession.create(bytes, { executionProviders: ["cpu"], intraOpNumThreads: 4 });
  })();
  return session;
}

export interface Patch {
  id: string;
  x: number;
  y: number;
  w: number;
  h: number;
  /** PNG of the reconstructed crop (kept in memory only, never written to disk). */
  dataUrl: string;
  coverage: number;
  ms: number;
}

export interface Rejected {
  id: string;
  reason: "mask-unreliable" | "visible-patch";
  coverage: number;
}

/** Above this share of the text box the mask is no longer "the glyphs" but art too. */
const MAX_COVERAGE = 0.85;

/** Reconstruct the artwork under each region's text with MI-GAN. */
export async function inpaintRegions(
  page: DecodedPage,
  regions: TextRegion[],
  charSizes: Record<string, number> = {},
  rejected: Rejected[] = [],
): Promise<Patch[]> {
  const s = await loadInpainter();
  const full = page.ctx.getImageData(0, 0, page.w, page.h);
  const out: Patch[] = [];
  for (const r of regions) {
    const t0 = performance.now();
    const job = artTextMask(full, r.members, { charSize: charSizes[r.id] });
    if (job.coverage > MAX_COVERAGE || job.coverage === 0) {
      rejected.push({ id: r.id, reason: "mask-unreliable", coverage: job.coverage });
      continue;
    }
    const { x, y, w, h } = job.crop;
    const n = w * h;
    const image = new Uint8Array(3 * n);
    const mask = new Uint8Array(n);
    for (let p = 0; p < n; p++) {
      const px = p % w;
      const py = (p - px) / w;
      const i = ((y + py) * page.w + (x + px)) * 4;
      image[p] = full.data[i];
      image[n + p] = full.data[i + 1];
      image[2 * n + p] = full.data[i + 2];
      mask[p] = job.hole[p] ? 0 : 255;
    }
    const res = await s.run({
      image: new ort.Tensor("uint8", image, [1, 3, h, w]),
      mask: new ort.Tensor("uint8", mask, [1, 1, h, w]),
    });
    const result = res.result.data as Uint8Array;
    if (!patchBlends(full, result, job).ok) {
      rejected.push({ id: r.id, reason: "visible-patch", coverage: job.coverage });
      continue;
    }
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
      patch.data[p * 4 + 3] = 255;
    }
    ctx.putImageData(patch, 0, 0);
    const png = await canvas.encode("png");
    out.push({ id: r.id, x, y, w, h, dataUrl: `data:image/png;base64,${png.toString("base64")}`, coverage: job.coverage, ms: Math.round(performance.now() - t0) });
  }
  return out;
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
