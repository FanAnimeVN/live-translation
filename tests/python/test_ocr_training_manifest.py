"""OCR adaptation must require reviewed, split-aware source labels."""
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import build_ocr_training_manifest as manifest


def counts_and_fingerprint(tmp_path):
    pixels = io.BytesIO()
    Image.new("RGB", (40, 60), "white").save(pixels, format="PNG")
    labels = [{"page_id": "p1", "image_file": "one.png", "image_size": {"w": 40, "h": 60},
               "bubbles": [{"bubble_id": "b1", "bbox": {"x": 2, "y": 3, "w": 10, "h": 15},
                            "ja_ocr_truth": "ありがとう"},
                           {"bubble_id": "b2", "bbox": {"x": 20, "y": 3, "w": 10, "h": 15},
                            "ja_ocr_truth": "さようなら"}]}]
    (tmp_path / "ground_truth_benchmark.json").write_text(json.dumps(labels), encoding="utf-8")
    (tmp_path / "one.png").write_bytes(pixels.getvalue())
    from benchmark import DirectoryDataset, audit, dataset_fingerprint
    with DirectoryDataset(tmp_path) as source:
        counts, issues, _ = audit(source)
        fingerprint = dataset_fingerprint(source)
    return counts, issues, fingerprint


def draft(fingerprint):
    return {"schema": 1, "dataset_fingerprint_sha256": fingerprint,
            "review_state": "unreviewed", "independent_human_review": False,
            "rights_confirmed": False, "rows": []}


def test_unreviewed_draft_is_rejected_before_manifest_creation(tmp_path):
    counts, issues, fingerprint = counts_and_fingerprint(tmp_path)
    with pytest.raises(ValueError, match="incomplete"):
        manifest.validate_review_pack(draft(fingerprint), counts=counts, issues=issues, fingerprint=fingerprint)


def test_reviewed_pack_requires_heldout_and_never_accepts_missing_review(tmp_path):
    counts, issues, fingerprint = counts_and_fingerprint(tmp_path)
    pack = {"schema": 1, "dataset_fingerprint_sha256": fingerprint,
            "review_state": "reviewed", "independent_human_review": True,
            "rights_confirmed": True, "rows": [{"page_id": "p1", "bubble_id": "b1",
            "image_file": "one.png", "reviewed_ja": "ありがとう", "reviewed_bbox": {"x": 2, "y": 3, "w": 10, "h": 15},
            "split": "train", "role": "dialogue", "difficulty": "ordinary", "reviewed_by": "reviewer"},
            {"page_id": "p1", "bubble_id": "b2", "image_file": "one.png", "reviewed_ja": "さようなら",
             "reviewed_bbox": {"x": 20, "y": 3, "w": 10, "h": 15}, "split": "train", "role": "dialogue",
             "difficulty": "ordinary", "reviewed_by": "reviewer"}]}
    with pytest.raises(ValueError, match="held-out"):
        manifest.validate_review_pack(pack, counts=counts, issues=issues, fingerprint=fingerprint)
    pack["rows"][1]["split"] = "heldout"
    result = manifest.validate_review_pack(pack, counts=counts, issues=issues, fingerprint=fingerprint)
    assert result["rows"][0]["text"] == "ありがとう"
    assert result["rows"][1]["split"] == "heldout"


@pytest.mark.parametrize("field,value", [("reviewed_bbox", {"x": 0, "y": 0, "w": 0, "h": 3}),
                                           ("reviewed_ja", ""), ("reviewed_by", "")])
def test_reviewed_row_rejects_unusable_training_evidence(tmp_path, field, value):
    counts, issues, fingerprint = counts_and_fingerprint(tmp_path)
    pack = {"schema": 1, "dataset_fingerprint_sha256": fingerprint,
            "review_state": "reviewed", "independent_human_review": True,
            "rights_confirmed": True, "rows": [{"page_id": "p1", "bubble_id": "b1",
            "image_file": "one.png", "reviewed_ja": "ありがとう", "reviewed_bbox": {"x": 2, "y": 3, "w": 10, "h": 15},
            "split": "train", "role": "dialogue", "difficulty": "ordinary", "reviewed_by": "reviewer"},
            {"page_id": "p1", "bubble_id": "b2", "image_file": "one.png", "reviewed_ja": "さようなら",
             "reviewed_bbox": {"x": 20, "y": 3, "w": 10, "h": 15}, "split": "heldout", "role": "dialogue",
             "difficulty": "ordinary", "reviewed_by": "reviewer"}]}
    pack["rows"][0][field] = value
    with pytest.raises(ValueError):
        manifest.validate_review_pack(pack, counts=counts, issues=issues, fingerprint=fingerprint)


def test_production_validation_binds_review_identity_to_source_geometry(tmp_path):
    counts, issues, fingerprint = counts_and_fingerprint(tmp_path)
    pack = {"schema": 1, "dataset_fingerprint_sha256": fingerprint,
            "review_state": "reviewed", "independent_human_review": True,
            "rights_confirmed": True, "rows": [{"page_id": "p1", "bubble_id": "b1",
            "image_file": "wrong.png", "reviewed_ja": "ありがとう", "reviewed_bbox": {"x": 2, "y": 3, "w": 10, "h": 15},
            "split": "train", "role": "dialogue", "difficulty": "ordinary", "reviewed_by": "reviewer"},
            {"page_id": "p1", "bubble_id": "b2", "image_file": "one.png", "reviewed_ja": "さようなら",
             "reviewed_bbox": {"x": 20, "y": 3, "w": 10, "h": 15}, "split": "heldout", "role": "dialogue",
             "difficulty": "ordinary", "reviewed_by": "reviewer"}]}
    expected = {("p1", "b1"): {"image_file": "one.png", "image_size": (40, 60)},
                ("p1", "b2"): {"image_file": "one.png", "image_size": (40, 60)}}
    with pytest.raises(ValueError, match="image"):
        manifest.validate_review_pack(pack, counts=counts, issues=issues, fingerprint=fingerprint, expected=expected)
