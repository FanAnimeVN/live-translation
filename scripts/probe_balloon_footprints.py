"""Private, model-free layout replay against exact recorded PP detections.

Images/masks stay in RAM. Reuse OCR only when source geometry AND inference
crops are identical. This grades neither Vietnamese meaning nor restored art.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from benchmark import DirectoryDataset, audit, dataset_fingerprint
from benchmark_pages import assign_to_labels, hashlib_image
from manga_live import ocr
from manga_live.text_scope import make_plan, route_regions


def read_report(value):
    path = Path(value).resolve()
    if path.parent != ROOT / "artifacts" or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Bounded private evidence required")
    report = json.loads(path.read_text(encoding="utf-8"))
    if report.get("cloud") is not False or report.get("ocr") != ocr.MangaEngine.name:
        raise ValueError("Recorded local evidence required")
    return report


def checked_pages(report, eligible):
    pages = report.get("pages", [])
    if len(pages) != len(eligible) or {p["page"] for p in pages} != eligible:
        raise ValueError("Every eligible page must occur exactly once")
    return {p["page"]: p for p in pages}


def source_geometry(regions):
    return [{key: r[key] for key in ("id", "bbox", "order")} for r in regions]


def replay(image, detections, original):
    actual_lettering = ocr.balloon_lettering
    def previous_lettering(*args, **kwargs):
        return actual_lettering(*args)  # Explicit pre-footprint union-only control.
    with patch.object(ocr, "balloon_lettering", previous_lettering):
        previous = ocr.group_regions(image, detections)
    current = ocr.group_regions(image, detections)
    if source_geometry(previous) != source_geometry(original) or any(
            a["overlay"] != b["overlay"] for a, b in zip(previous, original)):
        raise ValueError("Recorded detector replay does not reproduce production source geometry/overlay")
    if source_geometry(current) != source_geometry(original):
        raise ValueError("Lettering fix changed OCR source geometry/order/IDs")
    previous_crops, previous_partitions = ocr.partition_ocr_boxes(image, previous)
    current_crops, current_partitions = ocr.partition_ocr_boxes(image, current)
    if previous_crops != current_crops or previous_partitions != current_partitions:
        raise ValueError("Inference crops changed: fresh OCR is required, not inherited text")
    sources = deepcopy(original)
    for source, geometry in zip(sources, current):
        source["overlay"] = geometry["overlay"]
        if geometry.get("balloon"):
            source["balloon"] = geometry["balloon"]
        else:
            source.pop("balloon", None)
    # A render improvement must not manufacture role/source/memory permission.
    controls = [route_regions(rows, make_plan(image, rows, hashlib_image(image)), {})
                for rows in (deepcopy(original), sources)]
    if [r["scope"] for r in controls[0]] != [r["scope"] for r in controls[1]]:
        raise ValueError("Layout changed current routing/source keys; inspect before promotion")
    if [r["scope"]["key"] for r in controls[1]] != [r["scope"]["key"] for r in original]:
        raise ValueError("A stored reader source key changed")
    if any(a.get("balloon") and not b.get("balloon") for a, b in zip(previous, current)):
        raise ValueError("An existing integrated balloon regressed")
    return previous, current, sources


def run(args):
    reference, evidence = read_report(args.reference), read_report(args.detector_replay)
    destination = Path(args.output).resolve()
    if destination.parent != ROOT / "artifacts" or destination.exists():
        raise ValueError("New private JSON output required; never overwrite evidence")
    with DirectoryDataset(args.folder) as dataset:
        counts, issues, pages = audit(dataset)
        fingerprint = dataset_fingerprint(dataset)
    if any(r.get("input_fingerprint_sha256") != fingerprint for r in (reference, evidence)):
        raise ValueError("Dataset/evidence fingerprint differs")
    if (reference.get("layout_version") != "balloon-mask-v16-outer-notch-veto"
            or evidence.get("detector") != "PP-OCRv5_mobile_det"):
        raise ValueError("This comparator requires the recorded v16 baseline and PP source lines")
    eligible = {page["page_id"] for page, _, _ in pages}
    refs, raws = [checked_pages(value, eligible) for value in (reference, evidence)]
    report = {"schema": 1, "cloud": False, "inference": False, "image_persistence": False,
              "layout_version": ocr.LAYOUT_VERSION, "input_fingerprint_sha256": fingerprint,
              "counts": counts, "audit": issues, "pages": [],
              "limitations": ["Recorded detector/OCR, not fresh inference or live latency.",
                              "Stored source scope is preserved; current routing compared control vs candidate separately.",
                              "No independent Japanese/Vietnamese/clean-background gold."]}
    for page, image, bubbles in pages:
        ident = page["page_id"]
        raw = raws[ident]["detector_evidence"]["raw_detections"]
        if not isinstance(raw, list) or not 1 <= len(raw) <= 512:
            raise ValueError("Bounded raw PP source evidence required")
        previous, current, sources = replay(image, raw, refs[ident]["regions"])
        aligned, unmatched = assign_to_labels(bubbles, sources)
        if aligned != refs[ident]["aligned"]:
            raise ValueError("OCR/alignment changed under a lettering-only upgrade")
        changes = [{"id": after["id"], "bbox": after["bbox"],
                    "previous_integrated": bool(before.get("balloon")),
                    "integrated": bool(after.get("balloon")),
                    "text_box": after.get("balloon", {}).get("textBox")}
                   for before, after in zip(previous, current) if before != after]
        report["pages"].append({"page": ident, "previous_integrated": sum(bool(r.get("balloon")) for r in previous),
                                "integrated": sum(bool(r.get("balloon")) for r in current),
                                "changes": changes, "regions": sources, "aligned": aligned,
                                "unmatched_prediction_ids": unmatched})
        print(json.dumps({"page": ident, "changes": changes}), flush=True)
    aligned = [r for p in report["pages"] for r in p["aligned"]]
    report["aggregate"] = {"source_regions": sum(len(p["regions"]) for p in report["pages"]),
                           "previous_integrated": sum(p["previous_integrated"] for p in report["pages"]),
                           "integrated": sum(p["integrated"] for p in report["pages"]),
                           "exact": sum(r["reference"] == r["prediction"] for r in aligned),
                           "characters": sum(r["characters"] for r in aligned),
                           "edits": sum(r["edits"] for r in aligned),
                           "ocr_geometry_crops_text_alignment_scope_preserved": True}
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["aggregate"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--detector-replay", required=True)
    parser.add_argument("--output", required=True)
    run(parser.parse_args())
