"""Minimal operation contract. No codec or inventory implementation in RSF-1."""

from dataclasses import dataclass
from enum import StrEnum

from ro_sprite_forge.core.errors import ErrorCode, ForgeError


class Operation(StrEnum):
    INSPECT = "inspect"
    PLAN = "plan"
    VERIFY = "verify"
    ROUNDTRIP = "roundtrip"


@dataclass(frozen=True)
class Request:
    """Transport-neutral named path inputs/outputs; values are never opened here."""

    operation: Operation
    inputs: tuple[tuple[str, str], ...]
    outputs: tuple[tuple[str, str], ...] = ()
    scope: str | None = None


def execute(request: Request) -> None:
    """Fail closed until the operation's bounded implementation task is delivered."""
    raise ForgeError(
        ErrorCode.NOT_IMPLEMENTED,
        f"{request.operation.value} is not implemented by this path-operation contract; "
        "no input contents were validated and no output was written.",
    )
