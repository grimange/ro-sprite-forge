"""Offline action adapters for existing targets, ledger, compositor and timeline.

No native slot allocation, runtime dispatcher, artwork approval or binary encoder.
The optional target action declaration is rsf.offline-action/v1. Registry entries
are capability references to that target, not another animation project.
"""
from copy import deepcopy
import io

from ro_sprite_forge.core.canonical import canonical_bytes, check, digest, sealed
from ro_sprite_forge.core.contracts import reference
from ro_sprite_forge.core.topology import resolve_topology


def action_composition_basis(target, action):
    """Action-local visual authority, opt-in for targets containing offline actions."""
    semantic = deepcopy(action)
    if 'offline' in semantic:
        semantic['offline'].pop('label', None)
    # Declaration order does not alter the action's composition identity.
    semantic['parts'].sort(key=lambda p: p['part'])
    for part in semantic['parts']:
        part['views'].sort(key=lambda v: v['view'])
    return digest(canonical_bytes(dict(schema='rsf.action-composition/v1',
        target_id=target['id'], actor=target['actor'], runtime_profile=target['runtime_profile'],
        action=semantic)))


def action_support(target, *, actor, profile, inventories=()):
    """Report source-defined mappings separately from dispatch/native execution.

    The report never promotes source evidence into native verification. An offline
    declaration explicitly has no runtime mapping, including when its diagnostic
    storage happens to be an existing ACT slot.
    """
    req = resolve_topology(target, actor=actor, profile=profile, inventories=inventories)
    tv, pv = target.to_dict(), profile.to_dict()
    mappings = {a['id']: a for a in pv['actions']}
    rows = []
    for action in sorted(tv['actions'], key=lambda a: a['id']):
        if action['requirement'] == 'OUT_OF_SCOPE':
            continue
        slots = [s for s in req['slots'] if s['action'] == action['id']]
        complete = bool(slots) and all(s['resolution'] == 'RESOLVED' for s in slots)
        offline = action.get('offline')
        mapping = mappings.get(action['id']) if not offline else None
        supported = bool(mapping and mapping['mapping'] == 'SUPPORTED')
        rows.append(dict(action_id=action['id'],
            definition_sha256=action_composition_basis(tv, action),
            kind='OFFLINE_ONLY' if offline else 'PROFILE_ACTION',
            authoring='SUPPORTED' if complete else 'PARTIAL',
            preview='ASSIGNMENTS_REQUIRED' if complete else 'UNSUPPORTED',
            timing=offline['timing'] if offline else dict(authority='RUNTIME_PROFILE', profile=reference(profile)),
            runtime_mapping='SUPPORTED' if supported else 'UNSUPPORTED' if offline else 'UNVERIFIED',
            runtime_slots=[dict(view=s['view'], part=s['part'], slot=s['runtime_slot'])
                           for s in slots] if supported else [],
            runtime_evidence=pv['source'] if supported else None,
            gameplay_reachability=mapping['reachability'] if supported else 'UNSUPPORTED' if offline else 'UNVERIFIED',
            compilation=offline['compilation'] if offline else 'EXISTING_COMPILER_POLICY',
            diagnostic_storage=[dict(part=s['part'], view=s['view'],
                source_slot=s['authority']['source_slot'], inventory_sha256=s['authority']['inventory_sha256'])
                for s in slots if s['authority'] and s['authority']['kind'] == 'inherited']
                if offline and offline['compilation'] == 'BOUND_EXISTING_SLOT_DIAGNOSTIC' else [],
            native_verification='UNVERIFIED', production_authorized=False,
            diagnostics=[] if supported else ['RUNTIME_ACTION_MAPPING_UNAVAILABLE'] if offline else ['RUNTIME_MAPPING_UNVERIFIED'] ))
    return sealed(dict(schema='rsf.action-support/v1', target=reference(target),
        runtime_profile=reference(profile), requirements_sha256=req['canonical_sha256'], actions=rows))


def preview_offline_action(target, *, actor, profile, ledger, source_bytes,
                           action_id, view, frame=0, part='body', elapsed_ms=None,
                           inventories=(), canvas_size=(128, 128)):
    """Render assigned PNG pixels with the existing compositor and diagnostic clock.

    A transient single-sequence compositor input is not an ACT file or runtime
    mapping. Source-backed geometry is retained where inherited; explicit topology
    uses the compositor's declared identity transform at the origin.
    """
    from PIL import Image
    from ro_sprite_forge.core.ingestion import validate_png
    from ro_sprite_forge.core.ledger import resolve_ledger, load_ledger, AssignmentLedger
    from ro_sprite_forge.core.timeline import AnimationTimeline
    from ro_sprite_forge.formats.preview import composite_frame

    check(type(view) is int and type(frame) is int, 'INVALID_FRAME_SELECTION')
    check(isinstance(canvas_size, tuple) and len(canvas_size) == 2 and
          all(type(n) is int and 1 <= n <= 4096 for n in canvas_size), 'PREVIEW_DIMENSION_BUDGET')
    req = resolve_topology(target, actor=actor, profile=profile, inventories=inventories)
    action = next((a for a in target.to_dict()['actions'] if a['id'] == action_id), None)
    check(action is not None and 'offline' in action, 'OFFLINE_ACTION_UNAVAILABLE')
    slot = next((s for s in req['slots'] if s['action'] == action_id and s['view'] == view and s['part'] == part), None)
    check(slot is not None and slot['resolution'] == 'RESOLVED', 'UNDERSPECIFIED_LAYER_TOPOLOGY')
    check(0 <= frame < slot['frame_count'], 'INVALID_FRAME_ORDINAL')
    # Use RSF-12's explicit diagnostic interval, never its native action resolver.
    clock_input = dict(actions=[[dict(clips=[]) for _ in range(slot['frame_count'])]], delays=[0])
    clock = AnimationTimeline(clock_input)
    selection = clock.select(slot=0, frame=frame)
    timing = action['offline']['timing']
    if elapsed_ms is not None:
        selection = clock.seek(selection, elapsed_ms, diagnostic_frame_ms=timing['frame_ms'], diagnostic_loop=timing['loop'])
        frame = selection['frame']
    loaded = ledger if isinstance(ledger, AssignmentLedger) else load_ledger(ledger, requirements=req)
    report = resolve_ledger(loaded, requirements=req, source_bytes=source_bytes)
    rows = {a['requirement_id']: a for a in report['assignments']}
    layers = sorted((l for l in req['layers'] if l['action'] == action_id and
                     l['view'] == view and l['frame'] == frame and l['part'] == part), key=lambda l: l['ordinal'])
    check(len(layers) <= 256, "PREVIEW_LAYER_BUDGET")
    decoded_pixels = 0
    images, clips, provenance = [], [], []
    for layer in layers:
        row = rows.get(layer['id'])
        check(row is not None and row['effective_source'] is not None, 'MISSING_STAGED_SOURCE')
        source = row['effective_source']
        raw = source_bytes.get(source['id'])
        check(isinstance(raw, bytes), 'MISSING_STAGED_SOURCE')
        validate_png(raw, expected_sha256=source['sha256'])
        with Image.open(io.BytesIO(raw)) as im:
            decoded_pixels += im.width * im.height
            check(decoded_pixels <= 16_777_216, "PREVIEW_PIXEL_BUDGET")
            image = im.convert('RGBA')
        for step in row['transform_chain']:
            op = step['operation'].get('op')
            check(op == 'mirror_x', 'UNSUPPORTED_IMAGE_OPERATION: ' + str(op))
            image = image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        original = layer['source_layer']
        clip = deepcopy(original['raw']) if original and 'raw' in original else dict(
            x=0, y=0, scale_x=1.0, scale_y=1.0, angle=0, mirror=0, color=0xFFFFFFFF)
        clip.update(sprite=len(images), pool=1)
        images.append(image); clips.append(clip)
        provenance.append(dict(requirement_id=layer['id'], source=source,
                               composition_sha256=row['composition_sha256']))
    result = composite_frame(dict(actions=[[dict(clips=clips, anchors=[])]], delays=[0]),
                             images, 0, 0, canvas_size=canvas_size)
    result['offline'] = sealed(dict(schema='rsf.offline-preview/v1', action_id=action_id,
        target=reference(target), part=part, view=view, frame=frame,
        timing=timing, elapsed_ms=elapsed_ms, runtime_slot=None,
        runtime_mapping='UNSUPPORTED', native_verification='UNVERIFIED',
        visual_review='UNVERIFIED', sources=provenance,
        png_sha256=digest(result['png_bytes']), rgba_sha256=digest(result['image'].tobytes())))
    return result


def offline_registry_entry(registry, *, profile_id, target, actor, profile, action_id):
    """A hash-bound capability reference; no user-supplied runtime/native assertion."""
    from ro_sprite_forge.core.registry import to_runtime_profile_contract
    document = registry.to_dict() if hasattr(registry, 'to_dict') else registry
    entry = next((p for p in document['profiles'] if p['id'] == profile_id), None)
    check(entry is not None, 'UNKNOWN_ACTOR_PROFILE')
    check(reference(to_runtime_profile_contract(entry)) == reference(profile), 'PROFILE_REVISION_MISMATCH')
    action = next((a for a in target.to_dict()['actions'] if a['id'] == action_id), None)
    check(action is not None and 'offline' in action, 'OFFLINE_ACTION_UNAVAILABLE')
    # Validate target/profile/actor and its explicit declaration without loading art.
    from ro_sprite_forge.core.contracts import load_target
    load_target(target.to_dict(), actor=actor, profile=profile)
    return sealed(dict(schema='rsf.offline-action-capability/v1',
        id=profile_id + ':' + action_id, profile_id=profile_id,
        profile_sha256=entry['canonical_sha256'], target=reference(target), action_id=action_id,
        definition_sha256=action_composition_basis(target.to_dict(), action),
        runtime_mapping='UNSUPPORTED', native_verification='UNVERIFIED'))
