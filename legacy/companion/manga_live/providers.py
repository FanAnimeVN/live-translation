import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time
import urllib.error
import urllib.request
from .errors import AppError, require, INCOMPLETE_GENERATION
from .prompts import (translation_prompt, translation_schema, compact_prompt, compact_schema,
                      summary_schema, SUMMARY_RULES, evidence_summary_prompt, evidence_summary_schema)
from .validation import parse_model_json, translation_items,translation_output_issues, text
from .terminology import constraints, missing_terms, grounded_proposals
from .linguistics import address_output_issues
from .process_lifetime import own_process
from .expression import present_items
from .cloud_models import openrouter_request,gemini_thinking
from .summary_usage import SummaryUsage
from .config import SUMMARY_MODELS

_CURRENT_PROCESS = object()


def combined_usage(first,second):
    """Sum billing/token counters across a bounded repair; never add flags.

    Providers use different field names, so preserve their numeric counters
    (including nested token details) instead of reporting only the last call.
    """
    result=dict(first)
    for key,value in second.items():
        previous=result.get(key)
        if isinstance(value,dict) and isinstance(previous,dict):
            result[key]=combined_usage(previous,value)
        elif isinstance(value,(int,float)) and not isinstance(value,bool):
            result[key]=value+(previous if isinstance(previous,(int,float)) and not isinstance(previous,bool) else 0)
        else:result[key]=value
    return result


def post_json(url, body, headers=None, timeout=60, local=False):
    encoded = json.dumps(body,ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url,encoded,headers={"Content-Type":"application/json",**(headers or {})})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({})) if local else urllib.request.build_opener()
    try:
        with opener.open(req,timeout=timeout) as response:
            raw = response.read(2 * 1024 * 1024 + 1)
            require(len(raw) <= 2 * 1024 * 1024, "PROVIDER_SIZE")
            return json.loads(raw)
    except urllib.error.HTTPError as exc:
        code = {401:"KEY_INVALID",403:"FORBIDDEN",402:"QUOTA",429:"RATE_LIMIT"}.get(exc.code,"PROVIDER")
        raise AppError(code, f"Nhà cung cấp trả HTTP {exc.code}. Kiểm tra key/hạn mức trong Cài đặt.")
    except (urllib.error.URLError,TimeoutError,OSError):
        raise AppError("NETWORK","Không kết nối được model. Không tự chuyển sang backend khác.")
    except (ValueError,KeyError):
        raise AppError("PROVIDER_FORMAT","Phản hồi nhà cung cấp không hợp lệ.")


class LlamaWorker:
    def __init__(self, executable, model, threads=4):
        self.executable, self.model = Path(executable),Path(model)
        self.threads = threads
        self.process = None
        self._process_lock = threading.RLock()
        self._lifetimes = {}
        self.token = secrets.token_urlsafe(32)
        self.base = ""

    def start(self, cancel):
        require(not cancel.is_set(),"CANCELED","Đã hủy tải model.")
        with self._process_lock:
            if self.process and self.process.poll() is None:
                return
            previous=self._lifetimes.pop(self.process,None)
            if previous:previous.close()
            require(self.executable.is_file() and self.model.is_file(),"NO_MODEL","Chưa cài llama.cpp hoặc model GGUF.")
            with socket.socket() as sock:
                sock.bind(("127.0.0.1",0))
                port = sock.getsockname()[1]
            base = f"http://127.0.0.1:{port}"
            args = [str(self.executable),"-m",str(self.model),"--host","127.0.0.1","--port",str(port),
                    "--api-key",self.token,"-c","8192","-t",str(self.threads),"-tb",str(self.threads),
                    "-ngl","0","--parallel","1","--jinja","--log-disable"]
            process = subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            try:
                lifetime=own_process(process)
            except OSError:
                self.stop(expected=process)
                raise AppError("MODEL_LIFETIME","Không quản lý được vòng đời model. Đã dừng worker để tránh giữ RAM.") from None
            self._lifetimes[process]=lifetime
            self.process,self.base = process,base
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        until = time.monotonic()+90
        while time.monotonic() < until:
            if cancel.is_set():
                self.stop(expected=process)
                raise AppError("CANCELED","Đã hủy tải model.")
            with self._process_lock:
                require(self.process is process,"CANCELED","Tác vụ tải model đã bị ngắt.")
            require(process.poll() is None,"MODEL_CRASH","Model dừng khi khởi động. Kiểm tra RAM/runtime.")
            try:
                with opener.open(base+"/health",timeout=1) as response:
                    if response.status == 200:
                        with self._process_lock:
                            require(self.process is process and not cancel.is_set(),"CANCELED","Tác vụ tải model đã bị ngắt.")
                        return
            except (OSError,urllib.error.URLError):
                cancel.wait(0.2)
        self.stop(expected=process)
        raise AppError("MODEL_TIMEOUT","Model chưa sẵn sàng trong 90 giây.")

    def generate(self,prompt,cancel,schema=None,max_tokens=900):
        self.start(cancel)
        require(not cancel.is_set(),"CANCELED")
        # urllib blocks while llama.cpp generates. Watch cancellation separately
        # and stop only the child captured for this request, never its successor.
        with self._process_lock:
            process,base = self.process,self.base
        require(process is not None and not cancel.is_set(),"CANCELED","Model đã bị ngắt trước khi sinh bản dịch.")
        completed = threading.Event()
        def watch_cancel():
            while not completed.wait(0.025):
                if cancel.is_set():
                    self.stop(expected=process)
                    return
        watcher = threading.Thread(target=watch_cancel,daemon=True)
        body = {"model":"local","messages":[{"role":"user","content":prompt}],
                "temperature":0.2,"top_p":0.6,"top_k":20,"repeat_penalty":1.05,
                "max_tokens":max_tokens,"stream":False}
        if schema:
            body["response_format"] = {"type":"json_schema","json_schema":{"name":"translation","schema":schema}}
        watcher.start()
        try:
            response = post_json(base+"/v1/chat/completions",body,{"Authorization":"Bearer "+self.token},timeout=120,local=True)
        except AppError:
            if cancel.is_set():
                raise AppError("CANCELED","Đã hủy sinh bản dịch.") from None
            raise
        finally:
            completed.set()
            watcher.join(timeout=0.1)
        require(not cancel.is_set(),"CANCELED")
        try:
            choice = response["choices"][0]
            require(choice.get("finish_reason") != "length","TRUNCATED",INCOMPLETE_GENERATION)
            return choice["message"]["content"], response.get("usage",{})
        except (KeyError,IndexError,TypeError):
            raise AppError("MODEL_FORMAT","Model trả phản hồi không hợp lệ.")

    def stop(self,expected=_CURRENT_PROCESS):
        with self._process_lock:
            process = self.process if expected is _CURRENT_PROCESS else expected
            lifetime=self._lifetimes.pop(process,None)
            if self.process is process:
                self.process = None
        try:
            if process and process.poll() is None:
                process.terminate()
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill();process.wait(timeout=5)
        finally:
            if lifetime:lifetime.close()


class Translator:
    def __init__(self,config,vault,models,runtime):
        self.config,self.vault = config,vault
        self.models,self.runtime = Path(models),Path(runtime)
        exe = next(self.runtime.rglob("llama-server.exe"),self.runtime/"llama-server.exe")
        model = self.models/"translation/Hy-MT2-1.8B-Q6_K.gguf"
        if not model.exists():
            model = self.models/"translation-lite/Hy-MT2-1.8B-Q4_K_M.gguf"
        self.local = LlamaWorker(exe,model,config.values["threads"])
        self.summary_worker = LlamaWorker(exe,self.models/"summarizer/Qwen3-4B-Instruct-2507-Q4_K_M.gguf",config.values["threads"])
        self.summary_transport_lock=threading.Lock()

    def _summary_request(self,body,key,cancel,model):
        # A cancelled background request must release the foreground worker,
        # not keep the next manga page behind a 30-second urllib timeout.
        # Its HTTP attempt may still be billed. Keep exactly one live request
        # and its durable receipt; never replace/retry it silently.
        require(self.summary_transport_lock.acquire(blocking=False),"SUMMARY_BUSY",
                "Request tóm tắt trước còn chờ nhà cung cấp. Không tự gửi thêm hoặc tính phí lần nữa.")
        ledger=SummaryUsage(self.config.root/"summary-usage.sqlite3")
        try:attempt=ledger.begin(model)
        except Exception:
            self.summary_transport_lock.release();raise
        done=threading.Event();outcome={}
        def send():
            try:
                require(not cancel.is_set(),"CANCELED")
                response=post_json("https://openrouter.ai/api/v1/chat/completions",body,
                                   {"Authorization":"Bearer "+key},timeout=30)
                outcome["response"]=response
                ledger.finish(attempt,"received",response.get("usage") if isinstance(response,dict) else None,
                              response.get("id") if isinstance(response,dict) else None)
            except Exception as error:
                outcome["error"]=error
                ledger.finish(attempt,"unknown")
            finally:
                self.summary_transport_lock.release();done.set()
        try:threading.Thread(target=send,daemon=True).start()
        except Exception:
            ledger.finish(attempt,"unknown");self.summary_transport_lock.release();raise
        while not done.wait(.025):require(not cancel.is_set(),"CANCELED")
        require(not cancel.is_set(),"CANCELED")
        if "error" in outcome:raise outcome["error"]
        require("response" in outcome,"PROVIDER_FORMAT","Request tóm tắt kết thúc mà chưa có phản hồi hợp lệ.")
        return outcome["response"]

    def signature(self):
        cfg = self.config.values
        return "local:"+self.local.model.name if cfg["mode"] == "offline" else cfg["provider"]+":"+cfg[cfg["provider"]+"Model"]

    def summary_usage(self):
        return SummaryUsage(self.config.root/"summary-usage.sqlite3").recent()

    def translate(self,regions,context,cancel):
        items,measurement=self._translate(regions,context,cancel)
        exact_terms=constraints(context,regions)
        missing=missing_terms(context,regions,items)
        issues=translation_output_issues(regions,items,exact_terms)+address_output_issues(context,regions,items)
        if missing or issues:
            # A single bounded retry. Never silently replace a different name
            # inside natural prose or display an inconsistent canonical name.
            # Regenerate only failed IDs; preserve valid dialogue and its
            # grounded terms instead of spending tokens/changing its voice.
            failed={issue["id"] for issue in [*missing,*issues]}
            retry_regions=[r for r in regions if r["id"] in failed]
            retry_terms=[];retry_term_keys=set()
            for term in [*missing,*exact_terms]:
                key=(term.get("id"),term.get("ja"),term.get("vi"))
                if term.get("id") in failed and key not in retry_term_keys:
                    retry_term_keys.add(key)
                    retry_terms.append(term)
            repaired,second=self._translate(retry_regions,{**context,"terminology_repair":retry_terms,"output_repair":issues},cancel)
            by_id={i["id"]:i for i in repaired}
            again=[by_id[item["id"]] if item["id"] in failed else item for item in items]
            second["translation_ms"]+=measurement["translation_ms"]
            second["usage"]=combined_usage(measurement.get("usage",{}),second.get("usage",{}))
            second["terms"]=[term for term in measurement.get("terms",[]) if term.get("region_id") not in failed]+second.get("terms",[])
            second["attempts"]=2
            require(not missing_terms(context,regions,again),"TERM_MISMATCH",
                    "Model chưa giữ đúng tên đã khóa. Kiểm tra thuật ngữ hoặc đổi model; nguyên bản được giữ lại.")
            require(not (translation_output_issues(regions,again,exact_terms)+address_output_issues(context,regions,again)),"MODEL_OUTPUT",
                    "Model chưa giữ đúng xưng hô, nhịp thoại, dấu câu hoặc cấu trúc bản dịch. Kiểm tra OCR hoặc đổi model; nguyên bản được giữ lại.")
            return present_items(regions,again,exact_terms),second
        return present_items(regions,items,exact_terms),{**measurement,"attempts":1}

    def _translate(self,regions,context,cancel):
        cfg = self.config.values
        prompt = translation_prompt(regions,context)
        schema = translation_schema([r["id"] for r in regions])
        start = time.perf_counter()
        if cfg["mode"] == "offline":
            ids=[r["id"] for r in regions]
            raw,usage = self.local.generate(compact_prompt(regions,context),cancel,compact_schema(ids),
                                           max_tokens=min(1400,50+sum(len(r["ja"])*5 for r in regions)))
            compact=parse_model_json(raw)
            require(isinstance(compact,dict) and set(compact)==set(ids),"MODEL_FORMAT","Model trả thiếu ID bản dịch.")
            raw=json.dumps({"items":[{"id":r["id"],"vi":compact[r["id"]],
                       "ambiguous":r.get("speaker","unknown")=="unknown"} for r in regions]},ensure_ascii=False)
        else:
            require(cfg["cloudConsent"],"CONSENT","Bật đồng ý gửi text/context cho nhà cung cấp trước.")
            require(not cancel.is_set(),"CANCELED")
            provider = cfg["provider"]
            key = self.vault.get(provider)
            if provider == "deepseek":
                response = post_json("https://api.deepseek.com/chat/completions",{
                    "model":cfg["deepseekModel"],"thinking":{"type":"disabled"},
                    "messages":[{"role":"user","content":prompt}],"temperature":0.2,"max_tokens":1600,
                    "response_format":{"type":"json_object"}},{"Authorization":"Bearer "+key})
                try:
                    choice=response["choices"][0]
                    require(choice.get("finish_reason")!="length","TRUNCATED",INCOMPLETE_GENERATION)
                    require(not choice["message"].get("refusal") and choice.get("finish_reason")!="content_filter","REFUSED")
                    raw = choice["message"]["content"]
                    usage = response.get("usage",{})
                except (KeyError,IndexError):
                    raise AppError("PROVIDER_FORMAT","Phản hồi DeepSeek không có bản dịch.")
            elif provider=="openrouter":
                body=openrouter_request(cfg["openrouterModel"],prompt,schema)
                response=post_json("https://openrouter.ai/api/v1/chat/completions",body,{"Authorization":"Bearer "+key})
                try:
                    choice=response["choices"][0]
                    require(choice.get("finish_reason")!="length","TRUNCATED",INCOMPLETE_GENERATION)
                    require(not choice["message"].get("refusal") and choice.get("finish_reason")!="content_filter","REFUSED")
                    raw=choice["message"]["content"];usage=response.get("usage",{})
                except (KeyError,IndexError,TypeError):
                    raise AppError("PROVIDER_FORMAT","Phản hồi OpenRouter không có bản dịch.")
            else:
                generation={"temperature":0.2,"maxOutputTokens":1600,"responseMimeType":"application/json","responseJsonSchema":schema}
                thinking=gemini_thinking(cfg["geminiModel"])
                if thinking:generation["thinkingConfig"]=thinking
                response = post_json("https://generativelanguage.googleapis.com/v1beta/models/"+cfg["geminiModel"]+":generateContent",
                    {"contents":[{"parts":[{"text":prompt}]}],"generationConfig":generation},
                    {"x-goog-api-key":key})
                try:
                    candidate=response["candidates"][0]
                    require(candidate.get("finishReason")!="MAX_TOKENS","TRUNCATED",INCOMPLETE_GENERATION)
                    require(candidate.get("finishReason") not in ("SAFETY","RECITATION","BLOCKLIST","PROHIBITED_CONTENT"),"REFUSED")
                    raw = "".join(p.get("text","") for p in candidate["content"]["parts"] if not p.get("thought"))
                    usage = response.get("usageMetadata",{})
                except (KeyError,IndexError):
                    raise AppError("PROVIDER_FORMAT","Phản hồi Gemini không có bản dịch.")
        require(not cancel.is_set(),"CANCELED")
        parsed=parse_model_json(raw)
        items = translation_items(parsed,[r["id"] for r in regions])
        return items, {"translation_ms":(time.perf_counter()-start)*1000,"usage":usage,"backend":self.signature(),
                       "terms":grounded_proposals(parsed,regions,items)}

    def summarize(self,job,cancel):
        # Only one LLM consumes CPU; interruption can terminate the summary worker.
        regions=json.loads(job["regions"])
        ids=[r["id"] for r in regions]
        if not ids:
            return {"summary":"Không có lời thoại đã xử lý; không suy diễn nội dung hình ảnh.","facts":[]}
        cfg = self.config.values
        if cfg.get("summaryBackend", "local") == "cloud":
            require(cfg["mode"] == "byok" and cfg["provider"] == "openrouter", "OFFLINE",
                    "Tóm tắt cloud đang tắt; không tự chuyển engine.")
            require(cfg["cloudConsent"] is True and cfg.get("summaryCloudConsent") is True, "SUMMARY_CONSENT",
                    "Xác nhận riêng việc gửi thoại đã đọc để tóm tắt và phí API trước.")
            require(cfg.get("summaryModel") in SUMMARY_MODELS,"SUMMARY_MODEL","Model tóm tắt chưa có adapter đã kiểm thử.")
            require(not cancel.is_set(), "CANCELED")
            body = openrouter_request(cfg["summaryModel"], evidence_summary_prompt(regions),
                                      evidence_summary_schema(ids), max_tokens=900)
            require(len(body["messages"][0]["content"].encode("utf-8"))<=48000,"SUMMARY_SIZE",
                    "Trang quá dài để tóm tắt gọn; không tự chia thành nhiều request tính phí.")
            key = self.vault.get("openrouter")
            require(not cancel.is_set(), "CANCELED")
            response=self._summary_request(body,key,cancel,cfg["summaryModel"])
            require(not cancel.is_set(), "CANCELED")
            try:
                choice = response["choices"][0]
                require(choice.get("finish_reason") != "length", "TRUNCATED", "Model chưa hoàn tất tóm tắt; không lưu phần bị cắt.")
                require(not choice["message"].get("refusal") and choice.get("finish_reason") != "content_filter", "REFUSED")
                raw = choice["message"]["content"]
            except (KeyError, IndexError, TypeError):
                raise AppError("PROVIDER_FORMAT", "Phản hồi cloud không có tóm tắt hợp lệ.")
            parsed=parse_model_json(raw)
            require(isinstance(parsed,dict) and set(parsed)=={"summary","facts"},"MODEL_FORMAT")
            text(parsed["summary"],600)
            require(isinstance(parsed["facts"],list) and len(parsed["facts"])<=4,"MODEL_FORMAT")
            for fact in parsed["facts"]:
                require(isinstance(fact,dict) and set(fact)=={"text","evidence_ids"},"MODEL_FORMAT")
                text(fact["text"],160)
                evidence=fact["evidence_ids"]
                require(isinstance(evidence,list) and 1<=len(evidence)<=4 and
                        all(isinstance(item,str) and item in ids for item in evidence) and
                        len(set(evidence))==len(evidence),"EVIDENCE")
            # Internal provenance marker, never requested from the model.
            return {**parsed,"_summaryPolicy":"selected-events-v1"}
        raw,_ = self.summary_worker.generate(SUMMARY_RULES+"\n"+job["regions"],cancel,
                                            schema=summary_schema(ids),max_tokens=800)
        return parse_model_json(raw)

    def stop(self):
        self.local.stop()
        self.summary_worker.stop()
