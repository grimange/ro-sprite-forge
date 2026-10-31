"""Versioned filesystem-backed project persistence and atomic publication (RSF-15, RSF-37).

Provides local project management:
- Project creation, loading, saving, reopening and migration.
- Explicit version classification and deterministic schema migrations.
- Optimistic concurrency control via explicit revision numbers.
- Atomic JSON manifest publication with crash-safe recovery from previous backups.
- Hostile-input and resource-bound hardening (bounded manifest size, JSON depth, duplicate keys, path traversal).
- Content-addressed source/artifact blob storage (SHA-256) with integrity auditing.
- Strict path containment, symlink escape rejection, and size boundaries.
- Pure Python standard library with no external database or network dependency.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import threading
from typing import Any
from uuid import uuid4

try:
    from jsonschema import Draft202012Validator
except ImportError:
    Draft202012Validator = None

from ro_sprite_forge.core.canonical import canonical_bytes, check_seal, digest, sealed
from ro_sprite_forge.core.errors import ErrorCode, ForgeError

SCHEMA_NAME = "rsf.project/v1"
SUPPORTED_CURRENT_SCHEMA = "rsf.project/v1"
SUPPORTED_LEGACY_SCHEMAS = frozenset({
    "rsf.project/v0",
    "rsf.project/v0.1",
    "rsf.project/v1.0",
    "rsf.project",
})

SCHEMA_PATH = Path(__file__).resolve().parents[1] / "schemas" / "project-v1.json"

MAX_PROJECT_ID_LEN = 64
PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")
MAX_BLOB_SIZE = 32 * 1024 * 1024  # 32 MiB
MAX_MANIFEST_SIZE = 16 * 1024 * 1024  # 16 MiB
MAX_JSON_DEPTH = 64

_PROJECT_LOCKS: dict[str, threading.Lock] = {}
_PROJECT_LOCKS_LOCK = threading.Lock()


def _get_project_lock(project_path_str: str) -> threading.Lock:
    with _PROJECT_LOCKS_LOCK:
        lock = _PROJECT_LOCKS.get(project_path_str)
        if lock is None:
            lock = threading.Lock()
            _PROJECT_LOCKS[project_path_str] = lock
        return lock


def project_schema() -> dict:
    if not SCHEMA_PATH.exists():
        raise ForgeError(ErrorCode.IO_ERROR, f"Schema file missing: {SCHEMA_PATH}")
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _fsync_dir(path: Path) -> None:
    """Flush directory changes to disk where supported."""
    try:
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    except (OSError, AttributeError):
        pass


def validate_path_containment(base_dir: Path, target: Path) -> Path:
    """Ensure target path is strictly contained within base_dir and has no symlink escapes."""
    resolved_base = base_dir.resolve()
    resolved_target = target.resolve()
    try:
        resolved_target.relative_to(resolved_base)
    except ValueError as exc:
        raise ForgeError(ErrorCode.PERMISSION_DENIED, f"Path traversal rejected: '{target}' escapes '{base_dir}'.") from exc

    # Check each ancestor component for symlink escapes
    curr = target
    while curr != base_dir and curr != curr.parent:
        if curr.is_symlink():
            sym_target = curr.resolve()
            try:
                sym_target.relative_to(resolved_base)
            except ValueError as exc:
                raise ForgeError(ErrorCode.PERMISSION_DENIED, f"Symlink escape rejected: '{curr}' points outside '{base_dir}'.") from exc
        curr = curr.parent

    return resolved_target


def validate_project_id(project_id: str) -> None:
    if not isinstance(project_id, str) or not PROJECT_ID_PATTERN.match(project_id):
        raise ForgeError(
            ErrorCode.INVALID_ARGUMENT,
            f"Invalid project_id '{project_id}'. Must be 1-64 alphanumeric characters, underscores or hyphens.",
        )


def validate_safe_filename(filename: str) -> None:
    if not isinstance(filename, str) or not filename or len(filename) > 256:
        raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Filename must be 1-256 characters.")
    if "/" in filename or "\\" in filename or "\x00" in filename:
        raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Filename must not contain path separators or NUL bytes.")
    if filename in (".", ".."):
        raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Invalid filename '.' or '..'.")


def _strict_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    d: dict[str, Any] = {}
    for k, v in pairs:
        if k in d:
            raise ForgeError(ErrorCode.INVALID_INPUT, f"Duplicate JSON key detected: '{k}'.")
        d[k] = v
    return d


def _reject_constant(c: str) -> Any:
    raise ForgeError(ErrorCode.INVALID_INPUT, f"Nonfinite JSON constant forbidden: {c}.")


def _check_json_depth(obj: Any, depth: int = 1) -> None:
    if depth > MAX_JSON_DEPTH:
        raise ForgeError(ErrorCode.INVALID_INPUT, f"Excessive JSON nesting depth (exceeds {MAX_JSON_DEPTH}).")
    if isinstance(obj, dict):
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _check_json_depth(v, depth + 1)
    elif isinstance(obj, list):
        for item in obj:
            if isinstance(item, (dict, list)):
                _check_json_depth(item, depth + 1)


def parse_manifest_bytes(raw_bytes: bytes, source_label: str = "project manifest") -> dict[str, Any]:
    """Parse JSON manifest bytes with strict hostile-input bounds and validation."""
    if not raw_bytes:
        raise ForgeError(ErrorCode.INVALID_INPUT, f"{source_label.capitalize()} is empty.")
    if len(raw_bytes) > MAX_MANIFEST_SIZE:
        raise ForgeError(
            ErrorCode.PAYLOAD_TOO_LARGE,
            f"{source_label.capitalize()} exceeds {MAX_MANIFEST_SIZE} bytes limit (got {len(raw_bytes)} bytes).",
        )
    try:
        decoded_text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ForgeError(ErrorCode.INVALID_INPUT, f"Malformed UTF-8 encoding in {source_label}: {exc}") from exc

    try:
        data = json.loads(
            decoded_text,
            object_pairs_hook=_strict_pairs_hook,
            parse_constant=_reject_constant,
        )
    except ForgeError:
        raise
    except RecursionError as exc:
        raise ForgeError(ErrorCode.INVALID_INPUT, f"Excessive JSON nesting in {source_label}.") from exc
    except Exception as exc:
        raise ForgeError(ErrorCode.INVALID_INPUT, f"Malformed JSON in {source_label}: {exc}") from exc

    _check_json_depth(data)
    if not isinstance(data, dict):
        raise ForgeError(ErrorCode.INVALID_INPUT, f"{source_label.capitalize()} must be a JSON object.")
    return data


def classify_project_version(project_data: dict) -> tuple[str, str]:
    """Classify project version into CURRENT_SUPPORTED, MIGRATION_REQUIRED, or UNSUPPORTED_VERSION."""
    if not isinstance(project_data, dict):
        return ("UNSUPPORTED_VERSION", "Manifest payload must be a JSON object.")

    schema = project_data.get("schema")
    if not isinstance(schema, str):
        return ("UNSUPPORTED_VERSION", "Manifest missing required string 'schema' property.")

    if schema == SCHEMA_NAME:
        target = project_data.get("target")
        if isinstance(target, dict) and target.get("schema") in ("rsf.target/v1", "rsf.target/v0"):
            return ("MIGRATION_REQUIRED", f"Target uses legacy schema '{target.get('schema')}'.")

        profile = project_data.get("profile")
        if isinstance(profile, dict) and profile.get("schema") in ("rsf.runtime-profile/v1", "rsf.runtime-profile/v0"):
            return ("MIGRATION_REQUIRED", f"Profile uses legacy schema '{profile.get('schema')}'.")

        return ("CURRENT_SUPPORTED", f"Project matches canonical schema '{SCHEMA_NAME}'.")

    if schema in SUPPORTED_LEGACY_SCHEMAS:
        return ("MIGRATION_REQUIRED", f"Project uses supported legacy schema '{schema}'.")

    return ("UNSUPPORTED_VERSION", f"Unsupported project schema version '{schema}'.")


def cleanup_staging(project_dir: Path) -> int:
    """Safely remove leftover uncommitted files from staging directory and orphaned manifest temp files."""
    cleaned_count = 0
    staging_dir = project_dir / "staging"
    if staging_dir.exists() and staging_dir.is_dir():
        for item in staging_dir.iterdir():
            try:
                if item.is_file() or item.is_symlink():
                    item.unlink(missing_ok=True)
                    cleaned_count += 1
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)
                    cleaned_count += 1
            except OSError:
                pass

    # Also clean orphaned manifest temp files in project_dir
    try:
        for item in project_dir.iterdir():
            if item.is_file() and (item.name.startswith(".manifest-") or item.name.startswith("manifest-tmp-")) and item.name.endswith(".tmp"):
                try:
                    item.unlink(missing_ok=True)
                    cleaned_count += 1
                except OSError:
                    pass
    except OSError:
        pass

    return cleaned_count


def create_project(
    projects_dir: Path | str,
    project_id: str,
    name: str,
    actor: str,
    profile: str,
    *,
    target: dict | None = None,
    ledger: dict | None = None,
    inventory: dict | None = None,
) -> dict:
    """Create a new versioned project with atomic manifest initialization."""
    validate_project_id(project_id)
    if not isinstance(name, str) or not name.strip() or len(name) > 128:
        raise ForgeError(ErrorCode.INVALID_ARGUMENT, "Project name must be 1-128 characters.")

    base_dir = Path(projects_dir).resolve()
    base_dir.mkdir(parents=True, exist_ok=True)

    project_dir = base_dir / project_id
    validate_path_containment(base_dir, project_dir)

    if project_dir.exists():
        raise ForgeError(ErrorCode.CONFLICT, f"Project '{project_id}' already exists at {project_dir}.")

    staging_dir = project_dir / "staging"
    blobs_dir = project_dir / "blobs"

    staging_dir.mkdir(parents=True)
    blobs_dir.mkdir(parents=True)

    now = datetime.now(timezone.utc).isoformat()
    manifest_data: dict[str, Any] = {
        "schema": SCHEMA_NAME,
        "project_id": project_id,
        "name": name.strip(),
        "revision": 1,
        "created_at": now,
        "updated_at": now,
        "actor": actor,
        "profile": profile,
        "sources": {},
        "reviews": {},
    }
    if target is not None:
        manifest_data["target"] = target
    if ledger is not None:
        manifest_data["ledger"] = ledger
    if inventory is not None:
        manifest_data["inventory"] = inventory

    sealed_manifest = sealed(manifest_data)

    # Validate against JSON schema if validator available
    if Draft202012Validator is not None:
        validator = Draft202012Validator(project_schema())
        validator.validate(sealed_manifest)

    # Stage temporary manifest write
    temp_file = staging_dir / f".manifest-{uuid4().hex}.tmp"
    try:
        with open(temp_file, "wb") as f:
            f.write(canonical_bytes(sealed_manifest))
            f.flush()
            os.fsync(f.fileno())

        manifest_final = project_dir / "manifest.json"
        os.replace(temp_file, manifest_final)
        _fsync_dir(project_dir)
    except Exception as exc:
        if temp_file.exists():
            temp_file.unlink(missing_ok=True)
        shutil.rmtree(project_dir, ignore_errors=True)
        raise ForgeError(ErrorCode.IO_ERROR, f"Failed to initialize project manifest: {exc}") from exc

    return sealed_manifest


def load_project(projects_dir: Path | str, project_id: str, *, verify_blobs: bool = True) -> dict:
    """Load and validate an existing project manifest and verify referenced blobs."""
    validate_project_id(project_id)
    base_dir = Path(projects_dir).resolve()
    project_dir = base_dir / project_id
    validate_path_containment(base_dir, project_dir)

    manifest_path = project_dir / "manifest.json"
    if not manifest_path.exists() or not manifest_path.is_file():
        raise ForgeError(ErrorCode.INPUT_NOT_FOUND, f"Project '{project_id}' not found.", path=str(manifest_path))

    try:
        raw_bytes = manifest_path.read_bytes()
    except OSError as exc:
        raise ForgeError(ErrorCode.IO_ERROR, f"Cannot read project manifest: {exc}", path=str(manifest_path)) from exc

    manifest = parse_manifest_bytes(raw_bytes, "project manifest")

    status, reason = classify_project_version(manifest)
    if status == "MIGRATION_REQUIRED":
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"Project '{project_id}' requires migration: {reason}. Run migrate_project() first.",
            path=str(manifest_path),
        )
    if status == "UNSUPPORTED_VERSION":
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"Project '{project_id}' uses unsupported version: {reason}.",
            path=str(manifest_path),
        )

    check_seal(manifest, SCHEMA_NAME)

    if Draft202012Validator is not None:
        validator = Draft202012Validator(project_schema())
        validator.validate(manifest)

    if manifest.get("project_id") != project_id:
        raise ForgeError(
            ErrorCode.INVALID_INPUT,
            f"Project identity mismatch: requested '{project_id}', manifest defines '{manifest.get('project_id')}'.",
        )

    if verify_blobs:
        blobs_dir = project_dir / "blobs"
        for source_id, source_info in manifest.get("sources", {}).items():
            expected_hash = source_info.get("sha256", "").lower().strip()
            raw_blob_path = source_info.get("blob_path", "")

            # Guard against path traversal in blob_path
            if (
                not raw_blob_path.startswith("blobs/")
                or ".." in raw_blob_path
                or "\\" in raw_blob_path
                or raw_blob_path.startswith("/")
            ):
                raise ForgeError(
                    ErrorCode.PERMISSION_DENIED,
                    f"Path traversal rejected in blob path '{raw_blob_path}' for source '{source_id}'.",
                )

            blob_path = project_dir / raw_blob_path
            validate_path_containment(project_dir, blob_path)

            if not blob_path.exists() or not blob_path.is_file():
                raise ForgeError(
                    ErrorCode.INPUT_NOT_FOUND,
                    f"Referenced blob for source '{source_id}' is missing: {blob_path}",
                    path=str(blob_path),
                )
            blob_bytes = blob_path.read_bytes()
            if digest(blob_bytes) != expected_hash:
                raise ForgeError(
                    ErrorCode.INVALID_INPUT,
                    f"Integrity check failed for source '{source_id}': expected SHA-256 {expected_hash}, got {digest(blob_bytes)}.",
                    path=str(blob_path),
                )

    return manifest


def save_project(projects_dir: Path | str, project_data: dict, expected_revision: int) -> dict:
    """Atomically save an updated project revision with optimistic concurrency control."""
    project_id = project_data.get("project_id")
    validate_project_id(project_id)

    base_dir = Path(projects_dir).resolve()
    project_dir = base_dir / project_id
    validate_path_containment(base_dir, project_dir)

    with _get_project_lock(str(project_dir)):
        manifest_path = project_dir / "manifest.json"
        if not manifest_path.exists():
            raise ForgeError(ErrorCode.INPUT_NOT_FOUND, f"Cannot save nonexistent project '{project_id}'.")

        # Optimistic concurrency check against current on-disk revision
        current_manifest = load_project(projects_dir, project_id, verify_blobs=False)
        current_revision = current_manifest["revision"]

        if current_revision != expected_revision:
            raise ForgeError(
                ErrorCode.CONFLICT,
                f"Revision conflict for project '{project_id}': current on-disk revision is {current_revision}, "
                f"but save requested revision {expected_revision}.",
            )

        new_revision = expected_revision + 1
        updated_data = {
            **project_data,
            "revision": new_revision,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        # Remove old canonical_sha256 before resealing
        updated_data.pop("canonical_sha256", None)
        sealed_manifest = sealed(updated_data)

        if Draft202012Validator is not None:
            validator = Draft202012Validator(project_schema())
            validator.validate(sealed_manifest)

        manifest_bytes = canonical_bytes(sealed_manifest)
        if len(manifest_bytes) > MAX_MANIFEST_SIZE:
            raise ForgeError(
                ErrorCode.PAYLOAD_TOO_LARGE,
                f"Updated manifest size ({len(manifest_bytes)} bytes) exceeds limit ({MAX_MANIFEST_SIZE} bytes).",
            )

        staging_dir = project_dir / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)

        temp_file = staging_dir / f".manifest-{uuid4().hex}.tmp"
        backup_file = project_dir / "manifest.json.bak"

        try:
            with open(temp_file, "wb") as f:
                f.write(manifest_bytes)
                f.flush()
                os.fsync(f.fileno())

            # Backup current manifest before replacing
            shutil.copyfile(manifest_path, backup_file)
            # Atomic replacement
            os.replace(temp_file, manifest_path)
            _fsync_dir(project_dir)
        except Exception as exc:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            raise ForgeError(ErrorCode.IO_ERROR, f"Failed to publish updated manifest: {exc}") from exc

        return sealed_manifest


def migrate_project(
    projects_dir: Path | str,
    project_id: str,
    *,
    evaluate_review_invalidation: bool = True,
) -> dict:
    """Deterministically migrate a legacy project to current canonical schema.

    - Preserves source blobs and original SHA-256 hashes bit-exact.
    - Creates backups before migration (manifest.json.pre-migration.bak and manifest.json.bak).
    - Invalidates only affected reviews if target/composition basis changed.
    - Idempotent: safe no-op on already current projects.
    """
    validate_project_id(project_id)
    base_dir = Path(projects_dir).resolve()
    project_dir = base_dir / project_id
    validate_path_containment(base_dir, project_dir)

    manifest_path = project_dir / "manifest.json"
    if not manifest_path.exists() or not manifest_path.is_file():
        raise ForgeError(ErrorCode.INPUT_NOT_FOUND, f"Project '{project_id}' not found.", path=str(manifest_path))

    with _get_project_lock(str(project_dir)):
        raw_bytes = manifest_path.read_bytes()
        manifest_data = parse_manifest_bytes(raw_bytes, "project manifest")

        status, reason = classify_project_version(manifest_data)
        if status == "UNSUPPORTED_VERSION":
            raise ForgeError(ErrorCode.INVALID_INPUT, f"Cannot migrate project '{project_id}': {reason}")

        prev_schema = manifest_data.get("schema")
        prev_revision = manifest_data.get("revision", 1)

        if status == "CURRENT_SUPPORTED":
            return {
                "project_id": project_id,
                "status": "ALREADY_CURRENT",
                "previous_schema": prev_schema,
                "current_schema": SCHEMA_NAME,
                "previous_revision": prev_revision,
                "current_revision": prev_revision,
                "invalidated_reviews": [],
                "backup_path": None,
            }

        # Status is MIGRATION_REQUIRED
        backup_path = project_dir / "manifest.json.pre-migration.bak"
        std_backup = project_dir / "manifest.json.bak"
        shutil.copyfile(manifest_path, backup_path)
        shutil.copyfile(manifest_path, std_backup)

        migrated = json.loads(json.dumps(manifest_data))
        migrated["schema"] = SCHEMA_NAME

        target_changed = False
        target = migrated.get("target")
        if isinstance(target, dict):
            if target.get("schema") in ("rsf.target/v1", "rsf.target/v0", None):
                target["schema"] = "rsf.target/v2"
                if "compatibility" not in target:
                    target["compatibility"] = {
                        "engine": "korangar",
                        "pinned_client": "2020-04-01",
                        "body_profile": str(target.get("actor", migrated.get("actor", "novice-male"))),
                    }
                target_changed = True

        profile = migrated.get("profile")
        if isinstance(profile, dict) and profile.get("schema") in ("rsf.runtime-profile/v1", "rsf.runtime-profile/v0"):
            profile["schema"] = "rsf.runtime-profile/v2"

        # Invariant: preserve sources bit-exact
        if migrated.get("sources") != manifest_data.get("sources"):
            raise ForgeError(ErrorCode.INTERNAL_ERROR, "Migration invariant violation: sources altered.")

        invalidated_reviews: list[str] = []
        if target_changed and evaluate_review_invalidation:
            reviews = migrated.get("reviews")
            if isinstance(reviews, dict):
                for rid, rdata in list(reviews.items()):
                    if isinstance(rdata, dict) and rdata.get("approved") is True:
                        rdata["approved"] = False
                        invalidated_reviews.append(rid)

        # Advance revision
        new_revision = prev_revision + 1
        migrated["revision"] = new_revision
        migrated["updated_at"] = datetime.now(timezone.utc).isoformat()
        migrated.pop("canonical_sha256", None)

        sealed_manifest = sealed(migrated)

        if Draft202012Validator is not None:
            validator = Draft202012Validator(project_schema())
            validator.validate(sealed_manifest)

        staging_dir = project_dir / "staging"
        staging_dir.mkdir(parents=True, exist_ok=True)
        temp_file = staging_dir / f".manifest-migrate-{uuid4().hex}.tmp"
        try:
            with open(temp_file, "wb") as f:
                f.write(canonical_bytes(sealed_manifest))
                f.flush()
                os.fsync(f.fileno())
            os.replace(temp_file, manifest_path)
            _fsync_dir(project_dir)
        except Exception as exc:
            if temp_file.exists():
                temp_file.unlink(missing_ok=True)
            raise ForgeError(ErrorCode.IO_ERROR, f"Failed to publish migrated manifest: {exc}") from exc

        return {
            "project_id": project_id,
            "status": "MIGRATED",
            "previous_schema": prev_schema,
            "current_schema": SCHEMA_NAME,
            "previous_revision": prev_revision,
            "current_revision": new_revision,
            "invalidated_reviews": invalidated_reviews,
            "backup_path": str(backup_path),
        }


def recover_project(projects_dir: Path | str, project_id: str) -> dict:
    """Safely recover an interrupted or corrupted project using backups and cleaning staging.

    - Cleans up leftover uncommitted staging files.
    - If manifest.json is missing or corrupted, restores from valid backup.
    - Idempotent: repeated runs on recovered projects introduce no additional changes or revision drift.
    """
    validate_project_id(project_id)
    base_dir = Path(projects_dir).resolve()
    project_dir = base_dir / project_id
    validate_path_containment(base_dir, project_dir)

    if not project_dir.exists() or not project_dir.is_dir():
        raise ForgeError(ErrorCode.INPUT_NOT_FOUND, f"Project '{project_id}' does not exist.")

    with _get_project_lock(str(project_dir)):
        staging_cleaned = cleanup_staging(project_dir)

        manifest_path = project_dir / "manifest.json"
        manifest_healthy = False
        current_rev = None

        if manifest_path.exists() and manifest_path.is_file():
            try:
                raw_bytes = manifest_path.read_bytes()
                data = parse_manifest_bytes(raw_bytes, "project manifest")
                check_seal(data, SCHEMA_NAME)
                if Draft202012Validator is not None:
                    validator = Draft202012Validator(project_schema())
                    validator.validate(data)
                manifest_healthy = True
                current_rev = data.get("revision")
            except Exception:
                manifest_healthy = False

        if manifest_healthy:
            return {
                "project_id": project_id,
                "recovered": staging_cleaned > 0,
                "already_healthy": True,
                "action": "CLEANED_STAGING" if staging_cleaned > 0 else "NO_ACTION_NEEDED",
                "reason": "Project manifest is valid and healthy.",
                "restored_from": None,
                "revision": current_rev,
                "staging_cleaned_count": staging_cleaned,
                "backup_manifest_hash": None,
                "restored_manifest_hash": hashlib.sha256(raw_bytes).hexdigest(),
                "valid": True,
            }

        # Manifest is corrupt or missing. Inspect backup candidates.
        backup_candidates = [
            project_dir / "manifest.json.bak",
            project_dir / "manifest.json.pre-migration.bak",
        ]
        for candidate in backup_candidates:
            if candidate.exists() and candidate.is_file():
                try:
                    c_bytes = candidate.read_bytes()
                    c_data = parse_manifest_bytes(c_bytes, f"backup {candidate.name}")
                    c_schema = c_data.get("schema", SCHEMA_NAME)
                    check_seal(c_data, c_schema)
                    if c_schema == SCHEMA_NAME and Draft202012Validator is not None:
                        validator = Draft202012Validator(project_schema())
                        validator.validate(c_data)

                    # Restore from valid backup candidate
                    staging_dir = project_dir / "staging"
                    staging_dir.mkdir(parents=True, exist_ok=True)
                    temp_file = staging_dir / f".manifest-recover-{uuid4().hex}.tmp"
                    with open(temp_file, "wb") as f:
                        f.write(c_bytes)
                        f.flush()
                        os.fsync(f.fileno())
                    os.replace(temp_file, manifest_path)
                    _fsync_dir(project_dir)

                    b_hash = hashlib.sha256(c_bytes).hexdigest()
                    return {
                        "project_id": project_id,
                        "recovered": True,
                        "already_healthy": False,
                        "action": "RESTORED_FROM_BACKUP",
                        "reason": f"Corrupted or missing manifest restored from valid backup '{candidate.name}'.",
                        "restored_from": candidate.name,
                        "revision": c_data.get("revision"),
                        "staging_cleaned_count": staging_cleaned,
                        "backup_manifest_hash": b_hash,
                        "restored_manifest_hash": b_hash,
                        "valid": True,
                    }
                except Exception:
                    continue

        # No valid backup exists
        return {
            "project_id": project_id,
            "recovered": False,
            "already_healthy": False,
            "action": "UNRECOVERABLE",
            "reason": "Manifest is missing or corrupted and no valid backup was found.",
            "restored_from": None,
            "revision": None,
            "staging_cleaned_count": staging_cleaned,
            "backup_manifest_hash": None,
            "restored_manifest_hash": None,
            "valid": False,
        }


def audit_project_integrity(projects_dir: Path | str, project_id: str) -> dict:
    """Audit project integrity: verify manifest, source blob availability, hashes and detect orphans."""
    validate_project_id(project_id)
    base_dir = Path(projects_dir).resolve()
    project_dir = base_dir / project_id
    validate_path_containment(base_dir, project_dir)

    manifest = load_project(projects_dir, project_id, verify_blobs=False)
    blobs_dir = project_dir / "blobs"
    sources = manifest.get("sources", {})

    referenced_blobs: dict[str, str] = {}
    corrupted_blobs: list[dict] = []
    missing_blobs: list[dict] = []
    orphaned_blobs: list[str] = []
    valid_blobs: list[str] = []

    # 1. Audit all referenced sources in manifest
    for src_id, src_info in sources.items():
        exp_hash = src_info.get("sha256", "").lower().strip()
        raw_blob_path = src_info.get("blob_path", "")

        # Check path traversal
        if not raw_blob_path.startswith("blobs/") or ".." in raw_blob_path or "\\" in raw_blob_path:
            corrupted_blobs.append({
                "source_id": src_id,
                "reason": f"Path traversal in blob_path '{raw_blob_path}'",
            })
            continue

        blob_file = project_dir / raw_blob_path
        try:
            validate_path_containment(project_dir, blob_file)
        except ForgeError as err:
            corrupted_blobs.append({"source_id": src_id, "reason": str(err)})
            continue

        referenced_blobs[exp_hash] = src_id

        if not blob_file.exists() or not blob_file.is_file():
            missing_blobs.append({"source_id": src_id, "expected_sha256": exp_hash, "path": raw_blob_path})
            continue

        try:
            b_data = blob_file.read_bytes()
            act_hash = digest(b_data)
            if act_hash != exp_hash:
                corrupted_blobs.append({
                    "source_id": src_id,
                    "expected_sha256": exp_hash,
                    "actual_sha256": act_hash,
                    "reason": "Hash mismatch",
                })
            elif src_info.get("size") is not None and len(b_data) != src_info["size"]:
                corrupted_blobs.append({
                    "source_id": src_id,
                    "expected_size": src_info["size"],
                    "actual_size": len(b_data),
                    "reason": "Size mismatch",
                })
            else:
                valid_blobs.append(exp_hash)
        except OSError as exc:
            corrupted_blobs.append({"source_id": src_id, "reason": f"Read error: {exc}"})

    # 2. Audit disk files in blobs/
    if blobs_dir.exists() and blobs_dir.is_dir():
        for b_item in blobs_dir.iterdir():
            if b_item.is_file() and not b_item.name.startswith("."):
                disk_name = b_item.name.lower()
                if disk_name not in referenced_blobs:
                    orphaned_blobs.append(disk_name)

    if corrupted_blobs or missing_blobs:
        status = "CORRUPTED"
    elif orphaned_blobs:
        status = "INTACT_WITH_ORPHANS"
    else:
        status = "INTACT"

    return {
        "project_id": project_id,
        "revision": manifest["revision"],
        "manifest_valid": True,
        "manifest_sha256": manifest["canonical_sha256"],
        "blobs_total": len(sources),
        "blobs_valid_count": len(valid_blobs),
        "blobs_missing": missing_blobs,
        "blobs_corrupted": corrupted_blobs,
        "blobs_orphaned": sorted(orphaned_blobs),
        "integrity_status": status,
    }


def import_blob(
    projects_dir: Path | str,
    project_id: str,
    filename: str,
    data: bytes,
    *,
    expected_sha256: str | None = None,
) -> dict:
    """Store an immutable content-addressed source blob with bounded size and path checks."""
    validate_project_id(project_id)
    validate_safe_filename(filename)

    if len(data) > MAX_BLOB_SIZE:
        raise ForgeError(
            ErrorCode.PAYLOAD_TOO_LARGE,
            f"Blob size {len(data)} bytes exceeds maximum allowed limit of {MAX_BLOB_SIZE} bytes.",
        )

    actual_hash = digest(data)
    if expected_sha256 is not None:
        clean_expected = expected_sha256.lower().strip()
        if clean_expected != actual_hash:
            raise ForgeError(
                ErrorCode.INVALID_INPUT,
                f"Blob integrity check failed: expected {clean_expected}, computed {actual_hash}.",
            )

    base_dir = Path(projects_dir).resolve()
    project_dir = base_dir / project_id
    validate_path_containment(base_dir, project_dir)

    if not project_dir.exists():
        raise ForgeError(ErrorCode.INPUT_NOT_FOUND, f"Project '{project_id}' does not exist.")

    blobs_dir = project_dir / "blobs"
    blobs_dir.mkdir(parents=True, exist_ok=True)
    staging_dir = project_dir / "staging"
    staging_dir.mkdir(parents=True, exist_ok=True)

    blob_path = blobs_dir / actual_hash
    validate_path_containment(project_dir, blob_path)

    # Content-addressed idempotency: if blob exists and is verified, reuse it
    if blob_path.exists():
        existing_bytes = blob_path.read_bytes()
        if digest(existing_bytes) == actual_hash:
            return {
                "sha256": actual_hash,
                "filename": filename,
                "size": len(data),
                "blob_path": f"blobs/{actual_hash}",
            }

    temp_blob = staging_dir / f".blob-{actual_hash}-{uuid4().hex}.tmp"
    try:
        with open(temp_blob, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temp_blob, blob_path)
        _fsync_dir(blobs_dir)
    except Exception as exc:
        if temp_blob.exists():
            temp_blob.unlink(missing_ok=True)
        raise ForgeError(ErrorCode.IO_ERROR, f"Failed to persist blob: {exc}") from exc

    return {
        "sha256": actual_hash,
        "filename": filename,
        "size": len(data),
        "blob_path": f"blobs/{actual_hash}",
    }


def get_blob(projects_dir: Path | str, project_id: str, sha256_hash: str) -> bytes:
    """Retrieve raw bytes of an existing content-addressed blob."""
    validate_project_id(project_id)
    clean_hash = sha256_hash.lower().strip()
    if not re.match(r"^[0-9a-f]{64}$", clean_hash):
        raise ForgeError(ErrorCode.INVALID_ARGUMENT, f"Invalid SHA-256 hash '{sha256_hash}'.")

    base_dir = Path(projects_dir).resolve()
    project_dir = base_dir / project_id
    validate_path_containment(base_dir, project_dir)

    blob_path = project_dir / "blobs" / clean_hash
    validate_path_containment(project_dir, blob_path)

    if not blob_path.exists() or not blob_path.is_file():
        raise ForgeError(ErrorCode.INPUT_NOT_FOUND, f"Blob '{clean_hash}' not found in project '{project_id}'.")

    raw_bytes = blob_path.read_bytes()
    if digest(raw_bytes) != clean_hash:
        raise ForgeError(ErrorCode.INVALID_INPUT, f"Blob '{clean_hash}' failed integrity verification on read.")

    return raw_bytes


def list_projects(projects_dir: Path | str) -> list[dict]:
    """Scan and return summary metadata of all valid projects."""
    base_dir = Path(projects_dir).resolve()
    if not base_dir.exists():
        return []

    summaries = []
    for item in sorted(base_dir.iterdir()):
        if not item.is_dir():
            continue
        manifest_path = item / "manifest.json"
        if manifest_path.exists() and manifest_path.is_file():
            try:
                manifest = load_project(base_dir, item.name, verify_blobs=False)
                summaries.append({
                    "project_id": manifest["project_id"],
                    "name": manifest["name"],
                    "revision": manifest["revision"],
                    "actor": manifest["actor"],
                    "profile": manifest["profile"],
                    "updated_at": manifest["updated_at"],
                    "created_at": manifest["created_at"],
                })
            except Exception:
                # Ignore damaged or unmigrated projects during directory listing
                pass

    return summaries
