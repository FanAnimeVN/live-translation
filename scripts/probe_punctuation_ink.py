"""RAM-only source support metrics for a selected punctuation OCR region."""
import argparse
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from benchmark import DirectoryDataset,audit,dataset_fingerprint


def run(args):
    import cv2
    import numpy as np
    evidence=Path(args.evidence).resolve()
    if ROOT/"artifacts" not in evidence.parents:raise ValueError("Private evidence required")
    report=json.loads(evidence.read_text(encoding="utf-8"))
    with DirectoryDataset(args.folder) as source:
        _,_,pages=audit(source);fingerprint=dataset_fingerprint(source)
    if fingerprint!=report["input_fingerprint_sha256"]:raise ValueError("Source fingerprint differs")
    image=next(image for page,image,_ in pages if page["page_id"]==args.page)
    regions=next(row["regions"] for row in report["pages"] if row["page"]==args.page)
    region=next(r for r in regions if r["id"]==args.region)
    x,y,w,h=region["bbox"]
    if min(w,h)<4 or max(w,h)>128 or w*h>8192:raise ValueError("Bounded diagnostic crop required")
    grey=np.asarray(image.crop((x,y,x+w,y+h)).convert("L"))
    paper=int(np.bincount(grey.reshape(-1),minlength=256).argmax())
    output={"page":args.page,"region":args.region,"box":region["bbox"],"background":paper,"thresholds":[]}
    contrast=np.abs(grey.astype("int16")-paper)
    for threshold in (30,60,90,120):
        count,_,stats,_=cv2.connectedComponentsWithStats((contrast>=threshold).astype("uint8"))
        output["thresholds"].append({"threshold":threshold,"flat_support":float((contrast<12).mean()),
            "components":[[int(v) for v in row] for row in stats[1:] if row[cv2.CC_STAT_AREA]>=2]})
    print(json.dumps(output))


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--folder",required=True);parser.add_argument("--page",required=True)
    parser.add_argument("--region",required=True);parser.add_argument("--evidence",required=True);run(parser.parse_args())
