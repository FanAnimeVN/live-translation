"""The OCR review queue must stay diagnostic and source-preserving."""

import json

from scripts import build_ocr_review_queue as queue


def write_json(path, payload):
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def test_queue_records_unanimous_nonmatch_without_promoting_it(tmp_path, monkeypatch):
    base = {
        "rows": [{"id": "p:b", "reference": "猫！！", "variants": {"base": {"prediction": "猫!"}}}]
    }
    hayai = {"rows": [{"id": "p:b", "reference": "猫！！", "prediction": "猫!"}]}
    baberu = {"rows": [{"id": "p:b", "reference": "猫！！", "prediction": "猫!"}]}
    for name, payload in (("base.json", base), ("hayai.json", hayai), ("baberu.json", baberu)):
        write_json(tmp_path / name, payload)
    output = tmp_path / "artifacts" / "queue.json"
    monkeypatch.setattr(queue, "ROOT", tmp_path)
    queue.run(type("Args", (), {
        "base": str(tmp_path / "base.json"),
        "hayai": str(tmp_path / "hayai.json"),
        "baberu": str(tmp_path / "baberu.json"),
        "output": str(output),
    })())
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["counts"]["unanimous_nonmatch"] == 1
    assert report["rows"][0]["reason"] == "unanimous_nonmatch"
    assert report["gold_used_for_runtime_routing"] is False


def test_queue_accepts_baberu_page_alignment_shape(tmp_path, monkeypatch):
    base = {"rows": [{"id": "P:b", "reference": "猫", "variants": {"base": {"prediction": "猫"}}}]}
    hayai = {"rows": [{"id": "P:b", "reference": "猫", "prediction": "猫"}]}
    baberu = {"pages": [{"page": "P", "aligned": [{"id": "b", "reference": "猫", "prediction": "猫"}]}]}
    for name, payload in (("base.json", base), ("hayai.json", hayai), ("baberu.json", baberu)):
        write_json(tmp_path / name, payload)
    output = tmp_path / "artifacts" / "queue.json"
    monkeypatch.setattr(queue, "ROOT", tmp_path)
    queue.run(type("Args", (), {
        "base": str(tmp_path / "base.json"),
        "hayai": str(tmp_path / "hayai.json"),
        "baberu": str(tmp_path / "baberu.json"),
        "output": str(output),
    })())
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["counts"]["agreement_with_reference"] == 1
    assert report["rows"][0]["predictions"]["baberu"] == "猫"
