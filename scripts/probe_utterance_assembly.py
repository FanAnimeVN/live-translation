"""Replay conservative utterance assembly over recorded private OCR evidence.

No model, network or fresh OCR. Images are read only for dataset audit/size and
stay in RAM. Source rows, raw guide classes/scores and diagnostic label deltas
are preserved in a new gitignored text artifact; never in a release bundle.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from benchmark import DirectoryDataset, audit, dataset_fingerprint
from benchmark_pages import assign_to_labels
from manga_live.ocr import LAYOUT_VERSION
from manga_live.text_scope import story_regions
from manga_live.utterance_assembly import ASSEMBLY_VERSION, assemble_utterances


def read_evidence(value):
    path = Path(value).resolve()
    if path.parent != ROOT / "artifacts" or path.stat().st_size > 16*1024*1024:
        raise ValueError("Bounded evidence in private artifacts required")
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or result.get("cloud") is not False:
        raise ValueError("Recorded local OCR/detector evidence required")
    return result


def checked_planes(plan, original):
    """Verify source completeness independently of aggregate OCR scores."""
    if plan["sources"] != original:
        raise ValueError("Assembly changed the captured source plane")
    flattened = []
    scope_keys = []
    for row in plan["utterances"]:
        assembly = row.get("assembly")
        if assembly is None:
            flattened.append(row)
            continue
        members = assembly["source_regions"]
        if (assembly["source_ids"] != [member["id"] for member in members]
                or assembly["source_keys"] != [member["scope"]["key"] for member in members]
                or row["ja"] != "".join(member["ja"] for member in members)
                or not row.get("review") or assembly.get("erasure_permitted") is not False
                or story_regions([row]) or row.get("speaker") != "unknown"
                or row.get("listener") != "unknown"):
            raise ValueError("Assembly lost members, source text, anchors or trust boundaries")
        scope_keys.append(row["scope"]["key"])
        flattened.extend(members)
    by_id = {row["id"]: row for row in flattened}
    if (len(by_id) != len(flattened) or len(flattened) != len(original)
            or by_id != {row["id"]: row for row in original}
            or len(set(scope_keys)) != len(scope_keys)):
        raise ValueError("Missing/duplicate source or ambiguous assembly scope")


def checked_pages(report, eligible):
    rows = report.get("pages")
    if (not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows)
            or len({row.get("page") for row in rows}) != len(rows)
            or {row.get("page") for row in rows} != eligible):
        raise ValueError("Recorded evidence must cover every eligible page exactly once")
    return {row["page"]: row for row in rows}


def run(args):
    destination = Path(args.output).resolve()
    if destination.parent != ROOT / "artifacts" or destination.exists():
        raise ValueError("A new private text artifact is required")
    source = read_evidence(args.source)
    guides = read_evidence(args.guides)
    with DirectoryDataset(args.folder) as dataset:
        counts, issues, pages = audit(dataset)
        fingerprint = dataset_fingerprint(dataset)
    if (any(value.get("input_fingerprint_sha256") != fingerprint for value in (source, guides))
            or source.get("layout_version") != LAYOUT_VERSION
            or guides.get("detector") != "ogkalu-detector-v4-s-int8-private-blocks"):
        raise ValueError("Source, detector or dataset provenance differs")
    eligible = {row["page_id"] for row, _, _ in pages}
    source_pages, guide_pages = [checked_pages(value, eligible) for value in (source, guides)]
    report = {"schema": 1, "candidate": ASSEMBLY_VERSION,
        "production_default": False, "cloud": False, "fresh_ocr": False,
        "fresh_detector": False, "image_persistence": False,
        "input_fingerprint_sha256": fingerprint, "source_evidence": Path(args.source).name,
        "guide_evidence": Path(args.guides).name, "counts": counts, "audit": issues,
        "pages": [], "guide_model": deepcopy(guides.get("experimental_detector", {})),
        "limitations": ["Recorded local model outputs; replay is not inference or a latency measurement.",
            "Source preservation and label diagnostics do not prove sentence ownership or translation quality.",
            "No independently verified Japanese, Vietnamese or clean-background gold; not a runtime default."]}
    for page, image, bubbles in pages:
        page_id = page["page_id"]
        original = source_pages[page_id]["regions"]
        plan = assemble_utterances(original, guide_pages[page_id]["regions"], image.size)
        checked_planes(plan, original)
        aligned, unmatched = assign_to_labels(bubbles, plan["utterances"])
        baseline, _ = assign_to_labels(bubbles, original)
        deltas = [{"bubble_id": new["bubble_id"], "before_edits": old["edits"], "after_edits": new["edits"]}
                  for old, new in zip(baseline, aligned) if old["edits"] != new["edits"]]
        row = {"page": page_id, "size": list(image.size), "sources": plan["sources"],
            "source_fingerprint": plan["source_fingerprint"], "utterances": plan["utterances"],
            "assemblies": plan["assemblies"], "source_preservation_verified": True,
            "guide_detector_evidence": deepcopy(guide_pages[page_id].get("detector_evidence", {})),
            "aligned": aligned, "label_deltas": deltas, "unmatched_prediction_ids": unmatched}
        report["pages"].append(row)
    aligned = [row for page in report["pages"] for row in page["aligned"]]
    report["aggregate"] = {"eligible_pages": len(pages),
        "sources": sum(len(page["sources"]) for page in report["pages"]),
        "utterances": sum(len(page["utterances"]) for page in report["pages"]),
        "assemblies": sum(len(page["assemblies"]) for page in report["pages"]),
        "annotations": len(aligned), "assigned": sum(bool(row["region_ids"]) for row in aligned),
        "exact": sum(row["reference"] == row["prediction"] for row in aligned),
        "diagnostic_cer": sum(row["edits"] for row in aligned)/sum(row["characters"] for row in aligned),
        "source_preservation_verified": True}
    with destination.open("x", encoding="utf-8") as output:
        json.dump(report, output, ensure_ascii=False, indent=2, allow_nan=False)
    print(json.dumps({"output": str(destination), **report["aggregate"]}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--guides", required=True)
    parser.add_argument("--output", required=True)
    run(parser.parse_args())
