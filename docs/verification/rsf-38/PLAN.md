# RSF-38 Implementation & Verification Plan: Operator Documentation, Error Catalog, and Workflow Ergonomics

## Overview
Make the accepted RO Sprite Forge capabilities directly understandable, accessible, and actionable to a human operator without requiring internal Python module familiarity or raw JSON manipulation. Provide comprehensive operator documentation, an actionable source-backed error catalog, targeted workbench UX improvements, and end-to-end synthetic tutorials.

## Scope & Deliverables
1. **Operator Documentation Suite (`docs/operator/`)**:
   - `docs/operator/QUICKSTART.md`: Accurate installation from wheel, dependencies (stdlib core vs Pillow/jsonschema/FFmpeg/Rust), CLI startup, workbench startup, safe loopback binding.
   - `docs/operator/PRODUCTION_GUIDE.md`: Requirements-first production journey (topology discovery before art, work orders, PNG sequences, spritesheets, optional video candidates with PTS vs ACT timing separation, assignments, coverage, preview, review approvals, build eligibility, diagnostic vs production compilation).
   - `docs/operator/COMPATIBILITY_AND_ACTIONS.md`: Body/head separation, equipment attachment pairing, costume appearance independence, offline custom actions, and `PARTIAL_DIAGNOSTIC` runtime boundaries.
   - `docs/operator/PERSISTENCE_AND_RECOVERY.md`: Project schema, revisions, content-addressed storage, migration versions, crash recovery from `.bak`, recovery provenance reporting, and safe project backup policies.
   - `docs/operator/ERROR_CATALOG.md`: Source-backed catalog mapping every `ForgeError` code, validation failure, and diagnostic identifier to subsystem, root cause, project state impact, and operator next action.
   - `docs/operator/TUTORIAL.md`: Complete synthetic walkthrough of a bounded Walk replacement and a project recovery exercise using redistributable test assets.
2. **Targeted Recovery Provenance and Migration Hardening (`src/ro_sprite_forge/core/project.py`)**:
   - Enrich `recover_project()` return dictionary to include `backup_manifest_hash` and `restored_manifest_hash` for full operator transparency.
   - Verify deterministic migration timestamp behavior and document canonical vs metadata timestamp semantics.
3. **Workbench UX Ergonomics & Accessibility (`src/ro_sprite_forge/static/`)**:
   - Keyboard navigation: Arrow keys for timeline frame stepping and playback toggling (`Space`).
   - Zoom controls: 1x, 2x, 4x integer nearest-neighbor zoom with clear pixelated rendering and checkerboard toggle for alpha transparency inspection.
   - Non-color-only diagnostics: Text badges, icon indicators, and explicit status labels distinguishing technical validity from artistic approval and production authorization.
   - Responsive layout improvements for standard desktop viewports (1280x720 up to 1920x1080).
4. **Focused Test Suite (`tests/test_operator_documentation_and_ux.py`)**:
   - Error catalog cross-validation (every documented code exists in `errors.py` or contracts).
   - Documented CLI command and option verification.
   - Synthetic tutorial command execution verification.
   - Recovery provenance reporting verification.
   - Documentation link integrity verification.
5. **Full Verification Matrix**:
   - Focused suite, public suite (677 tests), private fixture suite, schema checkers, and clean distribution check.
