"""Offline probe for selecting a slower OCR candidate before recognition.

The selector consumes only baseline detector geometry captured before OCR.  It
is a quality/architecture experiment: it never reads gold to choose a page,
never drops a region, and never becomes a production default automatically.
"""
from __future__ import annotations

import argparse
import json
import statistics

from compare_page_reports import checked_pages, private_json_path
from benchmark import distance


def route(baseline, candidate, *, min_hardness):
    fingerprint = baseline.get("input_fingerprint_sha256")
    if not fingerprint or fingerprint != candidate.get("input_fingerprint_sha256"):
        raise ValueError("Dataset fingerprints differ")
    before, after = checked_pages(baseline), checked_pages(candidate)
    if set(before) != set(after):
        raise ValueError("Page coverage differs")
    pages, rows = [], []
    for page_id, (base_page, base_labels) in before.items():
        cand_page, cand_labels = after[page_id]
        if set(base_labels) != set(cand_labels):
            raise ValueError("Annotation coverage differs")
        signal = base_page.get("pre_ocr_hardness")
        if not isinstance(signal, dict) or not isinstance(signal.get("score"), (int, float)):
            raise ValueError("Baseline pre_ocr_hardness is required")
        use_candidate = float(signal["score"]) >= min_hardness
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
            "baseline_hardness": signal,
            "baseline_regions": len(base_page.get("regions", [])),
            "selected_regions": len(selected_page.get("regions", [])),
            "selected_detector_ms": selected_page.get("detector_ms"),
            "selected_ocr_ms": selected_page.get("ocr_ms"),
            "selected_total_ms": (selected_page.get("detector_ms", 0) or 0) + (selected_page.get("ocr_ms", 0) or 0),
            "rows": len(page_rows),
        })
    characters = sum(row["characters"] for row in rows)
    selected_edits = sum(row["edits"] for row in rows)
    totals = [page["selected_total_ms"] for page in pages]
    return {
        "schema": 1,
        "input_fingerprint_sha256": fingerprint,
        "automatic_promotion": False,
        "production_default": False,
        "router": {"signal": "baseline.pre_ocr_hardness.score", "min_hardness": min_hardness},
        "pages": pages,
        "rows": rows,
        "aggregate": {
            "annotations": len(rows),
            "characters": characters,
            "selected_edits": selected_edits,
            "selected_cer": selected_edits / max(1, characters),
            "selected_exact": sum(row["edits"] == 0 for row in rows),
            "selected_assigned": sum(row["assigned"] for row in rows),
            "selected_total_ms_p50": statistics.median(totals) if totals else 0,
            "selected_total_ms_p95": sorted(totals)[min(len(totals) - 1, int(len(totals) * .95))] if totals else 0,
        },
        "limitations": [
            "The score is uncalibrated geometry evidence, not a probability or semantic classifier.",
            "The candidate is selected before OCR from baseline detector output only.",
            "Gold labels are supplied transcriptions and have not been independently reviewed.",
            "A candidate page is selected as a whole; no source region is silently mixed across reports.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--min-hardness", required=True, type=float)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if not 0 <= args.min_hardness <= 100:
        parser.error("--min-hardness must be between 0 and 100")
    output = private_json_path(args.output, new=True)
    baseline = json.loads(private_json_path(args.baseline).read_text(encoding="utf-8"))
    candidate = json.loads(private_json_path(args.candidate).read_text(encoding="utf-8"))
    result = route(baseline, candidate, min_hardness=args.min_hardness)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

