"""Audited private fixture tests for reference comparison, contact sheets and sequence exports."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

from ro_sprite_forge.core.animation import AnimationInspector
from ro_sprite_forge.core.comparison import (
    compare_frames,
    comparison_schema,
)
from ro_sprite_forge.core.contact_sheet import (
    generate_contact_sheet,
    export_frame_sequence,
    contact_sheet_schema,
    sequence_manifest_schema,
)
from ro_sprite_forge.core.canonical import check_seal, digest
from test_audited_fixtures import AUDITED_HASHES, find_fixture


class AuditedComparisonTests(unittest.TestCase):
    def setUp(self):
        self.comp_validator = Draft202012Validator(comparison_schema()) if Draft202012Validator else None
        self.cs_validator = Draft202012Validator(contact_sheet_schema()) if Draft202012Validator else None
        self.seq_validator = Draft202012Validator(sequence_manifest_schema()) if Draft202012Validator else None

    def validate_comp(self, report):
        if self.comp_validator:
            self.comp_validator.validate(report)

    def validate_cs(self, report):
        if self.cs_validator:
            self.cs_validator.validate(report)

    def validate_seq(self, report):
        if self.seq_validator:
            self.seq_validator.validate(report)

    def resource(self, name: str) -> bytes:
        p = find_fixture(name)
        if p is None:
            self.skipTest("Private fixture unavailable: " + name)
        raw = p.read_bytes()
        self.assertEqual(digest(raw), AUDITED_HASHES[name])
        return raw

    def novice(self) -> AnimationInspector:
        return AnimationInspector(
            self.resource("novice_body_act"),
            self.resource("novice_body_spr"),
            category="player",
            head_act_bytes=self.resource("novice_head_act"),
            head_spr_bytes=self.resource("novice_head_spr"),
        )

    def orc(self) -> AnimationInspector:
        return AnimationInspector(
            self.resource("orc_skeleton_act"),
            self.resource("orc_skeleton_spr"),
            category="monster",
        )

    def test_novice_walk_contact_sheet_and_sequence(self):
        nov = self.novice()
        walk_sel = nov.timeline.select(action="Walk", view=0, frame=0)

        # Contact sheet for Novice Walk (8 frames)
        sheet_res = generate_contact_sheet(
            nov, walk_sel, columns=4, scale=1, padding=4, margin=8, labels=True,
            overlays=["anchors", "origin"]
        )
        rep = sheet_res["report"]
        self.validate_cs(rep)
        check_seal(rep, "rsf.contact-sheet/v1")
        self.assertEqual(rep["grid"]["columns"], 4)
        self.assertEqual(rep["grid"]["rows"], 2)
        self.assertEqual(rep["grid"]["total_tiles"], 8)
        self.assertEqual(len(rep["tiles"]), 8)

        # Sequence export for Novice Walk
        with tempfile.TemporaryDirectory(prefix="rsf-novice-seq-") as tmpdir:
            out_dir = Path(tmpdir) / "novice_walk"
            manifest = export_frame_sequence(nov, walk_sel, out_dir, overlays=["anchors"])
            self.validate_seq(manifest)
            check_seal(manifest, "rsf.sequence-manifest/v1")
            self.assertEqual(manifest["frame_count"], 8)
            self.assertEqual(len(manifest["frames"]), 8)
            for f in range(8):
                frame_png = out_dir / f"frame_{f:03d}.png"
                self.assertTrue(frame_png.is_file())
                self.assertGreater(frame_png.stat().st_size, 0)

    def test_novice_walk_frame_comparisons(self):
        nov = self.novice()
        frame0 = nov.timeline.select(action="Walk", view=0, frame=0)
        frame1 = nov.timeline.select(action="Walk", view=0, frame=1)

        # Self-comparison (frame0 vs frame0): must be MATCH
        self_res = compare_frames(nov, nov, frame0, frame0, mode="SIDE_BY_SIDE")
        self.validate_comp(self_res["report"])
        check_seal(self_res["report"], "rsf.preview-comparison/v1")
        self.assertEqual(self_res["report"]["comparison_status"], "MATCH")
        self.assertTrue(self_res["report"]["metrics"]["identical"])
        self.assertEqual(self_res["report"]["metrics"]["pixel_difference_count"], 0)

        # Cross-frame comparison (frame0 vs frame1): DIFFERENCE_OBSERVED
        diff_res = compare_frames(nov, nov, frame0, frame1, mode="DIFFERENCE")
        self.validate_comp(diff_res["report"])
        self.assertEqual(diff_res["report"]["comparison_status"], "DIFFERENCE_OBSERVED")
        self.assertFalse(diff_res["report"]["metrics"]["identical"])
        self.assertGreater(diff_res["report"]["metrics"]["pixel_difference_count"], 0)
        self.assertIsNotNone(diff_res["difference_image"])

    def test_orc_skeleton_death_contact_sheet_and_sequence(self):
        orc = self.orc()
        die_sel = orc.timeline.select(action="Die", view=0, frame=0)
        self.assertEqual(die_sel["frame_count"], 22)

        # 22-frame contact sheet for multilayer death animation (up to 12 layers per motion)
        sheet_res = generate_contact_sheet(
            orc, die_sel, columns=8, scale=1, padding=2, margin=4, labels=True,
            overlays=["bounds", "layers"]
        )
        rep = sheet_res["report"]
        self.validate_cs(rep)
        check_seal(rep, "rsf.contact-sheet/v1")
        self.assertEqual(rep["grid"]["columns"], 8)
        self.assertEqual(rep["grid"]["rows"], 3)
        self.assertEqual(rep["grid"]["total_tiles"], 22)
        self.assertEqual(len(rep["tiles"]), 22)

        # Export full death sequence
        with tempfile.TemporaryDirectory(prefix="rsf-orc-death-") as tmpdir:
            out_dir = Path(tmpdir) / "orc_death"
            manifest = export_frame_sequence(orc, die_sel, out_dir, overlays=["bounds"])
            self.validate_seq(manifest)
            check_seal(manifest, "rsf.sequence-manifest/v1")
            self.assertEqual(manifest["frame_count"], 22)
            self.assertEqual(len(manifest["frames"]), 22)

    def test_orc_skeleton_death_comparison_and_immutability(self):
        orc = self.orc()
        first_frame = orc.timeline.select(action="Die", view=0, frame=0)
        last_frame = orc.timeline.select(action="Die", view=0, frame=21)

        res = compare_frames(orc, orc, first_frame, last_frame, mode="SIDE_BY_SIDE", overlays=["origin", "bounds"])
        rep = res["report"]
        self.validate_comp(rep)
        self.assertEqual(rep["comparison_status"], "DIFFERENCE_OBSERVED")
        self.assertFalse(rep["metrics"]["identical"])
        self.assertGreater(rep["metrics"]["pixel_difference_count"], 0)

        # Verify underlying private asset bytes were never mutated
        for name in ("novice_body_act", "novice_body_spr", "novice_head_act", "novice_head_spr", "orc_skeleton_act", "orc_skeleton_spr"):
            p = find_fixture(name)
            if p is not None:
                self.assertEqual(digest(p.read_bytes()), AUDITED_HASHES[name], f"Fixture mutated: {name}")


if __name__ == "__main__":
    unittest.main()
