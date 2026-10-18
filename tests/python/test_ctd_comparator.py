import sys
from pathlib import Path
import numpy as np
from PIL import Image
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from benchmark_ctd import prepare_image, split_outputs, block_detections, ExperimentalCtd, INPUT_SIZE


def maps():
    return [np.zeros((1, 10, 7), dtype="float32"),
        np.zeros((1, 1, INPUT_SIZE, INPUT_SIZE), dtype="float32"),
        np.zeros((1, 2, INPUT_SIZE, INPUT_SIZE), dtype="float32")]


def test_comparator_padding_preserves_rgb_and_does_not_stretch_source():
    image = Image.new("RGB", (80, 160), (11, 23, 37))
    padded, resized = prepare_image(image)
    assert resized == (512, 1024)
    assert tuple(padded[0, 0]) == (11, 23, 37)
    assert not padded[:, 512:].any()
    assert padded.shape == (1024, 1024, 3)


def test_model_outputs_are_identified_by_shape_not_layer_order():
    blocks, mask, lines = maps()
    actual = split_outputs([lines, blocks, mask])
    assert actual[0] is blocks and actual[1] is mask and actual[2] is lines


@pytest.mark.parametrize("failure", ["missing", "duplicated", "wrong_size", "nan", "probability"])
def test_invalid_model_output_cannot_be_used_as_a_glyph_mask(failure):
    outputs = maps()
    if failure == "missing":
        outputs.pop()
    elif failure == "duplicated":
        outputs.append(outputs[1])
    elif failure == "wrong_size":
        outputs[2] = outputs[2][:, :, :32, :32]
    elif failure == "nan":
        outputs[2][0, 0, 0, 0] = float("nan")
    else:
        outputs[1][0, 0, 0, 0] = 1.1
    with pytest.raises(ValueError):
        split_outputs(outputs)


def test_block_coordinates_unpad_clamp_and_suppress_duplicates():
    blocks = np.array([[[256, 512, 200, 300, .9, 0, .95],
        [256, 512, 200, 300, .8, 0, .9],
        [900, 500, 100, 100, .9, 0, .9]]], dtype="float32")
    detections = block_detections(blocks, (512, 1024), (80, 160))
    assert len(detections) == 1, "The box in right padding is not source text"
    box = detections[0]["polygon"]
    assert box[0] == [24.375, 56.5625]
    assert box[2] == [55.625, 103.4375]


def test_missing_model_does_not_fetch_or_change_production_defaults(tmp_path):
    detector = ExperimentalCtd(tmp_path / "missing.onnx")
    with pytest.raises(ValueError, match="missing or checksum"):
        detector.detect(Image.new("RGB", (80, 80), "white"))
    assert not list(tmp_path.iterdir())
    assert detector.details["uses_mask_for_erasure"] is False
    assert detector.details["distribution_cleared"] is False


def test_onnxruntime_backend_is_explicit_and_keeps_comparator_only(tmp_path):
    detector = ExperimentalCtd(tmp_path / "missing.onnx", backend="onnxruntime")
    assert detector.backend == "onnxruntime"
    assert detector.details["backend"] == "onnxruntime"
    with pytest.raises(ValueError, match="missing or checksum"):
        detector.detect(Image.new("RGB", (80, 80), "white"))


def test_detector_report_retains_source_polygons_not_just_a_count(tmp_path):
    # Substitute only the external model-inference boundary. The adapter,
    # coordinate mapping, NMS, paper grouping and evidence path are real.
    outputs = maps()
    outputs[0][0, 0] = [256, 512, 200, 300, .9, 0, .95]

    class AuthoredNetwork:
        def setInput(self, blob):
            pass

        def getUnconnectedOutLayersNames(self):
            return ["blocks", "mask", "lines"]

        def forward(self, names):
            return outputs

    detector = ExperimentalCtd(tmp_path / "unused.onnx", output="blocks")
    detector.model = AuthoredNetwork()
    regions = detector.detect(Image.new("RGB", (80, 160), "white"))
    assert len(regions) == 1
    assert regions[0]["sourceMembers"] == [{
        "polygon": [[24.375, 56.5625], [55.625, 56.5625],
                    [55.625, 103.4375], [24.375, 103.4375]],
        "score": pytest.approx(.855)
    }]
    evidence = detector.last_evidence
    assert evidence["raw_detection_count"] == 1
    assert evidence["raw_detections"][0]["polygon"] == regions[0]["sourceMembers"][0]["polygon"]
    assert evidence["raw_detections"][0]["score"] == pytest.approx(.855)
    assert evidence["uses_mask_for_erasure"] is False
    # Raw source evidence must not alias either a returned Region or a backend
    # array that a later inference can reuse.
    regions[0]["sourceMembers"][0]["polygon"][0][0] = 0
    outputs[0][0, 0, 0] = 0
    assert evidence["raw_detections"][0]["polygon"][0] == [24.375, 56.5625]


def test_block_source_retains_location_class_and_raw_scores_after_nms():
    blocks = np.array([[[256, 512, 200, 300, .9, 0, .95],
                        [256, 512, 200, 300, .8, .9, 0]]], dtype="float32")
    detections = block_detections(blocks, (512, 1024), (80, 160))
    assert len(detections) == 1
    source = detections[0]["upstream_block"]
    assert source["candidate_index"] == 0
    assert source["class_index"] == 1
    assert source["raw_prediction"] == pytest.approx([256, 512, 200, 300, .9, 0, .95])
    assert source["objectness"] == pytest.approx(.9)
    assert source["class_probabilities"] == pytest.approx([0, .95])
    assert "role" not in detections[0] and "irrelevant" not in detections[0]
    blocks[:] = 0
    assert source["raw_prediction"][0] == 256
