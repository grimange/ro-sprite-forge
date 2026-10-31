# RSF-33 Verification Plan

## Objective
Verify equipment and attachment compatibility validation under pinned Korangar runtime rules:
- Validate body/head, body/shield, body/accessory, and companion attachment pairings.
- Action/view/frame mapping between parent and child resources, including exact mismatched frame count diagnostics (e.g. Group 3 Pickup: Body=3 frames vs Shield=2 frames across 8 views).
- Reconcile Jack Head Male Accessory (`jack-head-male-v1`) enrollment in the compatibility registry.
- Coordinate transformations and anchor delta composition without arbitrary rounding or guessing.
- Multilayer composition with layer ordering preservation without layer flattening.
- Incompatible weapon action family and gameplay-job/visual-outfit mismatch reporting without silent fallback.
- Scoped review invalidation (RSF-18): modifying child attachment recipe invalidates only child review, leaving parent body review intact.
- Multi-part topology resolution (RSF-8) and coverage evaluation (RSF-10).
- Independent Rust oracle parity on real lawful private fixtures.
- Independent clean virtual environment wheel installation and test execution.

## Verification Corridor
1. **Focused Unit Tests:** `tests/test_attachment_compatibility.py` (19 tests)
2. **Public Regression Suite:** `tests/` (583 tests)
3. **Private Fixture Hooks:** `tests/private_fixture_hooks/` (47 tests: 46 PASS, 1 SKIP)
4. **Schema Conformance Matrix:** 12 `scripts/check_*schema*.py` scripts
5. **Isolated Clean Distribution:** `tests/check_distribution.py` (583 tests PASS, 12 SKIP)
6. **Independent QA Review:** `forge-qa-reviewer` subagent read-only audit
