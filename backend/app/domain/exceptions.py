"""
Domain and infrastructure exception classes for the Referral Agent.
Provides strongly-typed, catchable exceptions mapped to proper HTTP status codes.
"""

from typing import Any


class AppException(Exception):
    """Base exception for application domain errors."""

    def __init__(self, message: str, status_code: int = 500, detail: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.detail = detail or message


class ZohoValidationError(AppException):
    """
    Raised when Zoho Recruit accepts the HTTP transport (200/201/202)
    but reports a record-level validation or schema error in resp.json()['data'][0].
    Maps to HTTP 422 Unprocessable Entity.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        field_name: str | None = None,
    ) -> None:
        self.code = code
        self.details = details or {}
        # Extract offending field name if present in details
        self.field_name = field_name or self.details.get("api_name") or self.details.get("parent_api_name")
        expected_type = self.details.get("expected_data_type")

        if self.field_name and expected_type:
            detail_msg = f"Zoho rejected field '{self.field_name}': {message} (expected data type: {expected_type})"
        elif self.field_name:
            detail_msg = f"Zoho rejected field '{self.field_name}': {message}"
        else:
            detail_msg = f"Zoho validation error ({code}): {message}"

        super().__init__(message=detail_msg, status_code=422, detail=detail_msg)


class ZohoTransportError(AppException):
    """
    Raised on genuine transport-level failures (5xx, network timeouts, unreachable host)
    after retry exhaustion. Maps to HTTP 502/503.
    """

    def __init__(self, message: str, status_code: int = 502) -> None:
        super().__init__(message=message, status_code=status_code, detail=message)


class ZohoUsersUnavailableError(AppException):
    """
    Raised when Zoho Recruit Users API is unreachable, token has scope mismatch,
    or fails after retries. Maps to HTTP 503 Service Unavailable.
    """

    def __init__(
        self,
        message: str = "Zoho identity service is unavailable. Please verify Zoho credentials and scopes.",
    ) -> None:
        super().__init__(message=message, status_code=503, detail=message)

