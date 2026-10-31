# Cross-worker handoff — Codex ↔ Antigravity ↔ independent QA

Either Codex or Antigravity may implement an authorized task. The reviewer must be a
different agent or separate session, must inspect the same actual revision, and must not
modify code. Cross-vendor review is welcome but not mandatory. Do not count one worker's
self-reflection as independent QA. For strict isolation use a separate read-only checkout.

Handoff packet: real Kaneo task, milestone criteria, paths and exact Git diff/revision,
private-fixture availability without copying art, executable tests+exit codes, observed
artifact hashes, provenance, gate states, and remaining known risks. Leave unrelated
working-tree changes untouched. Keep a bounded implement->test->QA->fix->QA loop within
one coordinator prompt. Do not have reviewer commit fixes or implementer declare PASS
on behalf of reviewer. Operator approves visual art and any explicitly operator-owned
native acceptance separately.

If `AGENTS.md` from the Codex kit and `GEMINI.md` are both present, preserve both and
resolve contradictions by asking for the intended rule instead of silently weakening one.
The `.agents/skills/agy-forge-*` names are intentionally distinct from the Codex
`forge-*` skills; both may coexist without overwriting the other's skill files.
