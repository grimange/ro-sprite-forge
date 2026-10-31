"""Reproduce public RSF-11 preview compositor evidence.

Uses purely synthetic test patterns and contracts.
Demonstrates layer ordering, affine transforms, alpha blending,
anchor alignment, safe clipping, and JSON Schema compliance.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "src"), str(ROOT / "tests")]

from ro_sprite_forge.core.canonical import canonical_bytes
from ro_sprite_forge.formats.preview import (
    PREVIEW_SCHEMA,
    RENDERER_VERSION,
    composite_frame,
    pack_color,
    preview_result_schema,
)
from test_preview import _make_act, _make_test_spr_doc


def generate_examples() -> dict[str, Any]:
    spr = _make_test_spr_doc()
    examples = {}

    # 1. Single opaque layer
    c0 = {
        "sprite": 0,
        "pool": 0,
        "x": 0,
        "y": 0,
        "mirror": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "angle": 0,
        "color": 0xFFFFFFFF,
    }
    act0 = _make_act([c0])
    res0 = composite_frame(act0, spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
    examples["single_opaque_layer"] = res0["report"]

    # 2. Two overlapping layers with order verification (Layer 0 under Layer 1)
    c1_0 = {
        "sprite": 0,
        "pool": 0,
        "x": 0,
        "y": 0,
        "mirror": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "angle": 0,
        "color": 0xFFFFFFFF,
    }
    c1_1 = {
        "sprite": 1,
        "pool": 0,
        "x": 0,
        "y": 0,
        "mirror": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "angle": 0,
        "color": 0xFFFFFFFF,
    }
    act1 = _make_act([c1_0, c1_1])
    res1 = composite_frame(act1, spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
    examples["two_overlapping_layers_order"] = res1["report"]

    # 3. Alpha blending (50% transparent blue over opaque red)
    c2_0 = {
        "sprite": 0,
        "pool": 0,
        "x": 0,
        "y": 0,
        "mirror": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "angle": 0,
        "color": 0xFFFFFFFF,
    }
    c2_1 = {
        "sprite": 2,
        "pool": 0,
        "x": 0,
        "y": 0,
        "mirror": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "angle": 0,
        "color": pack_color(255, 255, 255, 128),
    }
    act2 = _make_act([c2_0, c2_1])
    res2 = composite_frame(act2, spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
    examples["alpha_blending"] = res2["report"]

    # 4. Affine transformations (mirror, scale, angle, tint)
    c3 = {
        "sprite": 4,
        "pool": 0,
        "x": 4,
        "y": -2,
        "mirror": 1,
        "scale_x": 1.5,
        "scale_y": 0.8,
        "angle": 45,
        "color": pack_color(200, 150, 100, 220),
    }
    act3 = _make_act([c3])
    res3 = composite_frame(act3, spr, 0, 0, canvas_size=(48, 48), origin=(24, 24))
    examples["affine_transformations"] = res3["report"]

    # 5. Multipart anchor alignment (body + head)
    body_clip = {
        "sprite": 0,
        "pool": 0,
        "x": 0,
        "y": 0,
        "mirror": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "angle": 0,
        "color": 0xFFFFFFFF,
    }
    body_act = _make_act([body_clip], anchors=[{"x": 10, "y": 20}])
    head_clip = {
        "sprite": 1,
        "pool": 0,
        "x": 0,
        "y": 0,
        "mirror": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "angle": 0,
        "color": 0xFFFFFFFF,
    }
    head_act = _make_act([head_clip], anchors=[{"x": 2, "y": 5}])
    res4 = composite_frame(
        body_act,
        spr,
        0,
        0,
        head_act_data=head_act,
        head_spr_doc=spr,
        canvas_size=(64, 64),
        origin=(32, 32),
    )
    examples["multipart_anchor_alignment"] = res4["report"]

    # 6. Safe boundary clipping
    c5 = {
        "sprite": 0,
        "pool": 0,
        "x": -2,
        "y": -2,
        "mirror": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "angle": 0,
        "color": 0xFFFFFFFF,
    }
    act5 = _make_act([c5])
    res5 = composite_frame(act5, spr, 0, 0, canvas_size=(16, 16), origin=(0, 0))
    examples["safe_boundary_clipping"] = res5["report"]

    # 7. Synthetic 12-layer complex motion
    c6_list = []
    for i in range(12):
        c6_list.append({
            "sprite": i % 5,
            "pool": 0,
            "x": (i - 6) * 3,
            "y": (i % 3) * 2,
            "mirror": int(i % 2 == 1),
            "scale_x": 1.0 + (i * 0.05),
            "scale_y": 1.0,
            "angle": (i * 30) % 360,
            "color": 0xFFFFFFFF,
        })
    act6 = _make_act(c6_list)
    res6 = composite_frame(act6, spr, 0, 0, canvas_size=(128, 128), origin=(64, 64))
    examples["synthetic_12_layer_motion"] = res6["report"]

    # 8. Corrupt / invalid sprite reference (strict=False)
    bad_clip = {
        "sprite": 999,
        "pool": 0,
        "x": 0,
        "y": 0,
        "mirror": 0,
        "scale_x": 1.0,
        "scale_y": 1.0,
        "angle": 0,
        "color": 0xFFFFFFFF,
    }
    act7 = _make_act([bad_clip])
    res7 = composite_frame(act7, spr, 0, 0, strict=False)
    examples["corrupt_sprite_reference"] = res7["report"]

    return examples


def main():
    ex = generate_examples()
    out_path = Path(__file__).parent / "examples.json"
    out_path.write_text(json.dumps(ex, indent=2, sort_keys=True) + "\n")
    print(f"Generated {len(ex)} examples in {out_path}")


if __name__ == "__main__":
    main()
