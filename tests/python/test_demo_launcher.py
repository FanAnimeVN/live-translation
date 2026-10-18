"""Launcher checks without controlling any real browser or starting inference."""
import importlib.util
from pathlib import Path

SCRIPT=Path(__file__).resolve().parents[2]/"scripts/demo_launcher.py"
spec=importlib.util.spec_from_file_location("demo_launcher",SCRIPT)
demo=importlib.util.module_from_spec(spec);spec.loader.exec_module(demo)


def test_ready_reader_never_starts_a_second_process(monkeypatch):
    monkeypatch.setattr(demo,"reader_ready",lambda:True)
    monkeypatch.setattr(demo.subprocess,"Popen",lambda *a,**k:(_ for _ in ()).throw(AssertionError("Duplicate server")))
    demo.ensure_reader()


def test_no_open_validation_never_controls_browser(monkeypatch):
    calls=[]
    monkeypatch.setattr(demo,"ensure_reader",lambda:calls.append("ready"))
    monkeypatch.setattr(demo.os,"startfile",lambda *a:calls.append("browser"))
    assert demo.main(["--no-open"])==demo.URL
    assert calls==["ready"]


def test_manual_launcher_opens_only_fixed_loopback_edge_url(monkeypatch):
    calls=[]
    monkeypatch.setattr(demo,"ensure_reader",lambda:calls.append("ready"))
    monkeypatch.setattr(demo.os,"startfile",calls.append)
    demo.main([])
    assert calls==["ready","microsoft-edge:"+demo.URL]
