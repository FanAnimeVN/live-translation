import json
import threading
from types import SimpleNamespace
import pytest
from PIL import Image, ImageDraw
from manga_live.cloud_ocr import CloudCropOcr, CloudPageDetector
from manga_live.config import Config
from manga_live.errors import AppError
from manga_live.ocr import recognize_regions
from manga_live.text_scope import make_plan, route_regions, story_regions


def fixture():
    image = Image.new("RGB", (80, 120), "white")
    ImageDraw.Draw(image).text((15, 30), "ABC", fill="black")
    cfg = SimpleNamespace(values={"mode": "byok", "provider": "openrouter", "ocr": "cloud-gemini", "cloudConsent": True, "cloudOcrConsent": True})
    calls = []
    vault = SimpleNamespace(get=lambda provider: calls.append(provider) or "fake-test-key")
    return image, cfg, calls, CloudCropOcr(cfg, vault)


def test_image_permission_precedes_encoding_vault_and_network(monkeypatch):
    image, cfg, calls, engine = fixture()
    monkeypatch.setattr("manga_live.cloud_ocr.providers.post_json", lambda *_a, **_k: pytest.fail("unexpected network"))
    for patch in ({"mode": "offline"}, {"provider": "deepseek"}, {"ocr": "manga"}, {"cloudConsent": False}, {"cloudOcrConsent": False}):
        old = dict(cfg.values); cfg.values.update(patch)
        with pytest.raises(AppError): engine.recognize(image)
        cfg.values = old
    assert calls == []
    engine.load()
    assert engine.model is True and calls == []
    assert engine.recognize(Image.new("RGB", (20, 20), "white")) == "" and calls == []


def test_uncertain_cloud_result_never_becomes_memory_or_erasure_evidence(monkeypatch):
    image, cfg, calls, engine = fixture()
    def post(url, body, *args, **kwargs):
        assert body["model"] == "google/gemini-3.5-flash-lite"
        assert body["provider"]["zdr"] is True
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"items": [
            {"id": "0", "ja": "姉ちゃん", "uncertain": True}]})}}]}
    monkeypatch.setattr("manga_live.cloud_ocr.providers.post_json", post)
    regions = [{"id": "original-source-id", "bbox": [0, 0, 80, 120], "score": .9, "overlay": "label"}]
    result = recognize_regions(image, regions, engine, threading.Event(), batch_size=2)
    assert result[0]["id"] == "original-source-id" and result[0]["ja"] == "姉ちゃん"
    assert "cloud_ocr_uncertain" in result[0]["reviewReasons"]
    routed = route_regions(result, make_plan(image, regions, "authored-source"), {})
    assert routed[0]["scope"]["memory"] is False and story_regions(routed) == []
    assert calls == ["openrouter"]


def test_selected_vision_model_is_used_and_is_part_of_engine_identity(monkeypatch):
    image, cfg, calls, _ = fixture()
    cfg.values["cloudOcrModel"] = "anthropic/claude-haiku-5.5"
    engine = CloudCropOcr(cfg, SimpleNamespace(get=lambda provider: "fake-test-key"))
    def post(url, body, *args, **kwargs):
        assert body["model"] == "anthropic/claude-haiku-5.5"
        return {"choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"items": [
            {"id": "0", "ja": "姉ちゃん", "uncertain": False}]})}}]}
    monkeypatch.setattr("manga_live.cloud_ocr.providers.post_json", post)
    assert engine.recognize(image) == "姉ちゃん"
    assert engine.name.startswith("anthropic/claude-haiku-5.5/")


def test_page_detector_requires_separate_consent_and_returns_review_only_boxes(monkeypatch):
    image = Image.new("RGB", (80, 120), "white")
    cfg = SimpleNamespace(values={"mode": "byok", "provider": "openrouter", "detector": "cloud-page",
        "cloudConsent": True, "cloudPageOcrConsent": True, "cloudOcrModel": "google/gemini-3.5-flash-lite"})
    calls = []
    vault = SimpleNamespace(get=lambda provider: calls.append(provider) or "fake-test-key")
    detector = CloudPageDetector(cfg, vault)
    monkeypatch.setattr("manga_live.cloud_ocr.providers.post_json", lambda url, body, *args, **kwargs: {
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"items": [
            {"id": "r000", "ja": "姉ちゃん", "uncertain": True,
             "box": {"x": 10, "y": 20, "w": 30, "h": 40}}]})}}]})
    detector.warmup()
    result = detector.detect(image)
    assert result[0]["bbox"] == [10, 20, 30, 40]
    assert result[0]["review"] is True and "cloud_page_proposal" in result[0]["reviewReasons"]
    assert "cloud_ocr_uncertain" in result[0]["reviewReasons"]
    assert result[0]["speaker"] == result[0]["listener"] == "unknown"
    assert "balloon" not in result[0] and calls == ["openrouter"]


def test_page_detector_warmup_never_requests_and_rejects_missing_consent(monkeypatch):
    image = Image.new("RGB", (20, 20), "white")
    cfg = SimpleNamespace(values={"mode": "byok", "provider": "openrouter", "detector": "cloud-page",
        "cloudConsent": True, "cloudPageOcrConsent": False, "cloudOcrModel": "google/gemini-3.5-flash-lite"})
    detector = CloudPageDetector(cfg, SimpleNamespace(get=lambda _: pytest.fail("vault must not be read")))
    monkeypatch.setattr("manga_live.cloud_ocr.providers.post_json", lambda *_a, **_k: pytest.fail("warmup charged"))
    with pytest.raises(AppError): detector.warmup()
    cfg.values["cloudPageOcrConsent"] = True
    detector.warmup()
    assert detector.model is True


def test_cancelled_reply_never_applied_and_error_does_not_retry(monkeypatch):
    image, _, calls, engine = fixture()
    attempted = []
    def post(*args, **kwargs):
        attempted.append(1); engine.cancel.set()
        return {}
    monkeypatch.setattr("manga_live.cloud_ocr.providers.post_json", post)
    with pytest.raises(AppError) as error: engine.recognize(image)
    assert error.value.code == "CANCELED" and len(attempted) == 1


def test_unreadable_nonblank_crop_keeps_source_id_and_deferred_review(monkeypatch):
    image, _, _, engine = fixture()
    monkeypatch.setattr("manga_live.cloud_ocr.providers.post_json", lambda *_a, **_k: {
        "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"items": [
            {"id": "0", "ja": "", "uncertain": False}]})}}]})
    regions = [{"id": "source-not-lost", "bbox": [0, 0, 80, 120], "score": .9, "overlay": "label"}]
    result = recognize_regions(image, regions, engine, threading.Event(), batch_size=2)
    assert len(result) == 1 and result[0]["id"] == "source-not-lost" and result[0]["ja"] == ""
    routed = route_regions(result, make_plan(image, regions, "authored-source"), {})
    assert routed[0]["scope"]["action"] == "defer" and story_regions(routed) == []


def test_settings_save_has_no_inference_and_offline_clears_image_choice(tmp_path, monkeypatch):
    monkeypatch.setattr("manga_live.cloud_ocr.providers.post_json", lambda *_a, **_k: pytest.fail("settings charged"))
    cfg = Config(tmp_path)
    assert cfg.values["ocr"] == "manga" and cfg.values["cloudOcrConsent"] is False
    patch = {"mode": "byok", "provider": "openrouter", "ocr": "cloud-gemini", "cloudConsent": True}
    with pytest.raises(AppError): cfg.update(patch)
    cfg.update({**patch, "cloudOcrConsent": True})
    assert Config(tmp_path).values["ocr"] == "cloud-gemini"
    cfg.update({"mode": "offline"})
    assert cfg.values["ocr"] == "manga" and not cfg.values["cloudOcrConsent"] and not cfg.values["cloudConsent"]


def test_cloud_page_detector_requires_distinct_full_page_consent_and_offline_resets(tmp_path):
    cfg = Config(tmp_path)
    patch = {"mode": "byok", "provider": "openrouter", "detector": "cloud-page", "cloudConsent": True}
    with pytest.raises(AppError): cfg.update(patch)
    cfg.update({**patch, "cloudPageOcrConsent": True})
    assert Config(tmp_path).values["detector"] == "cloud-page"
    cfg.update({"mode": "offline"})
    assert cfg.values["detector"] == "paddle" and not cfg.values["cloudPageOcrConsent"]
