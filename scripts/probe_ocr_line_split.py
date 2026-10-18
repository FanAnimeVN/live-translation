"""Geometry-only line/column split probe for manga OCR.

Many manga pipelines recognize detector lines separately and concatenate them
in reading order.  This probe reproduces only that bounded idea on the frozen
source boxes: projection runs are derived from pixels, each run is OCRed, and
the result is kept as a diagnostic alternative.  It never changes production,
does not use labels to route output, and keeps crops in RAM.
"""

import argparse
import json
import time
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from benchmark import DirectoryDataset, audit, dataset_fingerprint, distance, normalized
from manga_live.ocr import MangaEngine


def _runs(values, threshold, max_gap):
    active = [index for index, value in enumerate(values) if value >= threshold]
    if not active:
        return []
    runs = []
    start = previous = active[0]
    for index in active[1:]:
        if index - previous > max_gap:
            runs.append((start, previous + 1))
            start = index
        previous = index
    runs.append((start, previous + 1))
    return runs


def split_crop(crop):
    """Return source-order line crops or None when geometry is ambiguous."""
    import numpy as np

    grey = np.asarray(crop.convert("L"))
    ink = grey < 170
    if not ink.any():
        return None
    vertical = crop.height >= crop.width * 1.25
    axis_values = ink.sum(axis=0 if vertical else 1)
    # Ignore tiny isolated specks and bridge only sub-character raster gaps.
    threshold = max(2, round((crop.height if vertical else crop.width) * .015))
    gap = max(1, round((crop.width if vertical else crop.height) * .025))
    runs = _runs(axis_values, threshold, gap)
    minimum = max(3, round((crop.width if vertical else crop.height) * .18))
    runs = [(start, stop) for start, stop in runs if stop - start >= minimum]
    if len(runs) < 2 or len(runs) > 12:
        return None
    pad = 3
    parts = []
    for start, stop in (sorted(runs, reverse=vertical)):
        start = max(0, start - pad)
        stop = min(crop.width if vertical else crop.height, stop + pad)
        if vertical:
            parts.append(crop.crop((start, 0, stop, crop.height)))
        else:
            parts.append(crop.crop((0, start, crop.width, stop)))
    return parts


def run(args):
    destination = Path(args.output).resolve()
    if ROOT / "artifacts" not in destination.parents:
        raise ValueError("Diagnostics must stay in this project's gitignored artifacts directory")
    cases = []
    with DirectoryDataset(args.folder) as archive:
        counts, issues, pages = audit(archive)
        fingerprint = dataset_fingerprint(archive)
        for page, image, bubbles in pages:
            for bubble in bubbles:
                x, y, w, h = (bubble["bbox"][key] for key in ("x", "y", "w", "h"))
                cases.append((page["page_id"] + ":" + bubble["bubble_id"],
                              image.crop((x, y, x + w, y + h)), bubble["ja_ocr_truth"]))
    engine = MangaEngine(ROOT / "models/ocr", args.threads)
    started = time.perf_counter()
    engine.load()
    load_ms = (time.perf_counter() - started) * 1000
    rows = []
    for index, (identifier, crop, reference) in enumerate(cases):
        parts = split_crop(crop)
        start = time.perf_counter()
        base = engine.recognize(crop)
        base_ms = (time.perf_counter() - start) * 1000
        if parts:
            start = time.perf_counter()
            predictions = engine.recognize_many(parts)
            split_ms = (time.perf_counter() - start) * 1000
            split_prediction = "".join(predictions)
        else:
            predictions, split_prediction, split_ms = [], base, 0.0
        ref = normalized(reference)
        rows.append({
            "id": identifier,
            "size": list(crop.size),
            "part_count": len(parts or []),
            "reference": reference,
            "base": base,
            "split_prediction": split_prediction,
            "parts": predictions,
            "base_exact": normalized(base) == ref,
            "split_exact": normalized(split_prediction) == ref,
            "base_edits": distance(ref, normalized(base)),
            "split_edits": distance(ref, normalized(split_prediction)),
            "base_ms": base_ms,
            "split_ms": split_ms,
        })
        print(json.dumps({"completed": index + 1, "total": len(cases), "id": identifier}), flush=True)
    split_rows = [row for row in rows if row["part_count"]]
    report = {
        "schema": 1,
        "engine": engine.name,
        "threads": args.threads,
        "load_ms": load_ms,
        "production_defaults_changed": False,
        "source": "private audited crop geometry probe",
        "counts": counts,
        "audit": issues,
        "input_fingerprint_sha256": fingerprint,
        "rows": rows,
        "aggregate": {
            "crops": len(rows),
            "split_candidates": len(split_rows),
            "base_exact": sum(row["base_exact"] for row in rows),
            "split_exact_on_candidates": sum(row["split_exact"] for row in split_rows),
            "base_edits_on_candidates": sum(row["base_edits"] for row in split_rows),
            "split_edits_on_candidates": sum(row["split_edits"] for row in split_rows),
            "base_edits": sum(row["base_edits"] for row in rows),
            "split_edits": sum(row["split_edits"] for row in rows),
            "changed": sum(row["base"] != row["split_prediction"] for row in split_rows),
        },
        "limitations": [
            "Japanese labels are not independently reviewed; no Vietnamese or clean-background gold.",
            "Projection runs are geometry-only and remain a review candidate; no production selector was changed.",
        ],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"aggregate": report["aggregate"], "output": str(destination)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--threads", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--output", default=str(ROOT / "artifacts/private-ocr-line-split-20261016.json"))
    run(parser.parse_args())
