"""No credentials or live requests in these safety tests."""
import importlib.util
from pathlib import Path
import sys

import pytest

SCRIPTS=Path(__file__).resolve().parents[2]/"scripts"
sys.path.insert(0,str(SCRIPTS))
spec=importlib.util.spec_from_file_location("qa_cloud_entry",SCRIPTS/"qa_cloud_entry.py")
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def options():
    return {"qaCloud":{"consent":True,"model":"google/gemini-3.5-flash-lite","budgetUsd":.03,
        "prices":{"prompt":.30,"completion":2.5,"request":0}}}


def test_native_paid_qa_is_explicit_and_price_bounded():
    assert module.validated_options(options())[1]==.03
    for patch in ({"consent":False},{"model":"unknown/auto"},{"budgetUsd":1},
                  {"prices":{"prompt":.3,"completion":2.5,"request":.01}}):
        with pytest.raises(ValueError):module.validated_options({"qaCloud":{**options()["qaCloud"],**patch}})


def test_nonfinite_qa_budget_and_rates_never_authorize_inference():
    for value in (float("nan"),float("inf"),-1,True):
        for key in ("budgetUsd","prices"):
            patch={key:value if key=="budgetUsd" else {"prompt":value,"completion":1,"request":0}}
            with pytest.raises(ValueError):module.validated_options({"qaCloud":{**options()["qaCloud"],**patch}})


def test_paid_native_qa_rejects_images_and_tools_before_any_network_or_charge():
    module.require_text_only({"messages":[{"role":"user","content":"text-only authored dialogue"}]})
    for body in (
        {"messages":[{"role":"user","content":[{"type":"image_url","image_url":{"url":"data:image/png;base64,AAAA"}}]}]},
        {"messages":[{"role":"user","content":"data:image/png;base64,AAAA"}]},
        {"messages":[{"role":"user","content":"hello"}],"tools":[{"type":"web_search"}]},
        {"messages":[]},
        {"messages":[{"role":"user","content":"x"*100001}]},
    ):
        with pytest.raises(module.AppError):module.require_text_only(body)
