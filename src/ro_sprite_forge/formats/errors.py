"""Format-specific error types and assertion helpers."""

from ro_sprite_forge.core.errors import ErrorCode, ForgeError


class CodecError(ForgeError):
    """Raised when an ACT or SPR stream violates format specification or safety bounds."""

    def __init__(self, message: str, *, path: str | None = None):
        super().__init__(ErrorCode.INVALID_INPUT, message, path=path)


# Backward-compatible alias for audited ro_reference code
AssetError = CodecError


def require(condition: bool, message: str, *, path: str | None = None) -> None:
    """Validate a format invariant, raising CodecError on violation."""
    if not condition:
        raise CodecError(message, path=path)
