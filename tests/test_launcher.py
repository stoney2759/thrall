"""Launcher setup checks — a new user's config problems get a message, not a crash."""
from __future__ import annotations
import importlib.util
import tomllib
from pathlib import Path
import pytest
from constants.launcher import TELEGRAM_NO_USERS_MSG

ROOT = Path(__file__).resolve().parent.parent

# thrall.py shares its name with the thrall/ package, so load it from its path
_spec = importlib.util.spec_from_file_location("thrall_launcher", ROOT / "thrall.py")
launcher = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(launcher)


def _telegram(ids) -> dict:
    return {"transports": {"telegram": {"enabled": True, "allowed_user_ids": ids}}}


class TestExampleConfig:
    def test_example_config_is_valid_toml(self):
        with open(ROOT / "config" / "config.example.toml", "rb") as f:
            config = tomllib.load(f)
        assert config["transports"]["telegram"]["allowed_user_ids"] == []


class TestTelegramReady:
    @pytest.fixture(autouse=True)
    def token(self, monkeypatch):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test-token")

    def test_no_allowed_users_explains_setup(self):
        assert launcher.telegram_ready(_telegram([])) == (False, TELEGRAM_NO_USERS_MSG)

    def test_ready_with_a_user(self):
        assert launcher.telegram_ready(_telegram([123456789])) == (True, "")


class TestLoadConfig:
    def test_invalid_toml_exits_with_message(self, tmp_path, monkeypatch, capsys):
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "config.toml").write_text("ids = [YOUR_ID]\n", encoding="utf-8")
        monkeypatch.setattr(launcher, "ROOT", tmp_path)
        with pytest.raises(SystemExit):
            launcher.load_config()
        assert "can't read" in capsys.readouterr().out

    def test_config_saved_with_bom_still_loads(self, tmp_path, monkeypatch):
        (tmp_path / "config").mkdir()
        (tmp_path / "config" / "config.toml").write_bytes(b"\xef\xbb\xbf[server]\nport = 8765\n")
        monkeypatch.setattr(launcher, "ROOT", tmp_path)
        assert launcher.load_config() == {"server": {"port": 8765}}

    def test_missing_config_exits_with_message(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(launcher, "ROOT", tmp_path)
        with pytest.raises(SystemExit):
            launcher.load_config()
        assert "config.example.toml" in capsys.readouterr().out
