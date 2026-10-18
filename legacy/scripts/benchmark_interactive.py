"""Compare first-overlay scheduling on real local engines, synthetic pages only.

No cloud calls, keys, private manga or on-disk images. Save measurements after
each run so an interrupted benchmark is not mistaken for no progress.
"""
import argparse
import io
import json
from pathlib import Path
import statistics
import sys
import tempfile
import threading
import time
from PIL import Image,ImageDraw,ImageFont
from fixture_server import synthetic_page

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.config import Config
from manga_live.memory import Memory
from manga_live.pipeline import Pipeline
import manga_live.providers as providers


def dense_page():
    image=Image.new("RGB",(800,1800),"#eeeae4");draw=ImageDraw.Draw(image)
    font=ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc",25)
    lines=[
        ["田中さん、","今日は来ないの？"],["来なくてもいいって","先生が言ってたよ。"],
        ["お兄ちゃん、","待って！"],["まだ終わってない。","少し待ってて。"],
        ["氷結結界を","展開する！"],["魔力が切れたら、","すぐ戻って。"],
        ["本当に？","冗談じゃないの？"],["冗談じゃない。","約束したんだ。"],
        ["先に帰ってて。","あとで行くから。"],["じゃあ、","無理しないでね。"],
        ["もう終わった？"],["まだだけど、","もう少しだよ。"],
    ]
    for index,texts in enumerate(lines):
        row,col=divmod(index,2);x=440 if col==0 else 55;y=30+row*290
        draw.ellipse((x,y,x+305,y+250),fill="white",outline="#333",width=3)
        for n,line in enumerate(texts):
            width=draw.textlength(line,font=font)
            draw.text((x+(305-width)/2,y+75+n*40),line,font=font,fill="black")
    data=io.BytesIO();image.save(data,format="PNG");return data.getvalue()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--repeats",type=int,choices=range(1,5),default=2)
    parser.add_argument("--threads",type=int,choices=(4,6,8),default=4)
    parser.add_argument("--dense",action="store_true")
    parser.add_argument("--output",default=str(ROOT/"artifacts/interactive-pilot.json"))
    args=parser.parse_args();rows=[];cancel=threading.Event()
    destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
    base_post=providers.post_json
    def seeded(url,body,*rest,**kwargs):return base_post(url,{**body,"seed":0},*rest,**kwargs)
    providers.post_json=seeded
    with tempfile.TemporaryDirectory(prefix="manga-interactive-") as temporary:
        config=Config(temporary);config.update({"mode":"offline","threads":args.threads})
        memory=Memory(Path(temporary)/"memory.sqlite3");memory.ensure_story("synthetic","Test","fantasy")
        memory.canonical_term("synthetic","ice","skill","氷結結界","Băng Kết Kết Giới",[],{"chapter":1,"page":0})
        translator=providers.Translator(config,None,ROOT/"models",ROOT/"runtime/llama")
        pipeline=Pipeline(memory,translator,config,ROOT/"models")
        try:
            warmup=pipeline.warmup(cancel)
            # Prime inference kernels/prefix independently of either variant.
            translator.translate([{"id":"r000","ja":"ありがとう。"}],{},cancel)
            pages=[("four",synthetic_page())]
            if args.dense:pages.append(("twelve",dense_page()))
            for repeat in range(args.repeats):
                for name,data in pages:
                    variants=[4,2] if repeat%2==0 else [2,4]
                    for size in variants:
                        pipeline.first_batch_size=size
                        events=[];start=time.perf_counter()
                        def emit(event,value):
                            events.append({"event":event,"at_ms":(time.perf_counter()-start)*1000})
                            if event=="translated":
                                print(json.dumps({"page":name,"repeat":repeat,"first_batch":size,
                                    "completed_group":len(value["regions"]),"at_ms":events[-1]["at_ms"]}),flush=True)
                        params={"storyId":"synthetic","title":"Test","pageId":f"{name}-{repeat}-{size}",
                            "revision":"test","at":{"chapter":1,"page":1}}
                        row={"page":name,"repeat":repeat,"first_batch":size,"threads":args.threads}
                        try:
                            result=pipeline.process(params,data,cancel,emit)
                            row.update(ok=True,events=events,metrics=result["metrics"],regions=result["regions"])
                        except Exception as error:row.update(ok=False,error=str(error),events=events)
                        rows.append(row)
                        report={"source":"author-created synthetic images; real CPU detector/OCR/translation",
                            "warmup":warmup,"rows":rows,
                            "limits":["Small non-blind pilot, not representative p95 or manga-quality certification.",
                                      "First-overlay metrics exclude browser capture/render time."]}
                        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
                        print(json.dumps({k:v for k,v in row.items() if k not in ("regions","events")}),flush=True)
            for name,_ in pages:
                for size in (4,2):
                    selected=[r["metrics"] for r in rows if r["ok"] and r["page"]==name and r["first_batch"]==size]
                    if selected:
                        print(json.dumps({"page":name,"first_batch":size,"runs":len(selected),
                            "median_first_ms":statistics.median(r["first_overlay_ms"] for r in selected),
                            "median_total_ms":statistics.median(r["total_ms"] for r in selected)}),flush=True)
        finally:providers.post_json=base_post;translator.stop();memory.close()


if __name__=="__main__":main()
