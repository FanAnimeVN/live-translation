"""Unaccepted candidate: source geometry only; never automatic erasure rights."""
import pytest
from PIL import Image,ImageDraw,ImageOps
from manga_live.ocr import group_regions,polygon
from copy import deepcopy
from types import SimpleNamespace
import sys
from pathlib import Path


def detected(boxes):
    return [{"polygon":polygon(box),"score":.95} for box in boxes]


@pytest.mark.parametrize("scale",[.5,1,2])
@pytest.mark.parametrize("dark",[False,True])
def test_substantially_overlapping_aligned_columns_keep_every_source_point(scale,dark):
    image=Image.new("RGB",(int(827*scale),int(1170*scale)),"black" if dark else "white")
    quads=[[[305,69],[339,68],[342,202],[308,203]],[[286,69],[315,69],[315,232],[286,232]]]
    detections=[{"polygon":[[x*scale,y*scale] for x,y in p],"score":.95} for p in quads]
    assert len(group_regions(image,detections))==2,"Production default must stay unchanged during comparison"
    regions=group_regions(image,detections,experimental_open_overlap=True)
    assert len(regions)==1 and regions[0]["review"] and regions[0]["reviewReasons"]==["layout_cluster"]
    assert regions[0]["overlay"]=="label" and "balloon" not in regions[0]
    x,y,w,h=regions[0]["bbox"]
    assert all(x<=px<=x+w and y<=py<=y+h for d in detections for px,py in d["polygon"])


@pytest.mark.parametrize("boxes",[
    ([100,100,30,140],[123,100,30,140]),  # minor bbox/padding overlap only
    ([100,100,30,140],[135,100,30,140]),  # proximity is not this candidate
    ([100,100,30,140],[118,122,30,140]),  # staggered start
    ([100,100,30,140],[118,110,30,140],[136,120,30,140]),  # no transitive drift
    ([100,100,30,140],[118,100,10,40]),   # different scale/side annotation
])
def test_overlap_does_not_generalize_into_nearby_caption_or_drifted_block(boxes):
    image=Image.new("RGB",(500,600),"white")
    assert len(group_regions(image,detected(boxes),experimental_open_overlap=True))>=2


@pytest.mark.parametrize("dark",[False,True])
def test_new_candidate_does_not_change_bounded_balloon_veto_or_ownership(dark):
    image=Image.new("RGB",(500,600),"#777777");draw=ImageDraw.Draw(image)
    draw.rectangle((70,70,220,310),fill="white",outline="black",width=3)
    draw.line((140,80,140,280),fill="black",width=3)
    detections=detected(([98,100,35,140],[146,100,35,140]))
    if dark:image=ImageOps.invert(image)
    assert group_regions(image,detections,experimental_open_overlap=True)==group_regions(image,detections)


def test_horizontal_overlap_and_exact_threshold_are_source_scale_relative():
    image=Image.new("RGB",(500,600),"white")
    assert len(group_regions(image,detected(([100,100,140,30],[100,121,140,30])),experimental_open_overlap=True))==1
    assert len(group_regions(image,detected(([100,100,140,30],[100,122,140,30])),experimental_open_overlap=True))==2


def test_candidates_cannot_be_combined():
    with pytest.raises(ValueError,match="exactly one"):
        group_regions(Image.new("RGB",(300,400)),[],experimental_open_text=True,experimental_open_overlap=True)


def test_twenty_percent_comparator_is_not_a_runtime_default_or_erasure_permission():
    image=Image.new("RGB",(500,600),"white")
    detections=detected(([100,100,30,140],[123,100,30,140],[146,102,30,55]))
    assert len(group_regions(image,detections))==3
    assert len(group_regions(image,detections,experimental_open_overlap=True))==3
    proposed=group_regions(image,detections,experimental_open_overlap=True,minimum_open_overlap=.2)
    assert len(proposed)==1 and proposed[0]["review"]
    assert proposed[0]["overlay"]=="label" and "balloon" not in proposed[0]


@pytest.mark.parametrize("fraction",[0,1,.1,float("nan"),float("inf"),True,None])
def test_unsupported_fraction_cannot_silently_change_geometry(fraction):
    with pytest.raises(ValueError,match="bounded experimental"):
        group_regions(Image.new("RGB",(500,600)),[],experimental_open_overlap=True,minimum_open_overlap=fraction)


def test_nondefault_fraction_cannot_bypass_experiment_flag():
    with pytest.raises(ValueError,match="experimental comparator"):
        group_regions(Image.new("RGB",(500,600)),[],minimum_open_overlap=.2)


def test_private_grouping_evidence_keeps_exact_members_and_raw_scores_without_mutation():
    image=Image.new("RGB",(500,600),"white")
    source=detected(([100,100,30,140],[123,100,30,140],[146,102,30,55]))
    source[0]["score"]=.47;source[1]["score"]=.82
    original=deepcopy(source)
    groups=group_regions(image,source,experimental_open_overlap=True,minimum_open_overlap=.2,
                         include_source_members=True)
    assert len(groups)==1 and source==original
    assert groups[0]["sourceMembers"]==original and groups[0]["score"]==.47
    assert groups[0]["review"] and groups[0]["overlay"]=="label" and "balloon" not in groups[0]
    groups[0]["sourceMembers"][0]["polygon"][0][0]=0
    assert source==original,"Evidence must not be an alias into raw detector records"
    assert all("sourceMembers" not in r for r in group_regions(image,source))


def test_overlap_comparator_reports_actual_detector_input_even_when_a_crop_is_bounded():
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
    from probe_open_overlap import OverlapDetector
    image=Image.new("RGB",(500,600),"white")
    source=detected(([100,100,30,140],[123,100,30,140]))
    source[0]["score"]=.47
    probe=OverlapDetector(4,.2)
    probe.detector=SimpleNamespace(detect_raw=lambda image:source)
    groups=probe.detect(image)
    evidence=probe.last_evidence
    assert evidence["raw_detections"]==source
    assert evidence["raw_line_count"]==2 and evidence["grouped_count"]==len(groups)==1
    assert groups[0]["sourceMembers"]==source
    source[0]["score"]=.9
    assert evidence["raw_detections"][0]["score"]==.47
