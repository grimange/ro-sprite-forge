"""Versioned canonical JSON: UTF-8, sorted keys, compact separators, final LF.

Finite JSON numbers retain Python's shortest round-tripping float representation.
Hashes never include paths, wall-clock time, or their own digest field.
"""

import hashlib
import json

from ro_sprite_forge.core.errors import ErrorCode, ForgeError


def canonical_bytes(value: object) -> bytes:
    try:
        return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                           ensure_ascii=True, allow_nan=False) + "\n").encode("utf-8")
    except (TypeError, ValueError, RecursionError) as exc:
        raise ForgeError(ErrorCode.INVALID_INPUT, "Expected finite, bounded JSON data.") from exc


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sealed(value: dict) -> dict:
    return {**value, "canonical_sha256": digest(canonical_bytes(value))}


def check(condition: bool, message: str) -> None:
    if not condition:
        raise ForgeError(ErrorCode.INVALID_INPUT, message)


def check_seal(value: dict, schema: str) -> None:
    check(isinstance(value, dict) and value.get("schema") == schema, f"Expected {schema}.")
    payload = {key: item for key, item in value.items() if key != "canonical_sha256"}
    check(value.get("canonical_sha256") == digest(canonical_bytes(payload)), "Canonical digest mismatch.")
