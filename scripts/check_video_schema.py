"""RSF-28 standalone and embedded candidate contracts, offline schema checks."""
import copy
import json
from importlib.resources import files
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.project import project_schema


def main():
    candidate=json.loads(files('ro_sprite_forge').joinpath('schemas/video-candidates-v1.json').read_text())
    project=project_schema()
    for schema in (candidate,project): Draft202012Validator.check_schema(schema)
    assert project['properties']['video_imports']['items']=={k:v for k,v in candidate.items() if k not in ('$id','$schema')}
    validator=Draft202012Validator(candidate)
    # Presence and closed enums, including no automatic approval/assignment.
    for record in ({},{'schema':'rsf.video-candidates/v1','automatic_assignment':True},
                   {'visual_review':'APPROVED'},{'unexpected':1}):
        assert list(validator.iter_errors(record))
    print('VIDEO_SCHEMA_PASS: standalone and embedded closed contract; actual generated records validated by test_video')

if __name__=='__main__': main()
