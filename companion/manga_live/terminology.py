"""Canonical naming is separate from plot facts and character address.

An alias is never guessed to be the same entity. User-confirmed alternate
labels may intentionally have different Vietnamese forms (e.g. an epithet).
"""
import json
import re
import unicodedata
from .linguistics import explicit_address
from .errors import AppError, require
from .validation import identifier, text

CATEGORIES = ("guild", "organization", "weapon", "skill", "item", "place", "epithet", "other")


def term_record(entity, category, ja, vi, aliases=(), origin="user"):
    entity = identifier(entity)
    require(category in CATEGORIES and origin in ("user", "auto"), "TERM")
    ja, vi = text(ja, 100), text(vi, 120)
    require(len(ja) >= 2, "TERM", "Cần tên cụ thể, không khóa một ký tự chung.")
    require(isinstance(aliases, (list, tuple)) and len(aliases) <= 8, "TERM")
    checked, seen = [], {ja}
    for alias in aliases:
        require(isinstance(alias, dict), "TERM")
        source, target = text(alias.get("ja"), 100), text(alias.get("vi", vi), 120)
        require(len(source) >= 2 and source not in seen, "TERM")
        seen.add(source)
        checked.append({"ja": source, "vi": target})
    return {"type": "canonical-term", "entity": entity, "category": category,
            "ja": ja, "vi": vi, "aliases": checked, "origin": origin}


def terms_in_context(context):
    result = []
    for row in context.get("glossary", []):
        try:
            value = json.loads(row.get("value", ""))
            if isinstance(value, dict) and value.get("type") == "canonical-term":
                result.append(term_record(value["entity"], value["category"], value["ja"],
                                          value["vi"], value.get("aliases", []), value.get("origin", "user")))
        except (AppError, ValueError, KeyError, TypeError):
            pass
    return result


def constraints(context, regions):
    address = explicit_address(context,regions)
    result,coverage = [],{}
    for term in terms_in_context(context):
        # Longest match first prevents applying both a full and shortened alias
        # at the same character positions. No ungrounded string replacement.
        forms = sorted([{"ja": term["ja"], "vi": term["vi"]}, *term["aliases"]],
                       key=lambda f: len(f["ja"]), reverse=True)
        for region in regions:
            covered = set()
            for form in forms:
                start = 0
                while (pos := region["ja"].find(form["ja"], start)) >= 0:
                    span = set(range(pos, pos + len(form["ja"])))
                    if not covered.intersection(span):
                        constraint = {"id": region["id"], **form}
                        if constraint not in result:
                            result.append(constraint)
                        covered.update(span)
                        coverage.setdefault(region["id"],set()).update(span)
                    start = pos + len(form["ja"])
    # A canonical named item may contain a character's name. The whole item's
    # confirmed label wins there; do not demand both its embedded address
    # and the weapon name when the reader explicitly chose that label.
    for rule in address:
        source=next(r["ja"] for r in regions if r["id"]==rule["id"])
        spans=[set(range(m.start(),m.end())) for m in re.finditer(re.escape(rule["ja"]),source)]
        if any(not span.intersection(coverage.get(rule["id"],set())) for span in spans):
            result.append(rule)
    return result


def missing_terms(context, regions, items):
    by_id = {item["id"]: unicodedata.normalize("NFKC", item["vi"]).casefold() for item in items}
    return [term for term in constraints(context, regions)
            if unicodedata.normalize("NFKC", term["vi"]).casefold() not in by_id.get(term["id"], "")]


def suggestions(context, regions):
    result=[]
    for row in context.get("glossary", []):
        if row.get("confirmed"):continue
        for record in terms_in_context({"glossary":[row]}):
            matches=[r["id"] for r in regions if record["ja"] in r["ja"]]
            if matches:result.append({**record,"region_ids":matches})
    return result


def grounded_proposals(raw, regions, items):
    """Malformed/ungrounded optional proposals are ignored, never ruin dialogue."""
    proposals = raw.get("terms", []) if isinstance(raw, dict) else []
    if not isinstance(proposals, list) or len(proposals) > 6:
        return []
    sources, targets = {r["id"]: r["ja"] for r in regions}, {r["id"]: r["vi"] for r in items}
    result = []
    for proposal in proposals:
        try:
            require(isinstance(proposal, dict) and proposal.get("category") in CATEGORIES, "TERM")
            source, target = text(proposal.get("ja"), 100), text(proposal.get("vi"), 120)
            evidence = proposal.get("region_id")
            require(len(source) >= 2 and source in sources.get(evidence, "") and target in targets.get(evidence, ""), "EVIDENCE")
            require(any('\u3040' <= c <= '\u9fff' for c in source), "TERM")
            result.append({"ja": source, "vi": target, "category": proposal["category"], "region_id": evidence})
        except (AppError, TypeError):
            continue
    return result
