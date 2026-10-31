# RSF-28 bounded implementation plan

Live task mdehayoorrfc43z930ij72wx has four mandatory criteria. Sole blocking
dependency RSF-26 was read back Accepted. Authenticated Codex account
aM3as9DCoQ7pMoO3V9XsDbL3q2j9pWjn claimed the unassigned task; assignment,
Ready and In Progress were each read back before source edits.

1. Add optional local media adapter with bounded subprocess execution, actual
   FFprobe stream/frame PTS and explicit ordinal/exact-PTS selection.
2. Extract validated RGBA PNG candidates without FPS conversion; verify native
   selection observations, preserve canonical toolchain/request/output provenance.
3. Reuse existing blob/project/sequence APIs for atomic collection publication and
   existing source tray/explicit assignment. Add CLI entry points, no browser changes.
4. Test known CFR/VFR media, failure budgets/cleanup, immutability, determinism,
   optional absence; run public/private/schema/installed regressions.
5. Independent read-only forge_qa_reviewer execution, corrections/retest if needed,
   then sync evidence and acceptance with live Kaneo read-back.

M5 accepted resources and implementation remain preserved. M6 remains open after
this bounded adapter. No artistic decisions, choreography, approval or ACT timing
are derived from video. Existing untracked repository files are preserved.
