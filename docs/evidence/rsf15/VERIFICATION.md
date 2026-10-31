# RSF-15 Verification Evidence Packet

## Task Identity
- **Task ID**: `e7nsxcjfb2xk226im4v11aic` (Ticket: `RSF-15`)
- **Title**: `[M3] Safe local service and atomic project persistence`
- **Milestone**: M3
- **Author / Implementer**: Codex / Antigravity Implementation Session
- **Status**: Implemented, verified locally, ready for independent QA Review

---

## Deliverables & Component Architecture

1. **Packaged Draft 2020-12 Schema** (`src/ro_sprite_forge/schemas/project-v1.json`):
   - Schema ID: `https://ro-sprite-forge.invalid/schemas/project-v1.json` (`rsf.project/v1`)
   - Strictly defines project manifest structure: `project_id`, `name`, `revision`, `created_at`, `updated_at`, `actor`, `profile`, `sources`, `reviews`, and cryptographic seal `canonical_sha256`.
2. **Project Persistence & Content-Addressed Blob Storage** (`src/ro_sprite_forge/core/project.py`):
   - Lifecycle operations: `create_project`, `load_project`, `save_project`, `list_projects`, `import_blob`, `get_blob`.
   - Optimistic concurrency control via explicit revision numbers; stale saves rejected with `CONFLICT`.
   - Atomic JSON manifest publication: temporary staging, `os.fsync`, backup to `manifest.json.bak`, and atomic `os.replace`.
   - Content-addressed source blob storage (`blobs/<sha256>`) with deduplication and read-back integrity verification.
   - Strict path containment (`validate_path_containment`), anti-traversal (`../`), and symlink escape defenses.
3. **Local Loopback Security Management** (`src/ro_sprite_forge/service/security.py`):
   - Enforces loopback binding (`127.0.0.1`, `::1`, `localhost`) by default; non-loopback bindings rejected with `PERMISSION_DENIED`.
   - Host validation against configured local authority to defend against DNS rebinding attacks.
   - Origin validation against local allowlist with zero wildcard `*` CORS.
   - Unpredictable 32-byte CSRF token enforcement (`secrets.token_urlsafe(32)`) on state-changing methods (`POST`, `PUT`, `DELETE`, `PATCH`).
4. **Local HTTP Application Service & API Router** (`src/ro_sprite_forge/service/server.py`):
   - Built on pure Python 3.12+ standard library (`http.server.ThreadingHTTPServer`).
   - Bounded request size (`MAX_REQUEST_BODY_SIZE = 16 * 1024 * 1024`) and blob size (`MAX_BLOB_SIZE = 32 * 1024 * 1024`).
   - RESTful API endpoints: `/api/health`, `/api/csrf-token`, `/api/projects`, `/api/projects/{id}`, `/api/projects/{id}/blobs`, `/api/projects/{id}/validate`.
   - Consistent typed JSON error mapping (`{"error": {"code": ..., "message": ...}}`) with sensitive path/traceback suppression.
5. **CLI Serve Subcommand** (`src/ro_sprite_forge/cli.py`):
   - Added `serve` subcommand: `ro-sprite-forge serve [--host 127.0.0.1] [--port 8080] [--projects-dir ./projects] [--allow-insecure-remote]`.
6. **Architectural Specification** (`docs/architecture/RSF15_SERVICE.md`):
   - Comprehensive documentation of service boundaries, threat model, persistence layout, concurrency semantics, and error handling.
7. **Comprehensive Automated Unit & Security Test Suites**:
   - `tests/test_project.py`: 15 persistence, atomic write, concurrency, and path defense unit tests.
   - `tests/test_service.py`: 17 HTTP, security, Host/Origin/CSRF, and boundary unit tests.

---

## Acceptance Criteria Traceability

| Acceptance Criterion | Implementation Evidence | Result |
| :--- | :--- | :--- |
| **1. Default bind is loopback; enforce Host/origin validation and CSRF/unsafe-method protection from first server** | Loopback binding validated in `SecurityManager`. Host headers checked against local authority. Origin checked against exact local allowlist without wildcard. CSRF tokens enforced on all unsafe HTTP methods. Tested in `tests/test_service.py`. | **PASS** |
| **2. Imports/uploads have bounded sizes and isolated staging; reject traversal, symlink escapes, collisions, source overwrite and project-defined command execution** | Bounded request bodies (16 MiB limit) and blobs (32 MiB limit). Isolated `staging/` directory used before atomic replacement. Content-addressed blobs prevent collision/overwrite. Traversal and symlinks rejected by `validate_path_containment`. Tested in `tests/test_project.py` and `tests/test_service.py`. | **PASS** |
| **3. Versioned manifests and blobs publish atomically with backups; refresh/reopen preserves source hashes, assignments and review records** | Manifests staged, fsync'd, and atomically replaced (`os.replace`) with `manifest.json.bak` backup. Revision numbers incremented under optimistic concurrency control. Source hashes and review records preserved across saves/loads. Tested in `tests/test_project.py`. | **PASS** |
| **4. HTTP uses same core validators/use cases as CLI with readable typed errors and no database/network service dependency in core** | HTTP router directly calls `ro_sprite_forge.core.project` which invokes core contracts, canonical JSON, and hashing utilities. Pure Python standard library with zero database or external network dependencies. Errors follow typed format `{"error": {"code": ..., "message": ...}}`. Tested in `tests/check_distribution.py`. | **PASS** |

---

## Verification Results Summary

| Verification Gate | Command | Result | Details |
| :--- | :--- | :--- | :--- |
| **Public Unit Tests** | `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'` | **PASS** | 277/277 passing (3.939s) |
| **Audited Private Fixtures** | `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py'` | **PASS** | 36/36 passing (11.228s) |
| **Package & Wheel Distribution** | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | **PASS** | `DISTRIBUTION_CHECK_PASS` (277 tests passing in isolated wheel install) |

---

## Artifact Hashes

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
