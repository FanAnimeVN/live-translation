"""Numeric, model-free shape evidence; private pixels stay in RAM.

This is an investigation of the same dominant paper component used by the
production grouping seam, not an OCR- or reference-conditioned splitter.
"""
import argparse
import json
from pathlib import Path
from types import SimpleNamespace
import cv2
import numpy as np
from benchmark import audit,dataset_source,dataset_fingerprint
from manga_live.ocr import rect
from benchmark_pages import intersection


def run(args):
    report=json.loads(Path(args.replay).read_text(encoding="utf-8"))
    with dataset_source(SimpleNamespace(folder=args.folder)) as source:
        _,_,pages=audit(source);fingerprint=dataset_fingerprint(source)
    if fingerprint!=report.get("input_fingerprint_sha256"):
        raise ValueError("Replay source mismatch")
    page=next(p for p in pages if p[0]["page_id"]==args.page)
    recorded=next(p for p in report["pages"] if p["page"]==args.page)
    image=page[1];grey=np.asarray(image.convert("L"))
    _,labels,stats,_=cv2.connectedComponentsWithStats((grey>175).astype("uint8"))
    selected=[]
    for group in recorded["line_results"]:
        for line in group["lines"]:
            box=rect(line["polygon"])
            if intersection(args.box,box)<max(1,box[2]*box[3])*.5:continue
            x,y,w,h=map(int,box);patch=labels[y:y+h,x:x+w]
            votes=np.bincount(patch[patch>0]);label=int(np.argmax(votes)) if votes.size else 0
            selected.append({"box":box,"surface_label":label})
    rows=[]
    for label in sorted({row["surface_label"] for row in selected if row["surface_label"]}):
        x,y,w,h,area=map(int,stats[label]);component=(labels[y:y+h,x:x+w]==label).astype("uint8")
        contours,_=cv2.findContours(component,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
        contour=max(contours,key=cv2.contourArea)
        filled=np.zeros_like(component);cv2.drawContours(filled,[contour],-1,1,cv2.FILLED)
        hull=cv2.convexHull(contour,returnPoints=False);defects=cv2.convexityDefects(contour,hull)
        samples=[]
        for column in range(max(x,args.box[0]),min(x+w,args.box[0]+args.box[2]),args.step):
            points=np.flatnonzero(filled[:,column-x])
            if points.size:samples.append([column,int(points[0]+y),int(points[-1]+y)])
        rows.append({"label":label,"component_box":[x,y,w,h],"area":area,
            "envelope_samples":samples,"convexity_defects":[] if defects is None else [
                {"start":(contour[start,0]+[x,y]).tolist(),"end":(contour[end,0]+[x,y]).tolist(),
                 "inner":(contour[inner,0]+[x,y]).tolist(),"depth":round(depth/256,2)}
                for start,end,inner,depth in defects[:,0] if depth/256>=5]})
    print(json.dumps({"page":args.page,"input_fingerprint_sha256":fingerprint,
                      "detector_boxes":selected,"surfaces":rows},ensure_ascii=True))


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--folder",required=True)
    parser.add_argument("--page",required=True);parser.add_argument("--box",nargs=4,type=int,required=True)
    parser.add_argument("--replay",default="artifacts/private-paddle-rec-pages-20261014.json")
    parser.add_argument("--step",type=int,choices=range(1,21),default=5)
    run(parser.parse_args())
