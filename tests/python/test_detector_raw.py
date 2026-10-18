from types import SimpleNamespace
import numpy as np
import pytest
from PIL import Image
from manga_live.errors import AppError
from manga_live.ocr import PaddleDetector,polygon


def detector_with_fake_model(tmp_path):
    (tmp_path/"inference.pdiparams").write_bytes(b"test-only")
    detector=PaddleDetector(tmp_path);calls=[]
    def predict(pixels,**options):
        calls.append((pixels,options))
        return [SimpleNamespace(json={"res":{"dt_polys":[polygon([10,10,12,30])],"dt_scores":[.9]}})]
    detector.model=SimpleNamespace(predict=predict)
    return detector,calls


def test_raw_detection_preserves_default_preprocessing_and_source_geometry(tmp_path):
    detector,calls=detector_with_fake_model(tmp_path)
    image=Image.new("RGB",(100,100),(20,40,60))
    lines=detector.detect_raw(image)
    assert lines==[{"polygon":polygon([10,10,12,30]),"score":.9}]
    assert calls[0][1]=={"batch_size":1},"Do not silently change production detector resize"
    assert np.array_equal(calls[0][0][0,0],[60,40,20])
    assert image.getpixel((0,0))==(20,40,60)
    assert not hasattr(detector,"last_evidence"),"Do not persist per-page private geometry in runtime"


def test_resize_probe_is_explicit_and_does_not_affect_next_default_call(tmp_path):
    detector,calls=detector_with_fake_model(tmp_path);image=Image.new("RGB",(100,100),"white")
    detector.detect_raw(image,limit_side_len=1280)
    detector.detect(image)
    assert calls[0][1]=={"batch_size":1,"limit_side_len":1280}
    assert calls[1][1]=={"batch_size":1}


def test_forced_resize_mode_is_explicit_not_an_implicit_max_cap(tmp_path):
    detector,calls=detector_with_fake_model(tmp_path);image=Image.new("RGB",(100,100),"white")
    detector.detect_raw(image,limit_side_len=1600,limit_type="resize_long")
    detector.detect_raw(image)
    assert calls[0][1]=={"batch_size":1,"limit_side_len":1600,"limit_type":"resize_long"}
    assert calls[1][1]=={"batch_size":1}


def test_box_threshold_probe_reaches_upstream_gate_and_does_not_change_next_default(tmp_path):
    (tmp_path/"inference.pdiparams").write_bytes(b"test-only")
    detector=PaddleDetector(tmp_path);calls=[]
    def predict(pixels,**options):
        calls.append(options)
        candidates=[(polygon([10,10,12,30]),.45),(polygon([30,10,12,30]),.8)]
        kept=[(poly,score) for poly,score in candidates if score>=options.get("box_thresh",.6)]
        return [SimpleNamespace(json={"res":{"dt_polys":[p for p,s in kept],
                                      "dt_scores":[s for p,s in kept]}})]
    detector.model=SimpleNamespace(predict=predict)
    image=Image.new("RGB",(100,100),"white")
    lines=detector.detect_raw(image,box_threshold=.4)
    assert [line["score"] for line in lines]==[.45,.8]
    assert detector.detect_raw(image)==[{"polygon":polygon([30,10,12,30]),"score":.8}]
    assert calls==[{"batch_size":1,"box_thresh":.4},{"batch_size":1}]


def test_failed_probe_does_not_leave_options_on_next_default_call(tmp_path):
    detector,calls=detector_with_fake_model(tmp_path)
    def predict(pixels,**options):
        calls.append(options)
        if "box_thresh" in options:raise RuntimeError("fixture inference failure")
        return []
    detector.model=SimpleNamespace(predict=predict)
    image=Image.new("RGB",(100,100),"white")
    with pytest.raises(RuntimeError,match="fixture inference"):
        detector.detect_raw(image,box_threshold=.4)
    assert detector.detect_raw(image)==[]
    assert calls==[{"batch_size":1,"box_thresh":.4},{"batch_size":1}]


@pytest.mark.parametrize("value",[True,63,2049,1280.0,"1280"])
def test_invalid_probe_dimensions_fail_before_inference(tmp_path,value):
    detector,calls=detector_with_fake_model(tmp_path)
    with pytest.raises(AppError) as error:detector.detect_raw(Image.new("RGB",(100,100)),limit_side_len=value)
    assert error.value.code=="DETECTOR_SIZE" and calls==[]


@pytest.mark.parametrize("size,mode",[(None,"resize_long"),(1280,"min"),(1280,True),(1280,1)])
def test_invalid_resize_mode_fails_before_inference(tmp_path,size,mode):
    detector,calls=detector_with_fake_model(tmp_path)
    with pytest.raises(AppError) as error:
        detector.detect_raw(Image.new("RGB",(100,100)),limit_side_len=size,limit_type=mode)
    assert error.value.code=="DETECTOR_SIZE" and calls==[]


@pytest.mark.parametrize("value",[True,.34,.81,".45",float("nan"),float("inf")])
def test_invalid_box_threshold_fails_before_inference(tmp_path,value):
    detector,calls=detector_with_fake_model(tmp_path)
    with pytest.raises(AppError) as error:detector.detect_raw(Image.new("RGB",(100,100)),box_threshold=value)
    assert error.value.code=="DETECTOR_THRESHOLD" and calls==[]
