"""Offline context replay of recorded OCR text; never loads images or a model.

Each source page is an independent simulated read-cache fixture, NOT a shared
story/chapter. No reference labels are inspected and no real reading progress
or persistent reader memory is changed. Numeric/private evidence only.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from manga_live.memory import Memory,bounded,encode
from manga_live.text_scope import story_regions
from compare_page_reports import private_json_path


def replay(report):
    pages=report.get("pages")
    if report.get("cloud") is not False or not isinstance(pages,list) or not 1<=len(pages)<=100:
        raise ValueError("Bounded offline recorded page report required")
    rows=[];page_ids=set()
    memory=Memory(":memory:")
    try:
        for index,page in enumerate(pages):
            page_id=page.get("page")
            regions=page.get("regions")
            if (not isinstance(page_id,str) or page_id in page_ids or
                    not isinstance(regions,list) or len(regions)>512):
                raise ValueError("Unique bounded source pages required")
            page_ids.add(page_id)
            if any(not isinstance(r,dict) or not isinstance(r.get("id"),str) or
                   not isinstance(r.get("ja"),str) for r in regions):
                raise ValueError("Source IDs and exact OCR strings required")
            by_id={r["id"]:r for r in regions}
            if len(by_id)!=len(regions):raise ValueError("Duplicate source IDs")
            # Do not assert these unrelated dataset pages are one real story.
            story=f"cache-fixture-{index}"
            memory.ensure_story(story,"Independent cache replay")
            at={"chapter":1,"page":1}
            memory.save_page(story,page_id,at,"recorded",regions,state="read")
            current=memory.context(story,{"chapter":1,"page":2})["data"]["recent_dialogue"]
            legacy=bounded(story_regions(regions)[-18:],500)
            positions={r["id"]:i for i,r in enumerate(regions)}
            ordered=[positions[r["id"]] for r in current]
            text_exact=all(all(row.get(key)==by_id[row["id"]].get(key)
                for key in ("ja","vi","speaker","listener","type")) for row in current)
            rows.append({"page":page_id,"source_regions":len(regions),
                "eligible_regions":len(story_regions(regions)),
                "legacy_retained":len(legacy),"current_retained":len(current),
                "legacy_bytes":len(encode(legacy).encode("utf-8")),
                "current_bytes":len(encode(current).encode("utf-8")),
                "source_records_unchanged":memory.page(story,page_id,"recorded")["regions"]==regions,
                "all_retained_text_exact":text_exact,
                "all_reading_order_preserved":ordered==sorted(ordered),
                "all_current_page_excluded":not memory.context(story,at)["data"]["recent_dialogue"]})
    finally:memory.close()
    return {"schema":1,"cloud":False,"fresh_inference":False,"images_loaded":False,
        "aggregate":{"pages":len(rows),
            "legacy_retained":sum(r["legacy_retained"] for r in rows),
            "current_retained":sum(r["current_retained"] for r in rows),
            **{key:all(r[key] for r in rows) for key in (
                "source_records_unchanged","all_retained_text_exact",
                "all_reading_order_preserved","all_current_page_excluded")}},
        "rows":rows,
        "limitations":["Independent per-page simulated read-cache fixtures, not actual chapter chronology.",
            "Recorded unreviewed OCR, not Japanese/Vietnamese semantic ground truth or a translation-quality score.",
            "No image/model inference, provider requests, live latency or reader-memory writes.",
            "Aggregate retention is byte-budget behavior, not proof all important context is recalled."]}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source",required=True)
    parser.add_argument("--output",required=True)
    args=parser.parse_args()
    destination=private_json_path(args.output,new=True)
    content=private_json_path(args.source).read_bytes()
    report=json.loads(content)
    result=replay(report)
    result.update(source_report_sha256=hashlib.sha256(content).hexdigest(),
                  input_fingerprint_sha256=report.get("input_fingerprint_sha256"))
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(result["aggregate"],allow_nan=False))


if __name__=="__main__":main()
