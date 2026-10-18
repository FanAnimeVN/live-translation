from copy import deepcopy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from compare_page_reports import compare


def report(prediction="あ",reference="あ"):
    return {"input_fingerprint_sha256":"same-input","pages":[{"page":"fixture",
            "regions":[{"id":"r000"}],"aligned":[{"id":"b01","reference":reference,
            "prediction":prediction,"characters":1,"edits":int(reference!=prediction),"region_ids":["r000"]}]}]}


def test_cer_improvement_cannot_hide_a_label_regression_or_auto_promote():
    base=report();trial=report("い")
    result=compare(base,trial)
    assert result["aggregate"]["regressed"]==1 and result["aggregate"]["candidate_exact"]==0
    assert result["automatic_promotion"] is False and result["new_inference"] is False
    assert "prediction" not in result["label_deltas"][0],"Do not copy private dialogue into summary deltas"


def test_equal_edit_count_does_not_hide_different_predictions():
    result=compare(report("い"),report("う"))
    assert result["aggregate"]["changed_same_edit_count"]==1
    assert result["label_deltas"][0]["changed_with_equal_edits"] is True


@pytest.mark.parametrize("mutate",[
    lambda data:data.update(input_fingerprint_sha256="different-images"),
    lambda data:data["pages"].append(deepcopy(data["pages"][0])),
    lambda data:data["pages"][0].update(page="another-page"),
    lambda data:data["pages"][0]["aligned"][0].update(reference="別"),
    lambda data:data["pages"][0]["aligned"][0].update(edits=50),
    lambda data:data["pages"][0]["aligned"][0].update(region_ids=["missing"]),
    lambda data:data["pages"][0]["aligned"].append(deepcopy(data["pages"][0]["aligned"][0])),
])
def test_changed_gold_coverage_counts_or_ambiguous_ids_are_rejected(mutate):
    base=report();trial=deepcopy(base);mutate(trial)
    with pytest.raises(ValueError):compare(base,trial)
