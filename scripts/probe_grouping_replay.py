"""Model-free RAM-only replay of private detector geometry.

Requires the same dataset fingerprint as the recorded full-page comparator.
The selection box and expected group count are a visually-reviewed diagnostic,
not reference-conditioned production grouping or modified ground truth.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
from benchmark import ROOT, audit, dataset_source, dataset_fingerprint
from benchmark_pages import intersection
from manga_live.ocr import (group_regions, rect, partition_ocr_boxes, LAYOUT_VERSION,
                            EXPERIMENTAL_LAYOUT_VERSION, PAIR_SCALE_GROUPING_VERSION)


def run(args):
    report=json.loads(Path(args.replay).read_text(encoding="utf-8"))
    with dataset_source(SimpleNamespace(folder=args.folder)) as source:
        _,_,pages=audit(source); fingerprint=dataset_fingerprint(source)
    if report.get("input_fingerprint_sha256")!=fingerprint:
        raise ValueError("Replay and dataset differ; do not substitute a source image")
    source_page=next((entry for entry in pages if entry[0]["page_id"]==args.page),None)
    replay_page=next((entry for entry in report.get("pages",[]) if entry.get("page")==args.page),None)
    if source_page is None or replay_page is None:
        raise ValueError("Selected page is not eligible or has no recorded source lines")
    image=source_page[1]; lines=[]
    for region in replay_page["line_results"]:
        for line in region["lines"]:
            box=rect(line["polygon"])
            if intersection(args.box,box)>=max(1,box[2]*box[3])*.5:
                # Recorded values are CTC scores, not detector probabilities.
                # No new score is used to filter the already-detected geometry.
                lines.append({"polygon":line["polygon"],"score":.95})
    if not lines:
        raise ValueError("No source detector line in selected diagnostic area")
    experimental=getattr(args,"experimental_open_text",False)
    pair_scale=getattr(args,"experimental_pair_scale",False)
    if pair_scale and experimental:raise ValueError('Compare one grouping recipe at a time')
    regions=group_regions(image,lines,experimental_open_text=experimental,
                          experimental_pair_scale=pair_scale,include_source_members=pair_scale)
    crops,evidence=({},[])
    if pair_scale:
        parents=group_regions(image,lines,include_source_members=True)
        crops,evidence=partition_ocr_boxes(image,regions,source_parents=parents)
    version=(PAIR_SCALE_GROUPING_VERSION if pair_scale else
             EXPERIMENTAL_LAYOUT_VERSION if experimental else LAYOUT_VERSION)
    result={"page":args.page,"layout_version":version,
        "experimental":experimental or pair_scale,"production_default":False,"source_lines":len(lines),
        "inference_crops":crops,"partition_evidence":evidence,
        "region_count":len(regions),"regions":[{k:r[k] for k in ("id","bbox","overlay","reviewReasons") if k in r}
                                               for r in regions]}
    print(json.dumps(result,ensure_ascii=True),flush=True)
    if args.expect_regions is not None and len(regions)!=args.expect_regions:
        raise SystemExit(2)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",required=True);parser.add_argument("--page",required=True)
    parser.add_argument("--replay",default=str(ROOT/"artifacts/private-paddle-rec-pages-20261014.json"))
    parser.add_argument("--box",type=int,nargs=4,required=True)
    parser.add_argument("--expect-regions",type=int)
    parser.add_argument("--experimental-open-text",action="store_true",
                        help="Replay the unaccepted aligned-open grouping candidate; never changes companion defaults")
    parser.add_argument("--experimental-pair-scale",action="store_true",
                        help="Replay disjoint pair-scale groups with bounded parent inference frames; not a native default")
    run(parser.parse_args())
