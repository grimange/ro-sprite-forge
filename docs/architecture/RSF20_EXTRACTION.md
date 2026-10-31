# RSF-20 Spritesheet Extraction and Rectangle Validation

RO Sprite Forge M4 spritesheet extraction enables deterministic subregion and regular grid
cropping from PNG spritesheets into content-addressed project blob storage, maintaining strict
source provenance without automatic pose identification, boundary inference, or silent visual approval.

## Technical Validation and Boundaries

The extraction engine in `src/ro_sprite_forge/core/extraction.py` enforces integer pixel conventions and security limits:
- **Pixel Convention**: Semi-open 0-indexed intervals $[x, y, x + \text{width}, y + \text{height})$.
- **Dimension & Coordinate Bounds**:
  - $x \ge 0, y \ge 0$ (negative coordinates raise `INVALID_RECTANGLE_COORDINATES`).
  - $\text{width} > 0, \text{height} > 0$ (non-positive dimensions raise `INVALID_RECTANGLE_DIMENSIONS`).
  - $x + \text{width} \le W_{\text{sheet}}, y + \text{height} \le H_{\text{sheet}}$ (exceeding sheet bounds raises `RECTANGLE_OUT_OF_BOUNDS`).
  - Boundary touching ($x + \text{width} = W_{\text{sheet}}$ or $y + \text{height} = H_{\text{sheet}}$) is strictly supported.
  - Single-pixel extractions ($1 \times 1$) are valid at any permissible coordinate.
- **Atomic Batch Validation**:
  - All requested rectangles are validated before any cropping or blob writes begin.
  - If any rectangle in a batch fails bounds checking, dimension checking, or ordinal contiguity, the entire extraction is rejected with zero side effects.
- **Source Verification & Bounds Limits**:
  - Validates source PNG signature, dimensions, decompression budget, and corruption using `validate_png()`.
  - Mismatch with `expected_sheet_sha256` raises `SOURCE_HASH_MISMATCH`.
  - Empty rectangle batches raise `EMPTY_EXTRACTION`.
  - Batches exceeding $1024$ rectangles raise `EXTRACTION_TOO_LARGE`.

## Regular Grid Expansion

- Supports uniform grids specifying `cell_width`, `cell_height`, `columns` (or `cols`), `rows`, `offset_x`, `offset_y`, `spacing_x`, `spacing_y`, and optional `cell_id_prefix`.
- Validates that total grid span $(\text{offset\_x} + \text{cols} \cdot \text{cell\_w} + (\text{cols} - 1) \cdot \text{spacing\_x}) \le W_{\text{sheet}}$ and similarly for height.
- Exceeding sheet span raises `GRID_OUT_OF_BOUNDS`.
- Enumerates cells in row-major order with contiguous ordinals $0, 1, \dots, N-1$.
- Supports optional sparse cell selection (`selected_cells` / `cells`) with explicit row and column indices.

## Four-Fold Orthogonal Provenance

Spritesheet extraction maintains four distinct identities for complete auditability:
1. **Source Spritesheet SHA-256 (`source_sha256`)**: The exact content digest of the original spritesheet PNG.
2. **Rectangle Extraction Recipe SHA-256 (`recipe_sha256`)**:
   $$\text{recipe\_sha256} = \text{digest}(\text{canonical\_bytes}(\{\text{"schema"}: \text{"rsf.extraction-recipe/v1"}, \text{"source\_sha256"}: \text{sheet\_sha256}, \text{"rectangle"}: [x, y, w, h, \text{id}, \text{ordinal}]\}))$$
   Distinguishes two crops with identical pixel content extracted from different coordinates or ordinals.
3. **Extracted Crop Image SHA-256 (`extracted_sha256`)**: Content-addressed digest of the deterministically encoded subregion PNG bytes. Enables blob deduplication.
4. **Collection Digest (`collection_sha256`)**:
   $$\text{collection\_sha256} = \text{digest}(\text{canonical\_bytes}([\text{item}[\text{extracted\_sha256}] \text{ for item in sorted\_items}]))$$
   Seals the complete ordered extraction result.

## Workbench, Ledger and Review Boundaries

- Candidate frames are staged as content-addressed blobs and recorded in `manifest["sources"]` with:
  - `origin = "AUTHORED"`, `kind = "IMAGE"`, `availability = "AVAILABLE"`, `validation = "VALID"`
  - Extraction metadata: `extraction_id`, `recipe_sha256`, `source_sheet_sha256`, `rect_id`, `crop_rect`
- Extractions are recorded in `manifest["extractions"]` under sealed schema `rsf.spritesheet-extraction/v1`.
- **Zero Auto-Assignment**: Extraction leaves `manifest["ledger"]["assignments"]` untouched.
- **Zero Auto-Approval**: Extraction leaves `manifest["review_events"]` untouched.
- Staged candidate frames appear in the existing source tray (`#art-source`) for explicit operator assignment.
