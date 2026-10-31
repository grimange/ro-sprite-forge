"""RSF-24 public golden mappings; expected selection uses independent Rust bytes."""
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from ro_sprite_forge.core.compiler import compile_resources, plan_compilation, image_reference_inventory, publish_compilation
from ro_sprite_forge.core.canonical import canonical_bytes
from ro_sprite_forge.core.errors import ForgeError
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.spr import read_spr, write_spr
from test_compiler import (_build_synthetic_monster_act_spr, _setup_monster_contracts,
    _find_layer_id, _make_png, _build_approved_ledger, RUST_ORACLE_BIN)


class ImagePoolRemappingTests(unittest.TestCase):
    def fixture(self, mode='mixed'):
        act, spr = _build_synthetic_monster_act_spr()
        a, s = read_act(act), read_spr(spr)
        if mode != 'mixed':
            for motions in a['actions']:
                for motion in motions:
                    for clip in motion['clips']:
                        if clip['sprite'] >= 0:
                            clip['pool'] = 0 if mode == 'indexed' else 1
                            clip['sprite'] = clip['sprite'] if mode == 'indexed' and clip['sprite'] < 5 else 0
            if mode == 'indexed': s.rgba_images = ()
            else: s.indexed_images = ()
        a['actions'][0][0]['clips'][0].update(pool=1 if mode != 'indexed' else 0, sprite=0)
        # Keep unused and duplicate images, including non-minimal original zero RLE.
        return write_act(a), write_spr(s)

    def inputs(self, mode='mixed', colors=((255,0,255,255),(0,255,255,255))):
        act, spr = self.fixture(mode)
        req = _setup_monster_contracts(act, spr, include_die=True)[-1]
        ids = [_find_layer_id(req, 'Walk', 0, i) for i in (0, 3)]
        sources = {f'src{i}': _make_png(4,4,c) for i,c in enumerate(colors)}
        ledger = _build_approved_ledger(req,[{'requirement_id':rid,'kind':'DIRECT_SOURCE',
            'source':{'id':f'src{i}','revision':1}} for i,rid in enumerate(ids)], sources)
        return act, spr, dict(requirements=req,ledger=ledger,source_bytes=sources,replacement_requirement_ids=ids)

    @unittest.skipUnless(RUST_ORACLE_BIN.is_file(), "optional repository Rust executable unavailable in installed distribution")
    def test_pool_matrix_complete_effective_mapping_and_rust(self):
        self.assertTrue(RUST_ORACLE_BIN.is_file(), 'independent oracle required')
        for mode in ('indexed','rgba','mixed'):
            for policy in ('preserve_pool','explicit_rgba','indexed_exact'):
                with self.subTest(mode=mode,policy=policy):
                    act,spr,kw=self.inputs(mode)
                    result=compile_resources(act,spr,**kw,replacement_policy=policy,isolation_strategy='always_append',oracle_executable=RUST_ORACLE_BIN)
                    m=result['manifest']; evidence=m['remapping']
                    out_spr=read_spr(result['spr_bytes'])
                    self.assertEqual(out_spr.palette,read_spr(spr).palette)
                    for old,new in zip(read_spr(spr).indexed_images,out_spr.indexed_images):
                        self.assertEqual(old.raw_rle,new.raw_rle)
                    targeted={(r['slot'],r['frame'],r['clip_ordinal']):r for r in m['replacements']}
                    with tempfile.TemporaryDirectory() as tmp:
                        ap,sp=Path(tmp)/'a.act',Path(tmp)/'s.spr'
                        ap.write_bytes(result['act_bytes']);sp.write_bytes(result['spr_bytes'])
                        proc=subprocess.run([str(RUST_ORACLE_BIN),str(ap),str(sp)],capture_output=True,check=True)
                        report=json.loads(proc.stdout)
                    # Independently select using runtime concatenated texture order from Rust decoded data.
                    textures=report['spr']['images']
                    for before,after in zip(evidence['before'],evidence['after']):
                        loc=tuple(after[k] for k in ('slot','frame','layer'))
                        clip=report['act']['actions'][loc[0]][loc[1]]['clips'][loc[2]]
                        tex=clip['sprite']+(report['spr']['indexed_count'] if clip['pool']==1 else 0)
                        selected=textures[tex]
                        self.assertEqual((selected['pool'],selected['index']),(after['pool'],after['index']))
                        if loc in targeted:
                            source=kw['source_bytes'][targeted[loc]['source_id']]
                            self.assertEqual(bytes.fromhex(selected['rgba']),Image.open(io.BytesIO(source)).convert('RGBA').tobytes())
                        else:
                            self.assertEqual(before['decoded_rgba_sha256'],after['decoded_rgba_sha256'])
                        self.assertEqual(before['metadata_sha256'],after['metadata_sha256'])
                    again=compile_resources(act,spr,**{**kw,'replacement_requirement_ids':list(reversed(kw['replacement_requirement_ids']))},replacement_policy=policy,isolation_strategy='always_append',oracle_executable=RUST_ORACLE_BIN)
                    self.assertEqual(result['act_bytes'],again['act_bytes'])
                    self.assertEqual(result['spr_bytes'],again['spr_bytes'])
                    self.assertEqual(canonical_bytes(m),canonical_bytes(again['manifest']))
                    self.assertFalse(m['status']['production_authorized'])
                    self.assertEqual(m['verification']['native_korangar'],'UNVERIFIED')

    def test_indexed_append_moves_truecolor_texture_position(self):
        act,spr,kw=self.inputs()
        m=compile_resources(act,spr,**kw,replacement_policy='preserve_pool',isolation_strategy='always_append')['manifest']
        unchanged=[(a,b) for a,b in zip(m['remapping']['before'],m['remapping']['after']) if a['pool']==1 and a['slot']!=8]
        self.assertTrue(unchanged)
        for a,b in unchanged:
            self.assertEqual(a['index'],b['index'])
            self.assertGreater(b['texture_index'],a['texture_index'])
            self.assertEqual(a['decoded_rgba_sha256'],b['decoded_rgba_sha256'])

    def test_identical_replacements_share_only_exact_pool_entry(self):
        act,spr,kw=self.inputs(colors=((255,0,255,255),)*2)
        m=compile_resources(act,spr,**kw,replacement_policy='explicit_rgba')['manifest']
        self.assertEqual(m['replacements'][0]['output_image'],m['replacements'][1]['output_image'])
        self.assertEqual(m['remapping']['output_counts'],[5,2])
        self.assertEqual(len(m['remapping']['conversion_loss']),1)

    def test_plan_rejects_unrepresentable_conversion(self):
        for color in ((23,42,63,255),(255,0,0,128),(1,2,3,0)):
            act,spr,kw=self.inputs(colors=(color,color))
            plan=plan_compilation(act,spr,**kw,replacement_policy='indexed_exact')
            self.assertFalse(plan['ready_to_compile'])
            self.assertIn('UNSUPPORTED_INDEXED_CONVERSION',str(plan['blockers']))
            with self.assertRaisesRegex(ForgeError,'UNSUPPORTED_INDEXED_CONVERSION'):
                compile_resources(act,spr,**kw,replacement_policy='indexed_exact')

    def test_plan_matches_actual_remapping(self):
        act,spr,kw=self.inputs()
        plan=plan_compilation(act,spr,**kw)
        result=compile_resources(act,spr,**kw)
        self.assertEqual(plan['remapping'],result['manifest']['remapping'])
        self.assertEqual(plan['selected_replacements'],result['manifest']['replacements'])

    def test_invalid_reference_reports_exact_occurrence(self):
        act,spr=self.fixture()
        for pool,index in ((2,0),(0,5),(1,1),(0,-2)):
            a=read_act(act);a['actions'][8][0]['clips'][0].update(pool=pool,sprite=index)
            with self.assertRaisesRegex(ForgeError,'slot=8 frame=0 layer=0'):
                image_reference_inventory(a,read_spr(spr))

    def test_publication_rejects_tampered_pair_and_preserves_existing_files(self):
        act,spr=self.fixture()
        result=compile_resources(act,spr,compilation_mode='preserve')
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'compiled.act';p.write_bytes(b'existing')
            with self.assertRaises(ForgeError): publish_compilation(tmp,result)
            self.assertEqual(p.read_bytes(),b'existing')
        result['spr_bytes']=result['spr_bytes'][:-1]
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaisesRegex(ForgeError,'COMPILATION_PAIR_MISMATCH'): publish_compilation(tmp,result)
            self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_duplicate_unused_originals_keep_distinct_identities(self):
        from ro_sprite_forge.formats.spr import SprDocument
        act,spr,kw=self.inputs()
        original=read_spr(spr)
        extra=SprDocument(list(original.indexed_images)+[original.indexed_images[0]],
                          list(original.rgba_images)+[original.rgba_images[0]],original.palette)
        # Rebuild contracts because the original resource identity has changed.
        spr=write_spr(extra)
        req=_setup_monster_contracts(act,spr,include_die=True)[-1]
        rid=_find_layer_id(req,'Walk',0,0)
        sources={'src':_make_png(4,4,(255,0,255,255))}
        ledger=_build_approved_ledger(req,[{'requirement_id':rid,'kind':'DIRECT_SOURCE','source':{'id':'src','revision':1}}],sources)
        result=compile_resources(act,spr,requirements=req,ledger=ledger,source_bytes=sources,replacement_policy="explicit_rgba")
        out=read_spr(result['spr_bytes'])
        self.assertEqual(out.indexed_count,6)
        self.assertEqual(out.rgba_count,3)
        self.assertEqual(out.indexed_images[5].raw_rle,extra.indexed_images[5].raw_rle)
        self.assertEqual(out.rgba_images[1],extra.rgba_images[1])
        self.assertEqual(result['manifest']['replacements'][0]['output_image']['index'],2)

    def test_noop_identity_for_each_pool_layout(self):
        for mode in ('mixed','indexed','rgba'):
            act,spr=self.fixture(mode)
            result=compile_resources(act,spr,compilation_mode='preserve')
            self.assertEqual((act,spr),(result['act_bytes'],result['spr_bytes']))

    def test_omitted_policy_preserves_representation_and_rejects_implicit_loss(self):
        act,spr,kw=self.inputs()
        result=compile_resources(act,spr,**kw)
        self.assertEqual(result['manifest']['replacement_policy'],'preserve_pool')
        self.assertTrue(all(r['output_image']['pool']==r['original_image']['pool'] for r in result['manifest']['replacements']))
        act,spr,kw=self.inputs(colors=((23,42,63,255),)*2)
        self.assertFalse(plan_compilation(act,spr,**kw)['ready_to_compile'])
        with self.assertRaisesRegex(ForgeError,'UNSUPPORTED_INDEXED_CONVERSION'):
            compile_resources(act,spr,**kw)
        explicit=compile_resources(act,spr,**kw,replacement_policy='explicit_rgba')
        self.assertTrue(all(r['output_image']['pool']==1 for r in explicit['manifest']['replacements']))

    def test_generated_bounded_manifest_schema_and_required_remapping(self):
        from ro_sprite_forge.core.compiler import compilation_manifest_schema, validate_compilation_manifest
        from ro_sprite_forge.core.canonical import sealed
        act,spr,kw=self.inputs()
        manifest=compile_resources(act,spr,**kw)['manifest']
        try:
            import jsonschema
        except ImportError:
            jsonschema=None
        if jsonschema is not None:
            jsonschema.validate(manifest,compilation_manifest_schema())
        del manifest['remapping']
        del manifest['canonical_sha256']
        with self.assertRaisesRegex(ForgeError,'INVALID_REMAPPING'):
            validate_compilation_manifest(sealed(manifest))

    def test_publication_rejects_corrupted_or_missing_head_pair(self):
        act,spr=self.fixture()
        for key, bad in (('head_act_bytes',None),('head_spr_bytes',None),('head_spr_bytes',b'broken')):
            result=compile_resources(act,spr,compilation_mode='preserve',head_act_bytes=act,head_spr_bytes=spr)
            result[key]=bad
            with tempfile.TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(ForgeError,'COMPILATION_PAIR_MISMATCH'):
                    publish_compilation(tmp,result)
                self.assertEqual(list(Path(tmp).iterdir()),[])

    def test_highest_supported_index_and_append_count_overflow(self):
        from ro_sprite_forge.formats.spr import SprDocument, MAX_SPR_IMAGES
        act,spr,_=self.inputs()
        original=read_spr(spr)
        full=SprDocument([original.indexed_images[0]]*MAX_SPR_IMAGES,[],original.palette)
        a=read_act(act)
        for motions in a['actions']:
            for motion in motions:
                for clip in motion['clips']:
                    if clip['sprite']>=0:clip.update(pool=0,sprite=MAX_SPR_IMAGES-1)
        act,spr=write_act(a),write_spr(full)
        rows=image_reference_inventory(read_act(act),read_spr(spr))
        self.assertTrue(all(row['index']==MAX_SPR_IMAGES-1 for row in rows))
        req=_setup_monster_contracts(act,spr,include_die=True)[-1]
        rid=_find_layer_id(req,'Walk',0,0)
        sources={'src':_make_png(4,4,(255,0,255,255))}
        ledger=_build_approved_ledger(req,[{'requirement_id':rid,'kind':'DIRECT_SOURCE','source':{'id':'src','revision':1}}],sources)
        with self.assertRaises(ForgeError):
            compile_resources(act,spr,requirements=req,ledger=ledger,source_bytes=sources,isolation_strategy='always_append')
        a['actions'][0][0]['clips'][0]['sprite']=MAX_SPR_IMAGES
        with self.assertRaisesRegex(ForgeError,'INVALID_IMAGE_REFERENCE'):
            image_reference_inventory(a,read_spr(spr))
