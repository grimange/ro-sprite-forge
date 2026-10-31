"""Execute native wrong-resource/selection controls and evidence tampering checks.

All mutations are copies beneath a new test directory. No original or candidate
is changed. A native run returning successfully is still rejected when it loaded
the wrong declared pair; a screenshot cannot override the provenance check.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess

from ro_sprite_forge.formats.act import read_act, write_act
from verify_walk import NativeMismatch, sha, verify


def controls(inputs_path, provenance_path, report_path, executable, stage, output):
    output.mkdir(parents=True, exist_ok=False)
    inputs = json.loads(inputs_path.read_text())
    provenance = json.loads(provenance_path.read_text())
    report = json.loads(report_path.read_text())
    directory = report_path.parent
    baseline = {v['path']: sha(Path(v['path']).read_bytes()) for v in inputs['files'].values()}
    results = []
    for name in ('original_instead_of_modified', 'wrong_act_pair', 'missing_file', 'missing_mount',
                 'hash_mismatch', 'invalid_frame', 'unsupported_action', 'invalid_pool_index'):
        candidate = copy.deepcopy(inputs)
        candidate['walk']['actors'] = [candidate['walk']['actors'][1]]
        modified = 'data\\sprite\\modified.'
        original = 'data\\sprite\\original.'
        if name == 'original_instead_of_modified':
            for extension in ('act', 'spr'):
                candidate['files'][modified + extension] = candidate['files'][original + extension]
        elif name == 'wrong_act_pair':
            candidate['files'][modified + 'act'] = candidate['files'][original + 'act']
        elif name == 'missing_file':
            candidate['files'][modified + 'spr']['path'] = str(output / 'absent.spr')
        elif name == 'missing_mount':
            del candidate['files'][modified + 'spr']
        elif name == 'hash_mismatch':
            candidate['files'][modified + 'spr']['sha256'] = '0' * 64
        elif name == 'invalid_frame':
            candidate['walk']['probe'] = dict(actor='modified', slot=8, frame=999)
        elif name == 'unsupported_action':
            candidate['walk']['actors'][0]['actions'] = ['Unsupported']
        else:
            act = read_act(Path(candidate['files'][modified + 'act']['path']).read_bytes())
            act['actions'][8][0]['clips'][0]['sprite'] = 99999
            raw = write_act(act)
            path = output / 'invalid-index.act'
            path.write_bytes(raw)
            candidate['files'][modified + 'act'] = dict(path=str(path), sha256=sha(raw))
        path = output / (name + '.json')
        path.write_text(json.dumps(candidate, sort_keys=True))
        destination = output / name
        env = dict(os.environ, VK_ICD_FILENAMES='/usr/share/vulkan/icd.d/lvp_icd.json')
        env.pop('DISPLAY', None)
        env.pop('WAYLAND_DISPLAY', None)
        argv = [str(executable), str(path), str(destination)]
        run = subprocess.run(argv, cwd=stage, env=env, text=True, capture_output=True, timeout=90)
        (output / (name + '.log')).write_text(run.stdout + run.stderr)
        expected = dict(missing_file='MISSING_MODIFIED_RESOURCE', missing_mount='RESOURCE_MOUNT_FAILED',
                        hash_mismatch='RESOURCE_MISMATCH', invalid_frame='INVALID_REQUESTED_FRAME',
                        unsupported_action='ACTION_UNSUPPORTED', invalid_pool_index='index out of bounds')
        if name in ('original_instead_of_modified', 'wrong_act_pair'):
            if run.returncode != 0:
                raise AssertionError(f'{name}: negative baseline must actually load and render: {run.stderr}')
            wrong = json.loads((destination / 'native-report.json').read_text())
            # Validate pair identity before any actor-coverage requirement.
            full = copy.deepcopy(inputs)
            full['files'] = candidate['files']
            try:
                verify(full, provenance, report, directory)
            except NativeMismatch as error:
                if 'PAIR_IDENTITY/modified/act' not in str(error):
                    raise
                diagnostic = 'PAIR_IDENTITY_MISMATCH'
            else:
                raise AssertionError('wrong pair incorrectly accepted')
            loaded = wrong['actors'][0]['loaded']
            observed = {r['path']: r['sha256'] for r in loaded}
        else:
            if run.returncode == 0 or (destination / 'native-report.json').exists():
                raise AssertionError(f'{name}: invalid native success/report')
            if expected[name] not in run.stderr:
                raise AssertionError(f'{name}: missing diagnostic {expected[name]}: {run.stderr}')
            diagnostic, observed = expected[name], None
        results.append(dict(case=name, argv=argv, native_exit=run.returncode,
                            diagnostic=diagnostic, accepted_as_exact=False, loaded=observed))
    mutations = {
        'wrong_loaded_hash': lambda r: r['actors'][1]['loaded'][0].update(sha256='0' * 64),
        'wrong_native_texture': lambda r: r['cases'][64]['sequence'][0]['selected'][0].update(image=0),
        'wrong_frame': lambda r: r['cases'][64]['sequence'][0].update(frame=999),
        'wrong_slot': lambda r: r['cases'][64].update(resolved_slot=0),
        'fallback_claimed_exact': lambda r: r['cases'][64].update(fallback='MODULO'),
        'unsupported_view': lambda r: r['cases'][64].update(requested_direction=8),
        'capture_hash': lambda r: r['cases'][64]['sequence'][0]['capture'].update(png_sha256='0' * 64),
        'missing_capture': lambda r: r['cases'][64]['sequence'][0].update(capture=None),
        'missing_negative_evidence': lambda r: r['negative_cases'].clear(),
    }
    for name, mutate in mutations.items():
        changed = copy.deepcopy(report)
        mutate(changed)
        try:
            verify(inputs, provenance, changed, directory)
        except NativeMismatch as error:
            results.append(dict(case=name, diagnostic=str(error), accepted_as_exact=False,
                                execution='checker_tampering_control'))
        else:
            raise AssertionError(f'{name}: altered evidence accepted')
    for path, digest in baseline.items():
        if sha(Path(path).read_bytes()) != digest:
            raise AssertionError('original input changed: ' + path)
    result = dict(result='NEGATIVE_CONTROLS_PASSED', cases=results, source_immutability='PASS')
    (output / 'results.json').write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(dict(result=result['result'], controls=len(results))))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for name in ('inputs', 'provenance', 'report', 'executable', 'stage', 'output'):
        parser.add_argument(name, type=Path)
    args = parser.parse_args()
    controls(args.inputs.resolve(), args.provenance.resolve(), args.report.resolve(),
             args.executable.resolve(), args.stage.resolve(), args.output.resolve())
