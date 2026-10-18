"""Local-only repro of short dialogue reaching the generation ceiling.

All dialogue is author-created; no OCR/dataset, reader profile, Vault or cloud.
Record the rejected raw response for diagnosis, never display it to a reader.
"""
import argparse
import json
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "companion")]
from manga_live.config import Config
from manga_live.errors import AppError
import manga_live.providers as providers


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(ROOT/"artifacts/short-local-repro.json"))
    parser.add_argument("--tokens", type=int)
    parser.add_argument("--plain", action="store_true")
    parser.add_argument("--no-schema", action="store_true")
    parser.add_argument("--focused", action="store_true")
    parser.add_argument("--source-quote-schema", action="store_true",
                        help="Experimental schema only: no source rewrite, added tokens or relaxed validation")
    parser.add_argument("--temperature", type=float, choices=(0.2,0.7), default=0.2)
    parser.add_argument("--case", choices=("quoted", "ordinary", "four"), default="quoted")
    args = parser.parse_args()
    regions = [{"id":"r000", "ja":"「姉ちゃん、まだ帰らないの？"}]
    if args.case == "ordinary": regions = [{"id":"r000", "ja":"先に帰ってて。あとで行くから。"}]
    if args.case == "four": regions += [
        {"id":"r001", "ja":"先に帰ってて。あとで行くから。"},
        {"id":"r002", "ja":"氷結結界を展開する！"},
        {"id":"r003", "ja":"「明日は来なくてもいい。"}]
    if args.plain and len(regions)!=1:
        parser.error("--plain is a single-region probe, not a four-bubble completion test")
    if args.source_quote_schema and (args.plain or args.no_schema):
        parser.error("Quote schema requires structured output")
    report = {"source":"author-created text only", "case":args.case, "responses":[],
              "source_quote_schema_candidate":args.source_quote_schema}
    original_post, original_prompt = providers.post_json, providers.compact_prompt
    original_schema = providers.compact_schema
    if args.source_quote_schema:
        from benchmark_mt2_templates import source_quote_schema
        providers.compact_schema = lambda ids: source_quote_schema([row for row in regions if row["id"] in ids], {})
    if args.focused:
        from manga_live.prompts import focused_compact_prompt
        providers.compact_prompt = focused_compact_prompt
    def capture(url, body, *rest, **kwargs):
        assert kwargs.get("local") is True and url.startswith("http://127.0.0.1:")
        body = {**body, "seed":0, "temperature":args.temperature}
        if args.tokens is not None: body["max_tokens"] = args.tokens
        if args.no_schema or args.plain: body.pop("response_format", None)
        started = time.perf_counter()
        response = original_post(url, body, *rest, **kwargs)
        report["responses"].append({"limit":body["max_tokens"], "schema":bool(body.get("response_format")),
            "elapsed_ms":(time.perf_counter()-started)*1000, "usage":response.get("usage"),
            "choice":response.get("choices", [None])[0]})
        return response
    if args.plain:
        providers.compact_prompt = lambda rs, ctx: ("Translate the following text into Vietnamese. "
            "Note that you should only output the translated result without any additional explanation:\n" + rs[0]["ja"])
    providers.post_json = capture
    with tempfile.TemporaryDirectory(prefix="mangalive-short-repro-") as folder:
        translator = providers.Translator(Config(folder), None, ROOT/"models", ROOT/"runtime/llama")
        try:
            translator.local.start(threading.Event())
            try:
                if args.plain:
                    value, metrics = translator.local.generate(providers.compact_prompt(regions, {}), threading.Event(), max_tokens=125)
                else:
                    value, metrics = translator.translate(regions, {}, threading.Event())
                report.update(ok=True, value=value, metrics=metrics)
            except AppError as error: report.update(ok=False, error=error.code)
        finally:
            translator.stop()
            providers.post_json, providers.compact_prompt = original_post, original_prompt
            providers.compact_schema = original_schema
    Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=True), flush=True)
    assert report["ok"], "Short dialogue rejected: " + report.get("error", "unknown")


if __name__ == "__main__": main()
