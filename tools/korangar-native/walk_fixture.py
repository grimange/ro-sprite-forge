"""Reproduce accepted RSF-26 authoring inputs; retain binaries for native execution.

Synthetic test review records are isolated declarations, never real-art approvals.
Private fixture paths/captures remain outside the public repository.
"""
import argparse
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'tests'))
from test_walk_compilation import staged_walk, clean_cli_builds, rust_report, png_pixels
from ro_sprite_forge.core.canonical import canonical_bytes, digest


def prepare(output, private=False):
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    act, spr, manifest, state, expected = staged_walk(output)
    builds = clean_cli_builds(unittest.TestCase(), output, act, spr, manifest, state, expected)
    files = {}
    def mount(name, paths):
        for extension, path in zip(('act','spr'),paths):
            files[f'data\\sprite\\{name}.{extension}'] = dict(path=str(path), sha256=digest(path.read_bytes()))
    mount('original', (output/'clean-1/input.act',output/'clean-1/input.spr'))
    mount('modified', (output/'clean-1/bundle/walk-1.act',output/'clean-1/bundle/walk-1.spr'))
    actors = [dict(id=n,kind='monster',parts=[n],actions=['Walk','Attack','Die','Idle']) for n in ('original','modified')]
    if private:
        sys.path.insert(0,str(ROOT/'tests/private_fixture_hooks'))
        from test_audited_fixtures import find_fixture, AUDITED_HASHES
        for name in ('novice_body','novice_head','orc_skeleton'):
            paths=[find_fixture(name+'_'+ext) for ext in ('act','spr')]
            for ext,p in zip(('act','spr'),paths):
                if p is None or digest(p.read_bytes())!=AUDITED_HASHES[name+'_'+ext]:
                    raise ValueError('PRIVATE_FIXTURE_UNAVAILABLE: '+name+'_'+ext)
            mount(name,paths)
        actors += [dict(id='orc',kind='monster',parts=['orc_skeleton'],actions=['Die','Walk']),
                   dict(id='novice',kind='player',parts=['novice_body','novice_head'],actions=['Walk'])]
    inputs=dict(files=files,walk=dict(actors=actors))
    (output/'inputs.json').write_bytes(canonical_bytes(inputs))
    for name, pair in [('original',(act,spr)),('modified',(builds[0]['act'],builds[0]['spr']))]:
        (output/(name+'-rust.json')).write_bytes(canonical_bytes(rust_report(*pair)))
    expected_rows=[]
    for (slot,frame,layer),raw in sorted(expected.items()):
        w,h,pixels=png_pixels(raw)
        expected_rows.append(dict(slot=slot,frame=frame,raw_layer=layer,width=w,height=h,
            source_png_sha256=digest(raw),decoded_rgba_sha256=digest(pixels)))
    provenance=dict(schema='rsf.native-walk-provenance/v1',
        original=dict(act_sha256=digest(act),spr_sha256=digest(spr)),
        modified=dict(act_sha256=digest(builds[0]['act']),spr_sha256=digest(builds[0]['spr'])),
        build_manifest_path=str(output/'clean-1/bundle/build-manifest.json'),
        source_blobs=[dict(path=str(output/'rsf26-monster/blobs'/h),sha256=h)
                      for h in sorted({r['source_png_sha256'] for r in expected_rows})],
        build_manifest_sha256=digest(builds[0]['build']),build=builds[0]['manifest']['build'],
        target=state['requirements']['target'],replacement_policy='explicit_rgba',
        requirements=state['requirements'],assignments=manifest['ledger'],
        review_events=manifest['review_events'],synthetic_review_only=True,
        expected=expected_rows,export_label='PARTIAL_DIAGNOSTIC',production_authorized=False,
        clean_builds=[dict(act_sha256=digest(b['act']),spr_sha256=digest(b['spr']),
            build_manifest_sha256=digest(b['build']),argv=b['argv'],exit=b['exit']) for b in builds],
        effective_comparison=builds[0]['comparison'])
    (output/'provenance.json').write_bytes(canonical_bytes(provenance))
    print(json.dumps(dict(inputs=str(output/'inputs.json'),provenance_sha256=digest(canonical_bytes(provenance)),
        modified=provenance['modified'],expected=expected_rows),sort_keys=True))
    return inputs,provenance

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('output',type=Path);parser.add_argument('--private',action='store_true')
    args=parser.parse_args();prepare(args.output,args.private)
