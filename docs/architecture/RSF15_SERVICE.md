# RSF-15 Safe Local Service and Atomic Project Persistence Specification

## 1. Architectural Scope and Role

RO Sprite Forge is a standalone, local, human-operated requirements planner, animation inspection workbench, and deterministic SPR/ACT compiler. Its application core is written in pure Python 3.12+ standard library with no external database, cloud service, or running game server dependencies.

RSF-15 establishes the foundational backend transport and persistence layer that allows all previous capabilities (M0 inventory and preservation, M1 finite requirements and ledgers, M2 preview and animation diagnostics) to become safely accessible to future browser-based operator interfaces (M3 workbench, RSF-16–RSF-18).

```text
Local Operator Browser (M3 UI)             CLI (Automation/Scripts)
            \                                      /
             \--- HTTP API (RSF-15) --------------/
                       |
               Application Core
  [Inventory | Contracts | Requirements | Ledger | Preview | Compiler]
                       |
        Project Storage & Persistence (RSF-15)
  [Atomic Manifests | Content-Addressed Blobs | Concurrency | Backups]
```

---

## 2. Local HTTP Service Architecture

### 2.1 Loopback Binding Policy
- **Default Listener**: Explicitly bound to IPv4 loopback (`127.0.0.1`) or IPv6 loopback (`::1`).
- **Enforcement**: `SecurityManager` inspects the bind address using `ipaddress.ip_address(host).is_loopback` before socket binding. Attempts to bind to `0.0.0.0` or non-loopback network interfaces are rejected with `PERMISSION_DENIED` unless `--allow-insecure-remote` is explicitly specified by the operator.
- **Port Allocation**: Defaults to port 8080 or dynamic port allocation (port 0) for automated test suites.

### 2.2 Host and DNS Rebinding Protection
A loopback-bound server is vulnerable to malicious external websites issuing requests to `http://localhost:<port>` or utilizing DNS rebinding domains.
- **Host Validation**: Every incoming request must supply a valid `Host` header.
- **Authority Allowlist**: The `Host` header must match one of the server's configured local authorities (`127.0.0.1:<port>`, `localhost:<port>`, `[::1]:<port>`, or bare hostnames).
- **Rejection**: Any unexpected host (e.g. `evil.com`, `attacker.local`) is immediately rejected with HTTP 403 Forbidden (`SECURITY_HOST_INVALID`) prior to any route dispatching.

### 2.3 Browser Origin and CORS Discipline
- **No Wildcard CORS**: The service strictly forbids wildcard `*` CORS headers.
- **Origin Allowlist**: Cross-origin requests are checked against the explicit local origin set (`http://127.0.0.1:<port>`, `http://localhost:<port>`, `http://[::1]:<port>`).
- **Preflight `OPTIONS`**: Handled with explicit `Access-Control-Allow-Origin: <origin>` only when the origin is in the local allowlist. Hostile origins receive HTTP 403 Forbidden.
- **Safe Method Protection**: Even `GET` requests bearing an unauthorized `Origin` header are rejected with HTTP 403.

### 2.4 CSRF Protection
- **Token Generation**: Upon server initialization, `SecurityManager` generates a cryptographically unpredictable 32-byte token using `secrets.token_urlsafe(32)`.
- **Token Acquisition**: Local browser sessions obtain the active token via `GET /api/csrf-token`.
- **Enforcement**: All state-changing HTTP methods (`POST`, `PUT`, `DELETE`, `PATCH`) must supply the token in the `X-CSRF-Token` header.
- **Constant-Time Verification**: Verified using `secrets.compare_digest` to prevent timing attacks. Missing or mismatched tokens are rejected with HTTP 403 Forbidden before any state mutation occurs.

### 2.5 Bounded Resource Limits
- **Request Body Limit**: `MAX_REQUEST_BODY_SIZE = 16 * 1024 * 1024` (16 MiB). Requests declaring a larger `Content-Length` or streaming more than 16 MiB are immediately aborted with HTTP 413 Payload Too Large.
- **Blob Limit**: `MAX_BLOB_SIZE = 32 * 1024 * 1024` (32 MiB). Individual source assets exceeding 32 MiB are rejected with HTTP 413.
- **Manifest Limit**: `MAX_MANIFEST_SIZE = 16 * 1024 * 1024` (16 MiB).

---

## 3. Filesystem Project Persistence

### 3.1 On-Disk Directory Layout
```text
<projects_dir>/
  <project_id>/
    manifest.json          # Durable canonical project record (schema: rsf.project/v1)
    manifest.json.bak      # Immediate backup of previous revision
    blobs/                 # Immutable content-addressed storage (SHA-256)
      095220613fe3...      # Raw asset content (SPR, ACT, PNG)
      f1b69541dc3e...
    staging/               # Isolated temporary writes (cleaned on startup/recovery)
      .manifest-*.tmp
      .blob-*.tmp
```

### 3.2 Atomic Manifest Publication
A project manifest is never modified in place:
1. Proposed manifest state is validated against JSON Schema (`rsf.project/v1`).
2. Optimistic concurrency check: verified against current on-disk `revision`.
3. Revision number is incremented (`new_revision = expected_revision + 1`).
4. Canonical JSON bytes are serialized and cryptographically sealed with `canonical_sha256`.
5. Staged to a temporary file (`staging/.manifest-<uuid>.tmp`).
6. Content is flushed to disk and synchronized with `os.fsync(fd)`.
7. Existing `manifest.json` is copied to `manifest.json.bak` as a durability backup.
8. Atomic replacement via `os.replace(staging_file, manifest_file)` commits the revision.
9. Any failure prior to step 8 preserves the existing valid manifest intact.

### 3.3 Content-Addressed Blob Storage
- **Identity by Content**: Blobs are addressed strictly by their SHA-256 digest (`blobs/<sha256>`).
- **Immutability & Idempotence**: Existing verified blobs are never overwritten. Re-importing identical bytes returns the existing content pointer.
- **Integrity Validation**: When opening/loading projects, `load_project(..., verify_blobs=True)` verifies that every referenced source blob exists and matches its recorded SHA-256.

### 3.4 Path Containment and Anti-Traversal
All filesystem paths are guarded by `validate_path_containment`:
- Validates that `(base_dir / target).resolve()` is strictly within `base_dir.resolve()`.
- Rejects `../` directory traversals.
- Rejects symlink escapes: inspects path components to ensure no symlink resolves outside the project boundary.
- Enforces strict project ID format: `^[a-zA-Z0-9_-]{1,64}$`.

---

## 4. HTTP API Contract

| Endpoint | Method | Security | Description | Response Status |
| :--- | :---: | :--- | :--- | :--- |
| `/api/health` | `GET` | Host | Server status, version, and loopback confirmation | 200 OK |
| `/api/csrf-token` | `GET` | Host | Retrieve active CSRF token | 200 OK |
| `/api/projects` | `GET` | Host | List all valid project summaries in project directory | 200 OK |
| `/api/projects` | `POST` | Host, Origin, CSRF | Create new project with initial revision 1 | 201 Created |
| `/api/projects/{id}` | `GET` | Host | Load project manifest and verify blob integrity | 200 OK / 404 |
| `/api/projects/{id}` | `PUT` | Host, Origin, CSRF | Save project revision (optimistic concurrency) | 200 OK / 409 |
| `/api/projects/{id}/blobs` | `POST` | Host, Origin, CSRF | Import content-addressed blob (binary or JSON base64) | 201 Created / 413 / 422 |
| `/api/projects/{id}/blobs/{sha}` | `GET` | Host | Download raw content-addressed blob | 200 OK / 404 |
| `/api/projects/{id}/validate` | `POST` | Host, Origin, CSRF | Execute core validation against project state | 200 OK / 422 |

---

## 5. Typed Error Handling

Errors follow the stable application error envelope:
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable explanation",
    "path": "optional_relative_path"
  }
}
```

HTTP Status mapping:
- `INVALID_ARGUMENT`: 400 Bad Request
- `INVALID_INPUT`: 422 Unprocessable Entity
- `INPUT_NOT_FOUND`: 404 Not Found
- `CONFLICT`: 409 Conflict (revision conflict, duplicate project)
- `PERMISSION_DENIED`: 403 Forbidden (CSRF, Host, Origin, path traversal)
- `PAYLOAD_TOO_LARGE`: 413 Payload Too Large
- `IO_ERROR`: 500 Internal Server Error (internal error masked; no stack traces or system paths leaked)
