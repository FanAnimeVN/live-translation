"""Explicit image-authorized, RAM-only OpenRouter OCR pilot. Never a native host.

Gold is used AFTER inference only, not in request construction. No images or
request bodies in reports. New output directory per run prevents silent replays.
"""
import argparse
from copy import deepcopy
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from manga_live import vision_ocr as vision
from manga_live.config import Secrets
from manga_live.errors import AppError
from manga_live.providers import post_json
from benchmark import DirectoryDataset, audit, dataset_fingerprint, normalized, distance
from benchmark_pages import assign_to_labels
from fixture_server import synthetic_layout
from cloud_response_evidence import capture_response, reported_cost_total, transport_failure_evidence

DATASET = Path("C:/Users/Huy/Downloads/drive-download-20261012T095418Z-1-001")
FINGERPRINT = "445d4e457c8ac8c56d8c17e215d683b6abb1a908ba98932729add4f679dbab7f"
# This dated authorization includes earlier text/native runs. Retain EVERY
# image attempt, including aborted runs with unknown-billed network errors.
PRIOR_TEXT_RESERVED_USD = .0673507
SESSION_LIMIT_USD = .50


def session_reserved(root=ROOT / "artifacts", prior=PRIOR_TEXT_RESERVED_USD):
    total = prior
    for path in root.glob("cloud-image-*/report.json"):
        value = json.loads(path.read_text(encoding="utf-8")).get("reserved_usd")
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= .25:
            raise ValueError("Invalid prior reservation; refusing budget reset")
        total += value
    if total > SESSION_LIMIT_USD:
        raise AppError("TEST_BUDGET", "Trần OCR + dịch tích lũy 0,50 USD: chưa gửi request.")
    return total


def options(args):
    if args.consent_images is not True:
        raise ValueError("Explicit image upload consent required")
    if type(args.budget) not in (int, float) or not math.isfinite(args.budget) or not 0 < args.budget <= .25:
        raise ValueError("A new run must reserve at most 0.25 USD")
    if not args.models or len(set(args.models)) != len(args.models) or any(m not in vision.MODELS for m in args.models):
        raise ValueError("Only reviewed vision model IDs allowed")
    destination = Path(args.workdir).resolve()
    if not destination.is_relative_to((ROOT / "artifacts").resolve()) or destination.exists():
        raise ValueError("Use a new private artifacts subfolder; refusing replay/overwrite")
    return destination


def price_caps(catalog, model):
    entry = catalog.get(model, {})
    if "image" not in entry.get("architecture", {}).get("input_modalities", []):
        raise ValueError("Live model no longer accepts images")
    if not {"response_format", "structured_outputs", "reasoning", "max_tokens"} <= set(entry.get("supported_parameters", [])):
        raise ValueError("Required live parameters unavailable")
    price = entry.get("pricing", {})
    rates = [round(float(price.get(k, "nan")) * 1000000, 12) for k in ("prompt", "completion")]
    if not all(math.isfinite(v) and v > 0 for v in rates) or rates[0] > .30 or rates[1] > 2.5:
        raise ValueError("Live rates exceed reviewed ceilings")
    if float(price.get("request", 0)) != 0:
        raise ValueError("Separate request billing not authorized")
    # Gemini's catalogue image field is per image-input TOKEN (model docs),
    # not provider.max_price.image (per IMAGE). Do not confuse the units.
    image_rate = float(price.get("image", 0)) * 1000000
    if not math.isfinite(image_rate) or image_rate < 0 or (image_rate and (model != vision.MODELS[1] or image_rate > rates[0])):
        raise ValueError("Unknown separate image billing")
    return {"prompt": rates[0], "completion": rates[1], "request": 0}


class ImageBudget:
    """Conservative reservation, not a provider billing guarantee.

    <=4 images, each <=1568 edge /2.5Mpx. Reserve 16,384 image tokens each,
    or 4,096 for reviewed Gemini3.5 (documented ultra-high 2,240 cap).
    Both exceed reviewed vendor formulas/caps. Count schema/text as UTF8 bytes
    plus 2048 framing tokens; NEVER pretend base64 length is token count.
    Reserve all max_tokens including hidden reasoning, retain failed attempts.
    Keep the upstream hard key limit as an independent final backstop.
    """
    def __init__(self, limit):
        if type(limit) not in (int, float) or not math.isfinite(limit) or not 0 < limit <= .25:
            raise ValueError("Invalid image budget")
        self.limit, self.reserved, self.calls = limit, 0., 0

    def amount(self, body, count):
        if type(count) is not int or not 1 <= count <= 4:
            raise ValueError("Invalid image count")
        text = [p["text"] for m in body["messages"] for p in m["content"] if p["type"] == "text"]
        visual_bound = 4096 if body["model"] == "google/gemini-3.5-flash-lite" else 16384
        bound = count * visual_bound + len(json.dumps(text, ensure_ascii=False).encode()) + len(json.dumps(body["response_format"]).encode()) + 2048
        if bound >= 100000 or not 1 <= body["max_tokens"] <= 2048:
            raise ValueError("Request outside reviewed token tier")
        rates = body["provider"]["max_price"]
        if rates.get("request") != 0 or not all(type(rates[k]) in (int, float) and math.isfinite(rates[k]) and 0 < rates[k] <= cap
                                                for k, cap in (("prompt", .30), ("completion", 2.5))):
            raise ValueError("Invalid enforced rate ceiling")
        return (bound * rates["prompt"] + body["max_tokens"] * rates["completion"]) / 1000000

    def reserve(self, body, count):
        amount = self.amount(body, count)
        if self.reserved + amount > self.limit:
            raise AppError("TEST_BUDGET", "Dừng trước request: đã tới trần benchmark ảnh.")
        self.reserved += amount
        self.calls += 1
        return amount


def fixtures():
    from PIL import Image
    image, glyphs = synthetic_layout()
    texts = ["姉ちゃん、まだ帰らないの？", "先に帰ってて。あとで行くから。", "氷結結界を展開する！", "明日は来なくてもいい。"]
    entries = []
    for n, text in enumerate(texts):
        points = glyphs[n*2:n*2+2]
        xs = [p[0] for g in points for p in g["polygon"]]
        ys = [p[1] for g in points for p in g["polygon"]]
        box = (max(0, min(xs)-4), max(0, min(ys)-4), min(image.width, max(xs)+4), min(image.height, max(ys)+4))
        entries.append({"id": "a%d" % n, "image": image.crop(box), "truth": text, "page": "authored"})
    yield "authored-crops", entries, False
    yield "blank-controls", [{"id": "blank-white", "image": Image.new("RGB", (256, 256), "white"), "truth": "", "page": "blank"},
                             {"id": "blank-dark", "image": Image.new("RGB", (256, 256), "#333333"), "truth": "", "page": "blank"}], False
    yield "authored-page", [{"id": "authored-page", "image": image, "truth": None, "page": "authored"}], True


def proposal_groups(report, pages, fingerprint, selected, region_ids):
    """Prepare original-pixel detector crops, independent of gold/transcripts.

    References travel only to post-inference grading. These review candidates
    do not gain speaker, plot-memory, glyph-mask or erasure authority.
    """
    if (not isinstance(report, dict) or report.get("cloud") is not False
            or report.get("fresh_inference") is not True
            or report.get("input_fingerprint_sha256") != fingerprint):
        raise ValueError("Matching fresh local proposal evidence required")
    recorded = report.get("pages")
    sources = {p[0]["page_id"]: p for p in pages}
    if (not isinstance(recorded, list) or len(recorded) != len(sources)
            or any(not isinstance(p, dict) or not isinstance(p.get("page"), str) for p in recorded)
            or len({p["page"] for p in recorded}) != len(recorded)
            or {p["page"] for p in recorded} != set(sources)):
        raise ValueError("Complete matching proposal page coverage required")
    wanted = set(selected) if selected else set(sources)
    if not wanted or not wanted <= set(sources):
        raise ValueError("Requested proposal page is absent or excluded")
    if region_ids and (len(wanted) != 1 or len(set(region_ids)) != len(region_ids)):
        raise ValueError("Explicit region IDs require exactly one page and no duplicates")
    groups, excluded, selected_units = [], [], 0
    for page in recorded:
        ident = page["page"]
        if ident not in wanted:
            continue
        _, image, bubbles = sources[ident]
        regions = page.get("regions")
        if (not isinstance(regions, list) or len(regions) > 64
                or any(not isinstance(r, dict) or not isinstance(r.get("id"), str)
                       or not 1 <= len(r["id"]) <= 80 for r in regions)
                or len({r["id"] for r in regions}) != len(regions)):
            raise ValueError("Bounded unique proposal regions required")
        if region_ids and not set(region_ids) <= {r["id"] for r in regions}:
            raise ValueError("Requested source region is absent")
        entries = []
        for region in regions:
            if region_ids and region["id"] not in region_ids:
                continue
            reader_excluded = region.get("readerExcluded", False)
            if type(reader_excluded) is not bool:
                raise ValueError("Explicit reader exclusion required")
            scope = region.get("scope", {})
            if reader_excluded or scope.get("reason") == "reader" and scope.get("action") == "defer":
                excluded.append({"page": ident, "id": region["id"], "reason": "reader_excluded"})
                continue
            box = region.get("bbox")
            crop = region.get("ocrCropBox", box)
            for bounds in (box, crop):
                if (not isinstance(bounds, list) or len(bounds) != 4
                        or any(type(v) is not int for v in bounds)
                        or min(bounds[:2]) < 0 or min(bounds[2:]) < 1
                        or bounds[0]+bounds[2] > image.width or bounds[1]+bounds[3] > image.height):
                    raise ValueError("Invalid retained proposal crop")
            members = region.get("sourceMembers")
            if not isinstance(members, list) or not 1 <= len(members) <= 512:
                raise ValueError("Retained detector members required")
            for member in members:
                points = member.get("polygon") if isinstance(member, dict) else None
                score = member.get("score") if isinstance(member, dict) else None
                if (type(score) not in (int, float) or not math.isfinite(score) or not 0 <= score <= 1
                        or not isinstance(points, list) or not 4 <= len(points) <= 64
                        or any(not isinstance(p, list) or len(p) != 2 or any(
                            type(v) not in (int, float) or not math.isfinite(v) or v < 0 for v in p)
                            or p[0] > image.width or p[1] > image.height for p in points)):
                    raise ValueError("Invalid retained detector member")
            x, y, w, h = crop
            entries.append({"id": region["id"], "page": ident, "bbox": list(box),
                            "crop_box": list(crop), "source_members": deepcopy(members),
                            "image": image.crop((x, y, x+w, y+h)), "truth": None,
                            "bubbles": bubbles})
        selected_units += len(entries)
        groups.extend((ident+"-proposals-%d" % offset, entries[offset:offset+4], False)
                      for offset in range(0, len(entries), 4))
    return groups, {"selected_units": selected_units, "reader_excluded": excluded,
                    "crop_source": "retained-detector-proposals", "erasure_authority": False}


def private_groups(source, selected, limit, *, proposals=None, region_ids=None):
    with DirectoryDataset(DATASET) as archive:
        counts, issues, pages = audit(archive)
        fingerprint = dataset_fingerprint(archive)
    if fingerprint != FINGERPRINT:
        raise ValueError("Dataset changed; re-audit and confirm image permission first")
    if source == "proposal-crops":
        if not proposals:
            raise ValueError("Proposal crop mode requires retained source evidence")
        path = Path(proposals).resolve(strict=True)
        if not path.is_relative_to((ROOT / "artifacts").resolve()) or path.suffix != ".json" or path.stat().st_size > 16*1024*1024:
            raise ValueError("Use bounded private proposal evidence under artifacts")
        data = path.read_bytes()
        if len(data) > 16*1024*1024:
            raise ValueError("Proposal evidence exceeds its bound")
        groups, evidence = proposal_groups(json.loads(data), pages, fingerprint, selected, region_ids)
        prepared = groups[:limit] if limit else groups
        return prepared, {"counts": counts, "audit": issues, "fingerprint": fingerprint,
                          "proposal_sha256": hashlib.sha256(data).hexdigest(), "proposal_selection": evidence,
                          "prepared_units": sum(len(entries) for _, entries, _ in prepared)}
    if selected:
        available = {p[0]["page_id"] for p in pages}
        if not set(selected) <= available: raise ValueError("Page excluded or absent")
        pages = [p for p in pages if p[0]["page_id"] in selected]
    groups = []
    for page, image, bubbles in pages:
        if source == "private-pages":
            # No downscale: a dimension change would introduce another variable.
            groups.append((page["page_id"], [{"id": page["page_id"], "page": page["page_id"], "image": image,
                                              "truth": None, "bubbles": bubbles}], True))
        else:
            entries = []
            for bubble in bubbles:
                x, y, w, h = (bubble["bbox"][k] for k in ("x", "y", "w", "h"))
                entries.append({"id": bubble["bubble_id"], "page": page["page_id"],
                                "image": image.crop((x, y, x+w, y+h)), "truth": bubble["ja_ocr_truth"]})
            groups.extend((page["page_id"] + "-%d" % offset, entries[offset:offset+4], False) for offset in range(0, len(entries), 4))
    return groups[:limit] if limit else groups, {"counts": counts, "audit": issues, "fingerprint": fingerprint}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--consent-images", action="store_true")
    parser.add_argument("--source", choices=("authored", "private-crops", "private-pages", "proposal-crops"), required=True)
    parser.add_argument("--models", nargs="+", required=True)
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--pages", nargs="*")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--proposals", help="Retained detector evidence; required only for proposal-crops")
    parser.add_argument("--region-ids", nargs="+", help="Specific source IDs on exactly one selected page")
    parser.add_argument("--completion-tokens", type=int, choices=(512, 1024, 1536, 2048),
                        help="Explicit benchmark-only output ceiling; incomplete output still fails")
    parser.add_argument("--plan-only", action="store_true")
    args = parser.parse_args()
    destination = options(args)
    if args.limit is not None and not 1 <= args.limit <= 32: raise ValueError("Invalid group limit")
    if args.source != "proposal-crops" and (args.proposals or args.region_ids):
        raise ValueError("Proposal selection cannot modify gold-crop/page/authored experiments")
    groups, metadata = (list(fixtures()), {}) if args.source == "authored" else private_groups(
        args.source, args.pages, args.limit, proposals=args.proposals, region_ids=args.region_ids)
    if args.source == "authored" and args.limit: groups = groups[:args.limit]
    if not groups: raise ValueError("No eligible non-excluded OCR crops; no request made")
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        catalog = {m["id"]: m for m in json.load(response)["data"]}
    caps = {model: price_caps(catalog, model) for model in args.models}
    ledger = ImageBudget(args.budget)
    estimate = 0
    output_caps = {}
    for model in args.models:
        for _, entries, page in groups:
            body = vision.request(model, [(r["id"], r["image"]) for r in entries], page=page)
            if args.completion_tokens is not None: body["max_tokens"] = args.completion_tokens
            body["provider"]["max_price"] = caps[model]
            output_caps[model] = body["max_tokens"]
            estimate += ledger.amount(body, len(entries))
    plan = {"source": args.source, "groups": len(groups), "requests": len(groups) * len(args.models),
            "reservation_plan_usd": estimate, "budget_usd": args.budget, "rates": caps,
            "output_caps": output_caps, "images": sum(len(entries) for _, entries, _ in groups)}
    print(json.dumps(plan), flush=True)
    if args.plan_only: return
    if estimate > args.budget: raise ValueError("Preflight exceeds image budget; narrow source/models/groups")
    key = Secrets("benchmark-openrouter").get("openrouter")
    destination.mkdir(parents=True, exist_ok=False)
    report = {"version": vision.VERSION, "source": args.source, "imageConsent": True, "imagesPersisted": False,
              "preflight": plan, "dataset": metadata, "rows": [], "attempts": [],
              "limitations": ["Unreviewed Japanese labels; no Vietnamese/clean-background gold.",
                  "Page annotation containment is diagnostic alignment, not true recall/precision.",
                  "Reservation uses reviewed vendor token bounds plus headroom, not an independent billing guarantee.",
                  "No browser/overlay or reliable latency p95 in this small pilot.",
                  "Vision boxes are never glyph masks, role classification, speaker evidence or erasure permission."]}
    if args.source == "proposal-crops":
        report["limitations"].append("Selected detector-crop probe, not a full-page or 78-label quality score; source transcripts/gold are not sent.")
    def save():
        report.update(reserved_usd=ledger.reserved, attempted_requests=ledger.calls,
                      reported_cost_usd=reported_cost_total(report["attempts"]))
        path = destination / "report.json"
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        tmp.replace(path)
    save()
    seen_generations = set()
    for model in args.models:
        for group, entries, page in groups:
            body = vision.request(model, [(r["id"], r["image"]) for r in entries], page=page)
            if args.completion_tokens is not None: body["max_tokens"] = args.completion_tokens
            body["provider"]["max_price"] = caps[model]
            amount = ledger.reserve(body, len(entries))
            attempt = {"attempt_id": uuid.uuid4().hex, "number": ledger.calls,
                       "started_at_unix_ns": time.time_ns(),
                       "model": model, "group": group, "state": "attempted", "reserved_usd": amount,
                       "request_sha256": hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True).encode()).hexdigest()}
            if args.source == "proposal-crops":
                attempt["source_ids"] = [{"page": r["page"], "id": r["id"]} for r in entries]
            report["attempts"].append(attempt)
            save()  # Unknown billed timeout still spends its reservation.
            report["session_reserved_usd"] = session_reserved(ROOT / "artifacts")
            save()
            started = time.perf_counter()
            row = {"model": model, "group": group, "pageMode": page}
            if args.source == "proposal-crops":
                row["selected_sources"] = [{k: r[k] for k in ("id", "page", "bbox", "crop_box", "source_members")}
                                           for r in entries]
                row["erasure_authority"] = False
            try:
                response = post_json("https://openrouter.ai/api/v1/chat/completions", body,
                                     {"Authorization": "Bearer " + key}, timeout=45)
                capture_response(attempt, response, save, seen_generations)
                if attempt["billing_state"] != "reported":
                    raise AppError("TEST_ACCOUNTING", "Dừng benchmark: phản hồi thiếu hoặc mâu thuẫn bằng chứng chi phí.")
                results = vision.checked_response(response, [r["id"] for r in entries], page=page,
                                                  image_size=entries[0]["image"].size if page else None)
                row.update(ok=True, results=results)
                if args.source == "proposal-crops":
                    by_id = {r["id"]: r for r in entries}
                    regions = [{"id": r["id"], "bbox": by_id[r["id"]]["bbox"], "ja": r["ja"], "order": n}
                               for n, r in enumerate(results)]
                    aligned, unmatched = assign_to_labels(entries[0]["bubbles"], regions)
                    row["aligned"] = [r for r in aligned if r["region_ids"]]
                    row["non_target_labels"] = sum(not r["region_ids"] for r in aligned)
                    row["unmatched_proposal_ids"] = unmatched
                elif not page:
                    refs = {r["id"]: r["truth"] for r in entries}
                    row["scored"] = [{"id": r["id"], "reference": refs[r["id"]], "prediction": r["ja"],
                                      "edits": distance(normalized(refs[r["id"]]), normalized(r["ja"])),
                                      "characters": len(normalized(refs[r["id"]]))} for r in results]
                elif entries[0].get("bubbles") is not None:
                    regions = [{"id": r["id"], "ja": r["ja"], "order": n,
                                "bbox": [r["box"][k] for k in ("x", "y", "w", "h")]}
                               for n, r in enumerate(results)]
                    row["regions"] = regions
                    row["aligned"], row["unmatched_ids"] = assign_to_labels(entries[0]["bubbles"], regions)
            except AppError as error:
                row.update(ok=False, error=error.code)
                failure = transport_failure_evidence(error)
                row.update(failure)
                attempt.update(failure)
                if attempt["state"] == "attempted":
                    attempt["state"] = "failed"
                attempt["error"] = error.code
            row["ms"] = (time.perf_counter() - started) * 1000
            report["rows"].append(row)
            save()
            print(json.dumps({k: row.get(k) for k in ("model", "group", "ok", "error", "ms")}), flush=True)
            # Billing evidence missing or outside the reservation is a stop,
            # not permission to accumulate unknown image charges.
            cost = attempt.get("reported_cost_usd")
            if (attempt.get("billing_state") != "reported" or type(cost) not in (int, float)
                    or not math.isfinite(cost) or not 0 <= cost <= amount):
                report["aborted"] = "missing_or_unbounded_usage"
                save()
                raise SystemExit("Stopped after attempt: missing/unbounded billing evidence")
            # Failed route/schema/timeout does not trigger a retry or model switch.
    summary = {}
    for model in args.models:
        rows = [r for r in report["rows"] if r["model"] == model]
        scored = [s for r in rows for s in r.get("scored", r.get("aligned", []))]
        characters = sum(s["characters"] for s in scored)
        summary[model] = {"accepted": sum(r["ok"] for r in rows), "requests": len(rows), "labels": len(scored),
                          "exact": sum(normalized(s["reference"]) == normalized(s["prediction"]) for s in scored),
                          "cer": sum(s["edits"] for s in scored) / characters if characters else None,
                          "p50_request_ms": statistics.median(r["ms"] for r in rows)}
    report["summary"] = summary
    save()
    print(json.dumps({"summary": summary, "reserved_usd": ledger.reserved, "reported_cost_usd": report["reported_cost_usd"]}), flush=True)


if __name__ == "__main__": main()
