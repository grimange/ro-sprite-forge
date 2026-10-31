"""Offline Draft 2020-12 checks for timeline/inspection contracts."""
import copy
import json
from pathlib import Path
import sys
sys.path[:0] = [str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1]/'tests')]
from importlib.resources import files
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.animation import inspection_schema
from test_animation import inspector


def main():
    inspection = inspection_schema()
    selection = json.loads(files('ro_sprite_forge').joinpath('schemas/timeline-selection-v1.json').read_text())
    for schema in (inspection,selection):
        Draft202012Validator.check_schema(schema)
    v=Draft202012Validator(inspection); s=Draft202012Validator(selection)
    e=inspector(category='monster')
    walk=e.timeline.select(action='Walk')
    results=[walk,e.timeline.step(walk,1),e.timeline.seek(walk,160,movement_speed=150),
             e.timeline.seek(walk,160),e.timeline.seek(walk,160,diagnostic_frame_ms=40),
             e.timeline.seek(e.timeline.select(action='Die'),500),
             e.timeline.seek(e.timeline.select(action='Attack1'),1000,duration_ms=1000)]
    for result in results:
        s.validate(result)
        v.validate(e.inspect(result)['report'])
    original=e.inspect(walk)['report']
    negative=[]
    for key,value in [('schema','rsf.animation-inspection/v99'),('review','APPROVED'),('unexpected',True)]:
        bad=copy.deepcopy(original); bad[key]=value; negative.append(bad)
    for key,value in [('clipping','MISSING'),('transformed_bounds',[0,0])]:
        bad=copy.deepcopy(original); bad['layers'][0]['geometry'][key]=value; negative.append(bad)
    bad=copy.deepcopy(original);del bad['sources']['body_act'];negative.append(bad)
    for bad in negative:
        assert list(v.iter_errors(bad)), 'Malformed report accepted'
    print(f'ANIMATION_SCHEMA_PASS schemas=2 valid={len(results)*2} invalid={len(negative)}')


if __name__=='__main__': main()
