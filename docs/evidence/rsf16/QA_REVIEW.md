# Independent QA Review Report: RSF-16

- **Task Ticket:** RSF-16 (ID: `ufpaifaxq9q2fa55w0ixs9iq`)
- **Task Title:** `[M3] Requirements-first operator workspace and readiness reports`
- **Milestone:** M3 (Animation Inspection & Operator Workbench)
- **Reviewer:** Independent Read-Only QA Reviewer
- **Implementation Manifest:** `docs/evidence/rsf16/implementation-manifest.json`
- **Architecture Specification:** `docs/architecture/RSF16_WORKBENCH.md`
- **Verification Evidence:** `docs/evidence/rsf16/VERIFICATION.md`
- **Formal Verdict:** **`QA_PASS`**

---

## 1. Acceptance Criteria & Architectural Review

| # | Acceptance Criterion | Evaluation & Findings | Status |
|---|---|---|:---:|
| 1 | **Create/open project, select/define target/profile and explicitly declare/inherit topology before artwork; show underspecified declarations as blockers.** | • Project management UI supports creating and opening projects with slug, display name, standard actor templates (`player`, `monster`, `npc`, `unverified`), and pinned runtime profiles.<br>• Target modal supports explicit topology declaration (e.g. `torso, cloak` or `body`).<br>• Projects without active targets or with missing topology are flagged with `[!] UNDERSPECIFIED` badges and display persistent blocker alert banners (`UNDERSPECIFIED_LAYER_TOPOLOGY` or `TARGET NOT DECLARED`). Silent defaulting to 1 layer is strictly prevented.<br>• Verified via `tests/test_workbench.py::test_requirements_endpoint_without_target` and `test_requirements_endpoint_with_explicit_topology`. | **PASS** |
| 2 | **Tree groups action/view/frame/layer and filters unassigned, invalid, unreviewed, unsupported, reused, ready and underspecified; exact IDs and topology provenance are visible.** | • Requirements tree arranges occurrences in strict 4-level hierarchy: `Action` → `View (Slot)` → `Frame` → `Layer`.<br>• Fully supports 8 orthogonal filter categories: `ALL`, `UNDERSPECIFIED`, `UNASSIGNED`, `INVALID`, `UNREVIEWED`, `UNSUPPORTED`, `REUSED`, `READY`.<br>• Leaf layer selection displays canonical requirement ID (e.g. `walk-proj/r1/body/action/Walk/slot8/view0/frame0/layer0`) and declaration provenance (explicit layers vs hash-pinned inventory observation).<br>• Verified via `test_requirements_endpoint_with_explicit_topology` and static DOM checks. | **PASS** |
| 3 | **Show separate slot/motion/layer/identity/content counters and scoped/full, structure, visual, preview and native states.** | • Bottom counters bar displays separate structural counters (required slots, underspecified slots, frames, layers) and assignment counters (unassigned occurrences, unique selected sources, distinct content hashes).<br>• Global status indicators surface independent orthogonal dimensions: Completeness (`COMPLETE_FOR_DECLARED_SCOPE`), Specification (`COMPLETE_FOR_DECLARED_SCOPE` / `UNDERSPECIFIED`), Coverage (`UNASSIGNED` / `PARTIAL` / `COMPLETE`), Technical Validation (`NOT_RUN` / `VALID`), Operator Review (`INCOMPLETE` / `COMPLETE`), Preview Fidelity (`UNVERIFIED`), Native Evidence (`UNVERIFIED`).<br>• Verified via `tests/test_workbench.py::test_coverage_and_work_order_with_unassigned_layers`. | **PASS** |
| 4 | **Export missing checklist/reports and readable validation errors from shared core API; missing source or mapping cannot produce fake green completion.** | • `GET /api/projects/{id}/work-order` supports exporting missing-art work orders in plain text (`format=text`) or structured JSON (`format=json`).<br>• Missing sources/unmapped occurrences cleanly generate actionable work order items; overall coverage remains strictly `UNASSIGNED` or `PARTIAL`, never fake green completion.<br>• Requesting work order on an unconfigured target cleanly raises HTTP 422 `INVALID_INPUT`.<br>• Verified via `tests/test_workbench.py::test_coverage_and_work_order_with_unassigned_layers` and `test_work_order_without_target_fails_cleanly`. | **PASS** |
| 5 | **Keyboard-accessible controls and non-color-only error states work without a dashboard maze or ordinary JSON editing.** | • Full keyboard navigation: tree nodes have `tabindex="0"`, `role="treeitem"`, `aria-level`, and support `ArrowUp`, `ArrowDown`, `ArrowLeft`, `ArrowRight`, `Enter`, and `Space`.<br>• Global `*:focus-visible` ring provides clear 2px outline for keyboard users.<br>• Non-color-only badges feature distinct prefix icons, borders, and labels (`[!] UNDERSPECIFIED`, `[-] UNASSIGNED`, `[x] INVALID`, `[?] UNREVIEWED`, `[ø] UNSUPPORTED`, `[~] REUSED`, `[✓] READY`).<br>• Pure human workbench layout avoids dashboard clutter and requires no direct JSON editing. | **PASS** |
| 6 | **Targeted RSF-15 Integration Corrections:**<br>1. *Concurrent-Save Race Condition*<br>2. *Upload Limit Reconciliation* | 1. `_get_project_lock(str(project_dir))` serializes `save_project` per project directory. Competing saves with same `expected_revision` cleanly result in exactly one HTTP 200 success and one HTTP 409 Conflict without lost updates.<br>2. `MAX_REQUEST_BODY_SIZE` reconciled to 48 MiB in `server.py`, allowing 32 MiB raw binary or base64 JSON uploads (~42.7 MiB) while maintaining `MAX_BLOB_SIZE = 32 MiB` inside project storage.<br>• Verified via `tests/test_workbench.py::test_rsf15_correction_concurrent_save_conflict` and `test_rsf15_correction_upload_limit_reconciliation`. | **PASS** |
| 7 | **Zero Third-Party Core Runtime Dependencies** | • `pyproject.toml` defines `dependencies = []`. Core and service modules execute exclusively on the Python 3.12+ standard library.<br>• Frontend static assets use vanilla HTML5, CSS3, and standard ES6 (`fetch`, DOM APIs). Zero third-party frontend dependencies. | **PASS** |

---

## 2. Independent Verification & Test Execution Results

All test suites were independently executed with `PYTHONDONTWRITEBYTECODE=1`:

1. **Workbench Integration Suite:**
   ```bash
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests/test_workbench.py
   ```
   - **Result:** Ran 9 tests in 4.620s. **OK** (0 failures, 0 errors).

2. **Full Public Test Suite:**
   ```bash
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p "test_*.py"
   ```
   - **Result:** Ran 286 tests in 9.230s. **OK** (0 failures, 0 errors).

3. **Audited Private Fixtures Suite:**
   ```bash
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p "test_*.py"
   ```
   - **Result:** Ran 36 tests in 12.500s. **OK** (0 failures, 0 errors).

4. **Isolated Package & Wheel Distribution Check:**
   ```bash
   PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf4-wheelhouse --python /usr/bin/python3.14
   ```
   - **Result:** Ran 286 tests in 8.894s inside clean isolated environment. **OK** (exit code 0, `DISTRIBUTION_CHECK_PASS`).

---

## 3. SHA-256 Digest Verification

All files were checked against `docs/evidence/rsf16/implementation-manifest.json` and matched exactly:

| File Path | SHA-256 Digest | Status |
|---|---|:---:|
| `src/ro_sprite_forge/core/project.py` | `89e3f4de48569e90a3c27f56b01bd4c6449a9981d4e6191b93f02dae16364847` | Verified |
| `src/ro_sprite_forge/service/server.py` | `7bb9ae94bff48f88f59c22b44f55d357d602f0f7c7f3b2024f0b29f2735c0221` | Verified |
| `src/ro_sprite_forge/static/workbench.css` | `5ff5cd74e353e14202106179065300ce4c026cea28007dba628fddf8bd4a0d15` | Verified |
| `src/ro_sprite_forge/static/workbench.js` | `73c35668a42845bdc8774365b1cea3c9669bcce0b8317240a017eac2fa428fca` | Verified |
| `src/ro_sprite_forge/static/index.html` | `61d86ee34bed8681274144d07811ca6ed1df87ab83d78d9ddabc5d28f1d61532` | Verified |
| `pyproject.toml` | `e517ab56281e72d79985d7a12868a07e206243667909d1873a25c2951b33ca6b` | Verified |
| `MANIFEST.in` | `6835e14456b0c9a0b2c71d88db007e59f6109ab2a4cf9c8490cdab69f37d15a1` | Verified |
| `tests/test_workbench.py` | `683453ccd4f727cacb5338067cf3ab9c835add07bd071b54ce5e063b321d7344` | Verified |
| `docs/architecture/RSF16_WORKBENCH.md` | `7aa226b39419d4780175d7c27c65c66183943a5b1830c67cc596ce9d7828e20a` | Verified |

---

## 4. Conclusion & Recommendation

The implementation of RSF-16 strictly satisfies all acceptance criteria, maintains architectural invariants (topology declared before artwork, separate orthogonal counters and statuses, non-color-only accessibility, zero third-party core runtime dependencies), resolves the two integration defects from RSF-15, and passes all public, private, and isolated wheel distribution tests.

**Recommendation:** Proceed with Kaneo PMP task transition to `Accepted`.
