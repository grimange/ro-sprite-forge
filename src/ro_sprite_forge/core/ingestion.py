"""Deterministic PNG sequence ingestion, technical validation, and immutable staging (RSF-19).

Provides:
- PNG technical validation: signature, dimensions, decode budget, corruption detection.
- Transparency analysis: OPAQUE, PARTIALLY_TRANSPARENT, FULLY_TRANSPARENT.
- Bounded decompression limits to protect against decompression bombs.
- Sequence validation: contiguous zero-based ordinals, duplicate/gap detection.
- Canonical sequence SHA-256 calculation based on ordered frame hashes.
- Immutable staging without automatic assignment, inferred choreography or auto-approval.
"""
from __future__ import annotations

import io
import re
from typing import Any

from ro_sprite_forge.core.canonical import canonical_bytes, check, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.project import MAX_BLOB_SIZE

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
MAX_DIMENSION = 4096
MAX_PIXELS = 16 * 1024 * 1024  # 16 megapixels
MAX_SEQUENCE_FRAMES = 1024
SEQUENCE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def analyze_transparency(im: Any) -> str:
    """Analyze image transparency across modes (RGBA, LA, P, RGB, L).

    Returns:
        'OPAQUE' | 'PARTIALLY_TRANSPARENT' | 'FULLY_TRANSPARENT'
    """
    mode = getattr(im, "mode", "")
    if mode in ("RGBA", "LA"):
        alpha = im.getchannel("A")
        min_a, max_a = alpha.getextrema()
        if min_a == 255:
            return "OPAQUE"
        if max_a == 0:
            return "FULLY_TRANSPARENT"
        return "PARTIALLY_TRANSPARENT"

    if mode == "P":
        # Palette mode with possible transparency chunk
        if "transparency" in im.info:
            try:
                rgba = im.convert("RGBA")
                alpha = rgba.getchannel("A")
                min_a, max_a = alpha.getextrema()
                if min_a == 255:
                    return "OPAQUE"
                if max_a == 0:
                    return "FULLY_TRANSPARENT"
                return "PARTIALLY_TRANSPARENT"
            except Exception:
                return "PARTIALLY_TRANSPARENT"
        return "OPAQUE"

    if mode in ("RGB", "L"):
        if "transparency" in im.info:
            try:
                rgba = im.convert("RGBA")
                alpha = rgba.getchannel("A")
                min_a, max_a = alpha.getextrema()
                if min_a == 255:
                    return "OPAQUE"
                if max_a == 0:
                    return "FULLY_TRANSPARENT"
                return "PARTIALLY_TRANSPARENT"
            except Exception:
                return "PARTIALLY_TRANSPARENT"
        return "OPAQUE"

    return "OPAQUE"


def validate_png(
    raw_bytes: bytes,
    filename: str | None = None,
    *,
    expected_sha256: str | None = None,
) -> dict[str, Any]:
    """Validate PNG binary integrity, dimensions, decode budget, and transparency."""
    if len(raw_bytes) > MAX_BLOB_SIZE:
        raise ForgeError(
            ErrorCode.PAYLOAD_TOO_LARGE,
            f"Payload size {len(raw_bytes)} bytes exceeds maximum allowed limit of {MAX_BLOB_SIZE} bytes.",
        )

    actual_hash = digest(raw_bytes)
    if expected_sha256 is not None:
        clean_expected = expected_sha256.lower().strip()
        if clean_expected != actual_hash:
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"SOURCE_HASH_MISMATCH: expected {clean_expected}, computed {actual_hash}.",
            )

    if len(raw_bytes) < 8 or raw_bytes[:8] != PNG_MAGIC:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            "INVALID_PNG_SIGNATURE: binary data does not start with standard PNG signature.",
        )

    try:
        from PIL import Image
        import PIL.ImageFile

        PIL.ImageFile.LOAD_TRUNCATED_IMAGES = False
        Image.MAX_IMAGE_PIXELS = MAX_PIXELS

        # Pass 1: verify stream structure
        bio1 = io.BytesIO(raw_bytes)
        with Image.open(bio1) as probe:
            if probe.format != "PNG":
                raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_PNG_FORMAT: expected PNG, got {probe.format}.")
            width, height = probe.size
            mode = probe.mode

            if width <= 0 or height <= 0:
                raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_DIMENSIONS: {width}x{height}")
            if width > MAX_DIMENSION or height > MAX_DIMENSION:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"DIMENSION_EXCEEDED: image dimensions {width}x{height} exceed {MAX_DIMENSION} limit.",
                )
            if width * height > MAX_PIXELS:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"DECODE_BUDGET_EXCEEDED: total pixels {width * height} exceed {MAX_PIXELS} budget.",
                )

            # verify internal chunk structures
            probe.verify()

        # Pass 2: transparency analysis
        bio2 = io.BytesIO(raw_bytes)
        with Image.open(bio2) as im:
            transparency_kind = analyze_transparency(im)

    except ForgeError:
        raise
    except Image.DecompressionBombError as exc:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"DECOMPRESSION_BOMB: image exceeds decompression budget limit ({exc}).",
        ) from exc
    except Exception as exc:
        raise ForgeError(ErrorCode.INVALID_INPUT, f"CORRUPTED_PNG_DATA: {exc}") from exc

    return {
        "sha256": actual_hash,
        "size": len(raw_bytes),
        "filename": filename or f"{actual_hash[:16]}.png",
        "width": width,
        "height": height,
        "mode": mode,
        "transparency_kind": transparency_kind,
        "has_transparency": (transparency_kind != "OPAQUE"),
    }


def validate_sequence(
    sequence_id: str,
    name: str,
    frames: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate frame ordering, ordinals, gaps, and compute canonical sequence hash."""
    if not isinstance(sequence_id, str) or not SEQUENCE_ID_PATTERN.match(sequence_id):
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"INVALID_SEQUENCE_ID: '{sequence_id}' must be 1-64 alphanumeric characters, underscores or hyphens.",
        )

    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            "INVALID_SEQUENCE_NAME: sequence name must be 1-128 characters.",
        )

    if not isinstance(frames, list) or len(frames) == 0:
        raise ForgeError(ErrorCode.INVALID_INPUT, "EMPTY_SEQUENCE: sequence must contain at least 1 frame.")

    if len(frames) > MAX_SEQUENCE_FRAMES:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"SEQUENCE_TOO_LARGE: maximum {MAX_SEQUENCE_FRAMES} frames allowed, got {len(frames)}.",
        )

    ordinals = []
    for idx, f in enumerate(frames):
        if not isinstance(f, dict):
            raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_FRAME_SPEC: frame {idx} must be an object.")
        ordinal = f.get("ordinal")
        if not isinstance(ordinal, int) or ordinal < 0:
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"INVALID_FRAME_ORDINAL: frame {idx} ordinal must be a nonnegative integer.",
            )
        sha256_hash = f.get("sha256")
        if not isinstance(sha256_hash, str) or not re.match(r"^[0-9a-f]{64}$", sha256_hash):
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"INVALID_FRAME_HASH: frame {idx} sha256 must be a 64-char hex string.",
            )
        filename = f.get("filename")
        if not isinstance(filename, str) or not filename:
            raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_FRAME_FILENAME: frame {idx} requires a valid filename.")
        ordinals.append(ordinal)

    # Check for duplicate ordinals
    if len(set(ordinals)) != len(ordinals):
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"DUPLICATE_FRAME_ORDINAL: sequence contains duplicate frame ordinals: {sorted(ordinals)}",
        )

    # Sort frames strictly by ordinal
    sorted_frames = sorted(frames, key=lambda f: f["ordinal"])

    # Check contiguous range from 0 to N-1
    expected_ordinals = list(range(len(sorted_frames)))
    actual_ordinals = [f["ordinal"] for f in sorted_frames]
    if actual_ordinals != expected_ordinals:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"FRAME_ORDINAL_GAP: frame ordinals must be contiguous from 0 to {len(sorted_frames) - 1}, got {actual_ordinals}.",
        )

    # Compute canonical sequence SHA-256 over ordered frame digests
    frame_hashes = [f["sha256"] for f in sorted_frames]
    sequence_sha256 = digest(canonical_bytes(frame_hashes))

    clean_frames = []
    for f in sorted_frames:
        item: dict[str, Any] = {
            "ordinal": f["ordinal"],
            "sha256": f["sha256"],
            "filename": f["filename"],
        }
        for key in ("width", "height", "mode", "transparency_kind", "has_transparency"):
            if key in f and f[key] is not None:
                item[key] = f[key]
        clean_frames.append(item)

    manifest_data = {
        "schema": "rsf.sequence/v1",
        "id": sequence_id,
        "name": name.strip(),
        "frame_count": len(sorted_frames),
        "sequence_sha256": sequence_sha256,
        "frames": clean_frames,
    }
    return sealed(manifest_data)
