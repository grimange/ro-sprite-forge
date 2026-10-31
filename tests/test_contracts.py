"""Public RSF-7 contracts: no private artwork or runtime required."""

import copy
import json
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.contracts import (assess_target, contract_schema, frozen_runtime_profile,
    load_actor, load_runtime_profile, load_target, reference)
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from test_inventory import resources


def unknown_compatibility():
    return {'status': 'UNVERIFIED', 'declarations': []}


def actor_document(profile=None, *, category='player', parts=None, resources=None):
    profile = profile or frozen_runtime_profile(category)
    return {'schema': 'rsf.actor/v1', 'id': 'custom-actor', 'revision': 1, 'previous_sha256': None,
            'category': category, 'gameplay_job': 'job-82017',
            'visual': {'body_family': 'unfamiliar-family', 'sex': None, 'body_variant': 'adult', 'costume': 'winter'},
            'parts': parts or ['body'], 'runtime_profile': reference(profile),
            'action_profile': 'operator-choreography', 'compatibility': unknown_compatibility(),
            'resources': resources or []}


def target_document(actor, profile, *, actions=None, count=3, topology=True, scope='scoped'):
    return {'schema': 'rsf.target/v2', 'id': 'winter-walk', 'revision': 1, 'previous_sha256': None,
            'actor': reference(actor), 'runtime_profile': reference(profile), 'scope': scope,
            'parts': actor.to_dict()['parts'], 'compatibility': unknown_compatibility(),
            'actions': actions if actions is not None else [{'id': 'Walk', 'requirement': 'REQUIRED', 'parts': [
                {'part': 'body', 'views': [{'view': 7, 'frame_count': count,
                 'topology': {'kind': 'explicit', 'layers': ['torso', 'cloak']} if topology else None}]}]}]}


class ContractTests(unittest.TestCase):
    def setUp(self):
        self.profile = frozen_runtime_profile('player')
        self.actor = load_actor(actor_document(self.profile))

    def target(self, document=None, **kwargs):
        return load_target(document or target_document(self.actor, self.profile, **kwargs), actor=self.actor, profile=self.profile)

    def assess(self, document=None, **kwargs):
        return assess_target(self.target(document, **kwargs), actor=self.actor, profile=self.profile)

    def invalid(self, call, path=None):
        with self.assertRaises(ForgeError) as caught:
            call()
        self.assertEqual(caught.exception.code, ErrorCode.INVALID_INPUT)
        if path:
            self.assertEqual(caught.exception.path, path)
        return caught.exception

    def test_actor_identity_dimensions_and_arbitrary_names(self):
        document = self.actor.to_dict()
        self.assertNotEqual(document['gameplay_job'], document['visual']['body_family'])
        self.assertEqual(document['visual']['costume'], 'winter')
        self.assertEqual(document['action_profile'], 'operator-choreography')
        self.assertIsNone(document['visual']['sex'])
        self.assertEqual(document['compatibility']['status'], 'UNVERIFIED')
        for job in ('novice', 'never-before-seen-job', 'custom-999999'):
            a = actor_document(self.profile); a['gameplay_job'] = job
            self.assertEqual(load_actor(a).to_dict()['gameplay_job'], job)

    def test_categories_and_player_only_part_relationships(self):
        for category in ('player', 'npc', 'monster', 'unverified'):
            profile = frozen_runtime_profile(category)
            actor = load_actor(actor_document(profile, category=category))
            self.assertEqual(actor.category, category)
            p = profile.to_dict()
            self.assertEqual(len(p['parts']['relationships']), 1 if category == 'player' else 0)
            self.assertEqual(p['parts']['order'], ['body', 'head'] if category == 'player' else [] if category == 'unverified' else ['body'])
        monster = frozen_runtime_profile('monster').to_dict()
        monster.pop('canonical_sha256')
        monster['parts'] = self.profile.to_dict()['parts']
        self.invalid(lambda: load_runtime_profile(monster), '/parts/relationships/0')

    def test_frozen_export_preserves_provenance_and_unknown_reachability(self):
        for category in ('player', 'npc', 'monster'):
            old = get_profile(category)
            before = canonical_bytes(old)
            new = frozen_runtime_profile(category).to_dict()
            self.assertEqual(new['legacy_profile_sha256'], old['canonical_sha256'])
            self.assertEqual(new['source']['revision'], old['revision'])
            ids = {a['action'] for a in old['actions']}
            expected_timing = {key: [a for a in value if a in ids] if key in ('looping', 'nonlooping') else value
                               for key, value in old['timing'].items()}
            self.assertEqual(new['timing'], expected_timing)
            self.assertEqual(new['resolution'], old['resolution'])
            self.assertEqual(new['actions'][1]['slots'], list(range(8,16)))
            self.assertTrue(all(a['reachability'] == 'UNVERIFIED' for a in new['actions']))
            self.assertEqual(canonical_bytes(old), before)

    def test_unknown_profile_custom_actions_do_not_get_novice_counts(self):
        p = frozen_runtime_profile('unverified')
        a = load_actor(actor_document(p, category='unverified'))
        doc = target_document(a, p, count=17)
        doc['actions'][0]['id'] = 'levitate-custom'
        t = load_target(doc, actor=a, profile=p)
        result = assess_target(t, actor=a, profile=p)
        self.assertEqual(result['runtime'], [{'action': 'levitate-custom', 'mapping':'UNVERIFIED', 'reachability':'UNVERIFIED','slots':[]}])
        self.assertEqual(t.to_dict()['actions'][0]['parts'][0]['views'][0]['frame_count'], 17)
        self.assertEqual(result['status']['artwork_coverage'], 'UNASSIGNED')
        doc['actions'][0]['parts'][0]['views'][0]['frame_count'] = None
        r = assess_target(load_target(doc, actor=a, profile=p), actor=a, profile=p)
        self.assertIn('UNDERSPECIFIED_FRAME_COUNT', [d['code'] for d in r['diagnostics']])

    def test_unfamiliar_import_has_numeric_slots_and_unknown_semantics(self):
        i = inventory(*resources(slots=24, frames=7, layers=2), actor='custom-999999')
        before = canonical_bytes(i)
        p = frozen_runtime_profile('unverified')
        d = actor_document(p, category='unverified', resources=[{
            'part':'body', 'inventory_sha256':i['canonical_sha256'],
            'act_sha256':i['sources']['act']['sha256'],'spr_sha256':i['sources']['spr']['sha256']}])
        a = load_actor(d)
        self.assertTrue(all(x['semantic_action'] is None and x['mapping_status'] == 'UNVERIFIED' for x in i['actions']))
        self.assertEqual(i['summary']['frame_occurrences'], 168)
        self.assertEqual(a.to_dict()['resources'][0]['inventory_sha256'], i['canonical_sha256'])
        self.assertEqual(before, canonical_bytes(i))

    def test_explicit_single_and_ordered_multilayer_topology(self):
        doc = target_document(self.actor, self.profile)
        view = doc['actions'][0]['parts'][0]['views'][0]
        for roles in (['body'], ['back', 'body', 'front']):
            view['topology'] = {'kind':'explicit','layers':roles}
            t = self.target(doc)
            self.assertEqual(t.to_dict()['actions'][0]['parts'][0]['views'][0]['topology']['layers'], roles)
            self.assertTrue(assess_target(t,actor=self.actor,profile=self.profile)['status']['declared_scope_specified'])
        view['topology'] = {'kind':'per_frame','frames':[['back','front'],[],['body']]}
        self.assertTrue(self.assess(doc)['status']['declared_scope_specified'])
        view['topology']['frames'].pop()
        self.invalid(lambda:self.target(doc), '/actions/0/parts/0/views/0/topology/frames')

    def test_missing_counts_and_topology_have_precise_diagnostics(self):
        for count, topology, expected in [(None,True,{'UNDERSPECIFIED_FRAME_COUNT'}),
                 (3,False,{'UNDERSPECIFIED_LAYER_TOPOLOGY'}),
                 (None,False,{'UNDERSPECIFIED_FRAME_COUNT','UNDERSPECIFIED_LAYER_TOPOLOGY'})]:
            r = self.assess(count=count,topology=topology)
            self.assertEqual({d['code'] for d in r['diagnostics']}, expected)
            self.assertTrue(all(d['path'].startswith('/actions/0/parts/0/views/0/') for d in r['diagnostics']))
            self.assertFalse(r['status']['declared_scope_specified'])
        doc=target_document(self.actor,self.profile);doc['actions'][0]['parts'][0]['views']=[]
        self.assertFalse(self.assess(doc)['status']['declared_scope_specified'])
        doc['actions'][0]['parts']=[]
        self.assertFalse(self.assess(doc)['status']['declared_scope_specified'])

    def test_required_optional_excluded_and_scoped_full(self):
        doc=target_document(self.actor,self.profile)
        optional=copy.deepcopy(doc['actions'][0]);optional.update(id='Idle',requirement='OPTIONAL')
        doc['actions'] += [optional, {'id':'Attack1','requirement':'OUT_OF_SCOPE','parts':[]}]
        result=self.assess(doc)
        self.assertTrue(result['status']['declared_scope_specified'])
        self.assertFalse(result['status']['full_profile_specified'])
        self.assertEqual([a['action'] for a in result['runtime']],['Walk','Idle'])
        doc['scope']='full'
        self.assertIn('INCOMPLETE_FULL_PROFILE',[d['code'] for d in self.assess(doc)['diagnostics']])
        doc['actions']=[{'id':a['id'],'requirement':'REQUIRED','parts':[{'part':'body','views':[
            {'view':v,'frame_count':1,'topology':{'kind':'explicit','layers':['body']}} for v in range(8)]}]}
            for a in self.profile.to_dict()['actions']]
        self.assertTrue(self.assess(doc)['status']['full_profile_specified'])
        doc['actions'][0]['requirement']='OPTIONAL'
        self.assertFalse(self.assess(doc)['status']['full_profile_specified'])

    def test_custom_unmapped_unsupported_and_evidenced_runtime_actions(self):
        p=self.profile.to_dict();p.pop('canonical_sha256')
        p['actions'].append({'id':'custom-spin','group':None,'slots':[],'mapping':'UNSUPPORTED','reachability':'UNSUPPORTED','evidence':[p['source']['evidence'][0]['sha256']]})
        p['profile_version']='1.1.0'
        profile=load_runtime_profile(p)
        actor=load_actor(actor_document(profile))
        doc=target_document(actor,profile);doc['actions'][0]['id']='custom-spin'
        report=assess_target(load_target(doc,actor=actor,profile=profile),actor=actor,profile=profile)
        self.assertEqual(report['runtime'][0]['mapping'],'UNSUPPORTED')
        p['actions'][-1].update(group=13,slots=list(range(104,112)),mapping='SUPPORTED',reachability='UNVERIFIED')
        self.assertEqual(load_runtime_profile(p).to_dict()['actions'][-1]['slots'],list(range(104,112)))
        p['actions'][-1]['evidence']=[]
        self.invalid(lambda:load_runtime_profile(p),'/actions/13/evidence')

    def test_unknown_numeric_group_retains_unverified_semantics(self):
        p=frozen_runtime_profile('unverified').to_dict();p.pop('canonical_sha256')
        p['views']=list(range(8));p['actions']=[dict(id=None,group=17,slots=list(range(136,144)),mapping='UNVERIFIED',reachability='UNVERIFIED',evidence=[])]
        parsed=load_runtime_profile(p).to_dict()
        self.assertIsNone(parsed['actions'][0]['id'])
        p['actions'][0]['mapping']='SUPPORTED'
        self.invalid(lambda:load_runtime_profile(p))

    def test_profile_conflicts_and_slot_errors(self):
        mutations=[lambda p:p['actions'][1].update(group=0),
                   lambda p:p['actions'][0].update(slots=[99]),
                   lambda p:p['actions'][0].update(evidence=['0'*64]),
                   lambda p:p.update(resolution=None),
                   lambda p:p['parts']['relationships'][0].update(child='missing')]
        for change in mutations:
            p=self.profile.to_dict();p.pop('canonical_sha256');change(p)
            with self.subTest(change=change):self.invalid(lambda:load_runtime_profile(p))

    def test_reference_identity_versions_hashes_and_categories(self):
        for key in ('id','profile_version','canonical_sha256'):
            d=target_document(self.actor,self.profile)
            d['runtime_profile'][key]={'id':'wrong','profile_version':'2.0.0','canonical_sha256':'0'*64}[key]
            self.invalid(lambda:self.target(d),'/runtime_profile')
        d=actor_document(self.profile);d['category']='monster';a=load_actor(d)
        self.invalid(lambda:load_target(target_document(a,self.profile),actor=a,profile=self.profile),'/actor/category')
        d=target_document(self.actor,self.profile);d['actor']['revision']=2
        self.invalid(lambda:self.target(d),'/actor')

    def test_revision_chain_is_explicit_and_old_record_immutable(self):
        before=self.actor.canonical_bytes()
        d=self.actor.to_dict();d.pop('canonical_sha256');d.update(revision=2,previous_sha256=self.actor.canonical_sha256)
        d['visual']['costume']='summer'
        newer=load_actor(d,previous=self.actor)
        self.assertEqual(newer.id,self.actor.id)
        self.assertNotEqual(newer.canonical_sha256,self.actor.canonical_sha256)
        self.assertEqual(before,self.actor.canonical_bytes())
        d['revision']=3
        self.invalid(lambda:load_actor(d,previous=self.actor),'/revision')
        d['revision']=2;d['previous_sha256']='0'*64
        self.invalid(lambda:load_actor(d,previous=self.actor),'/previous_sha256')
        old=self.target();v=old.to_dict();v.pop('canonical_sha256');v.update(revision=2,previous_sha256=old.canonical_sha256)
        v['actions'][0]['parts'][0]['views'][0]['frame_count']=9
        new=load_target(v,actor=self.actor,profile=self.profile,previous=old)
        self.assertNotEqual(new.canonical_sha256,old.canonical_sha256)
        self.assertEqual(old.to_dict()['actions'][0]['parts'][0]['views'][0]['frame_count'],3)

    def test_schema_versions_and_seals_reject_silent_migration(self):
        for schema in ('rsf.actor/v2','rsf.target/v1','rsf.runtime-profile/v99'):
            self.invalid(lambda:contract_schema(schema),'/schema')
        d=actor_document(self.profile);d['schema']='rsf.actor/v99'
        self.invalid(lambda:load_actor(d),'/schema')
        d=self.actor.to_dict();d['visual']['costume']='tampered'
        self.invalid(lambda:load_actor(d),'/canonical_sha256')

    def test_malformed_contract_fields_are_not_normalized(self):
        cases=[(lambda d:d.update(typo=1),'/typo'),(lambda d:d.pop('visual'),'/visual'),
               (lambda d:d.update(revision=True),'/revision'),
               (lambda d:d['visual'].update(body_family='bad/name'),'/visual/body_family'),
               (lambda d:d.update(parts=['body','body']),'/parts'),
               (lambda d:d.update(previous_sha256='0'*64),'/previous_sha256')]
        for mutation,path in cases:
            d=actor_document(self.profile);mutation(d)
            with self.subTest(path=path):self.invalid(lambda:load_actor(d),path)
        doc=target_document(self.actor,self.profile)
        for count in (True,-1,4097,1.0,'3'):
            d=copy.deepcopy(doc);d['actions'][0]['parts'][0]['views'][0]['frame_count']=count
            self.invalid(lambda:self.target(d),'/actions/0/parts/0/views/0/frame_count')

    def test_conflicting_target_parts_actions_views_layers(self):
        mutations=[lambda d:d['actions'].append(copy.deepcopy(d['actions'][0])),
            lambda d:d['actions'][0]['parts'][0]['views'].append(copy.deepcopy(d['actions'][0]['parts'][0]['views'][0])),
            lambda d:d['actions'][0]['parts'][0].update(part='absent'),
            lambda d:d['actions'][0]['parts'][0]['views'][0].update(topology={'kind':'explicit','layers':['body','body']}),
            lambda d:d['actions'][0].update(requirement='OUT_OF_SCOPE')]
        for mutation in mutations:
            d=target_document(self.actor,self.profile);mutation(d)
            self.invalid(lambda:self.target(d))

    def test_deterministic_bytes_hash_and_snapshot_isolation(self):
        doc=actor_document(self.profile)
        first=load_actor(doc);second=load_actor(dict(reversed(list(doc.items()))))
        self.assertEqual(first.canonical_bytes(),second.canonical_bytes())
        self.assertEqual(first.canonical_sha256,second.canonical_sha256)
        doc['visual']['costume']='mutated'
        detached=first.to_dict();detached['parts'].append('mutated')
        self.assertEqual(first.to_dict()['parts'],['body'])
        self.assertEqual(first.to_dict()['visual']['costume'],'winter')
        target=self.target()
        self.assertEqual(target.canonical_bytes(),self.target().canonical_bytes())
        self.assertEqual(canonical_bytes(self.assess()),canonical_bytes(self.assess()))
        body={k:v for k,v in target.to_dict().items() if k!='canonical_sha256'}
        self.assertEqual(digest(canonical_bytes(body)),target.canonical_sha256)

    def test_compatibility_unknown_and_evidence_backed_declarations(self):
        d=actor_document(self.profile)
        d['compatibility']={'status':'SUPPORTED','declarations':[]}
        self.invalid(lambda:load_actor(d),'/compatibility/status')
        d['compatibility']['declarations']=[{'id':'weapon-family','status':'SUPPORTED','evidence':['1'*64]}]
        self.assertEqual(load_actor(d).to_dict()['compatibility']['status'],'SUPPORTED')
        d['compatibility']['declarations'][0]['evidence']=[]
        self.invalid(lambda:load_actor(d),'/compatibility/declarations/0/evidence')

    def test_declaration_budgets_are_bounded(self):
        d=target_document(self.actor,self.profile,count=4096)
        d['actions'][0]['parts'][0]['views'][0]['topology']['layers']=['r'+str(i) for i in range(65)]
        self.invalid(lambda:self.target(d),'/actions')

    def test_inheritance_requires_exact_inventory_part_bytes_slot_and_count(self):
        observed=inventory(*resources(slots=16,frames=2,layers=2),actor='audited',profile=get_profile('player'))
        before=canonical_bytes(observed)
        actor=load_actor(actor_document(self.profile,resources=[{'part':'body','inventory_sha256':observed['canonical_sha256'],
                'act_sha256':observed['sources']['act']['sha256'],'spr_sha256':observed['sources']['spr']['sha256']}]))
        d=target_document(actor,self.profile,count=2)
        v=d['actions'][0]['parts'][0]['views'][0]
        v['topology']={'kind':'inherited','inventory_sha256':observed['canonical_sha256'],'slot':15}
        t=load_target(d,actor=actor,profile=self.profile)
        missing=assess_target(t,actor=actor,profile=self.profile)
        self.assertEqual(missing['diagnostics'][0]['code'],'INHERITANCE_SOURCE_UNAVAILABLE')
        r=assess_target(t,actor=actor,profile=self.profile,inventories=(observed,))
        self.assertTrue(r['status']['declared_scope_specified'])
        self.assertEqual(canonical_bytes(observed),before)
        v['topology']['slot']=7
        t=load_target(d,actor=actor,profile=self.profile)
        self.invalid(lambda:assess_target(t,actor=actor,profile=self.profile,inventories=(observed,)), '/actions/0/parts/0/views/0/topology/slot')
        v['topology']['slot']=15;v['frame_count']=3
        t=load_target(d,actor=actor,profile=self.profile)
        self.invalid(lambda:assess_target(t,actor=actor,profile=self.profile,inventories=(observed,)), '/actions/0/parts/0/views/0/frame_count')
        v['frame_count']=2;v['topology']['inventory_sha256']='0'*64
        self.invalid(lambda:load_target(d,actor=actor,profile=self.profile))

    def test_all_bundled_schemas_are_closed_and_versioned(self):
        for schema in ('rsf.actor/v1','rsf.runtime-profile/v2','rsf.target/v2'):
            value=contract_schema(schema)
            self.assertFalse(value['additionalProperties'])
            self.assertEqual(value['properties']['schema']['const'],schema)
            self.assertEqual(value['$schema'],'https://json-schema.org/draft/2020-12/schema')
            value['properties'].clear()
            self.assertTrue(contract_schema(schema)['properties'])


class ProfileVersionTests(unittest.TestCase):
    def test_sealed_malformed_inheritance_has_typed_field_errors(self):
        profile = frozen_runtime_profile('player')
        original = inventory(*resources(slots=16, frames=2, layers=2), profile=get_profile('player'))
        mutations = [(lambda d: d.pop('namespace'), '/namespace'),
                     (lambda d: d.update(namespace=None), '/namespace'),
                     (lambda d: d['sources']['act'].update(sha256=None), '/sources/act/sha256'),
                     (lambda d: d['actions'].__setitem__(0, None), '/actions/0'),
                     (lambda d: d['actions'][0].pop('slot'), '/actions/0/slot'),
                     (lambda d: d['actions'][0].pop('frames'), '/actions/0/frames'),
                     (lambda d: d['actions'][0]['frames'][0].pop('layers'), '/actions/0/frames/0/layers'),
                     (lambda d: d['actions'][0]['frames'][0]['layers'][0].pop('visible'), '/actions/0/frames/0/layers/0/visible')]
        for change, path in mutations:
            observed = copy.deepcopy(original)
            observed.pop('canonical_sha256')
            change(observed)
            observed = sealed(observed)
            actor = load_actor(actor_document(profile, resources=[{'part': 'body', 'inventory_sha256': observed['canonical_sha256'],
                'act_sha256': original['sources']['act']['sha256'], 'spr_sha256': original['sources']['spr']['sha256']}]))
            value = target_document(actor, profile, count=2)
            value['actions'][0]['parts'][0]['views'][0]['topology'] = {'kind': 'inherited', 'inventory_sha256': observed['canonical_sha256'], 'slot': 15}
            target = load_target(value, actor=actor, profile=profile)
            with self.subTest(path=path), self.assertRaises(ForgeError) as error:
                assess_target(target, actor=actor, profile=profile, inventories=(observed,))
            self.assertEqual(error.exception.code, ErrorCode.INVALID_INPUT)
            self.assertEqual(error.exception.path, '/inventories/0' + path)

    def test_timing_rejects_conflicting_and_unknown_action_references(self):
        for mode, name in (('nonlooping', 'Walk'), ('looping', 'imaginary-action')):
            value = frozen_runtime_profile('player').to_dict()
            value.pop('canonical_sha256')
            index = len(value['timing'][mode])
            value['timing'][mode].append(name)
            with self.subTest(mode=mode), self.assertRaises(ForgeError) as error:
                load_runtime_profile(value)
            self.assertEqual(error.exception.path, f'/timing/{mode}/{index}')

    def test_semantic_profile_revision_requires_explicit_advance(self):
        old=frozen_runtime_profile('monster')
        value=old.to_dict();value.pop('canonical_sha256')
        with self.assertRaises(ForgeError) as error:
            load_runtime_profile(value,previous=old)
        self.assertEqual(error.exception.path,'/profile_version')
        value['profile_version']='1.0.1'
        new=load_runtime_profile(value,previous=old)
        self.assertEqual(new.profile_version,'1.0.1')
        self.assertNotEqual(new.canonical_sha256,old.canonical_sha256)

    def test_unknown_runtime_part_does_not_destroy_structural_intent(self):
        profile=frozen_runtime_profile('unverified')
        actor=load_actor(actor_document(profile,category='unverified',parts=['hull']))
        value=target_document(actor,profile)
        value['actions'][0]['parts'][0]['part']='hull'
        target=load_target(value,actor=actor,profile=profile)
        result=assess_target(target,actor=actor,profile=profile)
        self.assertTrue(result['status']['declared_scope_specified'])
        self.assertEqual(result['diagnostics'],[{'code':'UNVERIFIED_RESOURCE_PART','path':'/actions/0/parts/0/part'}])
        self.assertEqual(result['status']['runtime_compatibility'],'UNVERIFIED')


if __name__ == '__main__':
    unittest.main()
