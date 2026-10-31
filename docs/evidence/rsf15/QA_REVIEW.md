# Independent Technical QA Review: Task RSF-15

- **Task ID**: `e7nsxcjfb2xk226im4v11aic`
- **Ticket**: `RSF-15`
- **Title**: `[M3] Safe local service and atomic project persistence`
- **Milestone**: M3
- **QA Verdict**: **`QA_PASS`**

---

## 1. Executive Summary

An independent, read-only technical audit of task **RSF-15** has been conducted against the repository requirements, AGENTS.md/GEMINI.md invariants, and the comprehensive plan v1.1. All four acceptance criteria have been verified with complete test coverage, strict defense-in-depth security invariants, reproducible artifact hashes, and clean wheel distribution checks.

No security flaws, regressions, or unverified claims were found.

---

## 2. Acceptance Criteria Verification

| # | Acceptance Criterion | Verification & Findings | Status |
| :--- | :--- | :--- | :---: |
| 1 | **Default bind is loopback; enforce Host/origin validation and CSRF/unsafe-method protection from the first server implementation.** | • Default listener is strictly bound to IPv4 `127.0.0.1` (or loopback IPv6 `::1`).<br>• `SecurityManager` validates bind IP via `ipaddress.ip_address(host).is_loopback` and rejects non-loopback bindings (`PERMISSION_DENIED`) unless explicitly overridden with `--allow-insecure-remote`.<br>• Strict Host header allowlist prevents DNS rebinding attacks.<br>• Browser Origin checks disallow unauthorized cross-origin requests; no wildcard `*` CORS is permitted.<br>• Unpredictable 32-byte CSRF token (`secrets.token_urlsafe(32)`) required on all state-changing HTTP methods (`POST`, `PUT`, `DELETE`, `PATCH`) with constant-time verification (`secrets.compare_digest`).<br>• Verified by `tests/test_service.py` (17 tests passing). | **PASS** |
| 2 | **Imports/uploads have bounded sizes and isolated staging; reject traversal, symlink escapes, collisions, source overwrite and project-defined command execution.** | • Bounded payloads: `MAX_REQUEST_BODY_SIZE` (16 MiB), `MAX_BLOB_SIZE` (32 MiB), and `MAX_MANIFEST_SIZE` (16 MiB). Oversized payloads immediately aborted with HTTP 413 / `PAYLOAD_TOO_LARGE`.<br>• Isolated temporary staging (`project/staging/.blob-*.tmp` and `.manifest-*.tmp`) with `os.fsync` before atomic replacement.<br>• Content-addressed blob storage (`blobs/<sha256>`) prevents collisions and source overwriting.<br>• Path containment strictly guarded by `validate_path_containment`: traverses parent components to reject symlinks escaping project directory; rejects directory traversal (`../`), path separators in filenames, and invalid project IDs.<br>• Passive JSON storage format only; no arbitrary execution vectors.<br>• Verified by `tests/test_project.py` and `tests/test_service.py`. | **PASS** |
| 3 | **Versioned manifests and blobs publish atomically with backups; refresh/reopen preserves source hashes, assignments and review records.** | • Manifests follow schema `rsf.project/v1` (`src/ro_sprite_forge/schemas/project-v1.json`).<br>• Optimistic concurrency control via monotonic integer revisions (`expected_revision`); concurrent or stale saves rejected with `CONFLICT` (HTTP 409).<br>• Manifest atomic publication: temporary staging write -> `os.fsync` -> backup to `manifest.json.bak` -> atomic `os.replace`.<br>• Reopen/load validates cryptographic seal `canonical_sha256` and verifies referenced blob presence and hash integrity.<br>• Preserves source hashes, assignments, and review records across lifecycle mutations.<br>• Verified by `tests/test_project.py`. | **PASS** |
| 4 | **HTTP uses the same core validators/use cases as CLI with readable typed errors and no database/network service dependency in core.** | • HTTP service routes directly to `ro_sprite_forge.core.project` core logic.<br>• Standard Python 3.12+ standard library (`http.server`, `hashlib`, `json`, `pathlib`, `secrets`, `ipaddress`); zero external database or network dependencies.<br>• Readable typed JSON error envelope `{"error": {"code": "...", "message": "..."}}` with absolute path and system information masking.<br>• CLI integration via `ro-sprite-forge serve` subcommand cleanly exposes server parameters.<br>• Verified by `tests/check_distribution.py` (isolated wheel build and execution). | **PASS** |

---

## 3. Independent Verification Execution Results

All verification commands were executed independently under `PYTHONDONTWRITEBYTECODE=1`:

1. **Project Persistence Tests**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests/test_project.py`
   - Exit status: `0`
   - Result: `Ran 15 tests in 0.026s -- OK`
2. **HTTP Service & Security Tests**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests/test_service.py`
   - Exit status: `0`
   - Result: `Ran 17 tests in 0.555s -- OK`
3. **Full Public Regression Suite**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
   - Exit status: `0`
   - Result: `Ran 277 tests in 4.119s -- OK`
4. **Audited Private Reference Fixtures**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py'`
   - Exit status: `0`
   - Result: `Ran 36 tests in 11.714s -- OK` (Novice Male & Orc Skeleton preservation and canonical inventories verified)
5. **Distribution & Isolated Wheel Build**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14`
   - Exit status: `0`
   - Result: `DISTRIBUTION_CHECK_PASS` (277 tests passed inside isolated wheel installation)

---

## 4. Deliverable Artifact Hashes

Verified exact cryptographic digests for all task deliverables against `docs/evidence/rsf15/implementation-manifest.json`:

- `src/ro_sprite_forge/schemas/project-v1.json`: `e3088b87ac7c58eaf631122f8bacbe6a05704a63506d5e53b919f12ce1c56042`
- `src/ro_sprite_forge/core/project.py`: `3ffacf467cc86fd34f3271bb2dfcae0e5e35e3bdb96fac5fb6717ad5ad8ffa1d`
- `src/ro_sprite_forge/service/__init__.py`: `dd21c74b8ee25bd87ec7510bd1707788cc3c7a65e1f5b8a62eb39e768c8bc096`
- `src/ro_sprite_forge/service/security.py`: `76cb0b6efe23cd52f0e8c063e0d06a0789424060f3116012fef3a544a4158586`
- `src/ro_sprite_forge/service/server.py`: `0df5a696da6129667b73996fb888d90776574cd09d034a868f48cb1e91191d4c`
- `src/ro_sprite_forge/core/errors.py`: `324b0669452000c4b2594338ee04701cb57b1bb9dc70b9ebb3d931308a007a69`
- `src/ro_sprite_forge/cli.py`: `001fa676c2bbec37fc68ece69cf4bf2a198acaba39f8a3598d4aaee7d128eb05`
- `tests/test_project.py`: `7648224fd051e67515de7795813bb43537ad70cacb3706b1e8d11a6bac5efd98`
- `tests/test_service.py`: `e16e4b0f509c9eae748777a43aee88ce5196efdfe6dca4bbe4587420216f8866`
- `docs/architecture/RSF15_SERVICE.md`: `bc751049389f189f024ee9fc39917552877d8609a8d867c947e9e8e38e4ba825`

---

## 5. Recommendation

Task **RSF-15** satisfies all architectural invariants and verification criteria. The task can safely be transitioned from `QA Review` (`in-review`) to `Accepted` in Kaneo PMP.
