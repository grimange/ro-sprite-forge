# RO Sprite Forge

Standalone local, human-operated sprite tooling. RSF-1–4 provide the installable
foundation, bounded SPR 2.1 / ACT 2.4 decoding, canonical resource inventory and
finite declared-target work orders, byte preservation and bounded ACT semantic verification.
Independent Rust/native gates and compilation are later tasks.
Python 3.12–3.14 is supported (`>=3.12,<3.15`). There are no runtime dependencies.
No LWR checkout, GRF, private fixture, client, server or network service is needed.

## Installation and development

Use a virtual environment; never install build tools globally:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m pip install --no-deps --no-build-isolation -e .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m build --no-isolation
```

Build tools and their complete dependency set are pinned in
`requirements-build.txt`; optional codec-preview tests use pinned Pillow in
`requirements-test.txt` (inventory and requirements need only the standard library).
The backend requirements are also pinned in
`pyproject.toml`. Initial tool acquisition needs an index or a pre-populated
wheelhouse; application execution and wheel installation need no network.
For offline setup, add `--no-index --find-links /path/to/wheelhouse` to the
requirements installation. Install a built wheel into another virtual environment
with `python -m pip install --no-index --no-deps /path/to/ro_sprite_forge-0.1.0-py3-none-any.whl`.

Run the automated build, archive inspection, repeated wheel-hash comparison,
isolated offline installation and external-directory test suite with:

```sh
.venv/bin/python tests/check_distribution.py --wheelhouse /path/to/test-wheels --python /path/to/python3.12 --python /path/to/python3.13 --python /path/to/python3.14
```

Provide a Pillow 12.1.1 wheel for each interpreter in the test wheelhouse. All
test environments and artifacts are temporary. The script prints actual
commands, results and artifact SHA-256 values. Repeated wheel equality is checked
under a fixed `SOURCE_DATE_EPOCH` and the pinned toolchain on the same platform;
this is packaging reproducibility, not a future SPR/ACT deterministic-build gate.

## CLI contracts

`ro-sprite-forge --help`, `ro-sprite-forge --version` and
`python -m ro_sprite_forge --help` are supported. Each command has its own help.
`argparse` is used because these bounded commands need no external CLI framework.

| Command | Required arguments | Behavior |
| --- | --- | --- |
| `inspect` | `--act FILE --spr FILE --json NEW_FILE` | Produce canonical inventory; optional `--actor`, `--part`, `--runtime-profile player\|npc\|monster\|unverified` |
| `plan` | `--inventory FILE --profile FILE --target FILE --output NEW_FILE` | Produce exact or provisional finite requirements |
| `verify` | `--act FILE --spr FILE` | Validate structure/references and ACT semantic roundtrip; canonical JSON on stdout |
| `roundtrip` | `--act FILE --spr FILE --output-act NEW_FILE --output-spr NEW_FILE` | Preserve original bytes; optional `--mode act-semantic` serializes ACT, SPR remains unchanged |

The CLI checks argument syntax, existing regular input files (or a project directory),
and new, distinct output paths whose parent directories exist. It rejects existing
outputs, including dangling symlinks, without overwriting them. Input symlinks are
followed for file-kind checks. `inspect` and `plan` read at most 128 MiB per input,
validate content and publish reports atomically without replacing existing files.
Invalid inputs create no report or resource output. `verify` creates no files;
`roundtrip` publishes validated new resources and reports source/output hashes.
Legacy `verify --project DIRECTORY --scope full|declared` remains NOT_IMPLEMENTED.
No command modifies source ACT/SPR resources. See the
[RSF-4 contract](docs/architecture/RSF4_PRESERVATION.md) for policy, independent
test coverage, unsupported conversions and publication limits.

See [the versioned contracts](docs/architecture/RSF3_CONTRACTS.md) for target
examples, exact topology rules, canonical hashing and report status semantics.
`plan` accepts a frozen profile JSON file; extract it from an inventory made with
the appropriate `--runtime-profile`:

```sh
ro-sprite-forge inspect --act actor.act --spr actor.spr --actor my-actor --part body --runtime-profile player --json inventory.json
python -c 'import json; from pathlib import Path; from ro_sprite_forge.core.canonical import canonical_bytes; p=json.loads(Path("inventory.json").read_bytes())["runtime_profile"]; Path("profile.json").write_bytes(canonical_bytes(p))'
ro-sprite-forge plan --inventory inventory.json --profile profile.json --target target.json --output requirements.json
```

A valid provisional report exits 0; consumers must inspect `status.work_order`
and diagnostics. Exact specification is separate from artwork coverage, operator
approval, runtime selection and native proof. No assignments or approvals are inferred.

Errors are a single JSON object on stderr, with empty stdout:

```json
{"error": {"code": "NOT_IMPLEMENTED", "message": "..."}}
```

The error object includes `path` when applicable. Stable codes are
`INVALID_ARGUMENT`, `INPUT_NOT_FOUND`, `INVALID_INPUT`, `INVALID_OUTPUT`,
`IO_ERROR` and `NOT_IMPLEMENTED`. Exit statuses: 0 for help/version or a produced
report; 2 for argument errors; 3 for input/contract/filesystem errors; 4 for unimplemented operations.
No abbreviated options are accepted. Unexpected programming defects are not
converted into successful results.

## Boundaries and fixtures

`src/ro_sprite_forge/core` contains pure inventory, frozen profiles, requirements,
canonical serialization and typed errors. It imports no CLI, filesystem, HTTP,
rendering or external-tool adapter. The CLI and `report_io` own argument parsing,
bounded filesystem access and publication. The version has one source
in `ro_sprite_forge.__version__`.

`tests/test_*.py` create deterministic synthetic inputs in temporary
directories; no proprietary resources are needed. `tests/synthetic` documents
public fixture policy. `tests/private_fixture_hooks` contains external optional
private codec/inventory regressions and is excluded from distributions. Run with
`python -m unittest discover -s tests/private_fixture_hooks -v` when fixtures are
available; missing fixtures explicitly skip. Original RO
assets and private fixtures must stay outside public deliverables.

The existing `compile` command supports canonical build manifests and immutable artifact
caching with `--cache-dir CACHE --output-dir OUTPUT`. Production mode requires complete
approved full-profile inputs and atomic directory publication. Bounded output carries
`PARTIAL_DIAGNOSTIC` status and a bundle marker. See
[the canonical build contract](docs/verification/rsf-25/CONTRACT.md) for exact ordering,
toolchain pins, export gates and evidence separation. Native Korangar verification
remains a separate gate.

## Video candidates in the local workbench

With a project open, expand **Import video candidate frames** in the assignment workspace.
Select a local file (up to 32 MiB) or an already staged video, inspect metadata, and
choose its absolute video-stream index. A single video stream is selected automatically;
multiple video streams require an explicit choice. Metadata inspection does not decode
the frame list. Use the separate bounded frame-inspection action when needed.

Choose exact presentation ordinals or exact integer PTS values, in the desired output
order. For example, the synthetic VFR fixture has PTS `0, 40, 120, 160, 300` with time
base `1/1000`; requesting `300, 0, 120` selects ordinals `4, 0, 2`. Preview displays the
actual extracted PNGs and their requested/resolved identities. Reordering or removing a
candidate requires another preview. Only **Confirm order and stage candidates** commits the
ordered collection and refreshes the existing source tray. Assign sources explicitly
through the usual requirement controls; extraction creates no assignments or reviews.

Media HTTP records transport exact integers as canonical decimal strings. The accepted
RSF-28 selection bound remains ±(2^53−1); requests beyond it fail explicitly. Larger
source metadata is displayed losslessly and retained on project save/reopen. Source PTS,
candidate order, and ACT/runtime playback timing remain independent. Existing versioned
crop, placement and alpha recipes provide before/after preview and scoped review
invalidation for these images too.

FFprobe/FFmpeg are optional and checked only when video capabilities are requested.
Missing tools disable video controls while PNG import and ordinary project work remain
available. Existing extraction bounds apply: 64 selected candidates, 4,096 inspected
frames, 120 seconds of source presentation span and bounded subprocess/output budgets.
The loopback HTTP service retains its Host/Origin/CSRF and revision checks. Preview is
temporary; staging re-extracts and verifies the preview identity before publication.
An unsuccessful project save may leave unreferenced immutable blobs, without committing
a partial candidate collection. See [RSF-29 evidence](docs/verification/rsf-29/REPORT.md).
