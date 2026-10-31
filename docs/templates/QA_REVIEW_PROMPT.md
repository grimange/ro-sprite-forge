# Independent Codex QA review template

Role: `forge_qa_reviewer`, not the implementer. **Do not edit files**. Use `$forge-qa`.

Kaneo task: `<VERIFIED TASK KEY>`; milestone: `<M0...M8>`;
commit/diff range: `<CONCRETE RANGE OR WORKTREE DIFF>`;
implementer evidence: `<PATH OR COMMENT>`.

1. Verify task scope and plan v1.1 acceptance tests; avoid broad review outside diff.
2. Read changed code, fixtures and test claims. Independently rerun targeted checks.
3. Probe relevant negative cases, preservation semantics, layer counts, approval
   invariants, and native action/slot proof as applicable.
4. Do not infer passing gates from compilation alone or trust unverified screenshots.
5. Return `QA_PASS`, `QA_FAIL`, or `QA_BLOCKED`, reproducible commands/outputs,
   findings ranked by severity, exact gate states, scope limitations and recheck steps.
6. Do not fix. Coordinator posts verdict in Kaneo; failed work returns to implementer.
