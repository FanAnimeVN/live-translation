import json
from pathlib import Path
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from import_manga109_xml import build_pack, parse_xml


def xml_text(*, title="Demo", index=1, width=40, height=30, content="ねえ"):
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<book title="{title}"><pages><page index="{index}" width="{width}" height="{height}">
<text id="00000001" xmin="1" ymin="2" xmax="11" ymax="12">{content}</text>
<frame id="00000002" xmin="0" ymin="0" xmax="40" ymax="30"/>
</page></pages></book>'''


def make_dataset(tmp_path):
    folder = tmp_path / "dataset"
    folder.mkdir()
    Image.new("RGB", (40, 30), "white").save(folder / "page.jpg")
    labels = [{"page_id": "p1", "image_file": "page.jpg", "image_size": {"w": 40, "h": 30},
               "bubbles": [{"bubble_id": "b1", "bbox": {"x": 1, "y": 2, "w": 10, "h": 10},
                             "ja_ocr_truth": "ねえ"}]}]
    (folder / "ground_truth_benchmark.json").write_text(json.dumps(labels, ensure_ascii=False), encoding="utf-8")
    xml_dir = tmp_path / "xml"
    xml_dir.mkdir()
    (xml_dir / "demo.xml").write_text(xml_text(), encoding="utf-8")
    mapping = [{"page_id": "p1", "xml_file": "demo.xml", "xml_page_index": 1}]
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps(mapping), encoding="utf-8")
    return folder, xml_dir, map_path


def test_parse_xml_keeps_text_geometry_and_ignores_non_text(tmp_path):
    path = tmp_path / "demo.xml"
    path.write_text(xml_text(content="「わ・た・し」"), encoding="utf-8")
    parsed = parse_xml(path)
    assert parsed["title"] == "Demo"
    assert parsed["pages"][1]["texts"] == [{
        "xml_id": "00000001", "bbox": {"x": 1, "y": 2, "w": 10, "h": 10},
        "ja_candidate": "「わ・た・し」", "role": "unknown"}]


def test_build_pack_checks_mapping_and_does_not_claim_gold(tmp_path):
    folder, xml_dir, map_path = make_dataset(tmp_path)
    pack = build_pack(str(folder), str(xml_dir), str(map_path), rights_confirmed=True)
    assert pack["independent_human_review"] is False
    assert pack["rights_confirmed"] is True
    assert pack["rows"][0]["reviewed_ja"] == "ねえ"
    assert pack["rows"][0]["review_state"] == "unreviewed"
    assert pack["rows"][0]["image_file"] == "page.jpg"


def test_xml_dtd_and_size_mismatch_fail_closed(tmp_path):
    bad = tmp_path / "bad.xml"
    bad.write_text("<!DOCTYPE book [<!ENTITY x SYSTEM 'file:///secret'>]><book/>", encoding="utf-8")
    with pytest.raises(ValueError, match="DTD/entity"):
        parse_xml(bad)
    folder, xml_dir, map_path = make_dataset(tmp_path)
    (xml_dir / "demo.xml").write_text(xml_text(width=41), encoding="utf-8")
    with pytest.raises(ValueError, match="size"):
        build_pack(str(folder), str(xml_dir), str(map_path))
