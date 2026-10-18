"""The translation seam must not replace captured-source identities."""
from copy import deepcopy
import pytest

from manga_live.utterance_assembly import assemble_utterances
from manga_live.prompts import translation_prompt
from manga_live.text_scope import story_regions
from manga_live.render_cleanup import render_patch
from PIL import Image


def source():
    return [
        {"id": "right", "order": 0, "bbox": [140, 100, 40, 119], "ja": "「俺は人間に",
         "overlay": "label", "score": .9, "speaker": "unknown", "listener": "unknown",
         "scope": {"v": 1, "key": "source-right", "group": "source-right", "role": "unknown",
                   "action": "translate", "reason": "unclassified", "memory": True}},
        {"id": "middle", "order": 1, "bbox": [115, 101, 40, 154], "ja": "媚びる つもりは",
         "overlay": "label", "score": .8, "speaker": "unknown", "listener": "unknown",
         "scope": {"v": 1, "key": "source-middle", "group": "source-middle", "role": "unknown",
                   "action": "translate", "reason": "unclassified", "memory": True}},
        {"id": "left", "order": 3, "bbox": [90, 103, 40, 61], "ja": "な い…」",
         "overlay": "label", "score": .7, "speaker": "unknown", "listener": "unknown",
         "scope": {"v": 1, "key": "source-left", "group": "source-left", "role": "unknown",
                   "action": "translate", "reason": "unclassified", "memory": True}},
    ]


def guides():
    # A location class is NOT semantic importance or permission to erase.
    return [{"id": "guide", "bbox": [85, 95, 100, 170]}]


def test_one_complete_utterance_keeps_negation_quotes_spacing_and_every_source_anchor():
    rows = source()
    for row in rows:
        row.update(vi="STALE TRANSLATION", expression={"sourceHash": "stale"})
    before = deepcopy(rows)
    plan = assemble_utterances(rows, guides(), (500, 600))
    assert rows == before and plan["sources"] == before
    assert len(plan["utterances"]) == 1
    utterance = plan["utterances"][0]
    assert utterance["ja"] == "「俺は人間に媚びる つもりはな い…」"
    assert utterance["assembly"]["source_ids"] == ["right", "middle", "left"]
    assert utterance["assembly"]["source_keys"] == ["source-right", "source-middle", "source-left"]
    assert utterance["id"] not in {r["id"] for r in rows}
    assert "vi" not in utterance and utterance.get("expression", {}).get("sourceHash") != "stale"
    assert utterance["speaker"] == utterance["listener"] == "unknown"
    assert utterance["review"] is True and utterance["scope"]["memory"] is False
    assert utterance["assembly"]["erasure_permitted"] is False
    assert story_regions([utterance]) == []
    assert render_patch(Image.new("RGB", (500, 600)), utterance) is None
    prompt = translation_prompt(plan["utterances"], {})
    assert utterance["ja"] in prompt and "STALE TRANSLATION" not in prompt


def test_intervening_weak_mark_remains_its_own_exact_source_not_part_of_sentence():
    rows = source()
    mark = {**deepcopy(rows[1]), "id": "mark", "order": 2, "bbox": [91, 210, 12, 13],
            "ja": "．．．", "review": True, "reviewReasons": ["visual_punctuation_support"],
            "scope": {**rows[1]["scope"], "key": "source-mark", "group": "source-mark",
                      "reason": "visual_review", "memory": False}}
    rows.insert(2, mark)
    plan = assemble_utterances(rows, guides(), (500, 600))
    assert len(plan["utterances"]) == 2 and plan["utterances"][1] == mark
    assert plan["utterances"][0]["assembly"]["source_ids"] == ["right", "middle", "left"]
    assert plan["sources"] == rows


@pytest.mark.parametrize("change", [
    {"speaker": "reader-confirmed"}, {"listener": "reader-confirmed"},
    {"speakerBindingReview": True}, {"reviewReasons": ["layout_fragment"]},
    {"reviewReasons": ["visual_low_signal"]}, {"balloon": {"textBox": [140, 100, 40, 119]}},
    {"type": "sfx"},
])
def test_reader_identity_or_separation_evidence_vetoes_all_members_of_same_guide(change):
    rows = source()
    rows[1].update(change)
    plan = assemble_utterances(rows, guides(), (500, 600))
    # Do not jump over an excluded/confirmed middle column and join its sides.
    assert plan["utterances"] == rows


@pytest.mark.parametrize("change", [{"action": "defer"}, {"reason": "reader"}])
def test_reader_scope_choice_is_not_swallowed_or_bridged(change):
    rows = source()
    rows[1]["scope"].update(change)
    assert assemble_utterances(rows, guides(), (500, 600))["utterances"] == rows


@pytest.mark.parametrize("change", [
    {"scope": {"v": 1, "key": "excluded-note", "action": "defer", "reason": "reader"}},
    {"speaker": "reader-confirmed"},
])
def test_reader_boundary_vetoes_bridge_even_when_its_orientation_differs(change):
    rows = source()
    note = deepcopy(rows[1])
    note.update(id="note", order=2, bbox=[125, 150, 45, 12], ja="注意",
                scope={**note["scope"], "key":"source-note"})
    note.update(change)
    rows.insert(2, note)
    assert assemble_utterances(rows, guides(), (500, 600))["utterances"] == rows


@pytest.mark.parametrize("scope", [
    {}, {"action": "translate"}, {"key": "", "action": "translate"},
    {"key": "   ", "action": "translate"}, {"key": "source-middle"},
])
def test_incomplete_source_scope_never_becomes_an_assembly_anchor(scope):
    rows = source()
    rows[1]["scope"] = scope
    assert assemble_utterances(rows, guides(), (500, 600))["utterances"] == rows


def test_undocumented_review_cannot_be_promoted_to_supported_crop_partition():
    rows = source()
    rows[1]["review"] = True
    assert assemble_utterances(rows, guides(), (500, 600))["utterances"] == rows


@pytest.mark.parametrize("vertical", [True, False])
def test_source_order_must_also_follow_the_supported_geometric_reading_direction(vertical):
    rows = source()
    if vertical:
        rows.reverse()
    else:
        for row, box in zip(rows, ([100, 160, 120, 30], [100, 125, 150, 30], [100, 90, 70, 30])):
            row["bbox"] = box
    for index, row in enumerate(rows):
        row["order"] = index
    support = guides() if vertical else [{"id": "guide", "bbox": [90, 80, 170, 120]}]
    assert assemble_utterances(rows, support, (500, 600))["utterances"] == rows


def test_distinct_assemblies_never_share_a_scope_identity_or_churn_with_unrelated_sources():
    rows = source()
    other = deepcopy(rows)
    for index, row in enumerate(other):
        row.update(id="other-"+row["id"], order=4+index)
        row["bbox"][0] += 200
        row["scope"].update(key="other-"+row["scope"]["key"], group="other-"+row["scope"]["group"])
    support = [*guides(), {"id": "other-guide", "bbox": [285, 95, 100, 170]}]
    plan = assemble_utterances(rows+other, support, (500, 600))
    assert len(plan["assemblies"]) == 2
    assert len({row["scope"]["key"] for row in plan["utterances"]}) == 2
    before = plan["utterances"][0]
    other[-1]["ja"] += "！"
    after = assemble_utterances(rows+other, support, (500, 600))["utterances"][0]
    assert before["id"] == after["id"] and before["scope"] == after["scope"]


def test_no_guessed_anchor_for_legacy_source_and_no_fake_guide_confidence():
    rows = source()
    rows[1].pop("scope")
    assert assemble_utterances(rows, guides(), (500, 600))["utterances"] == rows
    rows = source()
    rows[1].pop("score")
    utterance = assemble_utterances(rows, guides(), (500, 600))["utterances"][0]
    assert "score" not in utterance


def test_unique_geometric_support_required_and_fewer_regions_is_not_the_objective():
    rows = source()
    assert assemble_utterances(rows, guides() * 2, (500, 600))["utterances"] == rows
    # Two similarly placed guides have distinct IDs: still ambiguous.
    overlapping = [*guides(), {"id": "other", "bbox": [80, 90, 110, 180]}]
    assert assemble_utterances(rows, overlapping, (500, 600))["utterances"] == rows
    assert assemble_utterances(rows, [], (500, 600))["utterances"] == rows


@pytest.mark.parametrize("boxes", [
    [[100, 100, 40, 160], [125, 180, 35, 160]],  # staggered starts
    [[100, 100, 40, 160], [125, 100, 150, 35]],  # mixed orientation
    [[100, 100, 40, 160], [170, 100, 40, 160]],  # distant blocks
    [[100, 100, 40, 160], [101, 100, 40, 160]],  # duplicate padding
])
def test_guide_cannot_override_separate_layout_or_duplicate_evidence(boxes):
    rows = source()[:2]
    for row, box in zip(rows, boxes):
        row["bbox"] = box
    support = [{"id": "g", "bbox": [90, 90, 210, 270]}]
    assert assemble_utterances(rows, support, (500, 600))["utterances"] == rows


def test_source_order_conflict_is_review_not_a_silent_reorder_of_the_story():
    rows = source()
    rows[0], rows[2] = rows[2], rows[0]
    assert assemble_utterances(rows, guides(), (500, 600))["utterances"] == rows


def test_assembly_identity_is_stable_but_changes_when_any_source_ocr_or_anchor_changes():
    rows = source()
    first = assemble_utterances(rows, guides(), (500, 600))
    assert first == assemble_utterances(deepcopy(rows), deepcopy(guides()), (500, 600))
    rows[2]["ja"] += "！"
    second = assemble_utterances(rows, guides(), (500, 600))
    assert first["source_fingerprint"] != second["source_fingerprint"]
    assert first["utterances"][0]["id"] != second["utterances"][0]["id"]
    rows[2]["scope"]["key"] = "different-source"
    assert second["utterances"][0]["id"] != assemble_utterances(rows, guides(), (500, 600))["utterances"][0]["id"]


@pytest.mark.parametrize("mutation", ["duplicate_id", "duplicate_anchor", "bad_box", "nan", "boolean", "bad_text", "too_many"])
def test_invalid_source_is_rejected_before_any_translation(mutation):
    rows = source()
    if mutation == "duplicate_id": rows[1]["id"] = rows[0]["id"]
    elif mutation == "duplicate_anchor": rows[1]["scope"]["key"] = rows[0]["scope"]["key"]
    elif mutation == "bad_box": rows[0]["bbox"][0] = -1
    elif mutation == "nan": rows[0]["bbox"][0] = float("nan")
    elif mutation == "boolean": rows[0]["bbox"][0] = True
    elif mutation == "bad_text": rows[0]["ja"] = 1
    elif mutation == "too_many": rows *= 22
    with pytest.raises(ValueError): assemble_utterances(rows, guides(), (500, 600))
