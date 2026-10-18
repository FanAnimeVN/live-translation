import sys
import pytest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from fixture_server import synthetic_page,synthetic_layout
from manga_live.ocr import decode_image,group_regions,polygon,review_reasons


def test_balloon_lettering_uses_safe_interior_without_expanding_ocr_crop():
    image=decode_image(synthetic_page())
    detections=[{"polygon":polygon([520,135,90,30]),"score":0.95},
                {"polygon":polygon([520,180,90,30]),"score":0.95}]
    regions=group_regions(image,detections)
    assert len(regions)==1
    region=regions[0]
    assert region["bbox"]==[517,132,96,81],"OCR still receives the original text crop"
    balloon=region["balloon"]
    x,y,w,h=balloon["textBox"]
    assert w>region["bbox"][2],"Horizontal Vietnamese can use more than the narrow Japanese column"
    assert 440<x<x+w<760 and 70<y<y+h<300,"Do not cover the source outline or tail"
    assert balloon["background"]=="#ffffff"


def test_page_margin_or_art_is_not_invented_as_a_balloon():
    from PIL import Image,ImageDraw
    image=Image.new("RGB",(800,1050),"white")
    ImageDraw.Draw(image).text((50,50),"TEXT",fill="black")
    region=group_regions(image,[{"polygon":polygon([45,45,70,25]),"score":0.95}])[0]
    assert region["overlay"]=="label"
    assert "balloon" not in region


def test_erase_boxes_cover_all_authored_glyphs_without_hiding_balloon_outline():
    image,detections=synthetic_layout()
    regions=group_regions(image,detections)
    assert len(regions)==4 and all(r.get("balloon") for r in regions)
    for detection in detections:
        left,top=detection["polygon"][0];right,bottom=detection["polygon"][2]
        assert any(x<=left and y<=top and x+w>=right and y+h>=bottom for x,y,w,h in (r["bbox"] for r in regions))


def test_text_mask_covers_residual_ink_outside_inexact_detector_box():
    import cv2
    import numpy as np
    image=decode_image(synthetic_page())
    regions=group_regions(image,[{"polygon":polygon([490,150,160,20]),"score":0.95},
                                 {"polygon":polygon([490,195,160,20]),"score":0.95}])
    assert len(regions)==1
    region=regions[0];mask=region["balloon"]["erasePolygons"]
    assert mask,"An inexact detector rectangle must not be the only erasure evidence"
    painted=np.zeros((image.height,image.width),dtype="uint8")
    for poly in mask:cv2.fillPoly(painted,[np.asarray(poly,dtype="int32")],1)
    source=np.asarray(image.convert("L"))
    # All authored Japanese glyphs in the balloon, including missed punctuation.
    assert ((source[150:225,475:725]<180)&(painted[150:225,475:725]==0)).sum()==0
    assert painted[70,600]==0,"Balloon outline must never be erased"


def test_background_and_source_lettering_scale_are_measured_not_hardcoded():
    import numpy as np
    from PIL import Image
    image,detections=synthetic_layout();pixels=np.asarray(image).copy()
    pixels[(pixels==[255,255,255]).all(axis=2)]=[250,247,236]
    regions=group_regions(Image.fromarray(pixels),detections)
    assert all(r.get("balloon") for r in regions)
    assert all(r["balloon"]["background"]=="#faf7ec" for r in regions)
    assert all(15<=r["balloon"]["sourceFontPx"]<=36 for r in regions)


@pytest.mark.parametrize("background,dark",[((213,231,227),False),((30,43,53),True),((0,0,0),True)])
def test_tinted_or_dark_flat_balloons_use_their_real_color_and_ink(background,dark):
    import numpy as np
    from PIL import Image
    image,detections=synthetic_layout();pixels=np.asarray(image).copy()
    if dark:pixels=255-pixels
    pixels[(pixels==([0,0,0] if dark else [255,255,255])).all(axis=2)]=background
    regions=group_regions(Image.fromarray(pixels),detections)
    expected="#"+"".join(f"{value:02x}" for value in background)
    assert len(regions)==4 and all(r.get("balloon") for r in regions)
    assert all(r["balloon"]["background"]==expected for r in regions)
    assert all(r["balloon"]["erasePolygons"] for r in regions)
    assert all(r["balloon"]["ink"]==("#ffffff" if dark else "#000000") for r in regions)


def test_white_grouping_preserves_thin_balloon_outlines():
    image=decode_image(synthetic_page())
    detections=[]
    for x,y in [(475,135),(475,180),(110,215),(110,260),(475,565),(475,610),(110,755),(110,800)]:
        detections.append({"polygon":polygon([x,y,180,30]),"score":0.95})
    regions=group_regions(image,detections)
    assert len(regions)==4,"Lines inside each balloon should group, not bridge to white page gutters"
    assert all(r["overlay"]=="white" for r in regions)


@pytest.mark.parametrize("dark", [False, True])
def test_multiple_background_components_do_not_vote_as_one_balloon(dark):
    """A detector spanning two captions cannot inherit either caption's owner.

    The combined paper occupies >55% of the detection, but neither connected
    surface does. Merging it with an independent line in the right caption
    changes OCR order and erasure ownership. The ambiguous box stays reviewable.
    """
    from PIL import Image, ImageDraw, ImageOps
    image = Image.new("RGB", (600, 400), "#777777")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 25, 93, 110), fill="white", outline="black", width=3)
    draw.rectangle((107, 25, 176, 160), fill="white", outline="black", width=3)
    draw.rectangle((58, 50, 65, 58), fill="black")
    draw.rectangle((132, 120, 139, 128), fill="black")
    if dark:
        image = ImageOps.invert(image)
    detections = [{"polygon": polygon([45, 40, 125, 45]), "score": .95},
                  {"polygon": polygon([125, 115, 25, 22]), "score": .95}]
    regions = group_regions(image, detections)
    assert len(regions) == 2, "Disjoint backgrounds must not be summed to authorize a cross-caption merge"
    ambiguous = next(region for region in regions if region["bbox"][0] < 50)
    assert ambiguous["bbox"] == [42, 37, 131, 51]
    assert "balloon" not in ambiguous, "Keep uncertain artwork and OCR crop unchanged"


def test_oversized_surface_union_keeps_its_bounded_detector_members():
    from PIL import Image, ImageDraw
    image = Image.new("RGB", (800, 1000), "#777777")
    draw = ImageDraw.Draw(image)
    # Two small text areas are connected by narrow empty-paper corridors.
    # Component area is small, but its spread is not one sensible OCR crop.
    draw.rectangle((80, 80, 200, 190), fill="white")
    draw.rectangle((550, 650, 670, 770), fill="white")
    draw.rectangle((150, 125, 615, 138), fill="white")
    draw.rectangle((600, 130, 615, 690), fill="white")
    detections = [{"polygon": polygon([100, 110, 70, 35]), "score": .95},
                  {"polygon": polygon([570, 690, 70, 35]), "score": .95}]
    regions = group_regions(image, detections)
    assert len(regions) == 2, "An overlarge union must not silently discard both valid source detections"
    assert {tuple(region["bbox"]) for region in regions} == {(97, 107, 76, 41), (567, 687, 76, 41)}
    assert all("balloon" not in region for region in regions), "Splitting is not proof of enclosed balloon ownership"
    assert all(region["reviewReasons"] == ["layout_fragment"] for region in regions)
    import threading
    from manga_live.ocr import recognize_regions
    class Engine:
        def recognize_many(self, images):
            return ["テスト"] * len(images)
    recognized = recognize_regions(image, regions, Engine(), threading.Event())
    assert len(recognized) == 2
    assert all(region["review"] and region["reviewReasons"] == ["layout_fragment"] for region in recognized)


@pytest.mark.parametrize("dark",[False,True])
@pytest.mark.parametrize("vertical",[True,False])
def test_bounded_shared_paper_does_not_merge_distant_text_clusters(dark,vertical):
    """Connected paper is not sufficient evidence of one speech/text block.

    Two close columns per cluster should stay together, but not join another
    distant cluster through empty paper. The overall union is small enough to
    pass the older area gate; no new artwork erasure is inferred by splitting.
    """
    from PIL import Image,ImageDraw,ImageOps
    image=Image.new("RGB",(800,1000),"#777777")
    ImageDraw.Draw(image).rectangle((80,80,420,270) if vertical else (80,80,270,420),fill="white")
    if dark:image=ImageOps.invert(image)
    boxes=([x,100,25,140] if vertical else [100,x,140,25] for x in (100,136,320,356))
    detections=[{"polygon":polygon(box),"score":.95} for box in boxes]
    regions=group_regions(image,detections)
    assert len(regions)==2,"A connected flat surface must not merge distant source utterances"
    expected={(97,97,67,146),(317,97,67,146)} if vertical else {(97,97,146,67),(97,317,146,67)}
    assert {tuple(r["bbox"]) for r in regions}==expected
    assert all("balloon" not in r and r["reviewReasons"]==["layout_fragment"] for r in regions)


def test_unbalanced_quotes_are_reviewed_not_removed():
    assert "quote_balance" in review_reasons("「姉ちゃん、まだ帰らないの？",0.95)
    assert "quote_balance" in review_reasons("『明日は来なくてもいい。",0.95)
    assert review_reasons("「姉ちゃん、聞いて。」",0.95)==[]
    assert review_reasons("先に帰ってて。あとで行くから。",0.95)==[]
    assert "detector_low_score" in review_reasons("ありがとう。",0.4)


def test_actual_native_detector_crop_last_balloon_keeps_integrated_lettering():
    # Geometry captured from the real PP-OCRv5/native Edge fixture run.
    # Earlier tests used authored glyph boxes and did not cover this crop.
    image=decode_image(synthetic_page())
    region=group_regions(image,[{"polygon":polygon([98,751,225,85]),"score":.81}])[0]
    assert region["bbox"]==[95,748,231,91]
    assert region["overlay"]=="white","A safely enclosed flat balloon must not fall back to a translucent label"
    assert region["balloon"]["erasePolygons"]
    import cv2
    import numpy as np
    painted=np.zeros((image.height,image.width),dtype="uint8")
    for poly in region["balloon"]["erasePolygons"]:cv2.fillPoly(painted,[np.asarray(poly,dtype="int32")],1)
    source=np.asarray(image.convert("L"))
    assert ((source[750:850,95:330]<180)&(painted[750:850,95:330]==0)).sum()==0
    assert not painted[690,220],"Do not erase the source balloon outline"


def test_nonempty_crop_corner_near_outline_is_not_accepted_as_safe():
    from PIL import ImageDraw
    image=decode_image(synthetic_page())
    # This corner is outside the eroded interior. It is accepted only while
    # completely blank, never when it contains art or a missed source glyph.
    ImageDraw.Draw(image).point((95,748),fill="black")
    region=group_regions(image,[{"polygon":polygon([98,751,225,85]),"score":.81}])[0]
    assert region["overlay"]=="label"
    assert "balloon" not in region


@pytest.mark.parametrize("quality,scale", [(90, 1), (75, 1), (90, .5), (75, .5)])
def test_jpeg_balloon_ringing_is_not_mistaken_for_textured_paper(quality, scale):
    import io
    from PIL import Image
    image, detections = synthetic_layout()
    detections = detections[:2]  # Minimal one-balloon seam; unrelated tiny-line grouping is separate.
    image = image.resize((int(image.width * scale), int(image.height * scale)))
    detections = [{**d, "polygon": [[x * scale, y * scale] for x, y in d["polygon"]]} for d in detections]
    encoded = io.BytesIO()
    image.save(encoded, format="JPEG", quality=quality)
    compressed = Image.open(io.BytesIO(encoded.getvalue())).convert("RGB")
    regions = group_regions(compressed, detections)
    assert len(regions) == 1
    assert all(region.get("balloon") for region in regions), "A closed, flat JPEG balloon must not become a translation card"
    assert all(region["balloon"]["erasePolygons"] for region in regions)


def test_texture_far_from_glyph_edges_is_still_not_a_flat_balloon():
    import numpy as np
    from PIL import Image
    image, detections = synthetic_layout()
    pixels = np.asarray(image).copy()
    paper = (pixels == [255, 255, 255]).all(axis=2)
    gradient = np.broadcast_to(np.linspace(190, 255, image.width).astype("uint8"), (image.height, image.width))
    for channel in range(3):
        pixels[:, :, channel][paper] = gradient[paper]
    regions = group_regions(Image.fromarray(pixels), detections)
    assert not any(region.get("balloon") for region in regions), "Removing edge samples must not hide a real background gradient"


def test_detector_corner_can_include_the_outline_but_mask_never_erases_it():
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (320, 320), "#777777")
    draw = ImageDraw.Draw(image)
    draw.ellipse((40, 20, 134, 167), fill="white", outline="black", width=3)
    before_text = np.asarray(image).copy()
    font = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 22)
    for line, glyph in enumerate("うわ！"):
        draw.text((74, 38+28*line), glyph, font=font, fill="black")
    region = group_regions(image, [{"polygon": polygon([67, 31, 45, 95]), "score": .95}])[0]
    assert region.get("balloon"), "A tiny outline overhang is not a license to erase the outline, nor reason to invent a card"
    painted = np.zeros((image.height, image.width), dtype="uint8")
    for poly in region["balloon"]["erasePolygons"]:
        cv2.fillPoly(painted, [np.asarray(poly, dtype="int32")], 1)
    outline = (before_text == [0, 0, 0]).all(axis=2)
    assert not painted[outline].any(), "Every source outline pixel must remain untouched, not an arbitrary y-range"
    glyphs = (np.asarray(image) != before_text).any(axis=2)
    assert painted[glyphs].all(), "All printed glyph pixels must be removed, not just an empty box"
    assert painted[52:120, 73:101].any(), "Source glyphs, not just an empty box, are masked"
    too_far = group_regions(image, [{"polygon": polygon([67, 28, 45, 98]), "score": .95}])[0]
    assert not too_far.get("balloon"), "More than eight pixels outside the enclosed surface is not an outline exception"


def stepped_columns_balloon(*, foreign_mark=False, unsafe_member=False, decoration=False):
    """Unequal source columns leave a large empty OUTSIDE union corner."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (500, 500), "white")
    draw = ImageDraw.Draw(image)
    draw.polygon([(50, 30), (180, 30), (180, 120), (100, 250), (50, 250)],
                 fill="white", outline="black", width=3)
    if foreign_mark:
        # An unaccounted-for glyph in the empty union corner is NOT an outline.
        draw.rectangle((141, 208, 144, 212), fill="black")
    if decoration:
        draw.ellipse((62, 120, 69, 138), outline="black", width=2)
    before_text = np.asarray(image).copy()
    font = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 20)
    for x, chars in ((82, "帰ってゆく…"), (121, "ああ")):
        for line, glyph in enumerate(chars):
            draw.text((x, 60 + 28 * line), glyph, font=font, fill="black", anchor="lt")
    boxes = [[80, 55, 26, 165], [119, 55, 26, 67]]
    if unsafe_member:
        boxes[1][3] = 165  # Source evidence itself now claims the outside corner.
    return image, before_text, [{"polygon": polygon(box), "score": .95} for box in boxes]


@pytest.mark.parametrize("dark", [False, True])
@pytest.mark.parametrize("transpose", [False, True])
@pytest.mark.parametrize("scale", [1, 1.5])
def test_unequal_columns_do_not_invent_a_source_glyph_in_empty_union_corners(dark, transpose, scale):
    import cv2
    import numpy as np
    from PIL import Image, ImageOps
    image, before_text, detections = stepped_columns_balloon()
    background = Image.fromarray(before_text)
    if dark:
        image, background = ImageOps.invert(image), ImageOps.invert(background)
    if transpose:
        image, background = image.transpose(Image.Transpose.TRANSPOSE), background.transpose(Image.Transpose.TRANSPOSE)
        detections = [{**d, "polygon": [[y,x] for x,y in d["polygon"]]} for d in detections]
    if scale != 1:
        size = (int(image.width*scale), int(image.height*scale))
        image, background = image.resize(size), background.resize(size)
        detections = [{**d, "polygon": [[x*scale,y*scale] for x,y in d["polygon"]]} for d in detections]
    before_text = np.asarray(background)
    regions = group_regions(image, detections)
    assert len(regions) == 1
    region = regions[0]
    assert region.get("balloon"), "Safe individual columns must not inherit an unsafe empty union corner"
    if scale == 1:
        assert region["bbox"] == ([52,77,171,71] if transpose else [77,52,71,171]), "OCR geometry is not silently tightened"
    painted = np.zeros((image.height, image.width), dtype="uint8")
    for poly in region["balloon"]["erasePolygons"]:
        cv2.fillPoly(painted, [np.asarray(poly, dtype="int32")], 1)
    glyphs = (np.asarray(image) != before_text).any(axis=2)
    assert glyphs.any() and painted[glyphs].all()
    paper = [0,0,0] if dark else [255,255,255]
    assert not painted[(before_text != paper).any(axis=2)].any(), "No outside corner, outline or artwork is writable"


@pytest.mark.parametrize("foreign_mark,unsafe_member", [(True, False), (False, True)])
@pytest.mark.parametrize("experimental",[False,True])
def test_source_footprints_do_not_authorize_unaccounted_ink_or_an_unsafe_column(foreign_mark, unsafe_member,experimental):
    image, _, detections = stepped_columns_balloon(foreign_mark=foreign_mark, unsafe_member=unsafe_member)
    region = group_regions(image, detections,experimental_source_support=experimental)[0]
    assert not region.get("balloon"), "Every actual column and all unexplained union-corner ink must still pass"


def test_integrating_a_balloon_does_not_erase_a_nearby_sweat_mark_outside_source_columns():
    import cv2
    import numpy as np
    image, before_text, detections = stepped_columns_balloon(decoration=True)
    region = group_regions(image, detections)[0]
    assert region.get("balloon")
    painted = np.zeros((image.height, image.width), dtype="uint8")
    for poly in region["balloon"]["erasePolygons"]:
        cv2.fillPoly(painted, [np.asarray(poly, dtype="int32")], 1)
    assert not painted[(before_text != [255, 255, 255]).any(axis=2)].any(), "Nearby decoration is not glyph evidence"
    glyphs = (np.asarray(image) != before_text).any(axis=2)
    assert painted[glyphs].all()


@pytest.mark.parametrize("experimental",[False,True])
def test_half_size_source_with_padding_on_the_outline_keeps_reversible_fallback(experimental):
    image, _, detections = stepped_columns_balloon()
    image = image.resize((250, 250))
    detections = [{**d, "polygon": [[x*.5,y*.5] for x,y in d["polygon"]]} for d in detections]
    before = image.tobytes()
    region = group_regions(image, detections,experimental_source_support=experimental)[0]
    assert region["overlay"] == "label" and "balloon" not in region
    assert region["bbox"] == [37,24,38,88]
    assert image.tobytes() == before, "Do not loosen the source/outline gate for a small-resolution crop"


def actual_source_support_fixture():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    image=Image.new("RGB",(600,600),"#777777")
    draw=ImageDraw.Draw(image)
    draw.ellipse((50,50,210,330),fill="white",outline="black",width=3)
    before_text=np.asarray(image).copy()
    font=ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc",22)
    for x,chars in ((91,"おかえり…"),(135,"ああ")):
        for line,glyph in enumerate(chars):
            draw.text((x,90+32*line),glyph,font=font,fill="black",anchor="lt")
    detections=[{"polygon":polygon(box),"score":.95} for box in
                ([82,77,40,232],[126,77,40,145])]
    return image,before_text,detections


def test_actual_detector_column_support_is_not_the_extra_inference_padding():
    import cv2
    import numpy as np
    image,before_text,detections=actual_source_support_fixture()
    original=image.tobytes()
    regions=group_regions(image,detections,include_source_members=True,experimental_source_support=True)
    assert len(regions)==1
    region=regions[0]
    assert region["bbox"]==[79,74,90,238], "Neither OCR extent nor original detector evidence is tightened"
    assert region["sourceMembers"]==detections
    assert region.get("balloon"), "Prove the actual source support with the same outline gate, not its added crop padding"
    painted=np.zeros((image.height,image.width),dtype="uint8")
    for poly in region["balloon"]["erasePolygons"]:
        cv2.fillPoly(painted,[np.asarray(poly,dtype="int32")],1)
    glyphs=(np.asarray(image)!=before_text).any(axis=2)
    assert glyphs.any() and painted[glyphs].all()
    assert not painted[(before_text!=[255,255,255]).any(axis=2)].any(), "No source outline or external art becomes writable"
    assert image.tobytes()==original


def test_native_paddle_detection_uses_verified_actual_source_support_by_default(tmp_path):
    from types import SimpleNamespace
    from manga_live.ocr import PaddleDetector
    image,_,detections=actual_source_support_fixture()
    (tmp_path/"inference.pdiparams").write_bytes(b"authored-model-stub")
    detector=PaddleDetector(tmp_path)
    detector.model=SimpleNamespace(predict=lambda *a,**k:[SimpleNamespace(json={"res":{
        "dt_polys":[r["polygon"] for r in detections],"dt_scores":[r["score"] for r in detections]}})])
    region=detector.detect(image)[0]
    assert region["bbox"]==[79,74,90,238]
    assert region.get("balloon"), "Native fresh detection must not strand the validated improvement in an experiment"
    assert "sourceMembers" not in region, "Do not copy diagnostic source payload into the translation context"


def test_local_narration_surface_edges_are_protected_from_erosion_border_defaults():
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (400, 480), "#777777")
    draw = ImageDraw.Draw(image)
    draw.rectangle((50, 30, 120, 265), fill="white", outline="black", width=3)
    # Pale antialias/JPEG fringe belongs to the source border, not the text.
    # This is the boundary of the local component array, not of the page.
    draw.line((53, 33, 53, 262), fill="#cccccc")
    before_text = np.asarray(image).copy()
    font = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 19)
    for line, glyph in enumerate("数年前のお話"):
        draw.text((73, 73 + 20 * line), glyph, font=font, fill="black")
    region = group_regions(image, [{"polygon": polygon([69, 78, 34, 124]), "score": .95}])[0]
    assert region.get("balloon"), "A connected pale border must stay protected, not be classified as a giant glyph"
    painted = np.zeros((image.height, image.width), dtype="uint8")
    for poly in region["balloon"]["erasePolygons"]:
        cv2.fillPoly(painted, [np.asarray(poly, dtype="int32")], 1)
    source_border = (before_text != [255, 255, 255]).any(axis=2)
    assert not painted[source_border].any(), "No source border or its antialias fringe may be painted"
    glyphs = (np.asarray(image) != before_text).any(axis=2)
    assert painted[glyphs].all()


def test_small_detector_padding_beyond_the_component_box_is_not_a_text_card():
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (400, 480), "#777777")
    draw = ImageDraw.Draw(image)
    draw.rectangle((40, 20, 140, 170), fill="white", outline="black", width=3)
    before_text = np.asarray(image).copy()
    font = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 20)
    for line, glyph in enumerate("うわ！"):
        draw.text((75, 40 + 26 * line), glyph, font=font, fill="black")
    detection = {"polygon": polygon([70, 30, 40, 138]), "score": .95}
    region = group_regions(image, [detection])[0]
    assert region.get("balloon"), "Small, proven external-outline padding must be checked, not rejected by component bbox alone"
    assert region["bbox"] == [67, 27, 46, 144], "Do not silently shrink the actual OCR crop"
    painted = np.zeros((image.height, image.width), dtype="uint8")
    for poly in region["balloon"]["erasePolygons"]:
        cv2.fillPoly(painted, [np.asarray(poly, dtype="int32")], 1)
    border_or_art = (before_text != [255, 255, 255]).any(axis=2)
    assert not painted[border_or_art].any()
    glyphs = (np.asarray(image) != before_text).any(axis=2)
    assert painted[glyphs].all()


def test_background_sampling_excludes_bounded_glyph_ringing_not_real_texture():
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    image = Image.new("RGB", (600, 600), "#777777")
    draw = ImageDraw.Draw(image)
    draw.rectangle((60, 30, 200, 260), fill="white", outline="black", width=3)
    before_text = np.asarray(image).copy()
    font = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 22)
    for x, chars in ((140, "出てきなさい"), (91, "ナナ！")):
        for line, glyph in enumerate(chars):
            draw.text((x, 50 + 26 * line), glyph, font=font, fill="black")
    pixels = np.asarray(image).copy()
    glyphs = (pixels != before_text).any(axis=2)
    cores = (pixels.mean(axis=2) < 175) & glyphs
    ringing = (cv2.dilate(cores.astype("uint8"), np.ones((9, 9), np.uint8)) > 0)
    ringing &= ~glyphs & (before_text == [255, 255, 255]).all(axis=2)
    pixels[ringing] = [246, 246, 246]
    source = Image.fromarray(pixels)
    region = group_regions(source, [{"polygon": polygon([88, 50, 80, 165]), "score": .95}])[0]
    assert region.get("balloon"), "Measure paper away from up to four pixels of source glyph ringing, not a looser flatness tolerance"
    assert region["balloon"]["background"] == "#ffffff"
    painted = np.zeros((image.height, image.width), dtype="uint8")
    for poly in region["balloon"]["erasePolygons"]:
        cv2.fillPoly(painted, [np.asarray(poly, dtype="int32")], 1)
    assert painted[cores].all()
    assert not painted[(before_text != [255, 255, 255]).any(axis=2)].any()
