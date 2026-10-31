"""Unit tests for order-preserving multilayer preview compositor.

Validates 20 synthetic pixel scenarios, transformation pipeline,
fidelity reporting, determinism, and JSON Schema compliance.
"""

import json
import math
import unittest
from importlib.resources import files
from typing import Any

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

from PIL import Image

from ro_sprite_forge.core.contracts import _shape
from ro_sprite_forge.formats.errors import CodecError
from ro_sprite_forge.formats.preview import (
    PREVIEW_SCHEMA,
    RENDERER_VERSION,
    PreviewCompositor,
    actor_preview,
    apply_color_tint,
    composite_frame,
    only_clip,
    pack_color,
    place,
    place_clip,
    png_bytes,
    preview_result_schema,
    sha256_hex,
    transform_layer_image,
    unpack_color,
)
from ro_sprite_forge.formats.spr import IndexedImage, RgbaImage, SprDocument


def _make_palette() -> bytes:
    """Create a standard 1024-byte palette for testing."""
    pal = bytearray(1024)
    # Index 0: Transparent (canonical 0,0,0,0)
    pal[0:4] = b"\x00\x00\x00\x00"
    # Index 1: Opaque Red (255, 0, 0, 255)
    pal[4:8] = b"\xff\x00\x00\xff"
    # Index 2: Opaque Green (0, 255, 0, 255)
    pal[8:12] = b"\x00\xff\x00\xff"
    # Index 3: Opaque Blue (0, 0, 255, 255)
    pal[12:16] = b"\x00\x00\xff\xff"
    # Index 4: Opaque White (255, 255, 255, 255)
    pal[16:20] = b"\xff\xff\xff\xff"
    # Index 5: Opaque Yellow (255, 255, 0, 255)
    pal[20:24] = b"\xff\xff\x00\xff"
    # Index 6: Opaque Magenta (255, 0, 255, 255)
    pal[24:28] = b"\xff\x00\xff\xff"
    # Index 7: Opaque Cyan (0, 255, 255, 255)
    pal[28:32] = b"\x00\xff\xff\xff"
    return bytes(pal)


def _make_test_spr_doc() -> SprDocument:
    """Create SprDocument with known indexed and truecolor test patterns."""
    palette = _make_palette()

    # Indexed 0: 4x4 pure Red
    img0 = IndexedImage(4, 4, bytes([1] * 16), 16)
    # Indexed 1: 4x4 pure Green
    img1 = IndexedImage(4, 4, bytes([2] * 16), 16)
    # Indexed 2: 4x4 pure Blue
    img2 = IndexedImage(4, 4, bytes([3] * 16), 16)
    # Indexed 3: 4x4 with Index 0 (transparent) and Index 4 (white) checkerboard
    pattern = [0, 4, 0, 4, 4, 0, 4, 0, 0, 4, 0, 4, 4, 0, 4, 0]
    img3 = IndexedImage(4, 4, bytes(pattern), 16)
    # Indexed 4: 4x4 Asymmetric arrow: top-left quadrant is Red (1), others transparent (0)
    asym = [
        1, 1, 0, 0,
        1, 0, 0, 0,
        0, 0, 0, 0,
        0, 0, 0, 0,
    ]
    img4 = IndexedImage(4, 4, bytes(asym), 16)
    # Indexed 5: 4x4 pure White
    img5 = IndexedImage(4, 4, bytes([4] * 16), 16)

    # Truecolor RGBA 0: 4x4 semi-transparent Yellow (255, 255, 0, 128)
    tc_rgba0 = bytes([255, 255, 0, 128] * 16)
    rgba0 = RgbaImage(4, 4, tc_rgba0)

    # Truecolor RGBA 1: 4x4 gradient
    grad = []
    for y in range(4):
        for x in range(4):
            grad.extend([x * 64, y * 64, 128, 255])
    rgba1 = RgbaImage(4, 4, bytes(grad))

    return SprDocument([img0, img1, img2, img3, img4, img5], [rgba0, rgba1], palette)


def _make_act(clips: list[dict[str, Any]], anchors: list[dict[str, int]] | None = None) -> dict[str, Any]:
    """Helper to construct minimal valid ACT structure with one action and one frame."""
    motion = {
        "clips": clips,
        "anchors": anchors or [],
        "event_id": -1,
    }
    return {
        "magic": "AC",
        "version": 0x0204,
        "actions": [[motion]],
        "events": [],
        "delays": [4.0],
    }


class PreviewCompositorTests(unittest.TestCase):
    def setUp(self):
        self.spr = _make_test_spr_doc()
        self.schema = preview_result_schema()

    def _validate_schema(self, report: dict[str, Any]):
        if HAS_JSONSCHEMA:
            jsonschema.validate(instance=report, schema=self.schema)
        else:
            required = [
                "schema", "renderer_version", "fidelity", "dimensions", "origin",
                "bounds", "layers_rendered", "layers", "unsupported_semantics",
                "errors", "png_sha256"
            ]
            for field in required:
                self.assertIn(field, report)
            self.assertEqual(report["schema"], "rsf.preview-result/v1")
            self.assertIn(report["fidelity"], ("VERIFIED", "PARTIAL", "UNVERIFIED", "INVALID"))
            self.assertIsInstance(report["layers"], list)
            self.assertIsInstance(report["dimensions"], dict)
            self.assertIsInstance(report["origin"], dict)

    # Scenario 1: Single opaque layer
    def test_01_single_opaque_layer(self):
        clip = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        act = _make_act([clip])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        img = res["image"]
        # Center of 4x4 image at origin (16, 16):
        # left = 16 - (4-1)//2 = 15. top = 16 - (4-1)//2 = 15.
        # Placed at (15, 15) to (18, 18).
        pixel = img.getpixel((15, 15))
        self.assertEqual(pixel, (255, 0, 0, 255))
        self.assertEqual(res["report"]["layers_rendered"], 1)
        self.assertEqual(res["report"]["fidelity"], "VERIFIED")

    # Scenario 2: Two overlapping layers with order verification (Layer 0 under Layer 1)
    def test_02_two_overlapping_layers_order(self):
        # Layer 0: Red at (0, 0)
        c0 = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        # Layer 1: Green at (0, 0)
        c1 = {"sprite": 1, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        act = _make_act([c0, c1])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        img = res["image"]
        # Layer 1 (Green) is on top of Layer 0 (Red)
        self.assertEqual(img.getpixel((15, 15)), (0, 255, 0, 255))
        self.assertEqual(res["report"]["layers_rendered"], 2)

    # Scenario 3: Reversed layer order
    def test_03_reversed_layer_order(self):
        # Layer 0: Green at (0, 0)
        c0 = {"sprite": 1, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        # Layer 1: Red at (0, 0)
        c1 = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        act = _make_act([c0, c1])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        img = res["image"]
        # Layer 1 (Red) is on top of Layer 0 (Green)
        self.assertEqual(img.getpixel((15, 15)), (255, 0, 0, 255))

    # Scenario 4: Alpha blending (e.g. 50% transparent top layer)
    def test_04_alpha_blending(self):
        # Layer 0: Opaque Red
        c0 = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        # Layer 1: Opaque Blue with 50% alpha tint (color = 0x80FFFFFF)
        # alpha = 128 -> (128 << 24) | 0x00FFFFFF = 0x80FFFFFF
        c1 = {"sprite": 2, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": pack_color(255, 255, 255, 128)}
        act = _make_act([c0, c1])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        img = res["image"]
        p = img.getpixel((15, 15))
        # Expected blend of (255, 0, 0, 255) and (0, 0, 255, 128):
        # Red should be ~127, Blue ~128, Alpha 255
        self.assertAlmostEqual(p[0], 127, delta=3)
        self.assertEqual(p[1], 0)
        self.assertAlmostEqual(p[2], 128, delta=3)
        self.assertEqual(p[3], 255)

    # Scenario 5: Fully transparent layer
    def test_05_fully_transparent_layer(self):
        # Layer 0: Opaque Red
        c0 = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        # Layer 1: Layer with alpha=0 (color = 0x00FFFFFF)
        c1 = {"sprite": 2, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": pack_color(255, 255, 255, 0)}
        act = _make_act([c0, c1])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        img = res["image"]
        # Transparent layer on top leaves red intact
        self.assertEqual(img.getpixel((15, 15)), (255, 0, 0, 255))

    # Scenario 6: Indexed palette transparency (palette index 0)
    def test_06_indexed_palette_transparency(self):
        # Sprite 3 has checkerboard of index 0 (transparent) and index 4 (white)
        c0 = {"sprite": 3, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        act = _make_act([c0])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        img = res["image"]
        # Pixel (15, 15) is top-left of sprite 3, which is pattern index 0 -> transparent (0, 0, 0, 0)
        self.assertEqual(img.getpixel((15, 15)), (0, 0, 0, 0))
        # Pixel (16, 15) is top-second of sprite 3, which is pattern index 4 -> white (255, 255, 255, 255)
        self.assertEqual(img.getpixel((16, 15)), (255, 255, 255, 255))

    # Scenario 7: Truecolor RGBA channel order
    def test_07_truecolor_rgba_pool(self):
        # Pool 1 Sprite 0 is semi-transparent yellow (255, 255, 0, 128)
        c0 = {"sprite": 0, "pool": 1, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        act = _make_act([c0])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        img = res["image"]
        self.assertEqual(img.getpixel((15, 15)), (255, 255, 0, 128))
        self.assertEqual(res["report"]["layers"][0]["pool"], 1)

    # Scenario 8: Horizontal mirroring
    def test_08_horizontal_mirroring(self):
        # Sprite 4: top-left quadrant is Red (x in 0..1, y in 0..1)
        # Unmirrored: top-left (15, 15) is Red, top-right (17, 15) is transparent
        c0 = {"sprite": 4, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        res0 = composite_frame(_make_act([c0]), self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self.assertEqual(res0["image"].getpixel((15, 15)), (255, 0, 0, 255))
        self.assertEqual(res0["image"].getpixel((17, 15)), (0, 0, 0, 0))

        # Mirrored: top-left becomes top-right! (15, 15) is transparent, (18, 15) is Red
        c1 = {"sprite": 4, "pool": 0, "x": 0, "y": 0, "mirror": 1, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        res1 = composite_frame(_make_act([c1]), self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res1["report"])
        self.assertEqual(res1["image"].getpixel((15, 15)), (0, 0, 0, 0))
        self.assertEqual(res1["image"].getpixel((18, 15)), (255, 0, 0, 255))
        self.assertTrue(res1["report"]["layers"][0]["mirror"])

    # Scenario 9: Non-uniform scaling
    def test_09_non_uniform_scaling(self):
        # Scale 4x4 image by scale_x=2.0, scale_y=1.0 -> 8x4
        c0 = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 2.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        act = _make_act([c0])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        layer = res["report"]["layers"][0]
        self.assertEqual(layer["rendered_size"], {"width": 8, "height": 4})
        self.assertEqual(res["report"]["bounds"]["width"], 8)
        self.assertEqual(res["report"]["bounds"]["height"], 4)

    # Scenario 10: Rotation (90, 180, 270)
    def test_10_rotation_cardinal_and_arbitrary(self):
        # Sprite 4: asymmetric arrow in top-left
        # Rotate 90 degrees clockwise: top-left moves to top-right
        c0 = {"sprite": 4, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 90, "color": 0xFFFFFFFF}
        res = composite_frame(_make_act([c0]), self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])
        self.assertEqual(res["report"]["layers"][0]["angle"], 90)

        # Rotate 45 degrees arbitrary
        c1 = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 45, "color": 0xFFFFFFFF}
        res45 = composite_frame(_make_act([c1]), self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res45["report"])
        self.assertEqual(res45["report"]["fidelity"], "VERIFIED")

    # Scenario 11: Color tinting (modulating RGB channels)
    def test_11_color_tinting(self):
        # White sprite (Index 4 in palette) tinted with green (0xFF00FF00)
        # In ABGR: r=0, g=255, b=0, a=255
        col = pack_color(0, 255, 0, 255)
        # Using Index 0 (Red 255, 0, 0): tinting with 50% green (128) and 100% red (255)
        c0 = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": pack_color(128, 255, 255, 255)}
        res = composite_frame(_make_act([c0]), self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        img = res["image"]
        # Red channel was 255, tinted by 128 -> (255 * 128) // 255 = 128
        pixel = img.getpixel((15, 15))
        self.assertEqual(pixel[0], 128)
        self.assertEqual(pixel[1], 0)
        self.assertEqual(pixel[2], 0)

    # Scenario 12: Alpha modulation
    def test_12_alpha_modulation(self):
        c0 = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": pack_color(255, 255, 255, 64)}
        res = composite_frame(_make_act([c0]), self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        img = res["image"]
        pixel = img.getpixel((15, 15))
        self.assertEqual(pixel[3], 64)

    # Scenario 13: Multilayer occlusion (5 layers stacked)
    def test_13_multilayer_occlusion_five_layers(self):
        clips = []
        colors = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255), (255, 0, 255, 255)]
        for i in range(5):
            clips.append({
                "sprite": 5,
                "pool": 0,
                "x": i,
                "y": 0,
                "mirror": 0,
                "scale_x": 1.0,
                "scale_y": 1.0,
                "angle": 0,
                "color": pack_color(*colors[i]),
            })
        act = _make_act(clips)
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(64, 64), origin=(32, 32))
        self._validate_schema(res["report"])

        self.assertEqual(res["report"]["layers_rendered"], 5)
        # Check layer 4 is on top at its rightmost offset
        img = res["image"]
        # Center of layer 4 is at origin (32 + 4, 32) = (36, 32)
        # Left of layer 4 is 36 - (4-1)//2 = 36 - 1 = 35.
        p = img.getpixel((35, 31))
        self.assertEqual(p, (255, 0, 255, 255))

    # Scenario 14: Out of bounds / boundary clipping
    def test_14_boundary_clipping(self):
        # Clip placed at (-16, -16) relative to origin (0, 0)
        c0 = {"sprite": 0, "pool": 0, "x": -2, "y": -2, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        act = _make_act([c0])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(16, 16), origin=(0, 0))
        self._validate_schema(res["report"])

        self.assertTrue(res["report"]["layers"][0]["clipped"])
        # Top-left pixel of canvas (0, 0) should be colored
        self.assertEqual(res["image"].getpixel((0, 0)), (255, 0, 0, 255))

    # Scenario 15: Invisible placeholder layer
    def test_15_invisible_placeholder_layer(self):
        c_inv = {"sprite": -1, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        c_vis = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        act = _make_act([c_inv, c_vis])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        self._validate_schema(res["report"])

        # Only 1 layer should be rendered
        self.assertEqual(res["report"]["layers_rendered"], 1)
        self.assertEqual(res["report"]["layers"][0]["sprite"], 0)

    # Scenario 16: Multipart anchor alignment
    def test_16_multipart_anchor_alignment(self):
        body_clip = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        body_act = _make_act([body_clip], anchors=[{"x": 10, "y": 20}])

        head_clip = {"sprite": 1, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        head_act = _make_act([head_clip], anchors=[{"x": 2, "y": 5}])

        res = composite_frame(body_act, self.spr, 0, 0, head_act_data=head_act, head_spr_doc=self.spr, canvas_size=(64, 64), origin=(32, 32))
        self._validate_schema(res["report"])

        self.assertEqual(res["report"]["layers_rendered"], 2)
        # Head layer shift should be (10 - 2, 20 - 5) = (8, 15)
        head_layer = res["report"]["layers"][1]
        self.assertEqual(head_layer["part"], "head")
        self.assertEqual(head_layer["offset"], {"x": 8, "y": 15})

    # Scenario 17: Malformed / out of bounds sprite index
    def test_17_out_of_bounds_sprite_handling(self):
        # Sprite index 999 does not exist in pool
        bad_clip = {"sprite": 999, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        act = _make_act([bad_clip])

        # Strict mode raises CodecError
        with self.assertRaises(CodecError):
            composite_frame(act, self.spr, 0, 0, strict=True)

        # Non-strict mode reports INVALID fidelity
        res = composite_frame(act, self.spr, 0, 0, strict=False)
        self.assertEqual(res["report"]["fidelity"], "INVALID")
        self.assertTrue(len(res["report"]["errors"]) > 0)

    # Scenario 18: Output determinism
    def test_18_output_determinism(self):
        c0 = {"sprite": 0, "pool": 0, "x": 2, "y": -3, "mirror": 1, "scale_x": 1.5, "scale_y": 0.8, "angle": 33, "color": pack_color(200, 150, 100, 220)}
        act = _make_act([c0])

        res1 = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))
        res2 = composite_frame(act, self.spr, 0, 0, canvas_size=(32, 32), origin=(16, 16))

        self.assertEqual(res1["png_bytes"], res2["png_bytes"])
        self.assertEqual(res1["report"]["png_sha256"], res2["report"]["png_sha256"])
        self.assertEqual(res1["report"], res2["report"])

    # Scenario 19: JSON Schema validation and source hashes
    def test_19_schema_and_source_hashes(self):
        c0 = {"sprite": 0, "pool": 0, "x": 0, "y": 0, "mirror": 0, "scale_x": 1.0, "scale_y": 1.0, "angle": 0, "color": 0xFFFFFFFF}
        act = _make_act([c0])
        hashes = {
            "act": "a" * 64,
            "spr": "b" * 64,
        }
        res = composite_frame(act, self.spr, 0, 0, source_hashes=hashes)
        self._validate_schema(res["report"])
        self.assertEqual(res["report"]["source_hashes"], hashes)
        self.assertEqual(res["report"]["schema"], PREVIEW_SCHEMA)
        self.assertEqual(res["report"]["renderer_version"], RENDERER_VERSION)

    # Scenario 20: Layer details metadata accuracy
    def test_20_layer_details_metadata_accuracy(self):
        c0 = {
            "sprite": 2,
            "pool": 0,
            "x": 5,
            "y": -7,
            "mirror": 1,
            "scale_x": 1.25,
            "scale_y": 2.0,
            "angle": 45,
            "color": pack_color(10, 20, 30, 40),
        }
        act = _make_act([c0])
        res = composite_frame(act, self.spr, 0, 0, canvas_size=(48, 48), origin=(24, 24))
        self._validate_schema(res["report"])

        layer = res["report"]["layers"][0]
        self.assertEqual(layer["layer_index"], 0)
        self.assertEqual(layer["sprite"], 2)
        self.assertEqual(layer["pool"], 0)
        self.assertEqual(layer["offset"], {"x": 5, "y": -7})
        self.assertTrue(layer["mirror"])
        self.assertEqual(layer["scale"], {"x": 1.25, "y": 2.0})
        self.assertEqual(layer["angle"], 45.0)
        self.assertEqual(layer["color"]["r"], 10)
        self.assertEqual(layer["color"]["g"], 20)
        self.assertEqual(layer["color"]["b"], 30)
        self.assertEqual(layer["color"]["a"], 40)
        self.assertEqual(layer["source_size"], {"width": 4, "height": 4})


if __name__ == "__main__":
    unittest.main()
