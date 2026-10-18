"""Build a private, source-preserving OCR review queue.

The queue is for a Japanese-capable reviewer, not a runtime selector and not a
new gold file.  It combines already-recorded recognizer alternatives with
observable disagreement so that the next annotation pass can resolve labels,
boxes and reading order before any adaptation manifest is allowed.
"""

import argparse
import json
import unicodedata
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def normalized(value):
    return "".join(unicodedata.normalize("NFKC", value).split())


def load_rows(path):
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if "rows" in payload:
        return {row["id"]: row for row in payload["rows"]}
    rows = {}
    for page in payload.get("pages", []):
        page_id = page["page"]
        for row in page.get("aligned", []):
            rows[f"{page_id}:{row['id']}"] = {
                "id": f"{page_id}:{row['id']}",
                "reference": row.get("reference", ""),
                "prediction": row.get("prediction", ""),
                "edits": row.get("edits"),
            }
    return rows


def review_reason(row):
    predictions = row["predictions"]
    normalized_predictions = {normalized(value) for value in predictions.values()}
    reference = normalized(row["reference"])
    matches = [name for name, value in predictions.items() if normalized(value) == reference]
    if not matches:
        if len(normalized_predictions) == 1:
            return "unanimous_nonmatch"
        return "all_candidates_disagree"
    if len(normalized_predictions) > 1:
        return "candidate_disagreement"
    return "agreement_with_reference"


def run(args):
    output = Path(args.output).resolve()
    if ROOT / "artifacts" not in output.parents:
        raise ValueError("Review artifacts must stay in the project's ignored artifacts directory")
    base = load_rows(args.base)
    hayai = load_rows(args.hayai)
    baberu = load_rows(args.baberu)
    identifiers = sorted(set(base) & set(hayai) & set(baberu))
    rows = []
    for identifier in identifiers:
        reference = base[identifier].get("reference", "")
        predictions = {
            "manga_ocr": base[identifier].get("variants", {}).get("base", {}).get("prediction", "")
            if "variants" in base[identifier] else base[identifier].get("prediction", ""),
            "hayai_nova": hayai[identifier].get("prediction", ""),
            "baberu": baberu[identifier].get("prediction", ""),
        }
        row = {"id": identifier, "reference": reference, "predictions": predictions}
        normalized_predictions = {name: normalized(value) for name, value in predictions.items()}
        row["agreement_value"] = max(normalized_predictions.values(), key=lambda value: list(normalized_predictions.values()).count(value))
        row["agreement"] = max(list(normalized_predictions.values()).count(value) for value in normalized_predictions.values())
        row["reason"] = review_reason(row)
        row["recommended_action"] = (
            "verify pixels, crop geometry and reading order before using as training data"
            if row["reason"] in ("unanimous_nonmatch", "all_candidates_disagree")
            else "compare candidates against pixels; retain exact source expression"
        )
        rows.append(row)
    rows.sort(key=lambda row: (0 if row["reason"] == "unanimous_nonmatch" else 1,
                               row["agreement"], row["id"]))
    report = {
        "schema": 1,
        "source": "private recorded recognizer alternatives",
        "production_default_changed": False,
        "gold_used_for_runtime_routing": False,
        "rows": rows,
        "counts": {
            "rows": len(rows),
            "unanimous_nonmatch": sum(row["reason"] == "unanimous_nonmatch" for row in rows),
            "all_candidates_disagree": sum(row["reason"] == "all_candidates_disagree" for row in rows),
            "candidate_disagreement": sum(row["reason"] == "candidate_disagreement" for row in rows),
            "agreement_with_reference": sum(row["reason"] == "agreement_with_reference" for row in rows),
        },
        "limitations": [
            "This is a reviewer queue, not independent Japanese gold.",
            "No row is promoted, corrected, routed or granted erasure authority by this artifact.",
            "No Vietnamese or clean-background gold is present.",
        ],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"counts": report["counts"], "output": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default=str(ROOT / "artifacts/private-ocr-preprocess-variants-20261016.json"))
    parser.add_argument("--hayai", default=str(ROOT / "artifacts/private-hayai-nova-crops-384-20261016.json"))
    parser.add_argument("--baberu", default=str(ROOT / "artifacts/private-baberu-gold-crops-20261016.json"))
    parser.add_argument("--output", default=str(ROOT / "artifacts/private-ocr-review-queue-20261016.json"))
    run(parser.parse_args())
