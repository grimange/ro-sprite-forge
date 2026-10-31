"""RSF-35: synthetic offline actions; approvals are isolated test decisions."""
import copy
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from PIL import Image
from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, load_target, reference
from ro_sprite_forge.core.custom_actions import action_support, preview_offline_action, offline_registry_entry
from ro_sprite_forge.core.topology import resolve_topology
from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger as _resolve_ledger

def resolve_ledger(value, *, requirements, source_bytes=None):
    return _resolve_ledger(load_ledger(value,requirements=requirements),requirements=requirements,source_bytes=source_bytes)

from ro_sprite_forge.core.coverage import evaluate_coverage
from ro_sprite_forge.core.review import bases, make_event, evaluate_reviews
from ro_sprite_forge.core.registry import get_default_registry, create_registry, load_registry, to_actor_contract, to_runtime_profile_contract
from ro_sprite_forge.core.project import create_project, load_project, save_project, import_blob, get_blob
from ro_sprite_forge.core.compiler import compile_resources, plan_compilation
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.spr import read_spr
from test_contracts import actor_document, target_document
from test_compiler import _make_png, _build_approved_ledger, _build_synthetic_monster_act_spr, _setup_monster_contracts, RUST_ORACLE_BIN

COLORS = [(255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255), (255, 255, 0, 255)]
ROOT = Path(__file__).resolve().parents[1]


def declaration(name='Wave', count=4, topology=None):
    return dict(id=name, requirement='REQUIRED', offline=dict(schema='rsf.offline-action/v1', label=name,
        timing=dict(authority='EXPLICIT_DIAGNOSTIC_INTERVAL', frame_ms=80, loop=True), compilation='UNSUPPORTED'),
        parts=[dict(part='body', views=[dict(view=0, frame_count=count,
            topology=topology if topology is not None else dict(kind='explicit', layers=['body']))])])


def fixture(actor=None, profile=None, doc=None):
    profile = profile or frozen_runtime_profile('player')
    actor = actor or load_actor(actor_document(profile))
    if doc is None:
        walk = dict(id='Walk', requirement='REQUIRED', parts=[dict(part='body', views=[dict(view=0, frame_count=1,
            topology=dict(kind='explicit', layers=['body']))])])
        doc = target_document(actor, profile, actions=[declaration(), walk])
    target = load_target(doc, actor=actor, profile=profile)
    req = resolve_topology(target, actor=actor, profile=profile)
    sources = {f'art{i}': _make_png(4, 4, c) for i,c in enumerate(COLORS)}
    assignments = [dict(requirement_id=l['id'], kind='DIRECT_SOURCE', source=dict(id=f"art{l['frame'] % 4}", revision=1),
                        review_state=None) for l in req['layers']]
    ledger = _build_approved_ledger(req, assignments, sources)
    return actor, profile, target, req, ledger, sources


def bound_fixture(name='Guard'):
    act, spr = _build_synthetic_monster_act_spr()
    actor, profile, old, inv, _ = _setup_monster_contracts(act, spr)
    doc = old.to_dict(); doc.pop('canonical_sha256')
    action = declaration(name, topology=dict(kind='inherited', inventory_sha256=inv['canonical_sha256'], slot=8))
    action['offline']['compilation'] = 'BOUND_EXISTING_SLOT_DIAGNOSTIC'
    doc['actions'] = [action]
    target = load_target(doc, actor=actor, profile=profile)
    req = resolve_topology(target, actor=actor, profile=profile, inventories=(inv,))
    sources = {'art': _make_png(4,4,(12,34,56,255))}
    ledger = _build_approved_ledger(req, [dict(requirement_id=req['layers'][0]['id'], kind='DIRECT_SOURCE',
        source=dict(id='art', revision=1))], sources)
    return act, spr, actor, profile, target, inv, dict(requirements=req, ledger=ledger, source_bytes=sources, replacement_policy='explicit_rgba')


class OfflineActionTests(unittest.TestCase):
    def setUp(self):
        self.actor,self.profile,self.target,self.req,self.ledger,self.sources = fixture()

    def preview(self, **kwargs):
        return preview_offline_action(self.target, actor=self.actor, profile=self.profile,
            ledger=self.ledger, source_bytes=self.sources, action_id='Wave', view=0, canvas_size=(16,16), **kwargs)

    def test_exact_declared_topology_and_stable_identity(self):
        wave = [l for l in self.req['layers'] if l['action']=='Wave']
        self.assertEqual([(l['view'],l['frame'],l['ordinal']) for l in wave], [(0,n,0) for n in range(4)])
        self.assertTrue(all('/action/Wave/' in l['id'] and l['runtime_slot'] is None for l in wave))
        doc=self.target.to_dict();doc.pop('canonical_sha256');doc['actions'].reverse()
        req=resolve_topology(load_target(doc,actor=self.actor,profile=self.profile),actor=self.actor,profile=self.profile)
        self.assertEqual(self.req,req)

    def test_known_pixels_each_frame_and_diagnostic_clock(self):
        for n,color in enumerate(COLORS):
            result=self.preview(frame=n)
            visible=[p for p in result['image'].getdata() if p[3]]
            self.assertTrue(visible);self.assertEqual(set(visible),{color})
            self.assertEqual(result['offline']['frame'],n)
            self.assertEqual(result['offline']['visual_review'],'UNVERIFIED')
            self.assertEqual(result['offline']['runtime_mapping'],'UNSUPPORTED')
        self.assertEqual(self.preview(elapsed_ms=400)['offline']['frame'],1)
        self.assertEqual(self.preview(elapsed_ms=320)['offline']['frame'],0)

    def test_coverage_and_no_automatic_approval(self):
        report=resolve_ledger(self.ledger,requirements=self.req,source_bytes=self.sources)
        self.assertTrue(all(r['visual_review']=='UNVERIFIED' for r in report['assignments']))
        coverage=evaluate_coverage(self.req,self.ledger,source_bytes=self.sources,target=self.target)
        self.assertFalse(coverage['status']['export_ready'])
        partial=copy.deepcopy(self.ledger);partial['assignments']=partial['assignments'][:-1]
        missing=resolve_ledger(partial,requirements=self.req,source_bytes=self.sources)
        self.assertEqual(len(self.req['layers'])-len(missing['assignments']),1)

    def test_support_dimensions_walk_preserved_and_no_fallback(self):
        report=action_support(self.target,actor=self.actor,profile=self.profile)
        rows={r['action_id']:r for r in report['actions']}
        self.assertEqual(rows['Walk']['runtime_slots'],[dict(view=0,part='body',slot=8)])
        self.assertEqual(rows['Walk']['runtime_mapping'],'SUPPORTED')
        self.assertEqual(rows['Walk']['native_verification'],'UNVERIFIED')
        self.assertEqual(rows['Wave']['runtime_slots'],[])
        self.assertEqual(rows['Wave']['runtime_mapping'],'UNSUPPORTED')
        self.assertEqual(rows['Wave']['diagnostics'],['RUNTIME_ACTION_MAPPING_UNAVAILABLE'])
        from ro_sprite_forge.core.timeline import AnimationTimeline
        from test_compiler import _build_synthetic_monster_act_spr
        timeline=AnimationTimeline(read_act(_build_synthetic_monster_act_spr()[0]),category='monster')
        with self.assertRaises(ForgeError):timeline.select(action='Wave',view=0)

    def test_duplicate_and_native_identity_collisions(self):
        for change in ('duplicate','native'):
            doc=self.target.to_dict();doc.pop('canonical_sha256')
            if change=='duplicate':doc['actions'].append(copy.deepcopy(doc['actions'][0]))
            else:next(a for a in doc['actions'] if a['id']=='Wave')['id']='Idle'
            with self.assertRaises(ForgeError):load_target(doc,actor=self.actor,profile=self.profile)

    def test_slot_spoof_native_claim_and_bad_kind_rejected(self):
        for key,val in [('runtime_slot',104),('native_verification','VERIFIED'),('kind','NATIVE')]:
            doc=self.target.to_dict();doc.pop('canonical_sha256');next(a for a in doc['actions'] if a['id']=='Wave')['offline'][key]=val
            with self.assertRaises(ForgeError):load_target(doc,actor=self.actor,profile=self.profile)

    def test_undeclared_topology_remains_partial(self):
        doc=self.target.to_dict();doc.pop('canonical_sha256');next(a for a in doc['actions'] if a['id']=='Wave')['parts'][0]['views'][0]['topology']=None
        target=load_target(doc,actor=self.actor,profile=self.profile)
        row=next(r for r in action_support(target,actor=self.actor,profile=self.profile)['actions'] if r['action_id']=='Wave')
        self.assertEqual(row['authoring'],'PARTIAL');self.assertEqual(row['preview'],'UNSUPPORTED')

    def test_invalid_view_frame_and_action(self):
        for kwargs in [dict(frame=4),dict(frame=-1),dict(frame=True),dict(elapsed_ms=-1)]:
            with self.assertRaises(ForgeError):self.preview(**kwargs)
        for key,val in [('view',8),('frame_count',-1)]:
            doc=self.target.to_dict();doc.pop('canonical_sha256');next(a for a in doc['actions'] if a['id']=='Wave')['parts'][0]['views'][0][key]=val
            with self.assertRaises(ForgeError):load_target(doc,actor=self.actor,profile=self.profile)
        with self.assertRaises(ForgeError):preview_offline_action(self.target,actor=self.actor,profile=self.profile,
            ledger=self.ledger,source_bytes=self.sources,action_id='Idle',view=0)

    def test_missing_or_changed_source_and_stale_ledger(self):
        for sources in [{},dict(self.sources,art0=b'corrupt')]:
            with self.assertRaises(ForgeError):preview_offline_action(self.target,actor=self.actor,profile=self.profile,
                ledger=self.ledger,source_bytes=sources,action_id='Wave',view=0)
        bad=copy.deepcopy(self.ledger);bad['target']['revision']+=1
        with self.assertRaises(ForgeError):resolve_ledger(bad,requirements=self.req,source_bytes=self.sources)
        bad=copy.deepcopy(self.ledger);bad['assignments'][0]['binding']['frame']=99
        with self.assertRaises(ForgeError):load_ledger(bad,requirements=self.req)

    def test_source_and_timing_review_invalidation_is_scoped(self):
        report=resolve_ledger(self.ledger,requirements=self.req,source_bytes=self.sources)
        members=[dict(requirement_id=k,basis_sha256=v,evidence_sha256='e'*64) for k,v in sorted(bases(self.req,report).items())]
        event=make_event('demo',1,self.req['target'],'APPROVED',members,1)
        source_change=copy.deepcopy(self.ledger);source_change['assignments'][0]['revision']+=1
        changed=resolve_ledger(source_change,requirements=self.req,source_bytes=self.sources)
        review=evaluate_reviews('demo',[event],self.req,changed)
        self.assertEqual(review['counts']['STALE'],1)
        doc=self.target.to_dict();doc.pop('canonical_sha256');doc['revision']=2;doc['previous_sha256']=self.target.canonical_sha256
        next(a for a in doc['actions'] if a['id']=='Wave')['offline']['timing']['frame_ms']=90
        target=load_target(doc,actor=self.actor,profile=self.profile)
        req=resolve_topology(target,actor=self.actor,profile=self.profile)
        ledger=copy.deepcopy(self.ledger);ledger['target']=req['target'];ledger['requirements_sha256']=req['canonical_sha256']
        review=evaluate_reviews('demo',[event],req,resolve_ledger(ledger,requirements=req,source_bytes=self.sources))
        self.assertEqual(review['counts']['STALE'],4);self.assertEqual(review['counts']['APPROVED'],1)
        self.assertEqual(review['history'],[event])

    def test_topology_change_preserves_unrelated_action_review(self):
        report=resolve_ledger(self.ledger,requirements=self.req,source_bytes=self.sources)
        old=bases(self.req,report)
        doc=self.target.to_dict();doc.pop('canonical_sha256');next(a for a in doc['actions'] if a['id']=='Wave')['parts'][0]['views'][0]['frame_count']=3
        _,_,target,req,ledger,sources=fixture(self.actor,self.profile,doc)
        new=bases(req,resolve_ledger(ledger,requirements=req,source_bytes=sources))
        walk=next(l['id'] for l in self.req['layers'] if l['action']=='Walk')
        self.assertEqual(old[walk],new[walk])
        self.assertNotEqual(action_support(self.target,actor=self.actor,profile=self.profile)['canonical_sha256'],
                            action_support(target,actor=self.actor,profile=self.profile)['canonical_sha256'])

    def test_existing_project_save_reopen(self):
        with tempfile.TemporaryDirectory() as tmp:
            project=create_project(tmp,'wave','Offline Wave','custom','player',target=self.target.to_dict(),ledger=self.ledger)
            # Persist original image blobs through the existing project store.
            for sid,raw in self.sources.items():import_blob(tmp,'wave',sid+'.png',raw)
            project=load_project(tmp,'wave')
            self.assertEqual(project['target'],self.target.to_dict());self.assertEqual(project['ledger'],self.ledger)
            for raw in self.sources.values():self.assertEqual(get_blob(tmp,'wave',digest(raw)),raw)
            self.assertFalse(project.get('review_events'))


class DiagnosticActionCompilationTests(unittest.TestCase):
    def test_guard_and_dodge_exact_existing_storage_only(self):
        for name in ('Guard','Dodge'):
            act,spr,actor,profile,target,inv,kw=bound_fixture(name)
            before=read_act(act)
            result=compile_resources(act,spr,**kw,oracle_executable=RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None)
            plan=plan_compilation(act,spr,**kw)
            self.assertTrue(plan['ready_to_compile'])
            self.assertEqual(plan['selected_replacements'][0]['runtime_slot'],None)
            self.assertEqual(plan['selected_replacements'][0]['diagnostic_storage_slot'],8)
            self.assertEqual(plan['selected_replacements'][0]['runtime_mapping'],'UNSUPPORTED')
            self.assertTrue(any('RUNTIME_ACTION_MAPPING_UNAVAILABLE' in d for d in result['manifest']['status']['diagnostics']))
            after=read_act(result['act_bytes'])
            self.assertEqual(len(after['actions']),40)
            for slot,frames in enumerate(before['actions']):
                for frame,motion in enumerate(frames):
                    if (slot,frame)!=(8,0):self.assertEqual(motion,after['actions'][slot][frame])
            self.assertEqual(before['delays'],after['delays']);self.assertEqual(before['reserved'],after['reserved'])
            clip=after['actions'][8][0]['clips'][0]
            image=read_spr(result['spr_bytes']).rgba_images[clip['sprite']]
            self.assertEqual(image.rgba,bytes([12,34,56,255])*16)
            self.assertEqual(result['manifest']['status']['export_label'],'PARTIAL_DIAGNOSTIC')
            self.assertFalse(result['manifest']['status']['production_authorized'])
            support=action_support(target,actor=actor,profile=profile,inventories=(inv,))['actions'][0]
            self.assertEqual(support['runtime_slots'],[]);self.assertEqual(support['diagnostic_storage'][0]['source_slot'],8)
            other=compile_resources(act,spr,**kw)
            self.assertEqual(result['act_bytes'],other['act_bytes']);self.assertEqual(result['spr_bytes'],other['spr_bytes'])
            self.assertEqual(result['manifest']['build'],other['manifest']['build'])

    def test_unsupported_and_arbitrary_slot_not_compiled(self):
        act,spr,actor,profile,target,inv,kw=bound_fixture()
        req=copy.deepcopy(kw['requirements']);req.pop('canonical_sha256')
        for layer in req['layers']:layer['offline']['compilation']='UNSUPPORTED'
        req=sealed(req)
        # A stale ledger cannot authorize changed requirements either.
        with self.assertRaises(ForgeError):compile_resources(act,spr,**dict(kw,requirements=req))
        doc=target.to_dict();doc.pop('canonical_sha256');doc['actions'][0]['parts'][0]['views'][0]['topology']['slot']=104
        with self.assertRaises(ForgeError):resolve_topology(load_target(doc,actor=actor,profile=profile),actor=actor,profile=profile,inventories=(inv,))
        with self.assertRaises(ForgeError):compile_resources(act,spr,**kw,compilation_mode='production_export')

    def test_conflicting_storage_mappings_and_missing_approval(self):
        act,spr,actor,profile,target,inv,kw=bound_fixture()
        doc=target.to_dict();doc.pop('canonical_sha256');other=copy.deepcopy(doc['actions'][0]);other['id']='Dodge';doc['actions'].append(other)
        target=load_target(doc,actor=actor,profile=profile);req=resolve_topology(target,actor=actor,profile=profile,inventories=(inv,))
        ledger=_build_approved_ledger(req,[dict(requirement_id=l['id'],kind='DIRECT_SOURCE',source=dict(id='art',revision=1))
            for l in req['layers'] if l['frame']==0],kw['source_bytes'])
        with self.assertRaises(ForgeError):compile_resources(act,spr,**dict(kw,requirements=req,ledger=ledger))
        ledger=copy.deepcopy(kw['ledger']);ledger['assignments'][0]['review']=None
        with self.assertRaises(ForgeError):compile_resources(act,spr,**dict(kw,ledger=ledger))


class CustomRegistryTests(unittest.TestCase):
    def entry(self):
        registry=get_default_registry();profile_entry=next(p for p in registry.to_dict()['profiles'] if p['id']=='novice-male-body-v1')
        profile=to_runtime_profile_contract(profile_entry);actor=to_actor_contract(profile_entry)
        doc=target_document(actor,profile,actions=[declaration()])
        target=load_target(doc,actor=actor,profile=profile)
        entry=offline_registry_entry(registry,profile_id=profile_entry['id'],target=target,actor=actor,profile=profile,action_id='Wave')
        return registry,entry,target,actor,profile

    def test_version_compatible_registry_roundtrip_and_parent_binding(self):
        registry,entry,*_=self.entry();doc=registry.to_dict()
        new=create_registry(doc['profiles'],attachment_pairings=doc.get('attachment_pairings'),cosmetic_pairings=doc.get('cosmetic_pairings'),offline_actions=[entry])
        self.assertEqual(load_registry(new.canonical_bytes()).canonical_bytes(),new.canonical_bytes())
        self.assertEqual(new.to_dict()['profiles'],doc['profiles'])
        self.assertEqual(get_default_registry().canonical_bytes(),registry.canonical_bytes())
        for key,value in [('profile_sha256','0'*64),('native_verification','VERIFIED'),('runtime_mapping','SUPPORTED')]:
            bad=copy.deepcopy(entry);bad.pop('canonical_sha256');bad[key]=value;bad=sealed(bad)
            with self.assertRaises(ForgeError):create_registry(doc['profiles'],offline_actions=[bad])
        with self.assertRaises(ForgeError):create_registry(doc['profiles'],offline_actions=[entry,entry])

    def test_profile_and_native_action_spoof_rejected(self):
        registry,entry,target,actor,profile=self.entry()
        with self.assertRaises(ForgeError):offline_registry_entry(registry,profile_id='absent',target=target,actor=actor,profile=profile,action_id='Wave')
        with self.assertRaises(ForgeError):offline_registry_entry(registry,profile_id=entry['profile_id'],target=target,actor=actor,profile=frozen_runtime_profile('player'),action_id='Wave')

    def test_process_seed_and_enumeration_determinism(self):
        code="from test_custom_actions import fixture; from ro_sprite_forge.core.custom_actions import action_support; from ro_sprite_forge.core.canonical import canonical_bytes; a,p,t,r,l,s=fixture(); import sys; sys.stdout.buffer.write(canonical_bytes(dict(requirements=r,support=action_support(t,actor=a,profile=p))))"
        results=[]
        for seed in ('1','987'):
            with tempfile.TemporaryDirectory() as tmp:
                env=dict(os.environ,PYTHONPATH=os.pathsep.join([str(ROOT/'src'),str(Path(__file__).resolve().parent)]),PYTHONHASHSEED=seed)
                run=subprocess.run([sys.executable,'-c',code],cwd=tmp,env=env,capture_output=True)
                self.assertEqual(run.returncode,0,run.stderr.decode());results.append(run.stdout)
        self.assertEqual(*results)
