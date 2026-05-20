"""Live read-only Bitbucket API smoke tests."""

import pytest

from trinity.bitbucket.api import BitbucketAPI

pytestmark = pytest.mark.bb_auth


@pytest.fixture(scope="module")
def client() -> BitbucketAPI:
    return BitbucketAPI()


@pytest.mark.xfail(
    reason=(
        "test_connection hits /2.0/user, which repo-scoped tokens cannot "
        "access (403). Tracked separately in issue #2 — Bitbucket token "
        "scope. Will pass once a workspace-scoped App Password is in use."
    ),
    strict=False,
)
def test_test_connection(client: BitbucketAPI):
    result = client.test_connection()
    assert isinstance(result, dict)
    assert not result.get("error"), f"connection error: {result}"


def test_list_pull_requests(client: BitbucketAPI, bb_workspace: str, bb_repo: str):
    """Repo-token-scoped: at minimum the configured repo must list PRs."""
    prs = client.list_pull_requests(bb_workspace, bb_repo, state="OPEN")
    assert isinstance(prs, list)


def test_list_pipelines(client: BitbucketAPI, bb_workspace: str, bb_repo: str):
    result = client.list_pipelines(bb_workspace, bb_repo, limit=3)
    assert isinstance(result, dict)
    assert "values" in result or "size" in result or "page" in result
