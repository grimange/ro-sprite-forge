"""Canonical compiler inputs and complete, immutable Linux bundle publication.

This module does not encode images or resources. Verification reports and invocation
metadata belong to the outer compilation manifest, never the build identity/cache.
"""

from __future__ import annotations

import ctypes
import errno
from importlib.resources import files
import os
from pathlib import Path
import platform
import shutil
import tempfile
import zlib

from ro_sprite_forge.core.canonical import canonical_bytes, check, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError

PINNED_PILLOW = "12.1.1"
BUILD_SCHEMA = "rsf.canonical-build/v1"
TOOL_FILES = (
    "core/build.py", "core/compiler.py", "core/canonical.py", "core/coverage.py",
    "core/ledger.py", "core/review.py", "core/inventory.py", "core/topology.py",
    "core/contracts.py", "formats/act.py", "formats/spr.py",
    "formats/reader.py", "schemas/compilation-manifest-v1.json",
)


def toolchain(modified: bool) -> dict:
    pillow = None
    if modified:
        try:
            import PIL
        except ImportError as exc:
            raise ForgeError(ErrorCode.INVALID_INPUT, f"UNSUPPORTED_TOOLCHAIN: Pillow {PINNED_PILLOW} required for replacement compilation.") from exc
        pillow = PIL.__version__
        check(pillow == PINNED_PILLOW,
              f"UNSUPPORTED_TOOLCHAIN: PNG decoding requires Pillow {PINNED_PILLOW}, got {pillow}.")
    package = files("ro_sprite_forge")
    return {
        "python": {"implementation": platform.python_implementation(), "version": platform.python_version()},
        "pillow": pillow,
        "zlib": {"build": zlib.ZLIB_VERSION, "runtime": zlib.ZLIB_RUNTIME_VERSION} if modified else None,
        "png_decode": "pillow-8bit-to-top-down-RGBA/v1" if modified else "NOT_USED",
        "resampler": "NOT_USED-staged-recipes-never-reapplied",
        "color_space": "encoded-channel-values-no-ICC-or-gamma-conversion/v1",
        "palette": "original-1024-bytes-index0-transparent-exact-first-match/v1",
        "encoders": "ACT-2.4-little-endian-float32-SPR-2.1-zero-run-or-bottom-up-ABGR/v1",
        "ordering": "original-slot-frame-layer-pool-order-canonical-occurrence-appends/v1",
        "numeric": "finite-IEEE754-binary32-round-nearest-ties-even-no-decimal-rounding/v1",
        "canonical_json": "sorted-keys-ASCII-compact-finite-Python-floats-LF/v1",
        "source_sha256": {name: digest(package.joinpath(name).read_bytes()) for name in TOOL_FILES},
    }


def canonical_build(manifest: dict, requirements=None, resolved=None, selected=()) -> dict:
    """Bind pre-build composition before adding output hashes or verification evidence."""
    from ro_sprite_forge.core.review import bases

    selected = set(selected)
    review_bases = bases(requirements, resolved) if requirements is not None else {}
    rows = {r["requirement_id"]: r for r in (resolved or {}).get("assignments", [])}
    members = [{"requirement_id": rid, "operator_composition_sha256": review_bases[rid],
                "assignment_composition_sha256": rows[rid]["composition_sha256"],
                "source_sha256": rows[rid]["effective_source"]["sha256"],
                "review_state": rows[rid]["visual_review"]} for rid in sorted(selected)]
    composition = {"schema": "rsf.build-composition/v1", "target": manifest["target"],
                   "runtime_profile": manifest["runtime_profile"], "members": members}
    inputs = {
        "source_sha256": {k: v["sha256"] if v else None for k, v in manifest["input_resources"].items()},
        "target": manifest["target"], "runtime_profile": manifest["runtime_profile"],
        "requirements_sha256": manifest["requirements_sha256"],
        "ledger_revision": manifest["ledger"]["revision"] if manifest["ledger"] else None,
        "approved_composition": composition,
        "approved_composition_sha256": digest(canonical_bytes(composition)),
        "output_policy": {k: manifest[k] for k in ("compilation_mode", "part", "replacement_policy", "isolation_strategy")},
        "writer_version": manifest["writer_version"],
        "toolchain": toolchain(manifest["compilation_mode"] != "preserve"),
    }
    return sealed({"schema": BUILD_SCHEMA, "inputs": inputs, "input_sha256": digest(canonical_bytes(inputs)),
                   "remapping_sha256": digest(canonical_bytes(manifest["remapping"])),
                   "output_sha256": {k: v["sha256"] if v else None for k, v in manifest["output_resources"].items()}})


def _fsync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _rename_noreplace(source: Path, destination: Path) -> None:
    """Linux renameat2: atomic visibility AND no overwrite, including concurrent writers."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise ForgeError(ErrorCode.NOT_IMPLEMENTED, "ATOMIC_PUBLICATION_UNAVAILABLE: Linux renameat2 required.")
    rename.argtypes = (ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint)
    rename.restype = ctypes.c_int
    if rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1):
        code = ctypes.get_errno()
        raise OSError(code, os.strerror(code), str(destination))


def publish_bundle(destination: Path, contents: dict[str, bytes]) -> None:
    """Commit an entire fsynced bundle in one rename; an empty existing directory is allowed.

    A killed process can leave a hidden staging directory, never a partial final bundle.
    No overwrites, symlink destinations, or adding files to an existing resource directory.
    """
    check(all(Path(name).name == name and name not in ("", ".", "..") for name in contents),
          "INVALID_BUNDLE_FILENAME")
    if destination.is_symlink() or (destination.exists() and
            (not destination.is_dir() or any(destination.iterdir()))):
        raise ForgeError(ErrorCode.INVALID_OUTPUT, "OUTPUT_EXISTS: bundle destination must be absent or empty.", path=str(destination))
    stage = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        stage = Path(tempfile.mkdtemp(prefix=".rsf-staging-", dir=destination.parent))
        for name, raw in sorted(contents.items()):
            with (stage / name).open("xb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        _fsync_dir(stage)
        # rmdir never removes files and cannot replace a concurrent nonempty bundle.
        if destination.exists() and not destination.is_symlink():
            destination.rmdir()
        _rename_noreplace(stage, destination)
        stage = None
        _fsync_dir(destination.parent)
    except OSError as exc:
        code = ErrorCode.INVALID_OUTPUT if exc.errno in (errno.EEXIST, errno.ENOTEMPTY) else ErrorCode.IO_ERROR
        raise ForgeError(code, f"ATOMIC_PUBLICATION_FAILED: {exc}", path=str(destination)) from exc
    finally:
        if stage is not None:
            shutil.rmtree(stage)


def cache_bundle(cache_dir: str | Path, build: dict, resources: dict[str, bytes]) -> Path:
    """Verify or publish immutable cache content. Cached approval/status is never consumed."""
    destination = Path(cache_dir) / build["input_sha256"]
    contents = {**resources, "build-manifest.json": canonical_bytes(build)}
    if not destination.exists():
        try:
            publish_bundle(destination, contents)
        except ForgeError as exc:
            if exc.code != ErrorCode.INVALID_OUTPUT:
                raise
    check(destination.is_dir() and not destination.is_symlink(), "CORRUPT_BUILD_CACHE: invalid entry.")
    check({p.name for p in destination.iterdir()} == set(contents), "CORRUPT_BUILD_CACHE: file set differs.")
    for name, raw in contents.items():
        path = destination / name
        check(path.is_file() and not path.is_symlink() and path.stat().st_size == len(raw),
              f"CORRUPT_BUILD_CACHE: {name} size/type differs.")
        check(path.read_bytes() == raw, f"CORRUPT_BUILD_CACHE: {name} content differs.")
    return destination
