"""Custom exceptions for Vectriva."""

from typing import Any


class VectrivaError(Exception):
    """Base exception for all Vectriva errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class CalendarNotConnectedError(VectrivaError):
    """Raised when calendar operation attempted without OAuth connection."""

    pass


class InvalidTimezoneError(VectrivaError):
    """Raised when timezone identifier is invalid."""

    pass


class DateOutOfRangeError(VectrivaError):
    """Raised when requested date is outside allowed range."""

    pass


class SlotNoLongerAvailableError(VectrivaError):
    """Raised when a time slot is no longer available."""

    pass


class CalendarAPIError(VectrivaError):
    """Raised when Google Calendar API returns an error."""

    pass


class InvalidEmailError(VectrivaError):
    """Raised when email validation fails."""

    pass


class EventNotFoundError(VectrivaError):
    """Raised when calendar event does not exist."""

    pass


class EventInPastError(VectrivaError):
    """Raised when attempting to modify a past event."""

    pass


class EmbeddingServiceError(VectrivaError):
    """Raised when embedding generation fails."""

    pass


class NoDocumentsIndexedError(VectrivaError):
    """Raised when no documents are available for retrieval."""

    pass


class AlreadyEscalatedError(VectrivaError):
    """Raised when attempting to escalate an already-escalated conversation."""

    pass


class AuthenticationError(VectrivaError):
    """Raised when authentication fails."""

    pass


class TenantNotFoundError(VectrivaError):
    """Raised when tenant does not exist."""

    pass


class UnauthorizedError(VectrivaError):
    """Raised when user lacks permission for operation."""

    pass


RETRYABLE_ERRORS = {
    CalendarAPIError,
    EmbeddingServiceError,
}
