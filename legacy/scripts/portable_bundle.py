"""Stage only pinned app assets; never copy a development profile or dataset."""
import hashlib
from importlib import metadata
import json
from pathlib import Path
import re
import shutil
import zipfile
from provision import verify
from provision_llama import TAG, FILENAME, SPEC

MODEL_SET=("ocr","detector","translation","summarizer")
BUNDLE_PROFILES=("cloud-first","offline")
RUNTIME_FILES=("MangaLiveHost.exe","Install companion.exe","bundle.json","models.lock.json")
DETECTOR_METADATA=("opencv-contrib-python","opencv-python-headless","pyclipper","shapely","pypdfium2")


def target(folder,relative):
    folder=Path(folder).resolve()
    if not isinstance(relative,str) or not relative or "\\" in relative or ":" in relative:
        raise ValueError("Invalid portable asset path")
    part=Path(relative)
    if part.is_absolute() or ".." in part.parts:raise ValueError("Asset escapes portable bundle")
    destination=(folder/part).resolve()
    if destination==folder or not destination.is_relative_to(folder):raise ValueError("Asset escapes portable bundle")
    return destination


def profile_models(profile):
    if profile not in BUNDLE_PROFILES:raise ValueError("Unknown portable bundle profile")
    return ("ocr","detector") if profile=="cloud-first" else MODEL_SET


def stage_models(root,folder,profile="offline"):
    names=profile_models(profile)
    root,folder=Path(root),Path(folder)
    manifest=json.loads((root/"models.lock.json").read_text(encoding="utf-8"))
    selected={"schema":manifest["schema"]}
    for name in names:
        spec=manifest[name];selected[name]=spec
        for filename,details in spec["files"].items():
            source=target(root/"models",name+"/"+filename)
            if not verify(source,details):raise ValueError("Pinned model verification failed: "+name+"/"+filename)
            destination=target(folder,"models/"+name+"/"+filename)
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(source,destination)
        print("Staged verified model: "+name,flush=True)
    (folder/"models.lock.json").write_text(json.dumps(selected,indent=2),encoding="utf-8")
    return selected


def verify_cloud_models(folder):
    """Cloud translation still needs the pinned local detector/crop recognizer.

    No model download, runtime start, settings change or Vault access here.
    A profile marker must not turn an incomplete build into a valid install.
    """
    folder=Path(folder).resolve();lock=folder/"models.lock.json"
    try:
        manifest=json.loads(lock.read_text(encoding="utf-8"))
        if not isinstance(manifest,dict) or type(manifest.get("schema")) is not int or manifest["schema"]!=1:
            raise ValueError("Invalid cloud-first model manifest")
        for name in profile_models("cloud-first"):
            spec=manifest.get(name)
            files=spec.get("files") if isinstance(spec,dict) else None
            if not isinstance(files,dict) or not files:raise ValueError("Missing cloud-first model: "+name)
            for filename,details in files.items():
                if (not isinstance(details,dict) or type(details.get("bytes")) is not int or details["bytes"]<0 or
                        not ((isinstance(details.get("sha256"),str) and re.fullmatch(r"[a-f0-9]{64}",details["sha256"])) or
                             (isinstance(details.get("gitBlob"),str) and re.fullmatch(r"[a-f0-9]{40}",details["gitBlob"])) ) or
                        not verify(target(folder,"models/"+name+"/"+filename),details)):
                    raise ValueError("Corrupt cloud-first model: "+name)
    except (OSError,KeyError,TypeError) as error:
        raise ValueError("Incomplete cloud-first vision assets") from error


def build_profile(folder):
    """Legacy bundles omitted profile and keep their complete offline contract."""
    info=json.loads((Path(folder)/"bundle.json").read_text(encoding="utf-8"))
    if not isinstance(info,dict):raise ValueError("Invalid portable bundle marker")
    profile=info.get("profile","offline")
    profile_models(profile)
    return profile


def check_profile_asset(profile,relative):
    if profile=="cloud-first" and (relative.startswith("runtime/") or
            (relative.startswith("models/") and not relative.startswith(("models/ocr/","models/detector/")))):
        raise ValueError("Unexpected local LLM asset in cloud-first bundle: "+relative)


def stage_runtime(root,folder):
    archive=Path(root)/"runtime"/FILENAME
    if not verify(archive,SPEC):raise ValueError("Pinned llama.cpp archive verification failed")
    runtime=target(folder,"runtime/llama")
    runtime.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        entries=[]
        for item in bundle.infolist():
            destination=target(runtime,item.filename.rstrip("/"))
            if item.file_size>150000000:raise ValueError("Runtime archive member is too large")
            entries.append((item,destination))
        for item,destination in entries:
            if item.is_dir():destination.mkdir(parents=True,exist_ok=True);continue
            destination.parent.mkdir(parents=True,exist_ok=True)
            with bundle.open(item) as source,destination.open("wb") as output:
                shutil.copyfileobj(source,output)
    if not (runtime/"llama-server.exe").is_file():raise ValueError("Runtime archive lacks llama-server.exe")
    print("Staged verified llama.cpp CPU runtime: "+TAG,flush=True)


def stage_detector_metadata(folder,distribution=None):
    """PaddleX checks package versions, not just importability of their DLLs.

    Ship actual installed METADATA, never fake versions or bypass dependency
    checks. Exclude direct_url.json/RECORD and editable-project paths.
    """
    distribution=distribution or metadata.distribution
    for name in DETECTOR_METADATA:
        installed=distribution(name)
        records=[entry for entry in (installed.files or []) if len(Path(str(entry)).parts)==2
            and Path(str(entry)).parts[0].endswith(".dist-info") and Path(str(entry)).name=="METADATA"]
        if len(records)!=1:raise ValueError("Missing/ambiguous detector package metadata: "+name)
        record=records[0];source=Path(installed.locate_file(record))
        destination=target(folder,"_internal/"+Path(str(record)).as_posix())
        if not source.is_file():raise ValueError("Missing detector package metadata: "+name)
        destination.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(source,destination)
    print("Staged real detector dependency metadata",flush=True)


def sha256(path):
    result=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):result.update(chunk)
    return result.hexdigest()


def write_checksums(folder):
    folder=Path(folder).resolve();files={};profile=build_profile(folder)
    for path in sorted(folder.rglob("*")):
        if not path.is_file():continue
        relative=path.relative_to(folder).as_posix()
        if relative=="checksums.json":continue
        check_profile_asset(profile,relative)
        # Build output must not accidentally ship a previously registered host
        # config, a private memory or an arbitrary file dropped into the folder.
        if relative not in (*RUNTIME_FILES,"dependency-licenses.json") and not relative.startswith(("_internal/","models/","runtime/")):
            raise ValueError("Unexpected file in portable build; not packaged: "+relative)
        target(folder,relative)
        files[relative]={"bytes":path.stat().st_size,"sha256":sha256(path)}
    if not all(name in files for name in RUNTIME_FILES):raise ValueError("Portable build is incomplete")
    output={"schema":1,"files":files}
    (folder/"checksums.json").write_text(json.dumps(output,indent=2),encoding="utf-8")
    return output


def verify_bundle(folder,progress=None):
    """Corruption check, NOT authenticity/signature or a legal release gate."""
    folder=Path(folder).resolve();index=folder/"checksums.json"
    if not index.is_file() or index.stat().st_size>16*1024*1024:raise ValueError("Missing/oversized bundle checksum index")
    data=json.loads(index.read_text(encoding="utf-8"))
    if not isinstance(data,dict) or type(data.get("schema")) is not int or data["schema"]!=1:
        raise ValueError("Invalid bundle checksum index")
    files=data.get("files")
    if not isinstance(files,dict) or not 0<len(files)<=50000 or not all(name in files for name in RUNTIME_FILES):
        raise ValueError("Incomplete bundle checksum index")
    for position,(relative,spec) in enumerate(files.items(),1):
        path=target(folder,relative)
        if not isinstance(spec,dict) or type(spec.get("bytes")) is not int or spec["bytes"]<0 or not isinstance(spec.get("sha256"),str) or not re.fullmatch(r"[a-f0-9]{64}",spec["sha256"]):
            raise ValueError("Invalid asset checksum entry")
        if not path.is_file() or path.stat().st_size!=spec["bytes"] or sha256(path)!=spec["sha256"]:
            raise ValueError("Bundle file missing/corrupt: "+relative)
        if progress:progress(position,len(files))
    profile=build_profile(folder)
    for relative in files:check_profile_asset(profile,relative)
    if profile=="cloud-first":verify_cloud_models(folder)
    return {"files":len(files),"bytes":sum(spec["bytes"] for spec in files.values())}
