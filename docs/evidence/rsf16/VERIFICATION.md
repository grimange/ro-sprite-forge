# RSF-16 Verification & Evidence Packet: Requirements-First Operator Workbench & Readiness Reports

**Milestone:** M3 (Animation Inspection & Operator Workbench)  
**Task:** `RSF-16` / `[M3] Requirements-first operator workspace and readiness reports`  
**Worker / Role:** Primary Implementer (Senior Full-Stack & Systems Integration Engineer)  
**Verification Target:** Loopback HTTP API, Workbench SPA, Core Contracts Integration  

---

## 1. Acceptance Criteria Evaluation

| # | Acceptance Criterion | Verification Method & Implementation Evidence | Verdict |
|---|---|---|:---:|
| 1 | **Create/open project, select/define target/profile and explicitly declare/inherit topology before artwork; show underspecified declarations as blockers.** | • Project switcher and creation dialog support choosing project slug, display name, actor template (`player`, `monster`, `npc`, `unverified`), and pinned runtime profile.<br>• "Define Target & Topology" modal allows declaring ordered layer names (e.g., `torso, cloak` or `body`).<br>• Incomplete or missing topology emits `UNDERSPECIFIED_LAYER_TOPOLOGY`, displaying a blocker banner and disabling fake green completion.<br>• Verified by `tests/test_workbench.py::test_requirements_endpoint_without_target` and `test_requirements_endpoint_with_explicit_topology`. | **PASS** |
| 2 | **Tree groups action/view/frame/layer and filters unassigned, invalid, unreviewed, unsupported, reused, ready and underspecified; exact IDs and topology provenance are visible.** | • Hierarchical tree organizes occurrences by `Action` → `View (Slot)` → `Frame` → `Layer`.<br>• Full filtering support across 8 orthogonal categories (`ALL`, `UNDERSPECIFIED`, `UNASSIGNED`, `INVALID`, `UNREVIEWED`, `UNSUPPORTED`, `REUSED`, `READY`).<br>• Leaf node selection displays exact canonical requirement ID (e.g. `walk-proj/r1/body/action/Walk/slot8/view0/frame0/layer0`) and declaration provenance (explicit layers or hash-pinned observation).<br>• Verified by `tests/test_workbench.py::test_static_files_serving` and `test_requirements_endpoint_with_explicit_topology`. | **PASS** |
| 3 | **Show separate slot/motion/layer/identity/content counters and scoped/full, structure, visual, preview and native states.** | • Bottom counters bar displays separate structural counters (required slots, underspecified slots, frames, layers) and assignment counters (unassigned occurrences, unique selected sources, distinct content hashes).<br>• Displays independent orthogonal dimensions: Completeness (`COMPLETE_FOR_DECLARED_SCOPE`), Structural Specification (`COMPLETE_FOR_DECLARED_SCOPE` / `UNDERSPECIFIED`), Assignment Coverage (`UNASSIGNED` / `PARTIAL` / `COMPLETE`), Technical Validation (`NOT_RUN` / `VALID`), Visual Operator Review (`INCOMPLETE` / `COMPLETE`), Preview Fidelity (`UNVERIFIED`), Native Evidence (`UNVERIFIED`).<br>• Verified by `tests/test_workbench.py::test_coverage_and_work_order_with_unassigned_layers`. | **PASS** |
| 4 | **Export missing checklist/reports and readable validation errors from shared core API; missing source or mapping cannot produce fake green completion.** | • `GET /api/projects/{id}/work-order` exports missing-artwork work order in human-readable plain text or structured JSON format.<br>• Shared core API validates target, topology, and assignments, returning readable error envelopes with exact JSON pointers and error codes.<br>• Missing sources or unmapped actions are recorded as unresolved items; overall status remains strictly `INCOMPLETE` or `UNASSIGNED`.<br>• Verified by `tests/test_workbench.py::test_coverage_and_work_order_with_unassigned_layers` and `test_work_order_without_target_fails_cleanly`. | **PASS** |
| 5 | **Keyboard-accessible controls and non-color-only error states work without a dashboard maze or ordinary JSON editing.** | • Full keyboard navigation: tree nodes have `tabindex="0"`, `role="treeitem"`, `aria-level`, and support `ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight`, `Enter`, and `Space`.<br>• Focus visible rings (`*:focus-visible`) throughout all interactive elements.<br>• Non-color-only status badges utilize unique iconography, borders, and text: `[!] UNDERSPECIFIED`, `[-] UNASSIGNED`, `[x] INVALID`, `[?] UNREVIEWED`, `[ø] UNSUPPORTED`, `[~] REUSED`, `[✓] READY`.<br>• Verified by `tests/test_workbench.py::test_static_files_serving`. | **PASS** |

---

## 2. Targeted RSF-15 Integration Corrections

1. **Concurrent-Save Race Condition:**
   - Serialized `save_project` per project directory using `_get_project_lock(str(project_dir))`.
   - Competing concurrent saves with the same `expected_revision` cleanly result in one HTTP 200 success and one HTTP 409 Conflict without lost updates.
   - Tested and verified in `tests/test_workbench.py::test_rsf15_correction_concurrent_save_conflict`.

2. **Upload Limit Reconciliation:**
   - Increased `MAX_REQUEST_BODY_SIZE` from 16 MiB to 48 MiB in `server.py`.
   - Allows full 32 MiB raw binary or base64 JSON (~42.7 MiB) uploads without truncation, while strictly maintaining `MAX_BLOB_SIZE = 32 MiB` on storage.
   - Tested and verified in `tests/test_workbench.py::test_rsf15_correction_upload_limit_reconciliation`.

---

## 3. Test Execution Summary

| Test Suite | Command | Tests | Status | Evidence Log |
|---|---|:---:|:---:|---|
| **Workbench & Concurrency Suite** | `.venv/bin/python -m unittest tests/test_workbench.py` | 9 | **PASS** (0 failures, 0 errors) | `docs/evidence/rsf16/workbench-tests.log` |
| **Full Public Test Suite** | `.venv/bin/python -m unittest discover -s tests -p "test_*.py"` | 286 | **PASS** (0 failures, 0 errors) | `docs/evidence/rsf16/public-tests.log` |
| **Audited Private Fixtures Suite** | `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p "test_*.py"` | 36 | **PASS** (0 failures, 0 errors) | `docs/evidence/rsf16/private-tests.log` |
| **Isolated Package & Wheel Build** | `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14` | 286 | **PASS** (`DISTRIBUTION_CHECK_PASS`) | `docs/evidence/rsf16/distribution.log` |

---

## 4. File Manifest and SHA-256 Hashes

| Path | Bytes | SHA-256 |
|---|:---:|---|
| `src/ro_sprite_forge/core/project.py` | 16,461 | `89e3f4de48569e90a3c27f56b01bd4c6449a9981d4e6191b93f02dae16364847` |
| `src/ro_sprite_forge/service/server.py` | 27,150 | `7bb9ae94bff48f88f59c22b44f55d357d602f0f7c7f3b2024f0b29f2735c0221` |
| `src/ro_sprite_forge/static/workbench.css` | 12,791 | `5ff5cd74e353e14202106179065300ce4c026cea28007dba628fddf8bd4a0d15` |
| `src/ro_sprite_forge/static/workbench.js` | 31,035 | `73c35668a42845bdc8774365b1cea3c9669bcce0b8317240a017eac2fa428fca` |
| `src/ro_sprite_forge/static/index.html` | 15,083 | `61d86ee34bed8681274144d07811ca6ed1df87ab83d78d9ddabc5d28f1d61532` |
| `pyproject.toml` | 768 | `e517ab56281e72d79985d7a12868a07e206243667909d1873a25c2951b33ca6b` |
| `MANIFEST.in` | 215 | `6835e14456b0c9a0b2c71d88db007e59f6109ab2a4cf9c8490cdab69f37d15a1` |
| `tests/test_workbench.py` | 12,872 | `683453ccd4f727cacb5338067cf3ab9c835add07bd071b54ce5e063b321d7344` |
| `docs/architecture/RSF16_WORKBENCH.md` | 7,636 | `7aa226b39419d4780175d7c27c65c66183943a5b1830c67cc596ce9d7828e20a` |
