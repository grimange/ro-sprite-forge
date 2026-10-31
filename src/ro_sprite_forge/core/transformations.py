"""Reversible non-destructive image transformation engine (RSF-21).

Enforces:
1. Immutable source bytes preservation.
2. Operator-directed ordered transformation recipes (rsf.image-recipe/v1).
3. Discrete supported operations: crop, flip, scale, offset, matte_key, color_mode.
4. Independent 4-fold cryptographic identities: source_sha256, recipe_sha256,
   derived_sha256, and execution record.
5. Deterministic processing, nearest-neighbor pixel-art scaling, and explicit loss disclosure.
6. Zero AI synthesis, zero automatic guessing, and zero silent visual approval.
"""

from __future__ import annotations

import io
import math
import re
from typing import Any

from PIL import Image

from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.ingestion import (
    MAX_DIMENSION,
    MAX_PIXELS,
    analyze_transparency,
    validate_png,
)

RECIPE_SCHEMA = "rsf.image-recipe/v1"
RECORD_SCHEMA = "rsf.transformation-record/v1"
RECIPE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_RECIPE_OPERATIONS = 32
SUPPORTED_OPERATIONS = {"crop", "flip", "scale", "offset", "matte_key", "color_mode"}


def validate_operation(
    op: dict[str, Any],
    current_width: int | None = None,
    current_height: int | None = None,
) -> dict[str, Any]:
    """Validate a single operation object and its parameters."""
    if not isinstance(op, dict):
        raise ForgeError(ErrorCode.INVALID_INPUT, "Operation must be an object.")

    op_name = op.get("op")
    if not isinstance(op_name, str) or op_name not in SUPPORTED_OPERATIONS:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"UNSUPPORTED_OPERATION: operation '{op_name}' is not supported. Supported: {sorted(SUPPORTED_OPERATIONS)}.",
        )

    clean_op: dict[str, Any] = {"op": op_name}

    if op_name == "crop":
        for field in ("x", "y"):
            val = op.get(field)
            if not isinstance(val, int) or isinstance(val, bool) or val < 0:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"INVALID_CROP_PARAM: '{field}' must be a non-negative integer, got {val}.",
                )
            clean_op[field] = val

        for field in ("width", "height"):
            val = op.get(field)
            if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"INVALID_CROP_PARAM: '{field}' must be a positive integer, got {val}.",
                )
            clean_op[field] = val

        if current_width is not None and current_height is not None:
            if clean_op["x"] + clean_op["width"] > current_width:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"CROP_OUT_OF_BOUNDS: crop rectangle [x={clean_op['x']}, w={clean_op['width']}] exceeds image width {current_width}.",
                )
            if clean_op["y"] + clean_op["height"] > current_height:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"CROP_OUT_OF_BOUNDS: crop rectangle [y={clean_op['y']}, h={clean_op['height']}] exceeds image height {current_height}.",
                )

    elif op_name == "flip":
        direction = op.get("direction", "horizontal")
        if direction not in ("horizontal", "vertical", "both"):
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"INVALID_FLIP_PARAM: direction must be 'horizontal', 'vertical', or 'both', got '{direction}'.",
            )
        clean_op["direction"] = direction

    elif op_name == "scale":
        filter_name = op.get("filter", "nearest")
        if filter_name not in ("nearest", "bilinear", "bicubic"):
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"INVALID_SCALE_PARAM: filter must be 'nearest', 'bilinear', or 'bicubic', got '{filter_name}'.",
            )
        clean_op["filter"] = filter_name

        if "scale_x" in op or "scale_y" in op:
            sx = op.get("scale_x")
            sy = op.get("scale_y", sx)
            if not isinstance(sx, (int, float)) or not math.isfinite(sx) or sx <= 0:
                raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_SCALE_PARAM: 'scale_x' must be positive finite number, got {sx}.")
            if not isinstance(sy, (int, float)) or not math.isfinite(sy) or sy <= 0:
                raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_SCALE_PARAM: 'scale_y' must be positive finite number, got {sy}.")
            clean_op["scale_x"] = float(sx)
            clean_op["scale_y"] = float(sy)
        else:
            w = op.get("width")
            h = op.get("height")
            if not isinstance(w, int) or isinstance(w, bool) or w <= 0 or w > MAX_DIMENSION:
                raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_SCALE_PARAM: 'width' must be 1..{MAX_DIMENSION}, got {w}.")
            if not isinstance(h, int) or isinstance(h, bool) or h <= 0 or h > MAX_DIMENSION:
                raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_SCALE_PARAM: 'height' must be 1..{MAX_DIMENSION}, got {h}.")
            if w * h > MAX_PIXELS:
                raise ForgeError(ErrorCode.INVALID_INPUT, f"SCALE_BUDGET_EXCEEDED: {w}x{h} exceeds maximum pixel budget.")
            clean_op["width"] = w
            clean_op["height"] = h

    elif op_name == "offset":
        ox = op.get("offset_x", 0)
        oy = op.get("offset_y", 0)
        if not isinstance(ox, int) or isinstance(ox, bool):
            raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_OFFSET_PARAM: 'offset_x' must be integer, got {ox}.")
        if not isinstance(oy, int) or isinstance(oy, bool):
            raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_OFFSET_PARAM: 'offset_y' must be integer, got {oy}.")
        clean_op["offset_x"] = ox
        clean_op["offset_y"] = oy

        cw = op.get("canvas_width")
        ch = op.get("canvas_height")
        if cw is not None:
            if not isinstance(cw, int) or isinstance(cw, bool) or cw <= 0 or cw > MAX_DIMENSION:
                raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_OFFSET_PARAM: 'canvas_width' must be 1..{MAX_DIMENSION}, got {cw}.")
            clean_op["canvas_width"] = cw
        if ch is not None:
            if not isinstance(ch, int) or isinstance(ch, bool) or ch <= 0 or ch > MAX_DIMENSION:
                raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_OFFSET_PARAM: 'canvas_height' must be 1..{MAX_DIMENSION}, got {ch}.")
            clean_op["canvas_height"] = ch

        overflow = op.get("overflow", "clip")
        if overflow not in ("clip", "expand"):
            raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_OFFSET_PARAM: overflow must be 'clip' or 'expand', got '{overflow}'.")
        clean_op["overflow"] = overflow

    elif op_name == "matte_key":
        color = op.get("color")
        if not isinstance(color, (list, tuple)) or len(color) not in (3, 4):
            raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_MATTE_PARAM: color must be [r, g, b] or [r, g, b, a], got {color}.")
        for c in color:
            if not isinstance(c, int) or isinstance(c, bool) or not (0 <= c <= 255):
                raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_MATTE_PARAM: color channel must be 0..255, got {c}.")
        clean_op["color"] = list(color[:3])

        tol = op.get("tolerance", 0)
        if not isinstance(tol, int) or isinstance(tol, bool) or not (0 <= tol <= 255):
            raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_MATTE_PARAM: tolerance must be 0..255, got {tol}.")
        clean_op["tolerance"] = tol

        rep_a = op.get("replacement_alpha", 0)
        if not isinstance(rep_a, int) or isinstance(rep_a, bool) or not (0 <= rep_a <= 255):
            raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_MATTE_PARAM: replacement_alpha must be 0..255, got {rep_a}.")
        clean_op["replacement_alpha"] = rep_a

    elif op_name == "color_mode":
        target_mode = op.get("target_mode")
        if target_mode not in ("RGBA", "RGB", "P", "L", "LA"):
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"INVALID_COLOR_MODE_PARAM: target_mode must be 'RGBA', 'RGB', 'P', 'L', or 'LA', got '{target_mode}'.",
            )
        clean_op["target_mode"] = target_mode
        clean_op["dither"] = bool(op.get("dither", False))

    return clean_op


def validate_recipe(recipe: dict[str, Any]) -> dict[str, Any]:
    """Validate recipe schema, ID, source reference, and operation list."""
    if not isinstance(recipe, dict):
        raise ForgeError(ErrorCode.INVALID_INPUT, "Recipe must be an object.")

    rid = recipe.get("id")
    if not isinstance(rid, str) or not RECIPE_ID_PATTERN.match(rid):
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"INVALID_RECIPE_ID: recipe ID '{rid}' must be 1-64 alphanumeric characters, underscores or hyphens.",
        )

    name = recipe.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise ForgeError(ErrorCode.INVALID_INPUT, "INVALID_RECIPE_NAME: recipe name must be 1-128 characters.")

    source_sha = recipe.get("source_sha256")
    if not isinstance(source_sha, str) or len(source_sha) != 64 or not all(c in "0123456789abcdefABCDEF" for c in source_sha):
        raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_SOURCE_SHA256: '{source_sha}' is not a valid 64-hex SHA-256 digest.")
    source_sha = source_sha.lower()

    ops = recipe.get("operations")
    if not isinstance(ops, list) or len(ops) == 0:
        raise ForgeError(ErrorCode.INVALID_INPUT, "EMPTY_RECIPE: recipe must contain at least 1 operation.")
    if len(ops) > MAX_RECIPE_OPERATIONS:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"RECIPE_TOO_LONG: maximum {MAX_RECIPE_OPERATIONS} operations allowed, got {len(ops)}.",
        )

    validated_ops = [validate_operation(op) for op in ops]

    clean_recipe = {
        "schema": RECIPE_SCHEMA,
        "id": rid,
        "name": name.strip(),
        "source_sha256": source_sha,
        "source_filename": recipe.get("source_filename"),
        "operations": validated_ops,
        "semantics": "1.0.0",
    }
    return clean_recipe


def compute_recipe_sha256(clean_recipe: dict[str, Any]) -> str:
    """Compute canonical recipe hash covering source hash, ordered operations and semantics."""
    recipe_dict = {
        "schema": RECIPE_SCHEMA,
        "id": clean_recipe["id"],
        "name": clean_recipe["name"],
        "source_sha256": clean_recipe["source_sha256"],
        "source_filename": clean_recipe.get("source_filename"),
        "operations": clean_recipe["operations"],
        "semantics": "1.0.0",
    }
    return digest(canonical_bytes(recipe_dict))


def execute_operation(im: Image.Image, op: dict[str, Any], loss_report: list[str]) -> Image.Image:
    """Execute a single transformation operation on Pillow Image and append loss reports."""
    op_name = op["op"]

    if op_name == "crop":
        x, y, w, h = op["x"], op["y"], op["width"], op["height"]
        if x + w > im.width or y + h > im.height:
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"CROP_OUT_OF_BOUNDS: crop [{x}, {y}, {w}, {h}] exceeds current image size [{im.width}, {im.height}].",
            )
        if w < im.width or h < im.height:
            if "CROPPED_DISCARDED_PIXELS" not in loss_report:
                loss_report.append("CROPPED_DISCARDED_PIXELS")
        return im.crop((x, y, x + w, y + h))

    elif op_name == "flip":
        d = op["direction"]
        if d == "horizontal":
            return im.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        elif d == "vertical":
            return im.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        elif d == "both":
            return im.transpose(Image.Transpose.FLIP_LEFT_RIGHT).transpose(Image.Transpose.FLIP_TOP_BOTTOM)

    elif op_name == "scale":
        filter_name = op.get("filter", "nearest")
        filter_map = {
            "nearest": Image.Resampling.NEAREST,
            "bilinear": Image.Resampling.BILINEAR,
            "bicubic": Image.Resampling.BICUBIC,
        }
        resample = filter_map[filter_name]

        if "scale_x" in op:
            target_w = max(1, round(im.width * op["scale_x"]))
            target_h = max(1, round(im.height * op["scale_y"]))
        else:
            target_w = op["width"]
            target_h = op["height"]

        if target_w * target_h < im.width * im.height:
            if "DOWNSCALED_DISCARDED_PIXELS" not in loss_report:
                loss_report.append("DOWNSCALED_DISCARDED_PIXELS")
        if filter_name != "nearest":
            if "INTERPOLATED_RESAMPLING" not in loss_report:
                loss_report.append("INTERPOLATED_RESAMPLING")

        return im.resize((target_w, target_h), resample=resample)

    elif op_name == "offset":
        cw = op.get("canvas_width") or im.width
        ch = op.get("canvas_height") or im.height
        ox = op.get("offset_x", 0)
        oy = op.get("offset_y", 0)
        overflow = op.get("overflow", "clip")

        if overflow == "expand":
            min_x = min(0, ox)
            min_y = min(0, oy)
            max_x = max(cw, ox + im.width)
            max_y = max(ch, oy + im.height)
            final_w = max_x - min_x
            final_h = max_y - min_y
            paste_x = ox - min_x
            paste_y = oy - min_y
        else:
            final_w = cw
            final_h = ch
            paste_x = ox
            paste_y = oy
            if ox < 0 or oy < 0 or ox + im.width > cw or oy + im.height > ch:
                if "CANVAS_CLIPPED_PIXELS" not in loss_report:
                    loss_report.append("CANVAS_CLIPPED_PIXELS")

        # Create transparent canvas in RGBA mode
        canvas = Image.new("RGBA", (final_w, final_h), (0, 0, 0, 0))
        src_rgba = im.convert("RGBA") if im.mode != "RGBA" else im
        canvas.paste(src_rgba, (paste_x, paste_y), mask=src_rgba)
        return canvas

    elif op_name == "matte_key":
        im_rgba = im.convert("RGBA") if im.mode != "RGBA" else im.copy()
        kr, kg, kb = op["color"]
        tol = op.get("tolerance", 0)
        rep_a = op.get("replacement_alpha", 0)

        # Process pixels
        pixels = im_rgba.load()
        w, h = im_rgba.size
        modified = False
        for py in range(h):
            for px in range(w):
                r, g, b, a = pixels[px, py]
                if abs(r - kr) <= tol and abs(g - kg) <= tol and abs(b - kb) <= tol:
                    pixels[px, py] = (r, g, b, rep_a)
                    modified = True

        if modified and "ALPHA_CHANNEL_KEYED" not in loss_report:
            loss_report.append("ALPHA_CHANNEL_KEYED")
        return im_rgba

    elif op_name == "color_mode":
        target = op["target_mode"]
        if im.mode == "P" and target == "RGBA":
            if "PALETTE_INDICES_DISCARDED" not in loss_report:
                loss_report.append("PALETTE_INDICES_DISCARDED")
        if target == "RGB" and im.mode in ("RGBA", "LA"):
            if "ALPHA_CHANNEL_DISCARDED" not in loss_report:
                loss_report.append("ALPHA_CHANNEL_DISCARDED")
        if target == "P":
            if "COLOR_QUANTIZATION_LOSSY" not in loss_report:
                loss_report.append("COLOR_QUANTIZATION_LOSSY")

        dither = Image.Dither.FLOYDSTEINBERG if op.get("dither") else Image.Dither.NONE
        return im.convert(target, dither=dither)

    return im


def apply_transformation_recipe(
    source_bytes: bytes,
    recipe: dict[str, Any],
    *,
    expected_source_sha256: str | None = None,
) -> dict[str, Any]:
    """Execute recipe deterministically on source bytes and return derived output, hashes, and records."""
    # 1. Validate source PNG bytes
    source_meta = validate_png(source_bytes, expected_sha256=expected_source_sha256)
    actual_source_sha = source_meta["sha256"]

    # 2. Validate recipe structure and parameters
    clean_recipe = validate_recipe(recipe)
    if clean_recipe["source_sha256"] != actual_source_sha:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"SOURCE_HASH_MISMATCH: recipe source_sha256 '{clean_recipe['source_sha256']}' does not match actual sheet '{actual_source_sha}'.",
        )

    recipe_sha = compute_recipe_sha256(clean_recipe)
    sealed_recipe = sealed(dict(clean_recipe, canonical_sha256=recipe_sha))

    # 3. Load image into memory
    bio = io.BytesIO(source_bytes)
    with Image.open(bio) as im:
        current_im = im.copy()
        current_w, current_h = current_im.width, current_im.height
        input_mode = current_im.mode
        loss_report: list[str] = []

        # 4. Sequentially execute operations
        for op in clean_recipe["operations"]:
            # Validate operation against current intermediate dimensions
            validate_operation(op, current_im.width, current_im.height)
            current_im = execute_operation(current_im, op, loss_report)

        # 5. Deterministically encode output PNG
        out_bio = io.BytesIO()
        current_im.save(out_bio, format="PNG", optimize=False)
        output_bytes = out_bio.getvalue()

    derived_sha = digest(output_bytes)
    trans_kind = analyze_transparency(current_im)
    has_trans = trans_kind != "OPAQUE"

    execution_record = {
        "schema": RECORD_SCHEMA,
        "recipe_id": clean_recipe["id"],
        "recipe_sha256": recipe_sha,
        "source_sha256": actual_source_sha,
        "derived_sha256": derived_sha,
        "input_dimensions": [source_meta["width"], source_meta["height"]],
        "output_dimensions": [current_im.width, current_im.height],
        "input_mode": input_mode,
        "output_mode": current_im.mode,
        "transparency_kind": trans_kind,
        "has_transparency": has_trans,
        "loss_report": loss_report,
        "operations_count": len(clean_recipe["operations"]),
        "semantics": "1.0.0",
    }
    sealed_record = sealed(execution_record)

    return {
        "output_bytes": output_bytes,
        "derived_sha256": derived_sha,
        "recipe_sha256": recipe_sha,
        "recipe": sealed_recipe,
        "execution_record": sealed_record,
        "metadata": {
            "width": current_im.width,
            "height": current_im.height,
            "mode": current_im.mode,
            "transparency_kind": trans_kind,
            "has_transparency": has_trans,
            "loss_report": loss_report,
            "size": len(output_bytes),
        },
    }
