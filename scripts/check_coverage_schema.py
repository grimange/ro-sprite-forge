"""Offline Draft 2020-12 conformance checks for the RSF-10 coverage report schema."""
import copy
from pathlib import Path
import sys

sys.path[:0] = [
    str(Path(__file__).resolve().parents[1] / 'src'),
    str(Path(__file__).resolve().parents[1] / 'tests'),
]
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.coverage import coverage_schema, evaluate_coverage
from ro_sprite_forge.core.errors import ForgeError
from test_ledger import example_requirements, document, source, assignment, operation


def main():
    schema = coverage_schema()
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)

    r = example_requirements()
    d = document(r)
    d['sources'] = [source()]
    d['assignments'] = [assignment(r)]

    cov_empty = evaluate_coverage(r)
    cov_assigned = evaluate_coverage(r, d, source_bytes={'art-a': b'some-test-bytes'})

    positive = [cov_empty, cov_assigned]
    for x in positive:
        v.validate(x)

    bad = []
    # Test invalid schema string
    b1 = copy.deepcopy(cov_empty)
    b1['schema'] = 'rsf.coverage-report/v2'
    bad.append(b1)

    # Test invalid canonical_sha256 (not 64 hex chars)
    b2 = copy.deepcopy(cov_empty)
    b2['canonical_sha256'] = 'invalid'
    bad.append(b2)

    # Test missing required field in counts
    b3 = copy.deepcopy(cov_empty)
    del b3['counts']['structural']['required_slots']
    bad.append(b3)

    # Test invalid status enum
    b4 = copy.deepcopy(cov_empty)
    b4['status']['completeness'] = 'TOTALLY_COMPLETE'
    bad.append(b4)

    # Test negative count integer
    b5 = copy.deepcopy(cov_empty)
    b5['counts']['assignments']['direct'] = -1
    bad.append(b5)

    # Test unknown extra property (schema has additionalProperties: false)
    b6 = copy.deepcopy(cov_empty)
    b6['unknown_prop'] = 123
    bad.append(b6)

    # Test invalid work order item category
    b7 = copy.deepcopy(cov_empty)
    if b7['unresolved_items']:
        b7['unresolved_items'][0]['category'] = 'INVALID_CATEGORY'
        bad.append(b7)

    # Test invalid runtime support
    b8 = copy.deepcopy(cov_empty)
    if b8['unresolved_items']:
        b8['unresolved_items'][0]['runtime_support'] = 'MAGIC_SUPPORT'
        bad.append(b8)

    for b in bad:
        errors = list(v.iter_errors(b))
        assert errors, f"Validator accepted invalid document: {b}"

    print(f'COVERAGE_SCHEMA_PASS schemas=1 valid={len(positive)} invalid={len(bad)}')


if __name__ == '__main__':
    main()
