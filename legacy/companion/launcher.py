"""Development-bundle native executable; uses the provisioned project runtime."""
import json
import os
from pathlib import Path
import subprocess
import sys
from pipe_relay import relay_process


def external_environment():
    """Do not leak the launcher's bundled DLLs into external Python.

    PyInstaller's SetDllDirectoryW setting is inherited by child processes.
    All launcher imports are complete; it only waits for this one child after
    resetting that process-local search path. The reader's PATH is not edited.
    https://pyinstaller.org/en/stable/common-issues-and-pitfalls.html#launching-external-programs-from-the-frozen-application
    """
    environment=dict(os.environ)
    if getattr(sys,"frozen",False) and sys.platform=="win32":
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL("kernel32",use_last_error=True)
        reset=kernel.SetDllDirectoryW;reset.argtypes=[wintypes.LPCWSTR];reset.restype=wintypes.BOOL
        if not reset(None):raise ctypes.WinError(ctypes.get_last_error())
        bundle=Path(sys._MEIPASS).resolve()
        def bundled(value):
            try:return Path(value).resolve().is_relative_to(bundle)
            except (OSError,ValueError):return False
        if "PATH" in environment:
            environment["PATH"]=os.pathsep.join(p for p in environment["PATH"].split(os.pathsep) if not bundled(p))
    return environment

def main():
    base=Path(sys.executable).resolve().parent if getattr(sys,"frozen",False) else Path(__file__).resolve().parent
    config=base/"native-config.json"
    installation=json.loads(config.read_text(encoding="utf-8"))
    origin=next((arg for arg in sys.argv[1:] if arg.startswith("chrome-extension://")),"")
    if origin not in installation["allowedOrigins"]:return 2
    command=[installation["python"],installation["entry"],origin,"--config",str(config)]
    return relay_process(command,sys.stdin.buffer,sys.stdout.buffer,external_environment())

if __name__=="__main__":raise SystemExit(main())
