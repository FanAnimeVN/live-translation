"""Fixed-crop comparison only. Pixels remain in RAM; gold never routes OCR."""
import argparse
from copy import deepcopy
import hashlib
import json
import math
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from benchmark import DirectoryDataset, audit, dataset_fingerprint, normalized, distance
from compare_page_reports import checked_pages, compare, private_json_path
from benchmark_pages import assign_to_labels
from baberu_probe_engine import BaberuProbe


def reorder_recorded_members(region,*,directional_votes=False):
    """Comparator-only: disjoint fragments of one column/row keep order.

    Source projections, never padded crops or text content, create precedence.
    Unconstrained members retain the v1 RTL/top-down priority. No merging,
    recognition, punctuation editing or source/erasure authority is added.
    V2 remains the default; explicit v3 lets near-square fragments abstain
    from direction voting and reports any tie fallback.
    """
    if type(directional_votes) is not bool:
        raise ValueError("Explicit direction recipe required")
    members, readings = region.get("sourceMembers"), region.get("member_readings")
    if (not isinstance(members, list) or not 1 <= len(members) <= 512
            or not isinstance(readings, list) or len(readings) != len(members)):
        raise ValueError("Complete retained member readings required")
    excluded = region.get("readerExcluded", False)
    if type(excluded) is not bool:
        raise ValueError("Explicit reader exclusion required")
    bounds, seen = {}, set()
    for row in readings:
        if not isinstance(row, dict):
            raise ValueError("Recorded member identity/text mismatch")
        index = row.get("member_index")
        if (type(index) is not int or not 0 <= index < len(members) or index in seen
                or not isinstance(members[index], dict) or row.get("source") != members[index]
                or not isinstance(row.get("raw_text"), str) or len(row["raw_text"]) > 4096):
            raise ValueError("Recorded member identity/text mismatch")
        if (row.get("status") != ("reader_excluded" if excluded else "recognized")
                or excluded and row["raw_text"]):
            raise ValueError("Recorded reader exclusion disagrees with recognition")
        crop = row.get("crop_box")
        if (not isinstance(crop, list) or len(crop) != 4 or any(type(v) is not int for v in crop)
                or min(crop[:2]) < 0 or min(crop[2:]) < 1):
            raise ValueError("Invalid recorded source crop")
        points = members[index].get("polygon")
        if (not isinstance(points, list) or len(points) != 4 or any(
                not isinstance(p, list) or len(p) != 2 or any(
                    type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in p) for p in points)):
            raise ValueError("Invalid recorded source polygon")
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        box = (min(xs), min(ys), max(xs), max(ys))
        if box[0] >= box[2] or box[1] >= box[3]:
            raise ValueError("Degenerate recorded source polygon")
        bounds[index] = box
        seen.add(index)
    if region.get("ja") != "".join(row["raw_text"] for row in readings):
        raise ValueError("Recorded text is not the untouched member concatenation")
    vertical = sum(y2-y1 >= 1.5*(x2-x1) for x1, y1, x2, y2 in bounds.values()) > len(bounds)/2
    direction_evidence = {}
    if directional_votes:
        # The old binary vote treats every short/square Japanese fragment as
        # evidence of horizontal writing. Use the SAME fixed aspect evidence
        # symmetrically: square fragments abstain, they do not flip a column.
        v = sum(y2-y1 >= 1.5*(x2-x1) for x1,y1,x2,y2 in bounds.values())
        h = sum(x2-x1 >= 1.5*(y2-y1) for x1,y1,x2,y2 in bounds.values())
        if v != h:vertical = v > h
        direction_evidence = {"vertical_votes":v,"horizontal_votes":h,"ambiguous_votes":len(bounds)-v-h,
                              "selected":"vertical" if vertical else "horizontal","fallback":v==h}
    successors = {index: set() for index in bounds}
    predecessors = {index: 0 for index in bounds}
    for a, (ax1, ay1, ax2, ay2) in bounds.items():
        for b, (bx1, by1, bx2, by2) in bounds.items():
            if a == b:
                continue
            overlap = min(ax2, bx2)-max(ax1, bx1) if vertical else min(ay2, by2)-max(ay1, by1)
            extent = min(ax2-ax1, bx2-bx1) if vertical else min(ay2-ay1, by2-by1)
            precedes = ay2 <= by1 if vertical else ax2 <= bx1
            if overlap >= .6*extent and precedes:
                successors[a].add(b)
                predecessors[b] += 1
    by_index = {row["member_index"]: row for row in readings}
    def priority(index):
        # Retain v1 tie-breaking; halo coordinates do not grant precedence.
        x, y = by_index[index]["crop_box"][:2]
        return (-x, y, index) if vertical else (y, x, index)
    ready = [index for index, count in predecessors.items() if count == 0]
    ordered = []
    while ready:
        index = min(ready, key=priority)
        ready.remove(index)
        ordered.append(deepcopy(by_index[index]))
        for child in successors[index]:
            predecessors[child] -= 1
            if predecessors[child] == 0:
                ready.append(child)
    if len(ordered) != len(readings):
        raise ValueError("Conflicting source fragment precedence")
    result = {**deepcopy(region), "ja": "".join(row["raw_text"] for row in ordered),
            "member_readings": ordered, "erasure_authority": False,
            "reading_order_recipe": "source-direction-votes-v3" if directional_votes else "source-fragment-precedence-v2"}
    if directional_votes:result["direction_evidence"] = direction_evidence
    return result


def recognize_source_members(engine, image, region):
    """Frozen source-only recipe: 2px halo, no rotation, vertical RTL ordering.

    This is not a new default, glyph mask, speaker binding or semantic filter.
    Individual crops preserve orientation for the vertical-capable recognizer.
    """
    members = region.get("sourceMembers")
    excluded = region.get("readerExcluded", False)
    if (not isinstance(members, list) or not 1 <= len(members) <= 512
            or type(excluded) is not bool):
        raise ValueError("Retained source members and explicit exclusions required")
    readings = []
    for index, member in enumerate(members):
        points = member.get("polygon") if isinstance(member, dict) else None
        if (not isinstance(points, list) or len(points) != 4 or any(
                not isinstance(p, list) or len(p) != 2 or any(
                    type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in points)):
            raise ValueError("Invalid retained source polygon")
        xs, ys = [p[0] for p in points], [p[1] for p in points]
        if min(xs) < 0 or min(ys) < 0 or max(xs) > image.width or max(ys) > image.height:
            raise ValueError("Retained polygon outside source image")
        left, top, right, bottom = math.floor(min(xs)), math.floor(min(ys)), math.ceil(max(xs)), math.ceil(max(ys))
        if left == right or top == bottom:
            raise ValueError("Degenerate retained polygon")
        x1, y1, x2, y2 = max(0, left-2), max(0, top-2), min(image.width, right+2), min(image.height, bottom+2)
        readings.append({"member_index": index, "source": deepcopy(member),
            "crop_box": [x1, y1, x2-x1, y2-y1], "vertical": bottom-top >= 1.5*(right-left)})
    vertical = sum(r["vertical"] for r in readings) > len(readings)/2
    readings.sort(key=lambda r: (-r["crop_box"][0], r["crop_box"][1], r["member_index"]) if vertical else (
        r["crop_box"][1], r["crop_box"][0], r["member_index"]))
    for row in readings:
        started = time.perf_counter()
        if excluded:
            row.update(status="reader_excluded", raw_text="")
        else:
            x, y, w, h = row["crop_box"]
            row.update(status="recognized", raw_text=engine.recognize(image.crop((x, y, x+w, y+h))),
                       decode=deepcopy(getattr(engine,"last_decode",None)))
        row["ms"] = (time.perf_counter()-started)*1000
    return {**deepcopy(region), "ja": "".join(row["raw_text"] for row in readings),
            "member_readings": readings, "erasure_authority": False}


def replay_recorded_report(recorded, pages, fingerprint,*,directional_votes=False):
    """Rerate one frozen geometry rule, never run OCR or use gold to order."""
    if (recorded.get("complete") is not True or recorded.get("fresh_inference") is not True
            or recorded.get("cloud") is not False
            or recorded.get("crop_recipe") != "source-members-axis-halo2-rtl-v1"
            or recorded.get("input_fingerprint_sha256") != fingerprint):
        raise ValueError("Complete, matching, original member inference required")
    before = checked_pages(recorded)
    if len(pages) != len(before) or {p[0]["page_id"] for p in pages} != set(before):
        raise ValueError("Matching complete source coverage required")
    report = {"schema": 1, "ocr": recorded["ocr"], "input_fingerprint_sha256": fingerprint,
              "cloud": False, "production_default": False, "image_persistence": False,
              "fresh_inference": False, "reading_order_recipe": "source-direction-votes-v3" if directional_votes else "source-fragment-precedence-v2",
              "crop_recipe": recorded["crop_recipe"], "pages": [], "complete": False,
              "recorded_inference_aggregate": deepcopy(recorded.get("aggregate")),
              "limitations": ["Replay of unchanged raw member OCR, not new inference or detection.",
                  "Member ms and recorded_probe_ocr_ms are inherited, not replay latency.",
                  "Unreviewed Japanese development labels; no translation/artwork quality claim."]}
    for page, _, bubbles in pages:
        original, _labels = before[page["page_id"]]
        regions = []
        for region in original["regions"]:
            started = time.perf_counter()
            result = reorder_recorded_members(region,directional_votes=directional_votes)
            if "probe_ocr_ms" in result:
                result["recorded_probe_ocr_ms"] = result.pop("probe_ocr_ms")
            result["ordering_replay_ms"] = (time.perf_counter()-started)*1000
            regions.append(result)
        aligned, unmatched = assign_to_labels(bubbles, regions)
        report["pages"].append({"page": page["page_id"], "regions": regions,
                                "aligned": aligned, "unmatched_prediction_ids": unmatched})
    rows = [r for p in report["pages"] for r in p["aligned"]]
    report["aggregate"] = {"annotations": len(rows), "exact": sum(r["edits"] == 0 for r in rows),
                           "edits": sum(r["edits"] for r in rows),
                           "characters": sum(r["characters"] for r in rows),
                           "crops": sum(len(p["regions"]) for p in report["pages"])}
    report["comparison"] = compare(recorded, report)
    report["complete"] = True
    return report


def run(args):
    output = private_json_path(args.output, new=True)
    reorder_from = getattr(args, "reorder_from", None)
    if reorder_from and (args.baseline or getattr(args, "line_members", False)):
        raise ValueError("Ordering replay cannot be combined with new inference")
    baseline = json.loads(private_json_path(args.baseline).read_text(encoding="utf-8")) if args.baseline else None
    line_members = getattr(args, "line_members", False)
    if line_members and not baseline:
        raise ValueError("Line recognition requires retained detector proposals, not gold boxes")
    with DirectoryDataset(args.folder) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    if reorder_from:
        data = private_json_path(reorder_from).read_bytes()
        report = replay_recorded_report(json.loads(data), pages, fingerprint)
        report.update(counts=counts, audit=issues, source_report_sha256=hashlib.sha256(data).hexdigest())
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("x", encoding="utf-8") as destination:
            json.dump(report, destination, ensure_ascii=False, indent=2, allow_nan=False)
        print(json.dumps({"aggregate": report["aggregate"], "comparison": report["comparison"]["aggregate"]}), flush=True)
        return
    if baseline and (baseline.get("input_fingerprint_sha256") != fingerprint or
                     baseline.get("cloud") is not False or
                     {p["page"] for p in baseline["pages"]} != {p[0]["page_id"] for p in pages}):
        raise ValueError("Matching private source coverage required")
    from benchmark_hayai_nova import offline_guard
    from benchmark_paddle_rec import process_memory
    engine = BaberuProbe(threads=getattr(args, "threads", 4))
    started = time.perf_counter()
    with offline_guard():
        engine.load()
    report = {"schema": 1, "ocr": engine.name, "input_fingerprint_sha256": fingerprint,
              "counts": counts, "audit": issues, "production_default": False, "cloud": False,
              "image_persistence": False, "fresh_inference": True, "pages": [],
              "complete": False, "threads": engine.threads,
              "crop_recipe": "source-members-axis-halo2-rtl-v1" if line_members else "unchanged-whole-region",
              "load_ms": (time.perf_counter()-started)*1000,
              "limitations": ["Unreviewed Japanese labels; no Vietnamese/clean-background gold.",
                              "Recognizer-only comparison, not fresh detection, translation or browser latency."]}
    for page, image, bubbles in pages:
        ident = page["page_id"]
        if baseline:
            original = next(p for p in baseline["pages"] if p["page"] == ident)
            regions = deepcopy(original["regions"])
        else:
            regions = [{"id": b["bubble_id"], "bbox": [b["bbox"][key] for key in ("x", "y", "w", "h")],
                        "order": n} for n, b in enumerate(bubbles)]
        for region in regions:
            if line_members:
                started = time.perf_counter()
                with offline_guard():
                    result = recognize_source_members(engine, image, region)
                region.update(result, probe_ocr_ms=(time.perf_counter()-started)*1000)
                region.pop("vi", None)
                continue
            box = region.get("ocrCropBox", region["bbox"])
            x, y, w, h = box
            if min(x, y) < 0 or min(w, h) < 1 or x+w > image.width or y+h > image.height:
                raise ValueError("Invalid source crop")
            started = time.perf_counter()
            with offline_guard():
                region["ja"] = engine.recognize(image.crop((x, y, x+w, y+h)))
            region["probe_ocr_ms"] = (time.perf_counter()-started)*1000
            region["probe_decode"] = dict(engine.last_decode)
            region.pop("vi", None)
        aligned, unmatched = assign_to_labels(bubbles, regions) if baseline else (
            [{"id": b["bubble_id"], "reference": normalized(b["ja_ocr_truth"]),
              "prediction": normalized(r["ja"]), "edits": distance(normalized(b["ja_ocr_truth"]), normalized(r["ja"])),
              "characters": len(normalized(b["ja_ocr_truth"])), "region_ids": [r["id"]]}
             for b, r in zip(bubbles, regions)], [])
        report["pages"].append({"page": ident, "regions": regions, "aligned": aligned,
                                "unmatched_prediction_ids": unmatched})
        report["process_memory"] = process_memory()
        report["process_memory"]["scope"] = "recognizer/imports/RAM crops; no detector loaded (proposals replayed when supplied)"
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".tmp")
        temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        temporary.replace(output)
        print(json.dumps({"page": ident, "crops": len(regions), "exact": sum(r["edits"] == 0 for r in aligned),
                          "edits": sum(r["edits"] for r in aligned)}), flush=True)
    rows = [r for page in report["pages"] for r in page["aligned"]]
    times = sorted(r["probe_ocr_ms"] for p in report["pages"] for r in p["regions"])
    report["aggregate"] = {"annotations": len(rows), "exact": sum(r["edits"] == 0 for r in rows),
                           "edits": sum(r["edits"] for r in rows), "characters": sum(r["characters"] for r in rows),
                           "crops": len(times), "p50_crop_ms": times[len(times)//2],
                           "p95_crop_ms": times[min(len(times)-1, int(len(times)*.95))]}
    if baseline:
        report["comparison"] = compare(baseline, report)
    report["complete"] = True
    with output.open("w", encoding="utf-8") as destination:
        json.dump(report, destination, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(report["aggregate"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--baseline")
    parser.add_argument("--reorder-from", help="Replay retained raw member readings without model inference")
    parser.add_argument("--line-members", action="store_true")
    parser.add_argument("--threads", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--output", required=True)
    run(parser.parse_args())
