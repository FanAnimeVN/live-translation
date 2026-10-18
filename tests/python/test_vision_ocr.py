import json
import pytest
from PIL import Image
from manga_live import vision_ocr as vision
from manga_live.errors import AppError


def reply(items, finish="stop"):
    return {"choices": [{"finish_reason": finish, "message": {"content": json.dumps({"items": items})}}]}


def test_contract_uses_ram_images_privacy_no_tools_or_fallback():
    body = vision.request(vision.MODELS[0], [("a", Image.new("RGB", (20, 30), "white"))])
    assert body["provider"] == {"data_collection": "deny", "zdr": True, "sort": "latency",
                                "allow_fallbacks": False, "require_parameters": True, "only": ["google-vertex/global"]}
    assert "tools" not in body and "models" not in body and "temperature" not in body
    content = body["messages"][0]["content"]
    assert content[-1]["image_url"]["url"].startswith("data:image/png;base64,")
    assert "do not skip" in vision.request(vision.MODELS[1], [("a", Image.new("RGB", (2, 2)))], page=True)["messages"][0]["content"][0]["text"]
    assert "Do not silently skip small" in content[0]["text"]
    assert "standalone small text" in content[0]["text"]


def test_vertex_gemini_does_not_send_unsupported_sampling_parameters():
    body = vision.request(vision.MODELS[1], [("a", Image.new("RGB", (20, 30)))])
    assert "temperature" not in body
    assert body["provider"]["only"] == ["google-vertex/global"]


@pytest.mark.parametrize("items", [[], [{"id": "b", "ja": "a", "uncertain": False}],
    [{"id": "a", "ja": "a", "uncertain": False}] * 2,
    [{"id": "a", "ja": "a", "uncertain": "false"}], [{"id": "a", "ja": "a"*3001, "uncertain": False}]])
def test_crop_cardinality_never_accepts_missing_or_duplicate_ids(items):
    with pytest.raises(AppError): vision.checked_response(reply(items), ["a"])


def test_source_quotes_and_expressive_spaces_never_stripped():
    row = {"id": "a", "ja": "「わ・た・し〜 I L O V E Y O U", "uncertain": True}
    assert vision.checked_response(reply([row]), ["a"]) == [row]
    assert vision.checked_response(reply([{**row, "ja": ""}]), ["a"])[0]["ja"] == ""
    with pytest.raises(AppError): vision.checked_response(reply([row], "length"), ["a"])


def test_page_bounds_must_be_real_finite_integer_geometry():
    row = {"id": "r000", "ja": "姉ちゃん", "uncertain": False, "box": {"x": 1, "y": 1, "w": 10, "h": 20}}
    assert vision.checked_response(reply([row]), [], page=True, image_size=(800, 1050)) == [row]
    for patch in ({"x": True}, {"x": -1}, {"w": 1000}, {"h": 0}, {"x": float("nan")}):
        with pytest.raises(AppError): vision.checked_response(reply([{**row, "box": {**row["box"], **patch}}]), [], page=True, image_size=(800, 1050))
    assert vision.checked_response(reply([]), [], page=True, image_size=(800, 1050)) == []
    with pytest.raises(AppError): vision.checked_response(reply([row]), [], page=True)


def test_oversize_duplicate_unreviewed_images_rejected_before_encoding():
    image = Image.new("RGB", (10, 10))
    for model, images in (("auto", [("a", image)]), (vision.MODELS[0], [("a", image)] * 2),
                          (vision.MODELS[0], [("a", Image.new("RGB", (1569, 1)))])):
        with pytest.raises(AppError): vision.request(model, images)
