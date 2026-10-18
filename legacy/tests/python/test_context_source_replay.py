"""Recorded-text replay, not a model or translation-accuracy benchmark."""
from pathlib import Path
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))


def test_recorded_geometry_does_not_starve_context_or_modify_source():
    from benchmark_context_sources import replay
    report={"cloud":False,"pages":[{"page":"authored","regions":[
        {"id":"a","ja":"鍵は？","sourceMembers":[{"diagnostic":"x"*1800}]},
        {"id":"b","ja":"まだ返していない。","sourceMembers":[{"diagnostic":"y"*1800}]}]}]}
    result=replay(report)
    assert result["aggregate"]=={
        "pages":1,"legacy_retained":0,"current_retained":2,
        "source_records_unchanged":True,"all_retained_text_exact":True,
        "all_reading_order_preserved":True,"all_current_page_excluded":True}
    assert result["rows"][0]["current_bytes"]<=1500
    assert "まだ返していない。" not in str(result)

