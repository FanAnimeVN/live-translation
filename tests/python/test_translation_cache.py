"""Authored storage/pipeline regressions, not a translation-quality benchmark."""
import copy
import io
import json
import threading
from PIL import Image
import pytest

from manga_live.errors import AppError
from manga_live.memory import TTL
from manga_live.translation_cache import BATCH_CACHE_VERSION, batch_key, batch_payload, cached_batch
from test_pipeline import retry_fixture, FakeTranslator


def interrupted_page(tmp_path, monkeypatch):
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    generated=[]
    def translate(regions,context,cancel):
        generated.append([r["id"] for r in regions])
        if len(generated)==2:raise AppError("NETWORK","Authored later-batch failure")
        return FakeTranslator().translate(regions,context,cancel)
    pipeline.translator.translate=translate
    with pytest.raises(AppError) as error:
        pipeline.process(params,data,threading.Event(),lambda *args:None)
    assert error.value.code=="NETWORK"
    return pipeline,calls,data,params,generated


def checkpoints(memory):
    return [(row["key"],json.loads(row["payload"])) for row in memory.db.execute("SELECT key,payload FROM cache")
            if json.loads(row["payload"]).get("v")==BATCH_CACHE_VERSION]


@pytest.mark.parametrize("changed",["image","page","chapter","selection","model","prompt","batch-size"])
def test_resume_checkpoint_binds_source_cutoff_model_prompt_and_exact_group(tmp_path,monkeypatch,changed):
    pipeline,calls,data,params,generated=interrupted_page(tmp_path,monkeypatch)
    try:
        assert len(checkpoints(pipeline.memory))==1
        if changed=="image":
            buffer=io.BytesIO();Image.new("RGB",(100,100),"black").save(buffer,format="PNG");data=buffer.getvalue()
        elif changed=="page":params={**params,"pageId":"another-page"}
        elif changed=="chapter":params={**params,"at":{"chapter":2,"page":0}}
        elif changed=="selection":params={**params,"selection":[0,0,40,40]}
        elif changed=="model":pipeline.translator.signature=lambda:"other-model"
        elif changed=="prompt":monkeypatch.setattr("manga_live.pipeline.PROMPT_VERSION","changed-prompt")
        else:pipeline.first_batch_size=2
        result=pipeline.process({**params,"revision":"retry"},data,threading.Event(),lambda *args:None)
        assert result["metrics"]["reused_translation_groups"]==0
        assert generated[2]!=["r4","r5"],"A changed input must not borrow the old first group"
    finally:pipeline.memory.close()


@pytest.mark.parametrize("kind",["glossary","style","speaker","genre","recent"])
def test_relevant_reader_context_edits_do_not_reuse_old_group(tmp_path,monkeypatch,kind):
    pipeline,calls,data,params,generated=interrupted_page(tmp_path,monkeypatch);memory=pipeline.memory
    at=params["at"]
    try:
        if kind=="glossary":memory.canonical_term("s","thanks","other","ありがとう","Cảm tạ",[],at)
        elif kind=="style":memory.fact("s","style","honorifics","localize",at,{"type":"user"})
        elif kind=="speaker":
            import manga_live.pipeline as module
            bind=memory.bind_speakers
            monkeypatch.setattr(memory,"bind_speakers",lambda *args,**kwargs:
                {key:{**value,"speaker":"A","listener":"B"} for key,value in bind(*args,**kwargs).items()})
        elif kind=="genre":memory.ensure_story("s","Retry fixture",genre="fantasy")
        else:
            earlier={"chapter":0,"page":0}
            memory.save_page("s","previous",earlier,"old",[{"id":"old","ja":"さようなら。","vi":"Tạm biệt."}],state="read")
        result=pipeline.process({**params,"revision":"retry"},data,threading.Event(),lambda *args:None)
        assert result["metrics"]["reused_translation_groups"]==0
        assert generated[2]==["r0","r2","r3"]
    finally:memory.close()


def test_future_fact_does_not_evict_or_leak_into_earlier_checkpoint(tmp_path,monkeypatch):
    pipeline,calls,data,params,generated=interrupted_page(tmp_path,monkeypatch)
    pipeline.memory.fact("s","event","future","Authored future event",{"chapter":80,"page":0},{"type":"user"})
    translate=pipeline.translator.translate
    def checked(regions,context,cancel):
        assert "Authored future event" not in json.dumps(context)
        return translate(regions,context,cancel)
    pipeline.translator.translate=checked
    try:
        result=pipeline.process({**params,"revision":"retry"},data,threading.Event(),lambda *args:None)
        assert result["metrics"]["reused_translation_groups"]==1
        assert generated[2]==["r4","r5"]
    finally:pipeline.memory.close()


def test_expired_group_is_not_reused(tmp_path,monkeypatch):
    pipeline,calls,data,params,generated=interrupted_page(tmp_path,monkeypatch)
    now=pipeline.memory.clock()
    try:
        monkeypatch.setattr(pipeline.memory,"clock",lambda:now+TTL+1)
        result=pipeline.process({**params,"revision":"retry"},data,threading.Event(),lambda *args:None)
        assert result["metrics"]["reused_translation_groups"]==0 and generated[2]==["r0","r2","r3"]
    finally:pipeline.memory.close()


def test_checkpoint_hit_does_not_extend_its_expiry(tmp_path,monkeypatch):
    pipeline,calls,data,params,generated=interrupted_page(tmp_path,monkeypatch)
    now=pipeline.memory.clock()
    try:
        key,_=checkpoints(pipeline.memory)[0]
        expiry=pipeline.memory.db.execute("SELECT expires FROM cache WHERE key=?",(key,)).fetchone()[0]
        monkeypatch.setattr(pipeline.memory,"clock",lambda:now+100)
        pipeline.process({**params,"revision":"retry"},data,threading.Event(),lambda *args:None)
        assert pipeline.memory.db.execute("SELECT expires FROM cache WHERE key=?",(key,)).fetchone()[0]==expiry
    finally:pipeline.memory.close()


@pytest.mark.parametrize("bad",["json","version","wrong-id","empty-text","quote-only","extra-fields"])
def test_corrupt_group_is_a_miss_and_cannot_restore_arbitrary_fields(tmp_path,monkeypatch,bad):
    pipeline,calls,data,params,generated=interrupted_page(tmp_path,monkeypatch)
    try:
        key,payload=checkpoints(pipeline.memory)[0]
        if bad=="version":payload["v"]="unknown-version"
        elif bad=="wrong-id":payload["items"][0]["id"]="wrong"
        elif bad=="empty-text":payload["items"][0]["vi"]=""
        elif bad=="quote-only":payload["items"][0]["vi"]="“"
        elif bad=="extra-fields":payload["items"][0]["dataUrl"]="RAM_ONLY_SENTINEL"
        encoded="not-json" if bad=="json" else json.dumps(payload,ensure_ascii=False)
        with pipeline.memory.transaction() as db:db.execute("UPDATE cache SET payload=? WHERE key=?",(encoded,key))
        result=pipeline.process({**params,"revision":"retry"},data,threading.Event(),lambda *args:None)
        assert "RAM_ONLY_SENTINEL" not in str(result)
        if bad=="extra-fields":assert result["metrics"]["reused_translation_groups"]==1
        else:assert result["metrics"]["reused_translation_groups"]==0 and generated[2]==["r0","r2","r3"]
    finally:pipeline.memory.close()


@pytest.mark.parametrize("event_name",["regions","translated"])
@pytest.mark.parametrize("change",["edit","cancel"])
def test_reader_edit_or_cancellation_on_resume_cannot_continue_cached_work(tmp_path,monkeypatch,event_name,change):
    pipeline,calls,data,params,generated=interrupted_page(tmp_path,monkeypatch)
    events=[];cancel=threading.Event()
    def emit(name,payload):
        events.append(name)
        if name==event_name:
            if change=="edit":pipeline.memory.fact("s","style","honorifics","localize",params["at"],{"type":"user"})
            else:cancel.set()
    try:
        with pytest.raises(AppError) as error:
            pipeline.process({**params,"revision":"retry"},data,cancel,emit)
        assert error.value.code==("STALE_CONTEXT" if change=="edit" else "CANCELED")
        assert len(generated)==2,"Do not generate later groups after a stale cached publication"
        if event_name=="regions":assert "translated" not in events
        with pytest.raises(AppError):pipeline.memory.page("s","p","retry")
    finally:pipeline.memory.close()


def test_checkpoint_keeps_only_text_not_usage_geometry_images_or_prompt(tmp_path,monkeypatch):
    pipeline,calls,data,params,generated=interrupted_page(tmp_path,monkeypatch)
    try:
        key,payload=checkpoints(pipeline.memory)[0]
        assert set(payload)=={"v","items","terms"}
        assert all(set(item)=={"id","vi","ambiguous"} for item in payload["items"])
        assert payload["terms"]==[]
        exported=pipeline.memory.export("s")
        assert "cache" not in exported and "Đã sửa" not in str(exported)
    finally:pipeline.memory.close()


def trusted_plan(monkeypatch):
    """Authored white test pixels do not supply real glyph/memory evidence."""
    import manga_live.pipeline as module
    make_plan=module.make_plan
    def plan(*args):
        result=make_plan(*args)
        result["visual_review"]=set();result["punctuation_review"]=set()
        return result
    monkeypatch.setattr(module,"make_plan",plan)


def test_auto_accepted_term_does_not_rekey_an_old_translation_as_new_context(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    trusted_plan(monkeypatch)
    recognize=module.recognize_regions
    monkeypatch.setattr(module,"recognize_regions",lambda *args,**kwargs:
        [{**r,"ja":"氷結結界を展開する！"} for r in recognize(*args,**kwargs)])
    generated=[]
    def translate(regions,context,cancel):
        generated.append([r["id"] for r in regions])
        if len(generated)==2:raise AppError("NETWORK","Authored second-group failure")
        return ([{"id":r["id"],"vi":"Triển khai Kết giới băng giá!"} for r in regions],
            {"translation_ms":1,"terms":[{"region_id":regions[0]["id"],"category":"skill",
                "ja":"氷結結界","vi":"Kết giới băng giá"}]})
    pipeline.translator.translate=translate
    try:
        with pytest.raises(AppError):pipeline.process(params,data,threading.Event(),lambda *args:None)
        assert len(pipeline.memory.export("s")["facts"])==1
        assert len(checkpoints(pipeline.memory))==1
        result=pipeline.process({**params,"revision":"retry"},data,threading.Event(),lambda *args:None)
        assert generated[2]==["r0","r2","r3"],"New glossary is not the context that generated the old text"
        assert result["metrics"]["reused_translation_groups"]==0
        assert len(pipeline.memory.export("s")["facts"])==1,"Replaying grounded terms cannot duplicate a lock"
    finally:pipeline.memory.close()


def test_changed_earlier_translation_invalidates_a_cached_later_group(tmp_path,monkeypatch):
    import hashlib
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    trusted_plan(monkeypatch);generated=[]
    def translate(regions,context,cancel):
        generated.append([r["id"] for r in regions])
        items,measurement=FakeTranslator().translate(regions,context,cancel)
        if len(generated)>2:items=[{**item,"vi":"Đã cảm ơn."} for item in items]
        if regions[0]["id"]=="r4":assert len(context["recent_dialogue"])==3
        return items,measurement
    pipeline.translator.translate=translate
    try:
        pipeline.process(params,data,threading.Event(),lambda *args:None)
        saved=checkpoints(pipeline.memory)
        assert len(saved)==2
        first_key=next(key for key,payload in saved if payload["items"][0]["id"]=="r0")
        page_key=pipeline.page_cache_key("s","p",params["at"],hashlib.sha256(data).hexdigest(),None)
        with pipeline.memory.transaction() as db:db.execute("DELETE FROM cache WHERE key IN (?,?)",(first_key,page_key))
        result=pipeline.process({**params,"revision":"retry"},data,threading.Event(),lambda *args:None)
        assert result["metrics"]["reused_translation_groups"]==0
        assert generated==[["r0","r2","r3"],["r4","r5"],["r0","r2","r3"],["r4","r5"]]
    finally:pipeline.memory.close()


def test_real_translator_guards_keep_failed_later_ids_out_of_checkpoint(tmp_path,monkeypatch):
    from manga_live.providers import Translator
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch)
    translator=Translator.__new__(Translator);translator.signature=lambda:"authored-cloud"
    generated=[]
    def raw_translate(regions,context,cancel):
        generated.append([r["id"] for r in regions])
        target="“" if len(generated) in (2,3) else "Cảm ơn."
        return [{"id":r["id"],"vi":target} for r in regions],{"translation_ms":1}
    translator._translate=raw_translate;pipeline.translator=translator
    try:
        with pytest.raises(AppError) as error:pipeline.process(params,data,threading.Event(),lambda *args:None)
        assert error.value.code=="MODEL_OUTPUT" and len(generated)==3
        assert len(checkpoints(pipeline.memory))==1
        result=pipeline.process({**params,"revision":"retry"},data,threading.Event(),lambda *args:None)
        assert len(generated)==4 and generated[-1]==["r4","r5"]
        assert result["metrics"]["reused_translation_groups"]==1
        assert all(r["vi"]=="Cảm ơn." for r in result["regions"])
    finally:pipeline.memory.close()


@pytest.mark.parametrize("when",["translation","cleanup","publication"])
def test_canceled_or_unpublished_first_group_is_never_checkpointed(tmp_path,monkeypatch,when):
    import manga_live.pipeline as module
    pipeline,calls,data,params=retry_fixture(tmp_path,monkeypatch);cancel=threading.Event()
    def translate(regions,context,event):
        if when=="translation":cancel.set()
        return FakeTranslator().translate(regions,context,event)
    def clean(*args,**kwargs):
        if when=="cleanup":cancel.set()
        return None
    def emit(name,payload):
        if when=="publication" and name=="translated":cancel.set()
    pipeline.translator.translate=translate;monkeypatch.setattr(module,"render_patch",clean)
    try:
        with pytest.raises(AppError) as error:pipeline.process(params,data,cancel,emit)
        assert error.value.code=="CANCELED" and not checkpoints(pipeline.memory)
    finally:pipeline.memory.close()


def test_group_key_includes_preceding_page_dialogue_and_source_anchors():
    region={"id":"r","ja":"ありがとう。","scope":{"key":"source-key"}}
    context={"recent_dialogue":[{"ja":"先に帰ってて。","vi":"Em về trước đi."}]}
    key=batch_key("page-key",[region],context)
    changed=copy.deepcopy(context);changed["recent_dialogue"][0]["vi"]="Chị về trước đi."
    assert batch_key("page-key",[region],changed)!=key
    assert batch_key("page-key",[{**region,"scope":{"key":"changed-source"}}],context)!=key
    assert batch_key("another-page",[region],context)!=key


@pytest.mark.parametrize("target",["“",'“Cảm ơn.”',"ありがとう。"])
def test_checkpoint_rechecks_narrow_output_guards(target):
    regions=[{"id":"r","ja":"どうもありがとうございます。"}]
    if target=="ありがとう。":target=regions[0]["ja"]
    assert batch_payload(regions,{},[{"id":"r","vi":target}]) is None


def test_checkpoint_preserves_genuine_source_quotes_and_discards_ungrounded_terms():
    regions=[{"id":"r","ja":"「ありがとう。」"}]
    payload=batch_payload(regions,{},[{"id":"r","vi":"“Cảm ơn.”"}],
        [{"region_id":"r","ja":"氷結結界","vi":"Băng giới","category":"skill"}])
    assert payload["items"][0]["vi"]=="“Cảm ơn.”" and payload["terms"]==[]
    assert cached_batch(payload,regions,{})==payload
