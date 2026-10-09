"""TRINITY_HOME points a process at another identity's config directory.

A bot user (the hourly developer agent) runs on the same machine as its owner.
Its sessions set TRINITY_HOME=~/.trinity-agent so every trinity call they make
reads the bot's credentials, while the owner's sessions keep ~/.trinity.

CONFIG_DIR is resolved at import time, so each test reloads the module.
"""

import importlib
from pathlib import Path

from trinity.base import auth


def _reload(monkeypatch, value):
    if value is None:
        monkeypatch.delenv("TRINITY_HOME", raising=False)
    else:
        monkeypatch.setenv("TRINITY_HOME", value)
    return importlib.reload(auth)


def test_default_is_home_dot_trinity(monkeypatch):
    mod = _reload(monkeypatch, None)
    assert mod.CONFIG_DIR == Path.home() / ".trinity"
    assert mod.CONFIG_FILE == Path.home() / ".trinity" / "config.yaml"


def test_trinity_home_overrides(monkeypatch, tmp_path):
    mod = _reload(monkeypatch, str(tmp_path / "agent"))
    assert mod.CONFIG_DIR == tmp_path / "agent"
    assert mod.CONFIG_FILE == tmp_path / "agent" / "config.yaml"


def test_trinity_home_expands_tilde(monkeypatch):
    mod = _reload(monkeypatch, "~/.trinity-agent")
    assert mod.CONFIG_DIR == Path.home() / ".trinity-agent"


def test_empty_trinity_home_falls_back(monkeypatch):
    mod = _reload(monkeypatch, "")
    assert mod.CONFIG_DIR == Path.home() / ".trinity"


def teardown_module():
    # Leave the module as other tests expect it: resolved without the override.
    import os
    os.environ.pop("TRINITY_HOME", None)
    importlib.reload(auth)
