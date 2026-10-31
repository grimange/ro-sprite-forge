"""RSF-35 offline action and registry extension: Draft 2020-12 and core checks."""
from pathlib import Path
import sys
sys.path[:0]=[str(Path(__file__).resolve().parents[1]/'src'),str(Path(__file__).resolve().parents[1]/'tests')]
from copy import deepcopy
from jsonschema import Draft202012Validator
from ro_sprite_forge.core.contracts import contract_schema, load_target
from ro_sprite_forge.core.registry import create_registry
from ro_sprite_forge.core.errors import ForgeError
from test_custom_actions import fixture, CustomRegistryTests

a,p,t,*_=fixture()
schema=contract_schema('rsf.target/v2');Draft202012Validator.check_schema(schema)
v=Draft202012Validator(schema);v.validate(t.to_dict())
invalid=0
for key,value in [('runtime_slot',104),('native_verification','VERIFIED'),('compilation','APPEND_SLOT')]:
    doc=deepcopy(t.to_dict());doc.pop('canonical_sha256');next(x for x in doc['actions'] if 'offline' in x)['offline'][key]=value
    assert list(v.iter_errors(doc))
    try:load_target(doc,actor=a,profile=p)
    except ForgeError:invalid+=1
    else:raise AssertionError('Core accepted invalid offline action')
r,e,*_=CustomRegistryTests().entry();doc=r.to_dict()
r=create_registry(doc['profiles'],offline_actions=[e]);rs=contract_schema('rsf.compatibility-registry/v1')
Draft202012Validator.check_schema(rs);Draft202012Validator(rs).validate(r.to_dict())
print(f'CUSTOM_ACTION_SCHEMA_PASS schemas=2 valid=2 invalid={invalid}')
