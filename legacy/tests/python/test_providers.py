import threading
from types import SimpleNamespace
from manga_live.providers import Translator
from manga_live.errors import AppError
import pytest
from manga_live.providers import LlamaWorker
import manga_live.providers as providers
import time
import json
import os
from pathlib import Path
import subprocess


def test_short_local_truncation_is_not_reported_as_oversized_selection(monkeypatch):
    worker=LlamaWorker("unused","unused")
    worker.process=SimpleNamespace();worker.base="http://127.0.0.1:1"
    monkeypatch.setattr(worker,"start",lambda cancel:None)
    calls=[]
    def response(*args,**kwargs):
        calls.append(1)
        # Same failure shape as the 14-character real-model reproduction.
        return {"choices":[{"finish_reason":"length","message":{"content":'{"r":"“Nee-chan, chưa về à?”}'}}]}
    monkeypatch.setattr(providers,"post_json",response)
    with pytest.raises(AppError) as failure:worker.generate("short source",threading.Event())
    assert failure.value.code=="TRUNCATED" and len(calls)==1
    assert "quá dài" not in failure.value.message and "nhỏ hơn" not in failure.value.message
    assert "model" in failure.value.message.casefold()
import sys


@pytest.mark.parametrize("source,bad,good,reason",[
    ("「姉ちゃん、まだ帰らないの？",'“Nee-chan, vẫn chưa về à?”,',"Nee-chan, vẫn chưa về à?","unsupported_quote_completion"),
    ("「明日は来なくてもいい。",'“Ngày mai không cần đến cũng được.”',"Ngày mai không cần đến cũng được.","unsupported_quote_completion"),
    ("こんにちは。",'"Xin chào."',"Xin chào.","added_outer_quotes"),
    ("こんにちは。",'Xin chào.\\"',"Xin chào.","literal_serialization_escape"),
    ("「こんにちは。」",'“Xin chào.”,',"“Xin chào.”","trailing_serialization_punctuation"),
    ("こんにちは。","Xin chào.\x00","Xin chào.","unsupported_control_character"),
    ("「明日は来なくてもいい。",'“',"“Ngày mai không cần đến cũng được.","missing_translation_text"),
])
def test_spurious_model_punctuation_is_repaired_before_overlay(source,bad,good,reason):
    """Replay actual native-output shapes, not a CSS-only demonstration."""
    translator=Translator.__new__(Translator);calls=[]
    from manga_live.ocr import review_reasons
    region={"id":"r","ja":source,"reviewReasons":review_reasons(source)}
    original=dict(region)
    def response(regions,context,cancel):
        calls.append(context)
        return [{"id":"r","vi":bad if len(calls)==1 else good}],{"translation_ms":1,"usage":{}}
    translator._translate=response
    items,metrics=translator.translate([region],{},threading.Event())
    assert items[0]["vi"]==good and metrics["attempts"]==2
    assert reason in {issue["reason"] for issue in calls[1]["output_repair"]}
    assert region==original,"Output validation must not rewrite OCR evidence"


@pytest.mark.parametrize("source,target",[
    ("「明日は来なくてもいい。」",'“Ngày mai không cần đến cũng được.”'),
    ("「明日は来なくてもいい。",'“Ngày mai không cần đến cũng được.'),
    ("明日は来なくてもいい。」",'Ngày mai không cần đến cũng được.”'),
    ("「はい」、と答えた。",'Trả lời: “Vâng”, rồi.'),
    ("ま、待って…！？",'Đ-đợi đã…!?'),
    ("技名は『氷結結界』だ。",'Chiêu này tên là “Kết giới băng giá”.'),
    (r"C:\new\file の場所を確認。",r"Kiểm tra C:\new\file."),
    ("こんにちは。",'Xin chào.\nChào nhé!'),
])
def test_meaningful_source_punctuation_and_continued_quotes_are_not_deleted(source,target):
    translator=Translator.__new__(Translator)
    translator._translate=lambda *args:([{"id":"r","vi":target}],{"translation_ms":1,"usage":{}})
    items,metrics=translator.translate([{"id":"r","ja":source}],{},threading.Event())
    assert items[0]["vi"]==target and metrics["attempts"]==1


def test_reader_locked_quoted_label_is_not_treated_as_an_added_wrapper():
    from manga_live.terminology import term_record
    context={"glossary":[{"confirmed":1,"value":json.dumps(term_record("star","weapon","星の剣",'“Kiếm Sao”'))}]}
    translator=Translator.__new__(Translator)
    translator._translate=lambda *args:([{"id":"r","vi":'“Kiếm Sao”'}],{"translation_ms":1,"usage":{}})
    items,metrics=translator.translate([{"id":"r","ja":"星の剣"}],context,threading.Event())
    assert items[0]["vi"]=='“Kiếm Sao”' and metrics["attempts"]==1


@pytest.mark.parametrize("source,target",[("…！？","…!?"),("♡","♥")])
def test_punctuation_only_source_remains_expressive_without_invented_words(source,target):
    from manga_live.validation import translation_output_issues
    assert not translation_output_issues([{"id":"r","ja":source}],[{"id":"r","vi":target}])


def test_exact_reader_locked_symbolic_label_is_not_rejected_as_missing_dialogue():
    from manga_live.terminology import term_record
    context={"glossary":[{"confirmed":1,"value":json.dumps(term_record("star","weapon","星の剣","★"))}]}
    translator=Translator.__new__(Translator)
    translator._translate=lambda *args:([{"id":"r","vi":"★"}],{"translation_ms":1,"usage":{}})
    items,metrics=translator.translate([{"id":"r","ja":"星の剣"}],context,threading.Event())
    assert items[0]["vi"]=="★" and metrics["attempts"]==1


def test_persistently_spurious_punctuation_never_reaches_overlay():
    translator=Translator.__new__(Translator);calls=[]
    def response(*args):
        calls.append(1)
        return [{"id":"r","vi":'“Xin chào.”,'}],{"translation_ms":1,"usage":{}}
    translator._translate=response
    with pytest.raises(AppError) as error:
        translator.translate([{"id":"r","ja":"こんにちは。"}],{},threading.Event())
    assert error.value.code=="MODEL_OUTPUT" and len(calls)==2


def test_decoded_json_quotes_are_checked_before_offline_overlay():
    translator=Translator.__new__(Translator)
    translator.config=SimpleNamespace(values={"mode":"offline"})
    translator.signature=lambda:"test-offline"
    calls=[]
    class Worker:
        def generate(self,prompt,cancel,schema=None,max_tokens=900):
            calls.append(prompt)
            value='“Nee-chan, vẫn chưa về à?”,' if len(calls)==1 else "Nee-chan, vẫn chưa về à?"
            return json.dumps({"r":value},ensure_ascii=False),{"prompt_tokens":10,"completion_tokens":5}
    translator.local=Worker()
    region={"id":"r","ja":"「姉ちゃん、まだ帰らないの？","reviewReasons":["quote_balance"]}
    items,metrics=translator.translate([region],{},threading.Event())
    assert items[0]["vi"]=="Nee-chan, vẫn chưa về à?" and metrics["attempts"]==2
    assert metrics["usage"]=={"prompt_tokens":20,"completion_tokens":10}
    assert "incomplete quotation" in calls[0] and "Repair:" in calls[1]


def test_bounded_repair_only_regenerates_faulty_regions_and_keeps_valid_terms():
    translator=Translator.__new__(Translator);calls=[]
    regions=[{"id":"a","ja":"こんにちは。"},{"id":"b","ja":"ありがとう。"},{"id":"c","ja":"さようなら。"}]
    def response(selected,context,cancel):
        calls.append([r["id"] for r in selected])
        if len(calls)==1:
            return [{"id":"a","vi":"Xin chào."},{"id":"b","vi":'“Cảm ơn.”,'},{"id":"c","vi":"Tạm biệt."}],{
                "translation_ms":5,"usage":{"prompt_tokens":30,"completion_tokens":20},
                "terms":[{"region_id":"a","vi":"valid-a"},{"region_id":"b","vi":"invalid-b"}]}
        return [{"id":"b","vi":"Cảm ơn."}],{"translation_ms":3,"usage":{"prompt_tokens":10,"completion_tokens":5},
                                               "terms":[{"region_id":"b","vi":"fixed-b"}]}
    translator._translate=response
    items,metrics=translator.translate(regions,{},threading.Event())
    assert calls==[["a","b","c"],["b"]]
    assert items==[{"id":"a","vi":"Xin chào."},{"id":"b","vi":"Cảm ơn."},{"id":"c","vi":"Tạm biệt."}]
    assert metrics["translation_ms"]==8 and metrics["attempts"]==2
    assert metrics["usage"]=={"prompt_tokens":40,"completion_tokens":25}
    assert metrics["terms"]==[{"region_id":"a","vi":"valid-a"},{"region_id":"b","vi":"fixed-b"}]


def test_retry_usage_counts_both_paid_attempts():
    translator=Translator.__new__(Translator)
    attempts=iter([
        ([{"id":"r","vi":"Chị ơi"}],{"translation_ms":20,"usage":{"prompt_tokens":100,"completion_tokens":10,"cost":0.001}}),
        ([{"id":"r","vi":"Nee-chan"}],{"translation_ms":30,"usage":{"prompt_tokens":120,"completion_tokens":12,"cost":0.002}}),
    ])
    translator._translate=lambda *args:next(attempts)
    _,metrics=translator.translate([{"id":"r","ja":"姉ちゃん、聞いて。"}],{},threading.Event())
    assert metrics["translation_ms"]==50
    assert metrics["usage"]["prompt_tokens"]==220
    assert metrics["usage"]["completion_tokens"]==22
    assert metrics["usage"]["cost"]==0.003
    assert metrics["attempts"]==2


@pytest.mark.parametrize("bad,good",[
    ("Chị nee-chan, nghe này.","Nee-chan, nghe này."),
    ("Chị nee-chan","Nee-chan"),
    ("Chị gái nee-chan nghe này.","Nee-chan nghe này."),
])
@pytest.mark.parametrize("source",["姉ちゃん、聞いて。","姉ちゃん"])
def test_redundant_title_repairs_only_the_failed_id_at_the_cloud_seam(monkeypatch,bad,good,source):
    translator=Translator.__new__(Translator)
    translator.config=SimpleNamespace(values={"mode":"byok","provider":"openrouter",
        "cloudConsent":True,"openrouterModel":"qwen/qwen3.8-flash"})
    translator.vault=SimpleNamespace(get=lambda provider:"fake-qa-key")
    translator.signature=lambda:"test-cloud";calls=[]
    def reply(url,body,*args,**kwargs):
        calls.append(body)
        items=([{ "id":"a","vi":bad,"ambiguous":True},
                {"id":"b","vi":"Cảm ơn.","ambiguous":False}] if len(calls)==1 else
               [{"id":"a","vi":good,"ambiguous":True}])
        return {"choices":[{"message":{"content":json.dumps({"items":items,"terms":[]},ensure_ascii=False)}}],
                "usage":{"cost":0.001}}
    monkeypatch.setattr(providers,"post_json",reply)
    items,metrics=translator.translate([{"id":"a","ja":source},
        {"id":"b","ja":"ありがとう。"}],{},threading.Event())
    assert items[0]["vi"]==good and items[1]["vi"]=="Cảm ơn."
    assert metrics["attempts"]==2 and metrics["usage"]["cost"]==pytest.approx(.002)
    assert '"id": "b"' not in calls[1]["messages"][0]["content"]
    assert "redundant_retained_vocative" in calls[1]["messages"][0]["content"]


def test_persistent_sibling_stack_is_not_displayed_or_retried_indefinitely():
    translator=Translator.__new__(Translator);calls=[]
    def response(regions,context,cancel):
        calls.append(context)
        return [{"id":"r","vi":"Chị nee-chan"}],{"translation_ms":1,"usage":{}}
    translator._translate=response
    with pytest.raises(AppError) as error:
        translator.translate([{"id":"r","ja":"姉ちゃん！"}],{},threading.Event())
    assert error.value.code=="MODEL_OUTPUT" and len(calls)==2
    assert calls[1]["output_repair"]==[{"id":"r","reason":"redundant_retained_vocative"}]


@pytest.mark.parametrize("bad",["キリト、待って！","Được rồi. Tôi sẽ chờ.”} 翻译为： {"])
def test_no_source_echo_or_serialization_commentary_reaches_overlay(bad):
    translator=Translator.__new__(Translator);calls=[]
    def response(regions,context,cancel):
        calls.append(context)
        return [{"id":"r","vi":bad if len(calls)==1 else "Kirito, đợi đã!"}],{"translation_ms":1,"usage":{}}
    translator._translate=response
    items,metrics=translator.translate([{"id":"r","ja":"キリト、待って！"}],{},threading.Event())
    assert items[0]["vi"]=="Kirito, đợi đã!" and metrics["attempts"]==2
    assert calls[1]["output_repair"]


def test_persistently_untranslated_source_fails_closed_but_names_and_sfx_are_allowed():
    translator=Translator.__new__(Translator)
    translator._translate=lambda regions,*args:([{"id":r["id"],"vi":r["ja"]} for r in regions],{"translation_ms":1,"usage":{}})
    with pytest.raises(AppError) as error:
        translator.translate([{"id":"r","ja":"キリト、待って！"}],{},threading.Event())
    assert error.value.code=="MODEL_OUTPUT"
    assert translator.translate([{"id":"r","ja":"キリト"}],{},threading.Event())[0][0]["vi"]=="キリト"
    assert translator.translate([{"id":"r","ja":"ドキドキ","type":"sfx"}],{},threading.Event())[0][0]["vi"]=="ドキドキ"


def test_pronoun_placeholder_is_repaired_once_and_persistent_failure_never_reaches_overlay():
    translator=Translator.__new__(Translator);calls=[]
    bad="Senpai, anh/chị có thể giúp tôi được không?"
    def response(regions,context,cancel):
        calls.append(context)
        return [{"id":"r","vi":bad if len(calls)==1 else "Senpai, giúp một tay được không ạ?"}],{
            "translation_ms":1,"usage":{"prompt_tokens":10,"completion_tokens":5}}
    translator._translate=response
    region={"id":"r","ja":"先輩、手伝ってもらえますか。"}
    items,metrics=translator.translate([region],{},threading.Event())
    assert items[0]["vi"]=="Senpai, giúp một tay được không ạ?" and metrics["attempts"]==2
    assert calls[1]["output_repair"]==[{"id":"r","reason":"unresolved_address_placeholder"}]
    assert metrics["usage"]=={"prompt_tokens":20,"completion_tokens":10}
    failures=[]
    def persistent(regions,context,cancel):
        failures.append(context)
        return [{"id":"r","vi":bad}],{"translation_ms":1,"usage":{}}
    translator._translate=persistent
    with pytest.raises(AppError) as error:translator.translate([region],{},threading.Event())
    assert error.value.code=="MODEL_OUTPUT" and len(failures)==2


def test_confirmed_role_reversal_is_repaired_before_overlay():
    from manga_live.linguistics import voice_record
    translator=Translator.__new__(Translator);calls=[]
    region={"id":"r","ja":"先に帰ってて。あとで行くから。","speaker":"sister","listener":"younger"}
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(voice_record("sister","younger","chị","em"))}]}
    def response(regions,context,cancel):
        calls.append(context)
        return [{"id":"r","vi":"Chị về trước nhé. Lát nữa chị sẽ đến." if len(calls)==1 else
                 "Em về trước nhé. Lát nữa chị sẽ đến."}],{"translation_ms":1,"usage":{}}
    translator._translate=response
    items,metrics=translator.translate([region],context,threading.Event())
    assert items[0]["vi"].startswith("Em về") and metrics["attempts"]==2
    assert calls[1]["output_repair"]==[{"id":"r","reason":"directed_request_role_conflict"}]
    assert "output_repair" not in context


def test_confirmed_implicit_waiter_role_reversal_is_repaired_before_overlay():
    from manga_live.linguistics import voice_record
    translator=Translator.__new__(Translator);calls=[]
    region={"id":"r","ja":"わかった。待ってるね。","speaker":"younger","listener":"sister"}
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(
        voice_record("younger","sister","em","chị"))}]}
    def response(regions,context,cancel):
        calls.append(context)
        return [{"id":"r","vi":"Được rồi. Chị sẽ chờ em." if len(calls)==1 else
                 "Được rồi. Em sẽ chờ chị."}],{"translation_ms":1,"usage":{}}
    translator._translate=response
    items,metrics=translator.translate([region],context,threading.Event())
    assert items[0]["vi"].endswith("Em sẽ chờ chị.") and metrics["attempts"]==2
    assert calls[1]["output_repair"]==[{"id":"r","reason":"directed_wait_role_conflict"}]
    assert "output_repair" not in context


def test_confirmed_implicit_waiter_generic_first_person_is_repaired_before_overlay():
    from manga_live.linguistics import voice_record
    translator=Translator.__new__(Translator);calls=[]
    region={"id":"r","ja":"わかった。待ってるね。","speaker":"younger","listener":"sister"}
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(
        voice_record("younger","sister","em","chị"))}]}
    def response(regions,context,cancel):
        calls.append(context)
        return [{"id":"r","vi":"Được rồi. Tôi sẽ chờ cô ấy." if len(calls)==1 else
                 "Được rồi. Em sẽ chờ chị."}],{"translation_ms":1,"usage":{}}
    translator._translate=response
    items,metrics=translator.translate([region],context,threading.Event())
    assert items[0]["vi"].endswith("Em sẽ chờ chị.") and metrics["attempts"]==2
    assert calls[1]["output_repair"]==[{"id":"r","reason":"directed_wait_role_conflict"}]


def test_cancel_stops_local_generation_promptly_without_killing_next_worker(monkeypatch):
    terminated=threading.Event();entered=threading.Event();cancel=threading.Event();result=[]
    class Process:
        def poll(self):return 0 if terminated.is_set() else None
        def terminate(self):terminated.set()
        def wait(self,timeout=None):return 0
    worker=LlamaWorker("not-used","not-used");worker.process=Process();worker.base="http://127.0.0.1:1"
    monkeypatch.setattr(worker,"start",lambda event:None)
    def blocked(*args,**kwargs):
        entered.set();terminated.wait(2)
        if terminated.is_set():raise AppError("NETWORK","worker stopped")
        return {"choices":[{"message":{"content":"done"}}]}
    monkeypatch.setattr(providers,"post_json",blocked)
    def generate():
        try:worker.generate("test",cancel)
        except AppError as error:result.append(error.code)
    thread=threading.Thread(target=generate);thread.start();assert entered.wait(1)
    start=time.perf_counter();cancel.set();thread.join(timeout=1)
    assert not thread.is_alive() and time.perf_counter()-start<1
    assert terminated.is_set() and result==["CANCELED"]


def test_summary_generation_uses_evidence_constrained_schema():
    translator=Translator.__new__(Translator);captured={}
    translator.config=SimpleNamespace(values={"summaryBackend":"local"})
    class Worker:
        def generate(self,prompt,cancel,schema=None,max_tokens=900):
            captured["schema"]=schema
            return '{"summary":"Có lời chào","facts":[]}',{}
    translator.summary_worker=Worker()
    translator.summarize({"regions":json.dumps([{"id":"r1","ja":"こんにちは。","vi":"Xin chào."}])},threading.Event())
    schema=captured["schema"]
    assert schema["additionalProperties"] is False
    assert schema["properties"]["facts"]["items"]["properties"]["evidence_ids"]["items"]["enum"]==["r1"]


def test_old_cancellation_watchdog_never_stops_replacement_process(monkeypatch):
    entered=threading.Event();old_stopped=threading.Event();cancel=threading.Event();result=[]
    class Process:
        def __init__(self):self.stopped=threading.Event()
        def poll(self):return 0 if self.stopped.is_set() else None
        def terminate(self):self.stopped.set()
        def wait(self,timeout=None):return 0
    worker=LlamaWorker("unused","unused");old=Process();replacement=Process();worker.process=old
    monkeypatch.setattr(worker,"start",lambda event:None)
    def blocked(*args,**kwargs):
        entered.set();old.stopped.wait(1)
        raise AppError("NETWORK","old worker closed")
    monkeypatch.setattr(providers,"post_json",blocked)
    def generate():
        try:worker.generate("test",cancel)
        except AppError as error:result.append(error.code)
    thread=threading.Thread(target=generate);thread.start();assert entered.wait(1)
    worker.process=replacement;cancel.set();thread.join(timeout=1)
    assert not thread.is_alive() and old.stopped.is_set()
    assert worker.process is replacement and not replacement.stopped.is_set()
    assert result==["CANCELED"]


def test_interruption_during_model_health_check_does_not_dereference_cleared_process(monkeypatch,tmp_path):
    executable=tmp_path/"server.exe";model=tmp_path/"model.gguf"
    executable.touch();model.touch();worker=LlamaWorker(executable,model)
    class Process:
        stopped=False
        def poll(self):return 0 if self.stopped else None
        def terminate(self):self.stopped=True
        def wait(self,timeout=None):return 0
    process=Process();monkeypatch.setattr(providers.subprocess,"Popen",lambda *args,**kwargs:process)
    monkeypatch.setattr(providers,"own_process",lambda process:None)
    class Opener:
        def open(self,*args,**kwargs):
            worker.stop()
            raise providers.urllib.error.URLError("interrupted")
    monkeypatch.setattr(providers.urllib.request,"build_opener",lambda *args:Opener())
    with pytest.raises(AppError) as error:worker.start(threading.Event())
    assert error.value.code=="CANCELED" and worker.process is None


def test_explicit_empty_process_capture_does_not_stop_successor():
    worker=LlamaWorker("unused","unused")
    class Process:
        def poll(self):return None
        def terminate(self):pytest.fail("Empty capture must not terminate a successor")
    replacement=Process();worker.process=replacement
    worker.stop(expected=None)
    assert worker.process is replacement


def test_late_successful_health_response_cannot_revive_interrupted_start(monkeypatch,tmp_path):
    executable=tmp_path/"server.exe";model=tmp_path/"model.gguf"
    executable.touch();model.touch();worker=LlamaWorker(executable,model)
    class Process:
        stopped=False
        def poll(self):return 0 if self.stopped else None
        def terminate(self):self.stopped=True
        def wait(self,timeout=None):return 0
    original=Process();replacement=Process()
    monkeypatch.setattr(providers.subprocess,"Popen",lambda *args,**kwargs:original)
    monkeypatch.setattr(providers,"own_process",lambda process:None)
    class Response:
        status=200
        def __enter__(self):return self
        def __exit__(self,*args):pass
    class Opener:
        def open(self,*args,**kwargs):
            worker.stop(expected=original)
            with worker._process_lock:worker.process=replacement
            return Response()
    monkeypatch.setattr(providers.urllib.request,"build_opener",lambda *args:Opener())
    with pytest.raises(AppError) as error:worker.start(threading.Event())
    assert error.value.code=="CANCELED"
    assert worker.process is replacement and not replacement.stopped


@pytest.mark.skipif(os.name!="nt",reason="Windows native-host lifecycle")
def test_abrupt_host_exit_cannot_leave_its_model_worker_running():
    """Real parent/child handles, no model load, cloud, or personal profile.

    The mocked health response avoids an HTTP/model dependency; the real
    LlamaWorker startup still owns a harmless sleeping Python subprocess.
    The parent is killed without calling stop(), like an abruptly closed host.
    """
    import ctypes
    from ctypes import wintypes
    kernel=ctypes.WinDLL("kernel32",use_last_error=True)
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    kernel.WaitForSingleObject.restype=wintypes.DWORD
    kernel.TerminateProcess.argtypes=[wintypes.HANDLE,wintypes.UINT]
    kernel.TerminateProcess.restype=wintypes.BOOL
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.CloseHandle.restype=wintypes.BOOL
    program=r'''
import sys,threading,time
import manga_live.providers as providers
spawn=providers.subprocess.Popen
providers.subprocess.Popen=lambda args,**kwargs:spawn([sys.executable,"-c","import time; time.sleep(60)"],**kwargs)
class Response:
    status=200
    def __enter__(self):return self
    def __exit__(self,*args):pass
class Opener:
    def open(self,*args,**kwargs):return Response()
providers.urllib.request.build_opener=lambda *args:Opener()
worker=providers.LlamaWorker(sys.executable,sys.executable)
worker.start(threading.Event())
print(worker.process.pid,flush=True)
time.sleep(60)
'''
    environment=dict(os.environ)
    environment["PYTHONPATH"]=str(Path(providers.__file__).resolve().parents[1])
    parent=subprocess.Popen([sys.executable,"-c",program],env=environment,
        stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
    child_handle=None
    try:
        # Bound observation so a failing guard/startup cannot hang the suite.
        output=[]
        reader=threading.Thread(target=lambda:output.append(parent.stdout.readline()),daemon=True)
        reader.start();reader.join(5)
        assert not reader.is_alive(),"Test host did not return a worker PID"
        assert output and output[0].strip().isdigit(),"Test host did not start its worker"
        child_handle=kernel.OpenProcess(0x00100000|0x0001,False,int(output[0]))
        assert child_handle,"Could not observe the test-owned worker"
        assert kernel.WaitForSingleObject(child_handle,0)==258,"Worker exited before the parent-death test"
        parent.kill();parent.wait(timeout=5)
        assert kernel.WaitForSingleObject(child_handle,2000)==0,"A model worker survived its host's abrupt exit"
    finally:
        if parent.poll() is None:parent.kill();parent.wait(timeout=5)
        if child_handle:
            if kernel.WaitForSingleObject(child_handle,0)==258:
                kernel.TerminateProcess(child_handle,1);kernel.WaitForSingleObject(child_handle,2000)
            kernel.CloseHandle(child_handle)
        parent.stdout.close();parent.stderr.close()


def test_failed_lifetime_assignment_stops_only_newly_spawned_worker(monkeypatch,tmp_path):
    executable=tmp_path/"server.exe";model=tmp_path/"model.gguf"
    executable.touch();model.touch();worker=LlamaWorker(executable,model)
    class Process:
        stopped=False
        def poll(self):return 0 if self.stopped else None
        def terminate(self):self.stopped=True
        def wait(self,timeout=None):return 0
    process=Process();monkeypatch.setattr(providers.subprocess,"Popen",lambda *args,**kwargs:process)
    def cannot_own(process):raise OSError("assignment denied")
    monkeypatch.setattr(providers,"own_process",cannot_own)
    with pytest.raises(AppError) as error:worker.start(threading.Event())
    assert error.value.code=="MODEL_LIFETIME"
    assert process.stopped and worker.process is None and not worker._lifetimes


def test_lifetime_close_for_old_worker_never_closes_successor():
    worker=LlamaWorker("unused","unused")
    class Process:
        stopped=False
        def poll(self):return 0 if self.stopped else None
        def terminate(self):self.stopped=True
        def wait(self,timeout=None):return 0
    class Lifetime:
        closed=False
        def close(self):self.closed=True
    old,new=Process(),Process();old_life,new_life=Lifetime(),Lifetime()
    worker.process=new;worker._lifetimes={old:old_life,new:new_life}
    worker.stop(expected=old)
    assert old.stopped and old_life.closed
    assert worker.process is new and not new.stopped and not new_life.closed
    assert worker._lifetimes=={new:new_life}
    worker.stop();assert new.stopped and new_life.closed and not worker._lifetimes


def test_openrouter_latency_routing_keeps_privacy_and_no_model_fallback(monkeypatch,tmp_path):
    from manga_live.config import Config
    config=Config(tmp_path/"config")
    config.update({"mode":"byok","provider":"openrouter","cloudConsent":True})
    vault=SimpleNamespace(get=lambda provider:"test-only-not-a-real-key")
    translator=Translator(config,vault,tmp_path/"models",tmp_path/"runtime")
    captured=[]
    def fake_post(url,body,headers):
        captured.append((url,body))
        return {"choices":[{"message":{"content":'{"items":[{"id":"r","vi":"Cảm ơn.","ambiguous":true}]}'},"finish_reason":"stop"}],"usage":{}}
    monkeypatch.setattr(providers,"post_json",fake_post)
    items,_=translator.translate([{"id":"r","ja":"ありがとう。"}],{},threading.Event())
    assert items[0]["vi"]=="Cảm ơn." and len(captured)==1
    url,body=captured[0]
    assert url=="https://openrouter.ai/api/v1/chat/completions"
    assert body["model"]==config.values["openrouterModel"] and "models" not in body
    assert body["provider"]=={"data_collection":"deny","sort":"latency","require_parameters":True}
    assert body["reasoning"]=={"enabled":False}
