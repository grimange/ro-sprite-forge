# Independent QA Audit Report: RSF-33
**Task:** [M7] Equipment and attachment compatibility validation  
**Ticket ID:** RSF-33 (ohmigbqn0escc46dkopt2h0c)  
**Milestone:** M7 — Additional Profiles and Compatibility  
**Reviewer:** forge-qa-reviewer (Independent QA Subagent)  
**Implementer:** AGY (ICJQmirJliEFAZN3jBl3ZitHCandT0FG)  
**Date:** 2026-10-31  
**Verdict:** QA_PASS  

---

## 1. Executive Summary & Verdict

Independent QA inspection and testing of task **RSF-33** has concluded with a verdict of **QA_PASS**.

The implementation establishes a robust, data-driven attachment compatibility validation engine for RO Sprite Forge, adhering strictly to frozen Korangar / classic Ragnarok client mechanics:
- Supported conventional attachment pairs (`player_head_anchor_delta`, `head_accessory_anchor_delta`, `body_shield_relative`, `standalone_unattached`) correctly retain parent/child resource and anchor identities.
- Structural incompatibilities (e.g. gameplay job mismatches, missing weapon action families, companion attachment attempts, monster host attempts) emit structured diagnostics (`GAMEPLAY_JOB_MISMATCH`, `INCOMPATIBLE_ACTION_FAMILY`, `INCOMPATIBLE_RESOURCE_KIND`, `MISSING_ATTACHMENT_ACTION`) rather than silent fallback, modulo truncation, or filename substitution.
- Frame counts are inspected per numeric slot: the audited Dragon Knight Male Shield Pickup disparity (slots 24..31, 2 frames vs parent 3 frames) correctly emits 8 `MISMATCHED_FRAME_COUNT` diagnostics and yields overall status `PARTIAL`.
- Jack Head Male Accessory (`jack-head-male-v1`) is enrolled into `get_default_registry()` with audited ACT 2.4 and SPR 2.1 hashes and capability dimensions.
- Multi-layer composition arranges parts according to declared layer order without layer flattening or metadata corruption.
- Coordinate transformations use pure integer arithmetic without arbitrary rounding or guessing.
- Scoped review invalidation (RSF-18) preserves body review approval when an attached child recipe changes.
- Isolated distribution build and test (`tests/check_distribution.py`) executed cleanly with bit-exact wheel reproducibility and zero test failures.

---

## 2. Implementation & Evidence Manifest Verification

### 2.1 Implementation Manifest (`docs/verification/rsf-33/implementation-manifest.json`)
All 7 files were verified against their recorded SHA-256 hashes:

| File Path | Recorded SHA-256 | Actual SHA-256 | Hash Match |
|---|---|---|---|
| `src/ro_sprite_forge/core/attachments.py` | `5858747e2a599399d8c95529007e92dd6e8acb850ef16cbc93d81880f67e1a9b` | `5858747e2a599399d8c95529007e92dd6e8acb850ef16cbc93d81880f67e1a9b` | **MATCH** |
| `src/ro_sprite_forge/core/registry.py` | `b6509b1547f2a377f03b0387546743ec170feb47c3778c118f4d310d58a632d0` | `b6509b1547f2a377f03b0387546743ec170feb47c3778c118f4d310d58a632d0` | **MATCH** |
| `src/ro_sprite_forge/schemas/compatibility-registry-v1.json` | `19b0b23e2b749a23cb4ad18dca1ad1fe117767452faa6af7b52126236ddb6ef8` | `19b0b23e2b749a23cb4ad18dca1ad1fe117767452faa6af7b52126236ddb6ef8` | **MATCH** |
| `scripts/check_registry_schema.py` | `a5849bca48eb429f30c5723878cc1b5c8eac512f9d4575a4e002f85f442d2c6b` | `a5849bca48eb429f30c5723878cc1b5c8eac512f9d4575a4e002f85f442d2c6b` | **MATCH** |
| `tests/test_attachment_compatibility.py` | `a2ef1f6253029cf81151efbd1c575f9da437e29561ccfd579bb11e8b0bcc68ff` | `a2ef1f6253029cf81151efbd1c575f9da437e29561ccfd579bb11e8b0bcc68ff` | **MATCH** |
| `tests/private_fixture_hooks/test_attachment_fixtures.py` | `f8f7fee20a1736cdcbefef3b02ee6675dce616b3ef1e2c6a3066dd4538e4276a` | `f8f7fee20a1736cdcbefef3b02ee6675dce616b3ef1e2c6a3066dd4538e4276a` | **MATCH** |
| `tests/test_video.py` | `6a70eb79ba0cd2d0ce4a3f01b1c87ec3b823805c51f317cbd499a4d98507f20b` | `6a70eb79ba0cd2d0ce4a3f01b1c87ec3b823805c51f317cbd499a4d98507f20b` | **MATCH** |

### 2.2 Evidence Manifest (`docs/verification/rsf-33/evidence-manifest.json`)
All 11 evidence files match their recorded sizes and SHA-256 hashes exactly:
- `PLAN.md`: 1,648 bytes, `dbd5cbf8...` (MATCH)
- `REPORT.md`: 6,610 bytes, `245b3fa9...` (MATCH)
- `commands.json`: 1,481 bytes, `f13d8d26...` (MATCH)
- `distribution.log`: 160,586 bytes, `f8151058...` (MATCH)
- `environment.json`: 558 bytes, `11698649...` (MATCH)
- `focused.log`: 4,785 bytes, `e22b1a16...` (MATCH)
- `implementation-manifest.json`: 1,319 bytes, `52bba827...` (MATCH)
- `kaneo-start.json`: 319 bytes, `dc789e55...` (MATCH)
- `private.log`: 13,901 bytes, `3d57b35b...` (MATCH)
- `public.log`: 88,065 bytes, `c6f441b2...` (MATCH)
- `schemas.log`: 1,192 bytes, `a9696451...` (MATCH)

---

## 3. Independent Verification Execution Results

The following test suites were independently executed by the QA reviewer:

| Verification Target | Command Executed | Exit Code | Results | Status |
|---|---|---|---|---|
| **Focused Attachment Compatibility Suite** | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest tests/test_attachment_compatibility.py -v` | `0` | 19 tests run, 0 failures | **PASS** |
| **System Python Focused Suite** | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests/test_attachment_compatibility.py` | `0` | 19 tests run, 0 failures | **PASS** |
| **Full Public Test Discovery** | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests -p 'test_*.py'` | `0` | 583 tests run, 0 failures | **PASS** |
| **Private Fixture Hooks Discovery** | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -p 'test_*.py'` | `0` | 47 tests run, 0 failures, 1 skip (native RSF-6 evidence check) | **PASS** |
| **Registry Schema Checker** | `PYTHONPATH=src PYTHONDONTWRITEBYTECODE=1 .venv/bin/python scripts/check_registry_schema.py` | `0` | 1 valid doc, 12 negative mutations rejected | **PASS** |
| **All Schema Validation Checkers (12 scripts)** | `for s in scripts/check_*schema*.py; do python3 $s; done` | `0` | 12 of 12 scripts passed | **PASS** |
| **Isolated Wheel & Clean venv Distribution Check** | `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | `0` | Clean wheel build, identical sdist/wheel digest, 583 public tests passed (12 skipped for Rust oracle not in wheel), stdlib core smoke passed | **PASS** |

---

## 4. Acceptance Criteria Audit

### Acceptance Criterion 1: Model conventional body/head/equipment attachment pairs only where pinned runtime supports them, retaining parent/child resource and anchor identities
- **Status:** **PASS**
- **Evidence:**
  - Implemented rules:
    - `RULE_PLAYER_HEAD_ANCHOR_DELTA` ('player_head_anchor_delta'): Conventional Body + Head pairing. Subtracts child anchor coordinates from parent anchor coordinates and adds layer offset. Requires valid anchors on both parent and child.
    - `RULE_HEAD_ACCESSORY_ANCHOR_DELTA` ('head_accessory_anchor_delta'): Conventional Body/Head + Accessory pairing. Adds intermediate head anchor shift to anchor subtraction delta.
    - `RULE_BODY_SHIELD_RELATIVE` ('body_shield_relative'): Shields have 0 anchors and attach relative to body origin.
    - `RULE_STANDALONE_UNATTACHED` ('standalone_unattached'): Entities such as companions retain standalone coordinates.
  - Parent/child resource identities (`parent_profile_id`, `child_profile_id`, `parent_part`, `child_part`) are explicitly preserved in reports and sealed registry records.
  - Verified across tests 1, 2, 3, 11, 12, 14, 16 in `tests/test_attachment_compatibility.py` and private fixture hooks in `tests/private_fixture_hooks/test_attachment_fixtures.py`.

### Acceptance Criterion 2: Missing weapon action, incompatible action family, or gameplay-job/visual-outfit mismatch reports a compatibility issue rather than silent filename substitution or fallback
- **Status:** **PASS**
- **Evidence:**
  - `validate_attachment_compatibility` detects and emits structured diagnostics:
    - `GAMEPLAY_JOB_MISMATCH`: Emitted when parent body and child attachment specify incompatible jobs (e.g. Novice body with Dragon Knight shield; test 7).
    - `INCOMPATIBLE_ACTION_FAMILY`: Emitted when child requires a weapon action family not present in parent profile (test 8).
    - `INCOMPATIBLE_RESOURCE_KIND`: Emitted when attempting to attach standalone companions (test 5) or equipping monster hosts with player gear (test 6).
    - `MISSING_ATTACHMENT_ACTION`: Emitted when child profile lacks a numeric action slot present on parent (test 10).
    - `MISMATCHED_FRAME_COUNT`: Emitted on a per-slot basis when frame counts differ (tests 4, 10; private test 2).
    - `MISSING_ANCHOR`: Emitted when anchor rules cannot resolve due to missing anchors on specific motions (test 9).
  - No fallback, truncation, modulo wrap, or silent file substitution occurs.

### Acceptance Criterion 3: Preview/requirements/compiler preserve declared attachment ordering/anchors; unknown support remains UNVERIFIED
- **Status:** **PASS**
- **Evidence:**
  - `composite_attachment_layers` arranges multi-part layers according to explicitly declared `layer_order` (e.g. `['body', 'head', 'accessory']` or `['shield', 'body', 'head']`).
  - Preserves part identities, sprite indices, pools, layer bounds, ordinals, and transformations without layer flattening or lossy compositing (test 13).
  - Any undeclared attachment rules or unverified pairings retain status `UNVERIFIED` without artificial promotion (test 14, 16).
  - Pinned Korangar playback for non-Novice attachments remains strictly `UNVERIFIED`.

### Acceptance Criterion 4: Representative local lawful attachment pairs are checked against frozen profile rules and native evidence is separate from structural compatibility
- **Status:** **PASS**
- **Evidence:**
  - Real discovered resources from local lawful GRF archives (Genetic Female Body, Novice Body, Novice Head, Jack Head Male Accessory, Dragon Knight Male Shield) were verified against Python ACT/SPR codecs, attachment rules, byte-exact preservation, and the independent Rust oracle (`tools/rust-oracle`).
  - Native playback evidence is strictly separated into orthogonal compatibility dimensions:
    - Novice Male Body + Novice Male Head: `native_korangar: VERIFIED` (supported by M5 native playback evidence).
    - Novice Male Body + Jack Head: `static_structure: VERIFIED`, `native_korangar: UNVERIFIED`.
    - Novice Male Body + Dragon Knight Shield: `static_structure: VERIFIED`, `runtime_mapping: PARTIAL`, `native_korangar: UNVERIFIED`.
  - No false claims of native playback are made for unexecuted corridors.

---

## 5. Technical Contracts & Invariants Audit

1. **Dragon Knight Male Shield Mismatched Frame Count Analysis:**
   - Novice/player body: 104 slots, 456 frames.
   - Dragon Knight shield: 104 slots, 448 frames (8 frames fewer).
   - Exact per-slot verification confirmed that slots 0..23 (Idle, Walk, Sit) and 32..103 match 100%. Exactly slots 24..31 (Group 3 Pickup across all 8 camera angles) have 2 frames in shield vs 3 frames in body.
   - Attachment engine emits 8 `MISMATCHED_FRAME_COUNT` diagnostics and assigns overall status `PARTIAL` (96 matching, 8 mismatched) rather than truncating or modulo-wrapping frames.
2. **Jack Head Male Accessory Reconciliation:**
   - Enrolled in `get_default_registry()` as `jack-head-male-v1`.
   - Has ACT SHA-256 `5dd8c7b8ebd5762b29863e86a77c4e555834cd401c0f559a8f92061a25a3ac93` and SPR SHA-256 `e636bdc5772bb1fa9206b84369d46a13b3e6ac79b6c600e55c5dbb6a952fd655`.
   - Verified 104 slots, 456 motions, 1 clip layer, 1 anchor per motion, 14 indexed sprites.
   - Paired with Novice body with 104 matching slots, 0 mismatched, status `SUPPORTED`.
3. **Exact Coordinate Transformations:**
   - `compose_attachment_coordinates` uses pure integer coordinate arithmetic:
     - Delta: `(parent_anchor_x - child_anchor_x, parent_anchor_y - child_anchor_y)`
     - Intermediate shifts and layer offsets are added directly without floating-point rounding or heuristics.
4. **Order-Preserving Multilayer Composition:**
   - `composite_attachment_layers` takes raw layer entries, organizes by part in declared order, and preserves all layer metadata.
5. **Scoped Review Invalidation (RSF-18 Integration):**
   - In test 19, a two-part requirement (`body` and `accessory`) was approved. Changing the accessory assignment in the ledger transitions the accessory occurrence review state to `STALE` (`COMPOSITION_CHANGED_OR_REQUIREMENT_UNAVAILABLE`), while the unchanged parent body review remains `APPROVED`.
6. **Distribution & Packaging:**
   - Distribution check (`tests/check_distribution.py`) verified sdist and wheel generation, lack of private files in package, stdlib core functionality without third-party dependencies, and 100% pass on all 583 public tests in a clean venv.

---

## 6. Findings & Discrepancies

- **Ranked Findings:** None. No correctness, security, architectural, or regression defects were identified.
- **Observations:** The task prompt referenced `scripts/check_distribution.py`, but the script is located at `tests/check_distribution.py`. The script was executed from `tests/check_distribution.py` with full pass (`DISTRIBUTION_CHECK_PASS`).

---

## 7. Final QA Recommendation

The implementation satisfies all acceptance criteria, technical contracts, and architectural invariants.

**Verdict:** **`QA_PASS`**
