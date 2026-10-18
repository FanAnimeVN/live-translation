"""Source-preserving fallback for labels missing from the primary OCR pass.

This diagnostic fuses recorded reports without running inference.  It may use
the secondary result only when the primary assignment is empty and the
secondary assignment is exactly one region.  Existing primary text is never
replaced, and a secondary proposal is not granted balloon, memory or erasure
authority.  The rule uses assignment identity only, never gold text or edits.
"""
from __future__ import annotations

import argparse
import json

from benchmark import distance
from compare_page_reports import checked_pages, private_json_path


def fuse(baseline, secondary):
    fingerprint = baseline.get("input_fingerprint_sha256")
    if not fingerprint or fingerprint != secondary.get("input_fingerprint_sha256"):
        raise ValueError("Dataset fingerprints differ")
    before, after = checked_pages(baseline), checked_pages(secondary)
    if set(before) != set(after):
        raise ValueError("Page coverage differs")
    rows, pages = [], []
    for page_id, (base_page, base_labels) in before.items():
        secondary_page, secondary_labels = after[page_id]
        if set(base_labels) != set(secondary_labels):
            raise ValueError("Annotation coverage differs")
        page_sources = []
        for label, primary in base_labels.items():
            fallback = secondary_labels[label]
            use_fallback = not primary["region_ids"] and len(fallback["region_ids"]) == 1
            selected = fallback if use_fallback else primary
            reference = primary["reference"]
            if reference != selected["reference"] or selected["edits"] != distance(reference, selected["prediction"]):
                raise ValueError("Reference or stored edit count changed")
            row = {
                "page": page_id,
                "id": label,
                "source": "secondary_missing_only" if use_fallback else "primary",
                "reference": reference,
                "prediction": selected["prediction"],
                "edits": selected["edits"],
                "characters": selected["characters"],
                "assigned": bool(selected["region_ids"]),
                "primary_region_ids": list(primary["region_ids"]),
                "secondary_region_ids": list(fallback["region_ids"]),
            }
            rows.append(row)
            page_sources.append(row["source"])
        pages.append({
            "page": page_id,
            "secondary_missing_only_count": page_sources.count("secondary_missing_only"),
            "primary_count": page_sources.count("primary"),
        })
    characters = sum(row["characters"] for row in rows)
    edits = sum(row["edits"] for row in rows)
    return {
        "schema": 1,
        "input_fingerprint_sha256": fingerprint,
        "production_default": False,
        "automatic_promotion": False,
        "rule": "primary_unassigned_and_secondary_exactly_one_region",
        "pages": pages,
        "rows": rows,
        "aggregate": {
            "annotations": len(rows),
            "characters": characters,
            "selected_edits": edits,
            "selected_cer": edits / max(1, characters),
            "selected_exact": sum(row["edits"] == 0 for row in rows),
            "selected_assigned": sum(row["assigned"] for row in rows),
            "secondary_fallbacks": sum(row["source"] == "secondary_missing_only" for row in rows),
        },
        "limitations": [
            "This is a replay of recorded reports; no new inference or latency is measured.",
            "A secondary one-to-one assignment is not proof of semantic ownership or OCR correctness.",
            "Fallback rows require review and must retain original source/artwork until accepted.",
            "The private Japanese labels are unreviewed and no Vietnamese or clean-background gold exists.",
        ],
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--secondary", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = private_json_path(args.output, new=True)
    baseline = json.loads(private_json_path(args.baseline).read_text(encoding="utf-8"))
    secondary = json.loads(private_json_path(args.secondary).read_text(encoding="utf-8"))
    result = fuse(baseline, secondary)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

