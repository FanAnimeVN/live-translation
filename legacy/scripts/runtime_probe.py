"""Small DLL-import probe: don't load models or contact a network."""
import argparse
import subprocess
import sys
import threading
import time
import queue
import importlib
from pathlib import Path

parser=argparse.ArgumentParser();parser.add_argument("--case",choices=("main","worker","primed","reader"),default="worker");parser.add_argument("--child",action="store_true")
parser.add_argument("--input-stream",choices=("buffered","raw","win32"),default="buffered")
parser.add_argument("--library",choices=("numpy","torch","paddleocr"),default="numpy")
parser.add_argument("--no-window",action="store_true")
parser.add_argument("--quiet-stderr",action="store_true")
parser.add_argument("--timeout",type=int,choices=(5,20,40),default=5);args=parser.parse_args()

if not args.child and args.case!="main":
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"companion"))
    from manga_live.process_lifetime import own_process
    child=subprocess.Popen([sys.executable,__file__,"--case",args.case,"--input-stream",args.input_stream,"--library",args.library,"--child"],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL if args.quiet_stderr else subprocess.PIPE,
        creationflags=subprocess.CREATE_NO_WINDOW if args.no_window and sys.platform=="win32" else 0)
    lifetime=own_process(child)
    lines=queue.Queue()
    def reader():
        for line in child.stdout:lines.put(line.decode().strip())
    threading.Thread(target=reader,daemon=True).start()
    child.stdin.write(b"test");child.stdin.flush()
    try:
        line=lines.get(timeout=args.timeout);print(line,flush=True)
        if args.case=="primed":line=lines.get(timeout=args.timeout);print(line,flush=True)
        require_ready="worker ready" in line or (args.case=="reader" and "main ready" in line)
    except queue.Empty:
        print("worker stuck while main reads native stdin",flush=True);require_ready=False
    finally:
        child.stdin.close()
        try:child.wait(timeout=10)
        except subprocess.TimeoutExpired:
            if lifetime:lifetime.close();lifetime=None
            if child.poll() is None:child.terminate()
            child.wait(timeout=5)
        finally:
            if lifetime:lifetime.close()
        while not lines.empty():print("after closing stdin:",lines.get(),flush=True)
    raise SystemExit(0 if require_ready else 1)

if args.case in ("main","primed"):
    started=time.perf_counter();importlib.import_module(args.library)
    print(args.library+" main ready",round(time.perf_counter()-started,3),flush=True)
if args.case in ("worker","primed"):
    def load():
        importlib.import_module(args.library)
        print(args.library+" worker ready",flush=True)
    source=sys.stdin.buffer.raw if args.input_stream=="raw" else sys.stdin.buffer
    if args.input_stream=="win32":
        sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"companion"))
        from manga_live.native_input import native_input
        source=native_input(sys.stdin.buffer)
    if args.child:source.read(4)
    thread=threading.Thread(target=load,daemon=True);thread.start()
    if args.child:source.read(4)
    thread.join(timeout=4)
    if thread.is_alive():raise SystemExit("numpy worker stuck")
if args.case=="reader":
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"companion"))
    from manga_live.native_input import native_input
    source=native_input(sys.stdin.buffer) if args.input_stream=="win32" else sys.stdin.buffer
    consumed=threading.Event()
    def receive():
        source.read(4);consumed.set();source.read(4)
    thread=threading.Thread(target=receive,daemon=True);thread.start();consumed.wait(timeout=2)
    started=time.perf_counter();importlib.import_module(args.library)
    print(args.library+" main ready with reader",round(time.perf_counter()-started,3),flush=True)
