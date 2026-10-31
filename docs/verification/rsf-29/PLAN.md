# RSF-29 bounded implementation plan

Live task and Ready/In Progress ownership readbacks are in kaneo-start.json.
Baseline source/test/script hashes are in baseline.json; copies are retained at
/tmp/rsf29-baseline for bounded diff review. No commits or history changes.

1. Reuse RSF-28 inspection/extraction/staging. Add metadata-only stream probing,
   exact decimal-string HTTP transport and revision-aware preview/stage endpoints.
2. Add a focused workbench section for upload/staged video, explicit stream/frame
   inspection, exact selections, real PNG preview, reordering/removal and confirmed
   staging. Reuse the existing source tray, M4 recipes and assignment/review controls.
3. Test exact VFR/nonchronological pixels, integer precision and supported bounds,
   preview/commit separation, immutable save/reopen, timing separation and failures.
4. Run real Chromium journeys, public/private/schema/distribution regressions;
   retain commands, hashes and browser evidence. Keep M5 accepted scope unchanged.
5. Hand off to separate read-only forge_qa_reviewer; correct/retest findings, then
   synchronize evidence-backed acceptance and retrieve (do not start) the next task.

No new decoder, database, timing engine, automatic assignment or artistic decision.
RSF-28's selection integer bound remains ±(2**53−1); unsupported large selections
are rejected before conversion, while source metadata is displayed losslessly.
