import hashlib
import base64
import io
import json
import struct
import threading
from types import SimpleNamespace
import pytest
from manga_live.errors import AppError
from manga_live.memory import Memory,encode
from manga_live.host import Host,read_frame


def qa_host(memory):
    host=Host.__new__(Host);host.profile="qa";host.memory=memory
    host.output=io.BytesIO();host.write_lock=threading.Lock();host.context_imports={}
    host.config=SimpleNamespace(values={"autoSummary":False})
    return host


def call(host,op,params):
    host.output=io.BytesIO()
    host.receive({"v":1,"id":"r","profile":"qa","op":op,"params":params})
    host.output.seek(0);return read_frame(host.output)


def test_long_story_export_keeps_each_native_frame_small_and_all_records(tmp_path):
    memory=Memory(tmp_path/"long.db");memory.ensure_story("s","Long story")
    for chapter in range(1,101):
        for page in range(10):
            memory.summary("s",chapter,chapter,page,"Tóm tắt mẫu "*30,
                           {"type":"user","note":"x"*1000})
    expected=memory.export("s")
    assert len(encode(expected).encode())>1000000
    host=qa_host(memory);cursor=None;facts=[];summaries=[]
    while True:
        reply=call(host,"memory.export.page",{"storyId":"s","cursor":cursor})
        assert reply["ok"],reply.get("error")
        assert len(host.output.getvalue())<160000
        facts.extend(reply["result"]["facts"]);summaries.extend(reply["result"]["summaries"])
        cursor=reply["result"]["next"]
        if cursor is None:break
    assert facts==expected["facts"] and summaries==expected["summaries"]
    memory.close()


def test_export_cursor_is_story_version_and_cutoff_bound(tmp_path):
    memory=Memory(tmp_path/"cursor.db");memory.ensure_story("s","Story");memory.ensure_story("other","Other")
    for i in range(7):memory.fact("s","note",str(i),"x"*300,{"chapter":i,"page":0},{"type":"user"})
    cutoff={"chapter":3,"page":0}
    first=memory.export_page("s",at=cutoff,byte_budget=1600)
    assert first["next"] and all(f["chapter"]<=3 for f in first["facts"])
    with pytest.raises(AppError):memory.export_page("other",first["next"],at=cutoff,byte_budget=1600)
    with pytest.raises(AppError):memory.export_page("s",first["next"],at={"chapter":4,"page":0},byte_budget=1600)
    memory.fact("s","note","new","new",{"chapter":0,"page":0},{"type":"user"})
    with pytest.raises(AppError) as error:memory.export_page("s",first["next"],at=cutoff,byte_budget=1600)
    assert error.value.code=="STALE_CONTEXT"
    memory.close()


def test_chunked_import_checks_hash_and_is_atomic(tmp_path):
    memory=Memory(tmp_path/"import.db");host=qa_host(memory)
    pack={"schema":1,"story":{"id":"new","title":"Private story"},"facts":[],"summaries":[]}
    raw=encode(pack).encode();params={"transferId":"transfer","bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
    assert call(host,"context.begin",params)["ok"]
    import base64
    assert call(host,"context.chunk",{"transferId":"transfer","offset":0,"data":base64.b64encode(raw).decode()})["ok"]
    assert call(host,"context.commit",{"transferId":"transfer"})["ok"]
    assert memory.export("new")["story"]["title"]=="Private story"
    params["sha256"]="0"*64
    assert call(host,"context.begin",params)["ok"]
    assert call(host,"context.chunk",{"transferId":"transfer","offset":0,"data":base64.b64encode(raw).decode()})["ok"]
    reply=call(host,"context.commit",{"transferId":"transfer"})
    assert not reply["ok"] and reply["error"]["code"]=="CONTEXT_HASH"
    assert not host.context_imports
    memory.close()


def test_incomplete_and_bad_utf8_imports_leave_no_partial_story(tmp_path):
    memory=Memory(tmp_path/"partial.db");host=qa_host(memory)
    for raw,partial in [(b'{"schema":1}',True),(b'\xff\xfe',False)]:
        assert call(host,"context.begin",{"transferId":"x","bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()})["ok"]
        data=raw[:-1] if partial else raw
        assert call(host,"context.chunk",{"transferId":"x","offset":0,"data":base64.b64encode(data).decode()})["ok"]
        assert not call(host,"context.commit",{"transferId":"x"})["ok"]
        assert memory.list_stories()==[] and host.context_imports=={}
    memory.close()


def test_transfer_quota_offsets_expiry_and_cancel_are_enforced(tmp_path,monkeypatch):
    memory=Memory(tmp_path/"quota.db");host=qa_host(memory)
    begin=lambda name,size:call(host,"context.begin",{"transferId":name,"bytes":size,"sha256":"0"*64})
    assert begin("one",8*1024*1024)["ok"] and begin("two",8*1024*1024)["ok"]
    assert not begin("third",1)["ok"] and not begin("one",1)["ok"]
    for offset in (False,1,-1,0.5):
        assert not call(host,"context.chunk",{"transferId":"one","offset":offset,"data":"YQ=="})["ok"]
        assert not host.context_imports["one"]["data"]
    assert not call(host,"context.chunk",{"transferId":"one","offset":0,"data":base64.b64encode(b"x"*(128*1024+1)).decode()})["ok"]
    assert call(host,"context.cancel",{"transferId":"one"})["ok"] and begin("third",1)["ok"]
    expired_at=host.context_imports["two"]["created"]+121
    monkeypatch.setattr("manga_live.host.time.monotonic",lambda:expired_at)
    assert not call(host,"context.chunk",{"transferId":"two","offset":0,"data":"YQ=="})["ok"]
    assert "two" not in host.context_imports
    assert begin("fresh",16*1024*1024)["ok"]
    memory.close()


def test_export_rejects_an_individually_oversized_record_without_truncation(tmp_path):
    memory=Memory(tmp_path/"oversized.db");memory.ensure_story("s","Story")
    memory.fact("s","note","large","x"*1490,{"chapter":1,"page":0},{"type":"user"})
    with pytest.raises(AppError) as error:memory.export_page("s",byte_budget=1024)
    assert error.value.code=="CONTEXT_RECORD_SIZE"
    assert memory.export("s")["facts"][0]["value"]=="x"*1490
    memory.close()
