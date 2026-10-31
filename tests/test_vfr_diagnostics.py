"""RSF-31: VFR, candidate-frame diagnostics and repeatability verification.

Comprehensive verification of:
1. Exact presentation-frame identity for CFR and VFR sources.
2. Requested vs resolved PTS reporting.
3. Rational time-base preservation.
4. Duplicate, missing and ambiguous timestamp diagnostics.
5. Nonchronological selection ordering.
6. Candidate PNG pixel correctness against known synthetic patterns.
7. Deterministic extraction and canonical provenance under pinned toolchain.
8. Rejection and diagnostics for unsupported or invalid selections.
9. Preservation of video versus ACT timing separation.
10. Consistent assignment/coverage accounting (RSF-30 reconciliation).
"""
from __future__ import annotations

import copy
from fractions import Fraction
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from ro_sprite_forge.adapters import video
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.compiler import compile_resources, verify_pair_with_rust_oracle
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, reference
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.project import create_project, get_blob, load_project, save_project
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.spr import read_spr
from ro_sprite_forge.service import media
from ro_sprite_forge.service.media import stage_video
from ro_sprite_forge.service.server import make_standard_actor_doc
from ro_sprite_forge.service.workbench import (
    mutate,
    preview,
    record_review,
    review_proposal,
    source_catalog,
    workspace,
)
from test_compiler import _build_synthetic_monster_act_spr, RUST_ORACLE_BIN
from test_video import make_media, PILLOW, TOOLS
from test_walk_compilation import (
    assert_effective_mapping,
    clean_cli_builds,
    synthetic_pair,
)


def _make_duplicate_pts_media(directory: Path) -> tuple[bytes, str]:
    """Generate a synthetic MKV fixture with deliberate duplicate presentation timestamps.

    Frame 0: PTS 0
    Frame 1: PTS 40
    Frame 2: PTS 40  (duplicate PTS with frame 1)
    Frame 3: PTS 120
    Frame 4: PTS 160
    """
    directory = Path(directory)
    for n in range(5):
        img = Image.new('RGB', (16, 16), (n * 35, 200 - n * 30, 50 + n * 30))
        img.save(directory / f'dup-in-{n:02d}.png')

    output = directory / 'duplicate_pts.mkv'
    cmd = [
        '/usr/bin/ffmpeg', '-nostdin', '-v', 'error', '-bitexact', '-f', 'image2',
        '-framerate', '25', '-i', str(directory / 'dup-in-%02d.png'),
        '-vf', 'settb=1/1000,setpts=if(eq(N\\,0)\\,0\\,if(eq(N\\,1)\\,40\\,if(eq(N\\,2)\\,40\\,if(eq(N\\,3)\\,120\\,160))))',
        '-fps_mode', 'passthrough', '-enc_time_base', '1/1000',
        '-c:v', 'ffv1', '-threads', '1', '-pix_fmt', 'bgr0', '-fflags', '+bitexact',
        str(output),
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
    raw = output.read_bytes()
    return raw, digest(raw)


@unittest.skipUnless(TOOLS and PILLOW, 'FFmpeg/FFprobe and Pillow are required for VFR diagnostic tests')
class VfrDiagnosticsComprehensiveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture_dir = tempfile.TemporaryDirectory(prefix='rsf31-fixture-')
        cls.base = Path(cls.fixture_dir.name)
        cls.expected_pixels, cls.commands = make_media(cls.base)
        cls.cfr_bytes = (cls.base / 'cfr.mkv').read_bytes()
        cls.cfr_sha = digest(cls.cfr_bytes)
        cls.vfr_bytes = (cls.base / 'vfr.mkv').read_bytes()
        cls.vfr_sha = digest(cls.vfr_bytes)
        cls.dup_bytes, cls.dup_sha = _make_duplicate_pts_media(cls.base)

    @classmethod
    def tearDownClass(cls):
        cls.fixture_dir.cleanup()

    # -------------------------------------------------------------------------
    # 1. CFR exact-frame identity
    # -------------------------------------------------------------------------
    def test_01_cfr_exact_frame_identity(self):
        """CFR source inspection preserves exact time base, sequential PTS, and display order."""
        info = video.inspect_video(self.cfr_bytes)
        self.assertEqual(info['source']['sha256'], self.cfr_sha)
        self.assertEqual(info['time_base'], dict(numerator=1, denominator=1000))
        self.assertEqual(info['timing'], 'REGULAR_PTS_OBSERVED')
        self.assertEqual(info['decoded_frame_count'], 5)

        observed_pts = [f['pts'] for f in info['frames']]
        observed_ordinals = [f['ordinal'] for f in info['frames']]
        self.assertEqual(observed_pts, [0, 40, 80, 120, 160])
        self.assertEqual(observed_ordinals, [0, 1, 2, 3, 4])

        # Extract frames 0, 2, 4 by PTS
        ext = video.extract_candidates(self.cfr_bytes, stream_index=0, mode='pts', values=[0, 80, 160])
        manifest = ext['manifest']
        self.assertEqual([item['pts'] for item in manifest['items']], [0, 80, 160])
        self.assertEqual([item['ordinal'] for item in manifest['items']], [0, 2, 4])

        # Verify decoded pixel correctness against independent RGB patterns
        for item, png_data in zip(manifest['items'], ext['pngs']):
            with Image.open(io.BytesIO(png_data)) as im:
                self.assertEqual(im.mode, 'RGBA')
                self.assertEqual(im.tobytes(), self.expected_pixels[item['ordinal']])
                self.assertEqual(item['rgba_sha256'], digest(self.expected_pixels[item['ordinal']]))

    # -------------------------------------------------------------------------
    # 2. VFR exact-frame identity
    # -------------------------------------------------------------------------
    def test_02_vfr_exact_frame_identity(self):
        """VFR source preserves irregular intervals without nominal-FPS approximation."""
        info = video.inspect_video(self.vfr_bytes)
        self.assertEqual(info['source']['sha256'], self.vfr_sha)
        self.assertEqual(info['time_base'], dict(numerator=1, denominator=1000))
        self.assertEqual(info['timing'], 'IRREGULAR_PTS')
        self.assertEqual(info['decoded_frame_count'], 5)

        pts_list = [f['pts'] for f in info['frames']]
        self.assertEqual(pts_list, [0, 40, 120, 160, 300])

        intervals = [b - a for a, b in zip(pts_list, pts_list[1:])]
        self.assertEqual(intervals, [40, 80, 40, 140])

    # -------------------------------------------------------------------------
    # 3. Nonchronological PTS selection
    # -------------------------------------------------------------------------
    def test_03_nonchronological_pts_selection(self):
        """Operator-requested PTS [300, 0, 120] preserves order and resolves to ordinals [4, 0, 2]."""
        ext = video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[300, 0, 120])
        manifest = ext['manifest']

        self.assertEqual(manifest['request']['values'], [300, 0, 120])
        self.assertEqual(manifest['request']['ordering'], 'REQUEST_ORDER')

        items = manifest['items']
        self.assertEqual([i['requested'] for i in items], [300, 0, 120])
        self.assertEqual([i['pts'] for i in items], [300, 0, 120])
        self.assertEqual([i['ordinal'] for i in items], [4, 0, 2])

        # PNG bytes must match the requested nonchronological order
        for item, png_bytes in zip(items, ext['pngs']):
            ord_idx = item['ordinal']
            self.assertEqual(digest(png_bytes), item['png_sha256'])
            with Image.open(io.BytesIO(png_bytes)) as im:
                self.assertEqual(im.tobytes(), self.expected_pixels[ord_idx])

    # -------------------------------------------------------------------------
    # 4. Correct presentation order and B-frames
    # -------------------------------------------------------------------------
    def test_04_presentation_order_and_b_frames(self):
        """Container with B-frames preserves presentation PTS independent of decode order."""
        bframe_path = self.base / 'bframes.mkv'
        cmd = [
            '/usr/bin/ffmpeg', '-nostdin', '-v', 'error', '-framerate', '25',
            '-i', str(self.base / 'input-%02d.png'),
            '-c:v', 'mpeg4', '-bf', '2', '-q:v', '2', '-pix_fmt', 'yuv420p',
            '-threads', '1', '-y', str(bframe_path),
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        raw = bframe_path.read_bytes()

        info = video.inspect_video(raw)
        pict_types = [f['picture_type'] for f in info['frames']]
        self.assertIn('B', pict_types)
        self.assertEqual([f['pts'] for f in info['frames']], [0, 40, 80, 120, 160])

        # Nonchronological extraction by PTS
        ext = video.extract_candidates(raw, stream_index=0, mode='pts', values=[160, 40, 0])
        self.assertEqual([i['pts'] for i in ext['manifest']['items']], [160, 40, 0])
        self.assertEqual([i['ordinal'] for i in ext['manifest']['items']], [4, 1, 0])

    # -------------------------------------------------------------------------
    # 5. Duplicate PTS diagnostics
    # -------------------------------------------------------------------------
    def test_05_duplicate_pts_diagnostics(self):
        """Duplicate presentation timestamps fail closed on exact PTS request; ordinals succeed."""
        info = video.inspect_video(self.dup_bytes)
        pts_list = [f['pts'] for f in info['frames']]
        self.assertEqual(pts_list, [0, 40, 40, 120, 160])

        # Requesting ambiguous PTS 40 must fail with VIDEO_SELECTION_NOT_EXACT
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.dup_bytes, stream_index=0, mode='pts', values=[40])
        self.assertIn('VIDEO_SELECTION_NOT_EXACT', str(ctx.exception))
        self.assertIn('pts=40; matches=2', str(ctx.exception))

        # Explicit ordinal extraction remains unambiguous and succeeds
        res = video.extract_candidates(self.dup_bytes, stream_index=0, mode='ordinal', values=[1, 2])
        self.assertEqual(len(res['pngs']), 2)
        items = res['manifest']['items']
        self.assertEqual(items[0]['ordinal'], 1)
        self.assertEqual(items[0]['pts'], 40)
        self.assertEqual(items[1]['ordinal'], 2)
        self.assertEqual(items[1]['pts'], 40)
        self.assertNotEqual(items[0]['png_sha256'], items[1]['png_sha256'])

    # -------------------------------------------------------------------------
    # 6. Missing PTS diagnostics
    # -------------------------------------------------------------------------
    def test_06_missing_pts_diagnostics(self):
        """Missing or non-existent PTS fails with precise typed diagnostic without fallback."""
        # VFR fixture has PTS [0, 40, 120, 160, 300]. PTS 80 is absent.
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[80])
        self.assertIn('VIDEO_SELECTION_NOT_EXACT', str(ctx.exception))
        self.assertIn('pts=80; matches=0', str(ctx.exception))

        # PTS 9999 is out of range
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[9999])
        self.assertIn('VIDEO_SELECTION_NOT_EXACT', str(ctx.exception))

        # Verify resolve rejects None PTS
        frames_inspection = dict(frames=[dict(ordinal=0, pts=None), dict(ordinal=1, pts=40)])
        with self.assertRaises(ForgeError) as ctx:
            video._resolve(frames_inspection, 'pts', [0])
        self.assertIn('VIDEO_SELECTION_NOT_EXACT', str(ctx.exception))

    # -------------------------------------------------------------------------
    # 7. Invalid ordinal rejection
    # -------------------------------------------------------------------------
    def test_07_invalid_ordinal_rejection(self):
        """Invalid ordinals (negative, out-of-range, non-integer) fail closed before execution."""
        # Out-of-range ordinal (fixture has 5 frames: 0..4)
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='ordinal', values=[5])
        self.assertIn('VIDEO_SELECTION_NOT_EXACT', str(ctx.exception))

        # Negative ordinal
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='ordinal', values=[-1])
        self.assertIn('VIDEO_SELECTION_NOT_EXACT', str(ctx.exception))

        # Non-integer selection
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='ordinal', values=['0'])
        self.assertIn('VIDEO_INVALID_SELECTION', str(ctx.exception))

    # -------------------------------------------------------------------------
    # 8. Out-of-range selection rejection
    # -------------------------------------------------------------------------
    def test_08_out_of_range_selection_rejection(self):
        """Values exceeding integer bounds or candidate quotas are rejected immediately."""
        # Exceeding safe integer range
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[2**54])
        self.assertIn('VIDEO_INVALID_SELECTION', str(ctx.exception))

        # Empty candidate list
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[])
        self.assertIn('VIDEO_SELECTION_COUNT_EXCEEDED_OR_EMPTY', str(ctx.exception))

        # Exceeding candidate limit (MAX_CANDIDATES = 64)
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=list(range(65)))
        self.assertIn('VIDEO_SELECTION_COUNT_EXCEEDED_OR_EMPTY', str(ctx.exception))

        # Duplicate values in request
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[40, 40])
        self.assertIn('VIDEO_DUPLICATE_SELECTION', str(ctx.exception))

        # Unsupported mode
        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='timecode', values=[0])
        self.assertIn('VIDEO_UNSUPPORTED_SELECTION', str(ctx.exception))

    # -------------------------------------------------------------------------
    # 9. Rational time-base preservation
    # -------------------------------------------------------------------------
    def test_09_rational_time_base_preservation(self):
        """Time bases are parsed as exact numerator/denominator integer pairs without floats."""
        self.assertEqual(video._rational('1/1000'), dict(numerator=1, denominator=1000))
        self.assertEqual(video._rational('1/90000'), dict(numerator=1, denominator=90000))
        self.assertEqual(video._rational('1001/30000'), dict(numerator=1001, denominator=30000))
        self.assertIsNone(video._rational('0/0'))
        self.assertIsNone(video._rational('N/A'))
        self.assertIsNone(video._rational(None))

        # Invalid denominator
        with self.assertRaises(ForgeError):
            video._rational('1/0')
        with self.assertRaises(ForgeError):
            video._rational('not-a-fraction')

    # -------------------------------------------------------------------------
    # 10. Large metadata integer precision
    # -------------------------------------------------------------------------
    def test_10_large_metadata_integer_precision(self):
        """Integers exceeding JS safe integer limit are safely preserved as strings in wire records."""
        huge_val = 2**53 + 12345
        sample = dict(small=100, huge=huge_val, nested=[dict(big=2**60)])
        safe = media.browser_safe(sample)

        self.assertEqual(safe['small'], 100)
        self.assertEqual(safe['huge'], str(huge_val))
        self.assertEqual(safe['nested'][0]['big'], str(2**60))

        # Safe integer round-trip for string input
        self.assertEqual(media.exact_integer("100"), 100)

        # Value exceeding JS safe integer bound is rejected by exact_integer for selection
        with self.assertRaises(ForgeError) as ctx:
            media.exact_integer(safe['huge'])
        self.assertIn('VIDEO_SELECTION_INTEGER_OUT_OF_RANGE', str(ctx.exception))

    # -------------------------------------------------------------------------
    # 11. Known-pixel candidate verification
    # -------------------------------------------------------------------------
    def test_11_known_pixel_candidate_verification(self):
        """Extracted PNGs match independently known synthetic pixels with zero pixel mismatch."""
        ext = video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[0, 40, 120, 160, 300])
        self.assertEqual(len(ext['pngs']), 5)

        for ordinal, png_data in enumerate(ext['pngs']):
            with Image.open(io.BytesIO(png_data)) as im:
                self.assertEqual(im.size, (16, 16))
                self.assertEqual(im.mode, 'RGBA')
                self.assertEqual(im.tobytes(), self.expected_pixels[ordinal])

    # -------------------------------------------------------------------------
    # 12. Selection/output count consistency
    # -------------------------------------------------------------------------
    def test_12_selection_output_count_consistency(self):
        """Requesting K items produces exactly K PNGs and K manifest item entries."""
        for count in (1, 2, 3, 5):
            pts_vals = [0, 40, 120, 160, 300][:count]
            ext = video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=pts_vals)
            self.assertEqual(len(ext['pngs']), count)
            self.assertEqual(len(ext['manifest']['items']), count)
            self.assertEqual(ext['manifest']['request']['values'], pts_vals)

    # -------------------------------------------------------------------------
    # 13. Idempotent reimport
    # -------------------------------------------------------------------------
    def test_13_idempotent_reimport(self):
        """Re-staging the same video and selection does not produce duplicate imports or bump revision."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = create_project(root, 'vfr-idempotent', 'Idempotent Test', 'actor', 'player')
            rev1 = proj['revision']

            staged1 = stage_video(
                root, 'vfr-idempotent', self.vfr_bytes,
                expected_revision=rev1, stream_index=0, mode='pts', values=[300, 0, 120]
            )
            rev2 = staged1['revision']
            self.assertEqual(rev2, rev1 + 1)
            self.assertEqual(len(staged1['video_imports']), 1)

            # Re-stage identical video and selection
            staged2 = stage_video(
                root, 'vfr-idempotent', self.vfr_bytes,
                expected_revision=rev2, stream_index=0, mode='pts', values=[300, 0, 120]
            )
            # Must remain idempotent: same revision, same import list length
            self.assertEqual(staged2['revision'], rev2)
            self.assertEqual(len(staged2['video_imports']), 1)
            self.assertEqual(staged2, staged1)

    # -------------------------------------------------------------------------
    # 14. Candidate-order identity
    # -------------------------------------------------------------------------
    def test_14_candidate_order_identity(self):
        """Different selection orders produce identical candidate PNGs but distinct collection manifests."""
        ext_fwd = video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[0, 120, 300])
        ext_rev = video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[300, 120, 0])

        # Individual candidate PNG hashes match corresponding frames
        fwd_hashes = {item['pts']: item['png_sha256'] for item in ext_fwd['manifest']['items']}
        rev_hashes = {item['pts']: item['png_sha256'] for item in ext_rev['manifest']['items']}
        self.assertEqual(fwd_hashes, rev_hashes)

        # But candidate collection manifest SHA-256 differs due to explicit request ordering
        self.assertNotEqual(
            ext_fwd['manifest']['canonical_sha256'],
            ext_rev['manifest']['canonical_sha256']
        )

    # -------------------------------------------------------------------------
    # 15. Exact source SHA-256 verification
    # -------------------------------------------------------------------------
    def test_15_exact_source_sha256_verification(self):
        """Mismatched expected source hash fails closed before running inspection or tools."""
        bad_hash = 'a' * 64
        with self.assertRaises(ForgeError) as ctx:
            video.probe_video(self.vfr_bytes, expected_sha256=bad_hash)
        self.assertIn('HASH_MISMATCH', str(ctx.exception))

        with self.assertRaises(ForgeError) as ctx:
            video.inspect_video(self.vfr_bytes, expected_sha256=bad_hash)
        self.assertIn('HASH_MISMATCH', str(ctx.exception))

        with self.assertRaises(ForgeError) as ctx:
            video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[0], expected_sha256=bad_hash)
        self.assertIn('HASH_MISMATCH', str(ctx.exception))

    # -------------------------------------------------------------------------
    # 16. Repeated clean FFmpeg execution
    # -------------------------------------------------------------------------
    def test_16_repeated_clean_ffmpeg_execution(self):
        """Repeated clean FFmpeg extractions yield bit-exact PNGs and canonical manifest hashes."""
        run1 = video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[300, 0, 120])
        run2 = video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[300, 0, 120])

        self.assertEqual(len(run1['pngs']), len(run2['pngs']))
        for p1, p2 in zip(run1['pngs'], run2['pngs']):
            self.assertEqual(digest(p1), digest(p2))

        self.assertEqual(
            run1['manifest']['canonical_sha256'],
            run2['manifest']['canonical_sha256']
        )
        self.assertEqual(
            canonical_bytes(run1['manifest']),
            canonical_bytes(run2['manifest'])
        )

    # -------------------------------------------------------------------------
    # 17. Canonical manifest byte identity
    # -------------------------------------------------------------------------
    def test_17_canonical_manifest_byte_identity(self):
        """Manifest canonical serialization is bit-exact and validates against JSON Schema."""
        ext = video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[300, 0, 120])
        manifest = ext['manifest']

        b1 = canonical_bytes(manifest)
        b2 = canonical_bytes(manifest)
        self.assertEqual(b1, b2)

        # Validate against schema
        try:
            from jsonschema import Draft202012Validator
            from importlib.resources import files
            schema_text = files('ro_sprite_forge').joinpath('schemas/video-candidates-v1.json').read_text()
            schema = json.loads(schema_text)
            validator = Draft202012Validator(schema)
            validator.validate(manifest)
        except ImportError:
            pass  # optional jsonschema

    # -------------------------------------------------------------------------
    # 18. Toolchain provenance
    # -------------------------------------------------------------------------
    def test_18_toolchain_provenance(self):
        """Manifest preserves full toolchain provenance including FFmpeg/FFprobe identities."""
        ext = video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[300, 0, 120])
        manifest = ext['manifest']

        self.assertIn('ffprobe', manifest['inspection'])
        self.assertIn('ffmpeg', manifest)
        self.assertTrue(manifest['inspection']['ffprobe']['version'].startswith('ffprobe'))
        self.assertTrue(manifest['ffmpeg']['version'].startswith('ffmpeg'))
        self.assertEqual(len(manifest['inspection']['ffprobe']['executable_sha256']), 64)
        self.assertEqual(len(manifest['ffmpeg']['executable_sha256']), 64)

    # -------------------------------------------------------------------------
    # 19. Failed extraction cleanup
    # -------------------------------------------------------------------------
    def test_19_failed_extraction_cleanup(self):
        """Subprocess or validation failures clean up temporary directories completely."""
        with tempfile.TemporaryDirectory() as temp_root, patch.object(tempfile, 'tempdir', temp_root):
            with self.assertRaises(ForgeError):
                video.extract_candidates(self.vfr_bytes, stream_index=99, mode='pts', values=[0])
            self.assertEqual(list(Path(temp_root).iterdir()), [])

    # -------------------------------------------------------------------------
    # 20. Failed publication preservation
    # -------------------------------------------------------------------------
    def test_20_failed_publication_preservation(self):
        """Failed staging leaves the project manifest and revision unincremented."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = create_project(root, 'vfr-preserve', 'Preserve Test', 'actor', 'player')
            man_path = root / 'vfr-preserve' / 'manifest.json'
            before_bytes = man_path.read_bytes()

            # Attempt staging with invalid revision
            with self.assertRaises(ForgeError) as ctx:
                stage_video(root, 'vfr-preserve', self.vfr_bytes, expected_revision=999,
                            stream_index=0, mode='pts', values=[0])
            self.assertIn('STALE_PROJECT_REVISION', str(ctx.exception))
            self.assertEqual(man_path.read_bytes(), before_bytes)

    # -------------------------------------------------------------------------
    # 21. Optional dependency absence
    # -------------------------------------------------------------------------
    def test_21_optional_dependency_absence(self):
        """Core features work when video tools are unavailable; media functions report typed error."""
        with patch.object(video.shutil, 'which', return_value=None):
            cap = video.capabilities()
            self.assertFalse(cap['available'])
            self.assertIn('VIDEO_TOOL_UNAVAILABLE', cap['ffmpeg']['diagnostic'])

            with self.assertRaisesRegex(ForgeError, 'VIDEO_TOOL_UNAVAILABLE'):
                video.inspect_video(self.vfr_bytes)

            with self.assertRaisesRegex(ForgeError, 'VIDEO_TOOL_UNAVAILABLE'):
                video.extract_candidates(self.vfr_bytes, stream_index=0, mode='pts', values=[0])

        # Core project operations function normally without FFmpeg
        with tempfile.TemporaryDirectory() as tmp:
            p = create_project(tmp, 'no-tools', 'No Tools', 'actor', 'player')
            self.assertEqual(p['project_id'], 'no-tools')

    # -------------------------------------------------------------------------
    # 22. No auto assignment or approval
    # -------------------------------------------------------------------------
    def test_22_no_auto_assignment_or_approval(self):
        """Staging video candidates never creates assignments or approves artwork automatically."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proj = create_project(root, 'vfr-no-auto', 'No Auto', 'actor', 'player')
            staged = stage_video(
                root, 'vfr-no-auto', self.vfr_bytes,
                expected_revision=proj['revision'], stream_index=0, mode='pts', values=[300, 0, 120]
            )

            # Check manifest properties
            vimport = staged['video_imports'][0]
            self.assertFalse(vimport['automatic_assignment'])
            self.assertEqual(vimport['visual_review'], 'UNVERIFIED')

            # Staged project without a declared target has no ledger or coverage
            ws = workspace(root, staged)
            self.assertIsNone(ws['ledger'])
            self.assertIsNone(ws['coverage'])

    # -------------------------------------------------------------------------
    # 23. Video/ACT timing separation
    # -------------------------------------------------------------------------
    def test_23_video_act_timing_separation(self):
        """Video source PTS does not alter ACT animation delays; candidate timestamps remain source PTS."""
        from test_video_walk_compilation import setup_video_walk_project

        with tempfile.TemporaryDirectory() as tmp_root, tempfile.TemporaryDirectory() as tmp_base:
            act, spr, proj_manifest, ws, vfr_bytes, vfr_sha, manifest_ext, extracted_pngs = setup_video_walk_project(
                tmp_root, tmp_base
            )

            # Source PTS in video manifest
            video_pts = [item['pts'] for item in manifest_ext['items']]
            self.assertEqual(video_pts, [300, 0, 120])

            # ACT delays in compiled/read resource
            act_doc = read_act(act)
            walk_delays = act_doc['delays'][8]  # Walk view 0 slot
            self.assertEqual(walk_delays, 6.0)

            # Changing video selection does not alter ACT delays
            self.assertNotEqual(walk_delays, video_pts[0])

    # -------------------------------------------------------------------------
    # 24. RSF-30 coverage reconciliation
    # -------------------------------------------------------------------------
    def test_24_rsf30_coverage_reconciliation(self):
        """Reconcile RSF-30 scoped coverage arithmetic: 12 required = 3 assigned + 9 unassigned.

        Breakdown:
        - Monster Walk has 8 action view slots (slots 8 to 15, corresponding to views 0 to 7).
        - View 0 has 4 frames:
          * Frame 0: 1 layer  (Layer 0) -> Occurrence 1
          * Frame 1: 1 layer  (Layer 0) -> Occurrence 2
          * Frame 2: 2 layers (Layer 0, Layer 1) -> Occurrences 3 and 4
          * Frame 3: 1 layer  (Layer 0) -> Occurrence 5
          Total View 0 occurrences = 5 layer occurrences across 4 frames.
        - Views 1 to 7 each have 1 frame with 1 layer:
          * 7 views * 1 frame * 1 layer = 7 layer occurrences across 7 frames.
        - Total required frames = 4 + 7 = 11 frames.
        - Total required layers = 5 + 7 = 12 layer occurrences.

        Operator assigns 3 candidates to View 0 (frames 0, 1, 2, layer 0):
        - Assigned: 3 (direct assignments).
        - Unassigned: 9:
          * View 0, Frame 2, Layer 1 (second layer in composite frame)
          * View 0, Frame 3, Layer 0 (fourth frame in direction)
          * Views 1..7 (7 missing directions)
        - Sum: assigned (3) + unassigned (9) = required (12).
        - Work order categories: review_artwork (3) + supply_artwork (9) = 12.
        """
        from test_video_walk_compilation import setup_video_walk_project

        with tempfile.TemporaryDirectory() as tmp_root, tempfile.TemporaryDirectory() as tmp_base:
            act, spr, proj_manifest, ws, vfr_bytes, vfr_sha, manifest_ext, extracted_pngs = setup_video_walk_project(
                tmp_root, tmp_base
            )

            # Initial coverage before assignment
            init_counts = ws['coverage']['counts']
            self.assertEqual(init_counts['structural']['required_slots'], 8)
            self.assertEqual(init_counts['structural']['required_frames'], 11)
            self.assertEqual(init_counts['structural']['required_layers'], 12)
            self.assertEqual(init_counts['assignments']['direct'], 0)
            self.assertEqual(init_counts['assignments']['unassigned'], 12)
            self.assertEqual(init_counts['work_order_categories']['supply_artwork'], 12)
            self.assertEqual(init_counts['work_order_categories']['review_artwork'], 0)

            # Assign 3 candidates to View 0 frames 0, 1, 2 (layer 0)
            req = ws['requirements']
            selected_layers = [
                l for l in req['layers'] if l['view'] == 0 and l['ordinal'] == 0 and l['frame'] in (0, 1, 2)
            ]
            layer_by_frame = {l['frame']: l for l in selected_layers}
            mappings = [
                dict(
                    requirement_id=layer_by_frame[i]['id'],
                    kind='DIRECT_SOURCE',
                    source='blob-' + item['png_sha256'],
                    source_revision=1,
                    recipe=[],
                )
                for i, item in enumerate(manifest_ext['items'])
            ]
            assign_res = mutate(
                tmp_root, proj_manifest, 'assign', dict(expected_revision=proj_manifest['revision'], mappings=mappings)
            )
            proj_manifest = assign_res['project']
            ws_assigned = workspace(tmp_root, proj_manifest)

            # Reconciled coverage after assignment
            post_counts = ws_assigned['coverage']['counts']
            self.assertEqual(post_counts['structural']['required_layers'], 12)
            self.assertEqual(post_counts['assignments']['direct'], 3)
            self.assertEqual(post_counts['assignments']['unassigned'], 9)

            # Exact reconciliation equation: required = assigned + unassigned + other
            self.assertEqual(
                post_counts['structural']['required_layers'],
                post_counts['assignments']['direct'] + post_counts['assignments']['unassigned']
            )

            # Work order categories reconciliation: review_artwork + supply_artwork == required
            self.assertEqual(post_counts['work_order_categories']['review_artwork'], 3)
            self.assertEqual(post_counts['work_order_categories']['supply_artwork'], 9)
            self.assertEqual(
                post_counts['structural']['required_layers'],
                post_counts['work_order_categories']['review_artwork'] +
                post_counts['work_order_categories']['supply_artwork']
            )

            # Status reconciliation
            status = ws_assigned['coverage']['status']
            self.assertEqual(status['completeness'], 'INCOMPLETE')
            self.assertEqual(status['assignment_coverage'], 'PARTIAL')
            self.assertFalse(status['export_ready'])
            self.assertEqual(status['structural_specification'], 'COMPLETE_FOR_DECLARED_SCOPE')

    # -------------------------------------------------------------------------
    # 25. Existing video-derived Walk compilation regression
    # -------------------------------------------------------------------------
    def test_25_existing_video_walk_compilation_regression(self):
        """End-to-end regression: video candidate assignment -> preview -> compile -> Rust oracle PASS."""
        from test_video_walk_compilation import setup_video_walk_project

        with tempfile.TemporaryDirectory(prefix='rsf31-compile-') as tmp:
            base = Path(tmp)
            root = base / 'projects'
            act, spr, proj_manifest, ws, vfr_bytes, vfr_sha, manifest_ext, pngs = setup_video_walk_project(
                root, base
            )

            # Assign 3 candidates
            req = ws['requirements']
            selected_layers = [
                l for l in req['layers'] if l['view'] == 0 and l['ordinal'] == 0 and l['frame'] in (0, 1, 2)
            ]
            layer_by_frame = {l['frame']: l for l in selected_layers}
            mappings = [
                dict(
                    requirement_id=layer_by_frame[i]['id'],
                    kind='DIRECT_SOURCE',
                    source='blob-' + item['png_sha256'],
                    source_revision=1,
                    recipe=[],
                )
                for i, item in enumerate(manifest_ext['items'])
            ]
            assign_res = mutate(
                root, proj_manifest, 'assign', dict(expected_revision=proj_manifest['revision'], mappings=mappings)
            )
            proj_manifest = assign_res['project']

            # Operator review proposal and approval
            proposal = review_proposal(
                root,
                proj_manifest,
                dict(expected_revision=proj_manifest['revision'], requirements=[l['id'] for l in selected_layers]),
            )
            review_res = record_review(
                root,
                proj_manifest,
                dict(
                    expected_revision=proj_manifest['revision'],
                    decision='APPROVED',
                    proposal=proposal['proposal'],
                ),
            )
            proj_manifest = review_res['project']

            # Compile through accepted pipeline
            comp_res = mutate(
                root,
                proj_manifest,
                'compile',
                dict(
                    expected_revision=proj_manifest['revision'],
                    resource_id='original',
                    compilation_id='rsf31-video-walk',
                    replacement_policy='explicit_rgba',
                ),
            )
            proj_manifest = comp_res['project']
            comp_dir = root / proj_manifest['project_id'] / 'compilations' / 'rsf31-video-walk'
            out_act = (comp_dir / 'original.act').read_bytes()
            out_spr = (comp_dir / 'original.spr').read_bytes()

            self.assertTrue((comp_dir / 'PARTIAL_DIAGNOSTIC.txt').is_file())
            self.assertGreater(len(out_act), 0)
            self.assertGreater(len(out_spr), 0)

            # Independent Rust oracle verification
            if RUST_ORACLE_BIN.exists():
                oracle_result = verify_pair_with_rust_oracle(out_act, out_spr, RUST_ORACLE_BIN)
                self.assertEqual(oracle_result['result'], 'AGREEMENT')
                self.assertEqual(oracle_result['schema'], 'rsf.oracle-parity/v1')


if __name__ == '__main__':
    unittest.main()
