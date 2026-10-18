"""Public first-party package identity, not reader data or a quality seal.

Development hosts capture this once when host.py is imported. Frozen hosts
read the same record embedded by the freezer, never a nearby working tree.
This identifies our Python package only, not weights, dependencies or launcher.
"""
import hashlib
import json
from pathlib import Path
import re
import sys


RECORD_NAME = "_runtime_build.json"
PREFIX = "pkg-sha256:"


def source_build(folder=None):
    root = Path(folder or Path(__file__).parent).resolve()
    if not all((root / name).is_file() for name in ("__init__.py", "host.py")):
        raise ValueError("Runtime source package is incomplete")
    digest = hashlib.sha256(b"manga-live-python-package-v1\0")
    paths = sorted(root.rglob("*.py"), key=lambda path: path.relative_to(root).as_posix())
    for path in paths:
        if path.is_symlink() or not path.resolve().is_relative_to(root):
            raise ValueError("Runtime source escapes package")
        name = path.relative_to(root).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(name).to_bytes(4, "big"))
        digest.update(name)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return PREFIX + digest.hexdigest()


def checked_build_record(value):
    if (not isinstance(value, dict) or set(value) != {"v", "runtimeBuild"} or
            type(value["v"]) is not int or value["v"] != 1 or
            not isinstance(value["runtimeBuild"], str) or
            not re.fullmatch(r"pkg-sha256:[a-f0-9]{64}", value["runtimeBuild"])):
        raise ValueError("Invalid embedded runtime identity")
    return value["runtimeBuild"]


def runtime_build():
    if not getattr(sys, "frozen", False):
        return source_build()
    path = Path(__file__).with_name(RECORD_NAME)
    if path.stat().st_size > 256:
        raise ValueError("Invalid embedded runtime identity")
    return checked_build_record(json.loads(path.read_text(encoding="utf-8")))
