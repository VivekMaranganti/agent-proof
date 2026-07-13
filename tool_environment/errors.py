"""Shared exceptions for deterministic support tools."""


class ToolEnvironmentError(Exception):
    """Base exception for deterministic tool failures."""


class NotFoundError(ToolEnvironmentError):
    """Raised when a requested synthetic entity does not exist."""


class PolicyViolationError(ToolEnvironmentError):
    """Raised when a requested action violates the current policy contract."""
