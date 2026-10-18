"""Only disposable QA registrations; never replace the reader's native host."""
import argparse
import json
from pathlib import Path
import re
import tempfile
import winreg

BASE=r"Software\Microsoft\Edge\NativeMessagingHosts"
SOURCE_ROOT=Path(__file__).resolve().parents[1]


def fixture_manifest(host,path):
    if not isinstance(host,str) or not re.fullmatch(r"vn\.mangalive\.qa\.[a-f0-9]{32}",host):
        raise ValueError("Only a random, QA-only host name is allowed")
    path=Path(path).resolve();folder=path.parent;temporary=Path(tempfile.gettempdir()).resolve()
    if not folder.is_relative_to(temporary) or not folder.name.startswith("mangalive-real-browser-"):
        raise ValueError("QA registration must live in a disposable system-temp folder")
    data=json.loads(path.read_text(encoding="utf-8"))
    origin=data.get("allowed_origins")
    if (data.get("name")!=host or data.get("type")!="stdio" or not isinstance(origin,list) or
            len(origin)!=1 or not re.fullmatch(r"chrome-extension://[a-p]{32}/",origin[0])):
        raise ValueError("QA host must have exactly one explicit extension origin")
    config=json.loads((folder/"native-config.json").read_text(encoding="utf-8"))
    if config.get("allowedOrigins")!=origin or Path(config.get("dataRoot","")).resolve()!=folder/"data":
        raise ValueError("QA data and access must be isolated from reader profiles")
    executable=Path(data.get("path","")).resolve()
    if not executable.is_file():raise ValueError("QA executable is missing")
    if executable==(folder/"MangaLiveHost.cmd").resolve():
        python=SOURCE_ROOT/".venv/Scripts/python.exe"
        entry=Path(config.get("entry","")).resolve()
        if Path(config.get("python","")).resolve()!=python.resolve() or entry not in (
                (SOURCE_ROOT/"scripts/qa_native_entry.py").resolve(),(SOURCE_ROOT/"scripts/qa_relay_entry.py").resolve(),
                (SOURCE_ROOT/"scripts/qa_cloud_entry.py").resolve(),(SOURCE_ROOT/"scripts/qa_render_replay_entry.py").resolve(),
                (SOURCE_ROOT/"scripts/qa_image_entry.py").resolve(),
                (SOURCE_ROOT/"companion/entry.py").resolve()):
            raise ValueError("QA direct source must use this project's interpreter and entry")
        if entry==(SOURCE_ROOT/"scripts/qa_image_entry.py").resolve():
            from qa_cloud_entry import validated_options
            _,budget,_=validated_options(config)
            if config["qaCloud"].get("imageConsent") is not True or budget>.04:
                raise ValueError("Image QA requires separate consent and <=0.04 USD")
        paths=(str(python),str(entry),str(folder/"native-config.json"))
        if any(any(c in value for c in '\"%&|<>^\r\n') for value in paths):
            raise ValueError("Unsafe QA bootstrap path")
        expected=f'@echo off\n"{python}" "{entry}" %* --config "{folder / "native-config.json"}" 2>NUL\n'
        if executable.read_text(encoding="utf-8").replace("\r\n","\n")!=expected:
            raise ValueError("QA bootstrap content changed")
    elif executable!=(folder/"MangaLiveHost.exe").resolve():
        raise ValueError("QA manifest must select its own staged executable")
    return path


def register(host,path):
    path=fixture_manifest(host,path);key_path=BASE+"\\"+host
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key_path):pass
    except FileNotFoundError:pass
    else:raise ValueError("Refusing to overwrite an existing native registration")
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,key_path,access=winreg.KEY_READ|winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key,"",0,winreg.REG_SZ,str(path))


def unregister(host,path):
    path=fixture_manifest(host,path);key_path=BASE+"\\"+host
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,key_path) as key:
            value,kind=winreg.QueryValueEx(key,"")
            children,values,_=winreg.QueryInfoKey(key)
            if kind!=winreg.REG_SZ or Path(value).resolve()!=path or children or values!=1:
                raise ValueError("QA registration changed; refusing to remove it")
    except FileNotFoundError:return
    winreg.DeleteKey(winreg.HKEY_CURRENT_USER,key_path)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("action",choices=("register","unregister"))
    parser.add_argument("host");parser.add_argument("manifest");args=parser.parse_args()
    (register if args.action=="register" else unregister)(args.host,args.manifest)
    print(json.dumps({"action":args.action,"production_registration_changed":False}))
