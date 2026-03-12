"""Bitbucket Cloud REST API v2.0 client."""

import time
from typing import Any, Dict, List, Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from ..base.auth import get_bitbucket_auth_headers, get_workspace
from ..base.exceptions import (
    AtlassianAPIError,
    AuthenticationError,
    ConflictError,
    NotFoundError,
    PermissionError,
    RateLimitError,
)

BITBUCKET_BASE_URL = "https://api.bitbucket.org/2.0"


class BitbucketAPI:
    """Bitbucket Cloud REST API v2.0 client with retry and error handling."""

    def __init__(self, timeout: int = 30, retries: int = 3):
        self.base_url = BITBUCKET_BASE_URL
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
        return get_bitbucket_auth_headers()

    def _handle_response(self, response: requests.Response) -> Any:
        if response.status_code in (200, 201):
            return response.json() if response.content else {}
        if response.status_code == 204:
            return {}
        if response.status_code == 401:
            raise AuthenticationError("Authentication failed. Check BITBUCKET_REPO_TOKEN.")
        if response.status_code == 403:
            raise PermissionError("Insufficient permissions.")
        if response.status_code == 404:
            raise NotFoundError("Resource not found.")
        if response.status_code == 409:
            raise ConflictError("Conflict — cannot complete in current state.")
        if response.status_code == 429:
            raise RateLimitError("Rate limit exceeded. Please wait and retry.")
        try:
            msg = response.json().get("error", {}).get("message", f"HTTP {response.status_code}")
        except Exception:
            msg = f"HTTP {response.status_code}: {response.reason}"
        raise AtlassianAPIError(f"API error: {msg}")

    def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        url = f"{self.base_url}{endpoint}"
        headers = self._headers()
        if "headers" in kwargs:
            headers.update(kwargs.pop("headers"))
        response = self.session.request(method=method, url=url, headers=headers, timeout=self.timeout, **kwargs)
        return self._handle_response(response)

    def get(self, endpoint: str, params: Optional[Dict] = None) -> Any:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, json: Optional[Dict] = None) -> Any:
        return self._request("POST", endpoint, json=json)

    def put(self, endpoint: str, json: Optional[Dict] = None) -> Any:
        return self._request("PUT", endpoint, json=json)

    def delete(self, endpoint: str) -> Any:
        return self._request("DELETE", endpoint)

    def get_all_pages(self, endpoint: str, params: Optional[Dict] = None) -> List[Any]:
        results = []
        url = endpoint
        first = True
        while url:
            if first:
                data = self.get(url, params)
                first = False
            else:
                relative = url.replace(self.base_url, "")
                data = self.get(relative)
            results.extend(data.get("values", []))
            url = data.get("next")
            if url:
                time.sleep(0.1)
        return results

    def get_paginated(self, endpoint: str, params: Optional[Dict] = None) -> Dict[str, Any]:
        response = self.get(endpoint, params)
        return {
            "values": response.get("values", []),
            "page": response.get("page", 1),
            "pagelen": response.get("pagelen", 10),
            "size": response.get("size", 0),
            "next": response.get("next"),
            "previous": response.get("previous"),
        }

    # ── Pull Request Methods ───────────────────────────────────────────────────

    def create_pull_request(self, workspace: str, repo: str, **kwargs) -> Dict[str, Any]:
        payload: dict = {
            "title": kwargs.get("title"),
            "description": kwargs.get("description", ""),
            "source": {"branch": {"name": kwargs.get("source_branch")}},
            "destination": {"branch": {"name": kwargs.get("destination_branch", "main")}},
        }
        if kwargs.get("close_source_branch"):
            payload["close_source_branch"] = True
        if kwargs.get("reviewers"):
            payload["reviewers"] = kwargs["reviewers"]
        return self.post(f"/repositories/{workspace}/{repo}/pullrequests", json=payload)

    def get_pull_request(self, workspace: str, repo: str, pr_id: int) -> Dict[str, Any]:
        return self.get(f"/repositories/{workspace}/{repo}/pullrequests/{pr_id}")

    def list_pull_requests(self, workspace: str, repo: str, **kwargs) -> List[Dict[str, Any]]:
        params: dict = {}
        if kwargs.get("state"):
            params["state"] = kwargs["state"]
        if kwargs.get("limit"):
            params["pagelen"] = kwargs["limit"]

        query_parts = []
        if kwargs.get("author"):
            query_parts.append(f'author.username="{kwargs["author"]}"')
        if kwargs.get("reviewer"):
            query_parts.append(f'reviewers.username="{kwargs["reviewer"]}"')
        if query_parts:
            params["q"] = " AND ".join(query_parts)

        if kwargs.get("fetch_all"):
            return self.get_all_pages(f"/repositories/{workspace}/{repo}/pullrequests", params)
        return self.get_paginated(f"/repositories/{workspace}/{repo}/pullrequests", params)["values"]

    def update_pull_request(self, workspace: str, repo: str, pr_id: int, **kwargs) -> Dict[str, Any]:
        payload: dict = {}
        if kwargs.get("title"):
            payload["title"] = kwargs["title"]
        if kwargs.get("description") is not None:
            payload["description"] = kwargs["description"]
        if kwargs.get("destination_branch"):
            payload["destination"] = {"branch": {"name": kwargs["destination_branch"]}}
        if kwargs.get("reviewers"):
            payload["reviewers"] = kwargs["reviewers"]
        return self.put(f"/repositories/{workspace}/{repo}/pullrequests/{pr_id}", json=payload)

    def approve_pull_request(self, workspace: str, repo: str, pr_id: int) -> Dict[str, Any]:
        return self.post(f"/repositories/{workspace}/{repo}/pullrequests/{pr_id}/approve")

    def unapprove_pull_request(self, workspace: str, repo: str, pr_id: int) -> Dict[str, Any]:
        return self.delete(f"/repositories/{workspace}/{repo}/pullrequests/{pr_id}/approve")

    def decline_pull_request(self, workspace: str, repo: str, pr_id: int, message: Optional[str] = None) -> Dict[str, Any]:
        payload = {"message": message} if message else {}
        return self.post(f"/repositories/{workspace}/{repo}/pullrequests/{pr_id}/decline", json=payload)

    def merge_pull_request(self, workspace: str, repo: str, pr_id: int, **kwargs) -> Dict[str, Any]:
        payload: dict = {}
        if kwargs.get("message"):
            payload["message"] = kwargs["message"]
        if kwargs.get("close_source_branch"):
            payload["close_source_branch"] = True
        if kwargs.get("merge_strategy"):
            payload["merge_strategy"] = kwargs["merge_strategy"]
        return self.post(f"/repositories/{workspace}/{repo}/pullrequests/{pr_id}/merge", json=payload)

    # ── Comment Methods ────────────────────────────────────────────────────────

    def add_comment(self, workspace: str, repo: str, pr_id: int, message: str, **kwargs) -> Dict[str, Any]:
        payload: dict = {"content": {"raw": message}}

        if kwargs.get("file"):
            inline: dict = {"to": {"path": kwargs["file"]}}
            if kwargs.get("line"):
                inline["to"]["line"] = kwargs["line"]
            if kwargs.get("from_line") and kwargs.get("to_line"):
                inline["from"] = {"path": kwargs["file"], "line": kwargs["from_line"]}
                inline["to"]["line"] = kwargs["to_line"]
            payload["inline"] = inline

        if kwargs.get("reply_to"):
            payload["parent"] = {"id": kwargs["reply_to"]}

        return self.post(f"/repositories/{workspace}/{repo}/pullrequests/{pr_id}/comments", json=payload)

    def get_comments(self, workspace: str, repo: str, pr_id: int) -> List[Dict[str, Any]]:
        return self.get_all_pages(f"/repositories/{workspace}/{repo}/pullrequests/{pr_id}/comments")

    # ── Utility Methods ────────────────────────────────────────────────────────

    def get_diff(self, workspace: str, repo: str, pr_id: int) -> str:
        url = f"{self.base_url}/repositories/{workspace}/{repo}/pullrequests/{pr_id}/diff"
        headers = self._headers()
        headers["Accept"] = "text/plain"
        response = self.session.get(url, headers=headers, timeout=self.timeout)
        if response.status_code == 200:
            return response.text
        self._handle_response(response)
        return ""

    def get_diffstat(self, workspace: str, repo: str, pr_id: int) -> Dict[str, Any]:
        return self.get(f"/repositories/{workspace}/{repo}/pullrequests/{pr_id}/diffstat")

    def get_activity(self, workspace: str, repo: str, pr_id: int) -> List[Dict[str, Any]]:
        return self.get_all_pages(f"/repositories/{workspace}/{repo}/pullrequests/{pr_id}/activity")

    def get_current_user(self) -> Dict[str, Any]:
        return self.get("/user")

    def test_connection(self) -> Dict[str, Any]:
        try:
            user = self.get_current_user()
            return {"success": True, "user": {"username": user.get("username"), "display_name": user.get("display_name")}}
        except Exception as e:
            return {"success": False, "error": str(e)}
