"""Stable application errors, independent of their eventual CLI/HTTP rendering."""

from enum import StrEnum


class ErrorCode(StrEnum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    INPUT_NOT_FOUND = "INPUT_NOT_FOUND"
    INVALID_INPUT = "INVALID_INPUT"
    INVALID_OUTPUT = "INVALID_OUTPUT"
    IO_ERROR = "IO_ERROR"
    NOT_IMPLEMENTED = "NOT_IMPLEMENTED"
    CONFLICT = "CONFLICT"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"


class ForgeError(Exception):
    """Expected application failure with a stable category and optional path."""

    def __init__(self, code: ErrorCode, message: str, *, path: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
