# RSF-22 Architecture: Bounded Walk Artwork Production, End-to-End Integration and M4 Closure

## 1. Overview & Architectural Role

RSF-22 is the culminating integration deliverable of **Milestone M4 (Artwork Ingestion and Processing)** in RO Sprite Forge.

It brings together:
- **M1 Requirements & Coverage**: Bounded target declarations (`rsf.target/v2`), exact layer topology (`rsf.resolved-requirements/v1`), assignment ledgers (`rsf.assignment-ledger/v1`), and coverage work orders (`rsf.coverage-report/v1`).
- **M2 Preview & Diagnostics**: Multilayer alpha compositing (`ro_sprite_forge.formats.preview`), authoritative timeline stepping and seek (`ro_sprite_forge.core.timeline`), and diagnostic comparison.
- **M3 Local Operator Workbench**: Content-addressed persistence (`blobs/`), REST API, browser workbench UI, explicit operator review proposals, and scoped review invalidation.
- **M4 Ingestion & Processing**:
  - RSF-19: Ordered PNG sequence ingestion (`rsf.png-sequence/v1`).
  - RSF-20: Spritesheet extraction and rectangle validation (`rsf.spritesheet-extraction/v1`).
  - RSF-21: Reversible, non-destructive image transformations (`rsf.image-recipe/v1`).

---

## 2. Core Architectural Invariants in the Walk Workflow

### 1. Declared Target Precedes Ingestion
An actor target (e.g. Walk, 6 frames per view, layer topology `body`) is declared before any artwork is ingested. Illustrative $8 \times 6$ counts are never imposed as an arbitrary quota: the target's explicit action/view/frame/layer definition is authoritative.

### 2. Strict Immutability of Original Artwork
Original source bytes are stored immutably in content-addressed storage (`blobs/{source_sha256}`). Operations (crop, flip, scale, offset, matte keying) produce separate, deterministically encoded derived PNG blobs (`blobs/{derived_sha256}`) sealed with recipe digests (`recipe_sha256`). Original source bytes remain bit-for-bit unchanged and recoverable.

### 3. Single Application of Transformations
When a derived image is assigned via `DIRECT_SOURCE` in the assignment ledger, the compositor renders the actual derived image pixels (`blobs/{derived_sha256}`). The transformation recipe was already executed to produce the derived blob; the compositor does NOT reapply the transformation recipe.

### 4. Separation of Readiness Dimensions
Completion of a bounded Walk direction (e.g. view 0, 6 frames assigned and approved) satisfies only that specific narrow scope:
- **Bounded Walk Direction Complete**: 6 / 6 required layers in view 0 assigned.
- **Full Walk Action Complete**: Requires all 8 views (48 occurrences in player profile). Omitted directions remain unassigned gaps in the missing-art work order.
- **Full Actor Complete**: Requires all actions in the actor's profile.
- **Production Export Readiness**: Strictly `false` at M4. Native Korangar playback and modified binary compilation belong to Milestone M5.

### 5. Operator-Controlled Review & Scoped Invalidation
Artwork is never automatically approved upon ingestion, extraction, transformation, or assignment. The operator inspects the rendered composition and explicitly issues an `APPROVED` or `REJECTED` decision on the canonical composition digest (`basis_sha256`).
If an assigned source is later replaced or re-transformed, that specific layer occurrence's review transitions to `STALE` (`COMPOSITION_CHANGED_OR_REQUIREMENT_UNAVAILABLE`). Unrelated approved layer occurrences remain `APPROVED`.

---

## 3. End-to-End Workflow Pipeline

```
[Target Contract (Walk, 6 frames, layer: body)]
                     │
                     ▼
       [Requirements Resolver (RSF-8)]
                     │
                     ├───────────────────────────────┐
                     ▼                               ▼
       [Staged PNG Sequence (RSF-19)]  [Spritesheet Extraction (RSF-20)]
                     │                               │
                     └───────────────┬───────────────┘
                                     ▼
                     [Transformation Recipe (RSF-21)]
                                     │
                                     ▼
                     [Derived Candidate Blob Staged]
                                     │
                                     ▼
                     [Assignment Ledger (RSF-9/17)]
                                     │
                     ┌───────────────┴───────────────┐
                     ▼                               ▼
       [Multilayer Compositor (RSF-11)]    [Authoritative Timeline (RSF-12)]
                     │                               │
                     └───────────────┬───────────────┘
                                     ▼
                     [Operator Review Proposal (RSF-18)]
                                     │
                                     ▼
                     [Explicit Approval Recorded]
                                     │
                                     ▼
                     [Coverage Work Order Updated (RSF-10)]
```

---

## 4. Verification & Milestone M4 Closure

RSF-22 proves the end-to-end integration of all M4 capabilities through:
1. Python unit and integration tests (`tests/test_walk_workflow.py`).
2. Real-browser Playwright execution in Chromium (`tests/browser/rsf22-mcp.js`).
3. Isolated wheel distribution verification (`tests/check_distribution.py`).
4. Full public and private regression suite pass.
5. Independent read-only QA review by `forge-qa-reviewer`.
