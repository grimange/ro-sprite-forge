"""Independent accounting expectations for RSF-8; redistributable synthetic inputs."""
import copy
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.contracts import (frozen_runtime_profile, load_actor, load_target,
    single_layer_template)
from ro_sprite_forge.core.errors import ForgeError, ErrorCode
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.topology import resolve_topology, topology_work_order
from test_contracts import actor_document, target_document
from test_inventory import resources


class TopologyTests(unittest.TestCase):
    def setUp(self):
        self.profile = frozen_runtime_profile('player')
        self.actor = load_actor(actor_document(self.profile))

    def document(self, topology=None, count=6):
        d = target_document(self.actor, self.profile, count=count)
        v = d['actions'][0]['parts'][0]['views'][0]
        v['topology'] = topology
        d['actions'][0]['parts'][0]['views'] = [{**copy.deepcopy(v), 'view': i} for i in range(8)]
        return d

    def resolve(self, d, *, actor=None, profile=None, inventories=()):
        a, p = actor or self.actor, profile or self.profile
        t = load_target(d, actor=a, profile=p)
        return resolve_topology(t, actor=a, profile=p, inventories=inventories)

    def inherited(self, *, profile=None, layers=2):
        p = profile or self.profile
        i = inventory(*resources(slots=16, frames=2, layers=layers), profile=get_profile(p.category))
        a = load_actor(actor_document(p, category=p.category, resources=[{'part': 'body',
            'inventory_sha256': i['canonical_sha256'], 'act_sha256': i['sources']['act']['sha256'],
            'spr_sha256': i['sources']['spr']['sha256']}]))
        d = target_document(a, p, count=2)
        d['actions'][0]['parts'][0]['views'][0]['topology'] = {
            'kind': 'inherited', 'inventory_sha256': i['canonical_sha256'], 'slot': 15}
        return i, a, d

    def invalid(self, call, path=None, message=None):
        with self.assertRaises(ForgeError) as e: call()
        self.assertEqual(e.exception.code, ErrorCode.INVALID_INPUT)
        if path: self.assertEqual(e.exception.path, path)
        if message: self.assertIn(message, str(e.exception))

    def test_explicit_48_frames_48_layers(self):
        r = self.resolve(self.document({'kind': 'explicit', 'layers': ['body']}))
        self.assertEqual(len(r['frames']), 48)
        self.assertEqual(len(r['layers']), 48)
        self.assertEqual(r['counts']['required']['action_view_slots'], 8)
        self.assertEqual(r['counts']['required']['layer_occurrences_exact'], 48)
        self.assertTrue(all(f['layer_count'] == 1 for f in r['frames']))
        self.assertEqual(len({l['id'] for l in r['layers']}), 48)
        self.assertEqual(r['status']['specification'], 'COMPLETE_FOR_DECLARED_SCOPE')
        self.assertFalse(r['status']['full_profile_specified'])

    def test_explicit_48_frames_96_ordered_layers(self):
        r = self.resolve(self.document({'kind': 'explicit', 'layers': ['rear', 'front']}))
        self.assertEqual(len(r['frames']), 48)
        self.assertEqual(len(r['layers']), 96)
        self.assertEqual([l['role'] for l in r['layers']], ['rear', 'front'] * 48)
        self.assertEqual([l['ordinal'] for l in r['layers']], [0, 1] * 48)
        self.assertEqual(r['slots'][0]['runtime_slot'], 8)
        self.assertEqual(r['slots'][-1]['runtime_slot'], 15)
        self.assertEqual(r['counts']['required']['explicit_resolved_layers'], 96)

    def test_mixed_per_frame_topology_exact_sum_and_empty(self):
        r = self.resolve(self.document({'kind': 'per_frame', 'frames': [[], ['body'], ['rear', 'front'], ['body'], [], ['a','b','c']]}))
        self.assertEqual(len(r['frames']), 48)
        self.assertEqual(len(r['layers']), 56)  # 8 * (0+1+2+1+0+3)
        self.assertEqual([f['layer_count'] for f in r['frames'][:6]], [0,1,2,1,0,3])
        self.assertEqual(r['status']['work_order'], 'EXACT')

    def test_different_actions_views_parts_do_not_share_topology(self):
        d = self.document({'kind':'explicit','layers':['one']}, count=2)
        d['actions'][0]['parts'][0]['views'][3]['topology']['layers'] = ['a','b','c']
        optional = copy.deepcopy(d['actions'][0]);optional.update(id='Idle',requirement='OPTIONAL')
        d['actions'].append(optional)
        r = self.resolve(d)
        self.assertEqual(r['counts']['required']['layer_occurrences_exact'], 20)
        self.assertEqual(r['counts']['optional']['layer_occurrences_exact'], 20)
        self.assertEqual(len(r['layers']), 40)

    def test_missing_topology_provisional_frame_only_never_defaulted(self):
        r = self.resolve(self.document())
        self.assertEqual(len(r['frames']),48)
        self.assertEqual(r['layers'],[])
        self.assertTrue(all(f['layer_count'] is None for f in r['frames']))
        self.assertEqual(r['counts']['required']['underspecified_frames'],48)
        self.assertIsNone(r['counts']['required']['layer_occurrences_exact'])
        self.assertEqual(r['status']['work_order'],'PROVISIONAL')
        self.assertEqual({d['code'] for d in r['diagnostics']},{'UNDERSPECIFIED_LAYER_TOPOLOGY'})
        self.assertFalse(r['status']['export_ready'])

    def test_missing_count_not_inferred_from_per_frame_topology(self):
        r = self.resolve(self.document({'kind':'per_frame','frames':[['body']]*6},count=None))
        self.assertEqual(r['frames'],[])
        self.assertEqual(r['layers'],[])
        self.assertEqual(r['counts']['required']['unknown_frame_count_slots'],8)
        self.assertEqual({d['code'] for d in r['diagnostics']},{'UNDERSPECIFIED_FRAME_COUNT'})
        self.assertEqual(r['status']['work_order'],'PROVISIONAL')

    def test_zero_frames_and_zero_layers_are_explicit_valid_structures(self):
        r = self.resolve(self.document({'kind':'explicit','layers':[]},count=0))
        self.assertEqual(r['counts']['required']['layer_occurrences_exact'],0)
        self.assertEqual(r['status']['work_order'],'EXACT')
        r = self.resolve(self.document({'kind':'explicit','layers':[]}))
        self.assertEqual(len(r['frames']),48)
        self.assertEqual(r['layers'],[])
        self.assertEqual(r['status']['work_order'],'EXACT')

    def test_named_template_version_hash_and_scope_are_explicit(self):
        topo = single_layer_template('body')
        r = self.resolve(self.document(topo))
        self.assertEqual(len(r['layers']),48)
        authority = r['layers'][0]['authority']
        self.assertEqual(authority['kind'],'explicit')
        self.assertEqual(authority['template_sha256'],digest(canonical_bytes({
            'schema':'rsf.topology-template/v1','id':'single-layer','version':1,'layers':['body']})))
        for key,value in [('scope_confirmed',False),('version',2),('id','other'),('template_sha256','0'*64)]:
            bad = dict(topo);bad[key]=value
            with self.subTest(key=key):self.invalid(lambda:self.resolve(self.document(bad)))
        bad=dict(topo);bad.pop('scope_confirmed')
        self.invalid(lambda:self.resolve(self.document(bad)))

    def test_template_not_selected_implicitly_and_role_affects_hash(self):
        self.assertNotEqual(single_layer_template('body')['template_sha256'], single_layer_template('cloak')['template_sha256'])
        self.assertEqual(self.resolve(self.document())['layers'],[])
        self.invalid(lambda:single_layer_template('bad/role'),'/role')

    def test_inherited_order_source_fields_and_provenance(self):
        i,a,d=self.inherited()
        before=canonical_bytes(i)
        r=self.resolve(d,actor=a,inventories=(i,))
        self.assertEqual(len(r['frames']),2)
        self.assertEqual(len(r['layers']),4)
        source=i['actions'][15]
        self.assertEqual([l['source_layer'] for l in r['layers']], [l for f in source['frames'] for l in f['layers'] if l['visible']])
        self.assertEqual([l['source_layer_ordinal'] for l in r['layers']],[0,1,0,1])
        self.assertEqual(r['frames'][0]['constraints']['source_motion'],source['frames'][0])
        self.assertEqual(r['frames'][0]['constraints']['source_raw_delay'],source['raw_delay'])
        self.assertEqual(r['layers'][0]['authority']['source_slot'],15)
        self.assertEqual(r['layers'][0]['authority']['inventory_sha256'],i['canonical_sha256'])
        self.assertTrue(r['layers'][0]['authority']['mapping_complete'])
        self.assertEqual(r['counts']['required']['inherited_resolved_layers'],4)
        self.assertEqual(before,canonical_bytes(i))
        r['layers'][0]['source_layer']['raw']['x']=999
        self.assertEqual(before,canonical_bytes(i))

    def test_nonvisible_reference_records_not_flattened_or_authored(self):
        i,a,d=self.inherited()
        # Construct independent valid synthetic observations with an invisible placeholder.
        j=copy.deepcopy(i);j.pop('canonical_sha256')
        j['actions'][15]['frames'][0]['layers'][0]['visible']=False
        j=sealed(j)
        ad=a.to_dict();ad.pop('canonical_sha256');ad['resources'][0]['inventory_sha256']=j['canonical_sha256']
        a=load_actor(ad);d=target_document(a,self.profile,count=2)
        d['actions'][0]['parts'][0]['views'][0]['topology']={'kind':'inherited','inventory_sha256':j['canonical_sha256'],'slot':15}
        r=self.resolve(d,actor=a,inventories=(j,))
        self.assertEqual(len(r['layers']),3)
        self.assertEqual(r['layers'][0]['source_layer_ordinal'],1)
        self.assertEqual(len(r['frames'][0]['constraints']['source_motion']['layers']),2)

    def test_missing_reference_keeps_underspecified_topology(self):
        i,a,d=self.inherited()
        r=self.resolve(d,actor=a)
        self.assertEqual(len(r['frames']),2)
        self.assertEqual(r['layers'],[])
        self.assertEqual({x['code'] for x in r['diagnostics']},{'INHERITANCE_SOURCE_UNAVAILABLE','UNDERSPECIFIED_LAYER_TOPOLOGY'})
        self.assertEqual(canonical_bytes(r),canonical_bytes(self.resolve(d,actor=a)))

    def test_tampered_hash_unsupported_version_and_bad_part_rejected(self):
        i,a,d=self.inherited()
        for mutation in (lambda j:j.update(schema='rsf.inventory/v99'),
                         lambda j:j['namespace'].update(part='head'),
                         lambda j:j['sources']['act'].update(sha256='0'*64)):
            j=copy.deepcopy(i);mutation(j)
            self.invalid(lambda:self.resolve(d,actor=a,inventories=(j,)))
        j=copy.deepcopy(i);j.pop('canonical_sha256');j['namespace']['part']='head';j=sealed(j)
        ad=a.to_dict();ad.pop('canonical_sha256');ad['resources'][0]['inventory_sha256']=j['canonical_sha256'];a=load_actor(ad)
        d=target_document(a,self.profile,count=2);d['actions'][0]['parts'][0]['views'][0]['topology']={'kind':'inherited','inventory_sha256':j['canonical_sha256'],'slot':15}
        self.invalid(lambda:self.resolve(d,actor=a,inventories=(j,)),message='part mismatch')

    def test_changed_reference_not_automatically_substituted(self):
        i,a,d=self.inherited();j=copy.deepcopy(i);j.pop('canonical_sha256');j['namespace']['actor']='changed';j=sealed(j)
        r=self.resolve(d,actor=a,inventories=(j,))
        self.assertEqual(r['layers'],[])
        self.assertEqual(r['status']['work_order'],'PROVISIONAL')

    def test_frame_mismatch_rejects_no_wrap_trim_or_duplicate(self):
        i,a,d=self.inherited()
        for count in (1,3):
            d['actions'][0]['parts'][0]['views'][0]['frame_count']=count
            self.invalid(lambda:self.resolve(d,actor=a,inventories=(i,)), '/actions/0/parts/0/views/0/frame_count', 'frame count mismatch')

    def test_absent_and_conflicting_numeric_slot_rejected(self):
        i,a,d=self.inherited()
        for slot in (7,200):
            d['actions'][0]['parts'][0]['views'][0]['topology']['slot']=slot
            self.invalid(lambda:self.resolve(d,actor=a,inventories=(i,)), '/actions/0/parts/0/views/0/topology/slot')

    def test_unknown_semantics_keep_explicit_numeric_selection(self):
        p=frozen_runtime_profile('unverified');i,a,d=self.inherited(profile=p)
        d['actions'][0]['id']='custom-levitate'
        r=self.resolve(d,actor=a,profile=p,inventories=(i,))
        self.assertEqual(r['status']['work_order'],'EXACT')
        self.assertIsNone(r['slots'][0]['runtime_slot'])
        self.assertEqual(r['layers'][0]['authority']['semantic_mapping'],'UNVERIFIED')
        self.assertEqual(r['layers'][0]['authority']['source_slot'],15)
        self.assertEqual(r['slots'][0]['gameplay_reachability'],'UNVERIFIED')
        self.assertTrue(all(x['semantic_action'] is None for x in i['actions']))

    def test_conflicting_authorities_and_reference_graph_not_supported(self):
        for topology in ({'kind':'explicit','layers':['body'],'inventory_sha256':'0'*64,'slot':15},
                         {'kind':'inherited','target':'self'},
                         {'kind':'explicit','layers':['body','body']}):
            self.invalid(lambda:self.resolve(self.document(topology)))

    def test_partial_views_and_empty_action_part_declarations_not_exact(self):
        for mutate in (lambda d:d['actions'][0].update(parts=[]),
                       lambda d:d['actions'][0]['parts'][0].update(views=[]),
                       lambda d:d['actions'][0]['parts'][0]['views'][2].update(topology=None)):
            d=self.document({'kind':'explicit','layers':['body']});mutate(d)
            r=self.resolve(d)
            self.assertEqual(r['status']['work_order'],'PROVISIONAL')
            self.assertFalse(r['status']['export_ready'])
            self.assertIsNone(r['counts']['required']['layer_occurrences_exact'])
            if not r['slots']:
                self.assertIsNone(r['counts']['required']['action_view_slots_exact'])
                self.assertEqual(r['counts']['required']['unexpanded_action_part_declarations'],1)

    def test_local_topology_change_updates_only_affected_layer_identities(self):
        d=self.document({'kind':'per_frame','frames':[['body']]*6})
        old=self.resolve(d)
        d['actions'][0]['parts'][0]['views'][0]['topology']['frames'][2]=['back','body']
        new=self.resolve(d)
        oldids={l['id'] for l in old['layers']};newids={l['id'] for l in new['layers']}
        self.assertEqual(len(oldids & newids),47)
        self.assertNotEqual(old['canonical_sha256'],new['canonical_sha256'])

    def test_revision_changes_requirement_namespace(self):
        d=self.document({'kind':'explicit','layers':['body']});old=load_target(d,actor=self.actor,profile=self.profile)
        d.update(revision=2,previous_sha256=old.canonical_sha256)
        new=self.resolve(d)
        self.assertIn('/r2/',new['layers'][0]['id'])
        self.assertNotEqual(new['layers'][0]['id'],self.resolve(self.document({'kind':'explicit','layers':['body']}))['layers'][0]['id'])

    def test_repeatable_canonical_hashes_and_readable_complete_work_order(self):
        d=self.document(single_layer_template('body'))
        first=self.resolve(d);second=self.resolve(copy.deepcopy(d))
        self.assertEqual(canonical_bytes(first),canonical_bytes(second))
        payload={k:v for k,v in first.items() if k!='canonical_sha256'}
        self.assertEqual(first['canonical_sha256'],digest(canonical_bytes(payload)))
        text=topology_work_order(first)
        self.assertTrue(all(l['id'] in text for l in first['layers']))
        self.assertNotIn('/home/',canonical_bytes(first).decode())
        self.assertEqual(first['status']['artwork_coverage'],'UNASSIGNED')
        self.assertEqual(first['status']['unique_artwork_effort'],'UNKNOWN_UNTIL_ASSIGNMENTS')
        self.assertTrue(all(l['assignment']=='UNASSIGNED' and l['visual_review']=='UNVERIFIED' for l in first['layers']))

    def test_full_profile_and_scoped_are_distinct(self):
        d=self.document({'kind':'explicit','layers':['body']})
        self.assertFalse(self.resolve(d)['status']['full_profile_specified'])
        d['scope']='full'
        self.assertEqual(self.resolve(d)['status']['work_order'],'PROVISIONAL')
        d['actions']=[dict(id=a['id'],requirement='REQUIRED',parts=[{'part':'body','views':[
            {'view':v,'frame_count':1,'topology':{'kind':'explicit','layers':['body']}} for v in range(8)]}]) for a in self.profile.to_dict()['actions']]
        r=self.resolve(d)
        self.assertTrue(r['status']['full_profile_specified'])
        self.assertEqual(r['status']['work_order'],'EXACT')

    def test_monster_and_player_relationships_unchanged(self):
        for category in ('player','monster','npc'):
            p=frozen_runtime_profile(category);a=load_actor(actor_document(p,category=category))
            before=p.canonical_bytes()
            self.resolve(target_document(a,p),actor=a,profile=p)
            self.assertEqual(p.canonical_bytes(),before)
            self.assertEqual(len(p.to_dict()['parts']['relationships']),1 if category=='player' else 0)



class TopologyCliTests(unittest.TestCase):
    def test_cli_explicit_without_inventory_and_failure_cleanup(self):
        import contextlib
        import io
        import json
        from pathlib import Path
        import tempfile
        from ro_sprite_forge.cli import main
        p=frozen_runtime_profile('player');a=load_actor(actor_document(p))
        d=target_document(a,p,count=6);d['actions'][0]['parts'][0]['views'][0]['topology']=single_layer_template('body')
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for name,data in [('actor',a.to_dict()),('profile',p.to_dict()),('target',d)]:
                (root/(name+'.json')).write_bytes(canonical_bytes(data))
            args=['resolve','--actor',str(root/'actor.json'),'--profile',str(root/'profile.json'),
                  '--target',str(root/'target.json'),'--output',str(root/'out.json'),'--work-order']
            before={f.name:f.read_bytes() for f in root.iterdir()}
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(args),0)
            report=json.loads((root/'out.json').read_bytes())
            self.assertEqual(len(report['layers']),6)
            self.assertIn(report['layers'][0]['id'],out.getvalue())
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(args),3)
            self.assertEqual(json.loads(err.getvalue())['error']['code'],'INVALID_OUTPUT')
            for name,content in before.items():self.assertEqual((root/name).read_bytes(),content)
            d['actions'][0]['parts'][0]['views'][0]['topology']['scope_confirmed']=False
            (root/'target.json').write_bytes(canonical_bytes(d))
            args[args.index('--output')+1]=str(root/'failed.json')
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(args),3)
            self.assertEqual(json.loads(err.getvalue())['error']['code'],'INVALID_INPUT')
            self.assertFalse((root/'failed.json').exists())
            self.assertFalse(list(root.glob('.rsf-report-*')))


if __name__ == '__main__':unittest.main()
