"""Deterministic versioned compatibility registry for job/body profiles (RSF-32).

Maintains data-driven ACT/SPR resource profiles, separating gameplay job, visual body
family, sex/variant, action topology, equipment attachments, and orthogonal compatibility
dimensions. No implicit Novice defaults or artistic suitability claims are made.
"""

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any, Mapping

from ro_sprite_forge.core.canonical import canonical_bytes, check, check_seal, digest, sealed
from ro_sprite_forge.core.contracts import (
    ActorContract,
    RuntimeProfileContract,
    contract_schema,
    load_actor,
    load_runtime_profile,
    reference,
    require,
    _shape,
)
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.profiles import REVISION as KORANGAR_REVISION

REGISTRY_SCHEMA = 'rsf.compatibility-registry/v1'
EVIDENCE_KORANGAR_ANIM = '72a49aa2069306499e2fe76200a9388c8c69b97ec19ed76ade84c2297d1ccaa1'
EVIDENCE_KORANGAR_LOADER = '318e40783be1ee0a280b341967a69f3bcf247456fb72d0d099aead5551ab06b9'

PLAYER_ACTION_NAMES = (
    'Idle', 'Walk', 'Sit', 'Pickup', 'ReadyFight', 'Attack1', 'Hurt',
    'Freeze1', 'Die', 'Freeze2', 'Attack2', 'Attack3', 'Skill'
)
MONSTER_ACTION_NAMES = ('Idle', 'Walk', 'Attack1', 'Hurt', 'Die')
COMPANION_ACTION_NAMES = ('Idle', 'Walk')


def _validate_profile_entry(entry: dict, path: str = '/profiles') -> None:
    """Validate internal semantic consistency of a single profile entry."""
    require(isinstance(entry, dict), path, 'Expected profile entry object.')
    pid = entry.get('id')
    require(bool(pid) and isinstance(pid, str), f'{path}/id', 'Missing required profile identity.')
    p_path = f'{path}/{pid}'

    # Check version format
    ver = entry.get('version')
    require(
        bool(ver) and isinstance(ver, str) and re.fullmatch(r'^[1-9][0-9]{0,5}\.[0-9]{1,6}\.[0-9]{1,6}$', ver) is not None,
        f'{p_path}/version',
        'Malformed schema or profile version.',
    )

    # Check format versions
    formats = entry.get('formats', {})
    require(formats.get('act_version') == '2.4', f'{p_path}/formats/act_version', 'Unsupported format version: only ACT 2.4 supported.')
    require(formats.get('spr_version') == '2.1', f'{p_path}/formats/spr_version', 'Unsupported format version: only SPR 2.1 supported.')

    # Check source hashes
    sh = entry.get('source_hashes', {})
    for hk in ('act_sha256', 'spr_sha256'):
        hval = sh.get(hk)
        require(
            bool(hval) and isinstance(hval, str) and re.fullmatch(r'^[0-9a-f]{64}$', hval) is not None,
            f'{p_path}/source_hashes/{hk}',
            'Mismatched or malformed source hash format.',
        )

    # Check actions and slots
    actions = entry.get('actions', [])
    require(isinstance(actions, list), f'{p_path}/actions', 'Expected actions list.')
    seen_slots = set()
    for ai, action in enumerate(actions):
        a_path = f'{p_path}/actions/{ai}'
        for s in action.get('slots', []):
            require(s not in seen_slots, f'{a_path}/slots', f'Duplicate action slot: {s}.')
            seen_slots.add(s)

    # Check topology
    topo = entry.get('topology', {})
    require(isinstance(topo, dict), f'{p_path}/topology', 'Expected topology object.')
    require(topo.get('slot_count') == len(seen_slots), f'{p_path}/topology/slot_count', 'Topology slot_count must match action slots.')

    # Check parts and relationships
    parts = entry.get('parts', {})
    declared_parts = parts.get('declared', [])
    require(bool(declared_parts), f'{p_path}/parts/declared', 'Missing required resource part declaration.')
    for ri, rel in enumerate(parts.get('relationships', [])):
        r_path = f'{p_path}/parts/relationships/{ri}'
        parent, child = rel.get('parent'), rel.get('child')
        require(parent in declared_parts or parent in parts.get('order', []), f'{r_path}/parent', 'Inconsistent body/head resource links: parent undeclared.')
        require(child in parts.get('order', []), f'{r_path}/child', 'Inconsistent body/head resource links: child undeclared.')

    # Check evidence consistency
    evidence = entry.get('evidence', [])
    ev_hashes = {e.get('sha256') for e in evidence if isinstance(e, dict)}
    compat = entry.get('compatibility', {})
    for dim, status in compat.items():
        if status == 'VERIFIED':
            # Format decoding / Rust / Native verified requires evidence
            require(
                bool(evidence),
                f'{p_path}/compatibility/{dim}',
                'Evidence references inconsistent with declared support: VERIFIED requires supporting evidence.',
            )

    # Check canonical hash of profile payload
    payload = {k: v for k, v in entry.items() if k != 'canonical_sha256'}
    expected_sha = digest(canonical_bytes(payload))
    require(
        entry.get('canonical_sha256') == expected_sha,
        f'{p_path}/canonical_sha256',
        'Profile canonical digest mismatch.',
    )


def validate_registry(value: dict) -> dict:
    """Validate external registry document shape and semantic constraints."""
    require(isinstance(value, dict), '/', 'Expected a compatibility registry object.')
    require(value.get('schema') == REGISTRY_SCHEMA, '/schema', 'Unsupported schema version.')
    _shape(value, contract_schema(REGISTRY_SCHEMA))

    profiles = value.get('profiles', [])
    seen_ids = set()
    for i, profile in enumerate(profiles):
        pid = profile.get('id')
        require(pid not in seen_ids, f'/profiles/{i}/id', f'Duplicate profile ID: {pid}.')
        seen_ids.add(pid)
        _validate_profile_entry(profile, path=f'/profiles/{i}')

    if 'attachment_pairings' in value:
        pairings = value['attachment_pairings']
        require(isinstance(pairings, list), '/attachment_pairings', 'Expected attachment_pairings list.')
        seen_pairing_ids = set()
        for i, pairing in enumerate(pairings):
            require(isinstance(pairing, dict), f'/attachment_pairings/{i}', 'Expected attachment pairing object.')
            pair_id = pairing.get('id')
            require(bool(pair_id) and isinstance(pair_id, str), f'/attachment_pairings/{i}/id', 'Missing required pairing ID.')
            require(pair_id not in seen_pairing_ids, f'/attachment_pairings/{i}/id', f'Duplicate attachment pairing ID: {pair_id}.')
            seen_pairing_ids.add(pair_id)

            parent_pid = pairing.get('parent_profile_id')
            child_pid = pairing.get('child_profile_id')
            require(parent_pid in seen_ids, f'/attachment_pairings/{i}/parent_profile_id', f'Unknown parent profile ID: {parent_pid}.')
            require(child_pid in seen_ids, f'/attachment_pairings/{i}/child_profile_id', f'Unknown child profile ID: {child_pid}.')

            evidence = pairing.get('evidence', [])
            compat = pairing.get('compatibility', {})
            for dim, status in compat.items():
                if status == 'VERIFIED':
                    require(
                        bool(evidence),
                        f'/attachment_pairings/{i}/compatibility/{dim}',
                        'Evidence references inconsistent with declared support: VERIFIED requires supporting evidence.',
                    )

    if 'cosmetic_pairings' in value:
        from ro_sprite_forge.core.appearance import validate_cosmetic_pairing
        ids = set()
        for pairing in value['cosmetic_pairings']:
            require(pairing['id'] not in ids, '/cosmetic_pairings', 'CONFLICTING_COSTUME_BINDING.')
            ids.add(pairing['id'])
            validate_cosmetic_pairing(pairing, value)

    if 'offline_actions' in value:
        ids = set()
        by_id = {p['id']: p for p in profiles}
        for entry in value['offline_actions']:
            check_seal(entry, 'rsf.offline-action-capability/v1')
            require(entry['id'] not in ids, '/offline_actions', 'DUPLICATE_ACTION_ID.')
            ids.add(entry['id'])
            parent = by_id.get(entry['profile_id'])
            require(parent is not None, '/offline_actions', 'UNKNOWN_ACTOR_PROFILE.')
            require(entry['id'] == entry['profile_id'] + ':' + entry['action_id'],
                    '/offline_actions', 'INVALID_ACTION_IDENTITY.')
            require(entry['profile_sha256'] == parent['canonical_sha256'],
                    '/offline_actions', 'PROFILE_REVISION_MISMATCH.')
            require(entry['action_id'] not in {a['id'] for a in parent['actions']},
                    '/offline_actions', 'CONFLICTING_NATIVE_ACTION_BINDING.')

    payload = {k: v for k, v in value.items() if k != 'canonical_sha256'}
    expected_digest = digest(canonical_bytes(payload))
    require(value.get('canonical_sha256') == expected_digest, '/canonical_sha256', 'Registry digest mismatch.')
    return value


def verify_source_hashes(profile: dict, act_bytes: bytes, spr_bytes: bytes) -> bool:
    """Verify that concrete ACT/SPR bytes match the profile's hash binding.

    Raises ForgeError on hash mismatch, detecting source revision discrepancy.
    """
    act_sha = hashlib.sha256(act_bytes).hexdigest()
    spr_sha = hashlib.sha256(spr_bytes).hexdigest()
    expected_act = profile['source_hashes']['act_sha256']
    expected_spr = profile['source_hashes']['spr_sha256']

    if act_sha != expected_act:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f'SOURCE_HASH_MISMATCH: ACT sha256 {act_sha} does not match profile expectation {expected_act}.',
            path='/source_hashes/act_sha256',
        )
    if spr_sha != expected_spr:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f'SOURCE_HASH_MISMATCH: SPR sha256 {spr_sha} does not match profile expectation {expected_spr}.',
            path='/source_hashes/spr_sha256',
        )
    return True


def build_profile_entry(
    *,
    id: str,
    version: str = '1.0.0',
    resource_kind: str,
    gameplay_job: str | None,
    visual: dict,
    formats: dict,
    source_hashes: dict,
    actions: list[dict],
    parts: dict,
    image_pool: dict,
    topology: dict,
    compatibility: dict,
    evidence: list[dict],
    constraints: list[str] | None = None,
) -> dict:
    """Build a canonically sealed profile entry."""
    payload = {
        'id': id,
        'version': version,
        'resource_kind': resource_kind,
        'gameplay_job': gameplay_job,
        'visual': visual,
        'formats': formats,
        'source_hashes': source_hashes,
        'actions': actions,
        'parts': parts,
        'image_pool': image_pool,
        'topology': topology,
        'compatibility': compatibility,
        'evidence': evidence,
        'constraints': constraints or [],
    }
    return sealed(payload)


def to_runtime_profile_contract(profile: dict) -> RuntimeProfileContract:
    """Convert a registered profile entry into a validated RuntimeProfileContract (rsf.runtime-profile/v2)."""
    kind = profile['resource_kind']
    category = 'player' if kind in ('body', 'head', 'shield', 'weapon', 'accessory') else 'monster' if kind in ('monster', 'companion') else 'npc'

    # Build actions
    actions_doc = []
    for a in profile['actions']:
        actions_doc.append({
            'id': a['id'],
            'group': a['group'],
            'slots': a['slots'],
            'mapping': a['mapping'],
            'reachability': a['reachability'],
            'evidence': [EVIDENCE_KORANGAR_ANIM] if a['mapping'] == 'SUPPORTED' else [],
        })

    # Build timing
    timing = None
    if category in ('player', 'monster'):
        looping = [a['id'] for a in profile['actions'] if a['id'] in ('Idle', 'Walk')]
        nonlooping = [a['id'] for a in profile['actions'] if a['id'] in ('Attack1', 'Attack2', 'Attack3', 'Hurt', 'Pickup', 'Die')]
        timing = {
            'default_interval_ms': 'raw_delay * 50',
            'walk_interval_ms': 'raw_delay * movement_speed * 100 / 150 / 5',
            'pickup_interval_ms': 'raw_delay * 25',
            'attack_hurt_frame': 'elapsed_ms * selected_frame_count / server_duration_ms',
            'looping': looping,
            'nonlooping': nonlooping,
            'player_idle': 'always frame 0 (Player only)',
            'nonloop_end': 'clamp to final frame',
            'completion_check': 'uses group view 0, modulo arrays; frame_time > frame_count',
        }

    # Relationships
    relationships = []
    for r in profile['parts'].get('relationships', []):
        relationships.append({
            'parent': r['parent'],
            'child': r['child'],
            'rule': r['rule'],
            'status': r['status'],
            'evidence': [EVIDENCE_KORANGAR_LOADER] if r['status'] == 'SUPPORTED' else [],
        })

    source_evidence = [
        {'path': 'korangar/src/world/animation/mod.rs', 'sha256': EVIDENCE_KORANGAR_ANIM, 'sections': 'action_base_offset'},
        {'path': 'korangar/src/loaders/animation/mod.rs', 'sha256': EVIDENCE_KORANGAR_LOADER, 'sections': 'ordered parts, anchor registration'},
    ]

    rp_doc = {
        'schema': 'rsf.runtime-profile/v2',
        'id': f"rp-{profile['id']}",
        'profile_version': profile['version'],
        'category': category,
        'source': {
            'repository': 'https://github.com/vE5li/korangar',
            'revision': KORANGAR_REVISION,
            'evidence': source_evidence,
        },
        'legacy_profile_sha256': '0' * 64,
        'actions': actions_doc,
        'views': list(range(8)),
        'resolution': {
            'view': '(camera_direction + entity_direction) & 7',
            'requested_slot': 'group * 8 + view',
            'resolved_slot': 'requested_slot % prepared_animation_count',
            'delay_slot': 'requested_slot % delay_count',
            'unmapped_action': 'fallback to group 0; requested action UNSUPPORTED',
        },
        'timing': timing,
        'parts': {
            'order': profile['parts']['order'],
            'relationships': relationships,
            'attachments': {'status': 'UNVERIFIED', 'declarations': []},
        },
    }
    return load_runtime_profile(rp_doc)


def to_actor_contract(profile: dict, *, actor_id: str | None = None) -> ActorContract:
    """Convert a registered profile entry into a validated ActorContract (rsf.actor/v1)."""
    rp = to_runtime_profile_contract(profile)
    kind = profile['resource_kind']
    category = 'player' if kind in ('body', 'head', 'shield', 'weapon', 'accessory') else 'monster' if kind in ('monster', 'companion') else 'npc'

    resources = []
    for part in profile['parts']['declared']:
        resources.append({
            'part': part,
            'act_sha256': profile['source_hashes']['act_sha256'],
            'spr_sha256': profile['source_hashes']['spr_sha256'],
            'inventory_sha256': digest(canonical_bytes(profile['topology'])),
        })

    actor_doc = {
        'schema': 'rsf.actor/v1',
        'id': actor_id or f"actor-{profile['id']}",
        'revision': 1,
        'previous_sha256': None,
        'category': category,
        'gameplay_job': profile.get('gameplay_job'),
        'visual': profile['visual'],
        'parts': profile['parts']['declared'],
        'runtime_profile': reference(rp),
        'action_profile': f"{profile['id']}-actions",
        'compatibility': {
            'status': 'SUPPORTED' if profile['compatibility']['runtime_mapping'] == 'VERIFIED' else 'UNVERIFIED',
            'declarations': [
                {
                    'id': f"{profile['id']}-compat",
                    'status': 'SUPPORTED' if profile['compatibility']['runtime_mapping'] == 'VERIFIED' else 'UNVERIFIED',
                    'evidence': [profile['evidence'][0]['sha256']] if profile['evidence'] else [],
                }
            ],
        },
        'resources': resources,
    }
    return load_actor(actor_doc)


# Standard audited reference profiles
def _novice_male_body_profile() -> dict:
    act_sha = 'a82086ba005506a16ee0740ebd1d33c43de8cc4ee1a622ea933ff9e0502c1c77'
    spr_sha = '7f4efe357b0f80e71ba2dcdb93d1c110988b1b8f382e1dbfc722e3a2cf85a533'
    actions = [
        {'id': name, 'group': g, 'slots': list(range(g * 8, g * 8 + 8)), 'mapping': 'SUPPORTED', 'reachability': 'UNVERIFIED', 'frame_count': None}
        for g, name in enumerate(PLAYER_ACTION_NAMES)
    ]
    return build_profile_entry(
        id='novice-male-body-v1',
        version='1.0.0',
        resource_kind='body',
        gameplay_job='novice',
        visual={'body_family': 'human_standard', 'sex': 'male', 'body_variant': None, 'costume': None},
        formats={'act_version': '2.4', 'spr_version': '2.1'},
        source_hashes={'act_sha256': act_sha, 'spr_sha256': spr_sha},
        actions=actions,
        parts={
            'declared': ['body'],
            'order': ['body', 'head'],
            'relationships': [{'parent': 'body', 'child': 'head', 'rule': 'player_head_anchor_delta', 'status': 'SUPPORTED', 'evidence': [EVIDENCE_KORANGAR_LOADER]}],
            'attachments': {'status': 'UNVERIFIED', 'declarations': []},
        },
        image_pool={'indexed_count': 110, 'rgba_count': 0, 'referenced_count': 110, 'distinct_content_count': 108},
        topology={'action_count': 13, 'slot_count': 104, 'motion_count': 456, 'layer_counts': [1], 'anchor_counts': [1]},
        compatibility={
            'format_decoding': 'VERIFIED',
            'inventory': 'VERIFIED',
            'runtime_mapping': 'VERIFIED',
            'requirements': 'VERIFIED',
            'assignment': 'VERIFIED',
            'preview': 'VERIFIED',
            'compilation': 'VERIFIED',
            'independent_rust': 'VERIFIED',
            'native_korangar': 'VERIFIED',
        },
        evidence=[
            {'kind': 'source_act', 'reference': 'novice_male_body.act', 'sha256': act_sha},
            {'kind': 'source_spr', 'reference': 'novice_male_body.spr', 'sha256': spr_sha},
            {'kind': 'rust_oracle', 'reference': 'tools/rust-oracle', 'sha256': act_sha},
            {'kind': 'native_korangar', 'reference': 'Korangar-v1.1-pinned', 'sha256': EVIDENCE_KORANGAR_ANIM},
        ],
        constraints=['Player standard 13-group 104-slot runtime mapping.', 'Requires head part with player_head_anchor_delta.'],
    )


def _novice_male_head_profile() -> dict:
    act_sha = '96cb4c7daada65ead29ade650c34da1cba93937d3b360c5468506c3d056219de'
    spr_sha = 'dfc548c5cfd9aeb66616c5912df78773c2798834f9412a309a5a2b4f5868ac95'
    actions = [
        {'id': name, 'group': g, 'slots': list(range(g * 8, g * 8 + 8)), 'mapping': 'SUPPORTED', 'reachability': 'UNVERIFIED', 'frame_count': None}
        for g, name in enumerate(PLAYER_ACTION_NAMES)
    ]
    return build_profile_entry(
        id='novice-male-head-v1',
        version='1.0.0',
        resource_kind='head',
        gameplay_job='novice',
        visual={'body_family': 'human_standard', 'sex': 'male', 'body_variant': 'head_01', 'costume': None},
        formats={'act_version': '2.4', 'spr_version': '2.1'},
        source_hashes={'act_sha256': act_sha, 'spr_sha256': spr_sha},
        actions=actions,
        parts={
            'declared': ['head'],
            'order': ['head'],
            'relationships': [],
            'attachments': {'status': 'UNVERIFIED', 'declarations': []},
        },
        image_pool={'indexed_count': 15, 'rgba_count': 0, 'referenced_count': 15, 'distinct_content_count': 15},
        topology={'action_count': 13, 'slot_count': 104, 'motion_count': 456, 'layer_counts': [1], 'anchor_counts': [1]},
        compatibility={
            'format_decoding': 'VERIFIED',
            'inventory': 'VERIFIED',
            'runtime_mapping': 'VERIFIED',
            'requirements': 'VERIFIED',
            'assignment': 'VERIFIED',
            'preview': 'VERIFIED',
            'compilation': 'VERIFIED',
            'independent_rust': 'VERIFIED',
            'native_korangar': 'VERIFIED',
        },
        evidence=[
            {'kind': 'source_act', 'reference': 'novice_male_head.act', 'sha256': act_sha},
            {'kind': 'source_spr', 'reference': 'novice_male_head.spr', 'sha256': spr_sha},
            {'kind': 'rust_oracle', 'reference': 'tools/rust-oracle', 'sha256': act_sha},
            {'kind': 'native_korangar', 'reference': 'Korangar-v1.1-pinned', 'sha256': EVIDENCE_KORANGAR_ANIM},
        ],
        constraints=['Registered as child to body part via player_head_anchor_delta.'],
    )


def _orc_skeleton_profile() -> dict:
    act_sha = '31e1e75241bc534422e468ae134892c7b234d66022456b87b0423df5858370e2'
    spr_sha = 'a39f864209d63ae75bd62438da61775c510d7c55a78344b3065fb5918a55ce8f'
    actions = [
        {'id': name, 'group': g, 'slots': list(range(g * 8, g * 8 + 8)), 'mapping': 'SUPPORTED', 'reachability': 'UNVERIFIED', 'frame_count': None}
        for g, name in enumerate(MONSTER_ACTION_NAMES)
    ]
    return build_profile_entry(
        id='orc-skeleton-v1',
        version='1.0.0',
        resource_kind='monster',
        gameplay_job=None,
        visual={'body_family': 'monster_orc', 'sex': None, 'body_variant': None, 'costume': None},
        formats={'act_version': '2.4', 'spr_version': '2.1'},
        source_hashes={'act_sha256': act_sha, 'spr_sha256': spr_sha},
        actions=actions,
        parts={
            'declared': ['body'],
            'order': ['body'],
            'relationships': [],
            'attachments': {'status': 'UNVERIFIED', 'declarations': []},
        },
        image_pool={'indexed_count': 57, 'rgba_count': 0, 'referenced_count': 55, 'distinct_content_count': 57},
        topology={'action_count': 5, 'slot_count': 40, 'motion_count': 512, 'layer_counts': [1, 2, 3, 4, 12], 'anchor_counts': [0]},
        compatibility={
            'format_decoding': 'VERIFIED',
            'inventory': 'VERIFIED',
            'runtime_mapping': 'VERIFIED',
            'requirements': 'VERIFIED',
            'assignment': 'VERIFIED',
            'preview': 'VERIFIED',
            'compilation': 'VERIFIED',
            'independent_rust': 'VERIFIED',
            'native_korangar': 'VERIFIED',
        },
        evidence=[
            {'kind': 'source_act', 'reference': 'orc_skeleton.act', 'sha256': act_sha},
            {'kind': 'source_spr', 'reference': 'orc_skeleton.spr', 'sha256': spr_sha},
            {'kind': 'rust_oracle', 'reference': 'tools/rust-oracle', 'sha256': act_sha},
            {'kind': 'native_korangar', 'reference': 'Korangar-v1.1-pinned', 'sha256': EVIDENCE_KORANGAR_ANIM},
        ],
        constraints=['Monster 5-group 40-slot topology.', 'Multilayer frame structure including 12-layer death frame.'],
    )


def _genetic_female_body_profile() -> dict:
    act_sha = '27744afbed3b1fbca5a6cc3d012ced93b11559c45936465312c1cad67c931d34'
    spr_sha = '8130fe1646f0284f40b32c9118959334d480d75f70ace581d17f0e3b1300982c'
    actions = [
        {'id': name, 'group': g, 'slots': list(range(g * 8, g * 8 + 8)), 'mapping': 'SUPPORTED', 'reachability': 'UNVERIFIED', 'frame_count': None}
        for g, name in enumerate(PLAYER_ACTION_NAMES)
    ]
    return build_profile_entry(
        id='genetic-female-body-v1',
        version='1.0.0',
        resource_kind='body',
        gameplay_job='genetic',
        visual={'body_family': 'human_standard', 'sex': 'female', 'body_variant': None, 'costume': 'costume_1'},
        formats={'act_version': '2.4', 'spr_version': '2.1'},
        source_hashes={'act_sha256': act_sha, 'spr_sha256': spr_sha},
        actions=actions,
        parts={
            'declared': ['body'],
            'order': ['body', 'head'],
            'relationships': [{'parent': 'body', 'child': 'head', 'rule': 'player_head_anchor_delta', 'status': 'SUPPORTED', 'evidence': [EVIDENCE_KORANGAR_LOADER]}],
            'attachments': {'status': 'UNVERIFIED', 'declarations': []},
        },
        image_pool={'indexed_count': 122, 'rgba_count': 0, 'referenced_count': 122, 'distinct_content_count': 122},
        topology={'action_count': 13, 'slot_count': 104, 'motion_count': 456, 'layer_counts': [1], 'anchor_counts': [1]},
        compatibility={
            'format_decoding': 'VERIFIED',
            'inventory': 'VERIFIED',
            'runtime_mapping': 'VERIFIED',
            'requirements': 'VERIFIED',
            'assignment': 'VERIFIED',
            'preview': 'VERIFIED',
            'compilation': 'VERIFIED',
            'independent_rust': 'VERIFIED',
            'native_korangar': 'UNVERIFIED',
        },
        evidence=[
            {'kind': 'source_act', 'reference': r'data\sprite\인간족\몸통\여\costume_1\제네릭_여_1.act', 'sha256': act_sha},
            {'kind': 'source_spr', 'reference': r'data\sprite\인간족\몸통\여\costume_1\제네릭_여_1.spr', 'sha256': spr_sha},
            {'kind': 'rust_oracle', 'reference': 'tools/rust-oracle', 'sha256': act_sha},
        ],
        constraints=[
            'Non-Novice job class: Genetic female costume 1 body.',
            'Expanded 122 indexed sprite pool distinct from Novice 110 pool.',
            'Native Korangar verification unverified until explicitly tested in native corridor.',
        ],
    )


def _dragon_knight_male_shield_profile() -> dict:
    act_sha = 'c2175126b1357374b148f7da24eecb12de0a4ba5fb21e2330cb90e877fe176c9'
    spr_sha = '0b78157535438592c0572c55b5f870bd7b4a762ac344d7cf01703cb0a89558f4'
    actions = [
        {'id': name, 'group': g, 'slots': list(range(g * 8, g * 8 + 8)), 'mapping': 'SUPPORTED', 'reachability': 'UNVERIFIED', 'frame_count': None}
        for g, name in enumerate(PLAYER_ACTION_NAMES)
    ]
    return build_profile_entry(
        id='dragon-knight-male-shield-v1',
        version='1.0.0',
        resource_kind='shield',
        gameplay_job='dragon_knight',
        visual={'body_family': 'human_standard', 'sex': 'male', 'body_variant': None, 'costume': None},
        formats={'act_version': '2.4', 'spr_version': '2.1'},
        source_hashes={'act_sha256': act_sha, 'spr_sha256': spr_sha},
        actions=actions,
        parts={
            'declared': ['shield'],
            'order': ['shield'],
            'relationships': [],
            'attachments': {'status': 'UNVERIFIED', 'declarations': []},
        },
        image_pool={'indexed_count': 2, 'rgba_count': 0, 'referenced_count': 2, 'distinct_content_count': 2},
        topology={'action_count': 13, 'slot_count': 104, 'motion_count': 448, 'layer_counts': [1], 'anchor_counts': [0]},
        compatibility={
            'format_decoding': 'VERIFIED',
            'inventory': 'VERIFIED',
            'runtime_mapping': 'PARTIAL',
            'requirements': 'VERIFIED',
            'assignment': 'VERIFIED',
            'preview': 'VERIFIED',
            'compilation': 'VERIFIED',
            'independent_rust': 'VERIFIED',
            'native_korangar': 'UNVERIFIED',
        },
        evidence=[
            {'kind': 'source_act', 'reference': r'data\sprite\방패\dragon_knight\dragon_knight_남_쉴드.act', 'sha256': act_sha},
            {'kind': 'source_spr', 'reference': r'data\sprite\방패\dragon_knight\dragon_knight_남_쉴드.spr', 'sha256': spr_sha},
            {'kind': 'rust_oracle', 'reference': 'tools/rust-oracle', 'sha256': act_sha},
        ],
        constraints=[
            'Shield equipment topology with 448 motions instead of 456.',
            'No head anchor delta (0 anchors per frame).',
            'Partial runtime mapping due to differing action frame counts from base player bodies.',
        ],
    )


def _falcon_companion_profile() -> dict:
    act_sha = 'ac258085c313b566aa004a5a536a73578bd6a32033b7fb99331b2057dd83ad87'
    spr_sha = 'dce42bfa285251f17b7bd05ad824cb5f9f329ebf62ac1f0eb7f082f2e788dfae'
    actions = [
        {'id': name, 'group': g, 'slots': list(range(g * 8, g * 8 + 8)), 'mapping': 'SUPPORTED', 'reachability': 'UNVERIFIED', 'frame_count': None}
        for g, name in enumerate(COMPANION_ACTION_NAMES)
    ]
    return build_profile_entry(
        id='falcon-companion-v1',
        version='1.0.0',
        resource_kind='companion',
        gameplay_job=None,
        visual={'body_family': 'falcon', 'sex': None, 'body_variant': None, 'costume': None},
        formats={'act_version': '2.4', 'spr_version': '2.1'},
        source_hashes={'act_sha256': act_sha, 'spr_sha256': spr_sha},
        actions=actions,
        parts={
            'declared': ['body'],
            'order': ['body'],
            'relationships': [],
            'attachments': {'status': 'UNVERIFIED', 'declarations': []},
        },
        image_pool={'indexed_count': 45, 'rgba_count': 0, 'referenced_count': 45, 'distinct_content_count': 45},
        topology={'action_count': 2, 'slot_count': 16, 'motion_count': 72, 'layer_counts': [1], 'anchor_counts': [0]},
        compatibility={
            'format_decoding': 'VERIFIED',
            'inventory': 'VERIFIED',
            'runtime_mapping': 'PARTIAL',
            'requirements': 'VERIFIED',
            'assignment': 'VERIFIED',
            'preview': 'VERIFIED',
            'compilation': 'VERIFIED',
            'independent_rust': 'VERIFIED',
            'native_korangar': 'UNVERIFIED',
        },
        evidence=[
            {'kind': 'source_act', 'reference': r'data\sprite\몬스터\매.act', 'sha256': act_sha},
            {'kind': 'source_spr', 'reference': r'data\sprite\몬스터\매.spr', 'sha256': spr_sha},
            {'kind': 'rust_oracle', 'reference': 'tools/rust-oracle', 'sha256': act_sha},
        ],
        constraints=[
            'Non-standard 16-slot companion topology (2 action groups x 8 views).',
            'Only Idle and Walk mapped; combat actions unmapped.',
        ],
    )


def _synthetic_swordsman_profile() -> dict:
    act_sha = '1111111111111111111111111111111111111111111111111111111111111111'
    spr_sha = '2222222222222222222222222222222222222222222222222222222222222222'
    actions = [
        {'id': name, 'group': g, 'slots': list(range(g * 8, g * 8 + 8)), 'mapping': 'SUPPORTED', 'reachability': 'UNVERIFIED', 'frame_count': None}
        for g, name in enumerate(PLAYER_ACTION_NAMES)
    ]
    return build_profile_entry(
        id='synthetic-swordsman-v1',
        version='1.0.0',
        resource_kind='body',
        gameplay_job='swordsman',
        visual={'body_family': 'human_standard', 'sex': 'male', 'body_variant': 'armored', 'costume': None},
        formats={'act_version': '2.4', 'spr_version': '2.1'},
        source_hashes={'act_sha256': act_sha, 'spr_sha256': spr_sha},
        actions=actions,
        parts={
            'declared': ['body'],
            'order': ['body', 'head'],
            'relationships': [{'parent': 'body', 'child': 'head', 'rule': 'player_head_anchor_delta', 'status': 'SUPPORTED', 'evidence': [EVIDENCE_KORANGAR_LOADER]}],
            'attachments': {'status': 'UNVERIFIED', 'declarations': []},
        },
        image_pool={'indexed_count': 64, 'rgba_count': 0, 'referenced_count': 64, 'distinct_content_count': 64},
        topology={'action_count': 13, 'slot_count': 104, 'motion_count': 456, 'layer_counts': [1, 2], 'anchor_counts': [1]},
        compatibility={
            'format_decoding': 'VERIFIED',
            'inventory': 'VERIFIED',
            'runtime_mapping': 'VERIFIED',
            'requirements': 'VERIFIED',
            'assignment': 'VERIFIED',
            'preview': 'VERIFIED',
            'compilation': 'VERIFIED',
            'independent_rust': 'VERIFIED',
            'native_korangar': 'UNVERIFIED',
        },
        evidence=[
            {'kind': 'synthetic_spec', 'reference': 'tests/synthetic/swordsman.spec', 'sha256': act_sha},
        ],
        constraints=['Synthetic redistributable Swordsman job profile for public offline test coverage.'],
    )


def _jack_head_male_profile() -> dict:
    act_sha = '5dd8c7b8ebd5762b29863e86a77c4e555834cd401c0f559a8f92061a25a3ac93'
    spr_sha = 'e636bdc5772bb1fa9206b84369d46a13b3e6ac79b6c600e55c5dbb6a952fd655'
    actions = [
        {'id': name, 'group': g, 'slots': list(range(g * 8, g * 8 + 8)), 'mapping': 'SUPPORTED', 'reachability': 'UNVERIFIED', 'frame_count': None}
        for g, name in enumerate(PLAYER_ACTION_NAMES)
    ]
    return build_profile_entry(
        id='jack-head-male-v1',
        version='1.0.0',
        resource_kind='accessory',
        gameplay_job='novice',
        visual={'body_family': 'human_standard', 'sex': 'male', 'body_variant': 'jack_head', 'costume': None},
        formats={'act_version': '2.4', 'spr_version': '2.1'},
        source_hashes={'act_sha256': act_sha, 'spr_sha256': spr_sha},
        actions=actions,
        parts={
            'declared': ['accessory'],
            'order': ['body', 'head', 'accessory'],
            'relationships': [],
            'attachments': {'status': 'UNVERIFIED', 'declarations': []},
        },
        image_pool={'indexed_count': 14, 'rgba_count': 0, 'referenced_count': 14, 'distinct_content_count': 14},
        topology={'action_count': 13, 'slot_count': 104, 'motion_count': 456, 'layer_counts': [1], 'anchor_counts': [1]},
        compatibility={
            'format_decoding': 'VERIFIED',
            'inventory': 'VERIFIED',
            'runtime_mapping': 'VERIFIED',
            'requirements': 'VERIFIED',
            'assignment': 'VERIFIED',
            'preview': 'VERIFIED',
            'compilation': 'VERIFIED',
            'independent_rust': 'VERIFIED',
            'native_korangar': 'UNVERIFIED',
        },
        evidence=[
            {'kind': 'source_act', 'reference': r'data\sprite\악세사리\남\남_잭머리.act', 'sha256': act_sha},
            {'kind': 'source_spr', 'reference': r'data\sprite\악세사리\남\남_잭머리.spr', 'sha256': spr_sha},
            {'kind': 'rust_oracle', 'reference': 'tools/rust-oracle', 'sha256': act_sha},
        ],
        constraints=[
            'Audited head accessory profile (Jack Head Male).',
            'Attaches to head anchor coordinates via head_accessory_anchor_delta.',
        ],
    )


def _default_attachment_pairings() -> list[dict]:
    """Default verified and audited attachment pairing records."""
    return [
        {
            'id': 'novice-male-body-v1+novice-male-head-v1',
            'parent_profile_id': 'novice-male-body-v1',
            'child_profile_id': 'novice-male-head-v1',
            'parent_part': 'body',
            'child_part': 'head',
            'rule': 'player_head_anchor_delta',
            'status': 'SUPPORTED',
            'action_mapping': {
                'total_actions': 104,
                'matching_actions': 104,
                'mismatched_actions': 0,
            },
            'anchor_rule': {
                'mode': 'parent_head_anchor_delta',
                'parent_anchor_index': 0,
                'child_anchor_index': 0,
            },
            'layer_order': ['body', 'head'],
            'compatibility': {
                'static_structure': 'VERIFIED',
                'preview_composition': 'VERIFIED',
                'compilation': 'VERIFIED',
                'independent_rust': 'VERIFIED',
                'native_korangar': 'VERIFIED',
            },
            'evidence': [EVIDENCE_KORANGAR_LOADER, EVIDENCE_KORANGAR_ANIM],
            'constraints': [
                'Audited Player body + head attachment pair.',
                'Uses player_head_anchor_delta with exact anchor subtraction.',
                'Native Korangar verified playback in accepted M5 native corridor.',
            ],
        },
        {
            'id': 'novice-male-body-v1+jack-head-male-v1',
            'parent_profile_id': 'novice-male-body-v1',
            'child_profile_id': 'jack-head-male-v1',
            'parent_part': 'body',
            'child_part': 'accessory',
            'rule': 'head_accessory_anchor_delta',
            'status': 'SUPPORTED',
            'action_mapping': {
                'total_actions': 104,
                'matching_actions': 104,
                'mismatched_actions': 0,
            },
            'anchor_rule': {
                'mode': 'head_accessory_anchor_delta',
                'parent_anchor_index': 0,
                'child_anchor_index': 0,
            },
            'layer_order': ['body', 'head', 'accessory'],
            'compatibility': {
                'static_structure': 'VERIFIED',
                'preview_composition': 'VERIFIED',
                'compilation': 'VERIFIED',
                'independent_rust': 'VERIFIED',
                'native_korangar': 'UNVERIFIED',
            },
            'evidence': [EVIDENCE_KORANGAR_LOADER],
            'constraints': [
                'Audited Player body + Jack Head accessory pairing.',
                'Uses head_accessory_anchor_delta relative to head coordinates.',
                'Native Korangar unverified until explicitly executed in native corridor.',
            ],
        },
        {
            'id': 'novice-male-body-v1+dragon-knight-male-shield-v1',
            'parent_profile_id': 'novice-male-body-v1',
            'child_profile_id': 'dragon-knight-male-shield-v1',
            'parent_part': 'body',
            'child_part': 'shield',
            'rule': 'body_shield_relative',
            'status': 'PARTIAL',
            'action_mapping': {
                'total_actions': 104,
                'matching_actions': 96,
                'mismatched_actions': 8,
            },
            'anchor_rule': {
                'mode': 'body_shield_relative',
                'parent_anchor_index': None,
                'child_anchor_index': None,
            },
            'layer_order': ['body', 'shield'],
            'compatibility': {
                'static_structure': 'VERIFIED',
                'preview_composition': 'PARTIAL',
                'compilation': 'PARTIAL',
                'independent_rust': 'VERIFIED',
                'native_korangar': 'UNVERIFIED',
            },
            'evidence': [EVIDENCE_KORANGAR_LOADER],
            'constraints': [
                'Shield attachment with 448 motions vs 456 body motions.',
                'Group 3 (Pickup, slots 24..31) has 2 frames in shield vs 3 frames in body.',
                'Partial compatibility: Pickup slots require explicit mapping or exclusion.',
            ],
        },
        {
            'id': 'novice-male-body-v1+falcon-companion-v1',
            'parent_profile_id': 'novice-male-body-v1',
            'child_profile_id': 'falcon-companion-v1',
            'parent_part': 'body',
            'child_part': 'companion',
            'rule': 'standalone_unattached',
            'status': 'UNSUPPORTED',
            'action_mapping': {
                'total_actions': 104,
                'matching_actions': 0,
                'mismatched_actions': 104,
            },
            'anchor_rule': {
                'mode': 'standalone_unattached',
                'parent_anchor_index': None,
                'child_anchor_index': None,
            },
            'layer_order': ['body', 'companion'],
            'compatibility': {
                'static_structure': 'UNSUPPORTED',
                'preview_composition': 'UNSUPPORTED',
                'compilation': 'UNSUPPORTED',
                'independent_rust': 'VERIFIED',
                'native_korangar': 'UNVERIFIED',
            },
            'evidence': [EVIDENCE_KORANGAR_LOADER],
            'constraints': [
                'Companion entity is standalone (16 slots); cannot attach as equipment layer to player body.',
            ],
        },
    ]


@dataclass(frozen=True)
class CompatibilityRegistry:
    """Immutable, versioned container of compatibility profiles."""
    _bytes: bytes

    def to_dict(self) -> dict:
        return json.loads(self._bytes)

    @property
    def id(self) -> str:
        return self.to_dict()['id']

    @property
    def version(self) -> str:
        return self.to_dict()['version']

    @property
    def canonical_sha256(self) -> str:
        return self.to_dict()['canonical_sha256']

    def canonical_bytes(self) -> bytes:
        return self._bytes

    def list_profile_ids(self) -> list[str]:
        return [p['id'] for p in self.to_dict()['profiles']]

    def get_profile(self, profile_id: str) -> dict:
        for p in self.to_dict()['profiles']:
            if p['id'] == profile_id:
                return p
        raise ForgeError(ErrorCode.INVALID_INPUT, f'Unknown profile ID: {profile_id}.', path='/profiles')

    def has_profile(self, profile_id: str) -> bool:
        return any(p['id'] == profile_id for p in self.to_dict()['profiles'])

    def list_attachment_pairings(self) -> list[dict]:
        return self.to_dict().get('attachment_pairings', [])

    def get_attachment_pairing(self, pairing_id: str) -> dict:
        for p in self.list_attachment_pairings():
            if p['id'] == pairing_id:
                return p
        raise ForgeError(ErrorCode.INVALID_INPUT, f'Unknown attachment pairing ID: {pairing_id}.', path='/attachment_pairings')

    def find_pairings_for_parent(self, parent_profile_id: str) -> list[dict]:
        return [p for p in self.list_attachment_pairings() if p['parent_profile_id'] == parent_profile_id]

    def find_pairings_for_child(self, child_profile_id: str) -> list[dict]:
        return [p for p in self.list_attachment_pairings() if p['child_profile_id'] == child_profile_id]

    def find_pairing(self, parent_profile_id: str, child_profile_id: str) -> dict | None:
        for p in self.list_attachment_pairings():
            if p['parent_profile_id'] == parent_profile_id and p['child_profile_id'] == child_profile_id:
                return p
        return None

    def get_cosmetic_pairing(self, pairing_id: str) -> dict:
        for pairing in self.to_dict().get('cosmetic_pairings', []):
            if pairing['id'] == pairing_id:
                return pairing
        raise ForgeError(ErrorCode.INVALID_INPUT, f'UNKNOWN_COSTUME_PAIRING: {pairing_id}.')


def create_registry(
    profiles: list[dict],
    *,
    id: str = 'ro-sprite-forge-compatibility-registry',
    version: str = '1.0.0',
    attachment_pairings: list[dict] | None = None,
    cosmetic_pairings: list[dict] | None = None,
    offline_actions: list[dict] | None = None,
) -> CompatibilityRegistry:
    """Create a deterministically sealed CompatibilityRegistry from a list of profile records."""
    # Deterministic sorting by profile ID
    sorted_profiles = sorted(profiles, key=lambda p: p['id'])
    payload: dict[str, Any] = {
        'schema': REGISTRY_SCHEMA,
        'id': id,
        'version': version,
        'profiles': sorted_profiles,
    }
    if attachment_pairings is not None:
        payload['attachment_pairings'] = sorted(attachment_pairings, key=lambda p: p['id'])
    if cosmetic_pairings is not None:
        payload['cosmetic_pairings'] = sorted(cosmetic_pairings, key=lambda p: p['id'])

    if offline_actions is not None:
        payload['offline_actions'] = sorted(offline_actions, key=lambda p: p['id'])

    sealed_payload = sealed(payload)
    validate_registry(sealed_payload)
    return CompatibilityRegistry(canonical_bytes(sealed_payload))


def load_registry(value: dict | str | bytes) -> CompatibilityRegistry:
    """Load and validate a CompatibilityRegistry from a dictionary, JSON string, or bytes."""
    if isinstance(value, (str, bytes)):
        parsed = json.loads(value)
    elif isinstance(value, dict):
        parsed = deepcopy(value)
    else:
        raise ForgeError(ErrorCode.INVALID_INPUT, 'Expected registry dict, JSON string or bytes.')
    validated = validate_registry(parsed)
    return CompatibilityRegistry(canonical_bytes(validated))


def get_default_registry() -> CompatibilityRegistry:
    """Construct the standard baseline compatibility registry containing audited and synthetic profiles."""
    profiles = [
        _novice_male_body_profile(),
        _novice_male_head_profile(),
        _orc_skeleton_profile(),
        _genetic_female_body_profile(),
        _dragon_knight_male_shield_profile(),
        _falcon_companion_profile(),
        _synthetic_swordsman_profile(),
        _jack_head_male_profile(),
    ]
    return create_registry(profiles, attachment_pairings=_default_attachment_pairings())
