"""Prepare a provenance-bound, text-only grouped OCR pilot input.

This does not call a model and does not upload or persist image bytes. It keeps
the original source records in a separate in-memory plane, then emits only the
two presentation utterances selected for an explicitly authorized cloud test.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
sys.path.insert(0, str(ROOT / "scripts"))
from benchmark import DirectoryDataset, audit, dataset_fingerprint
from manga_live.utterance_assembly import ASSEMBLY_VERSION, assemble_utterances


def run(args):
    output = Path(args.output).resolve()
    if output.parent != ROOT / "artifacts" or output.exists():
        raise ValueError("Output must be a new private artifact")
    production = json.loads(Path(args.production).read_text(encoding="utf-8"))
    blocks = json.loads(Path(args.blocks).read_text(encoding="utf-8"))
    with DirectoryDataset(args.folder) as dataset:
        _, _, pages = audit(dataset)
        fingerprint = dataset_fingerprint(dataset)
    if production.get("input_fingerprint_sha256") != fingerprint or blocks.get("input_fingerprint_sha256") != fingerprint:
        raise ValueError("Evidence and selected private dataset differ")
    page = next((row for row in production.get("pages", []) if row.get("page") == args.page), None)
    block_page = next((row for row in blocks.get("pages", []) if row.get("page") == args.page), None)
    source_image = next((image for row, image, _ in pages if row.get("page_id") == args.page), None)
    if page is None or block_page is None or source_image is None:
        raise ValueError("Selected page is missing or ineligible")
    plan = assemble_utterances(page["regions"], block_page["regions"][:2], source_image.size)
    selected = [row for row in plan["utterances"] if "assembly" in row][:2]
    if len(selected) != 2:
        raise ValueError("Expected exactly two geometry-supported grouped utterances")
    # The nested source plane remains only in this process. The emitted report
    # carries source IDs/keys as provenance, not source images or gold labels.
    regions = []
    for row in selected:
        item = {key: value for key, value in row.items() if key not in ("vi", "assembly")}
        item["sourceAssembly"] = row["assembly"]
        regions.append(item)
    report = {"schema": 2, "cloud": False, "textOnly": True,
              "input_fingerprint_sha256": fingerprint, "sourceEvidence": "production-partition+member-preserving-geometry",
              "assemblyVersion": ASSEMBLY_VERSION, "pages": [{"page": args.page, "regions": regions}],
              "limitations": ["OCR text only; no image, ground truth or translation reference.",
                              "Grouped geometry is a reviewable candidate and is not production-default evidence."]}
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(output), "page": args.page, "regions": len(regions),
                      "source_fingerprint_sha256": fingerprint, "assembly_ids": [row["id"] for row in selected]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True); parser.add_argument("--page", required=True)
    parser.add_argument("--production", required=True); parser.add_argument("--blocks", required=True)
    parser.add_argument("--output", required=True)
    run(parser.parse_args())
