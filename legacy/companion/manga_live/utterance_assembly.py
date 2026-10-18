"""Conservative speech-unit assembly above the captured OCR plane.

OCR regions are source evidence and reader anchors.  This module only creates
an ephemeral presentation/translation unit when geometry supplies a unique,
small, same-orientation guide.  It never mutates the source list, invents a
reader anchor, grants erasure authority, or turns a grouped unit into story
memory.  A caller can therefore discard the proposal without losing any source
record or reader choice.
"""
from copy import deepcopy
import hashlib
import json
import math


MAX_SOURCES = 64
MAX_GUIDES = 64
MAX_TEXT = 3000
ASSEMBLY_VERSION = "utterance-assembly-boundaries-v2"


def _finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def _box(value, width, height):
    if (not isinstance(value, (list, tuple)) or len(value) != 4
            or any(not _finite_number(v) for v in value)
            or value[2] <= 0 or value[3] <= 0 or value[0] < 0 or value[1] < 0
            or value[0] + value[2] > width or value[1] + value[3] > height):
        raise ValueError("Invalid source/guide geometry")
    return [float(v) for v in value]


def _overlap(a, b):
    return max(0.0, min(a[0] + a[2], b[0] + b[2]) - max(a[0], b[0])) * max(
        0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))


def _contains(outer, inner, tolerance=4.0):
    return (outer[0] <= inner[0] + tolerance and outer[1] <= inner[1] + tolerance
            and outer[0] + outer[2] >= inner[0] + inner[2] - tolerance
            and outer[1] + outer[3] >= inner[1] + inner[3] - tolerance)


def _union(boxes):
    left = min(box[0] for box in boxes); top = min(box[1] for box in boxes)
    right = max(box[0] + box[2] for box in boxes); bottom = max(box[1] + box[3] for box in boxes)
    return [left, top, right - left, bottom - top]


def _source_id(row):
    value = row.get("id")
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise ValueError("Every OCR source needs a stable ID")
    return value


def _source_key(row):
    scope = row.get("scope")
    key = scope.get("key") if isinstance(scope, dict) else None
    return key if isinstance(key, str) and 0 < len(key) <= 128 and key.strip() == key else None


def _veto(row):
    """Return a reason when grouping would swallow a reader/source boundary."""
    scope = row.get("scope") if isinstance(row.get("scope"), dict) else {}
    if scope.get("reason") == "reader" or scope.get("action") == "defer":
        return "reader-choice"
    if row.get("speakerBindingReview") or row.get("speaker", "unknown") != "unknown" \
            or row.get("listener", "unknown") != "unknown":
        return "reader-identity"
    # A present-but-empty legacy scope is not a captured-source anchor. A
    # presentation ID must never manufacture the missing reader provenance.
    if not _source_key(row):
        return "legacy-source"
    if scope.get("action") != "translate":
        return "source-policy"
    if row.get("balloon") or row.get("type") in ("sfx", "editorial"):
        return "bounded-or-secondary"
    reasons = set(row.get("reviewReasons", [])) if isinstance(row.get("reviewReasons", []), list) else set()
    if reasons.intersection({"layout_fragment", "visual_low_signal", "visual_punctuation_support"}):
        return "visual-review"
    # ``ocr_crop_partition`` records a bounded source crop split; it is not a
    # semantic/visual exclusion. Other review flags are a source veto.
    if row.get("review") is True and (not reasons or not reasons.issubset({"ocr_crop_partition"})):
        return "review"
    return None


def _compatible(rows, boxes):
    if len(rows) < 2:
        return False
    if any(_veto(row) for row in rows):
        return False
    vertical = all(box[3] >= box[2] * 1.25 for box in boxes)
    horizontal = all(box[2] >= box[3] * 1.25 for box in boxes)
    if not (vertical or horizontal):
        return False
    if vertical:
        # The leading edge of a Japanese vertical utterance is a horizontal
        # band. Staggered starts are treated as separate text blocks.
        if max(box[1] for box in boxes) - min(box[1] for box in boxes) > max(2.0, min(box[2] for box in boxes) * .35):
            return False
        scales = [box[2] for box in boxes]
        axis, start_axis = 0, 1
    else:
        if max(box[0] for box in boxes) - min(box[0] for box in boxes) > max(2.0, min(box[3] for box in boxes) * .35):
            return False
        scales = [box[3] for box in boxes]
        axis, start_axis = 1, 0
    if max(scales) > min(scales) * 1.75:
        return False
    # Do not silently reorder the source to fit a guide, or concatenate a
    # reversed sentence just because its numeric order fields are sorted.
    # This conservative seam only supports vertical RTL and horizontal rows
    # top-to-bottom; ambiguous/other arrangements keep their exact sources.
    reading_centres = [box[axis] + box[axis + 2] / 2 for box in boxes]
    if any((following >= previous if vertical else following <= previous)
           for previous, following in zip(reading_centres, reading_centres[1:])):
        return False
    ordered = sorted(boxes, key=lambda box: box[axis])
    centres = [box[axis] + box[axis + 2] / 2 for box in ordered]
    gaps = [b - a for a, b in zip(centres, centres[1:])]
    # Detector padding that duplicates a column is not a bridge. Conversely,
    # unrelated distant columns cannot be made one sentence by a large guide.
    if any(gap < min(scales) * .25 or gap > max(scales) * 2.25 for gap in gaps):
        return False
    if len(rows) > 2 and any(_overlap(boxes[i], boxes[j]) > min(boxes[i][2] * boxes[i][3], boxes[j][2] * boxes[j][3]) * .80
                             for i in range(len(boxes)) for j in range(i + 1, len(boxes))):
        return False
    return True


def _canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _fingerprint(rows, guides):
    evidence = [{"id": _source_id(row), "order": row.get("order"), "bbox": row["bbox"], "ja": row["ja"],
                 "scope": {"key": _source_key(row), "group": (row.get("scope") or {}).get("group")}}
                for row in rows]
    return hashlib.sha256(_canonical({"sources": evidence, "guides": guides}).encode()).hexdigest()


def _validate_sources(rows, width, height):
    if not isinstance(rows, list) or not 1 <= len(rows) <= MAX_SOURCES:
        raise ValueError("Bounded source list required")
    ids, anchors = set(), set()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Invalid OCR source")
        ident = _source_id(row)
        if ident in ids:
            raise ValueError("Duplicate OCR source ID")
        ids.add(ident)
        if not isinstance(row.get("ja"), str) or not 1 <= len(row["ja"]) <= MAX_TEXT:
            raise ValueError("OCR source text is missing or too long")
        _box(row.get("bbox"), width, height)
        anchor = _source_key(row)
        if anchor:
            if anchor in anchors:
                raise ValueError("Duplicate source anchor")
            anchors.add(anchor)
        score = row.get("score")
        if score is not None and (not _finite_number(score) or not 0 <= score <= 1):
            raise ValueError("Invalid OCR score")
        order = row.get("order")
        if order is not None and (not _finite_number(order) or isinstance(order, bool)):
            raise ValueError("Invalid source order")
    return ids


def _validate_guides(guides, width, height):
    if not isinstance(guides, list) or len(guides) > MAX_GUIDES:
        raise ValueError("Bounded guide list required")
    result, ids = [], set()
    for guide in guides:
        if not isinstance(guide, dict) or not isinstance(guide.get("id"), str):
            raise ValueError("Invalid or duplicate guide ID")
        # Duplicate detector proposals are ambiguity, not a reason to fail the
        # page or silently choose one. The caller receives no assembly.
        if guide["id"] in ids:
            return []
        ids.add(guide["id"]); result.append((guide["id"], _box(guide.get("bbox"), width, height)))
    return result


def assemble_utterances(source_rows, guides, image_size):
    """Return source evidence and conservative translation utterances.

    The returned ``sources`` is a deep copy of the exact input plane.  When no
    candidate is safe, ``utterances`` is also an exact copy of that plane.
    Grouped units carry every source row and are explicitly untrusted for plot
    memory/erasure. Their ID is content-derived and is never a replacement for
    a source anchor.
    """
    if (not isinstance(image_size, (tuple, list)) or len(image_size) != 2
            or any(type(v) is not int or v <= 0 for v in image_size)):
        raise ValueError("Image size required")
    width, height = image_size
    source = deepcopy(source_rows)
    ids = _validate_sources(source, width, height)
    checked_guides = _validate_guides(guides, width, height)
    fingerprint = _fingerprint(source, [{"id": ident, "bbox": box} for ident, box in checked_guides])
    # One unique guide is necessary but not sufficient. A broad detector block
    # cannot manufacture an utterance from a tiny subset of the page.
    owners = []
    for ident, guide in checked_guides:
        contained = [row for row in source if _contains(guide, _box(row["bbox"], width, height))]
        # Explicit reader/identity boundaries are stronger than orientation.
        # A horizontal excluded note between vertical columns is not noise
        # that may be jumped over while joining the surrounding sentence.
        if any(_veto(row) in {"reader-choice", "reader-identity", "legacy-source", "source-policy"}
               for row in contained):
            continue
        # A tiny punctuation/review mark inside an open block is a separate
        # source item. It remains visible/recoverable through the reader's
        # secondary-text affordance, but should not veto a valid
        # vertical/horizontal speech run. A veto with the same geometry as the
        # run still vetoes the whole candidate (reader choice wins).
        safe = [row for row in contained if not _veto(row)]
        if len(safe) >= 2:
            vertical = all(_box(row["bbox"], width, height)[3] >= _box(row["bbox"], width, height)[2] * 1.25 for row in safe)
            horizontal = all(_box(row["bbox"], width, height)[2] >= _box(row["bbox"], width, height)[3] * 1.25 for row in safe)
            same_orientation_veto = any((vertical and _box(row["bbox"], width, height)[3] >= _box(row["bbox"], width, height)[2] * 1.25)
                                        or (horizontal and _box(row["bbox"], width, height)[2] >= _box(row["bbox"], width, height)[3] * 1.25)
                                        for row in contained if _veto(row))
            if same_orientation_veto:
                safe = []
            members = safe
        else:
            members = contained
        if len(members) < 2 or _overlap(guide, guide) <= 0:
            continue
        union = _union([_box(row["bbox"], width, height) for row in members])
        if guide[2] * guide[3] > union[2] * union[3] * 2.5:
            continue
        owners.append((ident, members, guide))
    selected = []
    used = set()
    for ident, members, guide in owners:
        member_ids = {_source_id(row) for row in members}
        if member_ids & used or len([candidate for candidate in owners if member_ids & {_source_id(row) for row in candidate[1]}]) != 1:
            continue
        ordered_positions = [source.index(row) for row in members]
        if ordered_positions != sorted(ordered_positions) or any(
                row.get("order") is not None and row["order"] != sorted(source, key=lambda r: r.get("order", 0))[source.index(row)].get("order")
                for row in members):
            continue
        boxes = [_box(row["bbox"], width, height) for row in members]
        if _compatible(members, boxes):
            selected.append((ident, members, guide)); used.update(member_ids)
    if not selected:
        return {"sources": source, "utterances": deepcopy(source), "source_fingerprint": fingerprint, "assemblies": []}
    by_first = {_source_id(members[0]): (ident, members, guide) for ident, members, guide in selected}
    skip = {_source_id(row) for _, members, _ in selected for row in members[1:]}
    utterances = []
    for row in source:
        ident = _source_id(row)
        if ident in skip:
            continue
        assembly = by_first.get(ident)
        if assembly is None:
            utterances.append(deepcopy(row)); continue
        guide_id, members, guide = assembly
        joined = "".join(member["ja"] for member in members)
        if len(joined) > MAX_TEXT:
            return {"sources": source, "utterances": deepcopy(source), "source_fingerprint": fingerprint, "assemblies": []}
        boxes = [_box(member["bbox"], width, height) for member in members]
        assembly_digest = hashlib.sha256(_canonical({"source_ids": [_source_id(m) for m in members],
            "source_keys": [_source_key(m) for m in members], "ja": joined}).encode()).hexdigest()[:32]
        row_value = {k: deepcopy(v) for k, v in row.items() if k not in {"vi", "expression", "score", "scope"}}
        row_value.update({"id": "u-" + assembly_digest,
                          "bbox": [int(v) if float(v).is_integer() else v for v in _union(boxes)], "ja": joined,
                          "order": row.get("order", utterances[-1].get("order", 0) + 1) if utterances else row.get("order", 0),
                          "speaker": "unknown", "listener": "unknown", "review": True,
                          "reviewReasons": ["layout_cluster"], "scope": {"v": 1, "key": "assembly-" + assembly_digest,
                              "group": "assembly-" + assembly_digest, "role": "unknown", "action": "translate",
                              "reason": "visual_review", "memory": False},
                          "assembly": {"guide_id": guide_id, "source_ids": [_source_id(m) for m in members],
                                       "source_keys": [_source_key(m) for m in members], "erasure_permitted": False,
                                       "source_regions": deepcopy(members)}})
        scores = [member.get("score") for member in members]
        if all(_finite_number(score) and 0 <= score <= 1 for score in scores):
            row_value["score"] = min(scores)
        utterances.append(row_value)
    assemblies = [{"id": utterance["id"], **utterance["assembly"]} for utterance in utterances if "assembly" in utterance]
    return {"sources": source, "utterances": utterances, "source_fingerprint": fingerprint, "assemblies": assemblies}
