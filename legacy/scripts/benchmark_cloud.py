"""Bounded OpenRouter pilot on author-created Japanese dialogue only.
Key enters via stdin or Windows Vault; report contains no secrets or manga scans.
"""
import argparse
import getpass
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import threading
import time
import urllib.request
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from manga_live.config import Config,Secrets
from manga_live.linguistics import voice_record,name_record
from manga_live.errors import AppError
import manga_live.providers as providers
from manga_live.prompts import PROMPT_VERSION,translation_prompt,translation_schema
from manga_live.terminology import constraints
from manga_live.terminology import term_record
from manga_live.expression import unpace_single_term
from manga_live.cloud_models import model_choices
from cloud_response_evidence import capture_response, reported_cost_total

MODELS=[model["id"] for model in model_choices() if model["provider"]=="openrouter"]

def cases():
    def relationship(a,b,s,t):
        return {"kind":"relationship","key":a+"→"+b,"value":json.dumps(voice_record(a,b,s,t),ensure_ascii=False),"confirmed":1,"chapter":1}
    return [
        {"name":"siblings","context":{"story":{"title":"Nhà của hai chị em","genre":"đời thường"},
          "characters":[relationship("younger","sister","em","chị"),relationship("sister","younger","chị","em")]},
         "regions":[{"id":"a","ja":"姉ちゃん、まだ帰らないの？","speaker":"younger","listener":"sister"},
                    {"id":"b","ja":"先に帰ってて。あとで行くから。","speaker":"sister","listener":"younger"},
                    {"id":"c","ja":"わかった。待ってるね。","speaker":"younger","listener":"sister"}]},
        {"name":"standalone_sibling_calls","context":{"styles":[{"key":"kinship","value":"preserve"}]},
         "regions":[{"id":"a","ja":"姉ちゃん"},{"id":"b","ja":"お兄ちゃん"}]},
        {"name":"scope","context":{"story":{"title":"Cuộc hẹn","genre":"đời thường"}},
         "regions":[{"id":"a","ja":"行かないわけじゃない。ただ、今は行けない。"},
                    {"id":"b","ja":"明日は来なくてもいい。"},
                    {"id":"c","ja":"兄に行かせられた。"}]},
        {"name":"fantasy_terms","context":{"story":{"title":"Người giữ thành","genre":"fantasy/action"},
          "styles":[{"key":"naming","value":"fantasy"}],
          "glossary":[{"key":"ice","value":json.dumps(term_record("ice","skill","氷結結界","Băng Kết Kết Giới"),ensure_ascii=False),"confirmed":1},
                      {"key":"potion","value":json.dumps(term_record("potion","item","魔力回復薬","Thuốc Hồi Ma Lực"),ensure_ascii=False),"confirmed":1}]},
         "regions":[{"id":"a","ja":"氷結結界を展開する！"},
                    {"id":"b","ja":"魔力回復薬はあと一本しかない。"},
                    {"id":"c","ja":"決して仲間を見捨てるな！"}]},
        {"name":"uncertainty_register","context":{"story":{"title":"Cửa hàng bí mật","genre":"đời thường"}},
         "regions":[{"id":"a","ja":"お客様、こちらにお掛けください。","speaker":"staff","listener":"customer"},
                    {"id":"b","ja":"来るらしいけど、まだ決まったわけじゃない。"},
                    {"id":"c","ja":"ドキドキ","type":"sfx"}]},
        {"name":"source_address","context":{"story":{"title":"Tên gọi","genre":"học đường, đời thường"},
          "characters":[{"kind":"character","key":"misaki","confirmed":1,"value":json.dumps(name_record("misaki",[
            {"ja":"田中","reading":"Tanaka","role":"family"},{"ja":"美咲","reading":"Misaki","role":"given"}]),ensure_ascii=False)}],
          "styles":[{"key":"honorifics","value":"preserve"},{"key":"kinship","value":"preserve"}]},
         "regions":[{"id":"a","ja":"田中さん、おはよう。"},
                    {"id":"b","ja":"美咲って呼んでもいい？"},
                    {"id":"c","ja":"お兄ちゃん、キリト君とアスラ様が来たよ。"}]},
        {"name":"no_added_suffix","context":{"story":{"title":"Cuộc hội ngộ","genre":"fantasy"},
          "styles":[{"key":"honorifics","value":"preserve"}]},
         "regions":[{"id":"a","ja":"キリト、待って！"},
                    {"id":"b","ja":"先輩、手伝ってもらえますか。"},
                    {"id":"c","ja":"私の兄は医者です。"}]},
        {"name":"expression_voice","context":{"characters":[relationship("younger","sister","em","chị")]},
         "regions":[{"id":"a","ja":"わ・た・し〜〜！","speaker":"younger","listener":"sister"},
                    {"id":"b","ja":"ま、まって…！","speaker":"younger","listener":"sister"}]},
        {"name":"expression_transfer","context":{},
         "regions":[{"id":"a","ja":"い、いや…！"},{"id":"b","ja":"おーーい！"},{"id":"c","ja":"あ・な・た〜〜？"}]},
        {"name":"spelled_caps","context":{},
         "regions":[{"id":"a","ja":"I L O V E Y O U"},{"id":"b","ja":"STOP!"}]},
        {"name":"partial_quote","context":{},
         "regions":[{"id":"a","ja":"「姉ちゃん、まだ帰らないの？"},{"id":"b","ja":"「明日は来なくてもいい。"}]},
        {"name":"ordinary_delivery","context":{},
         "regions":[{"id":"a","ja":"スーパーでパンを買った。"},{"id":"b","ja":"おかあさんに聞いてみる。"}]},
    ]

class EphemeralKey:
    def __init__(self,value):self.value=value
    def get(self,provider):return self.value


def budget_plan(models,catalog,repeats,selected=None,completion_tokens=700):
    """Reserve both attempts at enforced route ceilings, not cheapest price.

    OpenRouter max_price uses USD per million tokens. Request-priced routes
    are excluded. Add schema/framing headroom and the longer repair prompt.
    This is a conservative preflight estimate, not an upstream billing audit.
    """
    if type(completion_tokens) is not int or not 1 <= completion_tokens <= 700:
        raise ValueError("Invalid completion token ceiling")
    ceilings={};estimate=0
    for model in models:
        if model not in catalog:raise ValueError("Model absent from live catalogue: "+model)
        price=catalog[model]["pricing"]
        rates=[float(price[k])*1000000 for k in ("prompt","completion")]
        if not all(math.isfinite(r) and r>=0 for r in rates):raise ValueError("Invalid catalogue pricing")
        limits={"prompt":max(0.30,rates[0]),"completion":max(1.20,rates[1]),"request":0}
        ceilings[model]=limits
        for case in (selected if selected is not None else cases()):
            repair={**case["context"],"terminology_repair":constraints(case["context"],case["regions"]),"output_repair":True}
            input_bound=len(translation_prompt(case["regions"],repair).encode())+512
            input_bound+=len(json.dumps(translation_schema([r["id"] for r in case["regions"]])).encode())
            estimate+=(input_bound*limits["prompt"]+completion_tokens*limits["completion"])/1000000*repeats*2
    return estimate,ceilings


def bounded_request(body,ceilings,max_tokens=700):
    if type(max_tokens) is not int or not 1 <= max_tokens <= 700:
        raise ValueError("Invalid completion token ceiling")
    return {**body,"max_tokens":max_tokens,"provider":{**body.get("provider",{}),"max_price":ceilings[body["model"]]}}


class BudgetLedger:
    """Reserve before each attempt, including failed/unknown-billed responses.

    Byte-count bound + framing headroom at enforced price ceilings; do not
    refund on a timeout just because usage.cost was not returned. Also keep the
    user's upstream hard key limit: this is a conservative test harness bound,
    not an independent provider billing guarantee.
    """
    def __init__(self,limit):
        if not math.isfinite(limit) or not 0<limit<=1:raise ValueError("Budget outside (0,1] USD")
        self.limit,self.reserved,self.calls=limit,0,0

    def reserve(self,body):
        price=body["provider"]["max_price"]
        if price.get("request")!=0:raise ValueError("Per-request billed routes must be excluded")
        size=len(json.dumps(body,ensure_ascii=False).encode())+512
        amount=(size*price["prompt"]+body["max_tokens"]*price["completion"])/1000000
        if not math.isfinite(amount) or amount<0:raise ValueError("Invalid request reservation")
        if self.reserved+amount>self.limit:raise AppError("TEST_BUDGET","Đã tới giới hạn dành riêng cho benchmark; chưa gửi request tiếp theo.")
        self.reserved+=amount;self.calls+=1
        return amount


def ordered_runs(models,selected,repeats):
    # Rotate model order across groups and reverse on the second pass. Do not
    # confuse incidental prefix hits/provider changes with model-only speed.
    for repeat in range(repeats):
        for index,case in enumerate(selected):
            order=models[index%len(models):]+models[:index%len(models)]
            if repeat%2:order=list(reversed(order))
            for model in order:yield model,repeat,case


def narrow_checks(case,items):
    """Fixture-specific known-error checks, NOT a translation-quality score."""
    values={item["id"]:item["vi"].casefold() for item in items};checks={}
    if case=="siblings":
        checks["confirmed_self_not_generic"]=all(not re.search(r"\b(?:tôi|tớ|tao)\b",v) for v in values.values())
        checks["retained_vocative"]="nee-chan" in values["a"]
        checks["request_not_completed_action"]=not re.search(r"đã về|về trước rồi",values["b"])
        checks["recipient_not_older_speaker"]=not re.search(r"^chị\s+(?:hãy |cứ )?(?:về|đi) trước",values["b"])
        checks["speaker_is_waiter_not_object"]=not re.search(r"(?:đợi|chờ) em\b",values["c"])
    elif case=="standalone_sibling_calls":
        checks["retained_calls_without_stacked_titles"]=all(
            re.fullmatch(re.escape(title)+r"[!?…。.]*",values[rid].strip()) is not None
            for rid,title in (("a","nee-chan"),("b","onii-chan")))
    elif case=="scope":
        checks["refusal_not_inability"]=not re.search(r"(?:không phải|đâu phải)[^.!?]*không (?:thể|đi được)",values["a"])
        checks["causative_passive_compulsion"]=bool(re.search(r"\b(?:bắt|buộc|ép)\b",values["c"]))
        checks["not_necessary_is_not_forbidden"]=not re.search(r"\b(?:không được|cấm)\b",values["b"])
    elif case=="fantasy_terms":
        checks["no_pill_counter"]=not re.search(r"\bviên\b",values["b"])
        checks["locked_names"]="băng kết kết giới" in values["a"] and "thuốc hồi ma lực" in values["b"]
    elif case=="source_address":checks["name_caller_not_self"]=not re.search(r"gọi (?:tôi|mình|tao|tớ)\b",values["b"])
    elif case=="expression_voice":checks["confirmed_expressive_self"]=unpace_single_term(values["a"])=="em"
    elif case=="expression_transfer":
        checks["refusal_not_wait_example"]=bool(re.search(r"kh[-,]?\s*không|không|k-không",values["a"])) and "đợi" not in values["a"]
        checks["second_person_not_toi_example"]=unpace_single_term(values["c"]) not in ("tôi","tớ","em")
    elif case=="spelled_caps":
        checks["spelling_meaning"]=re.sub(r"\s+","",values["a"]) in ("tôiyêubạn","tôiyêucậu","tôiyêungười")
        checks["caps_meaning"]="dừng" in values["b"]
    elif case=="ordinary_delivery":
        checks["supermarket_not_superhero"]="siêu thị" in values["a"] and "bánh" in values["a"]
        checks["ordinary_vowels_not_stretch"]="ợợ" not in values["b"] and "aaa" not in values["b"]
    return checks

def run(args):
    if args.catalogue:
        catalogue=json.loads(Path(args.catalogue).read_text(encoding="utf-8"))
    else:
        with urllib.request.urlopen("https://openrouter.ai/api/v1/models",timeout=60) as response:
            catalogue=json.load(response)
    catalog={m["id"]:m for m in catalogue["data"]}
    selected=[case for case in cases() if not args.cases or case["name"] in args.cases]
    if not selected or len(set(args.models))!=len(args.models):raise SystemExit("Empty cases or duplicate models")
    ledger=BudgetLedger(args.budget)
    estimate,ceilings=budget_plan(args.models,catalog,args.repeats,selected)
    preflight={"preflight_estimate_usd":estimate,"budget_usd":args.budget,"groups":len(args.models)*len(selected)*args.repeats,
        "max_provider_requests":len(args.models)*len(selected)*args.repeats*2,"provider_price_ceilings":ceilings,
        "catalogue_models":[{k:catalog[m].get(k) for k in ("id","canonical_slug","pricing","reasoning","supported_parameters")} for m in args.models]}
    print(json.dumps(preflight,ensure_ascii=True),flush=True)
    if args.plan_only:return
    if estimate>args.budget:raise SystemExit("Estimated upper bound exceeds test budget; narrow cases/models/repeats")
    destination=Path(args.workdir);destination.mkdir(parents=True,exist_ok=True)
    if (destination/"cloud-benchmark.json").exists() or (destination/"cloud-benchmark.tmp").exists():
        raise ValueError("Use a new output folder; do not overwrite existing attempt evidence")
    try:
        with (destination/".cloud-benchmark.claim").open("x",encoding="utf-8") as claim:
            claim.write("Single-use benchmark output; not a live-process marker.\n")
    except FileExistsError:
        raise ValueError("Use a new output folder; this benchmark destination was already claimed") from None
    key=(getpass.getpass("Test API key (hidden): ").strip() if args.prompt_key else
         sys.stdin.readline().strip() if args.stdin_key else Secrets(args.vault_profile).get("openrouter"))
    if len(key)<12:raise SystemExit("No test key supplied")
    config=Config(destination/"cloud-profile")
    config.update({"mode":"byok","provider":"openrouter","cloudConsent":True})
    translator=providers.Translator(config,EphemeralKey(key),ROOT/"models",ROOT/"runtime/llama")
    rows=[];base_post=providers.post_json;last={};routes=[];attempts=[];active={};seen_generations=set()
    def save():
        report={"schema":3,"source":"author-created synthetic dialogue","models":args.models,"rows":rows,
                "attempts":attempts,"prompt_version":PROMPT_VERSION,"preflight":preflight,
                "reserved_usd":ledger.reserved,"attempted_requests":ledger.calls,
                "reported_cost_usd":reported_cost_total(attempts),
                "aborted":aborted,
                "limitations":["Small pilot, not representative Japanese–Vietnamese quality certification.",
                    "No human blind scoring; schema/contract and narrow guards are not semantic accuracy.",
                    "No OCR/overlay time or reliable p95; returned metadata is not a reconciled bill.",
                    "Latency-routed endpoints may differ; no provider-pinned model-only A/B or guaranteed cold/cache condition."]}
        path=destination/"cloud-benchmark.json";temporary=path.with_suffix(".tmp")
        temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
        temporary.replace(path)
    def instrumented(url,body,*rest,**kwargs):
        if "openrouter.ai" in url:
            body=bounded_request(body,ceilings)
            reservation=ledger.reserve(body)
        else:raise AppError("TEST_ENDPOINT","Benchmark only permits the chosen OpenRouter endpoint.")
        attempt={"attempt_id":uuid.uuid4().hex,"number":ledger.calls,"state":"attempted",
            "started_at_unix_ns":time.time_ns(),
            "model":body["model"],**active,
            "request_sha256":hashlib.sha256(json.dumps(body,ensure_ascii=False,sort_keys=True).encode()).hexdigest(),
            "requested_routing":body.get("provider",{}),"reserved_usd":reservation}
        attempts.append(attempt);routes.append(attempt);last.clear();last.update(attempt)
        save()  # Persist the reservation even if the transport never returns.
        try:
            response=base_post(url,body,*rest,**kwargs)
            capture_response(attempt,response,save,seen_generations)
            if attempt["billing_state"]!="reported":
                raise AppError("TEST_ACCOUNTING","Dừng benchmark: thiếu hoặc mâu thuẫn bằng chứng chi phí.")
            if args.capture_output:
                # Only fixed authored fixtures, never reader data; no raw envelope logging.
                choices=response.get("choices") if isinstance(response,dict) else None
                choice=choices[0] if isinstance(choices,list) and choices and isinstance(choices[0],dict) else {}
                message=choice.get("message")
                raw=message.get("content") if isinstance(message,dict) else None
                if isinstance(raw,str):attempt["author_output"]=raw[:12000]
            return response
        except AppError as error:
            if attempt["state"]=="attempted":attempt["state"]="failed"
            attempt["error"]=error.code;raise
        finally:
            last.clear();last.update(attempt);save()
    providers.post_json=instrumented
    aborted=None
    try:
        for model,repeat,case in ordered_runs(args.models,selected,args.repeats):
            config.update({"openrouterModel":model})
            active.clear();active.update(case=case["name"],repeat=repeat)
            last.clear();routes.clear()
            row={"model":model,"case":case["name"],"repeat":repeat}
            start=time.perf_counter()
            try:
                items,metrics=translator.translate(case["regions"],case["context"],threading.Event())
                checks=narrow_checks(case["name"],items)
                row.update(ok=True,items=items,metrics=metrics,route=dict(last),narrow_checks=checks,narrow_checks_passed=all(checks.values()))
            except AppError as exc:
                row.update(ok=False,error=exc.code)
                if last:row["route"]=dict(last) # Schema failure may still be billed.
            row["routes"]=list(routes)
            row["response_ms"]=(time.perf_counter()-start)*1000;rows.append(row)
            print(json.dumps({k:row.get(k) for k in ("model","case","ok","error","response_ms","narrow_checks")},ensure_ascii=True),flush=True)
            save()
            spent=reported_cost_total(attempts)
            if spent is not None and spent>=args.budget:raise SystemExit("Actual test budget reached")
            if any(route.get("billing_state")!="reported" for route in routes):
                aborted=row.get("error") or "TEST_ACCOUNTING";save();break
            if row.get("error") in ("KEY_INVALID","QUOTA","FORBIDDEN","TEST_BUDGET","TEST_ACCOUNTING"):
                aborted=row["error"];save();break
    finally:
        translator.stop();providers.post_json=base_post;translator.vault.value="";key=""
    summary=[]
    for model in args.models:
        accepted=[r for r in rows if r["model"]==model and r["ok"]]
        all_rows=[r for r in rows if r["model"]==model]
        summary.append({"model":model,"success":len(accepted),"p50_response_ms":statistics.median(r["response_ms"] for r in accepted) if accepted else None,
            "narrow_checks_passed":sum(r.get("narrow_checks_passed",False) for r in all_rows),"groups":len(all_rows),
            "cost_usd_including_failures":reported_cost_total([route for r in all_rows for route in r.get("routes",[])])})
    print(json.dumps({"summary":summary},ensure_ascii=True,indent=2))

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--stdin-key",action="store_true")
    parser.add_argument("--prompt-key",action="store_true",help="Read one ephemeral test key without terminal echo")
    parser.add_argument("--repeats",type=int,choices=range(1,4),default=1)
    parser.add_argument("--budget",type=float,default=0.20)
    parser.add_argument("--models",nargs="+",default=MODELS)
    parser.add_argument("--workdir",default=str(ROOT/"artifacts"))
    parser.add_argument("--catalogue")
    parser.add_argument("--plan-only",action="store_true",help="Read public catalogue and print reservation; no key or paid call")
    parser.add_argument("--vault-profile",default="benchmark-openrouter")
    parser.add_argument("--capture-output",action="store_true",help="Keep rejected authored-fixture text in private report, never stdout")
    parser.add_argument("--cases",nargs="+",choices=[case["name"] for case in cases()])
    run(parser.parse_args())
