import base64
import io
import threading

import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

from manga_live.render_cleanup import render_patch, continue_parallel_texture


def art_fixture(light=True):
    """Authored rain, not a copy of a supplied manga or a quality benchmark."""
    image = Image.new("RGB", (400, 240), (184, 184, 184) if light else (48, 48, 48))
    draw = ImageDraw.Draw(image)
    for x in range(-40, 440, 19):
        draw.line((x, 0, x - 34, 240), fill=(154, 154, 154) if light else (79, 79, 79), width=1)
    background = image.copy()
    font = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 28)
    text = "雨はまだ止まない。"
    position = (60, 90)
    draw.text(position, text, font=font, fill="black" if light else "white",
              stroke_width=1, stroke_fill="white" if light else "black")
    left, top, right, bottom = draw.textbbox(position, text, font=font, stroke_width=1)
    region = {"id": "rain", "bbox": [left-3, top-3, right-left+6, bottom-top+6],
              "ja": text, "overlay": "label", "score": 0.95, "review": False, "type": "dialogue"}
    return image, background, region


def composite(image, patch):
    pixels = Image.open(io.BytesIO(base64.b64decode(patch["dataUrl"].split(",", 1)[1]))).convert("RGBA")
    result = image.copy()
    result.paste(pixels, tuple(patch["bbox"][:2]), pixels)
    mask = Image.new("L", image.size, 0)
    mask.paste(pixels.getchannel("A"), tuple(patch["bbox"][:2]))
    return np.asarray(result), np.asarray(mask), np.asarray(pixels)


@pytest.mark.parametrize("light", [True, False])
def test_small_text_on_rain_has_a_transparent_masked_patch_not_a_card(light):
    image, background, region = art_fixture(light)
    patch = render_patch(image, region)
    assert patch is not None
    assert patch["regionId"] == "rain" and patch["method"] == "opencv-telea-v1"
    restored, mask, pixels = composite(image, patch)
    source = np.asarray(image)
    assert (pixels[:, :, 3] == 0).any(), "Never replace a whole rectangular area of the art"
    assert np.array_equal(restored[mask == 0], source[mask == 0]), "Unmasked rain/art is pixel-identical"
    glyph = ((source.astype(int)-np.asarray(background).astype(int))**2).sum(axis=2) > 2000
    assert (mask[glyph] > 0).mean() > 0.98, "Both old glyphs and their halo must disappear"
    old_error = np.abs(source.astype(float)-np.asarray(background)).mean()
    new_error = np.abs(restored.astype(float)-np.asarray(background)).mean()
    assert new_error < old_error * 0.25, "Restoration must improve against the known authored background"
    assert len(patch["dataUrl"]) < 512 * 1024


def test_uncertain_blank_huge_or_balloon_regions_are_not_inpainted():
    image, _, region = art_fixture()
    for changed in ({"review": True}, {"score": 0.4}, {"overlay": "white"},
                    {"type": "sfx"}, {"bbox": [0, 0, 400, 240]}, {"ja": ""}):
        assert render_patch(image, {**region, **changed}) is None
    assert render_patch(Image.new("RGB", image.size, "white"), region) is None


def test_cancel_and_message_budget_do_not_emit_partial_or_oversize_images():
    image, _, region = art_fixture()
    canceled = threading.Event(); canceled.set()
    assert render_patch(image, region, canceled) is None
    assert render_patch(image, region, max_bytes=20) is None


def test_long_structural_lines_are_not_misidentified_as_glyphs():
    image = Image.new("RGB", (400, 240), "#b8b8b8")
    draw = ImageDraw.Draw(image)
    for x in range(40, 360, 10):
        draw.line((x, 0, x-30, 239), fill="black", width=2)
    region = {"id": "rain", "bbox": [40, 80, 280, 50], "ja": "雨が降る。",
              "score": 0.95, "overlay": "label"}
    assert render_patch(image, region) is None


def test_light_ink_with_dark_outline_does_not_leave_the_original_white_centres():
    import sys
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
    from fixture_server import synthetic_art_layout
    from manga_live.ocr import group_regions
    image,detections=synthetic_art_layout()
    regions=group_regions(image,detections)
    region=regions[-1];region.update(ja="それでも歩いていく。",vi="Dù vậy, chị vẫn bước tiếp.")
    patch=render_patch(image,region)
    assert patch is not None and patch["ink"]=="#ffffff"
    restored,mask,_=composite(image,patch)
    x,y,w,h=region["bbox"]
    source=np.asarray(image)
    white=(source[y:y+h,x:x+w]>180).all(axis=2)
    assert (mask[y:y+h,x:x+w][white]>0).mean()>0.99,"Do not erase just the outline and leave the old word"
    assert not (restored[y:y+h,x:x+w]>180).all(axis=2).any(),"All old bright letter centres should be restored to dark texture"


def test_parallel_rain_continuation_improves_over_smoothing_without_touching_other_pixels():
    import cv2
    image,background,region=art_fixture();patch=render_patch(image,region)
    restored,mask,_=composite(image,patch)
    source=np.asarray(image);expected=np.asarray(background)
    classical=cv2.inpaint(source,mask,3,cv2.INPAINT_TELEA)
    guided=continue_parallel_texture(source,mask,classical)
    before=np.abs(classical.astype(float)-expected)[mask>0].mean()
    after=np.abs(guided.astype(float)-expected)[mask>0].mean()
    assert after<before*0.8,"A coherent line profile should continue rain instead of washing it out"
    assert np.array_equal(guided[mask==0],source[mask==0])


@pytest.mark.parametrize("region_index", [0, 1, 2])
def test_parallel_texture_keeps_rain_continuous_at_each_authored_text_position(region_index):
    import cv2
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"scripts"))
    from fixture_server import synthetic_art_layout
    from manga_live.ocr import group_regions
    image, detections = synthetic_art_layout()
    background, _ = synthetic_art_layout(with_text=False)
    region = group_regions(image, detections)[region_index]
    region.update(ja="Author-created fixture", review=False)
    patch = render_patch(image, region)
    assert patch is not None
    restored, mask, _ = composite(image, patch)
    x, y, w, h = patch["bbox"]
    source = np.asarray(image)[y:y+h, x:x+w]
    local_mask = mask[y:y+h, x:x+w]
    expected = np.asarray(background)[y:y+h, x:x+w]
    classical = cv2.inpaint(source, local_mask, 3, cv2.INPAINT_TELEA)
    actual = restored[y:y+h, x:x+w]
    classical_error = np.abs(classical.astype(float)-expected)[local_mask > 0].mean()
    actual_error = np.abs(actual.astype(float)-expected)[local_mask > 0].mean()
    assert actual_error < classical_error*0.8, "Do not pass a visibly smoothed rain region as texture continuation"


def test_parallel_texture_rejects_noncoherent_lines_with_unknown_detail():
    import cv2
    generator = np.random.default_rng(17)
    grey = generator.integers(145, 195, size=(90, 280), dtype="uint8")
    for x in range(10, 280, 17):
        cv2.line(grey, (x, 0), (x-11, 89), 150, 1)
    rgb = np.repeat(grey[:, :, None], 3, axis=2)
    mask = np.zeros(grey.shape, "uint8")
    mask[30:55, 90:180] = 255
    fallback = cv2.inpaint(rgb, mask, 3, cv2.INPAINT_TELEA)
    assert np.array_equal(continue_parallel_texture(rgb, mask, fallback), fallback), "Direction alone cannot justify redrawing detail"
