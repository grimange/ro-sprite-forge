"""Optional contract compatibility with private, hash-pinned source inventories."""
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import (frozen_runtime_profile, load_actor, load_target, reference, assess_target)
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from test_audited_fixtures import find_fixture, AUDITED_HASHES


class PrivateContractTests(unittest.TestCase):
    def check_actor(self, category, names):
        profile=frozen_runtime_profile(category)
        observations=[]
        resources=[]
        for part,name in names:
            act,spr=find_fixture(name+'_act'),find_fixture(name+'_spr')
            if act is None or spr is None:
                self.skipTest('Audited private pair unavailable: '+name)
            act_bytes,spr_bytes=act.read_bytes(),spr.read_bytes()
            self.assertEqual(digest(act_bytes),AUDITED_HASHES[name+'_act'])
            self.assertEqual(digest(spr_bytes),AUDITED_HASHES[name+'_spr'])
            observed=inventory(act_bytes,spr_bytes,actor='reference',part=part,profile=get_profile(category))
            observations.append(observed)
            resources.append(dict(part=part,inventory_sha256=observed['canonical_sha256'],act_sha256=observed['sources']['act']['sha256'],spr_sha256=observed['sources']['spr']['sha256']))
        before=[canonical_bytes(o) for o in observations]
        actor=load_actor(dict(schema='rsf.actor/v1',id='reference',revision=1,previous_sha256=None,category=category,
            gameplay_job='Novice' if category=='player' else None,
            visual=dict(body_family='novice-original' if category=='player' else 'orc-skeleton',sex='male' if category=='player' else None,body_variant=None,costume=None),
            parts=[part for part,name in names],runtime_profile=reference(profile),action_profile='reference-observed',
            compatibility=dict(status='UNVERIFIED',declarations=[]),resources=resources))
        actions=[]
        for action in profile.to_dict()['actions']:
            actions.append(dict(id=action['id'],requirement='REQUIRED',parts=[dict(part=part,views=[
                dict(view=v,frame_count=len(observed['actions'][action['group']*8+v]['frames']),
                     topology=dict(kind='inherited',inventory_sha256=observed['canonical_sha256'],slot=action['group']*8+v))
                for v in range(8)]) for (part,name),observed in zip(names,observations)]))
        target=load_target(dict(schema='rsf.target/v2',id='reference-target',revision=1,previous_sha256=None,actor=reference(actor),
            runtime_profile=reference(profile),scope='full',parts=actor.to_dict()['parts'],compatibility=dict(status='UNVERIFIED',declarations=[]),actions=actions),actor=actor,profile=profile)
        assessment=assess_target(target,actor=actor,profile=profile,inventories=tuple(observations))
        self.assertTrue(assessment['status']['full_profile_specified'])
        self.assertEqual(assessment['status']['artwork_coverage'],'UNASSIGNED')
        self.assertEqual(before,[canonical_bytes(o) for o in observations])
        self.assertEqual(digest(act.read_bytes()),AUDITED_HASHES[names[-1][1]+'_act'])
        self.assertEqual(digest(spr.read_bytes()),AUDITED_HASHES[names[-1][1]+'_spr'])
        return observations

    def test_novice_body_head_remain_distinct(self):
        body,head=self.check_actor('player',[('body','novice_body'),('head','novice_head')])
        self.assertEqual(body['summary']['action_slots'],104)
        self.assertEqual(body['summary']['frame_occurrences'],456)
        self.assertEqual(body['summary']['referenced_images'],110)
        self.assertEqual(head['summary']['referenced_images'],15)
        self.assertNotEqual(body['sources'],head['sources'])

    def test_orc_multilayer_contract_does_not_rewrite_inventory(self):
        observed,=self.check_actor('monster',[('body','orc_skeleton')])
        self.assertEqual(observed['summary']['frame_occurrences'],512)
        self.assertEqual(observed['summary']['visible_layer_references'],1776)
        self.assertEqual(observed['summary']['stored_images'],57)
