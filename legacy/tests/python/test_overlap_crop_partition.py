"""Authored pixels only; these regressions do not certify manga quality."""
from copy import deepcopy
from pathlib import Path
import sys

from PIL import Image, ImageDraw
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from probe_overlap_crop_partition import partition_boxes, partitioned_record
from manga_live.text_scope import story_regions


def source():
    image = Image.new("RGB", (200, 250), "white")
    ink = ImageDraw.Draw(image)
    for top in range(50, 120, 15):
        ink.rectangle((116, top, 127, top+9), fill="black")
        ink.rectangle((96, top, 106, top+9), fill="black")
    regions = [
        {"id": "right", "bbox": [104, 45, 30, 86], "overlay": "label", "ja": "SOURCE_RIGHT"},
        {"id": "left", "bbox": [90, 46, 29, 100], "overlay": "label", "ja": "SOURCE_LEFT"},
    ]
    for region in regions:
        region["scope"] = {"key": "authored-"+region["id"], "group": "authored-"+region["id"],
            "memory": True, "role": "unknown", "action": "translate", "reason": "unclassified"}
    return image, regions


def test_blank_seam_separates_neighbouring_ink_without_changing_source_geometry():
    image, regions = source()
    original = deepcopy(regions)
    boxes, evidence = partition_boxes(image, regions)
    assert regions == original
    assert len(evidence) == 1 and evidence[0]["source_ids"] == ["left", "right"]
    assert evidence[0]["erasure_permitted"] is False
    assert 107 < boxes[0][0] <= 115
    assert boxes[1][0]+boxes[1][2] == boxes[0][0]
    assert boxes[0][0]+boxes[0][2] == 134
    assert boxes[1][0] == 90 and boxes[1][1:] == [46, boxes[1][2], 100]


def test_text_and_reference_never_choose_a_seam():
    image, regions = source()
    before = partition_boxes(image, regions)
    for row in regions:
        row.update(ja="different OCR", vi="different translation", reference="not a geometry input")
    assert partition_boxes(image, regions) == before


@pytest.mark.parametrize("marker", [
    {"scope": {"reason": "reader", "action": "translate"}},
    {"scope": {"reason": "reader", "action": "defer"}},
    {"scope": {"reason": "unclassified", "action": "defer"}},
    {"speaker": "confirmed"}, {"listener": "confirmed"},
    {"balloon": {"textBox": [90, 45, 44, 101]}},
    {"reviewReasons": ["layout_fragment"]},
])
def test_partition_does_not_replace_reader_identity_exclusions_or_bounded_balloon(marker):
    image, regions = source()
    regions[0].update(marker)
    assert partition_boxes(image, regions) == ([r["bbox"] for r in regions], [])


def test_connected_artwork_is_not_a_blank_seam():
    image, regions = source()
    ImageDraw.Draw(image).rectangle((104, 70, 119, 73), fill="black")
    assert partition_boxes(image, regions) == ([r["bbox"] for r in regions], [])


def test_ink_beyond_the_neighbours_height_cannot_be_lost():
    image, regions = source()
    # Outside right's short crop, left has a real mark on the proposed removed
    # edge. Even an otherwise blank separator cannot justify losing this ink.
    ImageDraw.Draw(image).rectangle((116, 137, 118, 143), fill="black")
    assert partition_boxes(image, regions) == ([r["bbox"] for r in regions], [])


def test_near_duplicate_and_staggered_crops_are_not_partitioned():
    image, regions = source()
    regions[1]["bbox"] = [103, 46, 30, 100]
    assert partition_boxes(image, regions) == ([r["bbox"] for r in regions], [])
    image, regions = source()
    regions[1]["bbox"][1] = 85
    assert partition_boxes(image, regions) == ([r["bbox"] for r in regions], [])


def test_horizontal_lines_use_the_same_pixel_coverage_rules():
    image, regions = source()
    image = image.transpose(Image.Transpose.TRANSPOSE)
    for row in regions:
        x, y, w, h = row["bbox"]
        row["bbox"] = [y, x, h, w]
    boxes, evidence = partition_boxes(image, regions)
    assert len(evidence) == 1 and evidence[0]["orientation"] == "horizontal"
    assert boxes[1][1]+boxes[1][3] == boxes[0][1]


@pytest.mark.parametrize("box", [[-1, 5, 30, 40], [10, 10, 0, 40], [170, 5, 40, 40], [10, 5, float("nan"), 40]])
def test_invalid_geometry_is_rejected_without_touching_source(box):
    image, regions = source()
    regions[0]["bbox"] = box
    with pytest.raises(ValueError, match="geometry"):
        partition_boxes(image, regions)


def test_ambiguous_source_ids_are_rejected():
    image, regions = source()
    regions[1]["id"] = regions[0]["id"]
    with pytest.raises(ValueError, match="identities"):
        partition_boxes(image, regions)


def test_measured_crop_keeps_raw_text_and_anchor_but_cannot_inherit_translation_or_memory():
    _, regions = source()
    original = {**regions[0], "vi": "OLD_TRANSLATION", "expression": {"sourceHash": "OLD"},
        "scope": {"key": "CAPTURED_SOURCE", "group": "CAPTURED_SOURCE", "memory": True,
                  "reason": "unclassified", "role": "unknown", "action": "translate"},
        "reviewReasons": ["quote_balance"]}
    before = deepcopy(original)
    candidate = partitioned_record(original, [110, 45, 24, 86], "NEW_OCR")
    assert original == before and candidate["sourceOcr"] == before
    assert candidate["bbox"] == original["bbox"] and candidate["scope"]["key"] == "CAPTURED_SOURCE"
    assert "vi" not in candidate and "expression" not in candidate
    assert candidate["reviewReasons"] == ["quote_balance", "ocr_crop_partition"]
    assert candidate["scope"]["memory"] is False and story_regions([candidate]) == []
    assert candidate["sourceOcr"]["ja"] == "SOURCE_RIGHT"


def test_empty_measured_ocr_is_kept_not_silently_replaced_by_previous_text():
    _, regions = source()
    candidate = partitioned_record(regions[0], [110, 45, 24, 86], "")
    assert candidate["ja"] == "" and candidate["sourceOcr"]["ja"] == "SOURCE_RIGHT"


def test_legacy_missing_scope_cannot_be_assigned_an_invented_source_anchor():
    _, regions = source()
    regions[0].pop("scope")
    with pytest.raises(ValueError, match="legacy anchor"):
        partitioned_record(regions[0], [110, 45, 24, 86], "NEW_OCR")


@pytest.mark.parametrize("factor", [0.5, 1, 1.5, 2])
def test_scaled_partition_never_loses_original_ink(factor):
    import numpy as np
    image, regions = source()
    image = image.resize((int(image.width*factor), int(image.height*factor)), Image.Resampling.NEAREST)
    for row in regions:
        row["bbox"] = [int(value*factor) for value in row["bbox"]]
    boxes, _ = partition_boxes(image, regions)
    old = np.zeros((image.height, image.width), dtype=bool)
    new = old.copy()
    for x, y, w, h in (row["bbox"] for row in regions):
        old[y:y+h, x:x+w] = True
    for x, y, w, h in boxes:
        new[y:y+h, x:x+w] = True
    ink = np.asarray(image.convert("L")) < 220
    assert not (old & ink & ~new).any()
