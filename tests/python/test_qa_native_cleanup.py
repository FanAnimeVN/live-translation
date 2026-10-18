import importlib.util
from pathlib import Path


def module():
    path = Path(__file__).resolve().parents[2]/"scripts/qa_native_cleanup.py"
    spec = importlib.util.spec_from_file_location("qa_native_cleanup", path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


def test_qa_cleanup_requires_exact_config_entry_executable_and_origin(tmp_path):
    helper = module()
    config = tmp_path/"mangalive-real-browser-test"/"native-config.json"
    origin = "chrome-extension://"+"a"*32+"/"
    entry = str((helper.ROOT/"companion/entry.py").resolve())
    python = str((helper.ROOT/".venv/Scripts/python.exe").resolve())
    identity = (config, origin, {entry}, {python})
    argv = [python, entry, origin, "--config", str(config)]
    assert helper.matches_owned(argv, python, identity)
    assert not helper.matches_owned([python, entry, origin], python, identity)
    assert not helper.matches_owned(argv, str(tmp_path/"other/python.exe"), identity)
    assert not helper.matches_owned([python, str(tmp_path/"other.py"), origin, "--config", str(config)], python, identity)
    assert not helper.matches_owned([python, entry, origin, "--config", str(tmp_path/"other.json")], python, identity)
    assert not helper.matches_owned([python, entry, "chrome-extension://"+"b"*32+"/", "--config", str(config)], python, identity)
    assert not helper.matches_owned(None, python, identity)


def test_qa_cleanup_refuses_workspace_or_real_reader_profile(tmp_path, monkeypatch):
    import json
    import pytest
    helper = module()
    monkeypatch.setattr(helper.tempfile, "gettempdir", lambda: str(tmp_path))
    with pytest.raises(ValueError):
        helper.cleanup_configuration(helper.ROOT)
    folder = tmp_path/"mangalive-real-browser-test"
    folder.mkdir()
    config = folder/"native-config.json"
    config.write_text(json.dumps({"dataRoot": str(tmp_path/"reader"), "allowedOrigins": ["chrome-extension://"+"a"*32+"/"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="reader"):
        helper.cleanup_configuration(folder)
    config.write_text(json.dumps({"dataRoot": str(folder/"data"), "allowedOrigins": ["*"]}), encoding="utf-8")
    with pytest.raises(ValueError, match="origin"):
        helper.cleanup_configuration(folder)


def test_qa_cleanup_matches_only_its_exact_command_bootstrap(tmp_path):
    import os
    helper = module()
    config = tmp_path/"mangalive-real-browser-test"/"native-config.json"
    origin = "chrome-extension://"+"a"*32+"/"
    executable = str((Path(os.environ.get("SystemRoot", "C:/Windows"))/"System32/cmd.exe").resolve())
    bootstrap = str(config.parent/"MangaLiveHost.cmd")
    identity = (config, origin, set(), set())
    argv = [executable, "/d", "/s", "/c", f'"{bootstrap}" {origin} --parent-window=0']
    assert helper.matches_owned(argv, executable, identity)
    assert not helper.matches_owned([executable, "/d", "/s", "/c", f'"{bootstrap}other" {origin}'], executable, identity)
    assert not helper.matches_owned([executable, "/d", "/s", "/c", f'"{bootstrap}" {origin}other'], executable, identity)
    assert not helper.matches_owned([executable, "/c", f'"{bootstrap}" {origin}'], executable, identity)


def test_image_qa_entry_is_owned_only_with_the_isolated_config_and_origin(tmp_path, monkeypatch):
    import json
    helper = module()
    monkeypatch.setattr(helper.tempfile, "gettempdir", lambda: str(tmp_path))
    folder = tmp_path/"mangalive-real-browser-image"
    folder.mkdir()
    origin = "chrome-extension://"+"a"*32+"/"
    config = folder/"native-config.json"
    config.write_text(json.dumps({"dataRoot":str(folder/"data"),"allowedOrigins":[origin]}),encoding="utf-8")
    identity = helper.cleanup_configuration(folder)
    python = str((helper.ROOT/".venv/Scripts/python.exe").resolve())
    entry = str((helper.ROOT/"scripts/qa_image_entry.py").resolve())
    argv = [python, entry, origin, "--config", str(config)]
    assert helper.matches_owned(argv, python, identity)
    assert not helper.matches_owned([python,entry,origin,"--config",str(tmp_path/"reader.json")],python,identity)
