"""A malformed adapter result must never masquerade as completed source OCR."""
import io
import threading
from types import SimpleNamespace

from PIL import Image,ImageDraw
import pytest

from manga_live.errors import AppError
from manga_live.memory import Memory,digest
from manga_live.ocr import MangaEngine,recognize_regions,LAYOUT_VERSION,OCR_PARTITION_VERSION,OCR_COVERAGE_VERSION
from manga_live.pipeline import SCOPE_VERSION
from manga_live.memory import SPEAKER_BINDING_VERSION
from manga_live.prompts import PROMPT_VERSION
from manga_live.pipeline import Pipeline


def source_fixture():
    image=Image.new("RGB",(140,100),"white")
    draw=ImageDraw.Draw(image)
    for x in (12,82):draw.text((x,12),"ABC",fill="black")
    regions=[{"id":"a","bbox":[8,8,40,38],"order":0,"overlay":"label","score":.9},
             {"id":"b","bbox":[78,8,40,38],"order":1,"overlay":"label","score":.9}]
    return image,regions


@pytest.mark.parametrize("invalid",[["日本"],[],["日本","語","余分"],"日本",["日本",None]])
def test_manga_batch_rejects_missing_extra_or_malformed_outputs(tmp_path,invalid):
    image,regions=source_fixture()
    crops=[image.crop((x,y,x+w,y+h)) for x,y,w,h in (r["bbox"] for r in regions)]
    engine=MangaEngine(tmp_path)
    engine.model=SimpleNamespace(recognize_many=lambda items:invalid)
    with pytest.raises(AppError) as failure:engine.recognize_many(crops)
    assert failure.value.code=="OCR_RESULT"


@pytest.mark.parametrize("invalid",[["日本"],[],["日本","語","余分"],"日本",["日本",None]])
def test_generic_region_adapter_cannot_silently_drop_or_split_source_text(invalid):
    image,regions=source_fixture()
    engine=SimpleNamespace(recognize_many=lambda items:invalid)
    with pytest.raises(AppError) as failure:
        recognize_regions(image,regions,engine,threading.Event(),batch_size=2)
    assert failure.value.code=="OCR_RESULT"


def test_true_blank_positions_and_valid_empty_strings_remain_allowed(tmp_path):
    image,regions=source_fixture()
    crop=image.crop((8,8,48,46));blank=Image.new("RGB",crop.size,"white")
    engine=MangaEngine(tmp_path);seen=[]
    engine.model=SimpleNamespace(recognize_many=lambda items:seen.append(len(items)) or ["日本",""])
    assert engine.recognize_many([blank,crop,blank,crop])==["","日本","",""] and seen==[2]


def test_empty_region_is_retained_as_reviewable_source_instead_of_dropped():
    image,regions=source_fixture()
    engine=SimpleNamespace(recognize_many=lambda items:["", "日本"])
    result=recognize_regions(image,regions,engine,threading.Event(),batch_size=2)
    assert [row["id"] for row in result]==["a","b"]
    assert result[0]["ja"]=="" and result[0]["review"]
    assert "ocr_empty" in result[0]["reviewReasons"]


def test_unreadable_source_survives_pipeline_cache_and_can_be_corrected(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    image,regions=source_fixture();calls={"ocr":0,"translate":[],"cleanup":[]}
    memory=Memory(tmp_path/"unreadable.sqlite3")
    pipeline=Pipeline.__new__(Pipeline)
    pipeline.memory=memory;pipeline.config=SimpleNamespace(values={"detector":"paddle","ocrBatch":2,"artCleanup":True})
    def recognize(crops):
        calls["ocr"]+=1
        return ["", "日本"]
    pipeline.ocr=SimpleNamespace(name="authored-unreadable",recognize_many=recognize)
    pipeline.detectors={"paddle":SimpleNamespace(detect=lambda image:regions)}
    def translate(items,*args):
        calls["translate"].append([row["id"] for row in items])
        return [{"id":row["id"],"vi":"Bản dịch tự tạo"} for row in items],{"translation_ms":1}
    pipeline.translator=SimpleNamespace(signature=lambda:"authored",translate=translate)
    monkeypatch.setattr(module,"render_patch",lambda image,row,*a,**k:calls["cleanup"].append(row["id"]))
    buffer=io.BytesIO();image.save(buffer,format="PNG")
    params={"storyId":"s","title":"Authored","pageId":"p","revision":"rev","at":{"chapter":1,"page":0}}
    events=[]
    try:
        result=pipeline.process(params,buffer.getvalue(),threading.Event(),lambda event,value:events.append((event,value)))
        by_id={row["id"]:row for row in result["regions"]}
        assert set(by_id)=={"a","b"},"Unreadable detector source must remain recoverable"
        unreadable=by_id["a"]
        assert unreadable["ja"]=="" and "vi" not in unreadable
        assert unreadable["scope"]["action"]=="defer" and not unreadable["scope"]["memory"]
        assert calls["translate"]==[["b"]] and calls["cleanup"]==["b"]
        assert any(event=="regions" and any(row["id"]=="a" for row in value["regions"]) for event,value in events)
        cached=pipeline.process({**params,"revision":"cache"},buffer.getvalue(),threading.Event(),lambda *args:None)
        assert cached["cached"] and calls["ocr"]==1 and calls["translate"]==[["b"]]
        assert any(row["id"]=="a" for row in memory.page("s","p","cache")["regions"])
        fixed=pipeline.retranslate({**params,"revision":"cache","regionId":"a","ja":"ありがとう", "recoverDeferred":True},threading.Event())
        assert fixed["scope"]["action"]=="translate" and not fixed["scope"]["memory"]
        assert calls["translate"]==[["b"],["a"]]
    finally:memory.close()


@pytest.mark.parametrize("invalid",[None,42,["日本"]])
def test_single_crop_cannot_return_an_untyped_ocr_value(tmp_path,invalid):
    image,_=source_fixture();engine=MangaEngine(tmp_path);engine.model=lambda image:invalid
    with pytest.raises(AppError) as failure:engine.recognize(image)
    assert failure.value.code=="OCR_RESULT"


def test_failed_ocr_batch_does_not_cache_missing_region_as_processed(tmp_path):
    image,regions=source_fixture();memory=Memory(tmp_path/"incomplete.sqlite3")
    pipeline=Pipeline.__new__(Pipeline)
    pipeline.memory=memory;pipeline.config=SimpleNamespace(values={"detector":"paddle","ocrBatch":2,"artCleanup":False})
    engine=MangaEngine(tmp_path);calls=[]
    engine.model=SimpleNamespace(recognize_many=lambda items:["日本"])
    pipeline.ocr=engine;pipeline.detectors={"paddle":SimpleNamespace(detect=lambda image:regions)}
    def translate(items,*args):
        calls.append("translate")
        return [{"id":r["id"],"vi":"Bản dịch tự tạo"} for r in items],{"translation_ms":1}
    pipeline.translator=SimpleNamespace(signature=lambda:"authored",translate=translate)
    buffer=io.BytesIO();image.save(buffer,format="PNG")
    data=buffer.getvalue()
    params={"storyId":"s","title":"Authored","pageId":"p","revision":"rev","at":{"chapter":1,"page":0}}
    try:
        with pytest.raises(AppError) as failure:pipeline.process(params,data,threading.Event(),lambda *a:None)
        assert failure.value.code=="OCR_RESULT" and calls==[]
        import hashlib
        ocr_key=digest([OCR_COVERAGE_VERSION,LAYOUT_VERSION,OCR_PARTITION_VERSION,"s","p",
                        hashlib.sha256(data).hexdigest(),None,"paddle",engine.name])
        cached=memory.cache_get(ocr_key)
        assert cached and cached["processed"]==[] and cached["recognized"]==[]
        # A subsequent explicit retry must actually OCR both pending crops;
        # the old malformed batch cannot suppress its missing second item.
        engine.model=SimpleNamespace(recognize_many=lambda items:["日本","語"])
        result=pipeline.process({**params,"revision":"retry"},data,threading.Event(),lambda *a:None)
        assert [r["id"] for r in result["regions"]]==["a","b"] and calls==["translate"]
        coverage=memory.cache_get(ocr_key)
        assert coverage["processed"]==["a","b"] and [r["id"] for r in coverage["recognized"]]==["a","b"]
    finally:memory.close()
