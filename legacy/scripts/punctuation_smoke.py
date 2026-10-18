"""Bounded real-offline regression on authored dialogue; no OCR/quality claim.

No key, cloud call, private source, browser profile or production settings.
Outputs only authored test data/metrics to a fresh temporary evidence directory.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.config import Config
from manga_live.errors import AppError
from manga_live.ocr import review_reasons
from manga_live.providers import Translator
import manga_live.providers as providers
import manga_live.prompts as prompts
from manga_live.validation import translation_output_issues
from manga_live.terminology import constraints
from manga_live.prompts import PROMPT_VERSION


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--deadline",type=int,choices=range(10,61),default=50)
    parser.add_argument("--seed",type=int,default=0)
    parser.add_argument("--guidance",choices=("full","brief","none"),default="full")
    parser.add_argument("--case",choices=("all","observed","plain"),default="all")
    args=parser.parse_args()
    directory=Path(tempfile.mkdtemp(prefix="mangalive-punctuation-"))
    config=Config(directory/"config");config.update({"mode":"offline"})
    translator=Translator(config,None,ROOT/"models",ROOT/"runtime/llama")
    cancel=threading.Event();timer=threading.Timer(args.deadline,cancel.set)
    timer.daemon=True;timer.start();started=time.perf_counter()
    report={"source":"authored Japanese; actual offline Hy-MT2; no OCR or browser",
            "promptVersion":PROMPT_VERSION,"deadline_s":args.deadline,"cases":[],"passed":False,
            "seed":args.seed,"guidance":args.guidance,"requests":[],
            "limitations":["A small deterministic structural regression, not a translation-quality score or p95.",
                           "Unbalanced source quotations remain unchanged and reviewable; no ground-truth correction."]}
    print(json.dumps({"evidence":str(directory/"result.json"),"starting":"offline"}),flush=True)
    post=providers.post_json;guidance=prompts.punctuation_guidance
    def measured_post(url,body,*rest,**kwargs):
        assert kwargs.get("local") is True and url.startswith("http://127.0.0.1:"),"This harness may only call its local worker"
        reply=post(url,{**body,"seed":args.seed},*rest,**kwargs)
        choice=reply["choices"][0]
        # Authored diagnostic data only; never use this for a private reader job.
        report["requests"].append({"prompt_sha256":hashlib.sha256(body["messages"][0]["content"].encode()).hexdigest(),
            "finish_reason":choice.get("finish_reason"),"model_text":choice["message"]["content"],
            "usage":reply.get("usage",{}),"max_tokens":body["max_tokens"]})
        return reply
    def brief_guidance(regions,context):
        value="\nKeep meaningful source quotation; do not add decorative quotation wrappers or dangling separators to dialogue."
        if any(prompts.quote_imbalanced(r["ja"]) for r in regions):
            value+=" OCR quotation is uncertain: do not invent dialogue punctuation."
        if context.get("output_repair"):value+=" Repair the previous framing/escape artifacts; return clean dialogue values."
        return value
    providers.post_json=measured_post
    if args.guidance=="brief":prompts.punctuation_guidance=brief_guidance
    elif args.guidance=="none":prompts.punctuation_guidance=lambda *a:""
    try:
        warm=time.perf_counter();translator.local.start(cancel)
        report["load_ms"]=(time.perf_counter()-warm)*1000
        print(json.dumps({"ready":True,"load_ms":report["load_ms"]}),flush=True)
        cases=[
            ("observed-ocr-quote-shapes",[
                {"id":"r000","ja":"「姉ちゃん、まだ帰らないの？"},
                {"id":"r003","ja":"「明日は来なくてもいい。"}],{}),
            ("plain-and-genuine-quotation",[
                {"id":"a","ja":"こんにちは。"},
                {"id":"b","ja":"彼は「明日行く」と言った。"}],{}),
        ]
        if args.case=="observed":cases=cases[:1]
        elif args.case=="plain":cases=cases[1:]
        for name,regions,context in cases:
            original=[r["ja"] for r in regions]
            for region in regions:region.update(reviewReasons=review_reasons(region["ja"]))
            at=time.perf_counter();row={"name":name}
            try:
                items,metrics=translator.translate(regions,context,cancel)
                row.update(items=items,metrics=metrics,
                           passed=not translation_output_issues(regions,items,constraints(context,regions)))
            except AppError as error:row.update(passed=False,error=error.code)
            row["source_unchanged"]=original==[r["ja"] for r in regions]
            row["response_ms"]=(time.perf_counter()-at)*1000
            report["cases"].append(row)
            print(json.dumps(row,ensure_ascii=True),flush=True)
            if cancel.is_set():break
        report["passed"]=len(report["cases"])==len(cases) and all(r["passed"] and r["source_unchanged"] for r in report["cases"])
    except AppError as error:report["error"]=error.code
    finally:
        providers.post_json=post;prompts.punctuation_guidance=guidance
        timer.cancel();cancel.set();translator.stop()
        report["total_ms"]=(time.perf_counter()-started)*1000
        (directory/"result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({"passed":report["passed"],"evidence":str(directory/"result.json"),
                          "total_ms":report["total_ms"],"error":report.get("error")}),flush=True)
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
