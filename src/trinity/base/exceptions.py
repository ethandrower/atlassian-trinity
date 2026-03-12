"""Unified exception hierarchy for Trinity."""


class TrinityError(Exception):
    """Base exception for all Trinity errors."""
    pass


class AtlassianAPIError(TrinityError):
    """General API error from any Atlassian service."""
    pass


class AuthenticationError(TrinityError):
    """Authentication failed or credentials missing/invalid."""
    pass


class PermissionError(TrinityError):
    """Insufficient permissions for the requested operation."""
    pass


class NotFoundError(TrinityError):
    """Requested resource not found (404)."""
    pass


class ConflictError(TrinityError):
    """Operation conflicts with current state (e.g., PR already merged)."""
    pass


class RateLimitError(TrinityError):
    """API rate limit exceeded (429)."""
    pass


class ConfigurationError(TrinityError):
    """Configuration file error or invalid/missing settings."""
    pass


class ValidationError(TrinityError):
    """Input validation error."""
    pass


class GitError(TrinityError):
    """Git repository or operation error."""
    pass
