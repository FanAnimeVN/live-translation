"""Production adapter contracts, no credentials or paid requests."""
import threading
from types import SimpleNamespace
import pytest
from manga_live.cloud_models import model_choices,openrouter_request,gemini_thinking,OPENROUTER_DEFAULT
from manga_live.config import Config
from manga_live.prompts import translation_schema
from manga_live.providers import Translator
from manga_live.errors import AppError


def test_strict_candidate_schema_does_not_mutate_the_shared_schema():
    schema=translation_schema(["a","b"])
    body=openrouter_request(OPENROUTER_DEFAULT,"source",schema)
    strict=body["response_format"]["json_schema"]
    assert strict["strict"] is True
    assert strict["schema"]["required"]==["items","terms"]
    assert schema["required"]==["items"]
    assert strict["schema"]["properties"]["items"]["maxItems"]==2
    assert "models" not in body and "tools" not in body
    assert body["provider"]["data_collection"]=="deny" and body["provider"]["require_parameters"]


def test_haiku_has_no_incompatible_sampling_and_custom_keeps_explicit_id():
    haiku=openrouter_request("anthropic/claude-haiku-5.5","source",translation_schema(["a"]))
    assert not {"temperature","top_p","top_k"}.intersection(haiku)
    assert haiku["reasoning"]=={"enabled":False}
    custom=openrouter_request("custom/unknown","source",translation_schema(["a"]))
    assert custom["model"]=="custom/unknown" and custom["response_format"]["type"]=="json_object"
    assert "reasoning" not in custom  # Do not guess support for arbitrary IDs.


@pytest.mark.parametrize("model,effort",[("google/gemini-3.5-flash-lite","minimal"),("google/gemini-3.8-flash","low")])
def test_mandatory_gemini_reasoning_is_minimized_not_claimed_disabled(model,effort):
    body=openrouter_request(model,"source",translation_schema(["a"]))
    assert body["reasoning"]=={"effort":effort,"exclude":True}
    assert gemini_thinking(model.removeprefix("google/"))["thinkingLevel"]==effort


def test_new_profile_is_offline_and_existing_saved_preferences_are_not_migrated(tmp_path):
    config=Config(tmp_path)
    assert config.values["mode"]=="offline" and config.values["cloudConsent"] is False
    config.update({"mode":"byok","provider":"deepseek","deepseekModel":"reader-custom","cloudConsent":True})
    reopened=Config(tmp_path)
    assert reopened.values["provider"]=="deepseek" and reopened.values["deepseekModel"]=="reader-custom"
    # Reading model choices never loads a key, calls a provider or changes config.
    models=model_choices();models[0]["id"]="changed"
    assert model_choices()[0]["id"]==OPENROUTER_DEFAULT


def cloud_translator(provider,model):
    translator=Translator.__new__(Translator)
    translator.config=SimpleNamespace(values={"mode":"byok","cloudConsent":True,"provider":provider,provider+"Model":model})
    translator.vault=SimpleNamespace(get=lambda provider:"fake-only-not-a-secret")
    translator.signature=lambda:"test-cloud"
    return translator


def test_gemini_thought_parts_are_not_dialogue(monkeypatch):
    import manga_live.providers as providers
    captured=[]
    def fake(url,body,*a,**kw):
        captured.append(body)
        return {"candidates":[{"finishReason":"STOP","content":{"parts":[{"thought":True,"text":"hidden"},
            {"text":'{"items":[{"id":"a","vi":"Xin chào.","ambiguous":true}]}'}]}}]}
    monkeypatch.setattr(providers,"post_json",fake)
    translator=cloud_translator("gemini","gemini-3.8-flash")
    items,_=translator.translate([{"id":"a","ja":"こんにちは。"}],{},threading.Event())
    assert items[0]["vi"]=="Xin chào."
    assert captured[0]["generationConfig"]["thinkingConfig"]=={"thinkingLevel":"low","includeThoughts":False}


@pytest.mark.parametrize("provider,model,response,error",[
    ("deepseek","deepseek-flash",{"choices":[{"finish_reason":"length","message":{"content":"{}"}}]},"TRUNCATED"),
    ("openrouter",OPENROUTER_DEFAULT,{"choices":[{"finish_reason":"content_filter","message":{"content":"{}"}}]},"REFUSED"),
    ("gemini","gemini-3.5-flash-lite",{"candidates":[{"finishReason":"MAX_TOKENS","content":{"parts":[]}}]},"TRUNCATED"),
])
def test_truncation_and_refusal_do_not_trigger_a_paid_repair(monkeypatch,provider,model,response,error):
    import manga_live.providers as providers
    calls=[]
    def fake(*a,**kw):calls.append(1);return response
    monkeypatch.setattr(providers,"post_json",fake)
    with pytest.raises(AppError) as exc:
        cloud_translator(provider,model).translate([{"id":"a","ja":"こんにちは。"}],{},threading.Event())
    assert exc.value.code==error and len(calls)==1
