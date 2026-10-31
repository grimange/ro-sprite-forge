# RO Sprite Forge — Operator Documentation

Welcome to the **RO Sprite Forge** operator documentation. RO Sprite Forge is a **standalone, local, human-operated** animation requirements planner, sprite inspection workbench, and deterministic SPR/ACT asset compiler targeting pinned Korangar runtime compatibility.

---

## Documentation Index

| Guide | Description |
|---|---|
| [Quickstart Guide](QUICKSTART.md) | System requirements, package installation, CLI entry points, and local workbench startup. |
| [Production Guide](PRODUCTION_GUIDE.md) | End-to-end artwork workflow: declaring topology before art, importing PNG/video/spritesheets, assigning layers, previewing, operator visual approval, and deterministic compilation. |
| [Compatibility and Actions Guide](COMPATIBILITY_AND_ACTIONS.md) | Actor profiles (Novice, Orc Skeleton, Job bodies, Monsters), head/body separation, equipment attachments, offline custom actions, and `PARTIAL_DIAGNOSTIC` boundaries. |
| [Persistence and Recovery Guide](PERSISTENCE_AND_RECOVERY.md) | Content-addressed storage, project manifest revisions, atomic transactions, schema migrations, crash-safe disaster recovery, and recovery provenance reporting. |
| [Error Catalog](ERROR_CATALOG.md) | Complete diagnostic catalog mapping formal error codes and identifiers to subsystems, root causes, project impacts, and actionable operator resolutions. |
| [Synthetic Walk Tutorial](TUTORIAL.md) | Step-by-step tutorial executing a bounded 2-layer Walk replacement and simulated crash recovery using synthetic redistributable test assets. |

---

## Core Product & Operational Principles

### 1. Operator Controls Visuals
The human operator is the sole authority on visual aesthetics, pose correctness, choreography, character identity, and artistic acceptability. The application **never** invents, auto-generates, synthesizes, in-paints, aesthetically scores, or silently approves missing frames or layers.
- An algorithmic `PASS` signifies **objective structural validity and schema coverage**, not artistic quality or runtime proof.
- Transformations and reuse are explicit, versioned, and reproducible.
- Unknown does not mean accepted; silence is never approval.

### 2. Four Authorities Kept Strictly Separate
RO Sprite Forge maintains strict separation among four independent authorities:
1. **Observed Resource Inventory:** Audited classic or reference ACT/SPR binaries and their actual decoded content.
2. **Pinned Runtime Semantics:** Pinned Korangar action/view slot mappings and timing rules.
3. **Operator-Declared Target:** The finite work order specifying required actions, views, frames, and declared layer topology.
4. **Artwork Assignment Ledger:** The exact mapping connecting authored source assets or explicit reuse dependencies to target requirements.

### 3. Layer Topology Before Artwork Production
An actor target cannot claim an exact work order or evaluate coverage until action/view/frame counts **AND** ordered layer topology are declared or explicitly inherited.
- Undeclared topology produces `UNDERSPECIFIED_LAYER_TOPOLOGY`.
- The engine will **never** silently assume a single-layer default.

### 4. Orthogonal Status Dimensions
Asset status is tracked across orthogonal, non-conflated dimensions:
- **Requirement:** Finite target requirement presence.
- **Availability:** Authored or staged source asset presence.
- **Validation:** Image dimensions, bit depths, and format integrity.
- **Runtime Support:** Pinned Korangar slot resolution and timing capability.
- **Operator Visual Review:** Explicit pre-build composition review (`APPROVED`, `REJECTED`, `STALE`, `NOT_REQUIRED`).
- **Preview Fidelity:** Workbench rendering status (`FAITHFUL`, `PARTIAL_PREVIEW`, `UNVERIFIED`).
- **Independent Native Verification:** Execution proof in pinned Korangar native playback (`M0-N`).

---

## Directory Layout

```
docs/operator/
├── README.md                     # This index and overview
├── QUICKSTART.md                 # Setup, CLI, and workbench startup
├── PRODUCTION_GUIDE.md           # Requirements-first workflow & compilation
├── COMPATIBILITY_AND_ACTIONS.md  # Profiles, attachments & diagnostic actions
├── PERSISTENCE_AND_RECOVERY.md   # Storage, schema migration & disaster recovery
├── ERROR_CATALOG.md              # Complete error catalog & remediation steps
└── TUTORIAL.md                   # End-to-end synthetic Walk tutorial
```
