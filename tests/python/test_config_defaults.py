import json
import pytest
from manga_live.config import Config


def test_new_profile_enables_free_local_cleanup(tmp_path):
    settings = Config(tmp_path)
    assert settings.values["artCleanup"] is True
    assert settings.values["mode"] == "offline"
    assert settings.values["cloudConsent"] is False
    assert settings.values["metadataConsent"] is False


@pytest.mark.parametrize("saved", [None, True, False])
def test_missing_default_and_explicit_cleanup_choice_survive_save_reload(tmp_path, saved):
    values = {"mode": "offline"}
    if saved is not None:
        values["artCleanup"] = saved
    (tmp_path / "settings.json").write_text(json.dumps(values), encoding="utf-8")
    settings = Config(tmp_path)
    expected = True if saved is None else saved
    assert settings.values["artCleanup"] is expected
    settings.update({"threads": 2})
    assert Config(tmp_path).values["artCleanup"] is expected


def test_explicit_opt_out_can_be_changed_without_network_consent(tmp_path):
    settings = Config(tmp_path)
    settings.update({"artCleanup": False})
    assert Config(tmp_path).values["artCleanup"] is False
    settings.update({"artCleanup": True})
    assert Config(tmp_path).values["artCleanup"] is True
    assert not settings.values["cloudConsent"]
