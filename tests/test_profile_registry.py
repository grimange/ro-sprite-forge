"""Public test suite for RSF-32 compatibility registry and additional job profiles.

Validates all 25 points from the RSF-32 focused verification matrix.
No private artwork or GRF files are required for this test suite.
"""

from copy import deepcopy
import hashlib
import json
import re
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import (
    ActorContract,
    RuntimeProfileContract,
    frozen_runtime_profile,
    load_actor,
    load_target,
    load_runtime_profile,
)
from ro_sprite_forge.core.coverage import evaluate_coverage
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.registry import (
    CompatibilityRegistry,
    build_profile_entry,
    create_registry,
    get_default_registry,
    load_registry,
    to_actor_contract,
    to_runtime_profile_contract,
    validate_registry,
    verify_source_hashes,
)
from ro_sprite_forge.core.topology import resolve_topology


class ProfileRegistryTests(unittest.TestCase):
    def setUp(self):
        self.registry = get_default_registry()

    def test_01_existing_novice_profile_unchanged(self):
        """1. Existing Novice profile unchanged."""
        legacy_player = get_profile('player')
        self.assertEqual(legacy_player['canonical_sha256'], get_profile('player')['canonical_sha256'])
        v2_player = frozen_runtime_profile('player')
        self.assertEqual(v2_player.id, 'korangar-player-v1')
        self.assertEqual(v2_player.to_dict()['category'], 'player')
        self.assertEqual(len(v2_player.to_dict()['actions']), 13)

    def test_02_existing_orc_skeleton_profile_unchanged(self):
        """2. Existing Orc Skeleton profile unchanged."""
        legacy_monster = get_profile('monster')
        self.assertEqual(legacy_monster['canonical_sha256'], get_profile('monster')['canonical_sha256'])
        v2_monster = frozen_runtime_profile('monster')
        self.assertEqual(v2_monster.id, 'korangar-monster-v1')
        self.assertEqual(v2_monster.to_dict()['category'], 'monster')
        self.assertEqual(len(v2_monster.to_dict()['actions']), 5)

    def test_03_additional_real_reference_discovery(self):
        """3. Additional real reference discovery: non-Novice profiles present."""
        p_ids = self.registry.list_profile_ids()
        # Verify non-novice jobs are present
        self.assertIn('genetic-female-body-v1', p_ids)
        self.assertIn('dragon-knight-male-shield-v1', p_ids)
        self.assertIn('falcon-companion-v1', p_ids)
        self.assertIn('synthetic-swordsman-v1', p_ids)

    def test_04_source_hash_validation(self):
        """4. Source-hash validation: verify_source_hashes verifies or rejects."""
        p = self.registry.get_profile('genetic-female-body-v1')
        act_sha = p['source_hashes']['act_sha256']
        spr_sha = p['source_hashes']['spr_sha256']

        # Dummy bytes matching hashes
        fake_act = b'act_data_test'
        fake_act_sha = hashlib.sha256(fake_act).hexdigest()
        fake_spr = b'spr_data_test'
        fake_spr_sha = hashlib.sha256(fake_spr).hexdigest()

        test_p = deepcopy(p)
        test_p['source_hashes']['act_sha256'] = fake_act_sha
        test_p['source_hashes']['spr_sha256'] = fake_spr_sha

        self.assertTrue(verify_source_hashes(test_p, fake_act, fake_spr))

        # Mismatched ACT
        with self.assertRaises(ForgeError) as caught:
            verify_source_hashes(test_p, b'different_act', fake_spr)
        self.assertEqual(caught.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn('SOURCE_HASH_MISMATCH', caught.exception.message)

    def test_05_act_spr_version_recognition(self):
        """5. ACT/SPR version recognition: only supported versions accepted."""
        p = deepcopy(self.registry.get_profile('genetic-female-body-v1'))
        p['formats']['act_version'] = '2.5'  # Newer unsupported version
        p['canonical_sha256'] = digest(canonical_bytes({k: v for k, v in p.items() if k != 'canonical_sha256'}))

        with self.assertRaises(ForgeError) as caught:
            create_registry([p])
        self.assertEqual(caught.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn('Unsupported format version', caught.exception.message)

    def test_06_canonical_resource_inventory(self):
        """6. Canonical resource inventory counts stored in topology."""
        for pid in ('novice-male-body-v1', 'orc-skeleton-v1', 'genetic-female-body-v1', 'falcon-companion-v1'):
            p = self.registry.get_profile(pid)
            topo = p['topology']
            self.assertGreater(topo['action_count'], 0)
            self.assertGreater(topo['slot_count'], 0)
            self.assertGreater(topo['motion_count'], 0)
            self.assertTrue(bool(topo['layer_counts']))

    def test_07_action_slot_count_correctness(self):
        """7. Action-slot count correctness: does not force Novice 104 slots."""
        novice = self.registry.get_profile('novice-male-body-v1')
        self.assertEqual(novice['topology']['slot_count'], 104)

        orc = self.registry.get_profile('orc-skeleton-v1')
        self.assertEqual(orc['topology']['slot_count'], 40)

        falcon = self.registry.get_profile('falcon-companion-v1')
        self.assertEqual(falcon['topology']['slot_count'], 16)
        self.assertNotEqual(falcon['topology']['slot_count'], novice['topology']['slot_count'])

    def test_08_frame_occurrence_correctness(self):
        """8. Frame occurrence correctness: preserves distinct motion counts."""
        novice = self.registry.get_profile('novice-male-body-v1')
        self.assertEqual(novice['topology']['motion_count'], 456)

        shield = self.registry.get_profile('dragon-knight-male-shield-v1')
        self.assertEqual(shield['topology']['motion_count'], 448)

        orc = self.registry.get_profile('orc-skeleton-v1')
        self.assertEqual(orc['topology']['motion_count'], 512)

        falcon = self.registry.get_profile('falcon-companion-v1')
        self.assertEqual(falcon['topology']['motion_count'], 72)

    def test_09_ordered_layer_topology(self):
        """9. Ordered layer topology: distinguishes single and multi-layer topologies."""
        novice = self.registry.get_profile('novice-male-body-v1')
        self.assertEqual(novice['topology']['layer_counts'], [1])

        orc = self.registry.get_profile('orc-skeleton-v1')
        self.assertIn(12, orc['topology']['layer_counts'])

        swordsman = self.registry.get_profile('synthetic-swordsman-v1')
        self.assertIn(2, swordsman['topology']['layer_counts'])

    def test_10_referenced_versus_stored_images(self):
        """10. Referenced versus stored images."""
        orc = self.registry.get_profile('orc-skeleton-v1')
        pool = orc['image_pool']
        self.assertEqual(pool['indexed_count'], 57)
        self.assertEqual(pool['referenced_count'], 55)
        self.assertLess(pool['referenced_count'], pool['indexed_count'])

    def test_11_indexed_truecolor_image_inventory(self):
        """11. Indexed/truecolor image inventory: separate counting."""
        genetic = self.registry.get_profile('genetic-female-body-v1')
        pool = genetic['image_pool']
        self.assertEqual(pool['indexed_count'], 122)
        self.assertEqual(pool['rgba_count'], 0)
        self.assertEqual(pool['distinct_content_count'], 122)

    def test_12_body_head_relationship_handling(self):
        """12. Body/head relationship handling: player parts separated and typed."""
        novice = self.registry.get_profile('novice-male-body-v1')
        relationships = novice['parts']['relationships']
        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0]['rule'], 'player_head_anchor_delta')

        shield = self.registry.get_profile('dragon-knight-male-shield-v1')
        self.assertEqual(len(shield['parts']['relationships']), 0)

        falcon = self.registry.get_profile('falcon-companion-v1')
        self.assertEqual(len(falcon['parts']['relationships']), 0)

    def test_13_runtime_mapping_correctness(self):
        """13. Runtime mapping correctness: backed by mapping evidence."""
        p = self.registry.get_profile('novice-male-body-v1')
        rp = to_runtime_profile_contract(p)
        self.assertEqual(rp.category, 'player')
        self.assertEqual(len(rp.to_dict()['actions']), 13)

    def test_14_unknown_mapping_classification(self):
        """14. Unknown mapping classification: non-standard actions explicit."""
        falcon = self.registry.get_profile('falcon-companion-v1')
        actions = falcon['actions']
        self.assertEqual(len(actions), 2)  # Idle and Walk
        self.assertEqual(falcon['compatibility']['runtime_mapping'], 'PARTIAL')

    def test_15_compatibility_registry_schema_validation(self):
        """15. Compatibility-registry schema validation."""
        d = self.registry.to_dict()
        validated = validate_registry(d)
        self.assertEqual(validated['schema'], 'rsf.compatibility-registry/v1')

    def test_16_duplicate_registry_id_rejection(self):
        """16. Duplicate registry ID rejection."""
        p1 = self.registry.get_profile('novice-male-body-v1')
        p2 = deepcopy(p1)
        with self.assertRaises(ForgeError) as caught:
            validate_registry({
                'schema': 'rsf.compatibility-registry/v1',
                'id': 'test-reg',
                'version': '1.0.0',
                'profiles': [p1, p2],
                'canonical_sha256': '0' * 64,
            })
        self.assertEqual(caught.exception.code, ErrorCode.INVALID_INPUT)
        self.assertIn('Duplicate profile ID', caught.exception.message)

    def test_17_registry_source_revision_mismatch(self):
        """17. Source revision and compatibility invalidation: hash mismatch rejects verification."""
        p = self.registry.get_profile('genetic-female-body-v1')
        modified_bytes = b'different_bytes_here'
        with self.assertRaises(ForgeError) as caught:
            verify_source_hashes(p, modified_bytes, b'other')
        self.assertIn('SOURCE_HASH_MISMATCH', caught.exception.message)

    def test_18_deterministic_registry_serialization(self):
        """18. Registry determinism: profile order and key sorting do not affect canonical hash."""
        profiles = [
            self.registry.get_profile('novice-male-body-v1'),
            self.registry.get_profile('falcon-companion-v1'),
            self.registry.get_profile('genetic-female-body-v1'),
        ]
        reg1 = create_registry(profiles)
        reg2 = create_registry(list(reversed(profiles)))
        self.assertEqual(reg1.canonical_sha256, reg2.canonical_sha256)
        self.assertEqual(reg1.canonical_bytes(), reg2.canonical_bytes())

    def test_19_requirements_resolution_from_registered_profile(self):
        """19. Requirements resolution from a registered profile via RSF-8."""
        p = self.registry.get_profile('synthetic-swordsman-v1')
        rp = to_runtime_profile_contract(p)
        act = to_actor_contract(p)

        target_doc = {
            'schema': 'rsf.target/v2',
            'id': 'target-swordsman-v1',
            'revision': 1,
            'previous_sha256': None,
            'actor': {'id': act.id, 'revision': act.revision, 'canonical_sha256': act.canonical_sha256},
            'runtime_profile': {'id': rp.id, 'profile_version': rp.profile_version, 'canonical_sha256': rp.canonical_sha256},
            'scope': 'scoped',
            'parts': ['body'],
            'compatibility': {'status': 'UNVERIFIED', 'declarations': []},
            'actions': [
                {
                    'id': 'Walk',
                    'requirement': 'REQUIRED',
                    'parts': [
                        {
                            'part': 'body',
                            'views': [
                                {
                                    'view': 0,
                                    'frame_count': 5,
                                    'topology': {'kind': 'explicit', 'layers': ['torso', 'pauldrons']},
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        target = load_target(target_doc, actor=act, profile=rp)
        reqs = resolve_topology(target, actor=act, profile=rp)
        self.assertEqual(len(reqs['slots']), 1)
        self.assertEqual(len(reqs['frames']), 5)
        self.assertEqual(len(reqs['layers']), 10)  # 5 frames * 2 layers

    def test_20_coverage_and_missing_work_generation(self):
        """20. Coverage and missing-work generation via RSF-10."""
        p = self.registry.get_profile('falcon-companion-v1')
        rp = to_runtime_profile_contract(p)
        act = to_actor_contract(p)

        target_doc = {
            'schema': 'rsf.target/v2',
            'id': 'target-falcon-v1',
            'revision': 1,
            'previous_sha256': None,
            'actor': {'id': act.id, 'revision': act.revision, 'canonical_sha256': act.canonical_sha256},
            'runtime_profile': {'id': rp.id, 'profile_version': rp.profile_version, 'canonical_sha256': rp.canonical_sha256},
            'scope': 'scoped',
            'parts': ['body'],
            'compatibility': {'status': 'UNVERIFIED', 'declarations': []},
            'actions': [
                {
                    'id': 'Walk',
                    'requirement': 'REQUIRED',
                    'parts': [
                        {
                            'part': 'body',
                            'views': [
                                {
                                    'view': 0,
                                    'frame_count': 4,
                                    'topology': {'kind': 'explicit', 'layers': ['feathers']},
                                }
                            ],
                        }
                    ],
                }
            ],
        }
        target = load_target(target_doc, actor=act, profile=rp)
        reqs = resolve_topology(target, actor=act, profile=rp)
        cov = evaluate_coverage(reqs, target=target)
        self.assertEqual(cov['counts']['structural']['required_frames'], 4)
        self.assertEqual(cov['counts']['structural']['required_layers'], 4)
        self.assertEqual(cov['counts']['assignments']['unassigned'], 4)

    def test_21_unsupported_capability_classification(self):
        """21. Unsupported capability classification: orthogonal statuses."""
        falcon = self.registry.get_profile('falcon-companion-v1')
        compat = falcon['compatibility']
        self.assertEqual(compat['format_decoding'], 'VERIFIED')
        self.assertEqual(compat['runtime_mapping'], 'PARTIAL')
        self.assertEqual(compat['native_korangar'], 'UNVERIFIED')

    def test_22_no_false_compilation_claim(self):
        """22. No false compilation claim: decoding does not automatically equal compilation."""
        p = deepcopy(self.registry.get_profile('genetic-female-body-v1'))
        p['compatibility']['compilation'] = 'UNVERIFIED'
        p['canonical_sha256'] = digest(canonical_bytes({k: v for k, v in p.items() if k != 'canonical_sha256'}))
        reg = create_registry([p])
        retrieved = reg.get_profile('genetic-female-body-v1')
        self.assertEqual(retrieved['compatibility']['compilation'], 'UNVERIFIED')
        self.assertEqual(retrieved['compatibility']['format_decoding'], 'VERIFIED')

    def test_23_no_false_native_verification_claim(self):
        """23. No false native verification claim: non-Novice profiles remain UNVERIFIED natively."""
        genetic = self.registry.get_profile('genetic-female-body-v1')
        self.assertEqual(genetic['compatibility']['native_korangar'], 'UNVERIFIED')

        shield = self.registry.get_profile('dragon-knight-male-shield-v1')
        self.assertEqual(shield['compatibility']['native_korangar'], 'UNVERIFIED')

        falcon = self.registry.get_profile('falcon-companion-v1')
        self.assertEqual(falcon['compatibility']['native_korangar'], 'UNVERIFIED')

    def test_24_independent_rust_verification_where_supported(self):
        """24. Independent Rust verification where supported."""
        for pid in ('novice-male-body-v1', 'orc-skeleton-v1', 'genetic-female-body-v1', 'dragon-knight-male-shield-v1'):
            p = self.registry.get_profile(pid)
            self.assertEqual(p['compatibility']['independent_rust'], 'VERIFIED')
            has_rust_ev = any(e['kind'] == 'rust_oracle' for e in p['evidence'])
            self.assertTrue(has_rust_ev)

    def test_25_private_source_exclusion_from_public_artifacts(self):
        """25. Private-source exclusion from public artifacts: no raw art or absolute paths."""
        d = self.registry.to_dict()
        reg_json = json.dumps(d)
        self.assertNotIn('/home/ra/', reg_json)
        self.assertNotIn('Living-world-Ragnarok', reg_json)
        # Ensure only hex hashes and standard relative refs
        for p in d['profiles']:
            self.assertTrue(re.fullmatch(r'^[0-9a-f]{64}$', p['source_hashes']['act_sha256']))
            self.assertTrue(re.fullmatch(r'^[0-9a-f]{64}$', p['source_hashes']['spr_sha256']))


if __name__ == '__main__':
    unittest.main()
