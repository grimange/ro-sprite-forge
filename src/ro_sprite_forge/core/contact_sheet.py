"""Deterministic contact sheet generation and atomic frame sequence exports."""
from __future__ import annotations

import json
from importlib.resources import files
import os
from pathlib import Path
import shutil
from typing import Any, Mapping, Sequence, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    from PIL import Image

def _image_mod():
    from PIL import Image, ImageDraw
    return Image, ImageDraw

from ro_sprite_forge.core.canonical import canonical_bytes, check, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.animation import AnimationInspector
from ro_sprite_forge.core.comparison import apply_overlays
from ro_sprite_forge.formats.preview import png_bytes, RENDERER_VERSION, GEOMETRY_VERSION
from ro_sprite_forge.core.timeline import TIMING_VERSION

CONTACT_SHEET_SCHEMA = "rsf.contact-sheet/v1"
SEQUENCE_MANIFEST_SCHEMA = "rsf.sequence-manifest/v1"
CONTACT_SHEET_VERSION = "1.0.0"
EXPORT_VERSION = "1.0.0"


def contact_sheet_schema() -> dict[str, Any]:
    """Return parsed Draft 2020-12 contact sheet JSON Schema."""
    content = files("ro_sprite_forge").joinpath("schemas/contact-sheet-v1.json").read_text()
    return json.loads(content)


def sequence_manifest_schema() -> dict[str, Any]:
    """Return parsed Draft 2020-12 sequence manifest JSON Schema."""
    content = files("ro_sprite_forge").joinpath("schemas/sequence-manifest-v1.json").read_text()
    return json.loads(content)


def generate_contact_sheet(
    inspector: AnimationInspector,
    selection: Mapping[str, Any],
    *,
    columns: int = 8,
    scale: int = 1,
    padding: int = 4,
    margin: int = 8,
    labels: bool = True,
    overlays: Sequence[str] | None = None,
    canvas_size: tuple[int, int] = (256, 256),
    origin: tuple[int, int] = (128, 192),
    auto_fit: bool = False,
) -> dict[str, Any]:
    """Generate deterministic contact sheet image and canonical report.

    Arranges animation frames into a structured grid with nearest-neighbor integer scaling.
    """
    check(type(columns) is int and columns >= 1, "columns must be an integer >= 1.")
    check(type(scale) is int and scale >= 1, "scale must be an integer >= 1.")
    check(type(padding) is int and padding >= 0, "padding must be an integer >= 0.")
    check(type(margin) is int and margin >= 0, "margin must be an integer >= 0.")

    Image, ImageDraw = _image_mod()
    slot = selection["resolved_slot"]
    view = selection["view"]
    cam_dir = selection["camera_direction"]
    frame_count = selection["frame_count"]
    check(frame_count >= 1, "Cannot generate contact sheet for zero frames.")

    total_tiles = frame_count
    cols = min(columns, total_tiles)
    rows = (total_tiles + cols - 1) // cols

    tiles_data = []
    tile_images = []

    for f in range(frame_count):
        sel_f = inspector.timeline.select(slot=slot, view=view, camera_direction=cam_dir, frame=f)
        res_f = inspector.inspect(sel_f, canvas_size=canvas_size, origin=origin, auto_fit=auto_fit)
        rep_f = res_f["report"]
        img_f = res_f["image"]
        img_f_overlay = apply_overlays(img_f, rep_f, overlays=overlays)

        if scale > 1:
            sw = img_f_overlay.width * scale
            sh = img_f_overlay.height * scale
            img_f_scaled = img_f_overlay.resize((sw, sh), resample=Image.Resampling.NEAREST)
        else:
            img_f_scaled = img_f_overlay

        tile_images.append(img_f_scaled)
        tiles_data.append({
            "tile_index": f,
            "frame": f,
            "source_delay": rep_f["selection"]["source_delay"],
            "duration_ms": rep_f["selection"]["frame_duration_ms"],
            "bounds": rep_f["frame_bounds"]["visible"],
            "png_sha256": rep_f["preview_png_sha256"],
            "labels": [f"F{f:02d}"],
        })

    tile_w = tile_images[0].width
    tile_h = tile_images[0].height
    label_h = 16 if labels else 0
    cell_w = tile_w
    cell_h = tile_h + label_h

    sheet_w = margin * 2 + cols * cell_w + (cols - 1) * padding
    sheet_h = margin * 2 + rows * cell_h + (rows - 1) * padding

    sheet_img = Image.new("RGBA", (sheet_w, sheet_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(sheet_img)

    for idx, t_img in enumerate(tile_images):
        col = idx % cols
        row = idx // cols
        x = margin + col * (cell_w + padding)
        y = margin + row * (cell_h + padding)

        sheet_img.paste(t_img, (x, y), t_img)
        if labels:
            draw.text((x + 2, y + tile_h + 1), f"F{idx:02d}", fill=(220, 220, 220, 255))

    sheet_png = png_bytes(sheet_img)
    sheet_sha = digest(sheet_png)

    limitations = [
        "CPU Pillow ordered alpha composition; GPU WBOIT, native action-wide billboard bounds and cross-GPU pixel parity are not verified.",
        "Deterministic contact sheet of discrete animation frames.",
    ]

    report_dict = {
        "schema": CONTACT_SHEET_SCHEMA,
        "semantics": {
            "renderer": RENDERER_VERSION,
            "geometry": GEOMETRY_VERSION,
            "timing": TIMING_VERSION,
            "contact_sheet": CONTACT_SHEET_VERSION,
        },
        "sources": dict(inspector._hashes),
        "selection": {
            "category": selection["category"],
            "action": selection.get("action"),
            "slot": selection["resolved_slot"],
            "view": selection["view"],
            "direction": selection.get("direction"),
            "camera_direction": selection["camera_direction"],
        },
        "grid": {
            "columns": cols,
            "rows": rows,
            "total_tiles": total_tiles,
            "tile_dimensions": {"width": tile_w, "height": tile_h},
            "padding": padding,
            "margin": margin,
            "scale": scale,
        },
        "dimensions": {"width": sheet_w, "height": sheet_h},
        "tiles": tiles_data,
        "overlays": list(overlays) if overlays else [],
        "fidelity": {
            "overall": "PARTIAL",
            "geometry": "VERIFIED",
            "native_pixel_parity": "UNVERIFIED",
            "limitations": limitations,
        },
        "png_sha256": sheet_sha,
    }

    sealed_report = sealed(report_dict)
    return {
        "report": sealed_report,
        "image": sheet_img,
        "png_bytes": sheet_png,
    }


def export_frame_sequence(
    inspector: AnimationInspector,
    selection: Mapping[str, Any],
    output_dir: str | Path,
    *,
    overlays: Sequence[str] | None = None,
    canvas_size: tuple[int, int] = (256, 256),
    origin: tuple[int, int] = (128, 192),
    auto_fit: bool = False,
) -> dict[str, Any]:
    """Atomically export an animation frame sequence with its canonical manifest.

    Frames are staged in a temporary directory and published atomically to output_dir.
    """
    dest = Path(output_dir)
    try:
        dest.lstat()
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, "Cannot inspect output directory path.", path=str(dest)) from exc
    else:
        raise ForgeError(ErrorCode.INVALID_OUTPUT, "Output already exists; overwriting is forbidden.", path=str(dest))

    if not dest.parent.is_dir():
        raise ForgeError(ErrorCode.INVALID_OUTPUT, "Output parent must be an existing directory.", path=str(dest))

    staging = dest.parent / f".staging-{uuid.uuid4().hex}"
    try:
        staging.mkdir(parents=False, exist_ok=False)
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, "Cannot create staging directory.", path=str(staging)) from exc

    try:
        slot = selection["resolved_slot"]
        view = selection["view"]
        cam_dir = selection["camera_direction"]
        frame_count = selection["frame_count"]
        check(frame_count >= 1, "Cannot export sequence of zero frames.")

        frames = []
        for f in range(frame_count):
            sel_f = inspector.timeline.select(slot=slot, view=view, camera_direction=cam_dir, frame=f)
            res_f = inspector.inspect(sel_f, canvas_size=canvas_size, origin=origin, auto_fit=auto_fit)
            rep_f = res_f["report"]
            img_f = res_f["image"]
            img_f_overlay = apply_overlays(img_f, rep_f, overlays=overlays)

            frame_png = png_bytes(img_f_overlay)
            frame_sha = digest(frame_png)
            filename = f"frame_{f:03d}.png"

            frame_path = staging / filename
            frame_path.write_bytes(frame_png)

            frames.append({
                "frame": f,
                "filename": filename,
                "png_sha256": frame_sha,
                "bounds": rep_f["frame_bounds"]["visible"],
                "duration_ms": rep_f["selection"]["frame_duration_ms"],
            })

        sequence_sha = digest("".join(f["png_sha256"] for f in frames).encode("ascii"))
        limitations = [
            "CPU Pillow ordered alpha composition; GPU WBOIT, native action-wide billboard bounds and cross-GPU pixel parity are not verified.",
            "Deterministic sequence of PNG preview frames.",
        ]

        manifest_dict = {
            "schema": SEQUENCE_MANIFEST_SCHEMA,
            "semantics": {
                "renderer": RENDERER_VERSION,
                "geometry": GEOMETRY_VERSION,
                "timing": TIMING_VERSION,
                "export": EXPORT_VERSION,
            },
            "sources": dict(inspector._hashes),
            "selection": {
                "category": selection["category"],
                "action": selection.get("action"),
                "slot": selection["resolved_slot"],
                "view": selection["view"],
                "direction": selection.get("direction"),
                "camera_direction": selection["camera_direction"],
            },
            "frame_count": len(frames),
            "timing": {
                "mode": selection.get("mode", "MANUAL"),
                "source_delay": selection.get("source_delay"),
                "runtime_rule": selection.get("timing_rule"),
                "looping": selection.get("looping"),
            },
            "frames": frames,
            "overlays": list(overlays) if overlays else [],
            "fidelity": {
                "overall": "PARTIAL",
                "geometry": "VERIFIED",
                "native_pixel_parity": "UNVERIFIED",
                "limitations": limitations,
            },
            "sequence_sha256": sequence_sha,
        }

        sealed_manifest = sealed(manifest_dict)
        manifest_path = staging / "sequence-manifest.json"
        manifest_path.write_bytes(canonical_bytes(sealed_manifest))

        # Atomically rename staging directory to dest
        os.rename(staging, dest)
        return sealed_manifest

    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
