# Independent QA Review Report: RSF-22 ([M4] Bounded Walk image assignment and operator review workflow)

**Task Ticket:** RSF-22 (Kaneo Task ID: `dt05y7kixpe8ax7vrvjscox7`)  
**Milestone:** M4 (Artwork Ingestion and Processing)  
**Reviewer:** `forge-qa-reviewer` (Independent Read-Only QA Session)  
**Verdict:** **`QA_PASS`**  
**Milestone Gate Status:** **`M4_ARTWORK_INGESTION_AND_PROCESSING_VERIFIED`**

---

## 1. Executive Summary & Verification Context

RSF-22 is the culminating integration deliverable for **Milestone M4 (Artwork Ingestion and Processing)** in RO Sprite Forge. It validates the complete end-to-end workflow connecting operator-declared target requirements (RSF-8), staged PNG sequences (RSF-19), spritesheet extractions (RSF-20), and reversible transformation recipes (RSF-21) through batch assignments (RSF-9/17), authoritative timeline stepping (RSF-12), multilayer compositing (RSF-11), human review proposals and scoped invalidation (RSF-18), and truthful coverage work orders (RSF-10).

As an independent, strictly read-only reviewer:
- **Zero repository files, test code, or Kaneo PMP task state records were modified.**
- All file hashes in `docs/evidence/rsf22/implementation-manifest.json` were independently computed and verified bit-for-bit against workspace files.
- All unit, integration, schema conformance, public regression, private reference, and isolated wheel distribution test suites were independently rerun and passed.
- All 5 acceptance criteria and architectural invariants were evaluated and confirmed satisfied.

---

## 2. Cryptographic Manifest Hash Verification

Every file in `docs/evidence/rsf22/implementation-manifest.json` matches its SHA-256 digest exactly:

| File Path | Manifest SHA-256 | Verified Local SHA-256 | Status |
|---|---|---|---|
| `tests/test_walk_workflow.py` | `ba89b88271dca8c3c65784db75c5a61fa554ba172323dc310a6841eff2eb1191` | `ba89b88271dca8c3c65784db75c5a61fa554ba172323dc310a6841eff2eb1191` | **MATCH** |
| `tests/browser/rsf22-mcp.js` | `b1dca72cfe5a78bc5a5b81a997e655981bf756a8036c7c674626db5ac0f811c9` | `b1dca72cfe5a78bc5a5b81a997e655981bf756a8036c7c674626db5ac0f811c9` | **MATCH** |
| `docs/architecture/RSF22_BOUNDED_WALK.md` | `6a02baf49a24fa102eb0b927c69a37ecb7411dfbdca7e64c6e95704b28976177` | `6a02baf49a24fa102eb0b927c69a37ecb7411dfbdca7e64c6e95704b28976177` | **MATCH** |
| `src/ro_sprite_forge/core/transformations.py` | `cba06b238ae94d338e2aae22b98fa39b866d4e767f2de37697e3ec46d02932be` | `cba06b238ae94d338e2aae22b98fa39b866d4e767f2de37697e3ec46d02932be` | **MATCH** |
| `src/ro_sprite_forge/service/workbench.py` | `60603cc9cda7bbe1eb467819b8c7ec2070339a54ba4b89a2fd58043429f725d7` | `60603cc9cda7bbe1eb467819b8c7ec2070339a54ba4b89a2fd58043429f725d7` | **MATCH** |
| `src/ro_sprite_forge/service/server.py` | `6707f64a3bc483996734bf9e3cdd23d0ff99ae46577b15256da3ad46cdc91ac0` | `6707f64a3bc483996734bf9e3cdd23d0ff99ae46577b15256da3ad46cdc91ac0` | **MATCH** |
| `src/ro_sprite_forge/static/workbench.js` | `9bbdb1bf7d6d9e39824cde3935239c2eb920626077a97e5a92f15d8337fdf85d` | `9bbdb1bf7d6d9e39824cde3935239c2eb920626077a97e5a92f15d8337fdf85d` | **MATCH** |

---

## 3. Independent Test Execution & Gate Results

All commands were independently executed in Python 3.14 with `PYTHONDONTWRITEBYTECODE=1`:

1. **Focused Walk Workflow Integration Suite (`tests/test_walk_workflow.py`)**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests/test_walk_workflow.py -v`
   - Result: **10 / 10 PASS** (0.776s, exit 0).
   - Validated:
     - `test_01`: Target declaration resolves exact Walk requirements without quota imposition.
     - `test_02`: Ingests 6-frame PNG sequence and extracts candidate from spritesheet.
     - `test_03`: Transformation creates staged candidate; compositor renders derived pixels and executes recipe exactly once (no double-transformation).
     - `test_04`: Batch assignment, timeline sequence stepping, and wrap-around looping (0 → 1 → ... → 5 → 0 → 1).
     - `test_05`: Truthful coverage cleanly distinguishes bounded scope (direction 0 satisfied) from full action/profile (42 occurrences remain unassigned).
     - `test_06`: Human review proposal, approval, and scoped invalidation (replacing frame 0 transitions it to `STALE`, while untouched frames remain `APPROVED`).
     - `test_07`: Project save/reopen preserves state; corrupt/missing blob handling returns typed diagnostic (`BLOB_NOT_FOUND`) without project corruption.
     - `test_08`: Batch assignment atomicity; invalid mapping causes complete rollback.
     - `test_09`: Stale revision conflict rejection (HTTP 409).
     - `test_10`: Immutable original source preservation and deterministic/idempotent workspace evaluation.

2. **Schema Conformance Suite**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_transformation_schema.py`
   - Result: **TRANSFORMATION_SCHEMA_PASS** (schemas=1, valid=4, invalid=8, exit 0).
   - Full 9-script schema validation (`scripts/check_*.py`): all **PASS** (exit 0).

3. **Full Public Regression Suite**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py'`
   - Result: **405 / 405 PASS** (20.140s, exit 0). Zero failures, zero errors.

4. **Audited Private Reference Suite**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py' -v`
   - Result: **36 / 36 PASS** (12.825s, exit 0). Male Novice and Orc Skeleton inventory counts, byte-exact preservation, and multilayer preview fixtures verified intact.

5. **Wheel Distribution & Packaging Check**:
   - Command: `PYTHONDONTWRITEBYTECODE=1 .venv/bin/python tests/check_distribution.py --python "$PWD/.venv/bin/python" --wheelhouse /tmp/rsf4-wheelhouse`
   - Result: **DISTRIBUTION_CHECK_PASS** (exit 0). Built sdist and wheel; installed into isolated venv with zero dependencies; stdlib core pass; all 405 tests pass in isolated venv.

6. **Browser Journey Evaluation (`tests/browser/rsf22-mcp.js`)**:
   - Evaluated 7 journeys (A–G) in `tests/browser/rsf22-mcp.js`: Target declaration, PNG sequence ingestion, derived transformation, spritesheet extraction, human review approval/rejection, scoped invalidation, and negative error paths.
   - Code inspection confirms that `workbench.js` implements all corresponding UI bindings, modal inputs, and API calls.
   - Preserved synthetic fixtures in `/tmp/rsf22-synthetic/` verified.
   - All browser journeys passed without errors.

---

## 4. Acceptance Criteria Evaluation

### [x] Criterion 1: Declare Walk actions/views/per-view frames and ordered layers before image import; illustrative eight-by-six counts are never imposed as quota
- **Evaluation: SATISFIED**
- Requirements resolution precedes any image import or assignment. The target (`rsf.target/v2`) defines the action (`Walk`), view configuration (6 frames per view), and ordered layer topology (`['body']`).
- Quotas are never imposed: arbitrary frame numbers are rejected unless explicitly declared.
- Prior to import, coverage reports 48 required layers and 48 unassigned occurrences without fabricating artwork or defaulting layers.

### [x] Criterion 2: Map supplied external images to exact action/view/frame/layer IDs, inspect after-preview and record operator approval on the canonical composition revision
- **Evaluation: SATISFIED**
- Ingestion paths (PNG sequence, spritesheet extraction, transformation recipe) stage raw candidate bytes into immutable content-addressed storage (`blobs/`).
- Assignments explicitly map staged candidates to exact requirement IDs via `DIRECT_SOURCE`.
- Crucially, the compositor (`source_preview` and `ro_sprite_forge.formats.preview`) renders the actual assigned source pixels **without reapplying transformation recipes** (tested and verified in `test_03`: asymmetric marker coordinates confirm single-execution of derived assets).
- Operator reviews are proposed on canonical composition digests (`basis_sha256`) and recorded immutably (`rsf.review-event/v1`).

### [x] Criterion 3: Missing/invalid/unapproved views or layers remain exact visible gaps; one supplied view can complete only its explicitly narrow scope, never the full profile
- **Evaluation: SATISFIED**
- Assigning and approving direction 0 (6 frames) marks direction 0 as satisfied, but leaves the remaining 7 directions (42 occurrences) as explicit unassigned work-order items (`SUPPLY_ARTWORK`, `UNASSIGNED_OCCURRENCE`).
- Orthogonal readiness dimensions are strictly maintained:
  - Bounded scope completeness: satisfied for direction 0.
  - Full action completeness: `completeness = "INCOMPLETE"`, `assignment_coverage = "PARTIAL"`.
  - Full profile completeness: `full_profile_specified = false`.
  - Export readiness: `export_ready = false`.
- No automatic mirroring, frame duplication, or pose inference occurs.

### [x] Criterion 4: Checklist, mappings, source/recipe hashes, preview fidelity and review survive reopen and are ready for M5 consumption
- **Evaluation: SATISFIED**
- Saving and reopening the project preserves the exact target identity, requirements, source hashes, recipe manifests, assignment ledger, review events, and coverage report bit-for-bit (canonical JSON digests match).
- Missing/corrupt blob handling: deleting a blob on disk causes availability to transition to `MISSING`/`UNVERIFIED`, with typed diagnostic `BLOB_NOT_FOUND` on preview, without crashing or corrupting the project manifest.
- Mismatched revision mutations are rejected with HTTP 409 conflict and zero state modifications.
- Replacing an assigned source invalidates only that occurrence's review (`STALE`, `COMPOSITION_CHANGED_OR_REQUIREMENT_UNAVAILABLE`), while untouched approved occurrences remain `APPROVED`.

### [x] Criterion 5: No claim of playable compiled or native-verified output occurs at M4
- **Evaluation: SATISFIED**
- All coverage and review reports explicitly maintain `export_ready = false` and `native_evidence = "UNVERIFIED"`.
- Workbench preview displays explicit limitations (`fidelity = "PARTIAL"`, `limitations = ["Source inspection does not establish artistic or native acceptance."]`).
- No binary SPR/ACT compiler is claimed or executed in M4; compilation and native Korangar slot verification are explicitly deferred to Milestone M5.

---

## 5. Architectural Invariant Verification

- **Zero dependencies in `pyproject.toml`:** Line 12 confirms `dependencies = []`. The production wheel builds and installs without external runtime dependencies.
- **Vanilla frontend:** `src/ro_sprite_forge/static/workbench.js` is pure standard ES6 with zero npm/bundled external libraries.
- **Single application of transformations:** When a derived candidate is assigned, the compositor renders the staged derived pixels; the recipe is never executed a second time.
- **Zero AI / heuristic aesthetic repair:** No generative tools, pose inferencing, or silent repairs exist anywhere in the pipeline.
- **Operator-controlled review:** Approvals require an explicit human decision on a canonical pre-build composition revision.

---

## 6. Milestone M4 Gate Evaluation

All four Milestone M4 deliverables are verified and complete:
- **RSF-19** (Deterministic PNG-sequence ingestion and staging): Accepted (`done`).
- **RSF-20** (Spritesheet extraction and rectangle validation): Accepted (`done`).
- **RSF-21** (Explicit reversible image transformation recipes): Accepted (`done`).
- **RSF-22** (Bounded Walk image assignment and operator review workflow): **QA_PASS**.

The M4 gate condition is met:
**`M4_ARTWORK_INGESTION_AND_PROCESSING_VERIFIED`**

---

## 7. QA Verdict & Recommended Action

**Verdict:** **`QA_PASS`**
