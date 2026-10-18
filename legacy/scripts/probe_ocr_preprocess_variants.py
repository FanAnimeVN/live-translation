"""RAM-only OCR preprocessing probe for the private development set.

This is deliberately a comparator, not a runtime fallback.  It keeps the
pinned manga-ocr weights and geometry fixed while testing inexpensive image
normalisation variants.  Gold text is consulted only after inference.  The
report is private diagnostic evidence and must not be used to choose a reader
result or to train a production route.
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]

from PIL import Image, ImageFilter, ImageOps

from benchmark import DirectoryDataset, audit, dataset_fingerprint, distance, normalized
from manga_live.ocr import MangaEngine


def variants(image):
    """Return cheap in-RAM image variants with unchanged dimensions."""
    grey = image.convert("L")
    yield "base", image
    yield "autocontrast", ImageOps.autocontrast(grey).convert("RGB")
    yield "unsharp", grey.filter(ImageFilter.UnsharpMask(radius=1, percent=120, threshold=3)).convert("RGB")
    # A binary probe is useful for diagnosing threshold-sensitive scans but is
    # intentionally never a silent production transform: it can erase halftone
    # texture and expressive punctuation.
    yield "threshold180", grey.point(lambda value: 255 if value >= 180 else 0).convert("RGB")


def run(args):
    destination = Path(args.output).resolve()
    if ROOT / "artifacts" not in destination.parents or destination.exists():
        raise ValueError("Output must be a new private artifact below artifacts/")
    with DirectoryDataset(args.folder) as source:
        counts, issues, pages = audit(source)
        fingerprint = dataset_fingerprint(source)
        cases = []
        for page, image, bubbles in pages:
            for bubble in bubbles:
                x, y, w, h = (bubble["bbox"][key] for key in ("x", "y", "w", "h"))
                cases.append((page["page_id"] + ":" + bubble["bubble_id"],
                              image.crop((x, y, x + w, y + h)), bubble["ja_ocr_truth"]))

    engine = MangaEngine(ROOT / "models/ocr", args.threads)
    engine.load()
    cancel = threading.Event()
    rows = []
    started = time.perf_counter()
    for index, (identifier, crop, reference) in enumerate(cases, 1):
        row = {"id": identifier, "reference": reference, "characters": len(normalized(reference)), "variants": {}}
        for name, image in variants(crop):
            begin = time.perf_counter()
            prediction = engine.recognize(image)
            row["variants"][name] = {
                "prediction": prediction,
                "edits": distance(normalized(reference), normalized(prediction)),
                "exact": normalized(reference) == normalized(prediction),
                "ms": (time.perf_counter() - begin) * 1000,
            }
        rows.append(row)
        print(json.dumps({"completed": index, "total": len(cases), "id": identifier}), flush=True)

    names = [name for name, _ in variants(cases[0][1])]
    summaries = []
    for name in names:
        selected = [row["variants"][name] for row in rows]
        summaries.append({"variant": name, "exact": sum(item["exact"] for item in selected),
                          "edits": sum(item["edits"] for item in selected),
                          "characters": sum(row["characters"] for row in rows),
                          "cer": sum(item["edits"] for item in selected) /
                          max(1, sum(row["characters"] for row in rows)),
                          "p50_ms": sorted(item["ms"] for item in selected)[len(selected) // 2]})

    oracle = []
    for row in rows:
        best = min(item["edits"] for item in row["variants"].values())
        oracle.append(best)
    result = {
        "schema": 1,
        "engine": engine.name,
        "input_fingerprint_sha256": fingerprint,
        "counts": counts,
        "audit": issues,
        "production_defaults_changed": False,
        "variants": ["base", "autocontrast", "unsharp", "threshold180"],
        "rows": rows,
        "summaries": summaries,
        "oracle_lower_bound": {"exact": sum(edit == 0 for edit in oracle),
                               "edits": sum(oracle),
                               "cer": sum(oracle) / max(1, sum(row["characters"] for row in rows))},
        "elapsed_ms": (time.perf_counter() - started) * 1000,
        "limitations": [
            "Japanese labels are not independently reviewed and are not clean-background or translation gold.",
            "The oracle uses labels after inference and is not an admissible runtime selector.",
            "No variant is promoted without a source-independent confidence signal and held-out evidence.",
        ],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"summaries": summaries, "oracle_lower_bound": result["oracle_lower_bound"],
                      "output": str(destination)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument("--output", default=str(ROOT / "artifacts/private-ocr-preprocess-variants-20261016.json"))
    run(parser.parse_args())
