from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from probe_preocr_hardness_router import route


def report(candidate=False):
    return {
        "input_fingerprint_sha256": "a" * 64,
        "pages": [{
            "page": "p1", "pre_ocr_hardness": {"score": 30},
            "detector_ms": 10, "ocr_ms": 20,
            "regions": [{"id": "r1"}],
            "aligned": [{"id": "b1", "reference": "甲", "prediction": "乙" if not candidate else "甲",
                         "edits": 1 if not candidate else 0, "characters": 1, "region_ids": ["r1"]}],
        }, {
            "page": "p2", "pre_ocr_hardness": {"score": 80},
            "detector_ms": 10, "ocr_ms": 30,
            "regions": [{"id": "r2"}],
            "aligned": [{"id": "b2", "reference": "乙", "prediction": "乙" if not candidate else "丙",
                         "edits": 0 if not candidate else 1, "characters": 1, "region_ids": ["r2"]}],
        }],
    }


def test_routes_before_ocr_signal_only():
    result = route(report(), report(candidate=True), min_hardness=50)
    assert [page["source"] for page in result["pages"]] == ["baseline", "candidate"]
    assert result["aggregate"]["selected_assigned"] == 2


def test_missing_signal_fails_closed():
    broken = report()
    del broken["pages"][0]["pre_ocr_hardness"]
    try:
        route(broken, report(candidate=True), min_hardness=50)
    except ValueError as error:
        assert "pre_ocr_hardness" in str(error)
    else:
        raise AssertionError("missing pre-OCR signal must fail closed")

