"""Validate private context backups without coercion or database side effects."""
import json
import re
from .errors import require
from .validation import identifier, location, number, text, MAX_CONTEXT_PACK_BYTES


def flag(value):
    # SQLite exports 0/1; strings such as "false" are never confirmations.
    require(type(value) is bool or (type(value) is int and value in (0, 1)), "CONTEXT_PACK")
    return bool(value)


def exact_text(value, limit, empty=False):
    text(value, limit, empty=empty)
    return value  # A private backup must not silently trim previously stored text.


def json_value(value):
    if isinstance(value, str):
        try: return json.loads(value)
        except (ValueError, RecursionError): require(False, "CONTEXT_PACK")
    return value


def root_source(value):
    value = json_value(value)
    for _ in range(24):
        require(isinstance(value, dict), "EVIDENCE")
        if value.get("type") != "context-pack":
            require(value.get("type") in ("user", "dialogue", "metadata"), "EVIDENCE")
            return value
        value = value.get("original")
    require(False, "EVIDENCE", "Nguồn context lồng quá sâu; không tự coi là dữ kiện đã xác nhận.")


def source(value):
    result = {"type": "context-pack", "original": root_source(value)}
    require(len(json.dumps(result, ensure_ascii=False)) < 10000, "EVIDENCE")
    return result


def aliases(value):
    value = json_value(value)
    require(isinstance(value, list) and len(value) <= 30, "CONTEXT_PACK")
    return list(dict.fromkeys(text(item, 299) for item in value))


def metadata(value):
    value = json_value(value)
    require(isinstance(value, dict) and len(json.dumps(value, ensure_ascii=False)) < 8000, "CONTEXT_PACK")
    if not value: return value
    require(set(value) <= {"qid", "label", "aliases", "source", "license", "scope"}, "CONTEXT_PACK")
    require(isinstance(value.get("qid"), str) and re.fullmatch(r"Q\d{1,12}", value["qid"]), "CONTEXT_PACK")
    for field in ("label", "source", "license", "scope"):
        if field in value: text(value[field], 600)
    if "scope" in value: require(value["scope"] == "identity-only", "CONTEXT_PACK")
    if "aliases" in value: aliases(value["aliases"])
    return value


def validate_pack(pack):
    require(isinstance(pack, dict) and type(pack.get("schema")) is int and pack["schema"] == 1, "CONTEXT_PACK")
    try: encoded = json.dumps(pack, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, RecursionError): require(False, "CONTEXT_PACK")
    require(len(encoded.encode("utf-8")) <= MAX_CONTEXT_PACK_BYTES, "CONTEXT_SIZE")
    meta = pack.get("story")
    require(isinstance(meta, dict), "CONTEXT_PACK")
    profile = {"id": identifier(meta.get("id")), "title": exact_text(meta.get("title"), 300)}
    if "genre" in meta: profile["genre"] = exact_text(meta["genre"], 150, empty=True)
    if "aliases" in meta: profile["aliases"] = aliases(meta["aliases"])
    if "metadata" in meta: profile["metadata"] = metadata(meta["metadata"])
    require(isinstance(pack.get("facts"), list) and len(pack["facts"]) <= 20000, "CONTEXT_PACK")
    require(isinstance(pack.get("summaries"), list) and len(pack["summaries"]) <= 10000, "CONTEXT_PACK")
    facts, summaries = [], []
    for records, output, is_summary in ((pack["facts"], facts, False), (pack["summaries"], summaries, True)):
        ids = set()
        for record in records:
            require(isinstance(record, dict), "CONTEXT_PACK")
            item = {"source": source(record.get("source"))}
            if "id" in record:
                item["id"] = identifier(record["id"])
                require(item["id"] not in ids, "CONTEXT_PACK"); ids.add(item["id"])
            if "valid" in record: require(flag(record["valid"]), "CONTEXT_PACK")
            if is_summary:
                start, end = number(record.get("chapter_start")), number(record.get("chapter_end"))
                require(start <= end, "CONTEXT_PACK")
                at = location({"chapter": end, "page": record.get("page_end")})
                kind = record.get("kind", "recap")
                require(kind in ("chapter", "group", "recap"), "CONTEXT_PACK")
                item.update(chapter_start=start, chapter_end=end, page_end=at["page"], kind=kind,
                            text=exact_text(record.get("text"), 6000), complete=flag(record.get("complete")))
                if kind == "group":
                    refs = root_source(item["source"]).get("summary_ids")
                    require(item["complete"] and isinstance(refs, list) and refs and len(refs) <= 1000, "EVIDENCE")
                    for ref in refs: identifier(ref)
            else:
                kind = record.get("kind")
                require(kind in ("character", "relationship", "glossary", "event", "note", "style"), "CONTEXT_PACK")
                at = location({"chapter": record.get("chapter"), "page": record.get("page")})
                item.update(kind=kind, key=exact_text(record.get("key"), 160), value=exact_text(record.get("value"), 1500),
                            chapter=at["chapter"], page=at["page"], confirmed=flag(record.get("confirmed")),
                            locked=flag(record.get("locked")))
            output.append(item)
    progress = None
    if pack.get("progress") is not None:
        value = pack["progress"]; require(isinstance(value, dict), "CONTEXT_PACK")
        at = location({"chapter": value.get("last_chapter"), "page": value.get("last_page")})
        furthest = number(value.get("furthest_chapter"))
        require(furthest >= at["chapter"], "CONTEXT_PACK")
        progress = {"last_chapter": at["chapter"], "last_page": at["page"], "furthest_chapter": furthest}
    return {"story": profile, "facts": facts, "summaries": summaries, "progress": progress}
