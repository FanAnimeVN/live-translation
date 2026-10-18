"""Real private-report runner, only filesystem/model/OS boundaries authored."""
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
import sys
from types import SimpleNamespace

from PIL import Image
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))


def test_retained_members_are_read_without_gold_hints_or_source_geometry_changes(tmp_path,monkeypatch,capsys):
    import benchmark_manga_members as probe
    import compare_page_reports
    from benchmark import dataset_fingerprint
    from benchmark_pages import assign_to_labels
    from manga_live.ocr import MangaEngine
    image=Image.new("RGB",(100,150),"white")
    image.putpixel((40,15),(10,20,30))
    buffer=BytesIO();image.save(buffer,format="PNG")
    label={"bubble_id":"b1","bbox":{"x":30,"y":5,"w":40,"h":135},"ja_ocr_truth":"上…下♡"}
    labels=[{"page_id":"p","image_file":"source.png","image_size":{"w":100,"h":150},"bubbles":[label]}]
    class Dataset:
        values={"source.png":buffer.getvalue(),"ground_truth_benchmark.json":json.dumps(labels).encode()}
        def __init__(self,_):pass
        def read(self,entry):return self.values[entry if isinstance(entry,str) else entry.filename]
        def getinfo(self,name):return SimpleNamespace(filename=name,file_size=len(self.values[name]))
        def __enter__(self):return self
        def __exit__(self,*_):return False
    monkeypatch.setattr(compare_page_reports,"ROOT",tmp_path)
    import benchmark_mit48
    monkeypatch.setattr(benchmark_mit48,"physical_memory",lambda:{"available_physical_bytes":8*1024**3})
    members=[{"polygon":[[42,80],[52,80],[52,130],[42,130]],"score":.8},
             {"polygon":[[40,10],[50,10],[50,70],[40,70]],"score":.9}]
    source={"id":"original","bbox":[37,7,18,126],"order":0,"sourceMembers":members,"ja":"CONTROL"}
    aligned,unmatched=assign_to_labels([label],[source])
    parent={"cloud":False,"fresh_inference":True,"complete":True,"ocr":MangaEngine.name,
            "input_fingerprint_sha256":dataset_fingerprint(Dataset(None)),
            "pages":[{"page":"p","regions":[source],"aligned":aligned,"unmatched_prediction_ids":unmatched}]}
    destination=tmp_path/"artifacts";destination.mkdir()
    input_path=destination/"parent.json";input_path.write_text(json.dumps(parent),encoding="utf-8")
    output=destination/"candidate.json"
    class Recognizer:
        name=MangaEngine.name
        def __init__(self):self.answers=iter(["下♡","上…"])
        def load(self):pass
        def recognize(self,crop):
            assert crop.size in ((14,54),(14,64))
            return next(self.answers)
    args=SimpleNamespace(folder="RAM-only",primary=str(input_path),output=str(output),threads=2)
    result=probe.run(args,source_factory=Dataset,engine_factory=lambda _:Recognizer())
    region=result["pages"][0]["regions"][0]
    assert result["aggregate"]["exact"]==1
    assert region["ja"]=="上…下♡"
    assert [r["member_index"] for r in region["member_readings"]]==[1,0]
    assert region["sourceMembers"]==members and region["bbox"]==source["bbox"]
    assert region["memory_authority"] is False and region["erasure_authority"] is False
    assert result["source_records"]==parent["pages"]
    assert result["fresh_text_detection"] is False and result["fresh_recognition"] is True
    assert result["complete"] is True and json.loads(output.read_text())["complete"] is True
    assert all(p.suffix==".json" for p in destination.iterdir())
    assert "上…下♡" not in capsys.readouterr().out
    with pytest.raises(ValueError,match="overwrite"):
        probe.run(args,source_factory=Dataset,engine_factory=lambda _:pytest.fail("Must not infer twice"))
    # New source-direction recipe is a replay: no model or paid retry. Both
    # alternative readings remain private evidence, not a gold-based selector.
    replay_args=SimpleNamespace(folder="RAM-only",reorder_from=str(output),
                                output=str(destination/"direction.json"))
    reordered=probe.replay_order(replay_args,source_factory=Dataset)
    assert reordered["fresh_inference"] is False
    assert reordered["reading_order_recipe"]=="source-direction-votes-v3"
    assert reordered["aggregate"]["exact"]==1
    assert reordered["comparison"]["aggregate"]["regressed"]==0
    assert reordered["source_records"]==result["source_records"]

