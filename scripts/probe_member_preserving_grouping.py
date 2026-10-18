"""Targeted comparator: OCR source detector members, then join at group level.

This avoids the aspect-ratio change introduced by a union crop. It is a
private, local-only experiment: source pixels stay in RAM, no cloud request is
made, and no runtime/default/cache version is changed.
"""
import argparse
import hashlib
import json
import math
from copy import deepcopy
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from benchmark import DirectoryDataset, audit, dataset_fingerprint
from benchmark_pages import assign_to_labels
from manga_live.ocr import MangaEngine, rect
from manga_live.text_scope import SCOPE_VERSION

VERSION = "member-preserving-v2"
CANDIDATE_VERSIONS = {
    "balloon-mask-v18-open-overlap-candidate",
    "balloon-mask-v19-open-overlap20-candidate",
}


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def member_key(member):
    if not isinstance(member, dict):
        raise ValueError("Missing source member evidence")
    polygon = member.get("polygon")
    score = member.get("score")
    if (not isinstance(polygon, list) or not 4 <= len(polygon) <= 64
            or any(not isinstance(point, list) or len(point) != 2
                   or any(not numeric(value) or value < 0 for value in point) for point in polygon)
            or not numeric(score) or not 0 <= score <= 1):
        raise ValueError("Invalid source member polygon/score")
    return tuple(tuple(point) for point in polygon)


def member_box(member, image):
    member_key(member)
    left, top, width, height = rect(member["polygon"])
    x, y = math.floor(left), math.floor(top)
    right, bottom = math.ceil(left + width), math.ceil(top + height)
    w, h = right - x, bottom - y
    if not w or not h or right > image.width or bottom > image.height:
        raise ValueError("Source member crop is outside the selected image")
    return [x, y, w, h]


def reading_key(boxes):
    vertical = all(height >= width * 1.25 for _, _, width, height in boxes)
    if vertical:
        # Japanese vertical columns are read right-to-left, then top-down.
        return lambda item: (-item[1][0], item[1][1])
    return lambda item: (item[1][1], -item[1][0])


def load_candidate(path):
    path = Path(path).resolve()
    if ROOT / "artifacts" not in path.parents or path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError("Candidate evidence must be a bounded private artifact")
    with path.open("rb") as source:
        data = source.read(16 * 1024 * 1024 + 1)
    if len(data) > 16 * 1024 * 1024:
        raise ValueError("Candidate evidence changed size or exceeds its bound")
    report = json.loads(data)
    if (not isinstance(report, dict) or type(report.get("schema")) is not int or report["schema"] != 1
            or report.get("production_default") is not False or report.get("fresh_inference") is not True
            or report.get("cloud") is not False or report.get("device") != "CPU"
            or report.get("layout_version") not in CANDIDATE_VERSIONS
            or report.get("scope_version") != SCOPE_VERSION or report.get("ocr") != MangaEngine.name
            or report.get("detector") != "PP-OCRv5_mobile_det"):
        raise ValueError("Expected a compatible non-default fresh local grouping comparator")
    return report


def validate_pages(candidate, page_sources):
    pages = candidate.get("pages")
    if not isinstance(pages, list) or not 1 <= len(pages) <= 1000:
        raise ValueError("Candidate must contain a bounded nonempty page list")
    seen_pages = set()
    for page in pages:
        page_id = page.get("page") if isinstance(page, dict) else None
        if not isinstance(page_id, str) or page_id not in page_sources or page_id in seen_pages:
            raise ValueError("Candidate contains a duplicated, ineligible or missing page")
        seen_pages.add(page_id)
        _, image, _ = page_sources[page_id]
        evidence = page.get("detector_evidence")
        raw = evidence.get("raw_detections") if isinstance(evidence, dict) else None
        if not isinstance(raw, list) or len(raw) > 512:
            raise ValueError("Missing bounded raw detector evidence")
        raw_by_key = {}
        for index, member in enumerate(raw):
            key = member_key(member)
            member_box(member, image)
            if key in raw_by_key:
                raise ValueError("Duplicated raw detector polygon")
            raw_by_key[key] = (index, member)
        regions = page.get("regions")
        if not isinstance(regions, list) or len(regions) > 64:
            raise ValueError("Invalid candidate region count")
        used_members, ids = set(), set()
        for region in regions:
            if not isinstance(region, dict):
                raise ValueError("Invalid candidate region")
            region_id, box = region.get("id"), region.get("bbox")
            if (not isinstance(region_id, str) or not 1 <= len(region_id) <= 128 or region_id in ids
                    or not isinstance(region.get("ja"), str) or len(region["ja"]) > 3000
                    or not isinstance(box, list) or len(box) != 4 or any(not numeric(v) for v in box)
                    or min(box[:2]) < 0 or min(box[2:]) <= 0
                    or box[0] + box[2] > image.width or box[1] + box[3] > image.height):
                raise ValueError("Invalid candidate identity, text or crop")
            if (region.get("overlay") not in ("white", "label")
                    or type(region.get("review")) is not bool
                    or not isinstance(region.get("reviewReasons", []), list)
                    or any(not isinstance(reason, str) for reason in region.get("reviewReasons", []))
                    or not isinstance(region.get("scope"), dict)
                    or region["scope"].get("action") not in ("translate", "defer")
                    or type(region["scope"].get("memory")) is not bool
                    or not numeric(region.get("order", 0))):
                raise ValueError("Invalid source review/scope/order metadata")
            ids.add(region_id)
            if any(key in region for key in ("unionJa", "memberJa", "memberPredictions")):
                raise ValueError("Candidate already contains member OCR; fresh source evidence required")
            members = region.get("sourceMembers")
            if not isinstance(members, list) or not 1 <= len(members) <= 64:
                raise ValueError("Missing bounded source member evidence")
            for member in members:
                key = member_key(member)
                original = raw_by_key.get(key)
                if original is None or member != original[1] or key in used_members:
                    raise ValueError("Member is not unique exact raw detector evidence")
                if any(not (box[0] <= x <= box[0] + box[2] and box[1] <= y <= box[1] + box[3])
                       for x, y in member["polygon"]):
                    raise ValueError("Union crop cuts a source member")
                used_members.add(key)
            if "layout_cluster" in region.get("reviewReasons", []):
                if (len(members) < 2 or region.get("review") is not True or region.get("overlay") != "label"
                        or "balloon" in region or region.get("scope", {}).get("memory") is not False):
                    raise ValueError("Unaccepted cluster must retain visual and memory distrust")
    if seen_pages != set(page_sources):
        raise ValueError("Candidate does not cover every eligible source page")


def aggregate(pages, field="aligned"):
    aligned = [row for page in pages for row in page[field]]
    return {
        "annotation_count": len(aligned),
        "annotations_with_assigned_prediction": sum(bool(row["region_ids"]) for row in aligned),
        "diagnostic_aligned_cer": sum(row["edits"] for row in aligned) / max(1, sum(row["characters"] for row in aligned)),
        "diagnostic_aligned_exact_match": sum(row["reference"] == row["prediction"] for row in aligned) / max(1, len(aligned)),
        "exact": sum(row["reference"] == row["prediction"] for row in aligned),
        "regions": sum(len(page["regions"]) for page in pages),
    }


def run(args):
    if type(args.threads) is not int or not 1 <= args.threads <= 4 or type(args.batch) is not int or not 1 <= args.batch <= 2:
        raise ValueError("Member comparator is bounded to 1-4 CPU threads and batch 1-2")
    output = Path(args.output).resolve()
    if ROOT / "artifacts" not in output.parents or output.suffix != ".json" or output.exists():
        raise ValueError("Private output must be a new JSON file in artifacts; never overwrite evidence")
    candidate = load_candidate(args.candidate)
    with DirectoryDataset(args.folder) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    if candidate.get("input_fingerprint_sha256") != fingerprint:
        raise ValueError("Candidate and selected dataset differ")
    page_sources = {page["page_id"]: (page, image, bubbles) for page, image, bubbles in pages}
    validate_pages(candidate, page_sources)
    engine = MangaEngine(ROOT / "models" / "ocr", args.threads)
    result = {
        "schema": 2,
        "comparator_version": VERSION,
        "candidate_content_sha256": hashlib.sha256(json.dumps(candidate, sort_keys=True, ensure_ascii=False,
                                                               allow_nan=False).encode("utf-8")).hexdigest(),
        "input_fingerprint_sha256": fingerprint,
        "counts": counts,
        "audit": issues,
        "candidate_layout_version": candidate.get("layout_version"),
        "production_default": False,
        "cloud": False,
        "image_persistence": False,
        "member_ocr": True,
        "fresh_inference": False,
        "fresh_member_inference": True,
        "limitations": [
            "Only layout_cluster unions are re-OCRed; other candidate text is reused as recorded evidence.",
            "Joining member strings is an OCR diagnostic, not semantic ownership or translation ground truth.",
            "Member order is a geometric heuristic; equal aggregate metrics do not establish string equality.",
            "No clean-background or Vietnamese reference gold exists for this dataset.",
        ],
        "pages": [],
    }
    for candidate_page in candidate.get("pages", []):
        page_id = candidate_page.get("page")
        if page_id not in page_sources:
            raise ValueError("Candidate contains an ineligible or missing page")
        _, image, bubbles = page_sources[page_id]
        regions = deepcopy(candidate_page.get("regions", []))
        union_aligned, _ = assign_to_labels(bubbles, regions)
        raw_indices = {member_key(member): index for index, member in
                       enumerate(candidate_page["detector_evidence"]["raw_detections"])}
        jobs = []
        for index, region in enumerate(regions):
            if "layout_cluster" not in region.get("reviewReasons", []):
                continue
            members = region.get("sourceMembers")
            if region.get("scope", {}).get("action") == "defer":
                # Exclusions stay excluded, even in a diagnostic comparator.
                continue
            entries = [(member_index, member_box(member, image)) for member_index, member in enumerate(members)]
            entries.sort(key=reading_key([box for _, box in entries]))
            for member_index, box in entries:
                jobs.append((index, member_index, box))
        for start in range(0, len(jobs), args.batch):
            chunk = jobs[start:start + args.batch]
            crops = [image.crop((box[0], box[1], box[0] + box[2], box[1] + box[3])) for _, _, box in chunk]
            values = engine.recognize_many(crops)
            if (not isinstance(values, (list, tuple)) or len(values) != len(chunk)
                    or any(not isinstance(value, str) or len(value) > 3000 for value in values)):
                raise ValueError("Member OCR batch returned an incomplete result")
            for (index, member_index, box), value in zip(chunk, values):
                member = regions[index]["sourceMembers"][member_index]
                regions[index].setdefault("memberPredictions", []).append({
                    "sourceMemberIndex": member_index,
                    "rawDetectorIndex": raw_indices[member_key(member)],
                    "polygon": deepcopy(member["polygon"]),
                    "bbox": box,
                    "score": member.get("score"),
                    "ja": value,
                })
        for region in regions:
            predictions = region.get("memberPredictions")
            if predictions:
                region["unionJa"] = region["ja"]
                region["memberJa"] = "".join(item["ja"] for item in predictions)
                region["ja"] = region["memberJa"]
        aligned, unmatched = assign_to_labels(bubbles, regions)
        result["pages"].append({
            "page": page_id,
            "member_groups": [
                {"id": region["id"], "union": region["unionJa"], "members": region["memberJa"],
                 "equal": region["unionJa"] == region["memberJa"],
                 "memberPredictions": deepcopy(region["memberPredictions"])}
                for region in regions if "memberJa" in region
            ],
            "regions": regions,
            "aligned": aligned,
            "union_aligned": union_aligned,
            "detector_evidence": deepcopy(candidate_page["detector_evidence"]),
            "unmatched_prediction_ids": unmatched,
        })
        print(json.dumps({"page": page_id, "member_groups": sum("memberJa" in r for r in regions)}), flush=True)
    result["aggregate"] = aggregate(result["pages"])
    result["union_aggregate"] = aggregate(result["pages"], "union_aligned")
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as destination:
        json.dump(result, destination, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps(result["aggregate"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--candidate", default=str(ROOT / "artifacts" / "private-pages-open-overlap20-fresh-20261014.json"))
    parser.add_argument("--output", default=str(ROOT / "artifacts" / "private-member-preserving-20261014.json"))
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--batch", type=int, default=2)
    run(parser.parse_args())
