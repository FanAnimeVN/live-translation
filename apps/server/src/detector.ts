import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import * as ort from "onnxruntime-node";
import { createCanvas } from "@napi-rs/canvas";
import { buildRegions, decodeDetections, DETECTOR_INPUT, type Detection, type TextRegion } from "@lt/core";
import { env } from "./env";
import type { DecodedPage } from "./image";

/** ogkalu/comic-text-and-bubble-detector, revision 16e8a622f91fabc6b5b65c96d32d1183f8843546, Apache-2.0. */
export const DETECTOR_SHA256 = "5fe9e4f576e49d4e7e8b0e029d6d3cdc252abd4694113e1cae120e62c931ea79";

let session: Promise<ort.InferenceSession> | undefined;

export function loadDetector(): Promise<ort.InferenceSession> {
  session ??= (async () => {
    const bytes = await readFile(env.detectorModel);
    const sha = createHash("sha256").update(bytes).digest("hex");
    if (sha !== DETECTOR_SHA256) throw new Error(`Detector checksum mismatch (${sha}); refusing to load ${env.detectorModel}`);
    return ort.InferenceSession.create(bytes, { executionProviders: ["cpu"], intraOpNumThreads: 4 });
  })();
  return session;
}

export interface DetectResult {
  detections: Detection[];
  regions: TextRegion[];
  ms: number;
}

export async function detect(page: DecodedPage, minScore = 0.3): Promise<DetectResult> {
  const t0 = performance.now();
  const s = await loadDetector();
  const n = DETECTOR_INPUT;
  const canvas = createCanvas(n, n);
  const ctx = canvas.getContext("2d");
  ctx.drawImage(page.canvas, 0, 0, n, n);
  const rgba = ctx.getImageData(0, 0, n, n).data;
  const chw = new Float32Array(3 * n * n);
  for (let i = 0, p = 0; p < n * n; p++, i += 4) {
    chw[p] = rgba[i] / 255;
    chw[n * n + p] = rgba[i + 1] / 255;
    chw[2 * n * n + p] = rgba[i + 2] / 255;
  }
  const feeds: Record<string, ort.Tensor> = {
    [s.inputNames[0]]: new ort.Tensor("float32", chw, [1, 3, n, n]),
  };
  if (s.inputNames[1]) {
    feeds[s.inputNames[1]] = new ort.Tensor("int64", BigInt64Array.from([BigInt(page.w), BigInt(page.h)]), [1, 2]);
  }
  const out = await s.run(feeds);
  const [labels, boxes, scores] = s.outputNames.map((name) => out[name]);
  const detections = decodeDetections(
    {
      labels: labels.data as BigInt64Array,
      boxes: boxes.data as Float32Array,
      scores: scores.data as Float32Array,
      count: (scores.dims[1] as number) ?? scores.data.length,
    },
    page.w,
    page.h,
    minScore,
  );
  return { detections, regions: buildRegions(detections), ms: performance.now() - t0 };
}
