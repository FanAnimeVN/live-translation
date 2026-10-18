from pathlib import Path
import zipfile
from provision import download, ROOT

TAG = "b11429"
FILENAME = f"llama-{TAG}-bin-win-cpu-x64.zip"
SPEC = {"sha256":"1283323272b04cd07905816a597a0da810918102de958f4ff6f7bbaa70ed2efe","bytes":19398918}

if __name__ == "__main__":
    target = ROOT / "runtime/llama"
    archive = ROOT / "runtime" / FILENAME
    download(f"https://github.com/ggml-org/llama.cpp/releases/download/{TAG}/{FILENAME}",archive,SPEC)
    target.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for item in bundle.infolist():
            dest = (target / item.filename).resolve()
            if not dest.is_relative_to(target.resolve()) or item.file_size > 150000000:
                raise ValueError("Invalid runtime archive")
        bundle.extractall(target)
    print("Verified llama.cpp CPU runtime installed")
