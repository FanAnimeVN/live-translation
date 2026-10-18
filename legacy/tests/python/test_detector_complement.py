"""Fixed geometry-only candidate; no models, network or private data."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from probe_detector_complement import select_complement


def region(ident, box, **extra):
    return {"id": ident, "bbox": box, "order": 0, "ja": "原文", "score": .81,
            "scope": {"key": "captured-" + ident, "action": "translate", "memory": True}, **extra}


def test_adds_only_disjoint_secondary_and_retains_exact_source_evidence():
    primary = [region("a", [10, 10, 20, 80])]
    secondary = [region("a", [15, 10, 20, 80]), region("b", [100, 10, 20, 80],
        sourceMembers=[{"polygon": [[100, 10], [120, 10], [120, 90], [100, 90]], "score": .77}])]
    before = deepcopy((primary, secondary))
    result = select_complement("page", primary, secondary)
    assert (primary, secondary) == before
    assert result["source_records"] == {"primary": primary, "secondary": secondary}
    assert [r["source_ref"] for r in result["regions"]] == [
        {"plane": "secondary", "page": "page", "id": "b"},
        {"plane": "primary", "page": "page", "id": "a"}]
    assert result["decisions"][0]["action"] == "overlap_review"
    assert result["decisions"][0]["overlap_primary_ids"] == ["a"]
    for row in result["regions"]:
        assert row["erasure_authority"] is False and row["memory_authority"] is False
        assert row["review"] is True and "scope" not in row  # No invented/reassigned source key.
    assert result["regions"][0]["sourceMembers"] == secondary[1]["sourceMembers"]


def test_membership_ignores_ocr_text_gold_fields_scores_and_input_ordinal():
    primary = [region("a", [10, 10, 20, 80])]
    secondary = [region("b", [100, 10, 20, 80]), region("c", [11, 11, 10, 10])]
    result = select_complement("page", primary, secondary)
    altered = deepcopy(secondary)
    for row in altered:
        row.update(ja="別の読み", reference="NOT-INPUT", edits=0, score=.35, order=999)
    again = select_complement("page", primary, list(reversed(altered)))
    assert [r["source_ref"] for r in result["regions"]] == [r["source_ref"] for r in again["regions"]]
    assert [r["id"] for r in result["regions"]] == [r["id"] for r in again["regions"]]


def test_any_positive_overlap_is_review_not_a_threshold_to_tune_to_gold():
    primary = [region("a", [10, 10, 20, 80])]
    overlap = select_complement("p", primary, [region("overlap", [29, 10, 20, 80])])
    touching = select_complement("p", primary, [region("touch", [30, 10, 20, 80])])
    assert {r["source_ref"]["id"] for r in touching["regions"]} == {"a", "touch"}
    assert overlap["decisions"][0]["action"] == "overlap_review"


def test_ambiguous_secondary_overlap_is_retained_for_review_not_arbitrarily_selected():
    result = select_complement("p", [], [region("a", [10, 10, 20, 80]), region("b", [29, 10, 20, 80])])
    assert result["regions"] == []
    assert [d["action"] for d in result["decisions"]] == ["secondary_overlap_review"] * 2
    assert len(result["source_records"]["secondary"]) == 2


@pytest.mark.parametrize("plane", ["primary", "secondary"])
def test_reader_exclusion_vetoes_both_planes_without_deleting_either_source(plane):
    primary = [region("a", [10, 10, 20, 80])]
    secondary = [region("b", [11, 11, 18, 78])]
    target = primary if plane == "primary" else secondary
    target[0]["scope"].update(reason="reader", action="defer")
    result = select_complement("p", primary, secondary)
    assert result["regions"] == []
    assert result["source_records"] == {"primary": primary, "secondary": secondary}


@pytest.mark.parametrize("bad", [float("nan"), -1, True])
def test_invalid_geometry_cannot_be_reported_as_disjoint(bad):
    with pytest.raises(ValueError):
        select_complement("p", [], [region("a", [bad, 10, 20, 80])])


def test_duplicate_identity_cannot_be_silently_deduplicated():
    with pytest.raises(ValueError):
        select_complement("p", [], [region("a", [10, 10, 20, 80]), region("a", [100, 10, 20, 80])])


def test_v2_preserves_an_entire_secondary_overlap_component_when_primary_is_disjoint():
    secondary = [region("a", [10, 10, 20, 80]), region("b", [29, 10, 20, 80])]
    result = select_complement("p", [], secondary, preserve_secondary_components=True)
    assert {r["source_ref"]["id"] for r in result["regions"]} == {"a", "b"}
    assert all(d["action"] == "add_disjoint_secondary" for d in result["decisions"])
    assert all(d["component_secondary_ids"] == ["a", "b"] for d in result["decisions"])
    assert result["source_records"]["secondary"] == secondary


def test_v2_never_cherry_picks_the_disjoint_tail_of_a_component_touching_primary():
    # a overlaps primary, b overlaps only a, c overlaps only b. None is selected.
    secondary = [region("a", [29, 10, 20, 80]), region("b", [48, 10, 20, 80]),
                 region("c", [67, 10, 20, 80])]
    result = select_complement("p", [region("p", [10, 10, 20, 80])], secondary,
                               preserve_secondary_components=True)
    assert [r["source_ref"]["id"] for r in result["regions"]] == ["p"]
    assert all(d["action"] == "component_overlap_review" for d in result["decisions"])
    assert all(d["component_secondary_ids"] == ["a", "b", "c"] for d in result["decisions"])


def test_v2_excluded_component_member_cannot_bridge_into_a_selected_source():
    secondary = [region("a", [10, 10, 20, 80]), region("b", [29, 10, 20, 80]),
                 region("c", [48, 10, 20, 80], readerExcluded=True)]
    result = select_complement("p", [], secondary, preserve_secondary_components=True)
    assert result["regions"] == []
    assert all(d["action"] == "reader_boundary_review" for d in result["decisions"])


def test_full_replay_verifies_source_pixels_and_both_report_planes_without_inference(tmp_path, monkeypatch, capsys):
    from io import BytesIO
    import json
    from types import SimpleNamespace
    from PIL import Image
    import urllib.request
    import probe_detector_complement as probe
    import compare_page_reports
    buffer = BytesIO()
    Image.new("RGB", (160, 120), "white").save(buffer, format="PNG")
    labels = [{"page_id": "p", "image_file": "source.png", "image_size": {"w": 160, "h": 120},
               "bubbles": [{"bubble_id": "b1", "bbox": {"x": 8, "y": 8, "w": 24, "h": 84}, "ja_ocr_truth": "原文"},
                           {"bubble_id": "b2", "bbox": {"x": 98, "y": 8, "w": 24, "h": 84}, "ja_ocr_truth": "原文"}]}]
    class Dataset:
        values = {"source.png": buffer.getvalue(), "ground_truth_benchmark.json": json.dumps(labels).encode()}
        def __init__(self, _): pass
        def read(self, entry): return self.values[entry if isinstance(entry, str) else entry.filename]
        def getinfo(self, name): return SimpleNamespace(filename=name, file_size=len(self.values[name]))
        def __enter__(self): return self
        def __exit__(self, *_): return False
    monkeypatch.setattr(probe, "DirectoryDataset", Dataset)
    monkeypatch.setattr(compare_page_reports, "ROOT", tmp_path)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: pytest.fail("No network in replay"))
    from manga_live.ocr import MangaEngine
    monkeypatch.setattr(MangaEngine, "load", lambda *a: pytest.fail("No model in replay"))
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    sources = [[region("a", [10, 10, 20, 80])], [region("b", [100, 10, 20, 80])]]
    parents = []
    for plane, rows in zip(("primary", "secondary"), sources):
        aligned, unmatched = probe.assign_to_labels(labels[0]["bubbles"], rows)
        parent = {"input_fingerprint_sha256": probe.dataset_fingerprint(Dataset(None)), "ocr": "same-recognizer",
                  "fresh_inference": True, "cloud": False,
                  "pages": [{"page": "p", "regions": rows, "aligned": aligned, "unmatched_prediction_ids": unmatched}]}
        path = artifacts / (plane + ".json")
        path.write_text(json.dumps(parent), encoding="utf-8")
        parents.append(path)
    output = artifacts / "candidate.json"
    args = SimpleNamespace(primary=str(parents[0]), secondary=str(parents[1]), output=str(output),
                           folder="RAM-only", secondary_components=True)
    probe.run(args)
    saved = json.loads(output.read_text(encoding="utf-8"))
    assert saved["aggregate"]["exact"] == 2
    assert saved["pages"][0]["source_records"] == dict(zip(("primary", "secondary"), sources))
    assert saved["fresh_inference"] is False and saved["automatic_promotion"] is False
    assert saved["version"] == probe.COMPONENT_VERSION
    assert saved["paired_primary"]["aggregate"]["regressed"] == 0
    assert len(saved["source_report_sha256"]) == 2
    assert all(p.suffix == ".json" for p in artifacts.iterdir())
    assert "原文" not in capsys.readouterr().out
    # Existing evidence and a changed recognizer are both refused, not rerated.
    with pytest.raises(ValueError, match="overwrite"):
        probe.run(args)
    args.output = str(artifacts / "incompatible.json")
    changed = json.loads(parents[1].read_text(encoding="utf-8"))
    changed["ocr"] = "different-recognizer"
    parents[1].write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="recognizer"):
        probe.run(args)
    assert not Path(args.output).exists()
    changed["ocr"] = "same-recognizer"
    # This source overlaps primary and would not be selected. It must still
    # be validated against the actual image, not allowed to veto with bad bounds.
    changed["pages"][0]["regions"][0]["bbox"] = [20, 10, 200, 80]
    parents[1].write_text(json.dumps(changed), encoding="utf-8")
    with pytest.raises(ValueError, match="outside"):
        probe.run(args)
    assert not Path(args.output).exists()
