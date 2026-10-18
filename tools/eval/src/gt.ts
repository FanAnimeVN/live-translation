import { center, containment, containsPoint, iou, type Box, type TextRegion } from "@lt/core";
import type { GtBubble } from "@lt/server";

/** GT boxes with zero size or outside the page are excluded (audit found one size mismatch page). */
export function validGt(gt: GtBubble[], size: { w: number; h: number }): GtBubble[] {
  return gt.filter((g) => g.bbox.w > 0 && g.bbox.h > 0 && g.bbox.x + g.bbox.w <= size.w + 2 && g.bbox.y + g.bbox.h <= size.h + 2);
}

/**
 * A GT text box is "found" when a predicted region overlaps it substantially:
 * IoU >= 0.3, or the GT center lies inside the region and half of GT is covered.
 */
export function matchRegions(g: Box, regions: TextRegion[]): TextRegion[] {
  return regions.filter(
    (r) => iou(g, r.box) >= 0.3 || (containsPoint(r.box, center(g)) && containment(g, r.box) >= 0.5) || containment(r.box, g) >= 0.6,
  );
}
