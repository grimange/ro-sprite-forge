"""Offline conformance checks for the exact-scope RSF-18 event contract."""
import copy
from pathlib import Path
import sys
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'src')]
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.review import make_event, review_schema, validate_events
from ro_sprite_forge.core.errors import ForgeError


def main():
    schema = review_schema()
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    target = dict(id='synthetic', revision=1, canonical_sha256='0'*64)
    member = dict(requirement_id='synthetic/r1/body/walk/view0/frame0/layer0',
                  basis_sha256='1'*64, evidence_sha256='2'*64)
    valid = [make_event('synthetic', 1, target, decision, [member], 1,
                      'UNCHANGED_REFERENCE_STRUCTURAL_ONLY' if decision=='NOT_REQUIRED' else None)
             for decision in ('APPROVED','REJECTED','NOT_REQUIRED')]
    for event in valid:
        validator.validate(event)
        validate_events([event], 'synthetic')
    invalid = []
    for field,value in [('schema','rsf.review-event/v2'),('decision','AUTO_APPROVED'),
                        ('members',[]),('revision',0),('unknown',True)]:
        event=copy.deepcopy(valid[0]);event[field]=value;invalid.append(event)
    event=copy.deepcopy(valid[0]);event['members'][0]['basis_sha256']='invalid';invalid.append(event)
    for event in invalid:
        assert list(validator.iter_errors(event))
        try: validate_events([event], 'synthetic')
        except ForgeError: pass
        else: raise AssertionError('Malformed event accepted')
    print(f'REVIEW_SCHEMA_PASS schemas=1 valid={len(valid)} invalid={len(invalid)}')

if __name__=='__main__': main()
