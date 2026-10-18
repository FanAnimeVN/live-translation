"""Private full-page detector/OCR/cleanup diagnostics, not translation grading.

Images and raster patches never leave RAM. Sparse/approximate annotations do
not justify detector precision or clean-background fidelity claims.
"""
import argparse
import json
from pathlib import Path
import statistics
import threading
import time
from benchmark import audit, dataset_source, dataset_fingerprint, normalized, distance, ROOT
from manga_live.ocr import (MangaEngine, PaddleDetector, group_regions, recognize_regions,
                             partition_ocr_boxes, OCR_PARTITION_VERSION,
                             LAYOUT_VERSION, EXPERIMENTAL_LAYOUT_VERSION)
from manga_live.render_cleanup import render_patch, CLEANUP_VERSION, MAX_JOB_PATCH_BYTES
from manga_live.text_scope import make_plan,route_regions,SCOPE_VERSION
from manga_live.page_hardness import PAGE_HARDNESS_VERSION, score_page_hardness


def intersection(a, b):
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return max(0, min(ax+aw, bx+bw)-max(ax, bx)) * max(0, min(ay+ah, by+bh)-max(ay, by))


def assign_to_labels(bubbles, regions):
    """Each prediction used at most once; don't duplicate merged output as gold.

    Group by >=50% of prediction area inside a supplied annotation. This is
    only an alignment diagnostic, not proof that all original glyphs are read.
    """
    groups = [[] for _ in bubbles]
    boxes = [[b["bbox"][key] for key in ("x", "y", "w", "h")] for b in bubbles]
    unmatched = []
    for region in regions:
        box = region["bbox"]
        area = max(1, box[2]*box[3])
        overlaps = [(intersection(box, gold)/area, -gold[2]*gold[3], i) for i, gold in enumerate(boxes)]
        candidate = max(overlaps, default=(0, 0, -1))
        if candidate[0] >= .5:
            groups[candidate[2]].append(region)
        else:
            unmatched.append(region["id"])
    rows = []
    for bubble, matches, box in zip(bubbles, groups, boxes):
        matches.sort(key=lambda r: r.get("order", 0))
        ref = normalized(bubble["ja_ocr_truth"])
        pred = normalized("".join(r.get("ja", "") for r in matches))
        ious = []
        for region in matches:
            shared = intersection(box, region["bbox"])
            union = box[2]*box[3]+region["bbox"][2]*region["bbox"][3]-shared
            ious.append(shared/max(1, union))
        rows.append({"id": bubble["bubble_id"], "region_ids": [r["id"] for r in matches],
                     "reference": ref, "prediction": pred, "edits": distance(ref, pred),
                     "characters": len(ref), "best_iou": max(ious, default=0),
                     "one_to_one_iou_50": len(matches) == 1 and bool(ious and ious[0] >= .5)})
    return rows, unmatched


class DetectorResizeProbe:
    """One-variable local comparator, not a companion default/configuration."""
    name=PaddleDetector.name
    def __init__(self,threads,side_len,*,force_long=False):
        self.detector=PaddleDetector(ROOT/"models/detector",threads)
        self.side_len=side_len
        self.force_long=force_long
        self.details={"kind":"pp-resize-only","limit_side_len":side_len,
                      "limit_type":"resize_long" if force_long else "max",
                      "weights":"same pinned PP-OCRv5_mobile_det","production_default":False}

    def detect(self,image):
        options={"limit_side_len":self.side_len}
        if self.force_long:options["limit_type"]="resize_long"
        lines=self.detector.detect_raw(image,**options)
        self.last_evidence={"raw_line_count":len(lines),**self.details,
                            "raw_detections":[{"polygon":[list(point) for point in line["polygon"]],
                                               "score":line["score"]} for line in lines],
                            "resize_evidence":resize_processor_evidence(self.detector,image,options)}
        return group_regions(image,lines,include_source_members=True)


def resize_processor_evidence(detector,image,options):
    """Replay the installed resize on blank pixels; not tensor instrumentation.

    This detects a max-cap no-op without another network forward or private
    pixel persistence. Mark unavailable instead of guessing another backend.
    Time/RAM for this diagnostic replay is included in detector_ms.
    """
    import numpy as np
    predictor=getattr(detector.model,"paddlex_predictor",None)
    processors=getattr(predictor,"pre_tfs",{})
    resize=processors.get("Resize") if isinstance(processors,dict) else None
    if resize is None:return {"available":False,"reason":"unsupported_predictor"}
    pixels=np.zeros((image.height,image.width,3),dtype=np.uint8)
    resized,_=resize(imgs=[pixels],**options,max_side_limit=getattr(predictor,"max_side_limit",4000))
    return {"available":True,"method":"installed_processor_blank_replay_not_tensor_trace",
            "source_hw":[image.height,image.width],"resized_hw":list(resized[0].shape[:2]),
            "resize_type":getattr(resize,"resize_type",None),
            "limit_type":options.get("limit_type",getattr(resize,"limit_type",None))}


class DetectorThresholdProbe:
    """One-variable detector-recall comparator; never a companion default."""
    name=PaddleDetector.name
    def __init__(self,threads,threshold):
        self.detector=PaddleDetector(ROOT/"models/detector",threads)
        self.threshold=threshold
        self.details={"kind":"pp-box-threshold-only","box_thresh":threshold,
                      "post_output_min_score":.35,"default_upstream_box_thresh":.6,
                      "weights":"same pinned PP-OCRv5_mobile_det","production_default":False}
    def detect(self,image):
        lines=self.detector.detect_raw(image,box_threshold=self.threshold)
        self.last_evidence={"raw_line_count":len(lines),"box_thresh":self.threshold,
                            "low_score_line_count":sum(line["score"]<.6 for line in lines),
                            "raw_detections":[{"polygon":[list(point) for point in line["polygon"]],
                                               "score":line["score"]} for line in lines]}
        return group_regions(image,lines,include_source_members=True)


class OpenTextGroupingProbe:
    """Unaccepted aligned-open candidate, never a companion setting."""
    name=PaddleDetector.name
    def __init__(self,threads):
        self.detector=PaddleDetector(ROOT/"models/detector",threads)
        self.details={"kind":"open-text-grouping-only","production_default":False,
                      "weights":"same pinned PP-OCRv5_mobile_det"}
    def detect(self,image):
        return group_regions(image,self.detector.detect_raw(image),experimental_open_text=True)


def run(args, detector_override=None, engine_override=None):
    side_len=getattr(args,"detector_side_len",None)
    resize_long=getattr(args,"detector_resize_long",None)
    box_threshold=getattr(args,"detector_box_threshold",None)
    open_text=getattr(args,"experimental_open_text",False)
    requested_probes=sum((bool(open_text),side_len is not None,resize_long is not None,box_threshold is not None))
    if requested_probes>1 or (detector_override is not None and requested_probes):
        raise ValueError("Change one variable: detector comparators cannot be combined")
    with dataset_source(args) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    detector = detector_override or (OpenTextGroupingProbe(args.threads) if open_text else
                                    DetectorResizeProbe(args.threads,side_len) if side_len is not None else
                                    DetectorResizeProbe(args.threads,resize_long,force_long=True) if resize_long is not None else
                                    DetectorThresholdProbe(args.threads,box_threshold) if box_threshold is not None else
                                    PaddleDetector(ROOT / "models/detector", args.threads))
    engine = engine_override or MangaEngine(ROOT / "models/ocr", args.threads)
    cancel = threading.Event()
    report = {"schema": 1, "input_fingerprint_sha256": fingerprint, "counts": counts, "audit": issues,
              "device": "CPU", "threads": args.threads, "ocr": engine.name, "detector": detector.name,
              "layout_version": getattr(detector,"grouping_version",EXPERIMENTAL_LAYOUT_VERSION if open_text else LAYOUT_VERSION),
              "presentation_version":getattr(detector,"presentation_version",LAYOUT_VERSION),
              "ocr_partition_version": OCR_PARTITION_VERSION,
              "fresh_inference": True,
              "production_default": not (requested_probes or detector_override is not None or engine_override is not None),
              "cleanup_version": CLEANUP_VERSION, "cloud": False,
              "scope_version":SCOPE_VERSION,"scope_ground_truth":False,
              "page_hardness_version":PAGE_HARDNESS_VERSION,
              "limitations": ["Ground truth has not been independently verified; labels include difficult/partial text.",
                  "Annotation alignment uses prediction containment, not detector precision or true text recall.",
                  "Cleanup acceptance/pixel isolation is not visual fidelity; no clean-background gold images.",
                  "No translation model, context retrieval or browser transport in this benchmark.",
                  "First page includes detector/engine imports and loading; later pages are warm, not p95 evidence."],
              "pages": []}
    if hasattr(detector,"details"):
        report["experimental_detector"] = detector.details
    if hasattr(engine,"details"):
        report["experimental_recognizer"] = engine.details
    for page, image, bubbles in pages:
        started = time.perf_counter()
        regions = detector.detect(image)[:64]
        detector_ms = (time.perf_counter()-started)*1000
        # Pre-OCR routing evidence only. It cannot suppress text, infer a
        # semantic role, or grant artwork-erasure authority.
        pre_ocr_hardness = score_page_hardness(regions, image.width, image.height)
        crop_boxes, partition_evidence = partition_ocr_boxes(image, regions)
        started = time.perf_counter()
        recognized = recognize_regions(image, regions, engine, cancel, batch_size=2,
                                      crop_boxes=crop_boxes,
                                      partition_evidence=partition_evidence)
        recognized=route_regions(recognized,make_plan(image,regions,hashlib_image(image)),{})
        if getattr(detector,"review_only",False):
            # Private recall proposals are not erasure or plot-memory evidence.
            # This does not change the production detector or reader bindings.
            for region in recognized:
                region["scope"]["memory"]=False
                region.update(review=True,overlay="label")
                region.pop("balloon",None)
        if open_text or detector_override is not None:
            for region in recognized:
                if "layout_cluster" in region.get("reviewReasons",[]):
                    # A successful union OCR is not proof of semantic ownership
                    # or safe plot evidence from an unaccepted experiment.
                    region["scope"]["memory"]=False
        ocr_ms = (time.perf_counter()-started)*1000
        started = time.perf_counter()
        patches, budget = [], MAX_JOB_PATCH_BYTES
        for region in recognized:
            if region.get("scope",{}).get("action")=="defer":continue
            patch = render_patch(image, region, cancel, max_bytes=budget)
            if patch:
                size = (len(patch["dataUrl"])-22)*3//4
                budget -= size
                # Never persist PNG/base64, image buffers or masks.
                patches.append({"id": patch["regionId"], "bytes_upper_bound": size, "bbox": patch["bbox"]})
            if budget <= 0:
                break
        cleanup_ms = (time.perf_counter()-started)*1000
        aligned, unmatched = assign_to_labels(bubbles, recognized)
        row = {"page": page["page_id"], "detected": len(regions), "recognized": len(recognized),
               "flat_balloon_count": sum(bool(r.get("balloon")) for r in recognized),
               "review_count": sum(bool(r.get("review")) for r in recognized),
               "deferred_ids":[r["id"] for r in recognized if r.get("scope",{}).get("action")=="defer"],
               "detector_ms": detector_ms, "ocr_ms": ocr_ms, "cleanup_ms": cleanup_ms,
               "pre_ocr_hardness": pre_ocr_hardness,
               "transient_patches": patches, "partitions": partition_evidence,
               "partitioned_crop_count": len(crop_boxes),
               "aligned": aligned, "unmatched_prediction_ids": unmatched,
               "regions": [{key: r[key] for key in ("id", "bbox", "order", "ja", "overlay", "review","scope",
                     "score","reviewReasons","sourceMembers","ocrCropBox","ocrPartition") if key in r} for r in recognized]}
        if hasattr(detector, "last_evidence"):
            row["detector_evidence"] = detector.last_evidence
        report["pages"].append(row)
        print(json.dumps({key: row[key] for key in ("page", "detected", "recognized", "flat_balloon_count", "review_count", "detector_ms", "ocr_ms", "cleanup_ms")}), flush=True)
    aligned = [r for p in report["pages"] for r in p["aligned"]]
    report["aggregate"] = {"annotation_count": len(aligned),
        "annotations_with_assigned_prediction": sum(bool(r["region_ids"]) for r in aligned),
        "diagnostic_aligned_cer": sum(r["edits"] for r in aligned)/max(1, sum(r["characters"] for r in aligned)),
        "diagnostic_aligned_exact_match": sum(r["reference"] == r["prediction"] for r in aligned)/max(1, len(aligned)),
        "one_to_one_iou_50": sum(r["one_to_one_iou_50"] for r in aligned),
        "total_regions": sum(p["recognized"] for p in report["pages"]),
        "flat_balloon_count": sum(p["flat_balloon_count"] for p in report["pages"]),
        "patch_count": sum(len(p["transient_patches"]) for p in report["pages"]),
         "partitioned_crop_count": sum(p["partitioned_crop_count"] for p in report["pages"]),
         "partition_count": sum(len(p["partitions"]) for p in report["pages"]),
        "deferred_regions":sum(len(p["deferred_ids"]) for p in report["pages"]),
        "warm_cleanup_p50_ms": statistics.median(p["cleanup_ms"] for p in report["pages"][1:]) if len(pages)>1 else None}
    destination = Path(args.output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["aggregate"], indent=2))


def hashlib_image(image):
    # Pixel binding is only for private diagnostic scope keys; no bytes persist.
    import hashlib
    return hashlib.sha256(image.tobytes()).hexdigest()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--zip")
    inputs.add_argument("--folder")
    parser.add_argument("--threads", type=int, default=4)
    detector_probe=parser.add_mutually_exclusive_group()
    detector_probe.add_argument("--detector-side-len",type=int,choices=(960,1280,1600),
                        help="Experimental PP resize comparator only; does not change companion defaults")
    detector_probe.add_argument("--detector-resize-long",type=int,choices=(1280,1600),
                        help="Force a long-edge resize comparator, including upscale; not a companion setting")
    detector_probe.add_argument("--detector-box-threshold",type=float,choices=(0.35,0.4,0.45,0.5,0.6),
                        help="Experimental upstream PP box_thresh comparator, not a companion setting")
    parser.add_argument("--output", default=str(ROOT / "artifacts/private-pages.json"))
    detector_probe.add_argument("--experimental-open-text",action="store_true",
                        help="Compare unaccepted open grouping only; does not change companion defaults")
    run(parser.parse_args())
