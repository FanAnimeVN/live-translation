"""No live requests, Vault access or private images in these tests."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import benchmark_cloud_ocr as pilot


def test_proposal_crop_uses_detector_pixels_and_never_transmits_reference_text():
    image = Image.new("RGB", (80, 80), "white")
    image.putpixel((8, 8), (11, 22, 33))
    members = [{"polygon": [[10, 10], [20, 10], [20, 35], [10, 35]], "score": .8}]
    region = {"id": "r004", "bbox": [8, 8, 15, 30], "sourceMembers": members,
              "ja": "PRIMARY-READING-NOT-FOR-VERIFIER", "order": 4}
    report = {"cloud": False, "fresh_inference": True, "input_fingerprint_sha256": "same",
              "pages": [{"page": "page", "regions": [region]}]}
    pages = [({"page_id": "page"}, image, [
        {"bubble_id": "gold", "bbox": {"x": 0, "y": 0, "w": 70, "h": 70},
         "ja_ocr_truth": "REFERENCE-NOT-FOR-VERIFIER"}])]
    groups, evidence = pilot.proposal_groups(report, pages, "same", ["page"], ["r004"])
    assert len(groups) == 1
    entry = groups[0][1][0]
    assert entry["image"].size == (15, 30)
    assert entry["image"].getpixel((0, 0)) == (11, 22, 33)
    assert entry["bbox"] == [8, 8, 15, 30]
    assert entry["source_members"] == members
    assert entry["truth"] is None
    body = pilot.vision.request(pilot.vision.MODELS[2], [(entry["id"], entry["image"])])
    instructions = " ".join(p["text"] for m in body["messages"] for p in m["content"] if p["type"] == "text")
    assert "REFERENCE-NOT-FOR-VERIFIER" not in instructions
    assert "PRIMARY-READING-NOT-FOR-VERIFIER" not in instructions
    assert evidence["selected_units"] == 1


def test_selected_reader_exclusion_remains_recorded_without_a_cloud_crop():
    image = Image.new("RGB", (80, 80))
    report = {"cloud": False, "fresh_inference": True, "input_fingerprint_sha256": "same",
              "pages": [{"page": "page", "regions": [
                  {"id": "r004", "readerExcluded": True}]}]}
    groups, evidence = pilot.proposal_groups(report, [({"page_id": "page"}, image, [])],
                                             "same", ["page"], ["r004"])
    assert groups == []
    assert evidence["reader_excluded"] == [{"page": "page", "id": "r004", "reason": "reader_excluded"}]


@pytest.mark.parametrize("finish", ["stop", "length"])
def test_single_proposal_plan_and_attempt_share_cap_without_persisting_pixels(tmp_path, monkeypatch, capsys, finish):
    from io import BytesIO
    image = Image.new("RGB", (80, 80), "white")
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    labels = [{"page_id": "page", "image_file": "source.png", "image_size": {"w": 80, "h": 80},
               "bubbles": [{"bubble_id": "gold", "bbox": {"x": 0, "y": 0, "w": 70, "h": 70},
                            "ja_ocr_truth": "REFERENCE-NOT-INPUT"}]}]
    class Dataset:
        values = {"source.png": buffer.getvalue(), "ground_truth_benchmark.json": json.dumps(labels).encode()}
        def __init__(self, _): pass
        def read(self, entry): return self.values[entry if isinstance(entry, str) else entry.filename]
        def getinfo(self, name): return SimpleNamespace(filename=name, file_size=len(self.values[name]))
        def __enter__(self): return self
        def __exit__(self, *_): return False
    fingerprint = pilot.dataset_fingerprint(Dataset(None))
    proposal = {"cloud": False, "fresh_inference": True, "input_fingerprint_sha256": fingerprint,
                "pages": [{"page": "page", "regions": [{"id": "r004", "bbox": [8, 8, 15, 30],
                    "sourceMembers": [{"polygon": [[10, 10], [20, 10], [20, 35], [10, 35]], "score": .8}]}]}]}
    artifact = tmp_path / "artifacts/proposal.json"
    artifact.parent.mkdir()
    artifact.write_text(json.dumps(proposal), encoding="utf-8")
    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    monkeypatch.setattr(pilot, "DirectoryDataset", Dataset)
    monkeypatch.setattr(pilot, "FINGERPRINT", fingerprint)
    model = pilot.vision.MODELS[2]
    catalogue = {"data": [{"id": model, "architecture": {"input_modalities": ["image", "text"]},
        "supported_parameters": ["response_format", "structured_outputs", "reasoning", "max_tokens"],
        "pricing": {"prompt": ".00000015", "completion": ".00000047"}}]}
    monkeypatch.setattr(pilot.urllib.request, "urlopen", lambda *a, **kw: BytesIO(json.dumps(catalogue).encode()))
    monkeypatch.setattr(pilot, "Secrets", lambda *a: pytest.fail("Plan cannot access Vault"))
    monkeypatch.setattr(pilot, "post_json", lambda *a, **kw: pytest.fail("Plan cannot infer"))
    destination = tmp_path / "artifacts/cloud-image-proposal-plan"
    monkeypatch.setattr(sys, "argv", ["benchmark_cloud_ocr.py", "--consent-images", "--source", "proposal-crops",
        "--proposals", str(artifact), "--pages", "page", "--region-ids", "r004", "--models", model,
        "--completion-tokens", "512", "--budget", ".0035", "--workdir", str(destination), "--plan-only"])
    pilot.main()
    plan = json.loads(capsys.readouterr().out)
    assert plan["requests"] == 1
    assert 0 < plan["reservation_plan_usd"] < .003571
    assert plan["output_caps"] == {model: 512}
    assert not destination.exists()
    calls = []
    def response(url, body, *args, **kwargs):
        calls.append(body)
        assert body["max_tokens"] == 512
        assert body["provider"]["zdr"] is True
        assert body["provider"]["allow_fallbacks"] is False
        text = " ".join(p["text"] for m in body["messages"] for p in m["content"] if p["type"] == "text")
        assert "REFERENCE-NOT-INPUT" not in text
        return {"id": "gen-proposal-fixture", "provider": "fixture", "usage": {"cost": .00001},
                "choices": [{"finish_reason": finish, "message": {"content": json.dumps({"items": [
                    {"id": "r004", "ja": "読んだ", "uncertain": False}]})}}]}
    monkeypatch.setattr(pilot, "Secrets", lambda *a: SimpleNamespace(get=lambda *a: "not-a-real-test-key"))
    monkeypatch.setattr(pilot, "post_json", response)
    monkeypatch.setattr(sys, "argv", sys.argv[:-1])  # execute same plan once, no implicit retry
    pilot.main()
    assert len(calls) == 1
    result = json.loads((destination / "report.json").read_text(encoding="utf-8"))
    assert result["reserved_usd"] == pytest.approx(plan["reservation_plan_usd"])
    assert result["rows"][0]["ok"] is (finish == "stop")
    assert result["attempts"][0]["reported_cost_usd"] == .00001
    assert result["rows"][0]["selected_sources"][0]["crop_box"] == [8, 8, 15, 30]
    assert result["rows"][0]["erasure_authority"] is False
    if finish == "stop":
        row = result["rows"][0]
        assert row["aligned"][0]["region_ids"] == ["r004"]
        assert row["erasure_authority"] is False
    else:
        assert result["rows"][0]["error"] == "VISION_INCOMPLETE"
        assert result["summary"][model]["cer"] is None
    serialized = json.dumps(result)
    assert "data:image" not in serialized and "not-a-real-test-key" not in serialized


def body():
    result = pilot.vision.request(pilot.vision.MODELS[0], [("a", Image.new("RGB", (10, 10)))])
    result["provider"]["max_price"] = {"prompt": .1, "completion": .5, "request": 0}
    return result


def test_image_budget_separates_base64_from_token_bound_and_keeps_failures():
    payload = body()
    budget = pilot.ImageBudget(.003)
    first = budget.reserve(payload, 1)
    assert first > .0016
    payload["messages"][0]["content"][-1]["image_url"]["url"] += "x" * 100000
    assert budget.amount(payload, 1) == first
    with pytest.raises(pilot.AppError): budget.reserve(payload, 1)
    assert budget.calls == 1 and budget.reserved == first


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -1, True, .26])
def test_invalid_image_budget_never_allows_network(value):
    with pytest.raises(ValueError): pilot.ImageBudget(value)


def test_consent_scope_and_private_output_required_before_network(tmp_path):
    args = SimpleNamespace(consent_images=False, budget=.01, models=[pilot.vision.MODELS[0]], workdir=str(tmp_path / "new"))
    with pytest.raises(ValueError): pilot.options(args)
    args.consent_images = True
    args.workdir = str(pilot.ROOT / "outside-artifacts-new")
    with pytest.raises(ValueError): pilot.options(args)  # outside artifacts


def test_unknown_image_fees_and_nonvision_catalog_rejected():
    model = pilot.vision.MODELS[0]
    entry = {"architecture": {"input_modalities": ["image", "text"]},
             "supported_parameters": ["response_format", "structured_outputs", "reasoning", "max_tokens"],
             "pricing": {"prompt": ".0000001", "completion": ".0000005"}}
    assert pilot.price_caps({model: entry}, model)["prompt"] == pytest.approx(.1)
    for patch in ({"image": ".001"}, {"request": ".01"}, {"prompt": "nan"}):
        with pytest.raises(ValueError): pilot.price_caps({model: {**entry, "pricing": {**entry["pricing"], **patch}}}, model)


def test_authored_blank_controls_do_not_need_private_data():
    groups = list(pilot.fixtures())
    assert [len(g[1]) for g in groups] == [4, 2, 1]
    assert all(r["truth"] == "" for r in groups[1][1])


def test_session_keeps_unknown_billed_failed_runs_in_cumulative_cap(tmp_path):
    for name, amount in (("cloud-image-aborted", .2), ("cloud-image-next", .2)):
        folder = tmp_path / name
        folder.mkdir()
        (folder / "report.json").write_text(json.dumps({"reserved_usd": amount, "reported_cost_usd": 0}), encoding="utf-8")
    assert pilot.session_reserved(tmp_path, .0673507) == pytest.approx(.4673507)
    with pytest.raises(pilot.AppError): pilot.session_reserved(tmp_path, .13)


def test_malformed_model_response_retains_generation_and_charge_before_ocr_validation(tmp_path, monkeypatch):
    from io import BytesIO
    model = pilot.vision.MODELS[0]
    catalogue = {"data": [{"id": model, "architecture": {"input_modalities": ["image", "text"]},
        "supported_parameters": ["response_format", "structured_outputs", "reasoning", "max_tokens"],
        "pricing": {"prompt": ".0000001", "completion": ".0000005"}}]}
    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    monkeypatch.setattr(pilot.urllib.request, "urlopen", lambda *a, **kw: BytesIO(json.dumps(catalogue).encode()))
    class Vault:
        def __init__(self, profile): pass
        def get(self, provider): return "test-not-a-real-key"
    monkeypatch.setattr(pilot, "Secrets", Vault)
    calls = []
    def response(*args, **kwargs):
        calls.append(1)
        return {"id": "gen-fixture-billed-invalid-output", "provider": "test-provider",
                "usage": {"cost": .0002, "prompt_tokens": 10}, "choices": []}
    monkeypatch.setattr(pilot, "post_json", response)
    destination = tmp_path / "artifacts/cloud-image-invalid-output"
    monkeypatch.setattr(sys, "argv", ["benchmark_cloud_ocr.py", "--consent-images", "--source", "authored",
        "--models", model, "--budget", ".01", "--limit", "1", "--workdir", str(destination)])
    pilot.main()
    report = json.loads((destination / "report.json").read_text(encoding="utf-8"))
    assert calls == [1]
    assert report["attempts"][0]["generation_id"] == "gen-fixture-billed-invalid-output"
    assert report["attempts"][0]["reported_cost_usd"] == .0002
    assert report["reserved_usd"] > .0002
    assert report["rows"][0]["ok"] is False
    assert "test-not-a-real-key" not in json.dumps(report)


@pytest.mark.parametrize("status", [404, 429, 503])
def test_actual_transport_failure_retains_only_numeric_http_status_and_never_retries(tmp_path, monkeypatch, status):
    from io import BytesIO
    import urllib.error
    model = pilot.vision.MODELS[0]
    catalogue = {"data": [{"id": model, "architecture": {"input_modalities": ["image", "text"]},
        "supported_parameters": ["response_format", "structured_outputs", "reasoning", "max_tokens"],
        "pricing": {"prompt": ".0000001", "completion": ".0000005"}}]}
    monkeypatch.setattr(pilot, "ROOT", tmp_path)
    monkeypatch.setattr(pilot.urllib.request, "urlopen", lambda *a, **kw: BytesIO(json.dumps(catalogue).encode()))
    monkeypatch.setattr(pilot, "Secrets", lambda *a: SimpleNamespace(get=lambda *a: "fake-transport-secret"))
    calls = []
    class Opener:
        def open(self, request, **kwargs):
            calls.append(1)
            raise urllib.error.HTTPError("https://provider.invalid/private-url", status,
                "private error message", {"private-header": "private-header-value"},
                BytesIO(b"private error response body"))
    # Exercise the production post_json wrapping, not a hand-created AppError.
    monkeypatch.setattr(pilot.urllib.request, "build_opener", lambda *a: Opener())
    destination = tmp_path / "artifacts/cloud-image-transport-error"
    monkeypatch.setattr(sys, "argv", ["benchmark_cloud_ocr.py", "--consent-images", "--source", "authored",
        "--models", model, "--budget", ".01", "--limit", "1", "--workdir", str(destination)])
    with pytest.raises(SystemExit, match="missing/unbounded billing evidence"):
        pilot.main()
    result = json.loads((destination / "report.json").read_text(encoding="utf-8"))
    assert calls == [1]
    assert result["attempts"][0]["http_status"] == status
    assert result["rows"][0]["http_status"] == status
    assert result["rows"][0]["ok"] is False
    assert result["aborted"] == "missing_or_unbounded_usage"
    assert result["reserved_usd"] > 0 and result["reported_cost_usd"] is None
    assert "summary" not in result  # No successful prediction, no claimed quality score.
    saved = json.dumps(result)
    for forbidden in ("fake-transport-secret", "private-url", "private error", "private-header", "data:image"):
        assert forbidden not in saved
