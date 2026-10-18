"""Small, evidence-first translation policy. Not an automatic family-tree solver."""
import json
import re
from .errors import AppError, require
from .validation import identifier, text

STYLE_PRESETS={
    "natural":"Natural modern Vietnamese. Prefer clear everyday names, not archaic diction.",
    "fantasy":"Fantasy/action: concise forceful skill and item names. Use meaningful Sino-Vietnamese names for suitable kanji compounds, not invented powers. Translate compound meanings, not kanji one by one; prefer a fluent name over accidental repeated syllables, unless source rhetoric or an exact glossary requires them. Keep katakana/proper names unless confirmed in the glossary.",
    "historical":"Historical/fantasy register when supported by the story. Do not turn ordinary modern dialogue into archaic speech. Never invent kinship or rank.",
    "comedy":"Modern lively comedy. Preserve joke, tone and wordplay where possible; do not add jokes or internet slang absent from the source.",
}

HONORIFIC_MODES={
    "preserve":"Retain source-present personal honorifics as -san/-kun/-chan/-sama/-dono and sensei/senpai in address. Never add an honorific absent from the source. Keep ordinary Vietnamese sentences natural; do not stack redundant titles such as anh + onii-chan. Preserve deliberate honorific changes, irony and insults.",
    "hybrid":"Retain honorifics when a name, nickname, address change, joke or relationship depends on them. Otherwise convey the same register naturally in Vietnamese, without invented age/gender/kinship. Do not flatten a meaningful change into one constant form.",
    "localize":"Render address naturally in Vietnamese using confirmed relationships. Keep the meaning of name/honorific changes and jokes, even when localizing. Do not replace -san mechanically with anh/chị/ngài or invent relationships.",
}
KINSHIP_MODES={
    "preserve":"In direct address retain source-present お兄ちゃん=onii-chan, 兄ちゃん=nii-chan, お姉ちゃん=onee-chan, 姉ちゃん=nee-chan, お兄さん=onii-san, お姉さん=onee-san, 兄さん=nii-san, 姉さん=nee-san. These calls already carry the title: use nee-chan alone, never chị nee-chan or chị gái nee-chan; use onii-chan alone, never anh onii-chan or anh trai onii-chan. The same no-stack rule applies to the -san variants. Later Vietnamese pronouns may remain when supported. Keep variants consistent. Translate ordinary narrative kinship (e.g. 私の兄) into Vietnamese; do not invent blood kinship from a vocative.",
    "natural":"Translate sibling vocatives naturally with confirmed Vietnamese address. Do not infer real family relationships from a stranger being called お兄さん/お姉さん. Preserve meaningful nickname differences through glossary or context.",
}
STYLE_OPTIONS={"naming":STYLE_PRESETS,"honorifics":HONORIFIC_MODES,"kinship":KINSHIP_MODES}
NAME_POLICY="Preserve the exact family-name/given-name/nickname form used in each source line. A given-name switch may signal intimacy, but is not proof of romance or a new relationship. Use only confirmed readings/aliases when provided; never substitute a full name or a future nickname for the current source address."

CORE_POLICY="""Vietnamese address is relational, not a fixed dictionary mapping of 俺/僕/私/君/あなた.
Confirmed A→B self/address rules apply ONLY when that speaker/listener pair is known. Kinship, age, gender and social rank require evidence; never guess them from a name, visual appearance or politeness alone.
When unknown, natural subject omission is better than invented tôi/anh ấy/cô ấy. Preserve uncertainty.
Do not leave pronoun alternatives such as anh/chị in dialogue when the relationship is unknown; omit the pronoun naturally. Preserve genuine alternatives expressed by the source.
Glossary overrides naming style. Sino-Vietnamese styling applies to appropriate skill/item terminology, not automatically every kanji, Japanese native reading, personal name or katakana loanword. Preserve effect, conditions and power level; do not embellish."""

# Retrieve only relevant cautions instead of a grammar textbook per call.
GRAMMAR=[
    (r"わけ|ない|ず|ぬ|なかった|なきゃ", "Preserve negation scope and double negation; なくてもいい means not necessary, not forbidden; なければ/なきゃ may express obligation."),
    (r"せられ|させ|られ|れる|させて", "Distinguish passive, potential and causative from context; causative-passive can mean being made to act. Do not swap agent and patient."),
    (r"くれ|もら|あげ|くださ|いただ|やって", "Track giver/receiver and viewpoint in くれる/もらう/あげる; honorifics do not prove family or age."),
    (r"はず|らしい|そう|よう|かも|みたい|だろ|でしょう", "Retain probability, hearsay, appearance and expectation; do not convert uncertain statements into facts."),
    (r"ている|てる|ていた|てた|てしま|ちゃっ|とく|ておく", "Preserve progressive/result state, regret/completion and preparation where relevant; expand spoken contractions before interpreting."),
    (r"なら|たら|ば|ても|のに|けど|だけ|しか|まで|さえ", "Keep conditional, contrast and restrictive scope; しか…ない means only, not a second independent negative."),
    (r"って|と言|と思|んだ|のだ|ぞ|ぜ|かしら|かな|よ|ね|わ", "Resolve quoted speech vs topic って; render final particles as tone, not literal words or automatic gender changes."),
    (r"さん|様|さま|先輩|後輩|先生|兄|姉|叔|伯|おじ|おば", "Titles need situational equivalents. 兄/姉 indicate relative elder sibling, but おじさん/おばさん need not indicate actual family. Do not infer uncle/aunt branch without evidence."),
]

def grammar_focus(regions):
    source="\n".join(r["ja"] for r in regions)
    return [rule for pattern,rule in GRAMMAR if re.search(pattern,source)][:4]

def policy(context,regions):
    selected=style_values(context)
    return "\n".join([CORE_POLICY,NAME_POLICY,
        "Story naming style: "+STYLE_PRESETS[selected["naming"]],
        "Honorific policy: "+HONORIFIC_MODES[selected["honorifics"]],
        "Sibling vocatives: "+KINSHIP_MODES[selected["kinship"]],*grammar_focus(regions)])


def style_values(context):
    # Defaults are a user-requested product choice, not a claimed audience poll.
    selected={"naming":"natural","honorifics":"preserve","kinship":"preserve"}
    for row in context.get("styles",[]):
        key,value=row.get("key"),row.get("value")
        if key in STYLE_OPTIONS and value in STYLE_OPTIONS[key]:selected[key]=value
    return selected


def style_record(key,value):
    require(key in STYLE_OPTIONS and value in STYLE_OPTIONS[key],"STYLE","Phong cách không hợp lệ.")
    return key,value


def name_record(character,forms):
    character=identifier(character)
    require(character!="unknown" and isinstance(forms,list) and 1<=len(forms)<=8,"NAME")
    checked=[];seen=set()
    for form in forms:
        require(isinstance(form,dict) and form.get("role") in ("family","given","full","nickname"),"NAME")
        source,reading=text(form.get("ja"),80),text(form.get("reading"),100)
        require(source not in seen,"NAME","Một cách gọi chỉ có một cách đọc đã xác nhận.")
        seen.add(source);checked.append({"ja":source,"reading":reading,"role":form["role"]})
    return {"type":"name-forms","character":character,"forms":checked}


def confirmed_names(context):
    result=[]
    for row in context.get("characters",[]):
        if row.get("kind")!="character" or not row.get("confirmed"):continue
        try:
            value=json.loads(row["value"])
            if isinstance(value,dict) and value.get("type")=="name-forms":
                result.append(name_record(value["character"],value["forms"]))
        except (AppError,ValueError,KeyError,TypeError):continue
    return result


NAME_SUFFIXES=(("さん","san"),("くん","kun"),("君","kun"),("ちゃん","chan"),
               ("様","sama"),("さま","sama"),("殿","dono"))
SIBLING_VOCATIVES={"お兄ちゃん":"onii-chan","兄ちゃん":"nii-chan","お姉ちゃん":"onee-chan","姉ちゃん":"nee-chan",
                   "お兄さん":"onii-san","お姉さん":"onee-san","兄さん":"nii-san","姉さん":"nee-san"}
VOCATIVE_START=r'^[\s「『“"]*'
REQUEST_THEN_PROMISE=VOCATIVE_START+r"先に帰って(?:て|ください|くれ)[。！!]\s*(?:あとで|後で)行くから[。！!]?"

# A deliberately narrow source cue for the observed sibling-role regression.
# ``待ってる`` normally leaves the first-person subject implicit, but the
# same surface can also describe a third party. The helper below therefore
# rejects explicit subjects/quotations and imperative ``待ってて`` before the
# output guard is allowed to act.
WAITING_SELF_SOURCE=re.compile(
    r"^(?:[\s「『“\"]*(?:わかった|わかりました|うん|はい|了解|いいよ|大丈夫)[。！!、,]?\s*)?"
    r"待って(?:る|います|おります)(?:ね|よ|よね|から|んだ|の)?[。！!？?…]*[」』”\"]*$"
)
WAITING_EXPLICIT_SUBJECT=re.compile(
    r"(?:彼|彼女|あの子|あの人|姉ちゃん|兄ちゃん|お姉ちゃん|お兄ちゃん|先生|先輩|[\w一-龯々ぁ-んァ-ン]+)"
    r"(?:は|が|も)\s*(?:待って(?:る|います|おります))"
)


def implicit_waiting_source(source):
    """Return true only for a first-person-like implicit ``待ってる`` line.

    This is not a Japanese parser. It exists solely to keep a confirmed
    speaker/listener pair from being reversed in a common short reply. Any
    explicit subject, quotation wrapper with narrative text, or imperative
    wait request falls through for human/model review rather than being
    rewritten by policy.
    """
    value=source.strip()
    if "待ってて" in value or "待ってください" in value or "待ってくれ" in value:
        return False
    if "と言った" in value or "って言った" in value or "と答えた" in value:
        return False
    if WAITING_EXPLICIT_SUBJECT.search(value):
        return False
    return WAITING_SELF_SOURCE.fullmatch(value) is not None


def reversed_waiting_output(target,pair):
    """Detect a role-reversed or generic-self wait in a short direct reply."""
    self_term=str(pair.get("self","")).strip()
    address_term=str(pair.get("address","")).strip()
    if not self_term or not address_term or self_term.casefold()==address_term.casefold():
        return False
    subject=re.escape(address_term)
    object_term=re.escape(self_term)
    if re.search(
        r"(?:^|[.!?。！？…]\s*)[\s\"“「『]*"+subject+
        r"(?=\s|[,，:：])\s+(?:(?:sẽ|đang|vẫn|cũng|sắp)\s+)?"
        r"(?:chờ|đợi)\b[^.!?。！？…\n]{0,48}?\s*"+object_term+r"(?!\w)",
        target,re.I) is not None:
        return True
    # A confirmed pair can also regress to a generic first-person subject
    # (e.g. ``Tôi sẽ chờ cô ấy``). Catch that only in this implicit-waiting
    # source cue; generic pronouns elsewhere remain ordinary translation.
    generic_self={"tôi","tớ","tao","mình","ta","anh","chị","em","cô","chú","con","cháu","ông","bà"}
    generic_self.discard(self_term.casefold())
    return any(re.search(
        r"(?:^|[.!?。！？…]\s*)[\s\"“「『]*"+re.escape(term)+
        r"(?=\s|[,，:：])\s+(?:(?:sẽ|đang|vẫn|cũng|sắp)\s+)?(?:chờ|đợi)\b",
        target,re.I) for term in generic_self)


def role_guidance(context,regions):
    """Per-utterance roles, never a guessed speaker from another vocative.

    Explicit confirmed pairs are repeated next to their region ID to avoid a
    small translator applying a global 'tôi' default. A narrow speech-act hint
    distinguishes a recipient request from the speaker's following promise.
    It does not parse every Japanese clause or infer kinship.
    """
    pairs={(r["speaker"],r["listener"]):r for r in confirmed_rules(context,regions)}
    result=[]
    for region in regions:
        pair=pairs.get((region.get("speaker"),region.get("listener")))
        request_promise=re.fullmatch(REQUEST_THEN_PROMISE,region["ja"].strip())
        if not pair and not request_promise:continue
        hint={"id":region["id"]}
        if pair:
            hint.update(self=pair["self"],address=pair["address"],
                hint="When first-person is needed, use this confirmed self-term; do not revert to generic tôi. Use address only for the listener, not the speaker. Natural pronoun omission remains valid.")
        if request_promise:
            hint["hint"]=hint.get("hint","")+" The first clause asks the LISTENER to go home first; the second is the SPEAKER promising to come later. With unknown identities, omit pronouns naturally, do not guess a sister or younger sibling."
        if pair and implicit_waiting_source(region["ja"]):
            hint["hint"]=hint.get("hint","")+" This short reply uses an implicit subject for 待ってる: the SPEAKER is the one waiting, and the LISTENER is the person being waited for. Use self as subject and address as object; do not reverse them."
        result.append(hint)
    return result


def known_address_matches(context,region):
    """Only confirmed readings at clear source addresses; no name discovery.

    Longest non-overlapping forms prevent requiring Misaki-san inside the
    already-confirmed full Tanaka Misaki-san. Ambiguous confirmed readings
    remain soft context instead of contradictory exact constraints.
    """
    forms={}
    for name in confirmed_names(context):
        for form in name["forms"]:
            forms.setdefault(form["ja"],{}).setdefault(form["reading"],(name,form))
    candidates=[value for readings in forms.values() if len(readings)==1 for value in readings.values()]
    candidates.sort(key=lambda value:-len(value[1]["ja"]))
    source=region["ja"];start_of_address=re.match(VOCATIVE_START,source).end();covered=set();result=[]
    for name,form in candidates:
        for match in re.finditer(re.escape(form["ja"]),source):
            end=match.end();suffix=next(((ja,vi) for ja,vi in NAME_SUFFIXES if source.startswith(ja,end)),None)
            if not suffix and not (match.start()==start_of_address and
                    re.match(r'[、,，！!？?…。]|[」』”"]?(?:って|と)呼',source[end:])):
                continue
            stop=end+(len(suffix[0]) if suffix else 0);span=set(range(match.start(),stop))
            if covered.intersection(span):continue
            covered.update(span)
            vi=form["reading"]
            if suffix and style_values(context)["honorifics"]=="preserve":vi+="-"+suffix[1]
            result.append({"ja":source[match.start():stop],"vi":vi,"form":form,"name":name,"suffix":suffix})
    return result


def address_output_issues(context,regions,items):
    from .expression import whole_expressive_self,whole_expressive_person,unpace_single_term,whole_spelled_love_phrase,compare_paced_phrase
    from .terminology import constraints
    sources={r["id"]:r for r in regions};result=[]
    exact=constraints(context,regions)
    known_pairs={(rule["speaker"],rule["listener"]):rule for rule in confirmed_rules(context,regions)}
    for item in items:
        region=sources[item["id"]];target=item["vi"]
        pair=known_pairs.get((region.get("speaker"),region.get("listener")))
        # The observed whole English phrase must not fabricate an anh-em
        # couple. This is deliberately NOT a parser for arbitrary romance or
        # quoted dialogue. Reader-confirmed pairs/whole-phrase locks win.
        if not pair and whole_spelled_love_phrase(region["ja"]):
            comparable=compare_paced_phrase(target)
            reader_locked=any(term["id"]==item["id"] and term["ja"]==region["ja"] and
                compare_paced_phrase(term["vi"])==comparable for term in exact)
            gendered=r"(?:anh|chị|em|cô|chú|con|cháu|ông|bà)"
            self_term=r"(?:tôi|tớ|mình|tao|ta|"+gendered+r")"
            if not reader_locked and re.fullmatch(r"(?:"+self_term+r" )?yêu "+gendered+r"[!?…。.]*",comparable):
                result.append({"id":item["id"],"reason":"unconfirmed_spelled_english_pair"})
        if not pair and whole_expressive_person(region["ja"])=="address":
            gendered={"anh","chị","em","cô","chú","con","cháu","ông","bà"}
            if unpace_single_term(target) in gendered and not any(
                    term["id"]==item["id"] and term["vi"].casefold()==target.casefold() for term in exact):
                result.append({"id":item["id"],"reason":"unconfirmed_expressive_address"})
        # A retained source vocative is already a title. Catch only the
        # observed leading stack, not a pronoun in the next clause or a
        # narrative description. Exact reader glossary takes precedence.
        for title in explicit_address(context,[region]):
            doubled=re.match(r'^[\s「『“"]*(?:anh|chị|thầy|cô|ngài)\s+'
                +re.escape(title["vi"])+r'\s*[,，:：!！？?]',target,re.I)
            # A sibling call remains a title even without a following comma
            # or when printed alone. Do not broaden this to ordinary names:
            # a plain name is not itself a kinship/title word. Require a
            # whole retained call, not a prefix of a different nickname.
            if title["ja"] in SIBLING_VOCATIVES:
                doubled=doubled or re.match(r'^[\s「『“"]*(?:anh(?:\s+trai)?|chị(?:\s+gái)?)\s+'
                    +re.escape(title["vi"])+r'(?=$|\s|[,，:：.!！？?…」』”"])',target,re.I)
            locked=any(term["id"]==item["id"] and term["ja"]==title["ja"] and
                       target.casefold().lstrip('「『“" ').startswith(term["vi"].casefold())
                       for term in exact if term["vi"].casefold()!=title["vi"].casefold())
            if doubled and not locked:
                result.append({"id":item["id"],"reason":"redundant_retained_vocative"});break
        # Only the observed whole-word, expressive わ・た・し failure. Printed
        # stretching can hide a generic tôi from a plain word-boundary check.
        # Do not rewrite prose or apply this to unknown, reverse, quoted roles.
        if pair and whole_expressive_self(region["ja"]):
            single=unpace_single_term(target)
            known={"tôi","tớ","tao","mình","ta","em","chị","anh","con","cháu","cô","chú","ông","bà"}
            if single in known and single!=unpace_single_term(pair["self"]):
                result.append({"id":item["id"],"reason":"directed_expressive_self_conflict"})
        # A narrow, observed role reversal: 先に帰ってて is a request to the
        # listener, not a statement that the speaker goes first. Only reject
        # the confirmed speaker's self-term in that exact imperative slot.
        # Unknown roles, quoted narrative and coincident self/address forms
        # remain outside this guard; it is not a general parser of Japanese.
        if pair and pair["self"]!=pair["address"] and re.match(
                VOCATIVE_START+r"先に帰って(?:て|ください|くれ)[。！!？?]",region["ja"]) and re.match(
                r'^[\s“「\"]*'+re.escape(pair["self"])+r'\s+(?:(?:hãy|cứ)\s+)?(?:về|đi)\s+trước\b',target,re.I):
            result.append({"id":item["id"],"reason":"directed_request_role_conflict"})
        # Same observed utterance, different failure: a confirmed chị/em pair
        # silently reverts to a generic first-person in the speaker's promise.
        # Never rewrite unknown/quoted speech, or an unconventional user lock.
        if pair and re.fullmatch(REQUEST_THEN_PROMISE,region["ja"].strip()):
            alternatives={"tôi","tớ","tao","mình"}-{pair["self"].casefold(),pair["address"].casefold()}
            if any(re.search(r'(?<!\w)'+re.escape(pronoun)+r'\s+(?:(?:sẽ|cũng)\s+)?(?:đến|tới|qua|về|đi)\b',target,re.I)
                   for pronoun in alternatives):
                result.append({"id":item["id"],"reason":"directed_self_term_conflict"})
        # Another high-precision sibling regression: in ``わかった。待ってるね``
        # the implicit subject of "wait" is the confirmed speaker. Reject only
        # the inverted Vietnamese shape (listener/address as subject waiting
        # for speaker/self). Explicit Japanese subjects, quoted narration and
        # imperative wait requests are intentionally excluded by the helper.
        if pair and implicit_waiting_source(region["ja"]) and reversed_waiting_output(target,pair):
            result.append({"id":item["id"],"reason":"directed_wait_role_conflict"})
        # High-precision observed error only: a retained neutral title followed
        # by a gendered second-person subject. Do not treat narrative siblings
        # ("anh trai tôi") as address or override a confirmed directed rule.
        if pair is None:
            for title in explicit_address(context,[region]):
                if title["ja"] not in ("先輩","先生"):continue
                # A slash is not evidence-based address: the observed cloud
                # output left an editorial choice inside the dialogue. Keep
                # this narrow to neutral source vocatives, and allow explicit
                # source kinship alternatives (e.g. brother or sister).
                if not re.search(r"兄|姉|弟|妹",region["ja"]) and re.search(
                        r'^[\s「『“"]*'+re.escape(title["vi"])+
                        r'\s*[,，:：]\s*\(?\s*(?:anh|chị|cô|chú|ông|bà|em)\s*'
                        r'(?:/|hoặc)\s*(?:anh|chị|cô|chú|ông|bà|em)\s*\)?\s+'
                        r'(?:có|giúp|cho|hãy|đừng|làm|đã|đang|sẽ)\b',target,re.I):
                    result.append({"id":item["id"],"reason":"unresolved_address_placeholder"});break
                if re.search(
                        r'(?<!\w)'+re.escape(title["vi"])+r'\s*[,，:：]\s*(?:anh|chị|cô|chú|ông|bà)\s+(?:có|giúp|cho|hãy|đừng|làm|đã|đang|sẽ)\b',target,re.I):
                    result.append({"id":item["id"],"reason":"unconfirmed_gendered_address"});break
        for match in known_address_matches(context,region):
            if not match["suffix"] and re.search(re.escape(match["form"]["reading"])+
                    r'\s*-(?:san|kun|chan|sama|dono|senpai|sensei)\b',target,re.I):
                result.append({"id":item["id"],"reason":"added_name_suffix"})
            if match["form"]["role"]!="full":
                for full in match["name"]["forms"]:
                    if full["role"]=="full" and full["ja"] not in region["ja"] and re.search(
                            r'(?<!\w)'+re.escape(full["reading"])+r'(?!\w)',target,re.I):
                        result.append({"id":item["id"],"reason":"expanded_source_name"})
    return result


def explicit_address(context,regions):
    """Verifiable source-present vocatives; not a speaker/family inference."""
    selected=style_values(context);rules=[]
    for region in regions:
        source=region["ja"]
        # OCR may retain (or hallucinate) an opening quote. Match through it
        # without changing the evidence or treating narrative kinship as address.
        vocative_start=VOCATIVE_START
        if selected["kinship"]=="preserve":
            for ja,vi in SIBLING_VOCATIVES.items():
                # A whole call can lose punctuation during OCR. Permit only
                # the exact standalone title (optionally quoted), never a
                # title followed by narrative syntax such as 姉ちゃんは….
                if re.match(vocative_start+re.escape(ja)+r'(?:[、,，！!？?…]|[」』”"]?\s*$)',source):
                    rules.append({"id":region["id"],"ja":ja,"vi":vi});break
        if selected["honorifics"]=="preserve":
            for ja,vi in [("先輩","senpai"),("先生","sensei")]:
                if re.match(vocative_start+ja+r"[、,，！!？?…]",source):rules.append({"id":region["id"],"ja":ja,"vi":vi})
        rules.extend({"id":region["id"],"ja":match["ja"],"vi":match["vi"]}
                     for match in known_address_matches(context,region))
    return rules


def compact_policy(context):
    selected=style_values(context)
    return "\n".join(["Preserve source family/given name and use confirmed readings. Do not add suffixes or invented pronouns.",
        "Senpai/sensei do not establish gender. Do not add anh/chi/em without a confirmed speaker/listener rule or explicit source kinship.",
        "Unknown address: omit pronouns naturally, never leave anh/chị alternatives unless the source expresses that choice.",
        "Honorifics: "+HONORIFIC_MODES[selected["honorifics"]],
        "Sibling vocatives: "+KINSHIP_MODES[selected["kinship"]],
        "Terminology: "+STYLE_PRESETS[selected["naming"]]])

def voice_record(speaker,listener,self_term,address_term,register="natural"):
    speaker,listener=identifier(speaker),identifier(listener)
    require(speaker!="unknown" and listener!="unknown" and speaker!=listener,"VOICE","Cần hai ID nhân vật đã xác nhận.")
    require(register in ("natural","polite","rough","archaic"))
    return {"speaker":speaker,"listener":listener,"self":text(self_term,40),"address":text(address_term,40),"register":register}

def confirmed_rules(context,regions):
    pairs={(r.get("speaker"),r.get("listener")) for r in regions}
    result=[]
    for row in context.get("characters",[]):
        if row.get("kind")!="relationship" or not row.get("confirmed"):continue
        try:rule=json.loads(row["value"])
        except (ValueError,TypeError):continue
        if isinstance(rule,dict) and (rule.get("speaker"),rule.get("listener")) in pairs:
            try:checked=voice_record(rule["speaker"],rule["listener"],rule["self"],rule["address"],rule.get("register","natural"))
            except (AppError,KeyError,TypeError,ValueError):continue
            result.append(checked)
    return result
