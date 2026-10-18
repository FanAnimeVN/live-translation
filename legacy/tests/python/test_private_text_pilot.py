from copy import deepcopy
from pathlib import Path
import sys
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/"scripts"))
from translate_private_evidence import checked_page, run, bounded_private_request, MODEL, EphemeralKey
from manga_live.errors import AppError
from types import SimpleNamespace


def source():
    return {"cloud": False, "input_fingerprint_sha256": "same", "pages": [{"page": "p",
        "regions": [{"id": "r", "bbox": [5, 6, 20, 30], "ja": "テスト", "order": 0,
            "scope": {"action": "translate"}}]}]}


def test_only_ocr_text_regions_used_not_the_reference_and_no_source_mutation():
    evidence = source(); before = deepcopy(evidence)
    evidence["pages"][0]["aligned"] = [{"reference": "DO NOT TRANSMIT GOLD"}]
    regions = checked_page(evidence, "same", "p", (80, 160))
    assert regions[0]["speaker"] == regions[0]["listener"] == "unknown"
    assert "reference" not in str(regions)
    regions[0]["ja"] = "different"
    assert evidence["pages"][0]["regions"] == before["pages"][0]["regions"]


def test_ephemeral_key_adapter_has_no_persistence_surface():
    key = EphemeralKey("sk-or-test-value")
    assert key.get("openrouter") == "sk-or-test-value"
    assert not hasattr(key, "set") and not hasattr(key, "delete")


@pytest.mark.parametrize("failure", ["fingerprint", "cloud", "duplicate", "translation", "defer", "bounds", "blank"])
def test_pilot_does_not_substitute_source_or_translate_incomplete_pages(failure):
    evidence = source(); r = evidence["pages"][0]["regions"][0]
    if failure == "fingerprint": evidence["input_fingerprint_sha256"] = "different"
    elif failure == "cloud": evidence["cloud"] = True
    elif failure == "duplicate": evidence["pages"][0]["regions"].append(deepcopy(r))
    elif failure == "translation": r["vi"] = "from gold"
    elif failure == "defer": r["scope"]["action"] = "defer"
    elif failure == "bounds": r["bbox"] = [75, 6, 20, 30]
    else: r["ja"] = ""
    with pytest.raises(ValueError): checked_page(evidence, "same", "p", (80, 160))


@pytest.mark.parametrize("consent,budget", [(False,.01), (True,.02), (True,0), (True,float("nan")), (True,True)])
def test_consent_and_hard_ceiling_checked_before_file_key_or_network_access(consent,budget):
    with pytest.raises(ValueError, match="consent and budget"):
        run(SimpleNamespace(consent=consent, budget=budget))


@pytest.mark.parametrize("field,value", [
    ("messages", [{"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:image/png;base64,AAA="}}]}]),
    ("messages", []), ("model", "different"), ("provider", {"data_collection": "allow"}),
    ("tools", [{"type": "function"}])])
def test_future_adapter_changes_cannot_upload_an_image_or_enable_tools(field,value):
    body = {"model": MODEL, "messages": [{"role": "user", "content": "authored text"}],
        "provider": {"data_collection": "deny"}}
    body[field] = value
    with pytest.raises(AppError) as error: bounded_private_request(body, {MODEL: {"prompt": .3, "completion": 1.2, "request": 0}})
    assert error.value.code == "TEST_PRIVACY"
