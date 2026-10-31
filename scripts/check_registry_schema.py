"""Offline Draft 2020-12 conformance checks for RSF-32 compatibility registry schema."""

from copy import deepcopy
from pathlib import Path
import sys

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / 'src'),
    str(Path(__file__).resolve().parents[1] / 'tests'),
]

from jsonschema import Draft202012Validator
from ro_sprite_forge.core.contracts import contract_schema
from ro_sprite_forge.core.errors import ForgeError
from test_appearance import synthetic_case, reseal
from ro_sprite_forge.core.registry import (
    REGISTRY_SCHEMA,
    get_default_registry,
    load_registry,
    validate_registry,
)


def main():
    schema = contract_schema(REGISTRY_SCHEMA)
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)

    reg = get_default_registry()
    d = reg.to_dict()
    cosmetic = synthetic_case()[0].to_dict()
    positive = [d, cosmetic]

    # Validate all positive documents
    for doc in positive:
        validator.validate(doc)
        validate_registry(doc)

    bad = []
    # Invalid schema version
    b = deepcopy(d)
    b['schema'] = 'rsf.compatibility-registry/v2'
    bad.append(b)

    # Missing required id
    b = deepcopy(d)
    del b['id']
    bad.append(b)

    # Malformed version
    b = deepcopy(d)
    b['version'] = '0.0.0'
    bad.append(b)

    # Unknown field
    b = deepcopy(d)
    b['unknown_extra_field'] = 123
    bad.append(b)

    # Duplicate profile ID
    b = deepcopy(d)
    b['profiles'].append(deepcopy(b['profiles'][0]))
    bad.append(b)

    # Invalid profile format version
    b = deepcopy(d)
    b['profiles'][0]['formats']['act_version'] = '2.5'
    bad.append(b)

    # Malformed source hash
    b = deepcopy(d)
    b['profiles'][0]['source_hashes']['act_sha256'] = 'invalid_hash_string'
    bad.append(b)

    # Unknown compatibility status
    b = deepcopy(d)
    b['profiles'][0]['compatibility']['format_decoding'] = 'TOTALLY_VALID'
    bad.append(b)

    # Duplicate attachment pairing ID
    b = deepcopy(d)
    if 'attachment_pairings' in b and b['attachment_pairings']:
        b['attachment_pairings'].append(deepcopy(b['attachment_pairings'][0]))
        bad.append(b)

    # Unknown parent profile ID in pairing
    b = deepcopy(d)
    if 'attachment_pairings' in b and b['attachment_pairings']:
        b['attachment_pairings'][0]['parent_profile_id'] = 'nonexistent-profile-id'
        bad.append(b)

    # Invalid pairing status
    b = deepcopy(d)
    if 'attachment_pairings' in b and b['attachment_pairings']:
        b['attachment_pairings'][0]['status'] = 'TOTALLY_SUPPORTED'
        bad.append(b)

    # Invalid anchor rule mode
    b = deepcopy(d)
    if 'attachment_pairings' in b and b['attachment_pairings']:
        b['attachment_pairings'][0]['anchor_rule']['mode'] = 'magical_teleportation'
        bad.append(b)

    for key,value in [('representation','UNIVERSAL_COSTUME'),('appearance_part','missing'),
                      ('attachment_pairing_sha256','0'*64),('native_korangar','VERIFIED')]:
        b=deepcopy(cosmetic);b['cosmetic_pairings'][0][key]=value
        b['cosmetic_pairings'][0]=reseal(b['cosmetic_pairings'][0]);bad.append(reseal(b))
    b=deepcopy(cosmetic);b['cosmetic_pairings'][0]['action_views'][0]['view']=8
    b['cosmetic_pairings'][0]=reseal(b['cosmetic_pairings'][0]);bad.append(reseal(b))
    b=deepcopy(cosmetic);b['cosmetic_pairings'][0]['appearance_profile']['version']='9.0.0'
    b['cosmetic_pairings'][0]=reseal(b['cosmetic_pairings'][0]);bad.append(reseal(b))

    for b_doc in bad:
        # Schema validation error or core validation error
        has_schema_err = bool(list(validator.iter_errors(b_doc)))
        try:
            validate_registry(b_doc)
            accepted = True
        except ForgeError:
            accepted = False
        assert has_schema_err or not accepted, f"Invalid doc accepted: {b_doc}"

    print(f'REGISTRY_SCHEMA_PASS schemas=1 valid={len(positive)} invalid={len(bad)}')


if __name__ == '__main__':
    main()
