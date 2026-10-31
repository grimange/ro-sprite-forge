"""Reproduce public synthetic action evidence; no private artwork or runtime claim."""
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests')]
from ro_sprite_forge.core.canonical import canonical_bytes,digest
from ro_sprite_forge.core.custom_actions import action_support,preview_offline_action
from ro_sprite_forge.core.compiler import compile_resources
from test_custom_actions import fixture,bound_fixture
from test_compiler import RUST_ORACLE_BIN

def reproduce(out):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    a,p,t,r,l,s=fixture()
    docs={'target':t.to_dict(),'requirements':r,'ledger':l,'support':action_support(t,actor=a,profile=p)}
    for name,doc in docs.items():(out/(name+'.json')).write_bytes(canonical_bytes(doc))
    frames=[]
    for frame in range(4):
        result=preview_offline_action(t,actor=a,profile=p,ledger=l,source_bytes=s,action_id='Wave',view=0,frame=frame,canvas_size=(16,16))
        (out/f'wave-{frame}.png').write_bytes(result['png_bytes']);frames.append(result['offline'])
    (out/'previews.json').write_bytes(canonical_bytes(frames))
    runs=[]
    for name in ('Guard','Dodge'):
        act,spr,a,p,t,inv,kw=bound_fixture(name)
        (out/f'{name}-requirements.json').write_bytes(canonical_bytes(kw['requirements']))
        result=compile_resources(act,spr,**kw,oracle_executable=RUST_ORACLE_BIN if RUST_ORACLE_BIN.is_file() else None)
        again=compile_resources(act,spr,**kw)
        assert result['act_bytes']==again['act_bytes'] and result['spr_bytes']==again['spr_bytes']
        assert result['manifest']['build']==again['manifest']['build']
        (out/f'{name}-compilation.json').write_bytes(canonical_bytes(result['manifest']))
        runs.append(dict(action=name,original_act_sha256=digest(act),original_spr_sha256=digest(spr),
            output_act_sha256=digest(result['act_bytes']),output_spr_sha256=digest(result['spr_bytes']),
            build_manifest_sha256=digest(canonical_bytes(result['manifest']['build'])),
            build=result['manifest']['build'],verification=result['manifest']['verification'],
            support=action_support(t,actor=a,profile=p,inventories=(inv,)),repeated_binary_mismatches=0))
    (out/'compilations.json').write_bytes(canonical_bytes(runs))
    hashes={p.name:digest(p.read_bytes()) for p in sorted(out.iterdir()) if p.is_file() and p.name!='artifacts.json'}
    (out/'artifacts.json').write_bytes(canonical_bytes(hashes))
    print(canonical_bytes(runs).decode())
if __name__=='__main__':reproduce(sys.argv[1])
