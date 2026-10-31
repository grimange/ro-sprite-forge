# RSF-37 Implementation & Verification Plan: Project Migration, Recovery and Hostile-Input Hardening

## Overview
Implement versioned project migration, crash-safe atomic recovery, adversarial input hardening, path traversal protection, resource allocation bounding, and deterministic integrity verification for RO Sprite Forge projects.

## Scope & Deliverables
1. **Version Recognition & Deterministic Migration (`src/ro_sprite_forge/core/project.py`)**:
   - Version classifier: `classify_project_version(doc)` returning `CURRENT_SUPPORTED`, `MIGRATION_REQUIRED`, or `UNSUPPORTED_VERSION`.
   - Migration engine: `migrate_project(project_dir)` creating `.bak` backup, safely converting legacy structures to canonical `schemas/project-v1.json`, validating schemas, preserving source hashes in content-addressed `blobs/`, and scoping review invalidations via RSF-18.
2. **Crash-Safe Recovery & Concurrency Hardening**:
   - `recover_project(project_dir)`: inspects interrupted staging files (`manifest-tmp-*`), validates `manifest.json` and `manifest.json.bak`, restores corrupted or missing manifests from valid backups, cleans orphaned temp files, and ensures idempotent recovery.
   - Concurrency protection: enforce optimistic locking (`revision == R`), rejecting stale saves with `STALE_REVISION_CONFLICT`.
3. **Hostile-Input & Bounded-Resource Protections**:
   - Manifest size limit (16 MiB max).
   - Strict path traversal prevention (`..`, `/`, `\`) in blob references and path hints.
   - Symlink escape detection preventing access to files outside project boundary.
   - Comprehensive blob integrity verification: verify file content against computed SHA-256 and stored manifest references.
4. **Adversarial & Fault-Injection Regression Test Suite**:
   - `tests/test_project_hardening.py` covering all 30 adversarial scenarios: interrupted saves, corrupted JSON, missing manifests, backup restores, malformed schemas, path traversals, symlink escapes, oversized manifests, recursion limits, and stale revisions.
5. **Full Verification**:
   - Focused suite: `test_project_hardening.py`
   - Public suite: `python3 -m unittest discover -s tests -p 'test_*.py'`
   - Private fixture suite: `python3 tests/run_private_fixture_tests.py`
   - Schema validation: `python3 tests/validate_schemas.py`
   - Distribution check: `python3 tests/check_distribution.py`
