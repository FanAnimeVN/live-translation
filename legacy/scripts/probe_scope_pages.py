"""Replay scope policy on unchanged local OCR evidence; no inference/cloud.

Pixels stay in RAM. Scope flags are not semantic-role gold and this replay
does not measure OCR improvement, translation quality or background fidelity.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from benchmark import DirectoryDataset,audit,dataset_fingerprint
from benchmark_pages import assign_to_labels,hashlib_image
from manga_live.text_scope import make_plan,route_regions,SCOPE_VERSION


def compare_page(image,bubbles,row):
    source=[{k:v for k,v in region.items() if k!="scope"} for region in row["regions"]]
    started=time.perf_counter()
    routed=route_regions(source,make_plan(image,source,hashlib_image(image)),{})
    elapsed=(time.perf_counter()-started)*1000
    stable=all(all(a.get(k)==b.get(k) for k in ("id","bbox","ja","order","overlay","balloon"))
               for a,b in zip(source,routed)) and len(source)==len(routed)
    aligned,unmatched=assign_to_labels(bubbles,routed)
    alignment_stable=aligned==row["aligned"] and unmatched==row["unmatched_prediction_ids"]
    flagged=[]
    for region in routed:
        if region["scope"]["reason"]!="visual_review":continue
        flagged.append({"id":region["id"],"bbox":region["bbox"],"scope":region["scope"],
            "aligned_labels":[label["id"] for label in aligned if region["id"] in label["region_ids"]]})
    return {"page":row["page"],"region_count":len(routed),"scope_replay_ms":elapsed,
        "source_geometry_text_order_unchanged":stable,"alignment_unchanged":alignment_stable,
        "deferred_ids":[r["id"] for r in routed if r["scope"]["action"]=="defer"],"flagged":flagged}


def run(args):
    evidence=Path(args.evidence).resolve();destination=Path(args.output).resolve()
    if any(ROOT/"artifacts" not in path.parents for path in (evidence,destination)):
        raise ValueError("Replay inputs and diagnostics must remain private")
    report=json.loads(evidence.read_text(encoding="utf-8"))
    with DirectoryDataset(args.folder) as source:
        _,_,pages=audit(source);fingerprint=dataset_fingerprint(source)
    if fingerprint!=report["input_fingerprint_sha256"]:raise ValueError("Dataset fingerprint mismatch")
    rows={row["page"]:row for row in report["pages"]}
    if len(rows)!=len(report["pages"]) or set(rows)!={page["page_id"] for page,_,_ in pages}:
        raise ValueError("Exact eligible page coverage required")
    result={"scope_version":SCOPE_VERSION,"input_fingerprint_sha256":fingerprint,"cloud":False,
        "inference_rerun":False,"semantic_role_ground_truth":False,
        "limitations":"Routing replay only; original OCR/source/gold unchanged. No semantic or translation grading.",
        "pages":[compare_page(image,bubbles,rows[page["page_id"]]) for page,image,bubbles in pages]}
    result["aggregate"]={"pages":len(result["pages"]),"regions":sum(r["region_count"] for r in result["pages"]),
        "flagged":sum(len(r["flagged"]) for r in result["pages"]),
        "source_and_alignment_unchanged":all(r["source_geometry_text_order_unchanged"] and r["alignment_unchanged"] for r in result["pages"])}
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"scope_version":SCOPE_VERSION,**result["aggregate"],"flags":[
        {"page":row["page"],**flag} for row in result["pages"] for flag in row["flagged"]]},ensure_ascii=False))
    if not result["aggregate"]["source_and_alignment_unchanged"]:raise SystemExit(2)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",required=True)
    parser.add_argument("--evidence",default=str(ROOT/"artifacts/private-pages-20261014-v16-post-candidate.json"))
    parser.add_argument("--output",default=str(ROOT/"artifacts/private-scope-review-20261014.json"))
    run(parser.parse_args())
