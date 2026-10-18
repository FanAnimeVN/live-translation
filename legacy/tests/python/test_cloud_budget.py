"""Pure budget/routing checks; never credentials or requests."""
import importlib.util
from pathlib import Path

import pytest

spec=importlib.util.spec_from_file_location("qa_cloud_budget",Path(__file__).resolve().parents[2]/"scripts/benchmark_cloud.py")
cloud=importlib.util.module_from_spec(spec);spec.loader.exec_module(cloud)


def test_budget_uses_route_ceiling_and_reserves_repair():
    catalogue={"cheap":{"pricing":{"prompt":"0.000000045","completion":"0.000000891"}}}
    cost,caps=cloud.budget_plan(["cheap"],catalogue,1)
    assert caps=={"cheap":{"prompt":0.30,"completion":1.20,"request":0}}
    assert 0<cost<0.10
    assert cloud.budget_plan(["cheap"],catalogue,2)[0]==pytest.approx(cost*2)


def test_price_cap_keeps_privacy_controls_and_does_not_mutate_body():
    original={"model":"cheap","max_tokens":900,"provider":{"data_collection":"deny","require_parameters":True,"sort":"latency"}}
    caps={"cheap":{"prompt":0.30,"completion":1.20,"request":0}}
    body=cloud.bounded_request(original,caps)
    assert body["max_tokens"]==700 and original["max_tokens"]==900
    assert body["provider"]["data_collection"]=="deny" and body["provider"]["require_parameters"] is True
    assert body["provider"]["max_price"]==caps["cheap"]
    assert "max_price" not in original["provider"]


def test_bounded_request_accepts_narrow_explicit_completion_ceiling():
    body=cloud.bounded_request({"model":"cheap","messages":[]},
        {"cheap":{"prompt":0.30,"completion":1.20,"request":0}},max_tokens=320)
    assert body["max_tokens"]==320
    with pytest.raises(ValueError): cloud.bounded_request({"model":"cheap"},
        {"cheap":{"prompt":0.30,"completion":1.20,"request":0}},max_tokens=701)


@pytest.mark.parametrize("rate",["nan","inf","-0.1"])
def test_bad_pricing_never_authorizes_requests(rate):
    with pytest.raises(ValueError):cloud.budget_plan(["bad"],{"bad":{"pricing":{"prompt":rate,"completion":"0"}}},1)


def test_reservation_stops_before_request_even_if_failed_attempt_returned_no_usage():
    ledger=cloud.BudgetLedger(0.003)
    body=cloud.bounded_request({"model":"cheap","messages":[{"role":"user","content":"hello"}]},
        {"cheap":{"prompt":0.30,"completion":1.20,"request":0}})
    amount=ledger.reserve(body)
    assert amount>0
    for _ in range(10):
        if ledger.reserved+amount>ledger.limit:break
        ledger.reserve(body)
    previous=ledger.calls
    with pytest.raises(cloud.AppError) as error:ledger.reserve(body)
    assert error.value.code=="TEST_BUDGET" and ledger.calls==previous and ledger.reserved<=ledger.limit


def test_rotation_keeps_every_group_and_reverses_second_pass():
    cases=cloud.cases()[:2]
    runs=list(cloud.ordered_runs(["a","b","c"],cases,2))
    assert len(runs)==12
    assert [model for model,repeat,case in runs[:6]]==["a","b","c","b","c","a"]
    assert [model for model,repeat,case in runs[6:]]==["c","b","a","a","c","b"]


def test_locked_terms_in_cloud_benchmark_use_production_memory_format():
    case=next(case for case in cloud.cases() if case["name"]=="fantasy_terms")
    assert len(cloud.constraints(case["context"],case["regions"]))==2


def test_narrow_voice_check_detects_stretched_toi_but_is_not_general_scoring():
    assert not all(cloud.narrow_checks("expression_voice",[{"id":"a","vi":"Tô-iii!"},{"id":"b","vi":"Đ-đợi…!"}]).values())
    assert all(cloud.narrow_checks("expression_voice",[{"id":"a","vi":"Eeem!"},{"id":"b","vi":"Đ-đợi…!"}]).values())


def test_text_benchmark_retains_billed_invalid_envelope_and_never_replays(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    model = cloud.MODELS[0]
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(json.dumps({"data": [{"id": model,
        "pricing": {"prompt": ".0000001", "completion": ".0000005"}}]}), encoding="utf-8")
    class Vault:
        def __init__(self, profile): pass
        def get(self, provider): return "fake-only-not-a-secret"
    monkeypatch.setattr(cloud, "Secrets", Vault)
    calls = []
    def response(*args, **kwargs):
        calls.append(1)
        return {"id": "gen-text-invalid-fixture", "usage": {"cost": .0002}, "choices": []}
    monkeypatch.setattr(cloud.providers, "post_json", response)
    cloud.run(SimpleNamespace(catalogue=str(catalogue), cases=["ordinary_delivery"], models=[model],
        budget=.05, repeats=1, plan_only=False, prompt_key=False, stdin_key=False,
        vault_profile="test-only", workdir=str(tmp_path / "run"), capture_output=False))
    report = json.loads((tmp_path / "run/cloud-benchmark.json").read_text(encoding="utf-8"))
    assert calls == [1]
    assert report["attempts"][0]["generation_id"] == "gen-text-invalid-fixture"
    assert report["attempts"][0]["reported_cost_usd"] == .0002
    assert report["rows"][0]["ok"] is False
    assert "fake-only-not-a-secret" not in json.dumps(report)


@pytest.mark.parametrize("outcome", ["network", "duplicate"])
def test_unresolved_attempt_stops_later_benchmark_groups_without_releasing_reservations(tmp_path, monkeypatch, outcome):
    import json
    from types import SimpleNamespace
    model = cloud.MODELS[0]
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(json.dumps({"data": [{"id": model,
        "pricing": {"prompt": ".0000001", "completion": ".0000005"}}]}), encoding="utf-8")
    monkeypatch.setattr(cloud, "Secrets", lambda _: SimpleNamespace(get=lambda _: "fake-key-test-only"))
    calls = []
    def response(*args, **kwargs):
        calls.append(1)
        if outcome == "network": raise cloud.AppError("NETWORK", "Fixture transport failed")
        return {"id": "gen-repeated-fixture", "usage": {"cost": .0002},
            "choices": [{"finish_reason": "stop", "message": {"content": json.dumps({"items": [
                {"id": "a", "vi": "Đã mua bánh ở siêu thị.", "ambiguous": True},
                {"id": "b", "vi": "Để hỏi mẹ xem.", "ambiguous": True}]})}}]}
    monkeypatch.setattr(cloud.providers, "post_json", response)
    cloud.run(SimpleNamespace(catalogue=str(catalogue), cases=["ordinary_delivery"], models=[model],
        budget=.05, repeats=3, plan_only=False, prompt_key=False, stdin_key=False,
        vault_profile="test-only", workdir=str(tmp_path / "run"), capture_output=False))
    report = json.loads((tmp_path / "run/cloud-benchmark.json").read_text(encoding="utf-8"))
    assert len(calls) == (1 if outcome == "network" else 2)
    assert report["reserved_usd"] > 0
    assert report["reported_cost_usd"] == (None if outcome == "network" else .0002)


def test_existing_attempt_report_is_never_overwritten_or_replayed(tmp_path, monkeypatch):
    import json
    from types import SimpleNamespace
    model = cloud.MODELS[0]
    catalogue = tmp_path / "catalogue.json"
    catalogue.write_text(json.dumps({"data": [{"id": model,
        "pricing": {"prompt": ".0000001", "completion": ".0000005"}}]}), encoding="utf-8")
    output = tmp_path / "run"
    output.mkdir()
    evidence = output / "cloud-benchmark.json"
    evidence.write_text('{"known":"untouched"}', encoding="utf-8")
    monkeypatch.setattr(cloud, "Secrets", lambda _: pytest.fail("Refuse before credential access"))
    with pytest.raises(ValueError, match="existing|overwrite|new"):
        cloud.run(SimpleNamespace(catalogue=str(catalogue), cases=["ordinary_delivery"], models=[model],
            budget=.05, repeats=1, plan_only=False, prompt_key=False, stdin_key=False,
            vault_profile="test-only", workdir=str(output), capture_output=False))
    assert evidence.read_text(encoding="utf-8") == '{"known":"untouched"}'
