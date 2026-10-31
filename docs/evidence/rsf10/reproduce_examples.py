"""Reproduce public RSF-10 coverage and missing-art work-order evidence.

Only synthetic, non-image bytes are used. No operator approvals are generated.
"""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_contracts import actor_document, target_document
from test_ledger import example_requirements, source, assignment, document, operation
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, load_target
from ro_sprite_forge.core.coverage import evaluate_coverage, format_work_order
from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger
from ro_sprite_forge.core.topology import resolve_topology


def examples():
    requirements = example_requirements()

    # 1. Fully unassigned Walk target
    cov_unassigned = evaluate_coverage(requirements)
    wo_unassigned_text = format_work_order(cov_unassigned)

    # 2. Partially assigned Walk target (RSF-10 synthetic Walk scenario)
    declaration = document(requirements)
    declaration['sources'] = [source('art-a'), source('art-d', content=b'art-d-bytes')]
    declaration['assignments'] = [
        assignment(requirements, 0, 'A', 'DIRECT_SOURCE', sid='art-a'),
        assignment(requirements, 1, 'B', 'EXPLICIT_REUSE', dep='A', recipe=[operation('mirror_x')]),
        assignment(
            requirements,
            2,
            'C',
            'EXPLICIT_REUSE',
            dep='B',
            recipe=[operation('translate', x=3, y=-2)],
        ),
        assignment(requirements, 3, 'D', 'DIRECT_SOURCE', sid='art-d'),
    ]
    data = {
        'art-a': b'operator supplied synthetic bytes',
        'art-d': b'art-d-bytes',
    }
    cov_partial = evaluate_coverage(requirements, declaration, source_bytes=data)
    wo_partial_text = format_work_order(cov_partial)

    # 3. Missing source bytes
    cov_missing = evaluate_coverage(
        requirements,
        declaration,
        source_bytes={**data, 'art-a': None},
    )

    # 4. Invalid source hash (hash mismatch)
    cov_invalid_hash = evaluate_coverage(
        requirements,
        declaration,
        source_bytes={**data, 'art-a': b'corrupted changed bytes'},
    )

    # 5. Scoped versus full target
    p = frozen_runtime_profile('player')
    a = load_actor(actor_document(p))
    doc_full = target_document(a, p, count=1, scope='full')
    doc_full['actions'] = [
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
    target_full = load_target(doc_full, actor=a, profile=p)
    req_full = resolve_topology(target_full, actor=a, profile=p)
    cov_full = evaluate_coverage(req_full, target=target_full)

    # 6. Underspecified topology
    doc_underspec = target_document(a, p, count=2)
    doc_underspec['actions'][0]['parts'][0]['views'] = [
        {'view': 0, 'frame_count': None, 'topology': {'kind': 'explicit', 'layers': ['body']}},
        {'view': 1, 'frame_count': 2, 'topology': None},
    ]
    target_underspec = load_target(doc_underspec, actor=a, profile=p)
    req_underspec = resolve_topology(target_underspec, actor=a, profile=p)
    cov_underspec = evaluate_coverage(req_underspec, target=target_underspec)

    # 7. Source revision change reevaluation
    ledger_initial = load_ledger(declaration, requirements=requirements)
    changed = copy.deepcopy(declaration)
    changed['sources'][0].update(sha256=digest(b'new-bytes-r2'), revision=2)
    changed['assignments'][0]['source']['revision'] = 2
    changed['assignments'][0]['revision'] = 2
    changed['assignments'][1]['dependency']['revision'] = 2
    changed['assignments'][1]['revision'] = 2
    changed['assignments'][2]['dependency']['revision'] = 2
    changed['assignments'][2]['revision'] = 2
    changed.update(revision=2, previous_sha256=ledger_initial.canonical_sha256)
    revised_ledger = load_ledger(changed, requirements=requirements, previous=ledger_initial)
    cov_revised = evaluate_coverage(
        requirements,
        revised_ledger,
        source_bytes={**data, 'art-a': b'new-bytes-r2'},
    )

    return {
        'schema': 'rsf.coverage-examples/v1',
        'synthetic_only': True,
        'image_processing': 'NOT_RUN',
        'operator_approvals_recorded': 0,
        'requirements_walk_sha256': requirements['canonical_sha256'],
        'scenarios': {
            '1_fully_unassigned_walk': {
                'report': cov_unassigned,
                'work_order_text': wo_unassigned_text,
            },
            '2_partially_assigned_walk': {
                'report': cov_partial,
                'work_order_text': wo_partial_text,
            },
            '3_missing_source': {
                'report': cov_missing,
            },
            '4_invalid_source_hash': {
                'report': cov_invalid_hash,
            },
            '5_full_profile_target': {
                'report': cov_full,
            },
            '6_underspecified_topology': {
                'report': cov_underspec,
            },
            '7_source_revision_changed': {
                'report': cov_revised,
            },
        },
    }


if __name__ == '__main__':
    first = canonical_bytes(examples())
    assert first == canonical_bytes(examples()), 'Non-deterministic evidence'
    (Path(__file__).parent / 'examples.json').write_bytes(first)
    value = json.loads(first)
    p_rep = value['scenarios']['2_partially_assigned_walk']['report']
    print(
        json.dumps(
            {
                'examples_sha256': digest(first),
                'synthetic_walk_requirements_sha256': value['requirements_walk_sha256'],
                'scenario_2_counts': p_rep['counts'],
                'scenario_2_status': p_rep['status'],
                'scenario_2_unresolved_count': len(p_rep['unresolved_items']),
            },
            sort_keys=True,
            indent=2,
        )
    )
