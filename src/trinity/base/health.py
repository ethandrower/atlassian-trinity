"""Check that Trinity's logins work, so a bad one is reported as a bad login.

Jira quietly downgrades a rejected Basic Auth login to an anonymous visitor: an
issue lookup answers 404 and a search answers 200 with no results. Nothing in
the response says the login failed. Asking "who am I?" is the one call that does
answer 401, so that is what these checks use.
"""

import os
from typing import Any, Dict, List, Optional

import requests

from .auth import CONFIG_FILE, get_jira_auth_headers, load_config
from .client import _resolve_jira_url
from .exceptions import AuthenticationError, TrinityError
from .repo_context import resolve_workspace_repo

API_TOKEN_PAGE = "https://id.atlassian.com/manage-profile/security/api-tokens"


def _atlassian_email(config: Dict[str, Any]) -> Optional[str]:
    return (
        os.getenv("ATLASSIAN_EMAIL")
        or os.getenv("ATLASSIAN_SERVICE_ACCOUNT_EMAIL")
        or (config.get("atlassian") or {}).get("email")
    )


def _whoami() -> Optional[requests.Response]:
    """Ask Jira who we are. None means Jira couldn't be reached to ask."""
    try:
        return requests.get(
            f"{_resolve_jira_url()}/rest/api/3/myself",
            headers=get_jira_auth_headers(),
            timeout=15,
        )
    except requests.RequestException:
        return None


def _rejected_message() -> str:
    email = _atlassian_email(load_config())
    return (
        f"Atlassian rejected the login for {email}. Jira and Confluence would answer "
        "as an anonymous visitor, so tickets would look missing and searches empty. "
        f"Create a token at {API_TOKEN_PAGE}, then run: "
        "trinity config --email YOU@co.com --token NEW_TOKEN"
    )


def require_atlassian_login() -> None:
    """Raise if Atlassian says the login is bad.

    Only a definite 401 stops the command. A network blip here shouldn't fail a
    command that might still work, and the command reports its own errors.
    """
    response = _whoami()
    if response is not None and response.status_code == 401:
        raise AuthenticationError(_rejected_message())


def _check_atlassian() -> Dict[str, Any]:
    check = {"check": "Jira and Confluence login", "ok": False}
    try:
        response = _whoami()
    except AuthenticationError as e:
        return {**check, "detail": str(e)}
    if response is None:
        return {**check, "detail": f"Could not reach {_resolve_jira_url() or 'Jira (no URL set)'}"}
    if response.status_code == 401:
        return {**check, "detail": _rejected_message()}
    if response.status_code != 200:
        return {**check, "detail": f"Unexpected answer from Jira: HTTP {response.status_code}"}
    me = response.json()
    return {**check, "ok": True, "detail": f"Signed in as {me.get('emailAddress') or me.get('displayName')}"}


def _check_repo(slug: str) -> Dict[str, Any]:
    from ..bitbucket.api import BitbucketAPI

    check = {"check": f"Bitbucket {slug}", "ok": False}
    try:
        BitbucketAPI().get(f"/repositories/{slug}")
    except (TrinityError, requests.RequestException) as e:
        return {**check, "detail": str(e)}
    return {**check, "ok": True, "detail": "Token works"}


def run_checks() -> Dict[str, Any]:
    """Check Atlassian, every repo with a token, and the repo in use here."""
    bitbucket = load_config().get("bitbucket") or {}
    slugs: List[str] = list(bitbucket.get("repo_tokens") or {})
    workspace, repo = resolve_workspace_repo(os.getenv("BITBUCKET_WORKSPACE"))
    current = f"{workspace}/{repo}" if workspace and repo else None
    if current and current not in slugs:
        slugs.append(current)

    checks = [_check_atlassian()] + [_check_repo(slug) for slug in sorted(slugs)]
    return {
        "ok": all(c["ok"] for c in checks),
        "config_file": str(CONFIG_FILE),
        "current_repo": current,
        "checks": checks,
    }
