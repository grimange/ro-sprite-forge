"""RSF-34 source-bound private checks; no resources/captures are published."""
from copy import deepcopy
from pathlib import Path
import sys
import unittest

for directory in (Path(__file__).resolve().parent,Path(__file__).resolve().parents[1]):
    if str(directory) not in sys.path:sys.path.insert(0,str(directory))

from test_registry_fixtures import _find_grf,_extract_from_grf,RUST_ORACLE_PATH
from test_audited_fixtures import find_fixture
from test_appearance import reseal
from test_contracts import target_document
from ro_sprite_forge.core.appearance import build_cosmetic_pairing,evaluate_appearance,preview_appearance
from ro_sprite_forge.core.canonical import canonical_bytes,digest
from ro_sprite_forge.core.compiler import verify_pair_with_rust_oracle
from ro_sprite_forge.core.contracts import load_target
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.core.registry import get_default_registry,create_registry,verify_source_hashes,to_actor_contract,to_runtime_profile_contract
from ro_sprite_forge.core.topology import resolve_topology
from ro_sprite_forge.formats.act import read_act,write_act
from ro_sprite_forge.formats.spr import read_spr,write_spr

PREFIXES={
 'genetic-female-body-v1':r'data\sprite\인간족\몸통\여\costume_1\제네릭_여_1',
 'jack-head-male-v1':r'data\sprite\악세사리\남\남_잭머리',
 'dragon-knight-male-shield-v1':r'data\sprite\방패\dragon_knight\dragon_knight_남_쉴드',
}


def resource_requirements(body,act):
    actor=to_actor_contract(body);rp=to_runtime_profile_contract(body)
    actions=[dict(id=a['id'],requirement='REQUIRED',parts=[dict(part='body',views=[dict(view=s%8,
        frame_count=len(act['actions'][s]),topology=dict(kind='explicit',layers=['body-layer'])) for s in a['slots']])])
        for a in body['actions'] if a['mapping']=='SUPPORTED']
    return resolve_topology(load_target(target_document(actor,rp,actions=actions),actor=actor,profile=rp),actor=actor,profile=rp)


def private_case(body_id,child_id,resources,representation):
    default=get_default_registry();body=default.get_profile(body_id);child=default.get_profile(child_id)
    attachments=[]
    if representation!='COMPLETE_VISUAL_BODY':
        template=default.find_pairing('novice-male-body-v1',child_id)
        template.update(id='actual-'+child_id,parent_profile_id=body_id,
                        compatibility={k:'UNVERIFIED' for k in template['compatibility']})
        # This new two-resource preview explicitly scopes out the separate head chain.
        template['layer_order']=['body',template['child_part']]
        template['evidence']=[]
        attachments=[template]
    pairing=build_cosmetic_pairing(id='actual-cosmetic',body=body,appearance=child,representation=representation,
        appearance_part=child['parts']['declared'][0],attachment_pairing=attachments[0] if attachments else None,
        action_views=[dict(action=a['id'],view=s%8,body_slot=s,appearance_slot=s) for a in body['actions'] for s in a['slots']])
    reg=create_registry([body,child],attachment_pairings=attachments,cosmetic_pairings=[pairing])
    req=resource_requirements(body,read_act(resources[body_id][0]))
    report=evaluate_appearance(reg,'actual-cosmetic',requirements=req,resources=resources,character_id='private-C',gameplay_job='external-J')
    return reg,req,report


class PrivateAppearanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        grf=_find_grf()
        if grf is None:raise unittest.SkipTest('Private lawful GRF unavailable')
        cls.resources={pid:_extract_from_grf(grf,prefix) for pid,prefix in PREFIXES.items()}
        if not all(cls.resources.values()):raise unittest.SkipTest('Approved private cosmetic resources unavailable')
        for pid,pair in cls.resources.items():verify_source_hashes(get_default_registry().get_profile(pid),*pair)

    def test_01_actual_genetic_and_jack_all_slots_and_selected_geometry(self):
        ids=['genetic-female-body-v1','jack-head-male-v1'];data={pid:self.resources[pid] for pid in ids}
        before={pid:tuple(digest(b) for b in pair) for pid,pair in data.items()}
        reg,req,report=private_case(*ids,data,'HEAD_ACCESSORY')
        self.assertEqual(report['counts'],dict(requested=104,supported=104,unsupported=0))
        self.assertEqual(report['full_profile_status'],'SUPPORTED')
        self.assertEqual(report['dimensions']['native_korangar'],'UNVERIFIED')
        rendered=preview_appearance(reg,'actual-cosmetic',requirements=req,resources=data,
            character_id='private-C',action='Walk',view=0,frame=0)
        ba,ca=[read_act(data[pid][0]) for pid in ids]
        dx=ba['actions'][8][0]['anchors'][0]['x']-ca['actions'][8][0]['anchors'][0]['x']
        dy=ba['actions'][8][0]['anchors'][0]['y']-ca['actions'][8][0]['anchors'][0]['y']
        parts=rendered['report']['parts'];self.assertEqual([p['part'] for p in parts],['body','accessory'])
        for got,original in zip(parts[1]['clips'],ca['actions'][8][0]['clips']):
            expected=dict(original,x=original['x']+dx,y=original['y']+dy);self.assertEqual(got,expected)
        self.assertIsNotNone(rendered['image'].getbbox())
        self.assertEqual(before,{pid:tuple(digest(b) for b in pair) for pid,pair in data.items()})

    def test_02_exact_genetic_shield_partial_pickup_not_dragon_knight_body(self):
        ids=['genetic-female-body-v1','dragon-knight-male-shield-v1'];data={pid:self.resources[pid] for pid in ids}
        reg,req,report=private_case(*ids,data,'EQUIPMENT_VISUAL')
        self.assertEqual(report['counts'],dict(requested=104,supported=96,unsupported=8))
        self.assertEqual(report['status'],'PARTIAL')
        failed=[d for d in report['slot_details'] if d['status']=='UNSUPPORTED']
        self.assertEqual(sorted(d['mapping']['body_slot'] for d in failed),list(range(24,32)))
        self.assertTrue(all(d['diagnostics']==['MISMATCHED_FRAME_COUNT'] for d in failed))
        self.assertEqual(report['identity']['underlying_body']['id'],'genetic-female-body-v1')
        preview_appearance(reg,'actual-cosmetic',requirements=req,resources=data,character_id='C',action='Walk',view=0,frame=0)
        with self.assertRaisesRegex(ForgeError,'UNSUPPORTED_COSTUME_SCOPE'):
            preview_appearance(reg,'actual-cosmetic',requirements=req,resources=data,character_id='C',action='Pickup',view=0,frame=0)

    def test_03_previous_novice_label_cannot_authorize_genetic_bytes(self):
        default=get_default_registry()
        pairing=default.find_pairing('novice-male-body-v1','dragon-knight-male-shield-v1')
        self.assertEqual(pairing['parent_profile_id'],'novice-male-body-v1')
        self.assertEqual(pairing['status'],'PARTIAL')
        self.assertFalse(any(p['resource_kind']=='body' and p['gameplay_job']=='dragon_knight' for p in default.to_dict()['profiles']))
        with self.assertRaisesRegex(ForgeError,'SOURCE_HASH_MISMATCH'):
            verify_source_hashes(default.get_profile(pairing['parent_profile_id']),*self.resources['genetic-female-body-v1'])

    def test_04_rust_source_structure_pixels_and_noop_bytes(self):
        if not RUST_ORACLE_PATH.is_file():self.skipTest('Independent Rust oracle unavailable')
        for pid,pair in self.resources.items():
            with self.subTest(profile=pid):
                result=verify_pair_with_rust_oracle(*pair,RUST_ORACLE_PATH)
                self.assertEqual(result['result'],'AGREEMENT')
                self.assertEqual(write_act(read_act(pair[0])),pair[0])
                self.assertEqual(write_spr(read_spr(pair[1])),pair[1])

    def test_05_alternate_body_retains_separate_novice_head(self):
        paths=[find_fixture(name) for name in ('novice_body_act','novice_body_spr','novice_head_act','novice_head_spr')]
        if not all(paths):self.skipTest('Private Novice quartet unavailable')
        original=tuple(p.read_bytes() for p in paths)
        body_id='novice-male-body-v1';child_id='genetic-female-body-v1'
        data={body_id:original[:2],child_id:self.resources[child_id]}
        reg,req,report=private_case(body_id,child_id,data,'COMPLETE_VISUAL_BODY')
        self.assertEqual(report['counts']['supported'],104)
        # Separate head needs an explicit new host binding: neither borrowed nor flattened.
        d=reg.to_dict();d['profiles'].append(get_default_registry().get_profile('novice-male-head-v1'))
        from ro_sprite_forge.core.registry import load_registry
        reg=load_registry(reseal(d))
        with self.assertRaisesRegex(ForgeError,'UNRESOLVED_VISUAL_HOST_ATTACHMENTS'):
            preview_appearance(reg,'actual-cosmetic',requirements=req,resources=data,character_id='C',
                               action='Walk',view=0,frame=0,head_profile='novice-male-head-v1')
        self.assertEqual(tuple(p.read_bytes() for p in paths),original)


if __name__=='__main__':unittest.main()
