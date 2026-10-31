"""Canonical pre-build review events. No artistic inference or image execution.

The ledger's established assignment basis remains the dependency authority. This
versioned review envelope adds ordered frame context and inspectable preview policy.
Events never rewrite assignment revisions or historical decisions.
"""
import copy
import json
from importlib.resources import files
from ro_sprite_forge.core.canonical import canonical_bytes, check, check_seal, digest, sealed
from ro_sprite_forge.core.contracts import _shape

SEMANTICS = 'rsf.operator-layer-review/v1'
LIMITATIONS = [
    'PROVISIONAL: ordered source-layer inspection; not a compiled animation or native rendering approval.',
    'Only executed source recipes are reviewable; timing, placement and attachments remain separate technical evidence.',
    'Visual review does not establish replacement coverage, export readiness or native acceptance.',
]


def review_schema():
    return json.loads(files('ro_sprite_forge').joinpath('schemas/review-event-v1.json').read_text())


def validate_events(events, project_id):
    check(type(events) is list and len(events) <= 4096, 'Review history must contain at most 4096 events.')
    ids = set()
    for index, event in enumerate(events):
        _shape(event, review_schema())
        check_seal({k:v for k,v in event.items() if k != 'id'}, 'rsf.review-event/v1')
        check(event['project_id'] == project_id, 'Review project identity mismatch.')
        check(event['revision'] == index + 1, 'Review event revision sequence mismatch.')
        check(event['id'] == 'review-' + event['canonical_sha256'], 'Review event identity mismatch.')
        check(event['id'] not in ids, 'Duplicate review event.')
        ids.add(event['id'])
        members = event['members']
        check([m['requirement_id'] for m in members] == sorted({m['requirement_id'] for m in members}),
              'Review scope must be unique and canonically ordered.')


def bases(requirements, ledger_report):
    """Local composition basis: unrelated requirements/project metadata are excluded."""
    check_seal(requirements, 'rsf.resolved-requirements/v1')
    rows = {a['requirement_id']: a for a in (ledger_report or {}).get('assignments', [])}
    frames = {f['id']:f for f in requirements['frames']}
    slots = {s['id']:s for s in requirements['slots']}
    from ro_sprite_forge.core.ledger import composition_target
    from ro_sprite_forge.formats.preview import RENDERER_VERSION, GEOMETRY_VERSION
    from ro_sprite_forge.core.timeline import TIMING_VERSION
    groups = {}
    for layer in requirements['layers']:
        groups.setdefault(layer['frame_id'], []).append(layer)
    result = {}
    for layer in requirements['layers']:
        row = rows.get(layer['id'])
        if row is None or row['kind'] == 'UNASSIGNED':
            continue
        payload = dict(schema='rsf.operator-composition-basis/v1',
                       target=composition_target(requirements, layer), runtime_profile=requirements['runtime_profile'],
                       requirement=layer, frame=frames[layer['frame_id']],
                       slot=slots[frames[layer['frame_id']]['slot_id']],
                       rendering_versions=dict(renderer=RENDERER_VERSION,geometry=GEOMETRY_VERSION,timing=TIMING_VERSION),
                       assignment_basis=row['composition_sha256'],
                       ordered_frame=[dict(requirement=l, assignment_basis=rows.get(l['id'], {}).get('composition_sha256'))
                                      for l in sorted(groups[layer['frame_id']], key=lambda l:l['ordinal'])],
                       preview_semantics=SEMANTICS, policy='PROVISIONAL_ORDERED_LAYER_INSPECTION', limitations=LIMITATIONS)
        result[layer['id']] = digest(canonical_bytes(payload))
    return result


def make_event(project_id, project_revision, target, decision, members, revision, policy=None):
    check(decision in ('APPROVED', 'REJECTED', 'NOT_REQUIRED'), 'Unsupported operator decision.')
    check((decision == 'NOT_REQUIRED') == (policy == 'UNCHANGED_REFERENCE_STRUCTURAL_ONLY'),
          'NOT_REQUIRED requires the explicit unchanged-reference structural-only policy.')
    event = dict(schema='rsf.review-event/v1', project_id=project_id, project_revision=project_revision,
                 target=target, revision=revision, decision=decision, members=members,
                 provenance='EXPLICIT_SINGLE_OPERATOR_WORKBENCH_ACTION', identity_assurance='LOCAL_REQUEST_ONLY',
                 policy=policy, preview_semantics=SEMANTICS, limitations=LIMITATIONS)
    # ID is excluded from the seal to avoid a self-referential digest.
    event = sealed(event)
    event['id'] = 'review-' + event['canonical_sha256']
    return event


def evaluate_reviews(project_id, events, requirements, ledger_report, evidence=None):
    validate_events(events, project_id)
    current = bases(requirements, ledger_report)
    latest = {}
    for event in events:
        for member in event['members']:
            latest[member['requirement_id']] = (event, member)
    states = []
    for layer in requirements['layers']:
        rid = layer['id']; pair = latest.get(rid)
        state = dict(requirement_id=rid, state='UNVERIFIED', basis_sha256=current.get(rid), review_id=None, causes=[])
        if pair:
            event, member = pair
            state.update(review_id=event['id'], recorded_basis_sha256=member['basis_sha256'], recorded_evidence_sha256=member['evidence_sha256'], decision=event['decision'])
            if member['basis_sha256'] != current.get(rid) or (not layer.get('action_basis') and event['target'] != requirements['target']):
                state.update(state='STALE', causes=['COMPOSITION_CHANGED_OR_REQUIREMENT_UNAVAILABLE'])
            elif evidence is not None and evidence.get(rid) != member['evidence_sha256']:
                state.update(state='STALE', causes=['PREVIEW_OR_SOURCE_EVIDENCE_CHANGED'])
            else:
                state['state'] = event['decision']
        states.append(state)
    return sealed(dict(schema='rsf.review-status/v1', project_id=project_id, occurrences=states,
                       history=events, orphaned=sorted(set(latest)-{l['id'] for l in requirements['layers']}),
                       counts={s:sum(r['state']==s for r in states) for s in ('APPROVED','REJECTED','STALE','UNVERIFIED','NOT_REQUIRED')},
                       preview_semantics=SEMANTICS, limitations=LIMITATIONS, export_ready=False))


def apply_reviews(ledger_report, review_status, declaration, requirements, source_bytes):
    """Project validated events through the existing ledger acceptance rules.

    This projection is ephemeral: historical decisions never change persisted
    assignment revisions or their canonical composition bases.
    """
    if ledger_report is None: return None
    from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger
    value = copy.deepcopy(declaration)
    value.pop('canonical_sha256', None)
    states = {s['requirement_id']:s for s in review_status['occurrences']}
    rows = {r['requirement_id']:r for r in ledger_report['assignments']}
    for assignment in value['assignments']:
        state = states[assignment['requirement_id']]
        assignment['review'] = None
        if state['state'] in ('APPROVED','REJECTED','NOT_REQUIRED'):
            assignment['review'] = dict(state=state['state'], authority='OPERATOR', operator='local-workbench', evidence_sha256=state['recorded_evidence_sha256'],
                basis_sha256=rows[assignment['requirement_id']]['composition_sha256'],
                policy='UNCHANGED_REFERENCE' if state['state']=='NOT_REQUIRED' else 'VISUAL_DECISION')
    report = resolve_ledger(load_ledger(value,requirements=requirements),
                            requirements=requirements,source_bytes=source_bytes)
    for row in report['assignments']:
        if states[row['requirement_id']]['state']=='STALE': row['review_binding']='STALE'
    report.pop('canonical_sha256', None)
    return sealed(report)
