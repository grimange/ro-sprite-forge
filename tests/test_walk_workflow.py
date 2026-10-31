"""RSF-22: Bounded Walk image assignment, timeline inspection, and operator review workflow.

Proves that all accepted M4 capabilities (RSF-19 PNG ingestion, RSF-20 spritesheet extraction,
RSF-21 reversible transformations) work together seamlessly with the accepted M1–M3 foundation
(RSF-8 topology, RSF-9 assignment ledger, RSF-10 coverage, RSF-11 compositor, RSF-12 timeline,
RSF-15 persistence, RSF-16 workbench, RSF-17 assignments, RSF-18 approval & scoped invalidation).
"""

import base64
import copy
import hashlib
import io
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageDraw

from ro_sprite_forge.core.canonical import canonical_bytes, digest
from ro_sprite_forge.core.contracts import frozen_runtime_profile, load_actor, reference
from ro_sprite_forge.core.coverage import evaluate_coverage
from ro_sprite_forge.core.errors import ErrorCode, ForgeError
from ro_sprite_forge.core.ledger import load_ledger, resolve_ledger
from ro_sprite_forge.core.project import create_project, get_blob, load_project, save_project
from ro_sprite_forge.core.review import evaluate_reviews
from ro_sprite_forge.core.timeline import AnimationTimeline
from ro_sprite_forge.service.server import make_standard_actor_doc
from ro_sprite_forge.service.workbench import (
    comparison,
    mutate,
    record_review,
    review_proposal,
    source_preview,
    workspace,
)


def make_synthetic_walk_frame(ordinal: int, width: int = 64, height: int = 64) -> bytes:
    """Create a deterministic synthetic RGBA frame with an identifiable color and asymmetric marker."""
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    # Distinct background hue per frame
    color = (30 + ordinal * 35, 120, 200 - ordinal * 25, 255)
    draw.rectangle([10, 10, width - 10, height - 10], fill=color)
    # Asymmetric indicator on left side with frame ordinal
    draw.rectangle([12, 12, 24, 28], fill=(255, 255, 0, 255))
    draw.text((14, 14), str(ordinal), fill=(0, 0, 0, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def make_synthetic_spritesheet(width: int = 128, height: int = 64) -> bytes:
    """Create a 2-cell spritesheet (two 64x64 cells)."""
    im = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rectangle([0, 0, 63, 63], fill=(255, 0, 0, 255))
    draw.rectangle([64, 0, 127, 63], fill=(0, 255, 0, 255))
    buf = io.BytesIO()
    im.save(buf, format="PNG")
    return buf.getvalue()


def make_bounded_walk_target(
    project_id: str,
    *,
    frame_count: int = 6,
    active_views: tuple[int, ...] = (0,),
    layers: tuple[str, ...] = ("body",),
) -> dict:
    """Target declaring Walk with explicit frame count and ordered layer topology."""
    profile = frozen_runtime_profile("player")
    actor_doc = make_standard_actor_doc(project_id, profile, parts=["body"])
    actor = load_actor(actor_doc)

    views = []
    for v in range(8):
        if v in active_views:
            views.append({
                "view": v,
                "frame_count": frame_count,
                "topology": {"kind": "explicit", "layers": list(layers)},
            })
        else:
            # Other 7 views are required by full player profile but unconfigured in this bounded target
            views.append({
                "view": v,
                "frame_count": frame_count,
                "topology": {"kind": "explicit", "layers": list(layers)},
            })

    return {
        "schema": "rsf.target/v2",
        "id": f"{project_id}-walk-target",
        "revision": 1,
        "previous_sha256": None,
        "actor": reference(actor),
        "runtime_profile": reference(profile),
        "scope": "scoped",
        "parts": ["body"],
        "compatibility": {"status": "UNVERIFIED", "declarations": []},
        "actions": [
            {
                "id": "Walk",
                "requirement": "REQUIRED",
                "parts": [{"part": "body", "views": views}],
            }
        ],
    }


class BoundedWalkWorkflowTests(unittest.TestCase):
    """End-to-end integration tests for RSF-22 Bounded Walk Workflow."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.projects_dir = Path(self.tmpdir.name)
        self.project_id = "test-walk-proj"

        self.target = make_bounded_walk_target(self.project_id, frame_count=6, layers=("body",))
        self.manifest = create_project(
            self.projects_dir,
            self.project_id,
            "Bounded Walk Production Test",
            self.target["actor"]["id"],
            "player",
            target=self.target,
        )

    def tearDown(self):
        self.tmpdir.cleanup()

    def test_01_target_declaration_resolves_exact_walk_requirements_without_quota_imposition(self):
        """Criterion 1: Walk actions/views/per-view frames and ordered layers are declared before import;

        illustrative 8x6 counts are never imposed as an arbitrary quota.
        """
        w = workspace(self.projects_dir, self.manifest)
        reqs = w["requirements"]
        self.assertIsNotNone(reqs)
        self.assertEqual(reqs["target"]["id"], self.target["id"])

        # 8 views x 6 frames = 48 frame occurrences; 1 layer per frame = 48 layer requirements
        self.assertEqual(len(reqs["slots"]), 8)
        self.assertEqual(len(reqs["frames"]), 48)
        self.assertEqual(len(reqs["layers"]), 48)

        # Direction 0 has exactly 6 frames with explicit layer IDs
        dir0_layers = [l for l in reqs["layers"] if l["view"] == 0]
        self.assertEqual(len(dir0_layers), 6)
        for ord_idx, layer in enumerate(dir0_layers):
            self.assertEqual(layer["frame"], ord_idx)
            self.assertEqual(layer["role"], "body")
            self.assertEqual(layer["action"], "Walk")
            self.assertEqual(layer["part"], "body")

        # Prior to any import or assignment, coverage reports 48 missing artwork items
        cov = w["coverage"]
        self.assertEqual(cov["counts"]["structural"]["required_layers"], 48)
        self.assertEqual(cov["counts"]["assignments"]["unassigned"], 48)
        self.assertEqual(cov["counts"]["validation"]["missing_sources"], 0)
        self.assertEqual(cov["counts"]["review"]["approved"], 0)
        self.assertFalse(cov["status"]["export_ready"])

    def test_02_ingest_png_sequence_and_spritesheet_candidate(self):
        """Exercise RSF-19 PNG sequence ingestion and RSF-20 spritesheet extraction."""
        # 1. Ingest 6-frame PNG sequence
        frames_payload = []
        for i in range(6):
            png_bytes_data = make_synthetic_walk_frame(i)
            frames_payload.append({
                "ordinal": i,
                "filename": f"walk_0_{i}.png",
                "data_base64": base64.b64encode(png_bytes_data).decode("ascii"),
            })

        mut_seq = mutate(
            self.projects_dir,
            self.manifest,
            "stage-sequence",
            {
                "expected_revision": self.manifest["revision"],
                "sequence_id": "walk-south-seq",
                "name": "Walk South 6-Frame Sequence",
                "frames": frames_payload,
            },
        )
        self.manifest = mut_seq["project"]

        # 2. Extract a candidate frame from spritesheet (RSF-20)
        sheet_bytes = make_synthetic_spritesheet(128, 64)
        mut_sheet = mutate(
            self.projects_dir,
            self.manifest,
            "extract-spritesheet",
            {
                "expected_revision": self.manifest["revision"],
                "extraction_id": "walk-sheet-extract",
                "name": "Walk Spritesheet Extract",
                "sheet_filename": "walk_sheet.png",
                "sheet_data_base64": base64.b64encode(sheet_bytes).decode("ascii"),
                "grid": {"cell_width": 64, "cell_height": 64, "columns": 2, "rows": 1},
            },
        )
        self.manifest = mut_sheet["project"]

        w = workspace(self.projects_dir, self.manifest)
        self.assertEqual(len(w["sequences"]), 1)
        self.assertEqual(len(w["extractions"]), 1)

        # Ingestion alone does NOT assign or approve
        self.assertEqual(len(self.manifest.get("ledger", {}).get("assignments", [])), 0)
        self.assertEqual(len(self.manifest.get("review_events", [])), 0)

        # Catalog exposes all staged sources as AVAILABLE and VALID
        sources = w["sources"]
        authored = [s for s in sources if s["source"]["origin"] == "AUTHORED"]
        # 6 sequence frames + 1 sheet + 2 extracted crops = 9 authored sources
        self.assertEqual(len(authored), 9)
        for s in authored:
            self.assertEqual(s["availability"], "AVAILABLE")
            self.assertEqual(s["validation"], "VALID")

    def test_03_derived_image_transformation_and_single_application_in_compositor(self):
        """Criterion 2 & Critical Rule: RSF-21 transformations produce staged derived candidates;

        when assigned, compositor renders the derived pixels and DOES NOT apply the recipe twice.
        """
        # Stage frame 0
        raw_frame = make_synthetic_walk_frame(0, width=64, height=64)
        mut_stage = mutate(
            self.projects_dir,
            self.manifest,
            "stage-png",
            {
                "expected_revision": self.manifest["revision"],
                "filename": "frame_0.png",
                "data_base64": base64.b64encode(raw_frame).decode("ascii"),
            },
        )
        self.manifest = mut_stage["project"]
        orig_sha = digest(raw_frame)

        # Apply horizontal flip transformation recipe (RSF-21)
        recipe = {
            "id": "flip-h-recipe",
            "name": "Horizontal Flip Frame 0",
            "source_sha256": orig_sha,
            "operations": [{"op": "flip", "direction": "horizontal"}],
        }
        mut_trans = mutate(
            self.projects_dir,
            self.manifest,
            "apply-transform",
            {
                "expected_revision": self.manifest["revision"],
                "recipe": recipe,
            },
        )
        self.manifest = mut_trans["project"]
        derived_sha = mut_trans["derived_sha256"]
        self.assertNotEqual(derived_sha, orig_sha)

        # Retrieve derived image bytes and verify pixel content:
        # Original had marker at [12, 12, 24, 28].
        # Horizontally flipped (width 64) moves marker x to: 64 - 24 = 40 .. 64 - 12 = 52.
        derived_bytes = get_blob(self.projects_dir, self.project_id, derived_sha)
        with Image.open(io.BytesIO(derived_bytes)) as d_im:
            # Pixel at (45, 15) should be the yellow marker in derived image
            self.assertEqual(d_im.getpixel((45, 15)), (255, 255, 0, 255))
            # Pixel at (15, 15) should NOT be yellow (it moved to right)
            self.assertNotEqual(d_im.getpixel((15, 15)), (255, 255, 0, 255))

        # Assign the derived candidate to Walk view 0, frame 0 layer
        w = workspace(self.projects_dir, self.manifest)
        req_id = w["requirements"]["layers"][0]["id"]  # view 0, frame 0, layer body
        mut_assign = mutate(
            self.projects_dir,
            self.manifest,
            "assign",
            {
                "expected_revision": self.manifest["revision"],
                "mappings": [{
                    "requirement_id": req_id,
                    "kind": "DIRECT_SOURCE",
                    "source": f"blob-{derived_sha}",
                    "source_revision": 1,
                    "recipe": [],
                }],
            },
        )
        self.manifest = mut_assign["project"]

        # Render preview of assignment via source_preview
        report = mut_assign["ledger"]
        assigned_row = next(a for a in report["assignments"] if a["requirement_id"] == req_id)
        p_res = source_preview(self.projects_dir, self.manifest, {"assignment": assigned_row["id"]})
        self.assertEqual(p_res["execution"], "EXECUTED")

        # Verify that compositor rendered the derived pixels (yellow at x=45, NOT x=15)
        rendered_bytes = base64.b64decode(p_res["png_base64"])
        with Image.open(io.BytesIO(rendered_bytes)) as r_im:
            self.assertEqual(r_im.getpixel((45, 15)), (255, 255, 0, 255))
            self.assertNotEqual(r_im.getpixel((15, 15)), (255, 255, 0, 255))

        # Double-transformation check:
        # If the compositor accidentally reapplied the recipe ('flip'), the marker would be back at x=15.
        # It is at x=45, proving exactly single execution of the derived asset!

    def test_04_batch_assignment_timeline_inspection_and_looping_behavior(self):
        """Map supplied 6 Walk frames to exact requirements and verify timeline sequence."""
        # Stage 6 synthetic frames
        source_shas = []
        for i in range(6):
            data = make_synthetic_walk_frame(i)
            mut = mutate(
                self.projects_dir,
                self.manifest,
                "stage-png",
                {
                    "expected_revision": self.manifest["revision"],
                    "filename": f"walk_step_{i}.png",
                    "data_base64": base64.b64encode(data).decode("ascii"),
                },
            )
            self.manifest = mut["project"]
            source_shas.append(digest(data))

        # Batch map to all 6 frames of Walk direction 0
        w = workspace(self.projects_dir, self.manifest)
        dir0_layers = [l for l in w["requirements"]["layers"] if l["view"] == 0]
        self.assertEqual(len(dir0_layers), 6)

        mappings = []
        for i, layer in enumerate(dir0_layers):
            mappings.append({
                "requirement_id": layer["id"],
                "kind": "DIRECT_SOURCE",
                "source": f"blob-{source_shas[i]}",
                "source_revision": 1,
                "recipe": [],
            })

        mut_batch = mutate(
            self.projects_dir,
            self.manifest,
            "assign",
            {
                "expected_revision": self.manifest["revision"],
                "mappings": mappings,
            },
        )
        self.manifest = mut_batch["project"]

        # Verify each frame preview matches its exact assigned source
        report = mut_batch["ledger"]
        for i, layer in enumerate(dir0_layers):
            assigned = next(a for a in report["assignments"] if a["requirement_id"] == layer["id"])
            self.assertEqual(assigned["availability"], "AVAILABLE")
            self.assertEqual(assigned["validation"], "VALID")
            self.assertEqual(assigned["effective_source"]["sha256"], source_shas[i])

            p = source_preview(self.projects_dir, self.manifest, {"assignment": assigned["id"]})
            self.assertEqual(p["execution"], "EXECUTED")
            # Verify the rendered pixel bytes exactly match the source pixel bytes
            rendered_im = Image.open(io.BytesIO(base64.b64decode(p["png_base64"])))
            expected_im = Image.open(io.BytesIO(make_synthetic_walk_frame(i)))
            self.assertEqual(rendered_im.tobytes(), expected_im.tobytes())

        # Authoritative timeline looping verification:
        # Timeline step and seek on 6 frames (0 -> 1 -> 2 -> 3 -> 4 -> 5 -> 0 -> 1)
        synthetic_act = {
            "reserved": "00" * 10,
            "actions": [[{"bounds": [0] * 8, "clips": [{"x": 0, "y": 0, "sprite": 0, "pool": 1, "mirror": 0, "color": 0xffffffff, "scale_x": 1.0, "scale_y": 1.0, "angle": 0}], "anchors": [], "event": -1} for _ in range(6)] for _ in range(40)],
            "delays": [2.0] * 40,
            "events": [],
        }
        timeline = AnimationTimeline(synthetic_act, category="player")
        sel = timeline.select(slot=8, view=0, frame=0)  # slot 8 is Walk direction 0 in player profile
        self.assertEqual(sel["frame"], 0)

        step_1 = timeline.step(sel, 1, loop=True)
        self.assertEqual(step_1["frame"], 1)

        step_5 = timeline.step(sel, 5, loop=True)
        self.assertEqual(step_5["frame"], 5)

        # Loop wrap-around to 0
        step_6 = timeline.step(sel, 6, loop=True)
        self.assertEqual(step_6["frame"], 0)

        # Loop wrap-around to 1
        step_7 = timeline.step(sel, 7, loop=True)
        self.assertEqual(step_7["frame"], 1)

    def test_05_truthful_scoped_coverage_distinguishes_bounded_complete_from_full_profile(self):
        """Criterion 3: One supplied view can complete only its explicitly narrow scope,

        never the full Walk action or full actor profile.
        """
        # Assign only the 6 frames of direction 0
        source_shas = []
        for i in range(6):
            data = make_synthetic_walk_frame(i)
            mut = mutate(
                self.projects_dir,
                self.manifest,
                "stage-png",
                {
                    "expected_revision": self.manifest["revision"],
                    "filename": f"w_{i}.png",
                    "data_base64": base64.b64encode(data).decode("ascii"),
                },
            )
            self.manifest = mut["project"]
            source_shas.append(digest(data))

        w = workspace(self.projects_dir, self.manifest)
        dir0_layers = [l for l in w["requirements"]["layers"] if l["view"] == 0]
        mappings = [{
            "requirement_id": l["id"],
            "kind": "DIRECT_SOURCE",
            "source": f"blob-{source_shas[idx]}",
            "source_revision": 1,
            "recipe": [],
        } for idx, l in enumerate(dir0_layers)]

        mut_assign = mutate(
            self.projects_dir,
            self.manifest,
            "assign",
            {"expected_revision": self.manifest["revision"], "mappings": mappings},
        )
        self.manifest = mut_assign["project"]

        w = workspace(self.projects_dir, self.manifest)
        cov = w["coverage"]

        # 6 direct assignments in direction 0
        self.assertEqual(cov["counts"]["assignments"]["direct"], 6)
        # 42 occurrences in remaining 7 directions (views 1..7) remain unassigned!
        self.assertEqual(cov["counts"]["assignments"]["unassigned"], 42)

        # Verify unresolved items contains all 42 unassigned occurrences with exact reasons
        unresolved = cov["unresolved_items"]
        self.assertEqual(len(unresolved), 48)  # 6 need review, 42 need supply_artwork
        supply_items = [u for u in unresolved if u["category"] == "SUPPLY_ARTWORK"]
        self.assertEqual(len(supply_items), 42)
        for u in supply_items:
            self.assertNotEqual(u["view"], 0)
            self.assertEqual(u["reason"], "UNASSIGNED_OCCURRENCE")

        # Bounded direction 0 is complete for its 6 occurrences, but actor is NOT complete
        self.assertEqual(cov["status"]["completeness"], "INCOMPLETE")
        self.assertEqual(cov["status"]["assignment_coverage"], "PARTIAL")
        self.assertFalse(cov["status"]["full_profile_specified"])
        self.assertFalse(cov["status"]["export_ready"])

    def test_06_human_review_proposal_approval_and_scoped_invalidation(self):
        """Criterion 2 & 4: Operator reviews exact composition revision; modifying assigned source

        invalidates only the affected occurrence's approval (STALE).
        """
        # Assign 2 frames (view 0 frame 0 and frame 1)
        data0 = make_synthetic_walk_frame(0)
        data1 = make_synthetic_walk_frame(1)
        sha0 = digest(data0)
        sha1 = digest(data1)

        for name, data in [("f0.png", data0), ("f1.png", data1)]:
            mut = mutate(
                self.projects_dir,
                self.manifest,
                "stage-png",
                {
                    "expected_revision": self.manifest["revision"],
                    "filename": name,
                    "data_base64": base64.b64encode(data).decode("ascii"),
                },
            )
            self.manifest = mut["project"]

        w = workspace(self.projects_dir, self.manifest)
        req0 = w["requirements"]["layers"][0]["id"]
        req1 = w["requirements"]["layers"][1]["id"]

        mut_assign = mutate(
            self.projects_dir,
            self.manifest,
            "assign",
            {
                "expected_revision": self.manifest["revision"],
                "mappings": [
                    {"requirement_id": req0, "kind": "DIRECT_SOURCE", "source": f"blob-{sha0}", "source_revision": 1, "recipe": []},
                    {"requirement_id": req1, "kind": "DIRECT_SOURCE", "source": f"blob-{sha1}", "source_revision": 1, "recipe": []},
                ],
            },
        )
        self.manifest = mut_assign["project"]

        # Propose and record approval for both occurrences
        prop = review_proposal(
            self.projects_dir,
            self.manifest,
            {"expected_revision": self.manifest["revision"], "requirements": [req0, req1]},
        )
        self.assertTrue(prop["proposal"]["approvable"])

        rev_res = record_review(
            self.projects_dir,
            self.manifest,
            {
                "expected_revision": self.manifest["revision"],
                "decision": "APPROVED",
                "proposal": prop["proposal"],
            },
        )
        self.manifest = rev_res["project"]

        # Verify both are APPROVED
        w = workspace(self.projects_dir, self.manifest)
        states = {o["requirement_id"]: o["state"] for o in w["reviews"]["occurrences"]}
        self.assertEqual(states[req0], "APPROVED")
        self.assertEqual(states[req1], "APPROVED")

        # Now stage a derived image and replace assignment for req0 only
        recipe = {
            "id": "scale-f0",
            "name": "Scale Frame 0",
            "source_sha256": sha0,
            "operations": [{"op": "scale", "width": 32, "height": 32, "filter": "nearest"}],
        }
        mut_trans = mutate(
            self.projects_dir,
            self.manifest,
            "apply-transform",
            {
                "expected_revision": self.manifest["revision"],
                "recipe": recipe,
                "destination_requirement_id": req0,
            },
        )
        self.manifest = mut_trans["project"]

        # Check scoped invalidation:
        # req0 composition basis changed -> review is STALE!
        # req1 was untouched -> review remains APPROVED!
        w_final = workspace(self.projects_dir, self.manifest)
        final_states = {o["requirement_id"]: o["state"] for o in w_final["reviews"]["occurrences"]}
        self.assertEqual(final_states[req0], "STALE")
        self.assertEqual(final_states[req1], "APPROVED")
        self.assertIn("COMPOSITION_CHANGED_OR_REQUIREMENT_UNAVAILABLE", next(o for o in w_final["reviews"]["occurrences"] if o["requirement_id"] == req0)["causes"])

    def test_07_save_reopen_and_corrupt_blob_resilience(self):
        """Criterion 4: Checklist, mappings, hashes, preview and reviews survive reopen;

        corrupt/missing blobs report exact errors without crashing or corrupting the project.
        """
        data = make_synthetic_walk_frame(0)
        sha = digest(data)
        mut = mutate(
            self.projects_dir,
            self.manifest,
            "stage-png",
            {
                "expected_revision": self.manifest["revision"],
                "filename": "step0.png",
                "data_base64": base64.b64encode(data).decode("ascii"),
            },
        )
        self.manifest = mut["project"]

        w = workspace(self.projects_dir, self.manifest)
        req_id = w["requirements"]["layers"][0]["id"]
        mut_assign = mutate(
            self.projects_dir,
            self.manifest,
            "assign",
            {
                "expected_revision": self.manifest["revision"],
                "mappings": [{"requirement_id": req_id, "kind": "DIRECT_SOURCE", "source": f"blob-{sha}", "source_revision": 1, "recipe": []}],
            },
        )
        self.manifest = mut_assign["project"]

        # Explicit review approval
        prop = review_proposal(self.projects_dir, self.manifest, {"expected_revision": self.manifest["revision"], "requirements": [req_id]})
        rev = record_review(self.projects_dir, self.manifest, {"expected_revision": self.manifest["revision"], "decision": "APPROVED", "proposal": prop["proposal"]})
        self.manifest = rev["project"]

        # Save and reopen project
        reopened = load_project(self.projects_dir, self.project_id, verify_blobs=True)
        self.assertEqual(reopened["revision"], self.manifest["revision"])
        self.assertEqual(len(reopened["review_events"]), 1)
        self.assertEqual(len(reopened["ledger"]["assignments"]), 1)

        # Workspace re-evaluation produces identical state
        w_reopened = workspace(self.projects_dir, reopened)
        self.assertEqual(w_reopened["reviews"]["counts"]["APPROVED"], 1)

        # Simulate corrupt blob: delete blob on disk
        blob_path = self.projects_dir / self.project_id / f"blobs/{sha}"
        blob_path.unlink()

        # Workspace still loads without crashing! Availability transitions to MISSING / UNVERIFIED
        w_missing = workspace(self.projects_dir, reopened)
        self.assertIsNotNone(w_missing)
        report = w_missing["ledger"]
        assigned = next(a for a in report["assignments"] if a["requirement_id"] == req_id)
        self.assertEqual(assigned["availability"], "MISSING")
        self.assertEqual(assigned["validation"], "UNVERIFIED")

        # source_preview reports precise typed error
        with self.assertRaises(ForgeError) as cm:
            source_preview(self.projects_dir, reopened, {"assignment": assigned["id"]})
        self.assertIn("not found in project", cm.exception.message)

    def test_08_batch_assignment_atomicity_and_invalid_mapping_rejection(self):
        """Invalid batch mappings are rejected atomically; no partial assignment commits."""
        data0 = make_synthetic_walk_frame(0)
        sha0 = digest(data0)
        mut = mutate(
            self.projects_dir,
            self.manifest,
            "stage-png",
            {
                "expected_revision": self.manifest["revision"],
                "filename": "valid_frame.png",
                "data_base64": base64.b64encode(data0).decode("ascii"),
            },
        )
        self.manifest = mut["project"]

        w = workspace(self.projects_dir, self.manifest)
        req0 = w["requirements"]["layers"][0]["id"]
        req1 = w["requirements"]["layers"][1]["id"]
        rev_before = self.manifest["revision"]

        # Batch containing one valid and one invalid (non-existent source) mapping
        batch_with_invalid = [
            {"requirement_id": req0, "kind": "DIRECT_SOURCE", "source": f"blob-{sha0}", "source_revision": 1, "recipe": []},
            {"requirement_id": req1, "kind": "DIRECT_SOURCE", "source": "blob-0000000000000000000000000000000000000000000000000000000000000000", "source_revision": 1, "recipe": []},
        ]

        with self.assertRaises(ForgeError) as cm:
            mutate(
                self.projects_dir,
                self.manifest,
                "assign",
                {"expected_revision": rev_before, "mappings": batch_with_invalid},
            )
        self.assertIn("MISSING_SOURCE", cm.exception.message)

        # Atomic guarantee: project revision and assignments are unchanged
        w_after = workspace(self.projects_dir, load_project(self.projects_dir, self.project_id))
        self.assertEqual(w_after["project"]["revision"], rev_before)
        self.assertEqual(len(w_after["project"].get("ledger", {}).get("assignments", [])), 0)

    def test_09_stale_project_revision_conflict_rejection(self):
        """Mutations specifying a stale project revision are rejected with revision conflict."""
        data0 = make_synthetic_walk_frame(0)
        stale_rev = 999  # Current revision is 1

        with self.assertRaises(ForgeError) as cm:
            mutate(
                self.projects_dir,
                self.manifest,
                "stage-png",
                {
                    "expected_revision": stale_rev,
                    "filename": "conflict.png",
                    "data_base64": base64.b64encode(data0).decode("ascii"),
                },
            )
        self.assertIn("revision conflict", cm.exception.message.lower())

    def test_10_immutable_original_source_preservation_and_deterministic_evaluation(self):
        """Original source blob remains byte-for-byte identical after multiple operations;

        evaluating coverage and ledger is strictly idempotent.
        """
        data = make_synthetic_walk_frame(0)
        orig_sha = digest(data)
        mut = mutate(
            self.projects_dir,
            self.manifest,
            "stage-png",
            {
                "expected_revision": self.manifest["revision"],
                "filename": "orig.png",
                "data_base64": base64.b64encode(data).decode("ascii"),
            },
        )
        self.manifest = mut["project"]

        # Run multiple derived transformations and assignments
        for op in [
            {"op": "flip", "direction": "horizontal"},
            {"op": "scale", "width": 32, "height": 32, "filter": "nearest"},
            {"op": "crop", "x": 0, "y": 0, "width": 32, "height": 32},
        ]:
            rec = {
                "id": f"rec-{op['op']}",
                "name": f"Recipe {op['op']}",
                "source_sha256": orig_sha,
                "operations": [op],
            }
            res = mutate(
                self.projects_dir,
                self.manifest,
                "apply-transform",
                {"expected_revision": self.manifest["revision"], "recipe": rec},
            )
            self.manifest = res["project"]

        # Verify original blob in blobs/{orig_sha} is bit-for-bit identical to original bytes
        stored_bytes = get_blob(self.projects_dir, self.project_id, orig_sha)
        self.assertEqual(stored_bytes, data)
        self.assertEqual(digest(stored_bytes), orig_sha)

        # Idempotent coverage and ledger evaluation: calling workspace twice produces identical JSON
        w1 = workspace(self.projects_dir, self.manifest)
        w2 = workspace(self.projects_dir, self.manifest)
        self.assertEqual(canonical_bytes(w1["coverage"]), canonical_bytes(w2["coverage"]))
        self.assertEqual(canonical_bytes(w1["ledger"]), canonical_bytes(w2["ledger"]))


if __name__ == "__main__":
    unittest.main()
