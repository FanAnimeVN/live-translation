"""Validate experiment isolation; these tests do not certify OCR accuracy."""
import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest
from PIL import Image


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("resampling_probe", SCRIPTS / "probe_ocr_resampling.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.mark.parametrize("raises", [False, True])
def test_resampling_changes_one_field_and_always_restores_it(raises):
    processor = SimpleNamespace(resample=Image.Resampling.BILINEAR, do_resize=True, size={"height":224,"width":224})
    recognizer = SimpleNamespace(processor=processor)
    original = vars(processor).copy()
    try:
        with probe.resampling(recognizer, Image.Resampling.LANCZOS):
            assert processor.resample == Image.Resampling.LANCZOS
            assert processor.do_resize is True and processor.size == original["size"]
            if raises:
                raise RuntimeError("controlled failure")
    except RuntimeError:
        assert raises
    assert vars(processor) == original


def test_invalid_output_destination_is_rejected_before_model_load(tmp_path, monkeypatch):
    # tmp_path may itself be under the real artifacts directory when Windows'
    # default temp ACL is unavailable. Keep the tested boundary explicit.
    monkeypatch.setattr(probe, "ROOT", tmp_path / "isolated-project")
    monkeypatch.setattr(probe, "MangaEngine", lambda *args: pytest.fail("Must reject output before loading model"))
    with pytest.raises(ValueError, match="gitignored artifacts"):
        probe.run(SimpleNamespace(output=tmp_path / "report.json"))


def test_controls_include_true_partial_quotes_vertical_pacing_and_blank():
    if not Path("C:/Windows/Fonts/YuGothM.ttc").is_file():
        pytest.skip("Author-created control font is Windows-specific")
    cases = {name:(crop,reference) for name,crop,reference in probe.controls()}
    assert len(cases) == 13 and set(f"r{idx:03}" for idx in range(4)) <= cases.keys()
    assert cases["authored-real-quotes"][1] == "「待って！」"
    assert cases["opening-quote"][1].startswith("「") and "」" not in cases["opening-quote"][1]
    assert cases["closing-quote"][1].endswith("」") and "「" not in cases["closing-quote"][1]
    assert cases["multiline-real-quotes"][1] == "「明日は来なくてもいい。」"
    assert cases["multiline-opening-quote"][1] == "「姉ちゃん、まだ帰らないの？"
    assert cases["multiline-closing-quote"][1] == "あとで行くから。待っていて。」"
    assert cases["expressive"][1] == "わ…た…し…？"
    assert cases["authored-vertical"][0].height > cases["authored-vertical"][0].width
    assert cases["blank"][1] == "" and cases["blank"][0].getextrema() == ((255,255),)*3
