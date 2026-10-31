"""RSF-7 declarations, separate from immutable inventories and future assignments.

The three bundled JSON Schemas define wire shape. Cross-record checks pin exact
revisions and diagnose underspecified production intent without inventing artwork.
No resource decoding, rendering, file publication or runtime execution occurs here.
"""

from dataclasses import dataclass
from importlib.resources import files
import json
import re
from typing import Literal

from ro_sprite_forge.core.canonical import canonical_bytes, check_seal, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.profiles import get_profile

Category = Literal['player', 'npc', 'monster', 'unverified']
Support = Literal['SUPPORTED', 'UNSUPPORTED', 'UNVERIFIED']
SCHEMAS = {'rsf.actor/v1': 'actor-v1', 'rsf.runtime-profile/v2': 'runtime-profile-v2',
           'rsf.target/v2': 'target-v2', 'rsf.compatibility-registry/v1': 'compatibility-registry-v1'}


def fail(path: str, message: str) -> None:
    raise ForgeError(ErrorCode.INVALID_INPUT, message, path=path or '/')


def require(condition: bool, path: str, message: str) -> None:
    if not condition:
        fail(path, message)


def contract_schema(schema: str) -> dict:
    """Return a fresh packaged Draft 2020-12 schema; no network resolution."""
    require(schema in SCHEMAS, '/schema', 'UNSUPPORTED_SCHEMA_VERSION: explicit migration required.')
    return json.loads(files('ro_sprite_forge').joinpath('schemas', SCHEMAS[schema] + '.json').read_text())


def _shape(value: object, rule: dict, path: str = '') -> None:
    """Validate only the vocabulary used by our three closed, bounded schemas.

    This is not a general JSON Schema service. External validators can consume the
    same packaged schemas; semantic/reference rules below remain mandatory.
    """
    if 'anyOf' in rule:
        for choice in rule['anyOf']:
            try:
                _shape(value, choice, path)
                return
            except ForgeError:
                pass
        fail(path, 'Value does not match an allowed declaration shape.')
    if 'const' in rule:
        require(type(value) is type(rule['const']) and value == rule['const'], path, 'Unexpected constant.')
    if 'enum' in rule:
        require(any(type(value) is type(x) and value == x for x in rule['enum']), path, 'Unknown enumerated value.')
    kind = rule.get('type')
    if kind == 'object':
        require(type(value) is dict, path, 'Expected an object.')
        for key in rule['required']:
            require(key in value, path + '/' + key, 'Required field is missing.')
        for key in value:
            require(key in rule['properties'], path + '/' + str(key), 'Unknown field.')
            _shape(value[key], rule['properties'][key], path + '/' + key)
    elif kind == 'array':
        require(type(value) is list, path, 'Expected an array.')
        require(rule['minItems'] <= len(value) <= rule['maxItems'], path, 'Array count outside supported bounds.')
        if rule.get('uniqueItems'):
            require(len({canonical_bytes(x) for x in value}) == len(value), path, 'Duplicate array member.')
        for index, item in enumerate(value):
            _shape(item, rule['items'], path + '/' + str(index))
    elif kind == 'integer':
        require(type(value) is int and rule['minimum'] <= value <= rule['maximum'], path, 'Expected an integer in the supported range.')
    elif kind == 'string':
        require(type(value) is str, path, 'Expected a string.')
        require(rule.get('minLength', 0) <= len(value) <= rule['maxLength'], path, 'String length outside supported bounds.')
        if 'pattern' in rule:
            require(re.fullmatch(rule['pattern'], value) is not None, path, 'Invalid identifier, version or hash.')
    elif kind == 'null':
        require(value is None, path, 'Expected null for unknown data.')


def _unique(values: list, path: str) -> None:
    require(len(set(values)) == len(values), path, 'Duplicate identity.')


def _compatibility(value: dict, path: str) -> None:
    _unique([d['id'] for d in value['declarations']], path + '/declarations')
    for i, declaration in enumerate(value['declarations']):
        require(declaration['status'] == 'UNVERIFIED' or bool(declaration['evidence']),
                f'{path}/declarations/{i}/evidence', 'A support decision requires evidence hashes.')
    if value['status'] != 'UNVERIFIED':
        require(bool(value['declarations']) and all(d['status'] == value['status'] for d in value['declarations']),
                path + '/status', 'Aggregate compatibility must be supported by every declaration.')


@dataclass(frozen=True)
class Contract:
    """Immutable canonical snapshot. Returned dictionaries are independent copies."""
    _bytes: bytes

    def to_dict(self) -> dict:
        return json.loads(self._bytes)

    @property
    def canonical_sha256(self) -> str:
        return self.to_dict()['canonical_sha256']

    @property
    def id(self) -> str:
        return self.to_dict()['id']

    def canonical_bytes(self) -> bytes:
        return self._bytes


@dataclass(frozen=True)
class ActorContract(Contract):
    @property
    def category(self) -> Category:
        return self.to_dict()['category']

    @property
    def revision(self) -> int:
        return self.to_dict()['revision']


@dataclass(frozen=True)
class RuntimeProfileContract(Contract):
    @property
    def category(self) -> Category:
        return self.to_dict()['category']

    @property
    def profile_version(self) -> str:
        return self.to_dict()['profile_version']


@dataclass(frozen=True)
class TargetContract(Contract):
    @property
    def revision(self) -> int:
        return self.to_dict()['revision']


def reference(contract: Contract) -> dict:
    value = contract.to_dict()
    version_key = 'profile_version' if isinstance(contract, RuntimeProfileContract) else 'revision'
    return {'id': value['id'], version_key: value[version_key], 'canonical_sha256': contract.canonical_sha256}


def _payload(value: dict, schema: str) -> dict:
    require(type(value) is dict, '/', 'Expected a contract object.')
    require(value.get('schema') == schema, '/schema', 'UNSUPPORTED_SCHEMA_VERSION: explicit migration required.')
    _shape(value, contract_schema(schema))
    payload = {k: v for k, v in value.items() if k != 'canonical_sha256'}
    if 'canonical_sha256' in value:
        require(value['canonical_sha256'] == digest(canonical_bytes(payload)), '/canonical_sha256', 'Contract digest mismatch.')
    # Copy through canonical JSON: callers cannot mutate an accepted contract.
    return json.loads(canonical_bytes(payload))


def _revision(value: dict, previous: Contract | None) -> None:
    require((value['revision'] == 1) == (value['previous_sha256'] is None), '/previous_sha256',
            'Revision 1 has no predecessor; later revisions must pin the predecessor hash.')
    if previous is not None:
        old = previous.to_dict()
        require(value['id'] == old['id'] and value['schema'] == old['schema'], '/id', 'Revision must retain record identity and schema.')
        require(value['revision'] == old['revision'] + 1, '/revision', 'Revision must increment by exactly one.')
        require(value['previous_sha256'] == previous.canonical_sha256, '/previous_sha256', 'Predecessor digest mismatch.')


def load_actor(value: dict, *, previous: ActorContract | None = None) -> ActorContract:
    v = _payload(value, 'rsf.actor/v1')
    _revision(v, previous)
    _compatibility(v['compatibility'], '/compatibility')
    _unique([r['part'] for r in v['resources']], '/resources')
    for i, resource in enumerate(v['resources']):
        require(resource['part'] in v['parts'], f'/resources/{i}/part', 'Resource part is not declared by the actor.')
    return ActorContract(canonical_bytes(sealed(v)))


def load_runtime_profile(value: dict, *, previous: RuntimeProfileContract | None = None) -> RuntimeProfileContract:
    v = _payload(value, 'rsf.runtime-profile/v2')
    if previous is not None:
        old = previous.to_dict()
        require(v['id'] == old['id'], '/id', 'Profile revisions must retain profile identity.')
        require(tuple(map(int, v['profile_version'].split('.'))) > tuple(map(int, old['profile_version'].split('.'))),
                '/profile_version', 'A changed semantic profile must advance its version.')
    actions, views = v['actions'], v['views']
    _unique([a['id'] for a in actions if a['id'] is not None], '/actions')
    _unique([a['group'] for a in actions if a['group'] is not None], '/actions')
    _unique([s for a in actions for s in a['slots']], '/actions/slots')
    evidence = {e['sha256'] for e in v['source']['evidence']}
    for i, action in enumerate(actions):
        path = f'/actions/{i}'
        require(set(action['evidence']) <= evidence, path + '/evidence', 'Unknown source evidence hash.')
        if action['group'] is None:
            require(not action['slots'], path + '/slots', 'Unmapped action cannot declare numeric slots.')
        else:
            require(action['slots'] == [action['group'] * 8 + view for view in views], path + '/slots',
                    'Numeric slots must match the ordered group/view mapping.')
        if action['mapping'] == 'SUPPORTED':
            require(action['id'] is not None and action['group'] is not None and bool(views), path, 'Supported mapping needs semantic identity, group and views.')
        if action['id'] is None:
            require(action['mapping'] == action['reachability'] == 'UNVERIFIED', path, 'Unknown semantics must remain UNVERIFIED.')
        if action['mapping'] == 'UNSUPPORTED':
            require(action['group'] is None, path + '/group', 'Unsupported action cannot claim a mapped group.')
        if action['mapping'] != 'UNVERIFIED' or action['reachability'] != 'UNVERIFIED':
            require(bool(v['source']['revision']) and bool(action['evidence']), path + '/evidence', 'Runtime support/reachability decision requires pinned source evidence.')
            require(v['category'] != 'unverified', path, 'An unclassified runtime profile cannot claim verified semantics.')
        if action['reachability'] == 'SUPPORTED':
            require(action['mapping'] == 'SUPPORTED', path + '/reachability', 'Reachable action needs a supported mapping.')
    if any(a['mapping'] == 'SUPPORTED' for a in actions):
        require(v['resolution'] is not None, '/resolution', 'Supported mappings require declared selection rules.')
    if v['timing'] is not None:
        semantic_ids = {a['id'] for a in actions if a['id'] is not None}
        looping = set(v['timing']['looping'])
        for mode in ('looping', 'nonlooping'):
            for i, action_id in enumerate(v['timing'][mode]):
                path = f'/timing/{mode}/{i}'
                require(action_id in semantic_ids, path, 'Timing references an undefined action identity.')
                require(mode != 'nonlooping' or action_id not in looping, path,
                        'Action cannot be both looping and nonlooping.')
    order = v['parts']['order']
    _compatibility(v['parts']['attachments'], '/parts/attachments')
    _unique([(r['parent'], r['child']) for r in v['parts']['relationships']], '/parts/relationships')
    for i, relation in enumerate(v['parts']['relationships']):
        path = f'/parts/relationships/{i}'
        require(relation['parent'] in order and relation['child'] in order and relation['parent'] != relation['child'], path, 'Unknown or self-referential resource part.')
        require(set(relation['evidence']) <= evidence, path + '/evidence', 'Unknown relationship evidence.')
        if relation['rule'] == 'player_head_anchor_delta':
            require(v['category'] == 'player' and relation['parent'] == 'body' and relation['child'] == 'head', path, 'Player body/head rule is Player-only.')
        if relation['status'] != 'UNVERIFIED':
            require(relation['rule'] != 'unverified' and bool(relation['evidence']) and bool(v['source']['revision']), path, 'Verified relationship requires a known rule and pinned evidence.')
    return RuntimeProfileContract(canonical_bytes(sealed(v)))


def frozen_runtime_profile(category: Category) -> RuntimeProfileContract:
    """Explicit v1→v2 export; legacy records/hashes/occurrence IDs are unchanged.

    Source selection paths are not upgraded to gameplay reachability or native
    evidence. New native evidence remains in its own accepted gate packet.
    """
    old = get_profile(category)
    supported = old['evidence_status'] == 'SOURCE_VERIFIED'
    evidence = [x['sha256'] for x in old['source_evidence']]
    timing = old['timing']
    if timing is not None:
        # Legacy timing describes global client branches, including actions that
        # fall back for NPC/monster. A v2 category profile names only its actions.
        semantic_ids = {a['action'] for a in old['actions']}
        timing = {key: [a for a in value if a in semantic_ids] if key in ('looping', 'nonlooping') else value
                  for key, value in timing.items()}
    relationships = []
    if category == 'player':
        relationships = [{'parent': 'body', 'child': 'head', 'rule': 'player_head_anchor_delta',
                          'status': 'SUPPORTED', 'evidence': [evidence[1]]}]
    return load_runtime_profile({
        'schema': 'rsf.runtime-profile/v2', 'id': old['id'], 'profile_version': '1.0.0',
        'category': category, 'source': {'repository': 'https://github.com/vE5li/korangar' if supported else None,
                                       'revision': old['revision'], 'evidence': old['source_evidence']},
        'legacy_profile_sha256': old['canonical_sha256'],
        'actions': [{'id': a['action'], 'group': a['group'], 'slots': [a['group'] * 8 + view for view in old['views']],
                     'mapping': 'SUPPORTED', 'reachability': 'UNVERIFIED', 'evidence': [evidence[0]]} for a in old['actions']],
        'views': old['views'], 'resolution': old['resolution'], 'timing': timing,
        'parts': {'order': old['parts']['order'] if old['parts'] else [], 'relationships': relationships,
                  'attachments': {'status': 'UNVERIFIED', 'declarations': []}}})


def _match(value: dict, contract: Contract, path: str) -> None:
    require(value == reference(contract), path, 'Reference identity, version or digest mismatch.')


def load_target(value: dict, *, actor: ActorContract, profile: RuntimeProfileContract,
                previous: TargetContract | None = None) -> TargetContract:
    v = _payload(value, 'rsf.target/v2')
    _revision(v, previous)
    _match(v['actor'], actor, '/actor')
    _match(v['runtime_profile'], profile, '/runtime_profile')
    av, pv = actor.to_dict(), profile.to_dict()
    _match(av['runtime_profile'], profile, '/actor/runtime_profile')
    require(av['category'] == pv['category'], '/actor/category', 'Actor and runtime categories differ.')
    require(set(v['parts']) <= set(av['parts']), '/parts', 'Target references an undeclared actor part.')
    _compatibility(v['compatibility'], '/compatibility')
    _unique([a['id'] for a in v['actions']], '/actions')
    require(any(a['requirement'] != 'OUT_OF_SCOPE' for a in v['actions']), '/actions', 'Declare at least one in-scope action.')
    frames = layers = 0
    for i, action in enumerate(v['actions']):
        path = f'/actions/{i}'
        if 'offline' in action:
            require(type(action['offline']['timing']['loop']) is bool, path + '/offline/timing/loop', 'Expected boolean loop policy.')
            require(action['id'] not in {a['id'] for a in pv['actions']}, path + '/id',
                    'CONFLICTING_NATIVE_ACTION_BINDING: offline IDs cannot replace profile actions.')
            if action['offline']['compilation'] == 'BOUND_EXISTING_SLOT_DIAGNOSTIC':
                require(bool(action['parts']) and all(p['views'] and all(
                    w['topology'] is not None and w['topology']['kind'] == 'inherited'
                    for w in p['views']) for p in action['parts']), path + '/offline/compilation',
                    'UNBOUND_DIAGNOSTIC_COMPOSITION: explicit hash-bound inherited storage required.')
        _unique([p['part'] for p in action['parts']], path + '/parts')
        if action['requirement'] == 'OUT_OF_SCOPE':
            require(not action['parts'], path + '/parts', 'Excluded action cannot declare production work.')
        for j, part in enumerate(action['parts']):
            pp = f'{path}/parts/{j}'
            require(part['part'] in v['parts'], pp + '/part', 'Action references an undeclared target part.')
            _unique([w['view'] for w in part['views']], pp + '/views')
            for k, view in enumerate(part['views']):
                vp = f'{pp}/views/{k}'
                require(not pv['views'] or view['view'] in pv['views'], vp + '/view', 'View is absent from the selected runtime profile.')
                count, topology = view['frame_count'], view['topology']
                frames += count or 0
                if topology is not None:
                    if topology['kind'] == 'explicit':
                        layers += (count or 0) * len(topology['layers'])
                    elif topology['kind'] == 'per_frame':
                        require(count is None or len(topology['frames']) == count, vp + '/topology/frames', 'Topology length differs from declared frame count.')
                        layers += sum(map(len, topology['frames']))
                    elif topology['kind'] == 'template':
                        require(topology['template_sha256'] == single_layer_template(topology['role'])['template_sha256'],
                                vp + '/topology/template_sha256', 'Template content hash mismatch.')
                        layers += count or 0
                    else:
                        require(any(r['part'] == part['part'] and r['inventory_sha256'] == topology['inventory_sha256'] for r in av['resources']),
                                vp + '/topology/inventory_sha256', 'Inherited topology must pin an associated actor resource.')
    require(frames <= 65536, '/actions', 'Frame declaration budget exceeded.')
    require(layers <= 262144, '/actions', 'Layer declaration budget exceeded.')
    if any('offline' in a for a in v['actions']):
        v['actions'].sort(key=lambda a: a['id'])
        for action in v['actions']:
            action['parts'].sort(key=lambda p: p['part'])
            for part in action['parts']:
                part['views'].sort(key=lambda w: w['view'])
    return TargetContract(canonical_bytes(sealed(v)))


def assess_target(target: TargetContract, *, actor: ActorContract, profile: RuntimeProfileContract,
                  inventories: tuple[dict, ...] = ()) -> dict:
    """Validate references and report contract completeness, never artwork coverage.

    Inherited topology is checked against hash-pinned observations. RSF-8 owns
    generalized occurrence expansion/checklist generation, not this contract API.
    """
    load_target(target.to_dict(), actor=actor, profile=profile)
    tv, av, pv = target.to_dict(), actor.to_dict(), profile.to_dict()
    sources = {}
    for i, observed in enumerate(inventories):
        _inheritance_inventory(observed, f'/inventories/{i}')
        key = observed['canonical_sha256']
        require(key not in sources, f'/inventories/{i}', 'Duplicate inventory identity.')
        sources[key] = observed
    mapping = {a['id']: a for a in pv['actions'] if a['id'] is not None}
    diagnostics, runtime, pairs = [], [], set()
    known_layers = 0

    def diagnostic(code: str, path: str):
        diagnostics.append({'code': code, 'path': path})

    for i, action in enumerate(tv['actions']):
        path = f'/actions/{i}'
        if action['requirement'] == 'OUT_OF_SCOPE':
            continue
        mapped = mapping.get(action['id'])
        if 'offline' in action:
            mapped = dict(mapping='UNSUPPORTED', reachability='UNSUPPORTED', slots=[])
        runtime.append({'action': action['id'], 'mapping': mapped['mapping'] if mapped else 'UNVERIFIED',
                        'reachability': mapped['reachability'] if mapped else 'UNVERIFIED',
                        'slots': mapped['slots'] if mapped and mapped['mapping'] == 'SUPPORTED' else []})
        if not action['parts']:
            diagnostic('UNDERSPECIFIED_FRAME_COUNT', path + '/parts')
            diagnostic('UNDERSPECIFIED_LAYER_TOPOLOGY', path + '/parts')
        for j, part in enumerate(action['parts']):
            pp = f'{path}/parts/{j}'
            if part['part'] not in pv['parts']['order']:
                diagnostic('UNVERIFIED_RESOURCE_PART', pp + '/part')
            if not part['views']:
                diagnostic('UNDERSPECIFIED_FRAME_COUNT', pp + '/views')
                diagnostic('UNDERSPECIFIED_LAYER_TOPOLOGY', pp + '/views')
            for k, view in enumerate(part['views']):
                vp = f'{pp}/views/{k}'
                if action['requirement'] == 'REQUIRED':
                    pairs.add((action['id'], part['part'], view['view']))
                count, topology = view['frame_count'], view['topology']
                if count is None:
                    diagnostic('UNDERSPECIFIED_FRAME_COUNT', vp + '/frame_count')
                if topology is None:
                    diagnostic('UNDERSPECIFIED_LAYER_TOPOLOGY', vp + '/topology')
                elif topology['kind'] == 'explicit':
                    known_layers += (count or 0) * len(topology['layers'])
                elif topology['kind'] == 'per_frame':
                    known_layers += sum(map(len, topology['frames'])) if count is not None else 0
                elif topology['kind'] == 'template':
                    known_layers += count or 0
                else:
                    observed = sources.get(topology['inventory_sha256'])
                    if observed is None:
                        diagnostic('INHERITANCE_SOURCE_UNAVAILABLE', vp + '/topology')
                        continue
                    resource = next(r for r in av['resources'] if r['part'] == part['part'] and r['inventory_sha256'] == topology['inventory_sha256'])
                    require(observed['namespace']['part'] == part['part'], vp + '/topology', 'Inherited resource part mismatch.')
                    require(all(observed['sources'][fmt]['sha256'] == resource[fmt + '_sha256'] for fmt in ('act', 'spr')),
                            vp + '/topology', 'Inherited source byte identity mismatch.')
                    slot = topology['slot']
                    source = next((a for a in observed['actions'] if a['slot'] == slot), None)
                    require(source is not None, vp + '/topology/slot', 'Inherited numeric slot is absent.')
                    if mapped and mapped['mapping'] == 'SUPPORTED':
                        require(slot == mapped['group'] * 8 + view['view'], vp + '/topology/slot', 'Inherited slot conflicts with the verified action/view mapping.')
                    require(count is None or len(source['frames']) == count, vp + '/frame_count', 'Inherited topology frame count mismatch.')
                    if count is not None:
                        known_layers += sum(sum(layer['visible'] for layer in f['layers']) for f in source['frames'])
    require(known_layers <= 262144, '/actions', 'Resolved layer budget exceeded.')
    expected = {(a['id'], part, view) for a in pv['actions'] if a['id'] is not None and a['mapping'] == 'SUPPORTED'
                for part in av['parts'] for view in pv['views']}
    if tv['scope'] == 'full':
        if not expected or any(a['mapping'] != 'SUPPORTED' for a in pv['actions']):
            diagnostic('UNVERIFIED_FULL_PROFILE', '/scope')
        elif not expected <= pairs or set(tv['parts']) != set(av['parts']):
            diagnostic('INCOMPLETE_FULL_PROFILE', '/actions')
    specified = not any(d['code'] != 'UNVERIFIED_RESOURCE_PART' for d in diagnostics)
    return sealed({'schema': 'rsf.target-assessment/v1', 'actor': reference(actor), 'runtime_profile': reference(profile),
                   'target': reference(target), 'diagnostics': diagnostics, 'runtime': runtime,
                   'status': {'declared_scope_specified': specified, 'full_profile_specified': specified and tv['scope'] == 'full',
                              'artwork_coverage': 'UNASSIGNED', 'visual_review': 'UNVERIFIED',
                              'native_evidence': 'UNVERIFIED', 'runtime_compatibility': 'UNVERIFIED'}})


def _inheritance_inventory(observed: dict, path: str) -> None:
    """Validate the bounded observation fields this API consumes, not a new inventory schema."""
    try:
        check_seal(observed, 'rsf.inventory/v1')
    except ForgeError as error:
        fail(path, str(error))
    namespace = observed.get('namespace')
    require(type(namespace) is dict, path + '/namespace', 'Expected inventory namespace.')
    require(type(namespace.get('part')) is str, path + '/namespace/part', 'Expected resource part identity.')
    sources = observed.get('sources')
    require(type(sources) is dict, path + '/sources', 'Expected source identities.')
    for fmt in ('act', 'spr'):
        source = sources.get(fmt)
        require(type(source) is dict, path + '/sources/' + fmt, 'Expected source identity.')
        sha = source.get('sha256')
        require(type(sha) is str and re.fullmatch(r'[0-9a-f]{64}', sha) is not None,
                path + '/sources/' + fmt + '/sha256', 'Expected source SHA-256.')
    actions = observed.get('actions')
    require(type(actions) is list and 0 < len(actions) <= 4096, path + '/actions', 'Invalid action records.')
    slots, frames, layers = set(), 0, 0
    for i, action in enumerate(actions):
        ap = f'{path}/actions/{i}'
        require(type(action) is dict, ap, 'Expected an action record.')
        slot = action.get('slot')
        require(type(slot) is int and 0 <= slot < 4096 and slot not in slots, ap + '/slot', 'Invalid or duplicate action slot.')
        slots.add(slot)
        motions = action.get('frames')
        require(type(motions) is list and len(motions) <= 4096, ap + '/frames', 'Invalid motion records.')
        frames += len(motions)
        require(frames <= 65536, path + '/actions', 'Inherited motion budget exceeded.')
        for j, motion in enumerate(motions):
            mp = f'{ap}/frames/{j}'
            require(type(motion) is dict and type(motion.get('layers')) is list, mp + '/layers', 'Expected ordered layers.')
            require(len(motion['layers']) <= 1024, mp + '/layers', 'Inherited layer count exceeded.')
            layers += len(motion['layers'])
            require(layers <= 262144, path + '/actions', 'Inherited layer budget exceeded.')
            for k, layer in enumerate(motion['layers']):
                require(type(layer) is dict and type(layer.get('visible')) is bool,
                        f'{mp}/layers/{k}/visible', 'Layer visibility must be explicit.')


def single_layer_template(role: str) -> dict:
    """Explicit selection of the immutable single-layer/v1 template for one view.

    The role parameter is part of the hashed template content. Inserting this
    declaration into a target confirms only that exact action/part/view scope.
    """
    require(type(role) is str and re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', role) is not None,
            '/role', 'Invalid layer role.')
    content = {'schema': 'rsf.topology-template/v1', 'id': 'single-layer',
               'version': 1, 'layers': [role]}
    return {'kind': 'template', 'id': 'single-layer', 'version': 1, 'role': role,
            'template_sha256': digest(canonical_bytes(content)), 'scope_confirmed': True}
