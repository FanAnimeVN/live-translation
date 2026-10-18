"""Authored expression regressions at the production prompt/provider seams."""
import json
import threading
from types import SimpleNamespace

from manga_live.prompts import compact_prompt, translation_prompt
from manga_live.providers import Translator
import pytest
from manga_live.expression import bind_expression, source_cues, output_expression_issues, whole_spelling, spelled_text
from manga_live.prompts import focused_compact_prompt, PROMPT_VERSION
from manga_live.errors import AppError


def test_slow_segmented_source_gets_conditional_rhythm_guidance():
    regions=[{"id":"r","ja":"わ・た・し〜〜！"}]
    for prompt in (compact_prompt, translation_prompt, focused_compact_prompt):
        value=prompt(regions,{})
        assert "Expressive lettering" in value
        assert "segmented" in value and "elongated" in value
    assert "Expressive lettering" not in compact_prompt([{"id":"r","ja":"スーパーで買った。"}],{})


def test_model_flattened_rhythm_is_repaired_only_for_the_affected_id():
    translator=Translator.__new__(Translator)
    translator.config=SimpleNamespace(values={"mode":"offline"})
    translator.signature=lambda:"authored-expression-test"
    calls=[]
    class Worker:
        def generate(self,prompt,cancel,schema=None,max_tokens=900):
            calls.append(prompt)
            value={"a":"Xin chào.","b":"Tôi đây!"} if len(calls)==1 else {"b":"Tô-i… đââây!"}
            return json.dumps(value,ensure_ascii=False),{"prompt_tokens":10,"completion_tokens":5}
    translator.local=Worker()
    regions=[{"id":"a","ja":"こんにちは。"},{"id":"b","ja":"わ・た・し〜〜！"}]
    items,metrics=translator.translate(regions,{},threading.Event())
    assert items[1]["vi"]=="Tô-i… đââây!"
    assert len(calls)==2 and '"a":' not in calls[1]
    assert metrics["usage"]=={"prompt_tokens":20,"completion_tokens":10}


def test_whole_utterance_caps_are_preserved_without_another_model_call():
    translator=Translator.__new__(Translator);calls=[]
    def response(*args):
        calls.append(1)
        return [{"id":"r","vi":"Dừng lại!"}],{"translation_ms":1,"usage":{}}
    translator._translate=response
    items,metrics=translator.translate([{"id":"r","ja":"STOP!"}],{},threading.Event())
    assert items[0]["vi"]=="DỪNG LẠI!"
    assert len(calls)==1 and metrics["attempts"]==1


@pytest.mark.parametrize("source,cues",[
    ("わ・た・し〜〜！",["segmented","elongated"]),
    ("Wa-ta-shi",["segmented"]),
    ("I L O V E Y O U",["spelled","uppercase"]),
    ("Ｉ Ｌ Ｏ Ｖ Ｅ Ｙ Ｏ Ｕ",["spelled","uppercase"]),
    ("やめろーーー！",["elongated"]),
    ("いやあああ！",["elongated"]),
    ("わ、わたしは…",["paused","stutter"]),
    ("お風呂にする…？",["paused"]),
    ("W-Wait!",["stutter"]),
    ("STOP!",["uppercase"]),
])
def test_strong_printed_cues_are_detected(source,cues):
    assert source_cues(source)==cues


@pytest.mark.parametrize("source",[
    "スーパーで買った。","おかあさんに聞いて。","ア・ラ・カルト", "アル・ラ・ト",
    "ジャン・ピエール", "Kirito-kun", "one-on-one", "NASA", "HP", "A〜Z", "1〜3",
    "NASAの研究所", "先輩、ありがとう。", "わたし\nです。", "ごはん にする？",
])
def test_names_acronyms_long_vowels_and_physical_wraps_are_not_voice_acting(source):
    assert source_cues(source)==[]


def test_source_hash_and_version_are_rebound_after_ocr_edit_without_mutation():
    source={"id":"r","ja":"わ・た・し〜〜！","expression":{"v":0,"cues":["uppercase"]}}
    bound=bind_expression(source)
    assert bound["expression"]["v"]==1
    assert bound["expression"]["cues"]==["segmented","elongated"]
    assert len(bound["expression"]["sourceHash"])==64
    assert source["expression"]["v"]==0
    assert "expression" not in bind_expression({**bound,"ja":"普通の話です。"})
    edited=bind_expression({**bound,"ja":"まだ…？"})
    assert edited["expression"]["sourceHash"]!=bound["expression"]["sourceHash"]


@pytest.mark.parametrize("source,good,bad,reason",[
    ("わ・た・し", "Tô-i", "Tôi", "lost_source_segmentation"),
    ("彼はI L O V E Y O Uと言った", "Nói rằng E M   Y Ê U   A N H", "Nói rằng em yêu anh", "lost_source_segmentation"),
    ("待ってーーー！", "Đợợợi đã!", "Đợi đã!", "lost_source_elongation"),
    ("まだ…？", "Vẫn… chưa à?", "Vẫn chưa à?", "lost_source_pause"),
    ("わ、わたしは", "T-tôi thì", "Tôi thì", "lost_source_stutter"),
])
def test_guard_preserves_delivery_not_rigid_japanese_character_counts(source,good,bad,reason):
    assert output_expression_issues(source,good)==[]
    assert output_expression_issues(source,bad)==[reason]


def test_a_single_vietnamese_syllable_can_carry_slow_multi_syllable_source():
    assert output_expression_issues("あ・な・た〜〜？","Bạạạn?")==[]
    assert output_expression_issues("あ・な・た〜〜？","Bạn?")==["lost_source_segmentation","lost_source_elongation"]
    assert output_expression_issues("い、いや…！","Kh-không…!")==[]


@pytest.mark.parametrize("target",["Ê—ê!","Ơi…i!","Ơi...i!"])
def test_held_vowel_may_cross_a_printed_dash_or_pause_without_word_repetition(target):
    assert output_expression_issues("おーーい！",target)==[]
    assert "lost_source_elongation" in output_expression_issues("おーーい！","Ơi!")


def test_whole_unknown_second_person_does_not_invent_gender_or_family_address():
    from manga_live.linguistics import address_output_issues
    region={"id":"r","ja":"あ・な・た〜〜？"}
    assert address_output_issues({},[region],[{"id":"r","vi":"A・n・h〜〜?"}])==[
        {"id":"r","reason":"unconfirmed_expressive_address"}]
    assert address_output_issues({},[region],[{"id":"r","vi":"Bạạạn?"}])==[]
    context=expressive_voice_context("em","anh")
    known={**region,"speaker":"reader-younger","listener":"reader-older"}
    assert address_output_issues(context,[known],[{"id":"r","vi":"A・n・h〜〜?"}])==[]
    assert address_output_issues({},[{**region,"ja":"彼は『あ・な・た〜〜』と言った。"}],
        [{"id":"r","vi":"Cậu ấy nói: A・n・h〜〜?"}])==[]


def test_local_presentation_never_overflows_transport_or_truncates_meaning():
    from manga_live.expression import present_items
    with pytest.raises(AppError) as error:
        present_items([{"id":"r","ja":"I L O V E Y O U"}],[{"id":"r","vi":"manga"*1000}])
    assert error.value.code=="MODEL_OUTPUT"
    assert "vùng nhỏ hơn" not in error.value.message
    assert "nguyên bản được giữ lại" in error.value.message


def test_exact_reader_label_wins_even_if_it_intentionally_localizes_source_rhythm():
    assert output_expression_issues("わ・た・し","Tôi",["Tôi"])==[]


def test_whole_spelling_is_local_and_never_rewrites_a_partial_quoted_phrase():
    translator=Translator.__new__(Translator);calls=[]
    translator._translate=lambda *args:(calls.append(1) or [{"id":"r","vi":"Em yêu anh!"}],{"translation_ms":1,"usage":{}})
    regions=[{"id":"r","ja":"I L O V E Y O U!","speaker":"reader-younger","listener":"reader-older"}]
    items,metrics=translator.translate(regions,expressive_voice_context("em","anh"),threading.Event())
    assert items[0]["vi"]=="E M   Y Ê U   A N H!"
    assert len(calls)==1 and metrics["attempts"]==1
    assert not whole_spelling("彼はI L O V E Y O Uと言った")
    assert spelled_text("E M   Y Ê U   A N H!")=="E M   Y Ê U   A N H!"
    assert spelled_text("Em yêu Kirito-kun.")=="E m   y ê u   Kirito-kun."
    assert spelled_text("Em gọi Hội Sao.",["Hội Sao"])=="E m   g ọ i   Hội Sao."


@pytest.mark.parametrize("target", ["Anh yêu em", "Em yêu anh!", "A N H   Y Ê U   E M", "Yêu chị."])
def test_whole_spelled_english_does_not_invent_a_gendered_couple(target):
    from manga_live.linguistics import address_output_issues
    region={"id":"r","ja":"I L O V E Y O U"}
    assert address_output_issues({},[region],[{"id":"r","vi":target}])==[
        {"id":"r","reason":"unconfirmed_spelled_english_pair"}]
    assert address_output_issues({},[region],[{"id":"r","vi":"T Ô I   Y Ê U   B Ạ N"}])==[]
    known={**region,"speaker":"reader-younger","listener":"reader-older"}
    assert address_output_issues(expressive_voice_context("em","anh"),[known],[{"id":"r","vi":target}])==[]
    quoted={**region,"ja":"彼はI L O V E Y O Uと言った。"}
    assert address_output_issues({},[quoted],[{"id":"r","vi":target}])==[]


def test_exact_reader_phrase_lock_wins_over_unconfirmed_english_pair_guard():
    from manga_live.linguistics import address_output_issues
    from manga_live.terminology import term_record
    source="I L O V E Y O U"
    context={"glossary":[{"confirmed":1,"value":json.dumps(term_record("line","other",source,"Anh yêu em"),ensure_ascii=False)}]}
    assert address_output_issues(context,[{"id":"r","ja":source}],[{"id":"r","vi":"Anh yêu em"}])==[]


def test_unconfirmed_english_pair_repair_is_bounded_to_failed_id():
    translator=Translator.__new__(Translator);calls=[]
    def generate(regions,context,cancel):
        calls.append(([r["id"] for r in regions],context))
        return ([{"id":"r","vi":"Anh yêu em"},{"id":"ok","vi":"DỪNG LẠI!"}] if len(calls)==1 else
            [{"id":"r","vi":"Tôi yêu bạn"}]),{"translation_ms":1,"usage":{}}
    translator._translate=generate
    items,metrics=translator.translate([{"id":"r","ja":"I L O V E Y O U"},{"id":"ok","ja":"STOP!"}],{},threading.Event())
    assert [ids for ids,_ in calls]==[["r","ok"],["r"]]
    assert calls[1][1]["output_repair"]==[{"id":"r","reason":"unconfirmed_spelled_english_pair"}]
    assert [i["vi"] for i in items]==["T Ô I   Y Ê U   B Ạ N","DỪNG LẠI!"]
    assert metrics["attempts"]==2


def test_whole_spelled_i_you_prompt_is_specific_without_overriding_reader_pair():
    from manga_live.expression import expression_guidance
    region={"id":"r","ja":"I L O V E Y O U"}
    prompt=expression_guidance([region],{})
    assert 'Whole spelled I/you "r"' in prompt
    assert "neutral tôi/bạn" in prompt
    known={**region,"speaker":"reader-younger","listener":"reader-older"}
    assert "Whole spelled I/you" not in expression_guidance([known],expressive_voice_context("em","anh"))
    assert "Whole spelled I/you" not in expression_guidance([{**region,"ja":"彼はI L O V E Y O Uと言った。"}],{})


def test_caps_and_local_spelling_preserve_a_locked_label_including_quoted_form():
    from manga_live.terminology import term_record, constraints, missing_terms
    from manga_live.validation import translation_output_issues
    source="S T A R S W O R D"
    context={"glossary":[{"confirmed":1,"value":json.dumps(term_record("star","weapon",source,"“Kiếm Sao”"))}]}
    translator=Translator.__new__(Translator)
    translator._translate=lambda *args:([{"id":"r","vi":"“Kiếm Sao”"}],{"translation_ms":1,"usage":{}})
    regions=[{"id":"r","ja":source}]
    items,metrics=translator.translate(regions,context,threading.Event())
    assert items[0]["vi"]=="“KIẾM SAO”" and metrics["attempts"]==1
    assert not missing_terms(context,regions,items)
    assert not translation_output_issues(regions,items,constraints(context,regions))


def test_persistent_flattening_does_not_reach_overlay_or_loop_forever():
    translator=Translator.__new__(Translator);calls=[]
    translator._translate=lambda *args:(calls.append(1) or [{"id":"r","vi":"Tôi!"}],{"translation_ms":1,"usage":{}})
    with pytest.raises(AppError) as error:
        translator.translate([{"id":"r","ja":"わ・た・し〜〜！"}],{},threading.Event())
    assert error.value.code=="MODEL_OUTPUT" and len(calls)==2


def test_ordinary_translation_keeps_case_and_needs_no_conditional_prompt_budget():
    translator=Translator.__new__(Translator)
    translator._translate=lambda *args:([{"id":"r","vi":"Cảm ơn, Kirito-kun."}],{"translation_ms":1,"usage":{}})
    assert translator.translate([{"id":"r","ja":"キリトくん、ありがとう。"}],{},threading.Event())[0][0]["vi"]=="Cảm ơn, Kirito-kun."
    assert PROMPT_VERSION=="ja-vi-v22-directed-wait-no-stack"


def expressive_voice_context(self_term="em",address="chị",confirmed=True):
    from manga_live.linguistics import voice_record
    return {"characters":[{"kind":"relationship","confirmed":int(confirmed),
        "value":json.dumps(voice_record("reader-younger","reader-older",self_term,address),ensure_ascii=False)}]}


def test_expressive_prompt_does_not_anchor_a_confirmed_em_to_generic_toi():
    region={"id":"voice","ja":"わ・た・し〜〜！","speaker":"reader-younger","listener":"reader-older"}
    for prompt in (compact_prompt,translation_prompt,focused_compact_prompt):
        value=prompt([region],expressive_voice_context())
        assert "Tô-iii" not in value
        assert "Eeem" in value
        assert "em" in value and "chị" in value


def test_expressive_locked_self_is_repaired_at_cloud_provider_seam(monkeypatch):
    import manga_live.providers as providers
    translator=Translator.__new__(Translator)
    translator.config=SimpleNamespace(values={"mode":"byok","cloudConsent":True,"provider":"openrouter",
        "openrouterModel":"deepseek/deepseek-v4.1-flash"})
    translator.vault=SimpleNamespace(get=lambda provider:"fake-test-key-not-a-secret")
    translator.signature=lambda:"test-cloud"
    calls=[]
    def respond(url,body,*args,**kwargs):
        calls.append(body)
        return {"choices":[{"message":{"content":json.dumps({"items":[{"id":"voice",
            "vi":"Tô-iii!" if len(calls)==1 else "Eeem!","ambiguous":False}]},ensure_ascii=False)}}],
            "usage":{"cost":0.001,"prompt_tokens":10,"completion_tokens":5}}
    monkeypatch.setattr(providers,"post_json",respond)
    region={"id":"voice","ja":"わ・た・し〜〜！","speaker":"reader-younger","listener":"reader-older"}
    items,metrics=translator.translate([region],expressive_voice_context(),threading.Event())
    assert items[0]["vi"]=="Eeem!" and len(calls)==2
    assert metrics["usage"]["cost"]==pytest.approx(0.002)
    assert "directed_expressive_self_conflict" in calls[1]["messages"][0]["content"]


@pytest.mark.parametrize("source,target,confirmed",[
    ("わ・た・し〜〜！","Eeem!",True),
    ("わ・た・し〜〜！","Tô-iii!",False),
    ("わ・た・し〜〜！","Tô-iii!",True),
    ("彼は『わ・た・し〜〜』と言った。","Cậu ấy nói: 'Tô-iii!'.",True),
    ("あ・な・た〜〜？","Chịịị?",True),
])
def test_expressive_self_guard_requires_whole_source_and_direct_confirmed_pair(source,target,confirmed):
    from manga_live.linguistics import address_output_issues
    # A user may explicitly choose tôi. Never enforce a stock family hierarchy.
    self_term="tôi" if source=="わ・た・し〜〜！" and target=="Tô-iii!" and confirmed else "em"
    context=expressive_voice_context(self_term=self_term,confirmed=confirmed)
    region={"id":"voice","ja":source,"speaker":"reader-younger","listener":"reader-older"}
    assert address_output_issues(context,[region],[{"id":"voice","vi":target}])==[]


def test_reverse_direction_or_unknown_speaker_never_inherits_expressive_self_rule():
    from manga_live.linguistics import address_output_issues
    for speaker,listener in (("reader-older","reader-younger"),("unknown","reader-older")):
        region={"id":"voice","ja":"わ・た・し〜〜！","speaker":speaker,"listener":listener}
        assert address_output_issues(expressive_voice_context(),[region],[{"id":"voice","vi":"Tô-iii!"}])==[]


@pytest.mark.parametrize("bad",["Tô-iii!","Tớớớ!","Chịịị!"])
def test_whole_expressive_first_person_cannot_take_generic_or_listener_term(bad):
    from manga_live.linguistics import address_output_issues
    region={"id":"voice","ja":"わ・た・し〜〜！","speaker":"reader-younger","listener":"reader-older"}
    assert address_output_issues(expressive_voice_context(),[region],[{"id":"voice","vi":bad}])==[
        {"id":"voice","reason":"directed_expressive_self_conflict"}]
