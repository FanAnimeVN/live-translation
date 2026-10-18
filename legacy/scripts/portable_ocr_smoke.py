"""Framed development/frozen OCR check, stopping before translation/cloud.

BYOK without consent is an intentional gate in the isolated QA profile. The
expected CONSENT error occurs AFTER native 'regions' events, so we can inspect
real detector/OCR imports without loading an LLM on an already busy machine.
"""
import argparse
import json
from pathlib import Path
import tempfile
import time
import uuid
import io

from fixture_server import synthetic_page
from native_smoke import NativeClient

ROOT=Path(__file__).resolve().parents[1]
ORIGIN="chrome-extension://epcjjhbilmmmbojldhnfblgmgiamajpl/"


def ocr_request(client, page_id, data, selection=None):
    image_id=uuid.uuid4().hex;revision=uuid.uuid4().hex;payloads=[];events=[]
    params={"imageId":image_id,"storyId":"portable-ocr-qa","title":"Authored fixture",
        "pageId":page_id,"revision":revision,"at":{"chapter":1,"page":0}}
    if selection:params["selection"]=selection
    start=time.perf_counter();client.image(data,image_id)
    try:
        client.call("pipeline",params,events,event_payloads=payloads)
        raise AssertionError("OCR fixture should hit the translation consent gate")
    except RuntimeError as error:
        code=json.loads(str(error)).get("code")
        if code!="CONSENT":
            raise RuntimeError("Frozen OCR failed before consent gate: "+str(error)) from error
    results=[reply["result"] for reply in payloads if reply["event"]=="regions"]
    regions=[region for result in results for region in result["regions"]]
    assert regions and all(result["revision"]==revision for result in results)
    return {"page":page_id,"ms":(time.perf_counter()-start)*1000,"events":events,
        "regions":regions,"stages":[reply.get("result",{}).get("stage") for reply in payloads if reply["event"]=="progress"],
        "stopped_before_cloud":True,"expected_error":"CONSENT"}


def assert_reused_ocr(original,retry):
    """Do not award a fast retry that omitted/reordered/changed its sources."""
    fields=lambda result:[(r["id"],r["ja"],r.get("bbox")) for r in result["regions"]]
    assert fields(retry)==fields(original),"Retry must retain every OCR region in order"
    assert "detector" not in retry["stages"],"Retry ran detection instead of reusing coverage"


def main():
    parser=argparse.ArgumentParser()
    mode=parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--host-executable")
    mode.add_argument("--development",action="store_true",help="Use current Python source, not the portable binary")
    parser.add_argument("--detector-only",action="store_true",help="Minimized repro: skip unrelated crop OCR")
    parser.add_argument("--output",default=str(ROOT/"artifacts/portable-ocr-smoke.json"))
    args=parser.parse_args();host=Path(args.host_executable).resolve() if args.host_executable else None
    folder=host.parent if host else ROOT
    if host:assert host.is_file() and (folder/"bundle.json").is_file()
    report={"source":"authored in-RAM image; real framed "+("frozen" if host else "development")+" detector/OCR; no translation/cloud",
        "standalone_host":bool(host),"development_python_or_entry_config":not bool(host),"runs":[],"passed":False,
        "limitations":["Not installed-browser E2E, manga-quality certification or LLM latency proof.",
            "This intentionally exercises the missing-consent error path after OCR."]}
    try:
        with tempfile.TemporaryDirectory(prefix="manga-frozen-ocr-qa-") as temporary:
            config=Path(temporary)/"native-config.json"
            config.write_text(json.dumps({"models":str(folder/"models"),"runtime":str(folder/"runtime/llama"),
                "dataRoot":temporary,"allowedOrigins":[ORIGIN]}),encoding="utf-8")
            client=NativeClient(config,standalone_host=host)
            try:
                hello=client.call("hello")
                report["runtime"]={"promptVersion":hello.get("promptVersion"),"ocrVersion":hello.get("ocrVersion")}
                client.call("settings",{"mode":"byok","cloudConsent":False,"autoSummary":False})
                image=synthetic_page()
                if not args.detector_only:
                    report["runs"].append(ocr_request(client,"crop",image,[440,70,320,230]))
                    print(json.dumps({"stage":"crop","regions":len(report["runs"][-1]["regions"]),
                        "ms":report["runs"][-1]["ms"]}),flush=True)
                    assert report["runs"][-1]["regions"][0]["ja"]=="姉ちゃん、まだ帰らないの？"
                report["runs"].append(ocr_request(client,"detected-page",image))
                print(json.dumps({"stage":"detector","regions":len(report["runs"][-1]["regions"]),
                    "ms":report["runs"][-1]["ms"]}),flush=True)
                original=report["runs"][-1]
                retry=ocr_request(client,"detected-page",image)
                assert_reused_ocr(original,retry)
                retry["name"]="retry-after-consent-error";report["runs"].append(retry)
                print(json.dumps({"stage":"retry-ocr-coverage","regions":len(retry["regions"]),
                    "ms":retry["ms"],"translation_excluded":True}),flush=True)
                report["runs"].append(ocr_request(client,"warm-detected-page",image))
                print(json.dumps({"stage":"warm-detector-ocr","regions":len(report["runs"][-1]["regions"]),
                    "ms":report["runs"][-1]["ms"],"translation_excluded":True}),flush=True)
                from PIL import Image
                blank=io.BytesIO();Image.new("RGB",(800,1050),"white").save(blank,format="PNG")
                image_id=uuid.uuid4().hex;client.image(blank.getvalue(),image_id)
                empty=client.call("pipeline",{"imageId":image_id,"storyId":"portable-ocr-qa","title":"Authored blank",
                    "pageId":"blank","revision":uuid.uuid4().hex,"at":{"chapter":1,"page":0}})
                assert empty["regions"]==[],"Blank authored page must not produce dialogue"
                report["blank_page_has_no_dialogue"]=True
                # A new native process in the same isolated profile must restore
                # source coverage without loading either OCR or detector again.
                # This is NOT a new OCR latency sample or translation cache hit.
                profile=client.profile;client.close()
                client=NativeClient(config,standalone_host=host);client.profile=profile
                assert not client.call("hello")["engineWarm"]
                restored=ocr_request(client,"detected-page",image)
                assert_reused_ocr(original,restored)
                assert not client.call("status")["engineWarm"],"Cached OCR must not warm cold engines"
                restored["name"]="retry-after-host-restart";report["runs"].append(restored)
                report["ocr_coverage_restored_without_loading_engines"]=True
                print(json.dumps({"stage":"retry-after-host-restart","regions":len(restored["regions"]),
                    "ms":restored["ms"],"engines_remain_cold":True,"translation_excluded":True}),flush=True)
                report["passed"]=True
            except Exception:
                # This profile contains only our authored fixture and no keys.
                # Never enable raw runtime diagnostics for the reader profile.
                report["authored_fixture_runtime_diagnostics"]=client.diagnostics[-60:]
                raise
            finally:client.close()
    except Exception as error:
        report["error"]=str(error);raise
    finally:
        destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
        destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")


if __name__=="__main__":main()
