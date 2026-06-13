from __future__ import annotations


class HttpIntegrationNeedsConfirmationError(RuntimeError):
    """Raised when an external HTTP integration call needs explicit user confirmation."""


class HttpIntegrationValidationError(RuntimeError):
    """Invalid integration configuration or invocation arguments."""
