"""Private reader QA must never substitute an excluded/missing source page."""
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from fixture_server import private_images


def dataset(tmp_path):
    labels=[]
    for index,color in enumerate(("white","black")):
        image=Image.new("RGB",(40,60),color)
        image.save(tmp_path/f"{index}.png")
        labels.append({"page_id":f"p{index}","image_file":f"{index}.png",
            "image_size":{"w":40,"h":60},"bubbles":[{"bubble_id":"b1",
            "bbox":{"x":1,"y":1,"w":10,"h":15},"ja_ocr_truth":"テスト"}]})
    (tmp_path/"ground_truth_benchmark.json").write_text(json.dumps(labels),encoding="utf-8")
    return labels


def test_explicit_private_page_keeps_its_identity_and_image_bytes_in_ram(tmp_path):
    dataset(tmp_path)
    before={p.name:p.read_bytes() for p in tmp_path.iterdir()}
    images,ids=private_images(SimpleNamespace(folder=tmp_path,zip=None,private_page="p1"))
    assert ids==["p1"] and set(images)=={"/private/0.png"}
    assert Image.open(io.BytesIO(images["/private/0.png"])).getpixel((5,5))==(0,0,0)
    assert {p.name:p.read_bytes() for p in tmp_path.iterdir()}==before


@pytest.mark.parametrize("page_id",["missing","p0"])
def test_missing_or_audit_excluded_page_does_not_fall_back_to_a_different_sample(tmp_path,page_id):
    labels=dataset(tmp_path)
    labels[0]["image_size"]={"w":50,"h":60}
    (tmp_path/"ground_truth_benchmark.json").write_text(json.dumps(labels),encoding="utf-8")
    with pytest.raises(ValueError,match="missing or excluded"):
        private_images(SimpleNamespace(folder=tmp_path,zip=None,private_page=page_id))


def test_private_reader_without_a_dataset_has_no_source():
    assert private_images(SimpleNamespace(zip=None,folder=None,private_page=None))==({},[])
    with pytest.raises(ValueError,match="needs a dataset"):
        private_images(SimpleNamespace(zip=None,folder=None,private_page="p1"))
