"""Unaccepted source-preserving multi-scale recovery, using recorded inference.

Never replace a baseline crop, join new lines into its dialogue, infer a
speaker or grant erasure/memory. Disjoint candidates are review proposals,
not a new companion setting. Source audit uses RAM images only; no raster is
persisted, no detector/OCR is run and no API is called by this replay.
"""
import argparse
from copy import deepcopy
import json
import math
from benchmark_pages import intersection,assign_to_labels
from benchmark import dataset_source,audit,dataset_fingerprint,ROOT
from compare_page_reports import compare,private_json_path


VERSION="disjoint-multiscale-recovery-v1-candidate"


def checked_box(region):
    box=region.get("bbox")
    if (not isinstance(box,list) or len(box)!=4 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in box) or
            min(box[:2])<0 or min(box[2:])<=0):
        raise ValueError("Recovery needs finite positive source geometry")
    return box


def recovery_proposals(primary,secondary,*,max_added=8,exclusion_boxes=()):
    if type(max_added) is not int or not 1<=max_added<=8:raise ValueError("Bounded recovery budget required")
    if len(primary)>64 or len(secondary)>64:raise ValueError("Page exceeds bounded region budget")
    capacity=min(max_added,64-len(primary))
    protected=[checked_box(r) for r in primary]+[checked_box({"bbox":box}) for box in exclusion_boxes]
    result=deepcopy(primary);decisions=[]
    ids={r["id"] for r in primary};added=0
    if len(ids)!=len(primary):raise ValueError("Duplicate primary source identity")
    for candidate in secondary:
        box=checked_box(candidate);scope=candidate.get("scope",{})
        reason=("reader_owned" if scope.get("reason")=="reader" or
                any(candidate.get(key,"unknown")!="unknown" for key in ("speaker","listener")) else
                "overlaps_source_or_exclusion" if any(intersection(box,other)>0 for other in protected) else
                "budget_deferred" if added>=capacity else "review_proposal")
        decisions.append({"source_id":candidate["id"],"reason":reason})
        if reason!="review_proposal":continue
        # These are unverified secondary proposals, not auto-visible dialogue.
        # Keep source intact and defer for review, never call it irrelevant.
        # Any explicit reader choice was already excluded from this comparator.
        proposal=deepcopy(candidate);new_id="recovery-"+candidate["id"]
        if new_id in ids:raise ValueError("Recovery source identity collision")
        ids.add(new_id);proposal.update(id=new_id,overlay="label",review=True,
            order=max((r.get("order",0) for r in result),default=-1)+1,
            speaker="unknown",listener="unknown",erasure_permitted=False)
        proposal.pop("balloon",None)
        proposal["reviewReasons"]=list(dict.fromkeys([*candidate.get("reviewReasons",[]),"multi_scale_recovery"]))
        proposal["scope"]={**scope,"role":"unknown","action":"defer","reason":"visual_review","memory":False}
        proposal["recoverySourceId"]=candidate["id"]
        result.append(proposal);protected.append(box);added+=1
    return result,decisions


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",required=True);parser.add_argument("--baseline",required=True)
    parser.add_argument("--candidate",required=True);parser.add_argument("--output",required=True)
    args=parser.parse_args();output=private_json_path(args.output,new=True)
    baseline=json.loads(private_json_path(args.baseline).read_text(encoding="utf-8"))
    candidate=json.loads(private_json_path(args.candidate).read_text(encoding="utf-8"))
    compare(baseline,candidate)  # Fail closed on mixed source/gold/coverage.
    for key in ("ocr","layout_version","scope_version","ocr_partition_version"):
        if baseline.get(key)!=candidate.get(key):raise ValueError("Recovery comparison must change detector scale only")
    details=candidate.get("experimental_detector",{})
    if (candidate.get("fresh_inference") is not True or candidate.get("production_default") is not False or
            candidate.get("cloud") is not False or details.get("kind")!="pp-resize-only" or
            details.get("limit_type")!="resize_long"):
        raise ValueError("Need measured explicit long-edge comparator, not a guessed higher resolution")
    with dataset_source(args) as source:
        counts,issues,pages=audit(source);fingerprint=dataset_fingerprint(source)
    if fingerprint!=baseline.get("input_fingerprint_sha256"):raise ValueError("Source changed since inference")
    sources={p["page_id"]:(image,bubbles) for p,image,bubbles in pages}
    # Reuse the strict exact-member validator: learned/grouped boxes are not
    # permission to fabricate source members, scores or off-image geometry.
    from probe_member_preserving_grouping import validate_pages
    validate_pages(candidate,{p["page_id"]:(p,image,bubbles) for p,image,bubbles in pages})
    result={"schema":1,"version":VERSION,"input_fingerprint_sha256":fingerprint,
            "counts":counts,"audit":issues,"production_default":False,"fresh_inference":False,
            "cloud":False,"image_persistence":False,"pages":[],
            "limitations":["Replay of two recorded actual detector/OCR runs; no new inference or timing.",
                "Primary source records/anchors/order untouched; new proposals are appended, not a validated reading order.",
                "Disjoint boxes do not prove relevance, OCR correctness, semantic ownership or safe erasure.",
                "Extra detector pass has a latency cost; no claim of real-time or automatic promotion."]}
    for old in baseline["pages"]:
        high=next(p for p in candidate["pages"] if p["page"]==old["page"])
        regions,decisions=recovery_proposals(old["regions"],high["regions"])
        _,bubbles=sources[old["page"]]
        aligned,unmatched=assign_to_labels(bubbles,regions)
        result["pages"].append({"page":old["page"],"regions":regions,"aligned":aligned,
                                "unmatched_prediction_ids":unmatched,"recovery_decisions":decisions})
    result["comparison"]=compare(baseline,result)
    with output.open("x",encoding="utf-8") as destination:
        json.dump(result,destination,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(result["comparison"]["aggregate"],indent=2))


if __name__=="__main__":main()
