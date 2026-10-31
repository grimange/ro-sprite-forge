"""RSF-26 independent effective-image regression; private bytes stay external."""
from pathlib import Path
import sys
import unittest

for directory in (Path(__file__).resolve().parent, Path(__file__).resolve().parents[1]):
    if str(directory) not in sys.path:
        sys.path.insert(0, str(directory))

from test_audited_fixtures import AUDITED_HASHES, find_fixture
from test_walk_compilation import (walk_contracts, rust_report, assert_effective_mapping,
    _make_png, _build_approved_ledger, RUST_ORACLE_BIN)
from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.compiler import compile_resources, verify_pair_with_rust_oracle
from ro_sprite_forge.formats.act import read_act, write_act
from ro_sprite_forge.formats.spr import read_spr, write_spr


def private_regression(case, name):
    keys = ['novice_body_act','novice_body_spr','novice_head_act','novice_head_spr'] if name=='novice' else ['orc_skeleton_act','orc_skeleton_spr']
    paths = {key: find_fixture(key) for key in keys}
    if not all(paths.values()): case.skipTest('Private audited resources unavailable: '+name)
    sources = {key: path.read_bytes() for key,path in paths.items()}
    for key,raw in sources.items(): case.assertEqual(digest(raw),AUDITED_HASHES[key])
    act,spr = [sources[key] for key in keys[:2]]
    heads=tuple(sources[key] for key in keys[2:]) if name=='novice' else None
    actor,profile,target,inv,req = walk_contracts(act,spr,category='player' if heads else 'monster',
        actor_id='novice-male' if heads else 'orc-skeleton',heads=heads)
    selected=next(l for l in req['layers'] if l['view']==0 and l['frame']==0 and l['ordinal']==0)
    art={'walk-art':_make_png(24,32,(10,180,220,255),gradient=True)}
    ledger=_build_approved_ledger(req,[dict(requirement_id=selected['id'],kind='DIRECT_SOURCE',source=dict(id='walk-art',revision=1))],art)
    kwargs=dict(requirements=req,ledger=ledger,source_bytes=art,replacement_policy='explicit_rgba',oracle_executable=RUST_ORACLE_BIN)
    if heads: kwargs.update(head_act_bytes=heads[0],head_spr_bytes=heads[1])
    result=compile_resources(act,spr,**kwargs)
    before,after=rust_report(act,spr),rust_report(result['act_bytes'],result['spr_bytes'])
    mapping=assert_effective_mapping(case,before,after,
        {(selected['runtime_slot'],selected['frame'],selected['source_layer_ordinal']):art['walk-art']})
    case.assertEqual(mapping['targeted'],1)
    # All original indexed entries retain their encoded payload, palette and dimensions.
    old,new=read_spr(spr),read_spr(result['spr_bytes'])
    case.assertEqual(old.indexed_images,new.indexed_images)
    case.assertEqual(old.palette,new.palette)
    untouched=[]
    for slot,(a,b) in enumerate(zip(before['act']['actions'],after['act']['actions'])):
        if slot!=selected['runtime_slot']: case.assertEqual(a,b); untouched.append(slot)
    if heads:
        case.assertEqual((result['head_act_bytes'],result['head_spr_bytes']),heads)
        case.assertEqual(rust_report(*heads),rust_report(result['head_act_bytes'],result['head_spr_bytes']))
        case.assertEqual((mapping['slots'],mapping['frames'],len(untouched)),(104,456,103))
    else:
        case.assertEqual((mapping['slots'],mapping['frames'],mapping['targeted']+mapping['unaffected']),(40,512,1776))
    death_slots=next(a['slots'] for a in profile.to_dict()['actions'] if a['id']=='Die')
    death=[(s,f,m) for s in death_slots for f,m in enumerate(before['act']['actions'][s])]
    max_layers=max(sum(c['sprite']>=0 for c in m['clips']) for _,_,m in death)
    if not heads: case.assertEqual(max_layers,12)
    max_frames=[]
    for slot,frame,motion in death:
        if sum(c['sprite']>=0 for c in motion['clips'])==max_layers:
            case.assertEqual(motion,after['act']['actions'][slot][frame])
            max_frames.append(dict(slot=slot,frame=frame,layers=max_layers))
    for key,path in paths.items(): case.assertEqual(path.read_bytes(),sources[key])
    return dict(fixture=name,inputs={key:digest(raw) for key,raw in sources.items()},
        selected=selected,requirements_sha256=req['canonical_sha256'],ledger_sha256=ledger.get('canonical_sha256'),
        target=target.to_dict(),requirements=req,ledger=ledger,
        source_png_sha256=digest(art['walk-art']),outputs=dict(act_sha256=digest(result['act_bytes']),
        spr_sha256=digest(result['spr_bytes']),build=result['manifest']['build']),
        comparison=mapping,unaffected_slots=len(untouched),max_death_frames=max_frames,
        oracle=result['manifest']['verification'],
        rust_before_sha256=digest(canonical_bytes(before)),rust_after_sha256=digest(canonical_bytes(after)),head_unchanged=bool(heads))


@unittest.skipUnless(RUST_ORACLE_BIN.is_file(),'Independent Rust oracle unavailable')
class WalkPrivateRegressionTests(unittest.TestCase):
    def test_novice_every_occurrence_and_separate_head(self):
        private_regression(self,'novice')

    def test_orc_bounded_walk_and_all_twelve_layer_death_frames(self):
        private_regression(self,'orc')

    def test_orc_serializer_reconstruction_is_not_only_noop(self):
        paths=[find_fixture('orc_skeleton_'+ext) for ext in ('act','spr')]
        if not all(paths): self.skipTest('Audited Orc fixtures unavailable')
        original=tuple(p.read_bytes() for p in paths)
        for ext,raw in zip(('act','spr'),original): self.assertEqual(digest(raw),AUDITED_HASHES['orc_skeleton_'+ext])
        reconstructed=write_act(read_act(original[0])),write_spr(read_spr(original[1]))
        self.assertEqual(reconstructed,original)
        noop=compile_resources(*original,compilation_mode='preserve')
        self.assertEqual((noop['act_bytes'],noop['spr_bytes']),original)
        comparison=assert_effective_mapping(self,rust_report(*original),rust_report(*reconstructed),{})
        self.assertEqual(comparison['unaffected'],1776)
        self.assertEqual(verify_pair_with_rust_oracle(*reconstructed,RUST_ORACLE_BIN)['result'],'AGREEMENT')
        self.assertEqual(tuple(p.read_bytes() for p in paths),original)


if __name__=='__main__': unittest.main()
