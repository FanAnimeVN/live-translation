"""Experimental crop geometry is bounded and must preserve the production seam."""
import sys
from pathlib import Path
from types import SimpleNamespace
import threading

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from probe_ocr_polygons import padded_box,polygon_crop,crop_recognizer,PolygonDetector
from manga_live.ocr import polygon
from PIL import Image,ImageDraw
import pytest


def authored_source():
    image=Image.new("RGB",(160,200),"white")
    ImageDraw.Draw(image).rectangle((55,45,60,105),fill="black")
    return image,[[50,40],[74,38],[76,110],[52,112]]


@pytest.mark.parametrize("strategy",["mask","rectify","rectify-halo"])
def test_polygon_crop_is_ram_only_does_not_rotate_vertical_text_or_mutate_source(strategy):
    image,quad=authored_source();before=image.tobytes();points=[p.copy() for p in quad]
    result=polygon_crop(image,quad,strategy)
    assert result is not None and result.mode=="RGB" and result.height>result.width
    assert result.getextrema()[0][0]<50,"Authored interior ink must survive"
    assert image.tobytes()==before and quad==points


def test_mask_crop_changes_only_outside_detector_quad_and_preserves_size():
    image,quad=authored_source()
    x,y,w,h=padded_box(image,quad)
    ImageDraw.Draw(image).point((x,y),fill="black")
    result=polygon_crop(image,quad,"mask")
    assert result.size==(w,h) and result.getpixel((0,0))==(255,255,255)
    assert result.getpixel((58-x,60-y))==(0,0,0)
    assert image.getpixel((x,y))==(0,0,0)


def test_rectify_halo_retains_source_margin_not_a_synthetic_uniform_border():
    image=Image.new("RGB",(120,140),"white")
    quad=polygon([40,30,24,80])
    ImageDraw.Draw(image).rectangle((38,27,40,29),fill="black")
    without=polygon_crop(image,quad,"rectify")
    with_halo=polygon_crop(image,quad,"rectify-halo")
    assert with_halo.size==(without.width+6,without.height+6)
    assert with_halo.getpixel((2,2))[0]<30,"Source margin ink must be sampled, not repainted white"
    assert without.getextrema()==((255,255),)*3


@pytest.mark.parametrize("quad",[None,[],[[0,0]]*4,[[0,0],[0,0],[1,1],[3,3]],
    [[-1,0],[20,0],[20,30],[0,30]],[[0,0],[float("nan"),0],[20,30],[0,30]],
    [[0,0],[True,0],[20,30],[0,30]],[[0,0],[20,0],[0,30],[20,30]]])
def test_unsupported_quad_falls_back_instead_of_inventing_a_crop(quad):
    image,_=authored_source()
    assert polygon_crop(image,quad,"mask") is None
    assert polygon_crop(image,quad,"rectify") is None


def test_large_polygon_or_extreme_skew_keeps_original_crop():
    image=Image.new("RGB",(1200,1200),"white")
    assert polygon_crop(image,polygon([0,0,1000,1000]),"mask") is None
    assert polygon_crop(image,[[10,10],[40,35],[45,100],[15,75]],"rectify") is None


def test_duplicate_or_merged_evidence_is_not_selected_by_prediction_or_gold():
    image,quad=authored_source();box=padded_box(image,quad)
    detector=SimpleNamespace(quads=[quad,quad])
    counts={"regions":0,"transformed":0};seen=[]
    def recognize_many(images):
        seen.extend(images);return ["テスト"]*len(images)
    result=crop_recognizer(detector,"mask",counts)(image,[{"id":"r","bbox":box,"score":.9}],
        SimpleNamespace(recognize_many=recognize_many),threading.Event(),batch_size=1)
    assert [r["id"] for r in result]==["r"] and counts=={"regions":1,"transformed":0}
    x,y,w,h=box
    assert seen[0].tobytes()==image.crop((x,y,x+w,y+h)).tobytes()


def test_crop_adapter_keeps_batch_order_count_and_original_region_geometry():
    image,quad=authored_source();box=padded_box(image,quad)
    detector=SimpleNamespace(quads=[quad])
    counts={"regions":0,"transformed":0};seen=[]
    def recognize_many(images):
        seen.extend([i.size for i in images]);return ["日本"]*len(images)
    regions=[{"id":"a","bbox":box,"score":.9},{"id":"b","bbox":[85,40,30,72],"score":.9}]
    result=crop_recognizer(detector,"rectify",counts)(image,regions,
        SimpleNamespace(recognize_many=recognize_many),threading.Event(),batch_size=2)
    assert [r["id"] for r in result]==["a","b"]
    assert [r["bbox"] for r in result]==[r["bbox"] for r in regions]
    assert counts=={"regions":2,"transformed":1} and seen[1]==(30,72)
    assert seen[0][1]>seen[0][0]


def test_detector_captures_once_keeps_actual_scores_and_grouping(monkeypatch):
    import probe_ocr_polygons as module
    image,quad=authored_source();calls=[]
    raw=[{"polygon":quad,"score":.47}]
    detector=PolygonDetector.__new__(PolygonDetector)
    detector.detector=SimpleNamespace(detect_raw=lambda image:calls.append("detect") or raw)
    monkeypatch.setattr(module,"group_regions",lambda image,items:items)
    assert detector.detect(image)==raw and calls==["detect"] and detector.quads==[quad]
