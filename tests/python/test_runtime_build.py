import json
from pathlib import Path
import sys

import pytest

from manga_live import runtime_build as identity

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import native_smoke


def package_at(root):
    root.mkdir()
    (root / "__init__.py").write_text("# fixture\n", encoding="utf-8")
    (root / "host.py").write_text("# authored host fixture\n", encoding="utf-8")
    return root


def test_package_identity_is_location_independent_and_does_not_read_reader_files(tmp_path):
    first = package_at(tmp_path / "one")
    second = package_at(tmp_path / "two")
    (first / "reader.sqlite3").write_bytes(b"private fixture must not affect identity")
    (first / "_runtime_build.json").write_text("untrusted old generated record")
    assert identity.source_build(first) == identity.source_build(second)
    assert len(identity.source_build(first)) == len(identity.PREFIX) + 64


@pytest.mark.parametrize("change", ["bytes", "rename", "add", "remove"])
def test_each_package_source_change_invalidates_identity(tmp_path, change):
    root = package_at(tmp_path / "package")
    extra = root / "pipeline.py"
    extra.write_text("# first\n")
    before = identity.source_build(root)
    if change == "bytes":
        extra.write_text("# second\n")
    elif change == "rename":
        extra.rename(root / "renamed.py")
    elif change == "add":
        (root / "translation_cache.py").write_text("# checkpoint fixture\n")
    else:
        extra.unlink()
    assert identity.source_build(root) != before


@pytest.mark.parametrize("record", [None, {}, {"v": True, "runtimeBuild": "pkg-sha256:" + "a" * 64},
    {"v": 1, "runtimeBuild": "old"}, {"v": 2, "runtimeBuild": "pkg-sha256:" + "a" * 64},
    {"v": 1, "runtimeBuild": "pkg-sha256:" + "a" * 64, "private": "not allowed"}])
def test_embedded_identity_cannot_fall_back_to_neighboring_sources(record):
    with pytest.raises(ValueError, match="Invalid embedded"):
        identity.checked_build_record(record)


def test_frozen_identity_comes_only_from_embedded_record(tmp_path, monkeypatch):
    root = package_at(tmp_path / "bundle")
    stamp = {"v": 1, "runtimeBuild": "pkg-sha256:" + "a" * 64}
    (root / identity.RECORD_NAME).write_text(json.dumps(stamp))
    monkeypatch.setattr(identity.sys, "frozen", True, raising=False)
    monkeypatch.setattr(identity, "__file__", str(root / "runtime_build.py"))
    monkeypatch.setattr(identity, "source_build", lambda: pytest.fail("Frozen host read local sources"))
    assert identity.runtime_build() == stamp["runtimeBuild"]
    (root / identity.RECORD_NAME).write_text("{}")
    with pytest.raises(ValueError, match="Invalid embedded"):
        identity.runtime_build()


def test_native_verifier_rejects_old_or_different_host_even_with_same_prompt(monkeypatch):
    monkeypatch.setattr(native_smoke, "source_build", lambda: "pkg-sha256:" + "a" * 64)
    for reply in ({"promptVersion": "unchanged"},
                  {"runtimeBuild": "pkg-sha256:" + "b" * 64, "promptVersion": "unchanged"}):
        with pytest.raises(RuntimeError, match="Runtime package mismatch"):
            native_smoke.verify_runtime(reply)
    assert native_smoke.verify_runtime({"runtimeBuild": "pkg-sha256:" + "a" * 64}) is None


def test_verify_runtime_cannot_accidentally_start_an_inference_job(monkeypatch):
    monkeypatch.setattr(sys, "argv", ["native_smoke", "--verify-runtime"])
    monkeypatch.setattr(native_smoke, "NativeClient", lambda *args, **kwargs: pytest.fail("Host started before argument guard"))
    with pytest.raises(SystemExit) as error:
        native_smoke.main()
    assert error.value.code == 2
