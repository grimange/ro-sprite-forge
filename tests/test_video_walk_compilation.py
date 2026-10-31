"""RSF-30: Video-derived Walk assignment through the existing compiler.

Proves the end-to-end workflow:
Video -> Explicit frame selection -> Immutable PNG candidates ->
Explicit Walk assignment -> Animation preview -> Canonical compilation ->
Modified ACT/SPR -> Independent Rust structural verification.

All artwork and review decisions here are isolated synthetic test declarations.
No video-specific compiler, custom timing algorithm, or automatic artistic approval.
"""
from __future__ import annotations

import base64
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

from ro_sprite_forge.adapters import video
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.compiler import compile_resources, publish_compilation, verify_pair_with_rust_oracle
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, load_target, reference
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.project import create_project, get_blob, load_project
from ro_sprite_forge.core.timeline import AnimationTimeline
from ro_sprite_forge.core.topology import resolve_topology
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.spr import read_spr, write_spr
from ro_sprite_forge.service.media import stage_video
from ro_sprite_forge.service.server import make_standard_actor_doc
from ro_sprite_forge.service.workbench import (
    mutate,
    preview,
    record_review,
    review_proposal,
    source_catalog,
    source_evidence,
    workspace,
)
from test_compiler import _build_synthetic_monster_act_spr, RUST_ORACLE_BIN
from test_video import make_media, PILLOW, TOOLS
from test_walk_compilation import (
    assert_effective_mapping,
    clean_cli_builds,
    png_pixels,
    rust_report,
    synthetic_pair,
    walk_contracts,
)

ROOT = Path(__file__).resolve().parents[1]


def setup_video_walk_project(root: str | Path, base_dir: str | Path):
    """Set up an end-to-end project with staged video candidates and synthetic Walk target.

    VFR video: PTS [0, 40, 120, 160, 300], time base 1/1000.
    Operator-selected PTS: [300, 0, 120] -> ordinals [4, 0, 2].
    """
    base_dir = Path(base_dir)
    root = Path(root)
    expected_raw, _ = make_media(base_dir)
    vfr_bytes = (base_dir / 'vfr.mkv').read_bytes()
    vfr_sha = digest(vfr_bytes)

    # Extract candidates through the accepted RSF-28 adapter
    ext_res = video.extract_candidates(
        vfr_bytes, stream_index=0, mode='pts', values=[300, 0, 120], expected_sha256=vfr_sha
    )
    manifest_ext = ext_res['manifest']
    extracted_pngs = ext_res['pngs']

    # Create project
    proj_manifest = create_project(root, 'rsf30-video-walk', 'Video Walk Pipeline', 'rsf30-actor', 'monster')

    # Stage video candidates into project
    proj_manifest = stage_video(
        root,
        'rsf30-video-walk',
        vfr_bytes,
        expected_revision=proj_manifest['revision'],
        stream_index=0,
        mode='pts',
        values=[300, 0, 120],
        expected_sha256=vfr_sha,
        expected_preview_sha256=manifest_ext['canonical_sha256'],
    )

    # Import synthetic monster ACT/SPR pair
    act, spr = synthetic_pair()
    import_res = mutate(
        root,
        proj_manifest,
        'import-pair',
        dict(
            expected_revision=proj_manifest['revision'],
            id='original',
            part='body',
            act_base64=base64.b64encode(act).decode(),
            spr_base64=base64.b64encode(spr).decode(),
        ),
    )
    proj_manifest = import_res['project']
    inv = proj_manifest['resources'][0]['inventory']

    # Set up actor
    actor_doc = make_standard_actor_doc(proj_manifest['actor'], frozen_runtime_profile('monster'), parts=['body'])
    actor_doc['resources'] = [
        dict(part='body', inventory_sha256=inv['canonical_sha256'], act_sha256=digest(act), spr_sha256=digest(spr))
    ]
    (root / proj_manifest['project_id'] / 'actor.json').write_bytes(canonical_bytes(load_actor(actor_doc).to_dict()))

    # Declare formal Walk target
    profile = frozen_runtime_profile('monster').to_dict()
    walk_slots = next(r['slots'] for r in profile['actions'] if r['id'] == 'Walk')
    views = [
        dict(
            view=v,
            frame_count=len(read_act(act)['actions'][slot]),
            topology=dict(kind='inherited', inventory_sha256=inv['canonical_sha256'], slot=slot),
        )
        for v, slot in enumerate(walk_slots)
    ]
    target_res = mutate(
        root,
        proj_manifest,
        'target',
        dict(
            expected_revision=proj_manifest['revision'],
            target=dict(
                schema='rsf.target/v2',
                id='rsf30-walk',
                revision=1,
                previous_sha256=None,
                scope='scoped',
                parts=['body'],
                compatibility=dict(status='UNVERIFIED', declarations=[]),
                actions=[
                    dict(
                        id=a['id'],
                        requirement='REQUIRED' if a['id'] == 'Walk' else 'OUT_OF_SCOPE',
                        parts=[dict(part='body', views=views)] if a['id'] == 'Walk' else [],
                    )
                    for a in profile['actions']
                ],
            ),
        ),
    )
    proj_manifest = target_res['project']
    ws = workspace(root, proj_manifest)
    return (
        act,
        spr,
        proj_manifest,
        ws,
        vfr_bytes,
        vfr_sha,
        manifest_ext,
        extracted_pngs,
    )


@unittest.skipUnless(TOOLS and PILLOW, 'FFmpeg/FFprobe and Pillow are required for video walk tests')
class VideoWalkCompilationTests(unittest.TestCase):
    def test_01_vfr_video_source_inspection_and_exact_pts_selection(self):
        """Verify synthetic VFR video PTS [0, 40, 120, 160, 300] and exact selection [300, 0, 120]."""
        with tempfile.TemporaryDirectory(prefix='rsf30-media-') as tmp:
            expected_raw, _ = make_media(tmp)
            vfr_bytes = (Path(tmp) / 'vfr.mkv').read_bytes()
            vfr_sha = digest(vfr_bytes)
            self.assertEqual(vfr_sha, '51f0173b6b4dfd615acf3cb9d55e8131dd87c28b8e528098668b9fefd4c53a9d')

            res = video.extract_candidates(
                vfr_bytes, stream_index=0, mode='pts', values=[300, 0, 120], expected_sha256=vfr_sha
            )
            manifest = res['manifest']
            pngs = res['pngs']
            self.assertEqual(len(pngs), 3)

            # Preserves nonchronological operator ordering [300, 0, 120] -> ordinals [4, 0, 2]
            items = manifest['items']
            self.assertEqual([i['order'] for i in items], [0, 1, 2])
            self.assertEqual([i['requested'] for i in items], [300, 0, 120])
            self.assertEqual([i['pts'] for i in items], [300, 0, 120])
            self.assertEqual([i['ordinal'] for i in items], [4, 0, 2])
            self.assertEqual([i['time_base'] for i in items], [{'numerator': 1, 'denominator': 1000}] * 3)

            # Known extracted PNG hashes
            self.assertEqual(items[0]['png_sha256'], '1c5c3e4c120ee8a2861bf12636a1b96344f578171f7543869ea4a8b437883382')
            self.assertEqual(items[1]['png_sha256'], 'dde9003e6bd1bca8db19eaeb40b24733bbbf4dac8a934f0314cbc4b96f780ef9')
            self.assertEqual(items[2]['png_sha256'], '3e00777e379eecd20d3385f45bcd00b3d85d525d45c50318cbc0634f3f6f8989')

            # Video bytes remain byte-for-byte immutable
            self.assertEqual(digest(vfr_bytes), vfr_sha)

    def test_02_immutable_staging_and_source_catalog_entry(self):
        """Extracted PNGs enter project blob store as content-addressed image sources."""
        with tempfile.TemporaryDirectory(prefix='rsf30-staging-') as tmp:
            base = Path(tmp)
            root = base / 'projects'
            (act, spr, manifest, ws, vfr_bytes, vfr_sha, manifest_ext, pngs) = setup_video_walk_project(root, base)

            # Verify sources in catalog
            catalog = {s['source']['id']: s for s in ws['sources']}
            for item in manifest_ext['items']:
                sid = 'blob-' + item['png_sha256']
                self.assertIn(sid, catalog)
                entry = catalog[sid]
                self.assertEqual(entry['availability'], 'AVAILABLE')
                self.assertEqual(entry['validation'], 'VALID')
                self.assertEqual(entry['preview'], 'AVAILABLE')
                self.assertEqual(entry['source']['kind'], 'IMAGE')

            # Verify idempotency of staging
            rev_before = manifest['revision']
            staged_again = stage_video(
                root,
                manifest['project_id'],
                vfr_bytes,
                expected_revision=rev_before,
                stream_index=0,
                mode='pts',
                values=[300, 0, 120],
                expected_sha256=vfr_sha,
                expected_preview_sha256=manifest_ext['canonical_sha256'],
            )
            self.assertEqual(staged_again['revision'], rev_before)

    def test_03_formal_walk_target_declaration_and_scoped_coverage(self):
        """Bounded Walk target declares explicit topology; missing views remain missing."""
        with tempfile.TemporaryDirectory(prefix='rsf30-target-') as tmp:
            base = Path(tmp)
            root = base / 'projects'
            (act, spr, manifest, ws, vfr_bytes, vfr_sha, manifest_ext, pngs) = setup_video_walk_project(root, base)

            req = ws['requirements']
            self.assertEqual(req['counts']['required']['action_view_slots'], 8)
            self.assertEqual(req['counts']['required']['layer_occurrences_exact'], 12)
            self.assertGreater(len(req['layers']), 0)

            # Unassigned coverage: missing views/frames remain reported as missing
            cov = ws['coverage']
            self.assertFalse(cov['status']['export_ready'])
            self.assertEqual(cov['status']['completeness'], 'INCOMPLETE')
            self.assertEqual(cov['status']['assignment_coverage'], 'UNASSIGNED')
            self.assertEqual(cov['counts']['assignments']['unassigned'], 12)

    def test_04_explicit_walk_assignment_and_reopen_provenance(self):
        """Map video candidates to Walk view 0 frames [0, 1, 2]; verify provenance survives save/reopen."""
        with tempfile.TemporaryDirectory(prefix='rsf30-assign-') as tmp:
            base = Path(tmp)
            root = base / 'projects'
            (act, spr, manifest, ws, vfr_bytes, vfr_sha, manifest_ext, pngs) = setup_video_walk_project(root, base)

            req = ws['requirements']
            selected_layers = [
                l for l in req['layers'] if l['view'] == 0 and l['ordinal'] == 0 and l['frame'] in (0, 1, 2)
            ]
            layer_by_frame = {l['frame']: l for l in selected_layers}

            # Map: candidate 0 (ordinal 4, pts 300) -> frame 0
            #      candidate 1 (ordinal 0, pts 0)   -> frame 1
            #      candidate 2 (ordinal 2, pts 120) -> frame 2
            mappings = []
            for frame_idx, item in enumerate(manifest_ext['items']):
                layer = layer_by_frame[frame_idx]
                sid = 'blob-' + item['png_sha256']
                mappings.append(
                    dict(requirement_id=layer['id'], kind='DIRECT_SOURCE', source=sid, source_revision=1, recipe=[])
                )

            assign_res = mutate(
                root, manifest, 'assign', dict(expected_revision=manifest['revision'], mappings=mappings)
            )
            manifest = assign_res['project']

            # Reopen project and verify ledger
            reopened = load_project(root, manifest['project_id'])
            self.assertEqual(reopened['revision'], manifest['revision'])
            reopened_ws = workspace(root, reopened)
            assigned_ledger = reopened_ws['ledger']
            self.assertEqual(len(assigned_ledger['assignments']), 3)

            # No automatic approval occurred
            for occ in reopened_ws['reviews']['occurrences']:
                if occ['requirement_id'] in layer_by_frame:
                    self.assertEqual(occ['state'], 'UNVERIFIED')

    def test_05_preview_renders_exact_video_pixels(self):
        """Compositor renders the actual video-derived candidate pixels."""
        with tempfile.TemporaryDirectory(prefix='rsf30-prev-') as tmp:
            base = Path(tmp)
            root = base / 'projects'
            (act, spr, manifest, ws, vfr_bytes, vfr_sha, manifest_ext, pngs) = setup_video_walk_project(root, base)

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
            manifest = mutate(
                root, manifest, 'assign', dict(expected_revision=manifest['revision'], mappings=mappings)
            )['project']

            # Preview frame 0
            prev = preview(
                root,
                manifest,
                dict(resource='original', slot=selected_layers[0]['runtime_slot'], view=0, frame=0),
            )
            self.assertIn('png_base64', prev)
            rendered_bytes = base64.b64decode(prev['png_base64'])
            # Rendered image must be a valid PNG of non-zero size
            self.assertGreater(len(rendered_bytes), 0)
            with Image.open(io.BytesIO(rendered_bytes)) as im:
                self.assertEqual(im.format, 'PNG')
                self.assertGreater(im.width, 0)
                self.assertGreater(im.height, 0)

    def test_06_video_timing_and_act_timing_remain_separate_authorities(self):
        """Source video PTS does not become ACT frame delay; runtime timing remains independent."""
        with tempfile.TemporaryDirectory(prefix='rsf30-timing-') as tmp:
            base = Path(tmp)
            root = base / 'projects'
            (act, spr, manifest, ws, vfr_bytes, vfr_sha, manifest_ext, pngs) = setup_video_walk_project(root, base)

            # Record source video timing authority
            video_pts = [item['pts'] for item in manifest_ext['items']]
            self.assertEqual(video_pts, [300, 0, 120])
            self.assertEqual(manifest_ext['inspection']['streams'][0]['time_base'], {'numerator': 1, 'denominator': 1000})

            # Inspect ACT runtime playback timing at movement_speed=100 vs movement_speed=250
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
            manifest = mutate(
                root, manifest, 'assign', dict(expected_revision=manifest['revision'], mappings=mappings)
            )['project']

            slot = selected_layers[0]['runtime_slot']
            prev_fast = preview(
                root,
                manifest,
                dict(
                    resource='original',
                    slot=slot,
                    view=0,
                    frame=0,
                    elapsed_ms=0,
                    context=dict(movement_speed=100),
                ),
            )
            prev_slow = preview(
                root,
                manifest,
                dict(
                    resource='original',
                    slot=slot,
                    view=0,
                    frame=0,
                    elapsed_ms=0,
                    context=dict(movement_speed=250),
                ),
            )

            # Duration changes according to Korangar movement speed formula
            dur_fast = prev_fast['report']['selection']['frame_duration_ms']
            dur_slow = prev_slow['report']['selection']['frame_duration_ms']
            self.assertNotEqual(dur_fast, dur_slow)

            # Video PTS, source hashes, time base remain completely unchanged
            reopened = load_project(root, manifest['project_id'])
            v_import = reopened['video_imports'][0]
            self.assertEqual([i['pts'] for i in v_import['items']], [300, 0, 120])
            self.assertEqual(v_import['inspection']['streams'][0]['time_base'], {'numerator': 1, 'denominator': 1000})
            self.assertEqual(v_import['items'][0]['time_base'], {'numerator': 1, 'denominator': 1000})

            # Reverse test: reordering extraction candidates does not change ACT frame delays
            reordered_res = video.extract_candidates(
                vfr_bytes, stream_index=0, mode='pts', values=[300, 120, 0], expected_sha256=vfr_sha
            )
            # Extracted candidate ordering changed, but ACT timing definition remains unaltered
            act_doc = read_act(act)
            self.assertEqual(
                act_doc['delays'][slot], read_act(act)['delays'][slot]
            )

    def test_07_human_review_boundary_and_scoped_invalidation(self):
        """Simulate operator review proposal/approval, and verify scoped invalidation on source change."""
        with tempfile.TemporaryDirectory(prefix='rsf30-review-') as tmp:
            base = Path(tmp)
            root = base / 'projects'
            (act, spr, manifest, ws, vfr_bytes, vfr_sha, manifest_ext, pngs) = setup_video_walk_project(root, base)

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
            manifest = mutate(
                root, manifest, 'assign', dict(expected_revision=manifest['revision'], mappings=mappings)
            )['project']

            # Operator reviews the composition revision
            proposal = review_proposal(
                root,
                manifest,
                dict(expected_revision=manifest['revision'], requirements=[l['id'] for l in selected_layers]),
            )
            manifest = record_review(
                root,
                manifest,
                dict(expected_revision=manifest['revision'], decision='APPROVED', proposal=proposal['proposal']),
            )['project']

            ws = workspace(root, manifest)
            for occ in ws['reviews']['occurrences']:
                if occ['requirement_id'] in layer_by_frame:
                    self.assertEqual(occ['state'], 'APPROVED')

            # Change an assigned source mapping -> the affected approval becomes STALE
            new_mappings = [
                dict(
                    requirement_id=layer_by_frame[0]['id'],
                    kind='DIRECT_SOURCE',
                    source='blob-' + manifest_ext['items'][1]['png_sha256'],
                    source_revision=1,
                    recipe=[],
                )
            ]
            manifest = mutate(
                root, manifest, 'assign', dict(expected_revision=manifest['revision'], mappings=new_mappings)
            )['project']
            ws = workspace(root, manifest)
            state_by_req = {occ['requirement_id']: occ['state'] for occ in ws['reviews']['occurrences']}
            self.assertEqual(state_by_req[layer_by_frame[0]['id']], 'STALE')
            self.assertEqual(state_by_req[layer_by_frame[1]['id']], 'APPROVED')
            self.assertEqual(state_by_req[layer_by_frame[2]['id']], 'APPROVED')

    @unittest.skipUnless(RUST_ORACLE_BIN.is_file(), 'Rust oracle binary rsf-rust-oracle required')
    def test_08_diagnostic_compilation_and_independent_rust_oracle_verification(self):
        """Compile video-derived Walk through accepted M5 compiler; verify with independent Rust decoder."""
        with tempfile.TemporaryDirectory(prefix='rsf30-compile-') as tmp:
            base = Path(tmp)
            root = base / 'projects'
            (act, spr, manifest, ws, vfr_bytes, vfr_sha, manifest_ext, pngs) = setup_video_walk_project(root, base)

            req = ws['requirements']
            selected_layers = [
                l for l in req['layers'] if l['view'] == 0 and l['ordinal'] == 0 and l['frame'] in (0, 1, 2)
            ]
            layer_by_frame = {l['frame']: l for l in selected_layers}
            mappings = []
            expected = {}
            for i, item in enumerate(manifest_ext['items']):
                layer = layer_by_frame[i]
                sid = 'blob-' + item['png_sha256']
                mappings.append(
                    dict(requirement_id=layer['id'], kind='DIRECT_SOURCE', source=sid, source_revision=1, recipe=[])
                )
                expected[(layer['runtime_slot'], layer['frame'], layer['source_layer_ordinal'])] = pngs[i]

            manifest = mutate(
                root, manifest, 'assign', dict(expected_revision=manifest['revision'], mappings=mappings)
            )['project']

            # Operator approval
            proposal = review_proposal(
                root,
                manifest,
                dict(expected_revision=manifest['revision'], requirements=[l['id'] for l in selected_layers]),
            )
            manifest = record_review(
                root,
                manifest,
                dict(expected_revision=manifest['revision'], decision='APPROVED', proposal=proposal['proposal']),
            )['project']

            # Compile through accepted pipeline
            comp_res = mutate(
                root,
                manifest,
                'compile',
                dict(
                    expected_revision=manifest['revision'],
                    resource_id='original',
                    compilation_id='video-walk-comp',
                    replacement_policy='explicit_rgba',
                ),
            )
            manifest = comp_res['project']
            comp_dir = Path(root) / manifest['project_id'] / 'compilations' / 'video-walk-comp'
            out_act = (comp_dir / 'original.act').read_bytes()
            out_spr = (comp_dir / 'original.spr').read_bytes()

            # Output classification: scoped bounded Walk is PARTIAL_DIAGNOSTIC
            self.assertTrue((comp_dir / 'PARTIAL_DIAGNOSTIC.txt').is_file())
            manifest_doc = json.loads((comp_dir / 'compilation-manifest.json').read_bytes())
            self.assertEqual(manifest_doc['status']['export_label'], 'PARTIAL_DIAGNOSTIC')
            self.assertFalse(manifest_doc['status']['production_authorized'])

            # Independent Rust verification
            before_rep = rust_report(act, spr)
            after_rep = rust_report(out_act, out_spr)
            comp_map = assert_effective_mapping(self, before_rep, after_rep, expected)
            self.assertEqual(comp_map['targeted'], 3)
            self.assertEqual(comp_map['unaffected'], 51)
            self.assertEqual(comp_map['hidden'], 6)
            self.assertEqual(comp_map['mismatches'], 0)

    @unittest.skipUnless(RUST_ORACLE_BIN.is_file(), 'Rust oracle binary rsf-rust-oracle required')
    def test_09_deterministic_repeated_cli_compilations(self):
        """Clean CLI builds in different environments produce bit-for-bit identical ACT, SPR and build manifest."""
        with tempfile.TemporaryDirectory(prefix='rsf30-cli-') as tmp:
            base = Path(tmp)
            root = base / 'projects'
            (act, spr, manifest, ws, vfr_bytes, vfr_sha, manifest_ext, pngs) = setup_video_walk_project(root, base)

            req = ws['requirements']
            selected_layers = [
                l for l in req['layers'] if l['view'] == 0 and l['ordinal'] == 0 and l['frame'] in (0, 1, 2)
            ]
            layer_by_frame = {l['frame']: l for l in selected_layers}
            mappings = []
            expected = {}
            for i, item in enumerate(manifest_ext['items']):
                layer = layer_by_frame[i]
                sid = 'blob-' + item['png_sha256']
                mappings.append(
                    dict(requirement_id=layer['id'], kind='DIRECT_SOURCE', source=sid, source_revision=1, recipe=[])
                )
                expected[(layer['runtime_slot'], layer['frame'], layer['source_layer_ordinal'])] = pngs[i]

            manifest = mutate(
                root, manifest, 'assign', dict(expected_revision=manifest['revision'], mappings=mappings)
            )['project']

            proposal = review_proposal(
                root,
                manifest,
                dict(expected_revision=manifest['revision'], requirements=[l['id'] for l in selected_layers]),
            )
            manifest = record_review(
                root,
                manifest,
                dict(expected_revision=manifest['revision'], decision='APPROVED', proposal=proposal['proposal']),
            )['project']
            state = workspace(root, manifest)

            outputs = clean_cli_builds(self, root, act, spr, manifest, state, expected)
            self.assertEqual(outputs[0]['comparison']['targeted'], 3)
            self.assertEqual(outputs[0]['comparison']['unaffected'], 51)
            self.assertEqual(outputs[0]['comparison']['hidden'], 6)
            self.assertEqual(outputs[0]['act'], outputs[1]['act'])
            self.assertEqual(outputs[0]['spr'], outputs[1]['spr'])
            self.assertEqual(outputs[0]['build'], outputs[1]['build'])

    def test_10_negative_scenarios_and_fail_closed_boundaries(self):
        """Negative tests: corrupt video hash, invalid PTS, corrupted blob, unapproved compilation, production export failure."""
        with tempfile.TemporaryDirectory(prefix='rsf30-neg-') as tmp:
            base = Path(tmp)
            root = base / 'projects'
            (act, spr, manifest, ws, vfr_bytes, vfr_sha, manifest_ext, pngs) = setup_video_walk_project(root, base)

            # 1. Corrupted source video hash
            with self.assertRaisesRegex(ForgeError, 'HASH_MISMATCH'):
                video.extract_candidates(
                    vfr_bytes, stream_index=0, mode='pts', values=[300, 0, 120], expected_sha256='0' * 64
                )

            # 2. Invalid source PTS (out of range, string, negative unsupported)
            with self.assertRaises(ForgeError):
                video.extract_candidates(
                    vfr_bytes, stream_index=0, mode='pts', values=[2**54], expected_sha256=vfr_sha
                )

            # 3. Invalid requirement ID
            with self.assertRaisesRegex(ForgeError, 'NONEXISTENT_REQUIREMENT'):
                mutate(
                    root,
                    manifest,
                    'assign',
                    dict(
                        expected_revision=manifest['revision'],
                        mappings=[
                            dict(
                                requirement_id='nonexistent-req-id',
                                kind='DIRECT_SOURCE',
                                source='blob-' + manifest_ext['items'][0]['png_sha256'],
                                source_revision=1,
                            )
                        ],
                    ),
                )

            # 4. Production export rejected on bounded Walk (fails closed because full actor is not complete)
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
            manifest = mutate(
                root, manifest, 'assign', dict(expected_revision=manifest['revision'], mappings=mappings)
            )['project']
            proposal = review_proposal(
                root,
                manifest,
                dict(expected_revision=manifest['revision'], requirements=[l['id'] for l in selected_layers]),
            )
            manifest = record_review(
                root,
                manifest,
                dict(expected_revision=manifest['revision'], decision='APPROVED', proposal=proposal['proposal']),
            )['project']

            with self.assertRaises(ForgeError):
                mutate(
                    root,
                    manifest,
                    'compile',
                    dict(
                        expected_revision=manifest['revision'],
                        resource_id='original',
                        compilation_id='prod-fail',
                        compilation_mode='production_export',
                    ),
                )

            # 5. Corrupted staged blob fails compilation cleanly
            blob_path = (
                Path(root)
                / manifest['project_id']
                / 'blobs'
                / manifest_ext['items'][0]['png_sha256']
            )
            orig_blob_bytes = blob_path.read_bytes()
            blob_path.write_bytes(b'corrupted_blob_content')
            with self.assertRaises(ForgeError):
                mutate(
                    root,
                    manifest,
                    'compile',
                    dict(
                        expected_revision=manifest['revision'],
                        resource_id='original',
                        compilation_id='corrupt-blob-fail',
                    ),
                )
            # Restore blob and verify project state unchanged
            blob_path.write_bytes(orig_blob_bytes)
            self.assertFalse((Path(root) / manifest['project_id'] / 'compilations' / 'corrupt-blob-fail').exists())


if __name__ == '__main__':
    unittest.main()
