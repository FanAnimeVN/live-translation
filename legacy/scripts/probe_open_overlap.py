"""Narrow grouping candidate: model-free recorded-input replay or fresh OCR.

No private images/patches are written, no cloud, no production default change.
Replay checks current default geometry before reusing previously measured
predictions for exactly identical crops. It is not a fresh inference benchmark.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from benchmark import dataset_source,audit,dataset_fingerprint
from benchmark_pages import assign_to_labels,hashlib_image
from manga_live.ocr import group_regions,PaddleDetector,LAYOUT_VERSION
from manga_live.text_scope import make_plan,route_regions,SCOPE_VERSION

VERSION="balloon-mask-v18-open-overlap-candidate"
OVERLAP20_VERSION="balloon-mask-v19-open-overlap20-candidate"


def records_by_box(regions):
    result={}
    for region in regions:
        box=region.get("bbox")
        if (not isinstance(box,list) or len(box)!=4 or any(type(v) not in (int,float) for v in box)
                or tuple(box) in result or not isinstance(region.get("ja"),str)):
            raise ValueError("Ambiguous/missing recorded crop prediction")
        result[tuple(box)]=region
    return result


def select_recorded_predictions(image,detections,reference,candidate,minimum_open_overlap=.3):
    """No label/text-guided routing; select by source geometry alone."""
    current=group_regions(image,detections)
    if [(r["bbox"],r["overlay"]) for r in current]!=[(r["bbox"],r["overlay"]) for r in reference]:
        raise ValueError("Replayed default geometry differs from actual baseline")
    baseline=records_by_box(reference);changed=records_by_box(candidate)
    proposed=group_regions(image,detections,experimental_open_overlap=True,minimum_open_overlap=minimum_open_overlap)
    result=[];provenance=[]
    for region in proposed:
        box=tuple(region["bbox"])
        origin="baseline" if box in baseline else "v17-candidate"
        record=(baseline if box in baseline else changed).get(box)
        if record is None or record.get("overlay")!=region["overlay"]:
            raise ValueError("New crop has no matching previously measured input; fresh OCR required")
        # Preserve actual recorded review flags too. A dummy detector score
        # must never turn a low-confidence transcription into trusted output.
        result.append({**region,"ja":record["ja"],"review":bool(region.get("review") or record.get("review"))})
        provenance.append({"id":region["id"],"bbox":region["bbox"],"record":origin})
    return result,provenance


def read_evidence(path):
    path=Path(path).resolve()
    if ROOT/"artifacts" not in path.parents or path.stat().st_size>16*1024*1024:
        raise ValueError("Private replay evidence must be bounded and gitignored")
    return json.loads(path.read_text(encoding="utf-8"))


def replay(args):
    reference=read_evidence(args.reference);candidate=read_evidence(args.candidate);geometry=read_evidence(args.geometry)
    with dataset_source(args) as source:
        counts,issues,pages=audit(source);fingerprint=dataset_fingerprint(source)
    if any(r.get("input_fingerprint_sha256")!=fingerprint for r in (reference,candidate,geometry)):
        raise ValueError("Recorded inputs differ from the private source")
    if reference.get("layout_version")!=LAYOUT_VERSION or candidate.get("layout_version")!="balloon-mask-v17-aligned-open-text-experiment":
        raise ValueError("Unexpected recorded grouping versions")
    fraction=getattr(args,"overlap_fraction",.3)
    report={"schema":1,"layout_version":OVERLAP20_VERSION if fraction==.2 else VERSION,"minimum_open_overlap":fraction,"production_default":False,"fresh_inference":False,
        "cloud":False,"image_persistence":False,"input_fingerprint_sha256":fingerprint,"counts":counts,"audit":issues,
        "scope_version":SCOPE_VERSION,"pages":[],"limitations":[
        "Model-free geometry replay using exact crop predictions from past actual runs; no fresh OCR or timing.",
        "Recorded detector polygons use placeholder scores; grouping must match current baseline before reuse.",
        "Original labels are unaudited and incomplete. No translation or clean-background acceptance."]}
    for page,image,bubbles in pages:
        page_id=page["page_id"]
        rows=[next((p for p in r["pages"] if p["page"]==page_id),None) for r in (reference,candidate,geometry)]
        if any(row is None for row in rows):raise ValueError("Missing eligible page evidence")
        baseline_row,candidate_row,geometry_row=rows
        # The recorded line recognizer used the same full-page PP detector;
        # these are original page coordinates, never redetected label crops.
        detections=[];seen=set()
        for block in geometry_row["line_results"]:
            for line in block["lines"]:
                key=tuple(tuple(point) for point in line["polygon"])
                if key in seen:raise ValueError("Duplicated recorded detector geometry")
                seen.add(key);detections.append({"polygon":deepcopy(line["polygon"]),"score":1.})
        regions,provenance=select_recorded_predictions(image,detections,baseline_row["regions"],candidate_row["regions"],fraction)
        regions=route_regions(regions,make_plan(image,regions,hashlib_image(image)),{})
        aligned,unmatched=assign_to_labels(bubbles,regions)
        row={"page":page_id,"regions":[{k:r[k] for k in ("id","bbox","order","ja","overlay","review","scope") if k in r} for r in regions],
            "aligned":aligned,"unmatched_prediction_ids":unmatched,"provenance":provenance}
        report["pages"].append(row)
        print(json.dumps({"page":page_id,"baseline_regions":len(baseline_row["regions"]),"regions":len(regions),
            "reused_new_crops":sum(p["record"]!="baseline" for p in provenance)}),flush=True)
    aligned=[r for p in report["pages"] for r in p["aligned"]]
    report["aggregate"]={"annotations":len(aligned),"aligned":sum(bool(r["region_ids"]) for r in aligned),
        "exact":sum(r["edits"]==0 for r in aligned),"edits":sum(r["edits"] for r in aligned),
        "characters":sum(r["characters"] for r in aligned),"regions":sum(len(p["regions"]) for p in report["pages"])}
    output=Path(args.output).resolve()
    if ROOT/"artifacts" not in output.parents:raise ValueError("Private output must be in artifacts")
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report["aggregate"],indent=2))


class OverlapDetector:
    name=PaddleDetector.name
    grouping_version=VERSION
    def __init__(self,threads,fraction=.3):
        self.detector=PaddleDetector(ROOT/"models/detector",threads)
        self.fraction=fraction;self.grouping_version=OVERLAP20_VERSION if fraction==.2 else VERSION
        self.details={"kind":"open-overlap-grouping-only","production_default":False,"grouping_version":self.grouping_version,"minimum_open_overlap":fraction}
    def detect(self,image):
        raw=self.detector.detect_raw(image)
        regions=group_regions(image,raw,experimental_open_overlap=True,minimum_open_overlap=self.fraction,
                              include_source_members=True)
        self.last_evidence={"raw_line_count":len(raw),"grouped_count":len(regions),
            "raw_detections":deepcopy(raw),
            "groups":[{k:deepcopy(r[k]) for k in ("id","bbox","sourceMembers")} for r in regions]}
        return regions


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--folder",required=True)
    parser.add_argument("--infer",action="store_true");parser.add_argument("--threads",type=int,default=4)
    parser.add_argument("--overlap-fraction",type=float,choices=(.2,.3),default=.3,help="Bounded geometry comparator; no runtime setting")
    parser.add_argument("--reference",default=str(ROOT/"artifacts/private-pages-20261014-local-v3-contract.json"))
    parser.add_argument("--candidate",default=str(ROOT/"artifacts/private-pages-20261014-v17-aligned-candidate.json"))
    parser.add_argument("--geometry",default=str(ROOT/"artifacts/private-paddle-rec-pages-20261014.json"))
    parser.add_argument("--output",required=True);args=parser.parse_args()
    if args.infer:
        from benchmark_pages import run
        run(args,detector_override=OverlapDetector(args.threads,args.overlap_fraction))
    else:replay(args)


if __name__=="__main__":main()
