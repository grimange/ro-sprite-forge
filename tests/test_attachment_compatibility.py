"""Focused test suite for RSF-33 equipment and attachment compatibility validation.

Verifies:
1. Body + Head pairing (player_head_anchor_delta).
2. Body + Head Accessory pairing (head_accessory_anchor_delta) with Jack Head reconciliation.
3. Body + Shield pairing (body_shield_relative) with exact mismatched frame count diagnostics.
4. Companion and monster pairing rejections (incompatible resource kind).
5. Gameplay-job / visual-outfit mismatch reporting without silent fallback.
6. Missing weapon action and incompatible action family reporting.
7. Missing anchor detection.
8. Exact coordinate transformations without arbitrary rounding.
9. Order-preserving multilayer composition without layer flattening.
10. Registry attachment pairing APIs and schema conformance.
11. Integration with RSF-8 topology requirements resolution.
12. Integration with RSF-10 coverage evaluation.
13. Integration with RSF-18 scoped review invalidation.
14. Truthful orthogonal compatibility dimensions.
"""

from copy import deepcopy
import hashlib
import json
import unittest

from ro_sprite_forge.core.attachments import (
    CODE_GAMEPLAY_JOB_MISMATCH,
    CODE_INCOMPATIBLE_ACTION_FAMILY,
    CODE_INCOMPATIBLE_RESOURCE_KIND,
    CODE_MISMATCHED_FRAME_COUNT,
    CODE_MISSING_ACTION,
    CODE_MISSING_ANCHOR,
    CODE_MISSING_ATTACHMENT_ACTION,
    RULE_BODY_SHIELD_RELATIVE,
    RULE_HEAD_ACCESSORY_ANCHOR_DELTA,
    RULE_PLAYER_HEAD_ANCHOR_DELTA,
    RULE_STANDALONE_UNATTACHED,
    compose_attachment_coordinates,
    composite_attachment_layers,
    validate_attachment_compatibility,
    build_attachment_pairing_record,
)
from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.contracts import (
    ActorContract,
    RuntimeProfileContract,
    frozen_runtime_profile,
    load_actor,
    load_runtime_profile,
    load_target,
    reference,
)
from ro_sprite_forge.core.coverage import evaluate_coverage
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.registry import (
    CompatibilityRegistry,
    build_profile_entry,
    create_registry,
    get_default_registry,
    to_actor_contract,
    to_runtime_profile_contract,
    validate_registry,
)
from ro_sprite_forge.core.review import (
    bases,
    evaluate_reviews,
    make_event,
)
from ro_sprite_forge.core.topology import resolve_topology


class AttachmentCompatibilityTests(unittest.TestCase):
    def setUp(self):
        self.registry = get_default_registry()
        self.body_p = self.registry.get_profile('novice-male-body-v1')
        self.head_p = self.registry.get_profile('novice-male-head-v1')
        self.shield_p = self.registry.get_profile('dragon-knight-male-shield-v1')
        self.falcon_p = self.registry.get_profile('falcon-companion-v1')
        self.jack_p = self.registry.get_profile('jack-head-male-v1')
        self.orc_p = self.registry.get_profile('orc-skeleton-v1')

    # 1. Body + Head Compatibility
    def test_01_body_head_conventional_pairing_supported(self):
        """Body + Head with player_head_anchor_delta is SUPPORTED across all 104 slots."""
        rep = validate_attachment_compatibility(self.body_p, self.head_p, gameplay_job_check=False)
        self.assertEqual(rep['status'], 'SUPPORTED')
        self.assertEqual(rep['rule'], RULE_PLAYER_HEAD_ANCHOR_DELTA)
        self.assertEqual(rep['action_mapping']['total_actions'], 104)
        self.assertEqual(rep['action_mapping']['matching_actions'], 104)
        self.assertEqual(rep['action_mapping']['mismatched_actions'], 0)
        self.assertEqual(rep['anchor_rule']['mode'], 'parent_head_anchor_delta')
        self.assertEqual(rep['layer_order'], ['body', 'head'])
        self.assertEqual(len(rep['diagnostics']), 0)

    # 2. Jack Head Accessory Reconciliation
    def test_02_jack_head_enrolled_in_default_registry(self):
        """Jack Head male profile is enrolled in default registry with verified dimensions."""
        self.assertTrue(self.registry.has_profile('jack-head-male-v1'))
        p = self.registry.get_profile('jack-head-male-v1')
        self.assertEqual(p['resource_kind'], 'accessory')
        self.assertEqual(p['source_hashes']['act_sha256'], '5dd8c7b8ebd5762b29863e86a77c4e555834cd401c0f559a8f92061a25a3ac93')
        self.assertEqual(p['source_hashes']['spr_sha256'], 'e636bdc5772bb1fa9206b84369d46a13b3e6ac79b6c600e55c5dbb6a952fd655')
        self.assertEqual(p['topology']['slot_count'], 104)
        self.assertEqual(p['topology']['motion_count'], 456)
        self.assertEqual(p['image_pool']['indexed_count'], 14)
        self.assertEqual(p['compatibility']['format_decoding'], 'VERIFIED')
        self.assertEqual(p['compatibility']['independent_rust'], 'VERIFIED')
        self.assertEqual(p['compatibility']['native_korangar'], 'UNVERIFIED')

    def test_03_body_jack_head_accessory_pairing_supported(self):
        """Body + Jack Head Accessory pairing is SUPPORTED with head_accessory_anchor_delta."""
        rep = validate_attachment_compatibility(self.body_p, self.jack_p, gameplay_job_check=False)
        self.assertEqual(rep['status'], 'SUPPORTED')
        self.assertEqual(rep['rule'], RULE_HEAD_ACCESSORY_ANCHOR_DELTA)
        self.assertEqual(rep['action_mapping']['total_actions'], 104)
        self.assertEqual(rep['action_mapping']['matching_actions'], 104)
        self.assertEqual(rep['action_mapping']['mismatched_actions'], 0)
        self.assertEqual(rep['layer_order'], ['body', 'head', 'accessory'])

    # 3. Body + Shield Mismatched Frame Count Diagnostics
    def test_04_body_shield_mismatched_frame_count_exact_diagnostics(self):
        """Body + Dragon Knight Shield reports MISMATCHED_FRAME_COUNT for Pickup without fallback."""
        # Synthetic ACT data simulating Novice body 456 frames vs Shield 448 frames
        # Body: 104 slots; slot 24..31 (Pickup) has 3 frames; other slots have e.g. 4 frames
        # Shield: 104 slots; slot 24..31 (Pickup) has 2 frames; other slots match body
        body_act = {'actions': []}
        shield_act = {'actions': []}
        for s in range(104):
            group = s // 8
            if group == 3:  # Pickup
                body_act['actions'].append([{'clips': [], 'anchors': []}] * 3)
                shield_act['actions'].append([{'clips': []}] * 2)
            else:
                body_act['actions'].append([{'clips': [], 'anchors': []}] * 4)
                shield_act['actions'].append([{'clips': []}] * 4)

        rep = validate_attachment_compatibility(
            self.body_p, self.shield_p,
            parent_act=body_act, child_act=shield_act,
            gameplay_job_check=False,
        )
        self.assertEqual(rep['status'], 'PARTIAL')
        self.assertEqual(rep['action_mapping']['total_actions'], 104)
        self.assertEqual(rep['action_mapping']['matching_actions'], 96)
        self.assertEqual(rep['action_mapping']['mismatched_actions'], 8)

        # Verify exact diagnostics for all 8 pickup slots
        mismatched_diag = [d for d in rep['diagnostics'] if d['code'] == CODE_MISMATCHED_FRAME_COUNT]
        self.assertEqual(len(mismatched_diag), 8)
        for i, d in enumerate(mismatched_diag):
            slot = 24 + i
            self.assertEqual(d['slot'], slot)
            self.assertEqual(d['group'], 3)
            self.assertEqual(d['view'], i)
            self.assertEqual(d['parent_frames'], 3)
            self.assertEqual(d['child_frames'], 2)
            self.assertIn('No silent fallback applied', d['message'])

    # 4. Incompatible Resource Kinds
    def test_05_companion_attachment_rejected(self):
        """Attempting to attach a companion as an equipment piece reports INCOMPATIBLE_RESOURCE_KIND."""
        rep = validate_attachment_compatibility(self.body_p, self.falcon_p, gameplay_job_check=False)
        self.assertEqual(rep['status'], 'UNSUPPORTED')
        incompat = [d for d in rep['diagnostics'] if d['code'] == CODE_INCOMPATIBLE_RESOURCE_KIND]
        self.assertTrue(len(incompat) > 0)
        self.assertIn('companion is standalone', incompat[0]['message'])

    def test_06_monster_body_player_head_rejected(self):
        """Monster body cannot attach player head; reports INCOMPATIBLE_RESOURCE_KIND."""
        rep = validate_attachment_compatibility(self.orc_p, self.head_p, gameplay_job_check=False)
        self.assertEqual(rep['status'], 'UNSUPPORTED')
        incompat = [d for d in rep['diagnostics'] if d['code'] == CODE_INCOMPATIBLE_RESOURCE_KIND]
        self.assertTrue(len(incompat) > 0)

    # 5. Gameplay Job vs Visual Outfit Mismatch
    def test_07_gameplay_job_mismatch_reported(self):
        """Novice body paired with Dragon Knight shield reports GAMEPLAY_JOB_MISMATCH."""
        rep = validate_attachment_compatibility(self.body_p, self.shield_p, gameplay_job_check=True)
        # Should be UNSUPPORTED because gameplay job novice != dragon_knight
        self.assertEqual(rep['status'], 'UNSUPPORTED')
        job_mismatches = [d for d in rep['diagnostics'] if d['code'] == CODE_GAMEPLAY_JOB_MISMATCH]
        self.assertEqual(len(job_mismatches), 1)
        self.assertEqual(job_mismatches[0]['parent_job'], 'novice')
        self.assertEqual(job_mismatches[0]['child_job'], 'dragon_knight')

    # 6. Incompatible Action Family
    def test_08_incompatible_action_family_reported(self):
        """Missing required weapon action family reports INCOMPATIBLE_ACTION_FAMILY."""
        rep = validate_attachment_compatibility(
            self.body_p, self.head_p,
            required_weapon_family='bow_two_hand',
            available_weapon_families=['unarmed', 'one_hand_dagger'],
            gameplay_job_check=False,
        )
        self.assertEqual(rep['status'], 'UNSUPPORTED')
        fam_diag = [d for d in rep['diagnostics'] if d['code'] == CODE_INCOMPATIBLE_ACTION_FAMILY]
        self.assertEqual(len(fam_diag), 1)
        self.assertEqual(fam_diag[0]['required'], 'bow_two_hand')

    # 7. Missing Anchor Detection
    def test_09_missing_anchor_detected_for_anchor_rules(self):
        """If parent or child lacks required anchor, MISSING_ANCHOR diagnostic is emitted."""
        body_act = {'actions': [[{'clips': [], 'anchors': []}]]}  # missing anchor on slot 0 frame 0
        head_act = {'actions': [[{'clips': [], 'anchors': [{'x': 0, 'y': 0}]}]]}
        rep = validate_attachment_compatibility(
            self.body_p, self.head_p,
            parent_act=body_act, child_act=head_act,
            gameplay_job_check=False,
        )
        missing_anchors = [d for d in rep['diagnostics'] if d['code'] == CODE_MISSING_ANCHOR]
        self.assertEqual(len(missing_anchors), 1)
        self.assertEqual(missing_anchors[0]['part'], 'parent')

    # 8. Missing Action Slots
    def test_10_missing_attachment_action_slots(self):
        """Child profile lacking action slots reports MISSING_ATTACHMENT_ACTION."""
        # Child with only 16 slots (Idle, Walk) paired with 104-slot body
        falcon_body = deepcopy(self.falcon_p)
        falcon_body['resource_kind'] = 'accessory'  # fake accessory to bypass kind check
        rep = validate_attachment_compatibility(self.body_p, falcon_body, gameplay_job_check=False)
        self.assertEqual(rep['status'], 'PARTIAL')
        missing_actions = [d for d in rep['diagnostics'] if d['code'] == CODE_MISSING_ATTACHMENT_ACTION]
        self.assertEqual(len(missing_actions), 104 - 16)

    # 9. Coordinate Transformations & Exact Arithmetic
    def test_11_compose_attachment_coordinates_exact(self):
        """compose_attachment_coordinates computes exact integer coordinates without rounding."""
        # player_head_anchor_delta: (ba_x - ca_x + layer_x, ba_y - ca_y + layer_y)
        res1 = compose_attachment_coordinates((10, -50), (2, -15), (5, 8), rule=RULE_PLAYER_HEAD_ANCHOR_DELTA)
        # 10 - 2 + 5 = 13, -50 - (-15) + 8 = -27
        self.assertEqual(res1, (13, -27))

        # head_accessory_anchor_delta with intermediate head shift
        head_shift = (13, -27)
        res2 = compose_attachment_coordinates((2, -15), (1, -10), (0, 0), rule=RULE_HEAD_ACCESSORY_ANCHOR_DELTA, intermediate_shift=head_shift)
        # 13 + (2 - 1) = 14, -27 + (-15 - (-10)) = -32
        self.assertEqual(res2, (14, -32))

        # body_shield_relative
        res3 = compose_attachment_coordinates(None, None, (-12, 18), rule=RULE_BODY_SHIELD_RELATIVE, intermediate_shift=(0, 0))
        self.assertEqual(res3, (-12, 18))

    def test_12_compose_attachment_coordinates_rejects_missing_anchors(self):
        """player_head_anchor_delta raises error if anchors are None."""
        with self.assertRaises(ForgeError):
            compose_attachment_coordinates(None, (0, 0), (0, 0), rule=RULE_PLAYER_HEAD_ANCHOR_DELTA)

    # 10. Multilayer Composition & Layer Ordering Preservation
    def test_13_composite_attachment_layers_preserves_order_and_metadata(self):
        """composite_attachment_layers arranges parts in declared order without mutating metadata."""
        layer_body = {'part': 'body', 'layer_ordinal': 0, 'sprite': 10, 'scale_x': 1.0, 'color': 0xFFFFFFFF}
        layer_head = {'part': 'head', 'layer_ordinal': 0, 'sprite': 2, 'scale_x': 1.0, 'color': 0xFFFFFFFF}
        layer_acc = {'part': 'accessory', 'layer_ordinal': 0, 'sprite': 0, 'scale_x': 1.0, 'color': 0xFFFFFFFF}

        # Input in arbitrary scrambled order
        input_layers = [layer_acc, layer_body, layer_head]

        # Composed with order ['body', 'head', 'accessory']
        composed = composite_attachment_layers(input_layers, ['body', 'head', 'accessory'])
        self.assertEqual(len(composed), 3)
        self.assertEqual([l['part'] for l in composed], ['body', 'head', 'accessory'])
        self.assertEqual(composed[0]['sprite'], 10)
        self.assertEqual(composed[1]['sprite'], 2)
        self.assertEqual(composed[2]['sprite'], 0)

        # Alternative ordering: shield behind body: ['shield', 'body', 'head']
        layer_shield = {'part': 'shield', 'layer_ordinal': 0, 'sprite': 1}
        input_layers_2 = [layer_body, layer_shield, layer_head]
        composed_2 = composite_attachment_layers(input_layers_2, ['shield', 'body', 'head'])
        self.assertEqual([l['part'] for l in composed_2], ['shield', 'body', 'head'])

    # 11. Registry Attachment Pairing APIs
    def test_14_registry_attachment_pairing_apis(self):
        """Registry provides attachment pairing inspection and query APIs."""
        pairings = self.registry.list_attachment_pairings()
        self.assertGreaterEqual(len(pairings), 4)

        # Find specific pairing
        p_head = self.registry.find_pairing('novice-male-body-v1', 'novice-male-head-v1')
        self.assertIsNotNone(p_head)
        self.assertEqual(p_head['status'], 'SUPPORTED')

        p_shield = self.registry.find_pairing('novice-male-body-v1', 'dragon-knight-male-shield-v1')
        self.assertIsNotNone(p_shield)
        self.assertEqual(p_shield['status'], 'PARTIAL')

        p_falcon = self.registry.find_pairing('novice-male-body-v1', 'falcon-companion-v1')
        self.assertIsNotNone(p_falcon)
        self.assertEqual(p_falcon['status'], 'UNSUPPORTED')

        # Query by parent
        body_pairings = self.registry.find_pairings_for_parent('novice-male-body-v1')
        self.assertEqual(len(body_pairings), 4)

        # Get by ID
        entry = self.registry.get_attachment_pairing('novice-male-body-v1+novice-male-head-v1')
        self.assertEqual(entry['rule'], 'player_head_anchor_delta')

    def test_15_registry_attachment_pairing_unknown_raises(self):
        """get_attachment_pairing raises ForgeError on unknown ID."""
        with self.assertRaises(ForgeError):
            self.registry.get_attachment_pairing('unknown-parent+unknown-child')

    # 12. Build Attachment Pairing Record
    def test_16_build_attachment_pairing_record(self):
        """build_attachment_pairing_record builds a valid, sealed pairing record."""
        rec = build_attachment_pairing_record(self.body_p, self.jack_p)
        self.assertEqual(rec['id'], 'novice-male-body-v1+jack-head-male-v1')
        self.assertEqual(rec['parent_profile_id'], 'novice-male-body-v1')
        self.assertEqual(rec['child_profile_id'], 'jack-head-male-v1')
        self.assertEqual(rec['status'], 'SUPPORTED')
        self.assertEqual(rec['compatibility']['static_structure'], 'VERIFIED')
        self.assertEqual(rec['compatibility']['preview_composition'], 'VERIFIED')

    # 13. Integration with RSF-8 Topology Requirements Resolution
    def test_17_multi_part_target_topology_resolution(self):
        """resolve_topology resolves multipart target with distinct part occurrence IDs."""
        rp = frozen_runtime_profile('player')
        act = load_actor({
            'schema': 'rsf.actor/v1',
            'id': 'actor-multi-novice',
            'revision': 1,
            'previous_sha256': None,
            'category': 'player',
            'gameplay_job': 'novice',
            'visual': {'body_family': 'human_standard', 'sex': 'male', 'body_variant': None, 'costume': None},
            'parts': ['body', 'head', 'accessory'],
            'runtime_profile': reference(rp),
            'action_profile': 'novice-actions',
            'compatibility': {
                'status': 'SUPPORTED',
                'declarations': [{'id': 'c1', 'status': 'SUPPORTED', 'evidence': ['0' * 64]}],
            },
            'resources': [
                {'part': 'body', 'act_sha256': self.body_p['source_hashes']['act_sha256'], 'spr_sha256': self.body_p['source_hashes']['spr_sha256'], 'inventory_sha256': '0' * 64},
                {'part': 'head', 'act_sha256': self.head_p['source_hashes']['act_sha256'], 'spr_sha256': self.head_p['source_hashes']['spr_sha256'], 'inventory_sha256': '0' * 64},
                {'part': 'accessory', 'act_sha256': self.jack_p['source_hashes']['act_sha256'], 'spr_sha256': self.jack_p['source_hashes']['spr_sha256'], 'inventory_sha256': '0' * 64},
            ],
        })

        target = load_target({
            'schema': 'rsf.target/v2',
            'id': 'target-multi-walk',
            'revision': 1,
            'previous_sha256': None,
            'actor': {'id': act.id, 'revision': act.revision, 'canonical_sha256': act.canonical_sha256},
            'runtime_profile': {'id': rp.id, 'profile_version': rp.profile_version, 'canonical_sha256': rp.canonical_sha256},
            'scope': 'scoped',
            'parts': ['body', 'head', 'accessory'],
            'compatibility': {'status': 'UNVERIFIED', 'declarations': []},
            'actions': [
                {
                    'id': 'Walk',
                    'requirement': 'REQUIRED',
                    'parts': [
                        {
                            'part': 'body',
                            'views': [{'view': v, 'frame_count': 8, 'topology': {'kind': 'explicit', 'layers': ['body']}} for v in range(8)],
                        },
                        {
                            'part': 'head',
                            'views': [{'view': v, 'frame_count': 8, 'topology': {'kind': 'explicit', 'layers': ['head']}} for v in range(8)],
                        },
                        {
                            'part': 'accessory',
                            'views': [{'view': v, 'frame_count': 8, 'topology': {'kind': 'explicit', 'layers': ['accessory']}} for v in range(8)],
                        },
                    ],
                },
            ],
        }, actor=act, profile=rp)

        res = resolve_topology(target, actor=act, profile=rp)
        self.assertEqual(res['status']['work_order'], 'EXACT')
        self.assertEqual(res['status']['specification'], 'COMPLETE_FOR_DECLARED_SCOPE')
        # 3 parts * 8 views = 24 slots
        self.assertEqual(res['counts']['required']['action_view_slots'], 24)
        # 3 parts * 8 views * 8 frames = 192 frame occurrences
        self.assertEqual(res['counts']['required']['frame_occurrences_known'], 192)
        # Verify part occurrence IDs
        part_names = {l['part'] for l in res['layers']}
        self.assertEqual(part_names, {'body', 'head', 'accessory'})

    # 14. Integration with RSF-10 Coverage
    def test_18_multi_part_coverage_evaluation(self):
        """evaluate_coverage distinguishes body and attachment coverage."""
        rp = frozen_runtime_profile('player')
        act = load_actor({
            'schema': 'rsf.actor/v1',
            'id': 'actor-cov-multi',
            'revision': 1,
            'previous_sha256': None,
            'category': 'player',
            'gameplay_job': 'novice',
            'visual': {'body_family': 'human_standard', 'sex': 'male', 'body_variant': None, 'costume': None},
            'parts': ['body', 'head'],
            'runtime_profile': reference(rp),
            'action_profile': 'novice-actions',
            'compatibility': {
                'status': 'SUPPORTED',
                'declarations': [{'id': 'c1', 'status': 'SUPPORTED', 'evidence': ['0' * 64]}],
            },
            'resources': [
                {'part': 'body', 'act_sha256': '0' * 64, 'spr_sha256': '0' * 64, 'inventory_sha256': '0' * 64},
                {'part': 'head', 'act_sha256': '0' * 64, 'spr_sha256': '0' * 64, 'inventory_sha256': '0' * 64},
            ],
        })

        target = load_target({
            'schema': 'rsf.target/v2',
            'id': 'target-cov-walk',
            'revision': 1,
            'previous_sha256': None,
            'actor': {'id': act.id, 'revision': act.revision, 'canonical_sha256': act.canonical_sha256},
            'runtime_profile': {'id': rp.id, 'profile_version': rp.profile_version, 'canonical_sha256': rp.canonical_sha256},
            'scope': 'scoped',
            'parts': ['body', 'head'],
            'compatibility': {'status': 'UNVERIFIED', 'declarations': []},
            'actions': [
                {
                    'id': 'Walk',
                    'requirement': 'REQUIRED',
                    'parts': [
                        {
                            'part': 'body',
                            'views': [{'view': 0, 'frame_count': 1, 'topology': {'kind': 'explicit', 'layers': ['body']}}],
                        },
                        {
                            'part': 'head',
                            'views': [{'view': 0, 'frame_count': 1, 'topology': {'kind': 'explicit', 'layers': ['head']}}],
                        },
                    ],
                },
            ],
        }, actor=act, profile=rp)

        reqs = resolve_topology(target, actor=act, profile=rp)
        # No ledger supplied (all unassigned)
        cov = evaluate_coverage(reqs, None)
        self.assertEqual(cov['status']['assignment_coverage'], 'UNASSIGNED')
        self.assertEqual(cov['counts']['structural']['required_layers'], 2)
        self.assertEqual(cov['counts']['assignments']['unassigned'], 2)

    # 15. Integration with RSF-18 Scoped Review Invalidation
    def test_19_scoped_review_invalidation_preserves_unrelated_parts(self):
        """When an attachment recipe changes, only that attachment's review becomes STALE; body remains intact."""
        rp = frozen_runtime_profile('player')
        act = load_actor({
            'schema': 'rsf.actor/v1',
            'id': 'actor-rev-multi',
            'revision': 1,
            'previous_sha256': None,
            'category': 'player',
            'gameplay_job': 'novice',
            'visual': {'body_family': 'human_standard', 'sex': 'male', 'body_variant': None, 'costume': None},
            'parts': ['body', 'accessory'],
            'runtime_profile': reference(rp),
            'action_profile': 'novice-actions',
            'compatibility': {
                'status': 'SUPPORTED',
                'declarations': [{'id': 'c1', 'status': 'SUPPORTED', 'evidence': ['0' * 64]}],
            },
            'resources': [
                {'part': 'body', 'act_sha256': '0' * 64, 'spr_sha256': '0' * 64, 'inventory_sha256': '0' * 64},
                {'part': 'accessory', 'act_sha256': '0' * 64, 'spr_sha256': '0' * 64, 'inventory_sha256': '0' * 64},
            ],
        })

        target = load_target({
            'schema': 'rsf.target/v2',
            'id': 'target-rev-walk',
            'revision': 1,
            'previous_sha256': None,
            'actor': {'id': act.id, 'revision': act.revision, 'canonical_sha256': act.canonical_sha256},
            'runtime_profile': {'id': rp.id, 'profile_version': rp.profile_version, 'canonical_sha256': rp.canonical_sha256},
            'scope': 'scoped',
            'parts': ['body', 'accessory'],
            'compatibility': {'status': 'UNVERIFIED', 'declarations': []},
            'actions': [
                {
                    'id': 'Walk',
                    'requirement': 'REQUIRED',
                    'parts': [
                        {
                            'part': 'body',
                            'views': [{'view': 0, 'frame_count': 1, 'topology': {'kind': 'explicit', 'layers': ['body']}}],
                        },
                        {
                            'part': 'accessory',
                            'views': [{'view': 0, 'frame_count': 1, 'topology': {'kind': 'explicit', 'layers': ['accessory']}}],
                        },
                    ],
                },
            ],
        }, actor=act, profile=rp)

        reqs = resolve_topology(target, actor=act, profile=rp)
        body_layer_id = next(l['id'] for l in reqs['layers'] if l['part'] == 'body')
        acc_layer_id = next(l['id'] for l in reqs['layers'] if l['part'] == 'accessory')

        # Initial ledger
        ledger_v1 = {
            'assignments': [
                {'requirement_id': body_layer_id, 'kind': 'AUTHORED', 'composition_sha256': 'a' * 64},
                {'requirement_id': acc_layer_id, 'kind': 'AUTHORED', 'composition_sha256': 'b' * 64},
            ]
        }

        # Calculate review bases
        bases_v1 = bases(reqs, ledger_v1)
        event_body = make_event('proj-1', 1, reqs['target'], 'APPROVED', [{'requirement_id': body_layer_id, 'basis_sha256': bases_v1[body_layer_id], 'evidence_sha256': 'e' * 64}], 1)
        event_acc = make_event('proj-1', 1, reqs['target'], 'APPROVED', [{'requirement_id': acc_layer_id, 'basis_sha256': bases_v1[acc_layer_id], 'evidence_sha256': 'e' * 64}], 2)

        # Evaluate reviews under v1: both APPROVED
        rev_v1 = evaluate_reviews('proj-1', [event_body, event_acc], reqs, ledger_v1)
        state_map_v1 = {s['requirement_id']: s for s in rev_v1['occurrences']}
        self.assertEqual(state_map_v1[body_layer_id]['state'], 'APPROVED')
        self.assertEqual(state_map_v1[acc_layer_id]['state'], 'APPROVED')

        # Modify ONLY accessory assignment in ledger v2
        ledger_v2 = {
            'assignments': [
                {'requirement_id': body_layer_id, 'kind': 'AUTHORED', 'composition_sha256': 'a' * 64},  # unchanged!
                {'requirement_id': acc_layer_id, 'kind': 'AUTHORED', 'composition_sha256': 'c' * 64},  # changed!
            ]
        }

        # Evaluate reviews under v2: body remains APPROVED; accessory becomes STALE
        rev_v2 = evaluate_reviews('proj-1', [event_body, event_acc], reqs, ledger_v2)
        state_map_v2 = {s['requirement_id']: s for s in rev_v2['occurrences']}
        self.assertEqual(state_map_v2[body_layer_id]['state'], 'APPROVED', 'Unchanged body layer review must remain APPROVED')
        self.assertEqual(state_map_v2[acc_layer_id]['state'], 'STALE', 'Modified accessory layer review must transition to STALE')
        self.assertIn('COMPOSITION_CHANGED_OR_REQUIREMENT_UNAVAILABLE', state_map_v2[acc_layer_id]['causes'])


if __name__ == '__main__':
    unittest.main()
