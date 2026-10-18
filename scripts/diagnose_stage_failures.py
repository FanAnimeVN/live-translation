"""Classify private page OCR failures by pipeline stage.

This is a diagnostic only.  It never treats the supplied transcription as
independently verified gold and never promotes a detector region, OCR result,
or unlabeled source area into story memory.  Images stay in the selected
dataset reader; this report stores geometry and stage labels only.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from benchmark import audit, dataset_fingerprint, dataset_source, distance, normalized, ROOT


def intersection(a, b):
    return max(0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])) * max(
        0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1])
    )


def iou(a, b):
    shared = intersection(a, b)
    return shared / max(1, a[2] * a[3] + b[2] * b[3] - shared)


def prediction_matches(gold_box, region):
    """Use the same conservative prediction-containment rule as benchmark_pages."""
    box = region.get("bbox")
    if not isinstance(box, list) or len(box) != 4:
        return False
    return intersection(box, gold_box) / max(1, box[2] * box[3]) >= 0.5


def classify_page(gold_page, report_page):
    regions = list(report_page.get("regions", []))
    rows = []
    assigned = set()
    for bubble in gold_page.get("bubbles", []):
        gold_box = [bubble["bbox"][key] for key in ("x", "y", "w", "h")]
        matches = [region for region in regions if prediction_matches(gold_box, region)]
        for region in matches:
            assigned.add(region.get("id"))

        # A region can contain the edge of two source labels.  This is a
        # stronger grouping signal than merely having multiple fragments in
        # one bubble.
        cross_label = []
        for other in gold_page.get("bubbles", []):
            other_box = [other["bbox"][key] for key in ("x", "y", "w", "h")]
            if any(prediction_matches(other_box, region) for region in matches):
                cross_label.append(other["bubble_id"])
        cross_label = sorted(set(cross_label))

        matches.sort(key=lambda region: (region.get("order", 0), region.get("id", "")))
        prediction = normalized("".join(region.get("ja", "") for region in matches))
        reference = normalized(bubble.get("ja_ocr_truth", ""))
        if not matches:
            # Partial overlap is useful for diagnosing boxes that were found
            # but failed the strict assignment threshold.
            partial = max(
                (intersection(gold_box, region.get("bbox", [0, 0, 0, 0])) /
                 max(1, gold_box[2] * gold_box[3]) for region in regions),
                default=0,
            )
            stage = "detector_miss" if partial == 0 else "detector_partial"
        elif len(cross_label) > 1:
            stage = "grouping_cross_label"
        elif not prediction:
            stage = "ocr_empty"
        elif prediction == reference:
            # Multiple source regions are normal for a vertical multi-column
            # bubble when their ordered concatenation is exact.  Keep this
            # visible as an assembled success instead of mislabelling it as a
            # grouping failure.
            stage = "exact_assembled" if len(matches) > 1 else "exact"
        elif len(matches) > 1:
            stage = "grouping_fragmented"
        else:
            stage = "ocr_mismatch"
        rows.append({
            "page": gold_page["page_id"],
            "id": bubble["bubble_id"],
            "stage": stage,
            "region_ids": [region.get("id") for region in matches],
            "prediction": prediction,
            "reference": reference,
            "edits": distance(reference, prediction),
            "characters": len(reference),
            "cross_label_ids": cross_label,
            "best_iou": max((iou(gold_box, region.get("bbox", [0, 0, 0, 0])) for region in matches), default=0),
        })
    unmatched = [
        {"page": gold_page["page_id"], "region_id": region.get("id"),
         "bbox": region.get("bbox"), "ja": normalized(region.get("ja", ""))}
        for region in regions if region.get("id") not in assigned
    ]
    return rows, unmatched


def run(args):
    report = json.loads(Path(args.report).read_text(encoding="utf-8"))
    with dataset_source(args) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    if report.get("input_fingerprint_sha256") != fingerprint:
        raise ValueError("Report and dataset fingerprints differ")
    report_pages = {page.get("page"): page for page in report.get("pages", [])}
    rows, unmatched = [], []
    for page, _image, _bubbles in pages:
        candidate = report_pages.get(page["page_id"])
        if candidate is None:
            raise ValueError(f"Report is missing page {page['page_id']}")
        page_rows, page_unmatched = classify_page(page, candidate)
        rows.extend(page_rows)
        unmatched.extend(page_unmatched)
    counts_by_stage = {}
    for row in rows:
        counts_by_stage[row["stage"]] = counts_by_stage.get(row["stage"], 0) + 1
    success_stages = {"exact", "exact_assembled"}
    failed = [row for row in rows if row["stage"] not in success_stages]
    result = {
        "schema": 1,
        "input_fingerprint_sha256": fingerprint,
        "report": str(Path(args.report).resolve()),
        "report_production_default": report.get("production_default"),
        "dataset_counts": counts,
        "dataset_audit": issues,
        "gold_not_independently_verified": True,
        "stage_counts": counts_by_stage,
        "unmatched_report_regions": unmatched,
        "rows": rows,
        "summary": {
            "gold_rows": len(rows),
            "failed_rows": len(failed),
            "exact_rows": counts_by_stage.get("exact", 0) + counts_by_stage.get("exact_assembled", 0),
            "assigned_rows": sum(bool(row["region_ids"]) for row in rows),
            "unmatched_region_count": len(unmatched),
            "edit_count": sum(row["edits"] for row in rows),
            "character_count": sum(row["characters"] for row in rows),
            "diagnostic_cer": sum(row["edits"] for row in rows) / max(1, sum(row["characters"] for row in rows)),
        },
        "limitations": [
            "Ground-truth text and boxes are supplied labels, not independent human review.",
            "Unmatched regions may be legitimate unlabelled scene text, SFX or artwork; this is not a false-positive rate.",
            "Stage labels identify the first observable failure in this report, not a causal proof for every model error.",
        ],
    }
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"stage_counts": counts_by_stage, "summary": result["summary"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--folder")
    inputs.add_argument("--zip")
    parser.add_argument("--report", required=True)
    parser.add_argument("--output", default=str(ROOT / "artifacts/stage-diagnostics.json"))
    run(parser.parse_args())
