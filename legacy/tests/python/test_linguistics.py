import json
import pytest
from manga_live.linguistics import voice_record,confirmed_rules,policy,grammar_focus,name_record,confirmed_names,style_values,explicit_address
from manga_live.memory import Memory

def test_directed_pair_is_not_symmetric_or_guessed():
    rule=voice_record("younger","sister","em","chị","natural")
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(rule)}]}
    assert confirmed_rules(context,[{"speaker":"younger","listener":"sister"}])==[rule]
    assert confirmed_rules(context,[{"speaker":"sister","listener":"younger"}])==[]
    assert confirmed_rules(context,[{"speaker":"unknown","listener":"sister"}])==[]

def test_grammar_focus_and_style_are_bounded():
    regions=[{"ja":"行かないわけじゃない。兄に行かせられた。"}]
    focus=grammar_focus(regions)
    assert any("negation" in r for r in focus)
    assert any("causative" in r for r in focus)
    assert len(focus)<=4
    result=policy({"styles":[{"key":"naming","value":"fantasy"}]},regions)
    assert "Sino-Vietnamese" in result and "not invented powers" in result

def test_voice_and_glossary_retrieved_with_cutoff(tmp_path):
    memory=Memory(tmp_path/"test.db");memory.ensure_story("s","Test")
    for i in range(20):memory.fact("s","character",f"c{i}","unrelated",{"chapter":1,"page":0},{"type":"user"})
    rule=voice_record("A","B","em","chị")
    memory.fact("s","relationship","A→B",json.dumps(rule),{"chapter":2,"page":0},{"type":"user"})
    memory.fact("s","glossary","氷結結界","Băng Kết Kết Giới",{"chapter":2,"page":0},{"type":"user"})
    now=memory.context("s",{"chapter":2,"page":0},"氷結結界",entities={"A","B"})["data"]
    assert confirmed_rules(now,[{"speaker":"A","listener":"B"}])==[rule]
    assert now["glossary"][0]["key"]=="氷結結界"
    earlier=memory.context("s",{"chapter":1,"page":99},entities={"A","B"})["data"]
    assert not confirmed_rules(earlier,[{"speaker":"A","listener":"B"}])
    memory.close()

def test_vocatives_are_not_flattened_by_confirmed_family_rules():
    assert explicit_address({},[{"id":"a","ja":"姉ちゃん、まだ帰らないの？"}])==[{"id":"a","ja":"姉ちゃん","vi":"nee-chan"}]
    assert explicit_address({},[{"id":"a","ja":"私の兄は医者です。"}])==[]
    assert explicit_address({"styles":[{"key":"kinship","value":"natural"}]},[{"id":"a","ja":"姉ちゃん、聞いて。"}])==[]

def test_opening_quotes_do_not_hide_source_vocatives():
    for quote in ('「', '『', '“', '"'):
        source=quote+"姉ちゃん、まだ帰らないの？"
        regions=[{"id":"a","ja":source}]
        assert explicit_address({},regions)==[{"id":"a","ja":"姉ちゃん","vi":"nee-chan"}]
        assert regions[0]["ja"]==source  # Keep the OCR evidence untouched.
    assert explicit_address({},[{"id":"a","ja":"「先生、聞いてください。」"}])==[{"id":"a","ja":"先生","vi":"sensei"}]
    assert explicit_address({},[{"id":"a","ja":"「姉ちゃんはまだ帰らない。」"}])==[]

def test_source_address_policy_is_separate_from_vietnamese_pronouns():
    result=policy({},[{"ja":"田中さん、お兄ちゃんを呼んで。"}])
    assert "Never add an honorific absent" in result
    assert "exact family-name/given-name" in result
    assert "not proof of romance" in result
    assert "ordinary narrative kinship" in result
    assert style_values({})=={"naming":"natural","honorifics":"preserve","kinship":"preserve"}
    assert style_values({"styles":[{"key":"honorifics","value":"localize"}]})["honorifics"]=="localize"

def test_names_and_all_style_controls_survive_retrieval_without_future_aliases(tmp_path):
    memory=Memory(tmp_path/"names.db");memory.ensure_story("s","Test")
    at={"chapter":2,"page":0}
    for i in range(30):memory.fact("s","character",f"c{i}","unrelated",at,{"type":"user"})
    names=name_record("misaki",[{"ja":"田中","reading":"Tanaka","role":"family"},
                               {"ja":"美咲","reading":"Misaki","role":"given"}])
    memory.fact("s","character","misaki",json.dumps(names,ensure_ascii=False),at,{"type":"user"})
    for key,value in [("naming","fantasy"),("honorifics","hybrid"),("kinship","natural")]:
        memory.fact("s","style",key,value,at,{"type":"user"})
    now=memory.context("s",at,"田中さん、聞いて。")['data']
    assert confirmed_names(now)==[names]
    assert style_values(now)=={"naming":"fantasy","honorifics":"hybrid","kinship":"natural"}
    assert confirmed_names(memory.context("s",{"chapter":1,"page":99},"田中さん")['data'])==[]
    assert confirmed_names({"characters":[{"kind":"character","confirmed":1,"value":'{"type":"name-forms"}'}]})==[]
    memory.close()


def name_context():
    return {"characters":[{"kind":"character","confirmed":1,"value":json.dumps(name_record("misaki",[
        {"ja":"田中","reading":"Tanaka","role":"family"},
        {"ja":"美咲","reading":"Misaki","role":"given"},
        {"ja":"田中美咲","reading":"Tanaka Misaki","role":"full"}]),ensure_ascii=False)}]}


def test_confirmed_given_name_switch_has_exact_reading_constraint():
    assert explicit_address(name_context(),[{"id":"a","ja":"美咲って呼んでもいい？"}])==[
        {"id":"a","ja":"美咲","vi":"Misaki"}]


def test_full_name_address_does_not_also_require_short_given_name_suffix():
    assert explicit_address(name_context(),[{"id":"a","ja":"田中美咲さん、聞いて。"}])==[
        {"id":"a","ja":"田中美咲さん","vi":"Tanaka Misaki-san"}]


def test_known_name_inside_canonical_weapon_is_not_a_separate_name_constraint():
    from manga_live.terminology import constraints,term_record
    context=name_context();context["glossary"]=[{"value":json.dumps(
        term_record("sword","weapon","美咲さんの剣","Hoa Ảnh Kiếm"),ensure_ascii=False)}]
    assert constraints(context,[{"id":"a","ja":"美咲さんの剣を使う。"}])==[
        {"id":"a","ja":"美咲さんの剣","vi":"Hoa Ảnh Kiếm"}]


def test_bare_known_name_never_receives_new_suffix_or_expanded_full_name():
    from manga_live.linguistics import address_output_issues
    region={"id":"a","ja":"美咲、待って！"}
    assert address_output_issues(name_context(),[region],[{"id":"a","vi":"Misaki, đợi đã!"}])==[]
    assert address_output_issues(name_context(),[region],[{"id":"a","vi":"Misaki-san, đợi đã!"}])
    assert address_output_issues(name_context(),[region],[{"id":"a","vi":"Tanaka Misaki, đợi đã!"}])


def test_senpai_does_not_supply_unconfirmed_gendered_vietnamese_address():
    from manga_live.linguistics import address_output_issues
    region={"id":"a","ja":"先輩、手伝ってもらえますか。"}
    assert address_output_issues({},[region],[{"id":"a","vi":"Senpai, anh có thể giúp em một tay không?"}])==[
        {"id":"a","reason":"unconfirmed_gendered_address"}]
    assert address_output_issues({},[region],[{"id":"a","vi":"Senpai, giúp được không ạ?"}])==[]


def test_title_gender_check_respects_directed_reader_rule_and_narrative_kinship():
    from manga_live.linguistics import address_output_issues
    region={"id":"a","ja":"先輩、手伝ってもらえますか。","speaker":"junior","listener":"senior"}
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(voice_record("junior","senior","em","anh"))}]}
    assert address_output_issues(context,[region],[{"id":"a","vi":"Senpai, anh có thể giúp em một tay không?"}])==[]
    narrative={"id":"a","ja":"先生、兄が来ました。"}
    assert address_output_issues({},[narrative],[{"id":"a","vi":"Sensei, anh trai tôi đã đến."}])==[]
    assert address_output_issues({},[{"id":"a","ja":"先輩はまだ来ない。"}],[{"id":"a","vi":"Anh senpai chưa đến."}])==[]


def test_invalid_or_unknown_pair_cannot_authorize_gendered_address():
    region={"id":"a","ja":"先輩、手伝って。","speaker":"unknown","listener":"unknown"}
    invalid={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(
        {"speaker":"unknown","listener":"unknown","self":"em","address":"anh"})}]}
    assert confirmed_rules(invalid,[region])==[]
    malformed={"characters":[{"kind":"relationship","confirmed":1,"value":'{"speaker":"junior","listener":"senior","address":"anh"}'}]}
    assert confirmed_rules(malformed,[{"speaker":"junior","listener":"senior"}])==[]


def test_unknown_neutral_vocative_cannot_leave_a_pronoun_choice_in_dialogue():
    from manga_live.linguistics import address_output_issues
    regions=[{"id":"r","ja":"先輩、手伝ってもらえますか。"}]
    for vi in ("Senpai, anh/chị có thể giúp tôi được không?",
               "Senpai, anh / chị có thể giúp một tay không?",
               "Senpai, (anh/chị) có thể giúp không?",
               "Senpai, anh hoặc chị giúp một tay nhé?"):
        assert address_output_issues({},regions,[{"id":"r","vi":vi}])==[
            {"id":"r","reason":"unresolved_address_placeholder"}]
    assert address_output_issues({},regions,[{"id":"r","vi":"Senpai, giúp một tay được không ạ?"}])==[]


def test_placeholder_guard_preserves_confirmed_pair_and_explicit_source_alternatives():
    from manga_live.linguistics import address_output_issues
    region={"id":"r","ja":"先輩、手伝って。","speaker":"junior","listener":"senior"}
    # Even an unconventional user lock remains authoritative; the guard is
    # not permission to rewrite reader-confirmed address.
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(
        voice_record("junior","senior","tôi","anh/chị"))}]}
    output=[{"id":"r","vi":"Senpai, anh/chị giúp một tay nhé?"}]
    assert address_output_issues(context,[region],output)==[]
    assert address_output_issues(context,[{**region,"listener":"other"}],output)
    source={"id":"r","ja":"先生、兄か姉が迎えに来ます。"}
    assert address_output_issues({},[source],[{"id":"r","vi":"Sensei, anh/chị sẽ tới đón."}])==[]


def test_natural_address_repair_reaches_each_prompt_without_mutating_context():
    from manga_live.prompts import translation_prompt,compact_prompt,focused_compact_prompt,address_repair
    regions=[{"id":"r","ja":"先輩、手伝って。"}]
    context={"output_repair":[{"id":"r","reason":"unresolved_address_placeholder"}]}
    repair=address_repair(context)
    assert "never choose a gender" in repair and "omitting unknown pronouns" in repair
    for prompt in (translation_prompt,compact_prompt,focused_compact_prompt):
        assert repair.strip() in prompt(regions,context)
    assert context=={"output_repair":[{"id":"r","reason":"unresolved_address_placeholder"}]}


def test_confirmed_directed_request_cannot_reverse_speaker_and_recipient():
    from manga_live.linguistics import address_output_issues
    region={"id":"r","ja":"先に帰ってて。あとで行くから。","speaker":"sister","listener":"younger"}
    rule=voice_record("sister","younger","chị","em")
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(rule)}]}
    bad=[{"id":"r","vi":"Chị về trước nhé. Lát nữa chị sẽ đến."}]
    assert address_output_issues(context,[region],bad)==[{"id":"r","reason":"directed_request_role_conflict"}]
    for vi in ("Em về trước đi. Lát chị sẽ đến.","Về trước đi. Lát chị sẽ đến."):
        assert address_output_issues(context,[region],[{"id":"r","vi":vi}])==[]
    assert address_output_issues({},[region],bad)==[]
    assert address_output_issues(context,[{**region,"listener":"unknown"}],bad)==[]
    assert address_output_issues(context,[{**region,"ja":"私は先に帰る。"}],bad)==[]
    assert address_output_issues(context,[{**region,"ja":"先に帰っててくれと姉に頼まれた。"}],bad)==[]


def test_directed_request_repair_keeps_the_same_pair_in_all_prompt_adapters():
    from manga_live.prompts import translation_prompt,compact_prompt,focused_compact_prompt,address_repair
    context={"output_repair":[{"id":"r","reason":"directed_request_role_conflict"}]}
    region={"id":"r","ja":"先に帰ってて。"}
    repair=address_repair(context).strip()
    assert "LISTENER" in repair and "speaker's self-term" in repair
    for prompt in (translation_prompt,compact_prompt,focused_compact_prompt):assert repair in prompt([region],context)


def test_confirmed_reply_does_not_revert_to_generic_first_person():
    from manga_live.linguistics import address_output_issues
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(
        voice_record("sister","younger","chị","em"))}]}
    region={"id":"r","ja":"先に帰ってて。あとで行くから。","speaker":"sister","listener":"younger"}
    assert address_output_issues(context,[region],[{"id":"r","vi":"Cứ về trước đi. Tôi sẽ đến sau."}])==[
        {"id":"r","reason":"directed_self_term_conflict"}]
    for vi in ("Em về trước đi. Lát nữa chị tới.","Cứ về trước đi. Lát nữa sẽ đến."):
        assert address_output_issues(context,[region],[{"id":"r","vi":vi}])==[]
    # Generic first person can be correct for another confirmed register;
    # unknown speakers and quoted third-party speech are not silently changed.
    assert address_output_issues({},[region],[{"id":"r","vi":"Tôi sẽ đến sau."}])==[]
    quoted={**region,"ja":"彼は「先に帰ってて。あとで行くから」と言った。"}
    assert address_output_issues(context,[quoted],[{"id":"r","vi":"Cậu ấy nói: Tôi sẽ đến sau."}])==[]
    context["characters"][0]["value"]=json.dumps(voice_record("sister","younger","tôi","em"))
    assert address_output_issues(context,[region],[{"id":"r","vi":"Tôi sẽ đến sau."}])==[]


def test_confirmed_implicit_waiter_cannot_be_reversed_into_listener_waiting_for_speaker():
    from manga_live.linguistics import address_output_issues
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(
        voice_record("younger","sister","em","chị"))}]}
    region={"id":"r","ja":"わかった。待ってるね。","speaker":"younger","listener":"sister"}
    assert address_output_issues(context,[region],[{"id":"r","vi":"Được rồi. Chị sẽ chờ em."}])==[
        {"id":"r","reason":"directed_wait_role_conflict"}]
    assert address_output_issues(context,[region],[{"id":"r","vi":"Được rồi. Tôi sẽ chờ cô ấy."}])==[
        {"id":"r","reason":"directed_wait_role_conflict"}]
    assert address_output_issues(context,[region],[{"id":"r","vi":"Được rồi. Em sẽ chờ chị."}])==[]
    # The guard is not a general Japanese parser: explicit third-person and
    # unknown-role lines remain available for ordinary translation/review.
    assert address_output_issues(context,[{**region,"ja":"姉ちゃんが待ってる。"}],
        [{"id":"r","vi":"Chị đang chờ em."}])==[]
    assert address_output_issues({},[{"id":"r","ja":"わかった。待ってるね。"}],
        [{"id":"r","vi":"Chị sẽ chờ em."}])==[]


def test_directed_wait_repair_reaches_every_prompt_adapter():
    from manga_live.prompts import translation_prompt,compact_prompt,focused_compact_prompt,address_repair
    context={"output_repair":[{"id":"r","reason":"directed_wait_role_conflict"}]}
    region={"id":"r","ja":"わかった。待ってるね。"}
    repair=address_repair(context).strip()
    assert "implicit waiter" in repair and "Em sẽ chờ chị" in repair
    for prompt in (translation_prompt,compact_prompt,focused_compact_prompt):
        assert repair in prompt([region],context)


def test_role_guidance_is_scoped_and_keeps_vocatives_separate():
    from manga_live.linguistics import role_guidance
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(
        voice_record("sister","younger","chị","em"))}]}
    regions=[{"id":"r","ja":"先に帰ってて。あとで行くから。","speaker":"sister","listener":"younger"},
             {"id":"u","ja":"姉ちゃん、聞いて。","speaker":"unknown","listener":"unknown"}]
    hints=role_guidance(context,regions)
    assert len(hints)==1 and hints[0]["id"]=="r"
    assert hints[0]["self"]=="chị" and hints[0]["address"]=="em"
    assert "LISTENER" in hints[0]["hint"] and "SPEAKER" in hints[0]["hint"]
    assert role_guidance(context,[{**regions[0],"listener":"unknown"}])[0].get("self") is None


def test_role_guidance_marks_implicit_waiter_for_compact_local_prompt():
    from manga_live.linguistics import role_guidance
    context={"characters":[{"kind":"relationship","confirmed":1,"value":json.dumps(
        voice_record("younger","sister","em","chị"))}]}
    region={"id":"r","ja":"わかった。待ってるね。","speaker":"younger","listener":"sister"}
    hints=role_guidance(context,[region])
    assert len(hints)==1 and "implicit subject" in hints[0]["hint"]
    assert "SPEAKER" in hints[0]["hint"] and "LISTENER" in hints[0]["hint"]


def test_directed_self_conflict_guidance_reaches_every_prompt():
    from manga_live.prompts import translation_prompt,compact_prompt,focused_compact_prompt,address_repair
    context={"output_repair":[{"id":"r","reason":"directed_self_term_conflict"}]}
    region={"id":"r","ja":"先に帰ってて。あとで行くから。"}
    repair=address_repair(context).strip()
    assert "confirmed self-term" in repair and "tôi" in repair
    for prompt in (translation_prompt,compact_prompt,focused_compact_prompt):assert repair in prompt([region],context)


@pytest.mark.parametrize("source,bad,good",[
    ("姉ちゃん、まだ帰らないの？","Chị nee-chan, chị chưa về à?","Nee-chan, chị chưa về à?"),
    ("姉ちゃん！","Chị nee-chan","Nee-chan"),
    ("姉ちゃん、まだ帰らないの？","Chị nee-chan chưa về à?","Nee-chan chưa về à?"),
    ("お姉ちゃん、聞いて。","Chị gái onee-chan, nghe này.","Onee-chan, nghe này."),
    ("お兄ちゃん、聞いて。","Anh onii-chan, nghe này.","Onii-chan, nghe này."),
    ("お兄ちゃん！","Anh trai onii-chan","Onii-chan"),
    ("先生、聞いてください。","Thầy sensei, nghe này.","Sensei, nghe này."),
])
def test_retained_vocative_cannot_stack_a_redundant_leading_title(source,bad,good):
    from manga_live.linguistics import address_output_issues
    region={"id":"r","ja":source}
    assert address_output_issues({},[region],[{"id":"r","vi":bad}])==[
        {"id":"r","reason":"redundant_retained_vocative"}]
    assert address_output_issues({},[region],[{"id":"r","vi":good}])==[]
    assert address_output_issues({"styles":[{"key":"kinship","value":"natural"},
        {"key":"honorifics","value":"localize"}]},[region],[{"id":"r","vi":bad}])==[]


def test_redundant_title_guard_never_rewrites_narrative_or_reader_locked_name():
    from manga_live.linguistics import address_output_issues
    from manga_live.terminology import term_record
    region={"id":"r","ja":"姉ちゃん、聞いて。"}
    context={"glossary":[{"confirmed":1,"value":json.dumps(
        term_record("custom","epithet","姉ちゃん","Chị Nee-chan"),ensure_ascii=False)}]}
    assert address_output_issues(context,[region],[{"id":"r","vi":"Chị Nee-chan, nghe này."}])==[]
    assert address_output_issues({},[{"id":"r","ja":"姉ちゃんは先生だ。"}],
        [{"id":"r","vi":"Chị nee-chan là giáo viên."}])==[]


def test_retained_sibling_guard_keeps_later_pronouns_and_longer_nicknames():
    from manga_live.linguistics import address_output_issues
    region={"id":"r","ja":"姉ちゃん、聞いて。"}
    for vi in ("Nee-chan, chị nghe này.","Nee-chan, chị gái đang gọi kìa.",
               "Chị nee-chanette, nghe này."):
        assert address_output_issues({},[region],[{"id":"r","vi":vi}])==[]
    # The extra end/whitespace check is for kinship titles, not bare names.
    assert address_output_issues(name_context(),[{"id":"r","ja":"美咲、聞いて。"}],
        [{"id":"r","vi":"Chị Misaki nghe này."}])==[]


@pytest.mark.parametrize("locked",["Chị Nee-chan","Chị gái Nee-chan"])
def test_sibling_stack_guard_respects_exact_reader_lock_without_comma(locked):
    from manga_live.linguistics import address_output_issues
    from manga_live.terminology import term_record
    region={"id":"r","ja":"姉ちゃん、聞いて。"}
    context={"glossary":[{"confirmed":1,"value":json.dumps(
        term_record("custom","epithet","姉ちゃん",locked),ensure_ascii=False)}]}
    assert address_output_issues(context,[region],[{"id":"r","vi":locked}])==[]


def test_no_stacked_sibling_examples_reach_every_translation_prompt():
    from manga_live.prompts import translation_prompt,compact_prompt,focused_compact_prompt
    region={"id":"r","ja":"姉ちゃん、聞いて。"}
    for prompt in (translation_prompt,compact_prompt,focused_compact_prompt):
        value=prompt([region],{})
        assert "never chị nee-chan or chị gái nee-chan" in value
        assert "never anh onii-chan or anh trai onii-chan" in value


def test_san_sibling_readings_reach_every_prompt_without_overriding_natural_style():
    from manga_live.prompts import translation_prompt,compact_prompt,focused_compact_prompt
    region={"id":"r","ja":"姉さん、兄さん、聞いて。"}
    natural={"styles":[{"key":"kinship","value":"natural"}]}
    for prompt in (translation_prompt,compact_prompt,focused_compact_prompt):
        value=prompt([region],{})
        assert "兄さん=nii-san" in value and "姉さん=nee-san" in value
        localized=prompt([region],natural)
        assert "兄さん=nii-san" not in localized and "姉さん=nee-san" not in localized


@pytest.mark.parametrize("source,bad,good",[
    ("姉ちゃん","Chị nee-chan","Nee-chan"),
    ("お兄ちゃん","Anh trai onii-chan","Onii-chan"),
    ("「姉ちゃん」","Chị nee-chan","Nee-chan"),
])
def test_standalone_sibling_call_without_ocr_punctuation_still_cannot_stack(source,bad,good):
    from manga_live.linguistics import address_output_issues
    region={"id":"r","ja":source}
    assert address_output_issues({},[region],[{"id":"r","vi":bad}])==[
        {"id":"r","reason":"redundant_retained_vocative"}]
    assert address_output_issues({},[region],[{"id":"r","vi":good}])==[]


@pytest.mark.parametrize("source,title,redundant",[
    ("姉さん", "nee-san", "Chị nee-san"),
    ("兄さん", "nii-san", "Anh trai nii-san"),
    ("「姉さん、聞いて。」", "nee-san", "Chị nee-san, chị nghe này."),
    ("兄さん！", "nii-san", "Anh nii-san"),
])
def test_san_sibling_vocatives_share_the_same_narrow_no_stack_rule(source,title,redundant):
    from manga_live.linguistics import address_output_issues
    region={"id":"r","ja":source}
    assert explicit_address({},[region])==[{"id":"r","ja":"姉さん" if "姉" in source else "兄さん","vi":title}]
    assert address_output_issues({},[region],[{"id":"r","vi":redundant}])==[
        {"id":"r","reason":"redundant_retained_vocative"}]
    assert address_output_issues({},[region],[{"id":"r","vi":title+", chị nghe này."}])==[]
    assert explicit_address({"styles":[{"key":"kinship","value":"natural"}]},[region])==[]


@pytest.mark.parametrize("source,title",[("姉さん","nee-san"),("兄さん","nii-san")])
def test_san_sibling_guard_preserves_narrative_longer_names_source_quotes_and_reader_exception(source,title):
    from manga_live.linguistics import address_output_issues
    from manga_live.terminology import term_record
    region={"id":"r","ja":"「"+source+"」"}
    before=dict(region)
    locked="Chị "+title if "姉" in source else "Anh "+title
    context={"glossary":[{"confirmed":1,"value":json.dumps(
        term_record("reader_exception","epithet",source,locked),ensure_ascii=False)}]}
    assert address_output_issues(context,[region],[{"id":"r","vi":locked}])==[]
    assert explicit_address({},[{"id":"r","ja":source+"は医者です。"}])==[]
    assert address_output_issues({},[region],[{"id":"r","vi":locked+"ette, nghe này."}])==[]
    assert region==before
