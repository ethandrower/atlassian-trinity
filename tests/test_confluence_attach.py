from unittest import mock

from trinity.confluence.attach_files import attach_confluence_files


def test_attach_uploads_each_file_and_returns_embed_markup(tmp_path):
    f = tmp_path / "01-shot.jpg"
    f.write_bytes(b"\xff\xd8jpeg")
    resp = mock.Mock(status_code=200)
    resp.json.return_value = {"results": [{"id": "att123", "version": {"number": 1}}]}
    with mock.patch("trinity.confluence.attach_files.get_confluence_auth_headers",
                    return_value={"Authorization": "Basic x", "Content-Type": "application/json"}), \
         mock.patch("trinity.confluence.attach_files.requests.put", return_value=resp) as put:
        out = attach_confluence_files("42", [str(f)])
    assert out["success"] and out["attachments"][0]["attachment_id"] == "att123"
    assert 'ri:filename="01-shot.jpg"' in out["attachments"][0]["embed"]
    url, = put.call_args.args
    assert url.endswith("/wiki/rest/api/content/42/child/attachment")
    headers = put.call_args.kwargs["headers"]
    assert "Content-Type" not in headers and headers["X-Atlassian-Token"] == "nocheck"


def test_missing_file_is_an_error(tmp_path):
    with mock.patch("trinity.confluence.attach_files.get_confluence_auth_headers", return_value={}):
        out = attach_confluence_files("42", [str(tmp_path / "nope.png")])
    assert out["error"]
