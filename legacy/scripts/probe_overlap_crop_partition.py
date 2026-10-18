"""Unaccepted, pixel-supported OCR crop partition experiment.

Keep captured source geometry/keys and the recorded OCR evidence unchanged.
Inference crops are separate: a blank seam can remove a neighbouring column
from an overlapping crop, never authorize artwork erasure or speaker inference.
Images remain in RAM; no model/network/default changes. Labels grade only.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from benchmark import DirectoryDataset, audit, dataset_fingerprint
from benchmark_pages import assign_to_labels
from manga_live.ocr import (MangaEngine, LAYOUT_VERSION, checked_ocr_results,
                            partition_ocr_boxes)
from manga_live.errors import AppError
from probe_block_guided_grouping import reader_owned

VERSION = "overlap-blank-seam-crop-partition-v1-candidate"


def partition_boxes(image, regions):
    """Compatibility probe over the production crop-partition implementation.

    The benchmark script intentionally keeps its list-shaped return value, but
    must not carry a second copy of the seam algorithm.  This adapter converts
    the production map back to the historical benchmark shape and translates
    safe validation errors into the probe's public ``ValueError`` contract.
    """
    try:
        changed, evidence = partition_ocr_boxes(image, regions)
    except AppError as error:
        if error.code == "OCR_PARTITION":
            raise ValueError(error.message) from error
        raise
    boxes = [list(changed.get(region["id"], region["bbox"])) for region in regions]
    return boxes, evidence


def partitioned_record(region, crop_box, ja):
    """A measured candidate never inherits old translation or plot trust."""
    if not isinstance(ja, str):
        raise ValueError("Typed OCR output required")
    if (not isinstance(region.get("scope"), dict) or not isinstance(region["scope"].get("key"), str)
            or reader_owned(region)):
        raise ValueError("An unowned captured-source scope is required; do not invent a legacy anchor")
    result = {key: deepcopy(value) for key, value in region.items()
              if key not in ("ja", "vi", "expression", "ambiguous")}
    reasons = list(dict.fromkeys([*region.get("reviewReasons", []), "ocr_crop_partition"]))
    result.update(ja=ja, ocrCropBox=list(crop_box), sourceOcr=deepcopy(region),
                  review=True, reviewReasons=reasons, cropPartitionCandidate=True)
    result["scope"].update(memory=False, reason="visual_review")
    return result


def read_evidence(path):
    path = Path(path).resolve()
    if path.parent != ROOT / "artifacts" or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Bounded private evidence in artifacts required")
    return json.loads(path.read_text(encoding="utf-8"))


def run(args):
    if args.plan_only and (args.fresh or args.assert_label):
        raise ValueError("Planning cannot claim fresh OCR or label accuracy")
    recorded = read_evidence(args.reference)
    destination = Path(args.output).resolve()
    if destination.parent != ROOT / "artifacts" or destination.exists():
        raise ValueError("A new private artifact is required")
    with DirectoryDataset(args.folder) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    if (recorded.get("input_fingerprint_sha256") != fingerprint or
            recorded.get("layout_version") != LAYOUT_VERSION or
            recorded.get("ocr") != MangaEngine.name):
        raise ValueError("Source fingerprint/layout/OCR differs")
    by_page = {entry["page"]: entry for entry in recorded["pages"]}
    if len(by_page) != len(recorded["pages"]) or set(by_page) != {p[0]["page_id"] for p in pages}:
        raise ValueError("Exact recorded page coverage required")
    if args.page and args.page not in by_page:
        raise ValueError("Unknown page")
    report = {"version": VERSION, "input_fingerprint_sha256": fingerprint,
        "production_defaults_changed": False, "cloud": False, "image_persistence": False,
        "fresh_ocr": bool(args.fresh), "counts": counts, "audit": issues, "pages": [],
        "source_layout_version": recorded["layout_version"], "ocr": MangaEngine.name,
        "candidate_trust_revision": 1, "plan_only": bool(args.plan_only),
        "limitations": ["Unaudited Japanese labels; no Vietnamese or clean-background gold.",
            "Recorded source detector/OCR; only changed inference crops can receive fresh OCR.",
            "A blank seam is not paragraph ownership, speaker evidence or erasure permission."]}
    engine = None
    for page, image, bubbles in pages:
        page_id = page["page_id"]
        if args.page and page_id != args.page:
            continue
        regions = deepcopy(by_page[page_id]["regions"])
        boxes, evidence = partition_boxes(image, regions)
        changed = [index for index, (region, box) in enumerate(zip(regions, boxes)) if region["bbox"] != box]
        if changed and not args.fresh and not args.plan_only:
            raise ValueError("Changed crops require fresh measured OCR, not inherited text")
        if args.plan_only:
            report["pages"].append({"page": page_id, "partitions": evidence,
                "changed_inference_crops": [{"id": regions[index]["id"], "sourceBox": regions[index]["bbox"],
                                             "ocrCropBox": boxes[index]} for index in changed]})
            print(json.dumps({"page": page_id, "planned_crops": len(changed), "partitions": len(evidence)}), flush=True)
            continue
        start = time.perf_counter()
        if changed:
            if engine is None:
                engine = MangaEngine(ROOT / "models/ocr", 4)
                print(json.dumps({"stage": "local_ocr_load", "page": page_id, "planned_crops": len(changed)}), flush=True)
            for index in changed:
                x, y, w, h = boxes[index]
                ja = checked_ocr_results([engine.recognize(image.crop((x, y, x+w, y+h)))], 1)[0]
                # Retain all original source records, including empty retry
                # outputs. No new pixels, anchors or erasure rights enter it.
                regions[index] = partitioned_record(regions[index], boxes[index], ja)
        aligned, unmatched = assign_to_labels(bubbles, regions)
        row = {"page": page_id, "regions": regions, "partitions": evidence,
               "fresh_crops": len(changed), "aligned": aligned,
               "unmatched_prediction_ids": unmatched,
               "fresh_crop_ms": (time.perf_counter()-start)*1000 if changed else None}
        report["pages"].append(row)
        print(json.dumps({"page": page_id, "fresh_crops": len(changed), "partitions": len(evidence)}), flush=True)
    aligned = [row for page in report["pages"] for row in page.get("aligned", [])]
    report["aggregate"] = {"annotations": len(aligned), "exact": sum(r["edits"] == 0 for r in aligned),
        "edits": sum(r["edits"] for r in aligned), "characters": sum(r["characters"] for r in aligned),
        "aligned": sum(bool(r["region_ids"]) for r in aligned),
        "fresh_crops": sum(page.get("fresh_crops", 0) for page in report["pages"])}
    with destination.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(report["aggregate"]), flush=True)
    if args.assert_label:
        matches = [row for row in aligned if row["id"] == args.assert_label]
        if not args.page or len(matches) != 1:
            raise ValueError("Assertion requires one explicit page/label")
        if matches[0]["edits"] != 0:
            print(json.dumps({"label_exact": False, "edits": matches[0]["edits"]}), flush=True)
            raise SystemExit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--page")
    parser.add_argument("--fresh", action="store_true")
    parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--assert-label")
    parser.add_argument("--output", required=True)
    run(parser.parse_args())
