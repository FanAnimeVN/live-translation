"""The public diagnostic tracer must observe the actual grouping call."""
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))


def test_balloon_trace_records_actual_lettering_decision_without_pixel_arrays():
    from fixture_server import synthetic_layout
    from probe_balloon import trace_decisions
    from manga_live.ocr import group_regions
    image,detections=synthetic_layout()
    rows=[];previous=sys.gettrace()
    try:
        sys.settrace(trace_decisions(rows))
        regions=group_regions(image,detections[:2])
    finally:sys.settrace(previous)
    assert regions[0].get("balloon")
    assert any(r["seam"]=="balloon_lettering" and r["accepted"] for r in rows), "A tracer with no per-frame callback silently reports no evidence"
    assert any(r["seam"]=="group_regions" for r in rows)
    assert all("rgb" not in row and "image" not in row and "mask" not in row for row in rows)
