import io
import json
import struct
import threading
import pytest
from manga_live.memory import Memory,context_markdown,encode
from manga_live.errors import AppError
from manga_live.host import read_frame
from manga_live.validation import translation_items
from manga_live.ocr import blank_crop
from PIL import Image

@pytest.fixture
def memory(tmp_path):
    memory=Memory(tmp_path/"memory.db")
    memory.ensure_story("series","Demo","đời thường")
    yield memory
    memory.close()

def at(chapter,page=0):
    return {"chapter":chapter,"page":page}


def test_speaker_edit_and_context_invalidation_are_one_atomic_revision(memory,monkeypatch):
    memory.set_speaker("series","p","r","A","B",at(1))
    old_version=memory.version("series")
    entered=threading.Event();release=threading.Event();reader_started=threading.Event();read_done=threading.Event()
    observed=[];failures=[];invalidate=memory.invalidate
    def pause_invalidation(*args,**kwargs):
        entered.set()
        assert release.wait(3),"Test did not release invalidation"
        invalidate(*args,**kwargs)
    monkeypatch.setattr(memory,"invalidate",pause_invalidation)
    def writer():
        try:memory.set_speaker("series","p","r","B","A",at(1))
        except BaseException as error:failures.append(error)
    def reader():
        reader_started.set()
        with memory.lock:observed.append((memory.speaker("series","p","r"),memory.version("series")))
        read_done.set()
    writing=threading.Thread(target=writer);reading=threading.Thread(target=reader)
    writing.start()
    try:
        assert entered.wait(2);reading.start();assert reader_started.wait(2)
        exposed_half_edit=read_done.wait(.1)
    finally:
        release.set();writing.join(3)
        if reading.ident is not None:reading.join(3)
    assert not failures and not writing.is_alive() and not reading.is_alive()
    assert not exposed_half_edit,"A new speaker must never be visible with the old context revision"
    assert observed==[({"speaker":"B","listener":"A"},old_version+1)]

def test_100_chapters_temporal_cutoff_and_markdown(memory):
    summary_ids = {}
    for chapter in range(1,101):
        summary_ids[chapter] = memory.summary("series",chapter,chapter,10,f"Event only known at chapter {chapter}",{"type":"user"}, True)
        memory.fact("series","event",f"event{chapter}",f"Secret {chapter}",at(chapter),{"type":"user"})
    snapshot=memory.context("series",at(20,11))
    assert len(memory.export("series")["summaries"])==100
    assert all(f["chapter"]<=20 for f in snapshot["data"]["events"] if "chapter" in f)
    assert all(s["chapter_end"]<=20 for s in snapshot["data"]["events"] if "chapter_end" in s)
    assert "Secret 80" not in context_markdown(snapshot["data"])
    memory.summary("series",11,30,10,"Future combined summary",{"type":"dialogue","summary_ids":[summary_ids[11],summary_ids[30]]},True,"group")
    assert "Future combined summary" not in memory.markdown("series",at(20,99))[0]

def test_locked_directed_pronouns_not_overwritten(memory):
    rule=memory.fact("series","relationship","A→B","A xưng em, gọi B là anh",at(2),{"type":"user"},True,True)
    with pytest.raises(AppError):
        memory.fact("series","relationship","A→B","tao-mày",at(3),{"type":"dialogue"},False,False,rule)
    memory.fact("series","relationship","B→A","B xưng anh, gọi A là em",at(2),{"type":"user"})
    assert len(memory.context("series",at(2))["data"]["characters"])==2

def test_malformed_context_pack_is_atomic(memory):
    pack={"schema":1,"story":{"id":"imported","title":"New"},"facts":[
        {"kind":"character","key":"A","value":"Person","chapter":1,"page":0,"source":'{"type":"user"}',"confirmed":1,"locked":1},
        {"kind":"wrong","key":"B","value":"x","chapter":2,"page":0,"source":'{"type":"user"}',"confirmed":1,"locked":1}],"summaries":[]}
    with pytest.raises(AppError):
        memory.import_pack(pack)
    assert not any(s["id"]=="imported" for s in memory.list_stories())

def test_read_history_and_cache_expiry(memory):
    memory.save_page("series","page1",at(8,2),"revision",[])
    assert memory.next_job() is None
    with pytest.raises(AppError):
        memory.mark_read("series","page1","outdated")
    memory.mark_read("series","page1","revision")
    assert memory.list_stories()[0]["last_chapter"]==8
    assert memory.next_job()["page_id"]=="page1"
    memory.cache_put("cache","series",at(8),{"translation":"hello"})
    assert memory.cache_get("cache")
    current=memory.clock();memory.clock=lambda:current+86401;memory.prune()
    assert memory.cache_get("cache") is None
    assert memory.next_job() is None

def test_recent_dialogue_keeps_latest_eighteen_utterances_in_reading_order(memory):
    memory.save_page("series","previous",at(1,9),"rev",
        [{"id":f"old{i}","ja":"前の会話"} for i in range(10)])
    memory.save_page("series","latest",at(2,0),"rev",
        [{"id":f"new{i}","ja":"次の会話"} for i in range(10)])
    memory.mark_read("series","previous","rev")
    memory.mark_read("series","latest","rev")

    recent=memory.context("series",at(2,1))["data"]["recent_dialogue"]
    assert [row["id"] for row in recent]==[
        "old2","old3","old4","old5","old6","old7","old8","old9",
        "new0","new1","new2","new3","new4","new5","new6","new7","new8","new9"]


def test_render_geometry_cannot_displace_recent_dialogue_from_context(memory):
    sources=[{"polygon":[[1,1],[9,1],[9,40],[1,40]],"score":.8} for _ in range(40)]
    regions=[{"id":"question","ja":"鍵は？","vi":"Chìa khóa đâu?","speaker":"A","listener":"B",
              "sourceMembers":sources,"letteringBox":[1,1,20,80]},
             {"id":"answer","ja":"まだ返していない。","vi":"Vẫn chưa trả.","speaker":"B","listener":"A",
              "sourceMembers":sources,"letteringBox":[22,1,20,80]}]
    memory.save_page("series","previous",at(1,1),"rev",regions)
    memory.mark_read("series","previous","rev")

    recent=memory.context("series",at(1,2))["data"]["recent_dialogue"]
    assert [row["id"] for row in recent]==["question","answer"]
    assert [row["ja"] for row in recent]==["鍵は？","まだ返していない。"]
    assert "sourceMembers" not in encode(recent) and "letteringBox" not in encode(recent)
    assert memory.page("series","previous","rev")["regions"]==regions


def test_recent_context_byte_budget_prioritizes_latest_complete_utterances(memory):
    memory.save_page("series","previous",at(1,1),"rev",[
        {"id":"old","ja":"昔の話。","vi":"Đó là chuyện cũ. "*25},
        {"id":"middle","ja":"続きの話。","vi":"Đó là chuyện cũ. "*25},
        {"id":"latest","ja":"まだ返していない。","vi":"Đó là chuyện cũ. "*25}])
    memory.mark_read("series","previous","rev")

    recent=memory.context("series",at(1,2))["data"]["recent_dialogue"]
    assert [row["id"] for row in recent]==["middle","latest"]
    assert recent[-1]["ja"]=="まだ返していない。"
    assert len(encode(recent).encode("utf-8"))<=1500


def test_recent_dialogue_cutoffs_come_from_pages_not_reused_region_ids(memory):
    original={"id":"r1","ja":"まだ知らない。","chapter":999,"page":999}
    memory.save_page("series","previous",at(1,9),"rev",[original])
    memory.save_page("series","latest",at(2,0),"rev",[{"id":"r1","ja":"今わかった。"}])
    memory.mark_read("series","previous","rev")
    memory.mark_read("series","latest","rev")

    recent=memory.context("series",at(2,1))["data"]["recent_dialogue"]
    assert [(row["id"],row.get("chapter"),row.get("page")) for row in recent]==[
        ("r1",1,9),("r1",2,0)]
    assert memory.page("series","previous","rev")["regions"]==[original]


def test_read_queue_can_select_only_explicitly_authorized_jobs(memory):
    for page in (1,2):
        memory.save_page("series",f"p{page}",at(1,page),"revision",[{"id":"r","ja":"はい"}])
    first=memory.mark_read("series","p1","revision")
    second=memory.mark_read("series","p2","revision")
    assert first and second and first!=second
    assert memory.next_job(job_ids=[]) is None
    assert memory.next_job(job_ids=[second])["page_id"]=="p2"
    assert memory.next_job(job_ids=[second],at=at(1,1)) is None
    assert memory.next_job()["page_id"]=="p1"

def test_summary_evidence_and_correction(memory):
    memory.save_page("series","page",at(1),"revision",[{"id":"r1","ja":"こんにちは","vi":"Xin chào"}])
    memory.mark_read("series","page","revision");job=memory.next_job()
    with pytest.raises(AppError):
        memory.finish_job(job,{"summary":"A greets","facts":[{"text":"Fact","evidence_ids":["imaginary"]}]})
    assert memory.export("series")["summaries"]==[]
    memory.finish_job(job,{"summary":"Một lời chào","facts":[{"text":"Có lời chào","evidence_ids":["r1"]}]})
    assert memory.export("series")["facts"][0]["confirmed"]==0
    memory.invalidate("series",at(1),"page")
    assert memory.export("series")["summaries"]==[]


def test_same_page_model_summary_is_not_used_to_translate_earlier_bubbles(memory):
    memory.save_page("series","p",at(1,2),"rev",[{"id":"r","ja":"彼は敵だ。","vi":"Người đó là kẻ địch."}])
    memory.mark_read("series","p","rev");job=memory.next_job()
    memory.finish_job(job,{"summary":"Revealed enemy","facts":[{"text":"Revealed enemy","evidence_ids":["r"]}]})
    assert "Revealed enemy" not in context_markdown(memory.context("series",at(1,2))["data"])
    assert "彼は敵だ。" in context_markdown(memory.context("series",at(1,3))["data"])
    assert "Revealed enemy" not in context_markdown(memory.context("series",at(1,3))["data"])
    # User-supplied recap at this exact starting cutoff is intentionally usable.
    memory.summary("series",0,1,2,"User recap allowed here",{"type":"user"},kind="recap")
    assert "User recap allowed here" in context_markdown(memory.context("series",at(1,2))["data"])


def test_prompt_budget_excludes_database_evidence_overhead(memory):
    memory.fact("series","character","nana","ナナ = Nana",at(1),{"type":"user","note":"x"*3000})
    rows=memory.context("series",at(2),"ナナ")['data']["characters"]
    assert any(row["key"]=="nana" for row in rows)
    assert all("source" not in row and "id" not in row for row in rows)
    assert "note" in memory.export("series")["facts"][0]["source"]


def test_import_keeps_same_page_summary_temporal_provenance(memory):
    memory.save_page("series","p",at(3,2),"rev",[{"id":"r","ja":"秘密だ。","vi":"Là bí mật."}])
    memory.mark_read("series","p","rev")
    memory.finish_job(memory.next_job(),{"summary":"Secret revealed","facts":[{"text":"Secret revealed","evidence_ids":["r"]}]})
    pack=memory.export("series");pack["story"]["id"]="imported"
    memory.import_pack(pack)
    assert "Secret revealed" not in memory.markdown("imported",at(3,2))[0]
    assert "秘密だ。" in memory.markdown("imported",at(3,3))[0]
    assert "Secret revealed" not in memory.markdown("imported",at(3,3))[0]


def test_incorrect_ai_paraphrase_is_preserved_for_review_but_not_used_as_fact(memory):
    memory.save_page("series","p",at(1),"rev",[{"id":"r","ja":"先に帰ってて。","vi":"Cứ về trước đi."}])
    memory.mark_read("series","p","rev")
    memory.finish_job(memory.next_job(),{"summary":"Đã về trước","facts":[{"text":"Đã về trước","evidence_ids":["r"]}]})
    prompt=memory.markdown("series",at(2))[0]
    assert "先に帰ってて。" in prompt and "Đã về trước" not in prompt
    assert memory.export("series")["summaries"][0]["text"]=="Đã về trước"
    # Durable evidence remains available even after source cache expires.
    current=memory.clock();memory.clock=lambda:current+86401;memory.prune()
    assert "先に帰ってて。" in memory.markdown("series",at(2))[0]
    memory.fact("series","event","reader-correction","Được yêu cầu về trước",at(2),{"type":"user"})
    assert "Được yêu cầu về trước" in memory.markdown("series",at(3))[0]


def test_ai_group_uses_child_evidence_not_unverified_group_quotes(memory):
    child = memory.summary("series", 1, 1, 1, "AI đã hiểu sai yêu cầu", {
        "type": "dialogue", "utterances": [{"ja": "先に帰ってて。", "speaker": "unknown"}]}, True)
    memory.summary("series", 1, 2, 1, "AI kể thêm một bí mật", {
        "type": "dialogue", "summary_ids": [child],
        "utterances": [{"ja": "未来の秘密。", "speaker": "invented"}]}, True, "group")
    prompt = memory.markdown("series", at(3))[0]
    assert "先に帰ってて。" in prompt
    assert "未来の秘密。" not in prompt and "invented" not in prompt
    assert "AI kể thêm" not in prompt and "AI đã hiểu sai" not in prompt


def test_old_evidence_is_reachable_through_recent_groups_and_after_restore(memory):
    child = memory.summary("series", 1, 1, 1, "Unverified paraphrase", {
        "type": "dialogue", "utterances": [{"ja": "まだ決めていません。", "speaker": "unknown"}]}, True)
    # The leaf is older than the SQL's 20 most recent summary candidates.
    for chapter in range(2, 24):
        memory.summary("series", 1, chapter, 1, "Unverified rollup", {
            "type": "dialogue", "summary_ids": [child]}, True, "group")
    prompt = memory.markdown("series", at(24))[0]
    assert prompt.count("まだ決めていません。") == 1
    assert "Unverified" not in prompt
    pack = memory.export("series"); pack["story"]["id"] = "restored"
    memory.import_pack(pack)
    restored = memory.markdown("restored", at(24))[0]
    assert restored.count("まだ決めていません。") == 1
    assert "Unverified" not in restored


def test_reader_confirmed_group_text_remains_usable_without_ai_override(memory):
    child = memory.summary("series", 1, 1, 1, "Thông tin độc giả đã xác nhận", {"type": "user"}, True)
    memory.summary("series", 1, 2, 1, "Nhắc lại do độc giả xác nhận", {
        "type": "user", "summary_ids": [child]}, True, "group")
    assert "Nhắc lại do độc giả xác nhận" in memory.markdown("series", at(3))[0]


def test_known_alias_retrieves_old_dialogue_evidence_without_future_facts(memory):
    import json
    memory.fact("series", "character", "nana", json.dumps({"type":"name-forms", "character":"nana",
        "forms":[{"ja":"ナナ", "reading":"Nana", "role":"given"}]}, ensure_ascii=False), at(1), {"type":"user"})
    memory.summary("series", 5, 5, 1, "Unverified old paraphrase", {"type":"dialogue",
        "utterances":[{"ja":"ナナはまだ決めていません。", "speaker":"unknown"}]})
    for page in range(25):
        memory.summary("series", 19, 19, page, "Một ghi chú gần đây không liên quan", {"type":"user"})
    memory.summary("series", 80, 80, 1, "Future secret", {"type":"dialogue",
        "utterances":[{"ja":"ナナが裏切った。", "speaker":"unknown"}]})
    snapshot = memory.context("series", at(20), "ナナはいつ出発する？")
    prompt = context_markdown(snapshot["data"])
    assert "ナナはまだ決めていません。" in prompt
    assert "Unverified old paraphrase" not in prompt and "ナナが裏切った。" not in prompt
    # Known speaker IDs can retrieve relevant name evidence even if the source
    # omits the name. Aliases known only later must not enable earlier lookup.
    with_roles = context_markdown(memory.context("series", at(20), "まだなの？", entities=["nana"])["data"])
    assert "ナナはまだ決めていません。" in with_roles
    early = context_markdown(memory.context("series", at(4), "ナナはいつ出発する？")["data"])
    assert "ナナはまだ決めていません。" not in early and "ナナが裏切った。" not in early


@pytest.mark.parametrize("aliases", [None, 1, "雪牙", {"ja": "雪牙"}, [None], [{"ja": [], "vi": "Tuyết Nha"}]])
def test_malformed_imported_term_cannot_crash_or_drive_evidence_lookup(memory, aliases):
    pack = memory.export("series")
    pack["facts"].append({"kind": "glossary", "key": "broken", "value": json.dumps({
        "type": "canonical-term", "entity": "broken", "category": "weapon",
        "ja": "雪牙", "vi": "Tuyết Nha", "aliases": aliases}, ensure_ascii=False),
        "chapter": 1, "page": 0, "source": {"type": "user"}, "confirmed": 1, "locked": 1})
    memory.import_pack(pack)
    memory.summary("series", 1, 1, 1, "Unverified old paraphrase", {"type": "dialogue",
        "utterances": [{"ja": "雪牙の秘密。"}]})
    for page in range(25):
        memory.summary("series", 2, 2, page, "Recent reader note", {"type": "user"})
    snapshot = memory.context("series", at(3), "雪牙を使え！", entities=["broken"])
    assert "雪牙の秘密。" not in context_markdown(snapshot["data"])
    # Preserve private records for review rather than silently rewriting them.
    assert json.loads(memory.export("series")["facts"][0]["value"])["aliases"] == aliases


@pytest.mark.parametrize("forms", [None, 1, "ナナ", {"ja": "ナナ"}, [None], [{"ja": [], "reading": "Nana", "role": "given"}]])
def test_malformed_name_forms_do_not_crash_context_relevance(memory, forms):
    memory.fact("series", "character", "broken", json.dumps({"type": "name-forms",
        "character": "broken", "forms": forms}, ensure_ascii=False), at(1), {"type": "user"})
    snapshot = memory.context("series", at(2), "ナナ、待って！")
    assert snapshot["cutoff"] == at(2)


@pytest.mark.parametrize("utterances", [None, 1, "not-a-list", {"ja": "秘密。"}])
def test_malformed_dialogue_evidence_is_not_used_or_crashes(memory, utterances):
    memory.summary("series", 1, 1, 1, "Unverified paraphrase", {
        "type": "dialogue", "utterances": utterances})
    prompt = context_markdown(memory.context("series", at(2))["data"])
    assert "Unverified paraphrase" not in prompt and "秘密。" not in prompt


def test_canonical_alias_retrieves_old_evidence_without_future_names(memory):
    memory.canonical_term("series", "blade", "weapon", "雪牙", "Tuyết Nha",
        [{"ja": "白い牙", "vi": "Nanh Trắng"}], at(1))
    memory.summary("series", 5, 5, 1, "Unverified paraphrase", {"type": "dialogue",
        "utterances": [{"ja": "白い牙を預けた。"}]})
    for page in range(25):
        memory.summary("series", 19, 19, page, "Recent unrelated note", {"type": "user"})
    # New alias introduced at chapter 80 must not retrieve evidence at cutoff 20.
    memory.canonical_term("series", "blade", "weapon", "雪牙", "Tuyết Nha",
        [{"ja": "白い牙", "vi": "Nanh Trắng"}, {"ja": "闇の牙", "vi": "Hắc Nha"}], at(80))
    memory.summary("series", 6, 6, 1, "Unverified paraphrase", {"type": "dialogue",
        "utterances": [{"ja": "闇の牙の秘密。"}]})
    before = context_markdown(memory.context("series", at(20), "白い牙はどこ？")["data"])
    assert "白い牙を預けた。" in before and "闇の牙の秘密。" not in before
    after = context_markdown(memory.context("series", at(81), "闇の牙はどこ？")["data"])
    assert "闇の牙の秘密。" in after


def test_relevant_original_evidence_is_not_starved_by_unrelated_reader_notes(memory):
    memory.fact("series", "character", "nana", json.dumps({"type":"name-forms", "character":"nana",
        "forms":[{"ja":"ナナ", "reading":"Nana", "role":"given"}]}, ensure_ascii=False), at(1), {"type":"user"})
    memory.summary("series", 5, 5, 1, "Unverified old paraphrase", {"type":"dialogue",
        "utterances":[{"ja":"ナナはまだ決めていません。"}]})
    for page in range(25):
        memory.fact("series", "note", f"reader-note-{page}", "Unrelated reader note. "*60,
            at(19,page), {"type":"user"})
    snapshot = memory.context("series", at(20), "ナナはいつ出発する？")
    assert "ナナはまだ決めていません。" in context_markdown(snapshot["data"])
    assert len(json.dumps(snapshot["data"]["events"],ensure_ascii=False,separators=(",",":")).encode()) <= 1500


def test_original_quote_lookup_is_memoized_only_within_one_context_snapshot(memory, monkeypatch):
    import manga_live.memory as module
    memory.canonical_term("series", "blade", "weapon", "雪牙", "Tuyết Nha", [], at(1))
    original={"type":"dialogue","utterances":[{"ja":"雪牙を預けた。"}]}
    memory.fact("series", "event", "blade-event", "Unverified paraphrase", at(5,1), original, False, False)
    leaf=memory.summary("series", 5, 5, 1, "Unverified paraphrase", original)
    calls=[];read=module.source_utterances
    def observed(source):
        calls.append(source)
        return read(source)
    monkeypatch.setattr(module,"source_utterances",observed)
    before=memory.context("series",at(10),"雪牙はどこ？")
    assert "雪牙を預けた。" in context_markdown(before["data"])
    assert calls.count(encode(original)) == 1
    memory.invalidate("series",at(5,1),"not-a-cached-page")
    revised={"type":"dialogue","utterances":[{"ja":"雪牙は戻った。"}]}
    memory.summary("series",5,5,1,"Unverified revision",revised,summary_id=leaf)
    after=memory.context("series",at(10),"雪牙はどこ？")
    assert "雪牙は戻った。" in context_markdown(after["data"])
    assert "雪牙を預けた。" not in context_markdown(after["data"])
    assert before["fingerprint"] != after["fingerprint"]


def test_related_locked_reader_correction_has_priority_over_original_dialogue(memory):
    memory.canonical_term("series", "blade", "weapon", "雪牙", "Tuyết Nha", [], at(1))
    memory.summary("series", 5, 5, 1, "Unverified paraphrase", {"type":"dialogue",
        "utterances":[{"ja":"雪牙が戻った。"}]})
    memory.fact("series", "note", "reader-correction", "雪牙: đây chỉ là lời đồn chưa xác nhận.",
        at(6), {"type":"user"})
    events=memory.context("series",at(10),"雪牙は戻ったの？")["data"]["events"]
    assert events[0]["kind"]=="note" and events[0]["key"]=="reader-correction"


def test_summary_retry_is_story_scoped_and_expired_sources_cannot_retry(memory):
    memory.ensure_story("other","Other")
    for story in ("series","other"):
        memory.save_page(story,"p",at(1),"rev",[{"id":"r","ja":"はい","vi":"Vâng"}])
        memory.mark_read(story,"p","rev")
    memory.fail_job(memory.next_job("series"))
    memory.fail_job(memory.next_job("other"))
    assert memory.summary_status("series")["failed"]==1
    assert memory.retry_jobs("series")==1
    assert memory.next_job("other") is None
    assert memory.next_job("series",at(0)) is None
    assert memory.next_job("series",at(1))
    current=memory.clock();memory.clock=lambda:current+86401
    memory.prune()
    assert memory.summary_status("series")["gap"]==1
    assert memory.summary_status("other")["gap"]==1
    assert memory.retry_jobs("other")==0


def test_read_again_refreshes_source_but_does_not_resummarize_completed_job(memory):
    memory.save_page("series","p",at(1),"rev",[{"id":"r","ja":"はい","vi":"Vâng"}])
    memory.mark_read("series","p","rev");job=memory.next_job()
    memory.finish_job(job,{"summary":"Có lời đáp","facts":[]})
    memory.mark_read("series","p","rev")
    assert memory.next_job() is None
    memory.save_page("series","q",at(1,1),"rev2",[{"id":"r","ja":"はい","vi":"Vâng"}])
    memory.mark_read("series","q","rev2");memory.fail_job(memory.next_job())
    memory.mark_read("series","q","rev2")
    assert memory.next_job()["page_id"]=="q"

def test_id_contract_and_frame_limits():
    with pytest.raises(AppError):
        translation_items({"items":[{"id":"wrong","vi":"test"}]},["r1"])
    with pytest.raises(AppError):
        read_frame(io.BytesIO(struct.pack("<I",900000)))
    with pytest.raises(AppError):
        read_frame(io.BytesIO(struct.pack("<I",12)+b"{}"))
    assert blank_crop(Image.new("RGB",(120,120),"white"))

def test_delete_isolated_story(memory):
    memory.ensure_story("other","Other")
    memory.fact("series","character","A","name",at(1),{"type":"user"})
    memory.delete_story("series")
    assert [s["id"] for s in memory.list_stories()]==["other"]
