"""Optional cosmetic compatibility adapter (RSF-34), separate from binary compilation.

A pairing grants only the explicit source-backed technical scope tested here. It
never changes gameplay identity, authors artwork, grants approval, or authorizes export.
"""
from copy import deepcopy

from ro_sprite_forge.core.canonical import canonical_bytes, check, check_seal, digest, sealed

REPRESENTATIONS = ('COMPLETE_VISUAL_BODY', 'ATTACHED_OVERLAY', 'HEAD_ACCESSORY', 'EQUIPMENT_VISUAL')
SEMANTICS = 'rsf.cosmetic-compatibility/v1'


def profile_reference(profile):
    return {k: profile[k] for k in ('id', 'version', 'canonical_sha256')}


def build_cosmetic_pairing(*, id, body, appearance, representation, action_views,
                           body_part='body', appearance_part='body', attachment_pairing_id=None,
                           layer_order=None, evidence=(), attachment_pairing=None):
    """Build an explicit record; enrollment validates it against the existing registry."""
    if attachment_pairing is not None:
        check(attachment_pairing_id in (None, attachment_pairing['id']), 'CONFLICTING_COSTUME_BINDING')
        attachment_pairing_id = attachment_pairing['id']
    return sealed(dict(id=id, body_profile=profile_reference(body),
                       appearance_profile=profile_reference(appearance), representation=representation,
                       body_part=body_part, appearance_part=appearance_part,
                       attachment_pairing_id=attachment_pairing_id,
                       attachment_pairing_sha256=digest(canonical_bytes(attachment_pairing)) if attachment_pairing else None,
                       frame_mapping='EXACT_EQUAL_ORDINAL',
                       action_views=sorted(deepcopy(action_views), key=lambda r: (r['action'], r['view'])),
                       layer_order=list(layer_order or ([appearance_part] if representation == 'COMPLETE_VISUAL_BODY'
                                                        else [body_part, appearance_part])),
                       evidence=sorted(set(evidence))))


def validate_cosmetic_pairing(record, registry):
    from ro_sprite_forge.core.registry import _validate_profile_entry
    check(record['representation'] in REPRESENTATIONS, 'UNSUPPORTED_COSMETIC_REPRESENTATION')
    check(record['canonical_sha256'] == digest(canonical_bytes({k:v for k,v in record.items()
                                                              if k != 'canonical_sha256'})),
          'COSMETIC_PAIRING_DIGEST_MISMATCH')
    profiles = {p['id']:p for p in registry['profiles']}
    selected = []
    for key in ('body_profile', 'appearance_profile'):
        ref = record[key]
        check(ref['id'] in profiles, 'UNKNOWN_COSTUME_PROFILE')
        profile = profiles[ref['id']]
        _validate_profile_entry(profile)
        check(ref == profile_reference(profile), 'STALE_PROFILE_REVISION')
        selected.append(profile)
    body, appearance = selected
    check(body['resource_kind'] == 'body', 'INVALID_UNDERLYING_BODY')
    for profile, part in ((body, record['body_part']), (appearance, record['appearance_part'])):
        check(part in profile['parts']['declared'], 'UNDECLARED_RESOURCE_PART')
    rows = record['action_views']
    check(rows == sorted(rows, key=lambda r: (r['action'], r['view'])), 'NONCANONICAL_ACTION_MAPPING')
    check(len({(r['action'], r['view']) for r in rows}) == len(rows), 'CONFLICTING_COSTUME_BINDING')
    for key in ('body_slot', 'appearance_slot'):
        check(len({r[key] for r in rows}) == len(rows), 'CONFLICTING_COSTUME_BINDING')
    check(record['frame_mapping'] == 'EXACT_EQUAL_ORDINAL', 'UNSUPPORTED_FRAME_MAPPING')
    if record['representation'] == 'COMPLETE_VISUAL_BODY':
        check(appearance['resource_kind'] == 'body' and record['body_part'] == record['appearance_part'],
              'UNSUPPORTED_FULL_BODY_SUBSTITUTION')
        check(record['attachment_pairing_id'] is None and record['attachment_pairing_sha256'] is None,
              'CONFLICTING_COSTUME_BINDING')
        check(record['layer_order'] == [record['appearance_part']], 'INCORRECT_LAYER_ORDER')
    else:
        pairings = {p['id']:p for p in registry.get('attachment_pairings', [])}
        check(record['attachment_pairing_id'] in pairings, 'UNSUPPORTED_ADDITIVE_OVERLAY')
        pairing = pairings[record['attachment_pairing_id']]
        check(pairing['parent_profile_id'] == body['id'] and pairing['child_profile_id'] == appearance['id']
              and pairing['parent_part'] == record['body_part'] and pairing['child_part'] == record['appearance_part'],
              'INVALID_BODY_COSTUME_PAIRING')
        check(record['attachment_pairing_sha256'] == digest(canonical_bytes(pairing)),
              'STALE_ATTACHMENT_PAIRING')
        kinds = {'ATTACHED_OVERLAY': ('accessory',), 'HEAD_ACCESSORY': ('head', 'accessory'),
                 'EQUIPMENT_VISUAL': ('shield',)}
        check(appearance['resource_kind'] in kinds[record['representation']], 'UNSUPPORTED_ADDITIVE_OVERLAY')
        rules = {'head': 'player_head_anchor_delta', 'accessory': 'head_accessory_anchor_delta',
                 'shield': 'body_shield_relative'}
        check(pairing['rule'] == rules[appearance['resource_kind']], 'UNSUPPORTED_ATTACHMENT_RULE')
        check(pairing['status'] in ('SUPPORTED', 'PARTIAL'), 'UNSUPPORTED_ATTACHMENT_RULE')
        expected_anchor = (dict(mode='body_shield_relative', parent_anchor_index=None, child_anchor_index=None)
                           if appearance['resource_kind'] == 'shield' else
                           dict(mode='parent_head_anchor_delta' if appearance['resource_kind'] == 'head'
                                else 'head_accessory_anchor_delta', parent_anchor_index=0, child_anchor_index=0))
        check(pairing['anchor_rule'] == expected_anchor, 'UNSUPPORTED_ATTACHMENT_ANCHOR_RULE')
        expected = [p for p in pairing['layer_order'] if p in (record['body_part'], record['appearance_part'])]
        check(record['body_part'] != record['appearance_part'] and record['layer_order'] == expected
              and set(expected) == {record['body_part'], record['appearance_part']}, 'INCORRECT_LAYER_ORDER')


def _sources(registry, record, resources):
    """Hash check before decoding; use audited codecs and the compositor's pool resolver."""
    from ro_sprite_forge.core.registry import verify_source_hashes
    from ro_sprite_forge.formats.act import read_act
    from ro_sprite_forge.formats.spr import read_spr
    from ro_sprite_forge.formats.preview import _resolve_image_from_spr
    result = {}
    for key in ('body_profile', 'appearance_profile'):
        pid = record[key]['id']
        if pid in result:
            continue
        check(pid in resources, 'MISSING_COSTUME_SOURCE')
        pair = resources[pid]
        check(isinstance(pair, (list, tuple)) and len(pair) == 2 and all(type(b) is bytes for b in pair),
              'INVALID_RESOURCE_PAIR')
        profile = registry.get_profile(pid)
        verify_source_hashes(profile, *pair)
        act, spr = read_act(pair[0]), read_spr(pair[1])
        check(len(act['actions']) == profile['topology']['slot_count']
              and sum(map(len, act['actions'])) == profile['topology']['motion_count'], 'PROFILE_TOPOLOGY_MISMATCH')
        motions = [m for action in act['actions'] for m in action]
        check(sorted({len(m['clips']) for m in motions}) == profile['topology']['layer_counts']
              and sorted({len(m['anchors']) for m in motions}) == profile['topology']['anchor_counts'],
              'PROFILE_TOPOLOGY_MISMATCH')
        check((spr.indexed_count, spr.rgba_count) == (profile['image_pool']['indexed_count'],
                                                    profile['image_pool']['rgba_count']), 'PROFILE_IMAGE_POOL_MISMATCH')
        for motions in act['actions']:
            for motion in motions:
                for clip in motion['clips']:
                    if clip['sprite'] >= 0:
                        _resolve_image_from_spr(spr, clip['sprite'], clip['pool'])
        result[pid] = (act, spr)
    return result


def _mapped(profile, action, view, slot):
    # The enrolled runtime profile is pinned to the audited eight-view mapping.
    return any(a['id'] == action and a['mapping'] == 'SUPPORTED' and a['group'] is not None
               and a['group'] * 8 + view == slot and slot in a['slots'] for a in profile['actions'])


def evaluate_appearance(registry, pairing_id, *, requirements, resources, character_id,
                        gameplay_job=None, head_profile=None, equipment_profiles=()):
    """Compare all required body/appearance slots. No fallback or implicit correspondence.

    Head/equipment identities are retained, but their compatibility with a substituted
    visual host needs a separate explicit pairing; it is never inherited from the old body.
    """
    from ro_sprite_forge.core.registry import to_runtime_profile_contract
    from ro_sprite_forge.core.contracts import reference
    from ro_sprite_forge.core.attachments import validate_attachment_compatibility
    check_seal(requirements, 'rsf.resolved-requirements/v1')
    check(isinstance(character_id, str) and bool(character_id), 'MISSING_CHARACTER_IDENTITY')
    check(gameplay_job is None or isinstance(gameplay_job, str), 'INVALID_GAMEPLAY_CONTEXT')
    record = registry.get_cosmetic_pairing(pairing_id)
    body = registry.get_profile(record['body_profile']['id'])
    appearance = registry.get_profile(record['appearance_profile']['id'])
    check(requirements['runtime_profile'] == reference(to_runtime_profile_contract(body)), 'RUNTIME_PROFILE_MISMATCH')
    if head_profile is not None:
        check(registry.get_profile(head_profile)['resource_kind'] == 'head', 'INVALID_HEAD_PROFILE')
    check(isinstance(equipment_profiles, (tuple, list)) and len(set(equipment_profiles)) == len(equipment_profiles),
          'INVALID_EQUIPMENT_PROFILES')
    for pid in equipment_profiles:
        check(registry.get_profile(pid)['resource_kind'] in ('shield', 'accessory'), 'INVALID_EQUIPMENT_PROFILE')
    decoded = _sources(registry, record, resources)
    ba, _ = decoded[body['id']]; ca, _ = decoded[appearance['id']]
    full_body = record['representation'] == 'COMPLETE_VISUAL_BODY'
    attachment = None
    rule = None
    if not full_body:
        pairing = next(p for p in registry.to_dict()['attachment_pairings'] if p['id'] == record['attachment_pairing_id'])
        rule = pairing['rule']
        attachment = validate_attachment_compatibility(body, appearance, parent_act=ba, child_act=ca,
                                                        rule=rule, gameplay_job_check=False)
    rows = {(r['action'], r['view']):r for r in record['action_views']}
    slots = [s for s in requirements['slots'] if s['part'] in (record['body_part'], record['appearance_part'])
             and s['requirement'] == 'REQUIRED']
    check(bool(slots), 'NO_APPLICABLE_COSTUME_SCOPE')
    details = []
    for slot in sorted(slots, key=lambda s:s['id']):
        row = rows.get((slot['action'], slot['view']))
        codes = []
        dimensions = dict(action_view='UNVERIFIED', frame_correspondence='UNVERIFIED',
                          layer_topology='UNVERIFIED', anchors='UNVERIFIED')
        if row is None:
            codes.append('MISSING_COSTUME_ACTION_VIEW')
        elif not (_mapped(body, row['action'], row['view'], row['body_slot'])
                  and _mapped(appearance, row['action'], row['view'], row['appearance_slot'])
                  and slot['runtime_mapping'] == 'SUPPORTED' and slot['runtime_slot'] == row['body_slot']):
            codes.append('INVALID_ACTION_VIEW_MAPPING')
        elif row['body_slot'] >= len(ba['actions']) or row['appearance_slot'] >= len(ca['actions']):
            codes.append('MISSING_COSTUME_SLOT')
        else:
            dimensions['action_view'] = 'SUPPORTED'
            bm, cm = ba['actions'][row['body_slot']], ca['actions'][row['appearance_slot']]
            if not bm or len(bm) != len(cm) or slot['frame_count'] != len(bm):
                codes.append('MISMATCHED_FRAME_COUNT')
                dimensions['frame_correspondence'] = 'UNSUPPORTED'
            else:
                dimensions['frame_correspondence'] = 'SUPPORTED'
                dimensions['layer_topology'] = 'SUPPORTED'
                # Target topology is an independent authority, not inferred from a costume.
                frames = sorted((f for f in requirements['frames'] if f['slot_id'] == slot['id']), key=lambda f:f['ordinal'])
                selected = cm if full_body or slot['part'] == record['appearance_part'] else bm
                if len(frames) != len(selected) or any(f['layer_count'] != sum(c['sprite'] >= 0 for c in m['clips'])
                                                      for f,m in zip(frames, selected)):
                    codes.append('MISMATCHED_LAYER_TOPOLOGY')
                    dimensions['layer_topology'] = 'UNSUPPORTED'
                if rule:
                    dimensions['anchors'] = 'SUPPORTED'
                if rule in ('player_head_anchor_delta', 'head_accessory_anchor_delta'):
                    if any(len(b['anchors']) != 1 or len(c['anchors']) != 1 for b,c in zip(bm,cm)):
                        codes.append('MISSING_OR_AMBIGUOUS_ANCHOR')
                        dimensions['anchors'] = 'UNSUPPORTED'
                if rule == 'body_shield_relative' and any(c['anchors'] for c in cm):
                    codes.append('UNSUPPORTED_SHIELD_ANCHOR')
                    dimensions['anchors'] = 'UNSUPPORTED'
        if dimensions['action_view'] == 'UNVERIFIED':
            dimensions['action_view'] = 'UNSUPPORTED'
        details.append(dict(slot_id=slot['id'], action=slot['action'], view=slot['view'],
                            mapping=deepcopy(row), status='UNSUPPORTED' if codes else 'SUPPORTED',
                            dimensions=dimensions, diagnostics=codes))
    supported = sum(d['status'] == 'SUPPORTED' for d in details)
    status = 'SUPPORTED' if supported == len(details) else 'PARTIAL' if supported else 'UNSUPPORTED'
    declared = {(a['id'], s % 8) for a in body['actions'] for s in a['slots']}
    supported_keys = {(d['action'],d['view']) for d in details if d['status'] == 'SUPPORTED'}
    supported_keys -= {(d['action'],d['view']) for d in details if d['status'] != 'SUPPORTED'}
    def dimension_status(key):
        values = [d['dimensions'][key] for d in details]
        return ('SUPPORTED' if all(v == 'SUPPORTED' for v in values) else 'PARTIAL' if 'SUPPORTED' in values
                else 'UNSUPPORTED' if 'UNSUPPORTED' in values else 'UNVERIFIED')
    dependencies = ([head_profile] if head_profile else []) + list(equipment_profiles)
    diagnostics = []
    if dependencies:
        diagnostics.append('VISUAL_HOST_ATTACHMENT_REBIND_REQUIRED' if full_body else 'ADDITIONAL_ATTACHMENTS_NOT_COMPOSED')
    return sealed(dict(schema='rsf.cosmetic-compatibility-report/v1', semantics=SEMANTICS,
                       pairing_sha256=record['canonical_sha256'],
                       identity=dict(character_id=character_id, gameplay_job=gameplay_job,
                                     underlying_body=record['body_profile'], visual_appearance=record['appearance_profile'],
                                     head_profile=head_profile, equipment_profiles=sorted(equipment_profiles)),
                       representation=record['representation'], target=requirements['target'],
                       runtime_profile=requirements['runtime_profile'], requirements_sha256=requirements['canonical_sha256'],
                       sources={p['id']:p['source_hashes'] for p in (body,appearance)},
                       status=status, full_profile_status='SUPPORTED' if supported_keys == declared else 'PARTIAL' if supported else 'UNSUPPORTED',
                       slot_details=details, counts=dict(requested=len(details), supported=supported, unsupported=len(details)-supported),
                       missing_full_profile_scopes=[dict(action=a,view=v) for a,v in sorted(declared-supported_keys)],
                       dimensions=dict(source_validity='VERIFIED', pairing=status,
                                       action_view=dimension_status('action_view'),
                                       frame_correspondence=dimension_status('frame_correspondence'),
                                       layer_topology=dimension_status('layer_topology'), anchors=dimension_status('anchors'),
                                       preview='UNVERIFIED', compilation='UNVERIFIED', independent_rust='UNVERIFIED',
                                       native_korangar='UNVERIFIED', visual_review='UNVERIFIED',
                                       gameplay_eligibility='UNVERIFIED',
                                       remaining_attachments='UNVERIFIED'),
                       attachment_report_sha256=attachment['canonical_sha256'] if attachment else None,
                       gameplay_context=dict(body_profile_job=body['gameplay_job'],
                                             appearance_profile_job=appearance['gameplay_job'],
                                             context_matches_body=gameplay_job == body['gameplay_job'] if gameplay_job else None,
                                             eligibility='UNVERIFIED'),
                       diagnostics=diagnostics, export_ready=False, newly_authored_coverage=0))


def preview_appearance(registry, pairing_id, *, requirements, resources, character_id, action, view,
                       frame, canvas_size=(256,256), origin=(128,128), **context):
    """Render exact selected resources via the existing compositor, without changing sources."""
    from ro_sprite_forge.core.attachments import compose_attachment_coordinates, composite_attachment_layers
    from ro_sprite_forge.formats.preview import composite_frame
    report = evaluate_appearance(registry, pairing_id, requirements=requirements, resources=resources,
                                 character_id=character_id, **context)
    record = registry.get_cosmetic_pairing(pairing_id)
    details = [d for d in report['slot_details'] if (d['action'],d['view']) == (action,view)]
    check(bool(details) and all(d['status'] == 'SUPPORTED' for d in details), 'UNSUPPORTED_COSTUME_SCOPE')
    check(type(frame) is int and 0 <= frame, 'INVALID_COSTUME_FRAME')
    check(not report['diagnostics'], 'UNRESOLVED_VISUAL_HOST_ATTACHMENTS')
    decoded = _sources(registry, record, resources)
    mapping = details[0]['mapping']
    parts = [(record['body_part'],record['body_profile']['id'],mapping['body_slot']),
             (record['appearance_part'],record['appearance_profile']['id'],mapping['appearance_slot'])]
    check(frame < len(decoded[parts[0][1]][0]['actions'][mapping['body_slot']]), 'INVALID_COSTUME_FRAME')
    body_motion = decoded[parts[0][1]][0]['actions'][mapping['body_slot']][frame]
    if record['representation'] == 'COMPLETE_VISUAL_BODY':
        parts = parts[1:]
    rule = None
    if record['attachment_pairing_id']:
        rule = next(p['rule'] for p in registry.to_dict()['attachment_pairings'] if p['id'] == record['attachment_pairing_id'])
    prepared = []
    for part,pid,slot in parts:
        original = decoded[pid][0]['actions'][slot][frame]
        motion = deepcopy(original)
        if rule and part == record['appearance_part']:
            pa = body_motion['anchors'][0] if body_motion['anchors'] else None
            ca = motion['anchors'][0] if motion['anchors'] else None
            for clip in motion['clips']:
                clip['x'],clip['y'] = compose_attachment_coordinates(
                    (pa['x'],pa['y']) if pa else None, (ca['x'],ca['y']) if ca else None,
                    (clip['x'],clip['y']), rule=rule)
        # Coordinates were composed once above; disable compositor's automatic head shift.
        motion['anchors'] = []
        prepared.append(dict(part=part, pid=pid, motion=motion, source_motion=original,
                             source_delay=decoded[pid][0]['delays'][slot]))
    ordered = composite_attachment_layers(prepared, record['layer_order'])
    rendered = composite_frame([dict(actions=[[p['motion']]]) for p in ordered],
                               [decoded[p['pid']][1] for p in ordered], 0, 0,
                               canvas_size=canvas_size, origin=origin)
    proof = sealed(dict(schema='rsf.cosmetic-preview/v1', semantics=SEMANTICS,
                        compatibility_sha256=report['canonical_sha256'], action=action,view=view,frame=frame,
                        parts=[dict(part=p['part'],profile_id=p['pid'], clips=p['motion']['clips'],
                                    source_motion=p['source_motion'], source_delay=p['source_delay']) for p in ordered],
                        rendered_png_sha256=digest(rendered['png_bytes']), scope='STATIC_SELECTED_RESOURCE_COMPOSITION',
                        renderer=rendered['report'], native_korangar='UNVERIFIED', visual_review='UNVERIFIED', export_ready=False))
    return dict(image=rendered['image'], png_bytes=rendered['png_bytes'], report=proof, compatibility=report)


def bind_appearance_requirements(requirements, registry, pairing_id, *, dependent_frame_ids=()):
    """Declare visual dependencies in existing frame constraints; RSF-18 handles staleness."""
    check_seal(requirements, 'rsf.resolved-requirements/v1')
    record = registry.get_cosmetic_pairing(pairing_id)
    result = deepcopy(requirements)
    affected_part = record['appearance_part']
    slots = {s['id']:s for s in result['slots']}
    check(isinstance(dependent_frame_ids, (list,tuple))
          and len(set(dependent_frame_ids)) == len(dependent_frame_ids)
          and set(dependent_frame_ids) <= {f['id'] for f in result['frames']}, 'INVALID_COSMETIC_DEPENDENCY_SCOPE')
    for frame in result['frames']:
        if slots[frame['slot_id']]['part'] == affected_part or frame['id'] in dependent_frame_ids:
            constraints = frame.get('constraints')
            check(constraints is None or isinstance(constraints, dict), 'UNSUPPORTED_FRAME_CONSTRAINTS')
            frame['constraints'] = dict(constraints or {}, cosmetic_binding_sha256=record['canonical_sha256'])
    result.pop('canonical_sha256')
    return sealed(result)


def prepare_clothing_composition(registry, pairing_id, *, requirements, declaration, source_bytes,
                                  project_id, review_events, requirement_ids, resources, character_id):
    """Optional adapter plan over current approved assignments, never a compiler/export bypass.

    Resources retained as CLASSIC_REFERENCE remain reference coverage. This plan accepts
    only authored, validated PNGs with executed recipes and explicit current RSF-18 approval.
    """
    from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger
    from ro_sprite_forge.core.review import evaluate_reviews
    from ro_sprite_forge.core.ingestion import validate_png
    record = registry.get_cosmetic_pairing(pairing_id)
    bound = bind_appearance_requirements(requirements, registry, pairing_id)
    check(bound['canonical_sha256'] == requirements['canonical_sha256'], 'UNBOUND_COSMETIC_COMPOSITION')
    check(isinstance(requirement_ids, (list,tuple)) and bool(requirement_ids)
          and len(set(requirement_ids)) == len(requirement_ids), 'INVALID_CLOTHING_SCOPE')
    layers = {l['id']:l for l in requirements['layers']}
    check(all(r in layers and layers[r]['part'] == record['appearance_part'] for r in requirement_ids),
          'INVALID_CLOTHING_SCOPE')
    compatibility = evaluate_appearance(registry, pairing_id, requirements=requirements,
                                          resources=resources, character_id=character_id)
    scopes = {d['slot_id']:d for d in compatibility['slot_details']}
    frame_slots = {f['id']:f['slot_id'] for f in requirements['frames']}
    check(all(frame_slots[layers[r]['frame_id']] in scopes
              and scopes[frame_slots[layers[r]['frame_id']]]['status'] == 'SUPPORTED' for r in requirement_ids), 'UNSUPPORTED_CLOTHING_SCOPE')
    ledger = load_ledger(declaration, requirements=requirements)
    resolved = resolve_ledger(ledger, requirements=requirements, source_bytes=source_bytes)
    states = evaluate_reviews(project_id, review_events, requirements, resolved)
    reviews = {s['requirement_id']:s for s in states['occurrences']}
    rows = {r['requirement_id']:r for r in resolved['assignments']}
    assignments = []
    for rid in sorted(requirement_ids):
        row = rows.get(rid)
        check(row is not None and row['kind'] != 'UNASSIGNED' and row['validation'] == 'VALID', 'INVALID_CLOTHING_SOURCE')
        check(reviews[rid]['state'] == 'APPROVED', 'CURRENT_CLOTHING_APPROVAL_REQUIRED')
        check(row['effective_source']['origin'] == 'AUTHORED', 'RETAINED_REFERENCE_IS_NOT_NEW_ARTWORK')
        check(not row['transform_chain'], 'UNEXECUTED_CLOTHING_TRANSFORM')
        data = source_bytes.get(row['effective_source']['id'])
        check(type(data) is bytes and digest(data) == row['effective_source']['sha256'], 'CLOTHING_SOURCE_HASH_MISMATCH')
        validate_png(data)
        assignments.append(dict(requirement_id=rid, assignment_id=row['id'], revision=row['revision'],
                                source=deepcopy(row['effective_source']), composition_sha256=row['composition_sha256'],
                                review_id=reviews[rid]['review_id'], review_basis_sha256=reviews[rid]['basis_sha256']))
    return sealed(dict(schema='rsf.clothing-composition-plan/v1', semantics=SEMANTICS,
                       pairing_sha256=record['canonical_sha256'], requirements_sha256=requirements['canonical_sha256'],
                       target=requirements['target'], runtime_profile=requirements['runtime_profile'],
                       ledger_sha256=ledger.canonical_sha256, assignments=assignments,
                       compatibility_sha256=compatibility['canonical_sha256'],
                       native_korangar='UNVERIFIED', compilation='UNVERIFIED', export_ready=False))
