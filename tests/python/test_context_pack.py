import json
import pytest
from manga_live.errors import AppError
from manga_live.memory import Memory
from manga_live.context_pack import root_source


def at(chapter, page=0):
    return {"chapter": chapter, "page": page}


def fact(key="A→B", value="A xưng em, gọi B là chị", **extra):
    return {"id": "voice", "kind": "relationship", "key": key, "value": value,
            "chapter": 1, "page": 0, "source": '{"type":"user"}',
            "confirmed": 1, "locked": 1, **extra}


def pack(facts=None):
    return {"schema": 1, "story": {"id": "s", "title": "Story"},
            "facts": facts or [], "summaries": []}


def test_private_roundtrip_restores_profile_progress_and_summary_kind(tmp_path):
    source = Memory(tmp_path / "source.db")
    source.ensure_story("s", "Story", "fantasy")
    metadata = {"qid": "Q123", "label": "Story", "aliases": ["物語", "Story"],
                "scope": "identity-only"}
    source.confirm_metadata("s", metadata)
    source.fact("s", "relationship", "A→B", "em–chị", at(2), {"type": "user"})
    source.summary("s", 1, 2, 4, "Recap riêng", {"type": "user"}, kind="recap")
    source.save_page("s", "p", at(12, 7), "rev", [])
    source.mark_read("s", "p", "rev")
    source.save_page("s", "q", at(3, 2), "rev2", [])
    source.mark_read("s", "q", "rev2")
    exported = source.export("s")
    assert exported["progress"] == {"last_chapter": 3, "last_page": 2, "furthest_chapter": 12}
    target = Memory(tmp_path / "target.db")
    assert target.import_pack(exported) == "s"
    restored = target.export("s")
    assert restored["progress"] == exported["progress"]
    for field in ("genre", "aliases", "metadata"):
        assert restored["story"][field] == exported["story"][field]
    assert restored["summaries"][0]["kind"] == "recap"
    assert target.list_stories()[0]["last_chapter"] == 3
    source.close(); target.close()


def test_reimport_and_own_export_are_idempotent(tmp_path):
    memory = Memory(tmp_path / "repeat.db")
    incoming = pack([fact()])
    memory.import_pack(incoming)
    version = memory.version("s")
    memory.import_pack(incoming)
    memory.import_pack(memory.export("s"))
    assert len(memory.export("s")["facts"]) == 1
    assert memory.version("s") == version
    memory.close()


@pytest.mark.parametrize("field,value", [("confirmed", "false"), ("locked", "false"),
                                        ("locked", 2), ("confirmed", None), ("page", 0.5),
                                        ("chapter", True)])
def test_import_rejects_coerced_flags_and_locations_atomically(tmp_path, field, value):
    memory = Memory(tmp_path / "invalid.db")
    incoming = pack([fact(id="valid"), fact(key="other", id="invalid", **{field: value})])
    with pytest.raises(AppError): memory.import_pack(incoming)
    assert memory.list_stories() == []
    memory.close()


def test_import_cannot_shadow_existing_reader_lock_and_keeps_resume_position(tmp_path):
    memory = Memory(tmp_path / "locked.db")
    memory.ensure_story("s", "My title", "đời thường")
    memory.fact("s", "relationship", "A→B", "em–chị", at(2), {"type": "user"})
    memory.save_page("s", "p", at(8, 2), "r", []); memory.mark_read("s", "p", "r")
    before = memory.export("s")
    incoming = pack([fact(value="tao–mày", chapter=4)])
    incoming["story"]["genre"] = "horror"
    incoming["progress"] = {"last_chapter": 90, "last_page": 0, "furthest_chapter": 90}
    with pytest.raises(AppError) as error: memory.import_pack(incoming)
    assert error.value.code == "CONTEXT_CONFLICT"
    assert memory.export("s") == before
    # A compatible additive import must not move the user's current reading position.
    incoming["facts"] = []
    memory.import_pack(incoming)
    restored = memory.export("s")
    assert restored["story"]["title"] == "My title" and restored["story"]["genre"] == "đời thường"
    assert restored["progress"]["last_chapter"] == 8 and restored["progress"]["last_page"] == 2
    assert restored["progress"]["furthest_chapter"] == 90
    memory.close()


def test_existing_ids_in_another_story_cannot_be_overwritten(tmp_path):
    memory = Memory(tmp_path / "ids.db")
    memory.ensure_story("other", "Other")
    memory.fact("other", "note", "n", "Existing", at(1), {"type": "user"}, fact_id="voice")
    incoming = pack([fact()]); memory.import_pack(incoming); memory.import_pack(incoming)
    assert memory.export("other")["facts"][0]["value"] == "Existing"
    assert len(memory.export("s")["facts"]) == 1
    memory.close()


def test_additive_import_compares_latest_reader_revision_at_its_cutoff(tmp_path):
    memory = Memory(tmp_path / "revisions.db"); memory.ensure_story("s", "Story")
    memory.fact("s", "relationship", "A→B", "em–chị", at(1), {"type": "user"})
    memory.fact("s", "relationship", "A→B", "tôi–cậu", at(3), {"type": "user"})
    memory.import_pack(pack([fact(value="tôi–cậu", chapter=4)]))
    assert memory.context("s", at(2))["data"]["characters"][0]["value"] == "em–chị"
    assert memory.context("s", at(4))["data"]["characters"][0]["value"] == "tôi–cậu"
    memory.close()


def test_cursor_detects_progress_change_without_invalidating_translation_version(tmp_path):
    memory = Memory(tmp_path / "snapshot.db"); memory.ensure_story("s", "Story")
    for i in range(7): memory.fact("s", "note", str(i), "x" * 300, at(1), {"type": "user"})
    first = memory.export_page("s", byte_budget=1600); version = memory.version("s")
    assert first["next"]
    memory.save_page("s", "p", at(4, 2), "r", []); memory.mark_read("s", "p", "r")
    assert memory.version("s") == version
    with pytest.raises(AppError) as error: memory.export_page("s", first["next"], byte_budget=1600)
    assert error.value.code == "STALE_CONTEXT"
    memory.close()


def test_import_does_not_reclassify_group_summaries_or_grow_provenance(tmp_path):
    memory = Memory(tmp_path / "groups.db"); memory.ensure_story("s", "Story")
    memory.summary("s", 1, 1, 0, "Chapter one", {"type": "user"}, True, summary_id="a")
    memory.summary("s", 10, 10, 0, "Chapter ten", {"type": "user"}, True, summary_id="b")
    memory.summary("s", 1, 10, 0, "Group", {"type": "user", "summary_ids": ["a", "b"]}, True, "group")
    exported = memory.export("s"); exported["story"]["id"] = "copy"
    memory.import_pack(exported)
    restored = memory.export("copy")
    group = next(r for r in restored["summaries"] if r["kind"] == "group")
    refs = root_source(group["source"])["summary_ids"]
    assert set(refs) == {r["id"] for r in restored["summaries"] if r["kind"] == "chapter"}
    for _ in range(3): memory.import_pack(memory.export("copy"))
    assert memory.export("copy") == restored
    memory.close()


def summary(sid="a", chapter=1, **extra):
    return {"id": sid, "chapter_start": chapter, "chapter_end": chapter, "page_end": 0,
            "text": f"Chapter {chapter}", "kind": "chapter", "complete": True,
            "source": {"type": "user"}, **extra}


def group(sid="group", refs=None, **extra):
    return summary(sid, 10, kind="group", chapter_start=1, text="Combined",
                   source={"type": "user", "summary_ids": refs or ["a", "b"]}, **extra)


def test_import_group_resolves_equivalent_children_and_reversed_dependencies(tmp_path):
    memory = Memory(tmp_path / "dedup-links.db"); memory.ensure_story("s", "Story")
    memory.summary("s", 1, 1, 0, "Chapter 1", {"type": "user"}, True, summary_id="local-a")
    incoming = pack(); incoming["summaries"] = [group(), summary("b", 10), summary()]
    memory.import_pack(incoming)
    restored = memory.export("s")
    combined = next(r for r in restored["summaries"] if r["kind"] == "group")
    assert root_source(combined["source"])["summary_ids"] == ["local-a", "b"]
    assert len(restored["summaries"]) == 3
    memory.import_pack(incoming); memory.import_pack(restored)
    assert memory.export("s") == restored
    memory.close()


@pytest.mark.parametrize("bad", ["missing", "foreign", "partial", "future", "late-page", "cycle", "duplicate"])
def test_import_rejects_invalid_group_links_atomically(tmp_path, bad):
    memory = Memory(tmp_path / "invalid-links.db")
    memory.ensure_story("other", "Other")
    memory.summary("other", 1, 1, 0, "Private other story", {"type": "user"}, True, summary_id="foreign")
    before = memory.export("other")
    children = [summary(), summary("b", 10)]
    combined = group()
    if bad == "missing": combined["source"]["summary_ids"] = ["absent"]
    if bad == "foreign": combined["source"]["summary_ids"] = ["foreign"]
    if bad == "partial": children[0]["complete"] = False
    if bad == "future": children[1].update(chapter_start=80, chapter_end=80)
    if bad == "late-page": children[1]["page_end"] = 1
    if bad == "cycle": combined["source"]["summary_ids"] = ["group"]
    if bad == "duplicate": combined["source"]["summary_ids"] = ["a", "a"]
    incoming = pack([fact()]); incoming["summaries"] = [*children, combined]
    with pytest.raises(AppError): memory.import_pack(incoming)
    assert memory.export("other") == before
    assert all(r["id"] != "s" for r in memory.list_stories())
    memory.close()


def test_invalid_legacy_group_is_not_prompt_context_or_cutoff_export(tmp_path):
    memory = Memory(tmp_path / "legacy-links.db"); memory.ensure_story("s", "Story")
    memory.summary("s", 1, 1, 0, "Early", {"type": "user"}, True, summary_id="early")
    memory.summary("s", 80, 80, 0, "Future secret", {"type": "user"}, True, summary_id="future")
    memory.summary("s", 1, 10, 0, "Spoiler group", {"type": "user", "summary_ids": ["early"]}, True, "group", "g")
    # Simulate a legacy database, not the newly validated write path.
    with memory.transaction() as db:
        db.execute("UPDATE summaries SET source=? WHERE id='g'", (json.dumps({"type": "user", "summary_ids": ["future"]}),))
    assert "Spoiler group" not in memory.markdown("s", at(20))[0]
    assert all(r["id"] != "g" for r in memory.export_page("s", at=at(20))["summaries"])
    assert any(r["id"] == "g" for r in memory.export("s")["summaries"])  # Kept for explicit repair.
    memory.close()


def test_summary_ids_cannot_overwrite_another_story(tmp_path):
    memory = Memory(tmp_path / "summary-owner.db")
    memory.ensure_story("other", "Other"); memory.ensure_story("s", "Story")
    memory.summary("other", 1, 1, 0, "Keep", {"type": "user"}, summary_id="shared")
    with pytest.raises(AppError): memory.summary("s", 1, 1, 0, "Replace", {"type": "user"}, summary_id="shared")
    assert memory.export("other")["summaries"][0]["text"] == "Keep"
    memory.close()


def test_own_backup_preserves_whitespace_and_does_not_resurrect_invalid_rows(tmp_path):
    memory = Memory(tmp_path / "exact.db"); memory.ensure_story("s", " Story ", " fantasy ")
    memory.fact("s", "note", " note ", "  Giữ nguyên\n  dòng này. ", at(1), {"type": "user"})
    memory.summary("s", 1, 1, 0, " Recap có xuống dòng.\n ", {"type": "user"})
    before = memory.export("s"); memory.import_pack(before)
    assert memory.export("s") == before
    before["facts"][0]["valid"] = 0
    with pytest.raises(AppError): memory.import_pack(before)
    memory.close()
