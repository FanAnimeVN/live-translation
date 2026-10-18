"""Cheap pre-OCR page difficulty features.

This module deliberately uses only detector geometry and scores.  It must run
before recognizer inference, never reads OCR text, gold labels, context or
reader memory, and never authorizes skipping text or erasing artwork.  The
result is a routing hint for a bounded comparator (for example a slower CTD
path), not a confidence claim.
"""
from __future__ import annotations

import math


PAGE_HARDNESS_VERSION = "pre-ocr-hardness-v1"


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
        raise ValueError(f"{name} must be finite")
    return float(value)


def _box(region, width, height):
    box = region.get("bbox") if isinstance(region, dict) else None
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        raise ValueError("region bbox is required")
    x, y, w, h = (_number(value, "bbox") for value in box)
    if min(x, y, w, h) < 0 or w <= 0 or h <= 0 or x + w > width or y + h > height:
        raise ValueError("region bbox is outside page")
    return x, y, w, h


def _intersection(a, b):
    return max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])) * max(
        0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    )


def _iou(a, b):
    shared = _intersection(a, b)
    return shared / max(1.0, a[2] * a[3] + b[2] * b[3] - shared)


def _aligned_neighbour(a, b):
    """Return whether two boxes look like adjacent line fragments."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    vertical = ah >= aw * 1.25 and bh >= bw * 1.25
    horizontal = aw >= ah * 1.25 and bw >= bh * 1.25
    if vertical:
        scale = min(aw, bw)
        longitudinal = max(0.0, min(ay + ah, by + bh) - max(ay, by))
        gap = max(0.0, max(ax, bx) - min(ax + aw, bx + bw))
        return longitudinal >= min(ah, bh) * 0.55 and gap <= scale * 1.1
    if horizontal:
        scale = min(ah, bh)
        longitudinal = max(0.0, min(ax + aw, bx + bw) - max(ax, bx))
        gap = max(0.0, max(ay, by) - min(ay + ah, by + bh))
        return longitudinal >= min(aw, bw) * 0.55 and gap <= scale * 1.1
    return False


def score_page_hardness(regions, width, height):
    """Return a bounded, explainable page-routing hint before OCR.

    The score is intentionally not calibrated as a probability.  All fields
    are geometry-only and are safe to persist in private diagnostics.  A
    caller may use it to *select an OCR candidate*, but must not use it to
    suppress a region, infer semantic importance, or grant erasure authority.
    """
    if not isinstance(regions, list) or len(regions) > 64:
        raise ValueError("regions must be a list of at most 64 items")
    width = _number(width, "width")
    height = _number(height, "height")
    if width <= 0 or height <= 0 or width * height > 12_000_000:
        raise ValueError("invalid page size")
    boxes = [_box(region, width, height) for region in regions]
    page_area = width * height
    count = len(boxes)
    if not boxes:
        return {
            "version": PAGE_HARDNESS_VERSION,
            "score": 0.0,
            "features": {"region_count": 0, "overlap_pairs": 0, "aligned_pairs": 0},
            "reasons": [],
        }

    scores = [_number(region.get("score", 1.0), "score") for region in regions]
    if any(score < 0.0 or score > 1.0 for score in scores):
        raise ValueError("detector score outside [0, 1]")
    areas = [box[2] * box[3] for box in boxes]
    small = sum(area / page_area <= 0.00075 for area in areas) / count
    low_score = sum(max(0.0, min(1.0, (0.70 - score) / 0.35)) for score in scores) / count
    density = min(1.0, sum(areas) / page_area / 0.18)
    count_pressure = min(1.0, count / 24.0)
    edge = sum(
        box[0] <= 2 or box[1] <= 2 or box[0] + box[2] >= width - 2 or box[1] + box[3] >= height - 2
        for box in boxes
    ) / count

    overlap_pairs = 0
    aligned_pairs = 0
    for index, first in enumerate(boxes):
        for second in boxes[index + 1:]:
            if _iou(first, second) >= 0.05:
                overlap_pairs += 1
            if _aligned_neighbour(first, second):
                aligned_pairs += 1
    overlap_pressure = min(1.0, overlap_pairs / max(1.0, count * 0.6))
    neighbour_pressure = min(1.0, aligned_pairs / max(1.0, count * 0.8))

    extra_members = 0
    for region in regions:
        members = region.get("sourceMembers")
        if isinstance(members, list) and len(members) > 1:
            extra_members += len(members) - 1
    fragment_pressure = min(1.0, extra_members / max(1.0, count * 1.5))

    orientations = {
        "vertical": sum(box[3] >= box[2] * 1.25 for box in boxes),
        "horizontal": sum(box[2] >= box[3] * 1.25 for box in boxes),
    }
    mixed_orientation = 1.0 if orientations["vertical"] and orientations["horizontal"] else 0.0
    score = 100.0 * (
        0.16 * count_pressure
        + 0.12 * density
        + 0.14 * small
        + 0.16 * low_score
        + 0.16 * overlap_pressure
        + 0.12 * neighbour_pressure
        + 0.08 * fragment_pressure
        + 0.03 * edge
        + 0.03 * mixed_orientation
    )
    reasons = []
    if count_pressure >= 0.65:
        reasons.append("many_regions")
    if small >= 0.35:
        reasons.append("small_regions")
    if low_score >= 0.25:
        reasons.append("low_detector_scores")
    if overlap_pairs:
        reasons.append("overlap_or_fragmentation")
    if aligned_pairs >= max(2, count * 0.35):
        reasons.append("aligned_line_candidates")
    if fragment_pressure:
        reasons.append("grouped_source_members")
    if mixed_orientation:
        reasons.append("mixed_orientation")
    return {
        "version": PAGE_HARDNESS_VERSION,
        "score": round(max(0.0, min(100.0, score)), 3),
        "features": {
            "region_count": count,
            "overlap_pairs": overlap_pairs,
            "aligned_pairs": aligned_pairs,
            "small_fraction": round(small, 6),
            "low_score_pressure": round(low_score, 6),
            "area_density": round(density, 6),
            "edge_fraction": round(edge, 6),
            "fragment_pressure": round(fragment_pressure, 6),
            "vertical_regions": orientations["vertical"],
            "horizontal_regions": orientations["horizontal"],
        },
        "reasons": reasons,
    }

