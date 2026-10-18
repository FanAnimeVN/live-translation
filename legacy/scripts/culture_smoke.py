"""Real local cultural/grammar pilot, author-created text only, no cloud calls."""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading
import time
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from benchmark_cloud import cases
from manga_live.config import Config
from manga_live.linguistics import name_record
from manga_live.terminology import term_record
from manga_live.prompts import PROMPT_VERSION
from manga_live.errors import AppError
import manga_live.providers as providers


def culture_cases():
    selected=cases()
    names=[("kirito","キリト","Kirito"),("asura","アスラ","Asura")]
    for case in selected:
        if case["name"]=="fantasy_terms":
            case["context"]["glossary"]=[{"key":entity,"confirmed":1,"value":json.dumps(
                term_record(entity,category,source,target),ensure_ascii=False)}
                for entity,category,source,target in [("ice","skill","氷結結界","Băng Kết Kết Giới"),
                    ("potion","item","魔力回復薬","Thuốc Hồi Ma Lực")]]
        if case["name"] in ("source_address","no_added_suffix"):
            case["context"].setdefault("characters",[]).extend({"kind":"character","confirmed":1,"value":json.dumps(
                name_record(entity,[{"ja":source,"reading":target,"role":"given"}]),ensure_ascii=False)}
                for entity,source,target in names)
    full={"characters":[{"kind":"character","confirmed":1,"value":json.dumps(name_record("misaki",[
        {"ja":"田中美咲","reading":"Tanaka Misaki","role":"full"},
        {"ja":"美咲","reading":"Misaki","role":"given"},
        {"ja":"田中","reading":"Tanaka","role":"family"}]),ensure_ascii=False)}]}
    selected.append({"name":"name_switch","context":full,"regions":[
        {"id":"a","ja":"田中美咲さん、おはよう。"},
        {"id":"b","ja":"美咲って呼んでもいい？"},
        {"id":"c","ja":"美咲、待って！"}]})
    return selected


def run():
    parser=argparse.ArgumentParser();parser.add_argument("--output",default=str(ROOT/"artifacts/culture-smoke-v8.json"))
    args=parser.parse_args();destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
    selected=culture_cases()
    base_post=providers.post_json
    def seeded(url,body,*rest,**kwargs):return base_post(url,{**body,"seed":0},*rest,**kwargs)
    providers.post_json=seeded;rows=[]
    with tempfile.TemporaryDirectory(prefix="manga-culture-") as temporary:
        config=Config(temporary);translator=providers.Translator(config,None,ROOT/"models",ROOT/"runtime/llama")
        try:
            for case in selected:
                row={"case":case["name"],"source":case["regions"]};start=time.perf_counter()
                try:
                    items,metrics=translator.translate(case["regions"],case["context"],threading.Event())
                    row.update(ok=True,items=items,metrics=metrics)
                except AppError as error:row.update(ok=False,error=error.code)
                row["total_ms"]=(time.perf_counter()-start)*1000;rows.append(row)
                print(json.dumps(row,ensure_ascii=True),flush=True)
                destination.write_text(json.dumps({"source":"author-created Japanese text; real Hy-MT2 CPU",
                    "prompt_version":PROMPT_VERSION,"rows":rows,
                    "limits":["No images/browser time; first request includes model load.",
                              "Harness structural checks are not a semantic quality certificate; human review required."]},
                    ensure_ascii=False,indent=2),encoding="utf-8")
        finally:translator.stop();providers.post_json=base_post


if __name__=="__main__":run()
