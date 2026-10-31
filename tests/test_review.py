"""Synthetic explicit operator decisions only; no proprietary artwork approvals."""
import copy
import hashlib
import unittest
from ro_sprite_forge.core.canonical import canonical_bytes, sealed
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.core.project import load_project, save_project
from ro_sprite_forge.core.review import bases, validate_events, SEMANTICS
from ro_sprite_forge.service.workbench import workspace, review_proposal, record_review
import test_interactive as interactive

class ReviewTests(unittest.TestCase):
    setUp=interactive.InteractiveTests.setUp
    apply=interactive.InteractiveTests.apply
    direct=interactive.InteractiveTests.direct
    reuse=interactive.InteractiveTests.reuse
    def propose(self, ns):
        return review_proposal(self.root,self.m,dict(expected_revision=self.m['revision'],requirements=[self.layers[n]['id'] for n in ns]))
    def decide(self,ns,decision='APPROVED',**extra):
        p=self.propose(ns)['proposal']
        w=record_review(self.root,self.m,dict(expected_revision=self.m['revision'],proposal=p,decision=decision,**extra))
        self.m=w['project'];return w
    def test_review_deterministic_basis_and_separate_assignment_revision(self):
        self.apply('assign',mappings=[self.direct()]);p=self.propose([0]);self.assertEqual(p,self.propose([0]))
        old=self.m['ledger'];w=self.decide([0]);self.assertEqual(old,self.m['ledger'])
        self.assertEqual(w['reviews']['counts']['APPROVED'],1)
        self.assertEqual(w['coverage']['counts']['review']['approved'],1)
        self.assertFalse(w['coverage']['status']['export_ready'])
        self.assertEqual(workspace(self.root,load_project(self.root,'demo'))['reviews'],w['reviews'])
        event=self.m['review_events'][0]
        payload={k:v for k,v in event.items() if k not in ('id','canonical_sha256')}
        self.assertEqual(hashlib.sha256(canonical_bytes(payload)).hexdigest(),event['canonical_sha256'])
    def test_rejection_and_history(self):
        self.apply('assign',mappings=[self.direct()]);self.decide([0]);w=self.decide([0],'REJECTED')
        self.assertEqual(w['reviews']['counts']['REJECTED'],1);self.assertEqual(w['coverage']['counts']['review']['approved'],0)
        self.assertEqual(len(self.m['review_events']),2)
        self.assertIn('REVIEW_REJECTED',w['coverage']['occurrences'][0]['issues'])
    def test_transitive_change_preserves_independent_decision(self):
        self.apply('assign',mappings=[self.direct(0),self.direct(3)])
        a=next(a for a in self.m['ledger']['assignments'] if a['requirement_id']==self.layers[0]['id'])
        self.apply('assign',mappings=[self.reuse(1,a)])
        b=next(a for a in self.m['ledger']['assignments'] if a['requirement_id']==self.layers[1]['id'])
        self.apply('assign',mappings=[self.reuse(2,b)])
        self.decide([0,1,2,3]);before=copy.deepcopy(self.m['review_events'])
        result=self.apply('assign',mappings=[self.direct(0)])
        states={r['requirement_id']:r['state'] for r in result['reviews']['occurrences']}
        self.assertEqual([states[self.layers[i]['id']] for i in range(4)],['STALE','STALE','STALE','APPROVED'])
        self.assertEqual(before,self.m['review_events'])
        self.assertEqual(result['coverage']['counts']['review']['stale'],3)
        self.assertEqual(len(result['impact']['affected_assignments']),3)
    def test_unrelated_metadata_save_preserves_approval(self):
        self.apply('assign',mappings=[self.direct()]);self.decide([0]);self.m['name']='Display only'
        self.m=save_project(self.root,self.m,self.m['revision'])
        self.assertEqual(workspace(self.root,self.m)['reviews']['counts']['APPROVED'],1)
    def test_atomic_scope_and_missing_assignment(self):
        self.apply('assign',mappings=[self.direct()]);before=(self.root/'demo'/'manifest.json').read_bytes()
        for ids in [[self.layers[0]['id'],'absent'],[self.layers[0]['id']]*2,[],[self.layers[1]['id']]]:
            with self.assertRaises(ForgeError):review_proposal(self.root,self.m,dict(expected_revision=self.m['revision'],requirements=ids))
        self.assertEqual(before,(self.root/'demo'/'manifest.json').read_bytes())
    def test_stale_proposal_and_revision_rejected(self):
        self.apply('assign',mappings=[self.direct()]);p=self.propose([0])['proposal'];oldrev=self.m['revision']
        self.apply('assign',mappings=[self.direct()]);before=(self.root/'demo'/'manifest.json').read_bytes()
        for rev in [oldrev,self.m['revision']]:
            with self.assertRaises(ForgeError):record_review(self.root,self.m,dict(expected_revision=rev,proposal=p,decision='APPROVED'))
        self.assertEqual(before,(self.root/'demo'/'manifest.json').read_bytes())
    def test_unexecuted_recipe_cannot_be_approved(self):
        m=self.direct();m['recipe']=[dict(id='move',op='translate',version=1,parameters=dict(x=1,y=0))]
        self.apply('assign',mappings=[m]);p=self.propose([0])['proposal'];self.assertFalse(p['approvable'])
        with self.assertRaises(ForgeError):self.decide([0])
        self.assertEqual(self.decide([0],'REJECTED')['reviews']['counts']['REJECTED'],1)
    def test_explicit_not_required_policy(self):
        self.apply('assign',mappings=[self.direct()])
        with self.assertRaises(ForgeError):self.decide([0],'NOT_REQUIRED')
        w=self.decide([0],'NOT_REQUIRED',policy='UNCHANGED_REFERENCE_STRUCTURAL_ONLY',structural_only=True)
        self.assertEqual(w['reviews']['counts']['NOT_REQUIRED'],1)
        a=self.m['ledger']['assignments'][0];self.apply('assign',mappings=[self.reuse(1,a)])
        with self.assertRaises(ForgeError):self.decide([1],'NOT_REQUIRED',policy='UNCHANGED_REFERENCE_STRUCTURAL_ONLY',structural_only=True)
    def test_missing_source_makes_review_stale_and_unreviewable(self):
        self.apply('assign',mappings=[self.direct()]);self.decide([0]);(self.root/'demo'/'blobs'/self.m['resources'][0]['spr']).unlink()
        w=workspace(self.root,self.m);self.assertEqual(w['reviews']['counts']['STALE'],1)
        with self.assertRaises(ForgeError):self.propose([0])
    def test_malformed_event_and_untrusted_decision(self):
        self.apply('assign',mappings=[self.direct()]);self.decide([0]);bad=copy.deepcopy(self.m['review_events']);bad[0]['decision']='AUTO_APPROVED'
        with self.assertRaises(ForgeError):validate_events(bad,'demo')
        bad=copy.deepcopy(self.m['review_events']);bad[0]['members'][0]['basis_sha256']='0'*64
        with self.assertRaises(ForgeError):validate_events(bad,'demo')
        with self.assertRaises(ForgeError):self.decide([0],'INVALID')
    def test_batch_all_and_only_selected(self):
        self.apply('assign',mappings=[self.direct(n) for n in range(6)])
        w=self.decide([0,2,4]);self.assertEqual(w['reviews']['counts']['APPROVED'],3)
        self.assertEqual(w['reviews']['counts']['UNVERIFIED'],45)
        self.assertEqual([m['requirement_id'] for m in self.m['review_events'][0]['members']],sorted(self.layers[n]['id'] for n in [0,2,4]))

    def test_frame_timing_anchor_and_order_change_basis_locally(self):
        self.apply('assign',mappings=[self.direct(0),self.direct(1)])
        w=workspace(self.root,self.m);req=w['requirements'];report=w['ledger'];original=bases(req,report)
        for constraint in [dict(source_raw_delay=12),dict(anchors=[dict(x=2,y=4)]),dict(ordered_layers=['cloak','body'])]:
            changed=copy.deepcopy(req);changed['frames'][0]['constraints']=constraint
            changed.pop('canonical_sha256');changed=sealed(changed)
            result=bases(changed,report)
            self.assertNotEqual(result[self.layers[0]['id']],original[self.layers[0]['id']])
            self.assertEqual(result[self.layers[1]['id']],original[self.layers[1]['id']])
    def test_source_recipe_and_assignment_revision_affect_basis(self):
        self.apply('assign',mappings=[self.direct()]);w=workspace(self.root,self.m)
        old=bases(w['requirements'],w['ledger'])
        self.decide([0]);self.assertEqual(old,bases(workspace(self.root,self.m)['requirements'],workspace(self.root,self.m)['ledger']))
        mapping=self.direct();mapping['recipe']=[dict(id='mirror',op='mirror_x',version=1,parameters={})]
        self.apply('assign',mappings=[mapping]);self.assertEqual(workspace(self.root,self.m)['reviews']['counts']['STALE'],1)
        self.assertNotEqual(old,bases(workspace(self.root,self.m)['requirements'],workspace(self.root,self.m)['ledger']))
    def test_view_and_action_scopes_are_explicit_occurrence_lists(self):
        self.apply('assign',mappings=[self.direct(i) for i in range(48)])
        self.decide(list(range(6)));self.assertEqual(workspace(self.root,self.m)['reviews']['counts']['APPROVED'],6)
        self.decide(list(range(48)),'REJECTED');self.assertEqual(workspace(self.root,self.m)['reviews']['counts']['REJECTED'],48)
    def test_displayed_evidence_hash_is_checked(self):
        self.apply('assign',mappings=[self.direct()]);p=self.propose([0])['proposal']
        p['members'][0]['evidence_sha256']='0'*64
        with self.assertRaises(ForgeError):record_review(self.root,self.m,dict(expected_revision=self.m['revision'],proposal=p,decision='APPROVED'))
    def test_no_artistic_decision_from_preview_or_assignment(self):
        self.apply('assign',mappings=[self.direct()]);self.propose([0]);w=workspace(self.root,self.m)
        self.assertEqual(w['reviews']['counts']['APPROVED'],0);self.assertNotIn('review_events',self.m)
    def test_schema_validates_and_rejects_unknown_fields(self):
        try:
            from jsonschema import Draft202012Validator
        except ImportError:
            self.skipTest('Optional jsonschema validator is checked separately.')
        from ro_sprite_forge.core.review import review_schema
        self.apply('assign',mappings=[self.direct()]);self.decide([0]);schema=review_schema()
        Draft202012Validator.check_schema(schema);validator=Draft202012Validator(schema)
        event=self.m['review_events'][0];validator.validate(event)
        bad=dict(event,automatic_approval=True);self.assertTrue(list(validator.iter_errors(bad)))
        with self.assertRaises(ForgeError):validate_events([bad],'demo')

class ReviewHttpTests(unittest.TestCase):
    setUp_fixture=ReviewTests.setUp
    apply=ReviewTests.apply
    direct=ReviewTests.direct
    def setUp(self):
        import threading
        from ro_sprite_forge.service.server import create_server
        self.setUp_fixture();self.apply('assign',mappings=[self.direct()])
        self.projects_dir=self.root
        self.server=create_server(self.root,host='127.0.0.1',port=0)
        self.base_url=self.server.url;self.csrf_token=self.server.security.csrf_token
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):
        self.server.shutdown();self.server.server_close();self.thread.join()
    def request(self,*args,**kwargs):
        import test_workbench
        return test_workbench.WorkbenchServiceTests.request(self,*args,**kwargs)
    def proposal(self):
        status,result,_=self.request('POST','/api/projects/demo/review-proposal',dict(expected_revision=self.m['revision'],requirements=[self.layers[0]['id']]))
        self.assertEqual(status,200);return result['proposal']
    def test_http_decision_reopen_and_forged_generic_save(self):
        p=self.proposal()
        status,w,_=self.request('POST','/api/projects/demo/review',dict(expected_revision=self.m['revision'],proposal=p,decision='APPROVED'))
        self.assertEqual(status,200);self.assertEqual(w['reviews']['counts']['APPROVED'],1)
        status,w,_=self.request('GET','/api/projects/demo/workspace');self.assertEqual(w['reviews']['counts']['APPROVED'],1)
        m=w['project'];m['review_events']=[]
        status,_,_=self.request('PUT','/api/projects/demo',dict(project=m,expected_revision=m['revision']))
        self.assertNotEqual(status,200)
        status,_,_=self.request('POST','/api/projects/demo/review',dict(expected_revision=p['project_revision'],proposal=p,decision='APPROVED'))
        self.assertEqual(status,409)
    def test_concurrent_review_exactly_one_commit(self):
        from concurrent.futures import ThreadPoolExecutor
        p=self.proposal();body=dict(expected_revision=self.m['revision'],proposal=p,decision='REJECTED')
        with ThreadPoolExecutor(2) as pool:
            results=list(pool.map(lambda _:self.request('POST','/api/projects/demo/review',body)[0],range(2)))
        self.assertEqual(sorted(results),[200,409])
        self.assertEqual(len(load_project(self.root,'demo')['review_events']),1)

if __name__=='__main__':unittest.main()
