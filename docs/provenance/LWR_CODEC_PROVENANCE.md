# RO Sprite Forge — LWR Codec Provenance and License Record

Date: 2026-10-29  
Task: RSF-2 ([M0] Audited SPR 2.1 / ACT 2.4 codecs and source provenance)  
Authoritative Baseline Plan SHA-256: `5edfbebcdb47620c59a915e8874094f35092125dd0444b79468aa55a191a361e`  

---

## 1. Upstream Source Identification

| Property | Value |
|---|---|
| **Original filesystem path** | `/home/ra/Documents/Living-world-Ragnarok/tools/character_production/ro_reference.py` |
| **Original SHA-256** | `55aefdc8ba7bb5aaf4619983d72cb26c2865154961116c8ad075c65378142c46` |
| **Original size** | 6,618 bytes (169 lines) |
| **Repository** | Living-world-Ragnarok (LWR) |
| **Branch** | `roadmap/lwr-canonical-roadmap-tracking-e1` |
| **Repository HEAD** | `576049a6dfcb8eb606d244fb50da5a1c2363929d` |
| **Git tracking status** | **Untracked** (`?? tools/character_production/ro_reference.py`) |
| **Inspection reference** | `RO_SPRITE_FORGE_LWR_REUSE_AUDIT_E1.md` §§2.1, 3.1 |

> [!IMPORTANT]
> The upstream file is untracked in the inspected LWR working tree. Therefore, repository HEAD alone does not identify its contents. The content hash `55aefdc8ba7bb5aaf4619983d72cb26c2865154961116c8ad075c65378142c46` is the definitive identity of the reused source snapshot.

---

## 2. Ownership and Licensing Analysis

1. **Origin:** Authored locally by the human operator / project author within the LWR character production tooling workspace.
2. **LWR License Status:** The inspected LWR working tree contains no root `LICENSE` file. The associated Korangar repository checkout at `/home/ra/Documents/korangar/` contains `LICENSE.md` under the MIT License.
3. **Rights Assessment:** The code in `ro_reference.py` is original tooling developed for Ragnarok format parsing and character composition. It contains no proprietary Gravity source code, server binaries, or copyrighted client assets.
4. **Standalone RO Sprite Forge License:** `ro-sprite-forge` is licensed under the MIT License (`pyproject.toml: license = "MIT"`). The adapted code is incorporated into the package under the MIT License with provenance attribution.
5. **Asset Separation:** Game assets (ACT/SPR files from Gravity Co., Ltd.) remain strictly external, private, and hash-pinned. No proprietary game assets or GRF archives are included in public distributions or Git tracking.

---

## 3. Selected Components and Capabilities

The following functions and classes from `ro_reference.py` were selected for adaptation:

| Symbol | Original Responsibility | Adapted Location |
|---|---|---|
| `Reader` | Little-endian binary stream reader with bounds checking | `ro_sprite_forge.formats.reader.BinaryReader` |
| `read_act` | ACT 2.4 parser for actions, ordered layers, bounds, anchors, events, delays | `ro_sprite_forge.formats.act.read_act` |
| `write_act` | ACT 2.4 serializer with byte-exact preservation | `ro_sprite_forge.formats.act.write_act` |
| `read_spr` | SPR 2.1 decoder for indexed RLE and truecolor ABGR | `ro_sprite_forge.formats.spr.read_spr` |
| `write_rgba_spr` | SPR 2.1 truecolor serializer (lossy for indexed art) | `ro_sprite_forge.formats.spr.write_rgba_spr` |
| `png_bytes` | Deterministic PNG serialization | `ro_sprite_forge.formats.preview.png_bytes` |
| `only_clip` | Single-visible-layer reference clip extraction | `ro_sprite_forge.formats.preview.only_clip` |
| `place` | Integer-center sprite placement on canvas | `ro_sprite_forge.formats.preview.place` |
| `actor_preview` | Anchor-aligned body/head composition preview | `ro_sprite_forge.formats.preview.actor_preview` |
| `AssetError` | Unhandled error base class | Replaced by typed `ro_sprite_forge.formats.errors.CodecError` (inherits from `ForgeError(ErrorCode.INVALID_INPUT)`) |

---

## 4. Adaptations for Standalone RO Sprite Forge

1. **Package Boundary:** Relocated under `src/ro_sprite_forge/formats/`. A facade module `ro_sprite_forge.formats.ro_reference` preserves the exact audited API for backwards compatibility.
2. **Defensive Validation and Typed Diagnostics:**
   - Replaced generic `ValueError`/`AssetError` with `CodecError`, an instance of `ForgeError` with `ErrorCode.INVALID_INPUT`.
   - Explicit version rejection: non-2.4 ACT versions (e.g., ACT 2.0, 2.1, 2.5) and non-2.1 SPR versions (e.g., SPR 1.0, 2.0, 2.2) fail with actionable diagnostics.
   - Resource limits and budget enforcement: maximum dimensions (1024x1024), aggregate pixel decompression budget (64 MP), maximum action/motion/layer/anchor/event counts.
   - Decompression bounds: strict SPR zero-run RLE overrun and underrun detection.
   - Strict trailing data rejection on both ACT and SPR streams.
3. **Lossless Representation Preservation:**
   - Raw indexed sprite pixels (1 byte per pixel) and 1024-byte palette are preserved in `SprDocument`.
   - Converting indexed art to RGBA is explicitly documented as representation-lossy.
   - Decoupled from mandatory Pillow imports: format structures and binary validation execute cleanly using Python standard library alone.
4. **Path and Dependency Isolation:**
   - Zero hardcoded LWR paths (`REPO`, `HERE`).
   - Zero runtime dependency on LWR, Korangar, rAthena, GRF files, or network services.
