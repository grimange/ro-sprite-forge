# Kaneo PMP tracking for Sprite Forge development

This is an **external development workflow**, not a requirement for the Python Sprite
Forge runtime. The v1.1 plan intentionally does not include Kaneo as an application dependency.

## Source and connection

- Human UI: `https://pmp.kaneo.local.test`
- MCP URL: `https://pmp.kaneo.local.test/api/mcp`
- MCP name in Codex: `kaneo-local`
- Workspace: `Personal Projects`
- Intended project: `RO Sprite Forge` (**discover by live query**; project ID not known here)
- Auth is operator-controlled through Codex's MCP login/session. No secrets in Git.
- Codex CLI examples from the operator's established setup:
  `codex mcp add kaneo-local --url https://pmp.kaneo.local.test/api/mcp`
  `codex mcp login kaneo-local`
  `codex mcp list`
- When repo-local `.codex/config.toml` already declares the same server, do **not** add a
  second MCP entry blindly; inspect `codex mcp list` and authenticate existing connection.
- Host-local DNS, TLS CA and authentication must be valid from the worker machine.
  Never turn off certificate verification to work around configuration errors.

## Discovery before any write

Ask MCP for the workspace, project, actual columns/statuses, current task, assignee and
acceptance criteria. Do not invent IDs, keys, project membership or tool names. If the
project is missing, obtain operator authorization to create one. If the board uses different
names, map using live evidence instead of force-renaming the board. Do not automatically
create M0–M8 tasks: task seeding requires operator direction per plan v1.1 §6.

## Kanban mapping (desired, not proof that columns already exist)

Before implementation, discover the authenticated worker with `whoami` and verify its
workspace membership. Codex claims work as the Codex worker; Antigravity uses the Google
Antigravity worker. Never invent an account ID or assign AI work to the human operator.
If another worker owns the task, investigate before changing ownership. Self-assign,
read back the assignee, then transition through Ready to In Progress and verify both.
Preserve the implementer's assignment during independent QA and verify it again before
acceptance. Tracking outages may leave local work sync-pending, never falsely assigned.

| Existing desired column | Semantics | Who transitions |
|---|---|---|
| Backlog | Not yet approved as current implementation slice | Planner/operator |
| Ready | Scope and acceptance clear; queued | Planner/operator |
| In Progress | Implementer has claimed task | Implementer |
| QA Review | Implemented, tested and evidence posted; awaiting independent check | Implementer |
| Accepted | Independent QA PASS recorded; any human-only approval obtained | Reviewer result → orchestrator/operator |
| FAILED | Reproducible QA failure posted, needs root-cause correction | Orchestrator after review |
| Cancelled | Explicitly abandoned with reason | Operator |

A task must not jump from `In Progress` to `Accepted` based on implementer self-tests.
For engineering-only objective gates, independently reproducible QA PASS implies acceptance
without another bureaucratic approval. For artwork aesthetics or native decisions explicitly
reserved to the operator, request human approval before accepting that scope. If `FAILED`
does not exist, leave in QA Review with a failing comment and notify the operator.

## Smallest useful task unit

One bounded behavior/defect with tests and exact acceptance. Link to one milestone M0–M8.
Examples: M0 source provenance; M0 lossless preservation; M0 Rust independent decoder;
M0 pinned native smoke; M1 ordered layer-topology contract. These are examples, not
instructions to create tasks automatically.

Preferred task description: paste `docs/templates/KANEO_TASK.md`; evidence belongs in
a final comment, not dozens of live progress comments.

## One prompt, separate responsibilities

1. **Discover** live Kaneo state; claim a Ready task. If unavailable, set sync pending.
2. **Implementer** fixes one bounded scope, runs tests, posts evidence, enters QA Review.
3. **Independent reviewer** in a *separate agent/session* runs checks and reports result;
   does not modify code. Custom agent instructions are not OS-enforced read-only security.
4. **If fail** record repro (and FAILED column if available), implementer fixes root cause,
   then separate reviewer rechecks; avoid open-ended retries or silent status passing.
5. **If pass** record verified gate scope, move to Accepted where authorized/appropriate.
   Native and visual operator approvals remain distinct where explicitly required.

## When Kaneo is offline

Continue local authorized code/test work when possible. Final report must contain:

```text
KANEO_SYNC_PENDING
Workspace: Personal Projects
Project: RO Sprite Forge (unverified if not discovered)
Task ID/key: <known verified value OR unknown>
Current known status: <from last successful read OR unknown>
Desired transition: <actual column name if verified OR proposed>
Evidence to post: <paths/commands/exit statuses/hashes/review verdict>
Blocker: <MCP/TLS/auth/unavailable state>
```

Never say a task was created, commented, moved, or accepted unless a real tool call
returned success, ideally with read-back.
