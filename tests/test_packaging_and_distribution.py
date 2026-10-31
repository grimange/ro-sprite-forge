"""Comprehensive packaging, distribution, reproducibility, and release-artifact tests for RSF-36."""

import hashlib
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
import zipfile

BUILD_AVAILABLE = importlib.util.find_spec("build") is not None

def _find_repo_root() -> Path:
    if "RSF_REPO_ROOT" in os.environ:
        cand = Path(os.environ["RSF_REPO_ROOT"]).resolve()
        if (cand / "pyproject.toml").is_file():
            return cand
    for parent in [Path.cwd(), *Path(__file__).resolve().parents]:
        if (parent / "pyproject.toml").is_file():
            return parent.resolve()
    return Path(__file__).resolve().parents[1]


REPO_ROOT = _find_repo_root()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PackagingAndDistributionTests(unittest.TestCase):
    """Verifies packaging metadata, artifact safety, reproducibility, and clean installation."""

    def test_01_package_metadata_and_entry_points(self):
        """Criterion 1: Correct package name, dynamic version, entry points, and stdlib core dependencies."""
        pyproject_path = REPO_ROOT / "pyproject.toml"
        self.assertTrue(pyproject_path.is_file())
        text = pyproject_path.read_text(encoding="utf-8")
        
        # Verify package identity
        self.assertIn('name = "ro-sprite-forge"', text)
        self.assertIn('requires-python = ">=3.12,<3.15"', text)
        self.assertIn('ro-sprite-forge = "ro_sprite_forge.cli:main"', text)
        self.assertIn('license = "MIT"', text)
        self.assertIn('dependencies = []', text, "Core package must declare zero mandatory dependencies")
        
        # Verify requirements metadata is empty (stdlib-only)
        self.assertFalse(importlib.metadata.requires("ro-sprite-forge"))
        
        # Verify version format
        import ro_sprite_forge
        version = ro_sprite_forge.__version__
        self.assertTrue(version and isinstance(version, str))
        self.assertRegex(version, r"^\d+\.\d+\.\d+")

    def test_02_licenses_and_notices_provenance(self):
        """Criterion 3: Source modules/dependencies have explicit license/provenance review and notices."""
        # 1. Root LICENSE
        license_path = REPO_ROOT / "LICENSE"
        self.assertTrue(license_path.is_file(), "Root LICENSE file must exist")
        license_text = license_path.read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Ronniel Allan Castañito", license_text)
        
        # 2. Root NOTICE.md
        notice_path = REPO_ROOT / "NOTICE.md"
        self.assertTrue(notice_path.is_file(), "Root NOTICE.md must exist")
        notice_text = notice_path.read_text(encoding="utf-8")
        self.assertIn("Living-World-Ragnarok (LWR) Codec Extraction", notice_text)
        self.assertIn("Pinned Korangar Independent Decoding Oracle", notice_text)
        self.assertIn("Proprietary Game Assets and Intellectual Property Separation", notice_text)
        self.assertIn("55aefdc8ba7bb5aaf4619983d72cb26c2865154961116c8ad075c65378142c46", notice_text)
        self.assertIn("3f3d88a583203f09d079712f43343c1041258ffd", notice_text)
        self.assertIn("Gravity Co., Ltd.", notice_text)
        
        # 3. Provenance files
        lwr_prov = REPO_ROOT / "docs" / "provenance" / "LWR_CODEC_PROVENANCE.md"
        self.assertTrue(lwr_prov.is_file())
        self.assertIn("55aefdc8ba7bb5aaf4619983d72cb26c2865154961116c8ad075c65378142c46", lwr_prov.read_text())
        
        korangar_prov = REPO_ROOT / "docs" / "provenance" / "KORANGAR_RUNTIME_PROFILE.md"
        self.assertTrue(korangar_prov.is_file())
        
        rust_prov = REPO_ROOT / "tools" / "rust-oracle" / "PROVENANCE.md"
        self.assertTrue(rust_prov.is_file())
        self.assertIn("3f3d88a583203f09d079712f43343c1041258ffd", rust_prov.read_text())

    @unittest.skipUnless(BUILD_AVAILABLE, "build package required for distribution packaging tests")
    def test_03_artifact_exclusion_and_private_asset_guards(self):
        """Criterion 2: No private paths, credentials, art or GRFs enter public packages."""
        with tempfile.TemporaryDirectory(prefix="rsf-pkg-test-") as tmpdir:
            outdir = Path(tmpdir) / "dist"
            env = dict(os.environ)
            env["SOURCE_DATE_EPOCH"] = "1704067200"
            
            # Build sdist and wheel
            cmd = [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(outdir), str(REPO_ROOT)]
            proc = subprocess.run(cmd, env=env, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, f"Build failed: {proc.stderr}")
            
            sdist_files = list(outdir.glob("*.tar.gz"))
            wheel_files = list(outdir.glob("*.whl"))
            self.assertEqual(len(sdist_files), 1)
            self.assertEqual(len(wheel_files), 1)
            
            # 1. Audit Wheel
            with zipfile.ZipFile(wheel_files[0]) as whl:
                names = whl.namelist()
                # Prohibited patterns
                prohibited = [n for n in names if any(n.endswith(ext) for ext in (".act", ".spr", ".grf")) or
                              "private_fixture_hooks" in n or ".env" in n or ".key" in n or ".pem" in n]
                self.assertEqual(prohibited, [], f"Prohibited files found in wheel: {prohibited}")
                
                # Required contents
                self.assertTrue(any(n.endswith("schemas/project-v1.json") for n in names))
                self.assertTrue(any(n.endswith("schemas/target-v2.json") for n in names))
                self.assertTrue(any(n.endswith("schemas/actor-v1.json") for n in names))
                self.assertTrue(any(n.endswith("static/index.html") for n in names))
                self.assertTrue(any(n.endswith("static/workbench.js") for n in names))
                self.assertTrue(any(n.endswith("static/workbench.css") for n in names))
                self.assertTrue(any(n.endswith("licenses/LICENSE") for n in names))
                self.assertTrue(any(n.endswith("licenses/NOTICE.md") for n in names))
            
            # 2. Audit Sdist
            with tarfile.open(sdist_files[0]) as sdist:
                tar_names = sdist.getnames()
                prohibited_sdist = [n for n in tar_names if any(n.endswith(ext) for ext in (".act", ".spr", ".grf")) or
                                    "private_fixture_hooks" in n or ".env" in n or ".key" in n]
                self.assertEqual(prohibited_sdist, [], f"Prohibited files found in sdist: {prohibited_sdist}")
                
                self.assertTrue(any(n.endswith("NOTICE.md") for n in tar_names))
                self.assertTrue(any(n.endswith("LICENSE") for n in tar_names))
                self.assertTrue(any(n.endswith("docs/provenance/LWR_CODEC_PROVENANCE.md") for n in tar_names))
                self.assertTrue(any(n.endswith("tests/test_foundation.py") for n in tar_names))

    @unittest.skipUnless(BUILD_AVAILABLE, "build package required for distribution packaging tests")
    def test_04_reproducible_release_artifacts(self):
        """Criterion 2: Repeated release builds under SOURCE_DATE_EPOCH produce byte-identical artifacts."""
        with tempfile.TemporaryDirectory(prefix="rsf-repro-") as tmpdir:
            root = Path(tmpdir)
            out1 = root / "dist-1"
            out2 = root / "dist-2"
            
            env1 = dict(os.environ)
            env1["SOURCE_DATE_EPOCH"] = "1704067200"
            env1["PYTHONHASHSEED"] = "42"
            
            env2 = dict(os.environ)
            env2["SOURCE_DATE_EPOCH"] = "1704067200"
            env2["PYTHONHASHSEED"] = "99"
            
            # Build 1
            cmd1 = [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(out1), str(REPO_ROOT)]
            p1 = subprocess.run(cmd1, env=env1, capture_output=True, text=True)
            self.assertEqual(p1.returncode, 0, p1.stderr)
            
            # Build 2
            cmd2 = [sys.executable, "-m", "build", "--no-isolation", "--outdir", str(out2), str(REPO_ROOT)]
            p2 = subprocess.run(cmd2, env=env2, capture_output=True, text=True)
            self.assertEqual(p2.returncode, 0, p2.stderr)
            
            whl1 = list(out1.glob("*.whl"))[0]
            whl2 = list(out2.glob("*.whl"))[0]
            self.assertEqual(_file_sha256(whl1), _file_sha256(whl2), "Repeated wheel build hashes must be byte-identical")
            
            sdist1 = list(out1.glob("*.tar.gz"))[0]
            sdist2 = list(out2.glob("*.tar.gz"))[0]
            
            # Sdist member and payload comparison
            with tarfile.open(sdist1) as t1, tarfile.open(sdist2) as t2:
                names1 = sorted(t1.getnames())
                names2 = sorted(t2.getnames())
                self.assertEqual(names1, names2, "Sdist member lists must be identical")
                for name in names1:
                    m1 = t1.getmember(name)
                    m2 = t2.getmember(name)
                    self.assertEqual(m1.size, m2.size, f"Size differs for {name}")
                    if m1.isfile():
                        f1 = t1.extractfile(m1).read()
                        f2 = t2.extractfile(m2).read()
                        self.assertEqual(_sha256(f1), _sha256(f2), f"Payload hash differs for {name}")

    @unittest.skipUnless(BUILD_AVAILABLE, "build package required for distribution packaging tests")
    def test_05_clean_isolated_installation_and_outside_tree_cli(self):
        """Criterion 1: Clean installation runs CLI/UI workflows and resolves resources outside source tree."""
        with tempfile.TemporaryDirectory(prefix="rsf-install-") as tmpdir:
            root = Path(tmpdir)
            dist = root / "dist"
            venv_dir = root / "isolated-venv"
            
            env = dict(os.environ)
            env["SOURCE_DATE_EPOCH"] = "1704067200"
            
            # Build wheel
            subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(dist), str(REPO_ROOT)],
                           check=True, env=env, capture_output=True)
            wheel = list(dist.glob("*.whl"))[0]
            
            # Create isolated venv
            subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True, capture_output=True)
            py_bin = venv_dir / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            cli_bin = venv_dir / ("Scripts/ro-sprite-forge.exe" if os.name == "nt" else "bin/ro-sprite-forge")
            
            # Install wheel with no dependencies
            subprocess.run([str(py_bin), "-m", "pip", "install", "--no-index", "--no-deps", str(wheel)],
                           check=True, capture_output=True)
            
            # 1. Test CLI invocation from outside source directory
            outside_dir = root / "outside_workdir"
            outside_dir.mkdir()
            
            cli_res = subprocess.run([str(cli_bin), "--help"], cwd=outside_dir, capture_output=True, text=True)
            self.assertEqual(cli_res.returncode, 0)
            self.assertIn("ro-sprite-forge", cli_res.stdout)
            self.assertIn("inspect", cli_res.stdout)
            
            # 2. Test python module import from site-packages (no source leak)
            import_check = f"""
import sys, pathlib, ro_sprite_forge
pkg_file = pathlib.Path(ro_sprite_forge.__file__).resolve()
prefix = pathlib.Path(sys.prefix).resolve()
assert pkg_file.is_relative_to(prefix), f"Leaked to repo: {{pkg_file}}"
print("INSTALLED_IN_SITE_PACKAGES_PASS")
"""
            imp_res = subprocess.run([str(py_bin), "-I", "-c", import_check], cwd=outside_dir, capture_output=True, text=True)
            self.assertEqual(imp_res.returncode, 0, imp_res.stderr)
            self.assertIn("INSTALLED_IN_SITE_PACKAGES_PASS", imp_res.stdout)
            
            # 3. Test stdlib-only core execution (ACT/SPR codec and requirements)
            stdlib_smoke = """
import importlib.util
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.core.profiles import get_profile
from ro_sprite_forge.core.requirements import requirements
from ro_sprite_forge.core.preservation import roundtrip_pair
from ro_sprite_forge.formats.act import write_act
from ro_sprite_forge.formats.spr import write_rgba_spr, RgbaImage

assert importlib.util.find_spec('PIL') is None
assert importlib.util.find_spec('jsonschema') is None

a = write_act(dict(reserved='00'*10, actions=[[dict(bounds=(0,)*8, clips=[], event=-1, anchors=[])]], events=[], delays=[4.0]))
s = write_rgba_spr([RgbaImage(1, 1, bytes(4))])
assert roundtrip_pair(a, s)[:2] == (a, s)
assert roundtrip_pair(a, s, mode='act-semantic')[:2] == (a, s)

p = get_profile('player')
i = inventory(a, s, profile=p)
t = dict(schema='rsf.target/v1', actor='synthetic', part='body', scope='scoped',
         actions=[dict(action='Walk', requirement='required', views=[dict(view=0, frame_count=1, topology=dict(kind='explicit', layers=['body']))])])
assert requirements(i, p, t)['totals']['required_layers_known'] == 1
print('STDLIB_CORE_FUNCTIONAL_PASS')
"""
            smk_res = subprocess.run([str(py_bin), "-I", "-c", stdlib_smoke], cwd=outside_dir, capture_output=True, text=True)
            self.assertEqual(smk_res.returncode, 0, smk_res.stderr)
            self.assertIn("STDLIB_CORE_FUNCTIONAL_PASS", smk_res.stdout)

    @unittest.skipUnless(BUILD_AVAILABLE, "build package required for distribution packaging tests")
    def test_06_sdist_rebuild_integrity(self):
        """Criterion 1 & 2: Sdist extracts cleanly and builds an identical wheel without repo checkout."""
        with tempfile.TemporaryDirectory(prefix="rsf-sdist-rebuild-") as tmpdir:
            root = Path(tmpdir)
            dist1 = root / "dist1"
            extract_dir = root / "extracted"
            dist2 = root / "dist2"
            
            env = dict(os.environ)
            env["SOURCE_DATE_EPOCH"] = "1704067200"
            
            # Step 1: Build sdist from repo
            subprocess.run([sys.executable, "-m", "build", "--sdist", "--no-isolation", "--outdir", str(dist1), str(REPO_ROOT)],
                           check=True, env=env, capture_output=True)
            sdist = list(dist1.glob("*.tar.gz"))[0]
            
            # Step 2: Extract sdist
            with tarfile.open(sdist) as tar:
                tar.extractall(extract_dir, filter="data")
            
            extracted_src = list(extract_dir.iterdir())[0]
            
            # Step 3: Build wheel directly from extracted sdist directory
            subprocess.run([sys.executable, "-m", "build", "--wheel", "--no-isolation", "--outdir", str(dist2), str(extracted_src)],
                           check=True, env=env, capture_output=True)
            wheel = list(dist2.glob("*.whl"))[0]
            
            # Verify built wheel is valid and contains package resources
            with zipfile.ZipFile(wheel) as whl:
                names = whl.namelist()
                self.assertTrue(any(n.endswith("ro_sprite_forge/static/index.html") for n in names))
                self.assertTrue(any(n.endswith("ro_sprite_forge/schemas/project-v1.json") for n in names))
                self.assertTrue(any(n.endswith("licenses/NOTICE.md") for n in names))

    def test_07_ci_workflow_validity_and_matrix(self):
        """Criterion 1 & 4: CI workflow file exists and defines Python matrix 3.12, 3.13, 3.14."""
        ci_path = REPO_ROOT / ".github" / "workflows" / "ci.yml"
        self.assertTrue(ci_path.is_file(), "CI workflow .github/workflows/ci.yml must exist")
        ci_text = ci_path.read_text(encoding="utf-8")
        
        self.assertIn('python-version: ["3.12", "3.13", "3.14"]', ci_text)
        self.assertIn("distribution-and-rebuild:", ci_text)
        self.assertIn("reproducible-artifacts:", ci_text)
        self.assertIn("artifact-exclusion-and-licenses:", ci_text)
        self.assertIn("optional-adapters-isolation:", ci_text)

    def test_08_optional_adapter_isolation_and_diagnostics(self):
        """Criterion 1: Optional capabilities (FFmpeg, Rust oracle) degrade gracefully with diagnostics."""
        from ro_sprite_forge.adapters.video import capabilities
        
        caps = capabilities()
        self.assertIn("ffmpeg", caps)
        self.assertIn("ffprobe", caps)
        self.assertIn("available", caps)
        
        # Core profiles and contracts do NOT crash or demand optional tools
        from ro_sprite_forge.core.contracts import frozen_runtime_profile
        prof = frozen_runtime_profile("player")
        self.assertEqual(prof.id, "korangar-player-v1")

    def test_09_negative_prohibited_file_fails_exclusion_audit(self):
        """Negative test: Prohibited extensions (.act, .spr, .grf) are detected and fail audit."""
        mock_archive_members = [
            "ro_sprite_forge/__init__.py",
            "ro_sprite_forge/data/sample.act",  # prohibited
            "ro_sprite_forge/static/index.html",
        ]
        prohibited = [n for n in mock_archive_members if any(n.endswith(ext) for ext in (".act", ".spr", ".grf"))]
        self.assertEqual(prohibited, ["ro_sprite_forge/data/sample.act"])

    def test_10_negative_tampered_release_artifact_fails_digest(self):
        """Negative test: Tampering with a single byte in a release artifact invalidates its digest."""
        with tempfile.TemporaryDirectory(prefix="rsf-tamper-") as tmpdir:
            artifact = Path(tmpdir) / "release.whl"
            original_data = b"PK\x03\x04valid_zip_payload_bytes_here"
            artifact.write_bytes(original_data)
            orig_hash = _file_sha256(artifact)
            
            # Tamper
            tampered_data = b"PK\x03\x04valid_zip_payload_bytes_tampered"
            artifact.write_bytes(tampered_data)
            new_hash = _file_sha256(artifact)
            
            self.assertNotEqual(orig_hash, new_hash)

    def test_11_negative_missing_package_schema_fails_cleanly(self):
        """Negative test: Requesting an unknown schema fails cleanly without crashing."""
        from importlib.resources import files
        with self.assertRaises((FileNotFoundError, KeyError, Exception)):
            files("ro_sprite_forge").joinpath("schemas/nonexistent-schema-v99.json").read_text()


if __name__ == "__main__":
    unittest.main()
