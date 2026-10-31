# RO Sprite Forge — Persistence, Migration, and Recovery Guide

This guide details the immutable filesystem storage architecture, project manifest versioning, atomic publication guarantees, schema migration, and crash-safe disaster recovery procedures in **RO Sprite Forge**.

---

## 1. Storage Architecture Overview

RO Sprite Forge uses a deterministic, filesystem-based storage engine designed for durability, transparency, and complete offline independence.

```
<projects_dir>/<project_id>/
├── manifest.json                  # Canonical sealed project manifest
├── manifest.json.bak              # Most recent pre-mutation manifest backup
├── manifest.json.pre-migration.bak # Safety backup taken before schema migration
├── blobs/                         # Content-addressed immutable asset store
│   └── <sha256_hash>              # Raw PNG images, ACT/SPR binaries, etc.
└── staging/                       # Isolated directory for in-flight atomic transactions
```

### Key Properties
1. **Content-Addressed Blobs:** Stored under `blobs/<sha256>`. Image files and compiled binaries are identified solely by their SHA-256 content digest. Once written, a blob is **never modified**.
2. **De-duplication:** Identical frames or sprites share the same content blob, minimizing disk footprint.
3. **Single Source of Truth:** `manifest.json` describes the entire project state: target specification, layer topology, source registry, assignment ledger, review decisions, and compilation records.

---

## 2. Manifest Structure & Monotonic Revisions

Every project manifest contains an integer `revision` property ($0, 1, 2, \dots$).
- **Optimistic Concurrency:** Any mutating API operation (`POST /api/projects/:id/assign`, `/review`, `/compile`, etc.) requires the client to supply `expected_revision`.
- **Conflict Rejection:** If another process or tab has updated the project, the server returns `409 Conflict` (`STALE_REVISION_CONFLICT`) to prevent silent overwrites.
- **Sealed Integrity:** Manifests must conform strictly to the versioned JSON Schema (`schemas/project-v1.json` or `project-v2.json`). Extraneous or unvalidated properties are rejected.

---

## 3. Atomic Transactions & Crash Safety

Power loss, process termination, or disk errors during a write operation can corrupt traditional single-file databases. RO Sprite Forge prevents data loss using a strict 4-step write protocol:

```
[Write to staging/.tmp] ──► [fsync(file)] ──► [Atomic os.replace()] ──► [fsync(directory)]
```

1. **Staging Write:** The new manifest or blob is written to a unique temporary file inside `staging/` (e.g. `.manifest-write-abc123.tmp`).
2. **File Sync:** `flush()` and `os.fsync()` force all bytes from kernel cache onto physical media.
3. **Backup Rotation:** If an existing `manifest.json` is healthy, it is preserved as `manifest.json.bak`.
4. **Atomic Rename:** POSIX `os.replace()` atomically swaps the staging file into place as `manifest.json`.
5. **Directory Sync:** `os.fsync()` on the parent project directory guarantees directory entry durability.
6. **Concurrency Locking:** All operations acquire a local cross-thread/cross-process lock (`_get_project_lock`) to eliminate write races.

---

## 4. Project Schema Migration & Version Classification

### Schema Evolution & Layers
RO Sprite Forge versioning encompasses two distinct schema layers:
1. **Project Manifest Schema:** Current canonical schema is `rsf.project/v1`. The engine recognizes and supports migration from legacy project schemas: `rsf.project/v0`, `rsf.project/v0.1`, `rsf.project/v1.0`, and `rsf.project`.
2. **Target Contract Schema:** Current canonical contract is `rsf.target/v2` requiring declared ordered layer topology (`layers` array with `index`, `name`, `role`). Legacy target schemas `rsf.target/v1` and `rsf.target/v0` (which lacked ordered layer topology) trigger migration.

### Classifying Project Version
Operators can programmatically check project versions using the core API:
```python
from ro_sprite_forge.core.project import classify_project_version

status, reason = classify_project_version(project_data)
# Returns: ("CURRENT_SUPPORTED", "Project matches canonical schema 'rsf.project/v1'.")
# or: ("MIGRATION_REQUIRED", "Target uses legacy schema 'rsf.target/v1'.")
```

### Executing Migration
When a v1 project is opened, the operator can migrate it cleanly:
```python
from ro_sprite_forge.core.project import migrate_project

result = migrate_project(
    projects_dir="./projects",
    project_id="my-project",
    target_version="v2",
    default_topology=[
        {"index": 0, "name": "shadow", "role": "shadow"},
        {"index": 1, "name": "body", "role": "main"}
    ]
)
```

**Migration Guarantees:**
- Takes an automatic safety snapshot: `manifest.json.pre-migration.bak`.
- Monotonically increments project `revision`.
- Preserves all existing source blobs, assignments, and reviews without data loss.
- Bit-exact asset preservation: source image hashes and assignment ledgers remain unchanged.
- **Migration Determinism:** Source blobs and assignment hashes remain strictly bit-for-bit identical. The project manifest's canonical hash binds the migration event timestamp (`updated_at`), so canonical manifest identity reflects the discrete migration event while asset contents remain perfectly deterministic.

---

## 5. Crash-Safe Disaster Recovery

If a system crashes mid-transaction or a project manifest is corrupted (e.g. truncated bytes, invalid JSON, missing file), the operator can invoke the built-in recovery mechanism:

```python
from ro_sprite_forge.core.project import recover_project

provenance = recover_project(projects_dir="./projects", project_id="my-project")
```

### Recovery Protocol
1. **Clean Staging:** Deletes any uncommitted, orphaned `.tmp` files from `staging/`.
2. **Audit Primary Manifest:** Validates `manifest.json` syntax and schema conformance. If valid, no manifest restore is needed.
3. **Inspect Backup Candidates:** If `manifest.json` is corrupt or missing, inspects:
   - `manifest.json.bak`
   - `manifest.json.pre-migration.bak`
4. **Atomic Restore:** Restores the newest valid backup candidate via atomic staging rename.
5. **Idempotence:** Running `recover_project` repeatedly on a recovered project causes zero revision drift.

### Recovery Provenance Reporting
The recovery function returns a comprehensive provenance packet:
```json
{
  "project_id": "novice-walk-slice",
  "recovered": true,
  "already_healthy": false,
  "action": "RESTORED_FROM_BACKUP",
  "reason": "Corrupted or missing manifest restored from valid backup 'manifest.json.bak'.",
  "restored_from": "manifest.json.bak",
  "revision": 4,
  "staging_cleaned_count": 2,
  "backup_manifest_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "restored_manifest_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "valid": true
}
```

---

## 6. Project Backup and Export Best Practices

### Creating Cold Backups
To create an offline archive of a project:
1. Ensure the workbench server is idle or stopped.
2. Create a zip or tarball of the project directory:
   ```bash
   tar -czvf novice-walk-slice-backup.tar.gz ./projects/novice-walk-slice
   ```
3. Store the archive securely. Because all image references are content-addressed within `blobs/`, the archive is self-contained and fully portable.

### Restoring from Archive
Extract the archive directly into your active `projects/` directory:
```bash
tar -xzvf novice-walk-slice-backup.tar.gz -C ./projects/
```
Refresh the workbench; the restored project appears immediately with its complete revision history intact.

---

## 7. Security and Integrity Policies

- **Strict Slug Validation:** Project identifiers are restricted by regex `^[a-zA-Z0-9_-]{1,64}$`. Directory traversal attempts like `../../etc` are rejected with `INVALID_ARGUMENT`.
- **Filesystem Containment:** Every path accessed inside a project is verified via `validate_path_containment()` to prevent symlink traversal outside the project root.
- **Strict Size Limits:** Manifest files larger than 16 MiB or uploads larger than 32 MiB are rejected with `PAYLOAD_TOO_LARGE`.
