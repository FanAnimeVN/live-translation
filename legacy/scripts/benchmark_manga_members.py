"""Offline manga-ocr on retained individual detector lines, not a new default.

The unchanged source polygon -> axis-aligned 2px source halo -> manga-ocr ->
source-fragment precedence-v2 recipe separates recognizer from crop/grouping.
No gold hints, text splicing, glyph mask, erasure or semantic authority.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"scripts"),str(ROOT/"companion")]
from benchmark import DirectoryDataset,audit,dataset_fingerprint
from compare_page_reports import checked_pages,compare,private_json_path
from benchmark_pages import assign_to_labels
from benchmark_baberu_probe import recognize_source_members,reorder_recorded_members,replay_recorded_report
from benchmark_hayai_nova import offline_guard
from benchmark_mit48 import require_memory,system_memory
from benchmark_paddle_rec import process_memory
from probe_recorded_source_union import group_recorded_sources
from manga_live.ocr import MangaEngine
from provision import verify

VERSION="manga-ocr-retained-members-axis-halo2-source-order-v1"


def verified_engine(threads):
    spec=json.loads((ROOT/"models.lock.json").read_text(encoding="utf-8"))["ocr"]
    if not all(verify(ROOT/"models/ocr"/name,check) for name,check in spec["files"].items()):
        raise ValueError("Missing/mismatched locked manga-ocr assets; no inference download")
    return MangaEngine(ROOT/"models/ocr",threads)


def replay_order(args,*,source_factory=DirectoryDataset):
    output=private_json_path(args.output,new=True)
    content=private_json_path(args.reorder_from).read_bytes()
    recorded=json.loads(content)
    if recorded.get("version")!=VERSION or recorded.get("ocr")!=MangaEngine.name:
        raise ValueError("Original complete manga-member experiment required")
    before=checked_pages(recorded)
    with source_factory(args.folder) as source:
        counts,issues,pages=audit(source)
        fingerprint=dataset_fingerprint(source)
    for page,image,_ in pages:
        if page["page_id"] not in before:raise ValueError("Incomplete source coverage")
        group_recorded_sources(image,before[page["page_id"]][0]["regions"],[],
                               page=page["page_id"],primary_anchored=True)
    report=replay_recorded_report(recorded,pages,fingerprint,directional_votes=True)
    report.update(version=VERSION+"-direction-votes-v3",source_records=deepcopy(recorded["source_records"]),
                  source_report_sha256=hashlib.sha256(content).hexdigest(),counts=counts,audit=issues,
                  fresh_text_detection=False,fresh_recognition=False)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({"aggregate":report["aggregate"],"comparison":report["comparison"]["aggregate"]}),flush=True)
    return report


def run(args,*,source_factory=DirectoryDataset,engine_factory=verified_engine):
    output=private_json_path(args.output,new=True)
    content=private_json_path(args.primary).read_bytes()
    parent=json.loads(content)
    if (parent.get("cloud") is not False or parent.get("fresh_inference") is not True
            or parent.get("complete") is False or parent.get("ocr")!=MangaEngine.name):
        raise ValueError("Complete offline same-recognizer control required")
    if type(args.threads) is not int or not 1<=args.threads<=4:
        raise ValueError("Bounded threads required")
    recorded=checked_pages(parent)
    with source_factory(args.folder) as source:
        counts,issues,pages=audit(source)
        fingerprint=dataset_fingerprint(source)
    if (parent.get("input_fingerprint_sha256")!=fingerprint or
            set(recorded)!={p[0]["page_id"] for p in pages}):
        raise ValueError("Matching complete source fingerprint/coverage required")
    # Validate ALL original geometry/scores/exclusions before a model is loaded.
    # This shared validator's proposed groups are deliberately not used here.
    for page,image,_ in pages:
        group_recorded_sources(image,recorded[page["page_id"]][0]["regions"],[],
                               page=page["page_id"],primary_anchored=True)
    require_memory()
    with offline_guard():
        engine=engine_factory(args.threads)
        started=time.perf_counter();engine.load()
    report={"schema":1,"version":VERSION,"ocr":MangaEngine.name,"threads":args.threads,
        "cloud":False,"images_persisted":False,"production_default":False,"complete":False,
        "fresh_inference":True,"fresh_text_detection":False,"fresh_recognition":True,
        "input_fingerprint_sha256":fingerprint,"source_report_sha256":hashlib.sha256(content).hexdigest(),
        "crop_recipe":"source-members-axis-halo2-rtl-v1",
        "reading_order_recipe":"source-fragment-precedence-v2",
        "counts":counts,"audit":issues,"recognizer_load_ms":(time.perf_counter()-started)*1000,
        "source_records":deepcopy(parent["pages"]),"resource_start":system_memory(),"pages":[],
        "limitations":["Retained detector proposals, not fresh detection or upstream full-pipeline parity.",
            "Unreviewed Japanese development labels, not independent semantic/artwork or held-out gold.",
            "Line crops can cut furigana/expression or duplicate overlaps; preserve raw evidence for review.",
            "No erasure/memory authority; original source members/bindings never migrate.",
            "Stage timings and one process peak are not live p95 or total/system RAM."]}
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as stream:
        json.dump(report,stream,ensure_ascii=False,indent=2,allow_nan=False)
    def persist():
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False),encoding="utf-8")
    for page,image,labels in pages:
        original=recorded[page["page_id"]][0]
        regions=[]
        started=time.perf_counter()
        for source_region in original["regions"]:
            with offline_guard():
                raw=recognize_source_members(engine,image,source_region)
            region=reorder_recorded_members(raw)
            region.pop("vi",None)
            region.update(review=True,memory_authority=False,erasure_authority=False,
                          reviewReasons=list(dict.fromkeys([*region.get("reviewReasons",[]),"member_ocr_experiment"])))
            if isinstance(region.get("scope"),dict):region["scope"]["memory"]=False
            regions.append(region)
        elapsed=(time.perf_counter()-started)*1000
        aligned,unmatched=assign_to_labels(labels,regions)
        report["pages"].append({"page":page["page_id"],"regions":regions,"aligned":aligned,
            "unmatched_prediction_ids":unmatched,"ocr_and_order_ms":elapsed})
        report["process_memory"]=process_memory()
        report["process_memory"]["scope"]="recognizer/imports/RAM crops; retained source reports, no detector loaded"
        persist()
        print(json.dumps({"page":page["page_id"],"regions":len(regions),
            "members":sum(len(r["member_readings"]) for r in regions)}),flush=True)
    rows=[r for p in report["pages"] for r in p["aligned"]]
    report["aggregate"]={"annotations":len(rows),"exact":sum(r["edits"]==0 for r in rows),
        "edits":sum(r["edits"] for r in rows),"characters":sum(r["characters"] for r in rows),
        "regions":sum(len(p["regions"]) for p in report["pages"]),
        "members":sum(len(r["member_readings"]) for p in report["pages"] for r in p["regions"])}
    report["paired_primary"]=compare(parent,report)
    report["complete"]=True
    persist()
    print(json.dumps({"aggregate":report["aggregate"],"paired_primary":report["paired_primary"]["aggregate"]}),flush=True)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder",required=True)
    inputs=parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--primary")
    inputs.add_argument("--reorder-from",help="Source-direction-v3 replay, no inference or cloud call")
    parser.add_argument("--output",required=True)
    parser.add_argument("--threads",type=int,choices=range(1,5),default=2)
    parser.add_argument("--max-seconds",type=int,choices=range(30,1801),default=600)
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args=parser.parse_args()
    if args.reorder_from:replay_order(args)
    elif args.worker:run(args)
    else:
        require_memory()
        subprocess.run([sys.executable,str(Path(__file__).resolve()),*sys.argv[1:],"--worker"],
                       check=True,timeout=args.max_seconds)


if __name__=="__main__":main()
