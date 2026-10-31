# RSF-33 — [M7] Equipment and Attachment Compatibility Validation Report

## 1. Executive Summary

This report documents the implementation and technical verification of **RSF-33: Equipment and Attachment Compatibility Validation** for Milestone M7.

The engine establishes data-driven, versioned attachment compatibility rules reflecting frozen Korangar / classic Ragnarok client behavior, separating:
1. **Parent/child resource and anchor identities**: Conventional Body + Head, Body + Shield, Body + Head Accessory, and Companion relations.
2. **Exact action/view/frame mapping**: Detects missing actions, missing slots, and per-slot mismatched frame counts without silent modulo, truncation, or fallback.
3. **Exact coordinate composition**: Evaluates parent and child anchor deltas and layer offsets using integer coordinate arithmetic without arbitrary rounding or guessing.
4. **Order-preserving multilayer composition**: Arranges parts according to declared layer order without altering original layer metadata or flattening layers.
5. **Jack Head reconciliation**: Explicitly enrolls `jack-head-male-v1` into `get_default_registry()` with audited ACT 2.4 / SPR 2.1 hashes and capability dimensions.
6. **Incompatible action families and gameplay-job mismatches**: Reports structured diagnostics (`GAMEPLAY_JOB_MISMATCH`, `INCOMPATIBLE_ACTION_FAMILY`, `INCOMPATIBLE_RESOURCE_KIND`) rather than silent filename substitution.
7. **Downstream pipeline integration**: Integrates cleanly with RSF-8 topology resolution, RSF-10 coverage evaluation, and RSF-18 scoped review invalidation (modifying an attachment recipe invalidates only that attachment's review while preserving parent body approvals).

---

## 2. Acceptance Criteria Fulfillment

| Acceptance Criterion | Result | Evidence |
|---|---|---|
| **1. Model conventional body/head/equipment attachment pairs only where pinned runtime supports them, retaining parent/child resource and anchor identities.** | **PASS** | `RULE_PLAYER_HEAD_ANCHOR_DELTA`, `RULE_HEAD_ACCESSORY_ANCHOR_DELTA`, `RULE_BODY_SHIELD_RELATIVE`, `RULE_STANDALONE_UNATTACHED` implemented in `src/ro_sprite_forge/core/attachments.py`; tested in `tests/test_attachment_compatibility.py` (tests 1–4, 11–13) and `tests/private_fixture_hooks/test_attachment_fixtures.py` (tests 1–3). |
| **2. Missing weapon action, incompatible action family or gameplay-job/visual-outfit mismatch reports a compatibility issue rather than filename substitution.** | **PASS** | `validate_attachment_compatibility` emits structured diagnostics `GAMEPLAY_JOB_MISMATCH`, `INCOMPATIBLE_ACTION_FAMILY`, `MISSING_ATTACHMENT_ACTION`, `MISMATCHED_FRAME_COUNT`, `INCOMPATIBLE_RESOURCE_KIND`; verified in tests 5–8, 10. |
| **3. Preview/requirements/compiler preserve declared attachment ordering/anchors; unknown support remains UNVERIFIED.** | **PASS** | `composite_attachment_layers` arranges layers by declared order while preserving layer metadata and part identities; unverified pairings retain `UNVERIFIED` status without false promotion; verified in tests 13–15, 17–19. |
| **4. Representative local lawful attachment pairs are checked against frozen profile rules and native evidence is separate from structural compatibility.** | **PASS** | Audited local lawful fixtures (Novice Body, Novice Head, Jack Head Male Accessory, Dragon Knight Male Shield, Genetic Female Body) verified against Python codecs, attachment rules, and independent Rust oracle; verified in `test_attachment_fixtures.py`. Native Korangar playback marked `UNVERIFIED` for new non-Novice profiles/pairings. |

---

## 3. Key Technical Discoveries & Audited Findings

### 3.1 Dragon Knight Male Shield Mismatched Frame Count Analysis
- Body has 104 slots and 456 frames.
- Dragon Knight Shield (`dragon-knight-male-shield-v1`) has 104 slots and 448 frames (8 frames fewer).
- Exact per-slot inspection reveals:
  - Slots 0..23 (Idle, Walk, Sit): 100% matching frame counts.
  - Slots 24..31 (Group 3: Pickup across all 8 views): Body has 3 frames per view; Shield has 2 frames per view.
  - Slots 32..103 (ReadyFight, Attack1..3, Hurt, Freeze1..2, Die, Skill): 100% matching frame counts.
- **Result:** The attachment engine correctly emits `MISMATCHED_FRAME_COUNT` diagnostics for slots 24..31, marks action mapping as 96 matching / 8 mismatched, and assigns overall status `PARTIAL` rather than silently truncating or modulo-wrapping frames.

### 3.2 Jack Head Male Accessory Reconciliation
- Reconciled into `get_default_registry()` as `jack-head-male-v1`.
- ACT SHA-256: `5dd8c7b8ebd5762b29863e86a77c4e555834cd401c0f559a8f92061a25a3ac93`
- SPR SHA-256: `e636bdc5772bb1fa9206b84369d46a13b3e6ac79b6c600e55c5dbb6a952fd655`
- Topology: 104 action slots, 456 motions, 1 clip layer per motion, 1 anchor per motion, 14 indexed sprites.
- Pairable with Novice Male Body via `head_accessory_anchor_delta`: 104 matching slots, 0 mismatched slots, status `SUPPORTED`.

### 3.3 Scoped Review Invalidation (RSF-18)
- When multi-part actor requirements (`body`, `accessory`) are reviewed and approved:
- Changing the accessory assignment in the ledger transitions the accessory occurrence review state to `STALE` with cause `COMPOSITION_CHANGED_OR_REQUIREMENT_UNAVAILABLE`.
- The unrelated parent body review state remains `APPROVED`, proving strictly scoped invalidation without project-wide review thrashing.

---

## 4. Verification Evidence Summary

| Suite / Check | Command | Exit Code | Tests | Status |
|---|---|---|---|---|
| **Focused Unit Suite** | `PYTHONPATH=src .venv/bin/python -m unittest tests/test_attachment_compatibility.py -v` | `0` | 19 run, 0 fail | **PASS** |
| **Full Public Suite** | `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v` | `0` | 583 run, 0 fail | **PASS** |
| **Private Fixture Hooks** | `PYTHONPATH=src .venv/bin/python -m unittest discover -s tests/private_fixture_hooks -v` | `0` | 47 run, 1 skip (native RSF-6 run evidence) | **PASS** |
| **Schema Conformance** | 12 `scripts/check_*schema*.py` scripts | `0` | 12 scripts | **PASS** |
| **Isolated Distribution** | `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | `0` | 583 run, 12 skip (Rust oracle not in wheel) | **PASS** |
| **Python 3.12 / 3.13** | Matrix execution | `NOT_RUN` | — | Interpreter unavailable on host |
| **Native Korangar GPU** | Playback run | `NOT_RUN` | — | Native corridor unexecuted; non-Novice profiles marked `UNVERIFIED` |
| **Playwright Browser** | Browser journey | `NOT_RUN` | — | No UI / web controls modified |
