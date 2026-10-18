"""Diagnostic provenance tests; no model loads or private raster writes."""
from contextlib import nullcontext
from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import probe_member_preserving_grouping as probe
from manga_live.ocr import polygon
from manga_live.text_scope import SCOPE_VERSION


def fixture_candidate():
    # Deliberately disagree: identical aggregate scores would not imply that
    # these two independently recognized strings are equal.
    members = [{"polygon": polygon([35, 10, 10, 40]), "score": .92},
               {"polygon": polygon([20, 10, 10, 40]), "score": .47}]
    return {"schema": 1, "layout_version": "balloon-mask-v19-open-overlap20-candidate",
            "scope_version": SCOPE_VERSION, "ocr": probe.MangaEngine.name,
            "detector": "PP-OCRv5_mobile_det", "device": "CPU",
            "production_default": False, "fresh_inference": True, "cloud": False,
            "input_fingerprint_sha256": "a" * 64,
            "pages": [{"page": "p1", "detector_evidence": {"raw_detections": deepcopy(members)},
                       "regions": [{"id": "r000", "bbox": [18, 8, 30, 45], "ja": "合体！",
                                    "overlay": "label", "review": True,
                                    "reviewReasons": ["layout_cluster", "quote_balance"],
                                    "sourceMembers": members,
                                    "scope": {"action": "translate", "memory": False}}]}]}


def prepare_run(monkeypatch, tmp_path, candidate=None):
    candidate = fixture_candidate() if candidate is None else candidate
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    evidence = artifacts / "candidate.json"
    evidence.write_text(json.dumps(candidate), encoding="utf-8")
    output = artifacts / "result.json"
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    image = Image.new("RGB", (80, 80), "white")
    bubbles = [{"bubble_id": "b1", "bbox": {"x": 10, "y": 0, "w": 50, "h": 60},
                "ja_ocr_truth": "右左"}]
    pages = [({"page_id": "p1"}, image, bubbles)]
    monkeypatch.setattr(probe, "DirectoryDataset", lambda _: nullcontext(object()))
    monkeypatch.setattr(probe, "audit", lambda _: ({"eligible_pages": 1}, [], pages))
    monkeypatch.setattr(probe, "dataset_fingerprint", lambda _: "a" * 64)
    calls = []

    class FakeEngine:
        name = probe.MangaEngine.name

        def __init__(self, _, threads):
            calls.append(("init", threads))

        def recognize_many(self, crops):
            calls.append(("batch", [crop.size for crop in crops]))
            return ["右", "左"][:len(crops)]

    monkeypatch.setattr(probe, "MangaEngine", FakeEngine)
    args = SimpleNamespace(candidate=evidence, output=output, folder="authored", threads=4, batch=2)
    return args, candidate, calls


def test_union_and_member_text_are_independent_and_members_remain_auditable(monkeypatch, tmp_path):
    args, candidate, calls = prepare_run(monkeypatch, tmp_path)
    before = deepcopy(candidate)
    probe.run(args)
    report = json.loads(args.output.read_text(encoding="utf-8"))
    group = report["pages"][0]["member_groups"][0]
    assert group["union"] == "合体！", "Union evidence was overwritten before comparison"
    assert group["members"] == "右左"
    region = report["pages"][0]["regions"][0]
    assert region["unionJa"] == "合体！" and region["memberJa"] == region["ja"] == "右左"
    assert [p["ja"] for p in region["memberPredictions"]] == ["右", "左"]
    assert [p["score"] for p in region["memberPredictions"]] == [.92, .47]
    assert [p["sourceMemberIndex"] for p in region["memberPredictions"]] == [0, 1]
    assert region["sourceMembers"] == before["pages"][0]["regions"][0]["sourceMembers"]
    assert region["reviewReasons"] == ["layout_cluster", "quote_balance"]
    assert region["scope"]["memory"] is False and region["overlay"] == "label"
    assert candidate == before
    assert calls == [("init", 4), ("batch", [(10, 40), (10, 40)])]
    assert group["equal"] is False
    assert report["aggregate"]["exact"] == 1 and report["union_aggregate"]["exact"] == 0
    assert report["comparator_version"] == "member-preserving-v2" and report["schema"] == 2
    assert report["fresh_inference"] is False and report["fresh_member_inference"] is True
    assert report["pages"][0]["detector_evidence"] == before["pages"][0]["detector_evidence"]
    assert [p["rawDetectorIndex"] for p in region["memberPredictions"]] == [0, 1]
    assert json.loads(args.candidate.read_text(encoding="utf-8")) == before


def test_reading_order_retains_original_member_indices(monkeypatch, tmp_path):
    candidate = fixture_candidate()
    candidate["pages"][0]["regions"][0]["sourceMembers"].reverse()
    args, _, _ = prepare_run(monkeypatch, tmp_path, candidate)
    probe.run(args)
    region = json.loads(args.output.read_text(encoding="utf-8"))["pages"][0]["regions"][0]
    assert region["ja"] == "右左"
    assert [p["sourceMemberIndex"] for p in region["memberPredictions"]] == [1, 0]
    assert [p["rawDetectorIndex"] for p in region["memberPredictions"]] == [0, 1]


@pytest.mark.parametrize("field,value", [
    ("schema", True), ("schema", 2), ("layout_version", "balloon-mask-v16-outer-notch-veto"),
    ("scope_version", "obsolete-scope"), ("ocr", "other-engine"), ("detector", "other-detector"),
    ("device", "GPU"), ("production_default", True), ("fresh_inference", False), ("cloud", True),
    ("input_fingerprint_sha256", "b" * 64),
])
def test_incompatible_or_mismatched_source_rejected_before_engine(monkeypatch, tmp_path, field, value):
    candidate = fixture_candidate()
    candidate[field] = value
    args, _, calls = prepare_run(monkeypatch, tmp_path, candidate)
    with pytest.raises(ValueError):
        probe.run(args)
    assert calls == [] and not args.output.exists()


@pytest.mark.parametrize("field,value", [
    ("threads", 0), ("threads", 5), ("threads", True), ("threads", 1.5),
    ("batch", 0), ("batch", 3), ("batch", True), ("batch", 1.5),
])
def test_work_is_bounded_before_engine(monkeypatch, tmp_path, field, value):
    args, _, calls = prepare_run(monkeypatch, tmp_path)
    setattr(args, field, value)
    with pytest.raises(ValueError, match="bounded"):
        probe.run(args)
    assert calls == [] and not args.output.exists()


def test_existing_artifact_never_overwritten(monkeypatch, tmp_path):
    args, _, calls = prepare_run(monkeypatch, tmp_path)
    args.output.write_text("PREVIOUS_EVIDENCE", encoding="utf-8")
    with pytest.raises(ValueError, match="never overwrite"):
        probe.run(args)
    assert calls == [] and args.output.read_text(encoding="utf-8") == "PREVIOUS_EVIDENCE"


def test_output_cannot_escape_artifacts(monkeypatch, tmp_path):
    args, _, calls = prepare_run(monkeypatch, tmp_path)
    args.output = tmp_path / "outside.json"
    with pytest.raises(ValueError, match="new JSON"):
        probe.run(args)
    assert calls == [] and not args.output.exists()


@pytest.mark.parametrize("mutation", [
    "duplicate_page", "missing_page", "wrong_page", "duplicate_region", "stale_members",
    "changed_score", "changed_polygon", "duplicated_raw", "duplicated_member", "cut_union",
    "single_cluster", "trusted_cluster", "balloon_cluster", "bad_scope", "bad_order",
])
def test_bad_provenance_or_coverage_rejected_before_engine(monkeypatch, tmp_path, mutation):
    candidate = fixture_candidate()
    page = candidate["pages"][0]
    region = page["regions"][0]
    if mutation == "duplicate_page": candidate["pages"].append(deepcopy(page))
    elif mutation == "missing_page": candidate["pages"] = []
    elif mutation == "wrong_page": page["page"] = "unknown"
    elif mutation == "duplicate_region": page["regions"].append(deepcopy(region))
    elif mutation == "stale_members": region["memberPredictions"] = []
    elif mutation == "changed_score": region["sourceMembers"][0]["score"] = .1
    elif mutation == "changed_polygon": region["sourceMembers"][0]["polygon"][0][0] += 1
    elif mutation == "duplicated_raw": page["detector_evidence"]["raw_detections"].append(deepcopy(region["sourceMembers"][0]))
    elif mutation == "duplicated_member": region["sourceMembers"].append(deepcopy(region["sourceMembers"][0]))
    elif mutation == "cut_union": region["bbox"] = [20, 10, 20, 40]
    elif mutation == "single_cluster": region["sourceMembers"].pop()
    elif mutation == "trusted_cluster": region["scope"]["memory"] = True
    elif mutation == "balloon_cluster": region["balloon"] = {}
    elif mutation == "bad_scope": region["scope"] = None
    elif mutation == "bad_order": region["order"] = True
    args, _, calls = prepare_run(monkeypatch, tmp_path, candidate)
    with pytest.raises(ValueError):
        probe.run(args)
    assert calls == [] and not args.output.exists()


@pytest.mark.parametrize("value", [float("nan"), float("inf"), True, "10", -1])
def test_invalid_polygon_numbers_fail_before_crop(value):
    member = fixture_candidate()["pages"][0]["regions"][0]["sourceMembers"][0]
    member["polygon"][0][0] = value
    with pytest.raises(ValueError, match="polygon/score"):
        probe.member_box(member, Image.new("RGB", (80, 80)))


def test_fractional_polygon_rounds_outward_to_preserve_all_source_pixels():
    member = {"polygon": polygon([10.2, 10.3, 10.6, 30.8]), "score": .95}
    assert probe.member_box(member, Image.new("RGB", (80, 80))) == [10, 10, 11, 32]


@pytest.mark.parametrize("values", ["右左", [], ["右"], ["右", "左", "余"], ["右", 2], ["右", "x" * 3001]])
def test_incomplete_or_malformed_inference_is_not_recorded_as_success(monkeypatch, tmp_path, values):
    args, _, _ = prepare_run(monkeypatch, tmp_path)
    monkeypatch.setattr(probe.MangaEngine, "recognize_many", lambda _self, _: values)
    with pytest.raises(ValueError, match="incomplete"):
        probe.run(args)
    assert not args.output.exists()


def test_deferred_source_remains_unchanged_without_member_inference(monkeypatch, tmp_path):
    candidate = fixture_candidate()
    candidate["pages"][0]["regions"][0]["scope"]["action"] = "defer"
    args, _, calls = prepare_run(monkeypatch, tmp_path, candidate)
    probe.run(args)
    page = json.loads(args.output.read_text(encoding="utf-8"))["pages"][0]
    assert page["member_groups"] == [] and page["regions"] == candidate["pages"][0]["regions"]
    assert calls == [("init", 4)]
