"""Connected paper is not one utterance; only source outline geometry counts."""
import pytest
import numpy as np
import cv2
from PIL import Image,ImageOps
from manga_live.ocr import group_regions,polygon,rect


def touching_lobes(dark=False,horizontal=False,wide_neck=False):
    mask=np.zeros((1000,800),dtype="uint8")
    cv2.ellipse(mask,(112 if wide_neck else 102,145),(37 if wide_neck else 33,72),0,0,360,1,-1)
    cv2.ellipse(mask,(188,172),(67,102),0,0,360,1,-1)
    # Panel clips the upper arcs, so there is only a lower concave boundary.
    # A test requiring two straight separators would miss the real pattern.
    mask[:105]=0
    image=np.full((1000,800,3),119,dtype="uint8");image[mask>0]=255
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(image,contours,-1,(0,0,0),2)
    boxes=[[98,111,25,92],[135,111,26,103],[160,110,28,149],[187,112,27,144]]
    source=Image.fromarray(image)
    if dark:source=ImageOps.invert(source)
    if horizontal:
        source=source.transpose(Image.Transpose.TRANSPOSE)
        boxes=[[y,x,h,w] for x,y,w,h in boxes]
    return source,[{"polygon":polygon(box),"score":.95} for box in boxes]


@pytest.mark.parametrize("dark",[False,True])
@pytest.mark.parametrize("horizontal",[False,True])
def test_clipped_touching_balloons_split_at_the_outer_notch_not_a_fictional_inner_line(dark,horizontal):
    image,detections=touching_lobes(dark,horizontal)
    regions=group_regions(image,detections)
    assert len(regions)==2,"A shorter lobe ending at a deep outline notch must not swallow its neighbour"
    assert all("balloon" not in r for r in regions),"A split alone never proves new erasure ownership"
    assert all(r.get("reviewReasons")==["layout_fragment"] for r in regions)


@pytest.mark.parametrize("dark",[False,True])
def test_a_single_balloon_tail_below_all_text_does_not_split_an_utterance(dark):
    mask=np.zeros((1000,800),dtype="uint8")
    cv2.ellipse(mask,(165,170),(100,120),0,0,360,1,-1)
    cv2.fillPoly(mask,[np.array([[125,253],[180,350],[182,256]],dtype="int32")],1)
    pixels=np.full((1000,800,3),119,dtype="uint8");pixels[mask>0]=255
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    cv2.drawContours(pixels,contours,-1,(0,0,0),2)
    image=Image.fromarray(pixels)
    if dark:image=ImageOps.invert(image)
    boxes=([105,100,28,105],[140,100,28,125],[175,100,28,140])
    regions=group_regions(image,[{"polygon":polygon(box),"score":.95} for box in boxes])
    assert len(regions)==1,"A tail is not a second speaker or text block"


def test_deep_shape_indentation_cannot_cut_through_the_middle_of_a_detected_column():
    image,detections=touching_lobes()
    # One wide detection already crosses the suspected border. Splitting it
    # by geometry would be invented segmentation; keep that source crop.
    regions=group_regions(image,[{"polygon":polygon(box),"score":.95} for box in
                                ([98,111,70,149],[187,112,27,144])])
    assert len(regions)==1


def test_shallow_outer_indentation_alone_is_not_enough_to_split_text():
    image,detections=touching_lobes(wide_neck=True)
    assert len(group_regions(image,detections))==1


def test_disabling_only_the_boundary_veto_reproduces_the_same_overmerge(monkeypatch):
    from manga_live import layout_geometry
    image,detections=touching_lobes()
    assert len(group_regions(image,detections))==2
    monkeypatch.setattr(layout_geometry,"paper_notch_cuts",lambda *args:[])
    assert len(group_regions(image,detections))==1


def test_notch_below_every_detected_line_is_not_a_second_block_even_with_a_deep_contour():
    image,detections=touching_lobes()
    shortened=[]
    for detection in detections:
        x,y,w,h=rect(detection["polygon"])
        shortened.append({**detection,"polygon":polygon([x,y,w,90])})
    assert len(group_regions(image,shortened))==1


def test_outline_notch_does_not_supply_a_missing_column_gap():
    image,detections=touching_lobes()
    detections[1]={"polygon":polygon([128,111,26,103]),"score":.95}
    assert len(group_regions(image,detections))==1


@pytest.mark.parametrize("scale",[.5,1.5,2])
def test_outline_veto_scales_with_lettering_not_fixed_page_coordinates(scale):
    image,detections=touching_lobes()
    image=image.resize((int(image.width*scale),int(image.height*scale)))
    detections=[{**d,"polygon":[[x*scale,y*scale] for x,y in d["polygon"]]} for d in detections]
    regions=group_regions(image,detections)
    assert len(regions)==2
    assert all("balloon" not in r for r in regions)
