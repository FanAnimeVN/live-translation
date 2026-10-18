"""The benchmark itself must catch the concrete errors we have observed."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from semantic_regression import semantic_checks


def sibling_items(b="Em về trước đi. Lát chị sẽ tới.",c="Hiểu rồi. Em đợi nhé."):
    return [{"id":"a","vi":"Nee-chan, chị vẫn chưa về à?"},
            {"id":"b","vi":b},{"id":"c","vi":c}]


def test_correct_sibling_exchange_passes_known_error_guards():
    assert all(semantic_checks("siblings",sibling_items()).values())


@pytest.mark.parametrize("items",[
    sibling_items(b="Đã về trước rồi. Đi sau đó nhé."),
    sibling_items(c="Hiểu rồi. Đợi em nha."),
])
def test_sibling_guard_rejects_completed_request_and_reversed_waiter(items):
    assert not all(semantic_checks("siblings",items).values())


def test_sibling_guard_detects_wrong_self_in_older_speaker_second_clause():
    assert not all(semantic_checks("siblings",sibling_items(b="Hãy về trước đi. Em sẽ đến sau.")).values())


def test_scope_guard_does_not_mistake_refusal_for_inability():
    items=[{"id":"a","vi":"Không phải là không đi. Chỉ là giờ không thể đi."},
           {"id":"b","vi":"Mai không cần đến."},{"id":"c","vi":"Bị anh trai bắt đi."}]
    assert all(semantic_checks("scope",items).values())
    items[0]["vi"]="Không phải là không thể đi. Chỉ là giờ không thể đi."
    assert not all(semantic_checks("scope",items).values())


def test_sibling_guard_catches_first_clause_address_role_reversal_in_real_7b_output():
    items=sibling_items(b="Chị về trước nhé. Lát nữa chị sẽ đến.",c="Được rồi. Em sẽ đợi chị nhé.")
    checks=semantic_checks("siblings",items)
    assert checks["older_speaker_does_not_address_younger_as_chi"] is False
    assert not all(checks.values())
    assert semantic_checks("siblings",sibling_items(b="Em về trước nhé. Lát nữa chị sẽ đến."))[
        "older_speaker_does_not_address_younger_as_chi"]


@pytest.mark.parametrize("a,b,expected",[
    ("Nee-chan","Onii-chan",True),
    ("Chị nee-chan","Onii-chan",False),
    ("Nee-chan","Anh trai onii-chan",False),
])
def test_authored_cloud_pilot_checks_standalone_calls_without_redundant_titles(a,b,expected):
    from benchmark_cloud import narrow_checks
    assert all(narrow_checks("standalone_sibling_calls",[
        {"id":"a","vi":a},{"id":"b","vi":b}]).values()) is expected
