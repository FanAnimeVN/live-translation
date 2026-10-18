import io
import json
import threading
import urllib.request

import pytest

from manga_live.config import Config
from manga_live.errors import AppError
from manga_live.providers import Translator
from manga_live.host import Host


class TestVault:
    __test__ = False

    def get(self, provider):
        assert provider == "openrouter"
        return "authored-test-credential"

    def status(self):
        return {"openrouter":True}


def test_summary_consent_is_bound_to_model_and_provider(tmp_path):
    config=Config(tmp_path)
    config.update({"mode":"byok","provider":"openrouter","cloudConsent":True,
                   "summaryBackend":"cloud","summaryCloudConsent":True})
    config.update({"summaryModel":"anthropic/claude-haiku-5.5"})
    assert config.values["summaryCloudConsent"] is False
    config.update({"summaryCloudConsent":True})
    config.update({"provider":"gemini","summaryBackend":"local"})
    assert config.values["summaryCloudConsent"] is False
    config.update({"mode":"offline"})
    assert Config(tmp_path).values["summaryBackend"]=="local"


def test_disabling_cloud_cannot_silently_arm_local_summary_backlog(tmp_path):
    config=Config(tmp_path)
    config.update({"mode":"byok","cloudConsent":True,"autoSummary":True,
                   "summaryBackend":"cloud","summaryCloudConsent":True})
    config.update({"mode":"offline"})
    assert config.values["summaryBackend"]=="local" and config.values["autoSummary"] is False


def test_explicit_cloud_summary_uses_separate_model_and_only_dialogue(tmp_path, monkeypatch):
    config = Config(tmp_path / "settings")
    config.update({"mode": "byok", "provider": "openrouter", "cloudConsent": True,
                   "openrouterModel": "anthropic/claude-haiku-5.5", "summaryBackend": "cloud",
                   "summaryModel": "deepseek/deepseek-v4.1-flash", "summaryCloudConsent": True})
    requests = []

    class Transport:
        def open(self, request, timeout):
            requests.append(json.loads(request.data))
            return io.BytesIO(json.dumps({"id":"gen-authored-summary-test","choices": [{"finish_reason": "stop", "message": {
                "content": json.dumps({"summary": "Có lời nhờ sensei đến.", "facts": [
                    {"text": "Có lời nhờ sensei đến, chưa biết sensei đã đến chưa.", "evidence_ids": ["r1"]}]})}}],
                "usage": {"cost": .0001}}).encode())

    monkeypatch.setattr(urllib.request, "build_opener", lambda *args: Transport())
    translator = Translator(config, TestVault(), tmp_path / "models", tmp_path / "runtime")
    result = translator.summarize({"regions": json.dumps([{
        "id": "r1", "ja": "先生、来てください。", "vi": "Sensei, đến đây giúp em.",
        "speaker": "unknown", "listener": "unknown", "dataUrl": "NEVER_SEND_IMAGE",
        "future_wiki": "NEVER_SEND_WIKI"}])}, threading.Event())
    assert result["facts"][0]["evidence_ids"] == ["r1"]
    assert len(requests) == 1
    assert requests[0]["model"] == "deepseek/deepseek-v4.1-flash"
    prompt = requests[0]["messages"][0]["content"]
    assert "先生、来てください。" in prompt and '"speaker":"unknown"' in prompt
    assert "NEVER_SEND" not in prompt
    assert "REQUEST is not an action already performed" in prompt
    assert requests[0]["max_tokens"] <= 1000
    assert translator.summary_worker.process is None and translator.local.process is None
    receipts=translator.summary_usage()
    assert receipts[0]["state"]=="received" and receipts[0]["costUsd"]==.0001
    assert receipts[0]["providerId"]=="gen-authored-summary-test"
    assert "先生" not in json.dumps(receipts,ensure_ascii=False)
    assert "authored-test-credential" not in json.dumps(receipts)
    assert Translator(config,TestVault(),tmp_path/"models",tmp_path/"runtime").summary_usage()==receipts


@pytest.mark.parametrize("provider_error",[False,True])
def test_cloud_auto_summary_does_not_charge_saved_backlog_and_only_runs_new_read(tmp_path,monkeypatch,provider_error):
    monkeypatch.setattr("manga_live.host.Secrets",lambda profile:TestVault())
    requests=[];received=threading.Event();extra=threading.Event()
    class Transport:
        def open(self,request,timeout):
            requests.append(json.loads(request.data));received.set()
            if len(requests)>1:extra.set()
            if provider_error:raise urllib.error.URLError("authored provider failure")
            return io.BytesIO(json.dumps({"choices":[{"finish_reason":"stop","message":{
                "content":json.dumps({"summary":"Có lời chào.","facts":[]})}}]}).encode())
    monkeypatch.setattr(urllib.request,"build_opener",lambda *args:Transport())
    host=Host({"models":str(tmp_path/"models"),"runtime":str(tmp_path/"runtime"),
               "dataRoot":str(tmp_path/"data")},io.BytesIO(),start_worker=False)
    host.initialize("summary-qa")
    host.memory.ensure_story("story","Authored test")
    for page in (1,2):
        host.memory.save_page("story",f"p{page}",{"chapter":1,"page":page},"rev",
                              [{"id":"r1","ja":"さようなら。" if page==1 else "こんにちは。","vi":"Xin chào."}])
    def send(op,params):
        host.receive({"v":1,"profile":"summary-qa","id":"call-"+op,"op":op,"params":params})
    send("memory.read",{"storyId":"story","pageId":"p1","revision":"rev"})
    send("settings",{"mode":"byok","provider":"openrouter","cloudConsent":True,"autoSummary":True,
                     "summaryBackend":"cloud","summaryCloudConsent":True})
    # External monotonic clock keeps the real idle loop eligible without sleeps.
    monkeypatch.setattr("manga_live.host.time.monotonic",lambda:1000)
    host.last_interaction=0
    host.worker.start()
    try:
        assert not received.wait(1.25),"Saving settings must not send an old pending page"
        send("memory.read",{"storyId":"story","pageId":"p2","revision":"rev"})
        assert received.wait(2.5)
        assert not extra.wait(1.25),"Idle loop must not retry a failed/uncertain paid attempt"
        assert host.memory.summary_status("story")["failed" if provider_error else "done"]==1
    finally:host.close()
    assert len(requests)==1
    assert "こんにちは。" in requests[0]["messages"][0]["content"]
    assert "さようなら。" not in requests[0]["messages"][0]["content"]


@pytest.mark.parametrize("patch",[{"threads":2},{"mode":"offline"}])
def test_settings_cancel_pending_summary_before_configuration_changes(tmp_path,patch):
    host=Host({},io.BytesIO(),start_worker=False)
    host.profile="qa";host.config=Config(tmp_path)
    host.receive({"v":1,"profile":"qa","id":"setting","op":"settings","params":patch})
    assert host.summary_cancel.is_set()
    host.close()


def test_idle_selection_rechecks_settings_after_a_concurrent_offline_change(tmp_path,monkeypatch):
    monkeypatch.setattr("manga_live.host.Secrets",lambda profile:TestVault())
    reached=threading.Event();release=threading.Event();drained=threading.Event()
    class Output(io.BytesIO):
        def write(self,data):
            reply=json.loads(data[4:])
            if reply["id"]=="queued-summary":drained.set()
            return super().write(data)
    host=Host({"models":str(tmp_path/"models"),"runtime":str(tmp_path/"runtime"),"dataRoot":str(tmp_path/"data")},
              Output(),start_worker=False)
    host.initialize("race-qa");host.memory.ensure_story("story","Authored")
    host.memory.save_page("story","p",{"chapter":1,"page":1},"rev",[{"id":"r1","ja":"はい"}])
    host.memory.mark_read("story","p","rev")
    host.config.update({"mode":"byok","cloudConsent":True,"autoSummary":True,
                        "summaryBackend":"cloud","summaryCloudConsent":True})
    def clock():
        if threading.current_thread() is host.worker and not reached.is_set():
            reached.set();release.wait(3)
        return 1000 if threading.current_thread() is host.worker else 0
    monkeypatch.setattr("manga_live.host.time.monotonic",clock);host.last_interaction=0
    host.worker.start()
    try:
        assert reached.wait(2)
        host.receive({"v":1,"id":"offline","op":"settings","profile":"race-qa","params":{"mode":"offline"}})
        host.receive({"v":1,"id":"queued-summary","op":"summarize","profile":"race-qa",
                      "params":{"storyId":"story","at":{"chapter":1,"page":1}}})
        host.receive({"v":1,"id":"cancel","op":"cancel","profile":"race-qa","params":{"id":"queued-summary"}})
        release.set();assert drained.wait(3)
        assert host.memory.summary_status("story")["pending"]==1,"Disabling cloud must not consume a local backlog job"
    finally:release.set();host.close()


def test_cloud_event_memory_retains_only_cited_original_evidence(tmp_path,monkeypatch):
    from manga_live.memory import Memory
    config=Config(tmp_path/"settings")
    config.update({"mode":"byok","cloudConsent":True,"summaryBackend":"cloud","summaryCloudConsent":True})
    class Transport:
        def open(self,request,timeout):
            return io.BytesIO(json.dumps({"choices":[{"finish_reason":"stop","message":{"content":json.dumps({
                "summary":"Có lời nhờ sensei đến.","facts":[{"text":"Có lời nhờ sensei đến.","evidence_ids":["r1"]}]})}}]}).encode())
    monkeypatch.setattr(urllib.request,"build_opener",lambda *args:Transport())
    memory=Memory(tmp_path/"memory.db")
    try:
        memory.ensure_story("story","Authored")
        memory.save_page("story","p",{"chapter":1,"page":1},"rev",[
            {"id":"r1","ja":"先生、来てください。","vi":"Sensei, đến đây giúp em."},
            {"id":"r2","ja":"ああ。","vi":"Ờ."}])
        memory.mark_read("story","p","rev");job=memory.next_job()
        translator=Translator(config,TestVault(),tmp_path/"models",tmp_path/"runtime")
        memory.finish_job(job,translator.summarize(job,threading.Event()))
        exported=memory.export("story")
        durable=json.dumps([exported["facts"],exported["summaries"]],ensure_ascii=False)
        assert "先生、来てください。" in durable
        assert "ああ。" not in durable and "Sensei, đến đây giúp em." not in durable
        context=json.dumps(memory.context("story",{"chapter":1,"page":2})["data"],ensure_ascii=False)
        assert "先生、来てください。" in context
        assert "Có lời nhờ sensei đến." not in context
    finally:memory.close()


def test_cloud_summary_cancellation_releases_foreground_without_retrying_transport(tmp_path,monkeypatch):
    config=Config(tmp_path/"settings")
    config.update({"mode":"byok","cloudConsent":True,"summaryBackend":"cloud","summaryCloudConsent":True})
    entered=threading.Event();release=threading.Event();cancel=threading.Event();failures=[];requests=[]
    class Transport:
        def open(self,request,timeout):
            requests.append(request);entered.set();release.wait(3)
            return io.BytesIO(json.dumps({"choices":[{"finish_reason":"stop","message":{
                "content":'{"summary":"Có lời chào.","facts":[]}'}}],"usage":{"cost":.0001}}).encode())
    monkeypatch.setattr(urllib.request,"build_opener",lambda *args:Transport())
    translator=Translator(config,TestVault(),tmp_path/"models",tmp_path/"runtime")
    job={"regions":json.dumps([{"id":"r1","ja":"こんにちは。"}])}
    def run():
        try:translator.summarize(job,cancel)
        except AppError as error:failures.append(error.code)
    thread=threading.Thread(target=run);thread.start()
    try:
        assert entered.wait(1)
        cancel.set();thread.join(.5)
        assert not thread.is_alive(),"Foreground translation must not wait for the summary HTTP timeout"
        assert failures==["CANCELED"]
        with pytest.raises(AppError) as error:translator.summarize(job,threading.Event())
        assert error.value.code=="SUMMARY_BUSY" and len(requests)==1
    finally:
        release.set();thread.join(3)


@pytest.mark.parametrize("patch,code",[({"mode":"offline"},"OFFLINE"),({"cloudConsent":False},"SUMMARY_CONSENT"),
    ({"summaryCloudConsent":False},"SUMMARY_CONSENT"),({"summaryModel":"unreviewed/model"},"SUMMARY_MODEL")])
def test_cloud_summary_requires_current_route_and_consent_before_any_request(tmp_path,monkeypatch,patch,code):
    # Persisted settings from an old/malformed host cannot bypass provider gates.
    values={"mode":"byok","provider":"openrouter","cloudConsent":True,"summaryBackend":"cloud",
            "summaryCloudConsent":True,**patch}
    (tmp_path/"settings.json").write_text(json.dumps(values),encoding="utf-8")
    config=Config(tmp_path)
    monkeypatch.setattr(urllib.request,"build_opener",lambda *args:pytest.fail("No network allowed"))
    translator=Translator(config,TestVault(),tmp_path/"models",tmp_path/"runtime")
    with pytest.raises(AppError) as error:
        translator.summarize({"regions":'[{"id":"r1","ja":"はい"}]'},threading.Event())
    assert error.value.code==code and translator.summary_usage()==[]


@pytest.mark.parametrize("content",[
    '{"summary":"okay","facts":[{"text":"x","evidence_ids":["missing"]}]}',
    '{"summary":"okay","facts":[{"text":"x","evidence_ids":["r1","r1"]}]}',
    '{"summary":"okay","facts":[],"terms":[]}',
    json.dumps({"summary":"x"*601,"facts":[]})])
def test_invalid_cloud_summary_is_not_repaired_with_another_paid_request(tmp_path,monkeypatch,content):
    config=Config(tmp_path)
    config.update({"mode":"byok","cloudConsent":True,"summaryBackend":"cloud","summaryCloudConsent":True})
    requests=[]
    class Transport:
        def open(self,request,timeout):
            requests.append(request)
            return io.BytesIO(json.dumps({"choices":[{"finish_reason":"stop","message":{"content":content}}]}).encode())
    monkeypatch.setattr(urllib.request,"build_opener",lambda *args:Transport())
    translator=Translator(config,TestVault(),tmp_path/"models",tmp_path/"runtime")
    with pytest.raises(AppError):translator.summarize({"regions":'[{"id":"r1","ja":"はい"}]'},threading.Event())
    assert len(requests)==1 and translator.summary_usage()[0]["costUsd"] is None


def test_unreadable_optional_usage_ledger_does_not_disconnect_companion(tmp_path,monkeypatch):
    monkeypatch.setattr("manga_live.host.Secrets",lambda profile:TestVault())
    host=Host({"models":str(tmp_path/"models"),"runtime":str(tmp_path/"runtime"),"dataRoot":str(tmp_path/"data")},
              io.BytesIO(),start_worker=False)
    host.initialize("receipt-qa")
    try:
        (host.config.root/"summary-usage.sqlite3").write_bytes(b"authored invalid database")
        status=host.status()
        assert status["summaryUsageUnavailable"] is True and status["summaryUsage"]==[]
        assert status["settings"]["mode"]=="offline"
    finally:host.close()
