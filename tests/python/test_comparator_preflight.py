"""Preflight reads source as data; it cannot execute or approve upstream."""
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
import comparator_preflight as preflight


def test_model_mapping_is_parsed_without_executing_source():
    source='raise RuntimeError("MUST NOT EXECUTE")\nclass Fixture:\n _MODEL_MAPPING={"model":{"url":"https://example.invalid/model.ckpt","hash":"'+'a'*64+'"}}\n'
    result=preflight.model_mapping(source,"Fixture")
    assert result["model"]["hash"]=="a"*64


def test_nonliteral_mapping_is_not_evaluated():
    with pytest.raises(ValueError):preflight.model_mapping("class Fixture:\n _MODEL_MAPPING=load_code()","Fixture")


def test_io_scan_reports_image_log_and_network_paths_with_locations():
    source='def sample():\n cv2.imwrite("private.png", pixels)\n image.save("other.png")\n open("story.log", "a")\n await model.download()\n'
    result=preflight.io_evidence(source,"fixture.py")
    assert {row["kind"] for row in result}>={"image_write","file_write","model_download"}
    assert all(row["path"]=="fixture.py" and type(row["line"]) is int for row in result)


def test_snapshot_requires_pinned_commit_and_stays_blocked_without_runtime_audit():
    files={"LICENSE":"GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007"}
    for name,(path,cls) in preflight.MODEL_CLASSES.items():
        text=files.get(path,"")
        text+='\nclass '+cls+':\n _MODEL_MAPPING={"model":{"url":"https://example.invalid/'+name+'.ckpt","hash":"'+'b'*64+'"}}\n'
        files[path]=text
    for path in preflight.AUDIT_FILES:files.setdefault(path,"# fixture\n")
    result=preflight.snapshot(preflight.COMMIT,files.__getitem__)
    assert result["source_verified"] and not result["execution_allowed"]
    assert not result["fresh_inference"] and result["cloud"] is False
    assert result["primary_comparator"]=="manga-image-translator"
    assert len(result["models"])==3 and result["blockers"]
    assert all(len(row["sha256"])==64 for row in result["source_files"])
    with pytest.raises(ValueError):preflight.snapshot("0"*40,files.__getitem__)


def test_model_hash_must_be_complete_and_weights_are_not_assumed_installed():
    with pytest.raises(ValueError):
        preflight.model_mapping('class Fixture:\n _MODEL_MAPPING={"model":{"url":"https://example.invalid/m","hash":""}}',"Fixture")
