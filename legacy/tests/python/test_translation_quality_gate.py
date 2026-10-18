import json
import hashlib
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from benchmark import DirectoryDataset, dataset_fingerprint
from translation_quality_gate import score,main,prediction_fingerprint


def make_dataset(tmp_path, gold="Cảm ơn"):
    image = tmp_path / "page.png"
    Image.new("RGB", (40, 60), "white").save(image)
    labels = [{"page_id": "p1", "image_file": "page.png", "image_size": {"w": 40, "h": 60},
               "bubbles": [{"bubble_id": "b1", "bbox": {"x": 2, "y": 3, "w": 10, "h": 15},
                             "ja_ocr_truth": "ありがとう", "vi_gold_trans": gold}]}]
    (tmp_path / "ground_truth_benchmark.json").write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
    with DirectoryDataset(tmp_path) as archive:
        return dataset_fingerprint(archive)


def write_run(tmp_path, fingerprint, *, serious=None, review=True):
    predictions={"schema": 1,
        "dataset_fingerprint_sha256": fingerprint,
        "run":{"id":"fixture-run","model":"fixture-only","prompt_version":"fixture-v1",
            "source_ocr_fingerprint_sha256":"a"*64,"context_fingerprint_sha256":"b"*64},
        "rows": [{"page_id": "p1", "bubble_id": "b1", "vi": "Cảm ơn"}]}
    (tmp_path / "predictions.json").write_text(json.dumps(predictions), encoding="utf-8")
    run_hash=hashlib.sha256(json.dumps(predictions,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()
    rows = []
    if review:
        rows.append({"page_id": "p1", "bubble_id": "b1", "split": "heldout", "difficulty": "ordinary",
                     "reviewed_by": "tester", "serious_error_types": serious or []})
    (tmp_path / "reviews.json").write_text(json.dumps({"schema": 1,
        "dataset_fingerprint_sha256": fingerprint, "rights_confirmed": True,
        "prediction_fingerprint_sha256":run_hash,
        "reference_review":{"source_japanese_reviewed":True,"vietnamese_reference_reviewed":True,
            "independent_of_predictions":True,"reviewed_by":["fixture-gold-reviewer"]},
        "independent_human_review":True,
        "reviewer_count": 1, "rows": rows}), encoding="utf-8")


def mutate(path,change):
    value=json.loads(path.read_text(encoding="utf-8"));change(value)
    path.write_text(json.dumps(value),encoding="utf-8")


@pytest.mark.parametrize("change",[
    lambda value:value["rows"][0].update(vi="Không cảm ơn"),
    lambda value:value["run"].update(model="different-model-same-output"),
    lambda value:value["run"].update(prompt_version="different-prompt-same-output"),
    lambda value:value["run"].update(context_fingerprint_sha256="c"*64),
    lambda value:value["run"].update(source_ocr_fingerprint_sha256="d"*64),
])
def test_reviews_cannot_be_reused_after_output_or_run_provenance_changes(tmp_path,change):
    fingerprint=make_dataset(tmp_path);write_run(tmp_path,fingerprint)
    mutate(tmp_path/"predictions.json",change)
    with pytest.raises(ValueError,match="different prediction"):
        score(tmp_path,tmp_path/"predictions.json",tmp_path/"reviews.json")


def test_missing_serious_judgment_is_not_implicitly_no_error(tmp_path):
    fingerprint=make_dataset(tmp_path);write_run(tmp_path,fingerprint)
    mutate(tmp_path/"reviews.json",lambda value:value["rows"][0].pop("serious_error_types"))
    with pytest.raises(ValueError,match="serious_error_types"):
        score(tmp_path,tmp_path/"predictions.json",tmp_path/"reviews.json")


@pytest.mark.parametrize("count",[True,0,21])
def test_reviewer_count_is_explicit_bounded_and_not_a_boolean(tmp_path,count):
    fingerprint=make_dataset(tmp_path);write_run(tmp_path,fingerprint)
    mutate(tmp_path/"reviews.json",lambda value:value.update(reviewer_count=count))
    with pytest.raises(ValueError,match="reviewer_count"):
        score(tmp_path,tmp_path/"predictions.json",tmp_path/"reviews.json")


def test_missing_vietnamese_gold_is_a_structured_not_ready_result(tmp_path):
    fingerprint=make_dataset(tmp_path,gold="");write_run(tmp_path,fingerprint)
    report=score(tmp_path,tmp_path/"predictions.json",tmp_path/"reviews.json")
    assert report["passed"] is False and report["gate_ready"] is False
    assert report["missing_vietnamese_gold"]==[["p1","b1"]]


@pytest.mark.parametrize("field",["reference_review","independent_human_review"])
def test_unattested_reference_or_review_cannot_authorize_quality_pass(tmp_path,field):
    fingerprint=make_dataset(tmp_path);write_run(tmp_path,fingerprint)
    mutate(tmp_path/"reviews.json",lambda value:value.pop(field))
    report=score(tmp_path,tmp_path/"predictions.json",tmp_path/"reviews.json")
    assert report["passed"] is False and report["gate_ready"] is False


def test_malformed_serious_error_type_is_rejected_cleanly(tmp_path):
    fingerprint=make_dataset(tmp_path);write_run(tmp_path,fingerprint)
    mutate(tmp_path/"reviews.json",lambda value:value["rows"][0].update(serious_error_types=[{}]))
    with pytest.raises(ValueError,match="serious_error_types"):
        score(tmp_path,tmp_path/"predictions.json",tmp_path/"reviews.json")


@pytest.mark.parametrize("change",[
    lambda value:value.pop("run"),
    lambda value:value["run"].pop("prompt_version"),
    lambda value:value["run"].update(model={"not":"a model"}),
    lambda value:value["run"].update(context_fingerprint_sha256="unknown"),
])
def test_predictions_require_explicit_bounded_run_provenance(tmp_path,change):
    fingerprint=make_dataset(tmp_path);write_run(tmp_path,fingerprint)
    mutate(tmp_path/"predictions.json",change)
    predictions=json.loads((tmp_path/"predictions.json").read_text(encoding="utf-8"))
    digest=hashlib.sha256(json.dumps(predictions,sort_keys=True,ensure_ascii=False,
        separators=(",",":"),allow_nan=False).encode("utf-8")).hexdigest()
    mutate(tmp_path/"reviews.json",lambda value:value.update(prediction_fingerprint_sha256=digest))
    with pytest.raises(ValueError,match="run provenance"):
        score(tmp_path,tmp_path/"predictions.json",tmp_path/"reviews.json")


def test_canonical_run_hash_survives_json_formatting_but_not_content_change(tmp_path):
    fingerprint=make_dataset(tmp_path);write_run(tmp_path,fingerprint)
    predictions=json.loads((tmp_path/"predictions.json").read_text(encoding="utf-8"))
    (tmp_path/"predictions.json").write_text(json.dumps(predictions,ensure_ascii=False,indent=4,sort_keys=True),encoding="utf-8")
    assert score(tmp_path,tmp_path/"predictions.json",tmp_path/"reviews.json")["passed"] is True


def test_fingerprint_cli_is_read_only_and_does_not_require_dataset_or_review(tmp_path,monkeypatch,capsys):
    fingerprint=make_dataset(tmp_path);write_run(tmp_path,fingerprint)
    before={path.name:path.read_bytes() for path in tmp_path.iterdir()}
    monkeypatch.setattr(sys,"argv",["gate","--prediction-fingerprint",str(tmp_path/"predictions.json")])
    main()
    predictions=json.loads((tmp_path/"predictions.json").read_text(encoding="utf-8"))
    assert capsys.readouterr().out.strip()==prediction_fingerprint(predictions)
    assert before=={path.name:path.read_bytes() for path in tmp_path.iterdir()}


def test_reviewer_count_must_match_complete_attribution(tmp_path):
    fingerprint=make_dataset(tmp_path);write_run(tmp_path,fingerprint)
    mutate(tmp_path/"reviews.json",lambda value:value.update(reviewer_count=2))
    with pytest.raises(ValueError,match="reviewer_count differs"):
        score(tmp_path,tmp_path/"predictions.json",tmp_path/"reviews.json")


def test_gate_passes_only_with_complete_human_review(tmp_path):
    fingerprint = make_dataset(tmp_path)
    write_run(tmp_path, fingerprint)
    report = score(tmp_path, tmp_path / "predictions.json", tmp_path / "reviews.json")
    assert report["passed"] is True
    assert report["metrics"]["ordinary_serious_error_rate"] == 0


def test_serious_error_threshold_is_not_hidden_by_exact_text(tmp_path):
    fingerprint = make_dataset(tmp_path)
    write_run(tmp_path, fingerprint, serious=["negation"])
    report = score(tmp_path, tmp_path / "predictions.json", tmp_path / "reviews.json")
    assert report["gate_ready"] is True
    assert report["passed"] is False
    assert report["metrics"]["ordinary_serious_error_rate"] == 1


def test_missing_review_is_not_a_passing_zero(tmp_path):
    fingerprint = make_dataset(tmp_path)
    write_run(tmp_path, fingerprint, review=False)
    report = score(tmp_path, tmp_path / "predictions.json", tmp_path / "reviews.json")
    assert report["passed"] is False
    assert report["gate_ready"] is False
    assert report["missing_reviews"] == [["p1", "b1"]]


def test_fingerprint_mismatch_is_rejected(tmp_path):
    fingerprint = make_dataset(tmp_path)
    write_run(tmp_path, "0" * 64)
    with pytest.raises(ValueError, match="different dataset fingerprint"):
        score(tmp_path, tmp_path / "predictions.json", tmp_path / "reviews.json")
