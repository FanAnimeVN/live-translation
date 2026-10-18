"""Small deterministic live-model regression, not a translation-quality leaderboard."""
import json
import argparse
from pathlib import Path
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.config import Config
from manga_live.memory import Memory
import manga_live.providers as providers


def main():
    parser=argparse.ArgumentParser();parser.add_argument("--official-markers",action="store_true");args=parser.parse_args()
    config=Config(ROOT/"artifacts/prompt-regression");config.update({"mode":"offline"})
    memory=Memory(ROOT/"artifacts/prompt-regression/memory.db")
    memory.ensure_story("test","Tự tạo","đời thường")
    memory.fact("test","character","nana","ナナ = Nana. Không rõ tuổi/quan hệ.",{"chapter":1,"page":0},{"type":"user"})
    context=memory.context("test",{"chapter":1,"page":0})["data"]
    translator=providers.Translator(config,None,ROOT/"models",ROOT/"runtime/llama")
    if args.official_markers:
        from manga_live.memory import context_markdown
        providers.compact_prompt=lambda regions,context: "[Background Information]\n"+context_markdown(context)+"\nPlease translate ONLY the string values in the following JSON from Japanese into Vietnamese, taking the background information into consideration. Keep all JSON keys unchanged. Output only the translated JSON, without explanation.\n[Source Text]\n"+json.dumps({r["id"]:r["ja"] for r in regions},ensure_ascii=False)
    post=providers.post_json
    results=[]
    try:
        for seed in range(6):
            def seeded(url,body,*args,**kwargs):
                return post(url,{**body,"seed":seed},*args,**kwargs)
            providers.post_json=seeded
            items,metrics=translator.translate([{"id":"r0","ja":"私はナナです。よろしくお願いします。","speaker":"nana"}],context,threading.Event())
            value=items[0]["vi"].lower()
            valid="nana" in value and any(x in value for x in ("tôi", "mình", "tớ", "em")) and not any(x in value for x in ("không rõ", "quan hệ", "độ tuổi"))
            results.append({"seed":seed,"vi":items[0]["vi"],"pass":valid,"ms":metrics["translation_ms"]})
            print(json.dumps(results[-1],ensure_ascii=True),flush=True)
        (ROOT/"artifacts/prompt-regression.json").write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding="utf-8")
        assert all(r["pass"] for r in results), "Background leaked or self-introduction lost"
    finally:
        providers.post_json=post;translator.stop();memory.close()

if __name__=="__main__":main()
