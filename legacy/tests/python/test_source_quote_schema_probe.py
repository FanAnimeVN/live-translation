"""The local decoder experiment must not rewrite source or reject locked text."""
from copy import deepcopy
from pathlib import Path
import re
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from benchmark_mt2_templates import source_quote_schema, prompt_for
from manga_live.prompts import compact_schema
from manga_live.terminology import term_record
import json


def pattern(source, context=None):
    return source_quote_schema([{"id":"r", "ja":source}], context or {})["properties"]["r"].get("pattern")


def test_schema_experiment_changes_neither_source_prompt_nor_baseline_schema():
    rows = [{"id":"r", "ja":"「姉ちゃん、まだ帰らないの？"}]
    before = deepcopy(rows)
    assert prompt_for("current", rows, {}) == prompt_for("source-quote-schema", rows, {})
    schema = source_quote_schema(rows, {})
    assert rows == before and schema["additionalProperties"] is False
    assert compact_schema(["r"])["properties"]["r"] == {"type":"string"}


@pytest.mark.parametrize("value", ["「Nee-chan, vẫn chưa về à?", "“Nee-chan, vẫn chưa về à?"])
def test_open_source_quote_kept_without_completing_it(value):
    assert re.fullmatch(pattern("「姉ちゃん、まだ帰らないの？"), value)
    assert not re.fullmatch(pattern("「姉ちゃん、まだ帰らないの？"), value+"”")


@pytest.mark.parametrize("source", ["「姉ちゃん」", "『物語』", '"見ろ"'])
def test_full_genuine_quote_is_not_restricted(source):
    assert pattern(source) is None


def test_reader_locked_quote_has_precedence_over_constraint_candidate():
    context = {"glossary":[{"key":"skill", "confirmed":1,
        "value":json.dumps(term_record("skill","skill","結界",'“Kết Giới”'),ensure_ascii=False)}]}
    assert re.fullmatch(pattern("「結界を使う。", context), '“Dùng “Kết Giới”.')


def test_plain_quote_candidate_does_not_forbid_pauses_stutters_honorifics_or_spacing():
    assert re.fullmatch(pattern("「待って！"), "“Đ-đợi   nee-chan…!")


@pytest.mark.parametrize("source", [
    "待って！", "帰る。」", "「『物語』を読んだ。", "「「聞いて。", '"聞いて。',
])
def test_uncertain_nested_closing_only_or_unquoted_source_is_unchanged(source):
    assert pattern(source) is None


@pytest.mark.parametrize("target", [
    '“Nói là "đợi", nhé.', '“Dòng một.\nDòng hai.', r'“Kiểm tra C:\new\file.',
])
def test_runtime_pattern_accepts_legally_serialized_quotes_newlines_and_paths(target):
    # llama.cpp applies the regex to the encoded string interior. Never allow
    # its pattern branch to bypass JSON escaping (unlike a bare negated class).
    encoded = json.dumps(target, ensure_ascii=False)[1:-1]
    assert re.fullmatch(pattern("「待って。"), encoded)


@pytest.mark.parametrize("encoded", [
    '“Xin "chào".', '“Xin\nchào.', r'“Xin\u201D', r'“Xin\q', '“Xin”',
])
def test_runtime_pattern_rejects_invalid_json_or_unicode_escape_quote_bypass(encoded):
    assert not re.fullmatch(pattern("「待って。"), encoded)
