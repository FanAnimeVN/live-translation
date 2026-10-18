"""Score a reviewed Japanese→Vietnamese run without inventing a quality claim.

The Manga109 package currently contains Japanese OCR labels but no independent
Vietnamese reference or human error labels.  This gate therefore requires two
private, user-created artifacts: a prediction report and a review sidecar tied
to the exact dataset fingerprint.  Missing or mismatched evidence is a hard
failure, never a zero-error result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from benchmark import DirectoryDataset, audit, dataset_fingerprint  # noqa: E402


SCHEMA = 1
SPLITS = {"heldout", "development"}
DIFFICULTIES = {"ordinary", "hard"}
SERIOUS_TYPES = {"meaning", "negation", "speaker", "pronoun", "term", "omission", "addition"}
MAX_ROWS=2048
MAX_TEXT=3000
MAX_INPUT_BYTES=8*1024*1024


def validate_run(predictions:dict)->None:
    run=predictions.get("run")
    if not isinstance(run,dict):raise ValueError("Explicit run provenance is required")
    for field in ("id","model","prompt_version"):
        value=run.get(field)
        if not isinstance(value,str) or not value.strip() or len(value)>128:
            raise ValueError("Invalid run provenance identity")
    for field in ("source_ocr_fingerprint_sha256","context_fingerprint_sha256"):
        value=run.get(field)
        if not isinstance(value,str) or not re.fullmatch(r"[a-f0-9]{64}",value):
            raise ValueError("Invalid run provenance source/context fingerprint")


def prediction_fingerprint(predictions:dict)->str:
    """Bind reviews to exact output AND run metadata; never include this hash in its input."""
    try:
        raw=json.dumps(predictions,ensure_ascii=False,sort_keys=True,
            separators=(",",":"),allow_nan=False).encode("utf-8")
    except (TypeError,ValueError) as error:
        raise ValueError("Prediction provenance is not finite JSON") from error
    return hashlib.sha256(raw).hexdigest()


def norm(value: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", value)).casefold()


def distance(a: str, b: str) -> int:
    previous = list(range(len(b) + 1))
    for i, left in enumerate(a, 1):
        row = [i]
        for j, right in enumerate(b, 1):
            row.append(min(row[-1] + 1, previous[j] + 1,
                           previous[j - 1] + (left != right)))
        previous = row
    return previous[-1]


def _key(row: dict) -> tuple[str, str]:
    page, bubble = row.get("page_id"), row.get("bubble_id")
    if any(not isinstance(value,str) or not value.strip() or len(value)>128 for value in (page,bubble)):
        raise ValueError("Every row needs page_id and bubble_id")
    return page, bubble


def load_json(path: Path, label: str) -> dict:
    try:
        if path.stat().st_size>MAX_INPUT_BYTES:raise ValueError("Artifact exceeds input size limit")
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise ValueError(f"Cannot read {label}: {error}") from error
    if not isinstance(value, dict) or type(value.get("schema")) is not int or value["schema"] != SCHEMA:
        raise ValueError(f"{label} must use schema {SCHEMA}")
    return value


def score(dataset_folder: str | Path, predictions_path: str | Path,
          review_path: str | Path) -> dict:
    folder = Path(dataset_folder).resolve(strict=True)
    with DirectoryDataset(folder) as archive:
        counts, audit_issues, valid = audit(archive)
        fingerprint = dataset_fingerprint(archive)
        expected = {
            (page["page_id"], bubble["bubble_id"]): bubble
            for page, _image, bubbles in valid for bubble in bubbles
        }

    predictions = load_json(Path(predictions_path), "predictions")
    validate_run(predictions)
    reviews = load_json(Path(review_path), "review sidecar")
    for name, value in (("predictions", predictions), ("review sidecar", reviews)):
        if value.get("dataset_fingerprint_sha256") != fingerprint:
            raise ValueError(f"{name} is for a different dataset fingerprint")
    run_fingerprint=prediction_fingerprint(predictions)
    if reviews.get("prediction_fingerprint_sha256")!=run_fingerprint:
        raise ValueError("Review sidecar is for a different prediction run; output or provenance changed")
    reviewer_count=reviews.get("reviewer_count")
    if type(reviewer_count) is not int or not 1<=reviewer_count<=20:
        raise ValueError("reviewer_count must be an explicit integer in 1..20")

    prediction_rows = predictions.get("rows")
    review_rows = reviews.get("rows")
    if any(not isinstance(value,list) or len(value)>MAX_ROWS for value in (prediction_rows,review_rows)):
        raise ValueError("Both artifacts need a bounded rows array")
    predicted = {}
    for row in prediction_rows:
        if not isinstance(row, dict):
            raise ValueError("Prediction row is not an object")
        key = _key(row)
        if key in predicted:
            raise ValueError(f"Duplicate prediction row: {key}")
        if key not in expected:
            raise ValueError(f"Prediction is not an eligible gold bubble: {key}")
        value = row.get("vi")
        if not isinstance(value, str) or not value.strip() or len(value)>MAX_TEXT:
            raise ValueError(f"Empty prediction: {key}")
        predicted[key] = value

    reviewed = {}
    for row in review_rows:
        if not isinstance(row, dict):
            raise ValueError("Review row is not an object")
        key = _key(row)
        if key in reviewed:
            raise ValueError(f"Duplicate review row: {key}")
        if key not in predicted:
            raise ValueError(f"Review has no matching prediction: {key}")
        if (not isinstance(row.get("split"),str) or row["split"] not in SPLITS or
                not isinstance(row.get("difficulty"),str) or row["difficulty"] not in DIFFICULTIES):
            raise ValueError(f"Review split/difficulty is invalid: {key}")
        if not isinstance(row.get("reviewed_by"), str) or not row["reviewed_by"].strip() or len(row["reviewed_by"])>80:
            raise ValueError(f"Review row has no reviewer: {key}")
        serious = row.get("serious_error_types")
        if (not isinstance(serious,list) or len(serious)>len(SERIOUS_TYPES) or
                any(not isinstance(item,str) or item not in SERIOUS_TYPES for item in serious)):
            raise ValueError(f"Invalid serious_error_types: {key}")
        if len(set(serious)) != len(serious):
            raise ValueError(f"Duplicate serious error type: {key}")
        reviewed[key] = row

    missing_predictions = [list(key) for key in sorted(set(expected) - set(predicted))]
    missing_reviews = [list(key) for key in sorted(set(predicted) - set(reviewed))]
    missing_gold=[list(key) for key,row in sorted(expected.items())
        if not isinstance(row.get("vi_gold_trans"),str) or not row["vi_gold_trans"].strip()]
    if missing_predictions or missing_reviews or missing_gold:
        return {
            "schema": SCHEMA, "passed": False, "gate_ready": False,
            "dataset_fingerprint_sha256": fingerprint, "counts": counts,
            "prediction_fingerprint_sha256":run_fingerprint,
            "audit": audit_issues, "missing_predictions": missing_predictions,
            "missing_reviews": missing_reviews,"missing_vietnamese_gold":missing_gold,
            "limitations": ["A complete independent Vietnamese gold/review sidecar is required."],
        }
    if len({row["reviewed_by"] for row in reviewed.values()})!=reviewer_count:
        raise ValueError("reviewer_count differs from the complete row-level reviewer attribution")
    if any(len(row["vi_gold_trans"])>MAX_TEXT for row in expected.values()):
        raise ValueError("Vietnamese reference exceeds text limit")
    if sum(len(norm(expected[key]["vi_gold_trans"]))*len(norm(text)) for key,text in predicted.items())>30_000_000:
        raise ValueError("Lexical scoring exceeds bounded work budget")

    rows = []
    ordinary_heldout = []
    total_edits = total_chars = exact = 0
    for key, reference_row in expected.items():
        prediction = predicted[key]
        reference = reference_row.get("vi_gold_trans", "")
        edits = distance(norm(reference), norm(prediction))
        chars = len(norm(reference))
        review = reviewed[key]
        error_types = review["serious_error_types"]
        total_edits += edits
        total_chars += chars
        exact += norm(reference) == norm(prediction)
        row = {"page_id": key[0], "bubble_id": key[1], "edits": edits,
               "reference_chars": chars, "exact": not edits,
               "difficulty": review["difficulty"], "split": review["split"],
               "serious_error_types": error_types}
        rows.append(row)
        if review["split"] == "heldout" and review["difficulty"] == "ordinary":
            ordinary_heldout.append(row)

    ordinary_serious = sum(bool(row["serious_error_types"]) for row in ordinary_heldout)
    ordinary_rate = ordinary_serious / len(ordinary_heldout) if ordinary_heldout else None
    rights = reviews.get("rights_confirmed") is True
    reference_review=reviews.get("reference_review")
    gold_reviewers=reference_review.get("reviewed_by") if isinstance(reference_review,dict) else None
    reference_ok=(isinstance(reference_review,dict) and
        all(reference_review.get(field) is True for field in
            ("source_japanese_reviewed","vietnamese_reference_reviewed","independent_of_predictions")) and
        isinstance(gold_reviewers,list) and 1<=len(gold_reviewers)<=20 and
        all(isinstance(value,str) and value.strip() and len(value)<=80 for value in gold_reviewers) and
        len(set(gold_reviewers))==len(gold_reviewers))
    human_review=reviews.get("independent_human_review") is True
    gate_ready = not audit_issues and rights and reference_ok and human_review and bool(ordinary_heldout)
    passed = gate_ready and ordinary_rate is not None and ordinary_rate <= 0.02
    return {
        "schema": SCHEMA, "passed": passed, "gate_ready": gate_ready,
        "dataset_fingerprint_sha256": fingerprint, "counts": counts,
        "prediction_fingerprint_sha256":run_fingerprint,
        "audit": audit_issues, "rows": rows,
        "metrics": {"bubbles": len(rows), "exact": exact / len(rows),
                     "cer": total_edits / max(total_chars, 1),
                     "ordinary_heldout": len(ordinary_heldout),
                     "ordinary_serious_errors": ordinary_serious,
                     "ordinary_serious_error_rate": ordinary_rate,
                     "groups":{split+"/"+difficulty:{"bubbles":len(group),
                         "serious_errors":sum(bool(row["serious_error_types"]) for row in group),
                         "serious_error_rate":sum(bool(row["serious_error_types"]) for row in group)/len(group) if group else None}
                         for split in sorted(SPLITS) for difficulty in sorted(DIFFICULTIES)
                         for group in [[row for row in rows if row["split"]==split and row["difficulty"]==difficulty]]}},
        "requirements": {"rights_confirmed": rights, "reviewer_count":True,
                         "independent_human_review":human_review,"reference_review_attested":reference_ok,
                         "ordinary_heldout_present": bool(ordinary_heldout),
                         "serious_error_threshold": 0.02},
        "limitations": [
            "Exact/CER are lexical diagnostics, not semantic proof.",
            "Serious-error rate is human-review labeled and is not inferred from string distance.",
            "Hard or development rows are reported but excluded from the ordinary held-out gate.",
            "Reviewer independence is an explicit human attestation, not inferred or certified by this tool.",
            "A small or nonrepresentative held-out sample cannot prove production/population quality.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prediction-fingerprint",help="Read-only canonical hash of a prediction run; no scoring/review attestation")
    parser.add_argument("--dataset-folder")
    parser.add_argument("--predictions")
    parser.add_argument("--reviews")
    parser.add_argument("--output")
    args = parser.parse_args()
    if args.prediction_fingerprint:
        if any((args.dataset_folder,args.predictions,args.reviews,args.output)):
            parser.error("Fingerprint mode cannot be combined with scoring/output")
        predictions=load_json(Path(args.prediction_fingerprint),"predictions")
        validate_run(predictions)
        print(prediction_fingerprint(predictions));return
    if not all((args.dataset_folder,args.predictions,args.reviews,args.output)):
        parser.error("Scoring requires dataset-folder, predictions, reviews and output")
    report = score(args.dataset_folder, args.predictions, args.reviews)
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("passed", "gate_ready", "metrics", "requirements")
                      if key in report}, ensure_ascii=False, indent=2))
    if not report["passed"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
