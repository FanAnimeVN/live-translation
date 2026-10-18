import json
import sys
import pytest
from manga_live.errors import AppError
from manga_live.runtime_diagnostics import detector_probe


def test_probe_uses_only_a_fixed_blank_image_and_no_user_profile(tmp_path,monkeypatch,capsys):
    seen=[]
    class Detector:
        def __init__(self,folder,threads):seen.append((folder,threads))
        def detect(self,image):
            assert image.size==(64,64) and image.getpixel((0,0))==(255,255,255)
            return []
    monkeypatch.setattr("manga_live.ocr.PaddleDetector",Detector)
    assert detector_probe(tmp_path)==0
    report=json.loads(capsys.readouterr().out)
    assert seen==[(tmp_path/"detector",4)] and report["passed"]
    assert not report["reader_data_access"] and not report["cloud"]


def test_probe_has_a_precise_runtime_failure_signal(tmp_path,monkeypatch,capsys):
    class Detector:
        def __init__(self,*args,**kwargs):raise RuntimeError("authored missing dependency")
    monkeypatch.setattr("manga_live.ocr.PaddleDetector",Detector)
    assert detector_probe(tmp_path)==1
    report=json.loads(capsys.readouterr().out)
    assert not report["passed"] and report["error_type"]=="RuntimeError"
    assert "authored missing dependency" in report["traceback"]


def test_native_origin_cannot_enable_cli_exception_diagnostics(tmp_path,monkeypatch):
    from manga_live.host import main
    config=tmp_path/"config.json";config.write_text('{"models":"unused-models"}')
    monkeypatch.setattr(sys,"argv",["host","chrome-extension://"+"a"*32+"/",
        "--config",str(config),"--runtime-probe","detector"])
    monkeypatch.setattr("manga_live.runtime_diagnostics.detector_probe",
        lambda path:pytest.fail("Native requests must not enter the CLI diagnostic branch"))
    with pytest.raises(AppError) as error:main()
    assert error.value.code=="ORIGIN"
