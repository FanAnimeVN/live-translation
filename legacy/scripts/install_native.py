"""Per-user native registration for development or a self-contained bundle."""
import argparse
import json
from pathlib import Path
import re
import sys
import winreg
from portable_bundle import BUNDLE_PROFILES,verify_cloud_models

ROOT=Path(sys.executable).resolve().parents[2] if getattr(sys,"frozen",False) else Path(__file__).resolve().parents[1]
HOST="vn.mangalive.companion"
ORIGIN=re.compile(r"chrome-extension://[a-p]{32}/")
REGISTRY={"edge":r"Software\Microsoft\Edge\NativeMessagingHosts",
          "chrome":r"Software\Google\Chrome\NativeMessagingHosts"}


def registry_views():
    """Return the user registry views Edge/Chrome may search.

    A 32-bit browser can prefer the redirected view even when the installer
    itself is 64-bit.  Registering the same validated manifest in both views
    avoids a false NOT_FOUND caused solely by the installer process bitness.
    """
    views=[0]
    for name in ("KEY_WOW64_32KEY", "KEY_WOW64_64KEY"):
        value=getattr(winreg,name,None)
        if isinstance(value,int) and value not in views: views.append(value)
    return views

def registration_files(extension_id,folder,project_root=None):
    """Validate everything before writing config or touching the registry."""
    if not isinstance(extension_id,str) or not re.fullmatch(r"[a-p]{32}",extension_id):
        raise ValueError("ID extension phải có 32 ký tự a–p.")
    folder=Path(folder).resolve();exe=folder/"MangaLiveHost.exe"
    if not exe.is_file():raise ValueError("Chưa có MangaLiveHost.exe. Build companion trước.")
    origin=f"chrome-extension://{extension_id}/"
    cfg=folder/"native-config.json"
    previous=json.loads(cfg.read_text(encoding="utf-8")) if cfg.is_file() else {}
    if not isinstance(previous,dict):raise ValueError("Cấu hình đăng ký cũ không hợp lệ; không tự đặt lại.")
    origins=previous.get("allowedOrigins",[])
    if not isinstance(origins,list) or len(origins)>64 or any(not isinstance(v,str) or not ORIGIN.fullmatch(v) for v in origins):
        raise ValueError("Danh sách extension đã cho phép không hợp lệ; không tự nới quyền.")
    marker=folder/"bundle.json"
    if marker.is_file():
        info=json.loads(marker.read_text(encoding="utf-8"))
        if not isinstance(info,dict) or type(info.get("schema")) is not int or info["schema"]!=1 or info.get("kind")!="portable":
            raise ValueError("Bundle portable không hợp lệ.")
        profile=info.get("profile","offline")
        if profile not in BUNDLE_PROFILES:raise ValueError("Bundle profile không hợp lệ.")
        if not (folder/"models").is_dir() or (profile=="offline" and not (folder/"runtime/llama/llama-server.exe").is_file()):
            raise ValueError("Bundle chưa có models/runtime; không đăng ký bản build dở.")
        if profile=="cloud-first":verify_cloud_models(folder)
        config={"models":str(folder/"models"),"runtime":str(folder/"runtime/llama")}
    else:
        root=Path(project_root or ROOT).resolve()
        python=root/".venv/Scripts/python.exe";entry=root/"companion/entry.py"
        if not python.is_file() or not entry.is_file():
            raise ValueError("Bản development chưa có runtime Python đã provision.")
        config={"python":str(python),"entry":str(entry),"models":str(root/"models"),"runtime":str(root/"runtime/llama")}
    config["allowedOrigins"]=sorted(set([*origins,origin]))
    if "dataRoot" in previous:
        value=previous["dataRoot"]
        if not isinstance(value,str) or not value or not Path(value).is_absolute():
            raise ValueError("Vị trí dữ liệu cũ không hợp lệ; không tự di chuyển bộ nhớ.")
        config["dataRoot"]=value
    manifest={"name":HOST,"description":"Live translation local companion", "path":str(exe),
              "type":"stdio","allowed_origins":config["allowedOrigins"]}
    return config,manifest


def install(extension_id,bundle_dir=None,browser="edge"):
    if browser not in (*REGISTRY,"both"):raise ValueError("Chỉ hỗ trợ Edge/Chrome.")
    folder=Path(bundle_dir).resolve() if bundle_dir is not None else (
        Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else ROOT/"dist/windows")
    config,contents=registration_files(extension_id,folder,project_root=ROOT)
    cfg=folder/"native-config.json"
    cfg.write_text(json.dumps(config,indent=2),encoding="utf-8")
    manifest=folder/(HOST+".json")
    manifest.write_text(json.dumps(contents,indent=2),encoding="utf-8")
    for selected in REGISTRY if browser=="both" else (browser,):
        # REGISTRY already includes NativeMessagingHosts.  Appending it again
        # writes a valid key that the browser never searches.  Verify fresh
        # installs at the documented browser path, not a pre-existing key.
        parent_path=REGISTRY[selected]
        key_path=parent_path+"\\"+HOST
        for view in registry_views():
            # CreateKeyEx needs KEY_CREATE_SUB_KEY when the per-user parent
            # path has not been created yet.  Without it Windows reports an
            # opaque Access Denied and Edge later surfaces NATIVE_HOST_NOT_FOUND.
            access=(getattr(winreg,"KEY_SET_VALUE",0)|getattr(winreg,"KEY_QUERY_VALUE",0)|
                    getattr(winreg,"KEY_CREATE_SUB_KEY",0)|view)
            create=getattr(winreg,"CreateKeyEx",None)
            try:
                if create is None:
                    # Kept for very small test doubles/older embedded Python;
                    # production Windows uses CreateKeyEx so the view is explicit.
                    winreg.CreateKey(winreg.HKEY_CURRENT_USER,parent_path)
                    key=winreg.CreateKey(winreg.HKEY_CURRENT_USER,key_path)
                else:
                    parent=create(winreg.HKEY_CURRENT_USER,parent_path,0,access)
                    try:
                        key=create(winreg.HKEY_CURRENT_USER,key_path,0,access)
                    finally:
                        close=getattr(parent,"Close",None)
                        if close is not None:close()
            except PermissionError as error:
                raise PermissionError(
                    "Windows đang khóa quyền ghi vào nhánh Edge NativeMessagingHosts. "
                    "Hãy chạy companion installer bằng Run as administrator rồi thử lại; "
                    "không cần tắt antivirus hay thay policy Edge."
                ) from error
            with key:
                winreg.SetValueEx(key,"",0,winreg.REG_SZ,str(manifest))
                if hasattr(winreg,"QueryValueEx"):
                    actual,kind=winreg.QueryValueEx(key,"")
                    if kind!=winreg.REG_SZ or Path(actual).resolve()!=manifest.resolve():
                        raise OSError(f"Không xác minh được đăng ký native host ở registry view {view}.")
    return str(manifest)

if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("extension_id")
    parser.add_argument("--bundle-dir");parser.add_argument("--browser",choices=(*REGISTRY,"both"),default="edge")
    args=parser.parse_args()
    print(install(args.extension_id,args.bundle_dir,args.browser))
