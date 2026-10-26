#!/usr/bin/env python3
"""Attach files (screenshots, PDFs) to a Confluence page.

Uses the same Atlassian credentials as every other Confluence command. Re-attaching a
file with the same name adds a new version of that attachment instead of failing, so a
guide's screenshots can be refreshed in place.
"""

import mimetypes
import os
from typing import List

import requests

from ..base import CONFLUENCE_BASE_URL, format_error, get_confluence_auth_headers


def attach_confluence_files(page_id: str, paths: List[str]) -> dict:
    """Upload each file to the page. Returns {"success", "page_id", "attachments": [...]}.

    Each attachment entry carries the storage-format markup to embed it:
    <ac:image><ri:attachment ri:filename="..."/></ac:image>
    """
    headers = {k: v for k, v in get_confluence_auth_headers().items() if k.lower() != "content-type"}
    headers["X-Atlassian-Token"] = "nocheck"
    out = []
    for path in paths:
        if not os.path.isfile(path):
            return {"error": True, "message": f"No such file: {path}"}
        name = os.path.basename(path)
        mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
        with open(path, "rb") as fh:
            # No version comment: on this endpoint Confluence rejects one with
            # "Must be same number of attachment files and comments" (verified 2026-10-26).
            parts = [("file", (name, fh, mime)), ("minorEdit", (None, "true"))]
            try:
                # PUT creates the attachment, or a new version when the name already exists.
                response = requests.put(
                    f"{CONFLUENCE_BASE_URL}/wiki/rest/api/content/{page_id}/child/attachment",
                    headers=headers, files=parts, timeout=120)
            except requests.exceptions.RequestException as exc:
                return {"error": True, "message": f"Upload failed for {name}: {exc}"}
        if response.status_code not in (200, 201):
            return format_error(response.status_code, response.text)
        body = response.json()
        result = (body.get("results") or [body])[0]
        out.append({
            "file": name,
            "attachment_id": result.get("id"),
            "version": (result.get("version") or {}).get("number"),
            "embed": f'<ac:image ac:width="900"><ri:attachment ri:filename="{name}" /></ac:image>',
        })
    return {"success": True, "page_id": page_id, "attachments": out}
