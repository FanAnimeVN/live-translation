"""Single-variable resize experiment; not evidence of OCR/Fast parity."""
import importlib.util
from pathlib import Path
import sys

import pytest
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("hayai_tensor_resize_probe", SCRIPTS / "probe_hayai_tensor_resize.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_resize_keeps_rgb_channels_and_pixels_when_geometry_is_unchanged():
    image = Image.new("RGB", (32, 48), (19, 111, 237))
    result = probe.tensor_resize(image, 48, 32)
    assert result.mode == "RGB" and result.size == image.size
    assert result.tobytes() == image.tobytes()


def test_resize_preserves_constant_channels_and_does_not_mutate_source():
    image = Image.new("RGB", (31, 57), (0, 128, 255))
    before = image.tobytes()
    result = probe.tensor_resize(image, 80, 48)
    assert result.size == (48, 80)
    assert result.getextrema() == ((0, 0), (128, 128), (255, 255))
    assert image.tobytes() == before


@pytest.mark.parametrize("size", [(0, 32), (32, 0), (32.0, 32), (True, 32), (9000, 32)])
def test_resize_rejects_unbounded_or_ambiguous_dimensions(size):
    with pytest.raises(ValueError):
        probe.tensor_resize(Image.new("RGB", (32, 48)), *size)


def test_wrapper_changes_only_resize_and_keeps_slow_patch_normalization(monkeypatch):
    calls = []
    source = Image.new("RGB", (31, 57), (10, 20, 30))
    def slow(**kwargs):
        calls.append(kwargs)
        return {"pixel_values": "slow-normalized-and-patched"}
    monkeypatch.setattr(probe, "target_size", lambda height, width, patches: (80, 48))
    processor = probe.TensorResizeProcessor(slow)
    result = processor(images=[source], max_num_patches=512, return_tensors="pt")
    assert result == {"pixel_values": "slow-normalized-and-patched"}
    assert len(calls) == 1
    kwargs = calls[0]
    assert set(kwargs) == {"images", "max_num_patches", "return_tensors", "do_resize"}
    assert kwargs["max_num_patches"] == 512 and kwargs["return_tensors"] == "pt"
    assert kwargs["do_resize"] is False
    assert kwargs["images"][0].size == (48, 80)


@pytest.mark.parametrize("kwargs", [
    {"images": [], "max_num_patches": 512, "return_tensors": "pt"},
    {"images": [Image.new("RGB", (32, 48))] * 2, "max_num_patches": 512, "return_tensors": "pt"},
    {"images": [Image.new("L", (32, 48))], "max_num_patches": 512, "return_tensors": "pt"},
    {"images": [Image.new("RGB", (32, 48))], "max_num_patches": 513, "return_tensors": "pt"},
    {"images": [Image.new("RGB", (32, 48))], "max_num_patches": 512, "return_tensors": "np"},
])
def test_wrapper_rejects_changes_outside_fixed_comparison_contract(kwargs):
    with pytest.raises(ValueError):
        probe.TensorResizeProcessor(lambda **_: pytest.fail("Invalid input reached processor"))(**kwargs)


def test_tensor_recipe_does_not_import_or_replace_production_backend(monkeypatch):
    class Model:
        pass
    calls = []
    def baseline_load(self):
        calls.append("load")
        self.model = Model()
        self.processor = "unchanged-slow-processor"
    monkeypatch.setattr(probe.HayaiRecognizer, "load", baseline_load)
    engine = probe.TensorResizeHayaiRecognizer(patches=512, threads=4)
    engine.load()
    assert isinstance(engine.processor, probe.TensorResizeProcessor)
    assert engine.processor.slow == "unchanged-slow-processor"
    assert engine.details["production_default"] is False
    assert engine.details["processor_upstream_parity"] is False
    engine.load()
    assert calls == ["load"]


def test_real_patch_processor_preserves_rgb_order_mask_and_zero_padding(monkeypatch):
    import numpy as np
    import torch
    from transformers import Siglip2ImageProcessor
    yy, xx = np.indices((48, 32))
    colors = np.stack(((xx * 13) % 256, (yy * 7) % 256, (xx + yy * 3) % 256), axis=-1).astype("uint8")
    image = Image.fromarray(colors)
    monkeypatch.setattr(probe, "target_size", lambda *_: (48, 32))
    slow = Siglip2ImageProcessor()
    wrapped = probe.TensorResizeProcessor(slow)
    result = wrapped(images=[image], max_num_patches=256, return_tensors="pt")
    expected = slow(images=[image], max_num_patches=256, return_tensors="pt", do_resize=False)
    assert result["pixel_values"].shape == (1, 256, 768)
    for key in ("pixel_values", "pixel_attention_mask", "spatial_shapes"):
        assert torch.equal(result[key], expected[key])
    assert result["spatial_shapes"].tolist() == [[3, 2]]
    assert result["pixel_attention_mask"][0, :6].tolist() == [1] * 6
    assert torch.count_nonzero(result["pixel_values"][0, 6:]).item() == 0
    # A coordinate-coded pixel at (x=19,y=34) is in patch (1,2), offset (3,2).
    p = 2 * 2 + 1
    q = (2 * 16 + 3) * 3
    expected_rgb = (torch.tensor(colors[34, 19].astype("float64") / 255, dtype=torch.float32) - .5) / .5
    assert torch.equal(result["pixel_values"][0, p, q:q+3], expected_rgb)


def test_pair_audit_labels_the_actual_numeric_threshold():
    import torch
    from transformers import Siglip2ImageProcessor
    image = Image.new("RGB", (32, 48), (19, 111, 237))
    processor = probe.TensorResizeProcessor(Siglip2ImageProcessor(), audit_pairs=True)
    result = processor(images=[image], max_num_patches=256, return_tensors="pt")
    valid = int(result["pixel_attention_mask"].sum())
    assert torch.count_nonzero(result["pixel_values"][0, valid:]).item() == 0
    assert len(processor.pairs) == 1
    pair = processor.pairs[0]
    assert pair["geometry_mask_equal"] is True
    assert pair["values_above_1e_minus_6"] == 0
    assert "values_above_1e6" not in pair
