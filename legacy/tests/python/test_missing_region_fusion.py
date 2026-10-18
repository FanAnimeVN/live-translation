from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from probe_missing_region_fusion import fuse


def report(secondary=False):
    return {
        "input_fingerprint_sha256": "a" * 64,
        "pages": [{
            "page": "p1",
            "regions": [{"id": "r1"}] + ([{"id": "r2"}] if secondary else []),
            "aligned": [
                {"id": "b1", "reference": "甲", "prediction": "乙", "edits": 1,
                 "characters": 1, "region_ids": ["r1"]},
                {"id": "b2", "reference": "乙", "prediction": "乙" if secondary else "",
                 "edits": 0 if secondary else 1, "characters": 1,
                 "region_ids": ["r2"] if secondary else []},
            ],
        }],
    }


def test_only_missing_primary_rows_use_one_to_one_secondary():
    result = fuse(report(), report(secondary=True))
    assert result["aggregate"]["secondary_fallbacks"] == 1
    assert result["aggregate"]["selected_exact"] == 1
    assert [row["source"] for row in result["rows"]] == ["primary", "secondary_missing_only"]


def test_primary_text_is_never_replaced():
    primary = report()
    secondary = report(secondary=True)
    secondary["pages"][0]["aligned"][0]["prediction"] = "甲"
    secondary["pages"][0]["aligned"][0]["edits"] = 0
    result = fuse(primary, secondary)
    assert result["rows"][0]["source"] == "primary"
    assert result["rows"][0]["prediction"] == "乙"

