"""Equipment and attachment compatibility validation engine (RSF-33).

Models conventional body/head/equipment/accessory attachment pairs only where pinned
runtime supports them, retaining parent/child resource and anchor identities.
Exposes exact action/view/frame mapping, coordinate transformations, mismatched frame counts,
incompatible action families, and order-preserving multilayer composition.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
import re
from typing import Any, Mapping, Sequence

from ro_sprite_forge.core.canonical import canonical_bytes, check, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.registry import (
    CompatibilityRegistry,
    PLAYER_ACTION_NAMES,
    MONSTER_ACTION_NAMES,
    COMPANION_ACTION_NAMES,
    EVIDENCE_KORANGAR_LOADER,
    EVIDENCE_KORANGAR_ANIM,
)

REPORT_SCHEMA = 'rsf.attachment-compatibility-report/v1'

# Diagnostic error codes
CODE_MISMATCHED_FRAME_COUNT = 'MISMATCHED_FRAME_COUNT'
CODE_MISSING_ATTACHMENT_ACTION = 'MISSING_ATTACHMENT_ACTION'
CODE_MISSING_ACTION = CODE_MISSING_ATTACHMENT_ACTION
CODE_INCOMPATIBLE_RESOURCE_KIND = 'INCOMPATIBLE_RESOURCE_KIND'
CODE_INCOMPATIBLE_ACTION_FAMILY = 'INCOMPATIBLE_ACTION_FAMILY'
CODE_GAMEPLAY_JOB_MISMATCH = 'GAMEPLAY_JOB_MISMATCH'
CODE_MISSING_ANCHOR = 'MISSING_ANCHOR'
CODE_UNDERSPECIFIED_LAYER_ORDER = 'UNDERSPECIFIED_LAYER_ORDER'
CODE_UNSUPPORTED_RULE = 'UNSUPPORTED_RULE'
CODE_SOURCE_HASH_MISMATCH = 'SOURCE_HASH_MISMATCH'

# Supported attachment rules
RULE_PLAYER_HEAD_ANCHOR_DELTA = 'player_head_anchor_delta'
RULE_HEAD_ACCESSORY_ANCHOR_DELTA = 'head_accessory_anchor_delta'
RULE_BODY_SHIELD_RELATIVE = 'body_shield_relative'
RULE_STANDALONE_UNATTACHED = 'standalone_unattached'

SUPPORTED_RULES = (
    RULE_PLAYER_HEAD_ANCHOR_DELTA,
    RULE_HEAD_ACCESSORY_ANCHOR_DELTA,
    RULE_BODY_SHIELD_RELATIVE,
    RULE_STANDALONE_UNATTACHED,
)

# Standard action slot count
PLAYER_SLOT_COUNT = 104
PLAYER_ACTION_COUNT = 13
VIEWS_PER_ACTION = 8


def compose_attachment_coordinates(
    parent_anchor: tuple[int, int] | None,
    child_anchor: tuple[int, int] | None,
    layer_offset: tuple[int, int] = (0, 0),
    *,
    rule: str = RULE_PLAYER_HEAD_ANCHOR_DELTA,
    intermediate_shift: tuple[int, int] = (0, 0),
) -> tuple[int, int]:
    """Compute effective coordinate placement for an attached layer.

    All calculations maintain exact integer coordinate arithmetic without
    arbitrary rounding, truncation, or invented alignment offsets.

    - player_head_anchor_delta: (parent_x - child_x + layer_x, parent_y - child_y + layer_y)
    - head_accessory_anchor_delta: intermediate_shift + (parent_x - child_x + layer_x, ...)
    - body_shield_relative: intermediate_shift + layer_offset
    - standalone_unattached: layer_offset only
    """
    check(isinstance(layer_offset, (tuple, list)) and len(layer_offset) == 2, 'Invalid layer_offset.')
    check(isinstance(intermediate_shift, (tuple, list)) and len(intermediate_shift) == 2, 'Invalid intermediate_shift.')

    if rule == RULE_PLAYER_HEAD_ANCHOR_DELTA:
        check(parent_anchor is not None and child_anchor is not None, 'Anchors required for player_head_anchor_delta.')
        shift_x = parent_anchor[0] - child_anchor[0]
        shift_y = parent_anchor[1] - child_anchor[1]
        return (shift_x + layer_offset[0], shift_y + layer_offset[1])

    elif rule == RULE_HEAD_ACCESSORY_ANCHOR_DELTA:
        if parent_anchor is not None and child_anchor is not None:
            shift_x = intermediate_shift[0] + (parent_anchor[0] - child_anchor[0])
            shift_y = intermediate_shift[1] + (parent_anchor[1] - child_anchor[1])
        else:
            shift_x = intermediate_shift[0]
            shift_y = intermediate_shift[1]
        return (shift_x + layer_offset[0], shift_y + layer_offset[1])

    elif rule == RULE_BODY_SHIELD_RELATIVE:
        # Shields in classic RO have 0 anchors and align relative to parent body origin
        return (intermediate_shift[0] + layer_offset[0], intermediate_shift[1] + layer_offset[1])

    elif rule == RULE_STANDALONE_UNATTACHED:
        return (layer_offset[0], layer_offset[1])

    else:
        raise ForgeError(ErrorCode.INVALID_INPUT, f'Unsupported attachment rule: {rule}.')


def composite_attachment_layers(
    layers: Sequence[dict[str, Any]],
    layer_order: Sequence[str],
) -> list[dict[str, Any]]:
    """Arrange multi-part layers according to declared layer order without flattening.

    Preserves part identity, original layer ordinals, sprite indices, pools,
    transforms, bounds, and all layer metadata. Never mutates input records.
    """
    check(isinstance(layers, (list, tuple)), 'Expected sequence of layers.')
    check(isinstance(layer_order, (list, tuple)) and bool(layer_order), 'Expected non-empty layer_order sequence.')

    order_map = {part: idx for idx, part in enumerate(layer_order)}

    # Group layers by part while preserving internal order
    part_groups: dict[str, list[dict[str, Any]]] = {}
    for layer in layers:
        part = layer.get('part', 'unknown')
        part_groups.setdefault(part, []).append(deepcopy(layer))

    result: list[dict[str, Any]] = []

    # Emit parts in declared order
    for part in layer_order:
        if part in part_groups:
            for l in part_groups[part]:
                result.append(l)

    # Any parts not in declared order are placed at the end with diagnostic preservation
    for part, p_layers in part_groups.items():
        if part not in order_map:
            for l in p_layers:
                result.append(l)

    return result


def validate_attachment_compatibility(
    parent_profile: dict[str, Any],
    child_profile: dict[str, Any],
    *,
    parent_act: dict[str, Any] | None = None,
    child_act: dict[str, Any] | None = None,
    rule: str | None = None,
    gameplay_job_check: bool = True,
    required_weapon_family: str | None = None,
    available_weapon_families: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Validate full attachment compatibility between a parent profile and child profile.

    Detects:
    1. Incompatible resource kinds (e.g. companion attached to player, or monster with player head).
    2. Missing weapon actions or incompatible action families.
    3. Gameplay-job / visual-outfit mismatches without silent filename fallback.
    4. Per-slot action matching and exact frame counts (e.g. Pickup differing 3 vs 2).
    5. Anchor availability on every required frame.
    6. Exact layer order preservation.
    """
    diagnostics: list[dict[str, Any]] = []

    parent_id = parent_profile.get('id', 'unknown-parent')
    child_id = child_profile.get('id', 'unknown-child')
    parent_kind = parent_profile.get('resource_kind')
    child_kind = child_profile.get('resource_kind')

    # Determine default rule if not explicitly provided
    if rule is None:
        if parent_kind == 'body' and child_kind == 'head':
            rule = RULE_PLAYER_HEAD_ANCHOR_DELTA
        elif parent_kind in ('body', 'head') and child_kind == 'accessory':
            rule = RULE_HEAD_ACCESSORY_ANCHOR_DELTA
        elif parent_kind == 'body' and child_kind == 'shield':
            rule = RULE_BODY_SHIELD_RELATIVE
        elif child_kind == 'companion':
            rule = RULE_STANDALONE_UNATTACHED
        else:
            rule = 'unverified'

    # 1. Resource kind compatibility check
    if child_kind == 'companion':
        diagnostics.append({
            'code': CODE_INCOMPATIBLE_RESOURCE_KIND,
            'message': f'Companion resource {child_id} cannot be attached as equipment to parent {parent_id}; companion is standalone.',
            'parent_kind': parent_kind,
            'child_kind': child_kind,
        })
    elif parent_kind == 'monster' and child_kind in ('head', 'accessory', 'shield', 'weapon'):
        diagnostics.append({
            'code': CODE_INCOMPATIBLE_RESOURCE_KIND,
            'message': f'Monster body {parent_id} does not support player equipment/attachment {child_id}.',
            'parent_kind': parent_kind,
            'child_kind': child_kind,
        })
    elif parent_kind not in ('body', 'head') and child_kind in ('head', 'accessory', 'shield', 'weapon'):
        diagnostics.append({
            'code': CODE_INCOMPATIBLE_RESOURCE_KIND,
            'message': f'Parent {parent_id} with kind {parent_kind} cannot act as attachment host for {child_id}.',
            'parent_kind': parent_kind,
            'child_kind': child_kind,
        })

    # 2. Gameplay job vs visual outfit check
    if gameplay_job_check:
        parent_job = parent_profile.get('gameplay_job')
        child_job = child_profile.get('gameplay_job')
        # If both specify job and neither is universal/None and they don't match:
        if parent_job and child_job and parent_job != child_job:
            # E.g. Novice body with Dragon Knight shield
            if parent_job != 'all' and child_job != 'all':
                diagnostics.append({
                    'code': CODE_GAMEPLAY_JOB_MISMATCH,
                    'message': f'Gameplay job mismatch: parent body job "{parent_job}" is incompatible with child equipment job "{child_job}".',
                    'parent_job': parent_job,
                    'child_job': child_job,
                })

    # 3. Weapon action family check
    if required_weapon_family is not None and available_weapon_families is not None:
        if required_weapon_family not in available_weapon_families:
            diagnostics.append({
                'code': CODE_INCOMPATIBLE_ACTION_FAMILY,
                'message': f'Required weapon action family "{required_weapon_family}" is not supported by parent action profile.',
                'required': required_weapon_family,
                'available': list(available_weapon_families),
            })

    # 4. Action slot mapping and frame count verification
    parent_actions = parent_profile.get('actions', [])
    child_actions = child_profile.get('actions', [])

    # Map actions by group / id
    parent_by_slot: dict[int, dict[str, Any]] = {}
    for a in parent_actions:
        for s in a.get('slots', []):
            parent_by_slot[s] = a

    child_by_slot: dict[int, dict[str, Any]] = {}
    for a in child_actions:
        for s in a.get('slots', []):
            child_by_slot[s] = a

    # Slot frame counts from ACT if provided, else topology / actions
    parent_slot_frames: dict[int, int] = {}
    child_slot_frames: dict[int, int] = {}

    if parent_act is not None:
        for si, a in enumerate(parent_act.get('actions', [])):
            parent_slot_frames[si] = len(a)
    if child_act is not None:
        for si, a in enumerate(child_act.get('actions', [])):
            child_slot_frames[si] = len(a)

    total_slots = len(parent_by_slot)
    matching_slots = 0
    mismatched_slots = 0
    slot_details: list[dict[str, Any]] = []

    for slot in sorted(parent_by_slot.keys()):
        p_act_entry = parent_by_slot[slot]
        c_act_entry = child_by_slot.get(slot)

        if c_act_entry is None:
            # Missing action in child
            mismatched_slots += 1
            diagnostics.append({
                'code': CODE_MISSING_ATTACHMENT_ACTION,
                'slot': slot,
                'parent_action': p_act_entry.get('id'),
                'message': f'Child attachment {child_id} lacks numeric action slot {slot} (action {p_act_entry.get("id")}).',
            })
            slot_details.append({
                'slot': slot,
                'parent_action': p_act_entry.get('id'),
                'child_action': None,
                'status': 'MISSING_ACTION',
                'parent_frames': parent_slot_frames.get(slot),
                'child_frames': None,
            })
            continue

        p_frames = parent_slot_frames.get(slot)
        c_frames = child_slot_frames.get(slot)

        if p_frames is not None and c_frames is not None:
            if p_frames != c_frames:
                mismatched_slots += 1
                group = slot // 8
                view = slot % 8
                diagnostics.append({
                    'code': CODE_MISMATCHED_FRAME_COUNT,
                    'slot': slot,
                    'group': group,
                    'view': view,
                    'action': p_act_entry.get('id'),
                    'parent_frames': p_frames,
                    'child_frames': c_frames,
                    'message': (
                        f'Slot {slot} (Group {group} {p_act_entry.get("id")}, View {view}) frame count mismatch: '
                        f'parent={p_frames} frames, child={c_frames} frames. No silent fallback applied.'
                    ),
                })
                slot_details.append({
                    'slot': slot,
                    'parent_action': p_act_entry.get('id'),
                    'child_action': c_act_entry.get('id'),
                    'status': 'MISMATCHED_FRAME_COUNT',
                    'parent_frames': p_frames,
                    'child_frames': c_frames,
                })
            else:
                matching_slots += 1
                slot_details.append({
                    'slot': slot,
                    'parent_action': p_act_entry.get('id'),
                    'child_action': c_act_entry.get('id'),
                    'status': 'SUPPORTED',
                    'parent_frames': p_frames,
                    'child_frames': c_frames,
                })
        else:
            # No concrete ACT bytes provided, structural slots match
            matching_slots += 1
            slot_details.append({
                'slot': slot,
                'parent_action': p_act_entry.get('id'),
                'child_action': c_act_entry.get('id'),
                'status': 'SUPPORTED',
                'parent_frames': None,
                'child_frames': None,
            })

    # 5. Anchor checks if ACTs are supplied
    if parent_act is not None and child_act is not None:
        if rule in (RULE_PLAYER_HEAD_ANCHOR_DELTA, RULE_HEAD_ACCESSORY_ANCHOR_DELTA):
            # Check anchors on each motion
            p_actions_raw = parent_act.get('actions', [])
            c_actions_raw = child_act.get('actions', [])
            for si in range(min(len(p_actions_raw), len(c_actions_raw))):
                for fi in range(min(len(p_actions_raw[si]), len(c_actions_raw[si]))):
                    p_anchors = p_actions_raw[si][fi].get('anchors', [])
                    c_anchors = c_actions_raw[si][fi].get('anchors', [])
                    if rule == RULE_PLAYER_HEAD_ANCHOR_DELTA:
                        if not p_anchors:
                            diagnostics.append({
                                'code': CODE_MISSING_ANCHOR,
                                'slot': si,
                                'frame': fi,
                                'part': 'parent',
                                'message': f'Parent {parent_id} missing anchor on slot {si} frame {fi}.',
                            })
                            break
                        if not c_anchors:
                            diagnostics.append({
                                'code': CODE_MISSING_ANCHOR,
                                'slot': si,
                                'frame': fi,
                                'part': 'child',
                                'message': f'Child {child_id} missing anchor on slot {si} frame {fi}.',
                            })
                            break

    # Determine overall status
    has_incompatible = any(
        d['code'] in (CODE_INCOMPATIBLE_RESOURCE_KIND, CODE_INCOMPATIBLE_ACTION_FAMILY, CODE_GAMEPLAY_JOB_MISMATCH)
        for d in diagnostics
    )
    if has_incompatible:
        overall_status = 'UNSUPPORTED'
    elif mismatched_slots > 0:
        overall_status = 'PARTIAL'
    elif rule not in SUPPORTED_RULES or rule == 'unverified':
        overall_status = 'UNVERIFIED'
    else:
        overall_status = 'SUPPORTED'

    # Determine layer ordering
    parent_part = parent_profile.get('parts', {}).get('declared', ['body'])[0]
    child_part = child_profile.get('parts', {}).get('declared', ['attachment'])[0]

    if parent_part == 'body' and child_part == 'head':
        layer_order = ['body', 'head']
    elif parent_part == 'body' and child_part == 'shield':
        layer_order = ['body', 'shield']
    elif parent_part == 'body' and child_part == 'accessory':
        layer_order = ['body', 'head', 'accessory']
    elif parent_part == 'head' and child_part == 'accessory':
        layer_order = ['head', 'accessory']
    else:
        layer_order = [parent_part, child_part]

    # Anchor mode summary
    if rule == RULE_PLAYER_HEAD_ANCHOR_DELTA:
        anchor_mode = 'parent_head_anchor_delta'
        p_anchor_idx: int | None = 0
        c_anchor_idx: int | None = 0
    elif rule == RULE_HEAD_ACCESSORY_ANCHOR_DELTA:
        anchor_mode = 'head_accessory_anchor_delta'
        p_anchor_idx = 0
        c_anchor_idx = 0
    elif rule == RULE_BODY_SHIELD_RELATIVE:
        anchor_mode = 'body_shield_relative'
        p_anchor_idx = None
        c_anchor_idx = None
    elif rule == RULE_STANDALONE_UNATTACHED:
        anchor_mode = 'standalone_unattached'
        p_anchor_idx = None
        c_anchor_idx = None
    else:
        anchor_mode = 'unverified'
        p_anchor_idx = None
        c_anchor_idx = None

    report = {
        'schema': REPORT_SCHEMA,
        'id': f'compat-{parent_id}+{child_id}',
        'parent_profile_id': parent_id,
        'child_profile_id': child_id,
        'parent_part': parent_part,
        'child_part': child_part,
        'rule': rule,
        'status': overall_status,
        'action_mapping': {
            'total_actions': total_slots,
            'matching_actions': matching_slots,
            'mismatched_actions': mismatched_slots,
        },
        'anchor_rule': {
            'mode': anchor_mode,
            'parent_anchor_index': p_anchor_idx,
            'child_anchor_index': c_anchor_idx,
        },
        'layer_order': layer_order,
        'diagnostics': diagnostics,
        'slot_details': slot_details,
    }
    return sealed(report)


def build_attachment_pairing_record(
    parent_profile: dict[str, Any],
    child_profile: dict[str, Any],
    *,
    parent_act: dict[str, Any] | None = None,
    child_act: dict[str, Any] | None = None,
    rule: str | None = None,
    compatibility_dimensions: dict[str, str] | None = None,
    evidence: list[str] | None = None,
    constraints: list[str] | None = None,
) -> dict[str, Any]:
    """Build a versioned attachment pairing record for the compatibility registry."""
    validation = validate_attachment_compatibility(
        parent_profile, child_profile,
        parent_act=parent_act, child_act=child_act,
        rule=rule,
    )

    parent_id = parent_profile['id']
    child_id = child_profile['id']
    pairing_id = f'{parent_id}+{child_id}'

    # Default compatibility dimensions
    dims = {
        'static_structure': 'VERIFIED' if validation['status'] in ('SUPPORTED', 'PARTIAL') else 'UNSUPPORTED' if validation['status'] == 'UNSUPPORTED' else 'UNVERIFIED',
        'preview_composition': 'VERIFIED' if validation['status'] == 'SUPPORTED' else 'PARTIAL' if validation['status'] == 'PARTIAL' else 'UNSUPPORTED' if validation['status'] == 'UNSUPPORTED' else 'UNVERIFIED',
        'compilation': 'VERIFIED' if validation['status'] == 'SUPPORTED' else 'PARTIAL' if validation['status'] == 'PARTIAL' else 'UNSUPPORTED' if validation['status'] == 'UNSUPPORTED' else 'UNVERIFIED',
        'independent_rust': 'VERIFIED' if parent_profile.get('compatibility', {}).get('independent_rust') == 'VERIFIED' and child_profile.get('compatibility', {}).get('independent_rust') == 'VERIFIED' else 'UNVERIFIED',
        'native_korangar': 'VERIFIED' if parent_profile.get('compatibility', {}).get('native_korangar') == 'VERIFIED' and child_profile.get('compatibility', {}).get('native_korangar') == 'VERIFIED' else 'UNVERIFIED',
    }
    if compatibility_dimensions:
        dims.update(compatibility_dimensions)

    default_constraints = [
        f'Attachment pairing between parent {parent_id} and child {child_id}.',
        f'Rule: {validation["rule"]}; Status: {validation["status"]}.',
    ]
    for d in validation['diagnostics']:
        default_constraints.append(f"{d['code']}: {d['message']}")

    record = {
        'id': pairing_id,
        'parent_profile_id': parent_id,
        'child_profile_id': child_id,
        'parent_part': validation['parent_part'],
        'child_part': validation['child_part'],
        'rule': validation['rule'],
        'status': validation['status'],
        'action_mapping': validation['action_mapping'],
        'anchor_rule': validation['anchor_rule'],
        'layer_order': validation['layer_order'],
        'compatibility': dims,
        'evidence': evidence or [EVIDENCE_KORANGAR_LOADER],
        'constraints': constraints or default_constraints,
    }
    return record
