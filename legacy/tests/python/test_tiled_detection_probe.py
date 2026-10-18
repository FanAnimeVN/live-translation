"""Geometry-only recall experiment; no private pixels or models in fixtures."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from probe_tiled_detection import tile_boxes, fuse_detections, TiledDetector, DetectionReplay, POLICY, VERSION


def line(box, score=.9):
    x, y, w, h = box
    return {"polygon": [[x, y], [x+w, y], [x+w, y+h], [x, y+h]], "score": score}


def test_tiles_cover_odd_source_dimensions_with_overlap_without_resizing_source():
    boxes = tile_boxes(827, 1171)
    assert len(boxes) == 4
    assert boxes[0][:2] == [0, 0] and boxes[-1][0]+boxes[-1][2] == 827
    assert boxes[-1][1]+boxes[-1][3] == 1171
    for y in range(1171):
        for x in (0, 413, 826):
            assert any(a <= x < a+w and b <= y < b+h for a, b, w, h in boxes)
    assert boxes[0][0]+boxes[0][2] > boxes[1][0]
    assert boxes[0][1]+boxes[0][3] > boxes[2][1]


def test_fusion_retains_full_page_geometry_and_scores_before_duplicate_tile_reads():
    base = [line([100, 100, 20, 100], .61)]
    records = [{"tile": [80, 80, 240, 240], "detections": [line([20, 20, 20, 100], .99)]}]
    original = deepcopy((base, records))
    selected, evidence = fuse_detections(base, records, (500, 600))
    assert selected == base
    assert evidence[-1]["decision"] == "duplicate"
    assert evidence[-1]["score"] == .99 and evidence[-1]["polygon"][0] == [100, 100]
    selected[0]["polygon"][0][0] = 0
    assert (base, records) == original, "Evidence must not alias caller-owned detections"


def test_new_tile_text_is_mapped_exactly_but_an_internal_edge_cut_is_not_accepted():
    selected, evidence = fuse_detections([], [{"tile": [100, 200, 200, 200], "detections": [
        line([20, 20, 20, 80], .8), line([0, 20, 20, 80], .9),
    ]}], (500, 600))
    assert selected == [line([120, 220, 20, 80], .8)]
    assert sorted(record["decision"] for record in evidence) == ["new", "tile_edge"]
    # Touching the real source boundary is not an artificial tile cut.
    selected, _ = fuse_detections([], [{"tile": [0, 0, 200, 200], "detections": [line([0, 20, 20, 80])]}], (500, 600))
    assert len(selected) == 1


def test_ambiguous_overlap_is_retained_as_evidence_not_silently_called_irrelevant():
    selected, evidence = fuse_detections([line([100, 100, 30, 100])], [
        {"tile": [50, 50, 300, 300], "detections": [line([70, 50, 30, 100])]},
    ], (500, 600))
    assert len(selected) == 1
    assert evidence[-1]["decision"] == "overlap_review"
    assert evidence[-1]["polygon"] == line([120, 100, 30, 100])["polygon"]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), -1, 501, True])
def test_corrupt_detector_coordinates_are_not_clipped_into_plausible_sources(bad):
    source = line([30, 30, 20, 80]); source["polygon"][0][0] = bad
    with pytest.raises(ValueError):
        fuse_detections([source], [], (500, 600))


def test_same_tile_read_from_overlapping_crops_is_not_ocrd_twice():
    selected, evidence = fuse_detections([], [
        {"tile": [0, 0, 300, 300], "detections": [line([150, 150, 20, 80], .7)]},
        {"tile": [100, 100, 300, 300], "detections": [line([50, 50, 20, 80], .9)]},
    ], (500, 600))
    assert selected == [line([150, 150, 20, 80], .9)]
    assert sorted(record["decision"] for record in evidence) == ["duplicate", "new"]


def test_probe_uses_one_full_page_and_four_bounded_upscaled_tiles_without_pixel_persistence():
    class FakeDetector:
        def __init__(self): self.calls = []
        def detect_raw(self, image, **options):
            self.calls.append((image.size, options))
            return []
    fake = FakeDetector()
    probe = TiledDetector(threads=4, detector=fake)
    source = Image.new("RGB", (827, 1171), "white")
    assert probe.detect(source) == []
    assert fake.calls[0] == ((827, 1171), {}) and len(fake.calls) == 5
    assert all(options == {"limit_side_len": 960, "limit_type": "resize_long"} for _, options in fake.calls[1:])
    assert probe.review_only is True
    assert len(probe.last_evidence["tiles"]) == 4
    assert not any(isinstance(value, Image.Image) for value in vars(probe).values())


def test_detection_replay_binds_source_pixels_and_never_runs_detector(monkeypatch):
    import probe_tiled_detection as probe
    source = Image.new("RGB", (500, 600), "white")
    record = {"page": "p", "source_size": [500, 600], "image_sha256": probe.hashlib_image(source),
              "regions": [{"id": "r000", "bbox": [100, 100, 20, 100]}],
              "detector_ms": 321, "detector_evidence": {"raw_detections": []}}
    report = {"experiment": VERSION, "layout_version": probe.LAYOUT_VERSION, "policy": deepcopy(POLICY),
              "phase": "detection", "production_default": False, "cloud": False, "pages": [record]}
    replay = DetectionReplay(report, [({"page_id": "p"}, source, [])])
    monkeypatch.setattr(probe, "PaddleDetector", lambda *args: pytest.fail("Replay cannot load Paddle"))
    assert replay.detect(source) == record["regions"]
    assert replay.last_evidence["recorded_detector_ms"] == 321
    assert replay.details["latency_excludes_recorded_detection"] is True
    changed = source.copy(); changed.putpixel((0, 0), (0, 0, 0))
    replay = DetectionReplay(report, [({"page_id": "p"}, source, [])])
    with pytest.raises(ValueError, match="pixels changed"):
        replay.detect(changed)
    record["regions"] = [{"id": f"r{i:03}"} for i in range(65)]
    replay = DetectionReplay(report, [({"page_id": "p"}, source, [])])
    with pytest.raises(ValueError, match="do not truncate"):
        replay.detect(source)
