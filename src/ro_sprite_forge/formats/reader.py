"""Bounds-checked little-endian binary stream reader."""

import hashlib
import struct

from ro_sprite_forge.formats.errors import require


def sha(data: bytes) -> str:
    """Return lowercase hex SHA-256 digest of binary payload."""
    return hashlib.sha256(data).hexdigest()


class BinaryReader:
    """Stream reader with explicit bounds checking and typed diagnostics."""

    def __init__(self, data: bytes, *, path: str | None = None):
        self.data = data
        self.pos = 0
        self.path = path

    def read(self, fmt: str):
        size = struct.calcsize("<" + fmt)
        require(self.pos + size <= len(self.data), "truncated binary resource", path=self.path)
        values = struct.unpack_from("<" + fmt, self.data, self.pos)
        self.pos += size
        return values[0] if len(values) == 1 else list(values)

    def take(self, count: int) -> bytes:
        require(0 <= count <= len(self.data) - self.pos, "truncated binary payload", path=self.path)
        chunk = self.data[self.pos : self.pos + count]
        self.pos += count
        return chunk

    def peek(self, count: int) -> bytes:
        available = min(max(0, count), len(self.data) - self.pos)
        return self.data[self.pos : self.pos + available]

    @property
    def remaining(self) -> int:
        return len(self.data) - self.pos


# Audited alias
Reader = BinaryReader
