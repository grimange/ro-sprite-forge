"""Build and test the installed distribution; requires pinned build tools only."""

import argparse
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile


def run(args, *, cwd, env):
    print(f"RUN {args!r} cwd={cwd}", flush=True)
    result = subprocess.run(args, cwd=cwd, env=env, text=True, capture_output=True, timeout=180)
    print(result.stdout, end="")
    print(result.stderr, end="", file=sys.stderr)
    print(f"EXIT {result.returncode}", flush=True)
    result.check_returncode()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", action="append", required=True, help="Interpreter to independently install and test; repeat for matrix.")
    parser.add_argument("--wheelhouse", required=True, help="Offline Pillow 12.1.1 wheels for each tested interpreter (test dependency only).")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["SOURCE_DATE_EPOCH"] = "1704067200"
    env["RSF_REPO_ROOT"] = str(repo.resolve())
    with tempfile.TemporaryDirectory(prefix="rsf1-dist-") as temporary:
        root = Path(temporary)
        dist = root / "dist"
        run([sys.executable, "-m", "build", "--no-isolation", "--outdir", str(dist), str(repo)], cwd=root, env=env)
        sdist, = dist.glob("*.tar.gz")
        with tarfile.open(sdist) as archive:
            names = archive.getnames()
            assert any(name.endswith("tests/test_foundation.py") for name in names)
            assert any(name.endswith("NOTICE.md") for name in names)
            assert not any("private_fixture_hooks" in name for name in names)
            assert not any(name.endswith((".act", ".spr", ".grf")) for name in names)
            for number in (1, 2):
                source = root / f"source-{number}"
                source.mkdir()
                archive.extractall(source, filter="data")
        wheels = []
        for number in (1, 2):
            source, = (root / f"source-{number}").iterdir()
            output = root / f"wheel-{number}"
            run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(output), str(source)], cwd=root, env=env)
            wheel, = output.glob("*.whl")
            wheels.append(wheel)
        assert digest(wheels[0]) == digest(wheels[1]), "Repeated wheel hashes differ"
        with zipfile.ZipFile(wheels[0]) as archive:
            names = archive.namelist()
            assert all(name.startswith(("ro_sprite_forge/", "ro_sprite_forge-0.1.0.dist-info/")) for name in names), names
            assert any(name.endswith("NOTICE.md") for name in names), "NOTICE.md must be packaged in wheel"
            assert not any(name.endswith((".act", ".spr", ".grf")) for name in names)
        print(f"SDIST_SHA256 {digest(sdist)}\nWHEEL_SHA256 {digest(wheels[0])}", flush=True)
        public_tests = root / "public-tests"
        public_tests.mkdir()
        for test in repo.glob("tests/test_*.py"):
            shutil.copy2(test, public_tests)
        shutil.copytree(repo / "docs/provenance", root / "docs/provenance")
        if (repo / "docs/operator").is_dir():
            shutil.copytree(repo / "docs/operator", root / "docs/operator")
        for number, interpreter in enumerate(args.python):
            venv = root / f"venv-{number}"
            run([interpreter, "--version"], cwd=root, env=env)
            run([interpreter, "-m", "venv", str(venv)], cwd=root, env=env)
            binary = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            run([str(binary), "-m", "pip", "install", "--no-index", "--no-deps", str(wheels[0])], cwd=root, env=env)
            code = "import pathlib,sys,ro_sprite_forge; p=pathlib.Path(ro_sprite_forge.__file__).resolve(); assert p.is_relative_to(pathlib.Path(sys.prefix).resolve()), p; print(p)"
            run([str(binary), "-I", "-c", code], cwd=root, env=env)
            # Inventory/requirements must import and run with stdlib only.
            smoke = """
import importlib.util
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.requirements import requirements
from ro_sprite_forge.core.preservation import roundtrip_pair
from ro_sprite_forge.formats.act import write_act
from ro_sprite_forge.formats.spr import write_rgba_spr, RgbaImage
assert importlib.util.find_spec('PIL') is None
a = write_act(dict(reserved='00'*10,actions=[[dict(bounds=(0,)*8,clips=[],event=-1,anchors=[])]],events=[],delays=[4.0]))
s = write_rgba_spr([RgbaImage(1,1,bytes(4))])
assert roundtrip_pair(a,s)[:2] == (a,s)
assert roundtrip_pair(a,s,mode='act-semantic')[:2] == (a,s)
p = get_profile('player')
i = inventory(a,s,profile=p)
t = dict(schema='rsf.target/v1',actor='synthetic',part='body',scope='scoped',actions=[dict(action='Walk',requirement='required',views=[dict(view=0,frame_count=1,topology=dict(kind='explicit',layers=['body']))])])
assert requirements(i,p,t)['totals']['required_layers_known'] == 1
print('STDLIB_CORE_PASS')
"""
            run([str(binary), "-I", "-c", smoke], cwd=root, env=env)
            run([str(binary), "-m", "pip", "install", "--no-index", "--find-links", str(Path(args.wheelhouse).resolve()), "--no-deps", "-r", str(repo / "requirements-test.txt")], cwd=root, env=env)
            run([str(binary), "-I", "-m", "unittest", "discover", "-s", str(public_tests), "-v"], cwd=root, env=env)
        print("DISTRIBUTION_CHECK_PASS", flush=True)


if __name__ == "__main__":
    main()
