"""Visual uncertainty is not proof that a region is unimportant or non-text."""
import io
import json
import threading
from pathlib import Path
from types import SimpleNamespace

from PIL import Image,ImageDraw,ImageFont
import pytest

from manga_live.image_signal import weak_glyph_signal
from manga_live.memory import Memory
from manga_live.pipeline import Pipeline
from manga_live.text_scope import make_plan,route_regions,story_regions


def noisy_fixture():
    image=Image.new("RGB",(220,130),"white")
    draw=ImageDraw.Draw(image)
    for x,y in ((14,15),(23,20),(29,27),(18,30)):
        draw.rectangle((x,y,x+2,y+2),fill=(200,200,200))
    draw.text((74,22),"Reader",fill="black")
    regions=[{"id":"noise","bbox":[10,10,26,24],"order":0,"ja":"魔法団","overlay":"label"},
             {"id":"dialogue","bbox":[70,18,110,38],"order":1,"ja":"光の剣","overlay":"label"}]
    return image,regions


def test_pixel_signal_marks_only_the_nonempty_weak_crop_not_the_adjacent_text():
    image,regions=noisy_fixture()
    assert weak_glyph_signal(image,regions[0]["bbox"])
    assert not weak_glyph_signal(image,regions[1]["bbox"])
    assert not weak_glyph_signal(Image.new("RGB",(26,24),"white"),[0,0,26,24])


@pytest.mark.parametrize("paper,ink",[(255,0),(255,175),(40,150)])
def test_readable_grey_and_reverse_print_are_not_called_noise(paper,ink):
    path=Path("C:/Windows/Fonts/YuGothM.ttc")
    if not path.is_file():pytest.skip("Windows-authored Japanese font")
    image=Image.new("L",(180,52),paper)
    ImageDraw.Draw(image).text((6,4),"まだ帰らないの？",font=ImageFont.truetype(str(path),16),fill=ink)
    assert not weak_glyph_signal(image,[0,0,180,52])


def test_three_real_dots_and_unbounded_geometry_are_not_weak_signal():
    image=Image.new("RGB",(90,48),"white");draw=ImageDraw.Draw(image)
    for x in (18,40,62):draw.ellipse((x,18,x+4,22),fill="black")
    assert not weak_glyph_signal(image,[8,8,72,32])
    assert not weak_glyph_signal(image,[-1,0,20,20])
    assert not weak_glyph_signal(image,[0,0,400,400])


@pytest.mark.parametrize("box",[None,[],[0,0,8],[0,0,True,8],[0,0,float("inf"),8],
    [0,0,float("nan"),8],[0,0,-8,8],[.5,0,8,8],[0,0,96,96]])
def test_unsupported_or_excessive_geometry_is_not_a_text_verdict(box):
    assert not weak_glyph_signal(Image.new("RGB",(220,130),"white"),box)


@pytest.mark.parametrize("source",["一","！？","…","あ","せんぱい"])
@pytest.mark.parametrize("ink",[0,175,210])
def test_small_authored_japanese_and_punctuation_remain_outside_sparse_mark_hint(source,ink):
    path=Path("C:/Windows/Fonts/YuGothM.ttc")
    if not path.is_file():pytest.skip("Windows-authored Japanese font")
    image=Image.new("L",(90,40),255)
    ImageDraw.Draw(image).text((6,4),source,font=ImageFont.truetype(str(path),12),fill=ink)
    assert not weak_glyph_signal(image,[0,0,90,40])


def test_visual_review_keeps_translation_source_visible_but_not_plot_memory():
    image,regions=noisy_fixture();plan=make_plan(image,regions,"authored")
    routed=route_regions(regions,plan,{})
    noise=routed[0]
    assert noise["ja"]==regions[0]["ja"] and noise["scope"]["action"]=="translate"
    assert noise["review"] and "visual_low_signal" in noise["reviewReasons"]
    assert noise["scope"]["reason"]=="visual_review" and noise["scope"]["memory"] is False
    assert [r["id"] for r in story_regions(routed)]==["dialogue"]
    assert "scope" not in regions[0] and "reviewReasons" not in regions[0]
    assert not story_regions([{**noise,"scope":{**noise["scope"],"memory":True}}]),"Contradictory scope is not trusted"
    assert not story_regions([{k:v for k,v in noise.items() if k!="scope"}]),"Missing scope cannot upgrade a weak flag"
    override={noise["scope"]["key"]:{"role":"dialogue","action":"translate"}}
    assert route_regions(regions,plan,override)[0]["scope"]["memory"] is True


def test_visual_review_is_idempotent_and_never_mutates_prior_review_evidence():
    image,regions=noisy_fixture()
    regions[0].update(review=True,reviewReasons=["quote_balance"])
    plan=make_plan(image,regions,"authored")
    first=route_regions(regions,plan,{})
    second=route_regions(first,plan,{})
    assert first==second
    assert regions[0]["reviewReasons"]==["quote_balance"]
    assert first[0]["reviewReasons"]==["quote_balance","visual_low_signal"]


def test_small_punctuation_is_never_dropped_or_rewritten_by_a_visual_hint():
    image,regions=noisy_fixture();regions[0]["ja"]="…"
    result=route_regions(regions,make_plan(image,regions,"punctuation"),{})
    # A broad crop with ordinary surrounding pixels is not enough evidence to
    # defer an ellipsis; only the edge-connected, tiny case above is deferred.
    assert len(result)==2 and result[0]["ja"]=="…" and result[0]["scope"]["action"]=="translate"


@pytest.mark.parametrize("signal",["weak","punctuation"])
def test_weak_source_does_not_enter_recent_dialogue_jobs_or_automatic_terms(tmp_path,monkeypatch,signal):
    import manga_live.pipeline as module
    image,regions=noisy_fixture()
    if signal=="punctuation":
        ImageDraw.Draw(image).polygon([(10,10),(13,10),(22,23),(19,23)],fill="black")
        regions[0].update(bbox=[10,10,13,14],ja="．．．")
    memory=Memory(tmp_path/"weak.sqlite3");memory.ensure_story("s","Authored source quality")
    pipeline=Pipeline.__new__(Pipeline)
    pipeline.memory=memory;pipeline.config=SimpleNamespace(values={"detector":"paddle","ocrBatch":2,"artCleanup":True})
    pipeline.ocr=SimpleNamespace(name="fake-ocr")
    pipeline.detectors={"paddle":SimpleNamespace(detect=lambda image:regions)}
    def translate(items,context,cancel):
        return ([{"id":r["id"],"vi":"Ma pháp đoàn" if r["id"]=="noise" else "Kiếm Ánh Sáng"} for r in items],
            {"translation_ms":1,"terms":[{"ja":r["ja"],"vi":"Ma pháp đoàn" if r["id"]=="noise" else "Kiếm Ánh Sáng",
                "category":"organization" if r["id"]=="noise" else "weapon","region_id":r["id"]} for r in items]})
    pipeline.translator=SimpleNamespace(signature=lambda:"test",translate=translate)
    monkeypatch.setattr(module,"recognize_regions",lambda image,items,*a,**k:[dict(r) for r in items])
    monkeypatch.setattr(module,"render_patch",lambda *a,**k:None)
    buffer=io.BytesIO();image.save(buffer,format="PNG")
    params={"storyId":"s","title":"Authored source quality","pageId":"p","revision":"rev","at":{"chapter":1,"page":0}}
    try:
        result=pipeline.process(params,buffer.getvalue(),threading.Event(),lambda *a:None)
        expected_ja="．．．" if signal=="punctuation" else "魔法団"
        assert len(result["regions"])==2 and result["regions"][0]["ja"]==expected_ja,"No silent source removal"
        if signal=="punctuation":
            assert "vi" not in result["regions"][0] and result["regions"][0]["scope"]["action"]=="defer"
        else:
            assert result["regions"][0]["vi"]=="Ma pháp đoàn"
        assert all("Ma pháp đoàn" not in r["value"] for r in memory.context("s",params["at"])["data"]["glossary"])
        assert all(t["ja"]!="魔法団" for t in result["termSuggestions"])
        # Accepting a legitimate new weapon term invalidates the old context
        # snapshot once. A stable subsequent pass must be cached, not mistrusted.
        pipeline.process({**params,"revision":"rev2"},buffer.getvalue(),threading.Event(),lambda *a:None)
        cached=pipeline.process({**params,"revision":"rev2"},buffer.getvalue(),threading.Event(),lambda *a:None)
        assert cached["cached"] and cached["regions"][0]["scope"]["memory"] is False
        # A reader may correct OCR without asserting what those pixels depict.
        # No implicit permission to create facts/terms from "Lưu & dịch lại".
        corrected=pipeline.retranslate({**params,"revision":"rev2","regionId":"noise","ja":"魔法団",
            **({"recoverDeferred":True} if signal=="punctuation" else {})},threading.Event())
        if signal=="punctuation":
            assert corrected["scope"]["reason"]=="reader" and corrected["scope"]["memory"] is False
        else:
            assert corrected["scope"]["reason"]=="visual_review" and corrected["scope"]["memory"] is False
        assert all("Ma pháp đoàn" not in r["value"] for r in memory.context("s",params["at"])["data"]["glossary"])
        memory.mark_read("s","p","rev2");job=memory.next_job()
        assert [r["id"] for r in json.loads(job["regions"])]==["dialogue"]
        assert [r["id"] for r in memory.context("s",{"chapter":1,"page":1})["data"]["recent_dialogue"]]==["dialogue"]
    finally:memory.close()
