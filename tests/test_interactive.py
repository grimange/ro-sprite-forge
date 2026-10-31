"""RSF-17: transport proposals must obey canonical core and atomic persistence."""
import base64
import copy
from pathlib import Path
import tempfile
import unittest
from ro_sprite_forge.core.canonical import canonical_bytes
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.core.project import create_project, load_project
from ro_sprite_forge.service.workbench import mutate, workspace, preview, comparison, source_preview
from test_inventory import resources
from test_workbench import make_target_doc

class InteractiveTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.m = create_project(self.root,'demo','Synthetic','novice','player')
        target = make_target_doc('demo',frame_count=6)
        for v in target['actions'][0]['parts'][0]['views']:
            v['topology']['layers'] = ['body']
        self.apply('target',target=target)
        self.act,self.spr = resources(slots=40,frames=6)
        self.apply('import-pair',id='body',part='body',act_base64=base64.b64encode(self.act).decode(),spr_base64=base64.b64encode(self.spr).decode())
        self.w = workspace(self.root,self.m)
        self.layers = self.w['requirements']['layers']
        self.source = self.w['sources'][0]['source']
    def apply(self,op,**data):
        result = mutate(self.root,self.m,op,dict(expected_revision=self.m['revision'],**data))
        self.m = result['project']
        return result
    def direct(self,n=0):
        return dict(requirement_id=self.layers[n]['id'],kind='DIRECT_SOURCE',source=self.source['id'],source_revision=1,recipe=[])
    def reuse(self,n,a):
        return dict(requirement_id=self.layers[n]['id'],kind='EXPLICIT_REUSE',dependency=dict(id=a['id'],revision=a['revision']),recipe=[dict(id='mirror',op='mirror_x',version=1,parameters={})])
    def assert_atomic_failure(self,op,**data):
        before = canonical_bytes(load_project(self.root,'demo',verify_blobs=False))
        with self.assertRaises(ForgeError): self.apply(op,**data)
        self.assertEqual(before,canonical_bytes(load_project(self.root,'demo',verify_blobs=False)))
    def test_direct_batch_reuse_persistence_and_no_approval(self):
        self.assertEqual(len(self.layers),48)
        self.assertFalse(self.m.get('ledger'))
        self.apply('assign',mappings=[self.direct(0),self.direct(1)])
        a = self.m['ledger']['assignments'][0]
        self.apply('assign',mappings=[self.reuse(2,a)])
        b = next(x for x in self.m['ledger']['assignments'] if x['requirement_id']==self.layers[2]['id'])
        r = self.apply('assign',mappings=[self.reuse(3,b)])
        self.assertEqual(len(r['ledger']['assignments']),4)
        self.assertEqual(len(self.layers)-len(r['ledger']['assignments']),44)
        self.assertTrue(all(a['review'] is None for a in self.m['ledger']['assignments']))
        self.assertEqual(load_project(self.root,'demo')['ledger'],self.m['ledger'])
        image = source_preview(self.root,self.m,dict(assignment=b['id']))
        self.assertEqual(image['execution'],'EXECUTED')
        self.assertEqual(len(image['transform_chain']),1)
        self.assertEqual(canonical_bytes(workspace(self.root,self.m)),canonical_bytes(workspace(self.root,self.m)))
    def test_invalid_batch_does_not_publish_first_valid_mapping(self):
        self.assert_atomic_failure('assign',mappings=[self.direct(),dict(self.direct(1),requirement_id='unknown')])
    def test_duplicate_and_missing_source_and_stale_source(self):
        for mappings in ([self.direct(),self.direct()], [dict(self.direct(),source='missing')], [dict(self.direct(),source_revision=2)]):
            self.assert_atomic_failure('assign',mappings=mappings)
    def test_missing_dependency_and_unknown_recipe(self):
        self.assert_atomic_failure('assign',mappings=[self.reuse(0,dict(id='absent',revision=1))])
        self.assert_atomic_failure('assign',mappings=[dict(self.direct(),recipe=[dict(id='unknown',op='magic',version=1,parameters={})])])
    def test_self_cycle_and_stale_dependency(self):
        self.apply('assign',mappings=[self.direct()])
        a=self.m['ledger']['assignments'][0]
        self.assert_atomic_failure('assign',mappings=[self.reuse(0,dict(a,revision=2))])
        self.assert_atomic_failure('assign',mappings=[self.reuse(1,dict(a,revision=99))])
    def test_stale_project_and_target_revision(self):
        with self.assertRaises(ForgeError): mutate(self.root,self.m,'assign',dict(expected_revision=1,mappings=[self.direct()]))
        self.apply('assign',mappings=[self.direct()])
        self.assert_atomic_failure('target',target=make_target_doc('demo'))
    def test_import_rejects_invalid_bytes_and_duplicate_identity(self):
        self.assert_atomic_failure('import-pair',id='broken',part='body',act_base64='@@',spr_base64='@@')
        self.assert_atomic_failure('import-pair',id='body',part='body',act_base64=base64.b64encode(self.act).decode(),spr_base64=base64.b64encode(self.spr).decode())
    def test_missing_and_corrupt_original_remain_inspectable(self):
        self.apply('assign',mappings=[self.direct()])
        sprpath=self.root/'demo'/'blobs'/self.m['resources'][0]['spr']
        # Locate existing storage layout without assuming file suffixes.
        sprpath=next(p for p in (self.root/'demo'/'blobs').rglob('*') if p.is_file() and p.read_bytes()==self.spr)
        sprpath.write_bytes(b'corrupted')
        w=workspace(self.root,self.m)
        self.assertTrue(all(s['validation']!='VALID' for s in w['sources']))
        self.assertEqual(w['sources'][0]['source']['sha256'],self.source['sha256'])
        self.assert_atomic_failure('assign',mappings=[self.direct(1)])
        sprpath.unlink()
        self.assertTrue(all(s['availability']=='MISSING' for s in workspace(self.root,self.m)['sources']))
    def test_preview_exact_selection_steps_and_timing(self):
        q=dict(resource='body',slot=8,view=0,frame=0)
        first=preview(self.root,self.m,q)
        self.assertEqual(first['report']['selection']['fallback'],'NONE')
        self.assertEqual(preview(self.root,self.m,dict(q,step=1))['report']['selection']['frame'],1)
        self.assertEqual(preview(self.root,self.m,dict(q,step=-1))['report']['selection']['frame'],0)
        with self.assertRaises(ForgeError): preview(self.root,self.m,dict(q,slot=9))
        with self.assertRaises(ForgeError): preview(self.root,self.m,dict(q,frame=6))
        unresolved=preview(self.root,self.m,dict(q,elapsed_ms=100))
        self.assertNotEqual(unresolved['report']['selection']['timing_status'],'SUPPORTED')
        timed=dict(q,elapsed_ms=1000,context=dict(movement_speed=150))
        self.assertEqual(preview(self.root,self.m,timed),preview(self.root,self.m,timed))
        self.assertEqual(first,preview(self.root,self.m,q))
        for speed in (0.5,1,2):
            resumed=preview(self.root,self.m,dict(q,elapsed_ms=0,resume_frame=3,speed=speed,context=dict(movement_speed=150)))
            self.assertEqual(resumed['report']['selection']['frame'],3)
    def test_comparison_requires_explicit_candidate_and_preserves_sources(self):
        original=copy.deepcopy(self.m)
        q=dict(resource='body',slot=8,view=0,frame=0)
        with self.assertRaises(ForgeError): comparison(self.root,self.m,q)
        r=comparison(self.root,self.m,dict(q,candidate='body',mode='SIDE_BY_SIDE'))
        self.assertTrue(r['png_base64'])
        self.assertEqual(self.m,original)

if __name__=='__main__': unittest.main()

# Exercise the real protected transport rather than calling only pure adapters.
import test_workbench
class InteractiveHTTPTests(unittest.TestCase):
    setUp = test_workbench.WorkbenchServiceTests.setUp
    tearDown = test_workbench.WorkbenchServiceTests.tearDown
    request = test_workbench.WorkbenchServiceTests.request
    def test_routes_require_csrf_and_typed_invalid_inputs(self):
        self.request('POST','/api/projects',dict(project_id='demo',name='Demo',actor='novice',profile='player'))
        for route in ('target','import-pair','assign','preview','compare','source-preview'):
            status,_,_=self.request('POST',f'/api/projects/demo/{route}',{},headers={'X-CSRF-Token':'incorrect'})
            self.assertEqual(status,403,route)
        for route in ('assign','preview','compare','source-preview'):
            status,body,_=self.request('POST',f'/api/projects/demo/{route}',dict(expected_revision=1))
            self.assertGreaterEqual(status,400,(route,body))
            self.assertLess(status,500,(route,body))
    def test_put_cannot_forge_import_inventory(self):
        create_project(self.projects_dir,'demo','Demo','novice','player')
        m=load_project(self.projects_dir,'demo')
        m['resources']=[dict(id='fake',part='body',act='0'*64,spr='0'*64,inventory={})]
        status,_,_=self.request('PUT','/api/projects/demo',dict(expected_revision=1,project=m))
        self.assertGreaterEqual(status,400)
        self.assertEqual(load_project(self.projects_dir,'demo')['revision'],1)

    def test_missing_source_does_not_block_project_read_routes(self):
        m=create_project(self.projects_dir,'demo','Demo','novice','player')
        m=mutate(self.projects_dir,m,'target',dict(expected_revision=m['revision'],target=make_target_doc('demo')))['project']
        act,spr=resources(slots=40,frames=6)
        m=mutate(self.projects_dir,m,'import-pair',dict(expected_revision=m['revision'],id='body',part='body',act_base64=base64.b64encode(act).decode(),spr_base64=base64.b64encode(spr).decode()))['project']
        blob=next(p for p in (self.projects_dir/'demo'/'blobs').rglob('*') if p.is_file() and p.read_bytes()==spr)
        for corrupt in (True,False):
            if corrupt: blob.write_bytes(b'corrupt')
            else: blob.unlink()
            for suffix in ('','/requirements','/coverage','/work-order?format=json','/workspace'):
                status,body,_=self.request('GET','/api/projects/demo'+suffix)
                self.assertEqual(status,200,(suffix,body))
            w=workspace(self.projects_dir,m)
            self.assertTrue(all(source['validation']!='VALID' for source in w['sources']))
