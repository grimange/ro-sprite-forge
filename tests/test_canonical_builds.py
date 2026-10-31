"""RSF-25 canonical identities, fail-closed export, atomic bundles and cache.

All approvals below are synthetic test declarations, never artwork decisions.
"""
import copy
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from ro_sprite_forge.cli import main
from ro_sprite_forge.core.build import cache_bundle, publish_bundle, toolchain
from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed
from ro_sprite_forge.core.compiler import compile_resources, plan_compilation, publish_compilation, validate_compilation_manifest, compilation_manifest_schema
from ro_sprite_forge.core.contracts import load_target
from ro_sprite_forge.core.coverage import evaluate_coverage
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger
from ro_sprite_forge.core.review import bases, make_event, evaluate_reviews, apply_reviews
from ro_sprite_forge.core.topology import resolve_topology
from ro_sprite_forge.formats.act import read_act, write_act
from test_compiler import (_build_synthetic_monster_act_spr, _setup_monster_contracts,
                          _build_approved_ledger, _make_png, RUST_ORACLE_BIN)

ROOT = Path(__file__).resolve().parents[1]


def fixture(full=False, all_assignments=False, topology_kind='inherited'):
    act, spr = _build_synthetic_monster_act_spr()
    actor, profile, target, inv, req = _setup_monster_contracts(act, spr)
    if full:
        doc = target.to_dict(); doc.pop('canonical_sha256', None); doc['scope'] = 'full'
        original = read_act(act)
        for group, action in enumerate(doc['actions']):
            action['id'] = profile.to_dict()['actions'][group]['id']
            action['requirement'] = 'REQUIRED'
            action['parts'] = [dict(part='body', views=[dict(view=v,
                frame_count=len(original['actions'][group * 8 + v]),
                topology=dict(kind='inherited', inventory_sha256=inv['canonical_sha256'], slot=group * 8 + v)) for v in range(8)])]
            for view in action['parts'][0]['views']:
                motions = original['actions'][group * 8 + view['view']]
                roles = [[f'body{n}' for n, clip in enumerate(motion['clips']) if clip['sprite'] >= 0]
                         for motion in motions]
                if topology_kind == 'per_frame':
                    view['topology'] = dict(kind='per_frame', frames=roles)
                elif topology_kind == 'explicit' and group == 1 and view['view'] == 1:
                    view['topology'] = dict(kind='explicit', layers=roles[0])
        target = load_target(doc, actor=actor, profile=profile)
        req = resolve_topology(target, actor=actor, profile=profile, inventories=(inv,))
    selected = req['layers'] if full or all_assignments else req['layers'][:2]
    sources = {'art': _make_png(4, 4, (123, 45, 67, 200)), 'other': _make_png(4, 4, (76, 54, 32, 255))}
    assignments = [dict(requirement_id=l['id'], kind='DIRECT_SOURCE', source=dict(id='art' if i % 2 else 'other', revision=1)) for i,l in enumerate(selected)]
    ledger = _build_approved_ledger(req, assignments, sources)
    return act, spr, dict(requirements=req, ledger=ledger, source_bytes=sources,
                          replacement_policy='explicit_rgba')


class CanonicalBuildTests(unittest.TestCase):
    def test_clean_cli_builds_different_paths_times_and_hash_seeds(self):
        act, spr, kw = fixture()
        with tempfile.TemporaryDirectory() as tmp:
            outputs = []
            for run in (0, 1):
                root = Path(tmp) / f'workspace-{run}'; root.mkdir()
                (root/'original.act').write_bytes(act); (root/'original.spr').write_bytes(spr)
                (root/'req.json').write_bytes(canonical_bytes(kw['requirements']))
                (root/'ledger.json').write_bytes(canonical_bytes(kw['ledger']))
                for sid, raw in reversed(list(kw['source_bytes'].items())) if run else kw['source_bytes'].items():
                    (root/f'{sid}.png').write_bytes(raw)
                argv = [sys.executable, '-m', 'ro_sprite_forge', 'compile', '--act','original.act','--spr','original.spr',
                        '--requirements','req.json','--ledger','ledger.json','--policy','explicit_rgba',
                        '--source','art=art.png','--source','other=other.png', '--output-dir','result',
                        '--compilation-id',f'invocation-{run}','--output-prefix',f'output-{run}']
                env = dict(os.environ, PYTHONPATH=str(ROOT/'src'), PYTHONHASHSEED=str(run+10),
                           SOURCE_DATE_EPOCH=str(1700000000+run*10000))
                if run and RUST_ORACLE_BIN.is_file(): argv += ['--oracle',str(RUST_ORACLE_BIN)]
                proc = subprocess.run(argv,cwd=root,env=env,capture_output=True,text=True)
                self.assertEqual(proc.returncode,0,proc.stderr)
                out = root/'result'
                manifest = json.loads((out/'compilation-manifest.json').read_bytes())
                outputs.append(((out/f'output-{run}.act').read_bytes(),(out/f'output-{run}.spr').read_bytes(),(out/'build-manifest.json').read_bytes(),manifest))
                # Different actual modification times, independent of the canonical payload.
                os.utime(out/f'output-{run}.act', (1700000000+run*200,)*2)
            self.assertEqual(outputs[0][:3], outputs[1][:3])
            self.assertNotEqual(outputs[0][3]['canonical_sha256'], outputs[1][3]['canonical_sha256'])
            encoded = outputs[0][2].decode()
            self.assertNotIn(tmp,encoded); self.assertNotIn('invocation-',encoded)
            self.assertNotIn('native_korangar',encoded); self.assertNotIn('rust_report',encoded)

    def test_ordering_numeric_encoding_and_manifest_schema(self):
        act,spr,kw = fixture()
        a=read_act(act)
        clip=a['actions'][8][0]['clips'][0]
        clip.update(scale_x=1+2**-24,scale_y=-0.0,x=-2147483648,color=0xFEDCBA98)
        a['delays'][8] = 1+3*2**-24
        act=write_act(a)
        req = _setup_monster_contracts(act, spr)[-1]
        assignments = [dict(requirement_id=l['id'],kind='DIRECT_SOURCE',source=dict(id='art',revision=1)) for l in req['layers'][:2]]
        kw.update(requirements=req,ledger=_build_approved_ledger(req,assignments,kw['source_bytes']))
        result=compile_resources(act,spr,**kw)
        decoded=read_act(result['act_bytes'])
        self.assertEqual(struct.pack('<f',decoded['actions'][8][0]['clips'][0]['scale_x']),struct.pack('<f',1.0))
        self.assertEqual(struct.pack('<f',decoded['actions'][8][0]['clips'][0]['scale_y']),b'\0\0\0\x80')
        self.assertEqual(struct.pack('<f',decoded['delays'][8]),struct.pack('<f',1+2**-22))
        for slot in range(40):
            for old,new in zip(read_act(act)['actions'][slot],decoded['actions'][slot]):
                self.assertEqual([c['x'] for c in old['clips']],[c['x'] for c in new['clips']])
                self.assertEqual(old['anchors'],new['anchors'])
        reverse=copy.deepcopy(kw); reverse['ledger']['assignments'].reverse(); reverse['ledger']['sources'].reverse()
        reverse['replacement_requirement_ids']=[r['requirement_id'] for r in result['manifest']['replacements']][::-1]
        again=compile_resources(act,spr,**reverse)
        self.assertEqual(result['act_bytes'],again['act_bytes']); self.assertEqual(result['spr_bytes'],again['spr_bytes'])
        self.assertEqual(result['manifest']['build'],again['manifest']['build'])
        try: from jsonschema import Draft202012Validator
        except ImportError: self.skipTest('optional schema validator unavailable')
        Draft202012Validator(compilation_manifest_schema()).validate(result['manifest'])

    def test_build_identity_changes_for_semantic_inputs_and_toolchain(self):
        act,spr,kw=fixture(); first=compile_resources(act,spr,**kw)['manifest']['build']
        changed=compile_resources(act,spr,**kw,isolation_strategy='always_append')['manifest']['build']
        self.assertNotEqual(first['input_sha256'],changed['input_sha256'])
        with patch('ro_sprite_forge.core.build.platform.python_version',return_value='3.14.999'):
            changed=compile_resources(act,spr,**kw)['manifest']['build']
        self.assertNotEqual(first['input_sha256'],changed['input_sha256'])
        with patch('PIL.__version__','0.0.0'):
            with self.assertRaisesRegex(ForgeError,'UNSUPPORTED_TOOLCHAIN'): compile_resources(act,spr,**kw)
        # No-op remains independent of Pillow availability/version.
        with patch('PIL.__version__','0.0.0'):
            noop=compile_resources(act,spr,compilation_mode='preserve')
        self.assertEqual((noop['act_bytes'],noop['spr_bytes']),(act,spr))

    def test_scoped_complete_still_partial_and_production_rejected(self):
        act,spr,kw=fixture(all_assignments=True)
        result=compile_resources(act,spr,**kw)
        status=result['manifest']['status']
        self.assertEqual(status['export_label'],'PARTIAL_DIAGNOSTIC')
        self.assertEqual(status['declared_scope_completeness'],'COMPLETE_FOR_DECLARED_SCOPE')
        self.assertEqual(status['full_profile_completeness'],'INCOMPLETE')
        self.assertFalse(status['production_authorized'])
        with self.assertRaisesRegex(ForgeError,'PRODUCTION_EXPORT_NOT_READY'):
            compile_resources(act,spr,**kw,compilation_mode='production_export')

    def test_full_production_and_plan_requires_every_occurrence(self):
        act,spr,kw=fixture(full=True)
        result=compile_resources(act,spr,**kw,compilation_mode='production_export',oracle_executable=RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None)
        status=result['manifest']['status']
        self.assertEqual(status['export_label'],'PRODUCTION'); self.assertTrue(status['production_authorized'])
        self.assertEqual(status['full_profile_completeness'],'COMPLETE_FOR_FULL_PROFILE')
        self.assertEqual(result['manifest']['verification']['native_korangar'],'UNVERIFIED')
        plan=plan_compilation(act,spr,**kw,compilation_mode='production_export')
        self.assertTrue(plan['ready_to_compile']); self.assertTrue(plan['production_authorized'])
        self.assertEqual(plan['build'],result['manifest']['build'])
        with self.assertRaisesRegex(ForgeError,'PRODUCTION_EXPORT_NOT_READY'):
            compile_resources(act,spr,**kw,compilation_mode='production_export',replacement_requirement_ids=[kw['requirements']['layers'][0]['id']])
        with tempfile.TemporaryDirectory() as tmp:
            publish_compilation(Path(tmp)/'production',result)
            self.assertEqual(json.loads((Path(tmp)/'production/build-manifest.json').read_bytes()),result['manifest']['build'])

    def test_full_production_rejects_missing_invalid_stale_and_unapproved(self):
        act,spr,kw=fixture(full=True)
        for failure in ('missing','corrupt','unapproved','stale','unassigned','invalid_png'):
            with self.subTest(failure=failure):
                bad=copy.deepcopy(kw)
                if failure=='missing': bad['source_bytes']['art']=None
                elif failure=='corrupt': bad['source_bytes']['art']=b'bad'
                elif failure=='unapproved': bad['ledger']['assignments'][0]['review']=None
                elif failure=='stale': bad['ledger']['assignments'][0]['review']['basis_sha256']='a'*64
                elif failure=='unassigned': bad['ledger']['assignments'].pop()
                elif failure=='invalid_png':
                    bad['source_bytes']['art']=b'hash-valid non-PNG'
                    specs=[dict(requirement_id=l['id'],kind='DIRECT_SOURCE',source=dict(id='art',revision=1)) for l in bad['requirements']['layers']]
                    bad['ledger']=_build_approved_ledger(bad['requirements'],specs,bad['source_bytes'])
                with self.assertRaises(ForgeError): compile_resources(act,spr,**bad,compilation_mode='production_export')
        with self.assertRaisesRegex(ForgeError,'STALE_LEDGER_REVISION'):
            compile_resources(act,spr,**kw,compilation_mode='production_export',expected_ledger_revision=2)

    def test_production_rejects_unbound_explicit_composition(self):
        # Role declarations specify layer topology, not preserved ACT registration/timing.
        # They remain useful for diagnostics but cannot authorize a production composition.
        for kind in ('per_frame', 'explicit'):
            with self.subTest(topology=kind):
                act,spr,kw=fixture(full=True,topology_kind=kind)
                original=read_act(act)
                original['actions'][8][0]['clips'][0]['x']+=100
                original['delays'][8]*=2
                for raw in (act,write_act(original)):
                    with self.assertRaisesRegex(ForgeError,'UNBOUND_PRODUCTION_COMPOSITION'):
                        compile_resources(raw,spr,**kw,compilation_mode='production_export')
                    plan=plan_compilation(raw,spr,**kw,compilation_mode='production_export')
                    self.assertFalse(plan['ready_to_compile'])
                    self.assertFalse(plan['production_authorized'])
                bounded=compile_resources(act,spr,**kw)
                self.assertEqual(bounded['manifest']['status']['export_label'],'PARTIAL_DIAGNOSTIC')
                self.assertFalse(bounded['manifest']['status']['production_authorized'])

    def test_changed_source_stales_only_affected_reviews_and_projection(self):
        act,spr,kw=fixture(); req=kw['requirements']; declaration=kw['ledger']
        original=resolve_ledger(load_ledger(declaration,requirements=req),requirements=req,source_bytes=kw['source_bytes'])
        current=bases(req,original)
        event=make_event('test-project',1,req['target'],'APPROVED',
                         [dict(requirement_id=rid,basis_sha256=basis,evidence_sha256='e'*64) for rid,basis in sorted(current.items())],1)
        states=evaluate_reviews('test-project',[event],req,original)
        reviewed=apply_reviews(original,states,declaration,req,kw['source_bytes'])
        compile_resources(act,spr,**kw,reviewed_ledger=reviewed)
        altered=copy.deepcopy(kw); raw=_make_png(4,4,(17,23,41,255)); altered['source_bytes']['art']=raw
        for source in altered['ledger']['sources']:
            if source['id']=='art': source.update(sha256=digest(raw),revision=2)
        for assignment in altered['ledger']['assignments']:
            if assignment['source']['id']=='art': assignment['source']['revision']=2
        fresh=resolve_ledger(load_ledger(altered['ledger'],requirements=req),requirements=req,source_bytes=altered['source_bytes'])
        changed=evaluate_reviews('test-project',[event],req,fresh)
        byid={r['requirement_id']:r['state'] for r in changed['occurrences']}
        for row in fresh['assignments']:
            self.assertEqual(byid[row['requirement_id']],'STALE' if row['effective_source']['id']=='art' else 'APPROVED')
        with self.assertRaisesRegex(ForgeError,'STALE_REVIEWED_LEDGER'):
            compile_resources(act,spr,**altered,reviewed_ledger=reviewed)
        compile_resources(act,spr,**kw,reviewed_ledger=reviewed)  # identical rebuild keeps approvals

    def test_changed_original_and_forged_build_evidence_rejected(self):
        act,spr,kw=fixture()
        original=read_act(act);original['delays'][8]+=1
        with self.assertRaisesRegex(ForgeError,'CHANGED_COMPOSITION_RESOURCE'):
            compile_resources(write_act(original),spr,**kw)
        result=compile_resources(act,spr,**kw)
        value=copy.deepcopy(result['manifest']); value['replacement_policy']='indexed_exact'
        value=sealed({k:v for k,v in value.items() if k!='canonical_sha256'})
        with self.assertRaisesRegex(ForgeError,'INVALID_BUILD_POLICY'):validate_compilation_manifest(value)

    def test_bundle_interruption_and_cache_integrity(self):
        act,spr,kw=fixture(); result=compile_resources(act,spr,**kw)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); out=root/'output'; cache=root/'cache'
            with patch('ro_sprite_forge.core.build._rename_noreplace',side_effect=OSError('simulated interruption')):
                with self.assertRaises(ForgeError): publish_compilation(out,result,cache_dir=cache)
            self.assertFalse(out.exists()); self.assertFalse(any(cache.iterdir()))
            publish_compilation(out,result,cache_dir=cache)
            entry=cache/result['manifest']['build']['input_sha256']
            contents={p.name:p.read_bytes() for p in entry.iterdir()}
            publish_compilation(root/'again',result,cache_dir=cache)
            self.assertEqual(contents,{p.name:p.read_bytes() for p in entry.iterdir()})
            (entry/'spr.spr').write_bytes(b'corrupt')
            with self.assertRaisesRegex(ForgeError,'CORRUPT_BUILD_CACHE'): publish_compilation(root/'third',result,cache_dir=cache)
            self.assertFalse((root/'third').exists())
            self.assertEqual(act,_build_synthetic_monster_act_spr()[0]); self.assertEqual(kw['source_bytes']['art'],_make_png(4,4,(123,45,67,200)))

    def test_concurrent_cache_and_output_publication(self):
        from concurrent.futures import ThreadPoolExecutor
        act,spr,kw=fixture(); result=compile_resources(act,spr,**kw)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def attempt(i):
                try:
                    publish_compilation(root/'output',result,cache_dir=root/'cache')
                    return True
                except ForgeError:
                    return False
            with ThreadPoolExecutor(max_workers=6) as pool:
                outcomes=list(pool.map(attempt,range(6)))
            self.assertEqual(sum(outcomes),1)
            self.assertEqual((root/'output/compiled.act').read_bytes(),result['act_bytes'])
            self.assertTrue((root/'output/PARTIAL_DIAGNOSTIC.txt').read_text().startswith('PARTIAL_DIAGNOSTIC'))
            self.assertEqual(len(list((root/'cache').iterdir())),1)
            self.assertFalse(list(root.glob('.rsf-staging-*')))

    def test_cli_production_forbids_nonatomic_pair_export(self):
        from contextlib import redirect_stderr
        import io
        act,spr,kw=fixture()
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); (root/'a.act').write_bytes(act); (root/'s.spr').write_bytes(spr)
            error=io.StringIO()
            with redirect_stderr(error):
                code=main(['compile','--act',str(root/'a.act'),'--spr',str(root/'s.spr'),
                           '--mode','production_export','--output-act',str(root/'out.act'),'--output-spr',str(root/'out.spr')])
            self.assertNotEqual(code,0); self.assertIn('atomic --output-dir',error.getvalue())
            self.assertFalse((root/'out.act').exists()); self.assertFalse((root/'out.spr').exists())

    def test_process_killed_before_commit_leaves_no_partial_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); out=root/'output'
            script="""import os,sys
from pathlib import Path
import ro_sprite_forge.core.build as b
b._rename_noreplace=lambda *args: os._exit(73)
b.publish_bundle(Path(sys.argv[1]), {'a.act':b'ACT','b.spr':b'SPR','compilation-manifest.json':b'PRODUCTION'})
"""
            proc=subprocess.run([sys.executable,'-c',script,str(out)],env=dict(os.environ,PYTHONPATH=str(ROOT/'src')))
            self.assertEqual(proc.returncode,73); self.assertFalse(out.exists())
            stages=list(root.glob('.rsf-staging-*')); self.assertEqual(len(stages),1)
            publish_bundle(out,{'a':b'complete'})
            self.assertEqual((out/'a').read_bytes(),b'complete')

    def test_publication_rejects_bad_pairs_paths_and_overwrite(self):
        act,spr,kw=fixture(); result=compile_resources(act,spr,**kw)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            bad=copy.deepcopy(result); bad['spr_bytes']=b'corrupt'
            with self.assertRaisesRegex(ForgeError,'COMPILATION_PAIR_MISMATCH'): publish_compilation(root/'bad',bad)
            self.assertFalse((root/'bad').exists())
            bad=copy.deepcopy(result)
            bad['manifest']['output_resources']['act']['filename']='PARTIAL_DIAGNOSTIC.txt'
            bad['manifest']=sealed({k:v for k,v in bad['manifest'].items() if k!='canonical_sha256'})
            with self.assertRaisesRegex(ForgeError,'INVALID_OUTPUT_FILENAME'): publish_compilation(root/'reserved',bad)
            self.assertFalse((root/'reserved').exists())
            publish_compilation(root/'ok',result)
            with self.assertRaises(ForgeError): publish_compilation(root/'ok',result)
            with self.assertRaisesRegex(ForgeError,'INVALID_BUNDLE_FILENAME'): publish_bundle(root/'escape',{'../escape':b'bad'})
            self.assertFalse((root/'escape').exists())
            original=root/'original';original.mkdir();(root/'link').symlink_to(original)
            with self.assertRaises(ForgeError): publish_bundle(root/'link',{'a':b'bad'})
            self.assertEqual(list(original.iterdir()),[])


if __name__=='__main__': unittest.main()
