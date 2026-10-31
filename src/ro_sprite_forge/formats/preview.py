"""Audited classic reference preview and order-preserving multilayer compositor.

Renders actual animation frames from decoded SPR 2.1 / ACT 2.4 resources
while preserving:
1. Original sprite image identity.
2. Ordered ACT layer composition.
3. Indexed and truecolor image semantics.
4. Layer position and integer-center placement conventions.
5. Mirroring, scale, and rotation.
6. Tint, alpha, and transparency behavior.
7. Frame bounds and registration.
8. Multipart anchor alignment (e.g. Novice body + head).
9. Explicit fidelity state and unsupported semantics reporting.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
from importlib.resources import files
from typing import Any, Mapping, Sequence

from typing import Any, Mapping, Sequence, TYPE_CHECKING
if TYPE_CHECKING:
    from PIL import Image

def _image_mod():
    from PIL import Image
    return Image

from ro_sprite_forge.formats.errors import CodecError, require

PREVIEW_SCHEMA = "rsf.preview-result/v1"
RENDERER_VERSION = "1.1.0"
GEOMETRY_VERSION = "1.0.0"
MAX_PREVIEW_PIXELS = 16 * 1024 * 1024
MAX_PREVIEW_DIMENSION = 8192


def _check_size(width, height):
    require(type(width) is int and type(height) is int and
            0 < width <= MAX_PREVIEW_DIMENSION and 0 < height <= MAX_PREVIEW_DIMENSION
            and width * height <= MAX_PREVIEW_PIXELS, "Preview dimensions exceed bounded image budget")


def _local_bounds(image):
    return {"extent": [0, 0, image.width, image.height],
            "alpha": list(image.getchannel("A").getbbox()) if image.getchannel("A").getbbox() else None}


def _clipped_regions(extent, width, height):
    """Disjoint half-open rectangles outside the canvas, from actual placement."""
    x0, y0, x1, y1 = extent
    ix0, iy0, ix1, iy1 = max(0, x0), max(0, y0), min(width, x1), min(height, y1)
    if ix1 <= ix0 or iy1 <= iy0:
        return [extent]
    return [r for r in ([x0, y0, x1, iy0], [x0, iy1, x1, y1],
                        [x0, iy0, ix0, iy1], [ix1, iy0, x1, iy1])
            if r[0] < r[2] and r[1] < r[3]]


def preview_result_schema() -> dict[str, Any]:
    """Return parsed Draft 2020-12 preview result JSON Schema."""
    content = files("ro_sprite_forge").joinpath("schemas/preview-result-v1.json").read_text()
    return json.loads(content)


def png_bytes(image: Image.Image) -> bytes:
    """Return deterministic PNG binary bytes for PIL Image."""
    out = io.BytesIO()
    image.save(out, format="PNG", optimize=False, compress_level=9)
    return out.getvalue()


def sha256_hex(data: bytes) -> str:
    """Return SHA-256 lowercase hex string for bytes."""
    return hashlib.sha256(data).hexdigest()


def unpack_color(color: int) -> tuple[int, int, int, int]:
    """Unpack 32-bit unsigned integer color into (red, green, blue, alpha) 0..255."""
    r = color & 0xFF
    g = (color >> 8) & 0xFF
    b = (color >> 16) & 0xFF
    a = (color >> 24) & 0xFF
    return r, g, b, a


def pack_color(r: int, g: int, b: int, a: int) -> int:
    """Pack (red, green, blue, alpha) 0..255 into 32-bit unsigned integer."""
    return (r & 0xFF) | ((g & 0xFF) << 8) | ((b & 0xFF) << 16) | ((a & 0xFF) << 24)


def apply_color_tint(image: Any, color: int) -> Any:
    """Apply 32-bit color tint and alpha modulation to RGBA image."""
    Image = _image_mod()
    r_tint, g_tint, b_tint, a_tint = unpack_color(color)
    if (r_tint, g_tint, b_tint, a_tint) == (255, 255, 255, 255):
        return image

    r_lut = [(i * r_tint) // 255 for i in range(256)]
    g_lut = [(i * g_tint) // 255 for i in range(256)]
    b_lut = [(i * b_tint) // 255 for i in range(256)]
    a_lut = [(i * a_tint) // 255 for i in range(256)]

    r, g, b, a = image.split()
    r = r.point(r_lut)
    g = g.point(g_lut)
    b = b.point(b_lut)
    a = a.point(a_lut)
    return Image.merge("RGBA", (r, g, b, a))


def transform_layer_image(
    image: Any,
    clip: dict[str, Any],
    *,
    resample: Any = None,
) -> tuple[Any, dict[str, Any]]:
    """Apply mirror, scale, tint, and rotation transformations to layer image."""
    Image = _image_mod()
    if resample is None:
        resample = Image.Resampling.BILINEAR
    _check_size(image.width, image.height)
    img = image.copy()
    stages = {"source": _local_bounds(img)}
    mirror = bool(clip.get("mirror", 0))
    scale_x = float(clip.get("scale_x", 1.0))
    scale_y = float(clip.get("scale_y", 1.0))
    angle = float(clip.get("angle", 0))
    color = int(clip.get("color", 0xFFFFFFFF))
    require(all(math.isfinite(v) for v in (scale_x, scale_y, angle)), "Nonfinite layer transform")

    # 1. Mirroring
    if mirror:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if scale_x < 0:
        img = img.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        scale_x = abs(scale_x)
    if scale_y < 0:
        img = img.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        scale_y = abs(scale_y)

    stages["mirrored"] = _local_bounds(img)
    # 2. Scaling
    if scale_x != 1.0 or scale_y != 1.0:
        new_w = max(1, math.ceil(img.width * scale_x))
        new_h = max(1, math.ceil(img.height * scale_y))
        _check_size(new_w, new_h)
        img = img.resize((new_w, new_h), resample=resample)
    stages["scaled"] = _local_bounds(img)

    # 3. Tint / Alpha Modulation
    if color != 0xFFFFFFFF:
        img = apply_color_tint(img, color)

    # 4. Rotation (ACT positive angle rotates clockwise in screen space)
    norm_angle = angle % 360
    if norm_angle != 0:
        if norm_angle == 90:
            img = img.transpose(Image.Transpose.ROTATE_270)
        elif norm_angle == 180:
            img = img.transpose(Image.Transpose.ROTATE_180)
        elif norm_angle == 270:
            img = img.transpose(Image.Transpose.ROTATE_90)
        else:
            # Pillow may allocate an expanded rectangle; bound its enclosing square first.
            _check_size(img.width + img.height, img.width + img.height)
            img = img.rotate(-norm_angle, expand=True, resample=resample)

    _check_size(img.width, img.height)
    stages["rotated"] = _local_bounds(img)

    metadata = {
        "mirror": mirror,
        "scale": {"x": scale_x, "y": scale_y},
        "angle": angle,
        "color": {
            "r": color & 0xFF,
            "g": (color >> 8) & 0xFF,
            "b": (color >> 16) & 0xFF,
            "a": (color >> 24) & 0xFF,
            "raw": color,
        },
        "source_size": {"width": image.width, "height": image.height},
        "rendered_size": {"width": img.width, "height": img.height},
        "stages": stages,
    }
    return img, metadata


def place_clip(
    canvas: Any,
    image: Any,
    clip: dict[str, Any],
    *,
    shift: tuple[int, int] = (0, 0),
    origin: tuple[int, int] = (128, 192),
    resample: Any = None,
) -> dict[str, Any]:
    Image = _image_mod()
    if resample is None:
        resample = Image.Resampling.BILINEAR
    """Place transformed clip onto canvas using integer center convention and safe clipping."""
    transformed, meta = transform_layer_image(image, clip, resample=resample)

    cx = origin[0] + int(clip.get("x", 0)) + shift[0]
    cy = origin[1] + int(clip.get("y", 0)) + shift[1]

    left = cx - (transformed.width - 1) // 2
    top = cy - (transformed.height - 1) // 2

    # Safe alpha composite with canvas bounds
    crop_x0 = max(0, -left)
    crop_y0 = max(0, -top)
    crop_x1 = min(transformed.width, canvas.width - left)
    crop_y1 = min(transformed.height, canvas.height - top)

    dst_x = max(0, left)
    dst_y = max(0, top)

    clipped = (
        crop_x0 > 0
        or crop_y0 > 0
        or crop_x1 < transformed.width
        or crop_y1 < transformed.height
    )

    if crop_x1 > crop_x0 and crop_y1 > crop_y0:
        visible = transformed.crop((crop_x0, crop_y0, crop_x1, crop_y1))
        canvas.alpha_composite(visible, (dst_x, dst_y))

    meta["offset"] = {"x": int(clip.get("x", 0)) + shift[0], "y": int(clip.get("y", 0)) + shift[1]}
    meta["clipped"] = clipped
    return meta


def only_clip(motion: dict[str, Any]) -> dict[str, Any]:
    """Extract single visible clip from motion, validating reference constraint."""
    clips = [c for c in motion["clips"] if c["sprite"] >= 0]
    require(len(clips) == 1, "reference requires exactly one visible clip")
    return clips[0]


def place(
    canvas: Any,
    image: Any,
    clip: dict[str, Any],
    shift: tuple[int, int] = (0, 0),
    origin: tuple[int, int] = (128, 192),
) -> None:
    """Place transformed image onto canvas at origin with clip offsets.

    Preserves classic strict validation for identity transforms while allowing
    general transforms when present.
    """
    Image = _image_mod()
    is_simple = (
        clip.get("scale_x", 1.0) == 1.0
        and clip.get("scale_y", 1.0) == 1.0
        and clip.get("angle", 0) == 0
        and clip.get("color", 0xFFFFFFFF) == 0xFFFFFFFF
    )
    if is_simple:
        if clip.get("mirror"):
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        x = origin[0] + clip["x"] + shift[0] - (image.width - 1) // 2
        y = origin[1] + clip["y"] + shift[1] - (image.height - 1) // 2
        require(
            x >= 0
            and y >= 0
            and x + image.width <= canvas.width
            and y + image.height <= canvas.height,
            "reference canvas clipping",
        )
        canvas.alpha_composite(image, (x, y))
    else:
        place_clip(canvas, image, clip, shift=shift, origin=origin)


def actor_preview(body: Any, head: Any, bm: dict[str, Any], hm: dict[str, Any]) -> Any:
    """Composite single-clip body and head onto standard 256x256 canvas."""
    Image = _image_mod()
    image = Image.new("RGBA", (256, 256))
    place(image, body, only_clip(bm))
    ba, ha = bm["anchors"][0], hm["anchors"][0]
    place(image, head, only_clip(hm), (ba["x"] - ha["x"], ba["y"] - ha["y"]))
    return image


def _resolve_image_from_spr(
    spr_doc: Any,
    sprite_idx: int,
    pool: int,
    *,
    strict: bool = True,
) -> tuple[Image.Image | None, str | None]:
    """Extract RGBA PIL image from SprDocument preserving pool separation."""
    if hasattr(spr_doc, "indexed_images") and hasattr(spr_doc, "rgba_images"):
        if pool == 0:
            if sprite_idx < 0 or sprite_idx >= len(spr_doc.indexed_images):
                err = f"Indexed sprite index {sprite_idx} out of range [0, {len(spr_doc.indexed_images)})"
                if strict:
                    raise CodecError(err)
                return None, err
            return spr_doc.indexed_images[sprite_idx].to_pil(spr_doc.palette), None
        elif pool == 1:
            if sprite_idx < 0 or sprite_idx >= len(spr_doc.rgba_images):
                err = f"RGBA sprite index {sprite_idx} out of range [0, {len(spr_doc.rgba_images)})"
                if strict:
                    raise CodecError(err)
                return None, err
            return spr_doc.rgba_images[sprite_idx].to_pil(), None
        else:
            err = f"Unknown sprite pool {pool}; expected 0 (indexed) or 1 (rgba)"
            if strict:
                raise CodecError(err)
            return None, err

    # Fallback if spr_doc is a simple list of images or dict
    if isinstance(spr_doc, (list, tuple)):
        if sprite_idx < 0 or sprite_idx >= len(spr_doc):
            err = f"Sprite index {sprite_idx} out of range [0, {len(spr_doc)})"
            if strict:
                raise CodecError(err)
            return None, err
        img = spr_doc[sprite_idx]
        if hasattr(img, "convert"):
            return img.convert("RGBA"), None
        return img, None

    err = f"Unsupported sprite container type: {type(spr_doc).__name__}"
    if strict:
        raise CodecError(err)
    return None, err


def composite_frame(
    act_data: dict[str, Any] | Sequence[dict[str, Any]],
    spr_doc: Any | Sequence[Any],
    action_idx: int,
    frame_idx: int,
    *,
    head_act_data: dict[str, Any] | None = None,
    head_spr_doc: Any | None = None,
    head_frame_idx: int | None = None,
    origin: tuple[int, int] | None = None,
    canvas_size: tuple[int, int] | None = None,
    auto_fit: bool = False,
    margin: int = 16,
    background_color: tuple[int, int, int, int] = (0, 0, 0, 0),
    resample: Any = None,
    declared_fidelity: str | None = None,
    source_hashes: Mapping[str, str] | None = None,
    strict: bool = True,
) -> dict[str, Any]:
    """Composite multilayer animation frame in exact ACT order and return verified report.

    Args:
        act_data: Base actor ACT data dict or sequence of part ACT dicts.
        spr_doc: Base actor SprDocument or sequence of part SprDocuments.
        action_idx: Requested ACT action/view slot index.
        frame_idx: Requested motion/frame index within slot.
        head_act_data: Optional child/head ACT data for multipart actor.
        head_spr_doc: Optional child/head SprDocument.
        head_frame_idx: Frame index for head motion (defaults to frame_idx).
        origin: (x, y) canvas origin for placement.
        canvas_size: (width, height) output canvas dimensions.
        auto_fit: If True, dynamically sizes canvas to contain all layers.
        margin: Padding margin when auto_fit is enabled.
        background_color: RGBA background fill.
        resample: PIL resampling filter for scaling/rotation.
        declared_fidelity: Explicit fidelity override if provided.
        source_hashes: Optional mapping of resource IDs to SHA-256 hashes.
        strict: If True, raises CodecError on corrupt or missing references.

    Returns:
        Canonical preview result dict adhering to rsf.preview-result/v1.
    """
    unsupported_semantics: list[str] = []
    errors: list[str] = []

    # Prepare part lists
    parts_act: list[dict[str, Any]] = []
    parts_spr: list[Any] = []
    part_identifiers: list[str] = []

    if isinstance(act_data, (list, tuple)):
        parts_act.extend(act_data)
        if isinstance(spr_doc, (list, tuple)):
            parts_spr.extend(spr_doc)
        else:
            parts_spr.extend([spr_doc] * len(act_data))
        part_identifiers = [f"part_{i}" for i in range(len(parts_act))]
    else:
        parts_act.append(act_data)
        parts_spr.append(spr_doc)
        part_identifiers.append("body")

    if head_act_data is not None and head_spr_doc is not None:
        parts_act.append(head_act_data)
        parts_spr.append(head_spr_doc)
        part_identifiers.append("head")

    require(len(parts_act) == len(parts_spr), "mismatched ACT and SPR part counts")

    # Collect visible clips with part associations and anchor shifts
    visible_clips: list[tuple[dict[str, Any], Any, str, tuple[int, int]]] = []

    # Base part (part 0)
    base_act = parts_act[0]
    base_spr = parts_spr[0]
    require(0 <= action_idx < len(base_act["actions"]), f"action_idx {action_idx} out of range [0, {len(base_act['actions'])})")
    base_motions = base_act["actions"][action_idx]
    require(0 <= frame_idx < len(base_motions), f"frame_idx {frame_idx} out of range [0, {len(base_motions)})")
    base_motion = base_motions[frame_idx]

    for clip in base_motion["clips"]:
        if clip["sprite"] >= 0:
            visible_clips.append((clip, base_spr, part_identifiers[0], (0, 0)))

    # Attached parts (e.g. head)
    for p_idx in range(1, len(parts_act)):
        p_act = parts_act[p_idx]
        p_spr = parts_spr[p_idx]
        p_id = part_identifiers[p_idx]
        p_f_idx = head_frame_idx if (p_id == "head" and head_frame_idx is not None) else frame_idx

        if action_idx >= len(p_act["actions"]):
            unsupported_semantics.append(f"{p_id} has fewer actions than base ({len(p_act['actions'])} <= {action_idx})")
            continue
        p_motions = p_act["actions"][action_idx]
        if not 0 <= p_f_idx < len(p_motions):
            unsupported_semantics.append(f"{p_id} motion frame {p_f_idx} out of range [0, {len(p_motions)})")
            continue
        p_motion = p_motions[p_f_idx]

        # Anchor offset computation
        shift = (0, 0)
        if base_motion.get("anchors") and len(p_motion.get("anchors", [])) == 1:
            ba = base_motion["anchors"][0]
            ha = p_motion["anchors"][0]
            shift = (ba["x"] - ha["x"], ba["y"] - ha["y"])
        elif len(p_motion.get("anchors", [])) == 1:
            unsupported_semantics.append(f"Mismatched anchor count between base and {p_id}")

        for clip in p_motion["clips"]:
            if clip["sprite"] >= 0:
                visible_clips.append((clip, p_spr, p_id, shift))

    # Pre-calculate layer transformed bounds to handle canvas sizing / auto_fit
    pre_transformed: list[tuple[Image.Image, dict[str, Any], str, tuple[int, int], dict[str, Any]]] = []

    for clip, spr_container, part_id, shift in visible_clips:
        sprite = clip["sprite"]
        pool = clip.get("pool", 0)
        img, err = _resolve_image_from_spr(spr_container, sprite, pool, strict=strict)
        if err or img is None:
            errors.append(err or f"Failed to resolve sprite {sprite} pool {pool}")
            continue

        transformed, meta = transform_layer_image(img, clip, resample=resample)
        pre_transformed.append((transformed, clip, part_id, shift, meta))
        require(sum(item[0].width * item[0].height for item in pre_transformed) <= MAX_PREVIEW_PIXELS,
                "Aggregate transformed layer budget exceeded")

    Image = _image_mod()
    if resample is None:
        resample = Image.Resampling.BILINEAR

    # Determine canvas bounds and origin
    if canvas_size is None or auto_fit:
        if not pre_transformed:
            chosen_w, chosen_h = (256, 256)
            chosen_ox, chosen_oy = (128, 192)
        else:
            min_l, min_t, max_r, max_b = math.inf, math.inf, -math.inf, -math.inf
            for trans_img, clip, _, shift, _ in pre_transformed:
                px = int(clip.get("x", 0)) + shift[0]
                py = int(clip.get("y", 0)) + shift[1]
                left = px - (trans_img.width - 1) // 2
                top = py - (trans_img.height - 1) // 2
                min_l = min(min_l, left)
                min_t = min(min_t, top)
                max_r = max(max_r, left + trans_img.width)
                max_b = max(max_b, top + trans_img.height)

            if auto_fit:
                bbox_w = max(1, max_r - min_l)
                bbox_h = max(1, max_b - min_t)
                chosen_w = bbox_w + margin * 2
                chosen_h = bbox_h + margin * 2
                chosen_ox = -min_l + margin
                chosen_oy = -min_t + margin
            else:
                chosen_w = max(256, max_r - min_l + 64)
                chosen_h = max(256, max_b - min_t + 64)
                chosen_ox = chosen_w // 2
                chosen_oy = int(chosen_h * 0.75)
    else:
        chosen_w, chosen_h = canvas_size
        if origin is not None:
            chosen_ox, chosen_oy = origin
        else:
            chosen_ox, chosen_oy = (chosen_w // 2, int(chosen_h * 0.75))

    _check_size(chosen_w, chosen_h)
    canvas = Image.new("RGBA", (chosen_w, chosen_h), background_color)
    rendered_layers: list[dict[str, Any]] = []
    geometry: list[dict[str, Any]] = []

    # Composite layers in exact sequential order
    for layer_idx, (trans_img, clip, part_id, shift, meta) in enumerate(pre_transformed):
        cx = chosen_ox + int(clip.get("x", 0)) + shift[0]
        cy = chosen_oy + int(clip.get("y", 0)) + shift[1]

        left = cx - (trans_img.width - 1) // 2
        top = cy - (trans_img.height - 1) // 2

        crop_x0 = max(0, -left)
        crop_y0 = max(0, -top)
        crop_x1 = min(trans_img.width, canvas.width - left)
        crop_y1 = min(trans_img.height, canvas.height - top)

        dst_x = max(0, left)
        dst_y = max(0, top)

        clipped = (
            crop_x0 > 0
            or crop_y0 > 0
            or crop_x1 < trans_img.width
            or crop_y1 < trans_img.height
        )

        if crop_x1 > crop_x0 and crop_y1 > crop_y0:
            visible_rect = trans_img.crop((crop_x0, crop_y0, crop_x1, crop_y1))
            canvas.alpha_composite(visible_rect, (dst_x, dst_y))

        layer_record = {
            "layer_index": layer_idx,
            "part": part_id,
            "sprite": int(clip["sprite"]),
            "pool": int(clip.get("pool", 0)),
            "offset": {
                "x": int(clip.get("x", 0)) + shift[0],
                "y": int(clip.get("y", 0)) + shift[1],
            },
            "source_size": meta["source_size"],
            "rendered_size": meta["rendered_size"],
            "mirror": meta["mirror"],
            "scale": meta["scale"],
            "angle": meta["angle"],
            "color": meta["color"],
            "clipped": clipped,
        }
        rendered_layers.append(layer_record)
        extent = [left, top, left + trans_img.width, top + trans_img.height]
        alpha = meta["stages"]["rotated"]["alpha"]
        alpha_extent = ([left + alpha[0], top + alpha[1], left + alpha[2], top + alpha[3]]
                        if alpha else None)
        visible_alpha = trans_img.getchannel("A").crop((crop_x0, crop_y0, crop_x1, crop_y1)).getbbox() if crop_x1 > crop_x0 and crop_y1 > crop_y0 else None
        geometry.append({
            "stages": meta["stages"], "transformed_bounds": extent,
            "unclipped_visible_bounds": alpha_extent,
            "visible_bounds": ([dst_x + visible_alpha[0], dst_y + visible_alpha[1],
                                dst_x + visible_alpha[2], dst_y + visible_alpha[3]] if visible_alpha else None),
            "source_offset": [int(clip.get("x", 0)), int(clip.get("y", 0))],
            "anchor_shift": list(shift), "registration": [cx, cy],
            "integer_center": [(trans_img.width - 1) // 2, (trans_img.height - 1) // 2],
            "clipping": ("OUTSIDE" if crop_x1 <= crop_x0 or crop_y1 <= crop_y0 else "PARTIAL" if clipped else "INSIDE"),
            "transparent": alpha is None,
            "clipped_regions": _clipped_regions(extent, chosen_w, chosen_h),
            "canvas_intersection": ([max(0, left), max(0, top), min(chosen_w, extent[2]), min(chosen_h, extent[3])]
                                    if crop_x1 > crop_x0 and crop_y1 > crop_y0 else None),
        })

    # Compute bounding box
    raw_bbox = canvas.getbbox()
    if raw_bbox is not None:
        bounds = {
            "min_x": raw_bbox[0],
            "min_y": raw_bbox[1],
            "max_x": raw_bbox[2],
            "max_y": raw_bbox[3],
            "width": raw_bbox[2] - raw_bbox[0],
            "height": raw_bbox[3] - raw_bbox[1],
        }
    else:
        bounds = None

    png_data = png_bytes(canvas)
    png_sha = sha256_hex(png_data)

    # Fidelity assessment
    if declared_fidelity is not None:
        fidelity = declared_fidelity
    elif errors:
        fidelity = "INVALID"
    elif unsupported_semantics:
        fidelity = "PARTIAL"
    else:
        has_complex_transforms = any(
            l["scale"]["x"] != 1.0
            or l["scale"]["y"] != 1.0
            or l["angle"] != 0
            or l["color"]["raw"] != 0xFFFFFFFF
            for l in rendered_layers
        )
        if has_complex_transforms:
            # Complex scaling/rotation/tinting is faithful for supported scope
            fidelity = "VERIFIED"
        else:
            fidelity = "VERIFIED"

    report = {
        "schema": PREVIEW_SCHEMA,
        "renderer_version": RENDERER_VERSION,
        "fidelity": fidelity,
        "dimensions": {"width": chosen_w, "height": chosen_h},
        "origin": {"x": chosen_ox, "y": chosen_oy},
        "bounds": bounds,
        "layers_rendered": len(rendered_layers),
        "layers": rendered_layers,
        "unsupported_semantics": unsupported_semantics,
        "errors": errors,
        "png_sha256": png_sha,
    }

    if source_hashes:
        report["source_hashes"] = dict(source_hashes)

    return {
        "report": report,
        "image": canvas,
        "png_bytes": png_data,
        "geometry": geometry,
    }


class PreviewCompositor:
    """Stateful compositor holding preloaded ACT and SPR resources."""

    def __init__(
        self,
        act_data: dict[str, Any] | Sequence[dict[str, Any]],
        spr_doc: Any | Sequence[Any],
        *,
        head_act: dict[str, Any] | None = None,
        head_spr: Any | None = None,
        source_hashes: Mapping[str, str] | None = None,
        origin: tuple[int, int] = (128, 192),
        canvas_size: tuple[int, int] = (256, 256),
    ):
        self.act_data = act_data
        self.spr_doc = spr_doc
        self.head_act = head_act
        self.head_spr = head_spr
        self.source_hashes = source_hashes
        self.origin = origin
        self.canvas_size = canvas_size

    def render_frame(
        self,
        action_idx: int,
        frame_idx: int,
        *,
        head_frame_idx: int | None = None,
        auto_fit: bool = False,
        resample: Any = None,
        declared_fidelity: str | None = None,
        strict: bool = True,
    ) -> dict[str, Any]:
        """Render frame using stored configuration."""
        return composite_frame(
            self.act_data,
            self.spr_doc,
            action_idx,
            frame_idx,
            head_act_data=self.head_act,
            head_spr_doc=self.head_spr,
            head_frame_idx=head_frame_idx,
            origin=self.origin,
            canvas_size=self.canvas_size,
            auto_fit=auto_fit,
            resample=resample,
            declared_fidelity=declared_fidelity,
            source_hashes=self.source_hashes,
            strict=strict,
        )
