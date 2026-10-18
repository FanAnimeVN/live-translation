"""The frozen OCR harness must not confuse a failed engine with a pass."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from portable_ocr_smoke import ocr_request,assert_reused_ocr


class FixtureClient:
    def __init__(self, code="CONSENT", with_regions=True, stale=False):
        self.code,self.with_regions,self.stale=code,with_regions,stale
        self.uploads=[]
    def image(self, data, image_id):self.uploads.append((data,image_id))
    def call(self, op, params, events, event_payloads):
        assert op == "pipeline"
        if self.with_regions:
            event_payloads.append({"event":"regions","result":{
                "revision":"stale" if self.stale else params["revision"],
                "regions":[{"id":"r000","ja":"Author-created fixture"}]}})
        if self.code:raise RuntimeError(json.dumps({"code":self.code}))
        return {"regions":[]}


def test_ocr_smoke_requires_real_region_payload_before_expected_consent_gate():
    client=FixtureClient();result=ocr_request(client,"page",b"fixture bytes")
    assert client.uploads and result["regions"]
    assert result["expected_error"] == "CONSENT" and result["stopped_before_cloud"]


@pytest.mark.parametrize("client",[
    FixtureClient(code="ENGINE"),FixtureClient(with_regions=False),
    FixtureClient(stale=True),FixtureClient(code=None),
])
def test_missing_regions_stale_revision_or_other_errors_cannot_pass(client):
    with pytest.raises((AssertionError,RuntimeError)):
        ocr_request(client,"page",b"fixture bytes")


def test_retry_proof_requires_identical_ocr_regions_and_no_detection():
    original={"regions":[{"id":"r1","ja":"A","bbox":[1,2,3,4]},
                         {"id":"r2","ja":"B","bbox":[5,6,7,8]}],"stages":["detector","ocr"]}
    retry={**original,"stages":["ocr"]}
    assert_reused_ocr(original,retry)
    for invalid in ({**retry,"regions":retry["regions"][:1]},
                    {**retry,"regions":list(reversed(retry["regions"]))},
                    {**retry,"regions":[{**retry["regions"][0],"ja":"Different"},retry["regions"][1]]},
                    {**retry,"stages":["detector","ocr"]}):
        with pytest.raises(AssertionError):assert_reused_ocr(original,invalid)
