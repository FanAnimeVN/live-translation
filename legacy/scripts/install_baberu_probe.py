"""Explicit, pinned data-only comparator install. Never called by inference.

No remote Python, pickle, Transformers custom code or training data is fetched.
Downloaded weights stay in ignored models/; not approved for redistribution.
"""
import argparse
import hashlib
from pathlib import Path
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
REVISION = "fdf292a15dae9f5af37dd76bb408679dc4bcdfe4"
REPO = "genshiai-daichi/baberu-ocr"
FILES = {
    "onnx/vision_int4.onnx": (52293486, "9526bcf99eb8de805df7ea2f66b385cfcbcb5dff0e99a5dcfb02bdb2d4182bde"),
    "onnx/decoder_prefill_int8.onnx": (35133596, "91de16d4e70adaadc0c76ea536f0195b79f54b52e3279aeaac8fc06b46824c60"),
    "onnx/decoder_step_int8.onnx": (34715466, "f6164e9daee6622891d2a52394f143faa7f0ccfdfb90e8d6443193aff36d4c2d"),
    "tokenizer/vocab.json": (130761, "681de4eb83154a397af49e2ddae4705041b12a22e16fe00860b829e889e5f47c"),
    "LICENSE": (11348, "186332043e82fcfdbeb0b8e0e8d77b63d97ffa3dd9d91ccf7cef1377d8ab345b"),
}
MODEL_DIR = ROOT / "models" / "baberu-probe" / REVISION


def verified(path, spec):
    size, checksum = spec
    if path.is_symlink() or not path.is_file() or path.stat().st_size != size:
        return False
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest() == checksum


def install():
    if not MODEL_DIR.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Comparator directory escaped the workspace")
    for name, spec in FILES.items():
        target = MODEL_DIR / name
        if MODEL_DIR.resolve() not in target.resolve().parents:
            raise ValueError("Model path escaped")
        if target.exists():
            if not verified(target, spec):
                raise ValueError("Existing comparator data failed checksum; not overwriting")
            print("verified " + name, flush=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_name(target.name + ".partial-" + uuid.uuid4().hex)
        url = f"https://huggingface.co/{REPO}/resolve/{REVISION}/{name}"
        # Only this newly created partial file is removed on a failed download.
        try:
            with urllib.request.urlopen(url, timeout=45) as response, temporary.open("xb") as output:
                received = 0
                while chunk := response.read(1024 * 1024):
                    received += len(chunk)
                    if received > spec[0]:
                        raise ValueError("Download exceeded pinned size")
                    output.write(chunk)
            if not verified(temporary, spec):
                raise ValueError("Model checksum mismatch")
            # No clobber if a second install finished while this was downloading.
            temporary.rename(target)
            print("installed " + name, flush=True)
        finally:
            if temporary.exists():
                temporary.unlink()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true", required=True)
    parser.parse_args()
    install()
