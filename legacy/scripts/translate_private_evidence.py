"""Explicitly consented text-only pilot on provenance-checked local OCR.

Not installed/imported by the extension. No fresh OCR, Native Messaging,
context inference, image upload or source-label substitution. The output is
private text/metrics for the rendering replay; no raster is persisted.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion"), str(ROOT / "scripts")]
from benchmark import DirectoryDataset, audit, dataset_fingerprint
from benchmark_cloud import BudgetLedger, budget_plan, bounded_request
from manga_live.config import Config, Secrets
from manga_live.errors import AppError
from manga_live.prompts import PROMPT_VERSION
import manga_live.providers as providers

MODEL = "deepseek/deepseek-v4.1-flash"
PRIVATE_MAX_OUTPUT_TOKENS = 220


class EphemeralKey:
    """One-shot key adapter; unlike Secrets, it has no persistence methods."""
    def __init__(self, value): self.value = value
    def get(self, provider): return self.value


def bounded_private_request(body, ceilings):
    messages = body.get("messages")
    if (body.get("model") != MODEL or body.get("provider", {}).get("data_collection") != "deny"
            or body.get("tools") or not isinstance(messages, list) or not messages
            or any(not isinstance(m, dict) or not isinstance(m.get("content"), str) for m in messages)):
        raise AppError("TEST_PRIVACY", "Private pilot only permits text messages without tools/data-collection routes")
    return bounded_request(body, ceilings, max_tokens=PRIVATE_MAX_OUTPUT_TOKENS)


def checked_page(evidence, fingerprint, page_id, size):
    if evidence.get("input_fingerprint_sha256") != fingerprint or evidence.get("cloud") is not False:
        raise ValueError("OCR evidence and dataset differ, or source is not local")
    matches = [p for p in evidence.get("pages", []) if p.get("page") == page_id]
    if len(matches) != 1: raise ValueError("Exactly one eligible source page is required")
    regions = deepcopy(matches[0]["regions"])
    if not 1 <= len(regions) <= 6 or len({r["id"] for r in regions}) != len(regions):
        raise ValueError("Pilot requires one complete page of 1..6 unique regions, not selected gold crops")
    width, height = size
    for r in regions:
        box = r.get("bbox")
        if (not isinstance(box, list) or len(box) != 4 or any(type(v) is not int for v in box)
                or min(box[:2]) < 0 or min(box[2:]) <= 0
                or box[0]+box[2] > width or box[1]+box[3] > height
                or not isinstance(r.get("ja"), str) or not 0 < len(r["ja"]) <= 290
                or r.get("scope", {}).get("action") == "defer"):
            raise ValueError("Malformed or incomplete source regions")
        if "vi" in r: raise ValueError("OCR source already has translations")
        r.update(speaker="unknown", listener="unknown", type="dialogue")
    return regions


def run(args):
    if not args.consent or type(args.budget) not in (int, float) or not 0 < args.budget <= .01:
        raise ValueError("Explicit private text consent and budget <=0.01 USD are required")
    source_path, output = [Path(p).resolve() for p in (args.evidence, args.output)]
    if any(p.parent != ROOT/"artifacts" for p in (source_path, output)) or source_path == output:
        raise ValueError("Private text evidence must be separate files directly in gitignored artifacts")
    if source_path.stat().st_size > 16*1024*1024: raise ValueError("Oversized source evidence")
    evidence = json.loads(source_path.read_text(encoding="utf-8"))
    with DirectoryDataset(args.folder) as source:
        _, _, pages = audit(source); fingerprint = dataset_fingerprint(source)
    selected = [image for page, image, _ in pages if page["page_id"] == args.page]
    if len(selected) != 1: raise ValueError("Excluded or missing selected source page")
    image = selected[0]
    regions = checked_page(evidence, fingerprint, args.page, image.size)
    # No label/reference text, private metadata search, genre or guessed character
    # identity enters the request. Known OCR errors remain visible as evidence.
    context = {}
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        catalog = {m["id"]: m for m in json.load(response)["data"]}
    estimate, ceilings = budget_plan([MODEL], catalog, 1, [{"regions": regions, "context": context}],
        completion_tokens=PRIVATE_MAX_OUTPUT_TOKENS)
    print(json.dumps({"model": MODEL, "preflight_estimate_usd": estimate,
        "budget_usd": args.budget, "region_count": len(regions), "image_upload": False}), flush=True)
    if estimate > args.budget: raise ValueError("Worst-case reservation exceeds the authorized budget")
    if args.plan_only: return
    config = Config(ROOT/"artifacts/private-cloud-profile")
    config.update({"mode": "byok", "provider": "openrouter", "openrouterModel": MODEL,
        "cloudConsent": True, "metadataConsent": False, "autoSummary": False})
    if args.stdin_key:
        key = sys.stdin.readline().strip()
        if len(key) < 12: raise ValueError("No ephemeral test key supplied")
        vault = EphemeralKey(key)
    else:
        key = ""
        vault = Secrets("benchmark-openrouter")
    translator = providers.Translator(config, vault, ROOT/"models", ROOT/"runtime/llama")
    ledger = BudgetLedger(args.budget); attempts = []
    base_post = providers.post_json
    report = {"schema": 1, "privateTest": True, "privatePage": args.page,
        "source_evidence": source_path.name, "input_fingerprint_sha256": fingerprint,
        "cloud": True, "textOnly": True, "imagePersistence": False, "nativeTransport": False,
        "freshOcr": False, "freshTranslation": True, "context": "empty; unknown speakers; no lookup",
        "model": MODEL, "prompt_version": PROMPT_VERSION, "preflight_estimate_usd": estimate,
        "budget_usd": args.budget, "attempts": attempts, "runs": [],
        "limitations": ["Recorded actual OCR, fresh text translation, NOT a new complete native/browser inference run.",
            "Unaudited source transcription and no Vietnamese/clean-background gold; guards do not grade meaning.",
            "This comparator is not the production detector. OCR errors remain and are not corrected from labels."]}
    def save():
        report.update(reserved_usd=ledger.reserved,
            reported_cost_usd=sum(a.get("reported_cost_usd") or 0 for a in attempts))
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    def bounded_post(url, body, *rest, **kwargs):
        if url != "https://openrouter.ai/api/v1/chat/completions" or body.get("model") != MODEL:
            raise AppError("TEST_ENDPOINT", "Only the explicitly selected text endpoint is allowed")
        body = bounded_private_request(body, ceilings)
        amount = ledger.reserve(body)
        entry = {"number": ledger.calls, "reserved_usd": amount, "state": "attempted",
            "request_sha256": hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
        attempts.append(entry); save()
        try:
            result = base_post(url, body, *rest, **kwargs)
            usage = result.get("usage", {})
            entry.update(state="response", provider=result.get("provider"),
                reported_cost_usd=usage.get("cost"), input_tokens=usage.get("prompt_tokens"), output_tokens=usage.get("completion_tokens"))
            return result
        except AppError as error:
            entry.update(state="failed", error=error.code); raise
        finally: save()
    providers.post_json = bounded_post
    started = time.perf_counter()
    try:
        items, metrics = translator.translate(regions, context, threading.Event())
        by_id = {r["id"]: r for r in items}
        if set(by_id) != {r["id"] for r in regions}: raise ValueError("Translation ID mismatch")
        translated = [{**r, **by_id[r["id"]]} for r in regions]
        report["runs"].append({"native": {"width": image.width, "height": image.height,
            "regions": translated, "metrics": metrics}, "elapsed_ms": (time.perf_counter()-started)*1000})
        report["passed_output_contract"] = True
    except AppError as error:
        report.update(passed_output_contract=False, error=error.code)
        raise
    finally:
        providers.post_json = base_post; translator.stop(); key = ""; save()
    print(json.dumps({"passed_output_contract": True, "requests": ledger.calls,
        "reserved_usd": ledger.reserved, "reported_cost_usd": report["reported_cost_usd"],
        "translation_ms": report["runs"][0]["elapsed_ms"], "output": str(output)}), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--folder", required=True); parser.add_argument("--page", required=True)
    parser.add_argument("--evidence", required=True); parser.add_argument("--output", required=True)
    parser.add_argument("--consent", action="store_true"); parser.add_argument("--plan-only", action="store_true")
    parser.add_argument("--stdin-key", action="store_true", help="Read one ephemeral key from stdin; never write it to Vault")
    parser.add_argument("--budget", type=float, default=.01)
    run(parser.parse_args())
