from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from diagnose_stage_failures import classify_page


def page(bubbles):
    return {"page_id": "p1", "bubbles": bubbles}


def bubble(key, x, y, w, h, text):
    return {"bubble_id": key, "bbox": {"x": x, "y": y, "w": w, "h": h}, "ja_ocr_truth": text}


def test_separates_detector_miss_and_ocr_mismatch():
    gold = page([
        bubble("missing", 0, 0, 20, 20, "欠落"),
        bubble("wrong", 30, 0, 20, 20, "正解"),
        bubble("exact", 60, 0, 20, 20, "一致"),
    ])
    report = {"page": "p1", "regions": [
        {"id": "r-wrong", "bbox": [30, 0, 20, 20], "order": 0, "ja": "誤り"},
        {"id": "r-exact", "bbox": [60, 0, 20, 20], "order": 1, "ja": "一致"},
    ]}
    rows, unmatched = classify_page(gold, report)
    assert [row["stage"] for row in rows] == ["detector_miss", "ocr_mismatch", "exact"]
    assert unmatched == []


def test_marks_cross_label_union_and_unmatched_regions_without_calling_them_irrelevant():
    gold = page([
        bubble("a", 0, 0, 20, 20, "甲"),
        bubble("b", 20, 0, 20, 20, "乙"),
    ])
    report = {"page": "p1", "regions": [
        {"id": "union", "bbox": [0, 0, 40, 20], "order": 0, "ja": "甲乙"},
        {"id": "unlabelled", "bbox": [60, 0, 10, 10], "order": 1, "ja": "背景文字"},
    ]}
    rows, unmatched = classify_page(gold, report)
    assert [row["stage"] for row in rows] == ["grouping_cross_label", "grouping_cross_label"]
    assert unmatched == [{"page": "p1", "region_id": "unlabelled", "bbox": [60, 0, 10, 10], "ja": "背景文字"}]


def test_multiple_regions_inside_one_gold_is_grouping_fragmentation_before_ocr():
    gold = page([bubble("a", 0, 0, 40, 20, "甲乙")])
    report = {"page": "p1", "regions": [
        {"id": "r1", "bbox": [0, 0, 20, 20], "order": 0, "ja": "甲"},
        {"id": "r2", "bbox": [20, 0, 20, 20], "order": 1, "ja": "乙"},
    ]}
    rows, unmatched = classify_page(gold, report)
    assert rows[0]["stage"] == "exact_assembled"
    assert rows[0]["prediction"] == "甲乙"
    assert unmatched == []


def test_multiple_regions_with_wrong_order_or_missing_text_remains_grouping_failure():
    gold = page([bubble("a", 0, 0, 40, 20, "甲乙")])
    report = {"page": "p1", "regions": [
        {"id": "r1", "bbox": [0, 0, 20, 20], "order": 0, "ja": "甲"},
        {"id": "r2", "bbox": [20, 0, 20, 20], "order": 1, "ja": "欠"},
    ]}
    rows, _ = classify_page(gold, report)
    assert rows[0]["stage"] == "grouping_fragmented"
