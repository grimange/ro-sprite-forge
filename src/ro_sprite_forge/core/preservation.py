"""Pure, bounded pair verification; raw preservation and ACT encoding are distinct."""

from ro_sprite_forge.core.canonical import check, digest, sealed
from ro_sprite_forge.core.inventory import inventory
from ro_sprite_forge.formats.act import read_act, write_act


def roundtrip_pair(act: bytes, spr: bytes, *, mode: str = "preserve") -> tuple[bytes, bytes, dict]:
    check(mode in ("preserve", "act-semantic"),
          "Unsupported roundtrip mode; indexed SPR writing/conversion is not supported.")
    observed = inventory(act, spr)  # Includes finite fields and pool-local references.
    parsed = read_act(act)
    encoded = write_act(parsed)
    check(read_act(encoded) == parsed, "ACT semantic roundtrip mismatch.")
    output_act = act if mode == "preserve" else encoded
    # SPR is always passed through, including unused entries and original RLE/palette.
    checks = {"structure": "PASS", "pair_references": "PASS",
              "act_semantic_roundtrip": "PASS",
              "act_serializer_byte_equal": encoded == act,
              "act_output_byte_equal": output_act == act,
              "spr_output_byte_equal": True,
              "independent_binary_tests": "NOT_RUN",
              "rust_oracle": "NOT_RUN", "native": "UNVERIFIED"}
    report = sealed({"schema": "rsf.verification/v1", "policy": mode,
                     "result": "PASS", "checks": checks,
                     "resources": {name: {"input_sha256": digest(source),
                                           "output_sha256": digest(output)}
                                   for name, source, output in (("act", act, output_act), ("spr", spr, spr))},
                     "inventory_sha256": observed["canonical_sha256"],
                     "summary": observed["summary"],
                     "spr_policy": "original-bytes; no pool reorder or representation conversion"})
    return output_act, spr, report
