"""Comparator host-loop contracts; authored arrays only, no weights/network."""
from pathlib import Path
import sys
import threading

import numpy as np
from PIL import Image, ImageDraw
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import baberu_probe_engine as module


def fixture(tokens):
    engine = module.BaberuProbe()
    engine.characters = ["", "", "", "", "「", "…", " ", "」"]
    engine.content_ids = set()
    replies = iter(tokens)
    def result():
        logits = np.zeros((1, 1, 8), np.float32)
        logits[0, 0, next(replies)] = 20
        return [logits, *[np.zeros((1, 1, 1, 1), np.float32) for _ in range(12)]]
    class Vision:
        def run(self, names, feed):
            assert names == ["vision_embeds"] and feed["pixel_values"].shape == (1, 3, 224, 224)
            return [np.zeros((1, 4, 8), np.float32)]
    class Decode:
        def run(self, names, feed):
            assert names is None and feed["input_ids"].shape == (1, 1)
            return result()
    engine.sessions = [Vision(), Decode(), Decode()]
    image = Image.new("RGB", (80, 100), "white")
    ImageDraw.Draw(image).rectangle((20, 20, 40, 40), fill="black")
    return engine, image


def test_comparator_keeps_quotes_ellipsis_and_spacing_without_global_postprocessing():
    engine, image = fixture([4, 5, 6, 7, 2])
    assert engine.recognize(image) == "「… 」"
    assert engine.last_decode == {"eos": True, "run_cap": False, "unknown_token": False, "tokens": 4}


def test_blank_crop_never_loads_weights_and_canceled_crop_never_infers(monkeypatch):
    engine = module.BaberuProbe()
    monkeypatch.setattr(engine, "load", lambda: pytest.fail("Blank crop attempted to load model"))
    assert engine.recognize(Image.new("RGB", (80, 100), "white")) == ""
    engine.cancel.set()
    with pytest.raises(RuntimeError, match="canceled"):
        engine.recognize(Image.new("RGB", (80, 100), "white"))


def test_missing_or_modified_weights_fail_before_session_creation(monkeypatch):
    engine = module.BaberuProbe()
    monkeypatch.setattr(module, "verified", lambda *_: False)
    with pytest.raises(ValueError, match="Missing/unverified"):
        engine.load()
    assert engine.sessions is None


@pytest.mark.parametrize("threads", [0, 9, True, 1.5])
def test_threads_cannot_overallocate_or_be_coerced(threads):
    with pytest.raises(ValueError, match="threads"):
        module.BaberuProbe(threads)
