"""Authored source/reader-binding regressions at the real storage/pipeline seam."""
from copy import deepcopy
import io
import threading
from types import SimpleNamespace
import pytest

from PIL import Image
from manga_live.memory import Memory
from manga_live.pipeline import Pipeline
from manga_live.errors import AppError
import manga_live.memory as memory_module
import manga_live.pipeline as module


def source_binding_fixture(tmp_path, monkeypatch):
    memory = Memory(tmp_path / "source-binding.db")
    memory.ensure_story("s", "Authored speaker fixture")
    observed = []
    class Translator:
        def signature(self): return "authored-translator"
        def translate(self, regions, context, cancel):
            observed.extend(deepcopy(regions))
            return [{"id": r["id"], "vi": "Đã dịch.", "ambiguous": False} for r in regions], {"translation_ms": 0}
    layout = [
        {"id": "r000", "order": 0, "bbox": [480, 620, 40, 120], "overlay": "label"},
        {"id": "r001", "order": 1, "bbox": [150, 110, 40, 120], "overlay": "label"},
    ]
    pipeline = Pipeline.__new__(Pipeline)
    pipeline.memory, pipeline.translator = memory, Translator()
    pipeline.config = SimpleNamespace(values={"detector": "paddle", "ocrBatch": 2, "artCleanup": False})
    pipeline.ocr = SimpleNamespace(name="authored-ocr")
    pipeline.detectors = {"paddle": SimpleNamespace(detect=lambda image: deepcopy(layout))}
    monkeypatch.setattr(module, "recognize_regions", lambda image, regions, *args, **kwargs:
                        [{**deepcopy(r), "ja": "ありがとう。"} for r in regions])
    image = Image.new("RGB", (800, 900), "white")
    buffer = io.BytesIO(); image.save(buffer, format="PNG")
    params = {"storyId": "s", "title": "Authored speaker fixture", "pageId": "p",
              "revision": "rev1", "at": {"chapter": 1, "page": 0}}
    return pipeline, layout, observed, buffer.getvalue(), params


def test_reader_pair_follows_exact_source_region_when_reading_order_ids_change(tmp_path, monkeypatch):
    pipeline, layout, observed, data, params = source_binding_fixture(tmp_path, monkeypatch)
    try:
        pipeline.process(params, data, threading.Event(), lambda *args: None)
        pipeline.memory.set_speaker("s", "p", "r001", "older", "younger", params["at"])
        observed.clear()
        layout[:] = [{**layout[1], "id": "r000", "order": 0}, {**layout[0], "id": "r001", "order": 1}]
        # Simulate the actual layout-version cache boundary, not a manual
        # deletion of reader data or an OCR text change.
        monkeypatch.setattr(module, "LAYOUT_VERSION", "authored-new-reading-order")
        result = pipeline.process({**params, "revision": "rev2"}, data, threading.Event(), lambda *args: None)
        locked = next(r for r in result["regions"] if r["bbox"] == [150, 110, 40, 120])
        other = next(r for r in result["regions"] if r["bbox"] == [480, 620, 40, 120])
        assert (locked["speaker"], locked["listener"]) == ("older", "younger")
        assert (other["speaker"], other["listener"]) == ("unknown", "unknown")
        assert {tuple(r["bbox"]): r["speaker"] for r in observed} == {
            (150, 110, 40, 120): "older", (480, 620, 40, 120): "unknown"}
    finally:
        pipeline.memory.close()


def test_new_lock_on_reused_ordinal_does_not_replace_another_source_binding(tmp_path, monkeypatch):
    pipeline, layout, _, data, params = source_binding_fixture(tmp_path, monkeypatch)
    try:
        pipeline.process(params, data, threading.Event(), lambda *args: None)
        pipeline.memory.set_speaker("s", "p", "r001", "older", "younger", params["at"], "rev1")
        layout[:] = [{**layout[1], "id": "r000", "order": 0}, {**layout[0], "id": "r001", "order": 1}]
        monkeypatch.setattr(module, "LAYOUT_VERSION", "authored-order-v2")
        pipeline.process({**params, "revision": "rev2"}, data, threading.Event(), lambda *args: None)
        pipeline.memory.set_speaker("s", "p", "r001", "stranger", "unknown", params["at"], "rev2")
        result = pipeline.process({**params, "revision": "rev3"}, data, threading.Event(), lambda *args: None)
        assert {tuple(r["bbox"]): r["speaker"] for r in result["regions"]} == {
            (150, 110, 40, 120): "older", (480, 620, 40, 120): "stranger"}
    finally:
        pipeline.memory.close()


def test_reader_retranslation_uses_the_source_bound_pair_after_id_reordering(tmp_path, monkeypatch):
    pipeline, layout, observed, data, params = source_binding_fixture(tmp_path, monkeypatch)
    try:
        pipeline.process(params, data, threading.Event(), lambda *args: None)
        pipeline.memory.set_speaker("s", "p", "r001", "older", "younger", params["at"], "rev1")
        layout[:] = [{**layout[1], "id": "r000", "order": 0}, {**layout[0], "id": "r001", "order": 1}]
        monkeypatch.setattr(module, "LAYOUT_VERSION", "authored-order-retranslation")
        pipeline.process({**params, "revision": "rev2"}, data, threading.Event(), lambda *args: None)
        observed.clear()
        result = pipeline.retranslate({**params, "revision": "rev2", "regionId": "r000", "ja": "聞いて。"}, threading.Event())
        assert result["id"] == "r000"
        assert len(observed) == 1
        assert observed[0]["bbox"] == [150, 110, 40, 120]
        assert (observed[0]["speaker"], observed[0]["listener"]) == ("older", "younger")
    finally:
        pipeline.memory.close()


def test_different_source_image_cannot_inherit_same_page_id_and_ordinal_lock(tmp_path, monkeypatch):
    pipeline, _, _, data, params = source_binding_fixture(tmp_path, monkeypatch)
    try:
        pipeline.process(params, data, threading.Event(), lambda *args: None)
        pipeline.memory.set_speaker("s", "p", "r001", "older", "younger", params["at"], "rev1")
        replacement = Image.new("RGB", (800, 900), "#fafafa")
        output = io.BytesIO(); replacement.save(output, format="PNG")
        result = pipeline.process({**params, "revision": "rev2"}, output.getvalue(), threading.Event(), lambda *args: None)
        assert all(r["speaker"] == r["listener"] == "unknown" for r in result["regions"])
        assert next(r for r in result["regions"] if r["id"] == "r001")["speakerBindingReview"] is True
    finally:
        pipeline.memory.close()


def test_source_bound_pair_outlives_page_cache_and_does_not_cross_future_cutoff(tmp_path):
    clock = [100.]
    memory = Memory(tmp_path / "temporal-binding.db", clock=lambda: clock[0])
    memory.ensure_story("s", "Authored cutoffs")
    region = {"id": "r001", "bbox": [10, 20, 30, 100], "ja": "聞いて。", "scope": {"key": "scope-authored"}}
    at20, at80 = {"chapter": 20, "page": 0}, {"chapter": 80, "page": 0}
    try:
        memory.save_page("s", "p", at20, "rev20", [region])
        memory.set_speaker("s", "p", "r001", "older", "younger", at20, "rev20")
        memory.save_page("s", "p", at80, "rev80", [region])
        memory.set_speaker("s", "p", "r001", "rival", "unknown", at80, "rev80")
        clock[0] += 86401; memory.prune()
        current = [{**region, "id": "r000"}]
        assert memory.bind_speakers("s", "p", at20, current)["r000"]["speaker"] == "older"
        assert memory.bind_speakers("s", "p", at80, current)["r000"]["speaker"] == "rival"
        assert memory.bind_speakers("s", "p", {"chapter": 19, "page": 0}, current)["r000"]["speaker"] == "unknown"
    finally:
        memory.close()


def test_stale_speaker_confirmation_or_duplicate_source_keys_cannot_mutate_reader_choice(tmp_path):
    memory = Memory(tmp_path / "stale-binding.db")
    memory.ensure_story("s", "Authored stale source")
    at = {"chapter": 1, "page": 0}
    region = {"id": "r1", "scope": {"key": "scope-authored"}}
    try:
        memory.save_page("s", "p", at, "current", [region])
        memory.set_speaker("s", "p", "r1", "older", "younger", at, "current")
        version = memory.version("s")
        with pytest.raises(AppError) as error:
            memory.set_speaker("s", "p", "r1", "wrong", "unknown", at, "old")
        assert error.value.code == "STALE" and memory.version("s") == version
        duplicates = [region, {**region, "id": "r2"}]
        assert all(r["speaker"] == "unknown" for r in memory.bind_speakers("s", "p", at, duplicates).values())
        memory.save_page("s", "p", at, "duplicate", duplicates)
        with pytest.raises(AppError) as error:
            memory.set_speaker("s", "p", "r1", "wrong", "unknown", at, "duplicate")
        assert error.value.code == "SPEAKER_SOURCE" and memory.version("s") == version
        assert memory.bind_speakers("s", "p", at, [region])["r1"]["speaker"] == "older"
    finally:
        memory.close()


def test_legacy_ordinal_is_retained_for_review_not_attached_to_todays_geometry(tmp_path):
    memory = Memory(tmp_path / "legacy-binding.db")
    memory.ensure_story("s", "Authored legacy")
    at = {"chapter": 1, "page": 0}
    try:
        memory.set_speaker("s", "p", "r1", "older", "younger", at)
        region = {"id": "r1", "scope": {"key": "scope-today"}}
        memory.save_page("s", "p", at, "current", [region])
        resolved = memory.bind_speakers("s", "p", at, [region])["r1"]
        assert resolved == {"speaker": "unknown", "listener": "unknown", "speakerBindingReview": True}
        assert memory.speaker("s", "p", "r1") == {"speaker": "older", "listener": "younger"}
        memory.set_speaker("s", "p", "r1", "unknown", "unknown", at, "current")
        assert memory.bind_speakers("s", "p", at, [region])["r1"]["speakerBindingReview"] is False
        # The newly confirmed geometry may not be the original legacy bubble.
        # Preserve its old unanchored choice rather than silently erasing it.
        assert memory.db.execute("SELECT speaker,listener FROM speaker_legacy WHERE story='s' AND page_id='p'").fetchall()[0][:] == ("older", "younger")
    finally:
        memory.close()


def test_v2_migration_keeps_legacy_choice_without_inventing_a_source_anchor(tmp_path):
    path = tmp_path / "migration.db"
    at = {"chapter": 1, "page": 0}
    old = Memory(path); old.ensure_story("s", "Authored migration")
    old.set_speaker("s", "p", "r1", "older", "younger", at)
    old.save_page("s", "p", at, "current", [{"id": "r1", "scope": {"key": "scope-current"}}])
    # Construct an authored pre-upgrade database, not the user's database.
    old.db.execute("DROP TABLE speaker_bindings")
    old.db.execute("DROP TABLE IF EXISTS speaker_legacy")
    old.db.execute("PRAGMA user_version=2"); old.db.commit(); old.close()
    current = Memory(path)
    try:
        assert current.speaker("s", "p", "r1") == {"speaker": "older", "listener": "younger"}
        region = {"id": "r1", "scope": {"key": "scope-current"}}
        assert current.bind_speakers("s", "p", at, [region])["r1"]["speaker"] == "unknown"
        assert current.bind_speakers("s", "p", at, [region])["r1"]["speakerBindingReview"] is True
        assert current.db.execute("SELECT COUNT(*) FROM speaker_bindings").fetchone()[0] == 0
        assert current.db.execute("SELECT speaker,listener FROM speaker_legacy").fetchone()[:] == ("older", "younger")
    finally:
        current.close()


@pytest.mark.parametrize("version,table,breakpoint", [
    (2, "speaker_bindings", "PRAGMA user_version=3;"),
    (3, "speaker_legacy", "INSERT INTO speaker_legacy SELECT * FROM speakers;"),
])
def test_interrupted_legacy_history_migration_rolls_back_and_can_resume(tmp_path, monkeypatch, version, table, breakpoint):
    path = tmp_path / "interrupted-migration.db"
    old = Memory(path); old.ensure_story("s", "Authored interrupted migration")
    old.set_speaker("s", "p", "r1", "older", "younger", {"chapter": 1, "page": 0})
    old.db.execute("DROP TABLE speaker_legacy")
    if version == 2: old.db.execute("DROP TABLE speaker_bindings")
    old.db.execute(f"PRAGMA user_version={version}"); old.db.commit(); old.close()
    connect = memory_module.sqlite3.connect
    connections = []
    class BrokenCopy(memory_module.sqlite3.Connection):
        def executescript(self, sql):
            if f"CREATE TABLE {table}" in sql:
                sql = sql.replace(breakpoint,
                                  "INSERT INTO missing_authored_fixture VALUES(1);")
            return super().executescript(sql)
    def failing_connect(*args, **kwargs):
        value = connect(*args, factory=BrokenCopy, **kwargs); connections.append(value); return value
    with monkeypatch.context() as patch:
        patch.setattr(memory_module.sqlite3, "connect", failing_connect)
        try:
            with pytest.raises(memory_module.sqlite3.OperationalError, match="missing_authored_fixture"):
                Memory(path)
        finally:
            for value in connections: value.close()
    with connect(path) as check:
        assert check.execute("PRAGMA user_version").fetchone()[0] == version
        assert check.execute("SELECT name FROM sqlite_master WHERE name=?", (table,)).fetchone() is None
        assert check.execute("SELECT speaker,listener FROM speakers").fetchone() == ("older", "younger")
    resumed = Memory(path)
    try:
        assert resumed.speaker("s", "p", "r1") == {"speaker": "older", "listener": "younger"}
        assert resumed.db.execute("PRAGMA user_version").fetchone()[0] == 4
    finally:
        resumed.close()


def test_legacy_reconfirmation_notice_uses_history_at_the_reading_cutoff(tmp_path):
    memory = Memory(tmp_path / "legacy-history-cutoff.db")
    memory.ensure_story("s", "Authored legacy cutoff")
    region = {"id": "r1", "scope": {"key": "scope-today"}}
    try:
        memory.set_speaker("s", "p", "r1", "older", "younger", {"chapter": 20, "page": 0})
        memory.set_speaker("s", "p", "r1", "rival", "unknown", {"chapter": 80, "page": 0})
        before = memory.bind_speakers("s", "p", {"chapter": 19, "page": 0}, [region])["r1"]
        reread = memory.bind_speakers("s", "p", {"chapter": 20, "page": 0}, [region])["r1"]
        assert before == {"speaker": "unknown", "listener": "unknown", "speakerBindingReview": False}
        # Do not hide an eligible old choice just because the latest ordinal
        # was overwritten later. It is a review notice, never inference data.
        assert reread == {"speaker": "unknown", "listener": "unknown", "speakerBindingReview": True}
    finally:
        memory.close()
