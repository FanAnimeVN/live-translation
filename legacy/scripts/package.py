"""Build development launchers or a self-contained Windows CPU QA bundle."""
import argparse
from importlib import metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from portable_bundle import BUNDLE_PROFILES,stage_models,stage_runtime,stage_detector_metadata,write_checksums

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.prompts import PROMPT_VERSION
from manga_live.runtime_build import source_build,RECORD_NAME


def freeze(name,entry,dist,work,options):
    environment={**os.environ,"HF_HUB_OFFLINE":"1","TRANSFORMERS_OFFLINE":"1",
        "PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK":"True"}
    if entry=="installer/setup.py":
        # PyInstaller can exit successfully after excluding a broken tkinter.
        # Fail before it overwrites a working installer.  This starts only a
        # Tcl interpreter (no window, model, registry or reader-profile access).
        probe=("import os, tkinter, _tkinter; from pathlib import Path; "
            "interpreter=tkinter.Tcl(); library=Path(interpreter.eval('info library')); "
            "tk=Path(os.environ.get('TK_LIBRARY',str(library.parent/('tk'+_tkinter.TK_VERSION)))); "
            "assert (library/'init.tcl').is_file() and (tk/'tk.tcl').is_file()")
        result=subprocess.run([sys.executable,"-B","-c",probe],env=environment,
            capture_output=True,timeout=15)
        if result.returncode!=0:
            raise RuntimeError("Tcl/Tk không hoạt động trong môi trường build; dừng trước khi ghi đè bộ cài. "
                "Kiểm tra runtime và tài khoản build, không bỏ qua hook tkinter.")
    frozen_build=None
    if entry=="companion/entry.py":
        frozen_build=source_build()
        work.mkdir(parents=True,exist_ok=True)
        record=work/RECORD_NAME
        record.write_text(json.dumps({"v":1,"runtimeBuild":frozen_build}),encoding="utf-8")
        options=[*options,"--add-data",str(record)+os.pathsep+"manga_live"]
    subprocess.run([sys.executable,"-m","PyInstaller","--noconfirm","--noupx","--name",name,
        "--distpath",str(dist),"--workpath",str(work),"--specpath",str(work),
        "--paths",str(ROOT/"scripts"),"--paths",str(ROOT/"companion"),*options,str(ROOT/entry)],
        cwd=ROOT,env=environment,check=True)
    if frozen_build is not None and source_build()!=frozen_build:
        raise RuntimeError("Runtime package changed during freeze; bundle is not verified. Rebuild from a stable source tree.")
    return frozen_build


def run_checks():
    # Shared Windows pytest temp/cache directories may be locked by a previous
    # account/session. Never erase those trees or weaken the test gate.
    parent=ROOT/"build";parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="package-check-",dir=parent) as temporary:
        subprocess.run([sys.executable,"-B","-m","pytest","-q","-p","no:cacheprovider",
            "--basetemp",str(Path(temporary)/"cases")],cwd=ROOT,check=True)
    subprocess.run(["npm.cmd" if os.name=="nt" else "npm","run","check"],cwd=ROOT,check=True)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--mode",choices=("development","portable"),default="development")
    parser.add_argument("--profile",choices=BUNDLE_PROFILES,default="cloud-first",
                        help="Portable cloud-first excludes local translation/summary GGUF and llama.cpp")
    args=parser.parse_args()
    run_checks()
    if args.mode=="development":
        for name,entry,mode in (("MangaLiveHost","companion/launcher.py","--console"),("Install companion","installer/setup.py","--windowed")):
            freeze(name,entry,ROOT/"dist/windows",ROOT/"build/development"/name,["--onefile",mode])
        print("Development launchers built; retain .venv, companion, models and runtime.",flush=True)
        return
    output=(ROOT/("dist/portable-cloud-first" if args.profile=="cloud-first" else "dist/portable")).resolve()
    if not output.is_relative_to(ROOT.resolve()) or output==ROOT.resolve():raise ValueError("Invalid build output")
    work=ROOT/("build/portable-cloud-first" if args.profile=="cloud-first" else "build/portable")
    options=["--onedir","--console","--collect-all","manga_ocr","--collect-all","paddle",
        "--collect-all","paddleocr","--collect-all","paddlex","--collect-data","transformers",
        "--collect-data","unidic_lite",
        "--hidden-import","keyring.backends.Windows"]
    for module in ("transformers.models.bert.modeling_bert","transformers.models.bert.tokenization_bert",
        "transformers.models.bert.tokenization_bert_fast","transformers.models.bert_japanese.tokenization_bert_japanese",
        "transformers.models.vit.image_processing_vit","transformers.models.vit.modeling_vit",
        "transformers.models.vision_encoder_decoder.modeling_vision_encoder_decoder"):
        options.extend(("--hidden-import",module))
    for module in ("tensorflow","jax","IPython","pytest","matplotlib"):
        options.extend(("--exclude-module",module))
    runtime_build=freeze("MangaLiveHost","companion/entry.py",output,work/"host",options)
    folder=output/"MangaLiveHost"
    freeze("Install companion","installer/setup.py",folder,work/"installer",["--onefile","--windowed"])
    models=stage_models(ROOT,folder,profile=args.profile)
    if args.profile=="offline":stage_runtime(ROOT,folder)
    stage_detector_metadata(folder)
    dependencies=[]
    for name in ("python","manga-ocr","torch","transformers","paddleocr","paddlepaddle","paddlex","opencv-contrib-python","opencv-python-headless","pyclipper","shapely","pypdfium2","numpy","Pillow","keyring","pyinstaller"):
        if name=="python":dependencies.append({"name":name,"version":sys.version.split()[0]});continue
        distribution=metadata.distribution(name)
        dependencies.append({"name":name,"version":distribution.version,
            "license":distribution.metadata.get("License-Expression") or distribution.metadata.get("License"),
            "license_files":distribution.metadata.get_all("License-File") or []})
    (folder/"dependency-licenses.json").write_text(json.dumps({"dependencies":dependencies,
        "note":"Installed build dependency inventory, not a complete redistribution/license audit."},indent=2),encoding="utf-8")
    (folder/"bundle.json").write_text(json.dumps({"schema":1,"kind":"portable","version":"0.1.0","profile":args.profile,
        "runtimeBuild":runtime_build,
        "promptVersion":PROMPT_VERSION,
        "models":[name for name in models if name!="schema"],"release":"private-qa-unsigned",
        "extensionId":"epcjjhbilmmmbojldhnfblgmgiamajpl",
        "limitations":["Not signed; not a commercial/public release.","Installed-browser and clean-Windows inference checks required.",
            *(["BYOK translation needs a reader key and explicit cloud consent; local OCR/detector are included. Local LLM translation/summary are not included."]
              if args.profile=="cloud-first" else [])]},indent=2),encoding="utf-8")
    inventory=write_checksums(folder)
    print(json.dumps({"bundle":str(folder),"files":len(inventory["files"]),
        "bytes":sum(record["bytes"] for record in inventory["files"].values()),
        "self_contained_build":True,"runtime_verified":False,"development_registration_changed":False}),flush=True)


if __name__=="__main__":main()
