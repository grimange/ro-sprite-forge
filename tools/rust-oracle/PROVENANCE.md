# Pinned Korangar source

Repository: https://github.com/vE5li/korangar (local fork https://github.com/grimange/korangar).
Revision: `3f3d88a583203f09d079712f43343c1041258ffd`.
Actual local HEAD and `git show REV:path` were checked. `ragnarok-formats`,
`ragnarok-bytes` and `ragnarok-macros` upstream versions are 0.1.0, edition2024.
MIT source license, copyright 2023 Lucas Pütz, retained in vendor/LICENSE.md.
Game assets have separate rights and are not vendored.

`vendor/source-hashes.json` pins every copied upstream Rust source file. Files
were extracted with git show, not copied from a potentially modified working tree.
All copied .rs source bytes are unchanged. ragnarok-formats includes only action,
sprite, signature and version modules. Its lib.rs is an adapter module list with
the original required feature gates, excluding unrelated format/UI modules.
Crate manifests are explicit local dependency adaptations, excluding optional UI
and unrelated bitflags dependencies. The two other crate source trees are retained.
Cargo.lock pins registry dependencies/checksums; no live upstream checkout is needed.
The complete Korangar application and its workspace were not compiled or modified.

The upstream toolchain nightly-2026-02-01 is pinned here: rustc1.95.0-nightly
(905b92696 2026-01-31). Nightly is necessary for upstream ragnarok-bytes
array_try_from_fn and ragnarok-formats const parameter features. Cargo dependency
identities are in Cargo.lock, including cgmath0.18.0 and encoding_rs0.8.35.

Upstream ActionsData exposes all ordered ACT records, except its Event.name String
cannot preserve raw event bytes. The supplemental bounded Rust pass extracts those
exact 40-byte records. Upstream still decodes the entire ACT, including events.
Upstream SpriteData yields original indices, palette and raw ABGR truecolor, which
this adapter explicitly normalizes. The upstream indexed writer panics; it is never
called. No upstream writer is used, and no source resource is rewritten.

Preflight adds exact version/length validation, Forge count/pixel budgets and strict
RLE run validation before upstream parsing. This prevents upstream zero-dimension,
allocation and compressed counter edge cases from becoming accepted inputs. Pair
reference/finite/event/timing checks are Rust-side, never delegated to Python.
The harness is an independent decoding oracle, not a native renderer or second core.
