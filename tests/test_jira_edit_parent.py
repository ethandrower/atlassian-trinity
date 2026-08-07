"""Reparenting support on `jira edit`: payload construction and CLI wiring.

These are pure unit tests. A real edit would mutate a live Jira issue, so the
HTTP layer is stubbed and only the request payload is asserted. No credentials
required, so they run everywhere the read-only smoke tests skip.

`edit` is currently declared twice — the command the CLI actually registers
lives in trinity.cli, and trinity.jira.edit_issue carries a second copy. Every
test runs against both so the two cannot drift apart unnoticed.
"""

import pytest
from click.testing import CliRunner

from trinity.cli import jira_edit
from trinity.jira import edit_issue as edit_mod

COMMANDS = [
    pytest.param(jira_edit, id="cli"),
    pytest.param(edit_mod.edit_cmd, id="edit_issue"),
]


class RecordingPut:
    """Stands in for requests.put(), recording the payload instead of sending it."""

    def __init__(self):
        self.last_url = None
        self.last_payload = None

    def __call__(self, url, headers=None, json=None, timeout=None):
        self.last_url = url
        self.last_payload = json
        return type("Response", (), {"status_code": 204, "text": ""})()


@pytest.fixture
def recorder(monkeypatch):
    put = RecordingPut()
    monkeypatch.setattr(edit_mod.requests, "put", put)
    monkeypatch.setattr(edit_mod, "get_jira_auth_headers", lambda: {})
    return put


def run(command, *args):
    result = CliRunner().invoke(command, ["ECD-1", *args])
    assert result.exit_code == 0, result.output
    return result


@pytest.mark.parametrize("command", COMMANDS)
def test_parent_omitted_by_default(command, recorder):
    """Existing callers must produce a byte-identical payload to before."""
    run(command, "--summary", "new title")
    assert "parent" not in recorder.last_payload["fields"]


@pytest.mark.parametrize("command", COMMANDS)
def test_parent_sets_the_key(command, recorder):
    run(command, "--parent", "ECD-2341")
    assert recorder.last_payload["fields"]["parent"] == {"key": "ECD-2341"}


@pytest.mark.parametrize("command", COMMANDS)
def test_parent_none_orphans_the_issue(command, recorder):
    """'none' means 'remove the parent', mirroring --assignee none."""
    run(command, "--parent", "none")
    assert recorder.last_payload["fields"]["parent"] is None


@pytest.mark.parametrize("command", COMMANDS)
def test_parent_combines_with_other_fields(command, recorder):
    """Reparenting must not clobber sibling field updates in the same call."""
    run(command, "--parent", "ECD-2341", "--priority", "High")
    fields = recorder.last_payload["fields"]
    assert fields["parent"] == {"key": "ECD-2341"}
    assert fields["priority"] == {"name": "High"}


@pytest.mark.parametrize("command", COMMANDS)
def test_description_omitted_by_default(command, recorder):
    run(command, "--summary", "new title")
    assert "description" not in recorder.last_payload["fields"]


@pytest.mark.parametrize("command", COMMANDS)
def test_description_is_wrapped_as_adf(command, recorder):
    """Jira rejects a bare string here — the body must be an ADF document."""
    run(command, "--description", "First line.\n\nSecond line.")
    body = recorder.last_payload["fields"]["description"]
    assert body["type"] == "doc"
    assert [p["content"][0]["text"] for p in body["content"]] == ["First line.", "Second line."]


@pytest.mark.parametrize("command", COMMANDS)
def test_description_file_overrides_description(command, recorder, tmp_path):
    path = tmp_path / "body.txt"
    path.write_text("From the file.")
    run(command, "--description", "inline", "--description-file", str(path))
    body = recorder.last_payload["fields"]["description"]
    assert body["content"][0]["content"][0]["text"] == "From the file."
