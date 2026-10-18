import sys
from pathlib import Path
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import qa_image_entry as qa


def test_native_image_qa_accepts_only_ram_png_and_reviewed_private_route():
    body = qa.vision_ocr.request(qa.MODEL, [("0", Image.new("RGB", (20, 30), "white"))])
    assert qa.require_crop_request(body) == 1
    for patch in ({"model": "auto"}, {"tools": []}, {"provider": {"data_collection": "allow"}}):
        with pytest.raises(ValueError): qa.require_crop_request({**body, **patch})
    body["messages"][0]["content"][-1]["image_url"]["url"] = "https://remote.example/image.png"
    with pytest.raises(ValueError): qa.require_crop_request(body)


def test_separate_image_contract_does_not_weaken_text_only_native_qa():
    body = qa.vision_ocr.request(qa.MODEL, [("0", Image.new("RGB", (20, 30), "white"))])
    with pytest.raises(qa.AppError): qa.require_text_only(body)
