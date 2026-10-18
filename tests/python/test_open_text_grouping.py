"""Experimental bare text grouping; private regressions prohibit default use."""
import pytest
from PIL import Image,ImageDraw,ImageOps
from manga_live.ocr import group_regions as production_group_regions,polygon


def group_regions(image,detections):
    return production_group_regions(image,detections,experimental_open_text=True)


@pytest.mark.parametrize("dark",[False,True])
def test_adjacent_bare_vertical_columns_are_one_ocr_crop_without_erasure_rights(dark):
    image=Image.new("RGB",(400,480),"white");draw=ImageDraw.Draw(image)
    for x in (105,132):
        for y in range(104,195,20):draw.rectangle((x,y,x+12,y+12),fill="black")
    if dark:image=ImageOps.invert(image)
    detections=[{"polygon":polygon([100,100,27,100]),"score":.95},
                {"polygon":polygon([125,100,27,140]),"score":.95}]
    regions=group_regions(image,detections)
    assert len(regions)==1,"A bare multi-column text block must not OCR clipped neighbour columns twice"
    assert regions[0]["bbox"]==[97,97,58,146]
    assert "balloon" not in regions[0] and regions[0]["overlay"]=="label"


@pytest.mark.parametrize("dark",[False,True])
def test_shared_open_paper_still_respects_a_partial_panel_separator(dark):
    image=Image.new("RGB",(400,480),"white");draw=ImageDraw.Draw(image)
    draw.line((127,100,127,220),fill="black",width=3)
    if dark:image=ImageOps.invert(image)
    detections=[{"polygon":polygon([98,100,24,140]),"score":.95},
                {"polygon":polygon([132,100,24,140]),"score":.95}]
    regions=group_regions(image,detections)
    assert len(regions)==2,"Connected page paper cannot bridge a visible scene separator"
    assert all("balloon" not in r for r in regions)


@pytest.mark.parametrize("dark",[False,True])
def test_connected_small_balloons_do_not_merge_through_a_partial_outline(dark):
    image=Image.new("RGB",(400,480),"#777777");draw=ImageDraw.Draw(image)
    draw.rectangle((70,70,190,250),fill="white",outline="black",width=3)
    draw.line((127,75,127,220),fill="black",width=3)
    if dark:image=ImageOps.invert(image)
    detections=[{"polygon":polygon([98,100,24,140]),"score":.95},
                {"polygon":polygon([132,100,24,140]),"score":.95}]
    regions=group_regions(image,detections)
    assert len(regions)==2,"A substantial outline between nearby columns is evidence against merging"
    assert all("balloon" not in r for r in regions),"A split does not prove independent erasure ownership"


def test_horizontal_bare_lines_group_without_crossing_a_distant_caption():
    image=Image.new("RGB",(500,600),"white")
    detections=[{"polygon":polygon(box),"score":.95} for box in
                ([100,100,160,24],[100,135,130,24],[100,300,160,24])]
    regions=group_regions(image,detections)
    assert len(regions)==2
    assert {tuple(r["bbox"]) for r in regions}=={(97,97,166,65),(97,297,166,30)}
    assert all("balloon" not in r for r in regions)


def test_open_vertical_blocks_keep_an_interblock_gap_between_same_scale_columns():
    image=Image.new("RGB",(827,1170),"white")
    boxes=([736,84,43,195],[704,84,36,117],[640,85,38,169],[602,80,47,194])
    regions=group_regions(image,[{"polygon":polygon(box),"score":.95} for box in boxes])
    assert len(regions)==2,"Open paper cannot turn the gap between two introductions into one utterance"
    assert {tuple(r["bbox"]) for r in regions}=={(701,81,81,201),(599,77,82,200)}
    assert all("balloon" not in r for r in regions)


def test_open_caption_and_large_logo_do_not_merge_via_small_overlapping_annotation():
    image=Image.new("RGB",(827,1170),"white")
    boxes=([283,474,213,55],[442,522,52,32],[275,547,513,117])
    regions=group_regions(image,[{"polygon":polygon(box),"score":.95} for box in boxes])
    assert len(regions)==3,"Different typography scales and shallow cross-row overlap are not one OCR block"
    assert all("balloon" not in r for r in regions)


def test_open_handwritten_label_does_not_swallow_a_smaller_neighbour():
    image=Image.new("RGB",(827,1170),"white")
    boxes=([760,317,34,112],[791,349,14,41])
    regions=group_regions(image,[{"polygon":polygon(box),"score":.95} for box in boxes])
    assert len(regions)==2,"A tiny side mark does not establish the same lettering scale"


def test_ink_inside_overlapping_detector_columns_is_not_an_independent_separator():
    image=Image.new("RGB",(400,480),"#777777");draw=ImageDraw.Draw(image)
    draw.rectangle((70,70,190,250),fill="white",outline="black",width=3)
    # This ink lies INSIDE both detector boxes. Their uncertain overlap does
    # not supply a blank corridor in which a separate outline can be proved.
    draw.line((127,104,127,220),fill="black",width=3)
    boxes=([100,100,34,140],[122,100,34,140])
    regions=group_regions(image,[{"polygon":polygon(box),"score":.95} for box in boxes])
    assert len(regions)==1,"Do not invent a between-column corridor through detected glyphs"


def test_unaccepted_open_grouping_cannot_change_default_runtime():
    image=Image.new("RGB",(400,480),"white")
    detections=[{"polygon":polygon(box),"score":.95} for box in
                ([100,100,27,100],[125,100,27,140])]
    assert len(production_group_regions(image,detections))==2
    assert len(group_regions(image,detections))==1


def test_open_nearby_columns_with_different_starting_rows_are_not_one_block():
    image=Image.new("RGB",(400,480),"white")
    boxes=([100,100,24,130],[123,122,24,120])
    regions=group_regions(image,[{"polygon":polygon(box),"score":.95} for box in boxes])
    assert len(regions)==2,"Open paper and overlap alone cannot establish a shared text start"


def test_open_transitive_adjacency_cannot_walk_between_staggered_blocks():
    image=Image.new("RGB",(400,480),"white")
    # A→B and B→C individually have compatible starts. A whole group must
    # still fit one aligned start band, not drift through transitive edges.
    boxes=([100,100,24,130],[123,106,24,120],[146,112,24,120])
    regions=group_regions(image,[{"polygon":polygon(box),"score":.95} for box in boxes])
    assert len(regions)==2,"A local adjacency chain must not manufacture a single open dialogue block"


def test_open_two_neighbours_added_together_still_need_one_shared_start_band():
    image=Image.new("RGB",(400,480),"white")
    boxes=([100,100,24,130],[77,94,24,120],[123,106,24,120])
    regions=group_regions(image,[{"polygon":polygon(box),"score":.95} for box in boxes])
    assert len(regions)==2,"Two individually aligned neighbours may not agree with each other"


@pytest.mark.parametrize("scale",[.5,1,2])
def test_open_aligned_polygon_replay_keeps_whole_columns_and_never_grants_erasure(scale):
    image=Image.new("RGB",(int(827*scale),int(1170*scale)),"white")
    polygons=[[[305,69],[339,68],[342,202],[308,203]],[[286,69],[315,69],[315,232],[286,232]]]
    detections=[{"polygon":[[x*scale,y*scale] for x,y in poly],"score":.95} for poly in polygons]
    regions=group_regions(image,detections)
    assert len(regions)==1 and "balloon" not in regions[0] and regions[0]["overlay"]=="label"
    x,y,w,h=regions[0]["bbox"]
    assert all(x<=px<=x+w and y<=py<=y+h for d in detections for px,py in d["polygon"])
