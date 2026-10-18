"""Bounded authored-page inference through the actual development launcher.

No browser/registry/settings-page automation. Does NOT prove MV3 integration,
the personal Edge profile, representative manga quality or a latency p95.
Images stay in RAM; the only persisted evidence is text/geometry/usage.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import urllib.request
import uuid

from benchmark_cloud import budget_plan
from fixture_server import synthetic_page
from native_smoke import NativeClient, verify_runtime

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "chrome-extension://epcjjhbilmmmbojldhnfblgmgiamajpl/"


def validate_completed(result):
    rows = result.get("regions", [])
    if len(rows) != 4 or len({r.get("id") for r in rows}) != 4:
        raise AssertionError("The authored page must complete exactly four distinct bubbles")
    if any(not isinstance(r.get("vi"), str) or not r["vi"].strip() for r in rows):
        raise AssertionError("A completed bubble has no translated text")
    if any(r.get("overlay") != "white" or not r.get("balloon", {}).get("erasePolygons") for r in rows):
        raise AssertionError("A known flat authored balloon lost its integrated surface")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--consent", action="store_true")
    parser.add_argument("--budget", type=float, required=True)
    parser.add_argument("--model", default="google/gemini-3.5-flash-lite")
    parser.add_argument("--image-ocr", action="store_true", help="Separate image-authorized QA, never the text-only entry")
    args = parser.parse_args()
    if not args.consent or not 0 < args.budget <= (.04 if args.image_ocr else .01):
        parser.error("Explicit consent and bounded QA budget required")
    # Public catalogue read only; never print/retrieve a key in this process.
    with urllib.request.urlopen("https://openrouter.ai/api/v1/models", timeout=30) as response:
        catalogue = {m["id"]: m for m in json.load(response)["data"]}
    _, rates = budget_plan([args.model], catalogue, 1, selected=[])
    folder = Path(tempfile.mkdtemp(prefix="mangalive-real-browser-"))
    config = folder / "native-config.json"
    config.write_text(json.dumps({"models": str(ROOT / "models"), "runtime": str(ROOT / "runtime/llama"),
        "dataRoot": str(folder / "data"), "python": sys.executable,
        "entry": str(ROOT / ("scripts/qa_image_entry.py" if args.image_ocr else "scripts/qa_cloud_entry.py")), "allowedOrigins": [ORIGIN],
        "qaCloud": {"consent": True, "model": args.model, "budgetUsd": args.budget,
                    "prices": rates[args.model], "imageConsent": args.image_ocr}}), encoding="utf-8")
    launcher = folder / "MangaLiveHost.exe"
    shutil.copy2(ROOT / "dist/windows/MangaLiveHost.exe", launcher)
    report = {"passed": False, "cloud": True, "model": args.model, "budgetUsd": args.budget,
              "source": "author-created four-bubble image only", "imagePersistence": False, "cloudImageOcr": args.image_ocr,
              "transport": "real length-framed development launcher; not browser Native Messaging discovery",
              "runs": [], "limitations": ["Not personal Edge or MV3/browser-action verification.",
                  "Three requests are not a reliable latency p95 or manga-quality evaluation.",
                  "Authored crops sent only with --image-ocr; no private scans/gold."]}
    client = None
    try:
        client = NativeClient(config, launcher=launcher)
        hello = client.call("hello")
        verify_runtime(hello)
        report["runtime"] = {k: hello.get(k) for k in ("runtimeBuild", "promptVersion", "ocrVersion", "layoutVersion")}
        story = "authored-cloud-probe"
        at = {"chapter": 1, "page": 0}
        client.call("story.ensure", {"storyId": story, "title": "Authored fixture", "genre": "fantasy"})
        client.call("memory.term", {"storyId": story, "category": "skill", "ja": "氷結結界",
                                    "vi": "Kết Giới Băng Giá", "at": at})
        data = synthetic_page()
        report["sourcePngSha256"] = hashlib.sha256(data).hexdigest()
        for name, page_id in (("cold", "page-a"), ("warm-new-page", "page-b"), ("cached-revisit", "page-b")):
            image_id, revision = uuid.uuid4().hex, uuid.uuid4().hex
            events = []
            started = time.perf_counter()
            client.image(data, image_id)
            result = client.call("pipeline", {"imageId": image_id, "storyId": story, "title": "Authored fixture",
                "pageId": page_id, "revision": revision, "at": at}, events)
            elapsed = (time.perf_counter() - started) * 1000
            validate_completed(result)
            assert result["revision"] == revision
            assert result["cached"] is (name == "cached-revisit")
            report["runs"].append({"name": name, "framedTotalMs": elapsed, "events": events, "native": result})
            print(json.dumps({"stage": name, "framedTotalMs": elapsed, "cached": result["cached"],
                              "regions": len(result["regions"]), "metrics": result["metrics"]}), flush=True)
        report["passed"] = True
    except Exception as error:
        report["error"] = str(error)
    finally:
        if client:
            client.close()
        usage = folder / "cloud-usage.json"
        if usage.is_file():
            report["cloudUsage"] = json.loads(usage.read_text(encoding="utf-8"))
        destination = folder / "result.json"
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"passed": report["passed"], "error": report.get("error"),
            "evidence": str(destination), "runtime": report.get("runtime"), "cloudUsage": report.get("cloudUsage")}), flush=True)
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
