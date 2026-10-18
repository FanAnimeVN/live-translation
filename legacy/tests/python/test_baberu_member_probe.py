"""Retained detector input, not ground-truth boxes, controls line recognition."""
from pathlib import Path
from copy import deepcopy
import sys

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import benchmark_baberu_probe as probe


def test_recorded_column_fragments_read_top_before_bottom_despite_horizontal_jitter():
    members = [
        {"polygon": [[267, 826], [294, 825], [297, 890], [270, 891]], "score": .7},
        {"polygon": [[241, 721], [267, 721], [267, 810], [241, 810]], "score": .8},
        {"polygon": [[269, 708], [299, 709], [294, 822], [263, 820]], "score": .9},
    ]
    rows = [
        {"member_index": 0, "source": members[0], "crop_box": [265, 823, 34, 70],
         "raw_text": "下", "status": "recognized", "ms": 10},
        {"member_index": 2, "source": members[2], "crop_box": [261, 706, 40, 118],
         "raw_text": "上…  ", "status": "recognized", "ms": 20},
        {"member_index": 1, "source": members[1], "crop_box": [239, 719, 30, 93],
         "raw_text": "「左」", "status": "recognized", "ms": 30},
    ]
    region = {"id": "source", "sourceMembers": members, "member_readings": rows,
              "ja": "下上…  「左」", "erasure_authority": False}
    before = deepcopy(region)
    result = probe.reorder_recorded_members(region)
    assert result["ja"] == "上…  下「左」"
    assert [r["member_index"] for r in result["member_readings"]] == [2, 0, 1]
    assert result["sourceMembers"] == members
    assert result["erasure_authority"] is False
    assert region == before


def test_recorded_order_uses_source_overlap_not_the_halo_or_text():
    # Source x overlap is 4/10, below 60%; 2px halos overlap 8/14.
    members = [
        {"polygon": [[10, 60], [20, 60], [20, 100], [10, 100]]},
        {"polygon": [[4, 10], [14, 10], [14, 50], [4, 50]]},
    ]
    rows = [{"member_index": i, "source": m, "crop_box": box, "raw_text": text, "status": "recognized"}
            for i, m, box, text in zip(range(2), members,
                ([8, 58, 14, 44], [2, 8, 14, 44]), ("下", "上"))]
    result = probe.reorder_recorded_members(
        {"sourceMembers": members, "member_readings": rows, "ja": "下上"})
    assert result["ja"] == "下上"


def test_near_square_short_column_is_not_a_vote_for_horizontal_reading():
    members=[{"polygon":[[60,12],[80,12],[80,40],[60,40]],"score":.8},
             {"polygon":[[35,11],[50,11],[50,51],[35,51]],"score":.9}]
    rows=[{"member_index":i,"source":m,"crop_box":box,"raw_text":text,"status":"recognized"}
          for i,m,box,text in zip((1,0),reversed(members),([33,9,19,44],[58,10,24,32]),("左…","右♡"))]
    region={"sourceMembers":members,"member_readings":rows,"ja":"左…右♡"}
    before=deepcopy(region)
    assert probe.reorder_recorded_members(region)["ja"]=="左…右♡"
    result=probe.reorder_recorded_members(region,directional_votes=True)
    assert result["ja"]=="右♡左…"
    assert result["direction_evidence"]=={"vertical_votes":1,"horizontal_votes":0,"ambiguous_votes":1,
                                         "selected":"vertical","fallback":False}
    assert result["sourceMembers"]==members and region==before


def test_near_square_fragment_abstains_when_other_source_members_are_horizontal():
    members=[{"polygon":[[10,20],[50,20],[50,30],[10,30]],"score":.8},
             {"polygon":[[58,20],[78,20],[78,44],[58,44]],"score":.9}]
    rows=[{"member_index":i,"source":members[i],"crop_box":box,"raw_text":text,"status":"recognized"}
          for i,box,text in ((1,[56,18,24,28],"後♡"),(0,[8,18,44,14],"前…"))]
    region={"sourceMembers":members,"member_readings":rows,"ja":"後♡前…"}
    before=deepcopy(region)
    result=probe.reorder_recorded_members(region,directional_votes=True)
    assert result["ja"]=="前…後♡"
    assert result["direction_evidence"]=={"vertical_votes":0,"horizontal_votes":1,"ambiguous_votes":1,
                                         "selected":"horizontal","fallback":False}
    assert result["sourceMembers"]==members and region==before


def test_tied_source_direction_votes_report_legacy_fallback_instead_of_false_certainty():
    members=[{"polygon":[[10,10],[20,10],[20,40],[10,40]],"score":.8},
             {"polygon":[[40,10],[70,10],[70,20],[40,20]],"score":.9}]
    rows=[{"member_index":i,"source":members[i],"crop_box":box,"raw_text":text,"status":"recognized"}
          for i,box,text in ((1,[38,8,34,14],"後♡"),(0,[8,8,14,34],"前…"))]
    region={"sourceMembers":members,"member_readings":rows,"ja":"後♡前…"}
    result=probe.reorder_recorded_members(region,directional_votes=True)
    assert result["ja"]=="前…後♡"
    assert result["ja"]==probe.reorder_recorded_members(region)["ja"]
    assert result["direction_evidence"]=={"vertical_votes":1,"horizontal_votes":1,"ambiguous_votes":0,
                                         "selected":"horizontal","fallback":True}
    assert result["sourceMembers"]==members and result["erasure_authority"] is False


def test_order_replay_reports_a_horizontal_fix_without_claiming_new_ocr():
    members = [{"polygon": polygon, "score": .8} for polygon in (
        [[40, 9], [70, 9], [70, 19], [40, 19]],
        [[0, 10], [30, 10], [30, 20], [0, 20]])]
    region = {"id": "source", "bbox": [0, 9, 70, 11], "order": 0,
              "ja": "後前", "sourceMembers": members, "probe_ocr_ms": 100,
              "member_readings": [
                  {"member_index": i, "source": m, "raw_text": text,
                   "crop_box": box, "ms": 50, "status": "recognized"}
                  for i, m, box, text in zip(range(2), members,
                      ([38, 7, 34, 14], [0, 8, 32, 14]), ("後", "前"))]}
    report = {"complete": True, "fresh_inference": True, "cloud": False,
              "ocr": "recorded-engine", "input_fingerprint_sha256": "same-input",
              "crop_recipe": "source-members-axis-halo2-rtl-v1", "pages": [
                  {"page": "one", "regions": [region], "aligned": [
                      {"id": "b1", "reference": "前後", "prediction": "後前",
                       "edits": 2, "characters": 2, "region_ids": ["source"]}]}]}
    pages = [({"page_id": "one"}, Image.new("RGB", (80, 40)), [
        {"bubble_id": "b1", "bbox": {"x": 0, "y": 0, "w": 80, "h": 40},
         "ja_ocr_truth": "前後"}])]
    before = deepcopy(report)
    result = probe.replay_recorded_report(report, pages, "same-input")
    assert result["fresh_inference"] is False
    assert result["aggregate"]["exact"] == 1
    assert result["comparison"]["aggregate"]["improved"] == 1
    assert result["comparison"]["aggregate"]["assigned_lost"] == 0
    unit = result["pages"][0]["regions"][0]
    assert unit["ja"] == "前後"
    assert "probe_ocr_ms" not in unit
    assert unit["recorded_probe_ocr_ms"] == 100
    assert "p95_crop_ms" not in result["aggregate"]
    assert report == before


def test_excluded_recording_cannot_reintroduce_recognized_text():
    member = {"polygon": [[1, 1], [10, 1], [10, 30], [1, 30]], "score": .9}
    region = {"readerExcluded": True, "sourceMembers": [member], "ja": "禁止",
              "member_readings": [{"member_index": 0, "source": member,
                  "crop_box": [0, 0, 12, 32], "raw_text": "禁止", "status": "recognized"}]}
    with pytest.raises(ValueError, match="exclusion"):
        probe.reorder_recorded_members(region)
    region["ja"] = ""
    region["member_readings"][0].update(raw_text="", status="reader_excluded")
    result = probe.reorder_recorded_members(region)
    assert result["ja"] == ""
    assert result["readerExcluded"] is True
    assert len(result["member_readings"]) == 1


def test_member_recognition_uses_original_vertical_pixels_and_rtl_order():
    image = Image.new("RGB", (100, 120), "white")
    region = {"id": "source", "bbox": [5, 5, 80, 100], "sourceMembers": [
        {"polygon": [[10, 10], [20, 10], [20, 90], [10, 90]], "score": .7},
        {"polygon": [[60, 20], [70, 20], [70, 100], [60, 100]], "score": .9}]}
    class Recognizer:
        last_decode = {"eos": True}
        def __init__(self): self.inputs = []
        def recognize(self, crop):
            self.inputs.append(crop.size)
            return "右…" if len(self.inputs) == 1 else "「左」"
    engine = Recognizer()
    result = probe.recognize_source_members(engine, image, region)
    assert result["ja"] == "右…「左」"
    assert engine.inputs == [(14, 84), (14, 84)]
    assert [line["member_index"] for line in result["member_readings"]] == [1, 0]
    assert result["sourceMembers"] == region["sourceMembers"]
    assert result["member_readings"][0]["crop_box"] == [58, 18, 14, 84]
    assert result["erasure_authority"] is False


def test_reader_exclusion_retains_members_without_recognition():
    class Recognizer:
        def recognize(self, crop): pytest.fail("Reader exclusion must not infer")
    region = {"id": "excluded", "readerExcluded": True,
              "sourceMembers": [{"polygon": [[1, 1], [10, 1], [10, 30], [1, 30]], "score": .9}]}
    result = probe.recognize_source_members(Recognizer(), Image.new("RGB", (40, 40)), region)
    assert result["ja"] == ""
    assert result["member_readings"][0]["status"] == "reader_excluded"
    assert len(result["sourceMembers"]) == 1


def test_member_recognition_without_decoder_metadata_does_not_invent_confidence():
    class Recognizer:
        def recognize(self,crop):return "「…♡」"
    result=probe.recognize_source_members(Recognizer(),Image.new("RGB",(40,40)),
        {"id":"line","sourceMembers":[{"polygon":[[2,2],[12,2],[12,35],[2,35]],"score":.7}]})
    assert result["ja"]=="「…♡」"
    assert result["member_readings"][0]["decode"] is None


def test_empty_member_output_keeps_its_source_and_other_members_punctuation():
    region = {"id": "source", "sourceMembers": [
        {"polygon": [[3, 3], [30, 3], [30, 12], [3, 12]], "score": .4},
        {"polygon": [[3, 20], [30, 20], [30, 30], [3, 30]], "score": .8}]}
    class Recognizer:
        last_decode = {"eos": True, "blank": True}
        def __init__(self): self.values = iter(["", "「…  」"])
        def recognize(self, crop): return next(self.values)
    result = probe.recognize_source_members(Recognizer(), Image.new("RGB", (40, 40)), region)
    assert result["ja"] == "「…  」"
    assert len(result["member_readings"]) == 2
    assert result["member_readings"][0]["raw_text"] == ""
    assert result["member_readings"][0]["source"]["score"] == .4


@pytest.mark.parametrize("polygon", [None, [[1, 1]], [[True, 1], [10, 1], [10, 30], [1, 30]],
    [[-1, 1], [10, 1], [10, 30], [-1, 30]], [[1, 1], [1, 1], [1, 30], [1, 30]],
    [[1, 1], [float("nan"), 1], [10, 30], [1, 30]]])
def test_invalid_member_geometry_is_not_replaced_with_gold_or_union_box(polygon):
    class Recognizer:
        def recognize(self, crop): pytest.fail("Invalid source must not infer")
    with pytest.raises(ValueError, match="polygon"):
        probe.recognize_source_members(Recognizer(), Image.new("RGB", (40, 40)),
            {"id": "source", "bbox": [0, 0, 40, 40], "sourceMembers": [{"polygon": polygon}]})


def test_source_halo_is_clipped_without_rotation_or_background_reconstruction():
    image = Image.new("RGB", (20, 30), "white")
    image.putpixel((0, 0), (12, 34, 56))
    image.putpixel((1, 2), (90, 80, 70))
    class Recognizer:
        last_decode = {}
        def recognize(self, crop):
            assert crop.size == (12, 30)
            assert crop.getpixel((0, 0)) == (12, 34, 56)
            assert crop.getpixel((1, 2)) == (90, 80, 70)
            return "縦"
    result = probe.recognize_source_members(Recognizer(), image,
        {"id": "edge", "sourceMembers": [{"polygon": [[0, 0], [10, 0], [10, 30], [0, 30]]}]})
    assert result["ja"] == "縦"
