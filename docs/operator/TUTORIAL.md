# RO Sprite Forge — Synthetic Walk Vertical Slice Tutorial

This end-to-end tutorial guides you through the complete **RO Sprite Forge** workflow using synthetic, redistributable assets. You will create a project, declare layer topology, generate work orders, ingest PNG frames, assign layers, inspect multi-layer compositing on checkerboard backgrounds, record visual approval, compile deterministic ACT/SPR assets, and simulate crash recovery.

---

## Tutorial Prerequisites

Ensure you have installed RO Sprite Forge and can launch the local workbench:

```bash
# Activate your environment
source .venv/bin/activate

# Verify installation
ro-sprite-forge --version

# Start the local workbench server
ro-sprite-forge serve --port 8000 --projects-dir ./projects
```

Open `http://127.0.0.1:8000` in your web browser.

---

## Step 1: Create a New Project

1. In the top bar, click **"+ New Project"**.
2. Fill in the project details:
   - **Project Identifier (Slug):** `novice-walk-tutorial`
   - **Display Name:** `Male Novice Walk Tutorial`
   - **Actor Template:** `Player Character (Novice / Job)`
   - **Actor Profile:** `male_novice`
3. Click **"Create Project"**.
4. The workbench will load the project in Revision 0.

---

## Step 2: Declare Target and 2-Layer Topology

By default, a new project has no declared topology and displays:
`[!] UNDERSPECIFIED_LAYER_TOPOLOGY`

1. Click **"⚙️ Define Target & Topology"** in the center toolbar.
2. Configure the target:
   - **Target Scope:** Select `walk` (the bounded Walk vertical slice: 8 views × 8 frames).
   - **Layer Topology:** Declare two ordered layers:
     ```json
     [
       {"index": 0, "name": "shadow", "role": "shadow"},
       {"index": 1, "name": "body", "role": "main"}
     ]
     ```
3. Click **"Save Target & Topology"**.
4. The alert banner clears. The status badge updates to `[-] UNASSIGNED`.

---

## Step 3: Inspect the Work Order

Now that topology is declared, RO Sprite Forge calculates the exact work order:
- **Slots:** 8 slots (Action Group 1: Walk, Views 0 through 7).
- **Frames:** 64 motion frames (8 views × 8 frames per view).
- **Layers:** 128 layer occurrences (64 frames × 2 layers: shadow + body).
- **Unassigned:** 128 unassigned occurrences.

### Exporting Work Order
Click **"📥 Work Order (TXT)"** in the bottom panel. Open the downloaded file to see the checklist of required occurrences:
```
player.male_novice.walk.south.frame_0.layer_0 (shadow)
player.male_novice.walk.south.frame_0.layer_1 (body)
player.male_novice.walk.south.frame_1.layer_0 (shadow)
player.male_novice.walk.south.frame_1.layer_1 (body)
...
```

---

## Step 4: Ingest Authored PNG Frames

You can generate synthetic frames or import authored PNG files. In this tutorial, we will use Python to generate a minimal set of synthetic PNGs:

```python
# Create a synthetic 32x32 body frame
from PIL import Image
import os

os.makedirs("/tmp/tutorial_frames", exist_ok=True)
for i in range(8):
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    # Draw simple colored box representing character body motion
    for x in range(10, 22):
        for y in range(8 + i, 24):
            img.putpixel((x, y), (50, 120, 220, 255))
    img.save(f"/tmp/tutorial_frames/walk_south_{i}.png")
```

### Ingesting via Workbench
1. In the workbench, expand **"Import ordered PNG sequence"**.
2. Set **Sequence ID:** `walk-south-body`.
3. Set **Sequence Name:** `Walk South Body Frames`.
4. Select all 8 files from `/tmp/tutorial_frames/`.
5. Click **"Natural sort by filename"** to verify ordinals 0 through 7.
6. Click **"Import verified sequence"**.
7. The files are securely hashed and stored into content-addressed blobs (`blobs/<sha256>`).

---

## Step 5: Assign Artwork in the Ledger

### Direct Source Mapping (South Body Layer)
1. In the Left Navigation Tree, expand:
   `Walk (8) ──► South (0) ──► Frame 0 ──► Layer 1 (body)`.
2. In the center panel, under **"Existing source tray"**, select `walk-south-body-0`.
3. Click **"Review direct mapping"**.
4. Confirm the mapping prompt. The project advances to the next revision.
5. Repeat or use the batch mapping textarea to assign frames 1 through 7.

### Explicit Reuse with Horizontal Mirroring (South-East Mirrors South-West)
When assigning the South-East view (View 7):
1. Select `Walk ──► South-East (7) ──► Frame 0 ──► Layer 1 (body)`.
2. Under **"Explicit reuse"**, select the corresponding South-West assignment.
3. Check **"Explicit horizontal mirror (executed preview)"**.
4. Click **"Review reuse mapping"**.
5. Forge records the reuse dependency with an explicit `mirror_x` recipe.

---

## Step 6: Multi-Layer Preview & Alpha Inspection

1. Scroll to **"Native-profile animation inspection"**.
2. Select your imported resource.
3. Choose **Action group:** `Walk` and **View:** `0 (South)`.
4. Click **"▶ Play"** or press `Space` to start animation playback.
5. Inspect the animation:
   - Press `Left Arrow` / `Right Arrow` to step frame-by-frame.
   - Use the **Zoom** dropdown (or press `+` / `-`) to inspect at `2× (200%)` and `4× (400%)` nearest-neighbor integer scale.
   - Use the **Background** dropdown (or press `B`) to switch between **Checkerboard (Dark)**, **Checkerboard (Light)**, and **Solid White** to verify edge transparency and alpha clipping.

---

## Step 7: Operator Visual Review and Approval

Remember: An automated test checks data structure—**only the human operator can approve visual art**.

1. Under **"Operator visual decision"**, choose **Exact review scope:** `view` (to approve all 8 frames of Walk South at once).
2. Click **"Inspect review scope"**.
3. In the modal dialog, review the composited frames.
4. Click **"[A] Approve displayed scope"** (or press key `A`).
5. The review status updates to `[✓] APPROVED`. The approval is cryptographically sealed against the current composition SHA-256 digest.

---

## Step 8: Deterministic ACT/SPR Compilation

1. Scroll down and expand **"Deterministic ACT/SPR compiler & replacement writer"**.
2. Select:
   - **Base ACT/SPR resource:** Your imported base resource.
   - **Compilation ID:** `novice-walk-v1`.
   - **Compilation mode:** `bounded_replacement`.
   - **SPR pool policy:** `preserve_pool`.
   - **Shared SPR isolation:** `auto` (CoW append).
3. Click **"Inspect compilation plan"**.
   - Verify: `ready_to_compile: true`, `blockers: 0`.
4. Click **"Compile modified ACT/SPR"**.
5. Forge writes the compiled `.act` and `.spr` binaries atomically to `blobs/` and runs post-write decode verification:
   - `decode_after_write: true`
   - `export_ready: true`

---

## Step 9: Simulate Interruption & Crash Recovery

Let's test Forge's disaster recovery mechanism:

1. In your terminal, simulate an accidental corruption of the active manifest:
   ```bash
   # Introduce deliberate corruption into manifest.json
   echo "CORRUPTED_BYTES_%%@@!" > ./projects/novice-walk-tutorial/manifest.json
   ```
2. In Python, run the crash recovery routine:
   ```python
   from ro_sprite_forge.core.project import recover_project

   report = recover_project("./projects", "novice-walk-tutorial")
   print(report)
   ```
3. Observe the output:
   ```json
   {
     "project_id": "novice-walk-tutorial",
     "recovered": true,
     "already_healthy": false,
     "action": "RESTORED_FROM_BACKUP",
     "reason": "Corrupted or missing manifest restored from valid backup 'manifest.json.bak'.",
     "restored_from": "manifest.json.bak",
     "valid": true
   }
   ```
4. Refresh your workbench browser: the project is completely intact with zero lost assignments or corrupted state!

---

## Summary

You have successfully:
- Enforced layer topology before artwork production.
- Exported an exact missing-art checklist.
- Ingested PNG frames into content-addressed immutable storage.
- Mapped direct sources and explicit mirrored reuse.
- Inspected animations at 1x/2x/4x nearest-neighbor zoom across multiple backgrounds.
- Recorded a cryptographically bound visual approval.
- Deterministically compiled replacement ACT/SPR assets.
- Validated crash-safe recovery from automated backups.
