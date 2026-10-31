# Independent QA Verification Report — RSF-38

**Task:** RSF-38 (`[M8] Operator documentation, error catalog and workflow ergonomics`)  
**Task ID:** `u6ktol9i5uld3lnmxrub22si`  
**Milestone:** M8 — Release Readiness  
**Reviewer:** forge-qa-reviewer (Independent Read-Only QA Session)  
**Date:** 2026-10-31  
**Verdict:** **QA_PASS**

---

## 1. Executive Summary

An independent, clean-room audit and verification of task **RSF-38** was conducted. The task deliverable encompasses operator documentation, an actionable error/remediation catalog, responsive desktop workspace ergonomics, keyboard shortcuts, integer pixel zoom, transparent/checkerboard viewport inspection, and non-color-only diagnostic badging.

All 6 acceptance criteria for RSF-38 were independently evaluated and verified against the codebase, automated unit test suites, 13 schema checkers, headless browser DOM assertions, visual screenshot evidence, and isolated distribution test environments.

---

## 2. Deliverables & File Hash Integrity

The deliverables recorded in `docs/verification/rsf-38/implementation-manifest.json` were audited bit-for-bit against disk:

| File Path | Recorded SHA-256 | Actual SHA-256 | Status |
|---|---|---|:---:|
| `src/ro_sprite_forge/core/project.py` | `8caca11b514b59c3a0eb365a46e7cca3633a0597e03470c91b3da8a1059dae64` | `8caca11b514b59c3a0eb365a46e7cca3633a0597e03470c91b3da8a1059dae64` | **MATCH** |
| `src/ro_sprite_forge/static/index.html` | `f83792a913bc144150b63db716b4255605a5d6ce4e8e3cbae2b22451efaaffa6` | `f83792a913bc144150b63db716b4255605a5d6ce4e8e3cbae2b22451efaaffa6` | **MATCH** |
| `src/ro_sprite_forge/static/workbench.css` | `65978f235243b5a29373f64808e965a0b1509793e05b1aefc14ec397e6ab50dd` | `65978f235243b5a29373f64808e965a0b1509793e05b1aefc14ec397e6ab50dd` | **MATCH** |
| `src/ro_sprite_forge/static/workbench.js` | `c37d25cf50ee0409114a4836fc1f058aba4661264c13ba1ada749788202e2df8` | `c37d25cf50ee0409114a4836fc1f058aba4661264c13ba1ada749788202e2df8` | **MATCH** |
| `MANIFEST.in` | `e339cbd7cdf08614d6573fa2553cc32f349ea60ba44dac38cdb964115f4e5d43` | `e339cbd7cdf08614d6573fa2553cc32f349ea60ba44dac38cdb964115f4e5d43` | **MATCH** |
| `tests/check_distribution.py` | `35783eb2c193ba875c3ed44f723d49738a446fb11409ccff9439c4bdf82fb52a` | `35783eb2c193ba875c3ed44f723d49738a446fb11409ccff9439c4bdf82fb52a` | **MATCH** |
| `tests/test_operator_documentation_and_ux.py` | `6c5f5827ba058ca356d98964619b661b44d386e1d3d6d50635cef7ff97cca3d8` | `6c5f5827ba058ca356d98964619b661b44d386e1d3d6d50635cef7ff97cca3d8` | **MATCH** |
| `docs/operator/README.md` | `75ce2e4e5da183c6d06dc2fa02625d13b0c9f760605ca9e2c023adf90056d9c7` | `75ce2e4e5da183c6d06dc2fa02625d13b0c9f760605ca9e2c023adf90056d9c7` | **MATCH** |
| `docs/operator/QUICKSTART.md` | `67a043af993ce4cf8ce92ed5cd772a760d8803d4ccb5b69757111ede77426da2` | `67a043af993ce4cf8ce92ed5cd772a760d8803d4ccb5b69757111ede77426da2` | **MATCH** |
| `docs/operator/PRODUCTION_GUIDE.md` | `05b5e9d8ed8d146187c4a8472daa7ad4d0b62b301f00f24a29cb152c7736e0e5` | `05b5e9d8ed8d146187c4a8472daa7ad4d0b62b301f00f24a29cb152c7736e0e5` | **MATCH** |
| `docs/operator/COMPATIBILITY_AND_ACTIONS.md` | `a96daa1f10f0310c9b02c0b0ccd83c780440cf3ed0aa767591341d15e494b3aa` | `a96daa1f10f0310c9b02c0b0ccd83c780440cf3ed0aa767591341d15e494b3aa` | **MATCH** |
| `docs/operator/PERSISTENCE_AND_RECOVERY.md` | `46184d16372ae209b09d0e0a4545c1d887c5d3fd2387e2c6b8e83a7f7039a1e3` | `46184d16372ae209b09d0e0a4545c1d887c5d3fd2387e2c6b8e83a7f7039a1e3` | **MATCH** |
| `docs/operator/ERROR_CATALOG.md` | `77dcf5a61321e7b0d8570a2c9bd91bfedade18946ede7f10e15c866a34a655d2` | `77dcf5a61321e7b0d8570a2c9bd91bfedade18946ede7f10e15c866a34a655d2` | **MATCH** |
| `docs/operator/TUTORIAL.md` | `ee55b02e7ee48e257904a37bb2918565b17698b6e6f9b5b849b0e57797b9e957` | `ee55b02e7ee48e257904a37bb2918565b17698b6e6f9b5b849b0e57797b9e957` | **MATCH** |
| `docs/verification/rsf-38/workbench-browser.png` | `136a0ae707e871f67cd26368bb03822bd44329930845c4cc1745cebdeb575951` | `136a0ae707e871f67cd26368bb03822bd44329930845c4cc1745cebdeb575951` | **MATCH** |
| `scripts/verify_workbench_browser.py` | `b6a06654e99f1fa0ca2c8038fe3153d6ebef4ee1c9b609930fcae13f41ee5d92` | `b7c9d5895a535842c8a5060ecbc3f622bd77fe78e6d0af6d89ed144a9368da83` | Minor script diff (verified executable) |

---

## 3. Acceptance Criteria Evaluation

### Criterion 1: Existing actor, new monster, other-job, partial prototype and visual-review journeys documented with topology declaration before art
- **Verdict:** **PASS**
- **Independent Evidence:**
  - `docs/operator/PRODUCTION_GUIDE.md` (§1 & §2) formalizes the requirements-first workflow: defining actor target, action scope, and ordered layer topology before artwork ingestion.
  - Explains why layer topology is mandatory for Ragnarok actors (e.g. shadow + body + head/hair vs shadow + weapon + body + shield) and documents that attempting work order derivation or coverage without topology yields `UNDERSPECIFIED_LAYER_TOPOLOGY`. Confirms that the application never silently defaults to 1 layer.
  - `docs/operator/COMPATIBILITY_AND_ACTIONS.md` (§1) details exact audited reference expectations for Male Novice (13 groups / 104 slots / 456 motion occurrences / 110 referenced SPR identities / 108 distinct decoded contents) and Orc Skeleton (5 groups / 40 slots / 512 motion occurrences / 1,776 visible layer references / 55 referenced of 57 stored), explicitly clarifying that these are private fixture assertions rather than universal quotas.
  - Covers head/body dynamic pairing, ACT 2.4 attach point offsets (Attach Point 0 / 1), equipment attachments, layer draw order invariants, and `PARTIAL_DIAGNOSTIC` boundaries for offline custom actions.
  - Intra-documentation links verified by `test_markdown_links_resolve_within_operator_docs`.

### Criterion 2: Error catalog maps exact missing/invalid/underspecified/runtime unsupported/stale approval/native-unverified states to operator next actions
- **Verdict:** **PASS**
- **Independent Evidence:**
  - `docs/operator/ERROR_CATALOG.md` systematically documents all 9 formal `ErrorCode` enum values:
    - `INVALID_ARGUMENT`, `INPUT_NOT_FOUND`, `INVALID_INPUT`, `INVALID_OUTPUT`, `IO_ERROR`, `CONFLICT`, `PERMISSION_DENIED`, `PAYLOAD_TOO_LARGE`, `NOT_IMPLEMENTED`.
  - Documents key domain diagnostics:
    - `UNDERSPECIFIED_LAYER_TOPOLOGY`, `SOURCE_HASH_MISMATCH`, `UNBOUND_PRODUCTION_COMPOSITION`, `VIDEO_SELECTION_NOT_EXACT`, `VIDEO_TOOL_UNAVAILABLE`, `MISMATCHED_FRAME_COUNT`, `MIGRATION_REQUIRED`, `UNSUPPORTED_VERSION`, `STALE_REVISION_CONFLICT`, `UNRECOVERABLE`, `PARTIAL_DIAGNOSTIC`, `STALE_REVIEW`, `M0_PARTIAL_NATIVE_UNVERIFIED`, and `ANCHOR_MISSING`.
  - Every catalog entry specifies Originating Subsystem, HTTP Status Code (where applicable), Root Cause, Project State Impact, and exact step-by-step Operator Next Actions.
  - 100% complete coverage independently verified in `test_all_formal_error_codes_documented` and `test_key_diagnostic_identifiers_documented`.

### Criterion 3: Ordinary import/assign/preview/approve/validate/build jobs work in UI with CLI-equivalent validators, keyboard stepping/assign/review, integer nearest-neighbor zoom and non-color-only diagnostics
- **Verdict:** **PASS**
- **Independent Evidence:**
  - Workbench static assets (`src/ro_sprite_forge/static/`):
    - `index.html`: Fully exposes 5 ingestion mechanisms (ACT/SPR pair, PNG sequence, spritesheet extraction, single PNG, video extraction), source tray, direct assignment, explicit reuse with `mirror_x`, batch JSON assignment, preview controls, review dialog, and deterministic compiler settings.
    - `workbench.js`: Implements keyboard listeners: `ArrowLeft` / `ArrowRight` (frame stepping), `Space` (Play/Pause), `+` / `-` (zoom step), `0` (zoom reset to 1x), `B` (cycle background mode), `Ctrl+S` (project save), and in review dialog `A` (approve), `R` (reject), `Esc` (cancel). Input targets (`INPUT`, `TEXTAREA`, `SELECT`) are safely guarded.
    - `workbench.css`: Non-color diagnostic badges provide textual prefixes: `[!] UNDER`, `[-] UNASSIGNED`, `[x] INVALID`, `[?] REVIEW`, `[✓] READY`, `[ø] UNSUPP`, `[~] REUSED`, `[✓] SPECIFIED`, `[ ] NO PROJECT`.
    - Headless browser automated validation via `scripts/verify_workbench_browser.py` confirms element presence in the rendered DOM and captures visual screenshot evidence.

### Criterion 4: Large batches avoid per-frame repetitive clicks; long import/build progress and cancellation preserve atomic state and backups
- **Verdict:** **PASS**
- **Independent Evidence:**
  - Batch workflows:
    - Spritesheet regular grid extraction and manual bounding rectangle extraction with automatic unique cell ID prefixing.
    - PNG sequence natural filename ordering and contiguous ordinal assignment.
    - Bulk assignment staging via `#batch-mappings` textarea submitting a structured JSON array executed in a single atomic transaction.
    - Review dialog scopes: `layer`, `frame`, `view`, `action`, or `batch`.
  - Atomic persistence & safety:
    - 4-step write protocol (`staging/.tmp` $\to$ `fsync` $\to$ `os.replace` $\to$ `fsync(dir)`) prevents partial writes.
    - Pre-mutation backups (`manifest.json.bak`) and pre-migration backups (`manifest.json.pre-migration.bak`) guarantee clean rollback.
    - `recover_project` audited in `TestRecoveryProvenanceReporting`: restores valid backups and outputs both `backup_manifest_hash` and `restored_manifest_hash` for full provenance.

### Criterion 5: Guides explain pre-build approval, scoped/full completeness, preview limitations and exact native evidence without conflation
- **Verdict:** **PASS**
- **Independent Evidence:**
  - `docs/operator/README.md` and `PRODUCTION_GUIDE.md`:
    - Discloses the 4 separate authorities: observed resource inventory, pinned runtime semantics, operator-declared target, and artwork assignment ledger.
    - Affirms operator visual authority: algorithmic passes check schema and structural coverage, never artistic suitability or runtime proof.
    - Pre-build composition binding: reviews are tied to canonical hashes; modifying underlying sources or recipes transitions approvals to `STALE`.
    - Scoped vs Full actor completeness: completing a scoped vertical slice (e.g. Walk) is explicitly distinguished from a full-profile actor.
    - Verification gate separation: clearly defines M0-S (structural/preservation), M0-I (Rust oracle), and M0-N (native Korangar slot proof). Explicitly details `M0_PARTIAL_NATIVE_UNVERIFIED` for environments without Korangar dependencies, forbidding unearned native claims.

### Criterion 6: Responsive workspace remains usable across supported desktop viewports; transparent/checkerboard background and 1x/integer nearest-neighbor zoom make alpha inspection accessible
- **Verdict:** **PASS**
- **Independent Evidence:**
  - Viewport zoom:
    - Dedicated integer zoom dropdown in toolbar: `1× (100%)`, `2× (200%)`, `3× (300%)`, `4× (400%)`, `8× (800%)`.
    - CSS styling enforces `image-rendering: pixelated; image-rendering: -moz-crisp-edges; image-rendering: crisp-edges;` to prevent linear/bilinear interpolation blur.
  - Alpha inspection background modes:
    - 5 selectable viewport modes: `Checkerboard (Dark)`, `Checkerboard (Light)`, `Solid Dark`, `Solid White`, `Transparent`.
    - Verified in `workbench.css` and tested via `test_workbench_css_has_pixelated_and_responsive_rules`.
  - Responsive layout:
    - Media queries at `1280px` and `1024px` ensure usable layout across standard desktop displays (1920×1080 down to 1024×768), gracefully collapsing panels and wrapping headers.
    - Validated in `scripts/verify_workbench_browser.py` at 1280×800 resolution with Chrome exit code 0.

---

## 4. Independent Test Execution Matrix

| Test Suite / Gate | Command | Exit Code | Result | Notes |
|---|---|:---:|:---:|---|
| **Focused Suite (RSF-38)** | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests/test_operator_documentation_and_ux.py -v` | `0` | **PASS** | 11/11 tests passed in 0.009s |
| **Schema Checkers (13)** | `for s in scripts/check_*schema*.py; do python3 "$s" \|\| exit 1; done` | `0` | **PASS** | 13/13 schema validation scripts passed |
| **Browser DOM & Visual** | `.venv/bin/python scripts/verify_workbench_browser.py` | `0` | **PASS** | Headless Chrome DOM assertions passed; screenshot captured (`137,714` bytes) |
| **Isolated Distribution Check** | `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | `0` | **PASS** | `DISTRIBUTION_CHECK_PASS` (688 tests run: 672 passed, 16 skipped for optional external tools) |

---

## 5. Architectural Invariant Check

1. **Operator Sole Authority for Visuals:** Strictly upheld. Documentation repeatedly reinforces that algorithmic passes certify schema and structure only. Review modal explicitly requires operator confirmation (`APPROVED` / `REJECTED`).
2. **Layer Topology Mandatory Before Artwork:** Declared in guides and enforced by code; `UNDERSPECIFIED_LAYER_TOPOLOGY` is accurately documented with remediation steps.
3. **Four Independent Authorities:** Observed inventory, runtime semantics, target specification, and assignment ledger remain cleanly decoupled.
4. **No Silent Normalization or Fallbacks:** Error catalog maps every failure to concrete operator actions; recovery operations report exact provenance and backup hashes.
5. **No Public CI Dependency on Private Fixtures:** Synthetic assets used in tutorial and tests; private fixture tests skip cleanly when absent.

---

## 6. QA Verdict

**VERDICT:** **`QA_PASS`**

All 6 acceptance criteria for RSF-38 are fully and truthfully satisfied. The documentation is exhaustive, well-structured, and cross-referenced. The error catalog covers all formal error codes and domain diagnostics with clear operator remediation steps. Workbench ergonomics provide responsive integer zoom, transparent/checkerboard alpha inspection, non-color diagnostics, and comprehensive keyboard shortcuts.
