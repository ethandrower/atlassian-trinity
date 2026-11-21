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
from dotenv import find_dotenv, load_dotenv

from .exceptions import AuthenticationError, ConfigurationError

# Load .env from the invocation directory or any parent.
#
# The default search walks up from *this file's* location, which lives
# inside the installed package -- so an installed console script never
# saw a project's .env, despite the old comment here promising it did.
# ~/.trinity/config.yaml stays the machine-wide source of truth; this
# only restores per-project override for people who want it.
#
# Skipped under TRINITY_HOME: that means "act as exactly this identity", and a
# project .env (citemed_web's carries a BITBUCKET_REPO_TOKEN) would otherwise
# outrank the identity's own config and silently swap who trinity acts as.
if not os.environ.get("TRINITY_HOME"):
    load_dotenv(find_dotenv(usecwd=True))

# ── Config file location ───────────────────────────────────────────────────────
# TRINITY_HOME points one process tree at a different identity's config (e.g. a
# bot user's ~/.trinity-agent) without touching the machine-wide ~/.trinity or
# setting per-credential env vars that leak into everything else.
CONFIG_DIR = Path(os.environ.get("TRINITY_HOME") or Path.home() / ".trinity").expanduser()
CONFIG_FILE = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG: Dict[str, Any] = {
    "atlassian": {
        "email": None,
        "api_token": None,
        "cloud_id": None,
        "jira_url": None,
    },
    "jira": {
        # Team (customfield_10001) set on every issue `jira create` makes in that
        # project unless --team / --no-team says otherwise, keyed by project key:
        # {"ECD": "<atlassian team id>"}. Agents create most tickets, and a ticket
        # with no Team drops off the team's boards and reports.
        "default_team": {},
    },
    "bitbucket": {
        "repo_token": None,
        "username": None,
        "app_password": None,
        "workspace": None,
        # Named user identities for commands that must act as a real user
        # (approve / unapprove / decline / reviewer state). Keyed by a short
        # name, e.g. {"devbot": {"home": "~/.trinity-agent"}}. An entry either
        # points at another TRINITY_HOME directory whose config.yaml carries
        # bitbucket.username + bitbucket.app_password (no secret duplicated), or
        # carries {"username": ..., "app_password": ...} inline. Selected with
        # `trinity bb approve <id> --as <name>`. Repository access tokens can't
        # approve PRs — only a real user can — so these name the users who may.
        "identities": {},
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
        # Reviewers `bb ready` adds when a PR leaves draft (UUIDs, nicknames
        # or aliases), and the extra ones it adds with --client-visible.
        "default_reviewers": [],
        "pm_reviewers": [],
        # Short names for reviewers, e.g. {"devbot": "{55a6c1a9-...}"}.
        "reviewer_aliases": {},
    },
    "api": {
        "timeout": 30,
        "retries": 3,
    },
}


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(exist_ok=True, mode=0o700)


def _merge(default: dict, user: dict) -> dict:
    result = default.copy()
    for k, v in user.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _merge(result[k], v)
        else:
            result[k] = v
    return result


def _load_config_file(config_file: Path) -> Dict[str, Any]:
    """Read one config.yaml and merge it onto DEFAULT_CONFIG."""
    with open(config_file) as f:
        user_config = yaml.safe_load(f) or {}
    return _merge(DEFAULT_CONFIG, user_config)


def load_config() -> Dict[str, Any]:
    """Load config from ~/.trinity/config.yaml, creating defaults if absent."""
    _ensure_config_dir()

    if not CONFIG_FILE.exists():
        save_config(DEFAULT_CONFIG)
        return DEFAULT_CONFIG.copy()

    try:
        return _load_config_file(CONFIG_FILE)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in config file: {e}")
    except Exception as e:
        raise ConfigurationError(f"Error loading config: {e}")


def load_config_from(home: str) -> Dict[str, Any]:
    """Load the config.yaml of another TRINITY_HOME directory.

    Used to resolve a named identity whose user credentials live in a separate
    home (e.g. a bot's ~/.trinity-agent), so the secret is read from there
    rather than duplicated into the caller's config.
    """
    path = Path(home).expanduser() / "config.yaml"
    if not path.exists():
        raise ConfigurationError(
            f"No Trinity config at {path} for this identity (expected a config.yaml there)."
        )
    try:
        return _load_config_file(path)
    except yaml.YAMLError as e:
        raise ConfigurationError(f"Invalid YAML in {path}: {e}")


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
        return _basic_headers(username, app_password)

    if repo:
        # Name the repo. With per-repo tokens the common failure is not
        # "no credentials at all" but "credentials for other repos, none
        # for this one", and the generic message sends people to re-set a
        # global token they may deliberately not want.
        raise AuthenticationError(
            f"No Bitbucket credentials for {repo}. Add a per-repo token:\n"
            f"  trinity config --bb-repo-token {repo}=YOUR_TOKEN\n"
            "(or set a workspace-wide one with: trinity config --bb-token YOUR_TOKEN)"
        )
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


def _basic_headers(username: str, app_password: str) -> Dict[str, str]:
    encoded = base64.b64encode(f"{username}:{app_password}".encode()).decode()
    return {
        "Authorization": f"Basic {encoded}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "trinity-atlassian-cli/0.1.0",
    }


# ── Bitbucket user auth (approve / decline / reviewer state) ─────────────────────
#
# Some Bitbucket actions are tied to a *user*, not a repository: approving a PR
# records "this person approved". A repository (or workspace) access token is not
# a user, so Bitbucket rejects /approve from one with HTTP 400. These helpers
# resolve Basic-auth credentials for a real user, so approve/decline act as that
# user and never silently fall through to a token that cannot perform them.

def has_bitbucket_user_credentials(config: Optional[Dict[str, Any]] = None) -> bool:
    """True when user credentials (username + app_password) are available.

    Checks env vars first, then the current home's config. Does not consider
    named identities — those are selected explicitly with ``as_identity``.
    """
    if config is None:
        config = load_config()
    bb = config.get("bitbucket", {}) or {}
    username = os.getenv("BITBUCKET_USERNAME") or bb.get("username")
    app_password = os.getenv("BITBUCKET_APP_PASSWORD") or bb.get("app_password")
    return bool(username and app_password)


def _identity_credentials(name: str, config: Dict[str, Any]) -> tuple:
    """Resolve (username, app_password) for a named identity, or raise."""
    identities = (config.get("bitbucket") or {}).get("identities") or {}
    entry = identities.get(name)
    if entry is None:
        available = ", ".join(sorted(identities)) or "none configured"
        raise AuthenticationError(
            f"Unknown Bitbucket identity '{name}'. Configured identities: {available}. "
            f"Add one with: trinity config --bb-identity {name}=/path/to/home "
            "(a TRINITY_HOME dir whose config.yaml has bitbucket.username + "
            "bitbucket.app_password)."
        )
    # An entry may be a bare home path (string) or a dict with a home and/or
    # inline username + app_password.
    if isinstance(entry, str):
        entry = {"home": entry}
    if not isinstance(entry, dict):
        raise AuthenticationError(
            f"Malformed Bitbucket identity '{name}' in config (expected a path or a "
            "mapping with home / username / app_password)."
        )

    username = entry.get("username")
    app_password = entry.get("app_password")
    home = entry.get("home")
    if home and not (username and app_password):
        home_bb = (load_config_from(home).get("bitbucket") or {})
        username = username or home_bb.get("username")
        app_password = app_password or home_bb.get("app_password")

    if not (username and app_password):
        where = f" (looked in {home})" if home else ""
        raise AuthenticationError(
            f"Bitbucket identity '{name}' has no usable user credentials{where}. "
            "It needs a username + app_password, inline or in the referenced home's "
            "config.yaml (bitbucket.username / bitbucket.app_password)."
        )
    return username, app_password


def _no_user_auth_message(config: Dict[str, Any], repo: Optional[str]) -> str:
    """Actionable error when a user-only action has no user credentials."""
    bb = config.get("bitbucket") or {}
    identities = sorted(bb.get("identities") or {})
    has_token = bool(
        os.getenv("BITBUCKET_REPO_TOKEN")
        or bb.get("repo_token")
        or bb.get("repo_tokens")
    )
    lead = (
        "Bitbucket repository access tokens cannot approve or decline pull requests "
        "— only a real user account can. "
        if has_token
        else "No Bitbucket user credentials are configured. "
    )
    opts = [
        "configure a user app password: trinity config --bb-username USER "
        "--bb-app-password PW"
    ]
    if identities:
        opts.append("or act as a configured identity with --as <"
                    + "|".join(identities) + ">")
    else:
        opts.append("or add one: trinity config --bb-identity devbot=~/.trinity-agent "
                    "then pass --as devbot")
    opts.append("or set TRINITY_HOME to a home whose config has user credentials")
    return lead + "; ".join(opts) + "."


def get_bitbucket_user_auth_headers(
    config: Optional[Dict[str, Any]] = None,
    repo: Optional[str] = None,
    as_identity: Optional[str] = None,
) -> Dict[str, str]:
    """Return Basic-auth headers for a real Bitbucket user.

    Unlike :func:`get_bitbucket_auth_headers`, this never uses a repository
    access token: those cannot approve/decline PRs. Resolution:

      1. ``as_identity`` — the named identity's credentials (authoritative; a
         repo-token env var cannot override an explicit identity).
      2. Otherwise env (BITBUCKET_USERNAME + BITBUCKET_APP_PASSWORD) then the
         current home's bitbucket.username + bitbucket.app_password.

    Raises AuthenticationError with a remediation hint when no user credentials
    are available.
    """
    if config is None:
        config = load_config()

    if as_identity:
        username, app_password = _identity_credentials(as_identity, config)
        return _basic_headers(username, app_password)

    bb = config.get("bitbucket", {}) or {}
    username = os.getenv("BITBUCKET_USERNAME") or bb.get("username")
    app_password = os.getenv("BITBUCKET_APP_PASSWORD") or bb.get("app_password")
    if username and app_password:
        return _basic_headers(username, app_password)

    raise AuthenticationError(_no_user_auth_message(config, repo))


# ── Helpers ────────────────────────────────────────────────────────────────────

def is_authenticated(service: str = "jira", repo: Optional[str] = None) -> bool:
    """Check whether credentials for the given service are available.

    ``repo`` is an optional "workspace/repo" slug. Pass it when the caller
    knows which repository the command targets, so a per-repo token is
    credited to the check.

    A non-empty ``bitbucket.repo_tokens`` map counts as configured even
    when no slug is supplied. Repository access tokens are each scoped to
    exactly one repo, so a machine can be fully credentialed for every
    repo it uses without ever setting the global ``repo_token``. This
    function used to ignore the map entirely, which made the pre-flight
    gate in the ``bb`` front-end reject every command on such a machine --
    including commands the credential resolver would have served
    correctly a moment later.
    """
    try:
        if service in ("jira", "confluence"):
            get_jira_auth_headers()
        elif service == "bitbucket":
            try:
                get_bitbucket_auth_headers(repo=repo)
            except AuthenticationError:
                # No slug-specific or global credential. Fall back to
                # asking whether *any* per-repo token is on file.
                bb = load_config().get("bitbucket", {})
                repo_tokens = bb.get("repo_tokens") or {}
                if not (isinstance(repo_tokens, dict) and repo_tokens):
                    raise
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
