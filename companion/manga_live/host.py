"""Length-framed persistent Native Messaging host. No public listening socket."""
import argparse
import base64
import hashlib
import json
import os
from pathlib import Path
import queue
import re
import struct
import sys
import threading
import time
from .config import Config, Secrets, data_root
from .errors import AppError, require
from .memory import Memory, encode, SPEAKER_BINDING_VERSION
from .metadata import Metadata
from .pipeline import Pipeline
from .providers import Translator
from .validation import identifier, location, text, number, MAX_CONTEXT_PACK_BYTES
from .linguistics import voice_record, style_record, name_record
from .prompts import PROMPT_VERSION
from .ocr import LAYOUT_VERSION
from .text_scope import SCOPE_VERSION
from .cloud_models import model_choices,CATALOG_VERSION
from .native_input import native_input
from .runtime_build import runtime_build
from .translation_schedule import SCHEDULE_VERSION

MAX_MESSAGE = 768 * 1024
# Capture once for this process. Re-reading current disk files on every status
# could mislabel an old persistent host after a developer edits the package.
RUNTIME_BUILD = runtime_build()


def read_exact(stream,size):
    output = bytearray()
    while len(output)<size:
        part = stream.read(size-len(output))
        if not part:
            if not output:
                return None
            raise AppError("FRAME","Truncated native frame")
        output.extend(part)
    return bytes(output)


def read_frame(stream):
    header = read_exact(stream,4)
    if header is None:
        return None
    size = struct.unpack("<I",header)[0]
    require(0<size<=MAX_MESSAGE,"FRAME","Native message too large")
    payload = read_exact(stream,size)
    require(payload is not None,"FRAME")
    return json.loads(payload)


class Host:
    def __init__(self,installation,output,start_worker=True):
        self.installation,self.output = installation,output
        self.write_lock = threading.Lock()
        self.profile = None
        self.memory = None
        self.images = {}
        self.context_imports = {}
        self.cancels = {}
        self.work = queue.Queue(maxsize=8)
        self.closing = threading.Event()
        self.summary_cancel = threading.Event()
        self.summary_lock = threading.RLock()
        # Session-only, exact read acknowledgements. Never persisted or
        # reconstructed from backlog when opening/saving settings.
        self.cloud_summary_jobs = {}
        self.last_interaction = time.monotonic()
        self.worker = threading.Thread(target=self.loop,daemon=True)
        if start_worker:self.worker.start()

    def send(self,request_id,result=None,error=None,event=None):
        reply = {"v":1,"id":request_id}
        if event:
            reply.update(event=event,result=result)
        elif error:
            reply.update(ok=False,error={"code":error.code,"message":error.message})
        else:
            reply.update(ok=True,result=result)
        data = encode(reply).encode()
        require(len(data)<1000000,"FRAME")
        with self.write_lock:
            self.output.write(struct.pack("<I",len(data))+data)
            self.output.flush()

    def initialize(self,profile):
        identifier(profile)
        require(self.profile in (None,profile),"PROFILE")
        if self.profile:
            return
        self.profile = profile
        root = Path(self.installation.get("dataRoot",str(data_root())))/"profiles"/hashlib.sha256(profile.encode()).hexdigest()[:24]
        self.config = Config(root)
        self.memory = Memory(root/"memory.sqlite3")
        self.vault = Secrets(profile)
        self.models = Path(self.installation["models"])
        self.translator = Translator(self.config,self.vault,self.models,self.installation["runtime"])
        self.pipeline = Pipeline(self.memory,self.translator,self.config,self.models)
        self.metadata = Metadata(self.config)

    def status(self):
        manifest_path=self.models.parent/"models.lock.json"
        manifest=json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
        ready={}
        for key in ("ocr","detector","translation","translation-lite","summarizer"):
            files=manifest.get(key,{}).get("files",{})
            ready[key]=bool(files) and all((self.models/key/name).is_file() and (self.models/key/name).stat().st_size==spec["bytes"] for name,spec in files.items())
        usage_unavailable=False
        try:summary_usage=self.translator.summary_usage()
        except AppError:
            # Optional accounting diagnostics must not make a healthy native
            # connection/library look disconnected or erase a reader profile.
            summary_usage=[];usage_unavailable=True
        return {"version":"0.1.0","runtimeBuild":RUNTIME_BUILD,"promptVersion":PROMPT_VERSION,"ocrVersion":self.pipeline.engine.name,"layoutVersion":LAYOUT_VERSION,"scopeVersion":SCOPE_VERSION,
                "presentationVersion":getattr(self.pipeline.detectors[self.config.values["detector"]],"presentation_version",LAYOUT_VERSION),
                "scheduleVersion":SCHEDULE_VERSION,
                "summaryVersion":"read-evidence-cloud-v1",
                "summaryUsage":summary_usage,"summaryUsageUnavailable":usage_unavailable,
                "speakerBindingVersion":SPEAKER_BINDING_VERSION,
                "settings":self.config.values,"keys":self.vault.status(),
                "cloudModels":model_choices(),"cloudCatalogVersion":CATALOG_VERSION,
                "models":ready,
                "engineWarm":bool(self.pipeline.engine.model is not None and
                    (self.config.values["detector"]=="opencv" or self.pipeline.detectors["paddle"].model is not None) and
                    (self.config.values["mode"]!="offline" or (self.translator.local.process and self.translator.local.process.poll() is None))),
                "stories":self.memory.list_stories()}

    def receive(self,message):
        request_id = "invalid"
        try:
            require(isinstance(message,dict) and message.get("v")==1)
            request_id = identifier(message.get("id"))
            op = text(message.get("op"),60)
            params = message.get("params",{})
            require(isinstance(params,dict))
            if op == "hello":
                with self.summary_lock:self.initialize(message.get("profile"))
                self.send(request_id,self.status())
                return
            require(self.profile and message.get("profile")==self.profile,"PROFILE")
            if op=="context.begin":
                now=time.monotonic()
                self.context_imports={k:v for k,v in self.context_imports.items() if now-v["created"]<120}
                transfer_id=identifier(params.get("transferId"));size=params.get("bytes");sha=params.get("sha256")
                require(type(size) is int and 0<size<=MAX_CONTEXT_PACK_BYTES,"CONTEXT_SIZE")
                require(isinstance(sha,str) and re.fullmatch(r"[a-f0-9]{64}",sha),"CONTEXT_HASH")
                require(transfer_id not in self.context_imports and
                        sum(v["size"] for v in self.context_imports.values())+size<=MAX_CONTEXT_PACK_BYTES,"CONTEXT_SIZE")
                self.context_imports[transfer_id]={"size":size,"sha256":sha,"data":bytearray(),"created":now}
                self.send(request_id,{"ready":True});return
            if op=="context.chunk":
                transfer_id=identifier(params.get("transferId"));item=self.context_imports.get(transfer_id)
                if item and time.monotonic()-item["created"]>=120:
                    self.context_imports.pop(transfer_id,None);item=None
                require(item is not None,"CONTEXT_TRANSFER")
                require(type(params.get("offset")) is int and params["offset"]==len(item["data"]),"CONTEXT_OFFSET")
                decoded=base64.b64decode(text(params.get("data"),180000),validate=True)
                require(0<len(decoded)<=128*1024 and len(item["data"])+len(decoded)<=item["size"],"CONTEXT_SIZE")
                item["data"].extend(decoded);self.send(request_id,{});return
            if op=="context.cancel":
                self.context_imports.pop(identifier(params.get("transferId")),None)
                self.send(request_id,{});return
            if op=="context.commit":
                item=self.context_imports.pop(identifier(params.get("transferId")),None)
                require(item is not None and time.monotonic()-item["created"]<120,"CONTEXT_TRANSFER")
                require(len(item["data"])==item["size"],"CONTEXT_SIZE")
                require(hashlib.sha256(item["data"]).hexdigest()==item["sha256"],"CONTEXT_HASH")
                pack=json.loads(item["data"].decode("utf-8"))
                result={"storyId":self.memory.import_pack(pack)}
                self.send(request_id,result);return
            if op == "cancel":
                target = identifier(params.get("id"))
                if target in self.cancels:
                    self.cancels[target].set()
                self.images.pop(params.get("imageId"),None)
                self.send(request_id,{"canceled":True})
                return
            if op == "image.begin":
                now = time.monotonic()
                self.images = {k:v for k,v in self.images.items() if now-v["created"]<60}
                image_id = identifier(params.get("imageId"))
                total = int(number(params.get("bytes"),1,8*1024*1024))
                require(image_id not in self.images and sum(v["size"] for v in self.images.values())+total<=16*1024*1024,"IMAGE_SIZE")
                self.images[image_id] = {"size":total,"data":bytearray(),"created":now}
                self.send(request_id,{})
                return
            if op == "image.chunk":
                image = self.images.get(identifier(params.get("imageId")))
                require(image is not None,"IMAGE")
                chunk = text(params.get("data"),400000)
                require(params.get("offset")==len(image["data"]))
                decoded = base64.b64decode(chunk,validate=True)
                require(len(image["data"])+len(decoded)<=image["size"],"IMAGE_SIZE")
                image["data"].extend(decoded)
                self.send(request_id,{})
                return
            if op in ("pipeline","retranslate","summarize","warmup"):
                if op=="summarize":
                    if "storyId" in params:identifier(params["storyId"])
                    if "at" in params:location(params["at"])
                require(request_id not in self.cancels,"DUPLICATE")
                with self.summary_lock:
                    self.last_interaction = time.monotonic()
                    self.summary_cancel.set()
                if self.memory and self.translator.summary_worker.process:
                    self.translator.summary_worker.stop()
                data = None
                if op == "pipeline":
                    entry = self.images.pop(identifier(params.get("imageId")),None)
                    require(entry and len(entry["data"])==entry["size"],"IMAGE")
                    data = bytes(entry["data"])
                cancel = threading.Event()
                self.cancels[request_id] = cancel
                try:
                    self.work.put_nowait((request_id,op,params,data,cancel))
                except queue.Full:
                    self.cancels.pop(request_id,None)
                    raise AppError("BUSY","Hàng đợi đầy. Chờ trang đang xử lý.")
                return
            if op == "status":
                result = self.status()
            elif op == "settings":
                with self.summary_lock:
                    result = self.config.update(params)
                    self.summary_cancel.set()
                    self.cloud_summary_jobs.clear()
                    # Inference owns its original settings snapshot.
                    for running in self.cancels.values(): running.set()
            elif op == "key.set":
                with self.summary_lock:
                    self.summary_cancel.set();self.cloud_summary_jobs.clear()
                    self.vault.set(params.get("provider"),params.get("key"))
                result = {"saved":True}
            elif op == "key.delete":
                with self.summary_lock:
                    self.summary_cancel.set();self.cloud_summary_jobs.clear()
                    self.vault.delete(params.get("provider"))
                result = {"deleted":True}
            elif op == "story.ensure":
                self.memory.ensure_story(identifier(params.get("storyId")),text(params.get("title"),300),params.get("genre"))
                result = {"version":self.memory.version(params["storyId"])}
            elif op == "memory.get":
                story=identifier(params.get("storyId"))
                result = {**self.memory.export(story),"summaryStatus":{
                    **self.memory.summary_status(story),"enabled":self.config.values["autoSummary"]}}
            elif op=="memory.export.page":
                story=identifier(params.get("storyId"))
                result={**self.memory.export_page(story,params.get("cursor"),params.get("at")),
                        "summaryStatus":{**self.memory.summary_status(story),"enabled":self.config.values["autoSummary"]}}
            elif op == "memory.retry":
                result = {"retried":self.memory.retry_jobs(identifier(params.get("storyId")))}
            elif op == "memory.fact":
                self.memory.ensure_story(identifier(params.get("storyId")),text(params.get("title"),300))
                result = {"id":self.memory.fact(params["storyId"],params.get("kind"),params.get("key"),params.get("value"),
                    params.get("at"),{"type":"user"},True,True)}
            elif op=="memory.voice":
                rule=voice_record(params.get("speaker"),params.get("listener"),params.get("self"),params.get("address"),params.get("register","natural"))
                result={"id":self.memory.fact(identifier(params.get("storyId")),"relationship",rule["speaker"]+"→"+rule["listener"],encode(rule),params.get("at"),{"type":"user"},True,True)}
            elif op=="memory.style":
                key,value=style_record(params.get("key","naming"),params.get("style"))
                result={"id":self.memory.fact(identifier(params.get("storyId")),"style",key,value,params.get("at"),{"type":"user"},True,True)}
            elif op=="memory.name":
                record=name_record(params.get("character"),params.get("forms"))
                result={"id":self.memory.fact(identifier(params.get("storyId")),"character",record["character"],encode(record),params.get("at"),{"type":"user"},True,True)}
            elif op=="memory.term":
                result={"id":self.memory.canonical_term(identifier(params.get("storyId")),params.get("entity"),
                    params.get("category"),params.get("ja"),params.get("vi"),params.get("aliases",[]),location(params.get("at")))}
            elif op == "memory.recap":
                self.memory.ensure_story(identifier(params.get("storyId")),text(params.get("title"),300))
                at = location(params.get("at"))
                result = {"id":self.memory.summary(params["storyId"],0,at["chapter"],at["page"],text(params.get("value"),6000),{"type":"user"},kind="recap")}
            elif op == "memory.delete":
                self.memory.delete_story(identifier(params.get("storyId")))
                result = {}
            elif op == "memory.import":
                result = {"storyId":self.memory.import_pack(params.get("pack"))}
            elif op == "memory.markdown":
                result = {"markdown":self.memory.markdown(identifier(params.get("storyId")),location(params.get("at")))[0]}
            elif op == "metadata.search":
                result = self.metadata.search(params.get("title"))
            elif op == "metadata.confirm":
                self.memory.confirm_metadata(identifier(params.get("storyId")),params.get("metadata"))
                result = {}
            elif op == "memory.read":
                story=identifier(params.get("storyId"))
                with self.summary_lock:
                    job_id=self.memory.mark_read(story,identifier(params.get("pageId")),identifier(params.get("revision")))
                    cfg=self.config.values
                    if (cfg.get("summaryBackend")=="cloud" and cfg["autoSummary"] and cfg["mode"]=="byok"
                            and cfg["provider"]=="openrouter" and cfg["cloudConsent"] and cfg.get("summaryCloudConsent")):
                        self.cloud_summary_jobs[job_id]=True
                        while len(self.cloud_summary_jobs)>64:self.cloud_summary_jobs.pop(next(iter(self.cloud_summary_jobs)))
                result = {"summary":{"enabled":self.config.values["autoSummary"],**self.memory.summary_status(story)}}
            elif op == "speaker.set":
                self.memory.set_speaker(params.get("storyId"),params.get("pageId"),params.get("regionId"),
                    params.get("speaker"),params.get("listener"),params.get("at"),identifier(params.get("revision")))
                result = {}
            elif op=="term.confirm":
                result=self.memory.confirm_term(identifier(params.get("storyId")),identifier(params.get("pageId")),
                    identifier(params.get("revision")),identifier(params.get("entity")),location(params.get("at")),params.get("vi"))
            else:
                raise AppError("OPERATION","Tác vụ không được hỗ trợ.")
            self.send(request_id,result)
        except AppError as exc:
            self.send(request_id,error=exc)
        except Exception:
            self.send(request_id,error=AppError("INVALID","Yêu cầu không hợp lệ hoặc kho dữ liệu đang bận."))

    def loop(self):
        while not self.closing.is_set():
            try:
                request_id,op,params,data,cancel = self.work.get(timeout=1)
            except queue.Empty:
                now=time.monotonic()
                with self.summary_lock:
                    job=None
                    # Recheck settings AFTER acquiring the same lock used by
                    # settings/key/foreground actions. An earlier idle test
                    # must not authorize work after a concurrent opt-out.
                    if self.memory and self.config.values["autoSummary"] and now-self.last_interaction>15:
                        cloud=self.config.values.get("summaryBackend")=="cloud"
                        job = self.memory.next_job(job_ids=list(self.cloud_summary_jobs)) if cloud else self.memory.next_job()
                        if job:
                            # Consume authorization BEFORE I/O. A failed or
                            # cancelled paid attempt must not retry on idle.
                            self.cloud_summary_jobs.pop(job["id"],None)
                            self.summary_cancel = threading.Event()
                            summary_cancel=self.summary_cancel
                if job:
                    try:
                        raw = self.translator.summarize(job,summary_cancel)
                        with self.summary_lock:
                            require(not summary_cancel.is_set(),"CANCELED")
                            self.memory.finish_job(job,raw)
                    except Exception:
                        # Avoid an endless retry loop; explicit retry is available.
                        if not summary_cancel.is_set():
                            self.memory.fail_job(job)
                    finally:
                        self.translator.summary_worker.stop()
                continue
            try:
                require(not cancel.is_set(),"CANCELED")
                if op == "pipeline":
                    result = self.pipeline.process(params,data,cancel,lambda event,value:self.send(request_id,value,event=event))
                elif op == "retranslate":
                    result = self.pipeline.retranslate(params,cancel)
                elif op=="warmup":
                    result=self.pipeline.warmup(cancel)
                else:
                    with self.summary_lock:
                        job = self.memory.next_job(params.get("storyId"),params.get("at"))
                        require(job is not None,"NO_JOB","Chưa có trang đã đọc để tóm tắt.")
                        self.cloud_summary_jobs.pop(job["id"],None)
                        self.summary_cancel=cancel
                    try:
                        raw = self.translator.summarize(job,cancel)
                        with self.summary_lock:
                            require(not cancel.is_set(),"CANCELED")
                            self.memory.finish_job(job,raw)
                    except Exception:
                        if not cancel.is_set():self.memory.fail_job(job)
                        raise
                    finally:self.translator.summary_worker.stop()
                    result = {"summarized":True}
                self.send(request_id,result)
            except AppError as exc:
                self.send(request_id,error=exc)
            except Exception:
                self.send(request_id,error=AppError("ENGINE","Engine gặp lỗi. Kiểm tra model và chọn vùng nhỏ hơn."))
            finally:
                self.cancels.pop(request_id,None)
                self.work.task_done()

    def close(self):
        self.closing.set()
        self.images.clear();self.context_imports.clear()
        with self.summary_lock:
            self.summary_cancel.set()
            self.cloud_summary_jobs.clear()
        for cancel in tuple(self.cancels.values()):
            cancel.set()
        if self.memory:
            self.translator.stop()
        if self.worker.is_alive():self.worker.join(timeout=5)
        if self.memory and not self.worker.is_alive():
            self.memory.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("origin",nargs="?")
    parser.add_argument("--config")
    parser.add_argument("--stdio-test",action="store_true")
    parser.add_argument("--runtime-probe",choices=("detector",))
    args, _ = parser.parse_known_args()
    base = Path(sys.executable).parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parents[2]
    path = Path(args.config) if args.config else base/"native-config.json"
    installation = json.loads(path.read_text(encoding="utf-8"))
    if args.runtime_probe:
        # Never enable raw exception diagnostics on native browser requests or
        # initialize a reader profile. This CLI probe uses only a fixed image.
        require(args.origin is None,"ORIGIN","Runtime probe is CLI-only.")
        from .runtime_diagnostics import detector_probe
        raise SystemExit(detector_probe(installation["models"]))
    if args.stdio_test:
        import faulthandler
        faulthandler.dump_traceback_later(45,repeat=True,file=sys.stderr)
    if not args.stdio_test:
        require(args.origin in installation.get("allowedOrigins",[]),"ORIGIN")
    output = sys.stdout.buffer
    sys.stdout = sys.stderr
    if os.name == "nt":
        import msvcrt
        msvcrt.setmode(sys.stdin.fileno(),os.O_BINARY)
        msvcrt.setmode(output.fileno(),os.O_BINARY)
        # NumPy's first DLL import on this Windows runtime can wait for the
        # blocked native stdin descriptor. Prime before read_frame starts;
        # otherwise importing it lazily in the inference worker deadlocks.
        # Reproduction: scripts/runtime_probe.py --case worker / --case primed.
        import numpy
    # ML/DLL initialization belongs to the main thread on Windows. The
    # persistent browser pipe is read separately, so a blocked transport
    # cannot also be the thread required for native-library initialization.
    # Receive still validates/queues every inference job; no parallel LLMs.
    host = Host(installation,output,start_worker=False)
    source = native_input(sys.stdin.buffer)
    def receive_frames():
        try:
            while not host.closing.is_set():
                message=read_frame(source)
                if message is None:break
                host.receive(message)
        finally:
            host.closing.set();host.summary_cancel.set()
            for cancel in tuple(host.cancels.values()):cancel.set()
    reader=threading.Thread(target=receive_frames,daemon=True)
    reader.start()
    try:
        host.loop()
    finally:
        host.close()
        if args.stdio_test:faulthandler.cancel_dump_traceback_later()


if __name__ == "__main__":
    main()
