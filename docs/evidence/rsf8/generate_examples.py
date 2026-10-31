"""Recompute technical report identities; never publish private binary/pixel data."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests'),str(ROOT/'tests/private_fixture_hooks')]
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import single_layer_template
from test_topology import TopologyTests
from test_topology_fixtures import reference_requirements
from ro_sprite_forge.core.topology import resolve_topology


def summary(result):
    return {'canonical_sha256':result['canonical_sha256'],
            'serialized_sha256':digest(canonical_bytes(result)),
            'counts':result['counts'],'status':result['status'],'diagnostics':result['diagnostics'],
            'target':result['target'],
            'first_frame_id':result['frames'][0]['id'] if result['frames'] else None,
            'first_layer_id':result['layers'][0]['id'] if result['layers'] else None,
            'first_authority':result['layers'][0]['authority'] if result['layers'] else None}


def generate():
    t=TopologyTests();t.setUp()
    output={}
    for name,topology in [('single',{'kind':'explicit','layers':['body']}),
        ('multipart',{'kind':'explicit','layers':['rear','front']}),
        ('mixed',{'kind':'per_frame','frames':[[],['body'],['rear','front'],['body'],[],['a','b','c']]}),
        ('template',single_layer_template('body')),('underspecified',None)]:
        d=t.document(topology)
        r=t.resolve(d)
        assert canonical_bytes(r)==canonical_bytes(t.resolve(d))
        output[name]=summary(r)
    for category,names in [('player',[('body','novice_body'),('head','novice_head')]),
                           ('monster',[('body','orc_skeleton')])]:
        a,p,target,observations=reference_requirements(category,names)
        r=resolve_topology(target,actor=a,profile=p,inventories=tuple(observations))
        assert canonical_bytes(r)==canonical_bytes(resolve_topology(target,actor=a,profile=p,inventories=tuple(reversed(observations))))
        output[category]=summary(r)
        output[category]['inventories']=[{'canonical_sha256':o['canonical_sha256'],
            'namespace':o['namespace'],'sources':o['sources'],'summary':o['summary']} for o in observations]
    return output

if __name__=='__main__':
    (Path(__file__).parent/'examples.json').write_text(json.dumps(generate(),indent=2,sort_keys=True)+'\n')
