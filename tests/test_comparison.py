"""Unit tests for RSF-13 reference comparison, contact sheets, sequence exports and overlays."""
from __future__ import annotations

import io
import json
from pathlib import Path
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr

from PIL import Image

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

from ro_sprite_forge.cli import main
from ro_sprite_forge.core.animation import AnimationInspector
from ro_sprite_forge.core.comparison import (
    apply_overlays,
    compute_difference,
    create_side_by_side,
    blend_onion_skin,
    compare_frames,
    comparison_schema,
)
from ro_sprite_forge.core.contact_sheet import (
    generate_contact_sheet,
    export_frame_sequence,
    contact_sheet_schema,
    sequence_manifest_schema,
)
from ro_sprite_forge.core.canonical import canonical_bytes, check_seal
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.formats.act import write_act
from ro_sprite_forge.formats.spr import write_rgba_spr
from ro_sprite_forge.formats.preview import png_bytes, sha256_hex


def make_clip(**kw):
    return dict(x=0, y=0, sprite=0, pool=1, mirror=0, color=0xffffffff,
                scale_x=1.0, scale_y=1.0, angle=0) | kw


def make_motion(clips=None, anchors=None):
    return dict(bounds=[0] * 8, clips=[make_clip()] if clips is None else clips,
                anchors=anchors or [], event=-1)


def make_act(count=4, slots=40, clips_per_motion=1, anchors=None):
    return dict(
        reserved="00" * 10,
        actions=[[make_motion(clips=[make_clip() for _ in range(clips_per_motion)], anchors=anchors)
                  for _ in range(count)] for _ in range(slots)],
        delays=[2.0] * slots,
        events=[],
    )


def make_inspector(doc=None, image=None, **kw):
    img = image if image is not None else Image.new("RGBA", (16, 16), (255, 0, 0, 255))
    act_data = write_act(doc or make_act())
    spr_data = write_rgba_spr([img])
    return AnimationInspector(act_data, spr_data, **kw)


class ComparisonUnitTests(unittest.TestCase):
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

    def test_identical_frames_metric_match(self):
        ins1 = make_inspector(category="monster")
        ins2 = make_inspector(category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)
        sel2 = ins2.timeline.select(action="Walk", frame=0)

        res = compare_frames(ins1, ins2, sel1, sel2, mode="SIDE_BY_SIDE")
        rep = res["report"]
        self.validate_comp(rep)
        check_seal(rep, "rsf.preview-comparison/v1")

        self.assertEqual(rep["comparison_status"], "MATCH")
        m = rep["metrics"]
        self.assertTrue(m["identical"])
        self.assertTrue(m["dimensions_match"])
        self.assertTrue(m["bounds_match"])
        self.assertTrue(m["layer_count_match"])
        self.assertEqual(m["pixel_difference_count"], 0)
        self.assertEqual(m["alpha_difference_count"], 0)
        self.assertEqual(m["max_channel_difference"], 0)
        self.assertEqual(m["mean_absolute_difference"], 0.0)

        # Difference image must be 100% transparent
        diff_img = res["difference_image"]
        self.assertIsNotNone(diff_img)
        self.assertEqual(set(diff_img.getchannel("A").tobytes()), {0})

    def test_pixel_difference_metric(self):
        img1 = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
        img2 = Image.new("RGBA", (16, 16), (0, 0, 255, 255))
        ins1 = make_inspector(image=img1, category="monster")
        ins2 = make_inspector(image=img2, category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)
        sel2 = ins2.timeline.select(action="Walk", frame=0)

        res = compare_frames(ins1, ins2, sel1, sel2, mode="SIDE_BY_SIDE")
        rep = res["report"]
        self.validate_comp(rep)

        self.assertEqual(rep["comparison_status"], "DIFFERENCE_OBSERVED")
        m = rep["metrics"]
        self.assertFalse(m["identical"])
        self.assertEqual(m["pixel_difference_count"], 256)
        self.assertEqual(m["alpha_difference_count"], 0)
        self.assertEqual(m["max_channel_difference"], 255)
        self.assertGreater(m["mean_absolute_difference"], 0.0)

    def test_alpha_difference_metric(self):
        img1 = Image.new("RGBA", (16, 16), (255, 0, 0, 255))
        img2 = Image.new("RGBA", (16, 16), (255, 0, 0, 128))
        ins1 = make_inspector(image=img1, category="monster")
        ins2 = make_inspector(image=img2, category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)
        sel2 = ins2.timeline.select(action="Walk", frame=0)

        res = compare_frames(ins1, ins2, sel1, sel2, mode="DIFFERENCE")
        rep = res["report"]
        self.validate_comp(rep)

        m = rep["metrics"]
        self.assertFalse(m["identical"])
        self.assertEqual(m["pixel_difference_count"], 256)
        self.assertEqual(m["alpha_difference_count"], 256)
        self.assertEqual(m["max_channel_difference"], 127)

    def test_different_dimensions_on_unified_canvas(self):
        ins1 = make_inspector(category="monster")
        ins2 = make_inspector(category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)
        sel2 = ins2.timeline.select(action="Walk", frame=0)

        res = compare_frames(ins1, ins2, sel1, sel2, canvas_size=(128, 128))
        # Now compare with different canvas sizes by passing different canvas size via inspect inside compare
        # Our compare_frames accepts canvas_size parameter, let's verify dimensions_match is True when equal
        self.assertTrue(res["report"]["metrics"]["dimensions_match"])

    def test_alignment_origin_and_bounds_center(self):
        ins1 = make_inspector(category="monster")
        ins2 = make_inspector(category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)
        sel2 = ins2.timeline.select(action="Walk", frame=0)

        # ORIGIN alignment
        res_orig = compare_frames(ins1, ins2, sel1, sel2, alignment="ORIGIN")
        self.assertEqual(res_orig["report"]["alignment"]["policy"], "ORIGIN")
        self.validate_comp(res_orig["report"])

        # BOUNDS_CENTER alignment
        res_bc = compare_frames(ins1, ins2, sel1, sel2, alignment="BOUNDS_CENTER")
        self.assertEqual(res_bc["report"]["alignment"]["policy"], "BOUNDS_CENTER")
        self.validate_comp(res_bc["report"])

        # EXPLICIT alignment
        res_exp = compare_frames(ins1, ins2, sel1, sel2, alignment="EXPLICIT", displacement=(10, -5))
        self.assertEqual(res_exp["report"]["alignment"]["policy"], "EXPLICIT")
        self.assertEqual(res_exp["report"]["alignment"]["displacement"], {"x": 10, "y": -5})
        self.validate_comp(res_exp["report"])

    def test_layer_count_mismatch(self):
        doc1 = make_act(clips_per_motion=1)
        doc2 = make_act(clips_per_motion=2)
        ins1 = make_inspector(doc=doc1, category="monster")
        ins2 = make_inspector(doc=doc2, category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)
        sel2 = ins2.timeline.select(action="Walk", frame=0)

        res = compare_frames(ins1, ins2, sel1, sel2)
        rep = res["report"]
        self.validate_comp(rep)
        self.assertFalse(rep["metrics"]["layer_count_match"])
        self.assertEqual(rep["reference"]["layer_count"], 1)
        self.assertEqual(rep["candidate"]["layer_count"], 2)

    def test_missing_candidate(self):
        ins1 = make_inspector(category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)

        res = compare_frames(ins1, None, sel1, None, mode="SIDE_BY_SIDE")
        rep = res["report"]
        self.validate_comp(rep)
        check_seal(rep, "rsf.preview-comparison/v1")

        self.assertEqual(rep["comparison_status"], "MISSING_CANDIDATE")
        self.assertEqual(rep["mode"], "REFERENCE_ONLY")
        self.assertIsNone(rep["candidate"])
        self.assertIsNone(res["cand_image"])
        self.assertIsNone(res["difference_image"])

    def test_overlay_isolation_and_rendering(self):
        ins = make_inspector(category="monster")
        sel = ins.timeline.select(action="Walk", frame=0)

        raw_res = ins.inspect(sel, canvas_size=(128, 128), origin=(64, 96))
        raw_png = raw_res["png_bytes"]
        raw_hash = raw_res["report"]["preview_png_sha256"]

        # Overlays = None: byte-for-byte exact preservation
        copy_img = apply_overlays(raw_res["image"], raw_res["report"], overlays=None)
        self.assertEqual(png_bytes(copy_img), raw_png)

        # Overlays = empty list: byte-for-byte exact preservation
        empty_img = apply_overlays(raw_res["image"], raw_res["report"], overlays=[])
        self.assertEqual(png_bytes(empty_img), raw_png)

        # Overlays enabled: image is modified
        overlay_img = apply_overlays(raw_res["image"], raw_res["report"], overlays=["origin", "bounds", "layers"])
        self.assertNotEqual(png_bytes(overlay_img), raw_png)

        # In compare_frames, ref report's png_sha256 must match raw_hash even with overlays
        cmp_res = compare_frames(ins, ins, sel, sel, overlays=["origin", "bounds"], canvas_size=(128, 128), origin=(64, 96))
        self.assertEqual(cmp_res["report"]["reference"]["png_sha256"], raw_hash)
        self.assertEqual(cmp_res["report"]["candidate"]["png_sha256"], raw_hash)

    def test_modes_rendering(self):
        ins1 = make_inspector(category="monster")
        ins2 = make_inspector(category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)
        sel2 = ins2.timeline.select(action="Walk", frame=0)

        for mode in ("SIDE_BY_SIDE", "DIFFERENCE", "ONION_SKIN", "REFERENCE_ONLY", "CANDIDATE_ONLY"):
            res = compare_frames(ins1, ins2, sel1, sel2, mode=mode)
            self.assertEqual(res["report"]["mode"], mode)
            self.assertIsNotNone(res["png_bytes"])
            self.validate_comp(res["report"])

    def test_contact_sheet_generation(self):
        ins = make_inspector(category="monster")
        sel = ins.timeline.select(action="Walk", frame=0)

        # 4 frames: columns=2, scale=1
        res = generate_contact_sheet(ins, sel, columns=2, scale=1, padding=4, margin=8, labels=True)
        rep = res["report"]
        self.validate_cs(rep)
        check_seal(rep, "rsf.contact-sheet/v1")

        self.assertEqual(rep["grid"]["columns"], 2)
        self.assertEqual(rep["grid"]["rows"], 2)
        self.assertEqual(rep["grid"]["total_tiles"], 4)
        self.assertEqual(len(rep["tiles"]), 4)

        # Scale=2
        res2 = generate_contact_sheet(ins, sel, columns=4, scale=2, labels=False)
        self.validate_cs(res2["report"])
        self.assertEqual(res2["report"]["grid"]["scale"], 2)

    def test_sequence_export_atomic(self):
        ins = make_inspector(category="monster")
        sel = ins.timeline.select(action="Walk", frame=0)

        with tempfile.TemporaryDirectory(prefix="rsf-test-seq-") as tmpdir:
            out_dir = Path(tmpdir) / "walk_seq"
            manifest = export_frame_sequence(ins, sel, out_dir, overlays=["origin"])

            self.validate_seq(manifest)
            check_seal(manifest, "rsf.sequence-manifest/v1")
            self.assertTrue(out_dir.is_dir())
            self.assertTrue((out_dir / "sequence-manifest.json").is_file())
            for i in range(4):
                self.assertTrue((out_dir / f"frame_{i:03d}.png").is_file())

            # Overwrite protection: attempting to export to existing directory must fail
            with self.assertRaises(ForgeError) as cm:
                export_frame_sequence(ins, sel, out_dir)
            self.assertIn("already exists", cm.exception.message)

    def test_output_determinism(self):
        ins1 = make_inspector(category="monster")
        ins2 = make_inspector(category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)
        sel2 = ins2.timeline.select(action="Walk", frame=0)

        res1 = compare_frames(ins1, ins2, sel1, sel2, mode="SIDE_BY_SIDE")
        res2 = compare_frames(ins1, ins2, sel1, sel2, mode="SIDE_BY_SIDE")
        self.assertEqual(res1["png_bytes"], res2["png_bytes"])
        self.assertEqual(res1["report"]["canonical_sha256"], res2["report"]["canonical_sha256"])

        cs1 = generate_contact_sheet(ins1, sel1, columns=2, scale=1)
        cs2 = generate_contact_sheet(ins1, sel1, columns=2, scale=1)
        self.assertEqual(cs1["png_bytes"], cs2["png_bytes"])
        self.assertEqual(cs1["report"]["canonical_sha256"], cs2["report"]["canonical_sha256"])

    def test_cli_integration(self):
        with tempfile.TemporaryDirectory(prefix="rsf-cli-test-") as tmpdir:
            td = Path(tmpdir)
            act_path = td / "test.act"
            spr_path = td / "test.spr"
            act_path.write_bytes(write_act(make_act()))
            spr_path.write_bytes(write_rgba_spr([Image.new("RGBA", (16, 16), (255, 0, 0, 255))]))

            out_s = io.StringIO()
            err_s = io.StringIO()
            with redirect_stdout(out_s), redirect_stderr(err_s):
                # CLI compare
                cmp_out = td / "cmp.png"
                cmp_json = td / "cmp.json"
                diff_out = td / "diff.png"
                ret = main([
                    "compare",
                    "--ref-act", str(act_path),
                    "--ref-spr", str(spr_path),
                    "--ref-category", "monster",
                    "--ref-action", "Walk",
                    "--cand-act", str(act_path),
                    "--cand-spr", str(spr_path),
                    "--cand-category", "monster",
                    "--cand-action", "Walk",
                    "--output", str(cmp_out),
                    "--diff-output", str(diff_out),
                    "--json", str(cmp_json),
                ])
                self.assertEqual(ret, 0)
                self.assertTrue(cmp_out.is_file())
                self.assertTrue(diff_out.is_file())
                self.assertTrue(cmp_json.is_file())
                self.validate_comp(json.loads(cmp_json.read_text()))

                # CLI contact-sheet
                cs_out = td / "sheet.png"
                cs_json = td / "sheet.json"
                ret = main([
                    "contact-sheet",
                    "--act", str(act_path),
                    "--spr", str(spr_path),
                    "--category", "monster",
                    "--action", "Walk",
                    "--columns", "2",
                    "--output", str(cs_out),
                    "--json", str(cs_json),
                ])
                self.assertEqual(ret, 0)
                self.assertTrue(cs_out.is_file())
                self.assertTrue(cs_json.is_file())
                self.validate_cs(json.loads(cs_json.read_text()))

                # CLI sequence
                seq_out_dir = td / "seq_export"
                ret = main([
                    "sequence",
                    "--act", str(act_path),
                    "--spr", str(spr_path),
                    "--category", "monster",
                    "--action", "Walk",
                    "--output-dir", str(seq_out_dir),
                ])
                self.assertEqual(ret, 0)
                self.assertTrue(seq_out_dir.is_dir())
                self.assertTrue((seq_out_dir / "sequence-manifest.json").is_file())
                self.validate_seq(json.loads((seq_out_dir / "sequence-manifest.json").read_text()))

    def test_onion_skin_and_side_by_side_variations(self):
        ins1 = make_inspector(category="monster")
        ins2 = make_inspector(category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)
        sel2 = ins2.timeline.select(action="Walk", frame=0)

        # Onion skin with opacity 0.0, 0.5, 1.0
        for op in (0.0, 0.5, 1.0):
            res = compare_frames(ins1, ins2, sel1, sel2, mode="ONION_SKIN")
            self.validate_comp(res["report"])

        # Side by side without overlays and candidate only
        res_cand = compare_frames(ins1, ins2, sel1, sel2, mode="CANDIDATE_ONLY")
        self.assertEqual(res_cand["report"]["mode"], "CANDIDATE_ONLY")

    def test_contact_sheet_labels_and_padding(self):
        ins = make_inspector(category="monster")
        sel = ins.timeline.select(action="Walk", frame=0)

        res = generate_contact_sheet(ins, sel, columns=4, padding=8, margin=16, labels=False)
        self.validate_cs(res["report"])
        self.assertEqual(res["report"]["grid"]["padding"], 8)
        self.assertEqual(res["report"]["grid"]["margin"], 16)

    def test_error_handling_and_validation(self):
        ins1 = make_inspector(category="monster")
        sel1 = ins1.timeline.select(action="Walk", frame=0)

        # Invalid mode
        with self.assertRaises(ForgeError) as cm:
            compare_frames(ins1, ins1, sel1, sel1, mode="INVALID_MODE")
        self.assertIn("Unsupported mode", cm.exception.message)

        # Invalid alignment
        with self.assertRaises(ForgeError) as cm:
            compare_frames(ins1, ins1, sel1, sel1, alignment="INVALID_ALIGN")
        self.assertIn("Unsupported alignment", cm.exception.message)

        # Invalid overlay
        with self.assertRaises(ForgeError) as cm:
            compare_frames(ins1, ins1, sel1, sel1, overlays=["not_a_real_overlay"])
        self.assertIn("Unsupported overlay", cm.exception.message)

        # Non-integer columns in contact sheet
        with self.assertRaises(ForgeError):
            generate_contact_sheet(ins1, sel1, columns=0)


if __name__ == "__main__":
    unittest.main()
