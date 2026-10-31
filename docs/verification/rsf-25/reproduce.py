"""Reproduce two clean RSF-25 CLI builds; only synthetic public inputs are used."""
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tests'))
from test_canonical_builds import fixture, RUST_ORACLE_BIN
from ro_sprite_forge.core.canonical import canonical_bytes,digest

out=Path(__file__).resolve().parent
act,spr,kw=fixture()
runs=[]
with tempfile.TemporaryDirectory(prefix='rsf25-clean-') as tmp:
    for number in (1,2):
        cwd=Path(tmp)/f'path-{number}';cwd.mkdir()
        (cwd/'original.act').write_bytes(act);(cwd/'original.spr').write_bytes(spr)
        (cwd/'requirements.json').write_bytes(canonical_bytes(kw['requirements']))
        (cwd/'ledger.json').write_bytes(canonical_bytes(kw['ledger']))
        for sid,raw in kw['source_bytes'].items():(cwd/f'{sid}.png').write_bytes(raw)
        argv=[sys.executable,'-m','ro_sprite_forge','compile','--act','original.act','--spr','original.spr',
              '--requirements','requirements.json','--ledger','ledger.json','--policy','explicit_rgba',
              '--source','art=art.png','--source','other=other.png','--output-dir','bundle',
              '--output-prefix',f'artifact-{number}','--compilation-id',f'clean-build-{number}']
        if number==2:argv+=['--oracle',str(RUST_ORACLE_BIN)]
        proc=subprocess.run(argv,cwd=cwd,env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONHASHSEED=str(number)),capture_output=True,text=True)
        assert proc.returncode==0,proc.stderr
        manifest=json.loads((cwd/'bundle/compilation-manifest.json').read_bytes())
        runs.append(dict(act=(cwd/f'bundle/artifact-{number}.act').read_bytes(),spr=(cwd/f'bundle/artifact-{number}.spr').read_bytes(),
                         build=(cwd/'bundle/build-manifest.json').read_bytes(),manifest=manifest))
        print('EXIT',proc.returncode,'ARGV',argv,'CWD',cwd)
assert all(runs[0][k]==runs[1][k] for k in ('act','spr','build'))
assert runs[0]['manifest']['canonical_sha256']!=runs[1]['manifest']['canonical_sha256']
(out/'golden-build.json').write_bytes(runs[0]['build'])
(out/'golden-compilation.json').write_bytes(canonical_bytes(runs[1]['manifest']))
record=dict(python=sys.version,platform=platform.platform(),input_act=digest(act),input_spr=digest(spr),
            output_act=digest(runs[0]['act']),output_spr=digest(runs[0]['spr']),build_manifest_sha256=digest(runs[0]['build']),
            build_input_sha256=runs[0]['manifest']['build']['input_sha256'],rust_oracle=runs[1]['manifest']['verification']['rust_oracle'],
            native_korangar='UNVERIFIED',independent_clean_builds=2,canonical_build_and_binaries_equal=True,
            invocation_manifests_differ=True)
(out/'environment.json').write_text(json.dumps(record,indent=2)+'\n')
print(json.dumps(record,indent=2))
