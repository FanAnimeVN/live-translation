"""Real CPU prompt comparison on synthetic dialogue, not quality certification."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from benchmark_cloud import cases
from manga_live.config import Config
from manga_live.errors import AppError
from manga_live.terminology import term_record
from manga_live.prompts import compact_prompt,focused_compact_prompt
import manga_live.providers as providers


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repeats",type=int,choices=range(1,4),default=1)
    parser.add_argument("--engine",choices=("hy-mt2","qwen"),default="hy-mt2")
    parser.add_argument("--output",default=str(ROOT/"artifacts/local-prompt-comparison.json"))
    args=parser.parse_args();rows=[]
    destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
    testcases=cases()
    for case in testcases:
        # Use the real canonical-memory format; older benchmark text was only
        # a prompt hint, not a post-generation consistency constraint.
        if case["name"]=="fantasy_terms":
            case["context"]["glossary"]=[{"key":"ice","confirmed":1,"value":json.dumps(term_record("ice","skill","氷結結界","Băng Kết Kết Giới"),ensure_ascii=False)},
                {"key":"potion","confirmed":1,"value":json.dumps(term_record("potion","item","魔力回復薬","Thuốc Hồi Ma Lực"),ensure_ascii=False)}]
        if case["name"]=="siblings":case["regions"][0]["ja"]="「"+case["regions"][0]["ja"]
    base_post=providers.post_json;base_prompt=providers.compact_prompt
    with tempfile.TemporaryDirectory(prefix="manga-local-prompt-") as temporary:
        config=Config(temporary);config.update({"mode":"offline"})
        translator=providers.Translator(config,None,ROOT/"models",ROOT/"runtime/llama")
        if args.engine=="qwen":
            translator.local=translator.summary_worker
        try:
            start=time.perf_counter();translator.local.start(threading.Event());load_ms=(time.perf_counter()-start)*1000
            for repeat in range(args.repeats):
                for case in testcases:
                    # Alternate order across cases/repeats to limit warm-prefix bias.
                    variants=[("current",compact_prompt),("focused",focused_compact_prompt)]
                    if (repeat+testcases.index(case))%2:variants.reverse()
                    for name,prompt in variants:
                        def seeded(url,body,*rest,**kwargs):return base_post(url,{**body,"seed":repeat},*rest,**kwargs)
                        providers.post_json=seeded;providers.compact_prompt=prompt
                        row={"variant":name,"case":case["name"],"seed":repeat}
                        start=time.perf_counter()
                        try:
                            items,metrics=translator.translate(case["regions"],case["context"],threading.Event())
                            row.update(ok=True,items=items,metrics=metrics)
                        except AppError as error:row.update(ok=False,error=error.code)
                        row["response_ms"]=(time.perf_counter()-start)*1000;rows.append(row)
                        print(json.dumps(row,ensure_ascii=True),flush=True)
                        report={"source":"author-created dialogue; real local CPU; no cloud calls","engine":args.engine,
                            "load_ms":load_ms,"rows":rows,
                            "limitations":["Small non-blind pilot; inspect semantic errors, not only schema pass.","No browser/OCR time or representative p95."]}
                        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            for name in ("current","focused"):
                accepted=[r for r in rows if r["variant"]==name and r["ok"]]
                print(json.dumps({"variant":name,"success":len(accepted),"total":len(rows)//2,
                    "median_ms":statistics.median(r["response_ms"] for r in accepted) if accepted else None,
                    "mean_input_tokens":statistics.mean(r["metrics"]["usage"].get("prompt_tokens",0) for r in accepted) if accepted else None},ensure_ascii=True),flush=True)
        finally:
            providers.post_json=base_post;providers.compact_prompt=base_prompt;translator.stop()


if __name__=="__main__":main()
