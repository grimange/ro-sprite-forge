# Independent RSF-4 review

QA_PASS — RSF-4 bounded implementation. Reviewer context:
`/root/rsf4_independent_qa`, configured `forge_qa_reviewer`.
Reviewer was read-only and made no implementation or Kaneo changes.
No mandatory findings or correction loop was required.

The reviewer fetched the live task and assessed all five acceptance criteria,
read the ten-path diff and relevant instructions/skills/plan, and independently
executed:

- Public suite: exit 0, 69 passed (`qa-public.log`).
- Private suite: exit 0, 7 passed / 3 missing-Orc skips (`qa-private.log`).
- Distribution checker: exit 0, 69 installed-package tests, offline clean
  Python 3.14.4 install, stdlib smoke, repeated wheel equality and asset exclusion
  (`qa-distribution.log`).
- Clean installed Python 3.13.13: preservation 9, foundation 16, inventory 24;
  all exit 0, total 49 (`qa-python313.log`).
- Additional edge probes: five exact signed-coordinate/float32 raw-bit roundtrips
  and five typed invalid-field rejections, exit 0.
- All 61 current manifest entries and all 57 baseline archive entries verified;
  exactly ten changed paths. Snapshot SHA-256:
  `629cf9ed05de3b43c8163caa86f06c1e3b0b6b92eac0d4e54fac2d72e01be0db`.

Raw preservation and independent ACT golden/mutation evidence were assessed
separately. Eighteen literal-offset edits, full unrelated-byte comparisons,
layout-changing anchor insertion, 424 truncated prefixes, pool-local references,
raw event/anchor/header metadata, unsupported conversions, source immutability,
error exits and publication rollback were verified.

Novice body/head remain separate and retain pinned hashes under both policies.
Orc fresh preservation is NOT_RUN: missing pinned pair. Its historical acceptance
is not substituted for a fresh run. Python 3.12 is unavailable; full 3.13 preview
suite lacks an offline Pillow wheel. These limits are correctly disclosed.

Independent repeated wheel SHA-256 matches implementer:
`f2372f1d1523f65f74bc0e07dd06097094e6f9323e44fb7212107bffeb80a209`.
Independent sdist SHA-256:
`e00f9eb6c05a5c465f0bdfbde1d59d21df384f488c4605021c2028ea674f0245`.
Sdist differs from the earlier archive because gzip/tar timestamps are not
normalized. Reproducible sdist bytes are not claimed.

All five live RSF-4 criteria are supported within their explicit optional-private-
fixture and NOT_RUN provisions. Criterion four accepts a truthful evidence packet,
not a full M0-S success claim. Reviewer authorizes the orchestrator to synchronize
this QA_PASS, supported checkboxes and Accepted transition.

M0-S INCOMPLETE; M0-I NOT_RUN; M0-N NOT_RUN / native UNVERIFIED.
Overall M0 UNVERIFIED. Artwork UNASSIGNED; operator visual approval NOT_RUN.
Next structural gap: restore pinned Orc pair and rerun private hooks.
