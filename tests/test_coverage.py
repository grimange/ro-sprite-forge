"""RSF-10 coverage evaluation and missing-art work-order tests."""
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parent)]

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import (
    frozen_runtime_profile,
    load_actor,
    load_target,
    TargetContract,
)
from ro_sprite_forge.core.coverage import evaluate_coverage, format_work_order, coverage_schema
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.ledger import (
    load_ledger,
    resolve_ledger,
    assignment_binding,
)
from ro_sprite_forge.core.topology import resolve_topology
from test_contracts import actor_document, target_document
from test_ledger import (
    example_requirements,
    source,
    assignment,
    document,
    operation,
)


class CoverageTests(unittest.TestCase):
    def setUp(self):
        self.r = example_requirements()
        self.d = document(self.r)
        self.d['sources'] = [source('art-a'), source('art-d', content=b'art-d-bytes')]
        self.d['assignments'] = [
            assignment(self.r, 0, 'A', 'DIRECT_SOURCE', sid='art-a'),
            assignment(self.r, 1, 'B', 'EXPLICIT_REUSE', dep='A', recipe=[operation('mirror_x')]),
            assignment(
                self.r,
                2,
                'C',
                'EXPLICIT_REUSE',
                dep='B',
                recipe=[operation('translate', x=3, y=-2)],
            ),
            assignment(self.r, 3, 'D', 'DIRECT_SOURCE', sid='art-d'),
        ]
        self.data = {
            'art-a': b'operator supplied synthetic bytes',
            'art-d': b'art-d-bytes',
        }

    def test_synthetic_acceptance_scenario_accounting(self):
        """RSF-10 §13 synthetic Walk acceptance scenario."""
        cov = evaluate_coverage(self.r, self.d, source_bytes=self.data)
        # Structural
        s_counts = cov['counts']['structural']
        self.assertEqual(s_counts['required_slots'], 8)
        self.assertEqual(s_counts['required_frames'], 48)
        self.assertEqual(s_counts['required_layers'], 48)
        self.assertEqual(s_counts['underspecified_slots'], 0)
        self.assertEqual(cov['status']['structural_specification'], 'COMPLETE_FOR_DECLARED_SCOPE')

        # Assignment counts
        a_counts = cov['counts']['assignments']
        self.assertEqual(a_counts['direct'], 2)
        self.assertEqual(a_counts['explicit_reuse'], 2)
        self.assertEqual(a_counts['unassigned'], 44)
        self.assertEqual(a_counts['unique_selected_sources'], 2)
        self.assertEqual(a_counts['distinct_source_contents'], 2)
        self.assertEqual(a_counts['approved_source_art_roots'], 0)
        self.assertEqual(a_counts['accepted_reuse'], 0)
        self.assertEqual(a_counts['validated_replacement_occurrences'], 0)

        # Validation counts
        v_counts = cov['counts']['validation']
        self.assertEqual(v_counts['available_sources'], 2)
        self.assertEqual(v_counts['reused_sources'], 2)
        self.assertEqual(v_counts['valid_assignments'], 4)
        self.assertEqual(v_counts['invalid_assignments'], 0)
        self.assertEqual(v_counts['unverified_assignments'], 0)

        # Review counts
        r_counts = cov['counts']['review']
        self.assertEqual(r_counts['approved'], 0)
        self.assertEqual(r_counts['unverified'], 4)
        self.assertEqual(r_counts['rejected'], 0)
        self.assertEqual(r_counts['not_required'], 0)

        # Pending technical checks
        p_checks = cov['counts']['pending_technical_checks']
        self.assertEqual(p_checks['image_decoding'], 4)
        self.assertEqual(p_checks['transformation_execution'], 2)

        # Work order categories
        wo_cats = cov['counts']['work_order_categories']
        self.assertEqual(wo_cats['supply_artwork'], 44)
        self.assertEqual(wo_cats['review_artwork'], 4)
        self.assertEqual(len(cov['unresolved_items']), 48)

        # Status orthogonal dimensions
        status = cov['status']
        self.assertEqual(status['completeness'], 'INCOMPLETE')
        self.assertEqual(status['assignment_coverage'], 'PARTIAL')
        self.assertEqual(status['accepted_artwork_coverage'], 'INCOMPLETE')
        self.assertEqual(status['technical_validation'], 'NOT_RUN')
        self.assertEqual(status['preview_fidelity'], 'UNVERIFIED')
        self.assertEqual(status['native_evidence'], 'UNVERIFIED')
        self.assertFalse(status['export_ready'])

    def test_fully_unassigned_walk(self):
        """Target with zero artwork assignments (ledger=None)."""
        cov = evaluate_coverage(self.r)
        self.assertEqual(cov['counts']['assignments']['unassigned'], 48)
        self.assertEqual(cov['counts']['assignments']['direct'], 0)
        self.assertEqual(cov['counts']['assignments']['explicit_reuse'], 0)
        self.assertEqual(cov['status']['assignment_coverage'], 'UNASSIGNED')
        self.assertEqual(cov['status']['completeness'], 'INCOMPLETE')
        self.assertEqual(len(cov['unresolved_items']), 48)
        self.assertTrue(all(item['category'] == 'SUPPLY_ARTWORK' for item in cov['unresolved_items']))
        self.assertTrue(all(item['reason'] == 'UNASSIGNED_OCCURRENCE' for item in cov['unresolved_items']))

    def test_fully_assigned_but_unreviewed_walk(self):
        """All 48 layers assigned to valid sources, but visual review is unverified."""
        d = document(self.r)
        d['sources'] = [source(f'art-{i}', content=f'bytes-{i}'.encode('utf-8')) for i in range(48)]
        d['assignments'] = [
            assignment(self.r, i, f'A{i}', 'DIRECT_SOURCE', sid=f'art-{i}')
            for i in range(48)
        ]
        data = {f'art-{i}': f'bytes-{i}'.encode('utf-8') for i in range(48)}
        cov = evaluate_coverage(self.r, d, source_bytes=data)

        self.assertEqual(cov['counts']['assignments']['unassigned'], 0)
        self.assertEqual(cov['counts']['assignments']['direct'], 48)
        self.assertEqual(cov['counts']['review']['unverified'], 48)
        self.assertEqual(cov['status']['assignment_coverage'], 'COMPLETE_FOR_DECLARED_SCOPE')
        self.assertEqual(cov['status']['accepted_artwork_coverage'], 'INCOMPLETE')
        self.assertEqual(cov['status']['completeness'], 'INCOMPLETE')
        self.assertEqual(len(cov['unresolved_items']), 48)
        self.assertTrue(all(item['category'] == 'REVIEW_ARTWORK' for item in cov['unresolved_items']))
        self.assertTrue(all(item['reason'] == 'VISUAL_REVIEW_PENDING' for item in cov['unresolved_items']))

    def test_fully_assigned_and_approved_scoped_walk(self):
        """All 48 occurrences assigned, valid, and operator-approved for declared Walk scope."""
        p = frozen_runtime_profile('player')
        a = load_actor(actor_document(p))
        d_target = target_document(a, p, count=6)
        d_target['actions'][0]['parts'][0]['views'] = [
            {'view': i, 'frame_count': 6, 'topology': {'kind': 'explicit', 'layers': ['body']}}
            for i in range(8)
        ]
        target = load_target(d_target, actor=a, profile=p)
        r = resolve_topology(target, actor=a, profile=p)

        d = document(r)
        d['sources'] = [source(f'art-{i}', content=f'bytes-{i}'.encode('utf-8')) for i in range(48)]
        d['assignments'] = []
        data = {}

        # Resolve ledger first to compute basis hashes
        for i in range(48):
            d['assignments'].append(assignment(r, i, f'A{i}', 'DIRECT_SOURCE', sid=f'art-{i}'))
            data[f'art-{i}'] = f'bytes-{i}'.encode('utf-8')

        pre_resolved = resolve_ledger(load_ledger(d, requirements=r), requirements=r, source_bytes=data)
        # Bind operator review with exact composition hashes
        for a_row in pre_resolved['assignments']:
            basis = a_row['composition_sha256']
            item = next(x for x in d['assignments'] if x['id'] == a_row['id'])
            item['review'] = {
                'state': 'APPROVED',
                'authority': 'OPERATOR',
                'operator': 'lead-animator',
                'basis_sha256': basis,
                'evidence_sha256': 'a' * 64,
                'policy': 'VISUAL_DECISION',
            }

        cov = evaluate_coverage(r, d, source_bytes=data, target=target)
        self.assertEqual(cov['counts']['assignments']['unassigned'], 0)
        self.assertEqual(cov['counts']['assignments']['validated_replacement_occurrences'], 48)
        self.assertEqual(cov['counts']['review']['approved'], 48)
        self.assertEqual(len(cov['unresolved_items']), 0)
        self.assertEqual(cov['status']['completeness'], 'COMPLETE_FOR_DECLARED_SCOPE')
        self.assertEqual(cov['status']['structural_specification'], 'COMPLETE_FOR_DECLARED_SCOPE')
        self.assertEqual(cov['status']['assignment_coverage'], 'COMPLETE_FOR_DECLARED_SCOPE')
        self.assertEqual(cov['status']['accepted_artwork_coverage'], 'COMPLETE_FOR_DECLARED_SCOPE')
        self.assertFalse(cov['status']['full_profile_specified'])

    def test_full_profile_target_coverage(self):
        """Full-profile target coverage evaluation: scoped vs full profile distinction."""
        p = frozen_runtime_profile('player')
        a = load_actor(actor_document(p))
        doc = target_document(a, p, count=1, scope='full')
        doc['actions'] = [
            {
                'id': act['id'],
                'requirement': 'REQUIRED',
                'parts': [
                    {
                        'part': 'body',
                        'views': [
                            {'view': v, 'frame_count': 1, 'topology': {'kind': 'explicit', 'layers': ['body']}}
                            for v in range(8)
                        ],
                    }
                ],
            }
            for act in p.to_dict()['actions']
        ]
        target = load_target(doc, actor=a, profile=p)
        r = resolve_topology(target, actor=a, profile=p)
        self.assertTrue(r['status']['full_profile_specified'])

        # Without assignments:
        cov_empty = evaluate_coverage(r, target=target)
        self.assertEqual(cov_empty['status']['structural_specification'], 'COMPLETE_FOR_FULL_PROFILE')
        self.assertEqual(cov_empty['status']['assignment_coverage'], 'UNASSIGNED')
        self.assertEqual(cov_empty['status']['completeness'], 'INCOMPLETE')

    def test_missing_source_bytes_propagation(self):
        """Missing source bytes propagate RESTORE_OR_LOCATE_SOURCE through reuse chain."""
        data = copy.deepcopy(self.data)
        data['art-a'] = None  # Observed missing
        cov = evaluate_coverage(self.r, self.d, source_bytes=data)

        # Occurrence A (direct) and B, C (reused) should be affected
        items_by_req = {i['requirement_id']: i for i in cov['unresolved_items']}
        req_a = self.d['assignments'][0]['requirement_id']
        req_b = self.d['assignments'][1]['requirement_id']
        req_c = self.d['assignments'][2]['requirement_id']
        req_d = self.d['assignments'][3]['requirement_id']

        self.assertEqual(items_by_req[req_a]['category'], 'RESTORE_OR_LOCATE_SOURCE')
        self.assertEqual(items_by_req[req_a]['reason'], 'SOURCE_UNAVAILABLE')
        self.assertEqual(items_by_req[req_b]['category'], 'RESTORE_OR_LOCATE_SOURCE')
        self.assertEqual(items_by_req[req_b]['reason'], 'DEPENDENCY_SOURCE_MISSING')
        self.assertEqual(items_by_req[req_c]['category'], 'RESTORE_OR_LOCATE_SOURCE')
        self.assertEqual(items_by_req[req_c]['reason'], 'DEPENDENCY_SOURCE_MISSING')

        # D uses independent source art-d and is unaffected by art-a missing
        self.assertEqual(items_by_req[req_d]['category'], 'REVIEW_ARTWORK')
        self.assertEqual(items_by_req[req_d]['validation'], 'VALID')

    def test_invalid_source_hash_propagation(self):
        """Invalid source hash propagates CORRECT_INVALID_SOURCE_OR_ASSIGNMENT."""
        data = copy.deepcopy(self.data)
        data['art-a'] = b'wrong corrupted bytes'
        cov = evaluate_coverage(self.r, self.d, source_bytes=data)

        items_by_req = {i['requirement_id']: i for i in cov['unresolved_items']}
        req_a = self.d['assignments'][0]['requirement_id']
        req_b = self.d['assignments'][1]['requirement_id']
        req_c = self.d['assignments'][2]['requirement_id']
        req_d = self.d['assignments'][3]['requirement_id']

        self.assertEqual(items_by_req[req_a]['category'], 'CORRECT_INVALID_SOURCE_OR_ASSIGNMENT')
        self.assertEqual(items_by_req[req_a]['reason'], 'SOURCE_HASH_MISMATCH')
        self.assertEqual(items_by_req[req_b]['category'], 'CORRECT_INVALID_SOURCE_OR_ASSIGNMENT')
        self.assertEqual(items_by_req[req_b]['reason'], 'DEPENDENCY_INVALID')
        self.assertEqual(items_by_req[req_c]['category'], 'CORRECT_INVALID_SOURCE_OR_ASSIGNMENT')
        self.assertEqual(items_by_req[req_c]['reason'], 'DEPENDENCY_INVALID')

        # D remains unaffected
        self.assertEqual(items_by_req[req_d]['validation'], 'VALID')

    def test_unverified_source_bytes(self):
        """Unprovided source bytes yield VERIFY_SOURCE_CONTENT."""
        # Provide bytes only for art-d; art-a is unprovided
        data = {'art-d': b'art-d-bytes'}
        cov = evaluate_coverage(self.r, self.d, source_bytes=data)

        items_by_req = {i['requirement_id']: i for i in cov['unresolved_items']}
        req_a = self.d['assignments'][0]['requirement_id']
        self.assertEqual(items_by_req[req_a]['category'], 'VERIFY_SOURCE_CONTENT')
        self.assertEqual(items_by_req[req_a]['reason'], 'SOURCE_UNVERIFIED')

    def test_rejected_visual_review(self):
        """Operator explicitly rejected review."""
        pre = resolve_ledger(load_ledger(self.d, requirements=self.r), requirements=self.r, source_bytes=self.data)
        basis = pre['assignments'][0]['composition_sha256']
        self.d['assignments'][0]['review'] = {
            'state': 'REJECTED',
            'authority': 'OPERATOR',
            'operator': 'art-director',
            'basis_sha256': basis,
            'evidence_sha256': 'a' * 64,
            'policy': 'VISUAL_DECISION',
        }

        cov = evaluate_coverage(self.r, self.d, source_bytes=self.data)
        items_by_req = {i['requirement_id']: i for i in cov['unresolved_items']}
        req_a = self.d['assignments'][0]['requirement_id']
        self.assertEqual(items_by_req[req_a]['category'], 'CORRECT_INVALID_SOURCE_OR_ASSIGNMENT')
        self.assertEqual(items_by_req[req_a]['reason'], 'REVIEW_REJECTED')

    def test_stale_review_binding(self):
        """Stale review binding from composition change yields REVIEW_STALE."""
        self.d['assignments'][0]['review'] = {
            'state': 'APPROVED',
            'authority': 'OPERATOR',
            'operator': 'art-director',
            'basis_sha256': '1' * 64,  # Mismatched basis
            'evidence_sha256': 'a' * 64,
            'policy': 'VISUAL_DECISION',
        }
        cov = evaluate_coverage(self.r, self.d, source_bytes=self.data)
        items_by_req = {i['requirement_id']: i for i in cov['unresolved_items']}
        req_a = self.d['assignments'][0]['requirement_id']
        self.assertEqual(items_by_req[req_a]['category'], 'REVIEW_STALE')
        self.assertEqual(items_by_req[req_a]['reason'], 'REVIEW_STALE')

    def test_classic_reference_fallback_does_not_fulfill_replacement(self):
        """Classic reference origin does not count as authored replacement coverage."""
        d = document(self.r)
        d['sources'] = [
            {
                'id': 'classic-1',
                'revision': 1,
                'sha256': digest(b'classic-ref-bytes'),
                'kind': 'IMPORTED_IMAGE',
                'origin': 'CLASSIC_REFERENCE',
                'external_ref': 'classic-1',
                'image': {'pool': 'indexed', 'index': 0},
                'provenance': {'act_sha256': '0' * 64, 'spr_sha256': '1' * 64, 'inventory_sha256': '2' * 64},
            }
        ]
        d['assignments'] = [
            assignment(self.r, 0, 'A', 'DIRECT_SOURCE', sid='classic-1')
        ]
        # First compute basis for NOT_REQUIRED
        pre = resolve_ledger(load_ledger(d, requirements=self.r), requirements=self.r, source_bytes={'classic-1': b'classic-ref-bytes'})
        basis = pre['assignments'][0]['composition_sha256']
        d['assignments'][0]['review'] = {
            'state': 'NOT_REQUIRED',
            'authority': 'OPERATOR',
            'operator': 'human-policy',
            'basis_sha256': basis,
            'evidence_sha256': 'a' * 64,
            'policy': 'UNCHANGED_REFERENCE',
        }
        cov = evaluate_coverage(self.r, d, source_bytes={'classic-1': b'classic-ref-bytes'})

        self.assertEqual(cov['counts']['assignments']['validated_replacement_occurrences'], 0)
        self.assertEqual(cov['counts']['review']['not_required'], 1)
        items_by_req = {i['requirement_id']: i for i in cov['unresolved_items']}
        req_a = d['assignments'][0]['requirement_id']
        self.assertEqual(items_by_req[req_a]['category'], 'SUPPLY_ARTWORK')
        self.assertEqual(items_by_req[req_a]['reason'], 'CLASSIC_REFERENCE_FALLBACK')

    def test_optional_requirements(self):
        """Optional requirements are counted separately and do not block declared completeness."""
        p = frozen_runtime_profile('player')
        a = load_actor(actor_document(p))
        d_target = target_document(a, p, count=2)
        # Add an optional action
        d_target['actions'].append({
            'id': 'Sit',
            'requirement': 'OPTIONAL',
            'parts': [
                {
                    'part': 'body',
                    'views': [
                        {'view': 0, 'frame_count': 1, 'topology': {'kind': 'explicit', 'layers': ['body']}}
                    ],
                }
            ],
        })
        target = load_target(d_target, actor=a, profile=p)
        r = resolve_topology(target, actor=a, profile=p)
        cov = evaluate_coverage(r)
        self.assertGreater(cov['counts']['structural']['optional_slots'], 0)
        self.assertGreater(cov['counts']['structural']['optional_layers'], 0)

    def test_excluded_actions_out_of_scope(self):
        """OUT_OF_SCOPE actions are excluded from slots and reported in excluded_actions."""
        p = frozen_runtime_profile('player')
        a = load_actor(actor_document(p))
        d_target = target_document(a, p, count=2)
        d_target['actions'].append({
            'id': 'Sit',
            'requirement': 'OUT_OF_SCOPE',
            'parts': [],
        })
        target = load_target(d_target, actor=a, profile=p)
        r = resolve_topology(target, actor=a, profile=p)
        cov = evaluate_coverage(r, target=target)
        self.assertIn('Sit', cov['excluded_actions'])

    def test_underspecified_frame_count_and_topology(self):
        """Underspecified frame count and topology produce RESOLVE_REQUIREMENTS items."""
        p = frozen_runtime_profile('player')
        a = load_actor(actor_document(p))
        d_target = target_document(a, p, count=2)
        # One view with frame_count=None, one view with topology=None
        d_target['actions'][0]['parts'][0]['views'] = [
            {'view': 0, 'frame_count': None, 'topology': {'kind': 'explicit', 'layers': ['body']}},
            {'view': 1, 'frame_count': 2, 'topology': None},
        ]
        target = load_target(d_target, actor=a, profile=p)
        r = resolve_topology(target, actor=a, profile=p)
        cov = evaluate_coverage(r, target=target)

        self.assertEqual(cov['status']['structural_specification'], 'UNDERSPECIFIED')
        self.assertEqual(cov['status']['completeness'], 'UNDERSPECIFIED')
        self.assertGreater(cov['counts']['work_order_categories']['resolve_requirements'], 0)
        req_items = [i for i in cov['unresolved_items'] if i['category'] == 'RESOLVE_REQUIREMENTS']
        reasons = {i['reason'] for i in req_items}
        self.assertIn('UNDERSPECIFIED_FRAME_COUNT', reasons)
        self.assertIn('UNDERSPECIFIED_LAYER_TOPOLOGY', reasons)

    def test_runtime_unsupported_slot(self):
        """Runtime unsupported slot is surfaced with RESOLVE_RUNTIME_SUPPORT."""
        from ro_sprite_forge.core.contracts import load_runtime_profile
        p = frozen_runtime_profile('player')
        p_doc = p.to_dict()
        p_doc.pop('canonical_sha256')
        p_doc['actions'].append({
            'id': 'CustomDodge',
            'group': None,
            'slots': [],
            'mapping': 'UNSUPPORTED',
            'reachability': 'UNSUPPORTED',
            'evidence': [p_doc['source']['evidence'][0]['sha256']]
        })
        p_doc['profile_version'] = '1.1.0'
        custom_profile = load_runtime_profile(p_doc)
        a = load_actor(actor_document(custom_profile))
        d_target = target_document(a, custom_profile, count=2)
        d_target['actions'].append({
            'id': 'CustomDodge',
            'requirement': 'REQUIRED',
            'parts': [
                {
                    'part': 'body',
                    'views': [
                        {'view': 0, 'frame_count': 1, 'topology': {'kind': 'explicit', 'layers': ['body']}}
                    ],
                }
            ],
        })
        target = load_target(d_target, actor=a, profile=custom_profile)
        r = resolve_topology(target, actor=a, profile=custom_profile)
        cov = evaluate_coverage(r, target=target)

        dodge_items = [i for i in cov['unresolved_items'] if i['action'] == 'CustomDodge']
        self.assertTrue(any('RUNTIME_ACTION_UNSUPPORTED' in i['issues'] for i in dodge_items))

    def test_reevaluation_determinism_and_evolution(self):
        """Coverage reevaluation across lifecycle states produces stable, deterministic results."""
        # 1. Unassigned
        cov1 = evaluate_coverage(self.r)
        cov1_repeat = evaluate_coverage(self.r)
        self.assertEqual(canonical_bytes(cov1), canonical_bytes(cov1_repeat))
        self.assertEqual(cov1['counts']['assignments']['unassigned'], 48)

        # 2. Assigned with unverified source bytes
        cov2 = evaluate_coverage(self.r, self.d, source_bytes={})
        self.assertEqual(cov2['counts']['assignments']['unassigned'], 44)
        self.assertEqual(cov2['counts']['validation']['unverified_sources'], 4)

        # 3. Valid source bytes provided
        cov3 = evaluate_coverage(self.r, self.d, source_bytes=self.data)
        self.assertEqual(cov3['counts']['validation']['valid_assignments'], 4)
        self.assertEqual(cov3['counts']['review']['unverified'], 4)

        # 4. Source corrupted
        data_bad = copy.deepcopy(self.data)
        data_bad['art-a'] = b'corrupted'
        cov4 = evaluate_coverage(self.r, self.d, source_bytes=data_bad)
        self.assertEqual(cov4['counts']['validation']['invalid_assignments'], 3)

        # 5. Source corrected back
        cov5 = evaluate_coverage(self.r, self.d, source_bytes=self.data)
        self.assertEqual(canonical_bytes(cov3), canonical_bytes(cov5))

    def test_format_work_order_text(self):
        """Human-readable work order text formatting and filtering."""
        cov = evaluate_coverage(self.r, self.d, source_bytes=self.data)
        text = format_work_order(cov)
        self.assertIn("RO Sprite Forge — Missing-Art Work Order", text)
        self.assertIn("Target: winter-walk", text)
        self.assertIn("Overall Completeness:      INCOMPLETE", text)
        self.assertIn("SUPPLY_ARTWORK", text)
        self.assertIn("REVIEW_ARTWORK", text)

        # Filter by category
        filtered_supply = format_work_order(cov, filter_category='SUPPLY_ARTWORK')
        self.assertIn("[SUPPLY_ARTWORK]", filtered_supply)
        self.assertNotIn("[REVIEW_ARTWORK]", filtered_supply)

        filtered_review = format_work_order(cov, filter_category='REVIEW_ARTWORK')
        self.assertIn("[REVIEW_ARTWORK]", filtered_review)
        self.assertNotIn("[SUPPLY_ARTWORK]", filtered_review)

        # Show all occurrences (including resolved if any)
        text_all = format_work_order(cov, filter_status='all')
        self.assertIn("ACTIONABLE WORK ORDER ITEMS (48 items)", text_all)

    def test_cli_coverage_and_missing(self):
        """CLI execution of coverage and missing subcommands."""
        from ro_sprite_forge.cli import main

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            req_path = root / 'requirements.json'
            ledger_path = root / 'ledger.json'
            source_path = root / 'art-a.png'
            out_cov = root / 'coverage.json'
            out_txt = root / 'work-order.txt'

            req_path.write_bytes(canonical_bytes(self.r))
            loaded_ledger = load_ledger(self.d, requirements=self.r)
            ledger_path.write_bytes(canonical_bytes(loaded_ledger.to_dict()))
            source_path.write_bytes(self.data['art-a'])

            # 1. Test coverage command with json output and work order text output
            exit_code = main([
                'coverage',
                '--requirements', str(req_path),
                '--ledger', str(ledger_path),
                '--source', f'art-a={source_path}',
                '--output', str(out_cov),
                '--work-order-output', str(out_txt),
            ])
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_cov.is_file())
            self.assertTrue(out_txt.is_file())

            cov_json = json.loads(out_cov.read_text())
            self.assertEqual(cov_json['schema'], 'rsf.coverage-report/v1')
            self.assertEqual(cov_json['counts']['assignments']['direct'], 2)

            txt_content = out_txt.read_text()
            self.assertIn("Missing-Art Work Order", txt_content)

            # 2. Test atomic refusal of existing output
            exit_code_dup = main([
                'coverage',
                '--requirements', str(req_path),
                '--output', str(out_cov),  # already exists
            ])
            self.assertEqual(exit_code_dup, 3)

            # 3. Test missing command writing text to new file
            out_missing = root / 'missing-output.txt'
            exit_code = main([
                'missing',
                '--requirements', str(req_path),
                '--ledger', str(ledger_path),
                '--output', str(out_missing),
            ])
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_missing.is_file())
            self.assertIn("Missing-Art Work Order", out_missing.read_text())

            # 4. Test missing command writing json to new file
            out_missing_json = root / 'missing-output.json'
            exit_code = main([
                'missing',
                '--requirements', str(req_path),
                '--ledger', str(ledger_path),
                '--format', 'json',
                '--output', str(out_missing_json),
            ])
            self.assertEqual(exit_code, 0)
            self.assertTrue(out_missing_json.is_file())
            parsed_m = json.loads(out_missing_json.read_text())
            self.assertEqual(parsed_m['schema'], 'rsf.coverage-report/v1')

    def test_negative_cases(self):
        """Negative cases for input validation and mismatch rejection."""
        # 1. Changed requirements hash in ledger
        bad_ledger = copy.deepcopy(self.d)
        bad_ledger['requirements_sha256'] = '0' * 64
        with self.assertRaises(ForgeError):
            evaluate_coverage(self.r, bad_ledger)

        # 2. Target mismatch
        bad_ledger2 = copy.deepcopy(self.d)
        bad_ledger2['target']['revision'] = 99
        with self.assertRaises(ForgeError):
            evaluate_coverage(self.r, bad_ledger2)

        # 3. Invalid target contract reference
        p = frozen_runtime_profile('player')
        a = load_actor(actor_document(p))
        doc_other = target_document(a, p)
        doc_other['id'] = 'other-target'
        other_target = load_target(doc_other, actor=a, profile=p)
        with self.assertRaises(ForgeError):
            evaluate_coverage(self.r, target=other_target)


if __name__ == '__main__':
    unittest.main()
