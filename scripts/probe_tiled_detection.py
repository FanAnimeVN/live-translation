"""Private two-stage recall experiment using the installed pinned PP detector.

Full-page detections have priority. Four overlapping, independently resized
tiles may add new proposals, never silently replace a full-page source. Every
raw proposal and rejection reason is retained; a rejected proposal is not an
irrelevance classification. Images/crops/masks remain in RAM. This script is
not imported by the companion or included in the product defaults.

Detection and recognition are separate processes to avoid keeping Paddle and
PyTorch resident together on a low-memory development machine. No cloud or
model download is performed by either phase.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import json
import math
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from benchmark import audit, dataset_source, dataset_fingerprint
from benchmark_pages import run as recognize_pages, hashlib_image
from compare_page_reports import private_json_path
from manga_live.ocr import PaddleDetector, group_regions, rect, LAYOUT_VERSION
from provision import verify

VERSION = "pp-tiled-recall-v1"
POLICY = {
    "grid": [2, 2], "tile_fraction": .6, "tile_long_edge": 960,
    "duplicate_iou": .5, "duplicate_containment": .85,
    "ambiguous_containment": .15, "internal_edge_margin": 2,
    "baseline_precedence": True,
}


def verified_model(kind):
    """Preflight only: never resolve/download a missing model during inference."""
    spec = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))[kind]
    if any(not verify(ROOT / "models" / kind / name, file_spec) for name, file_spec in spec["files"].items()):
        raise ValueError(f"Installed {kind} model does not match its pinned manifest")
    return deepcopy(spec)


def tile_boxes(width, height):
    if any(type(value) is not int or value < 64 or value > 8000 for value in (width, height)) or width*height > 12000000:
        raise ValueError("Invalid source dimensions")
    w, h = math.ceil(width*.6), math.ceil(height*.6)
    return [[x, y, w, h] for y in (0, height-h) for x in (0, width-w)]


def checked_line(value, size):
    polygon = value.get("polygon") if isinstance(value, dict) else None
    score = value.get("score") if isinstance(value, dict) else None
    if (not isinstance(polygon, list) or len(polygon) != 4
            or type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
        raise ValueError("Invalid detector source")
    for point in polygon:
        if (not isinstance(point, list) or len(point) != 2
                or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
                or not 0 <= point[0] <= size[0] or not 0 <= point[1] <= size[1]):
            raise ValueError("Invalid detector coordinates")
    box = rect(polygon)
    if box[2] <= 0 or box[3] <= 0:
        raise ValueError("Degenerate detector source")
    return {"polygon": deepcopy(polygon), "score": score}


def overlap(a, b):
    shared = max(0, min(a[0]+a[2], b[0]+b[2])-max(a[0], b[0])) * max(
        0, min(a[1]+a[3], b[1]+b[3])-max(a[1], b[1]))
    return shared / min(a[2]*a[3], b[2]*b[3]), shared / (a[2]*a[3]+b[2]*b[3]-shared)


def fuse_detections(baseline, tile_records, source_size):
    if not isinstance(baseline, list) or len(baseline) > 512 or not isinstance(tile_records, list) or len(tile_records) > 4:
        raise ValueError("Unbounded detector evidence")
    selected, evidence = [], []
    for raw in baseline:
        line = checked_line(raw, source_size)
        evidence.append({**deepcopy(line), "pass": "full", "decision": "baseline", "selected_index": len(selected)})
        selected.append(line)
    candidates = []
    for tile_index, record in enumerate(tile_records):
        tile = record.get("tile") if isinstance(record, dict) else None
        raw = record.get("detections") if isinstance(record, dict) else None
        if (not isinstance(tile, list) or len(tile) != 4 or any(type(v) is not int for v in tile)
                or min(tile[:2]) < 0 or min(tile[2:]) <= 0
                or tile[0]+tile[2] > source_size[0] or tile[1]+tile[3] > source_size[1]
                or not isinstance(raw, list) or len(raw) > 512):
            raise ValueError("Invalid tile evidence")
        x, y, w, h = tile
        for native_index, value in enumerate(raw):
            local = checked_line(value, (w, h))
            line = {"polygon": [[px+x, py+y] for px, py in local["polygon"]], "score": local["score"]}
            box = rect(local["polygon"])
            cut = ((x > 0 and box[0] <= 2) or (y > 0 and box[1] <= 2)
                   or (x+w < source_size[0] and box[0]+box[2] >= w-2)
                   or (y+h < source_size[1] and box[1]+box[3] >= h-2))
            entry = {**deepcopy(line), "pass": "tile", "tile_index": tile_index,
                     "tile": list(tile), "native_index": native_index,
                     "local_polygon": local["polygon"], "decision": "tile_edge" if cut else "pending"}
            evidence.append(entry)
            if not cut: candidates.append((line, entry))
    # Full page always wins. Among new tile-only proposals, compare the most
    # confident original record first, without changing its raw score.
    for line, entry in sorted(candidates, key=lambda pair: -pair[0]["score"]):
        relations = [overlap(rect(line["polygon"]), rect(previous["polygon"])) for previous in selected]
        duplicate = next((i for i, (containment, iou) in enumerate(relations) if iou >= .5 or containment >= .85), None)
        if duplicate is not None:
            entry.update(decision="duplicate", duplicate_of=duplicate)
        elif any(containment > .15 for containment, _ in relations):
            entry["decision"] = "overlap_review"
        else:
            entry.update(decision="new", selected_index=len(selected))
            selected.append(line)
    return selected, evidence


class TiledDetector:
    name = PaddleDetector.name
    grouping_version = LAYOUT_VERSION
    review_only = True

    def __init__(self, threads, detector=None):
        self.detector = detector or PaddleDetector(ROOT / "models/detector", threads)
        self.details = {"kind": VERSION, "policy": deepcopy(POLICY), "production_default": False,
                        "weights": "same installed pinned PP-OCRv5_mobile_det", "review_only": True}

    def detect(self, image):
        baseline = self.detector.detect_raw(image)
        records = []
        for tile in tile_boxes(*image.size):
            x, y, w, h = tile
            with image.crop((x, y, x+w, y+h)) as crop:
                lines = self.detector.detect_raw(crop, limit_side_len=960, limit_type="resize_long")
            records.append({"tile": tile, "detections": lines})
        fused, raw = fuse_detections(baseline, records, image.size)
        self.last_evidence = {"raw_detections": raw, "selected_detections": deepcopy(fused),
                              "tiles": [record["tile"] for record in records], "policy": deepcopy(POLICY)}
        regions = group_regions(image, fused, include_source_members=True)
        for region in regions:
            region.update(review=True, overlay="label")
            region.pop("balloon", None)
        return regions


class DetectionReplay:
    name = PaddleDetector.name
    grouping_version = LAYOUT_VERSION
    review_only = True

    def __init__(self, report, pages):
        if (report.get("experiment") != VERSION or report.get("layout_version") != LAYOUT_VERSION
                or report.get("policy") != POLICY or report.get("phase") != "detection"
                or report.get("production_default") is not False or report.get("cloud") is not False):
            raise ValueError("Incompatible detection replay")
        self.records = report.get("pages", [])
        if [r.get("page") for r in self.records] != [page["page_id"] for page, _, _ in pages]:
            raise ValueError("Replay page coverage changed")
        self.index = 0
        self.details = {"kind": VERSION, "policy": deepcopy(POLICY), "production_default": False,
                        "review_only": True, "detection_replay": True,
                        "latency_excludes_recorded_detection": True}

    def detect(self, image):
        record = self.records[self.index]; self.index += 1
        if record["source_size"] != list(image.size) or record["image_sha256"] != hashlib_image(image):
            raise ValueError("Replay source pixels changed")
        evidence = record["detector_evidence"]
        regions = deepcopy(record["regions"])
        # Do not let the older benchmark's [:64] turn a crowded candidate into
        # apparently complete evidence by dropping the tail.
        if len(regions) > 64:
            raise ValueError("Candidate exceeds the source-region budget; do not truncate")
        self.last_evidence = {**deepcopy(evidence), "recorded_detector_ms": record["detector_ms"]}
        return regions


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--threads", type=int, choices=(1, 2, 4, 8), default=4)
    parser.add_argument("--recognize-from", help="Replay private detection JSON in a fresh OCR-only process")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    destination = private_json_path(args.output, new=True)
    with dataset_source(args) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    if args.recognize_from:
        report = json.loads(private_json_path(args.recognize_from).read_text(encoding="utf-8"))
        if report.get("input_fingerprint_sha256") != fingerprint:
            raise ValueError("Dataset fingerprint changed")
        replay = DetectionReplay(report, pages)
        replay.details["ocr_model_manifest"] = verified_model("ocr")
        recognize_pages(args, detector_override=replay)
        return
    model = verified_model("detector")
    detector = TiledDetector(args.threads)
    report = {"schema": 1, "experiment": VERSION, "phase": "detection", "cloud": False,
              "production_default": False, "input_fingerprint_sha256": fingerprint,
              "layout_version": LAYOUT_VERSION, "policy": deepcopy(POLICY), "threads": args.threads,
              "model_manifest": model,
              "counts": counts, "audit": issues, "pages": [],
              "limitations": ["Frozen development hypothesis, not calibrated recall or a runtime default.",
                  "Bounding-box overlap is not glyph identity, semantic relevance or erasure permission.",
                  "No OCR in this phase; no translation/clean-background quality is measured."]}
    for page, image, _ in pages:
        started = time.perf_counter()
        regions = detector.detect(image)
        elapsed = (time.perf_counter()-started)*1000
        report["pages"].append({"page": page["page_id"], "source_size": list(image.size),
            "image_sha256": hashlib_image(image), "regions": regions,
            "detector_ms": elapsed, "detector_evidence": deepcopy(detector.last_evidence)})
        decisions = {}
        for row in detector.last_evidence["raw_detections"]:
            decisions[row["decision"]] = decisions.get(row["decision"], 0)+1
        print(json.dumps({"page": page["page_id"], "regions": len(regions), "decisions": decisions,
                          "detector_ms": elapsed}), flush=True)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2, allow_nan=False)


if __name__ == "__main__":
    main()
