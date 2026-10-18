"""Paired real Qwen prompt pilot. Narrow regression checks, not blind grading."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.config import Config
from manga_live.providers import Translator
import manga_live.providers as providers
from manga_live.prompts import SUMMARY_RULES,evidence_summary_prompt,summary_schema
from manga_live.validation import parse_model_json

CASES=[("siblings",[
    {"id":"r0","ja":"姉ちゃん、まだ帰らないの？","vi":"Nee-chan, chưa về à?"},
    {"id":"r1","ja":"先に帰ってて。あとで行くから。","vi":"Cứ về trước đi. Lát nữa sẽ đi."}],
    ["nee-chan hỏi","đã về","đã trở về"]),
    ("permission",[{"id":"r0","ja":"明日は来なくてもいい。","vi":"Ngày mai không cần đến đâu."}],
    ["không được đến","cấm đến","đã không đến"]),
    ("future_request",[
    {"id":"r0","ja":"田中さん、明日の会議には出てください。","vi":"Tanaka-san, ngày mai hãy tham dự cuộc họp."},
    {"id":"r1","ja":"まだ決めていません。","vi":"Vẫn chưa quyết định."}],
    ["tanaka-san yêu cầu","tanaka yêu cầu","đã tham dự","đã quyết định tham dự"])]


def main():
    base_post=providers.post_json;rows=[]
    with tempfile.TemporaryDirectory(prefix="manga-summary-pilot-") as temporary:
        translator=Translator(Config(temporary),None,ROOT/"models",ROOT/"runtime/llama")
        try:
            translator.summary_worker.start(threading.Event())
            for index,(name,regions,forbidden) in enumerate(CASES):
                variants=[("current",SUMMARY_RULES+"\n"+json.dumps(regions,ensure_ascii=False)),
                    ("evidence",evidence_summary_prompt(regions))]
                if index%2:variants.reverse()
                for variant,prompt in variants:
                    providers.post_json=lambda url,body,*args,**kwargs:base_post(url,{**body,"seed":0},*args,**kwargs)
                    start=time.perf_counter()
                    raw,usage=translator.summary_worker.generate(prompt,threading.Event(),summary_schema([r["id"] for r in regions]),max_tokens=700)
                    parsed=parse_model_json(raw);content=json.dumps(parsed,ensure_ascii=False).lower()
                    row={"case":name,"variant":variant,"ms":(time.perf_counter()-start)*1000,"raw":parsed,"usage":usage,
                        "suspected_errors":[word for word in forbidden if word in content]}
                    rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
                    report={"source":"author-created dialogue; real local Qwen Q4 CPU","seed":0,"rows":rows,
                        "limits":["Three synthetic cases and lexical error flags are not complete semantic grading.",
                            "Review questions, addressee/speaker, tense and modality manually; do not count JSON success as semantic success."]}
                    destination=ROOT/"artifacts/summary-prompt-pilot.json";destination.parent.mkdir(parents=True,exist_ok=True)
                    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        finally:providers.post_json=base_post;translator.stop()


if __name__=="__main__":main()
