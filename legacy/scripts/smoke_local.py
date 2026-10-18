import json
from pathlib import Path
import sys
import threading
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"companion"))
from manga_live.config import Config
from manga_live.providers import Translator
from manga_live.memory import Memory

def main():
    config=Config(ROOT/"artifacts/smoke-profile");config.update({"mode":"offline"})
    translator=Translator(config,None,ROOT/"models",ROOT/"runtime/llama")
    memory=Memory(ROOT/"artifacts/smoke-profile/memory.db");memory.ensure_story("test","Tự tạo","đời thường")
    memory.fact("test","character","nana","ナナ = Nana. Không rõ tuổi/quan hệ.",{"chapter":1,"page":0},{"type":"user"})
    regions=[{"id":"r0","ja":"私はナナです。よろしくお願いします。","speaker":"nana","listener":"unknown"}]
    context=memory.context("test",{"chapter":1,"page":0})["data"]
    try:
        cold,metrics=translator.translate(regions,context,threading.Event())
        warm,second=translator.translate([{"id":"r1","ja":"わかった。行こう！"}],context,threading.Event())
        result={"cold":cold,"warm":warm,"cold_metrics":metrics,"warm_metrics":second}
        (ROOT/"artifacts/local-smoke.json").write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
        print(json.dumps(result,ensure_ascii=True,indent=2),flush=True)
        first=cold[0]["vi"].lower()
        assert "nana" in first and any(x in first for x in ("tôi", "mình", "tớ", "em")), "Translation lost the Japanese self-introduction"
        assert not any(x in first for x in ("không rõ quan hệ", "không rõ tuổi", "độ tuổi")), "Translation leaked background instead of translating source"
    finally:
        translator.stop();memory.close()
if __name__=="__main__":
    main()
