"""Optional test adapter: each decoder reads original bytes; no runtime integration."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.canonical import canonical_bytes
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.spr import read_spr


def sha(data):
    return hashlib.sha256(data).hexdigest()


def bits(value):
    return struct.unpack('<I', struct.pack('<f', value))[0]


def python_report(act, spr):
    inventory(act, spr)  # Mandatory paired validity, not just a permissive raw parse.
    a = copy.deepcopy(read_act(act))
    a['version'] = '2.4'
    a['delays'] = [bits(v) for v in a['delays']]
    for action in a['actions']:
        for motion in action:
            motion['bounds'] = list(motion['bounds'])
            for layer in motion['clips']:
                for k in ('scale_x', 'scale_y'):
                    layer[k] = bits(layer[k])
    s = read_spr(spr)
    images = []
    for pool, entries in enumerate((s.indexed_images, s.rgba_images)):
        for index, image in enumerate(entries):
            images.append(dict(pool=pool, index=index, width=image.width, height=image.height,
                               indices=image.pixels.hex() if pool == 0 else None,
                               rgba=(image.to_rgba(s.palette) if pool == 0 else image.rgba).hex()))
    return dict(schema='rsf.oracle-structure/v1', sources=dict(act=sha(act), spr=sha(spr)),
                act=a, spr=dict(version='2.1', indexed_count=s.indexed_count,
                               truecolor_count=s.rgba_count, palette=s.palette.hex(), images=images))


def differences(left, right, location='$'):
    """Compare every field, including missing/extra keys and ordered sequences."""
    if type(left) is not type(right):
        return [dict(location=location, python=left, rust=right)]
    if isinstance(left, dict):
        result = []
        for k in sorted(left.keys() | right.keys()):
            if k not in left or k not in right:
                result.append(dict(location=f'{location}.{k}', python=left.get(k), rust=right.get(k), missing=True))
            else:
                result.extend(differences(left[k], right[k], f'{location}.{k}'))
        return result
    if isinstance(left, list):
        if len(left) != len(right):
            return [dict(location=location+'.length', python=len(left), rust=len(right))]
        return [v for i, (a, b) in enumerate(zip(left, right)) for v in differences(a,b,f'{location}[{i}]')]
    return [] if left == right else [dict(location=location, python=left, rust=right)]


def summarize(report):
    actions = report['act']['actions']
    layers = [l for a in actions for m in a for l in m['clips']]
    refs = {(l['pool'], l['sprite']) for l in layers if l['sprite'] >= 0}
    images = report['spr']['images']
    content = {(i['pool'],i['index']):sha(struct.pack('<II',i['width'],i['height'])+bytes.fromhex(i['rgba'])) for i in images}
    return dict(groups=(len(actions)+7)//8, slots=len(actions), motions=sum(map(len,actions)),
                layers=len(layers), visible_layers=sum(l['sprite']>=0 for l in layers),
                referenced=len(refs), stored=len(images),
                unused=[list(k) for k in sorted(content.keys()-refs)],
                distinct_referenced_contents=len({content[k] for k in refs}))


def compare(executable, act_path, spr_path):
    act, spr = Path(act_path).read_bytes(), Path(spr_path).read_bytes()
    p = python_report(act, spr)
    result = subprocess.run([str(executable), str(act_path), str(spr_path)], capture_output=True, check=True)
    r = json.loads(result.stdout)
    diff = differences(p, r)
    return dict(schema='rsf.oracle-parity/v1', result='MISMATCH' if diff else 'AGREEMENT',
                sources=p['sources'], python_report_sha256=sha(canonical_bytes(p)),
                rust_report_sha256=sha(canonical_bytes(r)), mismatches=diff,
                python_summary=summarize(p), rust_summary=summarize(r))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--oracle',required=True)
    parser.add_argument('--act',required=True)
    parser.add_argument('--spr',required=True)
    args = parser.parse_args()
    result = compare(args.oracle,args.act,args.spr)
    print(canonical_bytes(result).decode(),end='')
    return int(result['result'] != 'AGREEMENT')

if __name__ == '__main__':
    raise SystemExit(main())
