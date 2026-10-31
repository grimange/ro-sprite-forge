"""Offline optional RSF-7 JSON Schema conformance check (jsonschema is test-only)."""
from copy import deepcopy
from importlib.metadata import version
from pathlib import Path
import sys

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'src'),
                str(Path(__file__).resolve().parents[1] / 'tests')]
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.contracts import (contract_schema, frozen_runtime_profile, load_actor, load_target, single_layer_template)
from test_contracts import actor_document, target_document


def main():
    validators = {}
    for schema in ('rsf.actor/v1', 'rsf.runtime-profile/v2', 'rsf.target/v2'):
        value = contract_schema(schema)
        Draft202012Validator.check_schema(value)
        validators[schema] = Draft202012Validator(value)
    positive = []
    for category in ('player', 'npc', 'monster', 'unverified'):
        profile = frozen_runtime_profile(category)
        actor = load_actor(actor_document(profile, category=category))
        target = load_target(target_document(actor, profile), actor=actor, profile=profile)
        positive.extend([profile.to_dict(), actor.to_dict(), target.to_dict()])
    doc = target_document(actor, profile)
    doc['actions'][0]['parts'][0]['views'][0]['topology'] = single_layer_template('body')
    positive.append(load_target(doc, actor=actor, profile=profile).to_dict())
    for document in positive:
        validators[document['schema']].validate(document)
    negative = []
    for document in positive:
        missing = deepcopy(document); del missing['id']; negative.append(missing)
        extra = deepcopy(document); extra['unknown_field'] = 1; negative.append(extra)
        invalid_version = deepcopy(document); invalid_version['schema'] += '99'; negative.append(invalid_version)
        invalid_id = deepcopy(document); invalid_id['id'] += '\n'; negative.append(invalid_id)
    for i, document in enumerate(negative):
        schema = positive[i // 4]['schema']
        assert list(validators[schema].iter_errors(document)), document
    for field, value in (('scope_confirmed', False), ('version', 2), ('id', 'other')):
        doc = deepcopy(positive[-1])
        doc['actions'][0]['parts'][0]['views'][0]['topology'][field] = value
        assert list(validators['rsf.target/v2'].iter_errors(doc))
    print(f'JSON_SCHEMA_PASS jsonschema={version("jsonschema")} schemas=3 valid={len(positive)} invalid={len(negative) + 3}')


if __name__ == '__main__':
    main()
