"""Reviewer lookup and merging for pull requests.

A reviewer can be named three ways:

* a Bitbucket account UUID, with or without braces: ``{55a6c1a9-...}``
* an alias from config (``bitbucket.reviewer_aliases``), e.g. ``devbot``
* an account nickname or display name, looked up among the repo's default
  reviewers and then the workspace's members

Bitbucket replaces the whole reviewer list on every PUT, so changes are always
computed against the PR's current reviewers: existing ones are kept unless
removed by name, and the PR author is dropped (Bitbucket rejects the author as
a reviewer with a 400).
"""

import re
from typing import Any, Dict, Iterable, List, Optional, Tuple

from ..base.auth import load_config
from ..base.exceptions import TrinityError

_UUID_RE = re.compile(
    r"^\{?([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})\}?$"
)


def normalize_uuid(value: str) -> Optional[str]:
    """Return ``{uuid}`` in lower case if value is a UUID, else None."""
    m = _UUID_RE.match((value or "").strip())
    return "{" + m.group(1).lower() + "}" if m else None


def _bb_config(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    cfg = cfg if cfg is not None else load_config()
    return cfg.get("bitbucket") or {}


def reviewer_aliases(cfg: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
    """Configured aliases, keyed lower-case."""
    raw = _bb_config(cfg).get("reviewer_aliases") or {}
    return {str(k).strip().lower(): str(v).strip() for k, v in raw.items()}


def default_reviewers(cfg: Optional[Dict[str, Any]] = None) -> List[str]:
    return list(_bb_config(cfg).get("default_reviewers") or [])


def cto_reviewers(cfg: Optional[Dict[str, Any]] = None) -> List[str]:
    """Reviewers added by ``bb ready`` unless ``--simple`` is passed.

    The CTO tier: added on almost every PR (the approver of record), and
    skipped only for a trivial change via ``--simple``.
    """
    return list(_bb_config(cfg).get("cto_reviewers") or [])


def pm_reviewers(cfg: Optional[Dict[str, Any]] = None) -> List[str]:
    return list(_bb_config(cfg).get("pm_reviewers") or [])


def split_names(values: Iterable[str]) -> List[str]:
    """Flatten repeatable and comma-separated reviewer arguments."""
    names: List[str] = []
    for value in values or []:
        for part in str(value).split(","):
            part = part.strip()
            if part:
                names.append(part)
    return names


def _uuid_of(user: Dict[str, Any]) -> Optional[str]:
    return normalize_uuid(user.get("uuid") or "")


def _candidate_users(api, workspace: str, repo: str) -> List[Dict[str, Any]]:
    """Users we can match a nickname against.

    The repo's effective default reviewers come first: that endpoint lives
    under /repositories/{ws}/{repo}/ and so works with a per-repo access token.
    Workspace members need a workspace-wide login and are tried second.
    """
    users: List[Dict[str, Any]] = []
    try:
        for entry in api.get_all_pages(
            f"/repositories/{workspace}/{repo}/effective-default-reviewers"
        ):
            if entry.get("user"):
                users.append(entry["user"])
    except Exception:
        pass
    try:
        for entry in api.get_all_pages(f"/workspaces/{workspace}/members"):
            if entry.get("user"):
                users.append(entry["user"])
    except Exception:
        pass
    return users


class ReviewerResolver:
    """Turns reviewer names into ``{"uuid": ...}`` objects, caching lookups."""

    def __init__(self, api, workspace: str, repo: str, cfg: Optional[Dict[str, Any]] = None):
        self.api = api
        self.workspace = workspace
        self.repo = repo
        self.aliases = reviewer_aliases(cfg)
        self._users: Optional[List[Dict[str, Any]]] = None

    def resolve(self, name: str) -> str:
        """Return the reviewer's ``{uuid}``. Raises TrinityError if unknown."""
        original = name
        name = name.strip()
        seen = set()
        while name.lower() in self.aliases and name.lower() not in seen:
            seen.add(name.lower())
            name = self.aliases[name.lower()]

        uuid = normalize_uuid(name)
        if uuid:
            return uuid

        if self._users is None:
            self._users = _candidate_users(self.api, self.workspace, self.repo)
        wanted = name.lower()
        for user in self._users:
            for field in ("nickname", "username", "display_name"):
                if (user.get(field) or "").lower() == wanted and _uuid_of(user):
                    return _uuid_of(user)

        raise TrinityError(
            f"Unknown reviewer {original!r}. Use the account UUID ({{...}}), or add an "
            f"alias: trinity config --bb-reviewer-alias {original}={{UUID}}"
            + (f". Aliases: {', '.join(sorted(self.aliases))}" if self.aliases else "")
        )

    def resolve_all(self, names: Iterable[str]) -> List[str]:
        out: List[str] = []
        for n in names:
            u = self.resolve(n)
            if u not in out:
                out.append(u)
        return out


def merge_reviewers(
    existing: List[Dict[str, Any]],
    add: Iterable[str] = (),
    remove: Iterable[str] = (),
    author_uuid: Optional[str] = None,
) -> Tuple[List[Dict[str, str]], Dict[str, List[str]]]:
    """Combine a PR's current reviewers with additions and removals.

    Returns the full reviewer list to PUT and a summary of what changed:
    ``{"added": [...], "removed": [...], "skipped_author": [...]}``.
    """
    author = normalize_uuid(author_uuid or "")
    remove_set = {normalize_uuid(r) for r in remove if normalize_uuid(r)}
    summary: Dict[str, List[str]] = {"added": [], "removed": [], "skipped_author": []}

    current: List[str] = []
    for user in existing or []:
        u = _uuid_of(user)
        if not u or u in current:
            continue
        if u in remove_set:
            summary["removed"].append(u)
            continue
        current.append(u)

    for u in add:
        u = normalize_uuid(u)
        if not u or u in remove_set:
            continue
        if author and u == author:
            if u not in summary["skipped_author"]:
                summary["skipped_author"].append(u)
            continue
        if u not in current:
            current.append(u)
            summary["added"].append(u)

    return [{"uuid": u} for u in current], summary

