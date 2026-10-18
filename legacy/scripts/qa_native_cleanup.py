"""Terminate only processes tied to one disposable browser-QA installation.

Not shipped in the companion. No generic Python/Edge/name-based termination.
Validate config, executable, entry, origin, PID lifetime and exact config argv.
"""
import argparse
import json
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def cleanup_configuration(folder):
    folder = Path(folder).resolve()
    temporary = Path(tempfile.gettempdir()).resolve()
    if not folder.is_relative_to(temporary) or not folder.name.startswith("mangalive-real-browser-"):
        raise ValueError("Only an isolated QA temporary directory is accepted")
    config = folder / "native-config.json"
    data = json.loads(config.read_text(encoding="utf-8"))
    if Path(data.get("dataRoot", "")).resolve() != folder / "data":
        raise ValueError("Refusing reader data")
    origins = data.get("allowedOrigins")
    import re
    if (not isinstance(origins, list) or len(origins) != 1 or
            not re.fullmatch(r"chrome-extension://[a-p]{32}/", origins[0])):
        raise ValueError("QA requires one explicit extension origin")
    entries = {str((ROOT / name).resolve()) for name in
               ("companion/entry.py", "scripts/qa_native_entry.py", "scripts/qa_relay_entry.py", "scripts/qa_cloud_entry.py",
                "scripts/qa_render_replay_entry.py", "scripts/qa_image_entry.py")}
    executables = {str(Path(sys.executable).resolve()), str(Path(getattr(sys, "_base_executable", sys.executable)).resolve()),
                   str((ROOT/".venv/Scripts/python.exe").resolve()),
                   str((folder/"MangaLiveHost.exe").resolve())}
    return config, origins[0], entries, executables


def matches_owned(argv, executable, identity):
    config, origin, entries, executables = identity
    system_cmd = str((Path(os.environ.get("SystemRoot", "C:/Windows"))/"System32/cmd.exe").resolve())
    if isinstance(argv, list) and executable and str(Path(executable).resolve()) == system_cmd:
        import re
        flags = {arg.lower() for arg in argv}
        command = " ".join(argv[1:])
        bootstrap = str(config.parent/"MangaLiveHost.cmd")
        return ({"/d", "/s", "/c"} <= flags and
                re.search(r'(?<=[\s"])'+re.escape(bootstrap)+r'(?=[\s"])', command) is not None and
                re.search(r'(?<=[\s"])'+re.escape(origin)+r'(?=[\s"]|$)', command) is not None)
    if (not isinstance(argv, list) or not executable or len(argv) < 3 or
            str(Path(executable).resolve()) not in executables or origin not in argv):
        return False
    try:
        index = argv.index("--config")
        if str(Path(argv[index+1]).resolve()) != str(config):
            return False
    except (ValueError, IndexError, OSError):
        return False
    return any(str(Path(arg).resolve()) in entries for arg in argv[1:] if not arg.startswith("-"))


def cleanup(folder):
    import psutil
    identity = cleanup_configuration(folder)
    selected = []
    for process in psutil.process_iter(["pid", "exe", "cmdline", "create_time"]):
        try:
            if process.pid != os.getpid() and matches_owned(process.info["cmdline"], process.info["exe"], identity):
                selected.append((process, process.info["create_time"]))
        except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
            continue
    stopped = []
    for process, created in reversed(selected):
        try:
            # PID reuse, changed command line or a lost ownership check must
            # stop cleanup, never broaden the set of targets.
            if process.create_time() != created or not matches_owned(process.cmdline(), process.exe(), identity):
                raise ValueError("QA process identity changed")
            process.kill()
            stopped.append(process.pid)
        except psutil.NoSuchProcess:
            continue
    psutil.wait_procs([p for p, _ in selected], timeout=5)
    return {"stoppedQaProcesses": stopped, "productionRegistrationChanged": False}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("folder")
    args = parser.parse_args()
    print(json.dumps(cleanup(args.folder)))
