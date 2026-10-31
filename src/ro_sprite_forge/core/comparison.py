"""Deterministic frame reference comparison, side-by-side, onion skin and difference metrics."""
from __future__ import annotations

import copy
import json
from importlib.resources import files
from typing import Any, Mapping, Sequence, TYPE_CHECKING

if TYPE_CHECKING:
    from PIL import Image

def _image_mod():
    from PIL import Image, ImageDraw
    return Image, ImageDraw

from ro_sprite_forge.core.canonical import canonical_bytes, check, digest, sealed
from ro_sprite_forge.core.animation import AnimationInspector
from ro_sprite_forge.formats.preview import png_bytes, RENDERER_VERSION, GEOMETRY_VERSION
from ro_sprite_forge.core.timeline import TIMING_VERSION

COMPARISON_SCHEMA = "rsf.preview-comparison/v1"
COMPARISON_VERSION = "1.0.0"

SUPPORTED_OVERLAYS = ("origin", "bounds", "anchors", "layers")
SUPPORTED_MODES = ("REFERENCE_ONLY", "CANDIDATE_ONLY", "SIDE_BY_SIDE", "DIFFERENCE", "ONION_SKIN")
SUPPORTED_ALIGNMENTS = ("NONE", "ORIGIN", "BOUNDS_CENTER", "EXPLICIT")


def comparison_schema() -> dict[str, Any]:
    """Return parsed Draft 2020-12 preview comparison JSON Schema."""
    content = files("ro_sprite_forge").joinpath("schemas/preview-comparison-v1.json").read_text()
    return json.loads(content)


def apply_overlays(image: Any, inspection_report: Mapping[str, Any],
                   overlays: Sequence[str] | None = None) -> Any:
    """Apply visual diagnostic overlays to an image copy; underlying image is never mutated.

    Strict overlay isolation: when overlays is empty or None, returns image.copy()
    which preserves exact original PNG hash without diagnostic pixel contamination.
    """
    Image, ImageDraw = _image_mod()
    result = image.copy()
    if not overlays:
        return result

    draw = ImageDraw.Draw(result)
    overlay_set = set(overlays)

    for ov in overlay_set:
        check(ov in SUPPORTED_OVERLAYS, f"Unsupported overlay: {ov!r}. Supported: {SUPPORTED_OVERLAYS}")

    canvas = inspection_report.get("canvas", {})
    origin = canvas.get("origin", {"x": 128, "y": 192})
    ox, oy = origin["x"], origin["y"]

    if "bounds" in overlay_set:
        frame_bounds = inspection_report.get("frame_bounds", {})
        tb = frame_bounds.get("transformed")
        if tb is not None:
            tx0, ty0, tx1, ty1 = tb
            draw.rectangle([tx0, ty0, tx1 - 1, ty1 - 1], outline=(0, 180, 255, 200))
        vb = frame_bounds.get("visible")
        if vb is not None:
            vx0, vy0, vx1, vy1 = vb
            draw.rectangle([vx0, vy0, vx1 - 1, vy1 - 1], outline=(0, 255, 64, 220))

    if "layers" in overlay_set:
        for layer in inspection_report.get("layers", []):
            geom = layer.get("geometry", {})
            lvb = geom.get("visible_bounds")
            ord_num = layer.get("layer_ordinal", 0)
            if lvb is not None:
                lx0, ly0, lx1, ly1 = lvb
                draw.rectangle([lx0, ly0, lx1 - 1, ly1 - 1], outline=(160, 160, 160, 150))
                draw.text((lx0 + 2, ly0 + 2), str(ord_num), fill=(255, 255, 255, 220))

    if "anchors" in overlay_set:
        for frame_info in inspection_report.get("source_frames", []):
            for anchor in frame_info.get("anchors", []):
                if isinstance(anchor, dict):
                    ax, ay = anchor["x"], anchor["y"]
                elif isinstance(anchor, (list, tuple)):
                    ax, ay = anchor[0], anchor[1]
                else:
                    continue
                cx, cy = ox + ax, oy + ay
                draw.ellipse([cx - 3, cy - 3, cx + 3, cy + 3], outline=(255, 220, 0, 240))
                draw.point([cx, cy], fill=(255, 220, 0, 255))

    if "origin" in overlay_set:
        draw.line([(ox - 6, oy), (ox + 6, oy)], fill=(255, 32, 64, 240), width=1)
        draw.line([(ox, oy - 6), (ox, oy + 6)], fill=(255, 32, 64, 240), width=1)

    return result


def compute_difference(ref_image: Any, cand_image: Any, *,
                       displacement: tuple[int, int] = (0, 0)) -> dict[str, Any]:
    """Compute objective pixel, alpha, and channel metrics between two images on a unified canvas.

    Displacement (dx, dy) shifts cand_image relative to ref_image.
    Returns metrics dict and the difference PIL Image.
    """
    Image, _ = _image_mod()
    dx, dy = displacement
    rw, rh = ref_image.width, ref_image.height
    cw, ch = cand_image.width, cand_image.height

    ref_x = max(0, -dx)
    ref_y = max(0, -dy)
    cand_x = max(0, dx)
    cand_y = max(0, dy)
    canvas_w = max(rw + ref_x, cw + cand_x)
    canvas_h = max(rh + ref_y, ch + cand_y)

    canvas_ref = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    canvas_ref.paste(ref_image, (ref_x, ref_y))

    canvas_cand = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    canvas_cand.paste(cand_image, (cand_x, cand_y))

    b1 = canvas_ref.tobytes()
    b2 = canvas_cand.tobytes()
    total_pixels = canvas_w * canvas_h

    if b1 == b2:
        diff_img = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
        diff_bytes = png_bytes(diff_img)
        return {
            "metrics": {
                "dimensions_match": (rw == cw and rh == ch),
                "pixel_difference_count": 0,
                "alpha_difference_count": 0,
                "total_pixels_compared": total_pixels,
                "max_channel_difference": 0,
                "mean_absolute_difference": 0.0,
                "difference_png_sha256": digest(diff_bytes),
                "identical": (rw == cw and rh == ch and dx == 0 and dy == 0),
            },
            "difference_image": diff_img,
            "difference_png_bytes": diff_bytes,
        }

    diff_count = 0
    alpha_diff_count = 0
    max_ch_diff = 0
    sum_ch_diff = 0
    out_buf = bytearray(len(b1))

    for i in range(0, len(b1), 4):
        dr = abs(b1[i] - b2[i])
        dg = abs(b1[i + 1] - b2[i + 1])
        db = abs(b1[i + 2] - b2[i + 2])
        da = abs(b1[i + 3] - b2[i + 3])
        if dr or dg or db or da:
            diff_count += 1
            if da:
                alpha_diff_count += 1
            m = max(dr, dg, db, da)
            if m > max_ch_diff:
                max_ch_diff = m
            sum_ch_diff += dr + dg + db + da
            out_buf[i] = dr
            out_buf[i + 1] = dg
            out_buf[i + 2] = db
            out_buf[i + 3] = 255 if (dr or dg or db) else da

    diff_img = Image.frombytes("RGBA", (canvas_w, canvas_h), bytes(out_buf))
    diff_bytes = png_bytes(diff_img)
    mean_abs_diff = round(sum_ch_diff / (total_pixels * 4), 6) if total_pixels > 0 else 0.0

    return {
        "metrics": {
            "dimensions_match": (rw == cw and rh == ch),
            "pixel_difference_count": diff_count,
            "alpha_difference_count": alpha_diff_count,
            "total_pixels_compared": total_pixels,
            "max_channel_difference": max_ch_diff,
            "mean_absolute_difference": mean_abs_diff,
            "difference_png_sha256": digest(diff_bytes),
            "identical": (rw == cw and rh == ch and dx == 0 and dy == 0 and diff_count == 0),
        },
        "difference_image": diff_img,
        "difference_png_bytes": diff_bytes,
    }


def create_side_by_side(ref_image: Any, cand_image: Any, *,
                        labels: tuple[str, str] = ("REFERENCE", "CANDIDATE"),
                        padding: int = 8, margin: int = 8,
                        bg_color: tuple[int, int, int, int] = (20, 20, 24, 255)) -> Any:
    """Compose reference and candidate side-by-side with optional labels and padding."""
    Image, ImageDraw = _image_mod()
    rw, rh = ref_image.width, ref_image.height
    cw, ch = cand_image.width, cand_image.height
    label_h = 20 if labels else 0
    max_h = max(rh, ch)

    total_w = margin * 2 + rw + padding + cw
    total_h = margin * 2 + label_h + max_h

    canvas = Image.new("RGBA", (total_w, total_h), bg_color)
    ref_pos = (margin, margin + label_h)
    cand_pos = (margin + rw + padding, margin + label_h)

    canvas.paste(ref_image, ref_pos, ref_image)
    canvas.paste(cand_image, cand_pos, cand_image)

    draw = ImageDraw.Draw(canvas)
    if labels:
        draw.text((ref_pos[0] + 4, margin + 2), labels[0], fill=(220, 220, 220, 255))
        draw.text((cand_pos[0] + 4, margin + 2), labels[1], fill=(220, 220, 220, 255))

    div_x = margin + rw + padding // 2
    draw.line([(div_x, margin), (div_x, total_h - margin)], fill=(60, 60, 70, 255), width=1)
    return canvas


def blend_onion_skin(ref_image: Any, cand_image: Any, *,
                     opacity: float = 0.5,
                     displacement: tuple[int, int] = (0, 0)) -> Any:
    """Blend candidate over reference with specified opacity and displacement."""
    Image, _ = _image_mod()
    check(0.0 <= opacity <= 1.0, "Opacity must be in range [0.0, 1.0].")
    dx, dy = displacement
    rw, rh = ref_image.width, ref_image.height
    cw, ch = cand_image.width, cand_image.height

    ref_x = max(0, -dx)
    ref_y = max(0, -dy)
    cand_x = max(0, dx)
    cand_y = max(0, dy)
    canvas_w = max(rw + ref_x, cw + cand_x)
    canvas_h = max(rh + ref_y, ch + cand_y)

    canvas = Image.new("RGBA", (canvas_w, canvas_h), (0, 0, 0, 0))
    canvas.alpha_composite(ref_image, (ref_x, ref_y))

    c_faded = cand_image.copy()
    if opacity < 1.0:
        c_alpha = c_faded.getchannel("A").point(lambda a: int(a * opacity))
        c_faded.putalpha(c_alpha)

    canvas.alpha_composite(c_faded, (cand_x, cand_y))
    return canvas


def compare_frames(
    ref_inspector: AnimationInspector,
    cand_inspector: AnimationInspector | None,
    ref_selection: Mapping[str, Any],
    cand_selection: Mapping[str, Any] | None = None,
    *,
    mode: str = "SIDE_BY_SIDE",
    alignment: str = "NONE",
    displacement: tuple[int, int] = (0, 0),
    overlays: Sequence[str] | None = None,
    canvas_size: tuple[int, int] = (256, 256),
    origin: tuple[int, int] = (128, 192),
    auto_fit: bool = False,
    actor: str | None = None,
    candidate_actor: str | None = None,
) -> dict[str, Any]:
    """Execute frame reference comparison, metrics computation and diagnostic rendering.

    Adheres strictly to rsf.preview-comparison/v1 schema and overlay isolation.
    """
    check(mode in SUPPORTED_MODES, f"Unsupported mode: {mode!r}. Supported: {SUPPORTED_MODES}")
    check(alignment in SUPPORTED_ALIGNMENTS, f"Unsupported alignment: {alignment!r}. Supported: {SUPPORTED_ALIGNMENTS}")
    check(isinstance(displacement, (tuple, list)) and len(displacement) == 2 and
          all(type(n) is int for n in displacement), "Displacement must be a pair of integers (dx, dy).")

    # Render reference frame
    ref_result = ref_inspector.inspect(ref_selection, canvas_size=canvas_size, origin=origin, auto_fit=auto_fit)
    ref_report = ref_result["report"]
    ref_img_raw = ref_result["image"]
    ref_png_raw_bytes = ref_result["png_bytes"]
    ref_img_rendered = apply_overlays(ref_img_raw, ref_report, overlays=overlays)

    ref_bounds = ref_report["frame_bounds"]["visible"]
    ref_origin = ref_report["canvas"]["origin"]
    ref_dims = ref_report["canvas"]["dimensions"]

    ref_spec = {
        "sources": dict(ref_inspector._hashes),
        "actor": actor,
        "category": ref_inspector._category,
        "action": ref_report["selection"]["action"],
        "slot": ref_report["selection"]["resolved_slot"],
        "view": ref_report["selection"]["view"],
        "frame": ref_report["selection"]["frame"],
        "dimensions": {"width": ref_dims["width"], "height": ref_dims["height"]},
        "origin": {"x": ref_origin["x"], "y": ref_origin["y"]},
        "bounds": ref_bounds,
        "layer_count": len(ref_report["layers"]),
        "png_sha256": ref_report["preview_png_sha256"],
    }

    limitations = [
        "CPU Pillow ordered alpha composition; GPU WBOIT, native action-wide billboard bounds and cross-GPU pixel parity are not verified.",
        "Diagnostic preview comparison; technical difference only, no aesthetic or artistic approval.",
    ]
    diagnostics: list[str] = []

    # Handle missing candidate
    if cand_inspector is None or cand_selection is None:
        effective_mode = "REFERENCE_ONLY"
        composite_img = ref_img_rendered
        composite_bytes = png_bytes(composite_img)

        metrics = {
            "dimensions_match": False,
            "bounds_match": False,
            "origin_displacement": [0, 0],
            "anchor_displacement": None,
            "layer_count_match": False,
            "pixel_difference_count": 0,
            "alpha_difference_count": 0,
            "total_pixels_compared": 0,
            "max_channel_difference": 0,
            "mean_absolute_difference": 0.0,
            "difference_png_sha256": None,
            "identical": False,
        }

        alignment_record = {
            "policy": alignment,
            "displacement": {"x": 0, "y": 0},
        }

        comparison_dict = {
            "schema": COMPARISON_SCHEMA,
            "semantics": {
                "renderer": RENDERER_VERSION,
                "geometry": GEOMETRY_VERSION,
                "timing": TIMING_VERSION,
                "comparison": COMPARISON_VERSION,
            },
            "mode": effective_mode,
            "alignment": alignment_record,
            "reference": ref_spec,
            "candidate": None,
            "metrics": metrics,
            "overlays": list(overlays) if overlays else [],
            "comparison_status": "MISSING_CANDIDATE",
            "technical_difference_only": True,
            "artistic_approval": "UNVERIFIED",
            "fidelity": {
                "overall": "PARTIAL",
                "geometry": "VERIFIED",
                "native_pixel_parity": "UNVERIFIED",
                "limitations": limitations,
            },
            "output_png_sha256": digest(composite_bytes),
            "diagnostics": ["MISSING_CANDIDATE: reference-only presentation; candidate not provided."],
        }

        sealed_report = sealed(comparison_dict)
        return {
            "report": sealed_report,
            "image": composite_img,
            "png_bytes": composite_bytes,
            "difference_image": None,
            "difference_png_bytes": None,
            "ref_image": ref_img_rendered,
            "ref_png_bytes": png_bytes(ref_img_rendered),
            "cand_image": None,
            "cand_png_bytes": None,
        }

    # Render candidate frame
    cand_result = cand_inspector.inspect(cand_selection, canvas_size=canvas_size, origin=origin, auto_fit=auto_fit)
    cand_report = cand_result["report"]
    cand_img_raw = cand_result["image"]
    cand_png_raw_bytes = cand_result["png_bytes"]
    cand_img_rendered = apply_overlays(cand_img_raw, cand_report, overlays=overlays)

    cand_bounds = cand_report["frame_bounds"]["visible"]
    cand_origin = cand_report["canvas"]["origin"]
    cand_dims = cand_report["canvas"]["dimensions"]

    cand_spec = {
        "sources": dict(cand_inspector._hashes),
        "actor": candidate_actor,
        "category": cand_inspector._category,
        "action": cand_report["selection"]["action"],
        "slot": cand_report["selection"]["resolved_slot"],
        "view": cand_report["selection"]["view"],
        "frame": cand_report["selection"]["frame"],
        "dimensions": {"width": cand_dims["width"], "height": cand_dims["height"]},
        "origin": {"x": cand_origin["x"], "y": cand_origin["y"]},
        "bounds": cand_bounds,
        "layer_count": len(cand_report["layers"]),
        "png_sha256": cand_report["preview_png_sha256"],
    }

    # Calculate alignment displacement
    calc_dx, calc_dy = displacement
    if alignment == "ORIGIN":
        calc_dx = ref_origin["x"] - cand_origin["x"]
        calc_dy = ref_origin["y"] - cand_origin["y"]
    elif alignment == "BOUNDS_CENTER":
        if ref_bounds is not None and cand_bounds is not None:
            ref_cx = (ref_bounds[0] + ref_bounds[2]) // 2
            ref_cy = (ref_bounds[1] + ref_bounds[3]) // 2
            cand_cx = (cand_bounds[0] + cand_bounds[2]) // 2
            cand_cy = (cand_bounds[1] + cand_bounds[3]) // 2
            calc_dx = ref_cx - cand_cx
            calc_dy = ref_cy - cand_cy
        else:
            calc_dx, calc_dy = 0, 0
            diagnostics.append("BOUNDS_CENTER alignment fell back to (0, 0) due to null visible bounds.")
    elif alignment == "NONE":
        calc_dx, calc_dy = 0, 0

    actual_disp = (calc_dx, calc_dy)

    # Calculate anchor displacement if present
    ref_anchors = [a for f in ref_report.get("source_frames", []) for a in f.get("anchors", [])]
    cand_anchors = [a for f in cand_report.get("source_frames", []) for a in f.get("anchors", [])]
    if ref_anchors and cand_anchors:
        def _anchor_coords(a):
            if isinstance(a, dict):
                return a["x"], a["y"]
            return a[0], a[1]
        rax, ray = _anchor_coords(ref_anchors[0])
        cax, cay = _anchor_coords(cand_anchors[0])
        anchor_disp = [cax - rax, cay - ray]
    else:
        anchor_disp = None

    # Compute difference metrics using rendered or raw images?
    # Difference metrics should evaluate the rendered frames without overlays to keep technical difference pristine
    diff_res = compute_difference(ref_img_raw, cand_img_raw, displacement=actual_disp)
    metrics_res = diff_res["metrics"]
    diff_img = diff_res["difference_image"]
    diff_png_bytes = diff_res["difference_png_bytes"]

    metrics = {
        "dimensions_match": metrics_res["dimensions_match"],
        "bounds_match": (ref_bounds == cand_bounds),
        "origin_displacement": [cand_origin["x"] - ref_origin["x"], cand_origin["y"] - ref_origin["y"]],
        "anchor_displacement": anchor_disp,
        "layer_count_match": (len(ref_report["layers"]) == len(cand_report["layers"])),
        "pixel_difference_count": metrics_res["pixel_difference_count"],
        "alpha_difference_count": metrics_res["alpha_difference_count"],
        "total_pixels_compared": metrics_res["total_pixels_compared"],
        "max_channel_difference": metrics_res["max_channel_difference"],
        "mean_absolute_difference": metrics_res["mean_absolute_difference"],
        "difference_png_sha256": metrics_res["difference_png_sha256"],
        "identical": metrics_res["identical"],
    }

    comparison_status = "MATCH" if metrics["identical"] else "DIFFERENCE_OBSERVED"

    # Select composite output image based on mode
    if mode == "SIDE_BY_SIDE":
        composite_img = create_side_by_side(ref_img_rendered, cand_img_rendered)
    elif mode == "DIFFERENCE":
        composite_img = diff_img
    elif mode == "ONION_SKIN":
        composite_img = blend_onion_skin(ref_img_rendered, cand_img_rendered, displacement=actual_disp)
    elif mode == "CANDIDATE_ONLY":
        composite_img = cand_img_rendered
    else:  # REFERENCE_ONLY
        composite_img = ref_img_rendered

    composite_bytes = png_bytes(composite_img)

    alignment_record = {
        "policy": alignment,
        "displacement": {"x": actual_disp[0], "y": actual_disp[1]},
    }

    comparison_dict = {
        "schema": COMPARISON_SCHEMA,
        "semantics": {
            "renderer": RENDERER_VERSION,
            "geometry": GEOMETRY_VERSION,
            "timing": TIMING_VERSION,
            "comparison": COMPARISON_VERSION,
        },
        "mode": mode,
        "alignment": alignment_record,
        "reference": ref_spec,
        "candidate": cand_spec,
        "metrics": metrics,
        "overlays": list(overlays) if overlays else [],
        "comparison_status": comparison_status,
        "technical_difference_only": True,
        "artistic_approval": "UNVERIFIED",
        "fidelity": {
            "overall": "PARTIAL",
            "geometry": "VERIFIED",
            "native_pixel_parity": "UNVERIFIED",
            "limitations": limitations,
        },
        "output_png_sha256": digest(composite_bytes),
        "diagnostics": diagnostics,
    }

    sealed_report = sealed(comparison_dict)
    return {
        "report": sealed_report,
        "image": composite_img,
        "png_bytes": composite_bytes,
        "difference_image": diff_img,
        "difference_png_bytes": diff_png_bytes,
        "ref_image": ref_img_rendered,
        "ref_png_bytes": png_bytes(ref_img_rendered),
        "cand_image": cand_img_rendered,
        "cand_png_bytes": png_bytes(cand_img_rendered),
    }
