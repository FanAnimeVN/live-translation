"""External detector boundary: real decoding, RAM masks, authored forward only."""
from pathlib import Path
import sys
import numpy as np
from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from benchmark_bubble_masks import ExperimentalBubbleMasks


def test_letterbox_inverse_and_per_instance_crop_do_not_turn_global_prototypes_into_page_masks():
    proposals = np.zeros((1, 37, 21504), np.float32)
    prototypes = np.zeros((1, 32, 256, 256), np.float32)
    proposals[0, :5, 0] = [512, 300, 128, 200, .9]
    proposals[0, 5, 0] = 1
    prototypes[0, 0] = 10  # globally positive prototype must still be cropped
    def forward(inputs):
        tensor = inputs["images"]
        assert tensor.shape == (1, 3, 1024, 1024)
        assert np.allclose(tensor[0, :, 0, 0], 114/255)
        assert np.allclose(tensor[0, :, 0, 256], [11/255, 23/255, 37/255])
        return [proposals, prototypes]
    result = ExperimentalBubbleMasks(forward=forward).segment(Image.new("RGB", (512, 1024), (11, 23, 37)))
    assert len(result["instances"]) == 1
    instance = result["instances"][0]
    assert instance["bbox"] == [192, 200, 128, 200]
    assert instance["mask"].shape == (200, 128)
    assert instance["mask"].dtype == np.uint8 and instance["mask"].all()
    assert result["preprocess"]["pad_left_top"] == [256, 0]
    assert instance["erasure_authority"] is False
    assert instance["memory_authority"] is False


def test_container_mask_not_its_rectangle_controls_column_grouping_and_preserves_all_sources():
    from benchmark_bubble_masks import group_with_container_masks
    def row(ident, x):
        return {"id": ident, "bbox": [x-3, 37, 20, 76], "order": 0,
                "sourceMembers": [{"polygon": [[x, 40], [x+14, 40], [x+14, 110], [x, 110]], "score": .8}]}
    rows = [row("left", 50), row("right", 110)]
    image = Image.new("RGB", (400, 400), "white")
    # Two masks share an identical outer rectangle but cover different text.
    left, right = np.zeros((140, 150), np.uint8), np.zeros((140, 150), np.uint8)
    left[:, :65], right[:, 65:] = 1, 1
    boxes = [{"index": i, "bbox": [20, 20, 150, 140], "mask": mask, "score": .9}
             for i, mask in enumerate((left, right))]
    separate = group_with_container_masks(image, rows, boxes, page="authored")
    assert len(separate["regions"]) == 2
    assert {r["owner_instance"] for r in separate["regions"]} == {0, 1}
    together = group_with_container_masks(image, rows, [dict(boxes[0], mask=np.ones((140, 150), np.uint8))], page="authored")
    assert len(together["regions"]) == 1
    assert len(together["regions"][0]["sourceMembers"]) == 2
    assert {r["id"] for r in together["regions"][0]["source_member_refs"]} == {"left", "right"}
    assert together["regions"][0]["erasure_authority"] is False
    assert together["regions"][0]["memory_authority"] is False


def test_offline_inference_cannot_be_combined_with_model_provisioning(tmp_path, monkeypatch):
    import urllib.request
    import benchmark_bubble_masks as probe
    monkeypatch.setattr(probe, "MODEL_PATH", tmp_path / "absent.onnx")
    monkeypatch.setattr(sys, "argv", ["benchmark_bubble_masks.py", "--folder", "private", "--primary", "source.json",
                                    "--output", "new.json", "--fetch-model"])
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("network before validation")))
    with pytest.raises(SystemExit):
        probe.main()
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("kind", ["shape", "nan", "score", "dtype", "extra", "overflow"])
def test_invalid_external_output_cannot_become_a_container_mask(kind):
    proposals = np.zeros((1, 37, 21504), np.float32)
    prototypes = np.zeros((1, 32, 256, 256), np.float32)
    proposals[0, :5, 0] = [512, 300, 128, 200, .9]
    values = [proposals, prototypes]
    if kind == "shape": values[0] = proposals[:, :, :10]
    elif kind == "nan": prototypes[0, 0, 0, 0] = np.nan
    elif kind == "score": proposals[0, 4, 0] = 2
    elif kind == "dtype": values[0] = proposals.astype(np.float64)
    elif kind == "extra": values.append(prototypes)
    else:
        proposals[0, 5, 0] = np.finfo(np.float32).max
        prototypes[0, 0] = np.finfo(np.float32).max
    with np.errstate(over="ignore", invalid="ignore"), pytest.raises(ValueError):
        ExperimentalBubbleMasks(forward=lambda _: values).segment(Image.new("RGB", (512, 1024)))


def test_ocr_isolation_preserves_source_pixels_and_refuses_even_one_uncovered_source_pixel():
    from benchmark_bubble_masks import prepare_container_ocr_crop
    image = Image.new("RGB", (100, 100), (23, 47, 89))
    before = image.tobytes()
    row = {"id": "r", "sourceMembers": [{"polygon": [[40, 40], [49, 40], [49, 49], [40, 49]], "score": .9}]}
    mask = np.ones((30, 30), np.uint8)
    instances = [{"index": 0, "bbox": [35, 35, 30, 30], "mask": mask}]
    decisions = [{"source": {"id": "r", "member_index": 0}, "owner": 0, "polygon_pixels": 100,
                  "coverage": [{"instance": 0, "pixels": 100, "fraction": 1.0}]}]
    isolated = prepare_container_ocr_crop(image, row, [30, 30, 40, 40], decisions, instances)
    assert isolated["crop"].getpixel((0, 0)) == (255, 255, 255)
    assert isolated["crop"].getpixel((15, 15)) == (23, 47, 89)
    assert image.tobytes() == before
    decisions[0]["coverage"][0].update(pixels=99, fraction=.99)
    refused = prepare_container_ocr_crop(image, row, [30, 30, 40, 40], decisions, instances)
    assert refused["crop"] is None and refused["reason"] == "incomplete_source_coverage"
    decisions[0]["coverage"][0].update(pixels=100, fraction=1.0)
    mask[10, 10] = 0  # actual pixel support wins over a stale numeric receipt
    refused = prepare_container_ocr_crop(image, row, [30, 30, 40, 40], decisions, instances)
    assert refused["crop"] is None and refused["reason"] == "incomplete_source_coverage"


def test_prepared_ocr_inputs_cannot_be_applied_to_a_different_same_size_crop():
    from benchmark_bubble_masks import IsolatedCropEngine
    import hashlib
    source = Image.new("RGB", (20, 20), "white")
    class Recognizer:
        def recognize_many(self, crops):
            return ["検証" for _ in crops]
    prepared = [{"crop": None, "source_sha256": hashlib.sha256(source.tobytes()).hexdigest(), "size": source.size}]
    assert IsolatedCropEngine(Recognizer(), prepared).recognize_many([source]) == ["検証"]
    with pytest.raises(ValueError, match="Stale or reordered"):
        IsolatedCropEngine(Recognizer(), prepared).recognize_many([Image.new("RGB", source.size, "black")])


def test_competing_masks_and_reader_exclusions_do_not_force_new_ownership():
    from benchmark_bubble_masks import group_with_container_masks
    from copy import deepcopy
    row = {"id": "r", "bbox": [37, 37, 20, 76], "order": 0,
           "sourceMembers": [{"polygon": [[40, 40], [54, 40], [54, 110], [40, 110]], "score": .8}]}
    rows = [row]
    before = deepcopy(rows)
    masks = [{"index": i, "bbox": [20, 20, 150, 140], "mask": np.ones((140, 150), np.uint8)} for i in range(2)]
    plan = group_with_container_masks(Image.new("RGB", (400, 400)), rows, masks, page="authored")
    assert plan["member_decisions"][0]["owner"] is None
    assert plan["regions"][0]["owner_instance"] is None
    assert plan["regions"][0]["bbox"] == row["bbox"] and rows == before
    row["readerExcluded"] = True
    with pytest.raises(ValueError, match="reader"):
        group_with_container_masks(Image.new("RGB", (400, 400)), rows, masks, page="authored")


def test_missing_segmenter_model_never_downloads(tmp_path, monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("no network")))
    with pytest.raises(ValueError, match="Missing/mismatched"):
        ExperimentalBubbleMasks(tmp_path / "absent.onnx").segment(Image.new("RGB", (100, 200)))
    assert not list(tmp_path.iterdir())
