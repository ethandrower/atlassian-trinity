"""
Shared HTTP client and URL constants for Trinity.

Provides:
  - URL constants for all three Atlassian services
  - AtlassianClient — session-based HTTP client with retry
  - format_error() — standardized error dict (Jira module compatibility)
  - build_adf_comment() — Atlassian Document Format comment builder
"""

import os
import time
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth import get_jira_auth_headers, get_bitbucket_auth_headers, load_config
from .exceptions import (
    AtlassianAPIError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionError,
    RateLimitError,
)

load_dotenv()

# ── URL constants ──────────────────────────────────────────────────────────────
#
# Trinity authenticates via Basic Auth (email + API token), which the OAuth
# gateway under api.atlassian.com/ex/{product}/{cloudId} does NOT accept — it
# only honors OAuth bearer tokens. The correct URL family for Basic Auth is
# the instance domain (e.g. https://acme.atlassian.net for Jira, with
# Confluence served from the same host under /wiki/...). The constants below
# are resolved lazily from env vars first, then ~/.trinity/config.yaml's
# atlassian.jira_url, so existing callsites (`from ..base import
# JIRA_BASE_URL`) keep working unchanged.

# Bitbucket has a single global base URL — no cloud-id segment and no
# per-instance domain — so it stays a plain constant.
BITBUCKET_BASE_URL = "https://api.bitbucket.org/2.0"


def _resolve_jira_url() -> str:
    """
    Resolve the Jira instance URL (e.g. https://acme.atlassian.net).

    Priority:
      1. ATLASSIAN_JIRA_URL env var (or legacy JIRA_INSTANCE_URL)
      2. atlassian.jira_url from ~/.trinity/config.yaml
      3. Empty string — caller will see a clear HTTP error rather than
         the misleading 404s the old gateway URLs produced when
         cloudId was unset.
    """
    try:
        cfg = (load_config().get("atlassian") or {}).get("jira_url")
    except Exception:
        # Never let config load failures block import — `trinity config`
        # itself must work with no config file in place.
        cfg = None
    base = (
        os.getenv("ATLASSIAN_JIRA_URL")
        or os.getenv("JIRA_INSTANCE_URL")
        or cfg
        or ""
    )
    return base.rstrip("/")


def _resolve_cloud_id() -> str:
    """Resolve the Atlassian cloudId. No longer used to build URLs after
    the gateway → instance-domain switch, but still exposed for callers
    that want it for OAuth-style URLs."""
    try:
        cfg = (load_config().get("atlassian") or {}).get("cloud_id")
    except Exception:
        cfg = None
    return os.getenv("ATLASSIAN_CLOUD_ID") or cfg or ""


def __getattr__(name: str) -> Any:
    """Lazy URL constants — see comment block above."""
    if name == "JIRA_BASE_URL":
        return _resolve_jira_url()
    if name == "AGILE_BASE_URL":
        base = _resolve_jira_url()
        return f"{base}/rest/agile/1.0" if base else ""
    if name == "CONFLUENCE_BASE_URL":
        # Confluence shares the instance domain. Callers append
        # /wiki/rest/api/... to this base — that path is correct for
        # both the gateway and instance-domain URL families, so no
        # callsite changes are needed.
        return _resolve_jira_url()
    if name == "JIRA_WEB_URL":
        return _resolve_jira_url()
    if name == "ATLASSIAN_CLOUD_ID":
        return _resolve_cloud_id()
    raise AttributeError(f"module 'trinity.base.client' has no attribute {name!r}")


# ── Shared helpers ─────────────────────────────────────────────────────────────

def format_error(status_code: int, message: str) -> Dict[str, Any]:
    """Return a standardized error dict — keeps Jira module signatures intact."""
    return {
        "error": True,
        "status_code": status_code,
        "message": message,
    }


def build_adf_comment(text: str, mentions: Optional[list] = None) -> dict:
    """
    Build an Atlassian Document Format (ADF) comment body.

    Args:
        text: Plain text (use @Name as placeholder for mentions)
        mentions: [{"id": "accountId", "name": "Display Name"}, ...]

    Returns:
        ADF document dict suitable for Jira/Confluence comment API
    """
    content = []

    if mentions:
        parts = text
        for mention in mentions:
            placeholder = f"@{mention['name']}"
            if placeholder in parts:
                before, after = parts.split(placeholder, 1)
                if before:
                    content.append({"type": "text", "text": before})
                content.append({
                    "type": "mention",
                    "attrs": {
                        "id": mention["id"],
                        "text": f"@{mention['name']}",
                        "accessLevel": "",
                    },
                })
                parts = after
        if parts:
            content.append({"type": "text", "text": parts})
    else:
        content.append({"type": "text", "text": text})

    return {
        "version": 1,
        "type": "doc",
        "content": [{"type": "paragraph", "content": content}],
    }


# ── HTTP client ────────────────────────────────────────────────────────────────

class AtlassianClient:
    """
    Session-based HTTP client for Atlassian REST APIs.

    Handles:
      - Auth header injection per service
      - Automatic retry with backoff (429, 5xx)
      - Typed exception mapping
      - Paginated result fetching
    """

    def __init__(self, service: str = "jira", timeout: int = 30, retries: int = 3):
        """
        Args:
            service: "jira", "confluence", or "bitbucket"
            timeout: Request timeout in seconds
            retries: Max retry attempts
        """
        self.service = service
        self.timeout = timeout

        self.session = requests.Session()
        retry_strategy = Retry(
            total=retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS"],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def _headers(self) -> Dict[str, str]:
        if self.service == "bitbucket":
            return get_bitbucket_auth_headers()
        return get_jira_auth_headers()

    def _handle_response(self, response: requests.Response) -> Any:
        if response.status_code in (200, 201):
            return response.json() if response.content else {}
        if response.status_code == 204:
            return {}
        if response.status_code == 401:
            raise AuthenticationError("Authentication failed. Check your credentials.")
        if response.status_code == 403:
            raise PermissionError("Insufficient permissions.")
        if response.status_code == 404:
            raise NotFoundError("Resource not found.")
        if response.status_code == 409:
            raise ConflictError("Conflict — cannot complete operation in current state.")
        if response.status_code == 429:
            raise RateLimitError("Rate limit exceeded. Please wait and retry.")
        try:
            msg = response.json().get("error", {}).get("message", f"HTTP {response.status_code}")
        except Exception:
            msg = f"HTTP {response.status_code}: {response.reason}"
        raise AtlassianAPIError(f"API error: {msg}")

    def request(self, method: str, url: str, **kwargs) -> Any:
        headers = self._headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        response = self.session.request(
            method=method,
            url=url,
            headers=headers,
            timeout=self.timeout,
            **kwargs,
        )
        return self._handle_response(response)

    def get(self, url: str, params: Optional[Dict] = None) -> Any:
        return self.request("GET", url, params=params)

    def post(self, url: str, json: Optional[Dict] = None) -> Any:
        return self.request("POST", url, json=json)

    def put(self, url: str, json: Optional[Dict] = None) -> Any:
        return self.request("PUT", url, json=json)

    def delete(self, url: str) -> Any:
        return self.request("DELETE", url)

    def get_all_pages(self, url: str, params: Optional[Dict] = None) -> List[Any]:
        """Fetch all pages of a paginated Bitbucket response (values + next)."""
        results = []
        current_url = url
        first = True

        while current_url:
            if first:
                data = self.get(current_url, params)
                first = False
            else:
                # next URL is absolute — strip base
                relative = current_url.replace(BITBUCKET_BASE_URL, "")
                data = self.get(BITBUCKET_BASE_URL + relative)

            results.extend(data.get("values", []))
            current_url = data.get("next")
            if current_url:
                time.sleep(0.1)

        return results
