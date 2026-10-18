"""Source-backed speech delivery, not voice acting inferred from artwork.

Printed punctuation is evidence. Tokenizer spaces, ordinary long vowels,
physical line wraps and Japanese glyph size are not. Keep source text intact;
formatting never guesses a speaker or changes remembered plot facts.
"""
import hashlib
import re
import unicodedata
from .errors import require

EXPRESSION_VERSION = 1
KANA = r"ぁ-ゖァ-ヺ"
SEGMENTED_KANA = re.compile(r"(?<!["+KANA+r"])["+KANA+r"](?:[・·･\-‐‑]["+KANA+r"]){2,}(?!["+KANA+r"])")
SPELLED = re.compile(r"(?<![A-Za-z])[A-Za-z](?:[ \t・·\-‐‑]+[A-Za-z]){2,}(?![A-Za-z])")
ROMAJI_RUN = re.compile(r"(?<![A-Za-z])[A-Za-z]{1,3}(?:[\-‐‑][A-Za-z]{1,3}){2,}(?![A-Za-z])")
ROMAJI_SYLLABLE = re.compile(r"(?:[aiueon]|(?:[kstnhmrgbpdzjwyf]|[kstnhmrgbpdzj]y)?[aiueo]|shi|chi|tsu|fu|sha|shu|sho|cha|chu|cho)", re.I)
PAUSE = re.compile(r"…+|\.{3,}|・{2,}")
STUTTER = re.compile(r"(["+KANA+r"])[、,]\s*\1|([A-Za-z])[\-‐‑]\2", re.I)
SOURCE_STRETCH = re.compile(r"ー{2,}|(?<=["+KANA+r"])[〜～~]+|(?<=[A-Za-z])[〜～~]+(?=[!?。…\s]|$)|([あいうえおぁぃぅぇぉアイウエオァィゥェォ])\1{2,}")
TARGET_STRETCH = re.compile(r"[〜～~]|([aeiouyàáâãèéêìíòóôõùúýăĩũơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ])\1{2,}", re.I)
TARGET_HELD_VOWEL = re.compile(r"([aeiouyàáâãèéêìíòóôõùúýăĩũơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ])(?:—|–|…|\.{3,})\s*\1",re.I)
TARGET_SPELLED = re.compile(r"(?<!\w)[^\W\d_](?:[ \t・·\-‐‑]+[^\W\d_]){2,}(?!\w)")
TARGET_SEGMENT = re.compile(r"(?<=\w)[・·\-‐‑](?=\w)")
TARGET_STUTTER = re.compile(r"(?<!\w)([^\W\d_]{1,3})[\-‐‑、,]\s*\1", re.I)


def source_cues(source):
    """Conservative textual cues; no case signal is invented for kana/kanji."""
    value=unicodedata.normalize("NFKC",source)
    cues=[]
    if SPELLED.search(value):cues.append("spelled")
    if SEGMENTED_KANA.search(value) or any(
            all(ROMAJI_SYLLABLE.fullmatch(part) for part in re.split(r"[\-‐‑]",match.group()))
            for match in ROMAJI_RUN.finditer(value)):
        cues.append("segmented")
    if SOURCE_STRETCH.search(value):cues.append("elongated")
    if PAUSE.search(value):cues.append("paused")
    if STUTTER.search(value):cues.append("stutter")
    # A bare acronym (HP, NASA) is not enough to uppercase an entire translation.
    # Only a wholly Latin utterance with phrase/expressive punctuation evidence.
    letters=re.findall(r"[A-Za-z]",value)
    if len(letters)>=3 and all(letter.isupper() for letter in letters) and not re.search(r"["+KANA+r"\u4e00-\u9fff]",value):
        words=re.findall(r"[A-Za-z]+",value)
        if len(words)>=2 or re.search(r"[!?]",value):cues.append("uppercase")
    return cues


def source_expression(region):
    """Recompute from ja; never trust stale/imported/model-supplied metadata."""
    source=region["ja"]
    cues=source_cues(source)
    return {"v":EXPRESSION_VERSION,"sourceHash":hashlib.sha256(source.encode("utf-8")).hexdigest(),"cues":cues} if cues else None


def bind_expression(region):
    result={key:value for key,value in region.items() if key!="expression"}
    expression=source_expression(region)
    if expression:result["expression"]=expression
    return result


def whole_spelling(source):
    value=unicodedata.normalize("NFKC",source).strip()
    match=SPELLED.search(value)
    return bool(match and not re.search(r"\w",value[:match.start()]+value[match.end():]))


def whole_spelled_love_phrase(source):
    """The observed I/you pilot case, not a romance/role inference engine."""
    value=unicodedata.normalize("NFKC",source).strip()
    return bool(whole_spelling(source) and re.fullmatch(
        r"[\sA-Za-z!?…。.・·\-‐‑]+",value) and
        re.sub(r"[\s!?…。.・·\-‐‑]","",value).casefold()=="iloveyou")


def compare_paced_phrase(value):
    """Comparison-only: never change visible wording or the source evidence.

    Local spelling uses single spaces between letters and triple spaces
    between words. Only join a word when every unit is a single letter.
    Plain Vietnamese prose is not concatenated into an unrelated token.
    """
    value=unicodedata.normalize("NFC",value).casefold().strip()
    if re.search(r"\s{2,}",value):
        words=[]
        for word in re.split(r"\s{2,}",value):
            units=re.split(r"\s+",word)
            if len(units)>1 and all(re.fullmatch(r"[^\W\d_][!?…。]*",unit) for unit in units):
                word="".join(units)
            words.append(word)
        value=" ".join(words)
    return re.sub(r"\s+"," ",value)


def whole_expressive_self(source):
    """Only an entire paced watashi, not quoted speech or a clause parser."""
    return whole_expressive_person(source)=="self"


def whole_expressive_person(source):
    if "segmented" not in source_cues(source):return False
    value=unicodedata.normalize("NFKC",source)
    plain=re.sub(r"[\s・·･\-‐‑〜～~ー…!！?？.。]","",value)
    return {"わたし":"self","ワタシ":"self","あなた":"address","アナタ":"address"}.get(plain)


def unpace_single_term(value):
    """Compare one printed pronoun without changing any visible translation."""
    plain=unicodedata.normalize("NFC",value).casefold().strip()
    plain=re.sub(r"[・·\-‐‑〜～~…!！?？.。]","",plain)
    return re.sub(r"(.)\1{1,}",r"\1",plain)


def self_delivery_example(term):
    # Formatting only. The reader's directed lock supplies the word, never a
    # universal first-person example that competes with that lock.
    vowels="aeiouyàáâãèéêìíòóôõùúýăĩũơưạảấầẩẫậắằẳẵặẹẻẽếềểễệỉịọỏốồổỗộớờởỡợụủứừửữựỳỵỷỹ"
    match=re.search("["+vowels+"]",term,re.I)
    if not match:return term
    value=term[:match.end()]+match.group()*2+term[match.end():]
    return value[:1].upper()+value[1:]


def spelled_text(target,protected_values=()):
    """Pure presentation after translation. Never split locked labels/suffixes.

    Unicode NFC keeps Vietnamese tone marks with their letter. Already spelled
    output is left intact; do not repeatedly insert spaces on cache/retry.
    """
    target=unicodedata.normalize("NFC",target)
    if TARGET_SPELLED.search(target):return target
    protected=[re.escape(value) for value in sorted(set(protected_values),key=len,reverse=True) if value]
    # Retained Japanese honorifics are a single cultural/name unit, not letters.
    protected.append(r"[^\W\d_]+-(?:san|kun|chan|sama|dono|senpai|sensei)\b")
    result=[];position=0
    for match in re.finditer("|".join(protected),target,re.I):
        result.append((False,target[position:match.start()]));result.append((True,match.group()))
        position=match.end()
    result.append((False,target[position:]))
    return "".join(value if locked else re.sub(r"[^\W\d_]+",lambda m:" ".join(m.group()),
        re.sub(r"[ \t]+","   ",value)) for locked,value in result)


def expression_guidance(regions,context):
    signals={r["id"]:cues for r in regions if (cues:=source_cues(r["ja"]))}
    if not signals:return ""
    import json
    cues={cue for values in signals.values() for cue in values}
    lines=["[Expressive lettering]\n"+json.dumps(signals,ensure_ascii=False,separators=(",",":"))]
    whole=[r["id"] for r in regions if whole_spelling(r["ja"])]
    if whole:lines.append("Whole spelled phrases in "+json.dumps(whole)+": first join letters mentally to read the original words, then translate their meaning into Vietnamese; never just copy the Latin phrase. Local lettering will separate Vietnamese letters. Do not add words to complete the source. Keep glossary/names intact.")
    from .linguistics import confirmed_rules
    from .terminology import constraints
    pairs={(pair["speaker"],pair["listener"]):pair for pair in confirmed_rules(context,regions)}
    locked=constraints(context,regions)
    for region in regions:
        if whole_spelled_love_phrase(region["ja"]) and (region.get("speaker"),region.get("listener")) not in pairs and not any(
                term["id"]==region["id"] and term["ja"]==region["ja"] for term in locked):
            lines.append("Whole spelled I/you "+json.dumps(region["id"])+
                ": identities/relationship are unconfirmed. I and you carry the source meaning, so use neutral tôi/bạn, not anh/em/chị. Translate the whole love declaration without adding words; local presentation applies spacing/CAPS to the Vietnamese meaning.")
    if "segmented" in cues or any("spelled" in values and identifier not in whole for identifier,values in signals.items()):
        lines.append("Keep deliberate slow delivery, not flattened prose. Split translated sounds or pace fragments naturally, not one Japanese glyph per Vietnamese glyph. Choose the correct words and confirmed self/address FIRST, then pace those words. Never replace a reader-locked pronoun to imitate a formatting example. Preserve names/honorifics and exact glossary.")
        for region in regions:
            pair=pairs.get((region.get("speaker"),region.get("listener")))
            if pair and whole_expressive_self(region["ja"]):
                lines.append("Whole first-person utterance "+json.dumps(region["id"])+": use confirmed self "+
                    json.dumps(pair["self"],ensure_ascii=False)+"; possible source-backed pacing "+
                    json.dumps(self_delivery_example(pair["self"])+"!",ensure_ascii=False)+
                    ". This is the speaker's self, not their address to the listener.")
            elif not pair and whole_expressive_person(region["ja"])=="address":
                lines.append("Whole second-person utterance "+json.dumps(region["id"])+
                    ": no confirmed pair; use neutral bạn, then stretch/pace that word. Do not infer anh/chị/em or add ơi, a location or a new question.")
    if "elongated" in cues:lines.append("Keep expressive stretching of the translated vowel. Do not repeat whole words, add a call, a location or a clause merely to show a held sound. A single Vietnamese syllable may express slow Japanese multi-syllable delivery. Normal Japanese long vowels are not dramatic stretches.")
    if "paused" in cues:lines.append("Keep meaningful internal pauses/ellipsis, not only a normal sentence-final period.")
    if "stutter" in cues:lines.append("Keep source stuttering by repeating the translated initial sound. Formatting example only: ま、まって…! -> Đ-đợi đã…! Translate the actual source, not the example. Do not replace stutters with an unrelated interjection.")
    if "uppercase" in cues:lines.append("Keep whole-utterance UPPERCASE as presentation, including Vietnamese accents. Japanese has no upper/lowercase; do not invent CAPS for it.")
    repairs=context.get("output_repair",[])
    if isinstance(repairs,list) and any(str(row.get("reason","")).startswith("lost_source_") for row in repairs if isinstance(row,dict)):
        lines.append("Repair: the previous text lost source-backed delivery. Restore the indicated rhythm without adding words, inventing emotions or changing the meaning.")
    return "\n"+"\n".join(lines)


def output_expression_issues(source,target,protected_values=()):
    """Only catch absent printed signals, never pretend to grade emotion/meaning."""
    if target.casefold() in {value.casefold() for value in protected_values}:return []
    cues=source_cues(source)
    value=spelled_text(target,protected_values) if whole_spelling(source) else unicodedata.normalize("NFC",target)
    # Vietnamese may reduce several Japanese syllables to one; an explicit
    # stretched sound then carries slow delivery without inventing syllables.
    stretched=bool(TARGET_STRETCH.search(value) or TARGET_HELD_VOWEL.search(value))
    paced=bool(TARGET_SPELLED.search(value) or TARGET_SEGMENT.search(value) or stretched
               or re.search(r"\S[ \t]{2,}\S",value) or len(PAUSE.findall(value))>=2)
    issues=[]
    if ("segmented" in cues or "spelled" in cues) and not paced:issues.append("lost_source_segmentation")
    if "elongated" in cues and not stretched:issues.append("lost_source_elongation")
    if "paused" in cues and not PAUSE.search(value):issues.append("lost_source_pause")
    if "stutter" in cues and not TARGET_STUTTER.search(value):issues.append("lost_source_stutter")
    return issues


def present_items(regions,items,exact_terms=()):
    """Case/spelling are local presentation, not another AI request or new lore."""
    sources={r["id"]:r for r in regions}
    result=[]
    for item in items:
        source=sources[item["id"]]["ja"];value=item["vi"]
        protected=[term["vi"] for term in exact_terms if term["id"]==item["id"]]
        if whole_spelling(source):value=spelled_text(value,protected)
        if "uppercase" in source_cues(source):value=value.upper()
        require(len(value)<=5000,"MODEL_OUTPUT",
                "Model trả lời quá dài cho đoạn dịch; nguyên bản được giữ lại. Thử dịch lại hoặc chỉnh OCR.")
        result.append({**item,"vi":value} if value!=item["vi"] else item)
    return result
