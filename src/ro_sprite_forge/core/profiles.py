"""Frozen source-reviewed Korangar semantics; never native playback evidence.

This data is deliberately separate from resource observations and target intent.
See docs/provenance/KORANGAR_RUNTIME_PROFILE.md for source identities and limits.
"""

from ro_sprite_forge.core.canonical import check, sealed

REVISION = "3f3d88a583203f09d079712f43343c1041258ffd"
PLAYER = ("Idle", "Walk", "Sit", "Pickup", "ReadyFight", "Attack1", "Hurt",
          "Freeze1", "Die", "Freeze2", "Attack2", "Attack3", "Skill")
MONSTER = ("Idle", "Walk", "Attack1", "Hurt", "Die")
SELECTABLE = {"Idle", "Walk", "Pickup", "Attack1", "Attack3", "Hurt", "Die"}


def get_profile(category: str) -> dict:
    """Return a fresh immutable-in-meaning record, with a canonical content hash."""
    check(category in ("player", "npc", "monster", "unverified"), "Unknown frozen runtime profile.")
    verified = category != "unverified"
    actions = PLAYER if category == "player" else MONSTER if verified else ()
    return sealed({
        "schema": "rsf.runtime-profile/v1", "id": f"korangar-{category}-v1",
        "category": category, "revision": REVISION if verified else None,
        "evidence_status": "SOURCE_VERIFIED" if verified else "UNVERIFIED",
        "native_evidence": "UNVERIFIED",
        "source_evidence": _evidence() if verified else [],
        "actions": [{"group": group, "action": action, "mapping": "SOURCE_VERIFIED",
                     "selection_path": "SOURCE_VERIFIED" if action in SELECTABLE else "UNVERIFIED"}
                    for group, action in enumerate(actions)],
        "views": list(range(8)) if verified else [],
        "resolution": {"view": "(camera_direction + entity_direction) & 7",
                       "requested_slot": "group * 8 + view",
                       "resolved_slot": "requested_slot % prepared_animation_count",
                       "delay_slot": "requested_slot % delay_count",
                       "unmapped_action": "fallback to group 0; requested action UNSUPPORTED"} if verified else None,
        "timing": {"default_interval_ms": "raw_delay * 50",
                   "walk_interval_ms": "raw_delay * movement_speed * 100 / 150 / 5",
                   "pickup_interval_ms": "raw_delay * 25",
                   "attack_hurt_frame": "elapsed_ms * selected_frame_count / server_duration_ms",
                   "looping": ["Idle", "Walk"], "nonlooping": ["Attack1", "Attack3", "Hurt", "Pickup", "Die"],
                   "player_idle": "always frame 0 (Player only)",
                   "nonloop_end": "clamp to final frame",
                   "completion_check": "uses group view 0, modulo arrays; frame_time > frame_count"} if verified else None,
        "parts": {"order": ["body", "head"] if category == "player" else ["body"],
                  "head_registration": "Player part 1: body anchor[0] minus head anchor[0], only with one attachment point" if category == "player" else None,
                  "empty_motion": "loader skips motions with zero clips",
                  "other_attachments": "UNVERIFIED"} if verified else None,
        "limitations": ["Source mapping does not prove gameplay reachability or native playback.",
                        "Prepared runtime frames may differ from raw ACT motions.",
                        "No actor-specific frame counts are prescribed.",
                        "Critical Attack3 on NPC/monster falls back to Idle group 0.",
                        "Named compass directions, equipment and visual approval remain UNVERIFIED."],
    })


def validate_profile(value: dict) -> dict:
    check(isinstance(value, dict), "Expected a frozen runtime-profile object.")
    category = value.get("category")
    expected = get_profile(category)
    check(value == expected, "Runtime profile differs from the frozen source-reviewed record.")
    return expected


def _evidence() -> list[dict]:
    # File hashes are at REVISION, independent of any local checkout path.
    return [
        {"path": "korangar/src/world/animation/mod.rs", "sha256": "72a49aa2069306499e2fe76200a9388c8c69b97ec19ed76ade84c2297d1ccaa1", "sections": "action_base_offset; AnimationState; get_frame; is_animation_over"},
        {"path": "korangar/src/loaders/animation/mod.rs", "sha256": "318e40783be1ee0a280b341967a69f3bcf247456fb72d0d099aead5551ab06b9", "sections": "ordered parts, layer transforms, anchor registration"},
        {"path": "korangar/src/loaders/action/mod.rs", "sha256": "31e10e0f8fbf8129028620819e609557f41f5ecc9124777988ece941f9116ac7", "sections": "raw delays and events"},
        {"path": "korangar/src/world/entity/mod.rs", "sha256": "5383bfc574e8a65b8a53ab0a55d8ca2929cc25c474339cdcb632a26b9b744fe0", "sections": "body/head paths and ordering"},
    ]
