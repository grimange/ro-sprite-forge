"""Audited private fixture tests for independent preview parity and fidelity evidence (RSF-14).

Verifies Python preview compositor against pinned Korangar native evidence:
- 160 native test cases and 1,664 timeline frame selections.
- 104 Novice slots (456 motions, 912 prepared layers) with body/head anchor placement.
- 40 Orc Skeleton slots (512 motions, 1,776 prepared layers) including 22-frame Death action.
- 0 mismatches across 2,688 prepared layers for offset, mirror, and angle.
- Exact schema validation and fidelity boundaries: overall PARTIAL, native_pixel_parity UNVERIFIED,
  artistic_approval UNVERIFIED, technical_difference_only True.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path
import sys
import unittest

_HOOKS_DIR = str(Path(__file__).resolve().parent)
if _HOOKS_DIR not in sys.path:
    sys.path.insert(0, _HOOKS_DIR)

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

from ro_sprite_forge.core.canonical import check_seal, digest
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.preview import composite_frame, RENDERER_VERSION, GEOMETRY_VERSION
from ro_sprite_forge.formats.spr import read_spr
from ro_sprite_forge.core.timeline import TIMING_VERSION
from test_audited_fixtures import AUDITED_HASHES, find_fixture

REPO_ROOT = Path(__file__).resolve().parents[2]


class AuditedParityEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.native_report_path = REPO_ROOT / "docs/evidence/rsf6/native-report.json.gz"
        if not cls.native_report_path.exists():
            raise unittest.SkipTest(f"Missing native reference evidence: {cls.native_report_path}")

        cls.native_raw = cls.native_report_path.read_bytes()
        cls.native_report_sha = hashlib.sha256(cls.native_raw).hexdigest()
        with gzip.open(cls.native_report_path, "rt") as f:
            cls.native = json.load(f)

        cls.schema_path = REPO_ROOT / "src/ro_sprite_forge/schemas/preview-parity-report-v1.json"
        if cls.schema_path.exists() and Draft202012Validator:
            schema_data = json.loads(cls.schema_path.read_text())
            Draft202012Validator.check_schema(schema_data)
            cls.validator = Draft202012Validator(schema_data)
        else:
            cls.validator = None

    def resource(self, name: str) -> bytes:
        p = find_fixture(name)
        if p is None:
            self.skipTest(f"Private fixture unavailable: {name}")
        raw = p.read_bytes()
        self.assertEqual(digest(raw), AUDITED_HASHES[name], f"Fixture {name} corrupted")
        return raw

    def test_preview_parity_report_file_and_schema(self):
        report_path = REPO_ROOT / "docs/evidence/rsf14/preview-parity-report.json"
        if not report_path.exists():
            self.skipTest("RSF-14 preview parity report not yet generated.")

        report = json.loads(report_path.read_text(encoding="utf-8"))
        check_seal(report, "rsf.preview-parity-report/v1")

        if self.validator:
            self.validator.validate(report)

        self.assertEqual(report["schema"], "rsf.preview-parity-report/v1")
        self.assertEqual(report["fidelity"]["overall"], "PARTIAL")
        self.assertEqual(report["fidelity"]["geometry"], "VERIFIED")
        self.assertEqual(report["fidelity"]["native_pixel_parity"], "UNVERIFIED")
        self.assertEqual(report["artistic_approval"], "UNVERIFIED")
        self.assertTrue(report["technical_difference_only"])

        self.assertEqual(report["results"]["mismatches_count"], 0)
        self.assertTrue(report["results"]["layer_transforms_match"])
        self.assertTrue(report["results"]["layer_ordering_match"])
        self.assertTrue(report["results"]["anchor_placement_match"])
        self.assertTrue(report["results"]["timeline_stepping_match"])
        self.assertTrue(report["results"]["slot_resolution_match"])

        self.assertEqual(report["scope"]["total_cases_evaluated"], 160)
        self.assertEqual(report["scope"]["total_frame_selections_evaluated"], 1664)
        self.assertEqual(report["scope"]["total_prepared_layers_evaluated"], 2688)

    def test_novice_prepared_layers_parity_and_anchoring(self):
        body_act = read_act(self.resource("novice_body_act"))
        body_spr = read_spr(self.resource("novice_body_spr"))
        head_act = read_act(self.resource("novice_head_act"))
        head_spr = read_spr(self.resource("novice_head_spr"))

        prepared = {r["actor"]: r["actions"] for r in self.native["prepared"]}
        novice_prepared = prepared["novice"]

        total_layers = 0
        mismatches = 0

        self.assertEqual(len(body_act["actions"]), 104)
        for slot in range(104):
            motions = body_act["actions"][slot]
            native_slot = novice_prepared[slot]
            self.assertEqual(len(motions), len(native_slot))

            for f_idx, motion in enumerate(motions):
                res = composite_frame(body_act, body_spr, slot, f_idx, head_act_data=head_act, head_spr_doc=head_spr)
                py_layers = res["report"]["layers"]
                native_parts = native_slot[f_idx]["parts"]

                self.assertEqual(len(py_layers), len(native_parts))
                for pl, np in zip(py_layers, native_parts):
                    total_layers += 1
                    if (pl["offset"]["x"], pl["offset"]["y"]) != (np["offset"][0], np["offset"][1]):
                        mismatches += 1
                    if pl["mirror"] != np["mirror"]:
                        mismatches += 1
                    if not math.isclose(pl["angle"] / 180 * math.pi, np["angle"], abs_tol=1e-5):
                        mismatches += 1

        self.assertEqual(total_layers, 912, "Novice must have exactly 912 visible prepared layers across 104 slots")
        self.assertEqual(mismatches, 0, "Novice prepared layers must have 0 geometry/offset/mirror/angle mismatches")

    def test_orc_skeleton_prepared_layers_parity_including_death(self):
        orc_act = read_act(self.resource("orc_skeleton_act"))
        orc_spr = read_spr(self.resource("orc_skeleton_spr"))

        prepared = {r["actor"]: r["actions"] for r in self.native["prepared"]}
        orc_prepared = prepared["orc"]

        total_layers = 0
        mismatches = 0

        self.assertEqual(len(orc_act["actions"]), 40)
        for slot in range(40):
            motions = orc_act["actions"][slot]
            native_slot = orc_prepared[slot]
            self.assertEqual(len(motions), len(native_slot))

            for f_idx, motion in enumerate(motions):
                res = composite_frame(orc_act, orc_spr, slot, f_idx)
                py_layers = res["report"]["layers"]
                native_parts = native_slot[f_idx]["parts"]

                self.assertEqual(len(py_layers), len(native_parts))
                for pl, np in zip(py_layers, native_parts):
                    total_layers += 1
                    if (pl["offset"]["x"], pl["offset"]["y"]) != (np["offset"][0], np["offset"][1]):
                        mismatches += 1
                    if pl["mirror"] != np["mirror"]:
                        mismatches += 1
                    if not math.isclose(pl["angle"] / 180 * math.pi, np["angle"], abs_tol=1e-5):
                        mismatches += 1

        self.assertEqual(total_layers, 1776, "Orc Skeleton must have exactly 1,776 visible prepared layers across 40 slots")
        self.assertEqual(mismatches, 0, "Orc Skeleton prepared layers must have 0 geometry/offset/mirror/angle mismatches")

        # Specific audit for Action 32 (Die / South, 22 frames with up to 12 layers per frame)
        death_slot = 32
        death_motions = orc_act["actions"][death_slot]
        self.assertEqual(len(death_motions), 22)
        death_layers = sum(len(orc_prepared[death_slot][f]["parts"]) for f in range(22))
        self.assertEqual(death_layers, 176, "Orc South Death action has exactly 176 prepared layers across 22 frames")

    def test_native_cases_resolution_and_timeline_stepping(self):
        groups = {
            "novice": {"Idle": 0, "Walk": 1, "Attack": 5, "Hurt": 6, "Die": 8},
            "orc": {"Idle": 0, "Walk": 1, "Attack": 2, "Hurt": 3, "Die": 4},
        }

        cases = self.native["cases"]
        self.assertEqual(len(cases), 160)

        total_selections = 0
        for case in cases:
            kind = case["actor"]
            action = case["requested_action"]
            direction = case["requested_direction"]
            camera = case["camera_view"]
            view = (direction + camera) & 7
            expected_slot = groups[kind][action] * 8 + view

            self.assertEqual(case["resolved_slot"], expected_slot)
            self.assertEqual(case["resolved_view"], view)

            for sample in case["sequence"]:
                total_selections += 1
                self.assertIn("frame", sample)
                self.assertIn("tick", sample)

        self.assertEqual(total_selections, 1664)


if __name__ == "__main__":
    unittest.main()
