"""A dots-only OCR output cannot silently turn edge-connected art into memory.

Authored positives/negatives exercise actual pixel routing, not label IDs.
Real source replay is separate; no assertion that this is a semantic detector.
"""
from pathlib import Path
import pytest
from PIL import Image,ImageDraw,ImageFont
from manga_live.text_scope import make_plan,route_regions,story_regions,key_for


def art_crop():
    image=Image.new("L",(64,64),255)
    ImageDraw.Draw(image).polygon([(10,10),(13,10),(22,23),(19,23)],fill=0)
    return image,[10,10,13,14]


def routed(image,box,text):
    regions=[{"id":"r","bbox":box,"ja":text,"order":0,"overlay":"label"}]
    return route_regions(regions,make_plan(image,regions,"authored-punctuation"),{})


@pytest.mark.parametrize("text",["．．．","...","…","⋯","‥", " … "])
def test_dots_read_from_dense_edge_connected_art_stay_reviewable_not_memory(text):
    image,box=art_crop();result=routed(image,box,text)
    assert result[0]["ja"]==text and result[0]["scope"]["action"]=="defer"
    assert result[0]["scope"]["reason"]=="visual_review" and not story_regions(result)
    assert "visual_punctuation_support" in result[0]["reviewReasons"]
    plan=make_plan(image,result,"authored-punctuation")
    assert route_regions(result,plan,{})==result
    key=result[0]["scope"]["key"]
    confirmed=route_regions(result,plan,{key:{"role":"dialogue","action":"translate"}})
    assert story_regions(confirmed)==confirmed,"Only an explicit reader role restores memory trust"


@pytest.mark.parametrize("text",["猫","一","！？","あ…", "お姉ちゃん", "・", "."])
def test_punctuation_hint_does_not_apply_to_words_or_other_punctuation(text):
    image,box=art_crop();result=routed(image,box,text)
    assert result[0]["scope"]["reason"]=="unclassified" and story_regions(result)==result


@pytest.mark.parametrize("vertical",[True,False])
@pytest.mark.parametrize("ink",[0,175])
def test_real_compact_three_dots_on_flat_paper_remain_trusted(vertical,ink):
    image=Image.new("L",(64,64),255);draw=ImageDraw.Draw(image)
    for i in range(3):
        x,y=(19,14+5*i) if vertical else (14+5*i,19)
        draw.ellipse((x,y,x+2,y+2),fill=ink)
    result=routed(image,[10,10,20,20],"．．．")
    assert not result[0].get("review") and story_regions(result)==result


@pytest.mark.parametrize("source",["…","‥","⋯","...","．．．"])
def test_authored_font_ellipsis_is_not_relabelled_art(source):
    font=Path("C:/Windows/Fonts/YuGothM.ttc")
    if not font.is_file():pytest.skip("Windows-authored source font")
    image=Image.new("L",(64,40),255)
    ImageDraw.Draw(image).text((8,4),source,font=ImageFont.truetype(str(font),12),fill=0)
    result=routed(image,[4,2,40,28],source)
    assert not result[0].get("review") and story_regions(result)==result


def test_tiny_border_marks_preserve_source_and_cannot_claim_memory_without_scope():
    image=Image.new("L",(64,64),255);draw=ImageDraw.Draw(image)
    for coords in ((10,10,13,14),(18,10,22,13),(20,18,22,22)):
        draw.rectangle(coords,fill=0)
    result=routed(image,[10,10,13,13],"．．．")
    assert not story_regions(result)
    assert not story_regions([{k:v for k,v in result[0].items() if k!="scope"}])
    assert not story_regions([{**result[0],"scope":{**result[0]["scope"],"memory":True,"reason":"unclassified"}}])


def test_existing_reader_scope_choice_survives_policy_upgrade():
    image,box=art_crop();regions=[{"id":"r","bbox":box,"ja":"...","order":0}]
    key=key_for(["text-scope-v3-weak-mark-review","same-source",box])
    result=route_regions(regions,make_plan(image,regions,"same-source"),{key:{"role":"sfx","action":"defer"}})
    assert result[0]["scope"]["key"]==key and result[0]["scope"]["reason"]=="reader"
    assert result[0]["scope"]["action"]=="defer" and not story_regions(result)
