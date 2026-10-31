"""Reproduce RSF-26 evidence without writing private artwork or touching originals.

Usage: .venv/bin/python docs/verification/rsf-26/reproduce.py --output-dir /tmp/rsf26-recheck
The output includes synthetic declarations/reviews and private hashes/metadata only.
"""
import argparse
import json
from pathlib import Path
import platform
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tests'))
sys.path.insert(0,str(ROOT/'tests/private_fixture_hooks'))
from test_walk_compilation import staged_walk,clean_cli_builds,rust_report
from test_walk_compilation_fixtures import private_regression
from ro_sprite_forge.core.canonical import canonical_bytes,digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    out=parser.parse_args().output_dir
    out.mkdir(parents=True,exist_ok=True)
    def save(name,value): (out/name).write_bytes(canonical_bytes(value))
    case=unittest.TestCase()
    with tempfile.TemporaryDirectory(prefix='rsf26-reproduce-') as tmp:
        act,spr,manifest,state,expected=staged_walk(tmp)
        results=clean_cli_builds(case,tmp,act,spr,manifest,state,expected)
        save('synthetic-snapshot.json',dict(project=manifest,requirements=state['requirements'],
            ledger=state['ledger'],reviews=state['reviews'],coverage=state.get('coverage'),
            original_sha256=dict(act=digest(act),spr=digest(spr)),
            staged_sources=[dict(location=list(loc),png_sha256=digest(raw)) for loc,raw in sorted(expected.items())]))
        save('golden-build.json',json.loads(results[0]['build']))
        save('golden-compilation.json',results[0]['manifest'])
        save('synthetic-effective-mapping.json',results[0]['comparison'])
        runs=[]
        for r in results:
            runs.append(dict(argv=r['argv'],exit_code=r['exit'],act_sha256=digest(r['act']),
                spr_sha256=digest(r['spr']),build_sha256=digest(r['build']),
                rust_report_sha256=digest(canonical_bytes(rust_report(r['act'],r['spr'])))))
        save('clean-builds.json',dict(python=sys.version,platform=platform.platform(),runs=runs,
            independent_processes=2,binaries_equal=True,canonical_build_equal=True,effective_mapping_equal=True,
            original_rust_report_sha256=digest(canonical_bytes(rust_report(act,spr))),native_korangar='UNVERIFIED'))
    private=[]
    for name in ('novice','orc'):
        try:
            result=private_regression(case,name)
            save(name+'-regression.json',result)
            private.append(dict(fixture=name,result='PASS',targeted=result['comparison']['targeted'],
                unaffected=result['comparison']['unaffected'],frames=result['comparison']['frames'],
                unaffected_slots=result['unaffected_slots'],outputs=result['outputs']))
        except unittest.SkipTest as exc: private.append(dict(fixture=name,result='NOT_RUN',reason=str(exc)))
    save('private-summary.json',private)
    print(json.dumps(dict(clean_builds=runs,private=private),indent=2))


if __name__=='__main__': main()
