"""Isolated pinned comparator invariants; no real weights or cloud imports."""
from contextlib import nullcontext
import importlib.util
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import pytest
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0,str(SCRIPTS))
spec = importlib.util.spec_from_file_location("hayai_comparator",SCRIPTS / "benchmark_hayai_nova.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


@pytest.mark.parametrize("values,expected",[("text",1),([None],1),([],1),(["a","b"],1),(["x"*8193],1)])
def test_bad_recognizer_output_is_rejected_not_silently_truncated(values,expected):
    with pytest.raises(ValueError,match="bounded Hayai output"):
        probe.checked_texts(values,expected)


def test_output_guard_does_not_strip_source_quotes_spacing_or_pacing():
    values = ["「姉ちゃん、\nまだ帰らないの？", "わ ・ た ・ し〜〜", "あとで行くから。」"]
    assert probe.checked_texts(values,3) is values


def test_load_allows_only_exact_reviewed_auxiliary_training_tensors():
    unused = list(probe.TRAINING_ONLY_TENSORS)
    info = {"missing_keys":[],"unexpected_keys":unused,"mismatched_keys":[],"error_msgs":[]}
    assert probe.checked_loading_info(info,probe.TRAINING_ONLY_TENSORS) == sorted(unused)
    assert probe.checked_loading_info({"unexpected_keys":[]},{}) == []


@pytest.mark.parametrize("field,value",[("missing_keys",["decoder.layers.0.attn.w_q.weight"]),
    ("unexpected_keys",["decoder.unreviewed.weight"]),("mismatched_keys",["vision.weight"]),
    ("error_msgs",["bad weights"])])
def test_recognition_checkpoint_differences_fail_closed(field,value):
    with pytest.raises(ValueError):
        probe.checked_loading_info({field:value},{})


def test_wrong_training_only_tensor_shape_or_dtype_is_not_accepted():
    info = {"unexpected_keys":["decoder.ids_head.weight"]}
    for tensor in (([227,512],"F32"),([226,512],"BF16")):
        with pytest.raises(ValueError,match="unreviewed"):
            probe.checked_loading_info(info,{"decoder.ids_head.weight":tensor})


def test_validation_precedes_import_of_downloaded_code(monkeypatch):
    def invalid(path):
        raise ValueError("bad checksum")
    monkeypatch.setattr(probe,"validate_model",invalid)
    monkeypatch.setattr(probe,"reviewed_modules",lambda *args:pytest.fail("Unverified code must not be imported"))
    with pytest.raises(ValueError,match="bad checksum"):
        probe.HayaiRecognizer().load()


def test_comparator_image_processor_is_explicit_local_pil_without_torchvision(monkeypatch):
    calls = []
    class Processor:
        @classmethod
        def from_pretrained(cls,path,**kwargs):
            calls.append((path,kwargs));return "local-pil-processor"
    monkeypatch.setitem(sys.modules,"transformers",SimpleNamespace(Siglip2ImageProcessor=Processor))
    assert probe.local_image_processor(probe.MODEL_PATH) == "local-pil-processor"
    assert calls == [(str(probe.MODEL_PATH / "siglip2"),{"local_files_only":True})]


def test_blank_crop_does_not_load_comparator_or_shift_results(monkeypatch):
    engine = probe.HayaiRecognizer()
    monkeypatch.setattr(engine,"load",lambda:pytest.fail("Blank input must not load model"))
    blank = Image.new("RGB",(240,90),"white")
    assert engine.recognize_many([]) == []
    assert engine.recognize_many([blank,blank]) == ["",""]


def test_batch_keeps_original_rgb_and_uses_bounded_fp32_greedy(monkeypatch):
    engine = probe.HayaiRecognizer(); calls = []
    monkeypatch.setattr(probe,"blank_crop",lambda image:image.getpixel((0,0)) == (255,255,255))
    class Processor:
        def __call__(self,images,**kwargs):
            assert kwargs == {"max_num_patches":512,"return_tensors":"pt"}
            assert images[0].mode == "RGB" and images[0].getpixel((0,0)) == (255,0,0)
            return {"pixel_values":"pixels","pixel_attention_mask":"mask","spatial_shapes":"shapes"}
    class Model:
        def generate(self,**kwargs):
            calls.append(kwargs);return ["「待って！」"]
    engine.model = Model();engine.processor = Processor();engine.tokenizer = "tokenizer"
    engine.torch = SimpleNamespace(inference_mode=nullcontext,float32="fp32")
    blank,text = Image.new("RGB",(4,4),"white"),Image.new("RGB",(4,4),"red")
    assert engine.recognize_many([blank,text,blank]) == ["","「待って！」",""]
    assert calls == [{"pixel_values":"pixels","pixel_attention_mask":"mask","spatial_shapes":"shapes",
                     "tokenizer":"tokenizer","max_new_tokens":300,"num_beams":1,"repetition_penalty":1.0,
                     "dtype":"fp32","use_cuda_graph":False}]


def test_socket_guard_blocks_connect_even_if_inference_catches_exception():
    original = socket.create_connection
    with probe.offline_guard() as attempts:
        with pytest.raises(RuntimeError,match="network I/O"):
            socket.create_connection(("example.invalid",443))
        assert attempts == ["socket-connect"]
    assert socket.create_connection is original


def test_fetch_uses_only_pinned_files_and_never_imports_code(monkeypatch):
    calls = []
    monkeypatch.setattr(probe,"download",lambda url,path,spec:calls.append((url,path,spec)))
    monkeypatch.setattr(probe,"reviewed_modules",lambda *args:pytest.fail("Downloading must not execute source"))
    probe.fetch_model()
    assert len(calls) == len(probe.MODEL_FILES)+len(probe.VISION_FILES)
    assert all(probe.MODEL_REVISION in url or probe.VISION_REVISION in url for url,_,_ in calls)
    assert all(spec["bytes"] > 0 and (spec.get("gitBlob") or spec.get("sha256")) for _,_,spec in calls)


def test_shared_crop_driver_uses_only_explicit_engine_not_hayai(monkeypatch,tmp_path):
    import probe_ocr_resampling
    import benchmark_paddle_rec
    calls=[]
    class Engine:
        details={"production_default":False};model=SimpleNamespace()
        def load(self):calls.append("load")
        def recognize(self,image):calls.append("recognize");return "「待って！」"
    monkeypatch.setattr(probe,"HayaiRecognizer",lambda *a:pytest.fail("do not instantiate default comparator"))
    monkeypatch.setattr(probe,"checked_destination",lambda value:Path(value))
    monkeypatch.setattr(probe_ocr_resampling,"controls",lambda:[("q",Image.new("RGB",(10,10)),"「待って！」")])
    monkeypatch.setattr(benchmark_paddle_rec,"process_memory",lambda:{"rss_bytes":0})
    args=SimpleNamespace(output=str(tmp_path/"report.json"),full_pages=False,authored=True,threads=4,socket_attempts=[])
    probe.run(args,engine_override=Engine())
    assert calls==["load","recognize"]
    import json
    report=json.loads((tmp_path/"report.json").read_text(encoding="utf-8"))
    assert report["aggregate"]["exact"]==1 and report["aggregate"]["edits"]==0
    assert report["model"]["production_default"] is False and report["socket_attempts"]==0


@pytest.mark.parametrize("patches,threads",[(128,4),(512.0,4),(512,True),(512,0),(512,9)])
def test_comparator_refuses_unbounded_resource_settings(patches,threads):
    with pytest.raises(ValueError):
        probe.HayaiRecognizer(patches,threads)
