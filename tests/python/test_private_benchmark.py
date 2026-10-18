"""Both private input formats must hit the same label/geometry audit seam."""
import io
import json
import sys
import zipfile
from pathlib import Path
import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from benchmark import DirectoryDataset, audit


def fixture(tmp_path):
    buffer = io.BytesIO()
    Image.new("RGB", (40, 60), "white").save(buffer, format="PNG")
    data = buffer.getvalue()
    pages = [{"page_id": "p1", "image_file": "one.png", "image_size": {"w": 40, "h": 60},
              "bubbles": [{"bubble_id": "b1", "bbox": {"x": 2, "y": 3, "w": 10, "h": 15},
                           "ja_ocr_truth": "ありがとう", "vi_gold_trans": "Cảm ơn"}]},
             {"page_id": "p2", "image_file": "copy.png", "image_size": {"w": 40, "h": 60},
              "bubbles": [{"bubble_id": "b2", "bbox": {"x": 2, "y": 3, "w": 10, "h": 15},
                           "ja_ocr_truth": "ありがとう", "vi_gold_trans": ""}]}]
    labels = json.dumps(pages).encode("utf-8")
    (tmp_path / "ground_truth_benchmark.json").write_bytes(labels)
    (tmp_path / "one.png").write_bytes(data)
    (tmp_path / "copy.png").write_bytes(data)
    archive_path = tmp_path / "input.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("ground_truth_benchmark.json", labels)
        archive.writestr("one.png", data)
        archive.writestr("copy.png", data)
    return pages, archive_path


def test_folder_and_zip_use_identical_audit_and_exclude_duplicate(tmp_path):
    _, archive_path = fixture(tmp_path)
    counts, issues, pages = audit(DirectoryDataset(tmp_path))
    with zipfile.ZipFile(archive_path) as archive:
        zip_counts, zip_issues, zip_pages = audit(archive)
    assert counts == zip_counts
    assert issues == zip_issues
    assert counts["eligible_pages"] == counts["eligible_bubbles"] == 1
    assert counts["eligible_vi_labels"] == 1
    assert issues == [{"page": "p2", "issue": "duplicate_image", "duplicate_of": "p1"}]
    assert pages[0][1].tobytes() == zip_pages[0][1].tobytes()


@pytest.mark.parametrize("filename", ["../secret.png", "..\\secret.png", "C:\\secret.png", "/secret.png"])
def test_folder_rejects_paths_instead_of_reading_other_files(tmp_path, filename):
    dataset = DirectoryDataset(tmp_path)
    with pytest.raises(ValueError):
        dataset.getinfo(filename)


def test_audit_rejects_nan_fractional_and_duplicate_boxes(tmp_path):
    pages, _ = fixture(tmp_path)
    original = pages[0]["bubbles"][0]
    pages = pages[:1]
    pages[0]["bubbles"].extend([
        {**original, "bubble_id": "nan", "bbox": {"x": float("nan"), "y": 0, "w": 10, "h": 10}},
        {**original, "bubble_id": "fractional", "bbox": {"x": .5, "y": 0, "w": 10, "h": 10}},
        dict(original),
    ])
    (tmp_path / "ground_truth_benchmark.json").write_text(json.dumps(pages), encoding="utf-8")
    counts, issues, _ = audit(DirectoryDataset(tmp_path))
    assert counts["eligible_bubbles"] == 1
    assert [issue["issue"] for issue in issues] == ["invalid_box", "invalid_box", "duplicate_bubble_id"]


def test_escaped_image_symlink_is_not_read(tmp_path):
    outside = tmp_path.parent / (tmp_path.name + "-outside.png")
    outside.write_bytes(b"not an image")
    try:
        try:
            (tmp_path / "escape.png").symlink_to(outside)
        except OSError:
            pytest.skip("Creating a symlink is not allowed on this Windows account")
        with pytest.raises(ValueError):
            DirectoryDataset(tmp_path).getinfo("escape.png")
    finally:
        outside.unlink(missing_ok=True)
