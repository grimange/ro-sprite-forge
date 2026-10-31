"""Read approved private hooks; publish only hashes/scoped findings, never artwork."""
import argparse
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[3]
sys.path[:0]=[str(ROOT/'src'),str(ROOT/'tests'),str(ROOT/'tests/private_fixture_hooks')]
from test_appearance_fixtures import PREFIXES,private_case
from test_registry_fixtures import _find_grf,_extract_from_grf,RUST_ORACLE_PATH
from ro_sprite_forge.core.compiler import verify_pair_with_rust_oracle
from ro_sprite_forge.core.canonical import canonical_bytes,digest
parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('output',type=Path);args=parser.parse_args()
grf=_find_grf()
if not grf:raise SystemExit('NOT_RUN: approved private GRF unavailable')
data={pid:_extract_from_grf(grf,prefix) for pid,prefix in PREFIXES.items()}
if not all(data.values()):raise SystemExit('NOT_RUN: approved private resources unavailable')
results={'oracle':{pid:verify_pair_with_rust_oracle(*pair,RUST_ORACLE_PATH) for pid,pair in data.items()},'combinations':[]}
for child,kind in [('jack-head-male-v1','HEAD_ACCESSORY'),('dragon-knight-male-shield-v1','EQUIPMENT_VISUAL')]:
    inputs={p:data[p] for p in ('genetic-female-body-v1',child)}
    reg,req,report=private_case('genetic-female-body-v1',child,inputs,kind)
    results['combinations'].append(dict(pairing_sha256=reg.get_cosmetic_pairing('actual-cosmetic')['canonical_sha256'],
        report_sha256=report['canonical_sha256'],identity=report['identity'],counts=report['counts'],
        status=report['status'],full_profile_status=report['full_profile_status'],
        unsupported=[r for r in report['slot_details'] if r['status']!='SUPPORTED'],
        native_korangar=report['dimensions']['native_korangar']))
args.output.write_bytes(canonical_bytes(results))
print('PRIVATE_METADATA_REPRODUCTION_PASS',digest(canonical_bytes(results)))
