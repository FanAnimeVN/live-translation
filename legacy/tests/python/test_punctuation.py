"""Preserve source meaning and catch framing, not arbitrary punctuation."""
import pytest
from manga_live.punctuation import output_punctuation_issues,quote_imbalanced
from manga_live.prompts import translation_prompt,compact_prompt,focused_compact_prompt
from manga_live.validation import parse_model_json


@pytest.mark.parametrize("text",["…!?","!?",";",",","……","Đ-đợi đã…",'Gọi là “người hùng” nhé.',"'Tis a name."])
def test_punctuation_only_and_inner_quotation_are_not_framing_errors(text):
    assert output_punctuation_issues("……！？",text)==[]


@pytest.mark.parametrize("quoted",['“Đừng đi.”',"「Đừng đi.」","『Đừng đi.』",'"Đừng đi."',"«Đừng đi.»","＂Đừng đi.＂"])
def test_complete_source_quotation_can_use_an_equivalent_target_style(quoted):
    assert output_punctuation_issues("「行かないで。」",quoted)==[]
    assert output_punctuation_issues("行かないで。",quoted)==["added_outer_quotes"]


def test_trailing_quote_comma_matches_source_not_a_blanket_punctuation_strip():
    assert output_punctuation_issues("「はい」、",'“Vâng”,')==[]
    assert output_punctuation_issues("「はい」",'“Vâng”,')==["trailing_serialization_punctuation"]
    assert output_punctuation_issues("はい",'“Vâng”,')==["added_outer_quotes","trailing_serialization_punctuation"]


def test_source_escape_and_locked_labels_are_preserved():
    assert output_punctuation_issues(r"\nと表示される。",r"Hiện chữ \n.")==[]
    assert output_punctuation_issues("星の剣",'“Kiếm Sao”',["“Kiếm Sao”"])==[]
    assert output_punctuation_issues("星の剣",'“Kiếm Sao”,',["“Kiếm Sao”"])==["added_outer_quotes","trailing_serialization_punctuation"]


@pytest.mark.parametrize("prompt",[translation_prompt,compact_prompt,focused_compact_prompt])
@pytest.mark.parametrize("repair",[True,False,[],[{"id":"r","reason":"unsupported_quote_completion"}]])
def test_every_prompt_has_source_aware_punctuation_rules_without_mutating_evidence(prompt,repair):
    regions=[{"id":"r","ja":"「明日は来なくてもいい。"}]
    value=prompt(regions,{"output_repair":repair})
    assert "extra quotation wrappers" in value and "incomplete quotation" in value
    assert regions==[{"id":"r","ja":"「明日は来なくてもいい。"}]


def test_source_imbalance_is_not_a_global_quote_deletion_rule():
    assert quote_imbalanced("「聞いて。")
    assert quote_imbalanced("聞いて。」")
    assert not quote_imbalanced("「聞いて。」")
    assert output_punctuation_issues("「聞いて。",'“Nghe này.')==[]
    assert output_punctuation_issues("聞いて。」",'Nghe này.”')==[]


def test_json_decoder_only_removes_reasoning_wrapper_outside_literal_dialogue():
    raw='{"items":[{"id":"r","vi":"Chuỗi <think>vẫn phải giữ</think> trong dữ liệu.","ambiguous":false}]}'
    assert parse_model_json(raw)["items"][0]["vi"]=="Chuỗi <think>vẫn phải giữ</think> trong dữ liệu."
    assert parse_model_json("<think>private reasoning</think>\n"+raw)==parse_model_json(raw)
