# RSF-22 Verification Evidence Packet

## Task Summary
- **Ticket**: `RSF-22` (ID: `dt05y7kixpe8ax7vrvjscox7`)
- **Title**: [M4] Bounded Walk image assignment and operator review workflow
- **Milestone**: M4 (Staging and Preview vertical slice)
- **Primary Implementer**: AGY (Codex Senior Animation Pipeline / Production Workflow Architect)
- **Independent Reviewer**: `forge-qa-reviewer`

---

## Acceptance Criteria Checklist & Evidence Mapping

### Criterion 1: Declare Walk actions/views/per-view frames and ordered layers before image import; illustrative eight-by-six counts are never imposed as quota
- **Evidence**:
  - `make_bounded_walk_target()` and RSF-8 topology resolver (`ro_sprite_forge.core.topology`): The target explicitly declares the action (`Walk`), view configurations (e.g. 6 frames per view), and ordered layer topology (`['body']`).
  - Illustrative quotas are never imposed: arbitrary frame numbers are rejected unless explicitly declared in target contract.
  - Prior to artwork import or assignment, coverage accurately reports 48 missing occurrences without inventing placeholders or default layers.
  - Verification: `tests/test_walk_workflow.py` (`test_01_target_declaration_resolves_exact_walk_requirements_without_quota_imposition`), browser test `tests/browser/rsf22-mcp.js` (Journey A).

### Criterion 2: Map supplied external images to exact action/view/frame/layer IDs, inspect after-preview and record operator approval on the canonical composition revision
- **Evidence**:
  - Ingestion via RSF-19 (ordered PNG sequences) and RSF-20 (spritesheet extraction) stages raw candidate bytes into immutable content-addressed storage (`blobs/`).
  - Transformation recipes via RSF-21 stage derived candidates (`blobs/{derived_sha256}`) with complete loss disclosure and recipe provenance.
  - Assignments in `manifest['ledger']['assignments']` explicitly map staged candidates to exact action/view/frame/layer IDs via `DIRECT_SOURCE`.
  - The compositor (`ro_sprite_forge.service.workbench:source_preview` and `ro_sprite_forge.formats.preview`) renders the actual assigned source pixels without reapplying the recipe.
  - Review proposals bind exact layer occurrences, canonical composition basis (`basis_sha256`), and preview evidence (`evidence_sha256`).
  - Explicit approval records an immutable `rsf.review-event/v1` in `manifest['review_events']`.
  - Verification: `tests/test_walk_workflow.py` (`test_02_ingest_png_sequence_and_spritesheet_candidate`, `test_03_derived_image_transformation_and_single_application_in_compositor`, `test_04_batch_assignment_timeline_inspection_and_looping_behavior`, `test_06_human_review_proposal_approval_and_scoped_invalidation`), browser test `tests/browser/rsf22-mcp.js` (Journeys A, B, C, D).

### Criterion 3: Missing/invalid/unapproved views or layers remain exact visible gaps; one supplied view can complete only its explicitly narrow scope, never the full profile
- **Evidence**:
  - `ro_sprite_forge.core.coverage`: Assigning and approving direction 0 (6 frames) marks direction 0 as satisfied, but leaves the remaining 7 directions (42 occurrences) as explicit unassigned work-order items (`SUPPLY_ARTWORK`, `UNASSIGNED_OCCURRENCE`).
  - Status dimensions are strictly orthogonal:
    - Bounded scope completeness: satisfied for direction 0.
    - Full action completeness: `completeness = "INCOMPLETE"`, `assignment_coverage = "PARTIAL"`.
    - Full profile completeness: `full_profile_specified = false`.
    - Export readiness: `export_ready = false`.
  - No automatic mirroring, frame duplication, or pose inference occurs.
  - Verification: `tests/test_walk_workflow.py` (`test_05_truthful_scoped_coverage_distinguishes_bounded_complete_from_full_profile`), browser test `tests/browser/rsf22-mcp.js` (Journey F).

### Criterion 4: Checklist, mappings, source/recipe hashes, preview fidelity and review survive reopen and are ready for M5 consumption
- **Evidence**:
  - Project round-trip: saving, reopening, reloading workbench, or restarting the service preserves the exact target identity, requirements, source hashes, recipe manifests, assignment ledger, review events, and coverage report.
  - Re-evaluating coverage and ledger on reopened projects produces bit-for-bit identical canonical JSON digests.
  - Corrupt or missing blob handling: if a blob is missing on disk, the project remains accessible; the missing source is reported with typed diagnostic (`BLOB_NOT_FOUND`) without silent substitution or project file corruption.
  - Stale revision conflict protection: mutations with mismatched `expected_revision` are rejected with HTTP 409 conflict and zero state changes.
  - Scoped invalidation: replacing an assigned source invalidates only the affected layer's review (`STALE`), while unaffected reviews remain `APPROVED`.
  - Verification: `tests/test_walk_workflow.py` (`test_06_human_review_proposal_approval_and_scoped_invalidation`, `test_07_save_reopen_and_corrupt_blob_resilience`, `test_08_batch_assignment_atomicity_and_invalid_mapping_rejection`, `test_09_stale_project_revision_conflict_rejection`, `test_10_immutable_original_source_preservation_and_deterministic_evaluation`), browser test `tests/browser/rsf22-mcp.js` (Journeys E, G).

### Criterion 5: No claim of playable compiled or native-verified output occurs at M4
- **Evidence**:
  - All coverage and review reports explicitly maintain `export_ready = false` and `native_evidence = "UNVERIFIED"`.
  - Workbench preview displays explicit limitations (`fidelity = "PARTIAL"`, `limitations = ["Source inspection does not establish artistic or native acceptance."]`).
  - No binary SPR/ACT compiler is claimed or executed in M4; compilation and native Korangar slot verification are explicitly deferred to Milestone M5.

---

## Test Execution Results & Preserved Logs

1. **Unit & Integration Suite (`tests/test_walk_workflow.py`)**:
   - Command: `.venv/bin/python -m unittest tests/test_walk_workflow.py -v`
   - Log: `docs/evidence/rsf22/walk-workflow-tests.log`
   - Result: 10 / 10 tests passed (OK).

2. **Full Public Regression Suite**:
   - Command: `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
   - Log: `docs/evidence/rsf22/public-tests.log`
   - Result: 405 / 405 tests passed in 22.215s (OK).

3. **Audited Private Reference Suite**:
   - Command: `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py' -v`
   - Log: `docs/evidence/rsf22/private-tests.log`
   - Result: 36 / 36 tests passed (OK).

4. **Schema Conformance Suite**:
   - Commands: `scripts/check_*.py`
   - Log: `docs/evidence/rsf22/schema-tests.log`
   - Result: All schema validators passed across all 9 schema scripts.

5. **Isolated Wheel Distribution Suite**:
   - Command: `.venv/bin/python tests/check_distribution.py --python "$PWD/.venv/bin/python" --wheelhouse /tmp/rsf4-wheelhouse`
   - Log: `docs/evidence/rsf22/distribution.log`
   - Result: Wheel built without dependencies; installed into isolated virtual environment; 405 tests passed (OK). `DISTRIBUTION_CHECK_PASS`.

6. **End-to-End Browser Journeys (Playwright & Google Chrome)**:
   - Script: `tests/browser/rsf22-mcp.js`
   - Journeys verified:
     - Journey A: Bounded Walk target creation (6 frames, body layer) and 6-frame PNG sequence ingestion.
     - Journey B: Derived artwork via RSF-21 transformation recipe (flip), verified rendered without double transformation.
     - Journey C: Spritesheet extraction integration (grid extraction of cells).
     - Journey D: Human-review mechanics (Approve and Reject decisions).
     - Journey E: Scoped approval invalidation (replaced frame 0 transitions to STALE, frames 1..2 remain APPROVED).
     - Journey F: Partial scope & truthful gap reporting (6 assigned, 42 unassigned, export_ready=false).
     - Journey G: Negative integration error handling (unassigned review rejected, stale revision conflict rejected, project save/reopen verified).
   - Result: `ALL RSF-22 BROWSER JOURNEYS COMPLETED SUCCESSFULLY`.

---

## Milestone M4 Gate Evaluation

With the completion of RSF-22:
- **RSF-19** (Deterministic PNG sequence ingestion): Accepted (`done`).
- **RSF-20** (Spritesheet extraction & rectangle validation): Accepted (`done`).
- **RSF-21** (Explicit reversible image transformations): Accepted (`done`).
- **RSF-22** (Bounded Walk artwork assignment & review workflow): Verified & ready for QA review.

All four M4 deliverables are verified and integrated through one complete, end-to-end human-operated workflow.

Milestone gate status:
`M4_ARTWORK_INGESTION_AND_PROCESSING_VERIFIED`
