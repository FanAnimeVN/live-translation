import json
import pytest
from manga_live.errors import AppError
from manga_live.memory import Memory
from manga_live.terminology import term_record, constraints, missing_terms, grounded_proposals


def test_explicit_aliases_do_not_flatten_original_name_changes():
    record=term_record("ice","skill","氷結結界","Băng Kết Kết Giới",[{"ja":"氷の壁","vi":"Bức Tường Băng"}])
    context={"glossary":[{"value":json.dumps(record,ensure_ascii=False)}]}
    regions=[{"id":"a","ja":"氷の壁を使う。"},{"id":"b","ja":"氷結結界だ！"}]
    assert constraints(context,regions)==[{"id":"a","ja":"氷の壁","vi":"Bức Tường Băng"},{"id":"b","ja":"氷結結界","vi":"Băng Kết Kết Giới"}]
    assert missing_terms(context,regions,[{"id":"a","vi":"Dùng Bức Tường Băng."},{"id":"b","vi":"Băng Kết Kết Giới!"}])==[]
    assert len(missing_terms(context,regions,[{"id":"a","vi":"Dùng bức tường."},{"id":"b","vi":"Kết giới băng!"}]))==2


def test_only_grounded_specific_proposals_survive():
    regions=[{"id":"a","ja":"氷結結界だ！"}];items=[{"id":"a","vi":"Băng Kết Kết Giới!"}]
    raw={"terms":[{"ja":"氷結結界","vi":"Băng Kết Kết Giới","category":"skill","region_id":"a"},
                  {"ja":"未来剣","vi":"Tương Lai Kiếm","category":"weapon","region_id":"a"}]}
    assert len(grounded_proposals(raw,regions,items))==1


def test_auto_lock_user_revision_and_temporal_retrieval(tmp_path):
    memory=Memory(tmp_path/"terms.db");memory.ensure_story("s","Test")
    at={"chapter":2,"page":1}
    proposal={"ja":"氷結結界","vi":"Băng Kết Kết Giới","category":"skill","region_id":"a"}
    records=memory.accept_terms("s",at,"p",[proposal]);assert len(records)==1
    assert memory.accept_terms("s",{"chapter":3,"page":0},"p2",[{**proposal,"vi":"Kết giới băng"}])==[]
    assert memory.context("s",{"chapter":1,"page":99},"氷結結界")["data"]["glossary"]==[]
    memory.canonical_term("s",records[0]["entity"],"skill","氷結結界","Băng Phong Kết Giới",[],{"chapter":4,"page":0})
    current=memory.context("s",{"chapter":4,"page":0},"氷結結界")["data"]
    earlier=memory.context("s",at,"氷結結界")["data"]
    assert json.loads(current["glossary"][0]["value"])["vi"]=="Băng Phong Kết Giới"
    assert json.loads(earlier["glossary"][0]["value"])["vi"]=="Băng Kết Kết Giới"
    memory.close()


def test_corrected_page_remains_readable_and_old_summary_cannot_commit(tmp_path):
    memory=Memory(tmp_path/"correction.db");memory.ensure_story("s","Test")
    at={"chapter":1,"page":0};regions=[{"id":"a","ja":"こんにちは","vi":"Xin chào"}]
    memory.save_page("s","p",at,"rev",regions);memory.mark_read("s","p","rev")
    job=memory.next_job()
    memory.set_speaker("s","p","a","A","B",at)
    assert memory.page("s","p","rev")
    memory.correct_region("s","p",at,"rev",{"id":"a","ja":"ありがとう","vi":"Cảm ơn"})
    with pytest.raises(AppError):memory.finish_job(job,{"summary":"Old greeting","facts":[]})
    memory.mark_read("s","p","rev")
    assert json.loads(memory.next_job()["regions"])[0]["vi"]=="Cảm ơn"
    with pytest.raises(AppError):memory.page("s","p","wrong")
    memory.close()


def test_reader_can_confirm_and_later_correct_auto_name_without_rewriting_past(tmp_path):
    memory=Memory(tmp_path/"reader.db");memory.ensure_story("s","Test")
    at={"chapter":2,"page":1};proposal={"ja":"氷結結界","vi":"Băng Kết Kết Giới","category":"skill","region_id":"a"}
    record=memory.accept_terms("s",at,"p",[proposal])[0]
    memory.save_page("s","p",at,"rev",[{"id":"a","ja":"氷結結界だ！","vi":"Băng Kết Kết Giới!"}])
    confirmed=memory.confirm_term("s","p","rev",record["entity"],at)
    assert confirmed["origin"]=="user" and not confirmed["changed"]
    memory.save_page("s","p2",{"chapter":4,"page":0},"rev2",[{"id":"a","ja":"氷結結界だ！","vi":"Băng Kết Kết Giới!"}])
    changed=memory.confirm_term("s","p2","rev2",record["entity"],{"chapter":4,"page":0},"Băng Phong Kết Giới")
    assert changed["changed"]
    assert "Băng Phong" not in memory.context("s",at,"氷結結界")["data"]["glossary"][0]["value"]
    with pytest.raises(AppError):memory.confirm_term("s","p","old",record["entity"],at)
    memory.close()
