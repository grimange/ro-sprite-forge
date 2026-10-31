# RO Sprite Forge — Quickstart Guide

This guide describes how to install, verify, and run **RO Sprite Forge** from the command line and how to launch the local, human-operated operator workbench.

---

## 1. System Requirements

- **Operating System:** Linux (Ubuntu 22.04+, Debian 12+, Fedora 38+, Arch), macOS 13+, or Windows 10/11.
- **Python:** Python 3.12, 3.13, or 3.14 (declared support matrix).
- **Core Dependencies:** Standard Python library only (`json`, `hashlib`, `pathlib`, `struct`, `http.server`, etc.).
- **Optional Dependencies:**
  - `Pillow` (PIL): Recommended for advanced raster scaling, format conversion, and pixel-level comparisons.
  - `ffmpeg` and `ffprobe` (version 5.0+): Optional for inspecting video candidate frames and extracting PTS timing in video-derived workflows.
  - `rustc` and `cargo`: Optional for building the independent Rust ACT/SPR verification oracle (`tools/oracle-rust`).
- **Web Browser:** Any modern web browser supporting ECMAScript 2020+ (Chromium, Chrome, Firefox, Edge, Safari).

---

## 2. Installation

### Option A: From Pre-built Wheel (Recommended for Operators)

Download the reproducible wheel artifact (e.g. `ro_sprite_forge-0.1.0-py3-none-any.whl`) and install into an isolated virtual environment:

```bash
# Create and activate an isolated virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install the wheel
pip install ro_sprite_forge-0.1.0-py3-none-any.whl

# Verify installation
ro-sprite-forge --version
```

### Option B: From Source (Development / Editable Mode)

Clone the repository and install in editable mode:

```bash
cd ro-sprite-forge
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## 3. Command Line Interface (CLI)

The CLI entry point is `ro-sprite-forge` (or `python3 -m ro_sprite_forge`).

### Overview of Core Commands

| Command | Purpose |
|---|---|
| `inspect` | Audit ACT 2.4 and SPR 2.1 binary resources, reporting frame, slot, and image counts. |
| `plan` | Derive finite action, view, frame, and layer work orders from an actor target. |
| `resolve` | Resolve canonical requirements with declared layer topology. |
| `ledger` | Manage the artwork assignment ledger and display dependency graphs. |
| `coverage` | Evaluate artwork assignment coverage and report missing work orders. |
| `preview` | Composite and inspect multi-layer animation frames. |
| `compile` | Deterministically compile operator-approved replacements into ACT/SPR binaries. |
| `verify` | Validate structural integrity and conformance of compiled assets. |
| `roundtrip` | Perform semantic ACT parse and serialization round-trip checks. |
| `serve` | Start the local HTTP operator workbench server. |

### CLI Sanity Check Examples

```bash
# Display top-level help and available commands
ro-sprite-forge --help

# Inspect an existing ACT/SPR binary pair
ro-sprite-forge inspect --act path/to/sample.act --spr path/to/sample.spr

# Verify ACT round-trip preservation
ro-sprite-forge roundtrip --act path/to/sample.act

# Plan requirements for Male Novice target
ro-sprite-forge plan --actor player --profile male_novice --target-file target.json
```

---

## 4. Launching the Local Operator Workbench

The operator workbench provides a browser-based user interface for visual animation inspection, timeline scrubbing, layered compositing, and visual approvals.

### Starting the Server

```bash
# Start server on default loopback (127.0.0.1:8000)
ro-sprite-forge serve

# Specify a custom port and projects directory
ro-sprite-forge serve --host 127.0.0.1 --port 8080 --projects-dir ./my-projects
```

Alternatively, invoke via Python module:

```bash
python3 -m ro_sprite_forge.service.server --host 127.0.0.1 --port 8000 --projects-dir ./projects
```

### Security and Network Boundaries

> [!IMPORTANT]
> - **Strict Loopback Binding:** The server binds strictly to `127.0.0.1` by default. It is designed exclusively for local, single-operator desktop usage and should **never** be exposed directly to untrusted public networks.
> - **CSRF Protection:** State-mutating API endpoints (`POST`, `PUT`, `DELETE`) require an anti-CSRF token generated per session (`X-CSRF-Token`).
> - **Filesystem Isolation:** All project paths and content blobs are validated against path traversal (`..` escapes) and unauthorized symlink dereferencing.

### Accessing the Workbench

Open your web browser and navigate to:
```
http://127.0.0.1:8000
```

Once loaded, you will see the **RO Sprite Forge Requirements Workbench** featuring:
1. **Left Panel:** Requirements tree navigation with search and status filter buttons (`[!] UNDER`, `[-] UNASSIGNED`, `[x] INVALID`, `[?] REVIEW`, `[✓] READY`).
2. **Center Panel:** Active project metadata, target & topology controls, artwork assignment workspace, and the native-profile animation inspector.
3. **Right Panel:** Orthogonal status dimensions (Availability, Technical Validation, Operator Visual Review, Pinned Runtime Support).
4. **Bottom Bar:** Real-time counters (Slots, Frames, Layers, Sources, Completeness) and export buttons for Work Orders (`TXT` / `JSON`).

---

## 5. Next Steps

- Proceed to the [Production Guide](PRODUCTION_GUIDE.md) to learn the complete artwork creation, assignment, preview, and deterministic compilation workflow.
- Review the [Error Catalog](ERROR_CATALOG.md) to understand diagnostic identifiers and remediation actions.
