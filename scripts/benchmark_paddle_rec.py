"""Private CPU line-recognition comparator; never imported by the companion.

Explicit --fetch-model is the only network operation. Inference uses the
installed PaddleOCR implementation and pinned official declarative weights.
Images/crops stay in RAM; only private text diagnostics enter artifacts/.
Multi-line ground-truth crops are split with the existing detector, not fed
as one line to a recognizer that cannot read an entire manga balloon.
"""
import argparse
import json
from importlib import metadata
import math
import os
import platform
from pathlib import Path
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from benchmark import audit, dataset_source, dataset_fingerprint, normalized, distance
from provision import download, verify
from manga_live.ocr import PaddleDetector, blank_crop, rect, group_regions, LAYOUT_VERSION


MODEL_NAME = "PP-OCRv5_mobile_rec"
MODEL_REPO = "PaddlePaddle/PP-OCRv5_mobile_rec"
MODEL_REVISION = "682f20538d8c086cb2128e5cfac775e6c4904e85"
MODEL_FILES = {
    "inference.json": {"bytes": 217724, "gitBlob": "90f76a83768033cbd2bc9aa4d10aaa08e7bf25f7"},
    "inference.pdiparams": {"bytes": 16458665, "sha256": "2460da90875937c94db97eba74ae3d9e5d4c4c57c42f1f41531c09a26bcc771a"},
    "inference.yml": {"bytes": 148345, "gitBlob": "176f6d552a120e6fa0a812089fb36c1bb983ce28"},
}
MODEL_PATH = ROOT / "artifacts/comparator-models/pp-ocrv5-mobile-rec"


def fetch_model(destination):
    for filename, spec in MODEL_FILES.items():
        download(f"https://huggingface.co/{MODEL_REPO}/resolve/{MODEL_REVISION}/{filename}",
                 Path(destination) / filename, spec)


def validate_model(path):
    if not all(verify(Path(path) / name, spec) for name, spec in MODEL_FILES.items()):
        raise ValueError("Missing or mismatched comparator model; use explicit --fetch-model")


def checked_prediction(payload):
    """Do not strip punctuation, threshold away low scores, or trust NaN."""
    if not isinstance(payload, dict):
        raise ValueError("Invalid line recognizer output")
    data = payload.get("res", payload)
    if not isinstance(data, dict):
        raise ValueError("Invalid line recognizer output")
    value, score = data.get("rec_text"), data.get("rec_score")
    if (not isinstance(value, str) or len(value) > 4096 or isinstance(score, bool) or
            not isinstance(score, (int, float)) or not math.isfinite(score) or not 0 <= score <= 1):
        raise ValueError("Invalid line recognizer output")
    return value, float(score)


def ordered_lines(lines):
    """Geometry-only ordering within ONE annotation crop, not a panel parser.

    Tall column-major crops go right-to-left, ordinary horizontal lines go
    top-to-bottom. Mixed/diagonal/furigana arrangements remain a limitation;
    this heuristic must never inspect the reference text to pick an order.
    """
    boxes = [rect(line["polygon"]) for line in lines]
    vertical = bool(boxes and sum(h >= 1.5*w for _, _, w, h in boxes) > len(boxes)/2)
    indexed = list(zip(lines, boxes))
    indexed.sort(key=lambda item: (-item[1][0], item[1][1]) if vertical else
                 (item[1][1], item[1][0]))
    return [line for line, _ in indexed], "vertical-rtl" if vertical else "horizontal-top-down"


class PaddleLineRecognizer:
    """Native local static engine; no Transformers update or remote Python."""
    def __init__(self, model_dir, threads=4):
        self.path, self.threads = Path(model_dir), threads
        self.model, self.cropper = None, None

    def load(self):
        if self.model is not None:
            return
        validate_model(self.path)
        os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "True"
        os.environ["PADDLE_PDX_CACHE_HOME"] = str(ROOT / "runtime/paddlex")
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        from paddleocr import TextRecognition
        from paddlex.inference.pipelines.components.common.crop_image_regions import CropByPolys
        self.model = TextRecognition(model_name=MODEL_NAME, model_dir=str(self.path),
                                     device="cpu", cpu_threads=self.threads, enable_mkldnn=False,
                                     engine="paddle_static")
        self.cropper = CropByPolys(det_box_type="quad")

    def recognize_lines(self, image, lines):
        if not lines or blank_crop(image):
            return [], "no-lines"
        self.load()
        import numpy as np
        ordered, orientation = ordered_lines(lines)
        bgr = np.asarray(image.convert("RGB"))[:, :, ::-1]
        crops = self.cropper(bgr, [line["polygon"] for line in ordered])
        rows = []
        # Batch=1 isolates source aspect ratios and bounds memory. Native
        # cropper applies perspective warp/np.rot90 for h/w >=1.5, as upstream.
        for line, crop in zip(ordered, crops):
            start = time.perf_counter()
            outputs = list(self.model.predict(crop, batch_size=1))
            if len(outputs) != 1:
                raise ValueError("Line recognizer changed result count")
            payload = outputs[0].json
            if callable(payload):
                payload = payload()
            if isinstance(payload, str):
                payload = json.loads(payload)
            value, score = checked_prediction(payload)
            rows.append({"text": value, "score": score, "polygon": line["polygon"],
                         "rectified_size": [int(crop.shape[1]), int(crop.shape[0])],
                         "ms": (time.perf_counter()-start)*1000})
        return rows, orientation


def authored_cases():
    from fixture_server import synthetic_layout, synthetic_detected_layout
    from PIL import Image, ImageDraw, ImageFont
    image, glyphs = synthetic_layout()
    _, unions, _ = synthetic_detected_layout()
    references = ["姉ちゃん、まだ帰らないの？", "先に帰ってて。あとで行くから。",
                  "氷結結界を展開する！", "明日は来なくてもいい。"]
    for idx, (union, reference) in enumerate(zip(unions, references)):
        x, y, w, h = map(int, rect(union["polygon"]))
        crop = image.crop((x, y, x+w, y+h))
        lines = [{"polygon": [[px-x, py-y] for px, py in line["polygon"]], "score": line["score"]}
                 for line in glyphs[idx*2:idx*2+2]]
        yield f"authored-{idx}", crop, reference, lines
    # True source quotes and vertical Japanese must be measured too; fixing
    # unquoted synthetic bubbles alone does not justify stripping punctuation.
    font = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 29)
    quote = "「待って！」"
    width = math.ceil(font.getlength(quote))+20
    crop = Image.new("RGB", (width, 60), "white")
    draw = ImageDraw.Draw(crop); draw.text((10, 8), quote, font=font, fill="black")
    box = draw.textbbox((10, 8), quote, font=font)
    x, y, right, bottom = box
    yield "authored-real-quotes", crop, quote, [{"polygon": [[x,y],[right,y],[right,bottom],[x,bottom]], "score": 1.}]
    columns = ["姉ちゃん", "待って"]
    crop = Image.new("RGB", (100, 190), "white"); draw = ImageDraw.Draw(crop); lines = []
    for idx, column in enumerate(columns):
        x = 60-idx*40
        bounds = []
        for pos, char in enumerate(column):
            location = (x, 8+pos*32); draw.text(location, char, font=font, fill="black")
            bounds.append(draw.textbbox(location, char, font=font))
        left, top = min(b[0] for b in bounds), min(b[1] for b in bounds)
        right, bottom = max(b[2] for b in bounds), max(b[3] for b in bounds)
        lines.append({"polygon": [[left,top],[right,top],[right,bottom],[left,bottom]], "score": 1.})
    yield "authored-vertical", crop, "".join(columns), lines


def score_rows(rows):
    chars = sum(row["characters"] for row in rows)
    durations = sorted(row["detector_ms"]+row["recognition_ms"] for row in rows)
    return {"crops": len(rows), "characters": chars,
            "cer": sum(row["edits"] for row in rows)/max(1, chars),
            "exact_count": sum(row["edits"] == 0 for row in rows),
            "crops_without_lines": sum(not row["lines"] for row in rows),
            "p50_crop_detector_recognition_ms": statistics.median(durations) if durations else None,
            "p95_crop_detector_recognition_ms": durations[min(len(durations)-1, int(len(durations)*.95))] if durations else None}


def process_memory():
    try:
        import psutil
        info = psutil.Process().memory_info()
        return {"rss_bytes": info.rss, "peak_working_set_bytes": getattr(info, "peak_wset", None),
                "scope": "this comparator process including imports, detector, recognizer and RAM crops"}
    except ImportError:
        return {"unavailable": "psutil is not installed; no memory claim"}


def distribute_lines(regions, lines):
    """Bind each source detector polygon once, without consulting labels.

    This is diagnostic association with the unchanged production grouping,
    not an erasure mask or a new default layout algorithm.
    """
    from benchmark_pages import intersection
    groups = {region["id"]: [] for region in regions}; unmatched = []
    for line in lines:
        box = rect(line["polygon"]); area = max(1,box[2]*box[3])
        candidates = [(intersection(box, r["bbox"])/area, -r["bbox"][2]*r["bbox"][3], -i)
                      for i,r in enumerate(regions)]
        best = max(candidates,default=(0,0,0))
        if best[0] >= .5:
            groups[regions[-best[2]]["id"]].append(line)
        else:
            unmatched.append(line)
    return groups, unmatched


def run_pages(args):
    from benchmark_pages import assign_to_labels
    with dataset_source(args) as source:
        counts, issues, pages = audit(source); fingerprint = dataset_fingerprint(source)
    engine = PaddleLineRecognizer(args.model,args.threads)
    start = time.perf_counter(); engine.load(); load_ms=(time.perf_counter()-start)*1000
    detector = PaddleDetector(ROOT / "models/detector",args.threads); page_rows=[]
    for page,image,bubbles in pages:
        start=time.perf_counter(); lines=detector.detect_raw(image)
        regions=group_regions(image,lines)[:64]
        groups,unassigned=distribute_lines(regions,lines)
        detection_grouping_ms=(time.perf_counter()-start)*1000
        recognized=[];line_rows=[];start=time.perf_counter()
        for region in regions:
            results,orientation=engine.recognize_lines(image,groups[region["id"]])
            value="".join(line["text"] for line in results)
            line_rows.append({"id":region["id"],"orientation":orientation,"lines":results})
            if value:
                recognized.append({**region,"ja":value})
        recognition_ms=(time.perf_counter()-start)*1000
        aligned,unmatched=assign_to_labels(bubbles,recognized)
        row={"page":page["page_id"],"detected_regions":len(regions),"recognized_regions":len(recognized),
             "raw_lines":len(lines),"raw_lines_without_group":len(unassigned),
             "detection_grouping_ms":detection_grouping_ms,"recognition_ms":recognition_ms,
             "aligned":aligned,"unmatched_prediction_ids":unmatched,"line_results":line_rows}
        page_rows.append(row)
        print(json.dumps({k:row[k] for k in ("page","raw_lines","detected_regions","recognized_regions",
            "raw_lines_without_group","detection_grouping_ms","recognition_ms")}),flush=True)
    aligned=[r for p in page_rows for r in p["aligned"]]
    aggregate={"annotation_count":len(aligned),
        "annotations_with_assigned_prediction":sum(bool(r["region_ids"]) for r in aligned),
        "diagnostic_aligned_cer":sum(r["edits"] for r in aligned)/max(1,sum(r["characters"] for r in aligned)),
        "diagnostic_aligned_exact_count":sum(r["edits"]==0 for r in aligned),
        "total_regions":sum(p["recognized_regions"] for p in page_rows),
        "raw_lines_without_group":sum(p["raw_lines_without_group"] for p in page_rows)}
    report={"schema":1,"kind":"full-page-line-recognition","input_fingerprint_sha256":fingerprint,
        "counts":counts,"audit":issues,"model":MODEL_NAME,"repo":MODEL_REPO,"revision":MODEL_REVISION,
        "files":MODEL_FILES,"load_ms":load_ms,"device":"CPU","threads":args.threads,"cloud":False,
        "layout_version":LAYOUT_VERSION,"aggregate":aggregate,"process_memory":process_memory(),"pages":page_rows,
        "limitations":["Source labels not independently verified; diagnostic containment alignment is not detection recall.",
            "Same production detector/grouping and 64-region cap, with per-line CTC recognition and geometric line order.",
            "No translation, context, cleanup, browser transport or clean-background grading.",
            "Missing/empty/ungrouped lines remain counted as errors; no reference-conditioned selection.",
            "One pass per page, not latency p95 evidence. Production defaults and install remain unchanged."]}
    destination=Path(args.output);destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(aggregate),flush=True)


def run(args):
    if args.authored:
        cases = [("authored", id, crop, ref, lines) for id, crop, ref, lines in authored_cases()]
        counts, issues, fingerprint = {"eligible_bubbles": len(cases)}, [], None
    else:
        with dataset_source(args) as source:
            counts, issues, pages = audit(source); fingerprint = dataset_fingerprint(source)
        cases = []
        for page, image, bubbles in pages:
            for bubble in bubbles:
                x, y, w, h = (bubble["bbox"][k] for k in ("x", "y", "w", "h"))
                cases.append((page["page_id"], bubble["bubble_id"], image.crop((x,y,x+w,y+h)), bubble["ja_ocr_truth"], None))
    engine = PaddleLineRecognizer(args.model, args.threads)
    start = time.perf_counter(); engine.load(); load_ms = (time.perf_counter()-start)*1000
    detector = PaddleDetector(ROOT / "models/detector", args.threads)
    rows, rounds = [], []
    for repetition in range(args.repeats):
        round_rows = []
        for page, id, crop, reference, known_lines in cases:
            # Gold line geometry is used only in the explicitly authored oracle
            # arm. Private results always include detector misses and wrong splits.
            start = time.perf_counter()
            lines = known_lines if args.line_source == "authored-glyphs" else detector.detect_raw(crop)
            if lines is None:
                raise ValueError("Authored glyph lines cannot be used with private data")
            detector_ms = (time.perf_counter()-start)*1000
            start = time.perf_counter(); results, orientation = engine.recognize_lines(crop, lines)
            recognition_ms = (time.perf_counter()-start)*1000
            ref, pred = normalized(reference), normalized("".join(line["text"] for line in results))
            row = {"page": page, "id": id, "repetition": repetition+1,
                   "reference": ref, "prediction": pred, "edits": distance(ref,pred),
                   "characters": len(ref), "crop_size": crop.size, "lines": results,
                   "orientation": orientation, "detector_ms": detector_ms, "recognition_ms": recognition_ms}
            rows.append(row); round_rows.append(row)
            print(json.dumps({"page": page, "id": id, "repetition": repetition+1,
                              "lines": len(results), "exact": row["edits"] == 0,
                              "ms": detector_ms+recognition_ms}, ensure_ascii=True), flush=True)
        rounds.append({"repetition": repetition+1, **score_rows(round_rows)})
    predictions = {}
    for row in rows:
        predictions.setdefault((row["page"], row["id"]), set()).add(row["prediction"])
    report = {"schema": 1, "input_fingerprint_sha256": fingerprint, "counts": counts, "audit": issues,
              "model": MODEL_NAME, "repo": MODEL_REPO, "revision": MODEL_REVISION, "files": MODEL_FILES,
              "load_ms": load_ms, "device": "CPU", "threads": args.threads, "cloud": False,
              "line_source": args.line_source, "aggregate": rounds[0], "rounds": rounds,
              "predictions_changed_between_repeats": sum(len(values)>1 for values in predictions.values()),
              "process_memory": process_memory(),
              "runtime": {"python": sys.version.split()[0], "platform": platform.platform(),
                          "processor": os.environ.get("PROCESSOR_IDENTIFIER", "unknown"),
                          "paddleocr": metadata.version("paddleocr"), "paddle": metadata.version("paddlepaddle"),
                          "paddlex": metadata.version("paddlex")}, "raw_results": rows,
              "limitations": ["Private transcription labels have not been independently verified.",
                  "Uses gold bubble crops, not a full-page pipeline or manga recognition accuracy proof.",
                  "Detector runs within each gold crop; does not measure full-page detection recall.",
                  "Geometric reading order can fail for furigana, mixed orientations or curved text.",
                  "CTC scores are not calibrated confidence; no punctuation is stripped or score-filtered.",
                  "Crop detector+recognition percentiles exclude recognizer loading; first detection is cold.",
                  "Not a replacement for manga-ocr yet; production defaults and install remain unchanged."]}
    destination = Path(args.output); destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(report["aggregate"], ensure_ascii=True), flush=True)


def main():
    parser = argparse.ArgumentParser()
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--folder"); inputs.add_argument("--zip"); inputs.add_argument("--authored", action="store_true")
    parser.add_argument("--model", default=str(MODEL_PATH)); parser.add_argument("--fetch-model", action="store_true")
    parser.add_argument("--threads", type=int, choices=range(1,9), default=4)
    parser.add_argument("--repeats", type=int, choices=range(1,5), default=1,
                        help="One first pass plus up to three warm repeat passes, without a result cache")
    parser.add_argument("--full-pages",action="store_true",
                        help="Detect once on each private page; group as production and reconstruct source lines")
    parser.add_argument("--line-source", choices=("detector","authored-glyphs"), default="detector")
    parser.add_argument("--output", default=str(ROOT / "artifacts/private-paddle-rec.json"))
    args = parser.parse_args()
    if args.line_source == "authored-glyphs" and not args.authored:
        parser.error("Gold line geometry is only available for authored fixtures")
    if args.full_pages and (not (args.folder or args.zip) or args.repeats!=1):
        parser.error("Full-page diagnostic requires private input and a single page pass")
    if args.fetch_model:
        fetch_model(args.model)
    if args.authored or args.folder or args.zip:
        (run_pages if args.full_pages else run)(args)
    elif not args.fetch_model:
        parser.error("Supply authored/private input or explicit --fetch-model")


if __name__ == "__main__":
    main()
