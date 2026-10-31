"""Reproduce synthetic RSF-28 provenance/byte comparisons in a fresh output directory."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys

REPO = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO/'src'), str(REPO/'tests')]
from test_video import make_media
from PIL import Image
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.project import create_project, load_project, get_blob
from ro_sprite_forge.adapters.video import capabilities


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    fixtures = out/'fixtures'; fixtures.mkdir()
    expected, generated = make_media(fixtures)
    commands = [dict(argv=c, exit_code=0) for c in generated]
    (out/'capabilities.json').write_bytes(canonical_bytes(capabilities()))
    env = dict(os.environ, PYTHONPATH=str(REPO/'src'))
    def run(arguments, report):
        command = [sys.executable,'-m','ro_sprite_forge',*arguments]
        result = subprocess.run(command,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=180)
        commands.append(dict(argv=command,exit_code=result.returncode,stdout_sha256=digest(result.stdout),stderr_sha256=digest(result.stderr)))
        (out/report).write_bytes(result.stdout)
        (out/(report+'.stderr')).write_bytes(result.stderr)
        result.check_returncode()
        return json.loads(result.stdout)
    source = fixtures/'vfr.mkv'
    first = run(['video-extract','--video',str(source),'--pts','300','--pts','0','--pts','120','--output-dir',str(out/'first')],'first.json')
    second = run(['video-extract','--video',str(source),'--pts','300','--pts','0','--pts','120','--output-dir',str(out/'second')],'second.json')
    assert first==second
    for a in (out/'first').iterdir():
        assert a.read_bytes()==(out/'second'/a.name).read_bytes()
    for i,n in enumerate((4,0,2)):
        with Image.open(out/'first'/f'candidate-{i:04d}.png') as im:
            assert im.tobytes()==expected[n]
    assert [f['pts'] for f in first['inspection']['frames']]==[0,40,120,160,300]
    create_project(out/'projects','media','Synthetic media','synthetic','player')
    staged=run(['video-stage','--video',str(source),'--pts','300','--pts','0','--pts','120',
                '--projects-dir',str(out/'projects'),'--project-id','media','--expected-revision','1'],'staged.json')
    assert load_project(out/'projects','media')==staged
    assert get_blob(out/'projects','media',digest(source.read_bytes()))==source.read_bytes()
    assert staged['video_imports']==[first]
    assert not staged.get('reviews') and not staged.get('ledger')
    result=dict(source_sha256=digest(source.read_bytes()),source_size=source.stat().st_size,
                extraction_sha256=first['canonical_sha256'],frame_png_sha256=[i['png_sha256'] for i in first['items']],
                expected_rgba_sha256=[digest(expected[n]) for n in (4,0,2)],pts=[300,0,120],time_base=first['inspection']['time_base'],
                repeat_manifest_equal=True,repeat_png_bytes_equal=True,pixel_mismatches=0,classification='UNVERIFIED_CANDIDATES',
                python=sys.version,commands=commands)
    (out/'results.json').write_bytes(canonical_bytes(result))
    print(json.dumps(result,indent=2))

if __name__=='__main__': main()
