"""Reproduce public synthetic evidence; no private resources or writes outside OUT."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'src'),str(ROOT/'tests')]
from test_appearance import synthetic_case
from ro_sprite_forge.core.appearance import REPRESENTATIONS,evaluate_appearance,preview_appearance
from ro_sprite_forge.core.canonical import canonical_bytes,digest

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('output',type=Path)
args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
results={}
for representation in REPRESENTATIONS:
    runs=[]
    for _ in range(2):
        reg,req,data=synthetic_case(representation=representation)
        report=evaluate_appearance(reg,'outfit-x',requirements=req,resources=data,character_id='C',gameplay_job='J')
        preview=preview_appearance(reg,'outfit-x',requirements=req,resources=data,character_id='C',
                                   gameplay_job='J',action='Walk',view=0,frame=0,canvas_size=(8,8),origin=(2,2))
        runs.append((reg.canonical_bytes(),canonical_bytes(report),canonical_bytes(preview['report']),preview['png_bytes']))
    assert runs[0]==runs[1]
    paths=[]
    for suffix,blob in zip(('registry.json','compatibility.json','preview.json','png'),runs[0]):
        path=args.output/f'{representation}.{suffix}';path.write_bytes(blob)
        paths.append(dict(file=path.name,sha256=digest(blob),bytes=len(blob)))
    results[representation]=dict(repetitions=2,mismatches=0,artifacts=paths,
        original_sources={pid:[digest(b) for b in pair] for pid,pair in sorted(data.items())})
(args.output/'determinism.json').write_bytes(canonical_bytes(results))
print('PUBLIC_SYNTHETIC_REPRODUCTION_PASS',digest(canonical_bytes(results)))
