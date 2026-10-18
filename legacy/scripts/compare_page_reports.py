"""Private, model-free comparison; never choose a production winner by CER alone."""
import argparse
import json
from pathlib import Path
from benchmark import ROOT, distance


def checked_pages(report):
    pages={}
    if not isinstance(report,dict) or not isinstance(report.get("pages"),list) or not report["pages"]:
        raise ValueError("Expected a nonempty page report")
    for page in report["pages"]:
        page_id=page.get("page")
        if not isinstance(page_id,str) or page_id in pages:
            raise ValueError("Missing or duplicated page identity")
        regions=page.get("regions",[])
        region_ids=[region.get("id") for region in regions]
        if any(not isinstance(value,str) for value in region_ids) or len(set(region_ids))!=len(region_ids):
            raise ValueError("Duplicated or missing region identity")
        labels={};used=set()
        for row in page.get("aligned",[]):
            key=row.get("id");ref=row.get("reference");pred=row.get("prediction")
            ids=row.get("region_ids")
            if (not isinstance(key,str) or key in labels or not isinstance(ref,str) or
                    not isinstance(pred,str) or not isinstance(ids,list) or
                    any(not isinstance(value,str) or value not in region_ids or value in used for value in ids) or
                    len(set(ids))!=len(ids)):
                raise ValueError("Invalid label/assignment identity")
            if row.get("characters")!=len(ref) or row.get("edits")!=distance(ref,pred):
                raise ValueError("Stored diagnostic counts disagree with text evidence")
            used.update(ids);labels[key]=row
        if not labels:raise ValueError("Page has no diagnostic annotations")
        pages[page_id]=(page,labels)
    return pages


def compare(baseline,candidate):
    fingerprint=baseline.get("input_fingerprint_sha256")
    if not fingerprint or fingerprint!=candidate.get("input_fingerprint_sha256"):
        raise ValueError("Dataset fingerprints differ; do not compare changed gold or images")
    before,after=checked_pages(baseline),checked_pages(candidate)
    if set(before)!=set(after):raise ValueError("Candidate page coverage differs")
    deltas=[];totals={"annotations":0,"characters":0,"baseline_edits":0,"candidate_edits":0,
                      "baseline_exact":0,"candidate_exact":0,"improved":0,"regressed":0,
                      "assigned_gained":0,"assigned_lost":0,"changed_same_edit_count":0}
    for page_id,(old_page,old_labels) in before.items():
        _,new_labels=after[page_id]
        if set(old_labels)!=set(new_labels):raise ValueError("Candidate annotation coverage differs")
        for key,old in old_labels.items():
            new=new_labels[key]
            if old["reference"]!=new["reference"]:
                raise ValueError("Reference changed; do not tune gold to match predictions")
            old_assigned,new_assigned=bool(old["region_ids"]),bool(new["region_ids"])
            change=new["edits"]-old["edits"]
            totals["annotations"]+=1;totals["characters"]+=old["characters"]
            totals["baseline_edits"]+=old["edits"];totals["candidate_edits"]+=new["edits"]
            totals["baseline_exact"]+=old["edits"]==0;totals["candidate_exact"]+=new["edits"]==0
            totals["improved"]+=change<0;totals["regressed"]+=change>0
            totals["assigned_gained"]+=not old_assigned and new_assigned
            totals["assigned_lost"]+=old_assigned and not new_assigned
            changed=old["prediction"]!=new["prediction"]
            totals["changed_same_edit_count"]+=changed and change==0
            if changed or old_assigned!=new_assigned:
                deltas.append({"page":page_id,"label":key,"before_edits":old["edits"],"after_edits":new["edits"],
                               "before_assigned":len(old["region_ids"]),"after_assigned":len(new["region_ids"]),
                               "changed_with_equal_edits":changed and change==0})
    for prefix in ("baseline","candidate"):
        totals[prefix+"_cer"]=totals[prefix+"_edits"]/max(1,totals["characters"])
        pages=before if prefix=="baseline" else after
        totals[prefix+"_regions"]=sum(len(page["regions"]) for page,_ in pages.values())
        totals[prefix+"_multi_region_labels"]=sum(len(row["region_ids"])>1 for _,labels in pages.values() for row in labels.values())
    return {"schema":1,"input_fingerprint_sha256":fingerprint,"cloud":False,"new_inference":False,
            "automatic_promotion":False,"aggregate":totals,"label_deltas":deltas,
            "limitations":["Normalized containment diagnostics only; assigned prediction is not true detector recall.",
                "Equal edit count can hide changed punctuation, names or meaning; changed strings still require review.",
                "No Vietnamese or clean-background gold; this report cannot certify translation/artwork quality."]}


def private_json_path(value,*,new=False):
    path=Path(value).resolve()
    if ROOT/"artifacts" not in path.parents or path.suffix!=".json":
        raise ValueError("Private evidence must stay in artifacts as JSON")
    if new and path.exists():raise ValueError("Do not overwrite recorded evidence")
    if not new and path.stat().st_size>16*1024*1024:raise ValueError("Evidence exceeds its bound")
    return path


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--baseline",required=True);parser.add_argument("--candidate",required=True)
    parser.add_argument("--output",required=True);args=parser.parse_args()
    output=private_json_path(args.output,new=True)
    reports=[]
    for value in (args.baseline,args.candidate):
        reports.append(json.loads(private_json_path(value).read_text(encoding="utf-8")))
    result=compare(*reports)
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as destination:
        json.dump(result,destination,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps(result["aggregate"],indent=2))  # No story text in terminal logs.


if __name__=="__main__":main()
