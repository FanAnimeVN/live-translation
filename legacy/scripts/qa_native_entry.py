"""Stack-only diagnostics for a disposable, authored-fixture browser host.

Not a production entry point. No locals, prompts, images or keys are recorded.
The actual host still enforces its configured extension origin.
"""
import faulthandler
import builtins
import json
from pathlib import Path
import sys
import tempfile
import os
import io

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))


def diagnostic_folder(arguments):
    index = arguments.index("--config")
    config = Path(arguments[index + 1]).resolve()
    folder = config.parent
    if not folder.is_relative_to(Path(tempfile.gettempdir()).resolve()) or not folder.name.startswith("mangalive-real-browser-"):
        raise ValueError("Stack diagnostics require an isolated QA temporary folder")
    data = json.loads(config.read_text(encoding="utf-8"))
    if Path(data["dataRoot"]).resolve() != folder / "data":
        raise ValueError("Reader data cannot be used for diagnostic QA")
    return folder


def detached_stdio(win32_handles=False):
    """Diagnostic counterfactual: native DLL stdio cannot consume browser IO.

    Keep the original Python wrappers alive after rebinding their descriptors.
    Transport uses duplicate descriptors; fd 0/1 become a private null device.
    No bytes are recorded and this helper is not a production entry point.
    """
    original = (sys.stdin, sys.stdout)
    reader = os.fdopen(os.dup(sys.stdin.fileno()), "rb", buffering=0)
    writer = os.fdopen(os.dup(sys.stdout.fileno()), "wb", buffering=0)
    null = os.open(os.devnull, os.O_RDWR)
    try:
        os.dup2(null, 0)
        os.dup2(null, 1)
    finally:
        os.close(null)
    if win32_handles and os.name == "nt":
        import ctypes
        from ctypes import wintypes
        import msvcrt
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.SetStdHandle.argtypes = [wintypes.DWORD, wintypes.HANDLE]
        kernel.SetStdHandle.restype = wintypes.BOOL
        for index, descriptor in ((-10, 0), (-11, 1)):
            if not kernel.SetStdHandle(index & 0xffffffff, msvcrt.get_osfhandle(descriptor)):
                raise ctypes.WinError(ctypes.get_last_error())
    sys.stdin = io.TextIOWrapper(reader, encoding="utf-8")
    sys.stdout = io.TextIOWrapper(writer, encoding="utf-8")
    # host.main redirects Python stdout to stderr. Keep this newly created
    # wrapper alive too, or its finalizer closes the duplicate transport fd.
    return original + (sys.stdin, sys.stdout)


if __name__ == "__main__":
    folder = diagnostic_folder(sys.argv)
    with (folder / "native-stack.log").open("w", encoding="utf-8") as trace:
        faulthandler.dump_traceback_later(35, repeat=True, file=trace)
        original_import=builtins.__import__;observed=set()
        def traced_import(name,*args,**kwargs):
            selected=name in {"numpy","paddleocr","paddle","paddlex","torch","cv2"} and name not in observed
            if selected:
                observed.add(name);trace.write("[DEBUG-qa-native-import] begin: "+name+"\n");trace.flush()
            result=original_import(name,*args,**kwargs)
            if selected:trace.write("[DEBUG-qa-native-import] end: "+name+"\n");trace.flush()
            return result
        builtins.__import__=traced_import
        try:
            config=json.loads((folder/"native-config.json").read_text(encoding="utf-8"))
            if config.get("qaModuleLines") is True:
                watched_files = {"torch/__init__.py", "paddle/__init__.py", "paddle/base/core.py",
                                 "paddle/base/framework.py", "paddlex/inference/utils/official_models.py",
                                 "paddleocr/__init__.py", "paddlex/__init__.py"}
                line_count = [0]
                observed_lines = set()
                def trace_module_lines(frame, event, arg):
                    filename = frame.f_code.co_filename.replace("\\", "/")
                    relative = filename.split("/site-packages/", 1)[-1]
                    selected = relative in watched_files or (relative.startswith(("paddlex/", "pydantic/", "pydantic_core/")) and
                        (frame.f_code.co_name == "<module>" or relative.endswith("/__init__.py")))
                    identity = (relative, frame.f_lineno)
                    if event == "line" and selected and identity not in observed_lines and line_count[0] < 4000:
                        observed_lines.add(identity)
                        line_count[0] += 1
                        trace.write(f"[DEBUG-qa-module-line] {relative}:{frame.f_lineno}\n")
                        trace.flush()
                    return trace_module_lines
                sys.settrace(trace_module_lines)
            if config.get("qaDetachStdio") is True:
                original_stdio = detached_stdio(config.get("qaDetachWin32") is True)
            if config.get("qaCwdRoot") is True:
                os.chdir(ROOT)
            library = config.get("qaLibraryProbe")
            if library is not None:
                if library not in ("torch", "paddle", "paddleocr", "pydantic"):
                    raise ValueError("Unsupported diagnostic library")
                # Match the real detector's disabled source check. A probe
                # must never introduce model-hub requests into offline QA.
                os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
                os.environ["HF_HUB_OFFLINE"] = "1"
                os.environ["TRANSFORMERS_OFFLINE"] = "1"
                from manga_live.pipeline import Pipeline
                def import_probe(self, cancel):
                    import importlib
                    import time
                    started = time.perf_counter()
                    if config.get("qaPrimeBaseModel") is True:
                        from pydantic import BaseModel
                    imported = importlib.import_module(library)
                    if library == "pydantic":
                        # PaddleX uses `from pydantic import BaseModel`.
                        # Package import alone leaves this lazy DLL path cold.
                        getattr(imported, "BaseModel")
                    return {"loadedLibrary": library, "importMs": (time.perf_counter()-started)*1000,
                            "modelsLoaded": False}
                Pipeline.warmup = import_probe
            if config.get("qaPrimeLibraries") is True:
                # Controlled counterfactual, before any transport reader exists.
                os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"]="True"
                os.environ["HF_HUB_OFFLINE"]="1"
                os.environ["TRANSFORMERS_OFFLINE"]="1"
                import numpy
                import torch
                import cv2
                import paddleocr
            from manga_live.host import main
            main()
        finally:
            sys.settrace(None)
            builtins.__import__=original_import
            faulthandler.cancel_dump_traceback_later()
