"""Reviewer drafts must never impersonate independently reviewed gold."""
import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
from PIL import Image
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
import export_gold_review as review


class Dataset:
    def __init__(self):
        pixels=io.BytesIO();Image.new("RGB",(80,80),"white").save(pixels,format="PNG")
        pages=[{"page_id":"fixture","image_file":"fixture.png","image_size":{"w":80,"h":80},
                "bubbles":[{"bubble_id":"b01","bbox":{"x":5,"y":5,"w":30,"h":40},
                            "ja_ocr_truth":"「ねえ…」","vi_gold_trans":"unreviewed source candidate"}]}]
        self.entries={"ground_truth_benchmark.json":json.dumps(pages).encode(),"fixture.png":pixels.getvalue()}
    def read(self,key):return self.entries[key if isinstance(key,str) else key.filename]
    def getinfo(self,key):return SimpleNamespace(filename=key,file_size=len(self.entries[key]))


def test_export_keeps_raw_source_without_inventing_human_review_or_vietnamese_gold():
    source=Dataset();before=dict(source.entries)
    result=review.make_review_pack(source)
    assert source.entries==before
    assert result["split"]=="development" and result["review_state"]=="unreviewed"
    assert result["independent_human_review"] is False and result["reviewed_by"]==[]
    row=result["rows"][0]
    assert row["source_ja_candidate"]=="「ねえ…」"
    assert row["source_vi_candidate"]=="unreviewed source candidate"
    assert row["reviewed_ja"] is None and row["vi_reference"] is None
    assert row["difficulty"]=="unclassified" and row["role"]=="unknown"
    assert row["group_members"]==[] and row["review_state"]=="unreviewed"
    serialized=json.dumps(result)
    assert "base64" not in serialized and "data:image" not in serialized
    assert len(result["dataset_fingerprint_sha256"])==64


def test_audit_exclusions_are_reported_and_not_silently_made_eligible():
    source=Dataset();pages=json.loads(source.entries["ground_truth_benchmark.json"])
    pages.append({**pages[0],"page_id":"duplicate"})
    source.entries["ground_truth_benchmark.json"]=json.dumps(pages).encode()
    result=review.make_review_pack(source)
    assert len(result["rows"])==1
    assert any(row["issue"]=="duplicate_image" for row in result["audit"])
    assert result["quality_accepted"] is False


def test_review_export_cannot_overwrite_existing_draft(tmp_path,monkeypatch):
    monkeypatch.setattr(review,"ROOT",tmp_path)
    path=tmp_path/"artifacts/private-review.json";path.parent.mkdir();path.write_text("keep")
    with pytest.raises(ValueError):review.output_path(path)
    assert path.read_text()=="keep"


def test_review_output_stays_private_json_not_a_distributable_or_raster(tmp_path,monkeypatch):
    monkeypatch.setattr(review,"ROOT",tmp_path)
    for value in (tmp_path/"docs/gold.json",tmp_path/"artifacts/review.png",tmp_path/"artifacts/../gold.json"):
        with pytest.raises(ValueError):review.output_path(value)


def test_pixels_first_pack_hides_candidate_transcriptions_without_attesting_review():
    source=Dataset();before=dict(source.entries)
    pack=review.make_review_pack(source,blind=True)
    rendered=json.dumps(pack,ensure_ascii=False)
    assert "「ねえ…」" not in rendered and "unreviewed source candidate" not in rendered
    assert "source_ja_candidate" not in rendered and "source_vi_candidate" not in rendered
    assert pack["review_mode"]=="pixels-first-candidates-hidden"
    assert pack["quality_accepted"] is False and pack["independent_human_review"] is False
    assert pack["rows"][0]["reviewed_ja"] is None and pack["rows"][0]["role"]=="unknown"
    assert source.entries==before and pack["rows"][0]["source_bbox"]=={"x":5,"y":5,"w":30,"h":40}
