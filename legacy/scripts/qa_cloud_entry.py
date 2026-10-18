"""Paid native QA, isolated from every personal browser profile.

Read the benchmark credential only from Windows Vault. Enforce reservation
before every provider attempt; no raw prompt/key/image logging or fallback.
This entry is never installed as the production native host.
"""
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from qa_native_entry import diagnostic_folder
from benchmark_cloud import BudgetLedger,bounded_request
from manga_live.cloud_models import model_choices
from manga_live.config import Secrets
from manga_live.errors import AppError
from cloud_response_evidence import capture_response, reported_cost_total


def require_text_only(body):
    """Fail before reservation/network if this text-authorized QA sees media."""
    messages=body.get("messages")
    if (body.get("tools") or not isinstance(messages,list) or not 1<=len(messages)<=8 or
        any(not isinstance(m,dict) or not isinstance(m.get("content"),str) or
            len(m["content"])>100000 or "data:image/" in m["content"].lower()
            for m in messages)):
        raise AppError("TEST_TEXT_ONLY","Lượt QA chỉ cho gửi text; ảnh/crop/công cụ bị chặn trước request.")


def validated_options(config):
    value=config.get("qaCloud",{})
    if value.get("consent") is not True:
        raise ValueError("Paid fixture QA requires explicit consent")
    allowed={m["id"] for m in model_choices() if m["provider"]=="openrouter"}
    model=value.get("model");prices=value.get("prices")
    budget=value.get("budgetUsd")
    if model not in allowed or not isinstance(prices,dict) or set(prices)!={"prompt","completion","request"}:
        raise ValueError("Unreviewed QA model/rate")
    if prices["request"]!=0 or any(type(prices[k]) not in (int,float) or not 0<prices[k]<=5 for k in ("prompt","completion")):
        raise ValueError("QA rate outside bounded ceilings")
    if type(budget) not in (int,float) or not 0<budget<=.10:
        raise ValueError("Native fixture QA budget exceeds 0.10 USD")
    return model,budget,prices


def main():
    folder=diagnostic_folder(sys.argv)
    config=json.loads((folder/"native-config.json").read_text(encoding="utf-8"))
    model,budget,prices=validated_options(config)
    import manga_live.providers as providers
    from manga_live.host import Host,main as host_main
    ledger=BudgetLedger(budget);attempts=[];seen_generations=set();accounting_failure=False
    base_post=providers.post_json;base_initialize=Host.initialize
    def save():
        (folder/"cloud-usage.json").write_text(json.dumps({"model":model,"budget_usd":budget,
            "reserved_usd":ledger.reserved,"attempts":attempts,
            "reported_cost_usd":reported_cost_total(attempts)},indent=2,allow_nan=False),encoding="utf-8")
    def initialize(self,profile):
        base_initialize(self,profile)
        self.translator.vault=Secrets("benchmark-openrouter")
        self.config.update({"mode":"byok","provider":"openrouter","openrouterModel":model,
            "cloudConsent":True,"autoSummary":False,"metadataConsent":False})
    def post(url,body,*args,**kwargs):
        nonlocal accounting_failure
        if accounting_failure:
            raise AppError("TEST_ACCOUNTING","QA đã dừng request sau lỗi đối soát chi phí.")
        if url!="https://openrouter.ai/api/v1/chat/completions" or body.get("model")!=model:
            raise AppError("TEST_ENDPOINT","QA không cho đổi provider/model hoặc gọi nền ngoài tác vụ kiểm thử.")
        require_text_only(body)
        body=bounded_request(body,{model:prices})
        if body.get("provider",{}).get("data_collection")!="deny" or body.get("tools"):
            raise AppError("TEST_PRIVACY","QA không cho nới privacy hoặc gọi công cụ.")
        amount=ledger.reserve(body)
        entry={"attempt_id":uuid.uuid4().hex,"started_at_unix_ns":time.time_ns(),
            "number":ledger.calls,"reserved_usd":amount,"state":"attempted",
            "request_sha256":hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest()}
        attempts.append(entry);save()
        try:
            result=base_post(url,body,*args,**kwargs)
            capture_response(entry,result,save,seen_generations)
            entry.update(input_tokens=entry["usage"].get("prompt_tokens"),
                         output_tokens=entry["usage"].get("completion_tokens"))
            if entry["billing_state"]!="reported":
                accounting_failure=True
                raise AppError("TEST_ACCOUNTING","QA dừng vì thiếu hoặc mâu thuẫn bằng chứng chi phí.")
            return result
        except AppError as error:
            if entry["state"]=="attempted":entry["state"]="failed"
            if entry.get("billing_state")!="reported":accounting_failure=True
            entry["error"]=error.code;raise
        finally:save()
    Host.initialize=initialize;providers.post_json=post
    trace=None
    if config.get("qaStackTrace") is True:
        # Disposable QA only: stack frames, never locals/text/keys/pixels.
        import faulthandler
        trace=(folder/"native-stack.log").open("w",encoding="utf-8")
        faulthandler.dump_traceback_later(35,repeat=True,file=trace)
    try:host_main()
    finally:
        if trace:
            faulthandler.cancel_dump_traceback_later();trace.close()
        Host.initialize=base_initialize;providers.post_json=base_post;save()


if __name__=="__main__":main()
