"""Private ZIP/folder benchmark: RAM images; no dataset or gold labels in releases."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import statistics
import sys
import time
import unicodedata
import zipfile
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from manga_live.ocr import MangaEngine, decode_image


def flat_filename(value):
    if (not isinstance(value, str) or not value or value in (".", "..") or
            any(c in value for c in ("/", "\\", ":", "\x00"))):
        raise ValueError("Only flat dataset filenames are accepted")
    return value


class DirectoryDataset:
    """Archive-compatible, bounded read-only access; never follow escaped links."""
    def __init__(self, root):
        self.root = Path(root).resolve(strict=True)
        if not self.root.is_dir():
            raise ValueError("Dataset folder is not a directory")

    def getinfo(self, filename):
        filename = flat_filename(filename)
        target = (self.root / filename).resolve(strict=True)
        if target.parent != self.root or not target.is_file():
            raise ValueError("Dataset entry escapes the selected folder")
        return SimpleNamespace(filename=filename, file_size=target.stat().st_size)

    def read(self, entry):
        filename = entry if isinstance(entry, str) else entry.filename
        info = self.getinfo(filename)
        limit = 2000000 if filename == "ground_truth_benchmark.json" else 8000000
        if info.file_size > limit:
            raise ValueError("Dataset entry too large")
        target = (self.root / filename).resolve(strict=True)
        if target.parent != self.root:
            raise ValueError("Dataset entry changed location")
        with target.open("rb") as source:
            value = source.read(limit + 1)
        if len(value) > limit or len(value) != info.file_size:
            raise ValueError("Dataset entry changed size")
        return value

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def dataset_source(args):
    return DirectoryDataset(args.folder) if getattr(args, "folder", None) else zipfile.ZipFile(args.zip)


def dataset_fingerprint(archive):
    labels = archive.read("ground_truth_benchmark.json")
    digest = hashlib.sha256(labels)
    for filename in sorted({flat_filename(page["image_file"]) for page in json.loads(labels)}):
        digest.update(filename.encode("utf-8"))
        digest.update(hashlib.sha256(archive.read(filename)).digest())
    return digest.hexdigest()


def normalized(value):
    return "".join(unicodedata.normalize("NFKC", value).split())


def distance(a, b):
    prev = list(range(len(b)+1))
    for i,x in enumerate(a,1):
        row = [i]
        for j,y in enumerate(b,1):
            row.append(min(row[-1]+1, prev[j]+1, prev[j-1]+(x != y)))
        prev = row
    return prev[-1]


def audit(archive):
    entry = archive.getinfo("ground_truth_benchmark.json")
    if entry.file_size > 2000000:
        raise ValueError("Label file too large")
    pages = json.loads(archive.read(entry))
    if not isinstance(pages, list) or not 1 <= len(pages) <= 1000:
        raise ValueError("Labels must contain a bounded nonempty page list")
    issues, valid, seen, seen_pages = [], [], {}, set()
    counts = {"pages":len(pages), "bubbles":0, "vi_labels":0}
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get("page_id"), str):
            raise ValueError("Invalid page label")
        if page["page_id"] in seen_pages:
            issues.append({"page":page["page_id"], "issue":"duplicate_page_id"})
            continue
        seen_pages.add(page["page_id"])
        if not isinstance(page.get("bubbles"), list) or len(page["bubbles"]) > 256:
            raise ValueError("Invalid bubble collection")
        filename = flat_filename(page["image_file"])
        if archive.getinfo(filename).file_size > 8000000:
            raise ValueError("Invalid image entry")
        data = archive.read(filename)
        image = decode_image(data)
        sha = hashlib.sha256(data).hexdigest()
        counts["bubbles"] += len(page["bubbles"])
        counts["vi_labels"] += sum(bool(b.get("vi_gold_trans","").strip()) for b in page["bubbles"])
        if sha in seen:
            issues.append({"page":page["page_id"], "issue":"duplicate_image", "duplicate_of":seen[sha]})
            continue
        seen[sha] = page["page_id"]
        declared = page["image_size"]
        if (declared["w"],declared["h"]) != image.size:
            issues.append({"page":page["page_id"], "issue":"image_size_mismatch", "declared":declared, "actual":image.size})
            continue
        valid_bubbles, seen_bubbles = [], set()
        for bubble in page["bubbles"]:
            if not isinstance(bubble, dict) or not isinstance(bubble.get("bubble_id"), str):
                raise ValueError("Invalid bubble label")
            if bubble["bubble_id"] in seen_bubbles:
                issues.append({"page":page["page_id"], "bubble":bubble["bubble_id"], "issue":"duplicate_bubble_id"})
                continue
            seen_bubbles.add(bubble["bubble_id"])
            box = bubble.get("bbox", {})
            values = [box.get(k) for k in ("x","y","w","h")] if isinstance(box, dict) else []
            if len(values) != 4 or any(type(v) is not int for v in values):
                issues.append({"page":page["page_id"], "bubble":bubble["bubble_id"], "issue":"invalid_box"})
                continue
            x,y,w,h = values
            if min(x,y) < 0 or min(w,h) <= 0 or x+w > image.width or y+h > image.height:
                issues.append({"page":page["page_id"], "bubble":bubble["bubble_id"], "issue":"invalid_box"})
            elif not isinstance(bubble.get("ja_ocr_truth"), str) or not bubble["ja_ocr_truth"].strip():
                issues.append({"page":page["page_id"], "bubble":bubble["bubble_id"], "issue":"empty_ja_label"})
            else:
                valid_bubbles.append(bubble)
        valid.append((page, image, valid_bubbles))
    counts["eligible_pages"] = len(valid)
    counts["eligible_bubbles"] = sum(len(p[2]) for p in valid)
    counts["eligible_vi_labels"] = sum(bool(b.get("vi_gold_trans", "").strip()) for _, _, bubbles in valid for b in bubbles)
    return counts, issues, valid


def run(args):
    with dataset_source(args) as archive:
        counts, issues, pages = audit(archive)
        fingerprint = dataset_fingerprint(archive)
    report = {"schema":2, "input_kind":"folder" if getattr(args,"folder",None) else "zip",
              "input_fingerprint_sha256":fingerprint,
              "counts":counts,"audit":issues,"normalization":"NFKC + remove whitespace",
              "limitations":["User-supplied transcription labels not independently verified.",
                  "Crop benchmark uses ground-truth boxes; detection and page latency are excluded.",
                  "Vietnamese references are sparse; no translation-quality conclusion from this set."]}
    if args.audit_only:
        print(json.dumps(report, ensure_ascii=True, indent=2))
    else:
        if not counts["eligible_bubbles"]:
            raise ValueError("No eligible ground-truth crops; fix audit issues first")
        engine = MangaEngine(args.model_dir,args.threads)
        start = time.perf_counter()
        engine.load()
        report["load_seconds"] = time.perf_counter()-start
        rows, edits, characters, exact, durations = [],0,0,0,[]
        for page,image,bubbles in pages:
            for bubble in bubbles:
                x,y,w,h = (bubble["bbox"][k] for k in ("x","y","w","h"))
                start = time.perf_counter()
                result = engine.recognize(image.crop((x,y,x+w,y+h)))
                elapsed = time.perf_counter()-start
                ref,hyp = normalized(bubble["ja_ocr_truth"]),normalized(result)
                error = distance(ref,hyp)
                edits += error
                characters += len(ref)
                exact += ref == hyp
                durations.append(elapsed*1000)
                rows.append({"page":page["page_id"],"id":bubble["bubble_id"],"reference":ref,
                             "prediction":hyp,"edits":error,"characters":len(ref),"ms":elapsed*1000})
            print(json.dumps({"completed_page":page["page_id"],"crops":len(rows)},ensure_ascii=True),flush=True)
        ranked = sorted(durations)
        report.update(engine=engine.name,threads=args.threads,device="CPU",python=sys.version.split()[0],
                      processor=os.environ.get("PROCESSOR_IDENTIFIER","unknown"),crop_count=len(rows),
                      cer=edits/max(characters,1),exact_match=exact/max(len(rows),1),
                      p50_crop_ms=statistics.median(durations),
                      p95_crop_ms=ranked[min(len(ranked)-1,int(len(ranked)*0.95))],
                      raw_results=rows)
        print(json.dumps({k:v for k,v in report.items() if k != "raw_results"},ensure_ascii=True,indent=2))
    destination = Path(args.output)
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    if getattr(args,"assert_perfect",False):
        passed=perfect_crop_gate(report)
        print(json.dumps({"perfect_crop_gate":passed,"required":"valid audited data and every eligible transcription exact",
            "translation_gate":"not measured by an OCR benchmark"}),flush=True)
        if not passed:raise SystemExit(2)


def perfect_crop_gate(report):
    """Do not call a partial/audit-only or rounded CER result perfect."""
    count=report.get("crop_count",0)
    return (not report.get("audit") and count>0 and
        count==report.get("counts",{}).get("eligible_bubbles") and
        len(report.get("raw_results",[]))==count and
        all(row.get("edits")==0 and row.get("prediction")==row.get("reference")
            for row in report["raw_results"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument("--zip")
    inputs.add_argument("--folder")
    parser.add_argument("--model-dir",default=str(ROOT/"models/ocr"))
    parser.add_argument("--output",default=str(ROOT/"artifacts/benchmark.json"))
    parser.add_argument("--threads",type=int,default=4)
    parser.add_argument("--audit-only",action="store_true")
    parser.add_argument("--assert-perfect",action="store_true",help="Fail with exit 2 unless audited source crops are all exact; never a translation certificate")
    run(parser.parse_args())
