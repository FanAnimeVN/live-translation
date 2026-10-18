from copy import deepcopy
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
from probe_disjoint_recovery import recovery_proposals


def region(key,box):
    return {"id":key,"bbox":box,"ja":"「…」","order":0,"overlay":"white","balloon":{"must_not_erase":True},
            "sourceMembers":[{"polygon":[[box[0],box[1]]],"score":.9}],
            "scope":{"key":"source-"+key,"action":"translate","memory":True}}


def test_primary_anchors_quotes_exclusions_and_source_records_never_change():
    primary=[region("r000",[0,0,10,40])]
    primary[0]["scope"].update(reason="reader",action="defer")
    original=deepcopy(primary)
    secondary=[region("r000",[2,0,9,40]),region("r001",[60,0,10,40])]
    snapshot=deepcopy(secondary)
    result,decisions=recovery_proposals(primary,secondary)
    assert result[:len(primary)]==primary==original and secondary==snapshot
    assert [d["reason"] for d in decisions]==["overlaps_source_or_exclusion","review_proposal"]
    proposal=result[-1]
    assert proposal["id"]=="recovery-r001" and proposal["scope"]["key"]=="source-r001"
    assert proposal["ja"]==secondary[-1]["ja"] and proposal["sourceMembers"]==secondary[-1]["sourceMembers"]
    assert proposal["review"] and proposal["scope"]["memory"] is False and proposal["erasure_permitted"] is False
    assert proposal["scope"]["action"]=="defer" and proposal["scope"]["reason"]=="visual_review"
    assert "balloon" not in proposal and proposal["overlay"]=="label"


def test_reader_choice_and_captured_speaker_never_rebound_as_new_region():
    candidates=[region("r000",[0,0,10,10]),region("r001",[30,0,10,10])]
    candidates[0]["scope"]["reason"]="reader";candidates[1]["speaker"]="confirmed-person"
    result,decisions=recovery_proposals([],candidates)
    assert result==[] and all(d["reason"]=="reader_owned" for d in decisions)


def test_excluded_geometry_and_budget_stay_recorded_and_existing_defer_survives():
    candidates=[region("r000",[0,0,10,10]),region("r001",[30,0,10,10]),region("r002",[60,0,10,10])]
    candidates[1]["scope"]["action"]="defer"
    result,decisions=recovery_proposals([],candidates,max_added=1,exclusion_boxes=([0,0,10,10],))
    assert [d["reason"] for d in decisions]==["overlaps_source_or_exclusion","review_proposal","budget_deferred"]
    assert len(result)==1 and result[0]["scope"]["action"]=="defer"


@pytest.mark.parametrize("box",[[0,0,-1,5],[float("nan"),0,5,5],[0,0,5,float("inf")],[-1,0,5,5]])
def test_invalid_geometry_is_not_treated_as_safe_empty_space(box):
    with pytest.raises(ValueError):recovery_proposals([],[region("bad",box)])


def test_recovery_never_exceeds_page_limit_or_drops_budget_evidence():
    primary=[region(f"r{index:03}",[index*20,0,10,10]) for index in range(64)]
    candidate=region("extra",[2000,0,10,10])
    result,decisions=recovery_proposals(primary,[candidate])
    assert result==primary and decisions==[{"source_id":"extra","reason":"budget_deferred"}]
