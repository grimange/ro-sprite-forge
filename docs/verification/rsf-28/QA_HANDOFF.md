# Independent RSF-28 review assignment

Review RSF-28 only, in a separate read-only context. Do not edit implementation,
Kaneo, ownership or evidence files. Return a report for the coordinator to retain.
Read AGENTS.md, forge-qa/forge-verification skills, relevant M6 plan sections,
QA_REVIEW_PROMPT and the complete live Kaneo task mdehayoorrfc43z930ij72wx.

Ownership remains Codex aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn. Sole blocker RSF-26
was verified Accepted before implementation. Live task has four mandatory criteria;
see kaneo-start.json. Existing untracked files are accepted source, not this diff.
Use baseline-hashes.json and baseline copies to isolate changed accepted files.

New implementation:
- src/ro_sprite_forge/adapters/{__init__,_media_exec,video}.py
- src/ro_sprite_forge/service/media.py
- src/ro_sprite_forge/schemas/video-candidates-v1.json
- tests/test_video.py
- scripts/check_video_schema.py

Existing changes:
- cli.py: lazy video-capabilities / inspect / extract-preview / stage commands.
- project-v1.json: optional closed video_imports records, no storage redesign.
- test_codecs.py: exact path/hash allowlist for four already-retained, hash-pinned
  RSF-27 synthetic marker binaries. Initial public suite exposed the existing
  extension-only guard's false positive. No accepted resource changed. Verify
  fixture generation/provenance and that modified/unlisted binaries still fail.

Execute independently:
- .venv/bin/python -m unittest discover -s tests -p test_video.py -v
- .venv/bin/python docs/verification/rsf-28/reproduce.py --output <fresh /tmp directory>
- .venv/bin/python -m unittest discover -s tests -v (existing HTTP tests need sockets)
- relevant private suite, 11 schema scripts, installed-distribution check where practical.

Independently compare known RGB patterns to lossless extracted RGBA, actual VFR
PTS [0,40,120,160,300], exact selection and request order [300,0,120] -> [4,0,2].
Check B-frame presentation order, multiple video streams, exact timestamp rejection,
optional tools/no ordinary process, local-only argv/process limits, timeout/group
cleanup, malformed/oversized media, corruption/count mismatch, canonical identity,
PNG validation, immutable blobs/reopen, idempotency and failed/stale publications.
Verify no assignment/review/ACT timing and source-tray discovery through existing API.
CLI/API scope is sufficient under live acceptance; no UI controls changed, no browser
claim. No new native/Rust proof is claimed; accepted M5 code is preserved.

Return QA_PASS / QA_FAIL / QA_BLOCKED. List exact independently executed commands,
exit statuses and scope, any expected/observed reproducible defects and gaps. Do
not pass an unmet mandatory criterion. Coordinator fixes defects; independently
retest corrections within this assignment.
