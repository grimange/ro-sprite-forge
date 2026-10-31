"""Hash-pinned private topology checks; fixtures remain outside distribution."""
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, load_target, reference
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.topology import resolve_topology
from test_audited_fixtures import find_fixture, AUDITED_HASHES


def reference_requirements(category, names):
    profile=frozen_runtime_profile(category)
    observations=[]
    for part,name in names:
        act,spr=find_fixture(name+'_act'),find_fixture(name+'_spr')
        if act is None or spr is None: raise unittest.SkipTest('Private pair unavailable: '+name)
        ab,sb=act.read_bytes(),spr.read_bytes()
        assert digest(ab)==AUDITED_HASHES[name+'_act'] and digest(sb)==AUDITED_HASHES[name+'_spr']
        observations.append(inventory(ab,sb,actor='reference',part=part,profile=get_profile(category)))
    actor=load_actor({'schema':'rsf.actor/v1','id':'reference','revision':1,'previous_sha256':None,
        'category':category,'gameplay_job':None,'visual':dict(body_family='audited',sex=None,body_variant=None,costume=None),
        'parts':[p for p,n in names],'runtime_profile':reference(profile),'action_profile':'audited-observation',
        'compatibility':dict(status='UNVERIFIED',declarations=[]),'resources':[
            dict(part=o['namespace']['part'],inventory_sha256=o['canonical_sha256'],
                 act_sha256=o['sources']['act']['sha256'],spr_sha256=o['sources']['spr']['sha256']) for o in observations]})
    actions=[dict(id=a['id'],requirement='REQUIRED',parts=[dict(part=o['namespace']['part'],views=[
        dict(view=v,frame_count=len(o['actions'][a['group']*8+v]['frames']),topology=dict(kind='inherited',
        inventory_sha256=o['canonical_sha256'],slot=a['group']*8+v)) for v in range(8)]) for o in observations])
        for a in profile.to_dict()['actions']]
    target=load_target(dict(schema='rsf.target/v2',id='reference-topology',revision=1,previous_sha256=None,
        actor=reference(actor),runtime_profile=reference(profile),scope='full',parts=actor.to_dict()['parts'],
        compatibility=dict(status='UNVERIFIED',declarations=[]),actions=actions),actor=actor,profile=profile)
    return actor,profile,target,observations


class PrivateTopologyTests(unittest.TestCase):
    def check(self,category,names):
        actor,profile,target,observed=reference_requirements(category,names)
        before=[canonical_bytes(o) for o in observed]
        r=resolve_topology(target,actor=actor,profile=profile,inventories=tuple(observed))
        self.assertEqual(r['status']['work_order'],'EXACT')
        self.assertTrue(r['status']['full_profile_specified'])
        self.assertEqual(len(r['layers']),sum(o['summary']['visible_layer_references'] for o in observed))
        self.assertEqual(len(r['frames']),sum(o['summary']['frame_occurrences'] for o in observed))
        lookup={o['canonical_sha256']:o for o in observed}
        for layer in r['layers']:
            authority=layer['authority'];o=lookup[authority['inventory_sha256']]
            source=o['actions'][authority['source_slot']]['frames'][layer['frame']]['layers'][layer['source_layer_ordinal']]
            self.assertEqual(layer['source_layer'],source)
        again=resolve_topology(target,actor=actor,profile=profile,inventories=tuple(reversed(observed)))
        self.assertEqual(canonical_bytes(r),canonical_bytes(again))
        self.assertEqual(before,[canonical_bytes(o) for o in observed])
        self.assertEqual(r['status']['artwork_coverage'],'UNASSIGNED')
        return r,observed

    def test_novice_body_head_separate_inherited_topology(self):
        r,(body,head)=self.check('player',[('body','novice_body'),('head','novice_head')])
        self.assertEqual(len(r['frames']),912)
        self.assertEqual(body['summary']['referenced_images'],110)
        self.assertEqual(body['summary']['distinct_referenced_contents'],108)
        self.assertEqual(head['summary']['referenced_images'],15)
        self.assertEqual(len({l['part'] for l in r['layers']}),2)

    def test_orc_multilayer_full_topology_order_and_inventory(self):
        r,(orc,)=self.check('monster',[('body','orc_skeleton')])
        self.assertEqual(len(r['frames']),512)
        self.assertEqual(len(r['layers']),1776)
        self.assertEqual(r['counts']['required']['inherited_resolved_layers'],1776)
        self.assertEqual(orc['summary']['referenced_images'],55)
        self.assertEqual(orc['summary']['stored_images'],57)
        self.assertEqual([int(i.rsplit('/i',1)[1]) for i in orc['unused_image_ids']],[36,39])
        self.assertGreater(max(f['layer_count'] for f in r['frames']),1)
