"""Real pipeline/storage seams; model replies from authored pixels, no network."""
from copy import deepcopy
import hashlib
import io
import threading
from types import SimpleNamespace

from PIL import Image, ImageDraw
import pytest

from manga_live.memory import Memory
from manga_live.pipeline import Pipeline
from manga_live.text_scope import story_regions


def fixture(tmp_path, enabled=True, first=2):
    image = Image.new("RGB", (200, 250), "white")
    draw = ImageDraw.Draw(image)
    for top in range(50, 120, 15):
        draw.rectangle((116, top, 127, top+9), fill="black")
        draw.rectangle((96, top, 106, top+9), fill="black")
    draw.rectangle((12, 180, 20, 190), fill="black")
    layout = [
        {"id": "other", "order": 0, "bbox": [8, 175, 30, 30], "overlay": "label"},
        {"id": "right", "order": 1, "bbox": [104, 45, 30, 86], "overlay": "label"},
        {"id": "left", "order": 2, "bbox": [90, 46, 29, 100], "overlay": "label"},
    ]
    calls = []
    class Engine:
        name = "authored-geometry-ocr"
        def recognize(self, crop):
            calls.append(crop.size)
            return "OCR_WITH_NEIGHBOUR" if crop.size == (30, 86) else "SOURCE_"+str(crop.width)
        def recognize_many(self, crops):
            return [self.recognize(crop) for crop in crops]
    class Translator:
        def signature(self): return "authored-translator"
        def translate(self, regions, *_):
            return [{"id": r["id"], "vi": "Bản dịch tự tạo."} for r in regions], {"translation_ms": 0}
    memory = Memory(tmp_path / "crop-plan.sqlite3")
    config = SimpleNamespace(values={"threads": 4, "detector": "paddle", "ocrBatch": 2, "artCleanup": False})
    pipeline = Pipeline(memory, Translator(), config, tmp_path, first)
    pipeline.ocr = Engine()
    pipeline.detectors = {"paddle": SimpleNamespace(detect=lambda _: deepcopy(layout))}
    buffer = io.BytesIO(); image.save(buffer, format="PNG")
    params = {"storyId": "s", "title": "Authored", "pageId": "p", "revision": "rev1",
              "at": {"chapter": 1, "page": 0}}
    return pipeline, image, layout, calls, buffer.getvalue(), params


@pytest.mark.parametrize("first", [2, 4])
def test_partition_uses_complete_layout_even_across_translation_batches(tmp_path, first):
    pipeline, _, layout, calls, data, params = fixture(tmp_path, first=first)
    try:
        before = deepcopy(layout)
        result = pipeline.process(params, data, threading.Event(), lambda *_: None)
        by_id = {r["id"]: r for r in result["regions"]}
        # The seam is the midpoint of the verified blank band.  Both source
        # crops therefore end/start at x=112; neither crop is allowed to keep
        # the overlap merely because the detector boxes had different widths.
        assert calls == [(30, 30), (22, 86), (22, 100)]
        assert by_id["right"]["ja"] == "SOURCE_22"
        assert layout == before and [r["bbox"] for r in result["regions"]] == [r["bbox"] for r in layout]
        assert all("ocr_crop_partition" in r.get("reviewReasons", [])
                   for r in result["regions"] if r["id"] in {"right", "left"})
        assert [r["id"] for r in story_regions(result["regions"])] == ["other"]
        calls.clear()
        cached = pipeline.process({**params, "revision": "rev2"}, data, threading.Event(), lambda *_: None)
        assert cached["cached"] and calls == []
        assert [(r["id"], r["scope"]["key"]) for r in cached["regions"]] == [
            (r["id"], r["scope"]["key"]) for r in result["regions"]]
    finally:
        pipeline.memory.close()


def test_crop_seam_neighbours_reach_translation_together_without_extra_requests(tmp_path):
    pipeline, _, _, _, data, params = fixture(tmp_path, first=2)
    calls = []
    previous = pipeline.translator.translate
    def record(regions, *args):
        calls.append([r["id"] for r in regions])
        return previous(regions, *args)
    pipeline.translator.translate = record
    try:
        pipeline.process(params, data, threading.Event(), lambda *_: None)
        assert calls == [["other"], ["right", "left"]]
    finally:
        pipeline.memory.close()


def test_default_never_reuses_legacy_text_cache_and_reader_key_is_stable(tmp_path):
    pipeline, _, _, calls, data, params = fixture(tmp_path)
    try:
        candidate = pipeline.process(params, data, threading.Event(), lambda *_: None)
        image_hash = hashlib.sha256(data).hexdigest()
        key = pipeline.page_cache_key("s", "p", params["at"], image_hash, None)
        # A cache written by the pre-partition production path must never be
        # accepted by the current reader.  The new key also remains stable
        # across a page revision, so a normal reread can use the validated
        # result without re-running OCR.
        from manga_live.memory import digest
        legacy_key = digest(["translation-dependencies-v1", "s", "legacy", params["at"], image_hash,
                             None, "paddle", pipeline.ocr.name, pipeline.translator.signature(),
                             "translation-prompt-v21"])
        pipeline.memory.cache_put(legacy_key, "s", params["at"], {"regions": [{"id": "legacy"}]})
        assert key != legacy_key
        assert candidate["cached"] is False
        calls.clear()
        fresh = pipeline.process({**params, "pageId": "legacy", "revision": "rev2"}, data,
                                 threading.Event(), lambda *_: None)
        assert fresh["cached"] is False and calls == [(30, 30), (22, 86), (22, 100)]
        calls.clear()
        cached = pipeline.process({**params, "revision": "rev3"}, data, threading.Event(), lambda *_: None)
        assert cached["cached"] is True and calls == []
        assert [(r["id"], r["scope"]["key"]) for r in cached["regions"]] == [
            (r["id"], r["scope"]["key"]) for r in candidate["regions"]]
    finally:
        pipeline.memory.close()


def test_confirmed_speaker_preserved_and_future_choice_not_used_on_reread(tmp_path):
    pipeline, _, _, calls, data, params = fixture(tmp_path)
    try:
        pipeline.process(params, data, threading.Event(), lambda *_: None)
        pipeline.memory.set_speaker("s", "p", "right", "older", "younger", params["at"], "rev1")
        calls.clear()
        confirmed = pipeline.process({**params, "revision": "rev2"}, data, threading.Event(), lambda *_: None)
        right = next(r for r in confirmed["regions"] if r["id"] == "right")
        assert right["speaker"] == "older" and right["listener"] == "younger"
        assert "ocr_crop_partition" in right.get("reviewReasons", [])
        assert (22, 86) in calls
        calls.clear()
        reread = pipeline.process({**params, "revision": "rev0", "at": {"chapter": 0, "page": 0}},
                                  data, threading.Event(), lambda *_: None)
        right = next(r for r in reread["regions"] if r["id"] == "right")
        assert right["speaker"] == right["listener"] == "unknown" and right["ja"] == "SOURCE_22"
    finally:
        pipeline.memory.close()


def test_source_layout_upgrade_invalidates_pages_but_retains_captured_reader_binding(tmp_path, monkeypatch):
    from manga_live import pipeline as runtime
    pipeline, _, _, calls, data, params = fixture(tmp_path)
    try:
        monkeypatch.setattr(runtime, "LAYOUT_VERSION", "balloon-mask-v16-outer-notch-veto")
        previous = pipeline.process(params, data, threading.Event(), lambda *_: None)
        old_key = pipeline.page_cache_key("s", "p", params["at"], hashlib.sha256(data).hexdigest(), None)
        pipeline.memory.set_speaker("s", "p", "right", "older", "younger", params["at"], "rev1")
        monkeypatch.setattr(runtime, "LAYOUT_VERSION", "balloon-mask-v20-source-footprint-corners")
        new_key = pipeline.page_cache_key("s", "p", params["at"], hashlib.sha256(data).hexdigest(), None)
        assert old_key != new_key
        calls.clear()
        current = pipeline.process({**params, "revision": "rev2"}, data, threading.Event(), lambda *_: None)
        assert current["cached"] is False and calls
        assert [(r["id"], r["bbox"], r["scope"]["key"]) for r in previous["regions"]] == [
            (r["id"], r["bbox"], r["scope"]["key"]) for r in current["regions"]]
        right = next(r for r in current["regions"] if r["id"] == "right")
        assert (right["speaker"], right["listener"]) == ("older", "younger")
    finally:
        pipeline.memory.close()


def test_schedule_upgrade_keeps_accepted_page_cache_and_confirmed_source_bindings(tmp_path, monkeypatch):
    from manga_live import pipeline as runtime
    pipeline, _, _, calls, data, params = fixture(tmp_path, first=2)
    try:
        pipeline.process(params, data, threading.Event(), lambda *_: None)
        pipeline.memory.set_speaker("s", "p", "right", "older", "younger", params["at"], "rev1")
        monkeypatch.setattr(runtime, "SCHEDULE_VERSION", "legacy-schedule")
        previous = pipeline.process({**params, "revision": "rev2"}, data, threading.Event(), lambda *_: None)
        calls.clear()
        monkeypatch.setattr(runtime, "SCHEDULE_VERSION", "upgraded-schedule")
        result = pipeline.process({**params, "revision": "rev3"}, data, threading.Event(), lambda *_: None)
        assert result["cached"] is True and calls == []
        # A cache hit keeps the generation provenance, not the newly imported
        # scheduling label. Reading it must not charge for a cosmetic upgrade.
        assert result["scheduleVersion"] == "legacy-schedule"
        assert [(r["id"], r["bbox"], r["ja"], r["scope"]["key"], r["speaker"], r["listener"]) for r in result["regions"]] == [
            (r["id"], r["bbox"], r["ja"], r["scope"]["key"], r["speaker"], r["listener"]) for r in previous["regions"]]
    finally:
        pipeline.memory.close()


def test_presentation_upgrade_keeps_accepted_page_and_its_original_provenance(tmp_path):
    pipeline, _, _, calls, data, params = fixture(tmp_path)
    detector=pipeline.detectors["paddle"]
    detector.presentation_version="authored-presentation-before"
    translations=[]
    translate=pipeline.translator.translate
    pipeline.translator.translate=lambda rows,*args:(translations.append([r["id"] for r in rows]) or translate(rows,*args))
    try:
        pipeline.process(params,data,threading.Event(),lambda *_:None)
        pipeline.memory.set_speaker("s","p","right","older","younger",params["at"],"rev1")
        accepted=pipeline.process({**params,"revision":"rev2"},data,threading.Event(),lambda *_:None)
        calls.clear();translations.clear()
        detector.presentation_version="authored-presentation-after"
        cached=pipeline.process({**params,"revision":"rev3"},data,threading.Event(),lambda *_:None)
        assert cached["cached"] and calls==[] and translations==[], "A lettering-only upgrade must not trigger paid translation or OCR"
        assert cached["presentationVersion"]=="authored-presentation-before", "An accepted cached surface keeps its actual generation provenance"
        assert cached["regions"]==accepted["regions"]
        right=next(r for r in cached["regions"] if r["id"]=="right")
        assert (right["speaker"],right["listener"])==("older","younger")
    finally:pipeline.memory.close()


def test_presentation_upgrade_resumes_old_ocr_without_relabeling_or_repeating_it(tmp_path):
    from manga_live.errors import AppError
    pipeline, _, _, calls, data, params=fixture(tmp_path,first=4)
    detector=pipeline.detectors["paddle"]
    detector.presentation_version="authored-before"
    translate=pipeline.translator.translate
    def unavailable(*args):raise AppError("CLOUD", "Authored provider failure")
    pipeline.translator.translate=unavailable
    try:
        with pytest.raises(AppError,match="Authored provider failure"):
            pipeline.process(params,data,threading.Event(),lambda *_:None)
        assert calls==[(30,30),(22,86),(22,100)]
        calls.clear();detector.presentation_version="authored-after"
        detector.detect=lambda _:pytest.fail("A lettering upgrade must not discard completed OCR coverage")
        pipeline.translator.translate=translate
        resumed=pipeline.process({**params,"revision":"rev2"},data,threading.Event(),lambda *_:None)
        assert resumed["presentationVersion"]=="authored-before" and calls==[]
        reread=pipeline.process({**params,"revision":"rev3"},data,threading.Event(),lambda *_:None)
        assert reread["cached"] and reread["presentationVersion"]=="authored-before"
    finally:pipeline.memory.close()


def test_legacy_accepted_surface_without_presentation_metadata_remains_readable(tmp_path):
    from manga_live.ocr import LAYOUT_VERSION
    pipeline, _, _, calls, data, params=fixture(tmp_path)
    try:
        previous=pipeline.process(params,data,threading.Event(),lambda *_:None)
        key=pipeline.page_cache_key("s","p",params["at"],hashlib.sha256(data).hexdigest(),None)
        legacy=pipeline.memory.cache_get(key);legacy.pop("presentationVersion",None)
        pipeline.memory.cache_put(key,"s",params["at"],legacy)
        calls.clear()
        pipeline.detectors["paddle"].presentation_version="authored-new"
        pipeline.translator.translate=lambda *_:pytest.fail("Legacy accepted text does not need paid regeneration")
        cached=pipeline.process({**params,"revision":"rev2"},data,threading.Event(),lambda *_:None)
        assert cached["cached"] and calls==[] and cached["regions"]==previous["regions"]
        assert cached["presentationVersion"]==LAYOUT_VERSION
    finally:pipeline.memory.close()
