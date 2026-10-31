"""Bounded filesystem adapter for immutable reports; no filesystem in the core."""

import json
import os
from pathlib import Path
import tempfile

from ro_sprite_forge.core.canonical import canonical_bytes
from ro_sprite_forge.core.errors import ErrorCode, ForgeError

MAX_INPUT_BYTES = 128 * 1024 * 1024


def read_bytes(path: str) -> bytes:
    try:
        with open(path, "rb") as stream:
            data = stream.read(MAX_INPUT_BYTES + 1)
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, "Cannot read input.", path=path) from exc
    if len(data) > MAX_INPUT_BYTES:
        raise ForgeError(ErrorCode.INVALID_INPUT, "Input exceeds 128 MiB limit.", path=path)
    return data


def read_json(path: str) -> dict:
    def unique(pairs):
        value = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = item
        return value

    try:
        value = json.loads(read_bytes(path), object_pairs_hook=unique,
                           parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        if not isinstance(value, dict):
            raise ValueError("expected an object")
        return value
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ForgeError(ErrorCode.INVALID_INPUT, "Invalid JSON object (duplicates/nonfinite values forbidden).", path=path) from exc


def publish(path: str, report: dict) -> None:
    """Publish a complete report atomically, refusing existing paths even in a race."""
    data = canonical_bytes(report)
    target = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=target.parent, prefix=".rsf-report-", delete=False) as stream:
            temporary = stream.name
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, target)
    except FileExistsError as exc:
        raise ForgeError(ErrorCode.INVALID_OUTPUT, "Output already exists; overwriting is forbidden.", path=path) from exc
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, "Cannot publish report.", path=path) from exc
    finally:
        if temporary is not None:
            os.unlink(temporary)


def publish_resources(resources: tuple[tuple[str, bytes], ...]) -> None:
    """Stage all bytes, then publish without replacement; roll back on exceptions.

    Each file appears atomically. Separate output paths are not a crash-atomic pair.
    No success report is emitted until both published files are read back.
    """
    staged = []
    published = []
    try:
        if len({str(Path(path).resolve()) for path, _ in resources}) != len(resources):
            raise ForgeError(ErrorCode.INVALID_OUTPUT, "Output paths must be distinct.")
        for path, data in resources:
            with tempfile.NamedTemporaryFile(dir=Path(path).parent, prefix=".rsf-resource-", delete=False) as stream:
                staged.append((stream.name, path, data))
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
        for temporary, path, data in staged:
            os.link(temporary, path)
            published.append((path, os.stat(temporary)))
        for _, path, data in staged:
            if read_bytes(path) != data:
                raise ForgeError(ErrorCode.IO_ERROR, "Published resource read-back differs.", path=path)
    except (OSError, ForgeError) as exc:
        for path, original in reversed(published):
            try:
                current = os.lstat(path)
                if (current.st_dev, current.st_ino) == (original.st_dev, original.st_ino):
                    os.unlink(path)
            except FileNotFoundError:
                pass
        if isinstance(exc, ForgeError):
            raise
        code = ErrorCode.INVALID_OUTPUT if isinstance(exc, FileExistsError) else ErrorCode.IO_ERROR
        raise ForgeError(code, "Cannot publish resource pair; incomplete outputs removed.") from exc
    finally:
        for temporary, _, _ in staged:
            os.unlink(temporary)
