"""Storage/retrieval fixture, NOT evidence of AI understanding 100 chapters."""
import argparse
import json
import math
from pathlib import Path
import statistics
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "companion"))
from manga_live.memory import Memory, encode, context_markdown


def percentile(values, q):
    return sorted(values)[max(0, math.ceil(len(values) * q) - 1)]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, choices=range(10, 201), default=100)
    parser.add_argument("--output", default=str(ROOT / "artifacts/context-retrieval-pilot.json"))
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="mangalive-retrieval-") as directory:
        memory = Memory(Path(directory) / "fixture.db")
        try:
            memory.ensure_story("fixture", "Storage fixture only")
            with memory.transaction():
                memory.fact("fixture", "character", "nana", encode({"type":"name-forms",
                    "character":"nana", "forms":[{"ja":"ナナ", "reading":"Nana", "role":"given"}]}),
                    {"chapter":1,"page":0}, {"type":"user"})
                memory.canonical_term("fixture", "blade", "weapon", "雪牙", "Tuyết Nha",
                    [{"ja":"白い牙","vi":"Nanh Trắng"}], {"chapter":1,"page":0})
                for index in range(60):
                    memory.fact("fixture", "character", f"person{index}", encode({"type":"name-forms",
                        "character":f"person{index}", "forms":[{"ja":f"人物名{index}",
                            "reading":f"Person {index}","role":"given"}]}),
                        {"chapter":1,"page":0}, {"type":"user"})
                for index in range(140):
                    memory.canonical_term("fixture", f"term{index}", "skill", f"術式第{index}式",
                        f"Thuật thức {index}", [], {"chapter":1,"page":0})
                for chapter in range(1, 101):
                    refs = []
                    for page in range(10):
                        utterance = f"まだ決めていません。{chapter}-{page}"
                        if (chapter,page)==(5,0):utterance="ナナが白い牙を預かった。"
                        if (chapter,page)==(80,0):utterance="ナナが雪牙を返した。"
                        evidence = {"type":"dialogue","utterances":[{
                            "ja":utterance,"speaker":"unknown","listener":"unknown"}]}
                        memory.fact("fixture", "event", f"event{chapter}p{page}", "Unverified paraphrase",
                            {"chapter":chapter,"page":page}, evidence, False, False)
                        refs.append(memory.summary("fixture", chapter, chapter, page, "Unverified paraphrase", {
                            "type": "dialogue", "utterances": [{
                                "ja": utterance, "speaker": "unknown", "listener": "unknown"}]},
                            True, summary_id=f"c{chapter}p{page}"))
                    # Complete is synthetic fixture data, not reader inference.
                    memory.summary("fixture", chapter, chapter, 10, "Unverified chapter rollup", {
                        "type": "dialogue", "summary_ids": refs}, True, "group", f"chapter{chapter}")
                for end in range(10, 101, 10):
                    memory.summary("fixture", end - 9, end, 10, "Unverified group rollup", {
                        "type": "dialogue", "summary_ids": [f"chapter{c}" for c in range(end - 9, end + 1)]},
                        True, "group", f"group{end}")
            counts = []
            scenarios = [(cutoff,mode) for cutoff in (20,100) for mode in ("recent","aliases")]
            for cutoff, mode in scenarios:
                def retrieve():
                    return memory.context("fixture", {"chapter": cutoff, "page": 11},
                        "ナナ、雪牙はどこ？" if mode=="aliases" else "",
                        entities=["nana","blade"] if mode=="aliases" else [])
                durations = []
                for _ in range(args.repeats):
                    started = time.perf_counter()
                    snapshot = retrieve()
                    durations.append((time.perf_counter() - started) * 1000)
                queries = []
                memory.db.set_trace_callback(lambda sql: queries.append(1) if sql.startswith("SELECT") else None)
                try:
                    snapshot = retrieve()
                finally:
                    memory.db.set_trace_callback(None)
                content = context_markdown(snapshot["data"])
                events = snapshot["data"]["events"]
                assert "Unverified" not in content
                assert events and all(e["kind"] == "dialogue-evidence" and e["chapter"] <= cutoff for e in events)
                assert len(encode(events).encode("utf-8")) <= 1500
                if mode=="aliases":assert "ナナが白い牙を預かった。" in content
                if cutoff==20:assert "ナナが雪牙を返した。" not in content
                counts.append({"cutoff": cutoff, "mode":mode, "calls": args.repeats,
                    "p50_ms": statistics.median(durations), "p95_ms": percentile(durations, 0.95),
                    "max_ms": max(durations), "select_queries": len(queries),
                    "events_bytes": len(encode(events).encode("utf-8")),
                    "evidence_regions": sum(len(e["utterances"]) for e in events)})
            report = {"source": "SQLite synthetic fixture: 100 chapter markers, 1000 leaves, 110 rollups, 202 validated profiles, 1000 evidence-backed proposed facts",
                "rows": counts, "limits": ["Storage retrieval only; no AI-generated chapters, OCR, translation or browser latency.",
                    "Local repeated queries on a hot synthetic database; not a representative production p95.",
                    "Prompt evidence is bounded; storing 100 chapters does not send all history into each request."]}
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(report, ensure_ascii=True), flush=True)
        finally:
            memory.close()


if __name__ == "__main__":
    main()
