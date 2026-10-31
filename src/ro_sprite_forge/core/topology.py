"""RSF-8 finite, ordered work orders; no artwork assignments or native claims.

Only immutable inventory references are supported. Frame mapping is ordinal and
one-to-one, validated by the contract assessment; there is no reference graph,
resampling, fallback or implicit template selection.
"""

import json

from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.contracts import (ActorContract, RuntimeProfileContract,
    TargetContract, assess_target, reference)


def resolve_topology(target: TargetContract, *, actor: ActorContract,
                     profile: RuntimeProfileContract, inventories: tuple[dict, ...] = ()) -> dict:
    """Expand Target/v2 into canonical rsf.resolved-requirements/v1.

    Invalid/changed references raise the existing typed ForgeError with a JSON
    pointer. Absent references/counts/topology remain diagnostic provisional work.
    Source image/transform records are observations, never replacement assignments.
    """
    assessment = assess_target(target, actor=actor, profile=profile, inventories=inventories)
    tv, pv = target.to_dict(), profile.to_dict()
    sources = {i['canonical_sha256']: i for i in inventories}
    mappings = {a['id']: a for a in pv['actions'] if a['id'] is not None}
    diagnostics = list(assessment['diagnostics'])
    scoped_actions = any('offline' in a for a in tv['actions'])
    slots, frames, layers = [], [], []
    unknown_dimensions = {requirement: sum(
        int(not a['parts']) + sum(not p['views'] for p in a['parts'])
        for a in tv['actions'] if a['requirement'] == requirement)
        for requirement in ('REQUIRED', 'OPTIONAL')}
    # Original declaration paths remain precise even though output order is canonical.
    for ai, action in sorted(enumerate(tv['actions']), key=lambda x: x[1]['id']):
        if action['requirement'] == 'OUT_OF_SCOPE':
            continue
        mapped = mappings.get(action['id'])
        action_basis = None
        if scoped_actions:
            from ro_sprite_forge.core.custom_actions import action_composition_basis
            action_basis = action_composition_basis(tv, action)
        if 'offline' in action:
            mapped = dict(mapping='UNSUPPORTED', reachability='UNSUPPORTED')
        for pi, part in sorted(enumerate(action['parts']), key=lambda x: x[1]['part']):
            for vi, view in sorted(enumerate(part['views']), key=lambda x: x[1]['view']):
                path = f'/actions/{ai}/parts/{pi}/views/{vi}'
                runtime_slot = mapped['group'] * 8 + view['view'] if mapped and mapped['mapping'] == 'SUPPORTED' else None
                prefix = (f"{target.id}/r{target.revision}/{part['part']}/action/{action['id']}"
                          f"/slot{runtime_slot if runtime_slot is not None else 'UNVERIFIED'}/view{view['view']}")
                if scoped_actions:
                    prefix = (f"{target.id}/action/{action['id']}/{part['part']}"
                              f"/slot{runtime_slot if runtime_slot is not None else 'OFFLINE'}/view{view['view']}")
                count, topology = view['frame_count'], view['topology']
                authority, source, source_action = None, None, None
                if topology is not None:
                    if topology['kind'] == 'inherited':
                        source = sources.get(topology['inventory_sha256'])
                        if source is not None:
                            source_action = next(a for a in source['actions'] if a['slot'] == topology['slot'])
                            authority = {'kind': 'inherited', 'reference_type': 'rsf.inventory/v1',
                                'inventory_sha256': source['canonical_sha256'], 'sources': source['sources'],
                                'namespace': source['namespace'], 'part': part['part'],
                                'source_slot': topology['slot'], 'target_runtime_slot': runtime_slot,
                                'semantic_mapping': 'SUPPORTED' if runtime_slot is not None else 'UNVERIFIED',
                                'frame_mapping': 'ORDINAL_ONE_TO_ONE',
                                'mapping_complete': count is not None}
                        if source is None:
                            diagnostics.append({'code': 'UNDERSPECIFIED_LAYER_TOPOLOGY', 'path': path + '/topology'})
                    elif topology['kind'] == 'template':
                        authority = {'kind': 'explicit', 'declaration': 'template',
                            'id': topology['id'], 'version': topology['version'],
                            'template_sha256': topology['template_sha256'], 'scope_confirmed': True}
                    else:
                        authority = {'kind': 'explicit', 'declaration': topology['kind']}
                slots.append({'id': prefix, 'part': part['part'], 'action': action['id'],
                    'view': view['view'], 'runtime_slot': runtime_slot,
                    'runtime_mapping': mapped['mapping'] if mapped else 'UNVERIFIED',
                    'gameplay_reachability': mapped['reachability'] if mapped else 'UNVERIFIED',
                    'requirement': action['requirement'], 'frame_count': count,
                    'resolution': 'RESOLVED' if count is not None and authority is not None else 'UNDERSPECIFIED',
                    'authority': authority})
                if scoped_actions:
                    slots[-1]['action_basis'] = action_basis
                if 'offline' in action:
                    slots[-1]['offline'] = action['offline']
                if count is None:
                    continue
                for fi in range(count):
                    frame_id = f'{prefix}/frame{fi}'
                    roles, observations, constraints = None, [], None
                    provenance = dict(authority) if authority is not None else None
                    if source_action is not None:
                        motion = source_action['frames'][fi]
                        observations = [(i, l) for i, l in enumerate(motion['layers']) if l['visible']]
                        roles = [l.get('role') for _, l in observations]
                        provenance['source_frame'] = fi
                        provenance['source_frame_id'] = motion.get('id')
                        # Keep every ordered source record, including non-visible placeholders.
                        constraints = {'source_motion': motion, 'source_raw_delay': source_action.get('raw_delay'),
                                       'interpretation': 'REFERENCE_OBSERVATIONS', 'reuse': 'UNDECLARED'}
                    elif authority is not None:
                        roles = (topology['frames'][fi] if topology['kind'] == 'per_frame' else
                                 [topology['role']] if topology['kind'] == 'template' else topology['layers'])
                    frame = {'id': frame_id, 'slot_id': prefix, 'ordinal': fi,
                        'requirement': action['requirement'], 'layer_count': None if roles is None else len(roles),
                        'resolution': 'UNDERSPECIFIED' if roles is None else 'RESOLVED',
                        'authority': provenance, 'constraints': constraints, 'layer_ids': []}
                    if roles is not None:
                        structure = digest(canonical_bytes({'roles': roles, 'authority': provenance, 'constraints': constraints}))
                        for li, role in enumerate(roles):
                            layer_id = f'{frame_id}/topology{structure}/layer{li}'
                            frame['layer_ids'].append(layer_id)
                            layers.append({'id': layer_id, 'frame_id': frame_id, 'ordinal': li,
                                'role': role, 'part': part['part'], 'action': action['id'],
                                'view': view['view'], 'frame': fi, 'runtime_slot': runtime_slot,
                                'requirement': action['requirement'], 'authority': provenance,
                                'source_layer_ordinal': observations[li][0] if observations else None,
                                'source_layer': observations[li][1] if observations else None,
                                'registration': 'REFERENCE_OBSERVATIONS' if observations else 'UNSPECIFIED',
                                'reuse': 'UNDECLARED', 'assignment': 'UNASSIGNED', 'visual_review': 'UNVERIFIED'})
                    if scoped_actions:
                        frame['action_basis'] = action_basis
                        for item in layers[-len(roles):] if roles else []:
                            item['action_basis'] = action_basis
                            if 'offline' in action:
                                item['offline'] = action['offline']
                    frames.append(frame)
    counts = {}
    for requirement in ('REQUIRED', 'OPTIONAL'):
        ss = [s for s in slots if s['requirement'] == requirement]
        ff = [f for f in frames if f['requirement'] == requirement]
        ll = [l for l in layers if l['requirement'] == requirement]
        counts[requirement.lower()] = {
            'action_view_slots': len(ss),
            'action_view_slots_exact': len(ss) if not unknown_dimensions[requirement] else None,
            'unexpanded_action_part_declarations': unknown_dimensions[requirement],
            'frame_occurrences_known': len(ff),
            'layer_occurrences_known': len(ll),
            'explicit_resolved_frames': sum(f['resolution'] == 'RESOLVED' and f['authority']['kind'] == 'explicit' for f in ff),
            'inherited_resolved_frames': sum(f['resolution'] == 'RESOLVED' and f['authority']['kind'] == 'inherited' for f in ff),
            'explicit_resolved_layers': sum(l['authority']['kind'] == 'explicit' for l in ll),
            'inherited_resolved_layers': sum(l['authority']['kind'] == 'inherited' for l in ll),
            'underspecified_slots': sum(s['resolution'] == 'UNDERSPECIFIED' for s in ss),
            'underspecified_frames': sum(f['resolution'] == 'UNDERSPECIFIED' for f in ff),
            'unknown_frame_count_slots': sum(s['frame_count'] is None for s in ss),
            'layer_occurrences_exact': len(ll) if not unknown_dimensions[requirement] and all(s['resolution'] == 'RESOLVED' for s in ss) else None}
    specified = assessment['status']['declared_scope_specified'] and all(s['resolution'] == 'RESOLVED' for s in slots)
    result = {'schema': 'rsf.resolved-requirements/v1', 'actor': reference(actor),
        'target': reference(target), 'runtime_profile': reference(profile), 'scope': tv['scope'],
        'slots': slots, 'frames': frames, 'layers': layers, 'counts': counts,
        'diagnostics': diagnostics, 'status': {
            'work_order': 'EXACT' if specified else 'PROVISIONAL',
            'specification': 'COMPLETE_FOR_DECLARED_SCOPE' if specified else 'UNDERSPECIFIED',
            'full_profile_specified': specified and assessment['status']['full_profile_specified'],
            'artwork_coverage': 'UNASSIGNED', 'unique_artwork_effort': 'UNKNOWN_UNTIL_ASSIGNMENTS',
            'export_ready': False, 'visual_review': 'UNVERIFIED', 'native_evidence': 'UNVERIFIED'}}
    # Detach all returned records from supplied inventories, including nested metadata.
    return json.loads(canonical_bytes(sealed(result)))


def topology_work_order(result: dict) -> str:
    """Operator-readable checklist of every frame and ordered layer requirement."""
    from ro_sprite_forge.core.canonical import check_seal
    check_seal(result, 'rsf.resolved-requirements/v1')
    lines = [f"{result['target']['id']} revision {result['target']['revision']}: "
             f"{result['scope']} {result['status']['work_order']}; artwork UNASSIGNED"]
    layer_lookup = {layer['id']: layer for layer in result['layers']}
    for frame in result['frames']:
        lines.append(f"{frame['id']} [{frame['requirement']}] layers={frame['layer_count']} {frame['resolution']}")
        for layer_id in frame['layer_ids']:
            layer = layer_lookup[layer_id]
            authority = layer['authority']
            source = authority.get('inventory_sha256', authority.get('template_sha256', 'operator'))
            lines.append(f"  {layer_id} role={layer['role']} authority={authority['kind']} source={source} "
                         f"source_ordinal={layer['source_layer_ordinal']} assignment=UNASSIGNED")
    lines.extend(d['code'] + ' ' + d['path'] for d in result['diagnostics'])
    return '\n'.join(lines) + '\n'
