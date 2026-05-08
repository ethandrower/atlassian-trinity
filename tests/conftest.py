"""
Pytest fixtures + skip gating for the Trinity smoke suite.

Tests that hit the live Atlassian/Bitbucket APIs are gated on credential
presence. Without creds the suite still imports cleanly (so static checks
pass) — individual tests are skipped with a clear reason.
"""

import os

import pytest

from trinity.base import is_authenticated
from trinity.base.auth import get_workspace


def _has_jira_auth() -> bool:
    return is_authenticated("jira")


def _has_bb_auth() -> bool:
    return is_authenticated("bitbucket")


def pytest_collection_modifyitems(config, items):
    """Apply auto-skip markers based on credentials available."""
    jira_ok = _has_jira_auth()
    bb_ok = _has_bb_auth()
    skip_jira = pytest.mark.skip(reason="Atlassian creds not configured (trinity config)")
    skip_bb = pytest.mark.skip(reason="Bitbucket creds not configured (trinity config --bb-token)")
    for item in items:
        if "jira_auth" in item.keywords and not jira_ok:
            item.add_marker(skip_jira)
        if "bb_auth" in item.keywords and not bb_ok:
            item.add_marker(skip_bb)


def pytest_configure(config):
    config.addinivalue_line("markers", "jira_auth: requires Atlassian credentials")
    config.addinivalue_line("markers", "bb_auth: requires Bitbucket credentials")


@pytest.fixture(scope="session")
def known_issue_key() -> str:
    """A stable Jira issue key for read-only checks. Override via env."""
    return os.getenv("TRINITY_TEST_ISSUE_KEY", "ECD-1")


@pytest.fixture(scope="session")
def known_project_key(known_issue_key: str) -> str:
    return known_issue_key.split("-")[0]


@pytest.fixture(scope="session")
def bb_workspace() -> str:
    ws = get_workspace()
    if not ws:
        pytest.skip("Bitbucket workspace not configured")
    return ws


@pytest.fixture(scope="session")
def bb_repo() -> str:
    """Bitbucket repo slug for read-only checks. Default to the
    repo-token-scoped one for the citemed setup."""
    return os.getenv("TRINITY_TEST_BB_REPO", "citemed_web")
