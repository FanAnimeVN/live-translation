"""A request for perfection must be a failing gate, not a report adjective."""
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location("strict_benchmark",Path(__file__).resolve().parents[2]/"scripts/benchmark.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def perfect():
    return {"audit":[],"counts":{"eligible_bubbles":1},"crop_count":1,
        "raw_results":[{"edits":0,"prediction":"テスト","reference":"テスト"}]}


def test_exact_gate_cannot_be_awarded_to_rounded_averages_or_incomplete_evidence():
    assert module.perfect_crop_gate(perfect())
    for patch in ({"crop_count":0},{"audit":[{"issue":"duplicate_image"}]},{"raw_results":[]},
        {"raw_results":[{"edits":1,"prediction":"テス卜","reference":"テスト"}]},
        {"counts":{"eligible_bubbles":2}}):
        assert not module.perfect_crop_gate({**perfect(),**patch,"cer":0,"exact_match":1})
