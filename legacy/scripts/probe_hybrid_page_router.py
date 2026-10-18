"""Offline page-router probe for a fast detector plus a CTD candidate.

The router is an experiment, not a runtime default.  It uses only observable
baseline page signals (review count) to decide whether a candidate page would
be selected; it never reads gold labels to make the decision.  Reports remain
private and images/models are not loaded here.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import statistics

from benchmark import ROOT, distance
from compare_page_reports import checked_pages, private_json_path


def route(baseline, candidate, *, min_review_count):
    fingerprint = baseline.get("input_fingerprint_sha256")
    if not fingerprint or fingerprint != candidate.get("input_fingerprint_sha256"):
        raise ValueError("Dataset fingerprints differ")
    before, after = checked_pages(baseline), checked_pages(candidate)
    if set(before) != set(after):
        raise ValueError("Page coverage differs")

    pages = []
    rows = []
    for page_id, (base_page, base_labels) in before.items():
        cand_page, cand_labels = after[page_id]
        if set(base_labels) != set(cand_labels):
            raise ValueError("Annotation coverage differs")
        review_count = base_page.get("review_count")
        if type(review_count) is not int or review_count < 0:
            raise ValueError("Baseline review_count is required")
        use_candidate = review_count >= min_review_count
        selected_page = cand_page if use_candidate else base_page
        selected_labels = cand_labels if use_candidate else base_labels
        page_rows = []
        for label, selected in selected_labels.items():
            reference = base_labels[label]["reference"]
            if reference != selected["reference"] or selected["edits"] != distance(reference, selected["prediction"]):
                raise ValueError("Reference or stored edit count changed")
            row = {
                "page": page_id,
                "id": label,
                "reference": reference,
                "prediction": selected["prediction"],
                "edits": selected["edits"],
                "characters": selected["characters"],
                "assigned": bool(selected["region_ids"]),
            }
            rows.append(row)
            page_rows.append(row)
        pages.append({
            "page": page_id,
            "source": "candidate" if use_candidate else "baseline",
            "baseline_review_count": review_count,
            "baseline_regions": len(base_page.get("regions", [])),
            "selected_regions": len(selected_page.get("regions", [])),
            "selected_detector_ms": selected_page.get("detector_ms"),
            "selected_ocr_ms": selected_page.get("ocr_ms"),
            "selected_total_ms": (selected_page.get("detector_ms", 0) or 0) + (selected_page.get("ocr_ms", 0) or 0),
            "rows": len(page_rows),
        })
    characters = sum(row["characters"] for row in rows)
    selected_edits = sum(row["edits"] for row in rows)
    result = {
        "schema": 1,
        "input_fingerprint_sha256": fingerprint,
        "automatic_promotion": False,
        "production_default": False,
        "router": {"signal": "baseline.review_count", "min_review_count": min_review_count},
        "pages": pages,
        "rows": rows,
        "aggregate": {
            "annotations": len(rows),
            "characters": characters,
            "selected_edits": selected_edits,
            "selected_cer": selected_edits / max(1, characters),
            "selected_exact": sum(row["edits"] == 0 for row in rows),
            "selected_assigned": sum(row["assigned"] for row in rows),
            "selected_total_ms_p50": statistics.median(page["selected_total_ms"] for page in pages),
            "selected_total_ms_p95": sorted(page["selected_total_ms"] for page in pages)[min(len(pages) - 1, int(len(pages) * .95))],
        },
        "limitations": [
            "The review-count router is a private hypothesis, not a calibrated confidence model.",
            "Gold labels are supplied transcriptions and have not been independently reviewed.",
            "Eight pages are development evidence, not a latency p95 population or held-out quality result.",
            "A candidate page is selected as a whole; no source region is silently mixed across reports.",
        ],
    }
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--min-review-count", required=True, type=int, choices=range(0, 65))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = private_json_path(args.output, new=True)
    baseline = json.loads(private_json_path(args.baseline).read_text(encoding="utf-8"))
    candidate = json.loads(private_json_path(args.candidate).read_text(encoding="utf-8"))
    result = route(baseline, candidate, min_review_count=args.min_review_count)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
