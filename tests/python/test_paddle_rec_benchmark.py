"""Comparator contracts without model imports, downloads or private images."""
import sys
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from benchmark_paddle_rec import checked_prediction, ordered_lines, score_rows, validate_model, distribute_lines
from manga_live.ocr import polygon


def test_native_prediction_keeps_real_quotes_and_low_score_text():
    assert checked_prediction({"res": {"rec_text": "「待って！」", "rec_score": .1}}) == ("「待って！」", .1)
    assert checked_prediction({"rec_text": "", "rec_score": 0}) == ("", 0.)


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -1., 1.01, True, "0.5", None])
def test_native_prediction_rejects_invalid_ctc_score(score):
    with pytest.raises(ValueError):
        checked_prediction({"rec_text": "待って", "rec_score": score})


@pytest.mark.parametrize("payload", [None, [], {"res":None}, {"res":[]}, {"rec_text":7,"rec_score":.5}])
def test_native_prediction_rejects_invalid_response_shape(payload):
    with pytest.raises(ValueError):
        checked_prediction(payload)


def test_vertical_columns_read_right_to_left_without_reference_text():
    left = {"id": "l", "polygon": polygon([5,0,10,90])}
    right = {"id": "r", "polygon": polygon([30,10,10,70])}
    rows, orientation = ordered_lines([left, right])
    assert rows == [right, left] and orientation == "vertical-rtl"


def test_horizontal_lines_read_top_down_not_rtl_across_different_lines():
    lower = {"id": "l", "polygon": polygon([30,40,100,10])}
    upper = {"id": "u", "polygon": polygon([10,10,90,10])}
    rows, orientation = ordered_lines([lower, upper])
    assert rows == [upper, lower] and orientation == "horizontal-top-down"


def test_no_detected_lines_count_as_missing_text_not_dropped_from_cer():
    report = score_rows([{"characters": 5,"edits":5,"lines":[],"detector_ms":2,"recognition_ms":0},
                         {"characters": 5,"edits":0,"lines":[{}],"detector_ms":2,"recognition_ms":1}])
    assert report["crops"] == 2 and report["cer"] == .5 and report["exact_count"] == 1
    assert report["crops_without_lines"] == 1 and report["p95_crop_detector_recognition_ms"] == 3


def test_local_recognizer_cannot_start_with_unpinned_model(tmp_path):
    with pytest.raises(ValueError, match="explicit --fetch-model"):
        validate_model(tmp_path)


def test_page_line_binding_uses_no_gold_and_never_duplicates_a_source_polygon():
    regions=[{"id":"large","bbox":[0,0,80,100]}, {"id":"local","bbox":[30,0,25,90]}]
    shared={"polygon":polygon([35,0,10,70])}
    left={"polygon":polygon([5,0,10,70])}
    outside={"polygon":polygon([180,0,10,70])}
    groups,unmatched=distribute_lines(regions,[shared,left,outside])
    assert groups=={"large":[left],"local":[shared]} and unmatched==[outside]


def test_no_group_does_not_discard_raw_lines():
    line={"polygon":polygon([5,0,10,70])}
    assert distribute_lines([],[line])==({},[line])
