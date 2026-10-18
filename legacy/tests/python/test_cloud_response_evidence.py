"""Provider-envelope boundary only; no paid calls, credentials or story data."""
from copy import deepcopy
import json
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from cloud_response_evidence import capture_response, response_evidence, reported_cost_total, transport_failure_evidence


def test_capture_persists_allowlisted_billing_before_caller_validates_model_content():
    attempt = {"reserved_usd": .01, "state": "attempted"}
    snapshots = []
    capture_response(attempt, {"id": "gen-fixture-1", "usage": {"cost": .0002, "prompt_tokens": 8,
        "prompt": "must not persist", "prompt_tokens_details": {"cached_tokens": 4, "text": "private"}},
        "choices": [{"finish_reason": "stop", "message": {"content": "unvalidated text"}}],
        "api_key": "not-a-real-key"}, lambda: snapshots.append(deepcopy(attempt)), set())
    assert snapshots[0]["generation_id"] == "gen-fixture-1"
    assert snapshots[0]["billing_state"] == "reported"
    assert snapshots[0]["usage"] == {"cost": .0002, "prompt_tokens": 8,
                                    "prompt_tokens_details": {"cached_tokens": 4}}
    assert "private" not in json.dumps(snapshots) and "unvalidated text" not in json.dumps(snapshots)
    assert "not-a-real-key" not in json.dumps(snapshots)


def test_duplicate_generation_remains_reserved_and_is_not_double_counted_as_a_charge():
    attempts, seen = [], set()
    for _ in range(2):
        attempt = {"reserved_usd": .01, "state": "attempted"}
        attempts.append(attempt)
        capture_response(attempt, {"id": "gen-fixture-1", "usage": {"cost": .0002}}, lambda: None, seen)
    assert attempts[1]["billing_state"] == "duplicate_generation_id"
    assert sum(a["reserved_usd"] for a in attempts) == .02
    assert reported_cost_total(attempts) == .0002


@pytest.mark.parametrize("cost", [None, "0.001", True, float("nan"), float("inf"), -1])
def test_invalid_or_missing_cost_never_becomes_zero_charge(cost):
    attempt = {"reserved_usd": .01}
    capture_response(attempt, {"id": "gen-fixture-2", "usage": {"cost": cost}}, lambda: None, set())
    assert attempt["reported_cost_usd"] is None
    assert attempt["billing_state"] == "missing_cost"
    assert attempt["reserved_usd"] == .01


@pytest.mark.parametrize("response", [None, [], {"usage": []}, {"id": "gen-bad\nidentity", "usage": {"cost": 0}}])
def test_malformed_envelope_or_id_has_no_attributed_charge(response):
    assert response_evidence(response)["generation_id"] is None


def test_extreme_reported_charge_is_retained_as_over_budget_not_lost_to_float_overflow():
    attempt = {"reserved_usd": .01}
    capture_response(attempt, {"id": "gen-extreme-charge", "usage": {"cost": 10**400}}, lambda: None, set())
    assert attempt["generation_id"] == "gen-extreme-charge"
    assert attempt["billing_state"] == "cost_exceeds_reservation"
    assert reported_cost_total([attempt]) is None


def test_numeric_http_evidence_is_not_guessed_from_messages_or_network_errors():
    from urllib.error import URLError
    assert transport_failure_evidence(ValueError("HTTP 404 private text")) == {}
    assert transport_failure_evidence(URLError("HTTP 503 private text")) == {}


@pytest.mark.parametrize("status", [True, "404", 399, 600])
def test_invalid_http_status_never_enters_evidence(status):
    from urllib.error import HTTPError
    assert transport_failure_evidence(HTTPError("private-url", status, "private", {}, None)) == {}
