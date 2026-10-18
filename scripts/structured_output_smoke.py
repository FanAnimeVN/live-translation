"""A tiny real-runtime schema enforcement probe; never a translation benchmark.

The instruction asks for ordinary Vietnamese text, while the constrained schema
requires exactly {"probe":"OK"}. If the latter is not enforced, fail visibly.
No key, cloud, OCR, private image, reader profile or runtime setting mutation.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.providers import Translator
import manga_live.providers as providers
from manga_live.config import Config
from manga_live.errors import AppError


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--shape",choices=("production","native-json-object","top-level-schema"),default="production")
    parser.add_argument("--deadline",type=int,choices=range(10,61),default=40)
    args=parser.parse_args()
    directory=Path(tempfile.mkdtemp(prefix="mangalive-schema-"))
    config=Config(directory/"config");config.update({"mode":"offline"})
    translator=Translator(config,None,ROOT/"models",ROOT/"runtime/llama")
    cancel=threading.Event();timer=threading.Timer(args.deadline,cancel.set);timer.daemon=True;timer.start()
    report={"passed":False,"shape":args.shape,"source":"authored schema probe, not manga",
            "runtime":"llama.cpp b11429 d81235049 (verify binary --version)",
            "limitations":["Tests schema syntax enforcement, not translation semantics or the full extension."],"requests":[]}
    post=providers.post_json;start=time.perf_counter()
    schema={"type":"object","properties":{"probe":{"type":"string","enum":["OK"]}},
            "required":["probe"],"additionalProperties":False}
    def instrument(url,body,*rest,**kwargs):
        assert kwargs.get("local") is True and url.startswith("http://127.0.0.1:")
        body={**body,"seed":0}
        if args.shape=="native-json-object":body["response_format"]={"type":"json_object","schema":schema}
        elif args.shape=="top-level-schema":
            body.pop("response_format",None);body["json_schema"]=schema
        reply=post(url,body,*rest,**kwargs)
        choice=reply["choices"][0]
        report["requests"].append({"format":body.get("response_format"),"json_schema":body.get("json_schema"),
                                   "finish_reason":choice.get("finish_reason"),"text":choice["message"]["content"],
                                   "usage":reply.get("usage",{})})
        return reply
    providers.post_json=instrument
    print(json.dumps({"evidence":str(directory/"result.json"),"shape":args.shape}),flush=True)
    try:
        raw,usage=translator.local.generate("Translate the following Japanese into Vietnamese. Output only the translated result without explanation:\nこんにちは。",cancel,schema,max_tokens=48)
        try:report["passed"]=json.loads(raw)=={"probe":"OK"}
        except ValueError:pass
    except AppError as error:report["error"]=error.code
    finally:
        providers.post_json=post;timer.cancel();cancel.set();translator.stop()
        report["total_ms"]=(time.perf_counter()-start)*1000
        (directory/"result.json").write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps({"passed":report["passed"],"requests":report["requests"],
                          "error":report.get("error"),"total_ms":report["total_ms"]},ensure_ascii=True),flush=True)
    return 0 if report["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
