from copy import deepcopy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"scripts"))
from probe_block_guided_grouping import guide_regions, route_guided, select_replayed
import probe_block_guided_grouping as probe
import pytest
from manga_live.render_cleanup import render_patch
from manga_live.text_scope import story_regions


def regions():
    return [{"id": "r0", "order": 0, "bbox": [100, 100, 40, 140], "ja": "not used", "overlay": "label"},
        {"id": "r1", "order": 1, "bbox": [125, 100, 35, 160], "ja": "not used either", "overlay": "label"}]


def test_unique_block_joins_overlapping_crops_without_changing_input_or_inventing_erasure():
    source = regions(); before = deepcopy(source)
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [95, 95, 70, 170]}], (500, 600))
    assert source == before and len(proposed) == 1
    assert proposed[0]["bbox"] == [100, 100, 60, 160]
    assert proposed[0]["reviewReasons"] == ["layout_cluster"] and "ja" not in proposed[0]
    assert merges[0]["source_ids"] == ["r0", "r1"] and merges[0]["erasure_permitted"] is False
    assert render_patch(Image.new("RGB", (500, 600)), {**proposed[0], "ja": "text"}) is None


def test_grouping_does_not_use_ja_vi_or_gold_to_choose_a_better_crop():
    source = regions(); blocks = [{"id": "b", "bbox": [95, 95, 70, 170]}]
    before = guide_regions(source, blocks, (500, 600))
    for r in source: r.update(ja="entirely different", vi="entirely different", reference="gold")
    assert guide_regions(source, blocks, (500, 600)) == before


def test_nested_ambiguous_blocks_cannot_silently_merge_or_drop_source():
    source = regions()
    proposed, merges = guide_regions(source, [{"id": "a", "bbox": [95, 95, 70, 170]},
        {"id": "b", "bbox": [90, 90, 80, 180]}], (500, 600))
    assert proposed == source and merges == []


def test_proximity_alone_or_partial_containment_does_not_merge():
    source = regions(); source[1]["bbox"][0] = 145
    assert guide_regions(source, [{"id": "b", "bbox": [95, 95, 95, 170]}], (500, 600))[0] == source
    source = regions()
    assert guide_regions(source, [{"id": "b", "bbox": [100, 100, 45, 140]}], (500, 600))[0] == source


def test_bounded_balloon_and_explicit_fragment_veto_are_preserved():
    for marker in ({"balloon": {"textBox": [100, 100, 40, 140]}}, {"reviewReasons": ["layout_fragment"]}):
        source = regions(); source[0].update(marker)
        assert guide_regions(source, [{"id": "b", "bbox": [95, 95, 70, 170]}], (500, 600))[0] == source


def test_existing_visual_distrust_survives_union_and_unknown_speakers_stay_unknown():
    source = regions(); source[0].update(review=True, reviewReasons=["visual_punctuation_support"])
    result, _ = guide_regions(source, [{"id": "b", "bbox": [95, 95, 70, 170]}], (500, 600))
    assert result[0]["reviewReasons"] == ["layout_cluster", "visual_punctuation_support"]
    assert result[0]["speaker"] == result[0]["listener"] == "unknown"


def test_reader_choice_is_not_a_grouping_candidate_or_implicitly_translated():
    source = regions(); source[0]["scope"] = {"reason": "reader", "action": "translate"}
    assert guide_regions(source, [{"id": "b", "bbox": [95, 95, 70, 170]}], (500, 600))[0] == source
    source[0]["scope"] = {"reason": "unclassified", "action": "defer"}
    assert guide_regions(source, [{"id": "b", "bbox": [95, 95, 70, 170]}], (500, 600))[0] == source


@pytest.mark.parametrize("field", ["speaker", "listener"])
def test_grouping_cannot_replace_confirmed_source_identity_with_unknown(field):
    source = regions()
    source[0][field] = "reader-confirmed-character"
    assert guide_regions(source, [{"id": "b", "bbox": [95, 95, 70, 170]}], (500, 600))[0] == source


def test_source_preserving_assembly_keeps_the_final_negation_and_all_raw_punctuation():
    source = [
        {"id": "right", "order": 0, "bbox": [140, 100, 40, 119], "ja": "「俺は人間に", "overlay": "label", "score": .9},
        {"id": "middle", "order": 1, "bbox": [115, 101, 40, 154], "ja": "媚びる つもりは", "overlay": "label", "score": .8},
        {"id": "left", "order": 2, "bbox": [90, 103, 40, 61], "ja": "な い…」", "overlay": "label", "score": .7},
    ]
    before = deepcopy(source)
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [85, 95, 100, 170]}], (500, 600))
    assert len(proposed) == 1
    assembled = probe.preserve_source_ocr(proposed, merges, source)
    assert assembled[0]["ja"] == "「俺は人間に媚びる つもりはな い…」"
    assert assembled[0]["sourceRegions"] == source and source == before
    assert assembled[0]["score"] == .7 and assembled[0]["review"] is True
    assert render_patch(Image.new("RGB", (500, 600)), assembled[0]) is None


def test_fresh_union_does_not_elevate_source_visual_distrust_into_plot_memory():
    source = regions(); source[0]["scope"] = {"reason": "visual_review", "action": "translate", "memory": False}
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [95, 95, 70, 170]}], (500, 600))
    proposed[0]["ja"] = "今日は学校に行かない。"
    routed = route_guided(Image.new("RGB", (500, 600), "white"), proposed, merges)
    assert routed[0]["scope"]["memory"] is False
    assert routed[0]["scope"]["reason"] == "visual_review" and story_regions(routed) == []


def test_crop_replay_requires_identical_geometry_and_retains_current_distrust():
    region = {"id": "new", "bbox": [10, 20, 30, 40], "overlay": "label", "review": True,
        "reviewReasons": ["layout_cluster"]}
    recorded = [{**region, "id": "old", "ja": "テスト", "review": False, "reviewReasons": []}]
    result = select_replayed([region], recorded)["new"]
    assert result["ja"] == "テスト" and result["review"] is True and result["reviewReasons"] == ["layout_cluster"]
    with pytest.raises(ValueError): select_replayed([{**region, "bbox": [10, 20, 31, 40]}], recorded)
    with pytest.raises(ValueError): select_replayed([region], recorded*2)


def test_learned_block_cannot_join_a_short_line_with_a_multirow_paragraph():
    # Authored geometry: two differently scaled horizontal blocks touch through
    # detector padding. One large learned block is not evidence of one sentence.
    source = [
        {"id": "short", "order": 0, "bbox": [100, 100, 180, 30], "overlay": "label", "ja": "authored"},
        {"id": "paragraph", "order": 1, "bbox": [100, 120, 390, 95], "overlay": "label", "ja": "authored"},
    ]
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [90, 90, 410, 140]}], (600, 600))
    assert proposed == source and merges == []


def test_learned_block_cannot_join_staggered_vertical_columns_from_distinct_starts():
    source = regions()
    source[1]["bbox"] = [125, 180, 35, 160]
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [95, 95, 70, 250]}], (500, 600))
    assert proposed == source and merges == []


def test_learned_block_cannot_bridge_horizontal_and_vertical_source_blocks():
    source = regions()
    source[1]["bbox"] = [115, 100, 150, 35]
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [95, 95, 180, 170]}], (600, 600))
    assert proposed == source and merges == []


def test_local_adjacency_cannot_drift_transitively_across_a_leading_band():
    source = regions()
    source[1]["bbox"] = [125, 110, 35, 160]
    source.append({"id": "r2", "order": 2, "bbox": [150, 120, 35, 160], "overlay": "label"})
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [95, 95, 95, 190]}], (500, 600))
    assert len(proposed) == 2
    assert merges[0]["source_ids"] == ["r0", "r1"]
    assert proposed[1] == source[2]


def test_duplicate_padding_cannot_bridge_into_a_third_column():
    source = [{"id": f"r{i}", "order": i, "bbox": [x, 100, 40, 160], "overlay": "label"}
              for i, x in enumerate((100, 101, 130))]
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [95, 95, 80, 170]}], (500, 600))
    assert len(proposed) == 2 and merges[0]["source_ids"] == ["r0", "r1"]
    assert proposed[1] == source[2]


def test_regular_parallel_columns_keep_all_members_and_current_source_ids():
    source = [{"id": f"r{i}", "order": i, "bbox": [x, 100, 40, 160], "overlay": "label"}
              for i, x in enumerate((100, 125, 150))]
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [95, 95, 100, 170]}], (500, 600))
    assert len(proposed) == 1 and proposed[0]["bbox"] == [100, 100, 90, 160]
    assert merges[0]["source_ids"] == ["r0", "r1", "r2"]
    assert proposed[0]["id"] == "r0" and proposed[0]["order"] == 0


def run_fixture(tmp_path, monkeypatch):
    """Authored run-level evidence, no private source/model/network."""
    monkeypatch.setattr(probe, "ROOT", tmp_path)
    (tmp_path / "artifacts").mkdir()
    pp = {"input_fingerprint_sha256": "fixture", "layout_version": probe.LAYOUT_VERSION,
          "ocr": "authored-ocr-v1", "pages": [{"page": "p1", "regions": regions()}]}
    raw = [{"label": 2, "class": "text_free", "score": .88, "bbox": [95, 95, 70, 170],
            "raw_xyxy": [95., 95., 165., 265.], "rejected_geometry": False}]
    guide = {"input_fingerprint_sha256": "fixture", "detector": "ogkalu-detector-v4-s-int8-private-blocks",
             "experimental_detector": {"revision": "authored", "classes": ["bubble", "text_bubble", "text_free"]},
             "pages": [{"page": "p1", "regions": [{"id": "b", "bbox": [95, 95, 70, 170]}],
                        "detector_evidence": {"raw_detections": raw}}]}
    reports = {"pp.json": pp, "guide.json": guide}
    monkeypatch.setattr(probe, "read_private", lambda path: deepcopy(reports[Path(path).name]))
    class Dataset:
        def __init__(self, folder): pass
        def __enter__(self): return self
        def __exit__(self, *args): pass
    monkeypatch.setattr(probe, "DirectoryDataset", Dataset)
    bubble = {"bubble_id": "b1", "bbox": {"x": 100, "y": 100, "w": 60, "h": 160},
              "ja_ocr_truth": "テスト"}
    monkeypatch.setattr(probe, "audit", lambda _: ({}, [], [({"page_id": "p1"}, Image.new("RGB", (500, 600), "white"), [bubble])]))
    monkeypatch.setattr(probe, "dataset_fingerprint", lambda _: "fixture")
    args = SimpleNamespace(pp_reference=tmp_path/"artifacts/pp.json", block_reference=tmp_path/"artifacts/guide.json",
                           ocr_replay=None, output=tmp_path/"artifacts/result.json", folder="authored", plan_only=False)
    return args, reports, raw


def test_run_preserves_raw_guide_location_classes_and_scores(tmp_path, monkeypatch):
    args, reports, raw = run_fixture(tmp_path, monkeypatch)
    monkeypatch.setattr(probe, "MangaEngine", lambda *args: object())
    monkeypatch.setattr(probe, "recognize_regions", lambda image, changed, *args: [{**r, "ja": "テスト"} for r in changed])
    probe.run(args)
    result = json.loads(args.output.read_text(encoding="utf-8"))
    assert result["pages"][0]["guide_detector_evidence"]["raw_detections"] == raw
    assert result["guide_model"] == reports["guide.json"]["experimental_detector"]
    assert result["pages"][0]["merges"][0]["source_ids"] == ["r0", "r1"]
    region = result["pages"][0]["regions"][0]
    assert region["scope"]["memory"] is False and region["speaker"] == "unknown"
    assert region["overlay"] == "label" and "balloon" not in region


def test_run_rejects_union_replay_from_a_different_ocr_before_loading_model(tmp_path, monkeypatch):
    args, reports, _ = run_fixture(tmp_path, monkeypatch)
    args.ocr_replay = tmp_path / "artifacts/replay.json"
    reports["replay.json"] = {"input_fingerprint_sha256": "fixture", "layout_version": probe.VERSION,
                              "ocr": "different-ocr", "pages": []}
    monkeypatch.setattr(probe, "MangaEngine", lambda *args: pytest.fail("Replay must be rejected first"))
    with pytest.raises(ValueError, match="provenance"):
        probe.run(args)
    assert not args.output.exists()


def test_source_assembly_does_not_instantiate_ocr_and_keeps_every_source_record(tmp_path, monkeypatch):
    args, reports, raw = run_fixture(tmp_path, monkeypatch)
    args.preserve_source_ocr = True
    monkeypatch.setattr(probe, "MangaEngine", lambda *_: pytest.fail("Source assembly cannot load a model"))
    monkeypatch.setattr(probe, "recognize_regions", lambda *_: pytest.fail("Source assembly cannot infer new OCR"))
    probe.run(args)
    result = json.loads(args.output.read_text(encoding="utf-8"))
    assert result["source_ocr_preserved"] is True and result["fresh_ocr_new_crops_only"] is False
    assert result["layout_version"] == probe.SOURCE_PRESERVING_VERSION
    page = result["pages"][0]
    assert page["source_regions"] == reports["pp.json"]["pages"][0]["regions"]
    assert page["regions"][0]["sourceRegions"] == page["source_regions"]
    assert page["regions"][0]["ja"] == "not usednot used either"
    assert page["regions"][0]["scope"]["memory"] is False
    assert page["guide_detector_evidence"]["raw_detections"] == raw
    assert page["new_crops"] == 0 and page["new_crop_ocr_ms"] is None


@pytest.mark.parametrize("report_name,mutation", [
    ("pp.json", "missing"), ("pp.json", "duplicate"), ("guide.json", "missing"), ("guide.json", "duplicate"),
])
def test_incomplete_or_duplicated_evidence_rejected_before_ocr(tmp_path, monkeypatch, report_name, mutation):
    args, reports, _ = run_fixture(tmp_path, monkeypatch)
    if mutation == "missing": reports[report_name]["pages"] = []
    else: reports[report_name]["pages"] *= 2
    monkeypatch.setattr(probe, "MangaEngine", lambda *_: pytest.fail("Coverage must be checked first"))
    with pytest.raises(ValueError, match="every eligible page"):
        probe.run(args)
    assert not args.output.exists()


@pytest.mark.parametrize("mutation", ["lost", "duplicated", "changed", "reordered", "missing_text", "trusted", "choice", "review"])
def test_assembly_cannot_hide_source_losses_or_promote_trust(mutation):
    source = regions()
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [95, 95, 70, 170]}], (500, 600))
    if mutation == "lost": merges[0]["source_ids"] = ["r0"]
    elif mutation == "duplicated": merges[0]["source_ids"] = ["r0", "r0"]
    elif mutation == "changed": merges[0]["source_ids"] = ["r0", "missing"]
    elif mutation == "reordered": merges[0]["source_ids"].reverse()
    elif mutation == "missing_text": source[0].pop("ja")
    elif mutation == "trusted": merges[0]["erasure_permitted"] = True
    elif mutation == "choice": source[0]["scope"] = {"reason": "reader", "action": "translate"}
    elif mutation == "review": source[0]["reviewReasons"] = ["visual_punctuation_support"]
    with pytest.raises(ValueError):
        probe.preserve_source_ocr(proposed, merges, source)


def test_unmerged_record_and_source_anchor_are_retained_and_old_vi_is_not_concatenated():
    source = regions()
    for index, row in enumerate(source):
        row.update(vi="OLD_VI_FRAGMENT", expression={"sourceHash": "old"},
                   scope={"key": "original-anchor-" + str(index), "reason": "unclassified", "action": "translate"})
    source.append({"id": "other", "bbox": [350, 350, 40, 140], "order": 2, "ja": "OTHER", "overlay": "label",
                   "scope": {"key": "reader-anchor", "reason": "reader", "action": "defer"}})
    proposed, merges = guide_regions(source, [{"id": "b", "bbox": [95, 95, 70, 170]}], (500, 600))
    assembled = probe.preserve_source_ocr(proposed, merges, source)
    assert assembled[1] == source[2] and assembled[0]["sourceRegions"] == source[:2]
    assert "vi" not in assembled[0] and "expression" not in assembled[0]
    assert [r["scope"]["key"] for r in assembled[0]["sourceRegions"]] == ["original-anchor-0", "original-anchor-1"]
