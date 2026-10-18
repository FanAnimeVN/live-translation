from copy import deepcopy
import random

import pytest

from manga_live.translation_schedule import schedule_regions


def seam(a, b, **extra):
    return {"source_ids": [a, b], "source_ink_coverage_preserved": True,
            "erasure_permitted": False, "orientation": "vertical", **extra}


def sources(count):
    return [{"id": f"r{i:03}", "scope": {"key": f"source-{i}"}, "order": i} for i in range(count)]


def boundaries(batches):
    return [sum(map(len, batches[:i])) for i in range(1, len(batches))]


def test_real_page_04_partition_relations_are_not_split_between_requests():
    rows = sources(28)
    evidence = [seam("r015", "r016"), seam("r017", "r019")]
    original = deepcopy(rows)
    batches = schedule_regions(rows, 4, evidence)
    assert len(batches) == 7
    assert all(not (lower < end <= upper) for end in boundaries(batches)
               for lower, upper in ((15, 16), (17, 19)))
    assert rows == original
    assert [row for batch in batches for row in batch] == original
    assert batches[0] == rows[:4]
    assert all(len(batch) <= 6 for batch in batches)


@pytest.mark.parametrize("first", [2, 4])
def test_many_source_relations_never_increase_requests_reorder_or_increase_cuts(first):
    generator = random.Random(47111)
    for count in range(1, 65):
        rows = sources(count)
        evidence = [seam(rows[a]["id"], rows[b]["id"]) for _ in range(min(count, 20))
                    for a, b in [sorted(generator.sample(range(count), 2))]] if count > 1 else []
        baseline = schedule_regions(rows, first)
        actual = schedule_regions(rows, first, evidence)
        assert len(actual) == len(baseline)
        assert len(actual[0]) <= first
        assert all(1 <= len(batch) <= 6 for batch in actual)
        flattened = [row for batch in actual for row in batch]
        assert len(flattened) == count and all(a is b for a, b in zip(flattened, rows))
        forbidden = {end for rel in evidence for a, b in [[int(ident[1:]) for ident in rel["source_ids"]]]
                     for end in range(a+1, b+1)}
        assert sum(end in forbidden for end in boundaries(actual)) <= sum(end in forbidden for end in boundaries(baseline))


@pytest.mark.parametrize("override", [
    {"source_ids": ["r001", "missing"]}, {"source_ids": ["r001", "r001"]},
    {"source_ids": [[], "r002"]}, {"source_ink_coverage_preserved": 1},
    {"erasure_permitted": True}, {"orientation": "guessed"},
])
def test_unverified_or_malformed_relations_cannot_reshape_requests(override):
    rows = sources(3)
    assert schedule_regions(rows, 2, [seam("r001", "r002", **override)]) == schedule_regions(rows, 2)


def test_no_evidence_or_impossible_improvement_keeps_original_boundaries():
    rows = sources(16)
    assert list(map(len, schedule_regions(rows))) == [4, 4, 4, 4]
    # A chain covering every boundary cannot be improved by arbitrary shuffling.
    evidence = [seam(rows[i]["id"], rows[i+1]["id"]) for i in range(15)]
    assert schedule_regions(rows, 4, evidence) == schedule_regions(rows)
    assert schedule_regions([], 4, []) == [[]]
