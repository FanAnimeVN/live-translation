"""Explicit model download. Runtime inference never goes online to obtain weights."""
import argparse
import concurrent.futures
import hashlib
import json
import re
import time
from pathlib import Path
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def verify(path, spec):
    if not path.exists() or path.stat().st_size != spec["bytes"]:
        return False
    h = hashlib.sha256() if "sha256" in spec else hashlib.sha1()
    if "gitBlob" in spec:
        h.update(f"blob {spec['bytes']}\0".encode())
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest() == spec.get("sha256", spec.get("gitBlob"))


def download(url, path, spec):
    if verify(path, spec):
        print(f"Verified {path.name}", flush=True)
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".download")
    # A failed download is not accepted as a usable model.
    restarted=False
    for attempt in range(8):
        offset=partial.stat().st_size if partial.exists() else 0
        if offset>=spec["bytes"]:
            if verify(partial,spec):break
            if restarted:raise RuntimeError(f"Checksum mismatch: {path.name}; original model not replaced")
            offset=0;restarted=True
        headers={"User-Agent":"MangaLiveSetup/0.1","Cache-Control":"no-cache"}
        if offset:headers["Range"]=f"bytes={offset}-"
        try:
            with urllib.request.urlopen(urllib.request.Request(url,headers=headers),timeout=60) as response:
                append=response.status==206
                if append:
                    match=re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)",response.headers.get("Content-Range",""))
                    if not match or int(match[1])!=offset or int(match[3])!=spec["bytes"]:
                        raise ValueError("Server sent a mismatched Content-Range; no data appended")
                else:offset=0
                with partial.open("ab" if append and offset else "wb") as stream:
                    size=offset
                    for chunk in iter(lambda:response.read(2*1024*1024),b""):
                        size+=len(chunk)
                        if size>spec["bytes"]:raise ValueError("Download exceeds pinned size")
                        stream.write(chunk)
            if verify(partial,spec):break
            print(f"Incomplete {path.name}: {partial.stat().st_size}/{spec['bytes']} bytes; retrying",flush=True)
        except (OSError,ValueError) as exc:
            if attempt==7:raise RuntimeError(f"Download failed: {path.name}; original model not replaced") from exc
            print(f"Retry {attempt+1}: {path.name}",flush=True)
        time.sleep(min(attempt+1,2))
    if not verify(partial,spec):raise RuntimeError(f"Checksum/size mismatch: {path.name}; original model not replaced")
    partial.replace(path)
    print(f"Downloaded and verified {path.name}", flush=True)


def provision(args):
    manifest = json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))
    models = Path(args.destination).resolve()
    tasks = []
    for name in args.models:
        spec = manifest[name]
        for filename, details in spec["files"].items():
            tasks.append((f"https://huggingface.co/{spec['repo']}/resolve/{spec['revision']}/{filename}", models / name / filename, details))
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(lambda t: download(*t), tasks))
    # Installed model inventory is generated data, not executable downloaded code.
    installed = models / "installed.json"
    state = json.loads(installed.read_text(encoding="utf-8")) if installed.exists() else {"schema": 1}
    for name in args.models:
        state[name] = manifest[name]
    installed.write_text(json.dumps(state, indent=2), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("models", nargs="+", choices=list(json.loads((ROOT / "models.lock.json").read_text(encoding="utf-8"))))
    parser.add_argument("--destination", default=str(ROOT / "models"))
    provision(parser.parse_args())
