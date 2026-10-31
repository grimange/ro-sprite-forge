"""Audited SPR 2.1 / ACT 2.4 reference codec facade.

Preserves the API contract established in LWR tools/character_production/ro_reference.py
while incorporating bounded validation and typed diagnostics.
"""

from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.errors import AssetError, CodecError, require
from ro_sprite_forge.formats.preview import actor_preview, only_clip, place, png_bytes
from ro_sprite_forge.formats.reader import BinaryReader, Reader, sha
from ro_sprite_forge.formats.spr import IndexedImage, RgbaImage, SprDocument, read_spr, write_rgba_spr

__all__ = [
    "AssetError",
    "BinaryReader",
    "CodecError",
    "IndexedImage",
    "Reader",
    "RgbaImage",
    "SprDocument",
    "actor_preview",
    "only_clip",
    "place",
    "png_bytes",
    "read_act",
    "read_spr",
    "require",
    "sha",
    "write_act",
    "write_rgba_spr",
]
