"""Diagnostic controls must not accidentally fix translations with gold text."""
import sys
from pathlib import Path
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from benchmark_mt2_templates import prompt_for, checks_for, run_condition


def test_plain_baseline_has_no_hidden_grammar_or_gold_answer():
    source = {"id": "r", "ja": "兄に行かせられた。"}
    prompt = prompt_for("official-plain", [source], {"gold": "bị anh trai bắt đi"})
    assert prompt.endswith(source["ja"])
    assert "Background" not in prompt and "bị anh trai" not in prompt
    assert "causative" not in prompt


def test_app_context_keeps_directed_roles_and_confirmed_address():
    import json
    context = {"characters": [{"kind": "relationship", "confirmed": 1,
        "value": json.dumps({"speaker": "younger", "listener": "older", "self": "em", "address": "chị"})}]}
    region = {"id": "r", "ja": "待ってる。", "speaker": "younger", "listener": "older"}
    prompt = prompt_for("app-context", [region], context)
    assert "Speaker: younger" in prompt and "Listener: older" in prompt
    assert 'uses "em" for self' in prompt and '"chị" for the listener' in prompt
    reversed_prompt = prompt_for("app-context", [{**region, "speaker": "older", "listener": "younger"}], context)
    assert 'uses "em" for self' not in reversed_prompt


def test_contrast_check_distinguishes_forced_permitted_and_requested():
    good = [{"id": "a", "vi": "Bị anh trai bắt đi."},
            {"id": "b", "vi": "Anh trai đã cho đi."},
            {"id": "c", "vi": "Anh trai nhờ đi."}]
    assert all(checks_for("causative_contrast", good).values())
    for index, wrong in ((0, "Được anh ấy dẫn đi."), (1, "Bị anh trai bắt đi."),
                         (2, "Bị anh trai buộc đi."), (2, "Tôi được yêu cầu đi với anh ấy.")):
        changed = [dict(r) for r in good]
        changed[index]["vi"] = wrong
        assert not all(checks_for("causative_contrast", changed).values())


def test_group_and_per_bubble_conditions_measure_call_count():
    import json
    class Worker:
        def generate(self, prompt, cancel, schema=None, max_tokens=900):
            if schema:
                return json.dumps({key: "Xin chào." for key in schema["required"]}), {"prompt_tokens": 20}
            return "Xin chào.", {"prompt_tokens": 20}
    case = {"name": "plain", "context": {}, "regions": [{"id": "a", "ja": "こんにちは。"}, {"id": "b", "ja": "こんばんは。"}]}
    grouped = run_condition(Worker(), "official-structured", case, threading.Event())
    single = run_condition(Worker(), "official-plain", case, threading.Event())
    assert grouped["calls"] == 1 and single["calls"] == 2
    assert grouped["usage"]["prompt_tokens"] == 20 and single["usage"]["prompt_tokens"] == 40
    assert single["group_ms"] >= single["first_item_ms"]
    assert not single["narrow_checks_passed"]  # No semantic checks != semantic success.
