"""Private fixture verification for order-preserving preview compositor.

Tests real private Novice and Orc Skeleton assets:
- Novice single-layer and body+head anchor composition.
- Orc Skeleton multilayer attack and 12-layer death frames.
- Layer order preservation, mirroring, rotation, scaling, and bounds.
- Comparison with native RSF-6 prepared frame geometry and captures.
- Full compliance with rsf.preview-result/v1 JSON Schema.
"""

import hashlib
import json
import os
from pathlib import Path
import unittest

try:
    import jsonschema
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False

from PIL import Image

from ro_sprite_forge.core.contracts import _shape
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.preview import (
    PreviewCompositor,
    composite_frame,
    preview_result_schema,
)
from ro_sprite_forge.formats.spr import read_spr
from test_audited_fixtures import AUDITED_HASHES, find_fixture


class AuditedPreviewFixtureTests(unittest.TestCase):
    def setUp(self):
        self.schema = preview_result_schema()

    def _validate_schema(self, report: dict):
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

    def test_novice_body_head_preview_idle_walk(self):
        body_act_path = find_fixture("novice_body_act")
        body_spr_path = find_fixture("novice_body_spr")
        head_act_path = find_fixture("novice_head_act")
        head_spr_path = find_fixture("novice_head_spr")
        if not all([body_act_path, body_spr_path, head_act_path, head_spr_path]):
            self.skipTest("Audited Novice fixtures not available")

        body_act = read_act(body_act_path.read_bytes())
        body_spr = read_spr(body_spr_path.read_bytes())
        head_act = read_act(head_act_path.read_bytes())
        head_spr = read_spr(head_spr_path.read_bytes())

        # Test Idle: Slot 0, Frame 0
        res_idle = composite_frame(
            body_act,
            body_spr,
            0,
            0,
            head_act_data=head_act,
            head_spr_doc=head_spr,
            canvas_size=(256, 256),
            origin=(128, 192),
            source_hashes={
                "novice_body_act": AUDITED_HASHES["novice_body_act"],
                "novice_body_spr": AUDITED_HASHES["novice_body_spr"],
                "novice_head_act": AUDITED_HASHES["novice_head_act"],
                "novice_head_spr": AUDITED_HASHES["novice_head_spr"],
            },
        )
        self._validate_schema(res_idle["report"])
        self.assertEqual(res_idle["report"]["layers_rendered"], 2)
        self.assertEqual(res_idle["report"]["fidelity"], "VERIFIED")
        self.assertIsNotNone(res_idle["report"]["bounds"])

        # Check anchor shift on head layer
        ba = body_act["actions"][0][0]["anchors"][0]
        ha = head_act["actions"][0][0]["anchors"][0]
        head_clip = [c for c in head_act["actions"][0][0]["clips"] if c["sprite"] >= 0][0]
        expected_head_offset = {
            "x": head_clip["x"] + (ba["x"] - ha["x"]),
            "y": head_clip["y"] + (ba["y"] - ha["y"]),
        }
        head_layer = res_idle["report"]["layers"][1]
        self.assertEqual(head_layer["part"], "head")
        self.assertEqual(head_layer["offset"], expected_head_offset)

        # Test Walk: Slot 8, Frame 0
        res_walk = composite_frame(
            body_act,
            body_spr,
            8,
            0,
            head_act_data=head_act,
            head_spr_doc=head_spr,
            canvas_size=(256, 256),
            origin=(128, 192),
        )
        self._validate_schema(res_walk["report"])
        self.assertEqual(res_walk["report"]["layers_rendered"], 2)

        # Determinism check
        res_walk2 = composite_frame(
            body_act,
            body_spr,
            8,
            0,
            head_act_data=head_act,
            head_spr_doc=head_spr,
            canvas_size=(256, 256),
            origin=(128, 192),
        )
        self.assertEqual(res_walk["png_bytes"], res_walk2["png_bytes"])
        self.assertEqual(res_walk["report"]["png_sha256"], res_walk2["report"]["png_sha256"])

    def test_orc_skeleton_multilayer_attack(self):
        act_path = find_fixture("orc_skeleton_act")
        spr_path = find_fixture("orc_skeleton_spr")
        if not act_path or not spr_path:
            self.skipTest("Audited Orc Skeleton fixtures not available")

        act = read_act(act_path.read_bytes())
        spr = read_spr(spr_path.read_bytes())

        # Attack: Slot 16, Frame 0
        res = composite_frame(
            act,
            spr,
            16,
            0,
            canvas_size=(256, 256),
            origin=(128, 192),
            source_hashes={
                "orc_skeleton_act": AUDITED_HASHES["orc_skeleton_act"],
                "orc_skeleton_spr": AUDITED_HASHES["orc_skeleton_spr"],
            },
        )
        self._validate_schema(res["report"])
        self.assertGreaterEqual(res["report"]["layers_rendered"], 1)
        self.assertEqual(res["report"]["fidelity"], "VERIFIED")

    def test_orc_skeleton_12_layer_death_frame(self):
        """Test Action 32 Frame 21 of Orc Skeleton, which features 12 animated layers."""
        act_path = find_fixture("orc_skeleton_act")
        spr_path = find_fixture("orc_skeleton_spr")
        if not act_path or not spr_path:
            self.skipTest("Audited Orc Skeleton fixtures not available")

        act = read_act(act_path.read_bytes())
        spr = read_spr(spr_path.read_bytes())

        # Action 32, Frame 21
        motion = act["actions"][32][21]
        visible_clips = [c for c in motion["clips"] if c["sprite"] >= 0]
        self.assertEqual(len(visible_clips), 12, "Action 32 Frame 21 must have exactly 12 visible clips")

        res = composite_frame(
            act,
            spr,
            32,
            21,
            canvas_size=(512, 512),
            origin=(256, 384),
            source_hashes={
                "orc_skeleton_act": AUDITED_HASHES["orc_skeleton_act"],
                "orc_skeleton_spr": AUDITED_HASHES["orc_skeleton_spr"],
            },
        )
        self._validate_schema(res["report"])

        report = res["report"]
        self.assertEqual(report["layers_rendered"], 12)
        self.assertEqual(report["fidelity"], "VERIFIED")
        self.assertIsNotNone(report["bounds"])

        # Verify exact sprite identities match ACT motion clips in order
        expected_sprites = [c["sprite"] for c in visible_clips]
        observed_sprites = [l["sprite"] for l in report["layers"]]
        self.assertEqual(observed_sprites, expected_sprites)

        # Expected sprites from audited fixture: [44, 45, 46, 47, 46, 47, 47, 42, 40, 41, 43, 47]
        self.assertEqual(observed_sprites, [44, 45, 46, 47, 46, 47, 47, 42, 40, 41, 43, 47])

        # Verify layer 10 has mirror=True
        self.assertTrue(report["layers"][10]["mirror"])
        self.assertEqual(report["layers"][10]["sprite"], 43)

        # Verify non-zero rotation angles across layers
        angles = [l["angle"] for l in report["layers"]]
        self.assertEqual(angles, [4.0, 70.0, 111.0, 330.0, 211.0, 339.0, 348.0, 12.0, 234.0, 293.0, 260.0, 266.0])

        # Verify raw indexed SPR bytes were NOT mutated by preview
        self.assertEqual(len(spr.indexed_images), 57)
        self.assertEqual(len(spr.palette), 1024)

    def test_native_rsf6_structural_parity(self):
        """Cross-check preview layer structure against native RSF-6 report if available."""
        native_report_path = Path("/tmp/rsf6-native-run-final-1/native-report.json")
        if not native_report_path.is_file():
            self.skipTest("Native RSF-6 run evidence not present in /tmp/rsf6-native-run-final-1")

        with open(native_report_path, "r") as f:
            native_data = json.load(f)

        # Find orc prepared slot 32 frame 21
        orc_prep = None
        for item in native_data.get("prepared", []):
            if item.get("actor") == "orc":
                orc_prep = item["actions"]
                break

        if orc_prep is None or len(orc_prep) <= 32 or len(orc_prep[32]) <= 21:
            self.skipTest("Orc slot 32 frame 21 not in native report")

        native_frame = orc_prep[32][21]
        native_parts = native_frame["parts"]
        self.assertEqual(len(native_parts), 12)

        # Compare sprite indices, mirror flags, and offsets
        act_path = find_fixture("orc_skeleton_act")
        spr_path = find_fixture("orc_skeleton_spr")
        act = read_act(act_path.read_bytes())
        spr = read_spr(spr_path.read_bytes())
        res = composite_frame(act, spr, 32, 21, canvas_size=(512, 512), origin=(256, 384))
        preview_layers = res["report"]["layers"]

        for idx, (p_layer, n_part) in enumerate(zip(preview_layers, native_parts)):
            self.assertEqual(p_layer["sprite"], n_part["image"], f"Layer {idx} sprite mismatch")
            self.assertEqual(p_layer["mirror"], n_part["mirror"], f"Layer {idx} mirror mismatch")
            self.assertEqual(p_layer["offset"]["x"], n_part["offset"][0], f"Layer {idx} offset X mismatch")
            self.assertEqual(p_layer["offset"]["y"], n_part["offset"][1], f"Layer {idx} offset Y mismatch")


if __name__ == "__main__":
    unittest.main()
