"""One-field decoder comparator; no companion import or automatic promotion.

Keep weights, crops, processor and postprocessing fixed. Never select a
variant from reference text. Raster stays in RAM, diagnostics in artifacts.
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import time
import unicodedata

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from PIL import Image,ImageDraw,ImageFont
from benchmark import DirectoryDataset,audit,dataset_fingerprint,distance,normalized
from probe_ocr_resampling import controls
from manga_live.ocr import MangaEngine,blank_crop

LENGTH_PENALTIES={"punctuation-one":1.0,"punctuation-mid":1.5}


def punctuation_ids(vocabulary):
    """WordPiece punctuation only; never classifies lexical/special tokens."""
    return frozenset(idx for token,idx in vocabulary.items()
        if (visible:=token.removeprefix("##")) and
        all(unicodedata.category(char).startswith("P") for char in visible))


def repeated_punctuation_next(tokens,punctuation,*,current_run=False):
    """Exactly the old size-3 mask, restricted to punctuation-only triples."""
    if current_run:
        start=len(tokens)
        while start and tokens[start-1] in punctuation:start-=1
        tokens=tokens[start:]
    if len(tokens)<3 or not all(token in punctuation for token in tokens[-2:]):return ()
    prefix=tuple(tokens[-2:])
    return tuple(sorted({tokens[index+2] for index in range(len(tokens)-2)
                         if tuple(tokens[index:index+2])==prefix and tokens[index+2] in punctuation}))


class PunctuationRepeatGuard:
    def __init__(self,vocabulary,*,current_run=False):
        self.punctuation=punctuation_ids(vocabulary);self.current_run=current_run
    def __call__(self,input_ids,scores):
        output=scores
        for row,tokens in enumerate(input_ids.tolist()):
            banned=repeated_punctuation_next(tokens,self.punctuation,current_run=self.current_run)
            if banned:
                if output is scores:output=scores.clone()
                output[row,list(banned)]=-float("inf")
        return output


def decode_many_variant(recognizer,images,variant):
    if not images:return []
    if variant not in ("punctuation-only","punctuation-runs",*LENGTH_PENALTIES):
        with ngram_limit(recognizer,variant):return recognizer.recognize_many(images)
    pixels=recognizer.processor([image.convert("L").convert("RGB") for image in images],return_tensors="pt").pixel_values
    guard=PunctuationRepeatGuard(recognizer.tokenizer.get_vocab(),current_run=variant=="punctuation-runs")
    extra={"length_penalty":LENGTH_PENALTIES[variant]} if variant in LENGTH_PENALTIES else {}
    with recognizer._torch.inference_mode():
        encoded=recognizer.model.generate(pixels.to(recognizer.model.device),max_length=300,
            no_repeat_ngram_size=0,logits_processor=[guard],**extra)
    raw=recognizer.tokenizer.batch_decode(encoded.cpu(),skip_special_tokens=True)
    return [recognizer._post_process(text) for text in raw]


def recognize_variant(engine,image,variant):
    if blank_crop(image):return ""
    engine.load()
    return decode_many_variant(engine.model,[image],variant)[0]


class DecoderProbe(MangaEngine):
    """Full-page comparator with the same blank handling and batch size."""
    def __init__(self,model_dir,threads,variant):
        super().__init__(model_dir,threads)
        if variant not in ("punctuation-only","punctuation-runs",*LENGTH_PENALTIES):raise ValueError("Unsupported candidate")
        self.variant=variant;self.name=MangaEngine.name+"/"+variant+"-experiment"
        self.details={"kind":"repetition-policy-only","policy":variant,"production_default":False,
                      "weights":"same pinned manga-ocr","no_repeat_ngram_size":0}
        if variant in LENGTH_PENALTIES:self.details.update(kind="punctuation-policy-with-shorter-beams",length_penalty=LENGTH_PENALTIES[variant])
    def recognize(self,image):return self.recognize_many([image])[0]
    def recognize_many(self,images):
        result=[""]*len(images)
        valid=[(i,image) for i,image in enumerate(images) if not blank_crop(image)]
        if valid:
            self.load()
            decoded=decode_many_variant(self.model,[image for _,image in valid],self.variant)
            if len(decoded)!=len(valid):raise ValueError("OCR candidate changed batch cardinality")
            for (idx,_),value in zip(valid,decoded):result[idx]=value
        return result


@contextmanager
def ngram_limit(recognizer,value):
    if type(value) is not int or value not in (0,3):raise ValueError("Only one-field 0/3 ngram comparison is supported")
    config=recognizer.model.generation_config
    original=config.no_repeat_ngram_size
    try:
        config.no_repeat_ngram_size=value
        yield
    finally:config.no_repeat_ngram_size=original


def decoding_controls():
    yield from controls()
    font=ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc",29)
    for name,source in (("intentional-repeat","いやいやいやいや！"),
                        ("repeated-address","ねえ、ねえ、ねえ、ねえ！"),
                        ("repeated-with-quotes","「待って、待って、待って、待って！」"),
                        ("six-dot-pause","……待って。"),
                        ("nine-dot-pause","………本当に？"),
                        ("separate-long-pauses","待って……。いや……。まだ……。")):
        image=Image.new("RGB",(round(font.getlength(source))+24,62),"white")
        ImageDraw.Draw(image).text((12,8),source,font=font,fill="black")
        yield name,image,source


def summarize(rows,variant):
    selected=[row for row in rows if row["variant"]==variant]
    return {"variant":variant,"crops":len(selected),"exact":sum(r["exact"] for r in selected),
            "edits":sum(r["edits"] for r in selected),
            "cer":sum(r["edits"] for r in selected)/max(1,sum(r["characters"] for r in selected))}


def run(args):
    destination=Path(args.output).resolve()
    if ROOT/"artifacts" not in destination.parents:
        raise ValueError("Diagnostics must stay in this project's gitignored artifacts directory")
    candidate=("punctuation-mid" if getattr(args,"length_penalty_mid",False) else
               "punctuation-one" if getattr(args,"length_penalty_one",False) else
               "punctuation-runs" if getattr(args,"punctuation_runs",False) else
               "punctuation-only" if getattr(args,"punctuation_only",False) else None)
    if getattr(args,"pages",False):
        if not args.folder or candidate is None:raise ValueError("Full-page probe requires a private folder and one candidate policy")
        if getattr(args,"case",None) or getattr(args,"assert_variant",None) is not None:
            raise ValueError("Full-page probe cannot ignore crop-only flags --case/--assert-variant")
        from benchmark_pages import run as run_pages
        run_pages(args,engine_override=DecoderProbe(ROOT/"models/ocr",args.threads,candidate))
        return
    variants=(("punctuation-only",candidate) if candidate in LENGTH_PENALTIES else
              (3,candidate) if candidate else (3,0))
    cases=[];report={"field":"length_penalty" if candidate in LENGTH_PENALTIES else
                            "repetition_policy" if candidate else "generation_config.no_repeat_ngram_size",
        "production_defaults_changed":False,
        "variants":variants,"source":"author-created controls","rows":[],
        "limitations":["Not a translation or layout benchmark.","Labels require independent verification.",
                        "A punctuation guard may truncate intentional long pauses; source evidence is not trimmed.",
                        "Disabling repetition constraints may cause hallucinated loops; max_length remains bounded at 300."]}
    if args.folder:
        with DirectoryDataset(args.folder) as source:
            counts,issues,pages=audit(source)
            report.update(source="private audited gold crops",counts=counts,audit=issues,
                          input_fingerprint_sha256=dataset_fingerprint(source))
        for page,image,bubbles in pages:
            for bubble in bubbles:
                x,y,w,h=(bubble["bbox"][key] for key in ("x","y","w","h"))
                cases.append((page["page_id"]+":"+bubble["bubble_id"],image.crop((x,y,x+w,y+h)),bubble["ja_ocr_truth"]))
    else:cases=list(decoding_controls())
    if args.case:
        cases=[case for case in cases if case[0]==args.case]
        if not cases:raise ValueError("Case not found")
    threads=getattr(args,"threads",4)
    engine=MangaEngine(ROOT/"models/ocr",threads)
    start=time.perf_counter();engine.load()
    config=engine.model.model.generation_config
    report.update(engine=engine.name,threads=threads,load_ms=(time.perf_counter()-start)*1000,
        generation_config={key:getattr(config,key) for key in
            ("num_beams","length_penalty","do_sample","no_repeat_ngram_size","early_stopping")})
    for index,(name,image,reference) in enumerate(cases):
        for variant in variants:
            start=time.perf_counter();prediction=recognize_variant(engine,image,variant)
            elapsed=(time.perf_counter()-start)*1000
            ref,hyp=normalized(reference),normalized(prediction)
            report["rows"].append({"id":name,"variant":variant,"reference":reference,"prediction":prediction,
                "exact":ref==hyp,"edits":distance(ref,hyp),"characters":len(ref),"ms":elapsed,
                "review_required":len(hyp)>=290})
        print(json.dumps({"completed":index+1,"total":len(cases),"id":name}),flush=True)
    report["summaries"]=[summarize(report["rows"],variant) for variant in variants]
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps({"summaries":report["summaries"],"output":str(destination)}),flush=True)
    if args.assert_variant is not None:
        asserted=int(args.assert_variant) if str(args.assert_variant) in ("0","3") else args.assert_variant
        selected=[row for row in report["rows"] if row["variant"]==asserted]
        if not selected or not all(row["exact"] for row in selected):raise SystemExit(2)


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--folder")
    policies=parser.add_mutually_exclusive_group()
    policies.add_argument("--punctuation-only",action="store_true",help="Permit lexical repetition but retain old punctuation-only size-3 mask; experimental")
    policies.add_argument("--punctuation-runs",action="store_true",help="Only check punctuation triples in the current contiguous punctuation run; experimental")
    policies.add_argument("--length-penalty-one",action="store_true",help="One-field comparison: punctuation-only policy with the pinned length_penalty vs 1.0; experimental")
    policies.add_argument("--length-penalty-mid",action="store_true",help="One-field comparison: punctuation-only policy with the pinned length_penalty vs 1.5; experimental")
    parser.add_argument("--pages",action="store_true",help="Full-page local comparison via benchmark_pages, with the production detector/layout")
    parser.add_argument("--threads",type=int,choices=(1,2,4),default=4)
    parser.add_argument("--case",help="Minimize an authored or private case; never selects the best variant from gold")
    parser.add_argument("--assert-variant",choices=("0","3","punctuation-only","punctuation-runs",*LENGTH_PENALTIES))
    parser.add_argument("--output",default=str(ROOT/"artifacts/ocr-decoding-controls-20261014.json"))
    run(parser.parse_args())
