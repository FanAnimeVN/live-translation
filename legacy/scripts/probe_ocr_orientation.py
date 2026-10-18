"""Bounded orientation probe for the pinned manga recognizer.

This is intentionally a diagnostic, not a runtime default.  It compares the
existing crop with a 90-degree clockwise view for tall source boxes.  The
decision is made from geometry only; labels are used after inference for
measurement and never to choose a reader result.  Source images stay in RAM
and the report is restricted to the private artifacts directory.
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


def oriented(crop):
    """Return a geometry-only candidate; keep ordinary/horizontal crops intact."""
    if crop.height < crop.width * 1.5:
        return crop, False
    # A vertical Japanese line becomes a horizontal reading strip.  This is a
    # candidate only; the production recognizer must not silently change until
    # a reviewed, held-out paired benchmark proves it preserves coverage.
    from PIL import Image
    return crop.transpose(Image.Transpose.ROTATE_90), True


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
        start = time.perf_counter()
        base = engine.recognize(crop)
        base_ms = (time.perf_counter() - start) * 1000
        candidate, rotated = oriented(crop)
        start = time.perf_counter()
        rotated_prediction = engine.recognize(candidate) if rotated else base
        rotated_ms = (time.perf_counter() - start) * 1000 if rotated else 0.0
        ref = normalized(reference)
        rows.append({
            "id": identifier,
            "size": list(crop.size),
            "rotated": rotated,
            "reference": reference,
            "base": base,
            "rotated_prediction": rotated_prediction,
            "base_exact": normalized(base) == ref,
            "rotated_exact": normalized(rotated_prediction) == ref,
            "base_edits": distance(ref, normalized(base)),
            "rotated_edits": distance(ref, normalized(rotated_prediction)),
            "base_ms": base_ms,
            "rotated_ms": rotated_ms,
        })
        print(json.dumps({"completed": index + 1, "total": len(cases), "id": identifier}), flush=True)
    rotated_rows = [row for row in rows if row["rotated"]]
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
            "vertical_candidates": len(rotated_rows),
            "base_exact": sum(row["base_exact"] for row in rows),
            "rotated_exact_on_vertical": sum(row["rotated_exact"] for row in rotated_rows),
            "base_edits_on_vertical": sum(row["base_edits"] for row in rotated_rows),
            "rotated_edits_on_vertical": sum(row["rotated_edits"] for row in rotated_rows),
            "base_edits": sum(row["base_edits"] for row in rows),
            "rotated_edits": sum(row["rotated_edits"] for row in rows),
            "vertical_changed": sum(row["base"] != row["rotated_prediction"] for row in rotated_rows),
        },
        "limitations": [
            "Japanese labels are not independently reviewed; no Vietnamese or clean-background gold.",
            "Orientation is geometry-only and remains a review candidate; no production selector was changed.",
        ],
    }
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"aggregate": report["aggregate"], "output": str(destination)}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--threads", type=int, choices=range(1, 9), default=4)
    parser.add_argument("--output", default=str(ROOT / "artifacts/private-ocr-orientation-20261016.json"))
    run(parser.parse_args())
