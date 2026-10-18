"""Isolated detector-quad OCR crop comparator; never a companion default.

Keep the detector, grouping, OCR weights/decoder and output geometry fixed.
Replace only the OCR input of uniquely matched single-line regions. Crops,
source pages and masks stay in RAM; private reports belong in artifacts/.
"""
import argparse
import math
from pathlib import Path
import sys
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
import benchmark_pages
from manga_live.ocr import MangaEngine,PaddleDetector,group_regions,rect,recognize_regions


def padded_box(image,quad):
    x,y,w,h=rect(quad)
    x,y=max(0,int(x)-3),max(0,int(y)-3)
    return [x,y,min(image.width-x,int(w)+6),min(image.height-y,int(h)+6)]


def polygon_crop(image,quad,strategy):
    """Return one bounded crop, not revised source evidence/erasure metadata."""
    import cv2
    import numpy as np
    from PIL import Image
    if strategy not in ("mask","rectify","rectify-halo"):raise ValueError("Exact crop strategy required")
    if (not isinstance(quad,(list,tuple)) or len(quad)!=4 or
        any(not isinstance(p,(list,tuple)) or len(p)!=2 or
            any(type(v) not in (int,float) or not math.isfinite(v) for v in p) for p in quad)):
        return None
    if any(not 0<=x<image.width or not 0<=y<image.height for x,y in quad):return None
    points=np.asarray(quad,dtype="float32")
    if len({tuple(p) for p in quad})!=4 or not cv2.isContourConvex(points.reshape(-1,1,2)):return None
    x,y,w,h=padded_box(image,quad)
    if min(w,h)<8 or max(w,h)>900 or w*h>90000:return None
    source=np.asarray(image.crop((x,y,x+w,y+h)).convert("RGB"))
    paper=np.median(source.reshape(-1,3),axis=0).astype("uint8")
    # Extrapolation is not source text. Limit the neutral matte to fairly flat
    # support; gradients/textures and unsupported art keep the original crop.
    if float((np.abs(source.astype("int16")-paper).max(axis=2)<=10).mean())<.55:return None
    local=points-np.asarray([x,y],dtype="float32")
    if strategy=="mask":
        mask=np.zeros((h,w),dtype="uint8")
        cv2.fillConvexPoly(mask,np.rint(local).astype("int32"),1)
        candidate=source.copy();candidate[mask==0]=paper
        return Image.fromarray(candidate)
    # Keep Japanese vertical text vertical. Never rotate a tall column into
    # a horizontal OCR line; reject extreme skew instead of guessing corners.
    top=points[np.argsort(points[:,1])[:2]];bottom=points[np.argsort(points[:,1])[2:]]
    tl,tr=top[np.argsort(top[:,0])];bl,br=bottom[np.argsort(bottom[:,0])]
    if min(tr[0]-tl[0],br[0]-bl[0],bl[1]-tl[1],br[1]-tr[1])<=0:return None
    width=max(np.linalg.norm(tr-tl),np.linalg.norm(br-bl))
    height=max(np.linalg.norm(bl-tl),np.linalg.norm(br-tr))
    if abs(tr[1]-tl[1])>width*.3 or abs(br[1]-bl[1])>width*.3:return None
    out_w,out_h=max(1,int(round(width))),max(1,int(round(height)))
    if min(out_w,out_h)<4 or max(out_w,out_h)>900 or out_w*out_h>90000:return None
    ordered=np.asarray([tl,tr,br,bl],dtype="float32")-np.asarray([x,y],dtype="float32")
    # One bounded second arm preserves production's 3px source halo rather
    # than cropping detector padding away. No choice is made using OCR/gold.
    pad=3 if strategy=="rectify-halo" else 0
    destination=np.asarray([[pad,pad],[out_w-1+pad,pad],[out_w-1+pad,out_h-1+pad],
                            [pad,out_h-1+pad]],dtype="float32")
    transform=cv2.getPerspectiveTransform(ordered,destination)
    candidate=cv2.warpPerspective(source,transform,(out_w+2*pad,out_h+2*pad),flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_CONSTANT,borderValue=tuple(int(v) for v in paper))
    return Image.fromarray(candidate)


class PolygonDetector:
    name=PaddleDetector.name
    def __init__(self,threads):
        self.detector=PaddleDetector(ROOT/"models/detector",threads)
        self.quads=[]
        self.details={"kind":"source-quad-crops","production_default":False,
                      "detector_weights_resize":"unchanged pinned defaults","grouping":"unchanged production"}
    def detect(self,image):
        raw=self.detector.detect_raw(image)
        self.quads=[d["polygon"] for d in raw]
        return group_regions(image,raw)


def crop_recognizer(detector,strategy,counts):
    def recognize(image,regions,engine,cancel,progress=None,batch_size=2):
        quads={}
        for quad in detector.quads:quads.setdefault(tuple(padded_box(image,quad)),[]).append(quad)
        candidates=[]
        for region in regions:
            x,y,w,h=region["bbox"]
            original=image.crop((x,y,x+w,y+h))
            matches=quads.get(tuple(region["bbox"]),[])
            candidate=polygon_crop(image,matches[0],strategy) if len(matches)==1 else None
            candidates.append(original if candidate is None else candidate)
            counts["regions"]+=1;counts["transformed"]+=candidate is not None
        class RegionEngine:
            def __init__(self):self.offset=0
            def recognize_many(self,items):
                if self.offset+len(items)>len(candidates):raise ValueError("Unexpected OCR crop cardinality")
                replacements=candidates[self.offset:self.offset+len(items)];self.offset+=len(items)
                return engine.recognize_many(replacements)
            def recognize(self,item):return self.recognize_many([item])[0]
        adapter=RegionEngine()
        result=recognize_regions(image,regions,adapter,cancel,progress,batch_size)
        if adapter.offset!=len(regions):raise ValueError("Incomplete crop replay")
        return result
    return recognize


def run(args):
    destination=Path(args.output).resolve()
    if ROOT/"artifacts" not in destination.parents:raise ValueError("Private output must stay in artifacts")
    detector=PolygonDetector(args.threads)
    engine=MangaEngine(ROOT/"models/ocr",args.threads)
    engine.details={"kind":"OCR-source-crop-only","strategy":args.strategy,"production_default":False,
        "weights_decoder_processor":"unchanged","image_persistence":False}
    counts={"regions":0,"transformed":0}
    with patch.object(benchmark_pages,"recognize_regions",crop_recognizer(detector,args.strategy,counts)):
        benchmark_pages.run(args,detector_override=detector,engine_override=engine)
    import json
    report=json.loads(destination.read_text(encoding="utf-8"))
    report["experimental_crop_counts"]=counts
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"strategy":args.strategy,**counts}),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder",required=True)
    parser.add_argument("--strategy",choices=("mask","rectify","rectify-halo"),required=True)
    parser.add_argument("--threads",type=int,default=4)
    parser.add_argument("--output",required=True)
    run(parser.parse_args())
