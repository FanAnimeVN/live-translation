"""Read a pinned external comparator as data. Never import, run or download it."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT=Path(__file__).resolve().parents[1]
COMMIT="d6de6ab62a7be6afc0d07a3184149cdefbcd32f2"
REPOSITORY="https://github.com/zyddnys/manga-image-translator"
MODEL_CLASSES={
    "detector":("manga_translator/detection/default.py","DefaultDetector"),
    "ocr48px":("manga_translator/ocr/model_48px.py","Model48pxOCR"),
    "inpainter":("manga_translator/inpainting/inpainting_lama_mpe.py","LamaLargeInpainter"),
}
AUDIT_FILES=("manga_translator/manga_translator.py","manga_translator/utils/inference.py",
    "manga_translator/utils/log.py","manga_translator/textline_merge/__init__.py",
    "manga_translator/config.py","requirements.txt","README.md")


def model_mapping(source,class_name):
    # literal_eval only accepts data. Do not import this GPL project into the
    # runtime or execute a model repository just to discover its metadata.
    tree=ast.parse(source)
    for node in tree.body:
        if not isinstance(node,ast.ClassDef) or node.name!=class_name:continue
        for statement in node.body:
            if not isinstance(statement,ast.Assign) or not any(isinstance(t,ast.Name) and t.id=="_MODEL_MAPPING" for t in statement.targets):continue
            try:mapping=ast.literal_eval(statement.value)
            except (TypeError,ValueError,SyntaxError) as error:raise ValueError("Nonliteral model mapping") from error
            if not isinstance(mapping,dict) or not mapping:raise ValueError("Missing model mapping")
            for spec in mapping.values():
                if (not isinstance(spec,dict) or not isinstance(spec.get("url"),str) or
                        not spec["url"].startswith("https://") or not isinstance(spec.get("hash"),str) or
                        not re.fullmatch(r"[a-f0-9]{64}",spec["hash"])):
                    raise ValueError("Unpinned or invalid model mapping")
            return mapping
    raise ValueError("Model mapping not found")


def io_evidence(source,path):
    evidence=[]
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node,ast.Call):continue
        name=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ""
        kind=None
        if name in ("imwrite","save","savefig"):kind="image_write"
        elif name in ("FileHandler","write_text","write_bytes"):kind="file_write"
        elif name=="open":
            mode=node.args[1] if len(node.args)>1 else next((k.value for k in node.keywords if k.arg=="mode"),None)
            if isinstance(mode,ast.Constant) and isinstance(mode.value,str) and any(c in mode.value for c in "wax+"):
                kind="file_write"
        elif name in ("download","_download","_download_file","download_url_with_progressbar"):kind="model_download"
        elif name in ("load","from_pretrained"):
            if isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id in ("torch","torchscript"):
                kind="checkpoint_load"
        if kind:evidence.append({"path":path,"line":node.lineno,"call":name,"kind":kind})
    return sorted(evidence,key=lambda row:row["line"])


def snapshot(commit,read_source):
    if commit!=COMMIT:raise ValueError("Comparator commit differs from reviewed pin")
    paths=tuple(dict.fromkeys(("LICENSE",*AUDIT_FILES,*(p for p,_ in MODEL_CLASSES.values()))))
    sources={path:read_source(path) for path in paths}
    if "GNU GENERAL PUBLIC LICENSE" not in sources["LICENSE"] or "Version 3" not in sources["LICENSE"]:
        raise ValueError("Unexpected comparator license; review again")
    models=[]
    for component,(path,cls) in MODEL_CLASSES.items():
        models.append({"component":component,"source":path,"class":cls,
            "upstream_mapping":model_mapping(sources[path],cls),"local_weights_verified":False})
    findings=[row for path,source in sources.items() if path.endswith(".py") for row in io_evidence(source,path)]
    return {"schema":1,"primary_comparator":"manga-image-translator","repository":REPOSITORY,
        "commit":commit,"license":"GPL-3.0","distribution":"external-comparator-only",
        "source_verified":True,"execution_allowed":False,"fresh_inference":False,"cloud":False,
        "source_files":[{"path":path,"sha256":hashlib.sha256(source.encode("utf-8")).hexdigest()} for path,source in sources.items()],
        "models":models,"io_findings":findings,
        "recipe":{"device":"cpu","detector":"default","ocr":"48px","inpainter":"lama_large",
            "upscale":False,"colorize":False,"verbose":False,"streaming":False},
        "blockers":["RAM-only adapter and transitive image/text logging paths not yet runtime-audited.",
            "Isolated dependency environment, all weights and font licenses/checksums not yet verified.",
            "Resolve mutable model URLs to immutable revisions before explicit provisioning.",
            "No inference or paired private-page quality/resource measurements have been run."],
        "limitations":["Static call locations are review leads, not proof of complete I/O isolation.",
            "Source code, model downloads and GPL obligations are separate from product runtime approval.",
            "No dataset opened, model imported, package installed or paid provider contacted."]}


def git_read(checkout,*arguments):
    result=subprocess.run(["git","--no-pager","-C",str(checkout),*arguments],check=True,
        capture_output=True,timeout=20)
    if len(result.stdout)>4*1024*1024:raise ValueError("Comparator source exceeds bound")
    return result.stdout.decode("utf-8")


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkout",default=str(ROOT/"artifacts/comparators/manga-image-translator"))
    parser.add_argument("--output",required=True);args=parser.parse_args()
    checkout=Path(args.checkout).resolve();destination=Path(args.output).resolve()
    if (ROOT/"artifacts").resolve() not in destination.parents or destination.suffix!=".json":
        raise ValueError("Comparator evidence stays under artifacts, outside the distributed bundle")
    if destination.exists():raise ValueError("Never overwrite recorded preflight evidence")
    commit=git_read(checkout,"rev-parse","HEAD").strip()
    report=snapshot(commit,lambda path:git_read(checkout,"show",commit+":"+path))
    destination.parent.mkdir(parents=True,exist_ok=True)
    with destination.open("x",encoding="utf-8") as stream:json.dump(report,stream,indent=2,allow_nan=False)
    print(json.dumps({"source_verified":True,"commit":commit,"io_review_locations":len(report["io_findings"]),
        "execution_allowed":False,"fresh_inference":False,"cloud":False}))


if __name__=="__main__":main()
