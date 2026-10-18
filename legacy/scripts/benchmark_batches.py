"""Compare OCR microbatch sizes on identical private oracle crops."""
import argparse
import json
from pathlib import Path
import statistics
import sys
import time
import zipfile
from benchmark import audit,normalized,distance
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.ocr import MangaEngine

parser=argparse.ArgumentParser();parser.add_argument("--zip",required=True);args=parser.parse_args()
with zipfile.ZipFile(args.zip) as archive:counts,issues,pages=audit(archive)
engine=MangaEngine(ROOT/"models/ocr",4);engine.load()
crops=[]
for page,image,bubbles in pages:
    for b in bubbles:
        x,y,w,h=(b["bbox"][k] for k in ("x","y","w","h"))
        crops.append((page["page_id"],b["bubble_id"],image.crop((x,y,x+w,y+h)),normalized(b["ja_ocr_truth"])))
engine.recognize(crops[0][2])
reports=[]
for size in (1,2,4):
    rows=[];durations=[];start=time.perf_counter()
    for offset in range(0,len(crops),size):
        batch=crops[offset:offset+size];t=time.perf_counter()
        predictions=engine.recognize_many([r[2] for r in batch]) if size>1 else [engine.recognize(batch[0][2])]
        durations.append((time.perf_counter()-t)*1000)
        for r,prediction in zip(batch,predictions):
            pred=normalized(prediction);rows.append({"page":r[0],"id":r[1],"prediction":pred,"reference":r[3],"edits":distance(r[3],pred)})
    total=(time.perf_counter()-start)*1000
    report={"batch_size":size,"crops":len(rows),"total_ms":total,"amortized_crop_ms":total/len(rows),
            "p50_batch_ms":statistics.median(durations),"max_batch_ms":max(durations),
            "cer":sum(r["edits"] for r in rows)/sum(len(r["reference"]) for r in rows),
            "exact_match":sum(r["prediction"]==r["reference"] for r in rows)/len(rows),"rows":rows}
    reports.append(report);print(json.dumps({k:v for k,v in report.items() if k!="rows"}),flush=True)
    (ROOT/"artifacts/ocr-batches.json").write_text(json.dumps({"counts":counts,"audit":issues,"threads":4,"device":"CPU","reports":reports},ensure_ascii=False,indent=2),encoding="utf-8")
