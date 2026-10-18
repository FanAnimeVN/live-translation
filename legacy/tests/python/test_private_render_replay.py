"""Authored evidence only: replay cannot replace sources or perform inference."""
from copy import deepcopy
import hashlib
import io
import json
from pathlib import Path
import sys
import threading
from types import SimpleNamespace

import pytest
from PIL import Image,ImageDraw

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
import private_render_payload as payloads
import qa_render_replay_entry as entry
from manga_live.errors import AppError


def evidence():
    regions=[{"id":"r1","bbox":[2,3,5,7],"order":0,"ja":"テスト","vi":"Kiểm thử",
        "overlay":"label","review":False,"scope":{"v":1,"key":"native-key","group":"native-group",
        "role":"unknown","action":"translate","reason":"unclassified","memory":True}}]
    native={"width":20,"height":30,"regions":regions}
    reference=deepcopy(regions);reference[0].pop("vi")
    reference[0]["scope"].update(key="cli-key",group="cli-group")
    return {"privateTest":True,"privatePage":"p1","runs":[{"native":native}]}, {
        "input_fingerprint_sha256":"fixture","pages":[{"page":"p1","regions":reference,
        "transient_patches":[{"id":"r1"}]}]}


def test_source_scope_hash_salts_may_differ_but_meaning_must_match():
    report,reference=evidence()
    assert payloads.checked_native(report,reference,"p1",(20,30))[0]==report["runs"][0]["native"]


@pytest.mark.parametrize("field,value",[("id","different"),("bbox",[2,3,6,7]),("order",1),
    ("ja","別"),("overlay","white"),("review",True),("vi",None)])
def test_changed_source_or_untyped_translation_is_rejected(field,value):
    report,reference=evidence();report["runs"][0]["native"]["regions"][0][field]=value
    with pytest.raises(ValueError):payloads.checked_native(report,reference,"p1",(20,30))


@pytest.mark.parametrize("field,value",[("role","editorial"),("action","defer"),("memory",False),
    ("reason","reader"),("v",2),("group",None),("key","")])
def test_changed_scope_permissions_are_not_hidden_by_identity_normalization(field,value):
    report,reference=evidence();report["runs"][0]["native"]["regions"][0]["scope"][field]=value
    with pytest.raises(ValueError):payloads.checked_native(report,reference,"p1",(20,30))


def test_scope_group_topology_is_preserved_even_with_other_hash_salts():
    report,reference=evidence()
    actual=report["runs"][0]["native"]["regions"]
    actual.append({**deepcopy(actual[0]),"id":"r2","order":1})
    expected=reference["pages"][0]["regions"]
    expected.append({**deepcopy(expected[0]),"id":"r2","order":1})
    assert payloads.checked_native(report,reference,"p1",(20,30))
    actual[1]["scope"]["group"]="other-group"
    with pytest.raises(ValueError):payloads.checked_native(report,reference,"p1",(20,30))


def test_page_size_order_and_cardinality_cannot_be_substituted():
    report,reference=evidence()
    with pytest.raises(ValueError):payloads.checked_native(report,reference,"other",(20,30))
    with pytest.raises(ValueError):payloads.checked_native(report,reference,"p1",(21,30))
    report["runs"][0]["native"]["regions"]*=2
    with pytest.raises(ValueError):payloads.checked_native(report,reference,"p1",(20,30))


def test_current_scope_replay_preserves_captured_words_coordinates_and_input():
    report,_=evidence();native=report["runs"][0]["native"]
    native["regions"][0].update(bbox=[2,3,13,14],ja="．．．",vi="...",review=False)
    before=deepcopy(native);image=Image.new("RGB",(20,30),"white")
    ImageDraw.Draw(image).polygon([(2,3),(5,3),(14,16),(11,16)],fill="black")
    result=payloads.current_scope_replay(image,native)
    assert native==before
    for key in ("id","bbox","order","ja","vi","overlay"):
        assert result["regions"][0][key]==native["regions"][0][key]
    assert result["regions"][0]["reviewReasons"]==["visual_punctuation_support"]
    assert result["regions"][0]["scope"]["memory"] is False


def test_current_scope_replay_cannot_discard_a_reader_choice():
    report,_=evidence();native=report["runs"][0]["native"]
    native["regions"][0]["scope"]["reason"]="reader"
    with pytest.raises(ValueError,match="reader override"):
        payloads.current_scope_replay(Image.new("RGB",(20,30)),native)


def fixture(tmp_path,monkeypatch):
    monkeypatch.setattr(payloads,"ROOT",tmp_path)
    artifacts=tmp_path/"artifacts";artifacts.mkdir()
    report,reference=evidence()
    for name,value in (("native.json",report),("reference.json",reference)):
        (artifacts/name).write_text(json.dumps(value),encoding="utf-8")
    args=SimpleNamespace(native_result=artifacts/"native.json",reference=artifacts/"reference.json",
        folder=tmp_path/"source",page="p1")
    image=Image.new("RGB",(20,30),"white")
    class Dataset:
        def __init__(self,folder):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
    monkeypatch.setattr(payloads,"DirectoryDataset",Dataset)
    monkeypatch.setattr(payloads,"audit",lambda source:(None,None,[({"page_id":"p1"},image,[])]))
    monkeypatch.setattr(payloads,"dataset_fingerprint",lambda source:"fixture")
    calls=[]
    def patch(source,region,max_bytes):
        calls.append(max_bytes)
        return {"regionId":region["id"],"dataUrl":"data:image/png;base64,AQ=="}
    monkeypatch.setattr(payloads,"render_patch",patch)
    return args,image,calls


def test_payload_images_and_cleanup_stay_in_ram(tmp_path,monkeypatch):
    args,image,calls=fixture(tmp_path,monkeypatch)
    before={p:p.read_bytes() for p in (tmp_path/"artifacts").iterdir()}
    payload=payloads.build_payload(args)
    assert payload["pixel_sha256"]==hashlib.sha256(image.tobytes()).hexdigest()
    assert payload["cloud"] is payload["inference"] is payload["image_persistence"] is False
    assert calls==[payloads.MAX_JOB_PATCH_BYTES]
    assert {p:p.read_bytes() for p in (tmp_path/"artifacts").iterdir()}==before
    assert set(tmp_path.iterdir())=={tmp_path/"artifacts"}


def test_dataset_fingerprint_checked_before_any_cleanup(tmp_path,monkeypatch):
    args,_,calls=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(payloads,"dataset_fingerprint",lambda source:"changed")
    with pytest.raises(ValueError,match="fingerprint"):payloads.build_payload(args)
    assert calls==[]


def test_missing_audited_page_or_changed_patch_coverage_is_rejected(tmp_path,monkeypatch):
    args,_,_=fixture(tmp_path,monkeypatch)
    monkeypatch.setattr(payloads,"audit",lambda source:(None,None,[]))
    with pytest.raises(ValueError,match="excluded or missing"):payloads.build_payload(args)
    monkeypatch.setattr(payloads,"audit",lambda source:(None,None,[({"page_id":"p1"},Image.new("RGB",(20,30)),[])]))
    monkeypatch.setattr(payloads,"render_patch",lambda *args,**kwargs:None)
    with pytest.raises(ValueError,match="cleanup coverage"):payloads.build_payload(args)


def test_evidence_outside_private_artifacts_is_rejected_before_file_access(tmp_path,monkeypatch):
    # Do not assume pytest's basetemp is outside this project's artifacts.
    monkeypatch.setattr(payloads,"ROOT",tmp_path/"isolated-project")
    with pytest.raises(ValueError,match="gitignored artifacts"):
        payloads.build_payload(SimpleNamespace(native_result=tmp_path/"missing",reference=tmp_path/"missing2"))


def configured_replay():
    report,_=evidence();image=Image.new("RGB",(20,30),"white")
    payload={"native":report["runs"][0]["native"],"patches":[{"regionId":"r1"}],
        "pixel_sha256":hashlib.sha256(image.tobytes()).hexdigest()}
    settings={}
    host=SimpleNamespace(config=SimpleNamespace(update=settings.update),pipeline=SimpleNamespace(),
        translator=SimpleNamespace(),metadata=SimpleNamespace())
    entry.configure_replay(host,payload)
    return host,payload,image,settings


def png(image):
    output=io.BytesIO();image.save(output,format="PNG");return output.getvalue()


def test_native_replay_uses_exact_source_pixels_and_current_revision_without_inference():
    host,payload,image,settings=configured_replay();events=[];cancel=threading.Event()
    result=host.pipeline.process({"revision":"current"},png(image),cancel,lambda *event:events.append(event))
    assert settings=={"mode":"offline","autoSummary":False,"metadataConsent":False,"cloudConsent":False}
    assert result["revision"]==events[0][1]["revision"]=="current"
    assert result["cached"] is False and result["metrics"]["render_replay"] is True
    result["regions"][0]["vi"]="changed";events[0][1]["patch"]["regionId"]="changed"
    assert payload["native"]["regions"][0]["vi"]=="Kiểm thử" and payload["patches"][0]["regionId"]=="r1"
    with pytest.raises(AppError) as error:
        host.pipeline.process({"revision":"current"},png(Image.new("RGB",image.size,"black")),cancel,lambda *args:None)
    assert error.value.code=="REPLAY_SOURCE"


def test_native_replay_cancellation_cannot_emit_or_resurrect_later_patches():
    host,payload,image,_=configured_replay();cancel=threading.Event();cancel.set();events=[]
    with pytest.raises(AppError) as error:host.pipeline.process({"revision":"r"},png(image),cancel,lambda *event:events.append(event))
    assert error.value.code=="CANCELED" and events==[]
    cancel.clear();payload["patches"].append({"regionId":"r2"})
    def emit(*event):events.append(event);cancel.set()
    with pytest.raises(AppError) as error:host.pipeline.process({"revision":"r"},png(image),cancel,emit)
    assert error.value.code=="CANCELED" and len(events)==1


@pytest.mark.parametrize("component,method",[("pipeline","warmup"),("pipeline","retranslate"),
    ("translator","translate"),("translator","summarize"),("metadata","search")])
def test_accidental_qa_buttons_cannot_load_models_or_search_network(component,method):
    host,_,_,_=configured_replay()
    with pytest.raises(AppError) as error:getattr(getattr(host,component),method)()
    assert error.value.code=="REPLAY_NETWORK"
