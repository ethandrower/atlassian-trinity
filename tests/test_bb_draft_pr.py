"""Draft pull-request support: payload construction and CLI wiring.

These are pure unit tests. Creating a real draft PR would leave debris in the
repository, so the HTTP layer is stubbed and only the request payload is asserted.
No credentials required, so they run everywhere the read-only smoke tests skip.
"""

from click.testing import CliRunner

from trinity.bitbucket.api import BitbucketAPI
from trinity.bitbucket.commands import create_pr


class RecordingAPI(BitbucketAPI):
    """A BitbucketAPI whose post() records the payload instead of sending it."""

    def __init__(self):  # noqa: D107 - deliberately skips real auth setup
        self.last_path = None
        self.last_payload = None

    def post(self, path, json=None, **kwargs):
        self.last_path = path
        self.last_payload = json
        return {"id": 1, "draft": bool((json or {}).get("draft")), "links": {}}


def test_draft_omitted_by_default():
    """Existing callers must produce a byte-identical payload to before."""
    api = RecordingAPI()
    api.create_pull_request(
        "ws", "repo", title="t", description="", source_branch="feature",
        destination_branch="develop",
    )
    assert "draft" not in api.last_payload


def test_draft_true_sets_the_flag():
    api = RecordingAPI()
    api.create_pull_request(
        "ws", "repo", title="t", description="", source_branch="feature",
        destination_branch="develop", draft=True,
    )
    assert api.last_payload["draft"] is True


def test_draft_false_still_omits_the_flag():
    """draft=False means 'don't ask for a draft', not 'send draft: false'."""
    api = RecordingAPI()
    api.create_pull_request(
        "ws", "repo", title="t", description="", source_branch="feature",
        destination_branch="develop", draft=False,
    )
    assert "draft" not in api.last_payload


def test_create_pr_threads_draft_through():
    """The command layer must pass draft down, not silently drop it."""
    api = RecordingAPI()
    create_pr(api, "ws", "repo", title="t", source="feature", dest="develop", draft=True)
    assert api.last_payload["draft"] is True


def test_create_pr_defaults_to_non_draft():
    api = RecordingAPI()
    create_pr(api, "ws", "repo", title="t", source="feature", dest="develop")
    assert "draft" not in api.last_payload


def test_cli_exposes_a_draft_flag():
    """`trinity bb create --draft` must parse; a missing flag is a usage error."""
    from trinity.cli import cli

    result = CliRunner().invoke(cli, ["bb", "create", "--help"])
    assert result.exit_code == 0
    assert "--draft" in result.output
