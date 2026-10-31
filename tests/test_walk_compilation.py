"""RSF-26: staged Walk -> accepted compiler -> independent binary expectations.

All artwork and review decisions here are isolated synthetic test declarations.
Rust decodes both pairs; no compiler remapping/PASS fields are used as expectations.
"""
import base64
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

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.compiler import compile_resources, publish_compilation, verify_pair_with_rust_oracle
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, load_target, reference
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.project import create_project, load_project
from ro_sprite_forge.core.topology import resolve_topology
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.spr import read_spr, write_spr
from ro_sprite_forge.service.server import make_standard_actor_doc
from ro_sprite_forge.service.workbench import mutate, record_review, review_proposal, workspace
from test_compiler import _build_synthetic_monster_act_spr, _build_approved_ledger, _make_png, RUST_ORACLE_BIN
from test_canonical_builds import fixture as canonical_fixture

ROOT = Path(__file__).resolve().parents[1]


def walk_contracts(act, spr, category='monster', actor_id='rsf26-monster', heads=None):
    """Bind requirements to observed frames/layers and frozen profile slot mapping."""
    profile = frozen_runtime_profile(category)
    inv = inventory(act, spr, actor=actor_id, part='body', profile=get_profile(category))
    inventories = [inv]
    if heads:
        inventories.append(inventory(*heads, actor=actor_id, part='head', profile=get_profile(category)))
    doc = make_standard_actor_doc(actor_id, profile, parts=['body', 'head'] if heads else ['body'])
    doc['resources'] = [dict(part=part, inventory_sha256=i['canonical_sha256'],
        act_sha256=i['sources']['act']['sha256'], spr_sha256=i['sources']['spr']['sha256']) for part,i in zip(('body','head'),inventories)]
    actor = load_actor(doc)
    original = read_act(act)
    actions = []
    for action in profile.to_dict()['actions']:
        required = action['id'] == 'Walk'
        views = [dict(view=v, frame_count=len(original['actions'][slot]),
                      topology=dict(kind='inherited', inventory_sha256=inv['canonical_sha256'], slot=slot))
                 for v, slot in enumerate(action['slots'])] if required else []
        actions.append(dict(id=action['id'], requirement='REQUIRED' if required else 'OUT_OF_SCOPE',
                            parts=[dict(part='body', views=views)] if required else []))
    target = load_target(dict(schema='rsf.target/v2', id=actor_id+'-walk', revision=1,
        previous_sha256=None, actor=reference(actor), runtime_profile=reference(profile), scope='scoped',
        parts=['body'], compatibility=dict(status='UNVERIFIED', declarations=[]), actions=actions), actor=actor, profile=profile)
    req = resolve_topology(target, actor=actor, profile=profile, inventories=tuple(inventories))
    return actor, profile, target, inv, req


def synthetic_pair():
    act, spr = _build_synthetic_monster_act_spr()
    a = read_act(act)
    profile = frozen_runtime_profile('monster').to_dict()
    slots = {r['id']: r['slots'][0] for r in profile['actions']}
    # An unaffected truecolor consumer must survive an indexed-pool insertion.
    a['actions'][slots['Idle']][0]['clips'][0].update(pool=1, sprite=0)
    walk = a['actions'][slots['Walk']]
    hidden = dict(walk[2]['clips'][0], sprite=-1, pool=17, mirror=9)
    # Target visible ordinal 1 must map to raw clip ordinal 2 after a hidden clip.
    walk[2]['clips'] = [hidden, walk[2]['clips'][0], dict(walk[0]['clips'][0], x=29, y=-41)]
    death = a['actions'][slots['Die']][0]
    death['clips'] = [dict(death['clips'][i % 3], x=i*11-60, y=31-i*7,
                           angle=(i*29)%360, mirror=i%2, scale_x=0.5+i/16,
                           scale_y=1.5-i/32, color=0x80FF00FF+i*256) for i in range(12)] + [hidden]
    return write_act(a), spr


def png_pixels(raw):
    with Image.open(io.BytesIO(raw)) as im:
        return im.width, im.height, im.convert('RGBA').tobytes()


def rust_report(act, spr):
    """Run the independent decoder directly; transport is not a Python decode."""
    with tempfile.TemporaryDirectory(prefix='rsf26-oracle-') as tmp:
        ap, sp = Path(tmp)/'pair.act', Path(tmp)/'pair.spr'
        ap.write_bytes(act); sp.write_bytes(spr)
        proc = subprocess.run([str(RUST_ORACLE_BIN), str(ap), str(sp)], capture_output=True)
        if proc.returncode:
            raise AssertionError(f'Rust exit {proc.returncode}: {proc.stderr.decode()}')
        return json.loads(proc.stdout)


def assert_effective_mapping(case, before, after, expected):
    """Test-side selection from Rust's ordered textures using the pinned runtime formula.

    expected: (numeric slot, frame, RAW clip ordinal) -> known PNG bytes. Compare
    every other field in the two independent ACT reports, including hidden clips.
    """
    old_act, new_act = copy.deepcopy(before['act']), copy.deepcopy(after['act'])
    case.assertEqual(len(old_act['actions']), len(new_act['actions']))
    seen, rows, targeted, unaffected, hidden = set(), [], 0, 0, 0
    for slot, (old_frames, new_frames) in enumerate(zip(old_act['actions'], new_act['actions'])):
        case.assertEqual(len(old_frames), len(new_frames))
        for frame, (old, new) in enumerate(zip(old_frames, new_frames)):
            case.assertEqual(len(old['clips']), len(new['clips']))
            for layer, (oc, nc) in enumerate(zip(old['clips'], new['clips'])):
                loc = (slot, frame, layer)
                if oc['sprite'] == -1:
                    hidden += 1; case.assertEqual(oc, nc); continue
                selected = []
                for report, clip in ((before, oc), (after, nc)):
                    case.assertIn(clip['pool'], (0, 1))
                    count = report['spr']['indexed_count'] if clip['pool'] == 0 else report['spr']['truecolor_count']
                    case.assertTrue(0 <= clip['sprite'] < count, loc)
                    tex = clip['sprite'] + (report['spr']['indexed_count'] if clip['pool'] == 1 else 0)
                    image = report['spr']['images'][tex]
                    case.assertEqual((image['pool'], image['index']), (clip['pool'], clip['sprite']))
                    selected.append((image['width'], image['height'], bytes.fromhex(image['rgba'])))
                if loc in expected:
                    case.assertEqual(selected[1], png_pixels(expected[loc]), loc)
                    targeted += 1; seen.add(loc)
                    # Only the authorized reference pair is excluded from metadata equality.
                    nc['pool'], nc['sprite'] = oc['pool'], oc['sprite']
                else:
                    case.assertEqual(selected[0], selected[1], loc)
                    case.assertEqual(oc, nc, loc)
                    unaffected += 1
                rows.append(dict(slot=slot, frame=frame, layer=layer, targeted=loc in expected,
                    before_pixels_sha256=digest(selected[0][2]), after_pixels_sha256=digest(selected[1][2]),
                    before_dimensions=list(selected[0][:2]), after_dimensions=list(selected[1][:2])))
    case.assertEqual(seen, set(expected))
    # Whole ACT equality covers delays (float32 bits), raw events, opaque header,
    # bounds, anchors, every ordered layer and all metadata outside selected refs.
    case.assertEqual(old_act, new_act)
    case.assertEqual(before['spr']['palette'], after['spr']['palette'])
    return dict(targeted=targeted, unaffected=unaffected, hidden=hidden, mismatches=0,
                slots=len(old_act['actions']), frames=sum(map(len, old_act['actions'])), occurrences=rows)


def staged_walk(root):
    """Declare actual topology before staging, then explicit assignments/test review."""
    act, spr = synthetic_pair()
    manifest = create_project(root, 'rsf26-monster', 'Synthetic Walk compiler regression', 'rsf26-monster', 'monster')
    def change(op, **data):
        nonlocal manifest
        result = mutate(root, manifest, op, dict(expected_revision=manifest['revision'], **data))
        manifest = result['project']
        return result
    change('import-pair', id='original', part='body', act_base64=base64.b64encode(act).decode(), spr_base64=base64.b64encode(spr).decode())
    inv = manifest['resources'][0]['inventory']
    actor_doc=make_standard_actor_doc(manifest['actor'], frozen_runtime_profile('monster'), parts=['body'])
    actor_doc['resources']=[dict(part='body',inventory_sha256=inv['canonical_sha256'],
        act_sha256=digest(act),spr_sha256=digest(spr))]
    (Path(root)/manifest['project_id']/'actor.json').write_bytes(canonical_bytes(load_actor(actor_doc).to_dict()))
    profile = frozen_runtime_profile('monster').to_dict()
    walk_slots = next(r['slots'] for r in profile['actions'] if r['id']=='Walk')
    views = [dict(view=v, frame_count=len(read_act(act)['actions'][slot]),
                  topology=dict(kind='inherited', inventory_sha256=inv['canonical_sha256'], slot=slot)) for v,slot in enumerate(walk_slots)]
    change('target', target=dict(schema='rsf.target/v2', id='rsf26-walk', revision=1, previous_sha256=None,
        scope='scoped', parts=['body'], compatibility=dict(status='UNVERIFIED', declarations=[]),
        actions=[dict(id=a['id'], requirement='REQUIRED' if a['id']=='Walk' else 'OUT_OF_SCOPE',
            parts=[dict(part='body', views=views)] if a['id']=='Walk' else []) for a in profile['actions']]))
    requirements = workspace(root, manifest)['requirements']
    assert not manifest.get('ledger', {}).get('assignments') and not manifest.get('review_events')
    art = [_make_png(6,5,(18,73,129,255),gradient=True), _make_png(3,7,(211,44,99,255),gradient=True)]
    change('stage-sequence', sequence_id='exact-walk-sources', name='Synthetic asymmetric Walk sources', frames=[
        dict(ordinal=i, filename=f'walk-{i}.png', data_base64=base64.b64encode(raw).decode()) for i,raw in enumerate(art)])
    # Keep both sheet and extracted blobs immutable even though this candidate is unused.
    change('extract-spritesheet', extraction_id='unused-sheet', name='Unused sheet candidate',
        sheet_filename='sheet.png', sheet_data_base64=base64.b64encode(_make_png(8,4,(7,61,123,255))).decode(),
        grid=dict(cell_width=4,cell_height=4,columns=2,rows=1))
    transformed = change('apply-transform', recipe=dict(id='explicit-flip', name='Explicit horizontal flip',
        source_sha256=digest(art[1]), operations=[dict(op='flip', direction='horizontal')]))
    derived_sha = transformed['derived_sha256']
    raw_derived = (Path(root)/manifest['project_id']/'blobs'/derived_sha).read_bytes()
    w,h,rgba = png_pixels(art[1])
    assert png_pixels(raw_derived)==(w,h,b''.join(rgba[(y*w+x)*4:(y*w+x+1)*4] for y in range(h) for x in reversed(range(w))))
    selected = [l for l in requirements['layers'] if l['view']==0 and ((l['frame'],l['ordinal']) in ((0,0),(2,1),(3,0)))]
    mappings, expected = [], {}
    for layer in selected:
        raw = raw_derived if layer['frame']==3 else art[0]
        sha = derived_sha if layer['frame']==3 else digest(raw)
        mappings.append(dict(requirement_id=layer['id'], kind='DIRECT_SOURCE', source='blob-'+sha, source_revision=1, recipe=[]))
        expected[(layer['runtime_slot'],layer['frame'],layer['source_layer_ordinal'])] = raw
    change('assign', mappings=mappings)
    proposal = review_proposal(root, manifest, dict(expected_revision=manifest['revision'], requirements=[l['id'] for l in selected]))
    # Explicit simulated operator action, confined to this temporary test project.
    manifest = record_review(root, manifest, dict(expected_revision=manifest['revision'], decision='APPROVED', proposal=proposal['proposal']))['project']
    state = workspace(root, manifest)
    return act, spr, manifest, state, expected


def clean_cli_builds(case, root, act, spr, manifest, state, expected):
    """Two separate processes/cwds: real CLI pipeline, cache, source integrity."""
    inputs = {p: p.read_bytes() for p in (Path(root)/manifest['project_id']).rglob('*') if p.is_file()}
    outputs = []
    for number in (1,2):
        cwd = Path(root)/f'clean-{number}'; cwd.mkdir()
        (cwd/'input.act').write_bytes(act); (cwd/'input.spr').write_bytes(spr)
        (cwd/'requirements.json').write_bytes(canonical_bytes(state['requirements']))
        ledger = copy.deepcopy(manifest['ledger'])
        reviews = {r['requirement_id']: r for r in state['reviews']['occurrences']}
        by_id = {r['requirement_id']: r for r in state['ledger']['assignments']}
        for row in ledger['assignments']:
            review=reviews[row['requirement_id']]
            case.assertEqual(review['state'],'APPROVED')
            # Same ephemeral projection as the accepted RSF-18 apply_reviews API.
            row['review'] = dict(state=review['state'],authority='OPERATOR',operator='local-workbench',
                evidence_sha256=review['recorded_evidence_sha256'],
                basis_sha256=by_id[row['requirement_id']]['composition_sha256'],policy='VISUAL_DECISION')
        ledger.pop('canonical_sha256',None)
        (cwd/'ledger.json').write_bytes(canonical_bytes(ledger))
        argv=[sys.executable,'-m','ro_sprite_forge','compile','--act','input.act','--spr','input.spr',
            '--requirements','requirements.json','--ledger','ledger.json','--policy','explicit_rgba',
            '--output-dir','bundle','--cache-dir',str(Path(root)/'cache'), '--oracle',str(RUST_ORACLE_BIN),
            '--compilation-id',f'clean-{number}','--output-prefix',f'walk-{number}']
        for source in reversed(ledger['sources']) if number==2 else ledger['sources']:
            raw = (Path(root)/manifest['project_id']/'blobs'/source['sha256']).read_bytes()
            (cwd/(source['id']+'.png')).write_bytes(raw)
            argv += ['--source',source['id']+'='+source['id']+'.png']
        proc=subprocess.run(argv,cwd=cwd,env=dict(os.environ,PYTHONPATH=str(ROOT/'src'),PYTHONHASHSEED=str(number*19)),capture_output=True,text=True)
        case.assertEqual(proc.returncode,0,proc.stderr)
        pair = ((cwd/f'bundle/walk-{number}.act').read_bytes(),(cwd/f'bundle/walk-{number}.spr').read_bytes())
        output=dict(act=pair[0],spr=pair[1],build=(cwd/'bundle/build-manifest.json').read_bytes(),
            manifest=json.loads((cwd/'bundle/compilation-manifest.json').read_bytes()), argv=argv, exit=proc.returncode)
        case.assertTrue((cwd/'bundle/PARTIAL_DIAGNOSTIC.txt').is_file())
        case.assertEqual(output['manifest']['status']['export_label'],'PARTIAL_DIAGNOSTIC')
        case.assertFalse(output['manifest']['status']['production_authorized'])
        output['comparison']=assert_effective_mapping(case,rust_report(act,spr),rust_report(*pair),expected)
        outputs.append(output)
    case.assertEqual([outputs[0][k] for k in ('act','spr','build')],[outputs[1][k] for k in ('act','spr','build')])
    case.assertEqual(outputs[0]['comparison'],outputs[1]['comparison'])
    case.assertEqual(len(list((Path(root)/'cache').iterdir())),1)
    for path, raw in inputs.items(): case.assertEqual(path.read_bytes(),raw,str(path))
    return outputs


class WalkCompilationTests(unittest.TestCase):
    @unittest.skipUnless(RUST_ORACLE_BIN.is_file(),'repository Rust oracle unavailable in installed distribution')
    def test_staged_walk_clean_cli_builds_and_complete_independent_mapping(self):
        with tempfile.TemporaryDirectory() as root:
            act,spr,manifest,state,expected=staged_walk(root)
            outputs=clean_cli_builds(self,root,act,spr,manifest,state,expected)
            self.assertEqual(outputs[0]['comparison']['targeted'],3)
            self.assertGreater(outputs[0]['comparison']['unaffected'],40)
            self.assertEqual(len(read_act(outputs[0]['act'])['actions'][32][0]['clips']),13)
            self.assertEqual(load_project(root,manifest['project_id']),manifest)

    @unittest.skipUnless(RUST_ORACLE_BIN.is_file(),'repository Rust oracle unavailable in installed distribution')
    def test_single_shared_reference_and_exact_layer_selection(self):
        act,spr=synthetic_pair(); req=walk_contracts(act,spr)[-1]
        for frame,ordinal in ((0,0),(2,1)):
            with self.subTest(frame=frame,ordinal=ordinal):
                layer=next(l for l in req['layers'] if l['view']==0 and l['frame']==frame and l['ordinal']==ordinal)
                sources={'art':_make_png(5,9,(71,123,211,255),gradient=True)}
                ledger=_build_approved_ledger(req,[dict(requirement_id=layer['id'],kind='DIRECT_SOURCE',source=dict(id='art',revision=1))],sources)
                result=compile_resources(act,spr,requirements=req,ledger=ledger,source_bytes=sources,replacement_policy='explicit_rgba')
                comparison=assert_effective_mapping(self,rust_report(act,spr),rust_report(result['act_bytes'],result['spr_bytes']),
                    {(layer['runtime_slot'],frame,layer['source_layer_ordinal']):sources['art']})
                self.assertEqual(comparison['targeted'],1)
                self.assertEqual(comparison['hidden'],6)

    @unittest.skipUnless(RUST_ORACLE_BIN.is_file(),'repository Rust oracle unavailable in installed distribution')
    def test_mixed_pool_append_preserves_effective_truecolor_and_raw_indexed(self):
        act,spr=synthetic_pair(); req=walk_contracts(act,spr)[-1]
        selected=[l for l in req['layers'] if l['view']==0 and l['frame'] in (0,3)]
        sources={'art':_make_png(4,4,(255,0,255,255))}
        ledger=_build_approved_ledger(req,[dict(requirement_id=l['id'],kind='DIRECT_SOURCE',source=dict(id='art',revision=1)) for l in selected],sources)
        result=compile_resources(act,spr,requirements=req,ledger=ledger,source_bytes=sources,isolation_strategy='always_append')
        expected={(l['runtime_slot'],l['frame'],l['source_layer_ordinal']):sources['art'] for l in selected}
        assert_effective_mapping(self,rust_report(act,spr),rust_report(result['act_bytes'],result['spr_bytes']),expected)
        old,new=read_spr(spr),read_spr(result['spr_bytes'])
        self.assertEqual((new.indexed_count,new.rgba_count),(old.indexed_count+1,old.rgba_count+1))
        self.assertEqual(old.palette,new.palette)
        for a,b in zip(old.indexed_images,new.indexed_images): self.assertEqual(a,b)

    @unittest.skipUnless(RUST_ORACLE_BIN.is_file(),'repository Rust oracle unavailable in installed distribution')
    def test_serializer_reconstruction_and_noop_are_separate_proofs(self):
        act,spr=synthetic_pair()
        noop=compile_resources(act,spr,compilation_mode='preserve')
        self.assertEqual((act,spr),(noop['act_bytes'],noop['spr_bytes']))
        reconstructed=(write_act(read_act(act)),write_spr(read_spr(spr)))
        self.assertEqual((act,spr),reconstructed)
        assert_effective_mapping(self,rust_report(act,spr),rust_report(*reconstructed),{})
        self.assertEqual(verify_pair_with_rust_oracle(*reconstructed,RUST_ORACLE_BIN)['result'],'AGREEMENT')

    @unittest.skipUnless(RUST_ORACLE_BIN.is_file(),'repository Rust oracle unavailable in installed distribution')
    def test_independent_comparison_detects_unchanged_reference_pixel_and_metadata_drift(self):
        act,spr=synthetic_pair(); original=rust_report(act,spr)
        for field in ('pixels','metadata','order'):
            with self.subTest(field=field):
                changed=copy.deepcopy(original)
                if field=='pixels':
                    image=changed['spr']['images'][changed['spr']['indexed_count']]
                    image['rgba']='00'+image['rgba'][2:]
                elif field=='metadata': changed['act']['actions'][0][0]['clips'][0]['x']+=1
                else: changed['act']['actions'][32][0]['clips'].reverse()
                with self.assertRaises(AssertionError): assert_effective_mapping(self,original,changed,{})

    def test_current_sources_and_approval_rechecked_with_existing_cache(self):
        act,spr,kw=canonical_fixture(full=True)
        result=compile_resources(act,spr,**kw,compilation_mode='production_export')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); cache=root/'cache'
            publish_compilation(root/'original',result,cache_dir=cache)
            snapshot={p:p.read_bytes() for p in cache.rglob('*') if p.is_file()}
            for failure in ('missing','corrupt','unapproved','stale','incomplete','revision'):
                with self.subTest(failure=failure):
                    bad=copy.deepcopy(kw); extra={}
                    if failure=='missing': bad['source_bytes'].pop('art')
                    elif failure=='corrupt': bad['source_bytes']['art']=b'corrupt'
                    elif failure=='unapproved': bad['ledger']['assignments'][0]['review']=None
                    elif failure=='stale': bad['ledger']['assignments'][0]['review']['basis_sha256']='f'*64
                    elif failure=='incomplete': bad['ledger']['assignments'].pop()
                    else: extra['expected_ledger_revision']=999
                    out=root/failure
                    with self.assertRaises(ForgeError):
                        current=compile_resources(act,spr,**bad,**extra,compilation_mode='production_export')
                        publish_compilation(out,current,cache_dir=cache)
                    self.assertFalse(out.exists())
                    self.assertEqual(snapshot,{p:p.read_bytes() for p in cache.rglob('*') if p.is_file()})
            entry=next(cache.iterdir()); (entry/'spr.spr').write_bytes(b'broken')
            with self.assertRaisesRegex(ForgeError,'CORRUPT_BUILD_CACHE'):
                publish_compilation(root/'corrupted',compile_resources(act,spr,**kw,compilation_mode='production_export'),cache_dir=cache)
            self.assertFalse((root/'corrupted').exists())

    def test_staged_source_failure_preserves_project_and_published_history(self):
        with tempfile.TemporaryDirectory() as root:
            act,spr,manifest,state,expected=staged_walk(root)
            manifest=mutate(root,manifest,'compile',dict(expected_revision=manifest['revision'],
                resource_id='original',compilation_id='previous-valid',replacement_policy='explicit_rgba'))['project']
            pid=manifest['project_id']; path=Path(root)/pid
            before={p:p.read_bytes() for p in path.rglob('*') if p.is_file()}
            data=dict(expected_revision=manifest['revision'],resource_id='original',compilation_id='invalid',replacement_policy='explicit_rgba')
            for failure in ('missing','corrupt','stale_revision','bad_occurrence','bad_policy'):
                with self.subTest(failure=failure):
                    request=copy.deepcopy(data)
                    source=next(iter(expected.values())); blob=path/'blobs'/digest(source)
                    if failure=='missing': blob.unlink()
                    elif failure=='corrupt': blob.write_bytes(b'corrupt')
                    elif failure=='stale_revision': request['expected_revision']-=1
                    elif failure=='bad_occurrence': request['replacement_requirement_ids']=['nonexistent-occurrence']
                    else: request['replacement_policy']='lossy_quantize'
                    with self.assertRaises(ForgeError): mutate(root,manifest,'compile',request)
                    self.assertFalse((path/'compilations/invalid').exists())
                    for p,raw in before.items():
                        if p!=blob: self.assertEqual(p.read_bytes(),raw)
                    blob.write_bytes(before[blob])
                    self.assertEqual(load_project(root,pid),manifest)


if __name__=='__main__': unittest.main()
