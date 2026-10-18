"""Manual development demo launcher: loopback reader only, no inference/API.

The .cmd is for the reader to open, not browser/extension automation. It never
reads a profile, credential or private dataset, or changes native registration.
"""
import argparse
import http.client
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
URL="http://127.0.0.1:65303/chapter/1"


def reader_ready():
    connection=http.client.HTTPConnection("127.0.0.1",65303,timeout=1)
    try:
        connection.request("GET","/chapter/1")
        response=connection.getresponse()
        return response.status==200 and b"Local QA reader" in response.read(32768)
    except OSError:
        return False
    finally:
        connection.close()


def ensure_reader():
    if reader_ready():return
    # Do not kill or replace a different process which owns this port.
    with socket.socket() as probe:
        try:probe.bind(("127.0.0.1",65303))
        except OSError:raise RuntimeError("Cổng demo 65303 đang được ứng dụng khác sử dụng. Không thay đổi ứng dụng đó.") from None
    child=subprocess.Popen([sys.executable,"-B",str(ROOT/"scripts/fixture_server.py"),"--port","65303"],
        cwd=ROOT,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
    deadline=time.monotonic()+20
    while time.monotonic()<deadline:
        if reader_ready():return
        if child.poll() is not None:break
        time.sleep(.15)
    raise RuntimeError("Chưa mở được trang demo. Không có request OCR/dịch cloud nào được gửi.")


def main(argv=None):
    parser=argparse.ArgumentParser();parser.add_argument("--no-open",action="store_true")
    args=parser.parse_args(argv)
    ensure_reader()
    if not args.no_open:
        os.startfile("microsoft-edge:"+URL)
    return URL


if __name__=="__main__":
    try:print(main())
    except Exception as error:
        if "--no-open" in sys.argv:raise
        from tkinter import Tk,messagebox
        root=Tk();root.withdraw();messagebox.showerror("Live translation · demo",str(error));root.destroy()
        raise SystemExit(1)
