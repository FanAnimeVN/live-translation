"""Small generated assets, never copy real weights, private data or executables."""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import sys
import zipfile
from types import SimpleNamespace
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
import portable_bundle as bundle


def files(tmp_path):
    folder=tmp_path/"bundle";folder.mkdir()
    for name in bundle.RUNTIME_FILES:(folder/name).write_bytes(name.encode())
    (folder/"bundle.json").write_text(json.dumps({"schema":1,"kind":"portable"}))
    (folder/"_internal").mkdir()
    (folder/"_internal/module.py").write_text("fixture")
    return folder


def test_checksum_roundtrip_covers_runtime_and_reports_progress(tmp_path):
    folder=files(tmp_path);index=bundle.write_checksums(folder);progress=[]
    result=bundle.verify_bundle(folder,lambda *value:progress.append(value))
    assert result["files"]==len(index["files"])==5
    assert progress[-1]==(5,5)
    assert result["bytes"]==sum(row["bytes"] for row in index["files"].values())


@pytest.mark.parametrize("path",["../escape","/escape","C:/escape","..\\escape",""])
def test_asset_paths_cannot_escape_selected_bundle(tmp_path,path):
    with pytest.raises(ValueError):bundle.target(tmp_path,path)


def test_private_registration_config_is_never_shipped(tmp_path):
    folder=files(tmp_path)
    (folder/"native-config.json").write_text('{"dataRoot":"private-user-path"}')
    with pytest.raises(ValueError):bundle.write_checksums(folder)
    assert not (folder/"checksums.json").exists()


def test_corruption_prevents_bundle_verification(tmp_path):
    folder=files(tmp_path);bundle.write_checksums(folder)
    (folder/"MangaLiveHost.exe").write_bytes(b"changed")
    with pytest.raises(ValueError):bundle.verify_bundle(folder)


def test_untrusted_index_path_is_checked_before_reading(tmp_path):
    folder=files(tmp_path);index=bundle.write_checksums(folder)
    index["files"]["../outside"]={"bytes":0,"sha256":"a"*64}
    (folder/"checksums.json").write_text(json.dumps(index))
    with pytest.raises(ValueError):bundle.verify_bundle(folder)


def test_models_are_pinned_and_a_failed_source_does_not_replace_destination(tmp_path,monkeypatch):
    root=tmp_path/"project";source=root/"models/ocr/weights.bin";source.parent.mkdir(parents=True)
    source.write_bytes(b"pinned")
    manifest={"schema":1,"ocr":{"files":{"weights.bin":{"bytes":6,"sha256":hashlib.sha256(b"pinned").hexdigest()}}}}
    (root/"models.lock.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(bundle,"MODEL_SET",("ocr",))
    folder=tmp_path/"bundle"
    bundle.stage_models(root,folder)
    assert (folder/"models/ocr/weights.bin").read_bytes()==b"pinned"
    source.write_bytes(b"broken")
    with pytest.raises(ValueError):bundle.stage_models(root,folder)
    assert (folder/"models/ocr/weights.bin").read_bytes()==b"pinned"


def test_runtime_archive_traversal_is_rejected_before_extracting_files(tmp_path,monkeypatch):
    root=tmp_path/"project";archive=root/"runtime/test.zip";archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive,"w") as file:
        file.writestr("llama-server.exe",b"fixture")
        file.writestr("../../../outside",b"bad")
    monkeypatch.setattr(bundle,"FILENAME","test.zip")
    monkeypatch.setattr(bundle,"SPEC",{"bytes":archive.stat().st_size,"sha256":bundle.sha256(archive)})
    folder=tmp_path/"bundle"
    with pytest.raises(ValueError):bundle.stage_runtime(root,folder)
    assert not (folder/"runtime/llama/llama-server.exe").exists()
    assert not (tmp_path/"outside").exists()


def test_detector_metadata_is_real_and_excludes_private_installation_paths(tmp_path,monkeypatch):
    name="opencv-contrib-python";relative=Path("opencv_contrib_python-4.10.0.dist-info/METADATA")
    installed=tmp_path/"installed";source=installed/relative;source.parent.mkdir(parents=True)
    source.write_text("Name: opencv-contrib-python\nVersion: 4.10.0\n")
    (source.parent/"direct_url.json").write_text('{"url":"private-local-path"}')
    info=SimpleNamespace(files=[relative,relative.with_name("direct_url.json")],locate_file=lambda path:installed/path)
    monkeypatch.setattr(bundle,"DETECTOR_METADATA",(name,))
    folder=tmp_path/"bundle";bundle.stage_detector_metadata(folder,lambda name:info)
    assert (folder/"_internal"/relative).read_bytes()==source.read_bytes()
    assert not (folder/"_internal"/relative.with_name("direct_url.json")).exists()


def test_missing_dependency_metadata_is_not_fabricated(tmp_path,monkeypatch):
    monkeypatch.setattr(bundle,"DETECTOR_METADATA",("fixture",))
    with pytest.raises(ValueError):bundle.stage_detector_metadata(tmp_path,lambda name:SimpleNamespace(files=[]))


def test_detector_sampler_metadata_is_discoverable_without_a_development_environment(tmp_path):
    # Regression: PaddleX eagerly creates PDFReaderBackend for image sampling.
    # The DLL was present, but importlib.metadata could not find pypdfium2.
    required=("opencv-contrib-python","pyclipper","shapely","pypdfium2")
    assert set(required)<=set(bundle.DETECTOR_METADATA)
    installed=tmp_path/"installed";installed.mkdir();fixtures={}
    for name in bundle.DETECTOR_METADATA:
        relative=Path(name.replace("-","_")+"-1.0.dist-info/METADATA")
        source=installed/relative;source.parent.mkdir();source.write_text("Name: "+name+"\nVersion: 1.0\n")
        fixtures[name]=SimpleNamespace(files=[relative],locate_file=lambda path:installed/path)
    folder=tmp_path/"bundle";bundle.stage_detector_metadata(folder,fixtures.__getitem__)
    discovered={entry.metadata["Name"]:entry.version for entry in metadata.distributions(path=[str(folder/"_internal")])}
    assert all(discovered.get(name)=="1.0" for name in required)


def test_cloud_first_stages_only_pinned_ocr_and_detector_without_local_llms(tmp_path):
    root=tmp_path/"project";manifest={"schema":1}
    for name in ("ocr","detector"):
        content=(name+" fixture").encode()
        source=root/"models"/name/"weights.bin";source.parent.mkdir(parents=True)
        source.write_bytes(content)
        manifest[name]={"revision":"a"*40,"files":{"weights.bin":{
            "bytes":len(content),"sha256":hashlib.sha256(content).hexdigest()}}}
    # No translation/summarizer weights or llama.cpp archive exist at all.
    (root/"models.lock.json").write_text(json.dumps(manifest))
    folder=tmp_path/"bundle"
    selected=bundle.stage_models(root,folder,profile="cloud-first")
    assert set(selected)=={"schema","ocr","detector"}
    assert {p.name for p in (folder/"models").iterdir()}=={"ocr","detector"}
    assert not (folder/"runtime").exists()
    assert json.loads((folder/"models.lock.json").read_text())==selected


def test_unknown_bundle_profile_is_rejected_before_copying_models(tmp_path):
    with pytest.raises(ValueError,match="profile"):
        bundle.stage_models(tmp_path/"missing",tmp_path/"output",profile="cloud-ish")
    assert not (tmp_path/"output").exists()


@pytest.mark.parametrize("relative",["models/translation/extra.gguf","models/summarizer/extra.gguf",
                                     "runtime/llama/llama-server.exe"])
def test_cloud_first_inventory_rejects_leftover_local_llm_assets(tmp_path,relative):
    folder=files(tmp_path)
    (folder/"bundle.json").write_text(json.dumps({"schema":1,"kind":"portable","profile":"cloud-first"}))
    asset=folder/relative;asset.parent.mkdir(parents=True,exist_ok=True);asset.write_bytes(b"leftover")
    with pytest.raises(ValueError,match="cloud-first"):
        bundle.write_checksums(folder)
