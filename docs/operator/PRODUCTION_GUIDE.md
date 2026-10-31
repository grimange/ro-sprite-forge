# RO Sprite Forge — Production Guide

This guide details the complete, requirements-driven artwork production workflow in **RO Sprite Forge**: from declaring actor requirements and ordered layer topology before drawing art, to ingesting source frames, assigning layers, previewing animations, recording visual approvals, and compiling deterministic ACT/SPR game resources.

---

## 1. Requirements-First Philosophy

In traditional sprite workflows, artists often draw animation frames without knowing the exact runtime layer counts, view angles, or slot assignments, resulting in mismatched frame counts, broken layer order, or missing diagonal directions.

**RO Sprite Forge reverses this pattern:**
1. **Declare Requirements First:** Specify the actor profile, target scope, and ordered layer topology before creating or importing artwork.
2. **Export Work Order:** Generate an exact checklist of required action/view/frame/layer occurrences.
3. **Ingest & Assign:** Map authored artwork directly to requirements or declare explicit reuse.
4. **Inspect & Review:** Preview multi-layer composited animations; the human operator exercises sole visual authority.
5. **Compile Deterministically:** Produce byte-consistent ACT/SPR binaries targeting pinned Korangar runtime playback.

---

## 2. Declaring Target and Ordered Layer Topology

### Why Layer Topology is Mandatory
A Ragnarok actor sprite rarely consists of a single flat image. Classic characters and monsters combine multiple ordered visual layers:
- **Novice Character:** Shadow (Layer 0) + Body (Layer 1) + Head/Hair (Layer 2) + Headgear (Layer 3+).
- **Orc Skeleton:** Shadow (Layer 0) + Weapon/Axe (Layer 1) + Body (Layer 2) + Shield (Layer 3).

> [!IMPORTANT]
> An actor target **cannot** claim an exact work order or evaluate coverage until both action/view/frame counts **AND** ordered layer topology are declared.
> Attempting to evaluate coverage without declared topology raises `UNDERSPECIFIED_LAYER_TOPOLOGY`. The application **never** silently defaults to a 1-layer topology.

### Declaring Topology in the Workbench

1. Click **"⚙️ Define Target & Topology"** in the center toolbar.
2. Select your **Target Scope**:
   - `walk`: Bounded Walk vertical slice (8 views, 8 frames/view).
   - `idle`: Stand/Idle animation (8 views, 4 frames/view).
   - `walk_idle`: Common mobility slice.
   - `combat`: Stand, Walk, Attack, Hurt, Die.
   - `full`: Complete 13-action actor profile (104 slots).
3. In the **Layer Topology** section, declare the explicit ordered layers:
   ```json
   [
     {"index": 0, "name": "shadow", "role": "shadow"},
     {"index": 1, "name": "body", "role": "main"}
   ]
   ```
4. Save the target. The workbench immediately generates the canonical requirement occurrences.

---

## 3. Work Orders and Missing Artwork Evaluation

Once topology is established, the workbench calculates exact coverage metrics:
- **Slots:** Total requested ACT action/view slots.
- **Frames:** Total animation occurrences across all views.
- **Layers:** Total distinct layer occurrences requiring artwork.
- **Unassigned:** Count of required occurrences not yet assigned.

### Exporting Work Orders
Click **"📥 Work Order (TXT)"** or **"📥 Work Order (JSON)"** in the bottom panel to export the missing-art checklist. The resulting document gives artists exact occurrence identifiers:

```
Occurrence: player.male_novice.walk.south.frame_0.layer_1 (body)
Occurrence: player.male_novice.walk.south.frame_1.layer_1 (body)
...
```

---

## 4. Ingesting Source Artwork

RO Sprite Forge provides five ingestion mechanisms. All imported source blobs are stored in immutable, content-addressed storage (`blobs/` SHA-256).

### A. Reference ACT/SPR Pair
Import existing game resources to inspect classic animation timing or provide a base for bounded replacements:
1. Expand **"Import an existing ACT/SPR reference pair"**.
2. Provide a Resource ID (e.g. `novice-male-ref`), choose Part (`body` or `head`), and select `.act` and `.spr` files.
3. Click **"Import selected pair"**.
*Original bytes are preserved bit-for-bit. Classic images do not become approved replacement art without explicit operator assignment.*

### B. Ordered PNG Sequence Ingestion
Ingest a directory or set of PNG files representing an animation sequence:
1. Expand **"Import ordered PNG sequence"**.
2. Enter Sequence ID (e.g. `walk-south`) and Name (`Walk South`).
3. Select the PNG frame files.
4. Verify or adjust the contiguous ordinals (0 to $N-1$) using the **"Natural sort by filename"** or manual ordering arrows.
5. Click **"Import verified sequence"**.

### C. PNG Spritesheet Extraction
Extract frame candidates from a sprite sheet image:
1. Expand **"Import PNG spritesheet & extract"**.
2. Upload the spritesheet PNG.
3. Select extraction mode:
   - **Manual Rectangles:** Define exact `[x, y, width, height]` bounding boxes.
   - **Regular Grid:** Specify cell width, cell height, columns, rows, and spacing offsets.
4. Click **"Extract and stage candidate frames"**.

### D. Single PNG Frame Ingestion
Expand **"Import single PNG frame"** to upload individual candidate textures or replacement sprites.

### E. Video Candidate Extraction (Optional)
If FFprobe/FFmpeg are available locally:
1. Expand **"Import video candidate frames"**.
2. Inspect video stream metadata and bounded presentation frames.
3. Select candidate frames by integer Presentation Timestamp (PTS) or presentation ordinal.
> [!NOTE]
> Video PTS represents source container timing. ACT/runtime animation timing remains independent in the animation inspector.

---

## 5. The Artwork Assignment Ledger

Assignments link authored source images to required occurrences.

### Direct Source Mapping
1. Select a leaf layer occurrence in the Left Navigation Tree.
2. In the **"Existing source tray"**, choose the imported source image.
3. Click **"Review direct mapping"** to assign.

### Explicit Reuse and Horizontal Mirroring
Ragnarok character walk cycles typically draw 5 primary directions (South, South-West, West, North-West, North) and mirror 3 directions (South-East, East, North-East):
1. Select the destination occurrence (e.g. `walk.south_east.frame_0.layer_body`).
2. In **"Explicit reuse"**, select the corresponding source assignment (`walk.south_west.frame_0.layer_body`).
3. Check **"Explicit horizontal mirror (executed preview)"**.
4. Click **"Review reuse mapping"**.

### Batch Assignments
To avoid repetitive clicks for large sequences:
1. Use **"Add selected requirement to batch"** to stage multiple mappings.
2. Review the structured JSON batch array in **"Explicit batch mappings"**.
3. Click **"Review batch mappings"** to publish all assignments in a single atomic transaction.

---

## 6. Non-Destructive Image Transformations

Operators can declare versioned, reversible image processing operations without modifying original source files:
- **Operations:** `crop`, `pad`, `resize`, `mirror_x`, `mirror_y`, `alpha_clip`.
- Expand **"Non-destructive image transformations (RSF-21)"**.
- Select the input source, add operation steps, and click **"Inspect before / after"**.
- Click **"Stage derived candidate"** to publish the transformed result with full cryptographic provenance and loss disclosure.

---

## 7. Multi-Layer Preview & Animation Inspection

The workbench provides a local Python-backed animation compositor that accurately reflects Korangar runtime slot resolution and layer ordering.

### Playback Controls and Keyboard Navigation
- **Action & View Selection:** Select action group (e.g. `walk`, `stand`) and view angle (0 to 7).
- **Frame Scrubber:** Drag the range slider or step frames using keyboard shortcuts:
  - `Left Arrow`: Step to previous frame.
  - `Right Arrow`: Step to next frame.
  - `Space`: Toggle Play / Pause.
- **Timing Context:** For Walk actions, enter the movement speed context; for Attack/Hurt actions, supply duration in milliseconds.

### Integer Nearest-Neighbor Zoom & Alpha Inspection
- **Zoom Toolbar:** Select `1× (100%)`, `2× (200%)`, `3× (300%)`, `4× (400%)`, or `8× (800%)`.
  - Shortcuts: `+` or `=` to zoom in, `-` to zoom out, `0` to reset to 1×.
  - Uses CSS pixelated nearest-neighbor sampling without blur.
- **Background Modes:** Toggle the viewport background to inspect semi-transparent pixels and edge bleeding:
  - `Checkerboard (Dark)`: Default contrast checkerboard.
  - `Checkerboard (Light)`: High-key light checkerboard.
  - `Solid Dark`: #14171d matte background.
  - `Solid White`: #ffffff white paper background.
  - `Transparent`: Clean alpha display.
  - Shortcut: Press `B` to cycle background modes.

---

## 8. Operator Visual Decisions

A successful algorithmic test certifies structure and schema coverage—**it does not approve visual art**. The operator must explicitly record visual decisions.

### Review Scopes
In **"Operator visual decision"**, select the review scope:
- `layer`: The currently selected layer.
- `frame`: All ordered layers in the current animation frame.
- `view`: All frames in the active view angle.
- `action`: All views and frames within the active action.
- `batch`: An explicit array of occurrence IDs.

### Executing Review
1. Click **"Inspect review scope"** to open the modal dialog.
2. Inspect composited images.
3. Choose an action:
   - **`[A] Approve displayed scope`** (`Key: A`): Records `APPROVED`.
   - **`[R] Reject displayed scope`** (`Key: R`): Records `REJECTED`.
   - **`Record NOT_REQUIRED policy`**: For unchanged classic references with no replacement claim.
   - **`[Esc] Cancel`** (`Key: Esc`): Dismiss without modifying status.

### Pre-Build Composition Binding & Stale Invalidation
Approvals are bound cryptographically to the canonical pre-build composition hash (incorporating source digests, layer topology, recipes, timing, and preview semantics).
- If an underlying source image or transformation recipe is subsequently modified, affected reviews transition automatically to `STALE`.
- The compiler rejects stale reviews for production builds.

---

## 9. Deterministic ACT/SPR Compilation

Once assignments are complete and visually approved, expand **"Deterministic ACT/SPR compiler & replacement writer"**:

### Compilation Settings
1. **Base ACT/SPR resource:** Choose the base resource to modify.
2. **Optional companion head resource:** Select companion head if compiling a combined character profile.
3. **Compilation Mode:**
   - `bounded_replacement`: Replace only authored/approved slots (e.g. Walk), preserving all other classic actions unchanged.
   - `preserve`: Byte-preserving sanity round-trip.
   - `production_export`: Full-profile export.
4. **SPR Pool Policy:**
   - `preserve_pool`: Retain indexed or RGBA pool according to original resource structure.
   - `explicit_rgba` (Pool 1): Compile sprites into 32-bit RGBA pool.
   - `indexed_exact` (Pool 0): Lossless indexed RLE sprite pool.
5. **Shared SPR Isolation:**
   - `auto`: Copy-on-Write (CoW). If a modified sprite image is referenced across multiple unassigned frames, isolations are appended automatically so unchanged frames are unaffected.
6. Click **"Inspect compilation plan"** to audit replacement counts and verify zero blockers.
7. Click **"Compile modified ACT/SPR"** to execute the deterministic compilation.

---

## 10. Milestone Verification Gates

Every compiled asset is subject to three independent verification gates:

| Gate | Name | Verification Standard |
|---|---|---|
| **M0-S** | Structural & Preservation | Codec parses binary without errors; unchanged actions match bit-for-bit; ACT roundtrip succeeds semantically. |
| **M0-I** | Independent Rust Oracle | Independent Rust decoder decodes compiled ACT/SPR with identical slot, frame, and layer counts. |
| **M0-N** | Pinned Korangar Native Proof | Executable Korangar client loads compiled asset and plays requested action/view slot without fallback or crash. |

> [!NOTE]
> If Gates M0-S and M0-I pass but the local environment lacks Korangar native playback dependencies, the asset is classified as `M0_PARTIAL_NATIVE_UNVERIFIED`. It is never falsely marked as passing native proof.
