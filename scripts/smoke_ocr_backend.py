"""Real CPU OCR on authored in-RAM crops, with no detector, LLM or network.

This narrow runtime check is not a manga-quality benchmark or portable-host
proof. The labels describe our own synthetic image only.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from fixture_server import synthetic_page
from benchmark import normalized
from manga_live.ocr import MangaEngine,decode_image


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",default=str(ROOT/"artifacts/owned-ocr-runtime-smoke.json"))
    args=parser.parse_args()
    image=decode_image(synthetic_page())
    fixtures=[((440,70,760,300),"姉ちゃん、まだ帰らないの？"),
        ((60,150,380,390),"先に帰ってて。あとで行くから。"),
        ((440,500,760,740),"氷結結界を展開する！"),
        ((60,690,380,960),"明日は来なくてもいい。")]
    engine=MangaEngine(ROOT/"models/ocr",4)
    start=time.perf_counter();engine.load();load_ms=(time.perf_counter()-start)*1000
    # Reuse loaded tensors to compare upstream's call algorithm without its
    # constructor, hidden site-packages compatibility patch or double RAM use.
    from manga_ocr import MangaOcr
    upstream=MangaOcr.__new__(MangaOcr)
    for key in ("processor","tokenizer","model"):
        setattr(upstream,key,getattr(engine.model,key))
    rows=[]
    for idx,(box,reference) in enumerate(fixtures):
        start=time.perf_counter();prediction=engine.recognize(image.crop(box))
        rows.append({"id":idx,"reference":reference,"prediction":prediction,
            "exact":normalized(reference)==normalized(prediction),"ms":(time.perf_counter()-start)*1000})
        rows[-1]["upstream_call_parity"]=upstream(image.crop(box))==prediction
        print(json.dumps({"crop":idx,"exact":rows[-1]["exact"],"ms":rows[-1]["ms"]}),flush=True)
    blanks=engine.recognize_many([image.crop((0,0,10,10))])
    report={"source":"author-created synthetic image; Python development runtime; real CPU OCR",
        "engine":engine.name,"load_ms":load_ms,"rows":rows,"blank_is_empty":blanks==[""],
        "independent_of_upstream_mangaocr_constructor":True,"offline_load_policy":"local_files_only=True; no download calls",
        "runtime_pass":blanks==[""] and all(row["prediction"] and row["upstream_call_parity"] for row in rows),
        "authored_labels_all_exact":all(row["exact"] for row in rows),
        "limitations":["Four authored crops only, not representative manga accuracy or a reliable p95.",
            "Not a clean Windows or frozen-host inference check."]}
    destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"load_ms":load_ms,"exact_crops":sum(row["exact"] for row in rows),
        "blank_is_empty":report["blank_is_empty"],"runtime_pass":report["runtime_pass"],
        "authored_labels_all_exact":report["authored_labels_all_exact"]}),flush=True)
    if not report["runtime_pass"]:
        raise SystemExit("OCR runtime/parity failed; inspect report")


if __name__=="__main__":main()
