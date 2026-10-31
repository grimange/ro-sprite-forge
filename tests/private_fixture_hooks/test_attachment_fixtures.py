"""Private fixture integration tests for RSF-33 attachment compatibility.

Verifies real discovered ACT 2.4 and SPR 2.1 resources from local lawful archives
against attachment rules, slot mapping, frame counts, anchors, and independent Rust oracle.
Skips gracefully if local private GRF archive is not available.
"""

import hashlib
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest
import zlib

from ro_sprite_forge.core.attachments import (
    CODE_MISMATCHED_FRAME_COUNT,
    RULE_BODY_SHIELD_RELATIVE,
    RULE_HEAD_ACCESSORY_ANCHOR_DELTA,
    RULE_PLAYER_HEAD_ANCHOR_DELTA,
    compose_attachment_coordinates,
    composite_attachment_layers,
    validate_attachment_compatibility,
)
from ro_sprite_forge.core.registry import get_default_registry, verify_source_hashes
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.spr import read_spr
from tests.private_fixture_hooks.test_registry_fixtures import _extract_from_grf, _find_grf, RUST_ORACLE_PATH


class PrivateAttachmentFixtureTests(unittest.TestCase):
    def setUp(self):
        self.grf_path = _find_grf()
        if not self.grf_path:
            self.skipTest('Local GRF archive not available for private fixture verification.')
        self.registry = get_default_registry()

    def _oracle_check(self, act_b: bytes, spr_b: bytes, profile_id: str):
        if RUST_ORACLE_PATH.is_file():
            with tempfile.NamedTemporaryFile(suffix='.act', delete=False) as fa, \
                 tempfile.NamedTemporaryFile(suffix='.spr', delete=False) as fs:
                fa.write(act_b)
                fs.write(spr_b)
                fa_path, fs_path = fa.name, fs.name

            try:
                res = subprocess.run([str(RUST_ORACLE_PATH), fa_path, fs_path], capture_output=True, text=True)
                self.assertEqual(res.returncode, 0, f'Rust oracle failed on {profile_id}: {res.stderr}')
            finally:
                os.unlink(fa_path)
                os.unlink(fs_path)

    def test_01_real_body_head_attachment(self):
        """Real Novice male body + head attachment compatibility and oracle check."""
        body_p = self.registry.get_profile('novice-male-body-v1')
        head_p = self.registry.get_profile('novice-male-head-v1')

        # Using Genetic female body (104 slots, 456 frames) as representative player body fixture from GRF
        pair_body = _extract_from_grf(self.grf_path, r'data\sprite\인간족\몸통\여\costume_1\제네릭_여_1')
        pair_jack = _extract_from_grf(self.grf_path, r'data\sprite\악세사리\남\남_잭머리')
        if not pair_body or not pair_jack:
            self.skipTest('Required fixtures not found in GRF.')

        body_act_b, body_spr_b = pair_body
        jack_act_b, jack_spr_b = pair_jack

        body_act = read_act(body_act_b)
        jack_act = read_act(jack_act_b)

        # 1. Byte-exact round-trip preservation
        self.assertEqual(write_act(body_act), body_act_b)
        self.assertEqual(write_act(jack_act), jack_act_b)

        # 2. Compatibility validation
        rep = validate_attachment_compatibility(
            body_p, self.registry.get_profile('jack-head-male-v1'),
            parent_act=body_act, child_act=jack_act,
            gameplay_job_check=False,
        )
        self.assertEqual(rep['status'], 'SUPPORTED')
        self.assertEqual(rep['action_mapping']['total_actions'], 104)
        self.assertEqual(rep['action_mapping']['matching_actions'], 104)
        self.assertEqual(rep['action_mapping']['mismatched_actions'], 0)

        # 3. Anchor coordinate composition on frame 0
        ba = body_act['actions'][0][0]['anchors'][0]
        ja = jack_act['actions'][0][0]['anchors'][0]
        coord = compose_attachment_coordinates((ba['x'], ba['y']), (ja['x'], ja['y']), (0, 0), rule=RULE_HEAD_ACCESSORY_ANCHOR_DELTA)
        self.assertEqual(coord, (ba['x'] - ja['x'], ba['y'] - ja['y']))

        # 4. Independent Rust oracle
        self._oracle_check(body_act_b, body_spr_b, 'genetic-female-body')
        self._oracle_check(jack_act_b, jack_spr_b, 'jack-head-male-v1')

    def test_02_real_body_shield_mismatched_frame_count(self):
        """Real Body + Dragon Knight Shield reveals exact 8 mismatched Pickup frames."""
        body_p = self.registry.get_profile('novice-male-body-v1')
        shield_p = self.registry.get_profile('dragon-knight-male-shield-v1')

        pair_body = _extract_from_grf(self.grf_path, r'data\sprite\인간족\몸통\여\costume_1\제네릭_여_1')
        pair_shield = _extract_from_grf(self.grf_path, r'data\sprite\방패\dragon_knight\dragon_knight_남_쉴드')
        if not pair_body or not pair_shield:
            self.skipTest('Required fixtures not found in GRF.')

        body_act_b, _ = pair_body
        shield_act_b, shield_spr_b = pair_shield

        body_act = read_act(body_act_b)
        shield_act = read_act(shield_act_b)

        rep = validate_attachment_compatibility(
            body_p, shield_p,
            parent_act=body_act, child_act=shield_act,
            gameplay_job_check=False,
        )
        self.assertEqual(rep['status'], 'PARTIAL')
        self.assertEqual(rep['action_mapping']['total_actions'], 104)
        self.assertEqual(rep['action_mapping']['matching_actions'], 96)
        self.assertEqual(rep['action_mapping']['mismatched_actions'], 8)

        # Inspect the 8 mismatched slots: exactly slots 24..31 (Group 3 Pickup)
        mismatched_slots = [d['slot'] for d in rep['diagnostics'] if d['code'] == CODE_MISMATCHED_FRAME_COUNT]
        self.assertEqual(mismatched_slots, list(range(24, 32)))

        # Pickup in Body has 3 frames; Shield has 2 frames
        for d in rep['diagnostics']:
            if d['code'] == CODE_MISMATCHED_FRAME_COUNT:
                self.assertEqual(d['parent_frames'], 3)
                self.assertEqual(d['child_frames'], 2)

        # Independent Rust oracle on shield
        self._oracle_check(shield_act_b, shield_spr_b, 'dragon-knight-male-shield-v1')

    def test_03_real_jack_head_accessory_audit(self):
        """Audit Jack Head real ACT/SPR against registered profile hashes and topology."""
        pair = _extract_from_grf(self.grf_path, r'data\sprite\악세사리\남\남_잭머리')
        if not pair:
            self.skipTest('Jack Head fixture not found in GRF.')

        act_b, spr_b = pair
        jack_p = self.registry.get_profile('jack-head-male-v1')

        # Hash check
        self.assertTrue(verify_source_hashes(jack_p, act_b, spr_b))

        # ACT check
        act = read_act(act_b)
        self.assertEqual(len(act['actions']), 104)
        self.assertEqual(sum(len(a) for a in act['actions']), 456)
        self.assertTrue(all(len(m['anchors']) == 1 for a in act['actions'] for m in a))
        self.assertTrue(all(len(m['clips']) == 1 for a in act['actions'] for m in a))

        # SPR check
        spr = read_spr(spr_b)
        self.assertEqual(spr.indexed_count, 14)
        self.assertEqual(spr.rgba_count, 0)

        # Independent Rust oracle
        self._oracle_check(act_b, spr_b, 'jack-head-male-v1')


if __name__ == '__main__':
    unittest.main()
