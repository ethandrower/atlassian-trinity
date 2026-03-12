"""Shared base utilities for Trinity — auth, client, exceptions."""

from .auth import (
    get_jira_auth_headers,
    get_confluence_auth_headers,
    get_bitbucket_auth_headers,
    load_config,
    save_config,
    is_authenticated,
)
from .client import (
    JIRA_BASE_URL,
    AGILE_BASE_URL,
    CONFLUENCE_BASE_URL,
    BITBUCKET_BASE_URL,
    JIRA_WEB_URL,
    ATLASSIAN_CLOUD_ID,
    AtlassianClient,
    format_error,
    build_adf_comment,
)
from .exceptions import (
    TrinityError,
    AtlassianAPIError,
    AuthenticationError,
    NotFoundError,
    RateLimitError,
    ConflictError,
    ConfigurationError,
    ValidationError,
)

__all__ = [
    "get_jira_auth_headers",
    "get_confluence_auth_headers",
    "get_bitbucket_auth_headers",
    "load_config",
    "save_config",
    "is_authenticated",
    "JIRA_BASE_URL",
    "AGILE_BASE_URL",
    "CONFLUENCE_BASE_URL",
    "BITBUCKET_BASE_URL",
    "JIRA_WEB_URL",
    "ATLASSIAN_CLOUD_ID",
    "AtlassianClient",
    "format_error",
    "build_adf_comment",
    "TrinityError",
    "AtlassianAPIError",
    "AuthenticationError",
    "NotFoundError",
    "RateLimitError",
    "ConflictError",
    "ConfigurationError",
    "ValidationError",
]
