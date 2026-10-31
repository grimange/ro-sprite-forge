"""Read-only independent RSF-35 expected-pixel and effective-reference QA probe."""
from pathlib import Path
import sys, tempfile, json, hashlib
sys.path[:0]=[str(Path.cwd()/'src'),str(Path.cwd()/'tests'),str(Path.cwd()/'tools/rust-oracle')]
from test_custom_actions import fixture, bound_fixture, declaration
from test_contracts import actor_document,target_document
from ro_sprite_forge.core.contracts import frozen_runtime_profile,load_actor
from ro_sprite_forge.core.custom_actions import preview_offline_action
from ro_sprite_forge.core.compiler import compile_resources
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.spr import read_spr
from ro_sprite_forge.core.errors import ForgeError
from test_compiler import RUST_ORACLE_BIN, _build_approved_ledger
from parity import compare
sha=lambda x:hashlib.sha256(x).hexdigest()
p=frozen_runtime_profile('player');a=load_actor(actor_document(p))
doc=target_document(a,p,actions=[declaration(topology=dict(kind='explicit',layers=['back','front']))])
a,p,t,r,l,s=fixture(a,p,doc)
# Independently assigned opaque front blue must occlude opaque red back.
l=_build_approved_ledger(r,[dict(requirement_id=row['id'],kind='DIRECT_SOURCE',source=dict(id='art0' if row['ordinal']==0 else 'art2',revision=1)) for row in r['layers']],s)
result=preview_offline_action(t,actor=a,profile=p,ledger=l,source_bytes=s,action_id='Wave',view=0,frame=2,canvas_size=(16,16))
visible=[pixel for pixel in result['image'].getdata() if pixel[3]]
assert len(visible)==16 and set(visible)=={(0,0,255,255)}
print('INDEPENDENT_TWO_LAYER_PIXELS_PASS',len(visible))
for name in ('Guard','Dodge'):
 act,spr,a,p,t,inv,kw=bound_fixture(name)
 before_sources={key:sha(value) for key,value in kw['source_bytes'].items()}
 out=compile_resources(act,spr,**kw)
 aa,bb=read_act(act),read_act(out['act_bytes'])
 ss,tt=read_spr(spr),read_spr(out['spr_bytes'])
 assert len(aa['actions'])==len(bb['actions'])==40
 for field in ('reserved','events','delays'):assert aa[field]==bb[field]
 assert ss.palette==tt.palette
 assert [(im.width,im.height,im.raw_rle) for im in ss.indexed_images]==[(im.width,im.height,im.raw_rle) for im in tt.indexed_images]
 def effective(resource,layer):
  if layer['sprite']<0:return None
  image=(resource.indexed_images if layer['pool']==0 else resource.rgba_images)[layer['sprite']]
  return image.width,image.height,(image.to_rgba(resource.palette) if layer['pool']==0 else image.rgba)
 changed=[];total=0
 for slot,(old,new) in enumerate(zip(aa['actions'],bb['actions'])):
  assert len(old)==len(new)
  for frame,(om,nm) in enumerate(zip(old,new)):
   assert {k:v for k,v in om.items() if k!='clips'}=={k:v for k,v in nm.items() if k!='clips'}
   assert len(om['clips'])==len(nm['clips'])
   for layer,(ol,nl) in enumerate(zip(om['clips'],nm['clips'])):
    total+=1
    assert {k:v for k,v in ol.items() if k not in ('sprite','pool')}=={k:v for k,v in nl.items() if k not in ('sprite','pool')}
    if effective(ss,ol)!=effective(tt,nl):
     changed.append((slot,frame,layer))
     assert effective(tt,nl)==(4,4,bytes((12,34,56,255))*16)
 assert total==49 and changed==[(8,0,0)]
 assert before_sources=={key:sha(value) for key,value in kw['source_bytes'].items()}
 with tempfile.TemporaryDirectory(prefix='rsf35-qa-oracle-') as temp:
  ap=Path(temp)/'candidate.act';sp=Path(temp)/'candidate.spr'
  ap.write_bytes(out['act_bytes']);sp.write_bytes(out['spr_bytes'])
  parity=compare(RUST_ORACLE_BIN.resolve(),ap,sp)
  assert parity['result']=='AGREEMENT' and parity['mismatches']==[]
  print(name,'ORACLE_AGREEMENT',parity['mismatches'])
 try:compile_resources(act,spr,**kw,compilation_mode='production_export')
 except ForgeError as error:
  # Current public mode is verified separately by focused production-gate tests.
  print(name,'PRODUCTION_PROBE',str(error))
 else:raise AssertionError('production accepted')
 print(name,'OCCURRENCES',total,'TARGETED',changed,'UNAFFECTED',total-len(changed),'OUTPUT',sha(out['act_bytes']),sha(out['spr_bytes']))
manifest=json.loads(Path('docs/verification/rsf-35/implementation-paths.json').read_text())
for row in manifest:assert sha(Path(row['path']).read_bytes())==row['sha256']
print('IMPLEMENTATION_HASHES_PASS',len(manifest))
left=Path('/tmp/rsf35-qa-repro');right=Path('/tmp/rsf35-qa-repro-repeat')
assert {p.name:p.read_bytes() for p in left.iterdir() if p.is_file()}=={p.name:p.read_bytes() for p in right.iterdir() if p.is_file()}
print('DIFFERENT_PATH_AND_HASH_SEED_REPRO_BYTE_IDENTITY',len(list(left.iterdir())))
for row in json.loads((left/'compilations.json').read_text()):
 print('CANONICAL',row['action'],row['build_manifest_sha256'],row['build'])
