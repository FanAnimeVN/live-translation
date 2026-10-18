"""Real local Qwen + SQLite on author-created dialogue; no cloud or scans."""
import json
from pathlib import Path
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.config import Config
from manga_live.memory import Memory,context_markdown
from manga_live.providers import Translator


def main():
    with tempfile.TemporaryDirectory(prefix="manga-summary-qa-") as temporary:
        config=Config(temporary);memory=Memory(Path(temporary)/"memory.db")
        translator=Translator(config,None,ROOT/"models",ROOT/"runtime/llama")
        regions=[{"id":"r0","ja":"姉ちゃん、まだ帰らないの？","vi":"Nee-chan, chưa về à?"},
            {"id":"r1","ja":"先に帰ってて。あとで行くから。","vi":"Cứ về trước đi. Lát nữa sẽ đi."},
            {"id":"r2","ja":"氷結結界を展開する！","vi":"Triển khai Băng Kết Kết Giới!"},
            {"id":"r3","ja":"明日は来なくてもいい。","vi":"Ngày mai không cần đến đâu."}]
        memory.ensure_story("qa","Trang tự tạo")
        memory.save_page("qa","page",{"chapter":1,"page":0},"rev",regions)
        memory.mark_read("qa","page","rev");job=memory.next_job("qa")
        try:
            start=time.perf_counter();raw=translator.summarize(job,threading.Event())
            elapsed=(time.perf_counter()-start)*1000
            memory.finish_job(job,raw)
            before=memory.context("qa",{"chapter":1,"page":0})
            after=memory.context("qa",{"chapter":1,"page":1})
            report={"source":"author-created dialogue; real local Qwen + SQLite; no API calls",
                "elapsed_ms":elapsed,"raw":raw,"memory":memory.export("qa"),
                "same_page":before,"next_page":after,
                "checks":{"same_page_has_no_generated_events":not before["data"]["events"],
                    "next_page_has_context":bool(after["data"]["events"]),
                    "summary_stays_partial":memory.export("qa")["summaries"][0]["complete"]==0},
                "limits":["A single synthetic page is not semantic quality certification.",
                    "Presence of a valid evidence ID does not prove the model inferred its meaning correctly."]}
            destination=ROOT/"artifacts/summary-smoke-v6.json";destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")
            print(json.dumps(report,ensure_ascii=True),flush=True)
            assert all(report["checks"].values())
        finally:translator.stop();memory.close()


if __name__=="__main__":main()
