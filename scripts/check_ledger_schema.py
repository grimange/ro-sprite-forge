"""Offline Draft 2020-12 conformance checks for the RSF-9 declaration contract."""
import copy
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1]/'tests')]
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.ledger import ledger_schema, load_ledger
from ro_sprite_forge.core.errors import ForgeError
from test_ledger import example_requirements, document, source, assignment, operation


def main():
    schema=ledger_schema();Draft202012Validator.check_schema(schema);v=Draft202012Validator(schema)
    r=example_requirements();d=document(r);d['sources']=[source()];d['assignments']=[assignment(r)]
    positive=[d,load_ledger(d,requirements=r).to_dict(),document(r)]
    reused=copy.deepcopy(d);reused['assignments'].append(assignment(r,1,'B','EXPLICIT_REUSE','A',recipe=[operation()]))
    positive.append(reused)
    for x in positive:v.validate(x)
    bad=[]
    for field,value in [('schema','rsf.assignment-ledger/v2'),('revision',0),('id','/tmp/private'),('assignments',{}),('unknown',1)]:
        b=copy.deepcopy(d);b[field]=value;bad.append(b)
    for op in (operation('guess'),operation('crop',x=0,y=0,width=0,height=2),operation('scale',x_num=1,x_den=0,y_num=1,y_den=1)):
        b=copy.deepcopy(d);b['assignments'][0]['recipe']=[op];bad.append(b)
    for b in bad:
        assert list(v.iter_errors(b))
        try:load_ledger(b,requirements=r)
        except ForgeError:pass
        else:raise AssertionError('Core accepted invalid schema shape')
    print(f'LEDGER_SCHEMA_PASS schemas=1 valid={len(positive)} invalid={len(bad)}')

if __name__=='__main__':main()
