import { createHash } from "node:crypto";
import { readFile } from "node:fs/promises";
import * as ort from "onnxruntime-node";
import { createCanvas } from "@napi-rs/canvas";
import { adoptBalloons, buildRegions, decodeDetections, DETECTOR_INPUT, WEAK_BUBBLE_SCORE, type Box, type Detection, type TextRegion } from "@lt/core";
import { CTD_WANTED, ctdBlocks } from "./ctd";
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

/**
 * Text boxes from the detector run on a zoomed crop. The page pass sees small text at
 * about half size: name tags and whispers are missed or boxed loosely. Zooming the area
 * (up to 4x) gives tight boxes around the text itself, in page coordinates.
 */
export async function detectInCrop(page: DecodedPage, crop: Box, minScore = 0.25): Promise<Array<{ box: Box; score: number }>> {
  const zoom = Math.min(4, DETECTOR_INPUT / Math.max(crop.w, crop.h));
  const zw = Math.max(1, Math.round(crop.w * zoom));
  const zh = Math.max(1, Math.round(crop.h * zoom));
  const canvas = createCanvas(zw, zh);
  const ctx = canvas.getContext("2d");
  ctx.imageSmoothingQuality = "high";
  ctx.drawImage(page.canvas, crop.x, crop.y, crop.w, crop.h, 0, 0, zw, zh);
  const det = await detect({ w: zw, h: zh, canvas, ctx }, minScore, false, false);
  return det.detections
    .filter((d) => d.cls !== "bubble")
    .map((d) => ({ box: { x: crop.x + d.box.x / zoom, y: crop.y + d.box.y / zoom, w: d.box.w / zoom, h: d.box.h / zoom }, score: d.score }));
}

/** Faint text inside a confident bubble still counts (a lone "!" scores ~0.15). */
const IN_BUBBLE_SCORE = 0.1;
/**
 * Bubbles count from this score, and become a region even with no text found inside:
 * small beep or one-word balloons score 0.2-0.5. Swept on the team's 50 GT pages:
 * recall 94.7% -> 96.1% for +2% regions; the reader model marks empty ones "none".
 */
const LONELY_BUBBLE = 0.2;

/**
 * `second`: also run the second detector (whole pages only; zoomed crops do not need it).
 * `balloons`: free text gets the balloon around it when the page pixels show one the detector
 * only half saw (see `findBalloon`).
 */
export async function detect(page: DecodedPage, minScore = 0.3, second = CTD_WANTED, balloons = true): Promise<DetectResult> {
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
  // The second detector runs alongside (see ./ctd); its blocks only add text the first one missed.
  const [out, extra] = await Promise.all([
    s.run(feeds),
    second ? ctdBlocks(page).catch((e: Error) => (warnOnce(`second detector off: ${e.message}`), [])) : Promise.resolve([]),
  ]);
  const [labels, boxes, scores] = s.outputNames.map((name) => out[name]);
  const raw = {
    labels: labels.data as BigInt64Array,
    boxes: boxes.data as Float32Array,
    scores: scores.data as Float32Array,
    count: (scores.dims[1] as number) ?? scores.data.length,
  };
  const all = decodeDetections(raw, page.w, page.h, Math.min(minScore, IN_BUBBLE_SCORE));
  all.push(...missedBy(all, extra, minScore));
  const detections = all.filter((d) => d.score >= minScore);
  let regions = buildRegions(all, { minScore, minScoreInBubble: IN_BUBBLE_SCORE, lonelyBubble: LONELY_BUBBLE, minBubble: LONELY_BUBBLE });
  if (balloons && regions.some((r) => !r.bubble)) {
    const weak = decodeDetections(raw, page.w, page.h, WEAK_BUBBLE_SCORE).filter((d) => d.cls === "bubble");
    regions = adoptBalloons(page.ctx.getImageData(0, 0, page.w, page.h) as never, regions, weak);
  }
  return { detections, regions, ms: performance.now() - t0 };
}

/**
 * The second detector's blocks that no text detection of the first covers (at least half of the
 * smaller box shared), as text detections: "text_bubble" when the block's centre lies in a detected
 * balloon, "text_free" otherwise, kept at least at `minScore` so region building takes them. A
 * block over a weak first detection (below `minScore`, which region building would drop) confirms
 * it instead: that detection is raised to `minScore` and keeps its tighter box.
 */
function missedBy(first: Detection[], blocks: Array<{ box: Box; score: number }>, minScore: number): Detection[] {
  const text = first.filter((d) => d.cls !== "bubble" && d.score >= minScore);
  const weak = first.filter((d) => d.cls !== "bubble" && d.score < minScore);
  const bubbles = first.filter((d) => d.cls === "bubble" && d.score >= LONELY_BUBBLE);
  const shared = (a: Box, b: Box) => {
    const w = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x);
    const h = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y);
    return w > 0 && h > 0 ? (w * h) / Math.min(a.w * a.h, b.w * b.h) : 0;
  };
  const out: Detection[] = [];
  for (const b of blocks) {
    if (text.some((t) => shared(t.box, b.box) >= 0.5) || out.some((o) => shared(o.box, b.box) >= 0.5)) continue;
    const confirmed = weak.filter((w) => shared(w.box, b.box) >= 0.5).sort((x, y) => y.score - x.score)[0];
    if (confirmed) {
      confirmed.score = minScore;
      text.push(confirmed);
      continue;
    }
    const cx = b.box.x + b.box.w / 2, cy = b.box.y + b.box.h / 2;
    const inBubble = bubbles.some((u) => cx >= u.box.x && cy >= u.box.y && cx < u.box.x + u.box.w && cy < u.box.y + u.box.h);
    out.push({ cls: inBubble ? "text_bubble" : "text_free", box: b.box, score: Math.max(minScore, b.score) });
  }
  return out;
}

let warned = false;
function warnOnce(msg: string): void {
  if (warned) return;
  warned = true;
  console.warn(msg);
}

/** Regions saved before balloons were looked for in the pixels (eval runs): look now. */
export async function adoptPageBalloons(page: DecodedPage, regions: TextRegion[]): Promise<TextRegion[]> {
  if (!regions.some((r) => !r.bubble)) return regions;
  const weak = (await detect(page, WEAK_BUBBLE_SCORE, false, false)).detections.filter((d) => d.cls === "bubble");
  return adoptBalloons(page.ctx.getImageData(0, 0, page.w, page.h) as never, regions, weak);
}
