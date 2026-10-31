"""Reproduce canonical RSF-13 comparison, contact sheet, and sequence export examples."""
from __future__ import annotations

import json
from pathlib import Path
import sys
import shutil

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(REPO_ROOT / "src"), str(REPO_ROOT / "tests/private_fixture_hooks")]

from ro_sprite_forge.core.animation import AnimationInspector
from ro_sprite_forge.core.comparison import compare_frames, apply_overlays
from ro_sprite_forge.core.contact_sheet import generate_contact_sheet, export_frame_sequence
from ro_sprite_forge.core.canonical import canonical_bytes
from ro_sprite_forge.formats.preview import png_bytes
from test_audited_fixtures import find_fixture


def main():
    evidence_dir = Path(__file__).resolve().parent
    artifacts_dir = evidence_dir / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    # Load audited fixtures
    nov_body_act = find_fixture("novice_body_act").read_bytes()
    nov_body_spr = find_fixture("novice_body_spr").read_bytes()
    nov_head_act = find_fixture("novice_head_act").read_bytes()
    nov_head_spr = find_fixture("novice_head_spr").read_bytes()

    orc_act = find_fixture("orc_skeleton_act").read_bytes()
    orc_spr = find_fixture("orc_skeleton_spr").read_bytes()

    nov = AnimationInspector(
        nov_body_act, nov_body_spr,
        category="player",
        head_act_bytes=nov_head_act,
        head_spr_bytes=nov_head_spr,
    )
    orc = AnimationInspector(orc_act, orc_spr, category="monster")

    examples = {}

    # 1. Novice Walk frame 0 self-comparison (Side by Side)
    walk_f0 = nov.timeline.select(action="Walk", view=0, frame=0)
    cmp_self = compare_frames(nov, nov, walk_f0, walk_f0, mode="SIDE_BY_SIDE")
    (artifacts_dir / "ex1_novice_walk_self_sbs.png").write_bytes(cmp_self["png_bytes"])
    examples["ex1_novice_walk_self_sbs"] = cmp_self["report"]

    # 2. Novice Walk frame 0 vs frame 1 (Difference)
    walk_f1 = nov.timeline.select(action="Walk", view=0, frame=1)
    cmp_diff = compare_frames(nov, nov, walk_f0, walk_f1, mode="DIFFERENCE")
    (artifacts_dir / "ex2_novice_walk_diff.png").write_bytes(cmp_diff["png_bytes"])
    examples["ex2_novice_walk_diff"] = cmp_diff["report"]

    # 3. Novice Walk frame 0 vs frame 1 (Onion Skin)
    cmp_onion = compare_frames(nov, nov, walk_f0, walk_f1, mode="ONION_SKIN")
    (artifacts_dir / "ex3_novice_walk_onion.png").write_bytes(cmp_onion["png_bytes"])
    examples["ex3_novice_walk_onion"] = cmp_onion["report"]

    # 4. Missing Candidate comparison (Reference Only)
    cmp_missing = compare_frames(nov, None, walk_f0, None)
    (artifacts_dir / "ex4_novice_missing_candidate.png").write_bytes(cmp_missing["png_bytes"])
    examples["ex4_novice_missing_candidate"] = cmp_missing["report"]

    # 5. Overlays (Origin, Bounds, Anchors, Layers) on Novice Walk frame 0
    cmp_overlays = compare_frames(
        nov, nov, walk_f0, walk_f1,
        mode="SIDE_BY_SIDE",
        overlays=["origin", "bounds", "anchors", "layers"]
    )
    (artifacts_dir / "ex5_novice_walk_overlays.png").write_bytes(cmp_overlays["png_bytes"])
    examples["ex5_novice_walk_overlays"] = cmp_overlays["report"]

    # 6. Contact Sheet: Novice Walk (8 frames)
    cs_nov = generate_contact_sheet(
        nov, walk_f0, columns=4, scale=1, padding=4, margin=8, labels=True,
        overlays=["anchors"]
    )
    (artifacts_dir / "ex6_novice_walk_contact_sheet.png").write_bytes(cs_nov["png_bytes"])
    examples["ex6_novice_walk_contact_sheet"] = cs_nov["report"]

    # 7. Contact Sheet: Orc Skeleton Death (22 frames, up to 12 layers)
    die_f0 = orc.timeline.select(action="Die", view=0, frame=0)
    cs_orc = generate_contact_sheet(
        orc, die_f0, columns=8, scale=1, padding=2, margin=4, labels=True,
        overlays=["bounds"]
    )
    (artifacts_dir / "ex7_orc_death_contact_sheet.png").write_bytes(cs_orc["png_bytes"])
    examples["ex7_orc_death_contact_sheet"] = cs_orc["report"]

    # 8. Frame Sequence Export: Novice Walk
    seq_dir = artifacts_dir / "novice_walk_sequence"
    if seq_dir.exists():
        shutil.rmtree(seq_dir)
    seq_manifest = export_frame_sequence(nov, walk_f0, seq_dir, overlays=["anchors"])
    examples["ex8_novice_walk_sequence_manifest"] = seq_manifest

    # Write summary examples.json
    (evidence_dir / "examples.json").write_bytes(canonical_bytes(examples))
    print(f"RSF13_REPRODUCE_EXAMPLES_PASS count={len(examples)} artifacts={len(list(artifacts_dir.glob('*.png')))}")


if __name__ == "__main__":
    main()
