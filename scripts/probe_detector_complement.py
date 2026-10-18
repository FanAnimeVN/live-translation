"""Frozen, model-free complement experiment; never a production OCR route.

Retain the primary plane and propose only wholly disjoint secondary sources.
Overlaps/exclusions remain explicit recoverable evidence, never erased text.
Selection cannot see annotations; post-selection grading is separate below.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math

from benchmark import DirectoryDataset, audit, dataset_fingerprint
from benchmark_pages import assign_to_labels
from compare_page_reports import checked_pages, compare, private_json_path

VERSION = "detector-complement-disjoint-v1"
COMPONENT_VERSION = "detector-complement-intact-secondary-components-v2"


def _overlap(a, b):
    return (min(a[0]+a[2], b[0]+b[2]) > max(a[0], b[0]) and
            min(a[1]+a[3], b[1]+b[3]) > max(a[1], b[1]))


def _excluded(row):
    scope = row.get("scope", {})
    return row.get("readerExcluded", False) or scope.get("reason") == "reader" and scope.get("action") == "defer"


def _validate(rows):
    if not isinstance(rows, list) or len(rows) > 128:
        raise ValueError("Bounded retained source plane required")
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid retained source record")
        ident, box = row.get("id"), row.get("bbox")
        if not isinstance(ident, str) or not 1 <= len(ident) <= 128 or ident in seen:
            raise ValueError("Unique source identity required within each plane")
        seen.add(ident)
        if (not isinstance(box, list) or len(box) != 4 or any(
                type(v) not in (int, float) or not math.isfinite(v) for v in box)
                or min(box[:2]) < 0 or min(box[2:]) <= 0):
            raise ValueError("Valid source geometry required")
        if (not isinstance(row.get("ja"), str) or len(row["ja"]) > 4096
                or type(row.get("readerExcluded", False)) is not bool
                or not isinstance(row.get("scope", {}), dict)):
            raise ValueError("Complete retained text and explicit reader state required")
        score = row.get("score")
        if score is not None and (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1):
            raise ValueError("Invalid retained source score")


def _ordered(rows):
    """Same simple RTL row geometry as the app, not verified panel reading order."""
    groups = []
    for row in sorted(rows, key=lambda r: (r["bbox"][1], -r["bbox"][0], r["id"])):
        box = row["bbox"]
        for group in groups:
            top = min(r["bbox"][1] for r in group)
            bottom = max(r["bbox"][1]+r["bbox"][3] for r in group)
            if min(bottom, box[1]+box[3])-max(top, box[1]) > min(box[3], bottom-top)*.45:
                group.append(row)
                break
        else:
            groups.append([row])
    result = [row for group in groups for row in sorted(group, key=lambda r: (-r["bbox"][0], r["bbox"][1], r["id"]))]
    for index, row in enumerate(result):
        row["order"] = index
    return result


def select_complement(page, primary, secondary, *, preserve_secondary_components=False):
    """One fixed rule; no thresholds, scoring labels, transcript voting or merge."""
    if not isinstance(page, str) or not 1 <= len(page) <= 128:
        raise ValueError("Source page identity required")
    if type(preserve_secondary_components) is not bool:
        raise ValueError("Explicit component recipe required")
    _validate(primary)
    _validate(secondary)
    sources = {"primary": deepcopy(primary), "secondary": deepcopy(secondary)}
    exclusions = [row for rows in sources.values() for row in rows if _excluded(row)]
    selected, primary_decisions, decisions = [], [], []

    def blocked(row):
        return _excluded(row) or any(_overlap(row["bbox"], barrier["bbox"]) for barrier in exclusions)

    components = {}
    pending = {row["id"]: row for row in secondary}
    while pending:
        ident = min(pending)
        stack, component = [pending.pop(ident)], []
        while stack:
            row = stack.pop()
            component.append(row)
            neighbours = [key for key, other in pending.items() if _overlap(row["bbox"], other["bbox"])]
            stack.extend(pending.pop(key) for key in neighbours)
        component.sort(key=lambda r: r["id"])
        for row in component:
            components[row["id"]] = component

    def append(plane, row):
        ref = {"plane": plane, "page": page, "id": row["id"]}
        identity = hashlib.sha256(json.dumps(ref, sort_keys=True).encode()).hexdigest()
        # Original scope/identity remains only in the exact source plane. No
        # candidate identity becomes a captured-source key or reader binding.
        copy = {k: deepcopy(row[k]) for k in ("bbox", "ja", "score", "polygon", "sourceMembers") if k in row}
        copy.update(id="complement-"+identity, source_ref=ref, review=True, overlay="label",
                    reviewReasons=["detector_complement_candidate"], erasure_authority=False,
                    memory_authority=False)
        selected.append(copy)

    for row in primary:
        action = "reader_boundary_review" if blocked(row) else "retain_primary"
        primary_decisions.append({"id": row["id"], "action": action})
        if action == "retain_primary":
            append("primary", row)
    for row in sorted(secondary, key=lambda r: r["id"]):
        overlaps = [r["id"] for r in primary if _overlap(row["bbox"], r["bbox"])]
        peers = [r["id"] for r in secondary if r["id"] != row["id"] and _overlap(row["bbox"], r["bbox"])]
        action = ("reader_boundary_review" if blocked(row) else "overlap_review" if overlaps else
                  "secondary_overlap_review" if peers else "add_disjoint_secondary")
        component = components[row["id"]]
        component_overlaps = [r["id"] for r in primary if any(_overlap(r["bbox"], m["bbox"]) for m in component)]
        if preserve_secondary_components:
            # Preserve a whole existing source component or none of it; never
            # mix a disjoint tail with primary text touching another member.
            action = ("reader_boundary_review" if any(blocked(m) for m in component) else
                      "component_overlap_review" if component_overlaps else "add_disjoint_secondary")
        decisions.append({"id": row["id"], "action": action, "overlap_primary_ids": overlaps,
                          "overlap_secondary_ids": peers, "component_secondary_ids": [m["id"] for m in component],
                          "component_overlap_primary_ids": component_overlaps})
        if action == "add_disjoint_secondary":
            append("secondary", row)
    return {"source_records": sources, "regions": _ordered(selected), "decisions": decisions,
            "primary_decisions": primary_decisions}


def run(args):
    destination = private_json_path(args.output, new=True)
    reports, hashes = [], []
    for value in (args.primary, args.secondary):
        content = private_json_path(value).read_bytes()
        report = json.loads(content)
        if report.get("cloud") is not False or report.get("fresh_inference") is not True:
            raise ValueError("Original complete offline source reports required, not another replay")
        reports.append(report)
        hashes.append(hashlib.sha256(content).hexdigest())
    primary, secondary = reports
    before, after = checked_pages(primary), checked_pages(secondary)
    with DirectoryDataset(args.folder) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    if any(r.get("input_fingerprint_sha256") != fingerprint for r in reports) or primary.get("ocr") != secondary.get("ocr"):
        raise ValueError("Unchanged dataset and recognizer required")
    if set(before) != set(after) or set(before) != {p[0]["page_id"] for p in pages}:
        raise ValueError("Complete matching source-page coverage required")
    for page in before:
        if set(before[page][1]) != set(after[page][1]) or any(
                before[page][1][ident]["reference"] != row["reference"] for ident, row in after[page][1].items()):
            raise ValueError("Reference coverage/text changed")
    components = args.secondary_components
    result = {"schema": 1, "version": COMPONENT_VERSION if components else VERSION, "input_fingerprint_sha256": fingerprint,
              "production_default": False, "automatic_promotion": False, "fresh_inference": False,
              "cloud": False, "images_persisted": False, "source_report_sha256": hashes,
              "ocr": primary["ocr"], "counts": counts, "audit": issues, "pages": [],
              "limitations": ["Replay of two existing recognition planes, not fresh detector/OCR or latency.",
                  "Any positive source-box overlap is retained for review, never resolved with gold or text.",
                  "Disjoint boxes do not establish distinct glyphs, relevance, speaker or erasure authority.",
                  "Simple RTL row order is not verified panel reading order.",
                  "Legacy parents retain aggregate scores but may lack raw line classes/polygons; none are invented.",
                  "Unreviewed development labels, not held-out fidelity, Vietnamese or clean-background gold."]}
    for page, image, labels in pages:
        ident = page["page_id"]
        planes = [before[ident][0]["regions"], after[ident][0]["regions"]]
        # An unselected/overlapping source can veto another source. Validate
        # both complete planes against the pixels, not just chosen outputs.
        for plane in planes:
            _validate(plane)
            for row in plane:
                x, y, w, h = row["bbox"]
                if x+w > image.width or y+h > image.height:
                    raise ValueError("Retained source outside the matching image")
        selection = select_complement(ident, *planes, preserve_secondary_components=components)
        aligned, unmatched = assign_to_labels(labels, selection["regions"])
        result["pages"].append({"page": ident, **selection, "aligned": aligned, "unmatched_prediction_ids": unmatched})
    rows = [row for page in result["pages"] for row in page["aligned"]]
    characters = sum(row["characters"] for row in rows)
    result["aggregate"] = {"annotations": len(rows), "characters": characters,
        "exact": sum(row["edits"] == 0 for row in rows), "edits": sum(row["edits"] for row in rows),
        "cer": sum(row["edits"] for row in rows)/characters if characters else None,
        "regions": sum(len(page["regions"]) for page in result["pages"]),
        "secondary_added": sum(d["action"] == "add_disjoint_secondary" for p in result["pages"] for d in p["decisions"])}
    result["paired_primary"] = compare(primary, result)
    result["paired_secondary"] = compare(secondary, result)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"aggregate": result["aggregate"], "paired_primary": result["paired_primary"]["aggregate"],
                      "paired_secondary": result["paired_secondary"]["aggregate"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--primary", required=True)
    parser.add_argument("--secondary", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--secondary-components", action="store_true",
                        help="Separate v2 recipe: preserve entire disjoint secondary overlap components")
    run(parser.parse_args())
