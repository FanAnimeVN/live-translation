"""Explicit CLI-only probe: fixed authored image, no reader files/vault/cloud.

Native protocol errors must not leak exception text from protected content.
This separate reproducible developer probe intentionally has no user input
besides the model folder, so its traceback describes runtime setup only.
"""
import json
from pathlib import Path
import time
import traceback


def detector_probe(models):
    from PIL import Image
    from .ocr import PaddleDetector
    start=time.perf_counter()
    result={"source":"fixed 64x64 blank authored image; runtime configuration only",
        "probe":"detector","reader_data_access":False,"cloud":False,"passed":False}
    try:
        regions=PaddleDetector(Path(models)/"detector",threads=4).detect(Image.new("RGB",(64,64),"white"))
        result.update(passed=True,regions=len(regions))
    except Exception as error:
        result.update(error_type=type(error).__name__,error=str(error),traceback=traceback.format_exc())
    result["ms"]=(time.perf_counter()-start)*1000
    print(json.dumps(result,ensure_ascii=True),flush=True)
    return 0 if result["passed"] else 1
