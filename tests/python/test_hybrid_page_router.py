from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from probe_hybrid_page_router import route


def report(candidate=False):
    return {
        "input_fingerprint_sha256": "a" * 64,
        "pages": [{
            "page": "p1", "review_count": 3 if not candidate else 9,
            "detector_ms": 10, "ocr_ms": 20,
            "regions": [{"id": "r1"}],
            "aligned": [{"id": "b1", "reference": "甲", "prediction": "乙" if not candidate else "甲",
                         "edits": 1 if not candidate else 0, "characters": 1, "region_ids": ["r1"]}],
        }, {
            "page": "p2", "review_count": 9 if not candidate else 9,
            "detector_ms": 10, "ocr_ms": 30,
            "regions": [{"id": "r2"}],
            "aligned": [{"id": "b2", "reference": "乙", "prediction": "乙" if not candidate else "丙",
                         "edits": 0 if not candidate else 1, "characters": 1, "region_ids": ["r2"]}],
        }],
    }


def test_routes_whole_pages_using_only_baseline_review_signal():
    result = route(report(), report(candidate=True), min_review_count=5)
    assert [page["source"] for page in result["pages"]] == ["baseline", "candidate"]
    assert result["aggregate"]["selected_exact"] == 0
    assert result["aggregate"]["selected_assigned"] == 2


def test_router_does_not_allow_different_fingerprints():
    candidate = report(candidate=True)
    candidate["input_fingerprint_sha256"] = "b" * 64
    try:
        route(report(), candidate, min_review_count=5)
    except ValueError as error:
        assert "fingerprint" in str(error)
    else:
        raise AssertionError("fingerprint mismatch must fail closed")
