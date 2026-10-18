import ctypes
import os
import sys
from types import SimpleNamespace

import launcher


def test_frozen_launcher_resets_dll_search_before_external_python(monkeypatch):
    calls=[]
    class Reset:
        def __call__(self,path):calls.append(path);return 1
    reset=Reset()
    monkeypatch.setattr(sys,"frozen",True,raising=False)
    monkeypatch.setattr(sys,"_MEIPASS",r"C:\QA\_MEI123",raising=False)
    monkeypatch.setattr(ctypes,"WinDLL",lambda *args,**kwargs:SimpleNamespace(SetDllDirectoryW=reset))
    monkeypatch.setenv("PATH",r"C:\Windows\System32;C:\QA\_MEI123;C:\QA\_MEI123\bin;C:\QA\_MEI1234\bin")
    environment=launcher.external_environment()
    assert calls==[None]
    assert environment["PATH"]==r"C:\Windows\System32;C:\QA\_MEI1234\bin"
    assert r"C:\QA\_MEI123;" in os.environ["PATH"]  # Never rewrite user's environment.


def test_unfrozen_launcher_leaves_environment_alone(monkeypatch):
    monkeypatch.setattr(sys,"frozen",False,raising=False)
    monkeypatch.setattr(ctypes,"WinDLL",lambda *a,**kw:(_ for _ in ()).throw(AssertionError("No global DLL change")))
    assert launcher.external_environment()==dict(os.environ)
