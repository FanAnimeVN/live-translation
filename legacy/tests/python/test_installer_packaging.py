"""A successful freezer exit must not conceal an omitted GUI runtime."""
from pathlib import Path
from types import SimpleNamespace
import json
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
import package as packaging
from manga_live.runtime_build import source_build, RECORD_NAME


def test_installer_missing_tcl_is_rejected_before_freeze_or_overwrite(tmp_path,monkeypatch):
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=1)
    monkeypatch.setattr(packaging.subprocess,"run",run)
    with pytest.raises(RuntimeError,match="Tcl/Tk"):
        packaging.freeze("Install companion","installer/setup.py",tmp_path/"dist",tmp_path/"work",["--onefile","--windowed"])
    assert len(calls)==1 and "PyInstaller" not in calls[0]


def test_installer_freeze_requires_tcl_data_preflight(tmp_path,monkeypatch):
    calls=[]
    def run(command,**kwargs):
        # Never let a failing assertion print the process environment/secrets.
        calls.append((command,{key:kwargs[key] for key in ("timeout","check") if key in kwargs}))
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(packaging.subprocess,"run",run)
    packaging.freeze("Install companion","installer/setup.py",tmp_path/"dist",tmp_path/"work",["--onefile","--windowed"])
    assert len(calls)==2
    assert "tkinter.Tcl()" in calls[0][0][-1]
    assert "tk.tcl" in calls[0][0][-1]
    assert calls[0][1]["timeout"]<=30
    assert "PyInstaller" in calls[1][0] and calls[1][1]["check"] is True


def test_headless_native_host_does_not_require_gui_runtime(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(packaging.subprocess,"run",lambda command,**kwargs:calls.append(command))
    packaging.freeze("MangaLiveHost","companion/launcher.py",tmp_path/"dist",tmp_path/"work",["--onefile","--console"])
    assert len(calls)==1 and "PyInstaller" in calls[0]


def test_standalone_host_embeds_exact_package_identity(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(packaging.subprocess,"run",lambda command,**kwargs:calls.append(command))
    work=tmp_path/"work"
    result=packaging.freeze("MangaLiveHost","companion/entry.py",tmp_path/"dist",work,["--onedir","--console"])
    expected=source_build()
    record=json.loads((work/RECORD_NAME).read_text(encoding="utf-8"))
    assert record=={"v":1,"runtimeBuild":expected} and result==expected
    assert len(calls)==1
    command=calls[0]
    assert command[command.index("--add-data")+1]==str(work/RECORD_NAME)+packaging.os.pathsep+"manga_live"


def test_package_source_change_during_freeze_prevents_a_verified_bundle(tmp_path,monkeypatch):
    values=iter(["pkg-sha256:"+"a"*64,"pkg-sha256:"+"b"*64])
    monkeypatch.setattr(packaging,"source_build",lambda:next(values))
    monkeypatch.setattr(packaging.subprocess,"run",lambda *args,**kwargs:None)
    with pytest.raises(RuntimeError,match="changed during freeze"):
        packaging.freeze("MangaLiveHost","companion/entry.py",tmp_path/"dist",tmp_path/"work",["--onedir"])


def test_build_checks_use_fresh_owned_temp_instead_of_shared_pytest_cache(tmp_path,monkeypatch):
    calls=[]
    monkeypatch.setattr(packaging,"ROOT",tmp_path)
    monkeypatch.setattr(packaging.subprocess,"run",lambda command,**kwargs:calls.append((command,kwargs)))
    packaging.run_checks()
    pytest_command=calls[0][0]
    assert "no:cacheprovider" in pytest_command
    destination=Path(pytest_command[pytest_command.index("--basetemp")+1])
    assert destination.parent.parent==tmp_path/"build"
    assert calls[0][1]["check"] and calls[1][1]["check"]
    assert not destination.parent.exists(),"Only this run's owned temporary test tree is removed"


def test_portable_default_is_cloud_first_and_does_not_stage_llama(tmp_path,monkeypatch):
    calls=[];selected={"schema":1,"ocr":{},"detector":{}}
    monkeypatch.setattr(packaging,"ROOT",tmp_path)
    monkeypatch.setattr(packaging,"run_checks",lambda:calls.append("checks"))
    def freeze(name,entry,dist,work,options):
        destination=dist/name if name=="MangaLiveHost" else dist
        destination.mkdir(parents=True,exist_ok=True)
        (destination/(name+".exe")).write_bytes(b"fixture")
        return "pkg-sha256:"+"a"*64
    def stage_models(root,folder,profile):
        assert profile=="cloud-first"
        (folder/"models.lock.json").write_text(json.dumps(selected))
        calls.append("cloud-models");return selected
    monkeypatch.setattr(packaging,"freeze",freeze)
    monkeypatch.setattr(packaging,"stage_models",stage_models)
    monkeypatch.setattr(packaging,"stage_runtime",lambda *args:pytest.fail("Cloud bundle must not stage llama.cpp"))
    monkeypatch.setattr(packaging,"stage_detector_metadata",lambda *args:None)
    # Match the METADATA API without reading the development environment.
    class Metadata(dict):
        def get_all(self,*args):return []
    monkeypatch.setattr(packaging.metadata,"distribution",lambda name:SimpleNamespace(version="fixture",metadata=Metadata()))
    monkeypatch.setattr(packaging.sys,"argv",["package.py","--mode","portable"])
    packaging.main()
    folder=tmp_path/"dist/portable-cloud-first/MangaLiveHost"
    manifest=json.loads((folder/"bundle.json").read_text())
    assert manifest["profile"]=="cloud-first" and manifest["models"]==["ocr","detector"]
    assert calls==["checks","cloud-models"]
    assert not (folder/"runtime").exists()
