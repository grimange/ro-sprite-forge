"""Reproduce authoring/build, two native executions, independent checks and controls.

Requires the existing isolated pinned native executable/stage. No external
checkout is changed. Private fixture captures stay in the requested output.
"""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--stage', required=True, type=Path)
    parser.add_argument('--executable', required=True, type=Path)
    parser.add_argument('--private', action='store_true')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    tools = ROOT / 'tools/korangar-native'
    env = dict(os.environ, PYTHONPATH=str(ROOT / 'src'),
               VK_ICD_FILENAMES='/usr/share/vulkan/icd.d/lvp_icd.json')
    env.pop('DISPLAY', None)
    env.pop('WAYLAND_DISPLAY', None)
    commands = []

    def run(argv, name, cwd=ROOT):
        result = subprocess.run([str(v) for v in argv], cwd=cwd, env=env,
                                capture_output=True, text=True, timeout=180)
        (output / (name + '.log')).write_text(result.stdout + result.stderr)
        commands.append(dict(argv=result.args, cwd=str(cwd), exit=result.returncode))
        (output / 'commands.json').write_text(json.dumps(commands, indent=2) + '\n')
        result.check_returncode()

    run([sys.executable, tools / 'walk_fixture.py', output / 'input'] + (['--private'] if args.private else []), 'authoring')
    inputs = output / 'input/inputs.json'
    provenance = output / 'input/provenance.json'
    for number in (1, 2):
        run([args.executable.resolve(), inputs, output / f'native-{number}'], f'native-{number}', args.stage.resolve())
        run([sys.executable, tools / 'verify_walk.py', inputs, provenance,
             output / f'native-{number}/native-report.json'], f'checked-{number}')
    report = output / 'native-1/native-report.json'
    assert report.read_bytes() == (output / 'native-2/native-report.json').read_bytes(), 'native reports differ'
    for capture in (output / 'native-1').glob('*.png'):
        assert capture.read_bytes() == (output / 'native-2' / capture.name).read_bytes(), capture.name
    run([sys.executable, tools / 'walk_controls.py', inputs, provenance, report,
         args.executable.resolve(), args.stage.resolve(), output / 'controls'], 'controls')
    print(json.dumps(dict(result='REPRODUCED', commands=len(commands), native_reports_identical=True)))


if __name__ == '__main__':
    main()
