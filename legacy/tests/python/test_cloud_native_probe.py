"""Authored native-probe completion checks; no models, Vault or network."""
from copy import deepcopy
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from cloud_native_probe import validate_completed


def result():
    return {"regions": [{"id": f"r{i:03}", "vi": "Authored response", "overlay": "white",
                         "balloon": {"erasePolygons": [[[1, 1], [2, 1], [2, 2]]]}} for i in range(4)]}


def test_probe_requires_all_four_bubbles_not_a_nonempty_partial_page():
    validate_completed(result())
    for count in (0, 1, 3):
        incomplete = result()
        incomplete["regions"] = incomplete["regions"][:count]
        with pytest.raises(AssertionError):
            validate_completed(incomplete)


@pytest.mark.parametrize("patch", [{"id": "r001"}, {"vi": ""}, {"vi": "   "}, {"vi": None},
                                   {"overlay": "label"}, {"balloon": {}}, {"balloon": {"erasePolygons": []}}])
def test_duplicate_empty_or_unintegrated_output_is_not_a_success(patch):
    invalid = deepcopy(result())
    invalid["regions"][0].update(patch)
    with pytest.raises(AssertionError):
        validate_completed(invalid)
