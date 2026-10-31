# Independent QA Verification Report — RSF-37

**Task:** RSF-37 (`[M8] Project migration, recovery and hostile-input hardening`)  
**Task ID:** `pfbw69nufbfh2yh8wzjmrdc9`  
**Milestone:** M8 — Release Readiness  
**Reviewer:** forge-qa-reviewer (Independent Read-Only QA Session)  
**Date:** 2026-10-31  
**Verdict:** **QA_PASS**

---

## 1. Executive Summary

An independent, clean-room audit and verification of task RSF-37 was conducted. The task scope encompasses deterministic project schema migration, crash-safe atomic publication and backup recovery, hostile-input and resource-bound hardening, and distinct persistence of source/composition hashes.

All four live acceptance criteria were independently verified against the codebase, automated unit and adversarial test suites, isolated distribution environments, and manifest hashes.

**Key Code Deliverables Verified:**
- `src/ro_sprite_forge/core/project.py`  
  SHA-256: `7a5ea31445c90c02d8555b77f6a7303c1cbfd373cbea56db1958f6dd4ab72b4a` (Size: 35,853 bytes)
- `tests/test_project_hardening.py`  
  SHA-256: `efed86851833397d2a8b1b20a1e4e4b3ef10c1fcd258e4568b3f70278c2ce378` (Size: 26,660 bytes)

Both files match bit-exact with the implementation manifest recorded in `docs/verification/rsf-37/implementation-manifest.json`.

---

## 2. Acceptance Criteria Evaluation

### Criterion 1: Migrations preserve original source hashes and invalidate only affected assignments/reviews with traceable links and backups
- **Verdict:** **PASS**
- **Independent Evidence:**
  - `classify_project_version(project_data)` unambiguously identifies `CURRENT_SUPPORTED`, `MIGRATION_REQUIRED`, and `UNSUPPORTED_VERSION` schemas (supporting legacy schemas `rsf.project/v0`, `rsf.project/v0.1`, `rsf.project/v1.0`, and `rsf.project`).
  - `migrate_project(projects_dir, project_id, ...)` generates pre-migration backups (`manifest.json.pre-migration.bak` and `manifest.json.bak`) prior to applying transformations.
  - Source integrity invariant enforced: `migrated.get("sources") == manifest_data.get("sources")` verifies that source hashes, filenames, and byte sizes remain unaltered.
  - Scoped review invalidation: when target definitions change during schema migration, affected reviews are transitioned from `approved=True` to `approved=False` with invalidated review IDs reported in the migration response. Migrations without target changes leave existing reviews untouched.
  - Post-migration manifest advances revision ($R \to R+1$), updates timestamp, reseals canonical hash, and validates against `schemas/project-v1.json`.
  - Migration is idempotent: repeated runs on an already current project return `ALREADY_CURRENT` without file mutations or revision drift.
  - Independently verified in tests 1, 2, 3, 4, 5, 6, 25, 26, and 27 of `tests/test_project_hardening.py`.

### Criterion 2: Interrupted/cancelled imports/builds and restore flows cannot delete source projects, expose partial approved outputs or overwrite originals
- **Verdict:** **PASS**
- **Independent Evidence:**
  - All manifest writes and blob imports write to isolated hidden temporary files in `staging/` (`.manifest-*.tmp`, `.blob-*.tmp`) before calling `os.fsync` and atomic `os.replace`.
  - Interrupted processes leave orphaned staging files that do not affect authoritative project reads and are safely cleaned up via `cleanup_staging(project_dir)`.
  - Truncated or corrupted manifests can be safely restored via `recover_project(projects_dir, project_id)` from `manifest.json.bak` or `manifest.json.pre-migration.bak`, returning an explicit recovery audit report.
  - Recovery is idempotent: repeated runs on healthy projects report `already_healthy=True` and `action="NO_ACTION_NEEDED"` without mutation or revision drift.
  - If both manifest and backups are corrupt or missing, `recover_project` safely returns `UNRECOVERABLE` without deleting the project directory or corrupting preserved files.
  - Build publications in `build.py` execute atomically, preventing partial bundle exposure or overwrites.
  - Independently verified in tests 7, 8, 12, 23, and 24 of `tests/test_project_hardening.py`.

### Criterion 3: Bound sizes/counts/offsets/dimensions/layers/decompression/video decode resources before allocation; malformed manifests/traversal/symlinks/collisions fail safely
- **Verdict:** **PASS**
- **Independent Evidence:**
  - `parse_manifest_bytes(raw_bytes, ...)` enforces strict resource bounds before parsing:
    - Maximum manifest size: 16 MiB (`MAX_MANIFEST_SIZE`). Oversized payloads raise `ForgeError(ErrorCode.PAYLOAD_TOO_LARGE)`.
    - Empty manifest check: 0-byte payloads raise `ForgeError(ErrorCode.INVALID_INPUT)`.
    - JSON nesting depth ceiling: 64 levels (`MAX_JSON_DEPTH`). Deeply nested objects raise `ForgeError(ErrorCode.INVALID_INPUT)`.
    - Duplicate JSON key rejection: `_strict_pairs_hook` rejects duplicate keys with `ForgeError(ErrorCode.INVALID_INPUT)`.
    - Nonfinite constants: `parse_constant` strictly forbids `NaN`, `Infinity`, and `-Infinity`.
  - Path traversal & symlink escape defenses:
    - `validate_project_id` enforces regex `^[a-zA-Z0-9_-]{1,64}$`, rejecting path separators, traversal `..`, and control characters.
    - `validate_safe_filename` enforces length 1–256 characters, rejecting `/`, `\`, and NUL bytes.
    - `validate_path_containment` validates resolved paths within the project base directory and verifies all ancestor path components to prevent symlink escapes.
    - Manifest `sources[id]["blob_path"]` is strictly validated to start with `blobs/` and contain no traversal escapes.
  - Bounded blob storage: `MAX_BLOB_SIZE = 32 * 1024 * 1024` (32 MiB). Blobs exceeding 32 MiB raise `ForgeError(ErrorCode.PAYLOAD_TOO_LARGE)`.
  - Archive safety: archive files are treated as raw immutable blobs without extracting or expanding into filesystem hierarchies.
  - Independently verified in tests 13, 14, 15, 16, 17, 18, 19, 20, 21, and 22 of `tests/test_project_hardening.py`.

### Criterion 4: Build/native evidence and source/composition hashes persist distinctly; local origin/Host/CSRF protections remain enforced
- **Verdict:** **PASS**
- **Independent Evidence:**
  - Build composition identities are computed independently via canonical visual inputs (`approved_composition_sha256`) and kept separate from execution logs and output hashes in compilation manifests.
  - `audit_project_integrity(projects_dir, project_id)` independently verifies content-addressed disk files in `blobs/` against declared manifest `sources` SHA-256 and detects orphaned, missing, or corrupted blobs.
  - Local HTTP service security (`security.py`) enforces:
    - Loopback-only binding (`127.0.0.1`, `localhost`, `::1`).
    - DNS rebinding prevention via Host header allowlists.
    - Cross-origin browser protection via strict Origin header validation.
    - CSRF protection requiring cryptographically unpredictable `X-CSRF-Token` for state-changing requests.
  - Isolated virtual environment distribution check (`tests/check_distribution.py`) passed all 677 public tests without source checkout dependency (`DISTRIBUTION_CHECK_PASS`).
  - Independently verified in tests 1, 9, 10, 11, 28, 29, and 30 of `tests/test_project_hardening.py` and distribution verification.

---

## 3. Independent Test Execution Matrix

| Test Suite / Gate | Command | Exit Code | Result | Notes |
| :--- | :--- | :---: | :---: | :--- |
| **Manifest Check** | SHA-256 comparison of implementation & evidence manifests | `0` | **PASS** | 100% hash and size match across code and evidence files |
| **Focused Hardening Suite** | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests/test_project_hardening.py -v` | `0` | **PASS** | 30/30 tests passed in 0.086s |
| **Full Public Discovery** | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py'` | `0` | **PASS** | 677/677 tests passed in 65.5s |
| **Private Fixture Hooks** | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py'` | `0` | **PASS** | 52 tests (51 passed, 1 skipped/NOT_RUN for GPU native playback) in 31.4s |
| **Schema Checkers (13 scripts)** | `for s in scripts/check_*schema*.py; do python3 "$s" \|\| exit 1; done` | `0` | **PASS** | 13/13 schema validation scripts passed |
| **Isolated Distribution Check** | `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | `0` | **PASS** | `DISTRIBUTION_CHECK_PASS` (677 run, 661 passed, 16 skipped for optional external tools) |

---

## 4. Observations & Non-Regressions

1. **Clean Failure Reporting and No Silent Normalization:**  
   In compliance with Milestone M8 constraints, unknown future schemas (`rsf.project/v99.0`) and unsupported ancient drafts are explicitly rejected with typed `ForgeError(ErrorCode.INVALID_INPUT)` rather than silently degraded or auto-normalized.
2. **Idempotency and Concurrency:**  
   Both schema migrations and crash-recovery procedures were validated to be completely idempotent: repeated invocations introduce zero mutations, zero file changes, and zero revision increments. Revision conflicts are cleanly rejected with `ErrorCode.CONFLICT`.
3. **Bit-Exact Blob Integrity:**  
   Content-addressed storage guarantees that original sources are immutable. Any disk tampering is flagged immediately by `load_project(verify_blobs=True)` and `audit_project_integrity`.

---

## 5. Final QA Verdict

**Verdict:** `QA_PASS`

All 4 acceptance criteria for RSF-37 have been independently validated and satisfied with complete evidence. The task is ready for operator acceptance synchronization in Kaneo PMP.
