"""Pixel-only diagnostic for possible hatch false positives; no promotion.

Outputs geometry, not raster/text. Source files are read locally through the
audited dataset adapter; candidate boxes are bound to its fingerprint.
"""
import argparse
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from benchmark import DirectoryDataset,audit,dataset_fingerprint


def noise_geometry(image,box):
    import cv2
    import numpy as np
    x,y,w,h=map(int,box)
    grey=np.asarray(image.crop((x,y,x+w,y+h)).convert("L"))
    background=int(np.bincount(grey.reshape(-1),minlength=256).argmax())
    contrast=np.abs(grey.astype("int16")-background)
    result={"background":background,"std":float(grey.std()),"area":int(grey.size),"levels":[]}
    for threshold in (20,30,45,120):
        mask=(contrast>=threshold).astype("uint8")
        count,_,stats,_=cv2.connectedComponentsWithStats(mask,connectivity=8)
        areas=sorted((int(value) for value in stats[1:,cv2.CC_STAT_AREA]),reverse=True)
        result["levels"].append({"contrast":threshold,"pixels":int(mask.sum()),"components":count-1,
            "largest":areas[:12],"support_boxes":[[int(v) for v in row[2:]] for row in stats[1:] if row[cv2.CC_STAT_AREA]>=3]})
    result["flat_fraction"]=float((contrast<12).mean())
    return result


def pattern_geometry(image,box):
    import cv2
    import numpy as np
    x,y,w,h=map(int,box)
    pad=max(8,min(40,min(w,h)))
    left=max(0,x-pad);top=max(0,y-pad)
    right=min(image.width,x+w+pad);bottom=min(image.height,y+h+pad)
    if min(right-left,bottom-top)<12 or (right-left)*(bottom-top)>160000:
        return {"bounded":False}
    grey=np.asarray(image.crop((left,top,right,bottom)).convert("L"))
    ink=(grey<110).astype("uint8")*255
    lines=cv2.HoughLinesP(ink,1,np.pi/180,threshold=12,
        minLineLength=max(12,round(min(w,h)*.6)),maxLineGap=2)
    if lines is None:return {"bounded":True,"line_count":0}
    segments=[];total=vector_x=vector_y=0.0
    for (sx,sy,ex,ey), in lines:
        length=math.hypot(ex-sx,ey-sy)
        angle=math.atan2(ey-sy,ex-sx)
        vector_x+=length*math.cos(2*angle);vector_y+=length*math.sin(2*angle);total+=length
        segments.append((int(sx),int(sy),int(ex),int(ey),length,angle))
    direction=math.atan2(vector_y,vector_x)/2
    mask=np.zeros_like(ink)
    for sx,sy,ex,ey,length,angle in segments:
        if abs(math.sin(angle-direction))<=math.sin(math.radians(10)):
            cv2.line(mask,(sx,sy),(ex,ey),255,3)
    roi=(slice(y-top,y-top+h),slice(x-left,x-left+w))
    roi_ink=ink[roi]>0
    fitted=(mask[roi]>0)&roi_ink
    pixels=int(roi_ink.sum())
    offsets=sorted((-(sx+ex)/2*math.sin(direction)+(sy+ey)/2*math.cos(direction))
        for sx,sy,ex,ey,_,angle in segments if abs(math.sin(angle-direction))<=math.sin(math.radians(10)))
    tracks=[]
    for offset in offsets:
        if not tracks or offset-tracks[-1]>2:tracks.append(offset)
    return {"bounded":True,"line_count":len(segments),"tracks":len(tracks),
        "direction_degrees":math.degrees(direction),"concentration":math.hypot(vector_x,vector_y)/max(total,1),
        "ink_pixels":pixels,"explained_ink":int(fitted.sum())/max(1,pixels),
        "track_gaps":[round(b-a,2) for a,b in zip(tracks,tracks[1:])]}


def run(args):
    evidence_path=Path(args.evidence).resolve()
    if ROOT/"artifacts" not in evidence_path.parents:raise ValueError("Private artifact required")
    report=json.loads(evidence_path.read_text(encoding="utf-8"))
    with DirectoryDataset(args.folder) as source:
        _,_,pages=audit(source);fingerprint=dataset_fingerprint(source)
    if fingerprint!=report["input_fingerprint_sha256"]:raise ValueError("Fingerprint mismatch")
    for page,image,_ in pages:
        if page["page_id"]!=args.page:continue
        matches=[r for row in report["pages"] if row["page"]==args.page for r in row["regions"] if r["id"]==args.region]
        if len(matches)!=1:raise ValueError("Exact region required")
        print(json.dumps({"page":args.page,"region":args.region,"bbox":matches[0]["bbox"],
            "geometry":pattern_geometry(image,matches[0]["bbox"]),
            "noise":noise_geometry(image,matches[0]["bbox"]),"production_changed":False}))
        return
    raise ValueError("Eligible page required")


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",required=True);parser.add_argument("--page",required=True)
    parser.add_argument("--region",required=True)
    parser.add_argument("--evidence",default=str(ROOT/"artifacts/private-pages-20261014-v16-post-candidate.json"))
    run(parser.parse_args())
