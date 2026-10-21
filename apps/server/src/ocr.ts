/**
 * Crop OCR for "OCR first" reading: Baberu OCR v1.2 (genshiai-daichi/baberu-ocr @ b9868433, Apache-2.0,
 * trained with Manga109-s: its notice is shown in the app credits, see licenses.ts "ocr/baberu").
 * Smallest published tier: DINOv2-B/14 vision encoder int4 + 6-layer decoder int8 with a KV cache (122 MB).
 * The decode follows the author's onnx_infer.py: greedy, repetition penalty 1.2, a run cap of 12 for one
 * letter/kana/kanji/digit and 16 for one symbol (ー). Measured on the team's 25 pages (label boxes, T4,
 * PyTorch): CER 6.3%, 80% exact lines; on detected regions 12.9% (docs/LOCAL-MODELS.md).
 * Model files are pinned by SHA-256; nothing is downloaded at run time.
 */
import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import { availableParallelism } from "node:os";
import { join } from "node:path";
import { Worker } from "node:worker_threads";
import * as ort from "onnxruntime-node";
import { createCanvas } from "@napi-rs/canvas";
import type { Box, TextRegion } from "@lt/core";
import { INPAINT_DEVICE, sessionOptions } from "./device";
import { ROOT } from "./env";
import type { DecodedPage } from "./image";
import { assertModelAllowed } from "./licenses";

const DIR = join(ROOT, "models", "ocr", "baberu", "b9868433dbda3ed9ba1357d008599ff4ada873d5");
const FILES = {
  vision: { file: join(DIR, "onnx", "vision_int4.onnx"), sha256: "1967ecef502e4c1e1e7c512ea0a2e06396b39ded87a8a9cc77bd7db2e981a361" },
  prefill: { file: join(DIR, "onnx", "decoder_prefill_int8.onnx"), sha256: "187a59cb61d3870f1f97c9eb027eb34ff19d023fba801cda113a13870be0b724" },
  step: { file: join(DIR, "onnx", "decoder_step_int8.onnx"), sha256: "46640b0b3db77f0f0eef660bbe5dc9126a5e0fb49eb2786b2edba7b0371d9769" },
  vocab: { file: join(DIR, "tokenizer", "vocab.json"), sha256: "681de4eb83154a397af49e2ddae4705041b12a22e16fe00860b829e889e5f47c" },
};
const SIZE = 224;
const MEAN = [0.485, 0.456, 0.406];
const STD = [0.229, 0.224, 0.225];
async function pinned(f: { file: string; sha256: string }): Promise<Buffer> {
  const bytes = await readFile(f.file);
  const sha = createHash("sha256").update(bytes).digest("hex");
  if (sha !== f.sha256) throw new Error(`OCR model checksum mismatch for ${f.file} (${sha})`);
  return bytes;
}

/** Decoder workers on their own threads (ocr-worker.mjs), each with 2 CPU threads. */
const WORKERS = Math.max(1, Number(process.env.OCR_WORKERS ?? Math.min(4, Math.max(1, Math.floor(availableParallelism() / 2)))));

interface Pool {
  workers: Worker[];
  pending: Map<number, { resolve: (toks: number[]) => void; reject: (e: Error) => void }>;
  next: number;
  busy: number;
}

interface Baberu {
  vision: ort.InferenceSession;
  pool: Pool;
  id2ch: string[];
}

let loaded: Promise<Baberu> | undefined;

export function loadOcr(): Promise<Baberu> {
  loaded ??= (async () => {
    assertModelAllowed("ocr/baberu");
    // Measured 22/10 (one crop, RTX 4060 Laptop / 8-core CPU): the vision encoder takes 188 ms on the CPU and
    // 23 ms on DirectML, but a decoder step takes 8.8 ms on the CPU and 58 ms on DirectML (per-call cost).
    // So the encoder runs on the GPU when one is set (INPAINT_DEVICE / OCR_DEVICE) and decoding on CPU worker
    // threads: onnxruntime-node runs each call synchronously on its thread, so parallel decoding needs them.
    const device = (process.env.OCR_DEVICE as typeof INPAINT_DEVICE | undefined) ?? INPAINT_DEVICE;
    const cpu: ort.InferenceSession.SessionOptions = { executionProviders: ["cpu"], intraOpNumThreads: 4, graphOptimizationLevel: "all" };
    const [visionBytes, prefillBytes, stepBytes, vocab] = await Promise.all([pinned(FILES.vision), pinned(FILES.prefill), pinned(FILES.step), pinned(FILES.vocab)]);
    const vision = await ort.InferenceSession.create(visionBytes, device === "cpu" ? cpu : sessionOptions(device));
    const charset = JSON.parse(vocab.toString("utf8")) as string[];
    const id2ch = ["", "", "", "", ...charset];
    const content: number[] = [];
    charset.forEach((ch, i) => {
      if ([...ch].length === 1 && !"ーｰ〜~".includes(ch) && /^[\p{L}\p{N}]$/u.test(ch)) content.push(i + 4);
    });
    const pool: Pool = { workers: [], pending: new Map(), next: 0, busy: 0 };
    pool.workers = await Promise.all(
      Array.from(
        { length: WORKERS },
        () =>
          new Promise<Worker>((resolve, reject) => {
            const w = new Worker(new URL("./ocr-worker.mjs", import.meta.url), { workerData: { prefill: prefillBytes, step: stepBytes, content, threads: 2 } });
            w.on("message", (msg: { ready?: boolean; id?: number; toks?: number[]; error?: string }) => {
              if (msg.ready) return resolve(w);
              const p = pool.pending.get(msg.id!);
              if (!p) return;
              pool.pending.delete(msg.id!);
              if (--pool.busy === 0) pool.workers.forEach((x) => x.unref());
              if (msg.error) p.reject(new Error(msg.error));
              else p.resolve(msg.toks!);
            });
            w.once("error", reject);
          }),
      ),
    );
    pool.workers.forEach((w) => w.unref()); // idle workers never keep a script alive
    return { vision, pool, id2ch };
  })();
  return loaded;
}

/** The crop as the model expects it: the box plus a small margin, squeezed to 224x224, ImageNet-normalised CHW. */
function pixels(page: DecodedPage, b: Box, margin = 4): Float32Array {
  const x = Math.max(0, Math.floor(b.x - margin)), y = Math.max(0, Math.floor(b.y - margin));
  const w = Math.max(1, Math.min(page.w - x, Math.ceil(b.w + 2 * margin))), h = Math.max(1, Math.min(page.h - y, Math.ceil(b.h + 2 * margin)));
  const canvas = createCanvas(SIZE, SIZE);
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(page.canvas, x, y, w, h, 0, 0, SIZE, SIZE);
  const rgba = ctx.getImageData(0, 0, SIZE, SIZE).data;
  const out = new Float32Array(3 * SIZE * SIZE);
  for (let i = 0; i < SIZE * SIZE; i++) for (let c = 0; c < 3; c++) out[c * SIZE * SIZE + i] = (rgba[4 * i + c] / 255 - MEAN[c]) / STD[c];
  return out;
}

async function encode(m: Baberu, page: DecodedPage, box: Box): Promise<ort.Tensor> {
  return (await m.vision.run({ pixel_values: new ort.Tensor("float32", pixels(page, box), [1, 3, SIZE, SIZE]) })).vision_embeds;
}

let ids = 0;
/** Hand the vision embeddings to the next worker; resolves with the decoded text. */
function decode(m: Baberu, vis: ort.Tensor): Promise<string> {
  const { pool } = m;
  const w = pool.workers[pool.next++ % pool.workers.length];
  const id = ids++;
  if (pool.busy++ === 0) pool.workers.forEach((x) => x.ref());
  const data = (vis.data as Float32Array).slice();
  return new Promise<number[]>((resolve, reject) => {
    pool.pending.set(id, { resolve, reject });
    w.postMessage({ id, embeds: data, dims: vis.dims }, [data.buffer]);
  }).then((toks) => toks.map((t) => m.id2ch[t] ?? "").join("").normalize("NFKC"));
}

/** Read the Japanese text in one box of the page. */
export async function readBox(page: DecodedPage, box: Box): Promise<string> {
  const m = await loadOcr();
  return decode(m, await encode(m, page, box));
}

/**
 * Read every region of a page, returning region id -> Japanese text: the encoder runs crop after crop on
 * this thread while the workers decode the previous crops.
 */
export async function readRegions(page: DecodedPage, regions: TextRegion[]): Promise<Record<string, string>> {
  const m = await loadOcr();
  const jobs: Array<Promise<[string, string]>> = [];
  for (const r of [...regions].sort((a, b) => a.order - b.order)) {
    const vis = await encode(m, page, r.box);
    jobs.push(decode(m, vis).then((t) => [r.id, t]));
  }
  return Object.fromEntries(await Promise.all(jobs));
}
