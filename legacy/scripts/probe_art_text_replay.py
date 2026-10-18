"""Replay actual detector boxes through scope routing; no OCR/model/cloud.

Private pixels stay in RAM. This is a geometric replay, not independently
annotated semantic-role gold or a translation-quality certificate.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from benchmark import DirectoryDataset,audit,dataset_fingerprint
from manga_live.text_scope import make_plan,route_regions,story_regions,SCOPE_VERSION


def run(args):
    evidence_path=Path(args.evidence).resolve()
    if ROOT/"artifacts" not in evidence_path.parents:
        raise ValueError("Replay evidence must stay in private artifacts")
    report=json.loads(evidence_path.read_text(encoding="utf-8"))
    with DirectoryDataset(args.folder) as source:
        _,_,pages=audit(source);fingerprint=dataset_fingerprint(source)
    if fingerprint!=report["input_fingerprint_sha256"]:
        raise ValueError("Replay fingerprint differs from the audited source")
    matches=[(page,image) for page,image,_ in pages if page["page_id"]==args.page]
    if len(matches)!=1:raise ValueError("An eligible exact page ID is required")
    image=matches[0][1]
    rows=[row for row in report["pages"] if row["page"]==args.page]
    if len(rows)!=1:raise ValueError("Replay page missing or duplicated")
    regions=[r for r in rows[0]["regions"] if r["id"]==args.region]
    if len(regions)!=1:raise ValueError("Replay region missing or duplicated")
    # Do not replay an old routing decision as if it were a reader lock.
    region={k:v for k,v in regions[0].items() if k!="scope"}
    plan=make_plan(image,[region],fingerprint)
    routed=route_regions([region],plan,{})
    print(json.dumps({"scope_version":SCOPE_VERSION,"page":args.page,"region":args.region,
        "bbox":region["bbox"],"scope":routed[0]["scope"],
        "story_memory_admitted":bool(story_regions(routed)),
        "limitations":"Numeric geometry replay; source text labels are not semantic-role gold."},ensure_ascii=False))
    if args.assert_not_memory and story_regions(routed):raise SystemExit(2)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",required=True)
    parser.add_argument("--page",required=True)
    parser.add_argument("--region",required=True)
    parser.add_argument("--evidence",default=str(ROOT/"artifacts/private-pages-20261014-v16-post-candidate.json"))
    parser.add_argument("--assert-not-memory",action="store_true")
    run(parser.parse_args())
