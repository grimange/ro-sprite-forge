"""Reproduce public RSF-9 evidence; only synthetic, non-image bytes are used."""
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / 'src'), str(ROOT / 'tests')]
from test_ledger import example_requirements, source, assignment, document, operation
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger, compare_ledgers


def examples():
    requirements = example_requirements()
    declaration = document(requirements)
    empty = resolve_ledger(load_ledger(declaration, requirements=requirements), requirements=requirements)
    declaration['sources'] = [source(), source('art-d')]
    declaration['assignments'] = [
        assignment(requirements),
        assignment(requirements, 1, 'B', 'EXPLICIT_REUSE', 'A', recipe=[operation()]),
        assignment(requirements, 2, 'C', 'EXPLICIT_REUSE', 'B', recipe=[operation('translate', x=3, y=-2)]),
        assignment(requirements, 3, 'D', sid='art-d')]
    data = {'art-a': b'operator supplied synthetic bytes', 'art-d': b'operator supplied synthetic bytes'}
    ledger = load_ledger(declaration, requirements=requirements)
    def resolve(content):
        return resolve_ledger(ledger, requirements=requirements, source_bytes=content)
    valid = resolve(data)
    missing = resolve({**data, 'art-a': None})
    mismatch = resolve({**data, 'art-a': b'changed bytes'})
    changed = copy.deepcopy(declaration)
    changed['sources'][0].update(sha256=digest(b'new'), revision=2)
    changed['assignments'][0]['source']['revision'] = 2
    changed['assignments'][0]['revision'] = 2
    changed['assignments'][1]['dependency']['revision'] = 2
    changed['assignments'][1]['revision'] = 2
    changed['assignments'][2]['dependency']['revision'] = 2
    changed['assignments'][2]['revision'] = 2
    changed.update(revision=2, previous_sha256=ledger.canonical_sha256)
    revised = load_ledger(changed, requirements=requirements, previous=ledger)
    after = resolve_ledger(revised, requirements=requirements, source_bytes={**data, 'art-a': b'new'})
    return {'synthetic_only': True, 'image_processing': 'NOT_RUN', 'operator_approvals_recorded': 0,
        'requirements': requirements, 'declaration': ledger.to_dict(), 'zero_assignments': empty,
        'resolved': valid, 'missing_source': missing, 'hash_mismatch': mismatch,
        'revised': after, 'impact': compare_ledgers(valid, after)}


if __name__ == '__main__':
    first = canonical_bytes(examples())
    assert first == canonical_bytes(examples()), 'Non-deterministic evidence'
    (Path(__file__).parent / 'examples.json').write_bytes(first)
    value = json.loads(first)
    print(json.dumps({'examples_sha256': digest(first),
        'frames': len(value['requirements']['frames']), 'counts': value['resolved']['counts'],
        'affected': value['impact']['affected_assignments'],
        'unaffected': value['impact']['unaffected_assignments']}, sort_keys=True))
