"""Text-only checkpoints for completed groups, never a completed/read page.

The key binds the full current source/context, not an ordinal region ID or a
new context snapshot manufactured after generation. Existing cache TTL/quota
and reader invalidation apply. No prompts, pixels, patches or usage survive.
"""
from .errors import AppError
from .memory import digest
from .validation import translation_items, translation_output_issues
from .linguistics import address_output_issues
from .terminology import constraints, missing_terms, grounded_proposals
from .text_scope import story_regions

BATCH_CACHE_VERSION = "accepted-translation-group-v1"


def batch_key(page_key, regions, context):
    # page_key already includes source bytes, story/page/cutoff, engine/model
    # signature and prompt/layout/routing versions. Include the exact group
    # and its preceding dialogue too, so changing grouping cannot mix voices.
    return digest([BATCH_CACHE_VERSION, page_key, regions, context])


def batch_payload(regions, context, items, terms=()):
    """Recheck the same narrow output gates; a bad cache entry is just a miss.

    This is not semantic certification. Reconstruct only validated text and
    grounded proposals; never persist arbitrary fields from a model/event.
    """
    try:
        checked = translation_items({"items": items}, [r["id"] for r in regions])
        exact = constraints(context, regions)
        if (missing_terms(context, regions, checked) or
                translation_output_issues(regions, checked, exact) or
                address_output_issues(context, regions, checked)):
            return None
        trusted_ids = {r["id"] for r in story_regions(regions)}
        proposals = [term for term in grounded_proposals({"terms": list(terms)}, regions, checked)
                     if term["region_id"] in trusted_ids]
        return {"v": BATCH_CACHE_VERSION, "items": checked, "terms": proposals}
    except (AppError, TypeError, ValueError, KeyError):
        return None


def cached_batch(payload, regions, context):
    if not isinstance(payload, dict) or payload.get("v") != BATCH_CACHE_VERSION:
        return None
    return batch_payload(regions, context, payload.get("items"), payload.get("terms", []))


def read_batch(memory, key, regions, context):
    try:
        return cached_batch(memory.cache_get(key), regions, context)
    except (TypeError, ValueError):
        # JSON corruption in an optional checkpoint is a cache miss, not a
        # failed reading session. Genuine SQLite/storage errors still surface.
        return None
