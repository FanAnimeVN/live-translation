"""Decoded pixels, not PNG compression, are the exact restoration invariant."""
from pathlib import Path
import sys
from PIL import Image
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from ram_pixel_compare import compare


def test_one_pixel_failure_is_counted_and_located_not_tolerated():
    before=Image.new("RGB",(12,8),"white");after=before.copy();after.putpixel((9,5),(254,255,255))
    result=compare(before,after)
    assert result["equal"] is False and result["changed_pixels"]==1
    assert result["bbox"]==[9,5,1,1] and result["max_channel_delta"]==1


def test_same_pixels_and_mismatched_dimensions_are_distinguished():
    source=Image.new("RGB",(12,8),"white")
    assert compare(source,source.copy())=={"equal":True,"size":[12,8],"changed_pixels":0}
    assert compare(source,Image.new("RGB",(8,12)))["equal"] is False
