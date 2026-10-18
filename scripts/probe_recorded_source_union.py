"""Experimental source-level detector union, not a runtime/default engine.

Recorded polygons are regrouped from original pixels, then genuinely new crops
are recognized. Old transcripts/gold never choose a member, crop or grouping.
All original source records survive; no artwork or plot authority is granted.
"""
from collections import defaultdict, deque
from copy import deepcopy
import argparse
import hashlib
import json
import math
from pathlib import Path
import sys
import subprocess
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from manga_live.ocr import group_regions
from benchmark import DirectoryDataset, audit, dataset_fingerprint
from compare_page_reports import checked_pages, compare, private_json_path

VERSION = "ctd-pp-recorded-source-union-v1"
COMPONENT_VERSION = "ctd-pp-recorded-source-support-components-v2"
ANCHORED_VERSION = "ctd-pp-recorded-source-primary-anchored-v3"


def group_recorded_sources(image, primary, secondary, *, page, support_components=False, primary_anchored=False):
    """One fixed geometry/paper recipe; source strings are retained, never used."""
    import cv2
    import numpy as np
    if (type(support_components) is not bool or type(primary_anchored) is not bool
            or support_components and primary_anchored
            or not isinstance(page, str) or not 1 <= len(page) <= 128
            or min(image.size) <= 0 or image.width*image.height > 12_000_000):
        raise ValueError("Bounded source page required")
    detections, origins, inherited = [], [], {}
    for plane, rows in (("primary", primary), ("secondary", secondary)):
        if not isinstance(rows, list) or len(rows) > 128:
            raise ValueError("Bounded source plane required")
        seen = set()
        for row in sorted(rows, key=lambda r: r.get("id", "") if isinstance(r, dict) else ""):
            ident = row.get("id") if isinstance(row, dict) else None
            if not isinstance(ident, str) or not 1 <= len(ident) <= 128 or ident in seen:
                raise ValueError("Unique source identity required")
            seen.add(ident)
            scope = row.get("scope", {})
            if not isinstance(scope, dict) or type(row.get("readerExcluded", False)) is not bool:
                raise ValueError("Explicit reader state required")
            if (row.get("readerExcluded", False) or scope.get("reason") == "reader"
                    or any(row.get(field, "unknown") != "unknown" for field in ("speaker", "listener"))):
                raise ValueError("Experiment cannot regroup reader choices/exclusions")
            box, members = row.get("bbox"), row.get("sourceMembers")
            if (not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box)
                    or min(box[:2]) < 0 or min(box[2:]) <= 0
                    or box[0]+box[2] > image.width or box[1]+box[3] > image.height
                    or not isinstance(members, list) or not 1 <= len(members) <= 512):
                raise ValueError("Original bounded source geometry/members required")
            reasons = row.get("reviewReasons", [])
            if not isinstance(reasons, list) or any(not isinstance(reason, str) for reason in reasons):
                raise ValueError("Original source review flags required")
            inherited[(plane, ident)] = reasons
            for index, member in enumerate(members):
                polygon = member.get("polygon") if isinstance(member, dict) else None
                score = member.get("score") if isinstance(member, dict) else None
                if (not isinstance(polygon, list) or len(polygon) != 4 or any(
                        not isinstance(p, list) or len(p) != 2 or any(
                            type(v) not in (int, float) or not math.isfinite(v) for v in p) for p in polygon)
                        or any(x < 0 or y < 0 or x > image.width or y > image.height for x, y in polygon)
                        or type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
                    raise ValueError("Original source polygon/score required")
                points = np.asarray(polygon, np.float32)
                if not cv2.isContourConvex(points) or cv2.contourArea(points) <= 0:
                    raise ValueError("Convex nondegenerate source polygon required")
                detections.append({"polygon": deepcopy(polygon), "score": score})
                origins.append({"plane": plane, "page": page, "id": ident, "member_index": index})
    if len(detections) > 512:
        raise ValueError("Combined source member bound exceeded")
    if primary_anchored:
        return _group_primary_anchored(image, primary, secondary, page, detections, origins, inherited)
    components = [{index} for index in range(len(detections))]
    support_edges = []
    if support_components:
        # Fixed cross-detector support rule, not transcript agreement or a
        # semantic duplicate label. One OCR view covers the whole component;
        # every exact original polygon/score remains separately recoverable.
        adjacency = {index: set() for index in range(len(detections))}
        points = [np.asarray(d["polygon"], np.float32) for d in detections]
        areas = [cv2.contourArea(p) for p in points]
        for a in range(len(detections)):
            for b in range(a+1, len(detections)):
                if origins[a]["plane"] == origins[b]["plane"]:
                    continue
                overlap, _ = cv2.intersectConvexConvex(points[a], points[b])
                union = areas[a]+areas[b]-overlap
                if union > 0 and overlap/union >= .5:
                    adjacency[a].add(b)
                    adjacency[b].add(a)
                    support_edges.append({"a": deepcopy(origins[a]), "b": deepcopy(origins[b]),
                                          "polygon_iou": overlap/union})
        components, pending = [], set(adjacency)
        while pending:
            first = min(pending)
            pending.remove(first)
            stack, component = [first], {first}
            while stack:
                index = stack.pop()
                neighbours = adjacency[index] & pending
                component.update(neighbours)
                pending.difference_update(neighbours)
                stack.extend(sorted(neighbours))
            components.append(component)
    views = []
    for component in components:
        indices = sorted(component)
        if len(indices) == 1:
            view = deepcopy(detections[indices[0]])
        else:
            polygon = [p for index in indices for p in detections[index]["polygon"]]
            left, top = min(p[0] for p in polygon), min(p[1] for p in polygon)
            right, bottom = max(p[0] for p in polygon), max(p[1] for p in polygon)
            view = {"polygon": [[left, top], [right, top], [right, bottom], [left, bottom]],
                    "score": min(detections[index]["score"] for index in indices)}
        views.append((view, indices))
    def key(member):
        return tuple(tuple(p) for p in member["polygon"]), member["score"]
    remaining = defaultdict(deque)
    for index, (detection, _) in enumerate(views):
        remaining[key(detection)].append(index)
    grouped = group_regions(image, [view for view, _ in views], include_source_members=True) if views else []
    assigned = []
    for region in grouped:
        refs, members = [], []
        for member in region["sourceMembers"]:
            indices = remaining[key(member)]
            if not indices:
                raise ValueError("Grouping repeated or changed a source member")
            view_index = indices.popleft()
            for index in views[view_index][1]:
                members.append(deepcopy(detections[index]))
                refs.append(deepcopy(origins[index]))
        region["sourceMembers"] = members
        assigned.append((region, refs))
    # The app's ordinary grouping can reject an oversized union. In this
    # recall experiment it must remain an explicit individual review proposal,
    # not silently disappear from source accounting or the OCR denominator.
    residual_count = sum(len(views[index][1]) for indices in remaining.values() for index in indices)
    for view_index in sorted(index for indices in remaining.values() for index in indices):
        member, indices = views[view_index]
        xs, ys = [p[0] for p in member["polygon"]], [p[1] for p in member["polygon"]]
        x, y = max(0, math.floor(min(xs))-3), max(0, math.floor(min(ys))-3)
        right, bottom = min(image.width, math.ceil(max(xs))+3), min(image.height, math.ceil(max(ys))+3)
        assigned.append(({"bbox": [x, y, right-x, bottom-y],
                          "sourceMembers": [deepcopy(detections[index]) for index in indices],
                          "score": member["score"], "order": len(grouped)+view_index},
                         [deepcopy(origins[index]) for index in indices]))
    if len(assigned) > 64:
        raise ValueError("Experiment exceeds 64 units; never silently truncate sources")
    result = []
    for region, refs in assigned:
        canonical_refs = sorted(refs, key=lambda r: (r["plane"], r["id"], r["member_index"]))
        identity = hashlib.sha256(json.dumps(canonical_refs, sort_keys=True).encode()).hexdigest()
        # Presentation proposal identity is never a captured-source/reader key.
        item = {k: deepcopy(region[k]) for k in ("bbox", "order", "score", "sourceMembers") if k in region}
        reasons = ["recorded_source_union", *region.get("reviewReasons", [])]
        reasons.extend(reason for ref in refs for reason in inherited[(ref["plane"], ref["id"])])
        item.update(id="source-union-"+identity, source_member_refs=refs, overlay="label", review=True,
                    reviewReasons=list(dict.fromkeys(reasons)), erasure_authority=False, memory_authority=False)
        result.append(item)
    if sum(len(region["sourceMembers"]) for region in result) != len(detections):
        raise ValueError("Incomplete source partition")
    return {"version": COMPONENT_VERSION if support_components else VERSION, "regions": result, "source_records": {
        "primary": deepcopy(primary), "secondary": deepcopy(secondary)}, "residual_member_count": residual_count,
        "support_edges": support_edges, "recognition_view_count": len(views)}


def _group_primary_anchored(image, primary, secondary, page, detections, origins, inherited):
    """Preserve primary partitions; associate support without transitive joins.

    Ambiguous/unsupported secondary members are retained as explicit review
    proposals in their original secondary row, not silently suppressed. The
    fixed .5 IoU support rule is the same as v2, not fitted to label scores.
    """
    import cv2
    import numpy as np
    primary_indices = [i for i, ref in enumerate(origins) if ref["plane"] == "primary"]
    secondary_indices = [i for i, ref in enumerate(origins) if ref["plane"] == "secondary"]
    points = [np.asarray(d["polygon"], np.float32) for d in detections]
    areas = [cv2.contourArea(p) for p in points]
    buckets = {(plane, row["id"]): [] for plane, rows in (("primary", primary), ("secondary", secondary)) for row in rows}
    rows = {(plane, row["id"]): row for plane, data in (("primary", primary), ("secondary", secondary)) for row in data}
    for index in primary_indices:
        buckets[("primary", origins[index]["id"])].append(index)
    edges, decisions = [], []
    for index in secondary_indices:
        touched, supported = set(), set()
        for anchor in primary_indices:
            overlap, _ = cv2.intersectConvexConvex(points[index], points[anchor])
            if overlap <= 0:
                continue
            ident = origins[anchor]["id"]
            touched.add(ident)
            union = areas[index]+areas[anchor]-overlap
            if union > 0 and overlap/union >= .5:
                supported.add(ident)
                edges.append({"a": deepcopy(origins[anchor]), "b": deepcopy(origins[index]), "polygon_iou": overlap/union})
        owner = next(iter(supported)) if len(supported) == 1 and touched == supported else None
        key = ("primary", owner) if owner is not None else ("secondary", origins[index]["id"])
        buckets[key].append(index)
        decisions.append({"source": deepcopy(origins[index]), "primary_id": owner,
                          "action": "attach_unique_support" if owner is not None else "retain_secondary_review",
                          "touched_primary_ids": sorted(touched), "supported_primary_ids": sorted(supported)})
    result = []
    for key, indices in sorted(buckets.items()):
        if not indices:
            continue
        row = rows[key]
        # Preserve the primary crop exactly unless associated support genuinely
        # extends beyond it. No paper flood-fill may join different anchors.
        box = row["bbox"]
        extra = [i for i in indices if origins[i]["plane"] != key[0] or origins[i]["id"] != key[1]]
        polygon = [p for i in extra for p in detections[i]["polygon"]]
        x, y, right, bottom = box[0], box[1], box[0]+box[2], box[1]+box[3]
        if polygon:
            x, y = min(x, max(0, math.floor(min(p[0] for p in polygon))-3)), min(y, max(0, math.floor(min(p[1] for p in polygon))-3))
            right = max(right, min(image.width, math.ceil(max(p[0] for p in polygon))+3))
            bottom = max(bottom, min(image.height, math.ceil(max(p[1] for p in polygon))+3))
        refs = [deepcopy(origins[i]) for i in indices]
        identity = hashlib.sha256(json.dumps(sorted(refs, key=lambda r: (r["plane"], r["id"], r["member_index"])), sort_keys=True).encode()).hexdigest()
        reasons = ["recorded_source_primary_anchored"]
        reasons.extend(reason for ref in refs for reason in inherited[(ref["plane"], ref["id"])])
        result.append({"id": "source-anchor-"+identity, "bbox": [x, y, right-x, bottom-y],
                       "order": row.get("order", 0), "score": min(detections[i]["score"] for i in indices),
                       "sourceMembers": [deepcopy(detections[i]) for i in indices], "source_member_refs": refs,
                       "reviewReasons": list(dict.fromkeys(reasons)), "review": True, "overlay": "label",
                       "erasure_authority": False, "memory_authority": False})
    if len(result) > 64:
        raise ValueError("Experiment exceeds 64 units; never silently truncate sources")
    if sum(len(r["sourceMembers"]) for r in result) != len(detections):
        raise ValueError("Incomplete source partition")
    return {"version": ANCHORED_VERSION, "regions": result, "source_records": {
        "primary": deepcopy(primary), "secondary": deepcopy(secondary)},
        "residual_member_count": sum(len(r["sourceMembers"]) for r in result if all(
            ref["plane"] == "secondary" for ref in r["source_member_refs"])),
        "support_edges": edges, "association_decisions": decisions, "recognition_view_count": len(result)}


def run(args, *, engine=None):
    from benchmark_pages import assign_to_labels
    from benchmark_hayai_nova import offline_guard
    from manga_live.ocr import MangaEngine, recognize_regions, partition_ocr_boxes
    output = private_json_path(args.output, new=True)
    parents, hashes = [], []
    for value in (args.primary, args.secondary):
        content = private_json_path(value).read_bytes()
        report = json.loads(content)
        if (report.get("cloud") is not False or report.get("fresh_inference") is not True
                or report.get("complete") is False or report.get("ocr") != MangaEngine.name):
            raise ValueError("Original complete offline same-recognizer evidence required")
        parents.append(report)
        hashes.append(hashlib.sha256(content).hexdigest())
    by_plane = [checked_pages(parent) for parent in parents]
    compare(*parents)  # Verify frozen references/coverage before paid-in-time model work; never select by its scores.
    with DirectoryDataset(args.folder) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    expected_pages = {page[0]["page_id"] for page in pages}
    if any(set(rows) != expected_pages for rows in by_plane) or any(
            parent.get("input_fingerprint_sha256") != fingerprint for parent in parents):
        raise ValueError("Matching unchanged source page coverage required")
    # Validate every page's grouping and all exclusions before any model work.
    planned = {}
    for page, image, _ in pages:
        key = page["page_id"]
        planned[key] = group_recorded_sources(image, *(plane[key][0]["regions"] for plane in by_plane), page=key,
                                             support_components=getattr(args, "support_components", False),
                                             primary_anchored=getattr(args, "primary_anchored", False))
    recognizer = engine or MangaEngine(ROOT / "models/ocr", args.threads)
    report = {"schema": 1, "version": next(iter(planned.values()))["version"],
              "ocr": recognizer.name,
              "input_fingerprint_sha256": fingerprint, "source_report_sha256": hashes,
              "cloud": False, "images_persisted": False, "production_default": False,
              "fresh_detection": False, "fresh_recognition": True, "fresh_inference": True,
              "complete": False, "counts": counts, "audit": issues, "threads": args.threads, "pages": [],
              "limitations": ["Regrouped retained detector proposals, not fresh detection or a runtime route.",
                              "Every crop receives new OCR; no transcript splicing or gold-aware source selection.",
                              "Duplicate detections remain source evidence, not repeated text contributions.",
                              "Geometry/paper grouping is not semantic ownership, glyph masks or erasure authority.",
                              "Unreviewed Japanese development labels; no held-out translation/artwork claim."]}
    output.parent.mkdir(parents=True, exist_ok=True)
    def persist():
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    # Reserve the new name without overwriting earlier evidence on a later error.
    with output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
    tick = time.perf_counter()
    with offline_guard():
        recognizer.load()
    report["load_ms"] = (time.perf_counter()-tick)*1000
    for page, image, labels in pages:
        key = page["page_id"]
        selection = planned[key]
        crop_boxes, partition_evidence = partition_ocr_boxes(image, selection["regions"])
        tick = time.perf_counter()
        with offline_guard():
            regions = recognize_regions(image, selection["regions"], recognizer, threading.Event(),
                                        crop_boxes=crop_boxes, partition_evidence=partition_evidence)
        aligned, unmatched = assign_to_labels(labels, regions)
        report["pages"].append({"page": key, "source_records": selection["source_records"],
                                "residual_member_count": selection["residual_member_count"],
                                "support_edges": selection["support_edges"],
                                "recognition_view_count": selection["recognition_view_count"],
                                **({"association_decisions": selection["association_decisions"]} if "association_decisions" in selection else {}),
                                "detector_evidence": {plane: deepcopy(by_plane[i][key][0].get("detector_evidence", {}))
                                                      for i, plane in enumerate(("primary", "secondary"))},
                                "regions": regions, "aligned": aligned, "unmatched_prediction_ids": unmatched,
                                "partitions": partition_evidence, "ocr_ms": (time.perf_counter()-tick)*1000})
        persist()
        print(json.dumps({"page": key, "regions": len(regions),
                          "members": sum(len(r["sourceMembers"]) for r in regions)}), flush=True)
    rows = [r for page in report["pages"] for r in page["aligned"]]
    report.update(complete=True, aggregate={"annotations": len(rows),
                  "exact": sum(r["edits"] == 0 for r in rows), "edits": sum(r["edits"] for r in rows),
                  "characters": sum(r["characters"] for r in rows),
                  "regions": sum(len(page["regions"]) for page in report["pages"]),
                  "members": sum(len(r["sourceMembers"]) for page in report["pages"] for r in page["regions"])})
    report["paired_primary"] = compare(parents[0], report)
    report["paired_secondary"] = compare(parents[1], report)
    persist()
    print(json.dumps({"aggregate": report["aggregate"], "paired_primary": report["paired_primary"]["aggregate"],
                      "paired_secondary": report["paired_secondary"]["aggregate"]}), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--primary", required=True)
    parser.add_argument("--secondary", required=True)
    parser.add_argument("--output", required=True)
    recipe = parser.add_mutually_exclusive_group()
    recipe.add_argument("--support-components", action="store_true",
                        help="Separate v2: one recognition view per polygon-IoU >= .5 cross-plane component")
    recipe.add_argument("--primary-anchored", action="store_true",
                        help="Separate v3: retain primary partitions; attach only uniquely supported secondary members")
    parser.add_argument("--threads", type=int, choices=range(1, 5), default=2)
    parser.add_argument("--max-seconds", type=int, choices=range(30, 1801), default=600)
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker:
        run(args)
    else:
        from benchmark_mit48 import require_memory
        require_memory()
        subprocess.run([sys.executable, str(Path(__file__).resolve()), *sys.argv[1:], "--worker"],
                       check=True, timeout=args.max_seconds)


if __name__ == "__main__":
    main()
