import io
import threading
from types import SimpleNamespace

from PIL import Image, ImageDraw
import pytest

from manga_live.memory import Memory
from manga_live.pipeline import Pipeline
from manga_live.text_scope import make_plan, route_regions, story_regions


def layout_fixture(title="作者コメント", with_panel=False):
    image=Image.new("RGB",(800,1000),"white")
    if with_panel:ImageDraw.Draw(image).rectangle((395,690,765,950),outline="black",width=3)
    regions=[{"id":"dialogue","bbox":[80,70,100,150],"order":0,"ja":"まだ帰らないの？",
              "balloon":{"textBox":[80,70,100,150]},"overlay":"white"},
             {"id":"thought","bbox":[500,80,45,140],"order":1,"ja":"どうしたらいいんだろう。","overlay":"label"}]
    # Authored multi-column supplementary block; no private manga coordinates.
    regions.extend({"id":f"note{i}","bbox":[720-i*50,720,36,180],"order":2+i,
                    "ja":title if i==0 else "これは短い説明です。","overlay":"label"} for i in range(6))
    return image,regions


def test_explicit_editorial_heading_routes_only_its_external_dense_block():
    image,regions=layout_fixture()
    plan=make_plan(image,regions,"source-a")
    routed=route_regions(regions,plan,{})
    assert [r["id"] for r in routed if r["scope"]["action"]=="defer"]==[f"note{i}" for i in range(6)]
    assert [r["id"] for r in story_regions(routed)]==["dialogue","thought"]
    assert all(r["scope"]["reason"]=="editorial_marker" for r in routed[2:])
    assert "scope" not in regions[0],"Do not mutate the cached OCR evidence"


@pytest.mark.parametrize("title",["母からの手紙","冒険者の依頼","犯人への手がかり","魔法講座を受けた。","魔法講座第1回",""])
def test_density_and_balloonless_text_are_not_skip_rules(title):
    image,regions=layout_fixture(title)
    assert all(r["scope"]["action"]=="translate" for r in route_regions(regions,make_plan(image,regions,"s"),{}))


def test_panel_contained_heading_is_not_treated_as_editorial():
    image,regions=layout_fixture(with_panel=True)
    assert all(r["scope"]["action"]=="translate" for r in route_regions(regions,make_plan(image,regions,"s"),{}))


def test_reader_override_wins_and_geometry_is_bound_to_source_pixels():
    image,regions=layout_fixture()
    plan=make_plan(image,regions,"source-a")
    first=route_regions(regions,plan,{})
    key=first[2]["scope"]["key"]
    override={key:{"role":"narration","action":"translate"}}
    assert route_regions(regions,plan,override)[2]["scope"]["memory"] is True
    assert route_regions(regions,make_plan(image,regions,"source-b"),override)[2]["scope"]["action"]=="defer"
    assert route_regions(regions,plan,{key:{"role":"editorial","action":"translate"}})[2]["scope"]["memory"] is False


def test_source_quote_is_not_an_editorial_header():
    image,regions=layout_fixture("作者コメントを読んだ？")
    assert all(r["scope"]["action"]=="translate" for r in route_regions(regions,make_plan(image,regions,"s"),{}))


def test_reader_role_does_not_send_empty_ocr_to_translation():
    image,regions=layout_fixture("母からの手紙")
    regions[0].update(ja="",review=True,reviewReasons=["ocr_empty"])
    plan=make_plan(image,regions,"unreadable-source")
    overrides={plan["keys"]["dialogue"]:{"role":"dialogue","action":"translate"}}
    result=route_regions(regions,plan,overrides)[0]
    assert result["ja"]=="" and result["scope"]["action"]=="defer"
    assert result["scope"]["memory"] is False and not story_regions([result])


def test_scope_deferral_never_reaches_translation_cleanup_or_story_memory(tmp_path,monkeypatch):
    import manga_live.pipeline as module
    image,regions=layout_fixture()
    memory=Memory(tmp_path/"scope.sqlite3")
    memory.ensure_story("s","Authored scope fixture")
    pipeline=Pipeline.__new__(Pipeline)
    pipeline.memory=memory;pipeline.config=SimpleNamespace(values={"detector":"paddle","ocrBatch":2,"artCleanup":True})
    pipeline.ocr=SimpleNamespace(name="fake-ocr")
    pipeline.detectors={"paddle":SimpleNamespace(detect=lambda image:regions)}
    calls={"translate":[],"cleanup":[]}
    def translate(items,context,cancel):
        calls["translate"].extend(r["id"] for r in items)
        return [{"id":r["id"],"vi":"Bản dịch tự tạo","ambiguous":False} for r in items],{"translation_ms":1}
    pipeline.translator=SimpleNamespace(signature=lambda:"test",translate=translate)
    monkeypatch.setattr(module,"recognize_regions",lambda image,items,*a,**k:[dict(r) for r in items])
    monkeypatch.setattr(module,"render_patch",lambda image,r,*a,**k:calls["cleanup"].append(r["id"]))
    buffer=io.BytesIO();image.save(buffer,format="PNG")
    params={"storyId":"s","title":"Authored scope fixture","pageId":"p","revision":"rev","at":{"chapter":1,"page":0}}
    try:
        result=pipeline.process(params,buffer.getvalue(),threading.Event(),lambda *a:None)
        assert calls["translate"]==["dialogue","thought"]
        assert calls["cleanup"]==["dialogue","thought"]
        assert len(result["regions"])==8,"Deferred OCR remains available to the reader"
        memory.mark_read("s","p","rev")
        job=memory.next_job()
        import json
        assert [r["id"] for r in json.loads(job["regions"])]==["dialogue","thought"]
        assert [r["id"] for r in memory.context("s",{"chapter":1,"page":1})["data"]["recent_dialogue"]]==["dialogue","thought"]
        memory.finish_job(job,{"summary":"Một câu hỏi và độc thoại.","facts":[]})
        calls["translate"].clear();calls["cleanup"].clear()
        cached=pipeline.process({**params,"revision":"rev2"},buffer.getvalue(),threading.Event(),lambda *a:None)
        assert cached["cached"] and not calls["translate"]
        assert set(calls["cleanup"])=={"dialogue","thought"},"Cache must not clean deferred source text"
        recovered=pipeline.retranslate({**params,"revision":"rev2","regionId":"note0","ja":"作者コメント",
            "recoverDeferred":True},threading.Event())
        assert recovered["scope"]["action"]=="translate" and recovered["scope"]["memory"] is False
        memory.mark_read("s","p","rev2")
        assert [r["id"] for r in json.loads(memory.next_job()["regions"])]==["dialogue","thought"]
        assert [r["id"] for r in memory.context("s",{"chapter":1,"page":1})["data"]["recent_dialogue"]]==["dialogue","thought"]
    finally:memory.close()


def test_summary_job_stamps_all_regions_even_when_the_prompt_filters_editorial(tmp_path):
    from manga_live.errors import AppError
    memory=Memory(tmp_path/"stamp.sqlite3");memory.ensure_story("s","Authored")
    at={"chapter":1,"page":0}
    regions=[{"id":"d","ja":"待って。","vi":"Đợi đã."},
        {"id":"e","ja":"作者コメント","scope":{"action":"defer","memory":False}}]
    try:
        memory.save_page("s","p",at,"rev",regions);memory.mark_read("s","p","rev")
        job=memory.next_job()
        memory.save_page("s","p",at,"rev",[regions[0],{**regions[1],"ja":"著者コメント"}])
        with pytest.raises(AppError) as failure:memory.finish_job(job,{"summary":"Có một lời yêu cầu.","facts":[]})
        assert failure.value.code=="STALE","Filtered-away source changes still invalidate pending jobs"
    finally:memory.close()
