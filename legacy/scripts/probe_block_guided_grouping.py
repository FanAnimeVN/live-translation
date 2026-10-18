"""Unaccepted source-preserving grouping ablation, no runtime default change.

Use recorded PP regions plus separately measured comic text-block geometry.
Only join overlapping unresolved source crops when exactly one learned block
supports them. No source/gold text determines groups; no new erasure rights.
Reuse unchanged actual OCR crops; infer only genuinely new union crops.
"""
import argparse
from copy import deepcopy
import json
import math
import statistics
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/"companion"), str(ROOT/"scripts")]
from benchmark import DirectoryDataset, audit, dataset_fingerprint
from benchmark_pages import intersection, assign_to_labels, hashlib_image
from manga_live.ocr import MangaEngine, recognize_regions, polygon, LAYOUT_VERSION, aligned_open_starts, nearby_text_boxes
from manga_live.text_scope import make_plan, route_regions, SCOPE_VERSION

VERSION = "pp-overlapping-crops-comic-block-guide-v2-parallel-band-candidate"
SOURCE_PRESERVING_VERSION = "pp-comic-block-source-ocr-assembly-v1-candidate"


def reader_owned(region):
    return (region.get("scope", {}).get("reason") == "reader"
            or region.get("scope", {}).get("action") == "defer"
            or any(region.get(field, "unknown") != "unknown" for field in ("speaker", "listener")))


def parallel_band(boxes):
    """All members must share orientation, leading band and transverse scale.

    A learned paragraph rectangle and connected detector padding cannot supply
    these facts. This is still a reviewable grouping hypothesis, never ownership,
    speaker or glyph-mask evidence. No OCR/translation/reference enters it.
    """
    if len(boxes) < 2:
        return False
    vertical = all(h >= w*1.25 for _, _, w, h in boxes)
    horizontal = all(w >= h*1.25 for _, _, w, h in boxes)
    if not vertical and not horizontal:
        return False
    if any(not aligned_open_starts(a, b) for i, a in enumerate(boxes) for b in boxes[i+1:]):
        return False
    axis = 0 if vertical else 1
    scales = [b[axis+2] for b in boxes]
    if max(scales) > min(scales)*1.75:
        return False
    # A repeated near-identical crop must not become a bridge into another
    # column. Check pitch only with >=3 members, without demanding equal length.
    centers = sorted(b[axis]+b[axis+2]/2 for b in boxes)
    pitch = [b-a for a, b in zip(centers, centers[1:])]
    return len(pitch) < 2 or (min(pitch) >= min(scales)*.25 and max(pitch) <= statistics.median(pitch)*1.75)


def guide_regions(source, blocks, size):
    """Unique block + overlapping compatible parallel crops, never text/gold."""
    width, height = size
    eligible = {i for i, r in enumerate(source) if r.get("overlay") == "label" and
        not r.get("balloon") and "layout_fragment" not in r.get("reviewReasons", []) and
        not reader_owned(r)}
    owners = {}
    for i in eligible:
        b = source[i]["bbox"]
        candidates = [j for j, block in enumerate(blocks)
            if intersection(b, block["bbox"]) >= b[2]*b[3]*.95]
        # Nested/duplicated model proposals cannot decide a merge implicitly.
        if len(candidates) == 1: owners[i] = candidates[0]
    groups = []
    pending = set(owners)
    while pending:
        first = min(pending); pending.remove(first); group = {first}; todo = [first]
        while todo:
            current = todo.pop()
            neighbors = [i for i in sorted(pending) if owners[i] == owners[first] and
                intersection(source[current]["bbox"], source[i]["bbox"]) > 0 and
                nearby_text_boxes(source[current]["bbox"], source[i]["bbox"], open_surface=True)]
            for i in neighbors:
                if not parallel_band([source[j]["bbox"] for j in sorted(group | {i})]):
                    continue
                pending.remove(i); group.add(i); todo.append(i)
        if len(group) > 1: groups.append(sorted(group))
    merged = {}; absorbed = set(); evidence = []
    for group in groups:
        boxes = [source[i]["bbox"] for i in group]
        x, y = min(b[0] for b in boxes), min(b[1] for b in boxes)
        right, bottom = max(b[0]+b[2] for b in boxes), max(b[1]+b[3] for b in boxes)
        box = [x, y, right-x, bottom-y]
        if min(box[2:]) < 4 or box[2]*box[3] > width*height*.16: continue
        first = group[0]; originals = [source[i]["id"] for i in group]
        reasons = list(dict.fromkeys(["layout_cluster", *[reason for i in group for reason in source[i].get("reviewReasons", [])]]))
        merged[first] = {"id": source[first]["id"], "order": source[first]["order"],
            "bbox": box, "polygon": polygon(box), "overlay": "label", "review": True,
            "reviewReasons": reasons, "speaker": "unknown", "listener": "unknown", "type": "dialogue"}
        absorbed.update(group[1:])
        evidence.append({"id": source[first]["id"], "source_ids": originals, "bbox": box,
            "guide_id": blocks[owners[first]]["id"], "erasure_permitted": False,
            "source_visual_review": any(source[i].get("scope", {}).get("reason") == "visual_review" for i in group)})
    result = [merged.get(i, deepcopy(r)) for i, r in enumerate(source) if i not in absorbed]
    return result, evidence


def preserve_source_ocr(proposed, merges, source):
    """Change presentation/translation blocks, never source OCR evidence.

    Only previously proposed geometry can be assembled. Every source record
    must occur exactly once, with its original text/box/flags/anchor preserved.
    These diagnostic blocks remain untrusted for memory and artwork erasure;
    this function is not a migration of persisted reader bindings.
    """
    if not all(isinstance(rows, list) and len(rows) <= 64 for rows in (source, proposed, merges)):
        raise ValueError("Bounded source/presentation lists required")
    by_id = {r["id"]: r for r in source}
    merge_by_id = {r["id"]: r for r in merges}
    if len(by_id) != len(source) or len(merge_by_id) != len(merges):
        raise ValueError("Ambiguous source or merge identity")
    if len({r["id"] for r in proposed}) != len(proposed) or not set(merge_by_id) <= {r["id"] for r in proposed}:
        raise ValueError("Missing or duplicated proposed assembly")
    consumed = set()
    result = []
    for region in proposed:
        merge = merge_by_id.get(region["id"])
        if merge is None:
            original = by_id.get(region["id"])
            if original is None or region != original or region["id"] in consumed:
                raise ValueError("Unmerged source evidence was changed or repeated")
            consumed.add(region["id"])
            result.append(deepcopy(region))
            continue
        ids = merge.get("source_ids")
        if (not isinstance(ids, list) or len(ids) < 2 or len(set(ids)) != len(ids)
                or any(member_id not in by_id or member_id in consumed for member_id in ids)
                or merge.get("erasure_permitted") is not False or merge.get("bbox") != region.get("bbox")
                or region.get("overlay") != "label" or region.get("review") is not True
                or "balloon" in region or "layout_cluster" not in region.get("reviewReasons", [])):
            raise ValueError("Assembly lost its source partition or visual distrust")
        members = [by_id[member_id] for member_id in ids]
        if any(reader_owned(member) for member in members):
            raise ValueError("Assembly cannot replace reader choices or confirmed identities")
        if any(not isinstance(member.get("ja"), str) or not member["ja"] or len(member["ja"]) > 3000 for member in members):
            raise ValueError("Assembly requires complete typed source OCR")
        # The geometry guide uses input reading order. Refuse stale evidence
        # rather than reordering records based on their text or reference gold.
        positions = [next(index for index, row in enumerate(source) if row["id"] == member_id) for member_id in ids]
        if positions != sorted(positions) or region["id"] != ids[0]:
            raise ValueError("Assembly does not retain source reading order")
        reasons = list(dict.fromkeys(["layout_cluster", *[reason for member in members
                                                          for reason in member.get("reviewReasons", [])]]))
        if region.get("reviewReasons") != reasons:
            raise ValueError("Assembly cannot remove inherited source review")
        joined = "".join(member["ja"] for member in members)
        if len(joined) > 3000:
            raise ValueError("Assembly exceeds the source text contract")
        # Invalidate any recorded translation/expression for this new utterance.
        # Never concatenate old Vietnamese fragments as a fresh translation.
        assembled = {k: deepcopy(value) for k, value in region.items()
                     if k not in ("vi", "ambiguous", "expression", "scope")}
        assembled.update(ja=joined, sourceRegions=deepcopy(members),
                         sourceOcrPreserved=True, speaker="unknown", listener="unknown")
        scores = [member.get("score") for member in members]
        if all(type(score) in (int, float) and math.isfinite(score) and 0 <= score <= 1 for score in scores):
            assembled["score"] = min(scores)
        else:
            # Absence of measured scores is not confidence=1.
            assembled.pop("score", None)
        consumed.update(ids)
        result.append(assembled)
    if consumed != set(by_id):
        raise ValueError("Assembly lost a source region")
    return result


def route_guided(image, regions, merges):
    result = route_regions(regions, make_plan(image, regions, hashlib_image(image)), {})
    union = {r["id"]: r for r in merges}
    for r in result:
        if r["id"] in union:
            # OCR of a union can remove the old tiny-ink heuristic without
            # establishing that all of its evidence is reliable. Never elevate
            # source distrust or unaccepted paragraph grouping into plot memory.
            r["scope"]["memory"] = False
            if union[r["id"]]["source_visual_review"]:
                r["scope"]["reason"] = "visual_review"
    return result


def read_private(path):
    path = Path(path).resolve()
    if path.parent != ROOT/"artifacts" or path.stat().st_size > 16*1024*1024:
        raise ValueError("Bounded evidence directly in gitignored artifacts required")
    return json.loads(path.read_text(encoding="utf-8"))


def select_replayed(changed, recorded):
    by_box = {tuple(r["bbox"]): r for r in recorded}
    if len(by_box) != len(recorded): raise ValueError("Ambiguous recorded crop")
    result = {}
    for region in changed:
        old = by_box.get(tuple(region["bbox"]))
        if old is None or old.get("overlay") != region["overlay"] or not isinstance(old.get("ja"), str):
            raise ValueError("No identical measured union crop; fresh OCR required")
        result[region["id"]] = {**deepcopy(old), **deepcopy(region), "ja": old["ja"]}
    return result


def run(args):
    preserve = bool(getattr(args, "preserve_source_ocr", False))
    if preserve and (args.ocr_replay or args.plan_only):
        raise ValueError("Source assembly cannot be combined with union OCR replay or plan-only")
    pp, block_report = read_private(args.pp_reference), read_private(args.block_reference)
    replay = read_private(args.ocr_replay) if args.ocr_replay else None
    output = Path(args.output).resolve()
    if (output.parent != ROOT/"artifacts" or output.exists()
            or output in (Path(args.pp_reference).resolve(), Path(args.block_reference).resolve())):
        raise ValueError("Separate private output required")
    with DirectoryDataset(args.folder) as source:
        counts, issues, pages = audit(source); fingerprint = dataset_fingerprint(source)
    if any(r.get("input_fingerprint_sha256") != fingerprint for r in (pp, block_report)):
        raise ValueError("Guide inputs do not share the exact dataset")
    eligible_pages = {page["page_id"] for page, _, _ in pages}
    for report in (pp, block_report):
        recorded_pages = report.get("pages")
        if (not isinstance(recorded_pages, list)
                or any(not isinstance(row, dict) or not isinstance(row.get("page"), str) for row in recorded_pages)
                or len({row["page"] for row in recorded_pages}) != len(recorded_pages)
                or {row["page"] for row in recorded_pages} != eligible_pages):
            raise ValueError("Guide evidence must cover every eligible page exactly once")
    if replay and (replay.get("input_fingerprint_sha256") != fingerprint or replay.get("layout_version") != VERSION
                   or replay.get("ocr") != pp.get("ocr")):
        raise ValueError("Recorded union inference has different provenance")
    if pp.get("layout_version") != LAYOUT_VERSION or block_report.get("detector") != "ogkalu-detector-v4-s-int8-private-blocks":
        raise ValueError("Unexpected comparator/layout provenance")
    if any(r.get("scope", {}).get("reason") == "reader" for report in (pp, block_report)
            for page in report["pages"] for r in page["regions"]):
        raise ValueError("A private benchmark cannot regroup or replace reader overrides")
    result = {"schema": 1, "layout_version": SOURCE_PRESERVING_VERSION if preserve else VERSION, "production_default": False,
        "cloud": False, "image_persistence": False, "input_fingerprint_sha256": fingerprint,
        "counts": counts, "audit": issues, "scope_version": SCOPE_VERSION, "pages": [],
        "ocr": pp["ocr"], "fresh_ocr_new_crops_only": not args.plan_only and replay is None and not preserve,
        "source_ocr_preserved": preserve,
        "guide_detector": block_report["detector"],
        "guide_model": deepcopy(block_report.get("experimental_detector", {})),
        "replayed_new_crop_predictions": replay is not None, "scope_guard_revision": 2,
        "limitations": ["Two recorded actual detector inputs, not a new detector or timing benchmark.",
            ("Every original source OCR record retained exactly once; assembled text is not fresh OCR."
             if preserve else "Unchanged predictions reused only by identical source crop; merged crops get fresh OCR."),
            "Learned box/geometry is not semantic ownership or erasure authority; all unions retain review.",
            "Original labels are unaudited; no Việt or clean-background gold. Not a runtime default."]}
    engine = MangaEngine(ROOT/"models/ocr", 4) if replay is None and not args.plan_only and not preserve else None
    for page, image, bubbles in pages:
        page_id = page["page_id"]
        a = next(r for r in pp["pages"] if r["page"] == page_id)
        b = next(r for r in block_report["pages"] if r["page"] == page_id)
        proposed, merges = guide_regions(a["regions"], b["regions"], image.size)
        changed = [r for r in proposed if "ja" not in r]
        row = {"page": page_id, "merges": merges, "new_crops": len(changed), "detected": len(proposed),
               # Recorded source detector evidence, not fresh inference or a
               # semantic importance label. Keep raw classes/scores unchanged.
               "guide_detector_evidence": deepcopy(b.get("detector_evidence", {}))}
        if preserve:
            # Retain the complete original plane, including unmerged records
            # and anchors. New paragraph geometry is not a new source crop.
            row["source_regions"] = deepcopy(a["regions"])
        if not args.plan_only:
            start = time.perf_counter()
            if preserve:
                regions = preserve_source_ocr(proposed, merges, a["regions"])
                row.update(new_crops=0, assembly_count=len(merges), source_region_count=len(a["regions"]))
            else:
                fresh = (select_replayed(changed, next(p for p in replay["pages"] if p["page"] == page_id)["regions"])
                    if replay else {r["id"]: r for r in recognize_regions(image, changed, engine, threading.Event())})
                if set(fresh) != {r["id"] for r in changed}: raise ValueError("Incomplete new crop inference")
                regions = [fresh.get(r["id"], r) for r in proposed]
            regions = route_guided(image, regions, merges)
            aligned, unmatched = assign_to_labels(bubbles, regions)
            row.update(regions=regions, aligned=aligned, unmatched_prediction_ids=unmatched,
                new_crop_ocr_ms=None if replay or preserve else (time.perf_counter()-start)*1000)
        result["pages"].append(row)
        print(json.dumps({k:row[k] for k in ("page", "new_crops", "detected", "merges")}), flush=True)
    if not args.plan_only:
        aligned = [r for p in result["pages"] for r in p["aligned"]]
        result["aggregate"] = {"annotation_count": len(aligned),
            "annotations_with_assigned_prediction": sum(bool(r["region_ids"]) for r in aligned),
            "diagnostic_aligned_cer": sum(r["edits"] for r in aligned)/sum(r["characters"] for r in aligned),
            "exact": sum(r["reference"] == r["prediction"] for r in aligned),
            "regions": sum(len(p["regions"]) for p in result["pages"]),
            "new_crops": sum(p["new_crops"] for p in result["pages"])}
        with output.open("x", encoding="utf-8") as destination:
            json.dump(result, destination, ensure_ascii=False, indent=2, allow_nan=False)
        print(json.dumps(result["aggregate"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--folder", required=True)
    parser.add_argument("--pp-reference", required=True); parser.add_argument("--block-reference", required=True)
    parser.add_argument("--ocr-replay", help="Reuse measured identical union crops; not fresh inference/timing")
    parser.add_argument("--preserve-source-ocr", action="store_true",
                        help="Assemble recorded source text for paragraph diagnosis, no OCR/LLM or runtime changes")
    parser.add_argument("--output", required=True); parser.add_argument("--plan-only", action="store_true")
    run(parser.parse_args())
