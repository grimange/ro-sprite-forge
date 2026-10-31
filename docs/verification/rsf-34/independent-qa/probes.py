import json,hashlib
from pathlib import Path
from copy import deepcopy
from test_appearance import synthetic_case,reseal
from ro_sprite_forge.core.appearance import evaluate_appearance,preview_appearance
from ro_sprite_forge.core.registry import load_registry
from ro_sprite_forge.formats.act import read_act,write_act
from ro_sprite_forge.formats.spr import write_rgba_spr
from ro_sprite_forge.core.canonical import canonical_bytes,digest
from ro_sprite_forge.core.errors import ForgeError
from PIL import Image
from jsonschema import Draft202012Validator
r,q,data=synthetic_case(representation='EQUIPMENT_VISUAL')
d=r.to_dict();p=next(p for p in d['profiles'] if p['id']=='costume-test')
spr=write_rgba_spr([Image.new('RGBA',(1,1),(0,255,0,128))]);data['costume-test']=(data['costume-test'][0],spr)
p['source_hashes']['spr_sha256']=digest(spr);d['profiles']=[reseal(x) for x in d['profiles']]
p=next(p for p in d['profiles'] if p['id']=='costume-test');pair=d['cosmetic_pairings'][0]
pair['appearance_profile']={k:p[k] for k in ('id','version','canonical_sha256')};d['cosmetic_pairings'][0]=reseal(pair);r=load_registry(reseal(d))
Draft202012Validator(json.loads(Path('src/ro_sprite_forge/schemas/compatibility-registry-v1.json').read_text())).validate(r.to_dict())
before=canonical_bytes(q),r.canonical_bytes(),deepcopy(data)
z=preview_appearance(r,'outfit-x',requirements=q,resources=data,character_id='independent-C',gameplay_job='external-UNCHANGED',action='Walk',view=0,frame=1,canvas_size=(5,5),origin=(2,2))
assert z['image'].getpixel((2,2))==(127,128,0,255)
assert z['compatibility']['identity']['gameplay_job']=='external-UNCHANGED'
assert before==(canonical_bytes(q),r.canonical_bytes(),data)
assert z['report']['parts'][0]['source_motion']==read_act(data['body-test'][0])['actions'][8][1]
broken=deepcopy(data);act=read_act(broken['costume-test'][0]);act['actions'][8][1]['clips'][0]['pool']=7
bad=write_act(act);bd=r.to_dict();p=next(p for p in bd['profiles'] if p['id']=='costume-test');p['source_hashes']['act_sha256']=digest(bad)
bd['profiles']=[reseal(x) for x in bd['profiles']];p=next(p for p in bd['profiles'] if p['id']=='costume-test');bd['cosmetic_pairings'][0]['appearance_profile']={k:p[k] for k in ('id','version','canonical_sha256')};bd['cosmetic_pairings'][0]=reseal(bd['cosmetic_pairings'][0]);br=load_registry(reseal(bd));broken['costume-test']=(bad,broken['costume-test'][1])
try:evaluate_appearance(br,'outfit-x',requirements=q,resources=broken,character_id='C')
except ForgeError as e:print('invalid pool rejected:',e)
else:raise AssertionError('invalid pool accepted')
for row in json.loads(Path('docs/verification/rsf-34/implementation-manifest.json').read_text())['changed']:
 assert hashlib.sha256(Path(row['path']).read_bytes()).hexdigest()==row['sha256']
left=Path('docs/verification/rsf-34/synthetic');right=Path('/tmp/rsf34-qa/synthetic')
for a in left.rglob('*'):
 if a.is_file():assert a.read_bytes()==(right/a.relative_to(left)).read_bytes()
print('QA_FRESH_PROBES_PASS: Draft202012 schema, exact alpha/frame1, external identity, immutable inputs, invalid pool, 6 manifest hashes, repeated artifacts')
