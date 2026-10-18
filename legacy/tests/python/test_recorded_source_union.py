"""Grouping experiment boundary: original sources, not gold-aware transcripts."""
from copy import deepcopy
from pathlib import Path
import sys

from PIL import Image, ImageDraw
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import probe_recorded_source_union as probe


def source(ident, x, *, text="原文", excluded=False):
    return {"id": ident, "bbox": [x-3, 37, 20, 76], "order": 0, "ja": text,
            "score": .8, "readerExcluded": excluded,
            "scope": {"key": "original-"+ident, "action": "translate", "memory": True},
            "sourceMembers": [{"polygon": [[x, 40], [x+14, 40], [x+14, 110], [x, 110]], "score": .8}]}


def test_grouping_unites_detector_sources_without_splicing_old_ocr_or_claiming_art():
    image = Image.new("RGB", (400, 400), "white")
    ImageDraw.Draw(image).rectangle((20, 20, 130, 150), outline="black", width=2)
    primary, secondary = [source("a", 50)], [source("a", 50), source("b", 75)]
    before = deepcopy((primary, secondary))
    result = probe.group_recorded_sources(image, primary, secondary, page="authored")
    assert len(result["regions"]) == 1
    region = result["regions"][0]
    assert {(r["plane"], r["id"], r["member_index"]) for r in region["source_member_refs"]} == {
        ("primary", "a", 0), ("secondary", "a", 0), ("secondary", "b", 0)}
    assert len(region["sourceMembers"]) == 3
    assert region["erasure_authority"] is False and region["memory_authority"] is False
    assert region["review"] is True and region["overlay"] == "label"
    assert not {"ja", "vi", "scope", "speaker", "listener", "balloon"}.intersection(region)
    assert result["source_records"] == {"primary": primary, "secondary": secondary}
    assert (primary, secondary) == before


def test_full_experiment_reads_new_crops_not_either_old_transcript(tmp_path, monkeypatch):
    from io import BytesIO
    from types import SimpleNamespace
    import json
    import urllib.request
    import compare_page_reports
    from benchmark import dataset_fingerprint
    from benchmark_pages import assign_to_labels
    from manga_live.ocr import MangaEngine
    image = Image.new("RGB", (400, 400), "white")
    ImageDraw.Draw(image).rectangle((20, 20, 130, 150), outline="black", width=2)
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    labels = [{"page_id": "authored", "image_file": "source.png", "image_size": {"w": 400, "h": 400},
               "bubbles": [{"bubble_id": "b1", "bbox": {"x": 20, "y": 20, "w": 110, "h": 130},
                            "ja_ocr_truth": "新しい読み"}]}]
    class Dataset:
        values = {"source.png": buffer.getvalue(), "ground_truth_benchmark.json": json.dumps(labels).encode()}
        def __init__(self, _): pass
        def read(self, entry): return self.values[entry if isinstance(entry, str) else entry.filename]
        def getinfo(self, name): return SimpleNamespace(filename=name, file_size=len(self.values[name]))
        def __enter__(self): return self
        def __exit__(self, *_): return False
    monkeypatch.setattr(probe, "DirectoryDataset", Dataset)
    monkeypatch.setattr(compare_page_reports, "ROOT", tmp_path)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **kw: (_ for _ in ()).throw(AssertionError("no network")))
    artifacts = tmp_path / "artifacts"
    artifacts.mkdir()
    paths = []
    for plane, regions in (("primary", [source("a", 50, text="古い一")]),
                           ("secondary", [source("a", 50, text="古い二"), source("b", 75, text="古い三")])):
        aligned, unmatched = assign_to_labels(labels[0]["bubbles"], regions)
        report = {"cloud": False, "fresh_inference": True, "ocr": MangaEngine.name,
                  "input_fingerprint_sha256": dataset_fingerprint(Dataset(None)),
                  "pages": [{"page": "authored", "regions": regions, "aligned": aligned,
                             "unmatched_prediction_ids": unmatched, "detector_evidence": {"raw_class": [0, 1]}}]}
        path = artifacts / (plane+".json")
        path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")
        paths.append(path)
    class Recognizer:
        name = MangaEngine.name
        def load(self): pass
        def recognize_many(self, crops):
            assert len(crops) == 1 and crops[0].width < image.width
            return ["新しい読み"]
    result = probe.run(SimpleNamespace(folder="RAM-only", primary=str(paths[0]), secondary=str(paths[1]),
                                      output=str(artifacts / "result.json"), threads=2), engine=Recognizer())
    assert result["aggregate"]["exact"] == 1
    assert result["pages"][0]["regions"][0]["ja"] == "新しい読み"
    assert result["pages"][0]["detector_evidence"]["primary"] == {"raw_class": [0, 1]}
    assert result["fresh_detection"] is False and result["fresh_recognition"] is True
    assert result["complete"] is True and result["production_default"] is False


@pytest.mark.parametrize("recipe", [{}, {"support_components": True}, {"primary_anchored": True}])
def test_source_membership_is_independent_of_transcripts_gold_scores_and_input_order(recipe):
    image = Image.new("RGB", (400, 400), "white")
    ImageDraw.Draw(image).rectangle((20, 20, 130, 150), outline="black", width=2)
    primary, secondary = [source("a", 50)], [source("b", 75), source("c", 90)]
    expected = probe.group_recorded_sources(image, primary, secondary, page="authored", **recipe)
    changed = deepcopy((primary, secondary))
    for rows in changed:
        rows.reverse()
        for row in rows:
            row.update(ja="DIFFERENT OCR 「 … 」", reference="NOT A ROUTING INPUT", edits=0, score=.4)
            for member in row["sourceMembers"]:
                member["score"] = .4
    result = probe.group_recorded_sources(image, *changed, page="authored", **recipe)
    assert [(r["id"], r["source_member_refs"], r["bbox"]) for r in result["regions"]] == [
        (r["id"], r["source_member_refs"], r["bbox"]) for r in expected["regions"]]


@pytest.mark.parametrize("choice", ["excluded", "reader_scope", "confirmed_speaker", "confirmed_listener"])
def test_experiment_refuses_reader_choices_instead_of_rebinding_them(choice):
    primary = [source("a", 50)]
    row = primary[0]
    if choice == "excluded": row["readerExcluded"] = True
    elif choice == "reader_scope": row["scope"]["reason"] = "reader"
    elif choice == "confirmed_speaker": row["speaker"] = "confirmed"
    else: row["listener"] = "confirmed"
    before = deepcopy(primary)
    with pytest.raises(ValueError, match="reader"):
        probe.group_recorded_sources(Image.new("RGB", (400, 400)), primary, [], page="authored")
    assert primary == before


@pytest.mark.parametrize("bad", ["missing_members", "nan", "outside", "bowtie", "duplicate_id"])
def test_invalid_original_geometry_cannot_be_invented_or_silently_deduplicated(bad):
    primary = [source("a", 50)]
    if bad == "missing_members": del primary[0]["sourceMembers"]
    elif bad == "nan": primary[0]["sourceMembers"][0]["score"] = float("nan")
    elif bad == "outside": primary[0]["sourceMembers"][0]["polygon"][0][0] = 401
    elif bad == "bowtie": primary[0]["sourceMembers"][0]["polygon"] = [[50, 40], [64, 110], [64, 40], [50, 110]]
    else: primary.append(deepcopy(primary[0]))
    with pytest.raises(ValueError):
        probe.group_recorded_sources(Image.new("RGB", (400, 400)), primary, [], page="authored")


def test_grouping_rejection_retains_a_tiny_source_as_explicit_review():
    original = source("thin", 50)
    original["sourceMembers"][0]["polygon"] = [[50, 40], [51, 40], [51, 110], [50, 110]]
    original["sourceMembers"][0]["upstream_class"] = "text_free"
    result = probe.group_recorded_sources(Image.new("RGB", (400, 400), "white"), [original], [], page="authored")
    assert result["residual_member_count"] == 1
    assert len(result["regions"]) == 1
    assert result["source_records"]["primary"][0]["sourceMembers"][0]["upstream_class"] == "text_free"
    assert result["regions"][0]["source_member_refs"] == [
        {"plane": "primary", "page": "authored", "id": "thin", "member_index": 0}]
    assert result["regions"][0]["erasure_authority"] is False


def test_more_than_64_units_fails_before_any_silent_truncation():
    rows = []
    for i in range(65):
        x, y = 5+(i % 5)*70, 5+(i // 5)*25
        rows.append({"id": str(i), "bbox": [x, y, 10, 10], "sourceMembers": [
            {"polygon": [[x, y], [x+10, y], [x+10, y+10], [x, y+10]], "score": .8}]})
    with pytest.raises(ValueError, match="64 units"):
        probe.group_recorded_sources(Image.new("RGB", (400, 400), "white"), rows, [], page="authored")


def test_overlapping_detector_support_is_read_once_but_keeps_both_original_members():
    # On open page paper the old grouping leaves each detector polygon as an
    # independent OCR request. They cover the same line, not two text copies.
    image = Image.new("RGB", (400, 400), "white")
    primary, secondary = [source("a", 50)], [source("b", 52)]
    result = probe.group_recorded_sources(image, primary, secondary, page="authored", support_components=True)
    assert len(result["regions"]) == 1
    region = result["regions"][0]
    assert len(region["sourceMembers"]) == 2
    lookup = {"primary": {"a": primary[0]}, "secondary": {"b": secondary[0]}}
    for member, ref in zip(region["sourceMembers"], region["source_member_refs"], strict=True):
        assert member == lookup[ref["plane"]][ref["id"]]["sourceMembers"][ref["member_index"]]
    assert region["bbox"] == [47, 37, 22, 76]
    assert region["erasure_authority"] is False


def test_support_rule_does_not_join_unrelated_or_same_plane_lines():
    image = Image.new("RGB", (400, 400), "white")
    primary, secondary = [source("a", 50), source("b", 50)], [source("c", 90)]
    result = probe.group_recorded_sources(image, primary, secondary, page="authored", support_components=True)
    assert result["support_edges"] == []
    assert len(result["regions"]) == 3
    assert sum(len(r["sourceMembers"]) for r in result["regions"]) == 3


def test_support_components_are_source_only_and_keep_exact_refs_after_regrouping():
    image = Image.new("RGB", (400, 400), "white")
    primary, secondary = [source("a", 50)], [source("b", 52), source("c", 95)]
    before = deepcopy((primary, secondary))
    expected = probe.group_recorded_sources(image, primary, secondary, page="authored", support_components=True)
    for rows in (primary, secondary):
        rows.reverse()
        for row in rows:
            row.update(ja="「DIFFERENT … OCR」", reference="NOT INPUT", edits=123)
    result = probe.group_recorded_sources(image, primary, secondary, page="authored", support_components=True)
    assert [(r["id"], r["bbox"], r["source_member_refs"]) for r in result["regions"]] == [
        (r["id"], r["bbox"], r["source_member_refs"]) for r in expected["regions"]]
    assert expected["source_records"] == dict(zip(("primary", "secondary"), before))
    assert len(result["support_edges"]) == 1
    assert result["recognition_view_count"] == 2


def test_primary_anchoring_does_not_let_secondary_support_merge_two_existing_utterances():
    # A learned/paper enclosure can cover two distinct primary utterances.
    # Their original partition must survive even when the secondary detector
    # bridges them with one broad proposal. This is not a glyph/erasure test.
    image = Image.new("RGB", (400, 400), "white")
    ImageDraw.Draw(image).rectangle((20, 20, 180, 150), outline="black", width=2)
    primary = [source("right", 110), source("left", 50)]
    bridge = source("bridge", 48)
    bridge["bbox"] = [45, 37, 84, 76]
    bridge["sourceMembers"][0]["polygon"] = [[48, 40], [126, 40], [126, 110], [48, 110]]
    secondary = [source("support", 112), bridge]
    before = deepcopy((primary, secondary))
    result = probe.group_recorded_sources(image, primary, secondary, page="authored", primary_anchored=True)
    for region in result["regions"]:
        primary_ids = {ref["id"] for ref in region["source_member_refs"] if ref["plane"] == "primary"}
        assert len(primary_ids) <= 1
    assert len(result["regions"]) == 3
    supported = next(r for r in result["regions"] if any(ref["id"] == "right" for ref in r["source_member_refs"]))
    assert {r["id"] for r in supported["source_member_refs"]} == {"right", "support"}
    assert result["source_records"] == dict(zip(("primary", "secondary"), before))
    assert sum(len(r["sourceMembers"]) for r in result["regions"]) == 4
    assert all(r["erasure_authority"] is False and r["memory_authority"] is False for r in result["regions"])
