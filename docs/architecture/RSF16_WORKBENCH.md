# RSF-16 Architecture Specification: Requirements-First Operator Workbench & Readiness Reports

**Milestone:** M3 (Animation Inspection & Operator Workbench)  
**Task:** `RSF-16` / `[M3] Requirements-first operator workspace and readiness reports`  
**Primary Compatibility Target:** Pinned Korangar build  
**Core Runtime:** Pure Python 3.12+ (standard library only for core domain logic; vanilla ES6, HTML5, CSS3 for frontend)  

---

## 1. Overview and Operational Philosophy

The Operator Workbench is a local-first, human-operated web workspace serving as the interactive command center for Ragnarok animation planning, inspection, and verification.

### Core Architecture Invariants

1. **Separation of Authorities:**
   - **Observed Resource Inventory:** Classic resource observations (`rsf.resource-inventory/v1`).
   - **Pinned Runtime Profile:** Pinned Korangar action/view/timing mappings (`rsf.runtime-profile/v2`).
   - **Operator Target Declaration:** Operator-authored finite production requirement (`rsf.target/v2`).
   - **Artwork Assignment Ledger:** Deterministic source-to-requirement assignment mapping (`rsf.assignment-ledger/v1`).
2. **Human Operator Visual Authority:**
   - Programmatic tests assess structural validity, topological consistency, and deterministic coverage.
   - The operator retains sole authority over aesthetic suitability, frame appropriateness, anatomy, poses, and character style.
   - Programmatic PASS never equates to aesthetic approval or runtime proof.
3. **Explicit Layer Topology:**
   - Every target must explicitly declare or inherit ordered layer topology before artwork work orders can proceed.
   - Underspecified topology is surfaced as a blocker (`UNDERSPECIFIED_LAYER_TOPOLOGY`).
   - The workbench never defaults silently to a 1-layer structure.

---

## 2. Workbench Layout and Interaction Model

The workbench provides an uncluttered, responsive 3-column layout with persistent header and footer panels:

### 2.1 Header Panel
- **Project Selection:** Switch active projects from local directory (`/api/projects`).
- **New Project Modal:** Create a new project with slug, name, actor template, and profile.
- **Persistence Controls:** Real-time optimistic revision indicator (`Rev N`) and save button.

### 2.2 Left Navigation Panel: Hierarchical Requirements Tree
- **Hierarchical Grouping:**
  - `Action` (e.g., `Walk`, `Idle`)
  - `View / Numeric Slot` (e.g., `View 0 (Slot 8)`)
  - `Frame` (e.g., `Frame 0`)
  - `Layer Occurrence` (e.g., `Layer 0: torso`, `Layer 1: cloak`)
- **Interactive Search:** Instant substring search across actions, views, slots, parts, and roles.
- **Orthogonal Status Filters:**
  - `ALL`: Display all occurrences.
  - `[!] UNDER`: Underspecified frame count or layer topology (`UNDERSPECIFIED_LAYER_TOPOLOGY`).
  - `[-] UNASSIGNED`: Required occurrences lacking artwork assignments.
  - `[x] INVALID`: Sources or assignments with validation errors or hash mismatches.
  - `[?] REVIEW`: Occurrences awaiting operator visual review.
  - `[ø] UNSUPP`: Actions unsupported by the pinned runtime profile.
  - `[~] REUSED`: Explicit reuse dependencies.
  - `[✓] READY`: Resolved, validated, approved, and runtime-supported occurrences.
- **Accessibility:**
  - Full keyboard tree navigation (`ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight`, `Enter`, `Space`).
  - Non-color-only status badges with distinct icons, borders, and label text.

### 2.3 Center Panel: Target, Topology, and Inspector
- **Target & Topology Bar:**
  - Live displays for Scope (`scoped` vs `full`), Actor, Profile, and Topology Summary.
  - "Define Target & Topology" dialog allowing operators to configure actions, views, frame counts, and ordered layer names (e.g., `torso, cloak`).
  - Blocker alert banner when topology is missing or underspecified.
- **Occurrence Inspector:**
  - Displays canonical occurrence ID (e.g., `project/r1/body/action/Walk/slot8/view0/frame0/layer0`).
  - Coordinate breakdown: Part, Action, Slot, View, Frame, Layer Ordinal, Role, and Authority.
  - Topology Provenance: Shows declaration source (explicit vs inherited from hash-pinned inventory).
  - Diagnostic issues and actionable guidance.

### 2.4 Right Panel: Orthogonal Status Breakdown
Displays independent status dimensions for the selected occurrence:
1. **Artwork Availability:** `AVAILABLE` / `MISSING` / `REUSED` / `UNVERIFIED`
2. **Technical Validation:** `VALID` / `INVALID` / `UNVERIFIED`
3. **Visual Operator Review:** `APPROVED` / `REJECTED` / `UNVERIFIED` / `NOT_REQUIRED`
4. **Pinned Runtime Support:** `SUPPORTED` / `UNSUPPORTED` / `UNVERIFIED`

### 2.5 Bottom Panel: Orthogonal Counters and Work Order Export
- **Counters:**
  - Slot counts (required, optional, underspecified)
  - Frame counts
  - Layer counts
  - Unassigned counts
  - Unique selected sources & distinct content hashes
- **Global Status Indicators:**
  - Overall Completeness (`COMPLETE_FOR_DECLARED_SCOPE`, `INCOMPLETE`, `UNDERSPECIFIED`)
  - Structural Specification (`COMPLETE_FOR_DECLARED_SCOPE`, `UNDERSPECIFIED`)
  - Assignment Coverage (`UNASSIGNED`, `PARTIAL`, `COMPLETE`)
  - Technical Validation (`NOT_RUN`, `VALID`, `INVALID`)
  - Accepted Artwork Coverage (`INCOMPLETE`, `COMPLETE`)
- **Export Actions:**
  - "Work Order (TXT)": Generates human-readable missing-art work order text.
  - "Work Order (JSON)": Exports structured actionable work order payload.

---

## 3. Targeted RSF-15 Integration Corrections

### 3.1 Concurrent-Save Race Condition
- **Problem:** In multi-threaded environments, two requests with the same expected revision could concurrently inspect `load_project`, both observe `current_revision == expected_revision`, and both perform an atomic `os.replace`, resulting in an unnotified lost update.
- **Resolution:** Added `_get_project_lock(project_path)` using `threading.Lock` serialized per project directory. Competing saves with the same expected revision cleanly result in exactly one HTTP 200 success and one HTTP 409 Conflict.

### 3.2 Upload Limit Reconciliation
- **Problem:** RSF-15 set `MAX_REQUEST_BODY_SIZE = 16 MiB`, which truncated 32 MiB binary blob uploads or base64 JSON uploads (~42.7 MiB).
- **Resolution:** Reconciled `MAX_REQUEST_BODY_SIZE = 48 * 1024 * 1024` (48 MiB) in `server.py`, ensuring that full 32 MiB blobs can be uploaded as raw binary or base64 JSON while enforcing `MAX_BLOB_SIZE = 32 MiB` inside project storage.

---

## 4. API Endpoints Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Serves workbench `index.html`. |
| `GET` | `/static/<path>` | Serves static assets (`workbench.css`, `workbench.js`) with path containment. |
| `GET` | `/api/actors` | Lists available standard actor templates (`player`, `monster`, `npc`, `unverified`). |
| `GET` | `/api/profiles` | Lists available runtime profiles (`player`, `monster`, `npc`, `unverified`). |
| `GET` | `/api/projects` | Lists all projects with revisions and metadata. |
| `GET` | `/api/projects/{id}` | Returns project manifest. |
| `GET` | `/api/projects/{id}/requirements` | Resolves target into canonical `rsf.resolved-requirements/v1` tree. |
| `GET` | `/api/projects/{id}/coverage` | Evaluates coverage into canonical `rsf.coverage-report/v1`. |
| `GET` | `/api/projects/{id}/work-order` | Exports missing-art work order in plain text or JSON format. |
| `PUT` | `/api/projects/{id}` | Updates project manifest with optimistic revision check. |
| `POST` | `/api/projects` | Creates new project with atomic directory initialization. |
| `POST` | `/api/projects/{id}/blobs` | Imports content-addressed binary blob (up to 32 MiB). |
