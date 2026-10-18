"""Bounded actual Hy-MT2 delivery probe on authored text, not quality certification.

No OCR, private data, browser registration, API key or cloud request. A separate
renderer replay tests fitting; this harness must not confuse it with generation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.config import Config
from manga_live.errors import AppError
from manga_live.providers import Translator
import manga_live.providers as providers
from manga_live.prompts import PROMPT_VERSION
from manga_live.validation import translation_output_issues
from manga_live.expression import bind_expression
from manga_live.linguistics import voice_record


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--deadline",type=int,choices=range(10,61),default=50)
    parser.add_argument("--seed",type=int,default=0)
    parser.add_argument("--case",choices=("all","rhythm","spelling","caps","ordinary","transfer","voice"),default="all")
    args=parser.parse_args()
    directory=Path(tempfile.mkdtemp(prefix="mangalive-expression-"))
    config=Config(directory/"config");config.update({"mode":"offline"})
    translator=Translator(config,None,ROOT/"models",ROOT/"runtime/llama")
    cancel=threading.Event();timer=threading.Timer(args.deadline,cancel.set)
    timer.daemon=True;timer.start();started=time.perf_counter()
    report={"source":"authored dialogue; actual Hy-MT2; no OCR, cloud or browser",
        "promptVersion":PROMPT_VERSION,"seed":args.seed,"deadline_s":args.deadline,
        "model":translator.local.model.name,"requests":[],"cases":[],"passed":False,
        "limitations":["Structural delivery checks and source-echo check, not a human translation-quality grade.",
                       "No p95 claim, no manga benchmark or portable-host acceptance."]}
    print(json.dumps({"evidence":str(directory/"result.json"),"starting":"offline"}),flush=True)
    post=providers.post_json
    def measured_post(url,body,*rest,**kwargs):
        assert kwargs.get("local") is True and url.startswith("http://127.0.0.1:"),"Only the owned local worker is allowed"
        at=time.perf_counter();reply=post(url,{**body,"seed":args.seed},*rest,**kwargs)
        choice=reply["choices"][0]
        report["requests"].append({"prompt_sha256":hashlib.sha256(body["messages"][0]["content"].encode()).hexdigest(),
            "finish_reason":choice.get("finish_reason"),"model_text":choice["message"]["content"],
            "usage":reply.get("usage",{}),"response_ms":(time.perf_counter()-at)*1000})
        return reply
    providers.post_json=measured_post
    try:
        at=time.perf_counter();translator.local.start(cancel)
        report["load_ms"]=(time.perf_counter()-at)*1000
        print(json.dumps({"ready":True,"load_ms":report["load_ms"]}),flush=True)
        cases=[
            ("rhythm",[{"id":"a","ja":"わ・た・し〜〜！"},{"id":"b","ja":"ま、まって…！"}]),
            ("spelling",[{"id":"c","ja":"I L O V E Y O U"}]),
            ("caps",[{"id":"d","ja":"STOP!"}]),
            ("ordinary",[{"id":"e","ja":"スーパーでパンを買った。"}]),
            ("transfer",[{"id":"f","ja":"い、いや…！"},{"id":"g","ja":"おーーい！"},{"id":"h","ja":"あ・な・た〜〜？"}]),
            ("voice",[{"id":"v","ja":"わ・た・し〜〜！","speaker":"younger","listener":"older"}]),
        ]
        if args.case!="all":cases=[case for case in cases if case[0]==args.case]
        plain=lambda text:re.sub(r"[\W_]+","",unicodedata.normalize("NFKC",text)).casefold()
        for name,regions in cases:
            regions=[bind_expression(r) for r in regions]
            original=[r["ja"] for r in regions]
            at=time.perf_counter();row={"name":name,"sources":regions}
            try:
                context={"characters":[{"kind":"relationship","confirmed":1,
                    "value":json.dumps(voice_record("younger","older","em","chị"))}]} if name=="voice" else {}
                items,metrics=translator.translate(regions,context,cancel)
                issues=translation_output_issues(regions,items)
                echoes=[item["id"] for item in items if plain(item["vi"])==plain(next(r["ja"] for r in regions if r["id"]==item["id"]))]
                fixture_checks={}
                if name=="transfer":
                    target={item["id"]:item["vi"].casefold() for item in items}
                    fixture_checks={"refusal_not_example_waiting":"không" in target["f"] and "đợi" not in target["f"],
                        "second_person_not_example_first_person":not re.search(r"t[ôo]?-?i",target["h"])}
                if name=="voice":fixture_checks={"confirmed_self_not_example_pronoun":"em" in plain(items[0]["vi"]) and "tô" not in plain(items[0]["vi"])}
                row.update(items=items,metrics=metrics,issues=issues,source_echo=echoes,fixture_checks=fixture_checks,
                           passed=not issues and not echoes and all(fixture_checks.values()))
            except AppError as error:row.update(passed=False,error=error.code)
            row["source_unchanged"]=original==[r["ja"] for r in regions]
            row["response_ms"]=(time.perf_counter()-at)*1000
            report["cases"].append(row)
            print(json.dumps(row,ensure_ascii=True),flush=True)
            if cancel.is_set():break
        report["passed"]=len(report["cases"])==len(cases) and all(row["passed"] and row["source_unchanged"] for row in report["cases"])
    except AppError as error:report["error"]=error.code
    finally:
        providers.post_json=post;timer.cancel();cancel.set();translator.stop()
        report["total_ms"]=(time.perf_counter()-started)*1000
        (directory/"result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({"passed":report["passed"],"evidence":str(directory/"result.json"),
                          "total_ms":report["total_ms"],"error":report.get("error")}),flush=True)
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
