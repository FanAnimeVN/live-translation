"""Image-authorized native QA only; never installed or used by text-only QA."""
import base64
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from qa_native_entry import diagnostic_folder
from qa_cloud_entry import require_text_only, validated_options
from benchmark_cloud import BudgetLedger, bounded_request
from benchmark_cloud_ocr import ImageBudget, session_reserved
from manga_live import vision_ocr
from manga_live.cloud_ocr import MODEL
from manga_live.config import Secrets
from manga_live.errors import AppError
from manga_live.ocr import decode_image


def require_crop_request(body):
    if body.get("model") != MODEL or any(k in body for k in ("tools", "models", "plugins")):
        raise ValueError("Only the reviewed crop model, no tools/fallback")
    messages = body.get("messages")
    if not isinstance(messages, list) or len(messages) != 1 or messages[0].get("role") != "user":
        raise ValueError("Invalid image message")
    parts = messages[0].get("content")
    if not isinstance(parts, list) or not 3 <= len(parts) <= 9:
        raise ValueError("Invalid crop body")
    count = 0
    for part in parts:
        if not isinstance(part, dict): raise ValueError("Invalid crop part")
        if part.get("type") == "text":
            if set(part) != {"type", "text"} or not isinstance(part["text"], str) or len(part["text"]) > 6000 or "data:image" in part["text"]:
                raise ValueError("Invalid OCR instruction/ID")
        elif part.get("type") == "image_url":
            info = part.get("image_url", {})
            url = info.get("url", "")
            if not isinstance(url, str) or not url.startswith("data:image/png;base64,") or len(url) > 2800000:
                raise ValueError("Only bounded embedded PNG, not remote URLs")
            raw = base64.b64decode(url[22:], validate=True)
            image = decode_image(raw)
            if len(raw) > vision_ocr.MAX_IMAGE_BYTES or max(image.size) > vision_ocr.MAX_EDGE or image.width * image.height > vision_ocr.MAX_PIXELS:
                raise ValueError("Crop exceeds consent/budget shape")
            count += 1
        else: raise ValueError("Unexpected image content")
    policy = body.get("provider", {})
    if not 1 <= count <= 4 or policy.get("data_collection") != "deny" or policy.get("zdr") is not True or policy.get("allow_fallbacks") is not False or policy.get("only") != ["google-vertex/global"]:
        raise ValueError("Unapproved image route/privacy")
    return count


def main():
    folder = diagnostic_folder(sys.argv)
    cfg = json.loads((folder / "native-config.json").read_text(encoding="utf-8"))
    model, budget, prices = validated_options(cfg)
    if cfg["qaCloud"].get("imageConsent") is not True or budget > .04:
        raise ValueError("Image-native QA requires separate consent and <=0.04 USD")
    import manga_live.providers as providers
    from manga_live.host import Host, main as host_main
    ledger = ImageBudget(budget)
    attempts = []
    prior = session_reserved()
    base_post, base_initialize = providers.post_json, Host.initialize
    def save():
        (folder / "cloud-usage.json").write_text(json.dumps({"imageConsent": True, "budget_usd": budget,
            "session_prior_reserved_usd": prior, "reserved_usd": ledger.reserved, "attempts": attempts,
            "reported_cost_usd": sum(a.get("reported_cost_usd") or 0 for a in attempts)}, indent=2), encoding="utf-8")
    def initialize(self, profile):
        base_initialize(self, profile)
        self.translator.vault = Secrets("benchmark-openrouter")
        self.config.update({"mode": "byok", "provider": "openrouter", "openrouterModel": model, "cloudConsent": True,
            "cloudOcrConsent": True, "ocr": "cloud-gemini", "ocrBatch": 4, "autoSummary": False, "metadataConsent": False})
    def post(url, body, *args, **kwargs):
        if url != "https://openrouter.ai/api/v1/chat/completions": raise AppError("TEST_ENDPOINT", "Unapproved endpoint")
        if body.get("model") == MODEL and isinstance(body.get("messages", [{}])[0].get("content"), list):
            count = require_crop_request(body)
            amount = ledger.amount(body, count)
            kind = "image-ocr"
        else:
            require_text_only(body)
            if body.get("model") != model: raise AppError("TEST_ENDPOINT", "Unapproved translation model")
            body = bounded_request(body, {model: prices})
            amount = BudgetLedger(1).reserve(body)
            kind = "text-translation"
        if ledger.reserved + amount > budget or prior + ledger.reserved + amount > .50:
            raise AppError("TEST_BUDGET", "Cumulative image + translation QA budget reached before network")
        ledger.reserved += amount; ledger.calls += 1
        attempt = {"kind": kind, "reserved_usd": amount, "state": "attempted",
            "request_sha256": hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
        attempts.append(attempt); save()
        try:
            response = base_post(url, body, *args, **kwargs)
            usage = response.get("usage", {})
            attempt.update(state="response", provider=response.get("provider"), reported_cost_usd=usage.get("cost"), usage=usage)
            cost = usage.get("cost")
            if type(cost) not in (int, float) or not math.isfinite(cost) or not 0 <= cost <= amount:
                ledger.reserved = budget  # hold the run on unknown billing
                raise AppError("TEST_USAGE", "Billing evidence absent/outside reservation; stopping")
            return response
        except AppError as error:
            attempt["error"] = error.code
            # Unknown-billed timeout must not start another paid repair.
            if attempt["state"] == "attempted": ledger.reserved = budget
            raise
        finally: save()
    Host.initialize = initialize; providers.post_json = post
    try: host_main()
    finally:
        Host.initialize = base_initialize; providers.post_json = base_post; save()


if __name__ == "__main__": main()
