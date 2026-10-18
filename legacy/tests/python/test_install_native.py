"""Registration fixtures never touch the real Windows registry or profile."""
import json
from pathlib import Path
import sys
import pytest

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/"scripts"))
import install_native

EXTENSION="a"*32


def portable(tmp_path):
    folder=tmp_path/"portable"
    folder.mkdir()
    (folder/"MangaLiveHost.exe").write_bytes(b"fixture")
    (folder/"bundle.json").write_text(json.dumps({"schema":1,"kind":"portable","version":"0.1.0"}))
    (folder/"models").mkdir()
    runtime=folder/"runtime/llama";runtime.mkdir(parents=True)
    (runtime/"llama-server.exe").write_bytes(b"fixture")
    return folder


def test_portable_registration_needs_no_development_python_or_entry(tmp_path):
    folder=portable(tmp_path)
    config,manifest=install_native.registration_files(EXTENSION,folder)
    assert "python" not in config and "entry" not in config
    assert config["models"]==str(folder/"models")
    assert config["runtime"]==str(folder/"runtime/llama")
    assert manifest["path"]==str(folder/"MangaLiveHost.exe")
    assert manifest["allowed_origins"]==[f"chrome-extension://{EXTENSION}/"]


def test_development_registration_keeps_existing_layout(tmp_path):
    folder=tmp_path/"dist/windows";folder.mkdir(parents=True)
    (folder/"MangaLiveHost.exe").write_bytes(b"fixture")
    python=tmp_path/".venv/Scripts/python.exe";python.parent.mkdir(parents=True);python.write_bytes(b"fixture")
    entry=tmp_path/"companion/entry.py";entry.parent.mkdir();entry.write_text("fixture")
    config,_=install_native.registration_files(EXTENSION,folder,project_root=tmp_path)
    assert config["python"]==str(python) and config["entry"]==str(entry)
    assert config["models"]==str(tmp_path/"models")


def test_registration_preserves_only_valid_explicit_extension_origins(tmp_path):
    folder=portable(tmp_path);origin=f"chrome-extension://{'b'*32}/"
    (folder/"native-config.json").write_text(json.dumps({"allowedOrigins":[origin,origin]}))
    config,manifest=install_native.registration_files(EXTENSION,folder)
    assert config["allowedOrigins"]==manifest["allowed_origins"]==sorted([origin,f"chrome-extension://{EXTENSION}/"])


@pytest.mark.parametrize("origins",[None,"*",["*"],["https://example.com/"],["chrome-extension://invalid/"]])
def test_invalid_existing_origin_list_is_not_silently_widened(tmp_path,origins):
    folder=portable(tmp_path)
    (folder/"native-config.json").write_text(json.dumps({"allowedOrigins":origins}))
    with pytest.raises(ValueError):install_native.registration_files(EXTENSION,folder)


@pytest.mark.parametrize("identifier",["", "a"*31, "a"*33, "z"*32, "../not-an-id"])
def test_bad_extension_id_is_rejected_before_registration(tmp_path,identifier):
    with pytest.raises(ValueError):install_native.registration_files(identifier,tmp_path)
    assert list(tmp_path.iterdir())==[]


def test_portable_marker_does_not_hide_missing_llama_runtime(tmp_path):
    folder=portable(tmp_path)
    (folder/"runtime/llama/llama-server.exe").unlink()
    with pytest.raises(ValueError):install_native.registration_files(EXTENSION,folder)


def cloud_portable(tmp_path):
    import hashlib
    folder=tmp_path/"cloud-portable";folder.mkdir()
    (folder/"MangaLiveHost.exe").write_bytes(b"fixture")
    (folder/"bundle.json").write_text(json.dumps({"schema":1,"kind":"portable","profile":"cloud-first"}))
    manifest={"schema":1}
    for name in ("ocr","detector"):
        data=(name+" fixture").encode();path=folder/"models"/name/"weights.bin"
        path.parent.mkdir(parents=True);path.write_bytes(data)
        manifest[name]={"files":{"weights.bin":{"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}}}
    (folder/"models.lock.json").write_text(json.dumps(manifest))
    return folder


def test_cloud_first_registration_requires_no_llama_or_development_checkout(tmp_path):
    folder=cloud_portable(tmp_path)
    previous={"allowedOrigins":[f"chrome-extension://{'b'*32}/"],"dataRoot":str(tmp_path/"reader-data")}
    (folder/"native-config.json").write_text(json.dumps(previous))
    config,manifest=install_native.registration_files(EXTENSION,folder)
    assert "python" not in config and "entry" not in config
    assert config["models"]==str(folder/"models")
    assert config["runtime"]==str(folder/"runtime/llama")
    assert config["dataRoot"]==previous["dataRoot"]
    assert set(manifest["allowed_origins"])=={*previous["allowedOrigins"],f"chrome-extension://{EXTENSION}/"}
    assert not (folder/"runtime").exists()


@pytest.mark.parametrize("missing",["models.lock.json","models/ocr/weights.bin","models/detector/weights.bin"])
def test_cloud_first_marker_cannot_register_incomplete_vision_assets(tmp_path,missing):
    folder=cloud_portable(tmp_path);(folder/missing).unlink()
    with pytest.raises(ValueError):install_native.registration_files(EXTENSION,folder)


def test_cloud_first_registration_rejects_corrupted_model(tmp_path):
    folder=cloud_portable(tmp_path);(folder/"models/ocr/weights.bin").write_bytes(b"broken")
    with pytest.raises(ValueError):install_native.registration_files(EXTENSION,folder)


def test_unknown_profile_does_not_bypass_portable_completeness(tmp_path):
    folder=portable(tmp_path)
    (folder/"bundle.json").write_text(json.dumps({"schema":1,"kind":"portable","profile":"whatever"}))
    with pytest.raises(ValueError):install_native.registration_files(EXTENSION,folder)


def test_registry_write_is_per_user_and_points_at_the_selected_bundle(tmp_path,monkeypatch):
    folder=portable(tmp_path);operations=[]
    class Key:
        def __enter__(self):return self
        def __exit__(self,*args):return False
    def create(hive,path,*args):operations.append((hive,path,args));return Key()
    monkeypatch.setattr(install_native.winreg,"CreateKey",create)
    monkeypatch.setattr(install_native.winreg,"CreateKeyEx",create)
    monkeypatch.setattr(install_native.winreg,"QueryValueEx",lambda *args:(str(folder/(install_native.HOST+".json")),install_native.winreg.REG_SZ))
    monkeypatch.setattr(install_native,"registry_views",lambda:[0])
    monkeypatch.setattr(install_native.winreg,"SetValueEx",lambda *args:operations.append(args))
    manifest=Path(install_native.install(EXTENSION,bundle_dir=folder))
    assert manifest.parent==folder
    assert operations[0][0]==install_native.winreg.HKEY_CURRENT_USER
    assert operations[-1][-1]==str(manifest)
    assert json.loads(manifest.read_text())["path"]==str(folder/"MangaLiveHost.exe")


def test_registry_views_are_explicit_and_both_are_written(tmp_path,monkeypatch):
    folder=portable(tmp_path);operations=[]
    class Key:
        def __enter__(self):return self
        def __exit__(self,*args):return False
    def create(hive,path,*args):operations.append((hive,path,args));return Key()
    monkeypatch.setattr(install_native.winreg,"CreateKeyEx",create)
    monkeypatch.setattr(install_native.winreg,"SetValueEx",lambda *args:operations.append(args))
    manifest_path=folder/(install_native.HOST+".json")
    monkeypatch.setattr(install_native.winreg,"QueryValueEx",lambda *args:(str(manifest_path),install_native.winreg.REG_SZ))
    monkeypatch.setattr(install_native,"registry_views",lambda:[0,512,256])
    install_native.install(EXTENSION,bundle_dir=folder)
    expected_base=(install_native.winreg.KEY_SET_VALUE|install_native.winreg.KEY_QUERY_VALUE|
                   install_native.winreg.KEY_CREATE_SUB_KEY)
    create_calls=[item for item in operations if len(item)==3]
    assert [item[2][1] for item in create_calls]==[expected_base|v for v in (0,512,256) for _ in (0,1)]


@pytest.mark.parametrize("browser,bases",[
    ("edge",[r"Software\Microsoft\Edge\NativeMessagingHosts"]),
    ("chrome",[r"Software\Google\Chrome\NativeMessagingHosts"]),
    ("both",[r"Software\Microsoft\Edge\NativeMessagingHosts",
             r"Software\Google\Chrome\NativeMessagingHosts"]),
])
def test_fresh_install_is_discoverable_at_browser_documented_path(tmp_path,monkeypatch,browser,bases):
    """An existing production registration must not hide a wrong installer path."""
    folder=portable(tmp_path);rows={};created=[]
    class Key:
        def __init__(self,path,view):self.path=path;self.view=view
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def Close(self):pass
    def create(hive,path,reserved,access):
        assert hive==install_native.winreg.HKEY_CURRENT_USER
        view=access&(install_native.winreg.KEY_WOW64_32KEY|install_native.winreg.KEY_WOW64_64KEY)
        rows.setdefault((path,view),{});created.append(path)
        return Key(path,view)
    def set_value(key,name,reserved,kind,value):rows[(key.path,key.view)][name]=(value,kind)
    monkeypatch.setattr(install_native.winreg,"CreateKeyEx",create)
    monkeypatch.setattr(install_native.winreg,"SetValueEx",set_value)
    monkeypatch.setattr(install_native.winreg,"QueryValueEx",lambda key,name:rows[(key.path,key.view)][name])
    views=[0,install_native.winreg.KEY_WOW64_32KEY,install_native.winreg.KEY_WOW64_64KEY]
    monkeypatch.setattr(install_native,"registry_views",lambda:views)
    manifest=install_native.install(EXTENSION,bundle_dir=folder,browser=browser)
    expected_paths={base+"\\vn.mangalive.companion" for base in bases}
    for key_path in expected_paths:
        for view in views:
            assert rows.get((key_path,view),{}).get("")==(
                manifest,install_native.winreg.REG_SZ), "Fresh install cannot be discovered by the browser"
    assert set(created)==set(bases)|expected_paths
