"""Model-free source-support lettering comparison against the frozen control.

Replay the unchanged full-page PP plane, not its extra tiled proposals. Reuse
recorded OCR only after source geometry and inference crops compare exactly.
All raster data remains in RAM; only private text/numeric JSON is emitted.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import sys
import time
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from benchmark import DirectoryDataset,audit,dataset_fingerprint
from compare_page_reports import checked_pages,compare,private_json_path
from benchmark_pages import assign_to_labels,hashlib_image
from manga_live.ocr import group_regions,partition_ocr_boxes,LAYOUT_VERSION,PRESENTATION_VERSION,PaddleDetector
from manga_live.text_scope import make_plan,route_regions
from probe_tiled_detection import VERSION as TILED_VERSION,POLICY

VERSION="balloon-actual-source-support-v1"


def full_plane(row,image):
    raw=row.get("detector_evidence",{}).get("raw_detections")
    if not isinstance(raw,list) or not 1<=len(raw)<=512:
        raise ValueError("Bounded retained detector plane required")
    result=[]
    for member in raw:
        if member.get("pass")!="full":continue
        points=member.get("polygon");score=member.get("score")
        if (not isinstance(points,list) or len(points)!=4 or any(
                not isinstance(p,list) or len(p)!=2 or any(type(v) not in (int,float) or
                not math.isfinite(v) for v in p) or not (0<=p[0]<=image.width and 0<=p[1]<=image.height)
                for p in points) or type(score) not in (int,float) or not math.isfinite(score) or not 0<=score<=1):
            raise ValueError("Invalid original detector polygon/score")
        result.append({"polygon":deepcopy(points),"score":score})
    if not result:raise ValueError("Missing unchanged full-page source plane")
    return result


def geometry(rows):
    return [{k:r[k] for k in ("id","bbox","order")} for r in rows]


def run(args):
    verify_native=getattr(args,"verify_native",False)
    output=private_json_path(args.output,new=True)
    contents=[private_json_path(value).read_bytes() for value in (args.reference,args.detector_replay)]
    reference,evidence=[json.loads(value) for value in contents]
    if (reference.get("layout_version")!=LAYOUT_VERSION or reference.get("cloud") is not False or
            evidence.get("layout_version")!=LAYOUT_VERSION or evidence.get("cloud") is not False or
            evidence.get("experimental_detector",{}).get("kind")!=TILED_VERSION or
            evidence["experimental_detector"].get("policy")!=POLICY):
        raise ValueError("Matching reviewed production control and tiled detector evidence required")
    before_pages,raw_pages=checked_pages(reference),checked_pages(evidence)
    with DirectoryDataset(args.folder) as source:
        counts,issues,pages=audit(source);fingerprint=dataset_fingerprint(source)
    eligible={p[0]["page_id"] for p in pages}
    if (any(r.get("input_fingerprint_sha256")!=fingerprint for r in (reference,evidence)) or
            set(before_pages)!=eligible or set(raw_pages)!=eligible):
        raise ValueError("Matching complete source fingerprint/coverage required")
    result={"schema":1,"version":VERSION,"layout_version":LAYOUT_VERSION,"cloud":False,
        "presentation_version":PRESENTATION_VERSION,"production_default":verify_native,
        "native_default_verified":verify_native,"fresh_inference":False,"image_persistence":False,"complete":False,
        "input_fingerprint_sha256":fingerprint,"counts":counts,"audit":issues,
        "input_report_sha256":[hashlib.sha256(value).hexdigest() for value in contents],"pages":[],
        "limitations":["Lettering geometry replay only; not new detection, OCR, translation or latency.",
            "Source boxes are not glyph masks; fixed 8px/10% and full foreign-ink checks remain.",
            "No independently reviewed Japanese/Vietnamese/clean-background or held-out gold.",
            "Accepted caches retain their existing surfaces; no cache/source-key or reader-memory migration."]}
    for meta,image,labels in pages:
        ident=meta["page_id"];original=before_pages[ident][0]
        if any(r.get("scope",{}).get("reason")=="reader" for r in original["regions"]):
            raise ValueError("Do not replay candidate over reader-owned source")
        raw=full_plane(raw_pages[ident][0],image)
        start=time.perf_counter();before=group_regions(image,raw,include_source_members=True)
        control_ms=(time.perf_counter()-start)*1000
        start=time.perf_counter();after=group_regions(image,raw,include_source_members=True,experimental_source_support=True)
        candidate_ms=(time.perf_counter()-start)*1000
        if verify_native:
            # Stub the external model boundary with its retained output, not
            # the owned detect/grouping methods being verified. No inference.
            detector=PaddleDetector(ROOT/"models/detector")
            detector.model=SimpleNamespace(predict=lambda *a,**k:[SimpleNamespace(json={"res":{
                "dt_polys":[r["polygon"] for r in raw],"dt_scores":[r["score"] for r in raw]}})])
            native=detector.detect(image)
            if native!=[{k:v for k,v in r.items() if k!="sourceMembers"} for r in after]:
                raise ValueError("Native default differs from the accepted presentation replay")
        if (geometry(before)!=geometry(original["regions"]) or geometry(before)!=geometry(after) or
                [r["sourceMembers"] for r in before]!=[r["sourceMembers"] for r in after] or
                [r["overlay"] for r in before]!=[r["overlay"] for r in original["regions"]]):
            raise ValueError("Control/source geometry changed; OCR reuse is not justified")
        if partition_ocr_boxes(image,before)!=partition_ocr_boxes(image,after):
            raise ValueError("Inference crop/partition changed; require new OCR")
        sources=deepcopy(original["regions"])
        for source,old,new in zip(sources,before,after):
            if old.get("balloon") and old!=new:raise ValueError("An existing integrated region changed")
            source["overlay"]=new["overlay"]
            if new.get("balloon"):source["balloon"]=deepcopy(new["balloon"])
        scope_before=route_regions(deepcopy(original["regions"]),make_plan(image,original["regions"],hashlib_image(image)),{})
        scope_after=route_regions(deepcopy(sources),make_plan(image,sources,hashlib_image(image)),{})
        if [r["scope"] for r in scope_before]!=[r["scope"] for r in scope_after]:
            raise ValueError("Render candidate changed source keys/routing/semantic trust")
        aligned,unmatched=assign_to_labels(labels,sources)
        if aligned!=original["aligned"]:raise ValueError("OCR/alignment changed under lettering-only candidate")
        changes=[{"id":new["id"],"bbox":new["bbox"],"textBox":new["balloon"]["textBox"]}
                 for old,new in zip(before,after) if old!=new]
        result["pages"].append({"page":ident,"regions":sources,"aligned":aligned,
            "unmatched_prediction_ids":unmatched,"source_plane":raw,"changes":changes,
            "previous_integrated":sum(bool(r.get("balloon")) for r in before),
            "integrated":sum(bool(r.get("balloon")) for r in after),
            "control_group_lettering_ms":control_ms,"candidate_group_lettering_ms":candidate_ms})
    result["comparison"]=compare(reference,result)
    result["aggregate"]={"previous_integrated":sum(p["previous_integrated"] for p in result["pages"]),
        "integrated":sum(p["integrated"] for p in result["pages"]),**result["comparison"]["aggregate"]}
    result["complete"]=True
    output.parent.mkdir(parents=True,exist_ok=True)
    with output.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2,allow_nan=False)
    print(json.dumps({"aggregate":result["aggregate"],"changes":[{"page":p["page"],"changes":p["changes"]}
        for p in result["pages"] if p["changes"]]}))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder",required=True);parser.add_argument("--reference",required=True)
    parser.add_argument("--detector-replay",required=True);parser.add_argument("--output",required=True)
    parser.add_argument("--verify-native",action="store_true",help="Verify real native detect() against retained model outputs; no inference")
    run(parser.parse_args())
