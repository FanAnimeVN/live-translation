import { area, containment, fromXYXY, iou, union, clampBox } from "./geometry";
import { xyCutOrder } from "./order";
import { DET_CLASSES, type Box, type Detection, type TextRegion } from "./types";

/** Detector input side expected by the ogkalu RT-DETR-v2 export. */
export const DETECTOR_INPUT = 640;

export interface RawDetections {
  labels: ArrayLike<number | bigint>;
  /** xyxy boxes in original-image pixels, length = count * 4. */
  boxes: ArrayLike<number>;
  scores: ArrayLike<number>;
  count: number;
}

export function decodeDetections(raw: RawDetections, imgW: number, imgH: number, minScore = 0.3): Detection[] {
  const dets: Detection[] = [];
  for (let i = 0; i < raw.count; i++) {
    const score = Number(raw.scores[i]);
    if (!(score >= minScore)) continue;
    const cls = DET_CLASSES[Number(raw.labels[i])];
    if (!cls) continue;
    const b = clampBox(
      fromXYXY(Number(raw.boxes[i * 4]), Number(raw.boxes[i * 4 + 1]), Number(raw.boxes[i * 4 + 2]), Number(raw.boxes[i * 4 + 3])),
      imgW,
      imgH,
    );
    if (b.w < 4 || b.h < 4) continue;
    dets.push({ cls, box: b, score });
  }
  return dets;
}

/** Class-wise suppression of duplicates (RT-DETR is NMS-free but can repeat boxes). */
export function suppressDuplicates(dets: Detection[], iouThr = 0.5): Detection[] {
  const kept: Detection[] = [];
  for (const d of [...dets].sort((a, b) => b.score - a.score)) {
    const dup = kept.some(
      (k) => sameFamily(k, d) && (iou(k.box, d.box) > iouThr || containment(d.box, k.box) > 0.85),
    );
    if (!dup) kept.push(d);
  }
  return kept;
}

const isText = (d: Detection) => d.cls !== "bubble";
const sameFamily = (a: Detection, b: Detection) => isText(a) === isText(b);

/**
 * Turn raw detections into text regions: merge overlapping text boxes, attach the
 * containing bubble, merge text boxes that share one bubble, and number them in
 * reading order. Raw detections stay available to callers for diagnostics.
 */
export function buildRegions(dets: Detection[]): TextRegion[] {
  const clean = suppressDuplicates(dets);
  const bubbles = clean.filter((d) => d.cls === "bubble");
  type Group = { box: Box; members: Box[]; score: number; inBubbleClass: boolean; bubble?: Box };
  let groups: Group[] = clean
    .filter(isText)
    .map((d) => ({ box: d.box, members: [d.box], score: d.score, inBubbleClass: d.cls === "text_bubble" }));

  // Merge overlapping text boxes (cross-class duplicates, split columns).
  let changed = true;
  while (changed) {
    changed = false;
    outer: for (let i = 0; i < groups.length; i++) {
      for (let j = i + 1; j < groups.length; j++) {
        const a = groups[i];
        const b = groups[j];
        if (iou(a.box, b.box) > 0.3 || containment(a.box, b.box) > 0.6 || containment(b.box, a.box) > 0.6) {
          groups[i] = merge(a, b);
          groups.splice(j, 1);
          changed = true;
          break outer;
        }
      }
    }
  }

  // Attach the bubble that contains most of each text group.
  for (const g of groups) {
    let best: Box | undefined;
    let bestCover = 0;
    for (const b of bubbles) {
      const cover = containment(g.box, b.box);
      if (cover > bestCover) {
        bestCover = cover;
        best = b.box;
      }
    }
    if (best && bestCover >= 0.6) g.bubble = best;
  }

  // One bubble = one region: merge text groups sharing the same bubble.
  const byBubble = new Map<Box, Group>();
  const merged: Group[] = [];
  for (const g of groups) {
    if (!g.bubble) {
      merged.push(g);
      continue;
    }
    const prev = byBubble.get(g.bubble);
    if (prev) {
      const m = merge(prev, g);
      m.bubble = g.bubble;
      merged[merged.indexOf(prev)] = m;
      byBubble.set(g.bubble, m);
    } else {
      byBubble.set(g.bubble, g);
      merged.push(g);
    }
  }
  groups = merged;

  const order = xyCutOrder(groups.map((g) => g.box));
  return order.map((gi, rank) => {
    const g = groups[gi];
    return {
      id: `r${rank + 1}`,
      kind: g.bubble || g.inBubbleClass ? "bubble" : "free",
      box: g.box,
      members: g.members,
      bubble: g.bubble,
      score: Math.round(g.score * 1000) / 1000,
      order: rank,
    } satisfies TextRegion;
  });

  function merge(a: Group, b: Group): Group {
    return {
      box: union(a.box, b.box),
      members: [...a.members, ...b.members],
      score: Math.max(a.score, b.score),
      inBubbleClass: a.inBubbleClass || b.inBubbleClass,
      bubble: a.bubble ?? b.bubble,
    };
  }
}

/** Small or thin regions get a zoomed crop in the model request. */
export function needsCrop(r: TextRegion, minSide = 70, minArea = 9000): boolean {
  return Math.min(r.box.w, r.box.h) < minSide || area(r.box) < minArea;
}
