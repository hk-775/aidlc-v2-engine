"""Explicit error types shared by the core, persistence layer, and CLI."""

from __future__ import annotations

from typing import Any


class AIDLCEngineError(Exception):
    """Base class with a stable machine-readable code and details."""

    code = "aidlc_v2_engine_error"
    exit_code = 1

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code or self.code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class ValidationError(AIDLCEngineError):
    code = "validation_error"
    exit_code = 2


class AuthorizationError(AIDLCEngineError):
    code = "authorization_error"
    exit_code = 3


class ForbiddenOperationError(AuthorizationError):
    code = "forbidden_operation"


class IntegrityError(AIDLCEngineError):
    code = "integrity_error"
    exit_code = 4


class NotFoundError(AIDLCEngineError):
    code = "not_found"
    exit_code = 5


class ConflictError(AIDLCEngineError):
    code = "conflict"
    exit_code = 6


class PersistenceError(AIDLCEngineError):
    code = "persistence_error"
    exit_code = 7
