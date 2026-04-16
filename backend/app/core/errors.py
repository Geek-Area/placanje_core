from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class ErrorPayload:
    code: str
    message: str
    details: dict[str, Any] | None = None


class AppError(Exception):
    status_code = 400
    code = "app_error"
    message = "Application error"

    def __init__(
        self, message: str | None = None, *, details: dict[str, Any] | None = None
    ) -> None:
        super().__init__(message or self.message)
        self.details = details
        self.message = message or self.message

    def to_payload(self) -> ErrorPayload:
        return ErrorPayload(code=self.code, message=self.message, details=self.details)


class ValidationFailed(AppError):
    status_code = 422
    code = "validation_failed"
    message = "The request payload is invalid."


class NotFound(AppError):
    status_code = 404
    code = "not_found"
    message = "The requested resource does not exist."


class Gone(AppError):
    status_code = 410
    code = "gone"
    message = "The requested resource is no longer available."


class Unauthorized(AppError):
    status_code = 401
    code = "unauthorized"
    message = "Authentication failed."


class Conflict(AppError):
    status_code = 409
    code = "conflict"
    message = "The request conflicts with the current resource state."


def _error_response(error: AppError) -> JSONResponse:
    payload = error.to_payload()
    body: dict[str, Any] = {"error": {"code": payload.code, "message": payload.message}}
    if payload.details is not None:
        body["error"]["details"] = payload.details
    return JSONResponse(status_code=error.status_code, content=body)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_response(exc)

    @app.exception_handler(Exception)
    async def handle_unexpected_error(_: Request, exc: Exception) -> JSONResponse:
        internal_error = AppError("Unexpected server error.", details={"type": type(exc).__name__})
        internal_error.status_code = 500
        internal_error.code = "internal_error"
        return _error_response(internal_error)
