"""Isolated real Native Messaging, with captured model output replay only.

All source pixels/cleanup are RAM-only. No key, cloud, model or provider
fallback is allowed. This entry is never installed as the reader's host.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"companion"),str(ROOT/"scripts")]
from qa_native_entry import diagnostic_folder
from private_render_payload import build_payload
from manga_live.ocr import decode_image
from manga_live.errors import AppError


def forbid_inference(*args,**kwargs):
    raise AppError("REPLAY_NETWORK","Replay không cho gọi model/provider/metadata.")


def configure_replay(host,payload):
    host.config.update({"mode":"offline","autoSummary":False,"metadataConsent":False,"cloudConsent":False})
    def process(params,data,cancel,emit):
        image=decode_image(data)
        if cancel.is_set():raise AppError("CANCELED","Đã hủy replay.")
        native=payload["native"]
        if image.size!=(native["width"],native["height"]) or hashlib.sha256(image.tobytes()).hexdigest()!=payload["pixel_sha256"]:
            raise AppError("REPLAY_SOURCE","Pixel nguồn replay không khớp ảnh đã kiểm tra.")
        for patch in payload["patches"]:
            if cancel.is_set():raise AppError("CANCELED","Đã hủy replay.")
            emit("render-patch",{"revision":params["revision"],"width":image.width,"height":image.height,"patch":deepcopy(patch)})
        result=deepcopy(native);result.update(revision=params["revision"],cached=False,metrics={"total_ms":1,"render_replay":True})
        return result
    host.pipeline.process=process
    # An accidental button click/settings change must not turn replay into an
    # OCR/model/metadata run, even through a local route or summary worker.
    host.pipeline.warmup=host.pipeline.retranslate=forbid_inference
    host.translator.translate=host.translator.summarize=forbid_inference
    host.metadata.search=forbid_inference


def main():
    folder=diagnostic_folder(sys.argv)
    config=json.loads((folder/"native-config.json").read_text(encoding="utf-8"))
    replay=config.get("qaRenderReplay",{})
    if replay.get("enabled") is not True:raise ValueError("Explicit replay mode required")
    payload=build_payload(SimpleNamespace(folder=replay["folder"],page=replay["page"],
        native_result=replay["nativeResult"],reference=str(ROOT/"artifacts/private-pages-20261014-local-v3-contract.json")))
    import manga_live.providers as providers
    from manga_live.host import Host,main as host_main
    base_initialize=Host.initialize;base_post=providers.post_json
    def initialize(self,profile):
        base_initialize(self,profile)
        configure_replay(self,payload)
    Host.initialize=initialize;providers.post_json=forbid_inference
    try:host_main()
    finally:Host.initialize=base_initialize;providers.post_json=base_post


if __name__=="__main__":main()
