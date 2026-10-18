"""Rejected/unaccepted geometry-only OCR retry experiment, not runtime code.

Compare tight horizontal line crops with the unchanged full source crop. No
punctuation is rewritten; vertically written or unseparated source is retained.
All image bytes remain in RAM. Gold text only grades the result after inference.
"""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from benchmark import DirectoryDataset, audit, dataset_fingerprint, normalized, distance
from manga_live.ocr import MangaEngine, review_reasons
from probe_ocr_resampling import controls


def horizontal_line_boxes(image):
    import numpy as np
    if image.width < 1.8*image.height:
        return []
    grey = np.asarray(image.convert("L"))
    if float(np.median(grey)) < 220:
        return []
    ink = grey < 180
    ys = np.flatnonzero(ink.sum(axis=1) >= 3)
    if not len(ys):
        return []
    bands = np.split(ys, np.flatnonzero(np.diff(ys) >= 5)+1)
    if not 2 <= len(bands) <= 4 or any(len(band) < 8 for band in bands):
        return []
    heights = [int(band[-1]-band[0]+1) for band in bands]
    if max(heights) > 1.5*min(heights):
        return []
    boxes = []
    for band in bands:
        top, bottom = max(0, int(band[0])-3), min(image.height, int(band[-1])+4)
        xs = np.flatnonzero(ink[int(band[0]):int(band[-1])+1].any(axis=0))
        if not len(xs) or int(xs[-1]-xs[0]+1) < 12:
            return []
        boxes.append((max(0, int(xs[0])-3), top, min(image.width, int(xs[-1])+4), bottom))
    return boxes


def run(args):
    destination = Path(args.output).resolve()
    if ROOT / "artifacts" not in destination.parents:
        raise ValueError("Diagnostics must stay in gitignored artifacts/")
    engine = MangaEngine(ROOT / "models/ocr", 4)
    engine.load()
    rows = []
    report = {"source": "authored source geometry and labels only", "engine": engine.name,
              "production_defaults_changed": False, "cloud": False}
    if args.folder:
        with DirectoryDataset(args.folder) as archive:
            counts, issues, pages = audit(archive)
            report.update(source="private audited gold crops", counts=counts, audit=issues,
                          input_fingerprint_sha256=dataset_fingerprint(archive))
        cases = []
        for page, image, bubbles in pages:
            for bubble in bubbles:
                x, y, w, h = (bubble["bbox"][key] for key in ("x", "y", "w", "h"))
                cases.append((page["page_id"]+":"+bubble["bubble_id"], image.crop((x, y, x+w, y+h)),
                              bubble["ja_ocr_truth"]))
    else:
        cases = list(controls())
    for name, crop, reference in cases:
        start = time.perf_counter(); baseline = engine.recognize(crop)
        baseline_ms = (time.perf_counter()-start)*1000
        boxes = horizontal_line_boxes(crop)
        start = time.perf_counter()
        pieces = [engine.recognize(crop.crop(box)) for box in boxes]
        candidate = "".join(pieces) if boxes else baseline
        review_candidate = candidate if "quote_balance" in review_reasons(baseline) else baseline
        candidate_ms = (time.perf_counter()-start)*1000
        row = {"id": name, "reference": reference, "baseline": baseline, "candidate": candidate,
               "boxes": boxes, "pieces": pieces, "baseline_ms": baseline_ms,
               "candidate_additional_ms": candidate_ms, "baseline_edits": distance(normalized(reference), normalized(baseline)),
               "candidate_edits": distance(normalized(reference), normalized(candidate)),
               "review_candidate": review_candidate,
               "review_candidate_edits": distance(normalized(reference), normalized(review_candidate)),
               "characters": len(normalized(reference))}
        rows.append(row)
        print(json.dumps({"id": name, "baseline_edits": row["baseline_edits"],
                          "candidate_edits": row["candidate_edits"], "pieces": len(pieces)}), flush=True)
    report.update(rows=rows,
              summary={"crops": len(rows), "baseline_exact": sum(row["baseline_edits"] == 0 for row in rows),
                          "candidate_exact": sum(row["candidate_edits"] == 0 for row in rows),
                          "review_candidate_exact": sum(row["review_candidate_edits"] == 0 for row in rows),
                          "baseline_edits": sum(row["baseline_edits"] for row in rows),
                          "candidate_edits": sum(row["candidate_edits"] for row in rows),
                          "review_candidate_edits": sum(row["review_candidate_edits"] for row in rows),
                          "characters": sum(row["characters"] for row in rows)})
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"]), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", help="Local private source crops; no image/text uploads")
    parser.add_argument("--output", default=str(ROOT / "artifacts/ocr-line-crops-authored-20261014.json"))
    run(parser.parse_args())
