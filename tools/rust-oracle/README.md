# Independent ACT/SPR oracle

Optional verification tool; ordinary Python inspection/planning never calls Rust.
The executable accepts original ACT 2.4 and SPR 2.1 paths, writes one deterministic
`rsf.oracle-structure/v1` JSON report, or exits 3 with INVALID_INPUT and no report.
Inputs are read-only, capped at 128 MiB each. Unsupported versions fail closed.

```sh
cd tools/rust-oracle
cargo build --locked
cargo fmt --check
cargo clippy --locked --all-targets -- -D warnings
cargo test --locked
../../.venv/bin/python test_parity.py
../../.venv/bin/python private_parity.py
../../.venv/bin/python parity.py --oracle target/debug/rsf-rust-oracle --act INPUT.act --spr INPUT.spr
```

After fetching dependencies, use `--offline --locked` for Cargo. Pinning is in
rust-toolchain.toml and Cargo.lock. No Python runtime is used by the Rust executable.
The optional Python adapter requires the existing Forge package, not Pillow.
Private hooks use existing RSF_FIXTURE_* environment variables or external fallback
paths. private_parity.py exits nonzero if any audited fixture is NOT_RUN.

The versioned comparison schema retains all supported ACT fields, numeric slot /
frame / layer ordering, raw 40-byte event records and header metadata. Float32
scales and delays are compared as unsigned IEEE bit patterns (including signed
zero); this avoids cross-language JSON float formatting changes without rounding.
No actual field is normalized away. Lists remain ordered. Missing/extra keys,
lengths and values are mismatches with exact JSON locations; a list-length mismatch
reports that location instead of inventing correspondence between different lists.
Numeric ordinals in paths identify action, motion and layer; image records retain
pool/index. The schema embeds both source hashes, versions, full raw palette,
indexed pixels, top-down RGBA and image dimensions/order. Raw truecolor ABGR is
normalized by reversing channels and bottom-up rows. Indexed zero is transparent
black; other indices use palette RGB/alpha255, with the raw palette separately kept.

Python and Rust reports are independently generated from original bytes. The Python
adapter first validates through the inventory engine. Rust preflight validates its
own bounds, exact lengths, RLE and budgets before upstream allocations. Upstream
Korangar decodes ACT/SPR; a supplemental Rust byte pass retains raw events because
upstream Event.name is a decoded String. The adapter validates finite fields,
positive delays, event indices and visible pool-local references. Hidden sprite -1
retains raw pool/mirror metadata. No rendering, encoding or resource mutation occurs.

Canonical report identities use the existing ASCII/sorted/compact JSON + LF
serialization in Python, after each independent report exists. Raw Rust JSON
transport bytes and canonical report bytes are distinct; canonical hashes identify
comparison values. Derived summaries separately account for stored/referenced/unused
identities and decoded-content equivalence; content classes do not change identities.
No paths/times enter either canonical report. Reproducibility is tested only on the
recorded Linux x86_64 toolchain, not asserted across untested platforms.

See PROVENANCE.md for source licensing, pin and deliberate integration changes.
