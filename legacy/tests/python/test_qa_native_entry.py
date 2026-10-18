import importlib.util
import json
from pathlib import Path
import tempfile

import pytest

path=Path(__file__).resolve().parents[2]/"scripts/qa_native_entry.py"
spec=importlib.util.spec_from_file_location("qa_native_entry",path)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)


def test_trace_is_restricted_to_disposable_fixture_data():
    with tempfile.TemporaryDirectory(prefix="mangalive-real-browser-") as temporary:
        folder=Path(temporary);config=folder/"native-config.json"
        config.write_text(json.dumps({"dataRoot":str(folder/"data")}),encoding="utf-8")
        assert module.diagnostic_folder(["entry","--config",str(config)])==folder.resolve()
        config.write_text(json.dumps({"dataRoot":str(folder/"reader-data")}),encoding="utf-8")
        with pytest.raises(ValueError):module.diagnostic_folder(["entry","--config",str(config)])


def test_trace_cannot_enable_on_arbitrary_profile(tmp_path):
    config=tmp_path/"native-config.json"
    with pytest.raises(ValueError):module.diagnostic_folder(["entry","--config",str(config)])
