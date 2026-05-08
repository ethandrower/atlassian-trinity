"""
Unit-level checks for the lazy URL resolver in trinity.base.client.

These don't touch the network — they verify that env/config feed through
correctly and that the URL family is the instance domain (not the
api.atlassian.com OAuth gateway, which Basic Auth doesn't accept).
"""

import importlib

import pytest


def test_jira_base_url_uses_instance_domain(monkeypatch):
    monkeypatch.setenv("ATLASSIAN_JIRA_URL", "https://acme.atlassian.net")
    monkeypatch.delenv("JIRA_INSTANCE_URL", raising=False)
    from trinity.base import client as c

    assert c.JIRA_BASE_URL == "https://acme.atlassian.net"
    assert c.AGILE_BASE_URL == "https://acme.atlassian.net/rest/agile/1.0"
    assert c.CONFLUENCE_BASE_URL == "https://acme.atlassian.net"
    assert c.JIRA_WEB_URL == "https://acme.atlassian.net"


def test_jira_base_url_strips_trailing_slash(monkeypatch):
    monkeypatch.setenv("ATLASSIAN_JIRA_URL", "https://acme.atlassian.net/")
    from trinity.base import client as c

    assert c.JIRA_BASE_URL == "https://acme.atlassian.net"


def test_legacy_jira_instance_url_env_still_works(monkeypatch):
    monkeypatch.delenv("ATLASSIAN_JIRA_URL", raising=False)
    monkeypatch.setenv("JIRA_INSTANCE_URL", "https://legacy.atlassian.net")
    from trinity.base import client as c

    assert c.JIRA_BASE_URL == "https://legacy.atlassian.net"


def test_env_takes_priority_over_config(monkeypatch):
    monkeypatch.setenv("ATLASSIAN_JIRA_URL", "https://override.atlassian.net")
    from trinity.base import client as c

    # config.yaml may say citemed, but the env wins
    assert c.JIRA_BASE_URL == "https://override.atlassian.net"


def test_falls_back_to_config_when_env_missing(monkeypatch):
    monkeypatch.delenv("ATLASSIAN_JIRA_URL", raising=False)
    monkeypatch.delenv("JIRA_INSTANCE_URL", raising=False)
    from trinity.base import client as c
    from trinity.base.auth import load_config

    cfg_url = (load_config().get("atlassian") or {}).get("jira_url")
    if not cfg_url:
        pytest.skip("No jira_url in config — nothing to verify")
    assert c.JIRA_BASE_URL == cfg_url.rstrip("/")


def test_no_oauth_gateway_url_anywhere(monkeypatch):
    """The whole point of the fix: never use api.atlassian.com/ex/{id}/..."""
    monkeypatch.setenv("ATLASSIAN_JIRA_URL", "https://acme.atlassian.net")
    from trinity.base import client as c

    for name in ("JIRA_BASE_URL", "AGILE_BASE_URL", "CONFLUENCE_BASE_URL", "JIRA_WEB_URL"):
        url = getattr(c, name)
        assert "api.atlassian.com/ex/" not in url, f"{name} still uses gateway: {url}"
