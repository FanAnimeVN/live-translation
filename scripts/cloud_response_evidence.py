"""Allowlisted billing evidence for private QA, never completion/prompt logging.

This only captures returned metadata. It does not reconcile reservations,
authorize requests, fetch generation records or establish billing finality.
"""
import math
import re
from urllib.error import HTTPError


def transport_failure_evidence(error):
    """Only an actual transport exception establishes a numeric HTTP status.

    post_json wraps HTTPError in AppError. Inspect that immediate cause/context,
    never parse a message, read the response body or persist request details.
    This is diagnostic evidence, not a zero-charge or automatic-retry verdict.
    """
    for cause in (error, error.__cause__, error.__context__):
        if isinstance(cause, HTTPError) and type(cause.code) is int and 400 <= cause.code <= 599:
            return {"http_status": cause.code}
    return {}


def valid_charge(value):
    return (type(value) is int and value >= 0) or (type(value) is float and math.isfinite(value) and value >= 0)


def response_evidence(response):
    envelope = response if isinstance(response, dict) else {}
    identity = envelope.get("id")
    identity = identity if isinstance(identity, str) and re.fullmatch(r"gen-[A-Za-z0-9_-]{1,180}", identity) else None
    supplied = envelope.get("usage")
    supplied = supplied if isinstance(supplied, dict) else {}
    usage = {}
    cost = supplied.get("cost")
    cost = cost if valid_charge(cost) else None
    if cost is not None:
        usage["cost"] = cost
    for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
        value = supplied.get(key)
        if type(value) is int and 0 <= value <= 10**12:
            usage[key] = value
    for key, fields in (("prompt_tokens_details", ("cached_tokens", "cache_write_tokens", "audio_tokens")),
                        ("completion_tokens_details", ("reasoning_tokens", "audio_tokens",
                                                       "accepted_prediction_tokens", "rejected_prediction_tokens"))):
        details = supplied.get(key)
        if isinstance(details, dict):
            clean = {name: details[name] for name in fields
                     if type(details.get(name)) is int and 0 <= details[name] <= 10**12}
            if clean:
                usage[key] = clean
    choices = envelope.get("choices")
    choice = choices[0] if isinstance(choices, list) and choices and isinstance(choices[0], dict) else {}
    reason = choice.get("finish_reason")
    if reason not in ("stop", "length", "tool_calls", "content_filter", "error", "function_call"):
        reason = None
    provider = envelope.get("provider")
    if not isinstance(provider, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 ._:/()\-]{0,95}", provider):
        provider = None
    return {"generation_id": identity, "provider": provider, "usage": usage,
            "reported_cost_usd": cost, "finish_reason": reason}


def capture_response(attempt, response, persist, seen_ids):
    evidence = response_evidence(response)
    identity, cost = evidence["generation_id"], evidence["reported_cost_usd"]
    if identity is None:
        status = "missing_generation_id"
    elif identity in seen_ids:
        status = "duplicate_generation_id"
    elif cost is None:
        status = "missing_cost"
    elif cost > attempt["reserved_usd"]:
        status = "cost_exceeds_reservation"
    else:
        status = "reported"
    if identity is not None:
        seen_ids.add(identity)
    attempt.update(state="response", billing_state=status, **evidence)
    persist()  # Before any caller reads choices/content or starts another attempt.


def reported_cost_total(attempts):
    """Returned charges only, not a settled bill or authority to release holds."""
    costs = {}
    for index, attempt in enumerate(attempts):
        cost = attempt.get("reported_cost_usd")
        if not valid_charge(cost):
            return None
        key = attempt.get("generation_id") or ("unattributed", index)
        costs[key] = max(costs.get(key, 0), cost)
    try:
        total = math.fsum(costs.values())
    except OverflowError:
        return None
    return total if math.isfinite(total) else None
