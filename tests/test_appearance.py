"""RSF-34: independently known pixels, explicit topology and operator decisions."""
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import unittest

from PIL import Image
from ro_sprite_forge.core.appearance import (build_cosmetic_pairing, evaluate_appearance,
    preview_appearance, bind_appearance_requirements, prepare_clothing_composition)
from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.contracts import load_target, load_actor
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.core.registry import (get_default_registry, create_registry, load_registry,
    to_actor_contract, to_runtime_profile_contract)
from ro_sprite_forge.core.topology import resolve_topology
from ro_sprite_forge.core.review import bases, evaluate_reviews, make_event
from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger
from ro_sprite_forge.core.coverage import evaluate_coverage
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.spr import write_rgba_spr
from test_contracts import target_document
from test_ledger import document, source, assignment


def reseal(record):
    return sealed({k:v for k,v in record.items() if k != 'canonical_sha256'})


def fixture_profile(pid, kind, color, *, mismatch=False, anchors=True, layers=1):
    image = Image.new('RGBA',(1,1),color)
    spr = write_rgba_spr([image])
    clip = dict(x=0,y=0,sprite=0,mirror=0,color=0xffffffff,scale_x=1.0,scale_y=1.0,angle=0,pool=1)
    motion = dict(bounds=[0]*8,clips=[dict(clip,x=i) for i in range(layers)],event=-1,
                  anchors=[dict(opaque=0,x=2 if kind=='body' else 1,y=0,attribute=0)] if anchors else [])
    act = write_act(dict(reserved='112233445566778899aa',actions=[
        [deepcopy(motion) for _ in range(1 if mismatch and s==8 else 2)] for s in range(16)],
        events=[],delays=[4.0]*16))
    p = get_default_registry().get_profile('novice-male-body-v1')
    p.update(id=pid, resource_kind=kind, gameplay_job='original-job' if kind=='body' else None)
    p['visual']['costume'] = pid
    part = 'body' if kind=='body' else 'head' if kind=='head' else 'shield' if kind=='shield' else 'accessory'
    p['parts'] = dict(declared=[part],order=[part],relationships=[],attachments=dict(status='UNVERIFIED',declarations=[]))
    p['source_hashes'] = dict(act_sha256=digest(act),spr_sha256=digest(spr))
    p['actions'] = p['actions'][:2]
    p['topology'] = dict(action_count=2,slot_count=16,motion_count=31 if mismatch else 32,
                         layer_counts=[layers],anchor_counts=[1 if anchors else 0])
    p['image_pool'] = dict(indexed_count=0,rgba_count=1,referenced_count=1,distinct_content_count=1)
    p['compatibility'] = {k:'UNVERIFIED' for k in p['compatibility']}
    p['evidence'] = []
    return reseal(p), (act,spr)


def synthetic_case(*, representation='ATTACHED_OVERLAY', mismatch=False, anchors=True, layers=1):
    body,body_bytes = fixture_profile('body-test','body',(255,0,0,255),layers=layers)
    kind = {'COMPLETE_VISUAL_BODY':'body','ATTACHED_OVERLAY':'accessory','HEAD_ACCESSORY':'head',
            'EQUIPMENT_VISUAL':'shield'}[representation]
    costume,costume_bytes = fixture_profile('costume-test',kind,(0,255,0,255),mismatch=mismatch,
                                           anchors=anchors and kind != 'shield',layers=layers)
    part = costume['parts']['declared'][0]
    attachments = []
    if kind != 'body':
        p = deepcopy(get_default_registry().to_dict()['attachment_pairings'][0])
        rule = {'head':'player_head_anchor_delta','accessory':'head_accessory_anchor_delta','shield':'body_shield_relative'}[kind]
        p.update(id='synthetic-attachment',parent_profile_id=body['id'],child_profile_id=costume['id'],
                 parent_part='body',child_part=part,rule=rule,layer_order=['body',part],
                 compatibility={k:'UNVERIFIED' for k in p['compatibility']},evidence=[])
        p['anchor_rule']['mode'] = {'head':'parent_head_anchor_delta','accessory':'head_accessory_anchor_delta',
                                  'shield':'body_shield_relative'}[kind]
        p['anchor_rule'].update(parent_anchor_index=None if kind == 'shield' else 0,
                                child_anchor_index=None if kind == 'shield' else 0)
        attachments = [p]
    pairing = build_cosmetic_pairing(id='outfit-x',body=body,appearance=costume,representation=representation,
        action_views=[dict(action=a,view=0,body_slot=s,appearance_slot=s) for a,s in [('Walk',8),('Idle',0)]],
        appearance_part=part,attachment_pairing=attachments[0] if attachments else None)
    registry = create_registry([body,costume],attachment_pairings=attachments,cosmetic_pairings=[pairing])
    rp = to_runtime_profile_contract(body); actor = to_actor_contract(body)
    actions = [dict(id=a,requirement='REQUIRED',parts=[dict(part='body',views=[dict(view=0,frame_count=2,
                topology=dict(kind='explicit',layers=['layer-'+str(i) for i in range(layers)]))])]) for a in ('Idle','Walk')]
    req = resolve_topology(load_target(target_document(actor,rp,actions=actions),actor=actor,profile=rp),actor=actor,profile=rp)
    return registry,req,{body['id']:body_bytes,costume['id']:costume_bytes}


class AppearanceTests(unittest.TestCase):
    def setUp(self):
        self.reg,self.req,self.data = synthetic_case()

    def evaluate(self,reg=None,req=None,data=None,**context):
        return evaluate_appearance(reg or self.reg,'outfit-x',requirements=req or self.req,
            resources=self.data if data is None else data,character_id='C',gameplay_job='J',**context)

    def preview(self,reg=None,req=None,data=None,**params):
        return preview_appearance(reg or self.reg,'outfit-x',requirements=req or self.req,
            resources=self.data if data is None else data,character_id='C',gameplay_job='J',
            action='Walk',view=0,frame=params.pop('frame',0),canvas_size=(12,12),origin=(5,5),**params)

    def change_pairing(self,**fields):
        d = self.reg.to_dict(); d['cosmetic_pairings'][0].update(fields)
        d['cosmetic_pairings'][0] = reseal(d['cosmetic_pairings'][0])
        return load_registry(reseal(d))

    def test_01_identity_separation_and_unchanged_inputs(self):
        before = canonical_bytes(self.reg.to_dict()), canonical_bytes(self.req),deepcopy(self.data)
        r = self.evaluate()
        self.assertEqual((r['identity']['character_id'],r['identity']['gameplay_job']),('C','J'))
        self.assertEqual(r['identity']['underlying_body']['id'],'body-test')
        self.assertEqual(r['identity']['visual_appearance']['id'],'costume-test')
        self.assertEqual(r['status'],'SUPPORTED'); self.assertEqual(r['full_profile_status'],'PARTIAL')
        self.assertEqual(r['counts'],dict(requested=2,supported=2,unsupported=0))
        self.assertEqual(before,(canonical_bytes(self.reg.to_dict()),canonical_bytes(self.req),self.data))
        self.assertEqual(r['newly_authored_coverage'],0)
        for dim in ('visual_review','native_korangar','compilation','independent_rust','gameplay_eligibility','preview'):
            self.assertEqual(r['dimensions'][dim],'UNVERIFIED')
        self.assertFalse(r['export_ready'])

    def test_02_overlay_pixels_anchor_once_and_original_layers(self):
        result = self.preview()
        # Parent registration at (5,5); child parent(2)-child(1)=+1, green at (6,5).
        self.assertEqual(result['image'].getpixel((5,5)),(255,0,0,255))
        self.assertEqual(result['image'].getpixel((6,5)),(0,255,0,255))
        parts = result['report']['parts']
        self.assertEqual([p['part'] for p in parts],['body','accessory'])
        self.assertEqual([p['clips'][0]['x'] for p in parts],[0,1])
        self.assertEqual(len(read_act(self.data['costume-test'][0])['actions'][8][0]['anchors']),1)
        self.assertEqual(result['report']['visual_review'],'UNVERIFIED')

    def test_03_full_visual_body_is_substitution_not_overlay(self):
        reg,req,data = synthetic_case(representation='COMPLETE_VISUAL_BODY')
        r = self.preview(reg,req,data)
        self.assertEqual(len(r['report']['parts']),1)
        self.assertEqual(r['image'].getpixel((5,5)),(0,255,0,255))
        self.assertEqual(r['compatibility']['identity']['underlying_body']['id'],'body-test')
        self.assertEqual(r['compatibility']['identity']['gameplay_job'],'J')

    def test_04_head_cosmetic_and_equipment_visual(self):
        for representation,offset in [('HEAD_ACCESSORY',1),('EQUIPMENT_VISUAL',0)]:
            with self.subTest(representation=representation):
                reg,req,data = synthetic_case(representation=representation)
                result = self.preview(reg,req,data)
                self.assertEqual(result['image'].getpixel((5+offset,5)),(0,255,0,255))
                self.assertEqual(result['compatibility']['status'],'SUPPORTED')

    def test_05_frame_mismatch_preserves_supported_idle(self):
        reg,req,data = synthetic_case(mismatch=True)
        r = self.evaluate(reg,req,data)
        self.assertEqual(r['status'],'PARTIAL')
        detail = {d['action']:d for d in r['slot_details']}
        self.assertEqual(detail['Idle']['status'],'SUPPORTED')
        self.assertEqual(detail['Walk']['diagnostics'],['MISMATCHED_FRAME_COUNT'])
        with self.assertRaisesRegex(ForgeError,'UNSUPPORTED_COSTUME_SCOPE'):self.preview(reg,req,data)

    def test_06_missing_action_scope_no_fallback(self):
        rows = self.reg.get_cosmetic_pairing('outfit-x')['action_views'][:1]
        r = self.evaluate(self.change_pairing(action_views=rows))
        self.assertEqual(r['status'],'PARTIAL')
        self.assertIn('MISSING_COSTUME_ACTION_VIEW',str(r))

    def test_07_invalid_action_and_direction_slots(self):
        for field,value in [('appearance_slot',9),('body_slot',1),('action','Unknown'),('view',1)]:
            rows = self.reg.get_cosmetic_pairing('outfit-x')['action_views']
            rows[0][field] = value
            rows.sort(key=lambda r:(r['action'],r['view']))
            r = self.evaluate(self.change_pairing(action_views=rows))
            self.assertNotEqual(r['status'],'SUPPORTED')
        with self.assertRaises(ForgeError):self.change_pairing(action_views=[dict(action='Walk',view=8,body_slot=8,appearance_slot=8)])

    def test_08_missing_anchor_does_not_use_attachment_fallback(self):
        reg,req,data = synthetic_case(anchors=False)
        self.assertEqual(self.evaluate(reg,req,data)['status'],'UNSUPPORTED')
        with self.assertRaisesRegex(ForgeError,'UNSUPPORTED_COSTUME_SCOPE'):self.preview(reg,req,data)

    def test_09_source_hash_rejected_before_preview(self):
        data = deepcopy(self.data); data['costume-test'] = (data['costume-test'][0],b'wrong')
        with self.assertRaisesRegex(ForgeError,'SOURCE_HASH_MISMATCH'):self.preview(data=data)
        with self.assertRaisesRegex(ForgeError,'MISSING_COSTUME_SOURCE'):self.evaluate(data={})

    def test_10_missing_hash_and_unsupported_format(self):
        for key,value in [('source_hashes',{}),('formats',dict(act_version='2.5',spr_version='2.1'))]:
            d = self.reg.to_dict(); d['profiles'][0][key] = value; d['profiles'][0] = reseal(d['profiles'][0])
            with self.assertRaises(ForgeError):load_registry(reseal(d))

    def test_11_profile_revision_and_unknown_profile(self):
        for key,value in [('id','absent'),('version','2.0.0'),('canonical_sha256','0'*64)]:
            ref = deepcopy(self.reg.get_cosmetic_pairing('outfit-x')['appearance_profile']);ref[key] = value
            with self.assertRaises(ForgeError):self.change_pairing(appearance_profile=ref)
        with self.assertRaisesRegex(ForgeError,'UNKNOWN_COSTUME_PAIRING'):self.reg.get_cosmetic_pairing('absent')

    def test_12_representation_parts_order_and_rule_rejections(self):
        for fields in [dict(representation='UNIVERSAL_FITTING'),dict(appearance_part='missing'),
                       dict(layer_order=['accessory','body']),dict(layer_order=['body']),
                       dict(attachment_pairing_id=None),dict(representation='COMPLETE_VISUAL_BODY')]:
            with self.subTest(fields=fields),self.assertRaises(ForgeError):self.change_pairing(**fields)
        d = self.reg.to_dict(); d['attachment_pairings'][0]['rule'] = 'standalone_unattached'
        with self.assertRaisesRegex(ForgeError,'STALE_ATTACHMENT_PAIRING'):load_registry(reseal(d))

    def test_13_conflicting_bindings(self):
        rows = self.reg.get_cosmetic_pairing('outfit-x')['action_views'];rows.append(deepcopy(rows[0]))
        rows.sort(key=lambda r:(r['action'],r['view']))
        with self.assertRaisesRegex(ForgeError,'CONFLICTING_COSTUME_BINDING'):self.change_pairing(action_views=rows)
        d = self.reg.to_dict();d['cosmetic_pairings'] *= 2
        with self.assertRaisesRegex(ForgeError,'CONFLICTING_COSTUME_BINDING'):load_registry(reseal(d))

    def test_14_multilayer_order_and_metadata_preserved(self):
        reg,req,data = synthetic_case(layers=2)
        result = self.preview(reg,req,data)
        self.assertEqual(result['report']['renderer']['layers_rendered'],4)
        self.assertEqual([[c['x'] for c in p['clips']] for p in result['report']['parts']],[[0,1],[1,2]])
        for part,pid in [('body','body-test'),('accessory','costume-test')]:
            clips = next(p['clips'] for p in result['report']['parts'] if p['part']==part)
            original = read_act(data[pid][0])['actions'][8][0]['clips']
            for a,b in zip(clips,original):
                self.assertEqual({k:v for k,v in a.items() if k!='x'},{k:v for k,v in b.items() if k!='x'})

    def test_15_topology_independent_from_valid_resource(self):
        reg,_,data = synthetic_case(layers=2)
        self.assertEqual(self.evaluate(reg,self.req,data)['status'],'UNSUPPORTED')
        self.assertIn('MISMATCHED_LAYER_TOPOLOGY',str(self.evaluate(reg,self.req,data)))

    def test_16_head_body_preserved_and_rebinding_visible(self):
        reg,req,data = synthetic_case(representation='COMPLETE_VISUAL_BODY')
        extra,_ = fixture_profile('separate-head','head',(0,0,255,255))
        d = reg.to_dict(); d['profiles'].append(extra);reg = load_registry(reseal(d))
        r = self.evaluate(reg,req,data,head_profile='separate-head')
        self.assertEqual(r['identity']['head_profile'],'separate-head')
        self.assertIn('VISUAL_HOST_ATTACHMENT_REBIND_REQUIRED',r['diagnostics'])
        with self.assertRaisesRegex(ForgeError,'UNRESOLVED_VISUAL_HOST_ATTACHMENTS'):
            self.preview(reg,req,data,head_profile='separate-head')

    def test_17_existing_registry_bytes_unchanged(self):
        old = get_default_registry()
        self.assertNotIn('cosmetic_pairings',old.to_dict())
        self.assertEqual(load_registry(old.to_dict()).canonical_sha256,old.canonical_sha256)
        self.assertEqual(old.get_profile('novice-male-body-v1')['gameplay_job'],'novice')

    def test_18_canonical_enumeration_labels_and_paths(self):
        d = self.reg.to_dict()
        other = create_registry(list(reversed(d['profiles'])),attachment_pairings=list(reversed(d['attachment_pairings'])),
                                cosmetic_pairings=list(reversed(d['cosmetic_pairings'])))
        self.assertEqual(other.canonical_sha256,self.reg.canonical_sha256)
        self.assertEqual(canonical_bytes(self.evaluate()),canonical_bytes(self.evaluate(other)))
        r = self.preview();self.assertEqual(r['png_bytes'],self.preview()['png_bytes'])
        self.assertEqual(r['report']['canonical_sha256'],self.preview()['report']['canonical_sha256'])
        self.assertNotIn(b'/tmp/',canonical_bytes(r['report']))
        self.assertNotIn(b'/home/',canonical_bytes(r['report']))

    def test_19_hashseed_determinism(self):
        code = "from test_appearance import *;r,q,d=synthetic_case();print(evaluate_appearance(r,'outfit-x',requirements=q,resources=d,character_id='C',gameplay_job='J')['canonical_sha256'])"
        results = [subprocess.check_output([sys.executable,'-c',code],env=dict(os.environ,PYTHONHASHSEED=str(seed),
                    PYTHONPATH=os.pathsep.join([str(Path(__file__).resolve().parent),str(Path(__file__).resolve().parents[1]/'src')])))
                   for seed in (1,734)]
        self.assertEqual(results[0],results[1])

    def test_20_runtime_authority_mismatch_rejected(self):
        req = deepcopy(self.req);req['runtime_profile']['canonical_sha256'] = '0'*64
        with self.assertRaisesRegex(ForgeError,'RUNTIME_PROFILE_MISMATCH'):self.evaluate(req=reseal(req))

    def test_21_invalid_frame_and_undeclared_scope(self):
        for frame in (-1,2,True):
            with self.assertRaisesRegex(ForgeError,'INVALID_COSTUME_FRAME'):self.preview(frame=frame)
        with self.assertRaisesRegex(ForgeError,'UNSUPPORTED_COSTUME_SCOPE'):
            preview_appearance(self.reg,'outfit-x',requirements=self.req,resources=self.data,character_id='C',
                               action='Walk',view=1,frame=0)

    def test_22_no_artwork_coverage_from_successful_preview(self):
        self.preview()
        coverage = evaluate_coverage(self.req)
        self.assertEqual(coverage['counts']['assignments']['direct'],0)

    def test_23_no_native_or_approval_fields_can_be_injected(self):
        d = self.reg.to_dict();d['cosmetic_pairings'][0]['native_korangar'] = 'VERIFIED'
        with self.assertRaises(ForgeError):load_registry(reseal(d))

    def test_31_exact_attachment_record_bound_and_anchor_indices_not_ignored(self):
        d = self.reg.to_dict();d['attachment_pairings'][0]['evidence']=['a'*64]
        with self.assertRaisesRegex(ForgeError,'STALE_ATTACHMENT_PAIRING'):load_registry(reseal(d))
        d['cosmetic_pairings'][0]['attachment_pairing_sha256']=digest(canonical_bytes(d['attachment_pairings'][0]))
        d['cosmetic_pairings'][0]=reseal(d['cosmetic_pairings'][0]);other=load_registry(reseal(d))
        self.assertNotEqual(other.get_cosmetic_pairing('outfit-x')['canonical_sha256'],
                            self.reg.get_cosmetic_pairing('outfit-x')['canonical_sha256'])
        d['attachment_pairings'][0]['anchor_rule']['parent_anchor_index']=1
        d['cosmetic_pairings'][0]['attachment_pairing_sha256']=digest(canonical_bytes(d['attachment_pairings'][0]))
        d['cosmetic_pairings'][0]=reseal(d['cosmetic_pairings'][0])
        with self.assertRaisesRegex(ForgeError,'UNSUPPORTED_ATTACHMENT_ANCHOR_RULE'):load_registry(reseal(d))

    def test_32_compatibility_dimensions_are_independent(self):
        reg,req,data=synthetic_case(mismatch=True)
        r=self.evaluate(reg,req,data)
        self.assertEqual(r['dimensions']['action_view'],'SUPPORTED')
        self.assertEqual(r['dimensions']['frame_correspondence'],'PARTIAL')
        walk=next(d for d in r['slot_details'] if d['action']=='Walk')
        self.assertEqual(walk['dimensions']['layer_topology'],'UNVERIFIED')
        self.assertEqual(walk['dimensions']['anchors'],'UNVERIFIED')
        reg,req,data=synthetic_case(anchors=False)
        r=self.evaluate(reg,req,data)
        self.assertEqual(r['dimensions']['frame_correspondence'],'SUPPORTED')
        self.assertEqual(r['dimensions']['layer_topology'],'SUPPORTED')
        self.assertEqual(r['dimensions']['anchors'],'UNSUPPORTED')

    def test_33_source_revision_changes_compatibility_identity(self):
        d=self.reg.to_dict();changed,pair=fixture_profile('costume-test','accessory',(0,0,255,255))
        d['profiles']=[changed if p['id']=='costume-test' else p for p in d['profiles']]
        # A new source cannot reuse the old pairing seal/profile reference.
        with self.assertRaisesRegex(ForgeError,'STALE_PROFILE_REVISION'):load_registry(reseal(d))
        d['cosmetic_pairings'][0]['appearance_profile']={k:changed[k] for k in ('id','version','canonical_sha256')}
        d['cosmetic_pairings'][0]=reseal(d['cosmetic_pairings'][0]);reg=load_registry(reseal(d))
        data=dict(self.data,**{'costume-test':pair});r=self.preview(reg,self.req,data)
        self.assertEqual(r['image'].getpixel((6,5)),(0,0,255,255))
        self.assertNotEqual(r['compatibility']['canonical_sha256'],self.evaluate()['canonical_sha256'])
        self.assertEqual(r['compatibility']['identity']['gameplay_job'],'J')

    def test_34_existing_head_not_silently_merged_and_geometry_evidence(self):
        head,_=fixture_profile('separate-head','head',(0,0,255,255))
        d=self.reg.to_dict();d['profiles'].append(head);reg=load_registry(reseal(d))
        r=self.evaluate(reg,head_profile='separate-head')
        self.assertEqual(r['diagnostics'],['ADDITIONAL_ATTACHMENTS_NOT_COMPOSED'])
        with self.assertRaisesRegex(ForgeError,'UNRESOLVED_VISUAL_HOST_ATTACHMENTS'):
            self.preview(reg,head_profile='separate-head')
        with self.assertRaisesRegex(ForgeError,'INVALID_HEAD_PROFILE'):self.evaluate(head_profile='costume-test')
        result=self.preview()
        for p in result['report']['parts']:
            original=read_act(self.data[p['profile_id']][0])
            self.assertEqual(p['source_motion'],original['actions'][8][0])
            self.assertEqual(p['source_delay'],original['delays'][8])
        self.assertEqual(result['report']['rendered_png_sha256'],digest(result['png_bytes']))

    def test_35_overlay_change_scoped_and_aggregate_review_invalidation(self):
        body=self.reg.get_profile('body-test');rp=to_runtime_profile_contract(body)
        actor_doc=to_actor_contract(body).to_dict();actor_doc.pop('canonical_sha256')
        actor_doc['parts']=['body','accessory','aggregate','unrelated'];actor=load_actor(actor_doc)
        actions=[dict(id='Walk',requirement='REQUIRED',parts=[dict(part=p,views=[dict(view=0,frame_count=2,
                 topology=dict(kind='explicit',layers=['selected-component']))]) for p in actor_doc['parts']])]
        req=resolve_topology(load_target(target_document(actor,rp,actions=actions),actor=actor,profile=rp),actor=actor,profile=rp)
        aggregate=[f['id'] for f in req['frames'] if '/aggregate/' in f['id']]
        old=bind_appearance_requirements(req,self.reg,'outfit-x',dependent_frame_ids=aggregate)
        d=document(old);raw=io.BytesIO();Image.new('RGBA',(1,1),'green').save(raw,format='PNG');raw=raw.getvalue()
        d['sources']=[source(content=raw)];d['assignments']=[assignment(old,i,'A'+str(i)) for i in range(len(old['layers']))]
        resolved=resolve_ledger(load_ledger(d,requirements=old),requirements=old,source_bytes={'art-a':raw})
        b=bases(old,resolved)
        events=[make_event('P',1,old['target'],'APPROVED',[
            dict(requirement_id=rid,basis_sha256=sha,evidence_sha256=digest(raw)) for rid,sha in sorted(b.items())],1)]
        other=self.reg.to_dict();y=deepcopy(other['cosmetic_pairings'][0]);y['id']='outfit-y';y['evidence']=['2'*64]
        other['cosmetic_pairings'].append(reseal(y));other=load_registry(reseal(other))
        new=bind_appearance_requirements(old,other,'outfit-y',dependent_frame_ids=aggregate)
        states=evaluate_reviews('P',events,new,resolved)
        parts={l['id']:l['part'] for l in old['layers']}
        for row in states['occurrences']:
            self.assertEqual(row['state'],'STALE' if parts[row['requirement_id']] in ('accessory','aggregate') else 'APPROVED')
        self.assertEqual(states['counts']['STALE'],4);self.assertEqual(states['counts']['APPROVED'],4)
        self.assertEqual(states['history'],events)
        self.assertEqual(new['target'],old['target']);self.assertEqual(new['runtime_profile'],old['runtime_profile'])
        with self.assertRaisesRegex(ForgeError,'INVALID_COSMETIC_DEPENDENCY_SCOPE'):
            bind_appearance_requirements(req,self.reg,'outfit-x',dependent_frame_ids=['invented'])


class ClothingReviewTests(unittest.TestCase):
    def setUp(self):
        self.reg,req,self.resources = synthetic_case(representation='COMPLETE_VISUAL_BODY')
        self.req = bind_appearance_requirements(req,self.reg,'outfit-x')
        self.d = document(self.req)
        raw = io.BytesIO();Image.new('RGBA',(2,2),(15,30,80,255)).save(raw,format='PNG');self.raw = raw.getvalue()
        self.data = {'art-a':self.raw}
        self.d['sources'] = [source(content=self.raw)]
        self.d['assignments'] = [assignment(self.req,i,'A'+str(i)) for i in range(len(self.req['layers']))]
        self.resolved = resolve_ledger(load_ledger(self.d,requirements=self.req),requirements=self.req,source_bytes=self.data)
        self.b = bases(self.req,self.resolved)
        members = [dict(requirement_id=r,basis_sha256=b,evidence_sha256=digest(self.raw)) for r,b in sorted(self.b.items())]
        self.events = [make_event('P',1,self.req['target'],'APPROVED',members,1)]

    def plan(self,**kw):
        params = dict(requirements=self.req,declaration=self.d,source_bytes=self.data,project_id='P',review_events=self.events,
                      requirement_ids=[self.req['layers'][0]['id']], resources=self.resources, character_id='C')
        params.update(kw)
        return prepare_clothing_composition(self.reg,'outfit-x',**params)

    def test_24_current_explicit_approval_and_exact_assignment_provenance(self):
        p = self.plan()
        self.assertEqual(p['assignments'][0]['assignment_id'],'A0')
        self.assertEqual(p['assignments'][0]['source']['sha256'],digest(self.raw))
        self.assertEqual(p['assignments'][0]['review_id'],self.events[0]['id'])
        self.assertFalse(p['export_ready']);self.assertEqual(p['native_korangar'],'UNVERIFIED')
        self.assertEqual(canonical_bytes(p),canonical_bytes(self.plan()))

    def test_25_missing_review_rejected(self):
        with self.assertRaisesRegex(ForgeError,'CURRENT_CLOTHING_APPROVAL_REQUIRED'):self.plan(review_events=[])

    def test_26_changed_outfit_invalidates_aggregate_not_history(self):
        d = self.reg.to_dict();pair = deepcopy(d['cosmetic_pairings'][0]);pair['id'] = 'outfit-y';pair['evidence'] = ['1'*64]
        pair = reseal(pair);d['cosmetic_pairings'].append(pair);reg = load_registry(reseal(d))
        new = bind_appearance_requirements(self.req,reg,'outfit-y')
        status = evaluate_reviews('P',self.events,new,self.resolved)
        self.assertTrue(all(r['state']=='STALE' for r in status['occurrences']))
        self.assertEqual(status['history'],self.events)
        self.assertEqual(evaluate_reviews('P',self.events,self.req,self.resolved)['counts']['APPROVED'],4)
        self.assertEqual(new['target'],self.req['target'])

    def test_27_classic_art_never_new_authored_coverage(self):
        d = deepcopy(self.d);d['sources'][0]['origin']='CLASSIC_REFERENCE'
        r = resolve_ledger(load_ledger(d,requirements=self.req),requirements=self.req,source_bytes=self.data)
        b = bases(self.req,r)
        events = [make_event('P',1,self.req['target'],'APPROVED',[
            dict(requirement_id=rid,basis_sha256=b[rid],evidence_sha256=digest(self.raw)) for rid in sorted(b)],1)]
        with self.assertRaisesRegex(ForgeError,'RETAINED_REFERENCE_IS_NOT_NEW_ARTWORK'):self.plan(declaration=d,review_events=events)

    def test_28_corrupt_missing_and_stale_inputs(self):
        for data in ({},{'art-a':b'corrupted'}):
            with self.assertRaises(ForgeError):self.plan(source_bytes=data)
        d = deepcopy(self.d);d['requirements_sha256']='0'*64
        with self.assertRaises(ForgeError):self.plan(declaration=d)
        d = deepcopy(self.d);d['assignments'][0]['source']['revision']=2
        with self.assertRaises(ForgeError):self.plan(declaration=d)

    def test_29_unbound_composition_rejected(self):
        r = deepcopy(self.req)
        for f in r['frames']:f['constraints']=None
        with self.assertRaisesRegex(ForgeError,'UNBOUND_COSMETIC_COMPOSITION'):self.plan(requirements=reseal(r))

    def test_30_invalid_scope(self):
        for ids in ([],['absent'],[self.req['layers'][0]['id']]*2):
            with self.assertRaisesRegex(ForgeError,'INVALID_CLOTHING_SCOPE'):self.plan(requirement_ids=ids)


if __name__ == '__main__':unittest.main()
