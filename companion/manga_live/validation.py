import json
import math
import re
from .errors import require
from .punctuation import output_punctuation_issues
from .expression import output_expression_issues

ID = re.compile(r"^[\w.:-]{1,128}$", re.ASCII)
MAX_CONTEXT_PACK_BYTES = 16 * 1024 * 1024


def identifier(value):
    require(isinstance(value, str) and bool(ID.fullmatch(value)))
    return value


def text(value, limit=4000, empty=False):
    require(isinstance(value, str) and len(value) <= limit and (empty or bool(value.strip())))
    return value.strip()


def number(value, minimum=0, maximum=1000000):
    require(isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and minimum <= value <= maximum)
    return value


def location(value):
    require(isinstance(value, dict))
    require(type(value.get("page")) is int)
    return {"chapter": number(value.get("chapter")), "page": number(value.get("page"), maximum=100000)}


def translation_items(raw, ids):
    """Fail closed: an invalid/missing ID can never be overlaid on another bubble."""
    require(isinstance(raw, dict) and isinstance(raw.get("items"), list), "MODEL_FORMAT", "Model trả kết quả sai cấu trúc.")
    items = raw["items"]
    require(len(items) == len(ids), "MODEL_FORMAT", "Model trả thiếu hoặc thừa đoạn dịch.")
    require({i.get("id") for i in items if isinstance(i, dict)} == set(ids), "MODEL_FORMAT", "ID bản dịch không khớp.")
    checked = []
    for item in items:
        require(isinstance(item, dict) and isinstance(item.get("ambiguous", False), bool), "MODEL_FORMAT")
        checked.append({"id": identifier(item["id"]), "vi": text(item.get("vi"), 5000),
                        "ambiguous": item.get("ambiguous", False)})
    return sorted(checked, key=lambda i: ids.index(i["id"]))


def translation_output_issues(regions,items,exact_terms=()):
    """Narrow structural checks, not an automatic semantic quality score."""
    sources={region["id"]:region for region in regions};issues=[]
    normalize=lambda value:re.sub(r"\s+","",value).strip('「」『』“”"')
    for item in items:
        region=sources[item["id"]];source,target=region["ja"],item["vi"]
        protected=[term["vi"] for term in exact_terms if term["id"]==item["id"]]
        # Valid JSON and matching IDs are insufficient: a whole sentence
        # reduced to a quotation mark is still missing dialogue. Keep actual
        # punctuation-only source and exact reader-locked symbolic labels.
        if (any(char.isalnum() for char in source) and not any(char.isalnum() for char in target)
                and not any(target.casefold()==value.casefold() for value in protected)):
            issues.append({"id":item["id"],"reason":"missing_translation_text"})
        issues.extend({"id":item["id"],"reason":reason}
                      for reason in output_punctuation_issues(source,target,protected))
        issues.extend({"id":item["id"],"reason":reason}
                      for reason in output_expression_issues(source,target,protected))
        # Bare names and SFX may legitimately stay Japanese. A complete long
        # sentence copied verbatim is not a usable Vietnamese translation.
        if region.get("type","dialogue")!="sfx" and len(re.findall(r"[\u3040-\u30ff\u4e00-\u9fff]",source))>=6 and re.search(r"[。！？!?]",source) and normalize(source)==normalize(target):
            issues.append({"id":item["id"],"reason":"untranslated_sentence"})
        marker=r"}\s*(?:翻译为|翻譯為|translation|translated(?:\s+JSON)?)\s*[：:]\s*{"
        if re.search(marker,target,re.I) and not re.search(marker,source,re.I):
            issues.append({"id":item["id"],"reason":"serialization_commentary"})
    return issues


def parse_model_json(raw):
    require(isinstance(raw, str) and len(raw) < 200000, "MODEL_FORMAT")
    # Remove a provider's outer reasoning wrapper, never matching text inside
    # an already serialized dialogue value. Source data may contain such tags.
    raw = re.sub(r"^\s*<think>.*?</think>\s*", "", raw, count=1, flags=re.S).strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        require(False, "MODEL_FORMAT", "Model không trả JSON hợp lệ. Có thể dịch lại từng bóng.")
