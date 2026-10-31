"""Optional audited private fixture runner; writes only hashes/counts to stdout."""
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'tests/private_fixture_hooks'))
from test_audited_fixtures import find_fixture,AUDITED_HASHES
from parity import compare,sha

results=[]
for name in ('novice_body','novice_head','orc_skeleton'):
    a,s=[find_fixture(name+'_'+ext) for ext in ('act','spr')]
    if not a or not s:
        results.append(dict(fixture=name,result='NOT_RUN'));continue
    assert sha(a.read_bytes())==AUDITED_HASHES[name+'_act']
    assert sha(s.read_bytes())==AUDITED_HASHES[name+'_spr']
    r=compare((Path(__file__).parent/'target/debug/rsf-rust-oracle').resolve(),a,s)
    assert r==compare((Path(__file__).parent/'target/debug/rsf-rust-oracle').resolve(),a,s)
    assert r['result']=='AGREEMENT',r['mismatches']
    summary=r['rust_summary']
    if name=='novice_body':
        assert [summary[k] for k in ('groups','slots','motions','referenced','distinct_referenced_contents')]==[13,104,456,110,108]
    elif name=='orc_skeleton':
        assert [summary[k] for k in ('groups','slots','motions','visible_layers','referenced','stored')]==[5,40,512,1776,55,57]
        assert summary['unused']==[[0,36],[0,39]]
    r['fixture']=name;results.append(r)
print(json.dumps(results,sort_keys=True,indent=2))
raise SystemExit(int(any(r['result']!='AGREEMENT' for r in results)))
