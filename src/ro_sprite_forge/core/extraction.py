"""Deterministic PNG spritesheet extraction, rectangle validation, and immutable staging (RSF-20).

Provides:
- Exact integer rectangle validation: bounds checks, non-negative coordinates, non-zero dimensions.
- Grid-to-rectangle coordinate expansion with cell spacing, margins, and explicit ordering.
- Deterministic Pillow-based crop extraction preserving transparency and image mode.
- Explicit recipe identity, collection manifest, and source-to-candidate lineage.
- Atomic batch validation and staging without automatic assignment, pose guessing, or silent approval.
"""
from __future__ import annotations

import io
import re
from typing import Any

from PIL import Image

from ro_sprite_forge.core.canonical import canonical_bytes, check, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.ingestion import analyze_transparency, validate_png

RECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
EXTRACTION_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_EXTRACTION_ITEMS = 1024


def validate_rectangle_spec(
    rect: dict[str, Any],
    sheet_width: int,
    sheet_height: int,
    default_ordinal: int = 0,
) -> dict[str, Any]:
    """Validate a single rectangle specification against sheet bounds [x, y, x + width, y + height)."""
    if not isinstance(rect, dict):
        raise ForgeError(ErrorCode.INVALID_INPUT, "Rectangle specification must be an object.")

    rect_id = rect.get("id")
    if not isinstance(rect_id, str) or not RECT_ID_PATTERN.match(rect_id):
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"INVALID_RECTANGLE_ID: '{rect_id}' must be 1-64 alphanumeric characters, underscores or hyphens.",
        )

    for field in ("x", "y", "width", "height"):
        val = rect.get(field)
        if not isinstance(val, int) or isinstance(val, bool):
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"INVALID_RECTANGLE_COORDINATES: rectangle '{rect_id}' field '{field}' must be an integer, got {val}.",
            )

    x: int = rect["x"]
    y: int = rect["y"]
    width: int = rect["width"]
    height: int = rect["height"]

    if x < 0 or y < 0:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"INVALID_RECTANGLE_COORDINATES: rectangle '{rect_id}' coordinates must be non-negative ([x={x}, y={y}]).",
        )

    if width <= 0 or height <= 0:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"INVALID_RECTANGLE_DIMENSIONS: rectangle '{rect_id}' width and height must be positive ([w={width}, h={height}]).",
        )

    if x + width > sheet_width or y + height > sheet_height:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"RECTANGLE_OUT_OF_BOUNDS: rectangle '{rect_id}' [x={x}, y={y}, w={width}, h={height}] "
            f"exceeds spritesheet bounds [W={sheet_width}, H={sheet_height}].",
        )

    ordinal = rect.get("ordinal", default_ordinal)
    if not isinstance(ordinal, int) or isinstance(ordinal, bool) or ordinal < 0:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"INVALID_RECTANGLE_ORDINAL: rectangle '{rect_id}' ordinal must be a non-negative integer, got {ordinal}.",
        )

    return {
        "id": rect_id,
        "x": x,
        "y": y,
        "width": width,
        "height": height,
        "ordinal": ordinal,
    }


def expand_grid_spec(
    grid: dict[str, Any],
    sheet_width: int,
    sheet_height: int,
) -> list[dict[str, Any]]:
    """Expand a grid specification into an ordered list of explicit validated rectangles."""
    if not isinstance(grid, dict):
        raise ForgeError(ErrorCode.INVALID_INPUT, "Grid specification must be an object.")

    cols = grid.get("columns", grid.get("cols"))
    rows = grid.get("rows")
    cell_w = grid.get("cell_width")
    cell_h = grid.get("cell_height")

    for field, val in [("cell_width", cell_w), ("cell_height", cell_h), ("columns", cols), ("rows", rows)]:
        if not isinstance(val, int) or isinstance(val, bool) or val <= 0:
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"INVALID_GRID_PARAM: grid field '{field}' must be a positive integer, got {val}.",
            )
    offset_x: int = grid.get("offset_x", 0)
    offset_y: int = grid.get("offset_y", 0)
    spacing_x: int = grid.get("spacing_x", 0)
    spacing_y: int = grid.get("spacing_y", 0)

    for field, val in [("offset_x", offset_x), ("offset_y", offset_y), ("spacing_x", spacing_x), ("spacing_y", spacing_y)]:
        if not isinstance(val, int) or isinstance(val, bool) or val < 0:
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"INVALID_GRID_PARAM: grid field '{field}' must be a non-negative integer, got {val}.",
            )

    total_cells = cols * rows
    if total_cells > MAX_EXTRACTION_ITEMS:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"GRID_TOO_LARGE: total grid cells {total_cells} exceeds limit of {MAX_EXTRACTION_ITEMS}.",
        )

    # Check overall grid bounds
    max_x = offset_x + cols * cell_w + (cols - 1) * spacing_x
    max_y = offset_y + rows * cell_h + (rows - 1) * spacing_y
    if max_x > sheet_width or max_y > sheet_height:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"GRID_OUT_OF_BOUNDS: grid dimensions [{max_x}x{max_y}] exceed spritesheet bounds [{sheet_width}x{sheet_height}].",
        )

    selected = grid.get("selected_cells") if "selected_cells" in grid else grid.get("cells")
    prefix = grid.get("cell_id_prefix") or "cell"
    rectangles = []

    if selected is not None:
        if not isinstance(selected, list) or len(selected) == 0:
            raise ForgeError(ErrorCode.INVALID_INPUT, "EMPTY_GRID_SELECTION: selected_cells must contain at least 1 cell.")
        for idx, item in enumerate(selected):
            if not isinstance(item, dict):
                raise ForgeError(ErrorCode.INVALID_INPUT, f"INVALID_GRID_CELL: cell {idx} must be an object.")
            r = item.get("row")
            c = item.get("col")
            if not isinstance(r, int) or r < 0 or r >= rows or not isinstance(c, int) or c < 0 or c >= cols:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"GRID_CELL_INDEX_OUT_OF_BOUNDS: cell [row={r}, col={c}] outside grid rows={rows}, cols={cols}.",
                )
            cell_id = item.get("id") or f"{prefix}_r{r}_c{c}"
            ordinal = item.get("ordinal", idx)
            x = offset_x + c * (cell_w + spacing_x)
            y = offset_y + r * (cell_h + spacing_y)
            rectangles.append(
                validate_rectangle_spec(
                    {"id": cell_id, "x": x, "y": y, "width": cell_w, "height": cell_h, "ordinal": ordinal},
                    sheet_width,
                    sheet_height,
                )
            )
    else:
        # Default row-major enumeration
        idx = 0
        for r in range(rows):
            for c in range(cols):
                x = offset_x + c * (cell_w + spacing_x)
                y = offset_y + r * (cell_h + spacing_y)
                rectangles.append(
                    validate_rectangle_spec(
                        {"id": f"{prefix}_r{r}_c{c}", "x": x, "y": y, "width": cell_w, "height": cell_h, "ordinal": idx},
                        sheet_width,
                        sheet_height,
                    )
                )
                idx += 1

    return rectangles


def extract_rectangle_pixels(
    im: Image.Image,
    x: int,
    y: int,
    width: int,
    height: int,
) -> tuple[bytes, dict[str, Any]]:
    """Extract pixel subregion from decoded image and encode deterministically to PNG bytes."""
    cropped = im.crop((x, y, x + width, y + height))
    bio = io.BytesIO()
    cropped.save(bio, format="PNG", optimize=False)
    raw_bytes = bio.getvalue()

    actual_hash = digest(raw_bytes)
    transparency_kind = analyze_transparency(cropped)

    meta = {
        "sha256": actual_hash,
        "size": len(raw_bytes),
        "width": width,
        "height": height,
        "mode": cropped.mode,
        "transparency_kind": transparency_kind,
        "has_transparency": (transparency_kind != "OPAQUE"),
    }
    return raw_bytes, meta


def compute_recipe_sha256(sheet_sha256: str, rect: dict[str, Any]) -> str:
    """Compute canonical extraction recipe digest covering source hash and rectangle specification."""
    recipe = {
        "schema": "rsf.extraction-recipe/v1",
        "source_sha256": sheet_sha256,
        "rectangle": {
            "id": rect["id"],
            "x": rect["x"],
            "y": rect["y"],
            "width": rect["width"],
            "height": rect["height"],
            "ordinal": rect["ordinal"],
        },
        "semantics": "1.0.0",
    }
    return digest(canonical_bytes(recipe))


def extract_spritesheet(
    sheet_bytes: bytes,
    extraction_id: str,
    name: str,
    rectangles: list[dict[str, Any]],
    *,
    expected_sheet_sha256: str | None = None,
    sheet_filename: str | None = None,
) -> dict[str, Any]:
    """Validate sheet, validate all rectangles atomically, extract crops, and return extraction manifest."""
    if not isinstance(extraction_id, str) or not EXTRACTION_ID_PATTERN.match(extraction_id):
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"INVALID_EXTRACTION_ID: '{extraction_id}' must be 1-64 alphanumeric characters, underscores or hyphens.",
        )

    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            "INVALID_EXTRACTION_NAME: extraction name must be 1-128 characters.",
        )

    # 1. Validate source PNG bytes
    sheet_meta = validate_png(sheet_bytes, filename=sheet_filename, expected_sha256=expected_sheet_sha256)
    sheet_sha256 = sheet_meta["sha256"]
    sheet_w = sheet_meta["width"]
    sheet_h = sheet_meta["height"]

    if not isinstance(rectangles, list) or len(rectangles) == 0:
        raise ForgeError(ErrorCode.INVALID_INPUT, "EMPTY_EXTRACTION: at least 1 rectangle must be specified.")

    if len(rectangles) > MAX_EXTRACTION_ITEMS:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"EXTRACTION_TOO_LARGE: maximum {MAX_EXTRACTION_ITEMS} rectangles allowed, got {len(rectangles)}.",
        )

    # 2. Atomically validate all rectangle coordinates and bounds
    validated_rects: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    ordinals: list[int] = []

    for idx, r in enumerate(rectangles):
        spec = validate_rectangle_spec(r, sheet_w, sheet_h, default_ordinal=idx)
        rid = spec["id"]
        if rid in seen_ids:
            raise ForgeError(ErrorCode.INVALID_INPUT, f"DUPLICATE_RECTANGLE_ID: duplicate rectangle ID '{rid}'.")
        seen_ids.add(rid)
        ordinals.append(spec["ordinal"])
        validated_rects.append(spec)

    # 3. Validate ordinals (contiguous 0..N-1, no duplicates, no gaps)
    if len(set(ordinals)) != len(ordinals):
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"DUPLICATE_RECTANGLE_ORDINAL: duplicate extraction ordinals: {sorted(ordinals)}",
        )

    sorted_rects = sorted(validated_rects, key=lambda item: item["ordinal"])
    expected_ordinals = list(range(len(sorted_rects)))
    actual_ordinals = [item["ordinal"] for item in sorted_rects]
    if actual_ordinals != expected_ordinals:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"RECTANGLE_ORDINAL_GAP: extraction ordinals must be contiguous from 0 to {len(sorted_rects) - 1}, got {actual_ordinals}.",
        )

    # 4. Decode sheet once and extract all validated regions
    bio = io.BytesIO(sheet_bytes)
    with Image.open(bio) as im:
        extracted_items = []
        for rect in sorted_rects:
            raw_crop, meta = extract_rectangle_pixels(im, rect["x"], rect["y"], rect["width"], rect["height"])
            recipe_sha = compute_recipe_sha256(sheet_sha256, rect)
            crop_filename = f"{extraction_id}_{rect['ordinal']:03d}_{rect['id']}.png"

            item_record = {
                "ordinal": rect["ordinal"],
                "id": rect["id"],
                "x": rect["x"],
                "y": rect["y"],
                "width": rect["width"],
                "height": rect["height"],
                "extracted_sha256": meta["sha256"],
                "recipe_sha256": recipe_sha,
                "filename": crop_filename,
                "mode": meta["mode"],
                "transparency_kind": meta["transparency_kind"],
                "has_transparency": meta["has_transparency"],
                "_raw_bytes": raw_crop,  # internal for staging
            }
            extracted_items.append(item_record)

    # 5. Compute canonical collection hash
    collection_sha256 = digest(canonical_bytes([it["extracted_sha256"] for it in extracted_items]))

    clean_items = []
    for it in extracted_items:
        clean_copy = {k: v for k, v in it.items() if k != "_raw_bytes"}
        clean_items.append(clean_copy)

    manifest_data = {
        "schema": "rsf.spritesheet-extraction/v1",
        "id": extraction_id,
        "name": name.strip(),
        "source_sha256": sheet_sha256,
        "source_filename": sheet_filename or f"{sheet_sha256[:16]}.png",
        "item_count": len(clean_items),
        "collection_sha256": collection_sha256,
        "items": clean_items,
    }
    sealed_manifest = sealed(manifest_data)

    return {
        "manifest": sealed_manifest,
        "sheet_metadata": sheet_meta,
        "extracted_items": extracted_items,
    }
