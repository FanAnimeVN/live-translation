"""Single-variable OCR crop experiment on author-created dialogue only.

Replay real recorded detector geometry. No image is written and no cloud is
called; model weights/preprocessing/postprocessing are identical in both arms.
This is not the user's private benchmark or a whole-page detection run.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from fixture_server import synthetic_detected_layout
from manga_live.ocr import MangaEngine, group_regions, rect
from benchmark import normalized
from PIL import ImageOps


def run(args):
    image,detections,_=synthetic_detected_layout()
    regions=group_regions(image,detections)
    references=["姉ちゃん、まだ帰らないの？","先に帰ってて。あとで行くから。",
                "氷結結界を展開する！","明日は来なくてもいい。"]
    engine=MangaEngine(ROOT/"models/ocr",4)
    rows=[]
    selected_regions=[(region,reference) for region,reference in zip(regions,references)
                      if not args.region or region["id"] in args.region]
    for region,reference in selected_regions:
        boxes=[("detector",region["bbox"])]
        masks=region.get("balloon",{}).get("erasePolygons",[])
        if masks:
            boxes.append(("glyph_mask",list(map(int,rect([p for poly in masks for p in poly])))))
        for strategy,(x,y,w,h) in boxes:
            started=time.perf_counter()
            prediction=engine.recognize(image.crop((x,y,x+w,y+h)))
            row={"id":region["id"],"strategy":strategy,"crop":[x,y,w,h],
                 "exact":normalized(prediction)==normalized(reference),
                 "prediction":prediction,"ms":(time.perf_counter()-started)*1000}
            rows.append(row)
            print(json.dumps(row,ensure_ascii=True),flush=True)
        if args.padding_tests and region["id"] in ("r000","r003"):
            x,y,w,h=region["bbox"]
            crop=image.crop((x,y,x+w,y+h))
            for name,variant in [("padding_12",ImageOps.expand(crop,border=12,fill="white")),
                                 ("padding_24",ImageOps.expand(crop,border=24,fill="white")),
                                 ("binary_128",crop.convert("L").point(lambda pixel:255 if pixel>=128 else 0).convert("RGB"))]:
                started=time.perf_counter()
                prediction=engine.recognize(variant)
                row={"id":region["id"],"strategy":name,"crop_size":variant.size,
                     "exact":normalized(prediction)==normalized(reference),
                     "prediction":prediction,"ms":(time.perf_counter()-started)*1000}
                rows.append(row)
                print(json.dumps(row,ensure_ascii=True),flush=True)
        if args.canvas_tests:
            x,y,w,h=region["bbox"];crop=image.crop((x,y,x+w,y+h))
            paper=region.get("balloon",{}).get("background","white")
            side=max(w,h);left,top=(side-w)//2,(side-h)//2
            variants=[("square_context",ImageOps.expand(crop,border=(left,top,side-w-left,side-h-top),fill=paper))]
            context_box=region.get("balloon",{}).get("textBox")
            if context_box:
                bx,by,bw,bh=context_box
                bounds=(min(x,bx),min(y,by),max(x+w,bx+bw),max(y+h,by+bh))
                variants.append(("lettering_context",image.crop(bounds)))
            for name,variant in variants:
                started=time.perf_counter();prediction=engine.recognize(variant)
                row={"id":region["id"],"strategy":name,"crop_size":variant.size,
                     "exact":normalized(prediction)==normalized(reference),
                     "prediction":prediction,"ms":(time.perf_counter()-started)*1000}
                rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
        if args.decoder_tests:
            engine.load();config=engine.model.model.generation_config
            x,y,w,h=region["bbox"];crop=image.crop((x,y,x+w,y+h))
            for name,key,value in (("beams_1","num_beams",1),("beams_2","num_beams",2),
                                   ("length_penalty_1","length_penalty",1.0)):
                original=getattr(config,key)
                try:
                    setattr(config,key,value);started=time.perf_counter();prediction=engine.recognize(crop)
                    row={"id":region["id"],"strategy":name,"changed_field":key,"original":original,"candidate":value,
                         "exact":normalized(prediction)==normalized(reference),"prediction":prediction,
                         "ms":(time.perf_counter()-started)*1000}
                    rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
                finally:setattr(config,key,original)
    chosen=[r for r in rows if r["strategy"]==args.assert_strategy]
    if args.assert_strategy and (len(chosen)!=len(selected_regions) or not chosen or not all(r["exact"] for r in chosen)):
        raise SystemExit(2)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--assert-strategy",choices=("detector","glyph_mask","square_context","lettering_context",
                                                    "beams_1","beams_2","length_penalty_1"))
    parser.add_argument("--padding-tests",action="store_true")
    parser.add_argument("--canvas-tests",action="store_true",help="Experimental source canvas only; never changes runtime defaults")
    parser.add_argument("--decoder-tests",action="store_true",help="One-field decoder probes only, restored after each crop")
    parser.add_argument("--region",action="append",choices=("r000","r001","r002","r003"),
                        help="Minimize the crop repro; repeat to select more than one region")
    run(parser.parse_args())
