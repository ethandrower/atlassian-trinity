"""
Unified authentication for Trinity.

Credential resolution order (for each service):
  1. Environment variable  (highest priority — works in CI/Heroku/agents)
  2. Config file           (~/.trinity/config.yaml)
  3. Raise AuthenticationError

Env vars recognized:
  Jira/Confluence:  ATLASSIAN_EMAIL, ATLASSIAN_API_TOKEN, ATLASSIAN_CLOUD_ID
  Bitbucket:        BITBUCKET_REPO_TOKEN  (preferred)
                    BITBUCKET_USERNAME + BITBUCKET_APP_PASSWORD  (fallback)
"""

import base64
import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from dotenv import load_dotenv

from .exceptions import AuthenticationError, ConfigurationError

# Load .env from current dir or any parent
load_dotenv()

# ── Config file location ───────────────────────────────────────────────────────
CONFIG_DIR = Path.home() / ".trinity"
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG: Dict[str, Any] = {
    "atlassian": {
        "email": None,
        "api_token": None,
        "cloud_id": None,
        "jira_url": None,
    },
    "bitbucket": {
        "repo_token": None,
        "username": None,
        "app_password": None,
        "workspace": None,
        # Default repo for `bb` commands invoked without -R. Resolution
        # order: -R flag → BITBUCKET_DEFAULT_REPO env → this field →
        # current git remote → error. Keeps `bb pr list` ergonomic when
        # working out of one main repo.
        "default_repo": None,
        # Per-repo bearer tokens, keyed by "workspace/repo" slug. Lets a
        # user keep separate repository access tokens (each scoped to
        # exactly one repo) without losing cross-repo functionality.
        # Lookup order: this map → BITBUCKET_REPO_TOKEN env / repo_token
        # field → username + app_password Basic Auth.
        "repo_tokens": {},
    },
    "api": {
        "timeout": 30,
        "retries": 3,
    },
}


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(exist_ok=True, mode=0o700)


def load_config() -> Dict[str, Any]:
    """Load config from ~/.trinity/config.yaml, creating defaults if absent."""
    _ensure_config_dir()

    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        with open(CONFIG_FILE) as f:
            user_config = yaml.safe_load(f) or {}

        def _merge(default: dict, user: dict) -> dict:
            result = default.copy()
            for k, v in user.items():
                if k in result and isinstance(result[k], dict) and isinstance(v, dict):
                    result[k] = _merge(result[k], v)
                else:
                    result[k] = v
            return result

        return _merge(DEFAULT_CONFIG, user_config)

    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in config file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Error loading config: {e}")


def save_config(config: Dict[str, Any]) -> None:
    """Persist config to ~/.trinity/config.yaml with secure permissions."""
    _ensure_config_dir()
    try:
        with open(CONFIG_FILE, "w") as f:
            yaml.safe_dump(config, f, default_flow_style=False, indent=2)
        CONFIG_FILE.chmod(0o600)
    except Exception as e:
        raise ConfigurationError(f"Error saving config: {e}")


# ── Jira / Confluence ──────────────────────────────────────────────────────────

def get_jira_auth_headers(config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """
    Return Basic-Auth headers for Jira (and Confluence) REST API.

    Resolves credentials from env vars first, then config file.
    """
    if config is None:
        config = load_config()

    atlassian = config.get("atlassian", {})

    email = (
        os.getenv("ATLASSIAN_EMAIL")
        or os.getenv("ATLASSIAN_SERVICE_ACCOUNT_EMAIL")
        or atlassian.get("email")
    )
    token = (
        os.getenv("ATLASSIAN_API_TOKEN")
        or os.getenv("ATLASSIAN_SERVICE_ACCOUNT_TOKEN")
        or atlassian.get("api_token")
    )

    if not email or not token:
        raise AuthenticationError(
            "Atlassian credentials missing. Set ATLASSIAN_EMAIL and ATLASSIAN_API_TOKEN "
            "(or run: trinity config --email YOU@co.com --token YOUR_TOKEN)"
        )

    encoded = base64.b64encode(f"{email}:{token}".encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "trinity-atlassian-cli/0.1.0",
    }


def get_confluence_auth_headers(config: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Same credentials as Jira — Atlassian shares auth across products."""
    return get_jira_auth_headers(config)


# ── Bitbucket ──────────────────────────────────────────────────────────────────

def get_bitbucket_auth_headers(
    config: Optional[Dict[str, Any]] = None,
    repo: Optional[str] = None,
) -> Dict[str, str]:
    """
    Return auth headers for Bitbucket REST API v2.0.

    Priority:
      1. Per-repo bearer token  (bitbucket.repo_tokens["workspace/repo"]),
         when ``repo`` is supplied and a matching entry exists. This is
         the only correct path for users who manage multiple repository
         access tokens — each is single-repo-scoped, so picking the wrong
         one produces silent 404s on cross-repo calls.
      2. Global bearer token    (BITBUCKET_REPO_TOKEN env or repo_token
         field). Works for the single-repo case and for any
         workspace-scoped token a user has stuffed in the same field.
      3. Basic auth             (BITBUCKET_USERNAME + BITBUCKET_APP_PASSWORD).
         Recommended for cross-repo use — App Passwords are workspace-wide.

    Args:
        config: Optional pre-loaded config; loaded fresh if None.
        repo:   Optional "workspace/repo" slug used to look up a per-repo
                token. Callers that know the repo (i.e. anything that
                hits a /repositories/{ws}/{repo}/... URL) should pass it
                so per-repo tokens are honored.
    """
    if config is None:
        config = load_config()

    bb = config.get("bitbucket", {})

    # 1. Per-repo token map — only consulted when caller passed a slug.
    if repo:
        repo_tokens = bb.get("repo_tokens") or {}
        per_repo = repo_tokens.get(repo) if isinstance(repo_tokens, dict) else None
        if per_repo:
            return _bearer_headers(per_repo)

    # 2. Single global bearer token.
    repo_token = os.getenv("BITBUCKET_REPO_TOKEN") or bb.get("repo_token")
    if repo_token:
        return _bearer_headers(repo_token)

    # 3. App Password / username Basic Auth.
    username = os.getenv("BITBUCKET_USERNAME") or bb.get("username")
    app_password = os.getenv("BITBUCKET_APP_PASSWORD") or bb.get("app_password")
    if username and app_password:
        encoded = base64.b64encode(f"{username}:{app_password}".encode()).decode()
        return {
            "Authorization": f"Basic {encoded}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "trinity-atlassian-cli/0.1.0",
        }

    raise AuthenticationError(
        "Bitbucket credentials missing. Set BITBUCKET_REPO_TOKEN "
        "(or run: trinity config --bb-token YOUR_TOKEN)"
    )


def _bearer_headers(token: str) -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "trinity-atlassian-cli/0.1.0",
    }


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_authenticated(service: str = "jira") -> bool:
    """Check whether credentials for the given service are available."""
    try:
        if service in ("jira", "confluence"):
            get_jira_auth_headers()
        elif service == "bitbucket":
            get_bitbucket_auth_headers()
        return True
    except AuthenticationError:
        return False


def get_workspace(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Return the configured Bitbucket workspace."""
    if config is None:
        config = load_config()
    return (
        os.getenv("BITBUCKET_WORKSPACE")
        or config.get("bitbucket", {}).get("workspace")
    )


def get_default_repo(config: Optional[Dict[str, Any]] = None) -> Optional[str]:
    """Return the configured Bitbucket default repo (workspace/repo or just repo)."""
    if config is None:
        config = load_config()
    return (
        os.getenv("BITBUCKET_DEFAULT_REPO")
        or config.get("bitbucket", {}).get("default_repo")
    )
