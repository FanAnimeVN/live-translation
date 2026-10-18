"""Rebuild transient cleanup for a provenance-checked private reader replay.

No OCR/LLM/network, no image or patch file output. Stdout is a bounded local
pipe to the renderer harness, not an application log or release artifact.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from benchmark import DirectoryDataset,audit,dataset_fingerprint
from manga_live.render_cleanup import render_patch,MAX_JOB_PATCH_BYTES
from manga_live.text_scope import make_plan,route_regions,SCOPE_VERSION,VISUAL_REVIEW_REASONS


def current_scope_replay(image,native):
    """Re-evaluate visual trust only after the original capture is validated.

    Captured translations remain captured translations, not fresh inference.
    No reader overrides can be erased/reinvented by an isolated QA profile.
    """
    if any(r.get("scope",{}).get("reason")=="reader" for r in native["regions"]):
        raise ValueError("Current-scope replay cannot replace a reader override")
    result=deepcopy(native)
    source=[{k:v for k,v in r.items() if k!="scope"} for r in result["regions"]]
    result["regions"]=route_regions(source,make_plan(image,source,hashlib.sha256(image.tobytes()).hexdigest()),{})
    return result


def checked_native(report,reference,page,size):
    if report.get("privateTest") is not True or report.get("privatePage")!=page:
        raise ValueError("Replay must bind to the explicitly selected private page")
    row=next((r for r in reference.get("pages",[]) if r.get("page")==page),None)
    runs=report.get("runs",[])
    if row is None or not runs or not isinstance(runs[0].get("native"),dict):
        raise ValueError("Missing native source evidence")
    native=runs[0]["native"]
    if (native.get("width"),native.get("height"))!=tuple(size):
        raise ValueError("Replay source dimensions differ")
    def signatures(regions):
        groups={};result=[]
        for region in regions:
            value={k:region.get(k) for k in ("id","bbox","order","ja","overlay","review")}
            scope=region.get("scope")
            if scope is not None:
                if not isinstance(scope,dict) or any(not isinstance(scope.get(k),str) or not scope[k] for k in ("key","group")):
                    raise ValueError("Malformed source scope evidence")
                # Scope IDs include the source page/story identity. Replay and
                # CLI benchmark use different profiles; compare meaning and
                # group topology, not their deliberately different hash salts.
                value["scope"]={k:scope.get(k) for k in ("v","role","action","reason","memory")}
                value["scope"]["group_index"]=groups.setdefault(scope["group"],len(groups))
            else:value["scope"]=None
            result.append(value)
        return result
    actual=native.get("regions",[]);expected=row.get("regions",[])
    if not actual or signatures(actual)!=signatures(expected):
        raise ValueError("Replay source text/geometry/order differs from local benchmark")
    if len({r["id"] for r in actual})!=len(actual) or any(not isinstance(r.get("vi"),str) for r in actual):
        raise ValueError("Replay translations must have unique IDs and typed text")
    return native,row


def build_payload(args):
    paths=[Path(args.native_result).resolve(),Path(args.reference).resolve()]
    if any(ROOT/"artifacts" not in p.parents for p in paths):
        raise ValueError("Private text evidence must be in gitignored artifacts")
    if any(p.stat().st_size>16*1024*1024 for p in paths):raise ValueError("Evidence file too large")
    report,reference=[json.loads(p.read_text(encoding="utf-8")) for p in paths]
    with DirectoryDataset(args.folder) as source:
        _,_,pages=audit(source);fingerprint=dataset_fingerprint(source)
    if fingerprint!=reference.get("input_fingerprint_sha256"):
        raise ValueError("Private dataset fingerprint differs")
    selected=[(p,image) for p,image,_ in pages if p["page_id"]==args.page]
    if len(selected)!=1:raise ValueError("Selected source page is excluded or missing")
    _,image=selected[0]
    native,row=checked_native(report,reference,args.page,image.size)
    current_scope=bool(getattr(args,"current_scope",False))
    if current_scope:native=current_scope_replay(image,native)
    patches=[];remaining=MAX_JOB_PATCH_BYTES
    for region in native["regions"]:
        patch=render_patch(image,region,max_bytes=remaining)
        if patch:
            remaining-=len(patch["dataUrl"].split(",",1)[1])*3//4
            patches.append(patch)
    if not current_scope and [p["regionId"] for p in patches]!=[p["id"] for p in row["transient_patches"]]:
        raise ValueError("Replay cleanup coverage differs from source benchmark")
    return {"page":args.page,"fingerprint":fingerprint,"native":native,"patches":patches,
        "pixel_sha256":hashlib.sha256(image.tobytes()).hexdigest(),
        "cloud":False,"inference":False,"image_persistence":False,
        "scope_recomputed":current_scope,"scope_version":SCOPE_VERSION if current_scope else reference.get("scope_version"),
        "visual_review_ids":[r["id"] for r in native["regions"] if VISUAL_REVIEW_REASONS.intersection(r.get("reviewReasons",[]))]}


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--folder",required=True)
    parser.add_argument("--page",required=True);parser.add_argument("--native-result",required=True)
    parser.add_argument("--reference",default=str(ROOT/"artifacts/private-pages-20261014-local-v3-contract.json"))
    parser.add_argument("--current-scope",action="store_true",help="Re-evaluate source support after capture validation; translations stay captured")
    print(json.dumps(build_payload(parser.parse_args()),ensure_ascii=True))
