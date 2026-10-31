# Antigravity CLI ↔ Kaneo PMP workflow

**Kaneo is external development tracking, not part of the Sprite Forge application.**
MCP endpoint: `https://pmp.kaneo.local.test/api/mcp` (workspace profile in
`.agents/mcp_config.json`). UI: `https://pmp.kaneo.local.test`.
Workspace name: `Personal Projects`. Intended project: `RO Sprite Forge`.
**Do not assume the project exists or invent an ID.**

## Connection and discovery

1. From the repository root start `agy`, then `/mcp` to inspect connection status.
2. If already configured globally, compare definitions and use one active Kaneo
   connection; do not duplicate a conflicting one. Authentication is managed in
   Antigravity's MCP configuration/auth flow; no tokens in committed files.
3. Trust the host only with valid local DNS, certificate chain (mkcert CA installed on
   that machine), and authorized credentials. Never bypass TLS validation.
4. Through the live MCP tool list find workspaces, project, task, column definitions,
   assignee and task permissions. Tool names are provider-specific: discover them.
5. If the project/task is absent, report it and request explicit authorization before
   creating project or one bounded task. Never automatically seed the M0–M8 roadmap.

## Expected board (not an asserted observed state)

| Column | Meaning | Transition initiator |
|---|---|---|
| Backlog | Unapproved or future slice | Operator/planner |
| Ready | Explicitly selected for implementation | Operator/planner |
| In Progress | Worker has claimed bounded task | Implementer |
| QA Review | Implementation tests/evidence complete | Implementer |
| Accepted | Separate QA verified objective criteria, with human sign-off where needed | Coordinator after review |
| FAILED | Reproducible QA defect, awaiting root-cause fix | Coordinator |
| Cancelled | Deliberately discontinued | Operator |

If actual board differs, use actual columns; do not rename/create columns by default.
A task is **not Accepted** because implementer tests passed. Reviewer does not fix.

## One bounded task / one coordinated loop

1. Read task + current status. Verify milestone, scope, constraints and acceptance.
2. Implementer claims Ready task; implement only that slice and preserve unrelated edits.
3. Implementer runs focused tests; posts *one* concise evidence comment with changed
   paths, diff/revision, tests/exit codes, real hashes and gate states; move QA Review.
4. Invoke `forge-qa-reviewer` as separate read-only subagent, or hand to distinct
   reviewer session (Codex and Antigravity can cross-review if they inspect same revision).
   Reviewer inspects independently and reports QA_PASS/QA_FAIL/QA_BLOCKED.
5. FAIL: attach repro, move FAILED if exists, implementer fixes root cause, tests again,
   reviewer rechecks. Cap retries sensibly; do not silently change acceptance criteria.
6. PASS: sync evidence and Accepted only where actual board and human-only gates permit.
7. Read back the updated task; don't claim a transition without confirmed tool result.

Human-only approval of art, animation readability or requested native acceptance
requires actual operator confirmation. `M0-S`/`M0-I` technical PASS cannot imply `M0-N`
PASS. If human sign-off is out of task scope, objective task may be Accepted, with
those separate states still UNVERIFIED.

## Failed connection packet

```text
KANEO_SYNC_PENDING
Workspace: Personal Projects
Project: RO Sprite Forge (verified ID or UNKNOWN)
Task: <verified key/id or UNKNOWN>
Last observed column: <verified or UNKNOWN>
Intended operation: <specific create/comment/status change requiring authorization>
Evidence: <diff, tests, exit statuses, hashes, independent QA verdict>
Blocker: <MCP disconnected / TLS / auth / task missing / permissions>
```

Never say an MCP operation happened when it did not. Never stash auth secrets in Git.
