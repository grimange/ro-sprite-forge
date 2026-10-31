"""Pure resource observations, not artwork assignments or runtime proof."""

import math
import re
import struct

from ro_sprite_forge.core.canonical import check, digest, sealed
from ro_sprite_forge.core.profiles import get_profile, validate_profile
from ro_sprite_forge.formats.act import read_act
from ro_sprite_forge.formats.spr import read_spr

SCHEMA = "rsf.inventory/v1"
CONTENT_DOMAIN = b"rsf.decoded-rgba/v1\0"


def namespace(value: str) -> str:
    check(isinstance(value, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", value) is not None,
          "Namespace components must be 1–80 ASCII letters, digits, '.', '_' or '-'.")
    return value


def inventory(act_bytes: bytes, spr_bytes: bytes, *, actor: str = "unspecified",
              part: str = "body", profile: dict | None = None) -> dict:
    """Inventory supported bytes without filename identities or image-library imports.

    Content hash = SHA256(domain || uint32LE width || uint32LE height || RGBA).
    Indexed zero is transparent black; other indices use palette RGB, alpha 255.
    Truecolor keeps all decoded RGBA bytes, including RGB beneath zero alpha.
    Palette/index representation hashes remain independent of content classes.
    """
    actor, part = namespace(actor), namespace(part)
    profile = get_profile("unverified") if profile is None else validate_profile(profile)
    act, spr = read_act(act_bytes), read_spr(spr_bytes)
    prefix = f"{actor}/{profile['id']}/{part}"
    images, classes = [], {}
    for pool, members in ((0, spr.indexed_images), (1, spr.rgba_images)):
        for index, image in enumerate(members):
            rgba = image.to_rgba(spr.palette) if pool == 0 else image.rgba
            content = digest(CONTENT_DOMAIN + struct.pack("<II", image.width, image.height) + rgba)
            identity = f"{prefix}/image/p{pool}/i{index}"
            record = {"id": identity, "pool": pool, "index": index,
                      "width": image.width, "height": image.height,
                      "decoded_content_sha256": content,
                      "representation_sha256": digest(image.pixels if pool == 0 else image.rgba),
                      "reference_count": 0}
            if pool == 0:
                record["rle_byte_length"] = image.rle_length
            images.append(record)
            classes.setdefault(content, []).append(identity)
    lookup = {(i["pool"], i["index"]): i for i in images}
    actions, frame_total, layer_total, visible_total = [], 0, 0, 0
    mapping = {a["group"]: a["action"] for a in profile["actions"]}
    for slot, motions in enumerate(act["actions"]):
        known = slot // 8 in mapping
        semantic = mapping.get(slot // 8)
        action_id = f"{prefix}/action/{semantic or 'UNVERIFIED'}/slot{slot}/view{slot % 8 if known else 'UNVERIFIED'}"
        delay = act["delays"][slot]
        check(math.isfinite(delay) and delay > 0, "ACT delay must be finite and positive.")
        frames = []
        for ordinal, motion in enumerate(motions):
            frame_id = f"{action_id}/frame{ordinal}"
            check(motion["event"] == -1 or 0 <= motion["event"] < len(act["events"]), "Invalid ACT event reference.")
            layers = []
            for layer_ordinal, clip in enumerate(motion["clips"]):
                check(all(math.isfinite(clip[k]) for k in ("scale_x", "scale_y")), "Non-finite ACT scale.")
                check(clip["sprite"] >= -1, "Invalid negative SPR image reference.")
                visible = clip["sprite"] != -1
                image = lookup.get((clip["pool"], clip["sprite"])) if visible else None
                check(not visible or image is not None, "ACT layer references an absent SPR pool/image.")
                if image is not None:
                    image["reference_count"] += 1
                layers.append({"id": f"{frame_id}/layer{layer_ordinal}", "ordinal": layer_ordinal,
                               "role": None, "visible": visible, "image_id": image["id"] if image else None,
                               "raw": dict(clip)})
                visible_total += int(visible)
            frames.append({"id": frame_id, "ordinal": ordinal, "bounds_raw": list(motion["bounds"]),
                           "anchors": motion["anchors"], "event_index": motion["event"], "layers": layers})
            frame_total += 1
            layer_total += len(layers)
        actions.append({"id": action_id, "slot": slot, "group_numeric": slot // 8,
                        "semantic_action": semantic, "mapped_view": slot % 8 if known else None,
                        "mapping_status": "SOURCE_VERIFIED" if known else "UNVERIFIED",
                        "raw_delay": delay, "frames": frames})
    referenced = [i["id"] for i in images if i["reference_count"]]
    unused = [i["id"] for i in images if not i["reference_count"]]
    referenced_contents = {i["decoded_content_sha256"] for i in images if i["reference_count"]}
    return sealed({"schema": SCHEMA, "namespace": {"actor": actor, "part": part, "profile": profile["id"]},
                   "sources": {"act": {"format": "ACT 2.4", "bytes": len(act_bytes), "sha256": digest(act_bytes)},
                               "spr": {"format": "SPR 2.1", "bytes": len(spr_bytes), "sha256": digest(spr_bytes)}},
                   "runtime_profile": profile,
                   "raw_metadata": {"reserved": act["reserved"], "events_hex": act["events"],
                                    "palette_hex": spr.palette.hex(), "palette_sha256": digest(spr.palette)},
                   "actions": actions, "images": images, "referenced_image_ids": referenced,
                   "unused_image_ids": unused,
                   "content_classes": [{"sha256": key, "image_ids": classes[key]} for key in sorted(classes)],
                   "summary": {"numeric_action_groups": (len(actions) + 7) // 8, "action_slots": len(actions),
                               "frame_occurrences": frame_total, "layer_occurrences": layer_total,
                               "visible_layer_references": visible_total,
                               "indexed_images": spr.indexed_count, "truecolor_images": spr.rgba_count,
                               "stored_images": len(images), "referenced_images": len(referenced),
                               "unused_images": len(unused), "distinct_stored_contents": len(classes),
                               "distinct_referenced_contents": len(referenced_contents)},
                   "status": {"resource_presence": "PRESENT", "structural_validity": "VALID_FOR_INVENTORY",
                              "artwork_assignments": "NOT_EVALUATED", "visual_approval": "UNREVIEWED",
                              "native_evidence": "UNVERIFIED"}})
