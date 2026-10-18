"""One-field preprocessing experiment; never imported by the companion.

Only processor.resample changes. Pinned weights, geometry, gray conversion,
generation, and punctuation postprocessing remain identical. Images stay in
RAM; private text diagnostics may only go to gitignored artifacts/.
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from PIL import Image, ImageDraw, ImageFont
from benchmark import DirectoryDataset, audit, dataset_fingerprint, distance, normalized
from benchmark_paddle_rec import authored_cases
from fixture_server import synthetic_detected_layout
from manga_live.ocr import MangaEngine, group_regions


RESAMPLING = {"bilinear": Image.Resampling.BILINEAR, "bicubic": Image.Resampling.BICUBIC,
              "lanczos": Image.Resampling.LANCZOS}


@contextmanager
def resampling(recognizer, value):
    original = recognizer.processor.resample
    try:
        recognizer.processor.resample = value
        yield
    finally:
        recognizer.processor.resample = original


def controls():
    image, detections, _ = synthetic_detected_layout()
    regions = group_regions(image, detections)
    references = ["姉ちゃん、まだ帰らないの？", "先に帰ってて。あとで行くから。",
                  "氷結結界を展開する！", "明日は来なくてもいい。"]
    for region, reference in zip(regions, references):
        x, y, w, h = region["bbox"]
        yield region["id"], image.crop((x, y, x+w, y+h)), reference
    for name, crop, reference, _ in authored_cases():
        if name in ("authored-real-quotes", "authored-vertical"):
            yield name, crop, reference
    font = ImageFont.truetype("C:/Windows/Fonts/YuGothM.ttc", 29)
    for name, reference in (("opening-quote", "「まだ帰らないの？"),
                            ("closing-quote", "あとで行くから。」"),
                            ("expressive", "わ…た…し…？")):
        width = round(font.getlength(reference))+24
        crop = Image.new("RGB", (width, 62), "white")
        ImageDraw.Draw(crop).text((12, 8), reference, font=font, fill="black")
        yield name, crop, reference
    for name, lines in (("multiline-real-quotes", ["「明日は", "来なくてもいい。」"]),
                        ("multiline-opening-quote", ["「姉ちゃん、", "まだ帰らないの？"]),
                        ("multiline-closing-quote", ["あとで行くから。", "待っていて。」"])):
        width = round(max(font.getlength(line) for line in lines))+24
        crop = Image.new("RGB", (width, 92), "white")
        draw = ImageDraw.Draw(crop)
        for index, line in enumerate(lines):
            draw.text((12, 8+45*index), line, font=font, fill="black")
        yield name, crop, "".join(lines)
    yield "blank", Image.new("RGB", (236, 89), "white"), ""


def decoder_evidence(recognizer, crop):
    pixels = recognizer.processor([crop.convert("L").convert("RGB")],
                                  return_tensors="pt").pixel_values
    with recognizer._torch.inference_mode():
        encoded = recognizer.model.generate(pixels.to(recognizer.model.device), max_length=300,
                                            return_dict_in_generate=True, output_scores=True)
    raw = recognizer.tokenizer.batch_decode(encoded.sequences.cpu(), skip_special_tokens=True)[0]
    special = set(recognizer.tokenizer.all_special_ids)
    visible_step = next((step for step, token in enumerate(encoded.sequences[0][1:])
                         if int(token) not in special), None)
    # The first generated token is forced CLS for these weights. Instrument
    # the first visible character instead of mistaking that forced step for
    # evidence about quotation probability. All beams still share this prefix.
    if visible_step is None:
        raise ValueError("Diagnostic crop generated no visible token")
    values, ids = encoded.scores[visible_step][0].topk(6)
    return {"raw": raw, "postprocessed": recognizer._post_process(raw),
            "first_visible_step": visible_step,
            "first_visible_top": [{"token": recognizer.tokenizer.decode([int(token)]),
                                "score": float(score)} for token, score in zip(ids, values)]}


def run(args):
    destination = Path(args.output).resolve()
    if ROOT / "artifacts" not in destination.parents:
        raise ValueError("Diagnostics must stay in this project's gitignored artifacts directory")
    engine = MangaEngine(ROOT / "models/ocr", 4)
    start = time.perf_counter(); engine.load(); load_ms = (time.perf_counter()-start)*1000
    processor = engine.model.processor
    report = {"engine": engine.name, "load_ms": load_ms, "production_defaults_changed": False,
              "field": "processor.resample", "default": int(processor.resample),
              "generation_config": {key: getattr(engine.model.model.generation_config, key)
                                    for key in ("num_beams", "length_penalty", "do_sample", "no_repeat_ngram_size")},
              "source": "author-created controls", "rows": []}
    if args.folder:
        with DirectoryDataset(args.folder) as archive:
            counts, issues, pages = audit(archive)
            report.update(source="private audited gold crops", counts=counts, audit=issues,
                          input_fingerprint_sha256=dataset_fingerprint(archive))
        cases = []
        for page, image, bubbles in pages:
            for bubble in bubbles:
                x, y, w, h = (bubble["bbox"][k] for k in ("x", "y", "w", "h"))
                cases.append((page["page_id"]+":"+bubble["bubble_id"],
                              image.crop((x, y, x+w, y+h)), bubble["ja_ocr_truth"]))
    else:
        cases = list(controls())
        report["decoder_evidence"] = decoder_evidence(engine.model, cases[0][1])
    for index, (name, crop, reference) in enumerate(cases):
        for variant in args.variants:
            with resampling(engine.model, RESAMPLING[variant]):
                start = time.perf_counter(); prediction = engine.recognize(crop)
                elapsed = (time.perf_counter()-start)*1000
            ref, hyp = normalized(reference), normalized(prediction)
            report["rows"].append({"id": name, "variant": variant, "size": crop.size,
                                   "reference": reference, "prediction": prediction,
                                   "exact": ref == hyp, "edits": distance(ref, hyp),
                                   "characters": len(ref), "ms": elapsed})
        print(json.dumps({"completed": index+1, "total": len(cases), "id": name}), flush=True)
    report["summaries"] = []
    for variant in args.variants:
        rows = [row for row in report["rows"] if row["variant"] == variant]
        report["summaries"].append({"variant": variant, "crops": len(rows),
            "exact": sum(row["exact"] for row in rows), "edits": sum(row["edits"] for row in rows),
            "cer": sum(row["edits"] for row in rows)/max(1, sum(row["characters"] for row in rows))})
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summaries": report["summaries"], "output": str(destination)}), flush=True)
    if args.assert_variant:
        chosen = [row for row in report["rows"] if row["variant"] == args.assert_variant]
        if not chosen or not all(row["exact"] for row in chosen):
            raise SystemExit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", help="Read private source crops locally, never call cloud")
    parser.add_argument("--variants", nargs="+", choices=tuple(RESAMPLING), default=list(RESAMPLING))
    parser.add_argument("--assert-variant", choices=tuple(RESAMPLING))
    parser.add_argument("--output", default=str(ROOT / "artifacts/ocr-resampling-authored-20261014.json"))
    run(parser.parse_args())
