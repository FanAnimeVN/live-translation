import threading
from types import SimpleNamespace
from PIL import Image
import io
import hashlib
import pytest
from manga_live.memory import Memory
from manga_live.pipeline import Pipeline
from manga_live.errors import AppError
from manga_live.memory import digest
from manga_live.prompts import PROMPT_VERSION


class FakeTranslator:
    def signature(self):return "test"
    def translate(self,regions,context,cancel):
        return [{"id":r["id"],"vi":"Đã sửa","ambiguous":False} for r in regions],{"translation_ms":1}


def test_retranslate_is_revision_checked_and_persists_source(tmp_path):
    memory=Memory(tmp_path/"pipeline.db");memory.ensure_story("s","Test")
    pipeline=Pipeline.__new__(Pipeline);pipeline.memory=memory;pipeline.translator=FakeTranslator()
    at={"chapter":1,"page":0};memory.save_page("s","p",at,"rev",[{"id":"r","ja":"old","vi":"cũ"}])
    params={"storyId":"s","pageId":"p","regionId":"r","ja":"new","revision":"wrong","at":at}
    with pytest.raises(AppError):pipeline.retranslate(params,threading.Event())
    assert memory.page("s","p","rev")["regions"][0]["ja"]=="old"
    params["revision"]="rev"
    assert pipeline.retranslate(params,threading.Event())["vi"]=="Đã sửa"
    assert memory.page("s","p","rev")["regions"][0]["ja"]=="new"
    memory.mark_read("s","p","rev");assert memory.next_job()
    memory.close()


def test_ocr_edit_recomputes_expression_and_removes_stale_source_delivery(tmp_path):
    from manga_live.expression import bind_expression
    memory=Memory(tmp_path/"expression.db");memory.ensure_story("s","Authored delivery")
    at={"chapter":1,"page":0}
    memory.save_page("s","p",at,"rev",[bind_expression({"id":"r","ja":"わ・た・し〜〜！","vi":"Tô-i… đââây!"})])
    received=[]
    class Translator(FakeTranslator):
        def translate(self,regions,*args):
            received.extend(regions)
            return super().translate(regions,*args)
    pipeline=Pipeline.__new__(Pipeline);pipeline.memory=memory;pipeline.translator=Translator()
    params={"storyId":"s","pageId":"p","regionId":"r","revision":"rev","at":at,"ja":"こんにちは。"}
    result=pipeline.retranslate(params,threading.Event())
    assert result["expression"] is None
    assert "expression" not in received[0]
    assert "expression" not in memory.page("s","p","rev")["regions"][0]
    params["ja"]="待ってーーー！"
    result=pipeline.retranslate(params,threading.Event())
    assert result["expression"]["cues"]==["elongated"]
    assert memory.page("s","p","rev")["regions"][0]["expression"]==result["expression"]
    memory.close()

def test_cache_hit_reports_current_latency_and_context_in_event_and_result(tmp_path):
    memory=Memory(tmp_path/"cache.db");memory.ensure_story("s","Test")
    pipeline=Pipeline.__new__(Pipeline);pipeline.memory=memory;pipeline.translator=FakeTranslator()
    pipeline.config=SimpleNamespace(values={"detector":"paddle"})
    pipeline.ocr=SimpleNamespace(name="fake-ocr")
    at={"chapter":1,"page":0};context=memory.context("s",at);data=b"cached image bytes"
    key=pipeline.page_cache_key("s","p",at,hashlib.sha256(data).hexdigest(),None)
    original={"detector_ms":20000,"ocr_ms":10000,"context_ms":30,"translation_ms":5000,
              "input_tokens":100,"output_tokens":50,"total_ms":35030,"first_overlay_ms":35000}
    memory.cache_put(key,"s",at,{"regions":[{"id":"r","ja":"ありがとう","vi":"Cảm ơn"}],
        "revision":"old","contextVersion":0,"width":100,"height":100,"metrics":original,"cached":False,
        "contextDependencies":[{"text":"ありがとう","entities":[],"fingerprint":memory.context("s",at,"ありがとう","p")["fingerprint"]}]})
    emitted=[]
    result=pipeline.process({"storyId":"s","title":"Test","pageId":"p","revision":"new","at":at},data,
        threading.Event(),lambda event,payload:emitted.append((event,payload)))
    assert result["cached"] and result["revision"]=="new"
    assert result["contextVersion"]==context["version"]
    assert result["metrics"]["total_ms"]<1000
    assert result["metrics"]["first_overlay_ms"]<1000
    assert result["metrics"]["translation_ms"]==0
    assert result["metrics"]["input_tokens"]==result["metrics"]["output_tokens"]==0
    assert result["sourceMetrics"]==original
    assert emitted==[("translated",result)]
    memory.close()


@pytest.mark.parametrize("size",[2,4])
@pytest.mark.parametrize("count",[0,1,2,3,4,6,12,64])
def test_interactive_batches_preserve_reading_order_and_all_regions(size,count):
    pipeline=Pipeline.__new__(Pipeline);pipeline.first_batch_size=size
    regions=list(range(count));batches=list(pipeline.region_batches(regions))
    assert [r for batch in batches for r in batch]==regions
    assert len(batches[0])<=size
    assert all(len(batch)<=4 for batch in batches)


def test_cache_checks_relevant_glossary_outside_generic_context_budget(tmp_path,monkeypatch):
    memory=Memory(tmp_path/"dependencies.db");memory.ensure_story("s","Test")
    at={"chapter":10,"page":0};source="氷結結界を展開する！"
    term_at={"chapter":1,"page":0}
    memory.canonical_term("s","ice","skill","氷結結界","Kết Giới Băng",[],term_at)
    for i in range(20):
        memory.fact("s","glossary",f"other-{i}","x"*600,
                    {"chapter":9,"page":i},{"type":"user"})
    generic=memory.context("s",at)
    relevant=memory.context("s",at,source,"p")
    assert all(r["key"]!="ice" for r in generic["data"]["glossary"])
    assert relevant["data"]["glossary"][0]["key"]=="ice"
    image=Image.new("RGB",(100,100),"white");buffer=io.BytesIO();image.save(buffer,format="PNG");data=buffer.getvalue()
    key=digest(["translation-dependencies-v1","s","p",at,hashlib.sha256(data).hexdigest(),None,"paddle","fake-ocr","test",PROMPT_VERSION])
    region={"id":"r","ja":source,"vi":"Kết Giới Băng","bbox":[0,0,20,20],"type":"dialogue"}
    memory.cache_put(key,"s",at,{"regions":[region],"revision":"old","width":100,"height":100,"metrics":{},
        "contextDependencies":[{"text":source,"entities":[],"fingerprint":relevant["fingerprint"]}]})
    memory.canonical_term("s","ice","skill","氷結結界","Băng Kết Kết Giới",[],term_at)
    assert memory.context("s",at)["fingerprint"]==generic["fingerprint"]
    assert memory.context("s",at,source,"p")["fingerprint"]!=relevant["fingerprint"]
    pipeline=Pipeline.__new__(Pipeline);pipeline.memory=memory;pipeline.translator=FakeTranslator()
    pipeline.config=SimpleNamespace(values={"detector":"paddle","ocrBatch":2})
    pipeline.ocr=SimpleNamespace(name="fake-ocr")
    pipeline.detectors={"paddle":SimpleNamespace(detect=lambda image:[region])}
    import manga_live.pipeline as module
    monkeypatch.setattr(module,"recognize_regions",lambda image,regions,*args,**kwargs:[dict(r) for r in regions])
    result=pipeline.process({"storyId":"s","title":"Test","pageId":"p","revision":"new","at":at},data,
                           threading.Event(),lambda *args:None)
    assert not result["cached"],"Changed relevant canonical term must invalidate a cached translation"
    assert result["regions"][0]["vi"]=="Đã sửa"
    memory.close()


def test_unrelated_generic_context_change_does_not_evict_matching_page_cache(tmp_path,monkeypatch):
    memory=Memory(tmp_path/"reuse.db");memory.ensure_story("s","Test")
    at={"chapter":10,"page":0}
    memory.fact("s","character","A","x"*900,{"chapter":1,"page":0},{"type":"user"})
    memory.fact("s","character","other","x"*900,{"chapter":9,"page":0},{"type":"user"})
    pipeline=Pipeline.__new__(Pipeline);pipeline.memory=memory;pipeline.translator=FakeTranslator()
    pipeline.config=SimpleNamespace(values={"detector":"paddle","ocrBatch":2})
    pipeline.ocr=SimpleNamespace(name="fake-ocr")
    region={"id":"r","ja":"A、ありがとう。","bbox":[0,0,20,20],"speaker":"unknown","listener":"unknown"}
    pipeline.detectors={"paddle":SimpleNamespace(detect=lambda image:[dict(region)])}
    import manga_live.pipeline as module
    monkeypatch.setattr(module,"recognize_regions",lambda image,regions,*args,**kwargs:[dict(r) for r in regions])
    image=Image.new("RGB",(100,100),"white");buffer=io.BytesIO();image.save(buffer,format="PNG");data=buffer.getvalue()
    params={"storyId":"s","title":"Test","pageId":"p","revision":"first","at":at}
    result=pipeline.process(params,data,threading.Event(),lambda *args:None)
    assert not result["cached"]
    generic=memory.context("s",at)["fingerprint"]
    relevant=memory.context("s",at,region["ja"],"p")["fingerprint"]
    memory.fact("s","character","other","y"*900,{"chapter":9,"page":0},{"type":"user"})
    assert memory.context("s",at)["fingerprint"]!=generic
    assert memory.context("s",at,region["ja"],"p")["fingerprint"]==relevant
    result=pipeline.process({**params,"revision":"second"},data,threading.Event(),lambda *args:None)
    assert result["cached"],"Irrelevant profile edit must not evict a page with unchanged retrieval dependencies"
    assert result["revision"]=="second" and result["contextVersion"]==memory.version("s")
    memory.close()


@pytest.mark.parametrize("dependencies",[None,[],[{}],[{"text":"x","entities":"A","fingerprint":"x"}]])
def test_cache_without_complete_retrieval_evidence_is_not_reused(tmp_path,dependencies):
    memory=Memory(tmp_path/"legacy.db");memory.ensure_story("s","Test")
    pipeline=Pipeline.__new__(Pipeline);pipeline.memory=memory
    cached={"regions":[{"id":"r","ja":"ありがとう","vi":"Cảm ơn"}]}
    if dependencies is not None:cached["contextDependencies"]=dependencies
    assert not pipeline.cache_context_matches("s","p",{"chapter":1,"page":0},cached)
    memory.close()


def retry_fixture(tmp_path,monkeypatch):
    """Real cache/storage seam; only detector, OCR and translation are faked."""
    import manga_live.pipeline as module
    memory=Memory(tmp_path/"ocr-retry.db");memory.ensure_story("s","Retry fixture")
    pipeline=Pipeline.__new__(Pipeline);pipeline.memory=memory;pipeline.translator=FakeTranslator()
    pipeline.config=SimpleNamespace(values={"detector":"paddle","ocrBatch":2})
    pipeline.ocr=SimpleNamespace(name="fake-ocr");calls={"detector":0,"ocr":[],"translate":0}
    layout=[{"id":f"r{i}","bbox":[i*10,0,10,20],"order":i,"type":"dialogue"} for i in range(6)]
    def detect(image):
        calls["detector"]+=1
        return [dict(r) for r in layout]
    def recognize(image,regions,*args,**kwargs):
        calls["ocr"].extend(r["id"] for r in regions)
        # A detected blank crop must stay skipped, including after a failed
        # translation. The remaining layout still has two unprocessed crops.
        return [{**r,"ja":"ありがとう。"} for r in regions if r["id"]!="r1"]
    pipeline.detectors={"paddle":SimpleNamespace(detect=detect)}
    monkeypatch.setattr(module,"recognize_regions",recognize)
    buffer=io.BytesIO();Image.new("RGB",(100,100),"white").save(buffer,format="PNG")
    params={"storyId":"s","title":"Retry fixture","pageId":"p","revision":"rev-a",
            "at":{"chapter":1,"page":0}}
    return pipeline,calls,buffer.getvalue(),params


@pytest.mark.parametrize("restart",[False,True])
@pytest.mark.parametrize("new_revision",[False,True])
def test_retry_does_not_regenerate_a_completed_translation_batch(tmp_path,monkeypatch,restart,new_revision):
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    generated=[];events=[]
    def translate(regions,context,cancel):
        generated.append([r["id"] for r in regions])
        if len(generated)==2:raise AppError("NETWORK","Authored second-group failure")
        items,measurement=FakeTranslator().translate(regions,context,cancel)
        return items,{**measurement,"usage":{"prompt_tokens":100,"completion_tokens":20}}
    pipeline.translator.translate=translate
    try:
        with pytest.raises(AppError) as error:
            pipeline.process(params,data,threading.Event(),lambda name,payload:events.append((name,payload)))
        assert error.value.code=="NETWORK"
        assert generated==[["r0","r2","r3"],["r4","r5"]]
        assert len([payload for name,payload in events if name=="translated"])==1
        with pytest.raises(AppError):pipeline.memory.page("s","p","rev-a")
        assert pipeline.memory.next_job() is None,"Partial translation is not a read page"
        if restart:
            pipeline.memory.close();pipeline.memory=Memory(tmp_path/"ocr-retry.db")
        events.clear()
        retry_revision="rev-b" if new_revision else "rev-a"
        result=pipeline.process({**params,"revision":retry_revision},data,threading.Event(),
            lambda name,payload:events.append((name,payload)))
        assert generated==[["r0","r2","r3"],["r4","r5"],["r4","r5"]],\
            "Retry must reuse the completed first group, not buy/generate it again"
        assert [r["id"] for r in result["regions"]]==["r0","r2","r3","r4","r5"]
        assert not result["cached"],"A resumed page is not a full-page cache hit"
        assert result["metrics"]["reused_translation_groups"]==1
        assert result["metrics"]["input_tokens"]==100 and result["metrics"]["output_tokens"]==20
        assert all(payload["revision"]==retry_revision for name,payload in events if name=="translated")
        assert calls["detector"]==1 and calls["ocr"]==["r0","r1","r2","r3","r4","r5"]
    finally:pipeline.memory.close()


@pytest.mark.parametrize("error_code",["NETWORK","CONSENT","MODEL_OUTPUT"])
def test_retry_after_translation_failure_reuses_completed_ocr_without_losing_pending_crops(tmp_path,monkeypatch,error_code):
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    def translate(regions,context,cancel):
        calls["translate"]+=1
        if calls["translate"]==1:raise AppError(error_code,"Authored test failure")
        return FakeTranslator().translate(regions,context,cancel)
    pipeline.translator.translate=translate
    try:
        with pytest.raises(AppError) as failure:
            pipeline.process(params,data,threading.Event(),lambda *args:None)
        assert failure.value.code==error_code
        assert calls["ocr"]==["r0","r1","r2","r3"]
        assert pipeline.memory.next_job() is None
        with pytest.raises(AppError):pipeline.memory.page("s","p","rev-a")
        result=pipeline.process({**params,"revision":"rev-b"},data,threading.Event(),lambda *args:None)
        assert calls["detector"]==1,"Retry must not run detection again"
        assert calls["ocr"]==["r0","r1","r2","r3","r4","r5"],"Only pending crops should run OCR"
        assert [r["id"] for r in result["regions"]]==["r0","r2","r3","r4","r5"]
        assert not result["cached"],"OCR cache is not a finished translation cache"
        assert result["revision"]=="rev-b"
        cached=pipeline.process({**params,"revision":"rev-c"},data,threading.Event(),lambda *args:None)
        assert cached["cached"] and cached["revision"]=="rev-c"
        assert calls["ocr"]==["r0","r1","r2","r3","r4","r5"]
        assert pipeline.memory.next_job() is None,"Processing is not proof the reader read the page"
    finally:pipeline.memory.close()


@pytest.mark.parametrize("mode",["offline","byok"])
@pytest.mark.parametrize("code",["TRUNCATED","MODEL_FORMAT","MODEL_OUTPUT","TERM_MISMATCH"])
def test_generation_failure_does_not_recursively_split_or_restart_translation(tmp_path,monkeypatch,mode,code):
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    pipeline.config.values["mode"]=mode
    def fail(regions,context,cancel):
        calls["translate"]+=1
        assert len(regions)==3  # Four detected crops; one is blank.
        raise AppError(code,"Authored generation failure")
    pipeline.translator.translate=fail
    try:
        with pytest.raises(AppError) as failure:
            pipeline.process(params,data,threading.Event(),lambda *args:None)
        assert failure.value.code==code and calls["translate"]==1
        assert calls["detector"]==1 and len(calls["ocr"])==4
    finally:pipeline.memory.close()


def test_cloud_warmup_never_starts_local_translation_or_calls_a_provider():
    pipeline=Pipeline.__new__(Pipeline);seen=[]
    pipeline.config=SimpleNamespace(values={"detector":"paddle","mode":"byok"})
    pipeline.detectors={"paddle":SimpleNamespace(detect=lambda image:seen.append("detector"))}
    pipeline.ocr=SimpleNamespace(load=lambda:seen.append("ocr"))
    pipeline.translator=SimpleNamespace(local=SimpleNamespace(start=lambda cancel:pytest.fail("Cloud warmup started local LLM")))
    assert pipeline.warmup(threading.Event())["ready"]
    assert seen==["detector","ocr"]


def test_cancellation_after_ocr_never_starts_translation(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    cancel=threading.Event()
    def recognize(image,regions,*args,**kwargs):
        cancel.set()
        return [{**r,"ja":"ありがとう。"} for r in regions]
    def translate(regions,context,cancel):
        calls["translate"]+=1
        return FakeTranslator().translate(regions,context,cancel)
    monkeypatch.setattr(module,"recognize_regions",recognize)
    pipeline.translator.translate=translate
    try:
        with pytest.raises(AppError) as failure:pipeline.process(params,data,cancel,lambda *args:None)
        assert failure.value.code=="CANCELED"
        assert calls["translate"]==0
    finally:pipeline.memory.close()


def test_partial_ocr_survives_host_restart_and_a_different_batch_size(tmp_path,monkeypatch):
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    pipeline.translator.translate=lambda *args:(_ for _ in ()).throw(AppError("NETWORK","Authored failure"))
    try:
        with pytest.raises(AppError):pipeline.process(params,data,threading.Event(),lambda *args:None)
        pipeline.memory.close()
        pipeline.memory=Memory(tmp_path/"ocr-retry.db")
        pipeline.first_batch_size=2
        pipeline.translator=FakeTranslator()
        result=pipeline.process({**params,"revision":"restarted"},data,threading.Event(),lambda *args:None)
        assert calls["detector"]==1
        assert calls["ocr"]==["r0","r1","r2","r3","r4","r5"]
        assert [r["id"] for r in result["regions"]]==["r0","r2","r3","r4","r5"]
    finally:pipeline.memory.close()


@pytest.mark.parametrize("changed",["image","page","ocr-version","selection"])
def test_partial_ocr_is_not_reused_for_changed_source_or_engine(tmp_path,monkeypatch,changed):
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    pipeline.translator.translate=lambda *args:(_ for _ in ()).throw(AppError("NETWORK","Authored failure"))
    try:
        with pytest.raises(AppError):pipeline.process(params,data,threading.Event(),lambda *args:None)
        if changed=="image":
            buffer=io.BytesIO();Image.new("RGB",(100,100),"black").save(buffer,format="PNG");data=buffer.getvalue()
        elif changed=="page":params={**params,"pageId":"other-page"}
        elif changed=="ocr-version":pipeline.ocr.name="new-ocr-version"
        else:params={**params,"selection":[0,0,40,40]}
        pipeline.translator=FakeTranslator()
        result=pipeline.process({**params,"revision":"changed"},data,threading.Event(),lambda *args:None)
        assert len(calls["ocr"])>4,"Changed source/engine must not reuse old OCR coverage"
        assert not result["cached"]
        if changed!="selection":assert calls["detector"]==2
    finally:pipeline.memory.close()


def test_cancellation_after_translation_does_not_publish_a_late_overlay(tmp_path,monkeypatch):
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch);cancel=threading.Event();events=[]
    def translate(regions,context,event):
        cancel.set()
        return FakeTranslator().translate(regions,context,event)
    pipeline.translator.translate=translate
    try:
        with pytest.raises(AppError) as failure:pipeline.process(params,data,cancel,lambda name,payload:events.append(name))
        assert failure.value.code=="CANCELED"
        assert "translated" not in events
        with pytest.raises(AppError):pipeline.memory.page("s","p","rev-a")
    finally:pipeline.memory.close()


def test_local_cleanup_default_optout_and_cache_never_persist_patches(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    detector=pipeline.detectors["paddle"].detect
    pipeline.detectors["paddle"].detect=lambda image:[{**r,"overlay":"label"} for r in detector(image)]
    patch_calls=[]
    def clean(image,region,*args,**kwargs):
        patch_calls.append(region["id"])
        return {"regionId":region["id"],"bbox":[0,0,10,20],"dataUrl":"data:image/png;base64,PRIVATE_RAM_ONLY",
                "ink":"#111111","stroke":"#ffffff","sourceFontPx":20,"method":"opencv-telea-v1"}
    monkeypatch.setattr(module,"render_patch",clean)
    try:
        events=[]
        result=pipeline.process(params,data,threading.Event(),lambda name,payload:events.append((name,payload)))
        assert len(patch_calls)==5 and sum(name=="render-patch" for name,_ in events)==5,"Missing setting must use free local cleanup"
        pipeline.config.values["artCleanup"]=False
        events.clear();patch_calls.clear()
        result=pipeline.process({**params,"revision":"disabled"},data,threading.Event(),lambda name,payload:events.append((name,payload)))
        assert result["cached"] and not patch_calls and not any(name=="render-patch" for name,_ in events)
        pipeline.config.values["artCleanup"]=True
        events.clear()
        result=pipeline.process({**params,"revision":"enabled"},data,threading.Event(),lambda name,payload:events.append((name,payload)))
        assert result["cached"] and len(patch_calls)==5,"Turning cleanup on must not pay for translation again"
        assert len([name for name,_ in events if name=="render-patch"])==5
        assert all(payload["revision"]=="enabled" for name,payload in events if name=="render-patch")
        assert "PRIVATE_RAM_ONLY" not in str(result)
        assert "PRIVATE_RAM_ONLY" not in str(pipeline.memory.page("s","p","enabled"))
        pipeline.memory.close()
        assert b"PRIVATE_RAM_ONLY" not in (tmp_path/"ocr-retry.db").read_bytes()
        pipeline.memory=Memory(tmp_path/"ocr-retry.db")
    finally:pipeline.memory.close()


def test_optional_renderer_failure_cannot_lose_a_good_translation(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    pipeline.config.values["artCleanup"]=True
    monkeypatch.setattr(module,"render_patch",lambda *args,**kwargs:(_ for _ in ()).throw(RuntimeError("Synthetic renderer failure")))
    try:
        result=pipeline.process(params,data,threading.Event(),lambda *args:None)
        assert len(result["regions"])==5
        assert all(r["vi"]=="Đã sửa" for r in result["regions"])
        assert pipeline.memory.page("s","p","rev-a")["regions"]==result["regions"]
    finally:pipeline.memory.close()


def test_persistently_spurious_punctuation_cannot_enter_page_cache_or_story_memory(tmp_path,monkeypatch):
    from manga_live.providers import Translator
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    translator=Translator.__new__(Translator)
    translator.signature=lambda:"test"
    translator._translate=lambda regions,*args:([
        {"id":r["id"],"vi":'“Cảm ơn.”,'} for r in regions],{"translation_ms":1,"usage":{}})
    pipeline.translator=translator;events=[]
    try:
        with pytest.raises(AppError) as error:
            pipeline.process(params,data,threading.Event(),lambda name,payload:events.append(name))
        assert error.value.code=="MODEL_OUTPUT"
        assert "translated" not in events and "render-patch" not in events
        key=pipeline.page_cache_key("s","p",params["at"],hashlib.sha256(data).hexdigest(),None)
        assert pipeline.memory.cache_get(key) is None
        with pytest.raises(AppError):pipeline.memory.page("s","p","rev-a")
        assert pipeline.memory.next_job() is None
        assert not pipeline.memory.context("s",{"chapter":1,"page":1})["data"]["recent_dialogue"]
        assert calls["ocr"],"Completed source OCR remains independently reusable"
    finally:pipeline.memory.close()


def test_reader_term_edit_during_translation_cannot_publish_or_store_old_context(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch);events=[]
    source="氷結結界を展開する！";at=params["at"]
    pipeline.memory.canonical_term("s","ice","skill","氷結結界","Kết Giới Băng",[],at)
    monkeypatch.setattr(module,"recognize_regions",lambda image,regions,*a,**k:
        [{**r,"ja":source} for r in regions])
    def translate(regions,context,cancel):
        pipeline.memory.canonical_term("s","ice","skill","氷結結界","Kết giới băng giá",[],at)
        return [{"id":r["id"],"vi":"Triển khai Kết Giới Băng!"} for r in regions],{"translation_ms":1}
    pipeline.translator.translate=translate
    try:
        with pytest.raises(AppError) as error:
            pipeline.process(params,data,threading.Event(),lambda name,payload:events.append(name))
        assert error.value.code=="STALE_CONTEXT"
        assert "translated" not in events and "render-patch" not in events
        key=pipeline.page_cache_key("s","p",at,hashlib.sha256(data).hexdigest(),None)
        assert pipeline.memory.cache_get(key) is None
        with pytest.raises(AppError):pipeline.memory.page("s","p","rev-a")
        assert pipeline.memory.next_job() is None
    finally:pipeline.memory.close()


def test_reader_term_edit_during_cleanup_cannot_publish_or_cache_old_context(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch);events=[]
    source="氷結結界を展開する！";at=params["at"]
    pipeline.memory.canonical_term("s","ice","skill","氷結結界","Kết Giới Băng",[],at)
    pipeline.detectors["paddle"].detect=lambda image:[{"id":"r0","bbox":[0,0,20,20],"order":0,
                                                     "type":"dialogue","overlay":"label"}]
    monkeypatch.setattr(module,"recognize_regions",lambda image,regions,*a,**k:
        [{**r,"ja":source} for r in regions])
    pipeline.translator.translate=lambda regions,*args:([{ "id":r["id"],"vi":"Triển khai Kết Giới Băng!"}
        for r in regions],{"translation_ms":1})
    def cleanup(*args,**kwargs):
        pipeline.memory.canonical_term("s","ice","skill","氷結結界","Kết giới băng giá",[],at)
        return None
    monkeypatch.setattr(module,"render_patch",cleanup)
    try:
        with pytest.raises(AppError) as error:
            pipeline.process(params,data,threading.Event(),lambda name,payload:events.append(name))
        assert error.value.code=="STALE_CONTEXT"
        assert "translated" not in events
        key=pipeline.page_cache_key("s","p",at,hashlib.sha256(data).hexdigest(),None)
        assert pipeline.memory.cache_get(key) is None
        with pytest.raises(AppError):pipeline.memory.page("s","p","rev-a")
        # A stale failure is recoverable from retained OCR. The correction is
        # real reader memory, not a change to the fixture's source/gold text.
        monkeypatch.setattr(module,"render_patch",lambda *args,**kwargs:None)
        pipeline.detectors["paddle"].detect=lambda *args:pytest.fail("Do not detect again after stale context")
        monkeypatch.setattr(module,"recognize_regions",lambda *args,**kwargs:pytest.fail("Completed OCR must survive stale context"))
        def retry_translate(regions,context,cancel):
            assert any("Kết giới băng giá" in r["value"] for r in context["glossary"])
            return [{"id":r["id"],"vi":"Triển khai Kết giới băng giá!"} for r in regions],{"translation_ms":1}
        pipeline.translator.translate=retry_translate
        result=pipeline.process({**params,"revision":"rev-b"},data,threading.Event(),lambda *args:None)
        assert not result["cached"] and result["regions"][0]["vi"]=="Triển khai Kết giới băng giá!"
        assert pipeline.memory.page("s","p","rev-b")["regions"]==result["regions"]
    finally:pipeline.memory.close()


@pytest.mark.parametrize("event_name",["translated","render-patch"])
def test_reader_edit_after_publication_stops_later_batches_and_final_commit(tmp_path,monkeypatch,event_name):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch);events=[]
    detect=pipeline.detectors["paddle"].detect
    pipeline.detectors["paddle"].detect=lambda image:[{**r,"overlay":"label"} for r in detect(image)]
    monkeypatch.setattr(module,"render_patch",lambda *args,**kwargs:{
        "regionId":args[1]["id"],"bbox":[0,0,10,20],"dataUrl":"data:image/png;base64,AAAA"})
    def translate(regions,*args):
        calls["translate"]+=1
        return FakeTranslator().translate(regions,*args)
    pipeline.translator.translate=translate
    def emit(name,payload):
        events.append(name)
        if name==event_name:
            pipeline.memory.canonical_term("s","ice","skill","氷結結界","Kết giới băng giá",[],params["at"])
    try:
        with pytest.raises(AppError) as error:pipeline.process(params,data,threading.Event(),emit)
        assert error.value.code=="STALE_CONTEXT"
        assert calls["translate"]==1,"Do not buy a later batch after an earlier context is obsolete"
        assert events.count(event_name)==1
        if event_name=="render-patch":assert "translated" not in events
        key=pipeline.page_cache_key("s","p",params["at"],hashlib.sha256(data).hexdigest(),None)
        assert pipeline.memory.cache_get(key) is None
        with pytest.raises(AppError):pipeline.memory.page("s","p","rev-a")
        assert pipeline.memory.next_job() is None
    finally:pipeline.memory.close()


def test_reader_edit_after_last_translated_event_cannot_commit_page(tmp_path,monkeypatch):
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    detect=pipeline.detectors["paddle"].detect
    pipeline.detectors["paddle"].detect=lambda image:detect(image)[:1]
    def emit(name,payload):
        if name=="translated":
            pipeline.memory.canonical_term("s","ice","skill","氷結結界","Kết giới băng giá",[],params["at"])
    try:
        with pytest.raises(AppError) as error:pipeline.process(params,data,threading.Event(),emit)
        assert error.value.code=="STALE_CONTEXT"
        key=pipeline.page_cache_key("s","p",params["at"],hashlib.sha256(data).hexdigest(),None)
        assert pipeline.memory.cache_get(key) is None
        with pytest.raises(AppError):pipeline.memory.page("s","p","rev-a")
    finally:pipeline.memory.close()


def test_cached_page_cleanup_edit_preserves_old_revision_and_reader_correction(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch);events=[]
    detect=pipeline.detectors["paddle"].detect
    pipeline.detectors["paddle"].detect=lambda image:[{**r,"overlay":"label"} for r in detect(image)[:1]]
    monkeypatch.setattr(module,"render_patch",lambda *args,**kwargs:None)
    try:
        first=pipeline.process(params,data,threading.Event(),lambda *args:None)
        def cleanup(*args,**kwargs):
            pipeline.memory.canonical_term("s","ice","skill","氷結結界","Kết giới băng giá",[],params["at"])
            return {"regionId":"r0","bbox":[0,0,10,20],"dataUrl":"data:image/png;base64,AAAA"}
        monkeypatch.setattr(module,"render_patch",cleanup)
        with pytest.raises(AppError) as error:
            pipeline.process({**params,"revision":"rev-b"},data,threading.Event(),lambda name,payload:events.append(name))
        assert error.value.code=="STALE_CONTEXT"
        assert "translated" not in events and "render-patch" not in events
        assert pipeline.memory.page("s","p","rev-a")["regions"]==first["regions"]
        with pytest.raises(AppError):pipeline.memory.page("s","p","rev-b")
        assert any("Kết giới băng giá" in r["value"] for r in pipeline.memory.context("s",params["at"])["data"]["glossary"])
    finally:pipeline.memory.close()


def test_job_owned_term_revision_can_continue_and_external_stale_retry_reuses_ocr(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch);contexts=[]
    recognize=module.recognize_regions
    monkeypatch.setattr(module,"recognize_regions",lambda *args,**kwargs:
        [{**r,"ja":"氷結結界を展開する！"} for r in recognize(*args,**kwargs)])
    def translate(regions,context,cancel):
        contexts.append(context)
        result,metrics=FakeTranslator().translate(regions,context,cancel)
        if len(contexts)==1:metrics["terms"]=[{"region_id":regions[0]["id"],"category":"skill","ja":"氷結結界","vi":"Kết giới băng giá"}]
        return result,metrics
    pipeline.translator.translate=translate
    try:
        result=pipeline.process(params,data,threading.Event(),lambda *args:None)
        assert len(contexts)==2 and result["contextVersion"]==pipeline.memory.version("s")
        assert any("Kết giới băng giá" in r["value"] for r in contexts[1]["glossary"])
        pipeline.memory.canonical_term("s","ice","skill","氷結結界","Băng giới",[],params["at"])
        ocr_before=list(calls["ocr"])
        retry=pipeline.process({**params,"revision":"rev-b"},data,threading.Event(),lambda *args:None)
        assert not retry["cached"] and calls["ocr"]==ocr_before and calls["detector"]==1
        assert any("Băng giới" in r["value"] for r in contexts[-1]["glossary"])
    finally:pipeline.memory.close()


def test_reader_can_edit_while_cleanup_runs_without_a_long_memory_lock(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    detect=pipeline.detectors["paddle"].detect
    pipeline.detectors["paddle"].detect=lambda image:[{**r,"overlay":"label"} for r in detect(image)[:1]]
    writer_done=threading.Event();workers=[];edited_during_cleanup=[]
    def edit():
        pipeline.memory.canonical_term("s","ice","skill","氷結結界","Kết giới băng giá",[],params["at"])
        writer_done.set()
    def cleanup(*args,**kwargs):
        worker=threading.Thread(target=edit);workers.append(worker);worker.start()
        edited_during_cleanup.append(writer_done.wait(2))
        return None
    monkeypatch.setattr(module,"render_patch",cleanup)
    try:
        with pytest.raises(AppError) as error:pipeline.process(params,data,threading.Event(),lambda *args:None)
        assert error.value.code=="STALE_CONTEXT"
        assert edited_during_cleanup==[True],"Memory guard must not cover expensive cleanup"
    finally:
        for worker in workers:worker.join(3)
        pipeline.memory.close()


def test_final_page_and_translation_cache_commit_atomically(tmp_path,monkeypatch):
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    put=pipeline.memory.cache_put
    def failing_put(key,story,at,payload):
        put(key,story,at,payload)
        if "contextDependencies" in payload:raise AppError("STORAGE","Authored write failure")
    monkeypatch.setattr(pipeline.memory,"cache_put",failing_put)
    try:
        with pytest.raises(AppError) as error:pipeline.process(params,data,threading.Event(),lambda *args:None)
        assert error.value.code=="STORAGE"
        key=pipeline.page_cache_key("s","p",params["at"],hashlib.sha256(data).hexdigest(),None)
        assert pipeline.memory.cache_get(key) is None
        with pytest.raises(AppError):pipeline.memory.page("s","p","rev-a")
        monkeypatch.setattr(pipeline.memory,"cache_put",put)
        before=list(calls["ocr"])
        result=pipeline.process({**params,"revision":"rev-b"},data,threading.Event(),lambda *args:None)
        assert not result["cached"] and calls["ocr"]==before
    finally:pipeline.memory.close()


def test_retranslate_cannot_mix_old_speaker_with_new_context_snapshot(tmp_path,monkeypatch):
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch);at=params["at"]
    pipeline.memory.save_page("s","p",at,"rev-a",[{"id":"r","ja":"ありがとう。","vi":"Cảm ơn."}])
    pipeline.memory.set_speaker("s","p","r","A","B",at)
    read_speaker=pipeline.memory.speaker
    def changed_after_read(*args):
        old=read_speaker(*args)
        pipeline.memory.set_speaker("s","p","r","B","A",at)
        return old
    monkeypatch.setattr(pipeline.memory,"speaker",changed_after_read)
    pipeline.translator.translate=lambda *args:pytest.fail("Do not translate with a mixed speaker/context snapshot")
    try:
        with pytest.raises(AppError) as error:
            pipeline.retranslate({**params,"regionId":"r","ja":"ありがとう。"},threading.Event())
        assert error.value.code=="STALE_CONTEXT"
        assert read_speaker("s","p","r")=={"speaker":"B","listener":"A"}
        assert pipeline.memory.page("s","p","rev-a")["regions"][0]["vi"]=="Cảm ơn."
    finally:pipeline.memory.close()
