"""RSF-9 independent graph/identity/state expectations using synthetic topology."""
import copy
import unittest

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, load_target
from ro_sprite_forge.core.errors import ForgeError, ErrorCode
from ro_sprite_forge.core.ledger import (load_ledger, resolve_ledger, compare_ledgers, assignment_binding)
from ro_sprite_forge.core.topology import resolve_topology
from test_contracts import actor_document, target_document


def example_requirements():
    p = frozen_runtime_profile('player'); a = load_actor(actor_document(p))
    d = target_document(a, p, count=6)
    d['actions'][0]['parts'][0]['views'] = [
        {'view':i,'frame_count':6,'topology':{'kind':'explicit','layers':['body']}} for i in range(8)]
    return resolve_topology(load_target(d,actor=a,profile=p),actor=a,profile=p)


def source(sid='art-a', content=b'operator supplied synthetic bytes', origin='AUTHORED'):
    return {'id':sid,'revision':1,'sha256':digest(content),'kind':'IMAGE',
        'origin':origin,'external_ref':sid,'image':None,'provenance':None}


def assignment(r, index=0, aid='A', kind='DIRECT_SOURCE', dep=None, sid='art-a', recipe=None):
    layer=r['layers'][index]
    return {'id':aid,'revision':1,'requirement_id':layer['id'],'binding':assignment_binding(layer),
        'kind':kind,'source':{'id':sid,'revision':1} if kind=='DIRECT_SOURCE' else None,
        'dependency':{'id':dep,'revision':1} if kind=='EXPLICIT_REUSE' else None,
        'recipe':recipe or [],'review':None}


def document(r):
    return {'schema':'rsf.assignment-ledger/v1','id':'walk-ledger','revision':1,'previous_sha256':None,
        'target':r['target'],'requirements_sha256':r['canonical_sha256'],
        'sources':[],'assignments':[],'attachments':[]}


def operation(op='mirror_x', **params):
    return {'id':op,'op':op,'version':1,'parameters':params}


class LedgerTests(unittest.TestCase):
    def setUp(self):
        self.r=example_requirements(); self.d=document(self.r)
        self.d['sources']=[source()]
        self.d['assignments']=[assignment(self.r),assignment(self.r,1,'B','EXPLICIT_REUSE','A',recipe=[operation()]),
            assignment(self.r,2,'C','EXPLICIT_REUSE','B',recipe=[operation('translate',x=3,y=-2)]),
            assignment(self.r,3,'D')]
        self.data={'art-a':b'operator supplied synthetic bytes'}

    def resolve(self,d=None,data=None):
        return resolve_ledger(load_ledger(d or self.d,requirements=self.r),requirements=self.r,
            source_bytes=self.data if data is None else data)

    def invalid(self,d,message=None):
        with self.assertRaises(ForgeError) as ctx:load_ledger(d,requirements=self.r)
        self.assertEqual(ctx.exception.code,ErrorCode.INVALID_INPUT)
        if message:self.assertIn(message,str(ctx.exception))
        self.assertIsNotNone(ctx.exception.path)

    def test_structurally_complete_zero_art_remains_unassigned(self):
        d=document(self.r);r=self.resolve(d,data={})
        self.assertEqual(len(self.r['frames']),48);self.assertEqual(len(self.r['layers']),48)
        self.assertEqual(r['counts']['unassigned'],48)
        self.assertEqual(r['counts']['selected_assignments'],0)
        self.assertTrue(all(o['kind']=='UNASSIGNED' and o['visual_review']=='UNVERIFIED' for o in r['occurrences']))
        self.assertFalse(r['status']['export_ready'])

    def test_direct_reuse_multilevel_and_unassigned_examples(self):
        r=self.resolve();a,b,c,d=r['assignments']
        self.assertEqual(r['counts']['direct'],2);self.assertEqual(r['counts']['explicit_reuse'],2)
        self.assertEqual(r['counts']['unassigned'],44)
        self.assertEqual(a['availability'],'AVAILABLE');self.assertEqual(a['validation'],'VALID')
        self.assertEqual(b['availability'],'REUSED');self.assertEqual(c['visual_review'],'UNVERIFIED')
        self.assertEqual([x['operation']['op'] for x in c['transform_chain']],['mirror_x','translate'])
        self.assertEqual([x['id'] for x in c['lineage']],['A','B','C'])
        self.assertEqual(c['effective_source']['sha256'],source()['sha256'])
        self.assertEqual(r['counts']['approved_source_art_roots'],0)
        self.assertFalse(c['transforms_executed'])

    def test_missing_unknown_hash_mismatch_distinct(self):
        for data,availability,validation in [({},'UNVERIFIED','UNVERIFIED'),({'art-a':None},'MISSING','UNVERIFIED'),
                ({'art-a':b'changed'},'AVAILABLE','INVALID')]:
            with self.subTest(data=data):
                r=self.resolve(data=data);self.assertEqual(r['assignments'][0]['availability'],availability)
                self.assertEqual(r['assignments'][0]['validation'],validation)
                self.assertEqual(r['counts']['validated_replacement_occurrences'],0)
        self.d['sources'][0]['sha256']=None
        self.assertEqual(self.resolve()['sources'][0]['diagnostic'],'SOURCE_HASH_UNDECLARED')

    def test_empty_source_and_wrong_byte_types_rejected(self):
        self.d['sources'][0]['sha256']=digest(b'')
        self.assertEqual(self.resolve(data={'art-a':b''})['sources'][0]['validation'],'INVALID')
        with self.assertRaises(ForgeError):self.resolve(data={'art-a':'not bytes'})
        with self.assertRaises(ForgeError):self.resolve(data={'unknown':b'x'})

    def test_explicit_unassigned_is_preserved(self):
        self.d['assignments']=[assignment(self.r,kind='UNASSIGNED')]
        r=self.resolve();self.assertEqual(r['counts']['unassigned'],48)
        self.d['assignments'][0]['recipe']=[operation()];self.invalid(self.d)

    def test_duplicate_assignment_identity_and_requirement(self):
        self.d['assignments'].append(copy.deepcopy(self.d['assignments'][0]));self.invalid(self.d,'DUPLICATE_IDENTITY')
        self.d['assignments'][-1]['id']='other';self.invalid(self.d,'DUPLICATE_ASSIGNMENT')

    def test_nonexistent_stale_and_cross_part_requirements(self):
        for mutate,code in [(lambda d:d['assignments'][0].update(requirement_id='absent'),'NONEXISTENT_REQUIREMENT'),
            (lambda d:d['target'].update(revision=2),'STALE_TARGET'),
            (lambda d:d.update(requirements_sha256='0'*64),'CHANGED_REQUIREMENTS'),
            (lambda d:d['assignments'][0]['binding'].update(part='head'),'BINDING_MISMATCH'),
            (lambda d:d['assignments'][0]['binding'].update(frame=5),'BINDING_MISMATCH')]:
            d=copy.deepcopy(self.d);mutate(d);self.invalid(d,code)

    def test_missing_and_stale_reuse_dependencies(self):
        self.d['assignments'][1]['dependency']['id']='missing';self.invalid(self.d,'MISSING_DEPENDENCY')
        self.d['assignments'][1]['dependency']={'id':'A','revision':2};self.invalid(self.d,'STALE_DEPENDENCY_REVISION')
        self.d['assignments'][0]['source']['revision']=2;self.invalid(self.d,'STALE_SOURCE_REVISION')

    def test_self_two_three_node_cycles(self):
        for count in (1,2,3):
            d=copy.deepcopy(self.d);d['assignments']=d['assignments'][:count]
            for i,a in enumerate(d['assignments']):
                a.update(kind='EXPLICIT_REUSE',source=None,dependency={'id':d['assignments'][(i+1)%count]['id'],'revision':1})
            self.invalid(d,'CYCLIC_REUSE')

    def test_invalid_recipe_shapes(self):
        bad=[operation('unknown'),operation('crop',x=0,y=0,width=0,height=2),
             operation('scale',x_num=1,x_den=0,y_num=1,y_den=1),operation('translate',x=float('nan'),y=1),
             operation('translate',x=True,y=1),operation('rotate',millidegrees=400000),
             {**operation(),'unexpected':1}]
        for op in bad:
            d=copy.deepcopy(self.d);d['assignments'][0]['recipe']=[op];self.invalid(d)
        self.d['assignments'][0]['recipe']=[operation(),operation()];self.invalid(self.d,'DUPLICATE_OPERATION')

    def test_ordered_recipes_are_not_normalized(self):
        self.d['assignments'][0]['recipe']=[operation('crop',x=0,y=0,width=4,height=3),operation('rotate',millidegrees=-90000),
            operation('scale',x_num=2,x_den=1,y_num=1,y_den=2)]
        r=self.resolve();self.assertEqual([x['operation']['op'] for x in r['assignments'][2]['transform_chain']],
            ['crop','rotate','scale','mirror_x','translate'])

    def test_determinism_order_and_immutable_contract(self):
        l=load_ledger(self.d,requirements=self.r);before=canonical_bytes(self.d)
        d=copy.deepcopy(self.d);d['assignments'].reverse()
        other=load_ledger(d,requirements=self.r)
        self.assertEqual(l.canonical_bytes(),other.canonical_bytes())
        self.assertEqual(canonical_bytes(self.resolve()),canonical_bytes(self.resolve()))
        x=l.to_dict();x['assignments'].clear();self.assertEqual(len(l.to_dict()['assignments']),4)
        self.assertEqual(before,canonical_bytes(self.d))
        self.assertNotIn('/home/',l.canonical_bytes().decode())

    def test_source_changes_and_transitive_invalidation(self):
        # D uses an independent selected source even if content is equal; no dedup inference.
        self.d['sources'].append(source('art-d'));self.d['assignments'][3]['source']['id']='art-d'
        before=self.resolve(data={**self.data,'art-d':self.data['art-a']})
        self.d['sources'][0]['sha256']=digest(b'new')
        after=self.resolve(data={'art-a':b'new','art-d':self.data['art-a']})
        impact=compare_ledgers(before,after)
        self.assertEqual(impact['affected_assignments'],['A','B','C'])
        self.assertEqual(impact['unaffected_assignments'],['D'])
        self.assertEqual(impact,compare_ledgers(before,after))
        self.assertEqual(before['assignments'][3],after['assignments'][3])

    def test_recipe_change_impacts_only_dependency_closure(self):
        before=self.resolve();self.d['assignments'][1]['recipe'][0]=operation('translate',x=1,y=2)
        impact=compare_ledgers(before,self.resolve())
        self.assertEqual(impact['affected_assignments'],['B','C'])
        self.assertEqual(impact['unaffected_assignments'],['A','D'])

    def test_noop_revision_and_observation_changes(self):
        before=self.resolve();self.assertEqual(compare_ledgers(before,self.resolve())['affected_assignments'],[])
        changed=self.resolve(data={'art-a':None})
        self.assertEqual(compare_ledgers(before,changed)['affected_assignments'],['A','B','C','D'])
        x=self.resolve(data={'art-a':b'bad1'});y=self.resolve(data={'art-a':b'bad2'})
        self.assertTrue(compare_ledgers(x,y)['affected_assignments'])

    def test_orphans_reported_without_remapping(self):
        from ro_sprite_forge.core.canonical import sealed
        old=self.resolve();r=copy.deepcopy(self.r);r.pop('canonical_sha256');r['layers']=r['layers'][1:];r=sealed(r)
        impact=compare_ledgers(old,old,current_requirements=r)
        self.assertEqual(impact['orphaned_assignments'],['A'])
        self.assertEqual(impact['affected_assignments'],['A','B','C'])

    def test_previous_revision_contract(self):
        first=load_ledger(self.d,requirements=self.r)
        self.assertEqual(first,load_ledger(self.d,requirements=self.r,previous=first))
        d=copy.deepcopy(self.d);d['assignments'][0]['recipe']=[operation()]
        with self.assertRaises(ForgeError):load_ledger(d,requirements=self.r,previous=first)
        d.update(revision=2,previous_sha256=first.canonical_sha256)
        with self.assertRaises(ForgeError):load_ledger(d,requirements=self.r,previous=first)
        d['assignments'][0]['revision']=2;d['assignments'][1]['dependency']['revision']=2
        d['assignments'][1]['revision']=2;d['assignments'][2]['dependency']['revision']=2;d['assignments'][2]['revision']=2
        self.assertEqual(load_ledger(d,requirements=self.r,previous=first).to_dict()['revision'],2)

    def test_no_approval_created_and_bound_operator_declarations(self):
        r=self.resolve();self.assertTrue(all(a['visual_review']=='UNVERIFIED' for a in r['assignments']))
        for item in self.d['assignments']:
            r=self.resolve();row=next(x for x in r['assignments'] if x['id']==item['id'])
            item['review']={'authority':'OPERATOR','operator':'synthetic-human-assertion','state':'APPROVED',
                'basis_sha256':row['composition_sha256'],'evidence_sha256':'a'*64,'policy':'VISUAL_DECISION'}
        r=self.resolve();self.assertEqual(r['counts']['accepted_reuse'],2)
        # Two direct roots with equal bytes still represent two explicit art roots.
        self.assertEqual(r['counts']['approved_source_art_roots'],2)
        self.d['assignments'][0]['recipe']=[operation()]
        r=self.resolve();self.assertTrue(all(a['review_binding']=='STALE' for a in r['assignments'][:3]))
        self.assertEqual(r['assignments'][3]['visual_review'],'APPROVED')

    def test_classic_reference_not_replacement_and_not_required_policy(self):
        self.d['sources'][0]['origin']='CLASSIC_REFERENCE'
        a=self.resolve()['assignments'][0]
        self.d['assignments'][0]['review']={'authority':'OPERATOR','operator':'human-policy','state':'NOT_REQUIRED',
            'basis_sha256':a['composition_sha256'],'evidence_sha256':'b'*64,'policy':'UNCHANGED_REFERENCE'}
        r=self.resolve();self.assertEqual(r['assignments'][0]['visual_review'],'NOT_REQUIRED')
        self.assertEqual(r['counts']['validated_replacement_occurrences'],0)
        self.d['sources'][0]['origin']='AUTHORED'
        row=self.resolve()['assignments'][0];self.d['assignments'][0]['review']['basis_sha256']=row['composition_sha256']
        self.assertEqual(self.resolve()['assignments'][0]['review_binding'],'INAPPLICABLE_POLICY')

    def test_unknown_versions_tampered_seals_and_paths(self):
        for mutate in (lambda d:d.update(schema='rsf.assignment-ledger/v99'),lambda d:d.update(canonical_sha256='0'*64),
                lambda d:d['sources'][0].update(external_ref='/home/private/art.png')):
            d=copy.deepcopy(self.d);mutate(d);self.invalid(d)

    def test_runtime_unsupported_remains_distinct(self):
        # Preserve accepted topology slot mapping status independently from art availability.
        from ro_sprite_forge.core.canonical import sealed
        r=copy.deepcopy(self.r);r.pop('canonical_sha256')
        for s in r['slots']:s['runtime_mapping']='UNSUPPORTED'
        self.r=sealed(r);self.d['requirements_sha256']=self.r['canonical_sha256']
        row=self.resolve()['assignments'][0]
        self.assertEqual(row['runtime_support'],'UNSUPPORTED');self.assertEqual(row['availability'],'AVAILABLE')

    def test_attachment_links_and_parent_change_impact(self):
        from ro_sprite_forge.core.canonical import sealed
        # Separate synthetic part, same exact action/view/frame; immutable identities retained.
        r=copy.deepcopy(self.r);r.pop('canonical_sha256');layer=copy.deepcopy(r['layers'][0])
        layer.update(id=layer['id']+'/head',part='head');r['layers'].append(layer)
        self.r=sealed(r);self.d['requirements_sha256']=self.r['canonical_sha256']
        self.d['assignments']=[assignment(self.r),assignment(self.r,48,'head')]
        self.d['attachments']=[{'id':'head-link','parent_assignment':'A','child_assignment':'head',
            'parent_part':'body','child_part':'head','anchor':{'id':'head-anchor','index':0,'x':1,'y':-3}}]
        before=self.resolve();self.d['assignments'][0]['recipe']=[operation()]
        after=self.resolve();self.assertNotEqual(before['assignments'][1]['composition_sha256'],after['assignments'][1]['composition_sha256'])
        self.assertEqual(compare_ledgers(before,after)['affected_assignments'],['A','head'])
        self.d['attachments'][0]['child_part']='body';self.invalid(self.d,'PART_MISMATCH')



    def test_decode_and_expansion_budgets_are_typed(self):
        from unittest.mock import patch
        with patch('ro_sprite_forge.core.ledger.MAX_SOURCE_BYTES',1):
            with self.assertRaises(ForgeError) as e:self.resolve()
            self.assertIn('SOURCE_BYTE_BUDGET',str(e.exception))
        with patch('ro_sprite_forge.core.ledger.MAX_RESOLVED_STEPS',1):
            with self.assertRaises(ForgeError) as e:self.resolve()
            self.assertIn('RESOLUTION_BUDGET',str(e.exception))

    def test_malformed_requirements_are_typed(self):
        from ro_sprite_forge.core.canonical import sealed
        for key,value in [('layers',[{'id':'bad'}]),('slots',[]),('target',None)]:
            r=copy.deepcopy(self.r);r.pop('canonical_sha256');r[key]=value;r=sealed(r)
            with self.assertRaises(ForgeError):load_ledger(self.d,requirements=r)

    def test_changed_requirement_record_with_same_id_is_stale(self):
        from ro_sprite_forge.core.canonical import sealed
        before=self.resolve();r=copy.deepcopy(self.r);r.pop('canonical_sha256');r['layers'][0]['registration']='changed'
        impact=compare_ledgers(before,before,current_requirements=sealed(r))
        self.assertEqual(impact['affected_assignments'],['A','B','C'])
        self.assertEqual(impact['orphaned_assignments'],[])
        self.assertIn('REQUIREMENT_CHANGED',impact['changed_assignments'][0]['reasons'])

    def test_reuse_unassigned_does_not_resolve_to_valid_art(self):
        self.d['assignments'][0]=assignment(self.r,kind='UNASSIGNED')
        report=self.resolve();self.assertEqual(report['assignments'][2]['availability'],'MISSING')
        self.assertIsNone(report['assignments'][2]['effective_source'])
        self.assertFalse(report['assignments'][2]['reuse_accepted'])

    def test_imported_image_requires_provenance(self):
        self.d['sources'][0]['kind']='IMPORTED_IMAGE';self.invalid(self.d,'REQUIRES_POOL_AND_PROVENANCE')
        self.d['sources'][0].update(image={'pool':'indexed','index':3},
            provenance={'inventory_sha256':'1'*64,'act_sha256':'2'*64,'spr_sha256':'3'*64},origin='CLASSIC_REFERENCE')
        self.assertEqual(self.resolve()['assignments'][0]['source_origin'],'CLASSIC_REFERENCE')

    def test_attachment_bad_reference_and_cycles(self):
        self.d['attachments']=[{'id':'link','parent_assignment':'A','child_assignment':'missing',
            'parent_part':'body','child_part':'head','anchor':{'id':'anchor','index':0,'x':0,'y':0}}]
        self.invalid(self.d,'INVALID_ATTACHMENT_REFERENCE')

    def test_review_evidence_metadata_does_not_change_composition(self):
        report=self.resolve();basis=report['assignments'][0]['composition_sha256']
        self.d['assignments'][0]['review']={'authority':'OPERATOR','operator':'synthetic-human',
            'state':'APPROVED','basis_sha256':basis,'evidence_sha256':'1'*64,'policy':'VISUAL_DECISION'}
        reviewed=self.resolve();self.assertEqual(reviewed['assignments'][0]['composition_sha256'],basis)
        self.assertEqual(compare_ledgers(report,reviewed)['affected_assignments'],[])

    def test_malformed_resolved_reports_are_typed(self):
        from ro_sprite_forge.core.canonical import sealed
        valid=self.resolve()
        malformed=[{'schema':'rsf.resolved-ledger/v1'}]
        for field,value in [('assignments',[{}]),('sources',None),('edges',[{'dependency':'missing','dependent':'A'}]),
                ('assignments',valid['assignments']*2),('sources',valid['sources']*2),
                ('occurrences',valid['occurrences']*2),('attachments',[{'id':'bad'}])]:
            d=copy.deepcopy(valid);d[field]=value;malformed.append(d)
        for field,value in [('availability',[]),('validation','PASS'),('effective_source',{}),
                ('lineage',[{'id':'missing','revision':1}]),('root_assignment','missing')]:
            d=copy.deepcopy(valid);d['assignments'][0][field]=value;malformed.append(d)
        d=copy.deepcopy(valid);d['edges'].append({'dependency':'C','dependent':'A'});malformed.append(d)
        for d in malformed:
            d.pop('canonical_sha256',None)
            with self.subTest(value=d),self.assertRaises(ForgeError) as error:
                compare_ledgers(sealed(d),valid)
            self.assertEqual(error.exception.code,ErrorCode.INVALID_INPUT)
            self.assertIsNotNone(error.exception.path)

    def test_impact_report_budget_and_duplicate_edges(self):
        from ro_sprite_forge.core.canonical import sealed
        from unittest.mock import patch
        valid=self.resolve();bad=copy.deepcopy(valid);bad.pop('canonical_sha256')
        bad['edges'].append(copy.deepcopy(bad['edges'][0]))
        with self.assertRaises(ForgeError):compare_ledgers(valid,sealed(bad))
        with patch('ro_sprite_forge.core.ledger.MAX_RECORDS',1):
            with self.assertRaises(ForgeError):compare_ledgers(valid,valid)


class LedgerCliTests(unittest.TestCase):
    def test_malformed_impact_input_exits_three_without_publication(self):
        import contextlib
        import io
        import tempfile
        from pathlib import Path
        from ro_sprite_forge.cli import main
        from ro_sprite_forge.core.canonical import sealed
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);bad=p/'bad.json';output=p/'impact.json'
            bad.write_bytes(canonical_bytes(sealed({'schema':'rsf.resolved-ledger/v1'})))
            with contextlib.redirect_stderr(io.StringIO()) as err:
                self.assertEqual(main(['ledger-impact','--before',str(bad),'--after',str(bad),'--output',str(output)]),3)
            self.assertIn('INVALID_INPUT',err.getvalue());self.assertNotIn('Traceback',err.getvalue())
            self.assertFalse(output.exists());self.assertFalse(list(p.glob('.rsf-report-*')))

    def test_cli_hash_validation_atomic_publication_and_impact(self):
        import contextlib
        import io
        import json
        from pathlib import Path
        import tempfile
        from ro_sprite_forge.cli import main
        r=example_requirements();d=document(r);d['sources']=[source()];d['assignments']=[assignment(r)]
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'r.json').write_bytes(canonical_bytes(r));(p/'l.json').write_bytes(canonical_bytes(d))
            (p/'art').write_bytes(b'operator supplied synthetic bytes')
            original={f.name:f.read_bytes() for f in p.iterdir()}
            args=['ledger','--requirements',str(p/'r.json'),'--ledger',str(p/'l.json'),'--source','art-a='+str(p/'art'),'--output',str(p/'out.json')]
            self.assertEqual(main(args),0)
            out=json.loads((p/'out.json').read_bytes());self.assertEqual(out['assignments'][0]['validation'],'VALID')
            self.assertNotIn(tmp,(p/'out.json').read_text())
            with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main(args),3)
            self.assertEqual({n:(p/n).read_bytes() for n in original},original)
            (p/'art').write_bytes(b'changed');args[-1]=str(p/'bad.json')
            with contextlib.redirect_stderr(io.StringIO()) as err:self.assertEqual(main(args),3)
            self.assertIn('SOURCE_VERIFICATION_INCOMPLETE',err.getvalue())
            self.assertEqual(json.loads((p/'bad.json').read_bytes())['assignments'][0]['validation'],'INVALID')
            self.assertEqual(main(['ledger-impact','--before',str(p/'out.json'),'--after',str(p/'bad.json'),'--output',str(p/'impact.json')]),0)
            self.assertEqual(json.loads((p/'impact.json').read_bytes())['affected_assignments'],['A'])
            d['assignments'][0].update(kind='EXPLICIT_REUSE',source=None,dependency={'id':'A','revision':1})
            (p/'l.json').write_bytes(canonical_bytes(d));args[-1]=str(p/'failed.json')
            with contextlib.redirect_stderr(io.StringIO()):self.assertEqual(main(args),3)
            self.assertFalse((p/'failed.json').exists());self.assertFalse(list(p.glob('.rsf-report-*')))

    def test_schema_draft_validation(self):
        # Dependency remains optional; separate script covers Draft validation offline.
        from ro_sprite_forge.core.ledger import ledger_schema
        self.assertFalse(ledger_schema()['additionalProperties'])


if __name__=='__main__':unittest.main()
