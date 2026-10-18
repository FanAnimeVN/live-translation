"""Private comparator contract; no model download, inference or corpus needed."""
import sys
from pathlib import Path
import numpy as np
from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from benchmark_comic_blocks import (prepare_image, checked_outputs, text_detections,
    ExperimentalComicBlocks, checked_contract, ONNX_INPUTS, ONNX_OUTPUTS)


def outputs():
    return [np.array([[0, 1, 2]], dtype="int64"),
        np.array([[[1, 2, 70, 140], [10, 20, 30, 60], [31, 20, 60, 80]]], dtype="float32"),
        np.array([[.95, .9, .8]], dtype="float32")]


def test_rgb_square_stretch_and_width_height_order_match_author_contract():
    data = prepare_image(Image.new("RGB", (80, 160), (11, 23, 37)))
    assert set(data) == {"images", "orig_target_sizes"}
    assert data["images"].shape == (1, 3, 640, 640)
    assert data["images"].dtype == np.float32
    assert np.allclose(data["images"][0, :, 0, 0], [11/255, 23/255, 37/255])
    assert data["orig_target_sizes"].dtype == np.int64
    assert data["orig_target_sizes"].tolist() == [[80, 160]]


def test_observed_pinned_onnx_metadata_is_not_a_generic_rtdetr_guess():
    checked_contract(ONNX_INPUTS, ONNX_OUTPUTS)
    with pytest.raises(ValueError): checked_contract(ONNX_INPUTS[::-1], ONNX_OUTPUTS)
    with pytest.raises(ValueError): checked_contract(ONNX_INPUTS, ONNX_OUTPUTS[::-1])
    with pytest.raises(ValueError): checked_contract([(name, kind, [1, *shape[1:]]) for name, kind, shape in ONNX_INPUTS], ONNX_OUTPUTS)


def test_location_classes_preserved_but_bubble_boxes_are_not_ocr_or_erasure():
    raw = checked_outputs(outputs())
    detections, evidence = text_detections(raw, (80, 160))
    assert len(detections) == 2
    assert [r["label"] for r in evidence] == [0, 1, 2]
    assert [d["detectorClass"] for d in detections] == ["text_bubble", "text_free"]
    assert all("balloon" not in d and "mask" not in d for d in detections)
    assert detections[1]["polygon"] == [[31, 20], [60, 20], [60, 80], [31, 80]]


@pytest.mark.parametrize("kind", ["length", "nan", "bad_class", "float_class", "bad_score", "bad_shape", "extra"])
def test_invalid_output_fails_closed_without_truncating_zip(kind):
    values = outputs()
    if kind == "length": values[2] = values[2][:, :2]
    elif kind == "nan": values[1][0, 1, 0] = np.nan
    elif kind == "bad_class": values[0][0, 1] = 7
    elif kind == "float_class": values[0] = values[0].astype("float32")
    elif kind == "bad_score": values[2][0, 1] = 1.1
    elif kind == "bad_shape": values[1] = values[1][:, :, :3]
    else: values.append(values[2])
    with pytest.raises(ValueError): checked_outputs(values)


def test_clamp_does_not_create_text_in_padding_or_suppress_text_free_by_semantics():
    values = outputs()
    values[1][0, 1] = [-2, 20, 30, 60]
    values[1][0, 2] = [90, 20, 100, 80]
    detections, evidence = text_detections(checked_outputs(values), (80, 160))
    assert len(detections) == 1 and detections[0]["polygon"][0] == [0, 20]
    assert evidence[2]["rejected_geometry"] is True


def test_overlapping_predictions_are_not_merged_or_filtered_by_gold():
    values = outputs(); values[1][0, 2] = values[1][0, 1]
    detections, _ = text_detections(checked_outputs(values), (80, 160))
    assert len(detections) == 2


def test_missing_model_never_downloads_and_does_not_import_runtime(tmp_path):
    detector = ExperimentalComicBlocks(tmp_path / "absent.onnx")
    with pytest.raises(ValueError, match="missing or checksum"):
        detector.detect(Image.new("RGB", (80, 160), "white"))
    assert not list(tmp_path.iterdir())
    assert detector.details["uses_box_for_erasure"] is False
    assert detector.details["production_default"] is False


@pytest.mark.parametrize("threads", [0, 9, True])
def test_unbounded_threads_rejected(threads):
    with pytest.raises(ValueError): ExperimentalComicBlocks("missing.onnx", threads)
