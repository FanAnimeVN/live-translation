import pytest

from manga_live.page_hardness import PAGE_HARDNESS_VERSION, score_page_hardness


def region(bbox, score=0.9, **extra):
    return {"bbox": list(bbox), "score": score, **extra}


def test_empty_page_is_easy_and_versioned():
    result = score_page_hardness([], 1000, 1000)
    assert result["version"] == PAGE_HARDNESS_VERSION
    assert result["score"] == 0
    assert result["reasons"] == []


def test_geometry_only_score_ignores_ocr_and_reader_fields():
    first = [region([100, 100, 40, 160], 0.58)]
    second = [region([100, 100, 40, 160], 0.58, ja="将来の秘密", speaker="locked")]
    assert score_page_hardness(first, 1000, 1000) == score_page_hardness(second, 1000, 1000)


def test_overlap_and_aligned_fragments_raise_explainable_pressure():
    easy = score_page_hardness([region([100, 100, 40, 160]), region([300, 100, 40, 160])], 1000, 1000)
    hard = score_page_hardness([
        region([100, 100, 40, 160], 0.42),
        region([125, 100, 40, 160], 0.44, sourceMembers=[{}, {}]),
        region([150, 100, 40, 160], 0.46),
    ], 1000, 1000)
    assert hard["score"] > easy["score"]
    assert "overlap_or_fragmentation" in hard["reasons"]
    assert "grouped_source_members" in hard["reasons"]


def test_score_is_bounded_and_bad_geometry_fails_closed():
    result = score_page_hardness([region([0, 0, 100, 100], 0.35)], 100, 100)
    assert 0 <= result["score"] <= 100
    with pytest.raises(ValueError):
        score_page_hardness([region([90, 0, 20, 20])], 100, 100)
    with pytest.raises(ValueError):
        score_page_hardness([region([0, 0, 20, 20], 1.2)], 100, 100)

