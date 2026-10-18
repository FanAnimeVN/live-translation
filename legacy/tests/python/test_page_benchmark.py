import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from benchmark_pages import assign_to_labels
import json
from copy import deepcopy
from contextlib import nullcontext
from types import SimpleNamespace
from PIL import Image
import pytest


def gold(id, x=0, text="ありがとう"):
    return {"bubble_id": id, "bbox": {"x": x, "y": 0, "w": 30, "h": 30}, "ja_ocr_truth": text}


def test_diagnostic_alignment_keeps_splits_in_reading_order_and_never_uses_prediction_twice():
    regions = [{"id": "right", "bbox": [0, 0, 10, 30], "order": 1, "ja": "がとう"},
               {"id": "left", "bbox": [10, 0, 10, 30], "order": 0, "ja": "あり"},
               {"id": "outside", "bbox": [100, 0, 10, 10], "order": 2, "ja": "追加"}]
    rows, unmatched = assign_to_labels([gold("a"), gold("b", x=50)], regions)
    assert rows[0]["region_ids"] == ["left", "right"]
    assert rows[0]["edits"] == 0
    assert not rows[0]["one_to_one_iou_50"]
    assert rows[1]["region_ids"] == []
    assert rows[1]["edits"] == 5
    assert unmatched == ["outside"]


def test_merged_prediction_not_counted_as_two_perfect_regions():
    rows, _ = assign_to_labels([gold("a"), gold("b", x=30)],
                              [{"id": "merged", "bbox": [0, 0, 60, 30], "order": 0, "ja": "ありがとうありがとう"}])
    assert sum(len(r["region_ids"]) for r in rows) == 1
    assert all(r["edits"] > 0 for r in rows)


def test_recognizer_override_keeps_layout_alignment_and_reports_its_identity(tmp_path,monkeypatch):
    import benchmark_pages as bench
    region={"id":"r000","bbox":[0,0,30,30],"polygon":[[0,0],[30,0],[30,30],[0,30]],
            "score":1.,"order":0,"overlay":"label"}
    detector=SimpleNamespace(name="same-detector",detect=lambda image:[region])
    engine=SimpleNamespace(name="candidate-ocr",details={"revision":"pinned-fixture","production_default":False},
                           recognize_many=lambda images:["ありがとう"]*len(images))
    monkeypatch.setattr(bench,"MangaEngine",lambda *args: (_ for _ in ()).throw(AssertionError("Must not load production OCR")))
    monkeypatch.setattr(bench,"dataset_source",lambda args:nullcontext(None))
    monkeypatch.setattr(bench,"audit",lambda source:({"eligible_pages":1,"eligible_bubbles":1},[],
        [({"page_id":"fixture"},Image.new("RGB",(30,30),"white"),[gold("a")])]))
    monkeypatch.setattr(bench,"dataset_fingerprint",lambda source:"fixture-fingerprint")
    monkeypatch.setattr(bench,"make_plan",lambda *args:{})
    monkeypatch.setattr(bench,"route_regions",lambda regions,*args:regions)
    monkeypatch.setattr(bench,"render_patch",lambda *args,**kwargs:None)
    output=tmp_path/"comparator.json"
    bench.run(SimpleNamespace(threads=4,output=str(output),folder="fixture"),detector_override=detector,engine_override=engine)
    report=json.loads(output.read_text(encoding="utf-8"))
    assert report["ocr"] == "candidate-ocr" and report["detector"] == "same-detector"
    assert report["layout_version"] == bench.LAYOUT_VERSION
    assert report["experimental_recognizer"] == engine.details
    assert report["pages"][0]["aligned"][0]["edits"] == 0
    assert report["aggregate"]["annotation_count"] == 1 and report["cloud"] is False
    assert report["fresh_inference"] is True and report["production_default"] is False
    assert report["pages"][0]["regions"][0]["score"]==region["score"],"Raw scores must not vanish from comparison evidence"
    # A grouping comparator must be labelled as such, not as the runtime's
    # current layout/cache version just because it uses the same detector.
    detector.grouping_version="fixture-overlap-candidate"
    bench.run(SimpleNamespace(threads=4,output=str(output),folder="fixture"),detector_override=detector,engine_override=engine)
    report=json.loads(output.read_text(encoding="utf-8"))
    assert report["layout_version"] == detector.grouping_version


def test_threshold_probe_records_raw_evidence_without_altering_source_or_grouping_policy(monkeypatch):
    import benchmark_pages as bench
    lines=[{"polygon":[[2,2],[5,2],[5,9],[2,9]],"score":.48}]
    calls=[]
    monkeypatch.setattr(bench,"PaddleDetector",lambda *args:SimpleNamespace(
        detect_raw=lambda image,**kwargs:(calls.append(kwargs) or lines)))
    def grouped(image,raw,**kwargs):
        assert raw==lines and kwargs=={"include_source_members":True}
        return ["same-grouping-policy"]
    monkeypatch.setattr(bench,"group_regions",grouped)
    probe=bench.DetectorThresholdProbe(4,.4)
    assert probe.detect(Image.new("RGB",(20,20)))==["same-grouping-policy"]
    assert calls==[{"box_threshold":.4}]
    assert probe.details["box_thresh"]==.4 and probe.details["production_default"] is False
    assert probe.last_evidence["low_score_line_count"]==1
    assert probe.last_evidence["raw_detections"]==lines
    lines[0]["polygon"][0][0]=100
    assert probe.last_evidence["raw_detections"][0]["polygon"][0][0]==2


def test_review_only_detector_cannot_make_plot_memory_or_cleanup_evidence(tmp_path, monkeypatch):
    import benchmark_pages as bench
    region={"id":"r000","bbox":[0,0,30,30],"order":0,"ja":"ありがとう","overlay":"white",
            "balloon":{"textBox":[0,0,30,30],"background":"#ffffff"},
            "scope":{"action":"translate","memory":True}}
    detector=SimpleNamespace(name="review-proposal",review_only=True,detect=lambda image:[region])
    monkeypatch.setattr(bench,"dataset_source",lambda args:nullcontext(None))
    monkeypatch.setattr(bench,"audit",lambda source:({},[],[({"page_id":"p"},Image.new("RGB",(30,30)),[gold("a")])]))
    monkeypatch.setattr(bench,"dataset_fingerprint",lambda source:"unchanged")
    monkeypatch.setattr(bench,"partition_ocr_boxes",lambda *args:({},[]))
    monkeypatch.setattr(bench,"recognize_regions",lambda *args,**kwargs:[deepcopy(region)])
    monkeypatch.setattr(bench,"make_plan",lambda *args:{})
    monkeypatch.setattr(bench,"route_regions",lambda regions,*args:regions)
    def cleanup(image, candidate, *args, **kwargs):
        assert candidate["scope"]["memory"] is False and candidate["overlay"]=="label"
        assert candidate["review"] is True and "balloon" not in candidate
    monkeypatch.setattr(bench,"render_patch",cleanup)
    output=tmp_path/"review-only.json"
    bench.run(SimpleNamespace(threads=4,folder="fixture",output=str(output)),
              detector_override=detector,engine_override=SimpleNamespace(name="fixture"))
    result=json.loads(output.read_text(encoding="utf-8"))
    assert result["pages"][0]["regions"][0]["scope"]["memory"] is False
    assert result["production_default"] is False


@pytest.mark.parametrize("options,override",[
    ({"detector_side_len":1280,"detector_box_threshold":.4},False),
    ({"experimental_open_text":True,"detector_box_threshold":.4},False),
    ({"detector_box_threshold":.4},True),
    ({"detector_side_len":1280},True),
    ({"detector_resize_long":1600,"detector_box_threshold":.4},False),
    ({"detector_resize_long":1600,"detector_side_len":1280},False),
])
def test_mixed_detector_probes_fail_before_opening_dataset_or_loading_models(monkeypatch,options,override):
    import benchmark_pages as bench
    def forbidden(*args):raise AssertionError("Do not open private corpus for invalid comparison")
    monkeypatch.setattr(bench,"dataset_source",forbidden)
    with pytest.raises(ValueError,match="Change one variable"):
        bench.run(SimpleNamespace(**options),detector_override=object() if override else None)


def test_resize_probe_distinguishes_forced_long_edge_and_max_cap(monkeypatch):
    import benchmark_pages as bench
    calls=[]
    monkeypatch.setattr(bench,"PaddleDetector",lambda *args:SimpleNamespace(
        detect_raw=lambda image,**kwargs:(calls.append(kwargs) or []),model=None))
    monkeypatch.setattr(bench,"group_regions",lambda *args,**kwargs:[])
    image=Image.new("RGB",(100,200))
    cap=bench.DetectorResizeProbe(4,1600)
    force=bench.DetectorResizeProbe(4,1600,force_long=True)
    cap.detect(image);force.detect(image)
    assert calls==[{"limit_side_len":1600},{"limit_side_len":1600,"limit_type":"resize_long"}]
    assert cap.details["limit_type"]=="max" and force.details["limit_type"]=="resize_long"
    assert force.last_evidence["resize_evidence"]["available"] is False


def test_resize_shape_evidence_is_explicit_blank_replay_not_a_tensor_trace():
    import benchmark_pages as bench
    import numpy as np
    calls=[]
    def resize(imgs,**options):
        assert len(imgs)==1 and not imgs[0].any(),"Do not retain private page pixels in diagnostic state"
        calls.append(options)
        return [np.zeros((128,96,3),dtype=np.uint8)],[]
    detector=SimpleNamespace(model=SimpleNamespace(paddlex_predictor=SimpleNamespace(pre_tfs={"Resize":resize})))
    evidence=bench.resize_processor_evidence(detector,Image.new("RGB",(82,117),"red"),
                                           {"limit_side_len":128,"limit_type":"resize_long"})
    assert evidence["source_hw"]==[117,82] and evidence["resized_hw"]==[128,96]
    assert "not_tensor_trace" in evidence["method"]
    assert calls==[{"limit_side_len":128,"limit_type":"resize_long","max_side_limit":4000}]
