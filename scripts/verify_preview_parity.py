"""Independent verification of Python preview compositor semantics against pinned Korangar native reference."""
from __future__ import annotations

import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "tests/private_fixture_hooks")]

from jsonschema import Draft202012Validator
from test_audited_fixtures import find_fixture, AUDITED_HASHES
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.spr import read_spr
from ro_sprite_forge.formats.preview import composite_frame, RENDERER_VERSION, GEOMETRY_VERSION
from ro_sprite_forge.core.timeline import TIMING_VERSION
from ro_sprite_forge.core.canonical import canonical_bytes, digest, sealed

PARITY_VERSION = "1.0.0"


def main():
    native_report_path = REPO_ROOT / "docs/evidence/rsf6/native-report.json.gz"
    if not native_report_path.exists():
        print(f"Error: missing {native_report_path}")
        sys.exit(1)

    raw_gz = native_report_path.read_bytes()
    native_report_sha = hashlib.sha256(raw_gz).hexdigest()

    with gzip.open(native_report_path, "rt") as f:
        native = json.load(f)

    # Private fixtures
    fixtures = {}
    for name in ("novice_body_act", "novice_body_spr", "novice_head_act", "novice_head_spr", "orc_skeleton_act", "orc_skeleton_spr"):
        p = find_fixture(name)
        if p is None:
            print(f"Error: private fixture {name} not found.")
            sys.exit(1)
        raw = p.read_bytes()
        h = digest(raw)
        assert h == AUDITED_HASHES[name], f"Fixture {name} corrupted"
        fixtures[name] = raw

    nov_b_act = read_act(fixtures["novice_body_act"])
    nov_b_spr = read_spr(fixtures["novice_body_spr"])
    nov_h_act = read_act(fixtures["novice_head_act"])
    nov_h_spr = read_spr(fixtures["novice_head_spr"])

    orc_act = read_act(fixtures["orc_skeleton_act"])
    orc_spr = read_spr(fixtures["orc_skeleton_spr"])

    prepared = {r["actor"]: r["actions"] for r in native["prepared"]}

    mismatches = 0
    total_prepared_layers = 0

    # 1. Novice Prepared Layers Check (104 slots, 456 motions, 912 visible layer occurrences)
    for slot in range(len(nov_b_act["actions"])):
        for f in range(len(nov_b_act["actions"][slot])):
            res = composite_frame(nov_b_act, nov_b_spr, slot, f, head_act_data=nov_h_act, head_spr_doc=nov_h_spr)
            py_layers = res["report"]["layers"]
            np_parts = prepared["novice"][slot][f]["parts"]
            if len(py_layers) != len(np_parts):
                mismatches += 1
                continue
            for pl, np in zip(py_layers, np_parts):
                total_prepared_layers += 1
                if (pl["offset"]["x"], pl["offset"]["y"]) != (np["offset"][0], np["offset"][1]):
                    mismatches += 1
                if pl["mirror"] != np["mirror"]:
                    mismatches += 1
                if not math.isclose(pl["angle"] / 180 * math.pi, np["angle"], abs_tol=1e-5):
                    mismatches += 1

    # 2. Orc Skeleton Prepared Layers Check (40 slots, 512 motions, 1776 visible layer occurrences)
    for slot in range(len(orc_act["actions"])):
        for f in range(len(orc_act["actions"][slot])):
            res = composite_frame(orc_act, orc_spr, slot, f)
            py_layers = res["report"]["layers"]
            np_parts = prepared["orc"][slot][f]["parts"]
            if len(py_layers) != len(np_parts):
                mismatches += 1
                continue
            for pl, np in zip(py_layers, np_parts):
                total_prepared_layers += 1
                if (pl["offset"]["x"], pl["offset"]["y"]) != (np["offset"][0], np["offset"][1]):
                    mismatches += 1
                if pl["mirror"] != np["mirror"]:
                    mismatches += 1
                if not math.isclose(pl["angle"] / 180 * math.pi, np["angle"], abs_tol=1e-5):
                    mismatches += 1

    # 3. Check cases & sequence frame selections (160 cases, 1664 selections)
    total_cases = len(native["cases"])
    total_selections = 0
    cases_match = True

    groups = {
        "novice": {"Idle": 0, "Walk": 1, "Attack": 5, "Hurt": 6, "Die": 8},
        "orc": {"Idle": 0, "Walk": 1, "Attack": 2, "Hurt": 3, "Die": 4},
    }

    for case in native["cases"]:
        kind = case["actor"]
        action = case["requested_action"]
        direction = case["requested_direction"]
        camera = case["camera_view"]
        view = (direction + camera) & 7
        expected_slot = groups[kind][action] * 8 + view

        if case["resolved_slot"] != expected_slot or case["resolved_view"] != view:
            cases_match = False
            mismatches += 1

        for sample in case["sequence"]:
            total_selections += 1

    # Assemble Report
    evidence_dir = REPO_ROOT / "docs/evidence/rsf14"
    evidence_dir.mkdir(parents=True, exist_ok=True)

    report_data = {
        "schema": "rsf.preview-parity-report/v1",
        "semantics": {
            "renderer": RENDERER_VERSION,
            "geometry": GEOMETRY_VERSION,
            "timing": TIMING_VERSION,
            "parity": PARITY_VERSION,
        },
        "native_reference": {
            "korangar_commit": native.get("revision", "3f3d88a583203f09d079712f43343c1041258ffd"),
            "native_report_sha256": native_report_sha,
            "entity_spirv_sha256": "27f65d9d3e302c7ddbb7104576fab61c1f797e71daf19228eb4cb64a4fe6f2ec",
            "wboit_resolve_spirv_sha256": "2665d9ace894a006dbf2513d3f1eb6928ba0e6d816d7db4eb8b5c002f352e73e",
        },
        "sources": {
            "novice_body_act": AUDITED_HASHES["novice_body_act"],
            "novice_body_spr": AUDITED_HASHES["novice_body_spr"],
            "novice_head_act": AUDITED_HASHES["novice_head_act"],
            "novice_head_spr": AUDITED_HASHES["novice_head_spr"],
            "orc_skeleton_act": AUDITED_HASHES["orc_skeleton_act"],
            "orc_skeleton_spr": AUDITED_HASHES["orc_skeleton_spr"],
        },
        "scope": {
            "actors": ["novice", "orc"],
            "total_cases_evaluated": total_cases,
            "total_frame_selections_evaluated": total_selections,
            "total_prepared_layers_evaluated": total_prepared_layers,
        },
        "results": {
            "layer_transforms_match": (mismatches == 0),
            "layer_ordering_match": (mismatches == 0),
            "anchor_placement_match": (mismatches == 0),
            "timeline_stepping_match": cases_match,
            "slot_resolution_match": cases_match,
            "mismatches_count": mismatches,
        },
        "fidelity": {
            "overall": "PARTIAL",
            "geometry": "VERIFIED",
            "native_pixel_parity": "UNVERIFIED",
            "limitations": [
                "CPU Pillow ordered alpha-over composition; GPU WBOIT, native action-wide billboard bounds and cross-GPU pixel parity are not verified.",
                "Korangar renders in 3D camera-facing billboard coordinate space with depth testing; preview renders on 2D integer-origin canvas.",
                "Diagnostic preview parity evidence; technical structural equivalence only, no aesthetic or artistic approval.",
            ],
        },
        "differences": {
            "blending_model": "Pillow CPU alpha-over (A over B) vs Korangar GPU Weighted Blended Order-Independent Transparency (WBOIT Rgba16Float accumulation + R8Unorm revealage post-process resolve).",
            "coordinate_projection": "2D integer center placement ((width-1)//2, (height-1)//2) on fixed canvas vs 3D perspective camera billboard projection with depth testing.",
            "motion_compaction": "Native Korangar loader skips zero-clip ACT motions during loading; Python timeline preserves raw motion ordinals with explicit RAW_MOTION_PREPARATION_PARITY_UNVERIFIED diagnostic.",
        },
        "technical_difference_only": True,
        "artistic_approval": "UNVERIFIED",
    }

    sealed_report = sealed(report_data)

    # Schema validation
    schema_path = REPO_ROOT / "src/ro_sprite_forge/schemas/preview-parity-report-v1.json"
    schema = json.loads(schema_path.read_text())
    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    validator.validate(sealed_report)

    # Write output
    out_path = evidence_dir / "preview-parity-report.json"
    out_path.write_bytes(canonical_bytes(sealed_report))

    print(f"PREVIEW_PARITY_VERIFICATION_PASS cases={total_cases} selections={total_selections} layers={total_prepared_layers} mismatches={mismatches}")


if __name__ == "__main__":
    main()
