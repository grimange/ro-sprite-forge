# RO Sprite Forge — Third-Party Notices and Provenance

## Project Notice
RO Sprite Forge  
Copyright (c) 2026 Ronniel Allan Castañito.  
Licensed under the MIT License (see LICENSE).

RO Sprite Forge is a standalone, local, human-operated requirements planner,
animation inspection workbench, and deterministic SPR/ACT asset compiler.

---

## 1. Living-World-Ragnarok (LWR) Codec Extraction
Portions of the ACT 2.4 and SPR 2.1 codecs in `ro_sprite_forge.formats` and
`ro_sprite_forge.core` were adapted from character production tooling
(`tools/character_production/ro_reference.py`) in the Living-world-Ragnarok
repository.

- **Author:** Ronniel Allan Castañito
- **License:** MIT License
- **Reused Source Snapshot SHA-256:** `55aefdc8ba7bb5aaf4619983d72cb26c2865154961116c8ad075c65378142c46`
- **Full Provenance Record:** `docs/provenance/LWR_CODEC_PROVENANCE.md`

---

## 2. Pinned Korangar Independent Decoding Oracle
The independent verification oracle located in `tools/rust-oracle/` contains
vendored Rust code from Korangar (https://github.com/vE5li/korangar):

- **Copyright:** (c) 2023 Lucas Pütz
- **License:** MIT License (`tools/rust-oracle/vendor/LICENSE.md`)
- **Pinned Upstream Commit:** `3f3d88a583203f09d079712f43343c1041258ffd`
- **Scope:** Used exclusively as an independent verification oracle and testing fixture.
  The oracle is NOT included in the production wheel distribution.
- **Full Provenance Record:** `tools/rust-oracle/PROVENANCE.md`

---

## 3. Proprietary Game Assets and Intellectual Property Separation
- Ragnarok Online assets, sprites (SPR), action files (ACT), and GRF archives are
  the proprietary intellectual property of Gravity Co., Ltd. and Lee Myung-jin.
- **Strict Separation Policy:** RO Sprite Forge does NOT distribute any proprietary
  Gravity assets, client binaries, or GRF archives.
- All bundled examples, test suites, and public CI artifacts use synthetic,
  clean-room, legally redistributable assets only.
- Private fixture hooks and local lawful reference comparisons remain strictly optional,
  isolated outside Git and public distributions, and are classified as `NOT_RUN` when absent.

---

## 4. Third-Party Dependencies and Tooling

### Core Package (Standard Library Only)
The core package `ro-sprite-forge` has zero mandatory runtime dependencies (`dependencies = []`),
running entirely on Python 3.12+ standard library modules.

### Optional and Development Dependencies
- **Pillow** (optional `image` extra / test dependency):
  Copyright (c) 1997-2024 by Secret Labs AB and contributors.
  License: HPND License / PIL Software License.
- **jsonschema** (optional `validation` extra / test dependency):
  Copyright (c) Julian Berman.
  License: MIT License.
- **setuptools / wheel / packaging / build** (build-system dependencies):
  License: MIT / Apache-2.0 / PSF License.
- **FFmpeg / FFprobe** (optional media extraction tool):
  License: LGPL 2.1+ / GPL 2+.
  FFmpeg is an external system executable; no FFmpeg binaries are distributed with RO Sprite Forge.

---

## 5. Source Ownership and Publication Policy
Any source module or asset lacking explicit ownership review or permissive licensing is
strictly prohibited from publication and release packaging.
