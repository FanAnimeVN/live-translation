"""Real length-framed Native Messaging + local OCR/LLM; synthetic images only.

Isolated profile, no private scans or API keys. Reports are generated artifacts.
This checks the host protocol, not the installed browser's native registration.
"""
import argparse
import base64
import json
import os
from pathlib import Path
import queue
import struct
import subprocess
import sys
import tempfile
import shutil
import threading
import time
import uuid

from fixture_server import synthetic_page

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.process_lifetime import own_process
from manga_live.runtime_build import source_build


def verify_runtime(hello):
    if hello.get("runtimeBuild") != source_build():
        raise RuntimeError("Runtime package mismatch: host is old, different or unidentified. "
                           "No inference was started; do not reset reader data or keys.")


class NativeClient:
    def __init__(self,config,launcher=None,standalone_host=None):
        if standalone_host:
            command=[str(standalone_host),"chrome-extension://epcjjhbilmmmbojldhnfblgmgiamajpl/","--config",str(config)]
        else:
            command=[str(launcher),"chrome-extension://epcjjhbilmmmbojldhnfblgmgiamajpl/"] if launcher else [sys.executable,str(ROOT/"companion/entry.py"),"--stdio-test","--config",str(config)]
        environment={k:v for k,v in os.environ.items() if k not in ("PYTHONPATH","PYTHONHOME","PYTHONSTARTUP")} if standalone_host else None
        self.process=subprocess.Popen(command,
            stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=environment,
            cwd=Path(config).parent if standalone_host else ROOT,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=="nt" else 0)
        self.lifetime=own_process(self.process)
        self.replies=queue.Queue();self.profile="qa-native-"+uuid.uuid4().hex
        self.diagnostics=[]
        def stderr_reader():
            for line in iter(self.process.stderr.readline,b""):
                self.diagnostics.append(line.decode("utf-8",errors="replace").rstrip())
                if len(self.diagnostics)>120:self.diagnostics.pop(0)
        threading.Thread(target=stderr_reader,daemon=True).start()
        self.thread=threading.Thread(target=self.reader,daemon=True);self.thread.start()

    def reader(self):
        try:
            while header:=self.process.stdout.read(4):
                size=struct.unpack("<I",header)[0]
                payload=bytearray()
                while len(payload)<size:
                    chunk=self.process.stdout.read(size-len(payload))
                    if not chunk:raise EOFError("Native host closed mid-frame")
                    payload.extend(chunk)
                self.replies.put(json.loads(payload))
        except Exception as error:
            self.replies.put(error)
        finally:self.replies.put(EOFError("Native host closed"))

    def call(self,op,params=None,events=None,event_payloads=None):
        request_id=uuid.uuid4().hex;start=time.perf_counter()
        message={"v":1,"id":request_id,"profile":self.profile,"op":op,"params":params or {}}
        data=json.dumps(message,ensure_ascii=False).encode()
        self.process.stdin.write(struct.pack("<I",len(data))+data);self.process.stdin.flush()
        while True:
            try:reply=self.replies.get(timeout=70)
            except queue.Empty:
                print("\n".join(self.diagnostics[-70:]),file=sys.stderr)
                raise TimeoutError("No native progress for 70 seconds")
            if isinstance(reply,Exception):raise reply
            if reply["id"]!=request_id:raise AssertionError("Native reply ID mismatch")
            if "event" in reply:
                if reply["event"]=="progress":print(json.dumps({"event":reply["event"],"stage":reply.get("result",{}).get("stage")}),flush=True)
                if events is not None:events.append({"event":reply["event"],"at_ms":(time.perf_counter()-start)*1000})
                if event_payloads is not None:event_payloads.append(reply)
                continue
            if not reply.get("ok"):raise RuntimeError(json.dumps(reply.get("error"),ensure_ascii=False))
            return reply["result"]

    def image(self,data,image_id):
        self.call("image.begin",{"imageId":image_id,"bytes":len(data)})
        for offset in range(0,len(data),128000):
            self.call("image.chunk",{"imageId":image_id,"offset":offset,"data":base64.b64encode(data[offset:offset+128000]).decode()})

    def close(self):
        self.process.stdin.close()
        try:self.process.wait(timeout=15)
        except subprocess.TimeoutExpired:
            if self.lifetime:self.lifetime.close();self.lifetime=None
            if self.process.poll() is None:self.process.terminate()
            self.process.wait(timeout=10)
        finally:
            if self.lifetime:self.lifetime.close();self.lifetime=None


def context_transfer_smoke(client):
    """Large private-context protocol check, not model-generated chapter QA."""
    from hashlib import sha256
    pack={"schema":1,"story":{"id":"long-context","title":"Bộ nhớ tự tạo 100 chapter","genre":"fantasy",
          "aliases":json.dumps(["Hồ sơ kiểm thử", "QA story"],ensure_ascii=False),"metadata":"{}"},"facts":[],
          "progress":{"last_chapter":20,"last_page":9,"furthest_chapter":100},
          "summaries":[{"chapter_start":chapter,"chapter_end":chapter,"page_end":page,"kind":"chapter",
            "complete":0,"text":f"Ghi chú kiểm thử chapter {chapter}, trang {page}. "*12,
            "source":json.dumps({"type":"user","note":"x"*1000})}
            for chapter in range(1,101) for page in range(10)]}
    raw=json.dumps(pack,ensure_ascii=False,separators=(",",":")).encode()
    assert len(raw)>1000000
    transfer_id=uuid.uuid4().hex;start=time.perf_counter()
    client.call("context.begin",{"transferId":transfer_id,"bytes":len(raw),"sha256":sha256(raw).hexdigest()})
    for offset in range(0,len(raw),128*1024):
        client.call("context.chunk",{"transferId":transfer_id,"offset":offset,"data":base64.b64encode(raw[offset:offset+128*1024]).decode()})
    assert client.call("context.commit",{"transferId":transfer_id})["storyId"]=="long-context"
    import_ms=(time.perf_counter()-start)*1000
    # A repeat backup import must not grow the history or forget resume metadata.
    repeat=uuid.uuid4().hex
    client.call("context.begin",{"transferId":repeat,"bytes":len(raw),"sha256":sha256(raw).hexdigest()})
    for offset in range(0,len(raw),128*1024):
        client.call("context.chunk",{"transferId":repeat,"offset":offset,"data":base64.b64encode(raw[offset:offset+128*1024]).decode()})
    client.call("context.commit",{"transferId":repeat})
    cursor=None;seen=set();largest=0;chunks=0;snapshot=None
    start=time.perf_counter()
    while True:
        part=client.call("memory.export.page",{"storyId":"long-context","cursor":cursor})
        assert part["progress"]==pack["progress"] and part["story"]["genre"]=="fantasy"
        assert json.loads(part["story"]["aliases"])==json.loads(pack["story"]["aliases"])
        if snapshot is not None:assert part["snapshotId"]==snapshot
        snapshot=part["snapshotId"]
        largest=max(largest,len(json.dumps(part,ensure_ascii=False).encode()));chunks+=1
        assert len(part["summaries"])+len(part["facts"]) or part["next"] is None
        for row in part["summaries"]:
            assert row["id"] not in seen;seen.add(row["id"])
        cursor=part["next"]
        if cursor is None:break
    assert len(seen)==1000 and largest<160000
    export_ms=(time.perf_counter()-start)*1000;cursor=None;cutoff={"chapter":20,"page":9};count=0
    while True:
        part=client.call("memory.export.page",{"storyId":"long-context","cursor":cursor,"at":cutoff})
        assert all(row["chapter_end"]<=20 for row in part["summaries"])
        count+=len(part["summaries"]);cursor=part["next"]
        if cursor is None:break
    assert count==200
    # Verify the new graph-evidence behavior through real framing/import, not
    # only a direct Memory unit test. All content below is authored fixture data.
    group_pack={"schema":1,"story":{"id":"group-evidence","title":"Evidence fixture"},"facts":[],"summaries":[
        {"id":"leaf","chapter_start":1,"chapter_end":1,"page_end":1,"kind":"chapter","complete":1,
         "text":"Unverified leaf paraphrase","source":{"type":"dialogue","utterances":[{"ja":"先に帰ってて。","speaker":"unknown"}]}},
        {"id":"root","chapter_start":1,"chapter_end":2,"page_end":1,"kind":"group","complete":1,
         "text":"Unverified parent paraphrase","source":{"type":"dialogue","summary_ids":["leaf"],
            "utterances":[{"ja":"未来の秘密。","speaker":"invented"}]}}]}
    for story in ("group-evidence","restored-group-evidence"):
        group_pack["story"]["id"]=story
        client.call("memory.import",{"pack":group_pack})
        result=client.call("memory.markdown",{"storyId":story,"at":{"chapter":3,"page":1}})["markdown"]
        assert result.count("先に帰ってて。")==1
        assert "未来の秘密。" not in result and "invented" not in result and "Unverified" not in result
        before=client.call("memory.markdown",{"storyId":story,"at":{"chapter":0,"page":0}})["markdown"]
        assert "先に帰ってて。" not in before
    malformed_pack={"schema":1,"story":{"id":"malformed-context","title":"Private import fixture"},
        "facts":[{"kind":"glossary","key":"broken","value":json.dumps({"type":"canonical-term",
            "entity":"broken","category":"weapon","ja":"雪牙","vi":"Tuyết Nha","aliases":None}),
            "chapter":1,"page":0,"source":{"type":"user"},"confirmed":1,"locked":1}],
        "summaries":[{"chapter_start":1,"chapter_end":1,"page_end":1,"kind":"chapter","complete":0,
            "text":"Unverified malformed evidence","source":{"type":"dialogue","utterances":None}}]}
    client.call("memory.import",{"pack":malformed_pack})
    safe=client.call("memory.markdown",{"storyId":"malformed-context","at":{"chapter":2,"page":1}})["markdown"]
    assert "Unverified malformed evidence" not in safe
    return {"source":"author-created storage fixtures; not 100 chapters summarized by AI",
            "bytes":len(raw),"summaries":len(seen),"chunks":chunks,"largest_reply_bytes":largest,
            "import_ms":import_ms,"export_ms":export_ms,"cutoff_20_summaries":count,
            "repeat_import_idempotent":True,"profile_and_progress_restored":True,
            "group_original_evidence":True,"unverified_group_quotes_excluded":True,
            "malformed_private_context_does_not_crash":True}


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--output",default=str(ROOT/"artifacts/native-smoke.json"))
    parser.add_argument("--launcher",action="store_true",help="Test the actual packaged executable, with isolated temporary config")
    parser.add_argument("--host-executable",help="Test the frozen onedir host directly; keep its _internal DLLs beside it")
    parser.add_argument("--handshake-only",action="store_true")
    parser.add_argument("--verify-runtime",action="store_true",help="Require the actual host to match the current Python package; handshake only")
    parser.add_argument("--warmup",action="store_true")
    parser.add_argument("--summarize",action="store_true",help="Exercise the real Qwen evidence-constrained memory worker")
    parser.add_argument("--context-transfer",action="store_true",help="Exercise large context import/export through real framed host")
    parser.add_argument("--context-only",action="store_true",help="Real framed context checks only, without loading OCR or LLM")
    args=parser.parse_args()
    if args.verify_runtime and not args.handshake_only:
        parser.error("--verify-runtime requires --handshake-only; it must not start inference")
    if args.launcher and args.host_executable:parser.error("Choose launcher OR standalone host")
    standalone_host=Path(args.host_executable).resolve() if args.host_executable else None
    if standalone_host and (not standalone_host.is_file() or not (standalone_host.parent/"bundle.json").is_file()):
        parser.error("Standalone bundle is missing/incomplete")
    assets=standalone_host.parent if standalone_host else ROOT
    with tempfile.TemporaryDirectory(prefix="manga-native-qa-") as temporary:
        installation={"models":str(assets/"models"),"runtime":str(assets/"runtime/llama"),"dataRoot":temporary,
            "python":sys.executable,"entry":str(ROOT/"companion/entry.py"),
            "allowedOrigins":["chrome-extension://epcjjhbilmmmbojldhnfblgmgiamajpl/"] if args.launcher or standalone_host else []}
        if standalone_host:
            installation.pop("python");installation.pop("entry")
        config=Path(temporary)/"native-config.json";config.write_text(json.dumps(installation),encoding="utf-8")
        launcher=None
        if args.launcher:
            launcher=Path(temporary)/"MangaLiveHost.exe";shutil.copy2(ROOT/"dist/windows/MangaLiveHost.exe",launcher)
        client=NativeClient(config,launcher,standalone_host);runs=[]
        try:
            hello=client.call("hello")
            if args.verify_runtime:verify_runtime(hello)
            if args.handshake_only:
                print(json.dumps({"handshake":hello,"packaged_launcher":bool(launcher),"standalone_host":bool(standalone_host),"isolated_profile":True,"runtime_verified":bool(args.verify_runtime)}),flush=True);return
            context_transfer=context_transfer_smoke(client) if args.context_transfer or args.context_only else None
            if args.context_only:
                report={"source":"author-created storage fixtures; real framed "+("frozen" if standalone_host else "Python")+" host; no inference/cloud",
                    "runtime":{"promptVersion":hello.get("promptVersion"),"ocrVersion":hello.get("ocrVersion")},
                    "packaged_launcher":bool(launcher),"context_transfer":context_transfer,
                    "standalone_host":bool(standalone_host),"development_python_or_entry_config":not bool(standalone_host),
                    "limitations":["Not installed-browser E2E or translation-quality proof."]}
                destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
                destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
                print(json.dumps(report,ensure_ascii=True),flush=True);return
            client.call("settings",{"mode":"offline","autoSummary":False})
            client.call("story.ensure",{"storyId":"synthetic","title":"Trang tự tạo","genre":"fantasy"})
            client.call("memory.term",{"storyId":"synthetic","category":"skill","ja":"氷結結界","vi":"Băng Kết Kết Giới","at":{"chapter":1,"page":0}})
            data=synthetic_page()
            readiness=client.call("warmup") if args.warmup else None
            # Same image different page ID measures warm engine, not cache.
            for name,page_id in [("first-after-warmup" if readiness else "cold","page-a"),("warm","page-b"),("cached","page-b")]:
                image_id=uuid.uuid4().hex;revision=uuid.uuid4().hex;events=[];start=time.perf_counter()
                client.image(data,image_id)
                result=client.call("pipeline",{"imageId":image_id,"storyId":"synthetic","title":"Trang tự tạo",
                    "pageId":page_id,"revision":revision,"at":{"chapter":1,"page":0}},events)
                assert result["revision"]==revision and result["regions"],"No usable regions"
                runs.append({"name":name,"framed_total_ms":(time.perf_counter()-start)*1000,"events":events,"result":result})
                print(json.dumps({"name":name,"regions":len(result["regions"]),"cached":result["cached"],"metrics":result["metrics"]}),flush=True)
            assert runs[-1]["result"]["cached"],"Repeated page did not hit cache"
            region=runs[-1]["result"]["regions"][0]
            corrected=client.call("retranslate",{"storyId":"synthetic","pageId":"page-b","revision":revision,
                "at":{"chapter":1,"page":0},"regionId":region["id"],"ja":"ありがとう。"})
            client.call("memory.read",{"storyId":"synthetic","pageId":"page-b","revision":revision})
            progress=client.call("status")["stories"][0]
            assert progress["last_chapter"]==1
            summary_run=None
            if args.summarize:
                start=time.perf_counter()
                client.call("summarize",{"storyId":"synthetic","at":{"chapter":1,"page":0}})
                summary_run={"elapsed_ms":(time.perf_counter()-start)*1000,"memory":client.call("memory.get",{"storyId":"synthetic"})}
                assert len(summary_run["memory"]["summaries"])==1
                assert summary_run["memory"]["summaryStatus"]["done"]==1
                assert summary_run["memory"]["summaries"][0]["complete"]==0
                evidence=json.loads(summary_run["memory"]["summaries"][0]["source"])
                assert evidence["type"]=="dialogue" and evidence["region_ids"]
                before=client.call("memory.markdown",{"storyId":"synthetic","at":{"chapter":1,"page":0}})["markdown"]
                after=client.call("memory.markdown",{"storyId":"synthetic","at":{"chapter":1,"page":1}})["markdown"]
                summary_text=summary_run["memory"]["summaries"][0]["text"]
                assert summary_text not in before and "Original utterances only" in after
            report={"source":"author-created synthetic image; local engines only","runs":runs,"correction":corrected,
                "runtime":{"promptVersion":hello.get("promptVersion"),"ocrVersion":hello.get("ocrVersion")},
                "readiness":readiness,"packaged_launcher":bool(launcher),
                "standalone_host":bool(standalone_host),"development_python_or_entry_config":not bool(standalone_host),
                "summary_run":summary_run,
                "context_transfer":context_transfer,
                "checks":{"framing":True,"real_ocr_and_llm":True,"cache":True,"edit_then_read":True},
                "limitations":["Not installed-browser E2E proof.","Three runs cannot estimate a reliable p95.","Synthetic page is not a representative manga quality corpus."]}
            destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            print("Native synthetic end-to-end smoke passed",flush=True)
        finally:client.close()


if __name__=="__main__":main()
