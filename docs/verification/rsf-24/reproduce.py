"""Reproduce the public RSF-24 golden compile; requires repository test/oracle tools."""
from pathlib import Path
import hashlib
import json
import platform
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tests'))
from test_image_pool_remapping import ImagePoolRemappingTests, RUST_ORACLE_BIN
from ro_sprite_forge.core.compiler import compile_resources
from ro_sprite_forge.core.canonical import canonical_bytes


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    act, spr, inputs = ImagePoolRemappingTests().inputs()
    runs = [compile_resources(act, spr, **inputs, replacement_policy='explicit_rgba',
                              oracle_executable=RUST_ORACLE_BIN) for _ in range(3)]
    first = runs[0]
    for run in runs[1:]:
        assert run['act_bytes'] == first['act_bytes']
        assert run['spr_bytes'] == first['spr_bytes']
        assert canonical_bytes(run['manifest']) == canonical_bytes(first['manifest'])
    assert first['manifest']['verification']['rust_oracle'] == 'PASS'
    output = Path(__file__).resolve().parent
    manifest = canonical_bytes(first['manifest'])
    (output / 'golden-manifest.json').write_bytes(manifest)
    environment = {
        'python': sys.version, 'platform': platform.platform(),
        'oracle_sha256': sha(RUST_ORACLE_BIN.read_bytes()),
        'input_act': sha(act), 'input_spr': sha(spr),
        'output_act': sha(first['act_bytes']), 'output_spr': sha(first['spr_bytes']),
        'manifest_sha256': sha(manifest),
        'canonical_compilation_sha256': first['manifest']['canonical_sha256'],
        'independent_runs_equal': len(runs),
        'native_korangar': first['manifest']['verification']['native_korangar'],
    }
    (output / 'environment.json').write_text(json.dumps(environment, indent=2) + '\n')
    print(json.dumps(environment, indent=2))


if __name__ == '__main__':
    main()
