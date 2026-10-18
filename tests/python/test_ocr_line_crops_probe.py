"""Geometry experiment isolation, not a model-quality certificate."""
import importlib.util
from pathlib import Path
import sys
from PIL import Image, ImageDraw


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
spec = importlib.util.spec_from_file_location("line_crops_probe", SCRIPTS / "probe_ocr_line_crops.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_projection_splits_horizontal_source_at_the_blank_gap_only():
    image = Image.new("RGB", (240, 90), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20,10,110,33), fill="black")
    draw.rectangle((10,56,210,79), fill="black")
    assert probe.horizontal_line_boxes(image) == [(17,7,114,37),(7,53,214,83)]


def test_projection_keeps_vertical_single_line_blank_and_dark_source():
    for size, color in (((90,240),"white"),((240,90),"white"),((240,90),"black")):
        assert probe.horizontal_line_boxes(Image.new("RGB", size, color)) == []
    image = Image.new("RGB", (240,90), "white")
    ImageDraw.Draw(image).rectangle((20,10,210,33), fill="black")
    assert probe.horizontal_line_boxes(image) == []


def test_small_stroke_holes_do_not_become_new_lines():
    image = Image.new("RGB", (240,90), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20,10,210,19), fill="black")
    draw.rectangle((20,22,210,33), fill="black")
    assert probe.horizontal_line_boxes(image) == []
