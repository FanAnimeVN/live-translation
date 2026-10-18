"""Build a private, leakage-resistant OCR training manifest.

The command intentionally refuses the current unreviewed draft.  It emits
metadata and source coordinates only; images remain in the user's private
dataset and are loaded by a later training job in RAM.  No predictions are
accepted as labels and no title-held-out row may be used for adaptation.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from benchmark import audit, dataset_fingerprint, dataset_source

VERSION = "ocr-training-manifest-v1"
ALLOWED_SPLITS = {"train", "validation", "heldout"}
ALLOWED_ROLES = {"dialogue", "thought", "narration", "scene_text", "sfx", "decorative", "unknown"}


def _finite_box(value):
    if not isinstance(value, dict) or set(value) != {"x", "y", "w", "h"}:
        raise ValueError("reviewed_bbox must contain x,y,w,h only")
    values = [value[key] for key in ("x", "y", "w", "h")]
    if any(type(item) is not int for item in values) or min(values[0], values[1]) < 0 or min(values[2:]) <= 0:
        raise ValueError("reviewed_bbox must be finite positive integer geometry")
    return {key: int(value[key]) for key in ("x", "y", "w", "h")}


def validate_review_pack(pack, *, counts, issues, fingerprint, expected=None):
    """Return a text/geometry manifest or fail before any output is created."""
    if not isinstance(pack, dict) or pack.get("schema") != 1:
        raise ValueError("Unsupported review pack")
    if pack.get("dataset_fingerprint_sha256") != fingerprint:
        raise ValueError("Review pack and dataset fingerprints differ")
    if issues or pack.get("review_state") != "reviewed" or pack.get("independent_human_review") is not True:
        raise ValueError("Dataset audit or independent Japanese review is incomplete")
    if pack.get("rights_confirmed") is not True:
        raise ValueError("Rights confirmation is required before training")
    rows = pack.get("rows")
    if not isinstance(rows, list) or len(rows) != counts.get("eligible_bubbles"):
        raise ValueError("Review coverage does not match eligible dataset rows")
    seen = set()
    manifest = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Malformed review row")
        identity = (row.get("page_id"), row.get("bubble_id"))
        if identity in seen or not all(isinstance(value, str) and value for value in identity):
            raise ValueError("Duplicate or missing review identity")
        seen.add(identity)
        source = expected.get(identity) if expected is not None else None
        if expected is not None and source is None:
            raise ValueError("Review identity is not an eligible source label")
        if source is not None and row.get("image_file") != source["image_file"]:
            raise ValueError("Review image does not match the source label")
        text = row.get("reviewed_ja")
        reviewer = row.get("reviewed_by")
        split = row.get("split")
        role = row.get("role")
        if not isinstance(text, str) or not text.strip() or len(text) > 3000:
            raise ValueError("Every training row needs reviewed Japanese text")
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise ValueError("Every training row needs a reviewer")
        if split not in ALLOWED_SPLITS:
            raise ValueError("Every row needs train/validation/heldout split")
        if role not in ALLOWED_ROLES:
            raise ValueError("Every row needs an explicit role")
        box = _finite_box(row.get("reviewed_bbox"))
        if source is not None:
            width, height = source["image_size"]
            if box["x"] + box["w"] > width or box["y"] + box["h"] > height:
                raise ValueError("Reviewed geometry is outside the source image")
        manifest.append({"page_id": identity[0], "bubble_id": identity[1],
                         "image_file": row.get("image_file"), "bbox": box,
                         "text": text, "split": split, "role": role,
                         "difficulty": row.get("difficulty", "unknown"),
                         "reading_order": row.get("reading_order"),
                         "reviewed_by": reviewer})
    if not any(row["split"] == "heldout" for row in manifest):
        raise ValueError("At least one title-held-out row is required")
    if not any(row["split"] == "train" for row in manifest):
        raise ValueError("At least one training row is required")
    return {"schema": 1, "version": VERSION, "dataset_fingerprint_sha256": fingerprint,
            "counts": counts, "rows": manifest,
            "limitations": ["Manifest contains private source text/coordinates; keep it outside distribution.",
                            "A held-out split is for evaluation only and must not be used for adaptation.",
                            "This command does not train a model or prove title-held-out quality."]}


def output_path(value):
    path = Path(value).resolve()
    if (ROOT / "artifacts").resolve() not in path.parents or path.suffix != ".json" or path.exists():
        raise ValueError("Output must be a new private JSON below artifacts")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", required=True)
    parser.add_argument("--review", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    destination = output_path(args.output)
    pack = json.loads(Path(args.review).read_text(encoding="utf-8"))
    with dataset_source(args) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
    expected = {(page["page_id"], bubble["bubble_id"]):
                {"image_file": page["image_file"], "image_size": (image.width, image.height)}
                for page, image, bubbles in pages for bubble in bubbles}
    result = validate_review_pack(pack, counts=counts, issues=issues, fingerprint=fingerprint, expected=expected)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest_created": True, "rows": len(result["rows"]),
                      "fingerprint": fingerprint, "heldout": sum(r["split"] == "heldout" for r in result["rows"])},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
