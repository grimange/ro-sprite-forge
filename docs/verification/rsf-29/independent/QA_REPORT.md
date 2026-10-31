# RSF-29 independent QA

Verdict: **QA_PASS**. Reviewer: separate configured `forge_qa_reviewer` context
`/root/rsf24_qa`, reused for RSF-29. The reviewer changed no source/evidence files,
made no Kaneo writes, took no ownership and granted no real artwork approval.
The coordinator archived this returned verdict and the reviewer's temporary outputs.

All four live checklist items passed:

1. Actual Chromium selected PTS `[300,0,120]` → presentation ordinals `[4,0,2]`,
   verified source/PNG hashes and exact time base, reordered to `[300,120,0]`,
   explicitly staged, repeated staging, reopened and manually assigned three candidates
   to declared view-0 frame/layer requirements. The remaining 21 of 24 requirements
   stayed unassigned. Canonical selection identity and assignment revisions persist.
2. Source PTS `[0,40,120,160,300]` remained unchanged when runtime movement speed
   changed 100 → 250. Observed Walk slot 8 had fallback `NONE`; frame durations
   changed approximately 53.333332 → 133.333344 ms without changing video provenance.
3. Actual existing M4 crop `(1,1,14,14)`, placement `(1,1)` on a 16×16 canvas and
   exact matte key `(170,80,165)` showed before/after previews without publication,
   then explicitly staged a derived image. Independently constructed expected RGBA
   pixels matched exactly. Isolated synthetic review records demonstrated only the
   affected occurrence became stale after reassignment; the other stayed approved.
4. Extraction/staging created no assignments or approvals. Video collection review
   stayed `UNVERIFIED`; missing art was not filled or aesthetically judged.

## Independently executed checks

| Command | Exit/result |
| --- | --- |
| `.venv/bin/python -m unittest discover -s tests -p test_video_workbench.py -v` | 0; 26 PASS |
| `.venv/bin/python -m unittest discover -s tests -q` | 0; 504 PASS |
| `.venv/bin/python -m unittest discover -s tests/private_fixture_hooks -q` | 0; 40 PASS, 1 existing legacy native-report skip |
| Eleven schema checker scripts | Each 0; exact commands/output in `rsf29-qa-schemas.json` |
| `.venv/bin/python tests/check_distribution.py --wheelhouse /tmp/rsf24-wheelhouse --python /usr/bin/python3.14` | 0; 504 discovered, 494 PASS, 10 optional skips; distribution PASS |
| `node /tmp/rsf29-qa-browser.cjs` | 0; primary and workflow browser scripts PASS |
| `.venv/bin/python /tmp/rsf29-qa-pixels.py` | 0; independent source/transformed pixels match |
| Refreshed implementation manifest and baseline hashes | 0; 13 changed paths, 121 unchanged baseline files, zero mismatches |

Chrome 156.0.8078.73 ran through installed Playwright in a fresh context. The MCP
browser was attempted but its shared profile was locked; the reviewer independently
used an isolated installed-Playwright fallback. The wrapper executes the repository
scripts with only screenshot destinations changed to `/tmp`. Both workflows had zero
unexpected console/page errors and zero failed requests. Expected negative HTTP
responses remain recorded separately.

Actual journeys covered keyboard selection, known-pixel previews, nonchronological
ordering, preview without commit, staging/idempotency/reopen, source tray, PNG import,
manual assignment, timing separation, M4 recipes/scoped invalidation, audio-first
absolute stream 1, malformed-container failure, missing PTS, invalid ordinal,
unsupported stream and stale revision.

Large-PTS and missing-dependency browser responses were deliberately simulated;
backend tests independently exercised large-integer persistence and patched tool absence.
RSF-28's supported selection bound remains ±(2^53−1), enforced before conversion.
Larger metadata stays exact decimal text, including `9007199254740993` and denominator
`10000000000000001`. No oversized-PTS decoding claim is made.

The custom pixel probe constructs synthetic patterns mathematically rather than
calling Forge transformations. Source ordinals 4, 2 and 0 and the derived image matched
every expected RGBA byte. Derived PNG SHA-256:
`c47c90c05eb58b54757725ae8cdab92acdf57c33cd2f0548807c227cf9b7fdfe`;
RGBA SHA-256: `e5b632373931fc9ab25d4dfa6a33cda58631dc9896e3fc8399adf27683685831`.

Code review covered adapter factoring, exact DTOs, immutable provenance restoration
on generic save, preview-identity enforcement, revision checks, browser generation
guards and existing assignment/review integration. No mandatory source defect was
found. An initial inventory omitted regenerated `egg-info/PKG-INFO`; the coordinator
corrected the inventory and the reviewer independently verified the refreshed seal:
`805b5d8241f2b14b93ec5e92ea9627d37a0b8062b2338919793b1df2e7c7d51e`.

Python 3.14.4 executed checks; 3.12/3.13 unavailable, NOT_RUN. Rust/native GPU NOT_RUN
for this adapter/UI slice. Accepted M5 evidence retains its previous scope. This
verdict grants no artistic approval, new native compatibility claim or full M6 closure.

Kaneo was independently read in QA Review with Codex ownership
`aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn`. All four criteria are supported; coordinator may
synchronize objective engineering acceptance through the existing workflow.
