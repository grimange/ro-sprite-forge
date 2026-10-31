"""Public, deterministic contract tests; run against an installed package."""

import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from ro_sprite_forge import __version__
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.operations import Operation, Request, execute


class PackageTests(unittest.TestCase):
    def test_version_and_dependency_metadata(self):
        self.assertEqual(importlib.metadata.version("ro-sprite-forge"), __version__)
        self.assertFalse(importlib.metadata.requires("ro-sprite-forge"))

    def test_core_import_is_transport_independent(self):
        code = """
import sys
from ro_sprite_forge.core import operations, errors
for name in ('argparse', 'ro_sprite_forge.cli', 'http', 'socket', 'subprocess', 'PIL'):
    assert name not in sys.modules, name
assert operations.Operation.INSPECT.value == 'inspect'
"""
        result = subprocess.run([sys.executable, "-I", "-c", code], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_typed_errors(self):
        error = ForgeError(ErrorCode.INVALID_INPUT, "bad input", path="example.act")
        self.assertIsInstance(error, Exception)
        self.assertEqual(str(error), "bad input")
        self.assertEqual(error.code, ErrorCode.INVALID_INPUT)
        self.assertEqual(error.path, "example.act")

    def test_every_core_operation_fails_closed(self):
        for operation in Operation:
            with self.subTest(operation=operation):
                with self.assertRaises(ForgeError) as caught:
                    execute(Request(operation, ()))
                self.assertEqual(caught.exception.code, ErrorCode.NOT_IMPLEMENTED)


class CLITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="rsf1-contract-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        # Deliberately not valid SPR/ACT/JSON: RSF-1 must not claim content validity.
        self.source = self.root / "synthetic input.bin"
        self.source.write_bytes(b"synthetic foundation input\n")
        self.original = self.source.read_bytes()
        self.output = self.root / "output.json"
        self.console = Path(sys.executable).parent / ("ro-sprite-forge.exe" if os.name == "nt" else "ro-sprite-forge")
        self.assertTrue(self.console.is_file(), "Install the package before running the full test suite.")

    def run_cli(self, *args, module=False):
        command = [sys.executable, "-I", "-m", "ro_sprite_forge"] if module else [str(self.console)]
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        return subprocess.run(command + list(args), cwd=self.root, env=env, capture_output=True, text=True, timeout=10)

    def assert_error(self, args, status, code):
        result = self.run_cli(*args)
        self.assertEqual(result.returncode, status, result.stderr)
        self.assertEqual(result.stdout, "")
        diagnostic = json.loads(result.stderr)
        self.assertEqual(diagnostic["error"]["code"], code)
        self.assertTrue(diagnostic["error"]["message"])
        self.assertEqual(self.source.read_bytes(), self.original)
        return diagnostic

    def valid_commands(self):
        source, output = str(self.source), str(self.output)
        return [
            ["inspect", "--act", source, "--spr", source, "--json", output],
            ["plan", "--inventory", source, "--profile", source, "--target", source, "--output", output],
            ["verify", "--project", str(self.root), "--scope", "full"],
            ["roundtrip", "--act", source, "--spr", source, "--output-act", str(self.root / "new.act"), "--output-spr", str(self.root / "new.spr")],
        ]

    def test_help_and_required_commands(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stderr, "")
        top_help = result.stdout
        for name in Operation:
            self.assertIn(name.value, top_help)
            result = self.run_cli(name.value, "--help")
            self.assertEqual(result.returncode, 0, result.stderr)
            if name == Operation.VERIFY:
                self.assertIn("not yet implemented", result.stdout)
            else:
                self.assertIn("--output" if name in (Operation.PLAN, Operation.ROUNDTRIP) else "--json", result.stdout)
        self.assertEqual(list(self.root.iterdir()), [self.source])

    def test_installed_version_and_module_entry_point(self):
        for module in (False, True):
            result = self.run_cli("--version", module=module)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, f"ro-sprite-forge {__version__}\n")
            self.assertEqual(result.stderr, "")

    def test_argument_errors(self):
        for args in ([], ["unknown"], ["--unknown"], ["inspect"], ["plan"], ["verify"], ["roundtrip"],
                     ["verify", "--project", str(self.root), "--scope", "typo"],
                     ["verify", "--proj", str(self.root), "--scope", "full"]):
            with self.subTest(args=args):
                self.assert_error(args, 2, "INVALID_ARGUMENT")

    def test_invalid_or_unimplemented_commands_create_nothing(self):
        for args in self.valid_commands():
            with self.subTest(command=args[0]):
                if args[0] in ("inspect", "plan", "roundtrip"):
                    self.assert_error(args, 3, "INVALID_INPUT")
                else:
                    self.assert_error(args, 4, "NOT_IMPLEMENTED")
                self.assertEqual(list(self.root.iterdir()), [self.source])
        declared = ["verify", "--project", str(self.root), "--scope", "declared"]
        self.assert_error(declared, 4, "NOT_IMPLEMENTED")

    def test_missing_inputs_for_every_command(self):
        for args in self.valid_commands():
            # Replace the first input (all contracts begin with an input option).
            args[2] = str(self.root / "absent")
            with self.subTest(command=args[0]):
                self.assert_error(args, 3, "INPUT_NOT_FOUND")
                self.assertFalse(self.output.exists())

    def test_wrong_input_kinds(self):
        for path in (self.root,):
            self.assert_error(["inspect", "--act", str(path), "--spr", str(self.source), "--json", str(self.output)], 3, "INVALID_INPUT")
        self.assert_error(["verify", "--project", str(self.source), "--scope", "full"], 3, "INVALID_INPUT")

    def test_existing_output_is_preserved(self):
        self.output.write_bytes(b"do not replace")
        self.assert_error(self.valid_commands()[0], 3, "INVALID_OUTPUT")
        self.assertEqual(self.output.read_bytes(), b"do not replace")

    def test_missing_output_parent(self):
        args = self.valid_commands()[0]
        args[-1] = str(self.root / "absent" / "output.json")
        self.assert_error(args, 3, "INVALID_OUTPUT")
        self.assertFalse((self.root / "absent").exists())

    def test_output_cannot_alias_input_or_other_output(self):
        args = self.valid_commands()[0]
        args[-1] = str(self.source)
        self.assert_error(args, 3, "INVALID_OUTPUT")
        args = self.valid_commands()[3]
        args[-1] = args[-3]
        self.assert_error(args, 3, "INVALID_OUTPUT")

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks not supported")
    def test_dangling_output_symlink_is_preserved(self):
        self.output.symlink_to(self.root / "absent")
        self.assert_error(self.valid_commands()[0], 3, "INVALID_OUTPUT")
        self.assertTrue(self.output.is_symlink())
        self.assertFalse((self.root / "absent").exists())

    @unittest.skipUnless(hasattr(os, "mkfifo"), "FIFO not supported")
    def test_special_input_is_rejected_without_opening(self):
        fifo = self.root / "pipe.act"
        os.mkfifo(fifo)
        args = self.valid_commands()[0]
        args[2] = str(fifo)
        self.assert_error(args, 3, "INVALID_INPUT")

    def test_empty_path(self):
        args = self.valid_commands()[0]
        args[2] = ""
        self.assert_error(args, 2, "INVALID_ARGUMENT")


if __name__ == "__main__":
    unittest.main()
