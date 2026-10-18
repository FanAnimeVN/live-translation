"""Build a private renderer replay using grouped text-only translations.

The source image remains in the fixture reader's RAM. This artifact contains
only the already-captured region metadata and two cloud translations; it is a
diagnostic replay, never a production page or cache entry.
"""
import argparse
import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(args):
    output = Path(args.output).resolve(); reference_output = Path(args.reference_output).resolve()
    if output.parent != ROOT / "artifacts" or reference_output.parent != ROOT / "artifacts" or output.exists() or reference_output.exists():
        raise ValueError("Replay outputs must be new private artifacts")
    native_source = json.loads(Path(args.native).read_text(encoding="utf-8"))
    grouped_source = json.loads(Path(args.grouped).read_text(encoding="utf-8"))
    cloud = json.loads(Path(args.cloud).read_text(encoding="utf-8"))
    native = copy.deepcopy(native_source)
    regions = native["runs"][0]["native"]["regions"]
    by_id = {row["id"]: row for row in cloud["runs"][0]["native"]["regions"]}
    selected = grouped_source["pages"][0]["regions"]
    source_ids = set()
    replacements = []
    for row in selected:
        assembly = row.get("sourceAssembly") or {}
        members = assembly.get("source_ids")
        if not isinstance(members, list) or len(members) < 2:
            raise ValueError("Grouped replay requires source member IDs")
        source_ids.update(members)
        cloud_row = by_id.get(row["id"])
        if cloud_row is None:
            raise ValueError("Cloud result does not match grouped ID")
        replacement = copy.deepcopy(row)
        replacement["vi"] = cloud_row["vi"]
        replacement["ambiguous"] = cloud_row.get("ambiguous", True)
        replacement["speaker"] = "unknown"; replacement["listener"] = "unknown"
        replacements.append(replacement)
    kept = [row for row in regions if row["id"] not in source_ids]
    native["runs"][0]["native"]["regions"] = sorted(kept + replacements, key=lambda row: row.get("order", 0))
    native["runs"][0]["native"]["metrics"] = {**native["runs"][0]["native"].get("metrics", {}), "grouped_replay": True}
    native["groupedReplay"] = True; native["sourceAssemblyVersion"] = grouped_source.get("assemblyVersion")
    output.write_text(json.dumps(native, ensure_ascii=False, indent=2), encoding="utf-8")
    ref = {"schema": 1, "cloud": False, "input_fingerprint_sha256": grouped_source["input_fingerprint_sha256"],
           "scope_version": "text-scope-v4-punctuation-support-review",
           "pages": [{"page": native["privatePage"], "regions": [
               {key: row.get(key) for key in ("id", "bbox", "order", "ja", "overlay", "review", "scope")}
               for row in native["runs"][0]["native"]["regions"]], "transient_patches": []}]}
    reference_output.write_text(json.dumps(ref, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"native": str(output), "reference": str(reference_output),
                      "source_ids_replaced": sorted(source_ids), "regions": len(native["runs"][0]["native"]["regions"])}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("--native", required=True); parser.add_argument("--grouped", required=True)
    parser.add_argument("--cloud", required=True); parser.add_argument("--output", required=True); parser.add_argument("--reference-output", required=True)
    run(parser.parse_args())
