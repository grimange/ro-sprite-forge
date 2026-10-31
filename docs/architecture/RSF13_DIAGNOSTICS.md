# RSF-13 — Reference Comparison, Contact Sheets and Sequence Exports

## 1. Architectural Role and Invariants

RSF-13 extends the M2 inspection workbench with deterministic comparison, visualization, filmstrip/contact sheet generation, and atomic frame sequence exports.

### Separation of Concerns & Authorities
1. **Mathematical / Geometric Parity Only**: The comparison engine evaluates objective dimensions, bounding boxes, origin shifts, channel deltas, and pixel/alpha difference counts. It never evaluates visual aesthetic suitability or character appearance.
2. **Operator Visual Authority**: Human visual approval remains exclusive and unverified by algorithms (`artistic_approval: "UNVERIFIED"`, `technical_difference_only: true`).
3. **Strict Overlay Isolation**: Visual overlays (origin crosshair, transformed/visible bounds, multipart anchors, and layer ordinals) are rendered strictly onto a copy of the rendered image. When overlays are disabled, PNG output is bit-for-bit identical to the raw composite preview. When overlays are enabled, the underlying `preview_png_sha256` recorded in the canonical comparison report remains the untouched hash of the raw render.
4. **Candidate Absence & No Invention**: If a candidate asset is not supplied, the workbench provides a reference-only inspection (`comparison_status: "MISSING_CANDIDATE"`). It never invents placeholder artwork or silently falls back to classic client defaults.
5. **Atomic Publication**: Frame sequence exports are staged in an isolated temporary directory and published atomically to the destination directory along with a sealed `sequence-manifest.json`.

---

## 2. Comparison Subsystem (`ro_sprite_forge.core.comparison`)

### Diagnostic Modes
- `SIDE_BY_SIDE`: Composites reference (left) and candidate (right) separated by a padding border, with optional text headers.
- `DIFFERENCE`: Computes an amplified channel-by-channel delta image on a unified canvas. Zero-difference pixels are completely transparent `(0, 0, 0, 0)`.
- `ONION_SKIN`: Blends candidate over reference at configurable alpha opacity (default 50%).
- `REFERENCE_ONLY`: Renders only the reference frame.
- `CANDIDATE_ONLY`: Renders only the candidate frame.

### Alignment Policies
- `NONE`: No displacement `(0, 0)`.
- `ORIGIN`: Displaces candidate such that candidate canvas origin aligns with reference origin.
- `BOUNDS_CENTER`: Displaces candidate such that the center of candidate's visible bounds aligns with the center of reference's visible bounds.
- `EXPLICIT`: User-declared displacement `(dx, dy)`.

### Objective Difference Metrics
- `dimensions_match`: Whether canvas width and height match.
- `bounds_match`: Whether visible bounding boxes match.
- `origin_displacement`: Exact `[dx, dy]` shift between candidate and reference origin.
- `anchor_displacement`: Exact `[dx, dy]` shift between candidate and reference multipart anchors (or null).
- `layer_count_match`: Whether layer count in the selected motion matches.
- `pixel_difference_count`: Number of pixels differing in RGBA channels.
- `alpha_difference_count`: Number of pixels differing in alpha.
- `total_pixels_compared`: Total pixels on the comparison canvas.
- `max_channel_difference`: Maximum absolute difference (0..255) across R, G, B, A channels.
- `mean_absolute_difference`: Average channel difference across all pixels and channels.
- `difference_png_sha256`: SHA-256 hash of the difference image PNG bytes.
- `identical`: Strict boolean identity (`pixel_difference_count == 0` and dimensions match).

---

## 3. Contact Sheet & Sequence Export Subsystem (`ro_sprite_forge.core.contact_sheet`)

### Filmstrips & Contact Sheets
- Arranges animation frames into an $M \times N$ tile grid.
- Integer nearest-neighbor zoom scaling (`scale >= 1`) to preserve sharp pixel art edges without blur or anti-aliasing artifacts.
- Configurable margins, inter-tile padding, and frame ordinal labels (`F00`, `F01`, ...).
- Sealed under schema `rsf.contact-sheet/v1`.

### Frame Sequence Exports
- Stages individual PNG frames (`frame_000.png`, ...) in an isolated temporary directory.
- Computes individual frame hashes and aggregate `sequence_sha256`.
- Produces a canonical `sequence-manifest.json` under schema `rsf.sequence-manifest/v1`.
- Performs atomic directory rename to prevent partial or corrupted exports.
- Output preflight ensures existing target directories are never silently overwritten.

---

## 4. Packaged Contracts & Schemas
- `rsf.preview-comparison/v1`: Closed Draft 2020-12 schema for frame reference comparison.
- `rsf.contact-sheet/v1`: Closed Draft 2020-12 schema for contact sheet generation.
- `rsf.sequence-manifest/v1`: Closed Draft 2020-12 schema for frame sequence export manifests.
